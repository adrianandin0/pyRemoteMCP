from PySide6.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QSplitter, QPlainTextEdit, QGroupBox
)
from PySide6.QtGui import QIcon, QTextCursor
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from typing import Optional
from pyremotempc.config.models import ConnectionNode
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.ui.terminal_widget import TerminalWidget
from pyremotempc.ui.sftp_widget import SFTPWidget
from pyremotempc.engine.rdp_engine import RDPEngine
from pyremotempc.engine.vnc_engine import VNCEngine


import ctypes

class OutputBridge(QObject):
    """Bridge QObject to thread-safely emit signals from background thread to Qt GUI thread."""
    output_received = Signal(str)


class X11EmbedWidget(QWidget):
    """A QWidget that resizes its foreign X11 children when it gets resized."""
    
    # Signal emitted when the widget size settles (after a resize debounce)
    size_settled = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_settled)

    def _on_resize_settled(self):
        self.size_settled.emit(self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(500)  # 500ms debounce
        try:
            from ctypes import cdll, c_void_p, c_ulong, c_int, c_uint, POINTER, byref, c_char_p
            x11 = cdll.LoadLibrary("libX11.so.6")
            
            x11.XOpenDisplay.argtypes = [c_char_p]
            x11.XOpenDisplay.restype = c_void_p
            x11.XCloseDisplay.argtypes = [c_void_p]
            x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
            x11.XQueryTree.restype = c_int
            x11.XMoveResizeWindow.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint]
            x11.XFree.argtypes = [c_void_p]
            
            display = x11.XOpenDisplay(None)
            if not display:
                return
            
            def resize_tree(win):
                root_r = c_ulong()
                parent_r = c_ulong()
                children_r = POINTER(c_ulong)()
                nchildren_r = c_uint()
                if x11.XQueryTree(display, win, byref(root_r), byref(parent_r), byref(children_r), byref(nchildren_r)) != 0:
                    for i in range(nchildren_r.value):
                        child = children_r[i]
                        x11.XMoveResizeWindow(display, child, 0, 0, self.width(), self.height())
                        resize_tree(child)
                    x11.XFree(children_r)

            resize_tree(c_ulong(int(self.winId())))
            x11.XCloseDisplay(display)
        except Exception:
            pass


class SessionTabWidget(QTabWidget):
    """
    Tab Bar Container for Active Sessions (SSH, RDP, VNC, etc.).
    Supports per-session SFTP File Transfer drawers, RDP session containers, and TXT export.
    """

    def __init__(self, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.settings = settings_manager or SettingsManager()
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self._show_welcome_tab()

    def _show_welcome_tab(self):
        lang = self.settings.language
        welcome_widget = QFrame()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel(tr("welcome_title", lang))
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #3b82f6;")
        lbl_sub = QLabel(tr("welcome_sub", lang))
        lbl_sub.setStyleSheet("font-size: 14px; color: #6b7280;")

        layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub, alignment=Qt.AlignmentFlag.AlignCenter)

        idx = self.addTab(welcome_widget, QIcon.fromTheme("help-about"), "Welcome")
        self.tabBar().setTabButton(idx, self.tabBar().ButtonPosition.RightSide, None)

    def open_session(self, node: ConnectionNode):
        """Opens a new session tab for the specified ConnectionNode."""
        if self.count() == 1 and self.tabText(0) in ("Welcome", "Bienvenido"):
            self.removeTab(0)

        proto = node.protocol.upper()
        if "SSH" in proto or proto == "TELNET":
            self._open_ssh_session(node)
        elif proto == "RDP":
            self._open_rdp_session(node)
        elif proto == "VNC":
            self._open_vnc_session(node)
        else:
            self._open_ssh_session(node)

    def _open_ssh_session(self, node: ConnectionNode):
        lang = self.settings.language
        session_container = QWidget(self)
        vbox = QVBoxLayout(session_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Per-tab action bar
        action_bar = QWidget(session_container)
        action_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3c3c3c;")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(f"<b>{node.name}</b> ({node.hostname}:{node.port})", action_bar)
        lbl_info.setStyleSheet("color: #cccccc;")
        act_layout.addWidget(lbl_info)
        act_layout.addStretch()

        btn_sftp = QPushButton(tr("sftp_manager", lang), action_bar)
        btn_sftp.setToolTip("Toggle integrated SFTP file manager for this active tab")
        act_layout.addWidget(btn_sftp)

        btn_export = QPushButton(tr("export_txt", lang), action_bar)
        btn_export.setToolTip("Export terminal output to TXT file")
        act_layout.addWidget(btn_export)

        vbox.addWidget(action_bar)

        # Vertical Splitter: Terminal on Top, SFTP File Manager on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical, session_container)

        term = TerminalWidget(node, self.settings, splitter)
        splitter.addWidget(term)

        # Pass term.engine & settings_manager to SFTPWidget
        sftp_panel = SFTPWidget(node, ssh_engine=term.engine, settings_manager=self.settings, parent=splitter)
        sftp_panel.setVisible(False)
        splitter.addWidget(sftp_panel)

        vbox.addWidget(splitter)

        # Wire Action Bar Buttons
        btn_export.clicked.connect(term.export_to_txt)
        btn_sftp.clicked.connect(lambda: self._toggle_sftp(sftp_panel))

        # Store handles on container widget for closing
        session_container.term = term
        session_container.sftp_panel = sftp_panel

        idx = self.addTab(session_container, QIcon.fromTheme("utilities-terminal"), f"{node.name} ({node.hostname})")
        self.setCurrentIndex(idx)
        term.start_session()

    def _toggle_sftp(self, sftp_panel: SFTPWidget):
        is_visible = sftp_panel.isVisible()
        sftp_panel.setVisible(not is_visible)
        if not is_visible and not sftp_panel.sftp_engine.is_connected:
            sftp_panel.connect_sftp()

    def _open_rdp_session(self, node: ConnectionNode):
        lang = self.settings.language
        rdp_container = QWidget(self)
        vbox = QVBoxLayout(rdp_container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Top Control Bar
        action_bar = QWidget(rdp_container)
        action_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3c3c3c;")
        act_layout = QHBoxLayout(action_bar)
        act_layout.setContentsMargins(6, 2, 6, 2)

        lbl_info = QLabel(f"<b>RDP: {node.name}</b> ({node.hostname}:{node.port})", action_bar)
        lbl_info.setStyleSheet("color: #cccccc;")
        act_layout.addWidget(lbl_info)
        act_layout.addStretch()

        btn_toggle_log = QPushButton("📜 " + tr("sftp_log_btn", lang).replace("📜 ", ""), action_bar)
        btn_toggle_log.setCheckable(True)
        btn_toggle_log.setChecked(True)
        act_layout.addWidget(btn_toggle_log)

        btn_reconnect = QPushButton(tr("reconnect_rdp", lang), action_bar)
        act_layout.addWidget(btn_reconnect)

        vbox.addWidget(action_bar)

        # Splitter: Embedded Window Area on Top, Live Diagnostic Log on Bottom
        splitter = QSplitter(Qt.Orientation.Vertical, rdp_container)

        embed_widget = X11EmbedWidget(splitter)
        embed_layout = QVBoxLayout(embed_widget)
        lbl_status = QLabel(f"Launching RDP to {node.hostname}:{node.port}...", embed_widget)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setStyleSheet("font-size: 14px; color: #3b82f6; background: #1e1e1e;")
        embed_layout.addWidget(lbl_status)
        splitter.addWidget(embed_widget)

        # RDP Log Console
        group_log = QGroupBox(tr("rdp_log_title", lang), splitter)
        log_vbox = QVBoxLayout(group_log)
        log_vbox.setContentsMargins(2, 2, 2, 2)

        txt_rdp_log = QPlainTextEdit(group_log)
        txt_rdp_log.setReadOnly(True)
        txt_rdp_log.setStyleSheet("background-color: #111111; color: #00ff66; font-family: Monospace; font-size: 11px;")
        log_vbox.addWidget(txt_rdp_log)
        splitter.addWidget(group_log)
        
        btn_toggle_log.toggled.connect(group_log.setVisible)

        splitter.setSizes([500, 200])
        vbox.addWidget(splitter)

        def append_rdp_log_safe(text: str):
            cursor = txt_rdp_log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            txt_rdp_log.setTextCursor(cursor)
            txt_rdp_log.ensureCursorVisible()

        rdp_bridge = OutputBridge(rdp_container)
        rdp_bridge.output_received.connect(append_rdp_log_safe)

        rdp_engine = RDPEngine(
            hostname=node.hostname,
            port=node.port,
            username=node.username,
            password=node.password,
            domain=node.domain,
            rdp_security=getattr(node, "rdp_security", "Auto"),
            redirect_drives=getattr(node, "redirect_drives", False)
        )
        rdp_container.rdp_engine = rdp_engine

        def start_rdp():
            txt_rdp_log.clear()
            win_id = None
            try:
                win_id = int(embed_widget.winId())
            except Exception:
                pass
            w = embed_widget.width()
            h = embed_widget.height()
            if w < 100 or h < 100:
                # Fallback to a high resolution if the layout hasn't settled yet
                w = 1920
                h = 1080
            rdp_engine.start_session(on_output=rdp_bridge.output_received.emit, win_id=win_id, width=w, height=h)

        btn_reconnect.clicked.connect(start_rdp)
        
        def on_embed_resized(w, h):
            if not rdp_engine.process or rdp_engine.process.poll() is not None:
                return
            # If size changed significantly (more than 10 pixels), reconnect
            if abs(w - rdp_engine.width) > 10 or abs(h - rdp_engine.height) > 10:
                rdp_bridge.output_received.emit(f"\n[INFO] Auto-reconnecting to resize desktop to {w}x{h} (Windows 7 compatibility)...\n")
                rdp_engine.stop_session()
                start_rdp()

        embed_widget.size_settled.connect(on_embed_resized)

        idx = self.addTab(rdp_container, QIcon.fromTheme("computer"), f"RDP: {node.name}")
        self.setCurrentIndex(idx)
        start_rdp()

    def _open_vnc_session(self, node: ConnectionNode):
        vnc_container = QWidget(self)
        layout = QVBoxLayout(vnc_container)
        lbl = QLabel(f"Launching VNC Viewer to {node.hostname}:{node.port}...")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        idx = self.addTab(vnc_container, QIcon.fromTheme("network-server"), f"VNC: {node.name}")
        self.setCurrentIndex(idx)

        vnc_engine = VNCEngine(hostname=node.hostname, port=node.port, password=node.password)
        vnc_container.vnc_engine = vnc_engine
        vnc_engine.start_session(win_id=vnc_container.winId())

    def close_tab(self, index: int):
        widget = self.widget(index)
        if hasattr(widget, "term"):
            widget.term.close()
        if hasattr(widget, "sftp_panel"):
            widget.sftp_panel.close()
        if hasattr(widget, "rdp_engine"):
            widget.rdp_engine.stop_session()
        if hasattr(widget, "vnc_engine"):
            widget.vnc_engine.stop_session()

        self.removeTab(index)

        if self.count() == 0:
            self._show_welcome_tab()
