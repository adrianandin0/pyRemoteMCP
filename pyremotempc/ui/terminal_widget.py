import builtins
import os
import re
import datetime
from typing import Optional
from collections import defaultdict
import pyte
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QFileDialog, QMessageBox
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent, QInputMethodEvent
from PySide6.QtCore import Qt, Signal, QObject, QEvent
from pyremotempc.engine.ssh_engine import SSHEngine
from pyremotempc.engine.ssh1_engine import SSH1Engine
from pyremotempc.engine.telnet_engine import TelnetEngine
from pyremotempc.config.settings import SettingsManager


def term_debug(msg: str):
    try:
        with open("/tmp/terminal_debug.log", "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


THEME_STYLES = {
    "Dark": "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; selection-background-color: #264f78; }",
    "Classic Green": "QPlainTextEdit { background-color: #0c100c; color: #00ff66; selection-background-color: #005522; }",
    "Amber": "QPlainTextEdit { background-color: #120c02; color: #ffb000; selection-background-color: #664400; }",
    "Light": "QPlainTextEdit { background-color: #f5f5f5; color: #111111; selection-background-color: #b3d7ff; }",
}


class OutputBridge(QObject):
    """Bridge QObject to thread-safely emit signals from SSH background thread to Qt GUI thread."""
    output_received = Signal(str)


class SSHPlainTextEdit(QPlainTextEdit):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._terminal_widget = parent
        # Force all keys to bypass Wayland InputMethod and go directly to keyPressEvent
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        # The viewport natively handles events first, so we filter it
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.viewport():
            if event.type() == QEvent.Type.KeyPress:
                self.keyPressEvent(event)
                return True
            elif event.type() == QEvent.Type.InputMethod:
                self.inputMethodEvent(event)
                return True
        return super().eventFilter(obj, event)

    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            if self.engine:
                self.engine.send_input(text)
        else:
            super().insertFromMimeData(source)

    def inputMethodEvent(self, event):
        """Catch text inserted via Input Method (Wayland) that bypasses keyPressEvent."""
        text = event.commitString()
        if text and self.engine:
            term_debug(f"SENDING TEXT (IME): {repr(text)}")
            self.engine.send_input(text)

    def keyPressEvent(self, event: QKeyEvent):
        if not self.engine:
            return super().keyPressEvent(event)

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt_pressed = bool(modifiers & Qt.KeyboardModifier.AltModifier)

        # Ctrl+Shift+C -> Copy, Ctrl+Shift+V -> Paste
        if ctrl_pressed and shift_pressed:
            if key == Qt.Key.Key_C:
                self.copy()
                return
            elif key == Qt.Key.Key_V:
                self.paste()
                return

        # Handle Ctrl + Key combinations (A-Z)
        if ctrl_pressed and not shift_pressed and not alt_pressed:
            if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                ctrl_code = chr(key - Qt.Key.Key_A + 1)
                self.engine.send_input(ctrl_code)
                return
            elif key == Qt.Key.Key_BracketLeft:
                self.engine.send_input("\x1b")
                return
            elif key == Qt.Key.Key_Backslash:
                self.engine.send_input("\x1c")
                return
            elif key == Qt.Key.Key_BracketRight:
                self.engine.send_input("\x1d")
                return

        # Check DECCKM (Application Cursor Keys Mode) tracked by pyte
        is_app_cursor = False
        if hasattr(self._terminal_widget, "screen") and self._terminal_widget.screen:
            is_app_cursor = bool({1, 32} & set(self._terminal_widget.screen.mode))

        # Arrow Keys
        if key == Qt.Key.Key_Up:
            self.engine.send_input("\x1bOA" if is_app_cursor else "\x1b[A")
            return
        elif key == Qt.Key.Key_Down:
            self.engine.send_input("\x1bOB" if is_app_cursor else "\x1b[B")
            return
        elif key == Qt.Key.Key_Right:
            self.engine.send_input("\x1bOC" if is_app_cursor else "\x1b[C")
            return
        elif key == Qt.Key.Key_Left:
            self.engine.send_input("\x1bOD" if is_app_cursor else "\x1b[D")
            return

        # Special Navigation Keys
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.engine.send_input("\r")
            return
        elif key == Qt.Key.Key_Backspace:
            self.engine.send_input("\x7f")
            return
        elif key == Qt.Key.Key_Delete:
            self.engine.send_input("\x1b[3~")
            return
        elif key == Qt.Key.Key_Insert:
            self.engine.send_input("\x1b[2~")
            return
        elif key == Qt.Key.Key_Escape:
            self.engine.send_input("\x1b")
            return
        elif key == Qt.Key.Key_Tab:
            if shift_pressed:
                self.engine.send_input("\x1b[Z")
            else:
                self.engine.send_input("\t")
            return
        elif key == Qt.Key.Key_PageUp:
            self.engine.send_input("\x1b[5~")
            return
        elif key == Qt.Key.Key_PageDown:
            self.engine.send_input("\x1b[6~")
            return
        elif key == Qt.Key.Key_Home:
            self.engine.send_input("\x1b[H")
            return
        elif key == Qt.Key.Key_End:
            self.engine.send_input("\x1b[F")
            return

        # Function Keys (F1 - F12)
        elif key == Qt.Key.Key_F1:
            self.engine.send_input("\x1bOP")
            return
        elif key == Qt.Key.Key_F2:
            self.engine.send_input("\x1bOQ")
            return
        elif key == Qt.Key.Key_F3:
            self.engine.send_input("\x1bOR")
            return
        elif key == Qt.Key.Key_F4:
            self.engine.send_input("\x1bOS")
            return
        elif key == Qt.Key.Key_F5:
            self.engine.send_input("\x1b[15~")
            return
        elif key == Qt.Key.Key_F6:
            self.engine.send_input("\x1b[17~")
            return
        elif key == Qt.Key.Key_F7:
            self.engine.send_input("\x1b[18~")
            return
        elif key == Qt.Key.Key_F8:
            self.engine.send_input("\x1b[19~")
            return
        elif key == Qt.Key.Key_F9:
            self.engine.send_input("\x1b[20~")
            return
        elif key == Qt.Key.Key_F10:
            self.engine.send_input("\x1b[21~")
            return
        elif key == Qt.Key.Key_F11:
            self.engine.send_input("\x1b[23~")
            return
        elif key == Qt.Key.Key_F12:
            self.engine.send_input("\x1b[24~")
            return

        # Alt + key prefix
        elif alt_pressed and text:
            self.engine.send_input("\x1b" + text)
            return

        # Standard text input
        elif text:
            self.engine.send_input(text)
            return

        event.accept()


class TerminalWidget(QWidget):
    """
    Interactive VT100 / xterm Terminal Widget for SSH & Telnet sessions in pyRemoteMPC.
    Uses 'pyte' full screen terminal emulator for perfect vim, htop, nano, bash navigation,
    scrollback history, automatic file logging, TXT export, themes, and keyboard PTY forwarding.
    """
    title_changed = Signal(str)
    session_closed = Signal()

    def __init__(self, node, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.node = node
        self.settings = settings_manager or SettingsManager()

        self.bridge = OutputBridge(self)
        self.bridge.output_received.connect(self.append_text)

        # Setup pyte VT100/xterm screen emulator
        scroll_limit = self.settings.scrollback_lines if self.settings.scrollback_lines > 0 else 100000
        self.screen = pyte.HistoryScreen(80, 24, history=scroll_limit)
        self.stream = pyte.Stream(self.screen)

        proto = (node.protocol or "SSH2").upper()
        key_file = getattr(node, "key_path", "") or getattr(node, "private_key_file", "")

        if proto == "TELNET":
            self.engine = TelnetEngine(
                hostname=node.hostname,
                port=node.port if node.port else 23,
                username=node.username,
                password=node.password
            )
        elif proto == "SSH1":
            self.engine = SSH1Engine(
                hostname=node.hostname,
                port=node.port if node.port else 22,
                username=node.username,
                password=node.password,
                key_filename=key_file
            )
        else:
            self.engine = SSHEngine(
                hostname=node.hostname,
                port=node.port if node.port else 22,
                username=node.username,
                password=node.password,
                key_filename=key_file,
                legacy_mode=getattr(node, "legacy_ssh", True),
                protocol=proto
            )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = SSHPlainTextEdit(self.engine, self)
        self.apply_settings()

        self.text_edit.setUndoRedoEnabled(False)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_edit)

        # File Logging Setup
        self.log_file = None
        if self.settings.enable_logging:
            self._init_session_logger()

    def apply_settings(self):
        """Applies font, size, scrollback buffer lines and theme from settings."""
        font = QFont(self.settings.font_family, self.settings.font_size)
        self.text_edit.setFont(font)

        style = THEME_STYLES.get(self.settings.theme, THEME_STYLES["Dark"])
        self.text_edit.setStyleSheet(style)

    def _init_session_logger(self):
        try:
            log_dir = self.settings.log_directory
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                log_dir = os.path.expanduser("~/.config/pyremotempc/logs")
                os.makedirs(log_dir, exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            proto = (self.node.protocol or "SSH2").upper()
            clean_host = re.sub(r'[^a-zA-Z0-9_\.-]', '_', self.node.hostname or self.node.name or "session")
            filename = f"{proto}_{clean_host}_{timestamp}.log"
            filepath = os.path.join(log_dir, filename)
            self.log_file = open(filepath, "a", encoding="utf-8")
        except Exception:
            self.log_file = None

    def _safe_resize_screen(self, new_lines: int, new_columns: int):
        """
        Safely resizes pyte.HistoryScreen without destroying top lines when height decreases.
        Standard pyte.Screen.resize() calls delete_lines() from top, destroying terminal content.
        This method pushes cut-off lines to screen.history.top so zero content is lost.
        """
        old_lines = self.screen.lines
        old_columns = self.screen.columns

        if new_lines == old_lines and new_columns == old_columns:
            return

        # 1. Update columns if changed
        if new_columns != old_columns:
            self.screen.columns = new_columns
            for line in list(self.screen.buffer.values()):
                if new_columns < old_columns:
                    for x in range(new_columns, old_columns):
                        line.pop(x, None)

        # 2. Update lines if changed
        if new_lines != old_lines:
            if new_lines < old_lines:
                # Find max non-empty row index or cursor row
                max_row = self.screen.cursor.y
                for r in range(old_lines - 1, self.screen.cursor.y, -1):
                    row_str = "".join(self.screen.buffer[r][c].data for c in range(self.screen.columns)).rstrip()
                    if row_str:
                        max_row = r
                        break

                needed_lines = max_row + 1
                if needed_lines <= new_lines:
                    # Content fits in new height, trim bottom empty lines
                    for r in range(new_lines, old_lines):
                        self.screen.buffer.pop(r, None)
                    self.screen.lines = new_lines
                else:
                    # Content exceeds new height; push top overflow lines to history.top
                    shift = needed_lines - new_lines
                    for r in range(shift):
                        if r in self.screen.buffer:
                            self.screen.history.top.append(self.screen.buffer[r])

                    new_buf = defaultdict(self.screen.buffer.default_factory)
                    for r in range(shift, old_lines):
                        if r in self.screen.buffer:
                            new_buf[r - shift] = self.screen.buffer[r]
                    self.screen.buffer = new_buf
                    self.screen.lines = new_lines
                    self.screen.cursor.y = max(0, self.screen.cursor.y - shift)
            else:
                # Expanding height: pull lines from history.top back into display if available
                avail_history = len(self.screen.history.top)
                shift = min(avail_history, new_lines - old_lines)
                if shift > 0:
                    pulled_lines = [self.screen.history.top.pop() for _ in range(shift)][::-1]
                    new_buf = defaultdict(self.screen.buffer.default_factory)
                    for i, line in enumerate(pulled_lines):
                        new_buf[i] = line
                    for r in range(old_lines):
                        if r in self.screen.buffer:
                            new_buf[r + shift] = self.screen.buffer[r]
                    self.screen.buffer = new_buf
                    self.screen.cursor.y = min(new_lines - 1, self.screen.cursor.y + shift)
                self.screen.lines = new_lines

        self.screen.dirty.update(range(new_lines))
        self.screen.set_margins()

    def _update_pty_dimensions(self):
        if not hasattr(self, "text_edit") or not hasattr(self, "screen"):
            return
        fm = self.text_edit.fontMetrics()
        char_w = max(1, fm.horizontalAdvance("M"))
        char_h = max(1, fm.height())
        vp_w = self.text_edit.viewport().width()
        vp_h = self.text_edit.viewport().height()

        if vp_w < 100 or vp_h < 100:
            win = self.window()
            if win and win.width() > 500:
                vp_w = max(800, win.width() - 300)
                vp_h = max(400, win.height() - 180)
            else:
                vp_w = 1200
                vp_h = 700

        cols = max(40, vp_w // char_w)
        rows = max(10, vp_h // char_h)

        if cols != self.screen.columns or rows != self.screen.lines:
            self._safe_resize_screen(rows, cols)
            if hasattr(self.engine, "resize_pty"):
                self.engine.resize_pty(cols, rows)
            self.append_text("")

    def start_session(self):
        """Starts SSH connection."""
        self._update_pty_dimensions()
        self.append_text(f"Connecting to {self.node.hostname}:{self.node.port} via {self.node.protocol}...\r\n")
        connected = self.engine.connect(
            on_output=self.bridge.output_received.emit,
            term_type="xterm-256color",
            width=self.screen.columns,
            height=self.screen.lines
        )
        if not connected:
            self.session_closed.emit()

    def append_text(self, text: str):
        """Feeds output into pyte VT100 screen emulator and updates QPlainTextEdit screen."""
        term_debug(f"RECV: {repr(text)}")
        self.stream.feed(text)

        # Clear scrollback history when clear command (\x1b[2J or \x1b[3J) is received
        if "\x1b[2J" in text or "\x1b[3J" in text:
            self.screen.history.top.clear()

        # Extract history lines and active screen display lines
        history_lines = [
            "".join(char.data for char in row.values()).rstrip()
            for row in self.screen.history.top
        ]
        screen_lines = [line.rstrip() for line in self.screen.display]

        # Trim trailing blank lines on active screen if cursor is above them
        cursor_y = self.screen.cursor.y
        max_active_row = cursor_y
        for r_idx in range(len(screen_lines) - 1, cursor_y, -1):
            if screen_lines[r_idx]:
                max_active_row = r_idx
                break

        active_screen_lines = screen_lines[:max_active_row + 1]
        full_lines = history_lines + active_screen_lines
        full_text = "\n".join(full_lines)

        self.text_edit.setPlainText(full_text)

        # Position text cursor to match pyte virtual cursor coordinates
        cursor_line_idx = len(history_lines) + cursor_y
        doc = self.text_edit.document()
        block = doc.findBlockByNumber(min(cursor_line_idx, max(0, doc.blockCount() - 1)))

        char_col = min(self.screen.cursor.x, max(0, block.length() - 1))
        pos = block.position() + char_col

        tc = self.text_edit.textCursor()
        tc.setPosition(pos)
        self.text_edit.setTextCursor(tc)
        self.text_edit.ensureCursorVisible()

        # Write raw received text to session log file if enabled
        if self.log_file and not self.log_file.closed:
            try:
                self.log_file.write(text)
                self.log_file.flush()
            except Exception:
                pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pty_dimensions()

    def export_to_txt(self):
        """Prompts user and exports current session terminal buffer to a TXT file."""
        default_name = f"{self.node.name}_session.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Session Output to TXT", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return

        try:
            content = self.text_edit.toPlainText()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Export Successful", f"Session output saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save TXT file:\n{str(e)}")

    def closeEvent(self, event):
        if self.log_file and not self.log_file.closed:
            try:
                self.log_file.close()
            except Exception:
                pass
        self.engine.disconnect()
        super().closeEvent(event)
