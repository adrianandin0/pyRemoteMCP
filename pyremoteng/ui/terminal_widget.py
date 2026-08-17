import builtins
import os
import re
import datetime
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QFileDialog, QMessageBox
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent, QInputMethodEvent
from PySide6.QtCore import Qt, Signal, QObject, QEvent
from pyremoteng.engine.ssh_engine import SSHEngine
from pyremoteng.config.settings import SettingsManager

def term_debug(msg: str):
    try:
        with open("/tmp/terminal_debug.log", "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

# Regex to split ANSI escape codes (keeps them as tokens)
ANSI_SPLIT_REGEX = re.compile(
    r'(\x1b\][^\x07]*\x07|'          # OSC Operating System Commands (window titles)
    r'\x1b\[\??[0-9;]*[a-zA-Z]|'    # CSI Control Sequence Introducer
    r'\x1b[()<>=][0-9A-Z]|'         # Character set selection
    r'\x1b[M]|\x1b[78])'             # Save/restore cursor & mouse controls
)

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
    def __init__(self, engine: SSHEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        # Force all keys to bypass Wayland InputMethod and go directly to keyPressEvent
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        # The viewport natively handles events first, so we MUST filter it
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
        # Intentionally not calling super() to prevent native insertion
            
    def keyPressEvent(self, event: QKeyEvent):
        if not self.engine:
            return super().keyPressEvent(event)

        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        ctrl_pressed = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if ctrl_pressed and shift_pressed:
            if key == Qt.Key.Key_C:
                self.copy()
                return
            elif key == Qt.Key.Key_V:
                self.paste()
                return

        if ctrl_pressed and not shift_pressed:
            if key == Qt.Key.Key_C:
                self.engine.send_input("\x03")
                return
            elif key == Qt.Key.Key_D:
                self.engine.send_input("\x04")
                return
            elif key == Qt.Key.Key_Z:
                self.engine.send_input("\x1a")
                return
            elif key == Qt.Key.Key_L:
                self.engine.send_input("\x0c")
                return
            elif key == Qt.Key.Key_U:
                self.engine.send_input("\x15")
                return
            elif key == Qt.Key.Key_A:
                self.engine.send_input("\x01")
                return
            elif key == Qt.Key.Key_E:
                self.engine.send_input("\x05")
                return

        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            term_debug("SENDING: \\r (Enter)")
            self.engine.send_input("\r")
            return
        elif key == Qt.Key.Key_Backspace:
            term_debug("SENDING: \\x7f (Backspace)")
            self.engine.send_input("\x7f")
            return
        elif key == Qt.Key.Key_Delete:
            term_debug("SENDING: \\x1b[3~ (Delete)")
            self.engine.send_input("\x1b[3~")
            return
        elif key == Qt.Key.Key_Escape:
            term_debug("SENDING: \\x1b (Escape)")
            self.engine.send_input("\x1b")
            return
        elif key == Qt.Key.Key_Tab:
            term_debug("SENDING: \\t (Tab)")
            self.engine.send_input("\t")
            return
        elif key == Qt.Key.Key_Up:
            self.engine.send_input("\x1b[A")
            return
        elif key == Qt.Key.Key_Down:
            self.engine.send_input("\x1b[B")
            return
        elif key == Qt.Key.Key_Right:
            self.engine.send_input("\x1b[C")
            return
        elif key == Qt.Key.Key_Left:
            self.engine.send_input("\x1b[D")
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
        elif text:
            term_debug(f"SENDING TEXT: {repr(text)}")
            self.engine.send_input(text)
            return
            
        event.accept()

class TerminalWidget(QWidget):
    """
    Interactive Terminal Widget for SSH & Telnet sessions in Qt.
    Supports ANSI escape codes, configurable scrollback (including infinite lines for Cisco configs),
    automatic file logging, TXT export, themes, and complete keyboard PTY forwarding.
    """
    title_changed = Signal(str)
    session_closed = Signal()

    def __init__(self, node, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.node = node
        self.settings = settings_manager or SettingsManager()

        self.bridge = OutputBridge(self)
        self.bridge.output_received.connect(self.append_text)

        self.engine: SSHEngine = SSHEngine(
            hostname=node.hostname,
            port=node.port,
            username=node.username,
            password=node.password,
            key_filename=getattr(node, "private_key_file", ""),
            legacy_mode=getattr(node, "legacy_ssh", True),
            protocol=getattr(node, "protocol", "SSH2")
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

        # Set maximum block (line) count: 0 means infinite scrollback lines
        max_lines = self.settings.scrollback_lines
        self.text_edit.setMaximumBlockCount(max_lines)

        style = THEME_STYLES.get(self.settings.theme, THEME_STYLES["Dark"])
        self.text_edit.setStyleSheet(style)

    def _init_session_logger(self):
        try:
            log_dir = self.settings.log_directory
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_host = re.sub(r'[^a-zA-Z0-9_\.-]', '_', self.node.hostname or self.node.name)
            filename = f"{clean_host}_{timestamp}.log"
            filepath = os.path.join(log_dir, filename)
            self.log_file = open(filepath, "a", encoding="utf-8")
        except Exception:
            self.log_file = None

    def start_session(self):
        """Starts SSH connection."""
        self.append_text(f"Connecting to {self.node.hostname}:{self.node.port} via {self.node.protocol}...\n")
        connected = self.engine.connect(on_output=self.bridge.output_received.emit)
        if not connected:
            self.session_closed.emit()

    def append_text(self, text: str):
        """Appends output text onto terminal screen and writes to session log file."""
        term_debug(f"RECV: {repr(text)}")
        cursor = self.text_edit.textCursor()

        tokens = ANSI_SPLIT_REGEX.split(text)
        cleaned_for_log = ""
        
        for token in tokens:
            if not token:
                continue
                
            if token.startswith('\x1b'):
                if token == '\x1b[D':
                    cursor.movePosition(QTextCursor.MoveOperation.Left)
                elif token == '\x1b[C':
                    cursor.movePosition(QTextCursor.MoveOperation.Right)
                elif token == '\x1b[K':
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                elif token == '\x1b[H':
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                continue

            cleaned_for_log += token
            i = 0
            while i < len(token):
                char = token[i]
                
                if char == '\r' and i + 1 < len(token) and token[i+1] == '\n':
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.insertText('\n')
                    i += 2
                    continue
                    
                if char == '\x08' or char == '\b' or char == '\x7f':
                    if not cursor.atBlockStart():
                        cursor.movePosition(QTextCursor.MoveOperation.Left)
                elif char == '\r':
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
                elif char == '\n':
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.insertText('\n')
                elif char == '\x07':
                    pass # Ignore BELL
                else:
                    if ord(char) >= 32 or char == '\t':
                        if cursor.position() < self.text_edit.document().characterCount() - 1 and not cursor.atBlockEnd():
                            cursor.deleteChar()
                        cursor.insertText(char)
                i += 1

        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        # Write to log file if enabled
        if self.log_file and not self.log_file.closed and cleaned_for_log:
            try:
                self.log_file.write(cleaned_for_log)
                self.log_file.flush()
            except Exception:
                pass

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
