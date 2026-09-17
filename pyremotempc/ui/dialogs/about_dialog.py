import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from pyremotempc.ui.icon_manager import get_icon
from pyremotempc.config.version import get_version


class AboutDialog(QDialog):
    """
    About pyRemoteMPC dialog displaying version, protocol features, author contacts, and graphic credits in English.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About pyRemoteMPC")
        self.setFixedSize(540, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Top Header: Icon + Title & Acronym Explanation
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        lbl_icon = QLabel(self)
        lbl_icon.setPixmap(get_icon("pyremotempc").pixmap(64, 64))
        header_layout.addWidget(lbl_icon, 0, Qt.AlignmentFlag.AlignTop)

        lbl_title = QLabel(self)
        lbl_title.setTextFormat(Qt.TextFormat.RichText)
        lbl_title.setOpenExternalLinks(True)

        version_str = get_version()

        title_html = f"""
        <div style="font-size: 11px; font-weight: normal; color: #ffffff;">
            <p style="margin: 0; font-size: 12px; line-height: 1.4;">
                <b>py</b>Remote<b>MPC</b> ( <b>py</b>thon <b>Remote</b> <b>M</b>ulti-<b>P</b>rotocol <b>C</b>onnections )
            </p>
            <p style="margin: 4px 0 0 0; color: #3b82f6; font-size: 11px;">
                Version: <b>{version_str}</b>
            </p>
        </div>
        """
        lbl_title.setText(title_html)
        header_layout.addWidget(lbl_title, 1)

        layout.addLayout(header_layout)

        # Description and Complete Supported Connection Types List
        lbl_body = QLabel(self)
        lbl_body.setWordWrap(True)
        lbl_body.setTextFormat(Qt.TextFormat.RichText)
        lbl_body.setOpenExternalLinks(True)

        body_html = """
        <div style="font-size: 11px; font-weight: normal; color: #cccccc; line-height: 1.4;">
            <p style="margin-top: 4px;">
                Native Python Multi-Protocol Remote Connections Manager for Linux.
            </p>
            <p style="margin-bottom: 4px;"><b>Supported Connection Protocols:</b></p>
            <ul style="margin-top: 2px; margin-bottom: 10px; padding-left: 20px;">
                <li><b>SSH2</b> &mdash; Interactive secure terminal sessions.</li>
                <li><b>SSH1</b> &mdash; Compatibility support for legacy devices and older network hardware.</li>
                <li><b>SFTP / FTP</b> &mdash; Integrated tabbed file manager per session.</li>
                <li><b>RDP</b> &mdash; Remote Desktop Protocol with native container window embedding.</li>
                <li><b>VNC</b> &mdash; Virtual Network Computing (UltraVNC / MSLogon / Standard VNC auth).</li>
                <li><b>TELNET</b> &mdash; Telnet terminal access.</li>
                <li><b>SERIAL</b> &mdash; Direct serial port communication (TTY / COM) with active port auto-detection.</li>
            </ul>
            <hr style="border: none; border-top: 1px solid #3c3c3c; margin: 8px 0;" />
            <p style="margin: 3px 0;"><b>Author:</b> Adrián Andino</p>
            <p style="margin: 3px 0;"><b>Contact:</b> <a style="color: #3b82f6; text-decoration: underline;" href="mailto:adrianandino@pm.me">adrianandino@pm.me</a></p>
            <p style="margin: 3px 0;"><b>X:</b> <a style="color: #3b82f6; text-decoration: underline;" href="https://x.com/adrian_and_ino">@adrian_and_ino</a></p>
            <p style="margin: 3px 0;"><b>GitHub:</b> <a style="color: #3b82f6; text-decoration: underline;" href="https://github.com/adrianandin0/pyRemoteMPC">https://github.com/adrianandin0/pyRemoteMPC</a></p>
            <hr style="border: none; border-top: 1px solid #3c3c3c; margin: 8px 0;" />
            <p style="margin: 3px 0; font-size: 10px; color: #888888;">
                Icons and graphical assets from <a style="color: #888888; text-decoration: underline;" href="https://www.flaticon.com/">Flaticon</a> by <a style="color: #888888; text-decoration: underline;" href="https://www.flaticon.com/authors/magnific">magnific</a>.
            </p>
        </div>
        """
        lbl_body.setText(body_html)
        layout.addWidget(lbl_body, 1)

        # OK / Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close", self)
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
