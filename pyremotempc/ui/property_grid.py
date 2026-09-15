from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QScrollArea
)
import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from pyremotempc.config.models import ConnectionNode
from pyremotempc.ui.icon_manager import get_icon


class PropertyGridScrollContent(QWidget):
    """Container widget for QScrollArea that returns a 0 width sizeHint & minimumSizeHint so QScrollArea never overflows horizontally."""
    def sizeHint(self):
        s = super().sizeHint()
        return QSize(0, s.height())

    def minimumSizeHint(self):
        s = super().minimumSizeHint()
        return QSize(0, s.height())


class PropertyGridWidget(QWidget):
    """
    Property Grid Inspector Panel for selected connection/folder.
    Updates dynamically whenever a node is selected in the tree.
    All input fields expand fluidly to fill the sidebar width.
    """
    property_changed = Signal(ConnectionNode)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node: ConnectionNode = None
        self.loading: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = PropertyGridScrollContent()
        
        self.form_layout = QFormLayout(scroll_content)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form_layout.setContentsMargins(6, 6, 10, 6)
        self.form_layout.setSpacing(6)

        # General Group
        self.txt_name = QLineEdit()
        self.txt_name.setMinimumWidth(30)
        self.txt_name.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Name:", self.txt_name)

        self.txt_description = QLineEdit()
        self.txt_description.setMinimumWidth(30)
        self.txt_description.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Description:", self.txt_description)

        self.cmb_icon = QComboBox()
        self.cmb_icon.setMinimumWidth(30)
        self.cmb_icon.addItem(get_icon("windows"), "Windows")
        self.cmb_icon.addItem(get_icon("terminal"), "Terminal")
        self.cmb_icon.addItem(get_icon("vnc"), "VNC")
        self.cmb_icon.addItem(get_icon("connections"), "Connections")
        self.cmb_icon.addItem(get_icon("server"), "Server")
        self.cmb_icon.addItem(get_icon("linux"), "Linux")
        self.cmb_icon.addItem(get_icon("network"), "Router")
        self.cmb_icon.addItem(get_icon("network"), "Switch")
        self.cmb_icon.addItem(get_icon("vm"), "VM")
        self.cmb_icon.addItem(get_icon("storage"), "Storage")
        self.cmb_icon.addItem(get_icon("database"), "Database")
        self.cmb_icon.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Icon:", self.cmb_icon)

        # Connection Group
        self.txt_hostname = QLineEdit()
        self.txt_hostname.setMinimumWidth(30)
        self.txt_hostname.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Hostname / IP:", self.txt_hostname)

        self.cmb_protocol = QComboBox()
        self.cmb_protocol.setMinimumWidth(30)
        self.cmb_protocol.addItems(["SSH2", "SSH1", "RDP", "VNC", "Telnet", "HTTP", "HTTPS"])
        self.cmb_protocol.currentTextChanged.connect(self._on_protocol_changed)
        self.form_layout.addRow("Protocol:", self.cmb_protocol)

        self.spn_port = QSpinBox()
        self.spn_port.setMinimumWidth(30)
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(22)
        self.spn_port.valueChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Port:", self.spn_port)

        # Credentials Group
        self.txt_domain = QLineEdit()
        self.txt_domain.setMinimumWidth(30)
        self.txt_domain.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Domain:", self.txt_domain)

        self.txt_username = QLineEdit()
        self.txt_username.setMinimumWidth(30)
        self.txt_username.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Username:", self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setMinimumWidth(30)
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Password:", self.txt_password)

        # Private Key File Layout
        self.txt_private_key = QLineEdit()
        self.txt_private_key.setMinimumWidth(30)
        self.txt_private_key.textChanged.connect(self._on_field_edited)
        self.btn_browse_key = QPushButton("...")
        self.btn_browse_key.setFixedWidth(26)
        self.btn_browse_key.clicked.connect(self._on_browse_key)
        
        key_layout = QHBoxLayout()
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(2)
        key_layout.addWidget(self.txt_private_key)
        key_layout.addWidget(self.btn_browse_key)
        self.form_layout.addRow("Private Key File:", key_layout)

        # Protocol Specific Settings
        self.chk_legacy_ssh = QCheckBox("Enable Legacy Security")
        self.chk_legacy_ssh.setChecked(True)
        self.chk_legacy_ssh.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("SSH Options:", self.chk_legacy_ssh)

        self.cmb_rdp_sec = QComboBox()
        self.cmb_rdp_sec.setMinimumWidth(30)
        self.cmb_rdp_sec.addItems(["Auto", "NLA", "RDP", "TLS"])
        self.cmb_rdp_sec.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("RDP Security:", self.cmb_rdp_sec)

        # RDP SSL Certificate Options
        self.chk_rdp_cert_ignore = QCheckBox("Ignore Untrusted SSL Certs")
        self.chk_rdp_cert_ignore.setChecked(True)
        self.chk_rdp_cert_ignore.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("RDP SSL Cert:", self.chk_rdp_cert_ignore)

        self.txt_rdp_cert_path = QLineEdit()
        self.txt_rdp_cert_path.setMinimumWidth(30)
        self.txt_rdp_cert_path.setPlaceholderText("Path to custom CA / cert.crt")
        self.txt_rdp_cert_path.textChanged.connect(self._on_field_edited)
        self.btn_browse_cert = QPushButton("...")
        self.btn_browse_cert.setFixedWidth(26)
        self.btn_browse_cert.clicked.connect(self._on_browse_cert)

        cert_layout = QHBoxLayout()
        cert_layout.setContentsMargins(0, 0, 0, 0)
        cert_layout.setSpacing(2)
        cert_layout.addWidget(self.txt_rdp_cert_path)
        cert_layout.addWidget(self.btn_browse_cert)
        self.form_layout.addRow("Custom CA File:", cert_layout)

        self.chk_redirect_clipboard = QCheckBox("Redirect Clipboard (+clipboard)")
        self.chk_redirect_clipboard.setChecked(True)
        self.chk_redirect_clipboard.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("RDP Clipboard:", self.chk_redirect_clipboard)

        self.chk_redirect_drives = QCheckBox("Redirect Network Drive")
        self.chk_redirect_drives.setChecked(True)
        self.chk_redirect_drives.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("RDP Drive:", self.chk_redirect_drives)

        self.txt_rdp_shared_folder = QLineEdit()
        self.txt_rdp_shared_folder.setMinimumWidth(30)
        self.txt_rdp_shared_folder.setPlaceholderText("Global default (~/RDP_Shared)")
        self.txt_rdp_shared_folder.textChanged.connect(self._on_field_edited)
        self.btn_browse_rdp_folder = QPushButton("...")
        self.btn_browse_rdp_folder.setFixedWidth(26)
        self.btn_browse_rdp_folder.clicked.connect(self._on_browse_rdp_folder)

        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(2)
        folder_layout.addWidget(self.txt_rdp_shared_folder)
        folder_layout.addWidget(self.btn_browse_rdp_folder)
        self.form_layout.addRow("RDP Shared Folder:", folder_layout)

        # VNC Specific Settings
        self.cmb_vnc_engine = QComboBox()
        self.cmb_vnc_engine.setMinimumWidth(30)
        self.cmb_vnc_engine.addItems(["Auto", "Native", "System (TigerVNC / Remmina)"])
        self.cmb_vnc_engine.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("VNC Engine:", self.cmb_vnc_engine)

        self.cmb_vnc_sec = QComboBox()
        self.cmb_vnc_sec.setMinimumWidth(30)
        self.cmb_vnc_sec.addItems(["Auto", "Standard VNC Auth (Type 2)", "UltraVNC MSLogon (Type 11)"])
        self.cmb_vnc_sec.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("VNC Security:", self.cmb_vnc_sec)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def load_node(self, node: ConnectionNode):
        """Populates the property fields with data from node cleanly."""
        if not node:
            return

        self.loading = True
        self.current_node = node

        self.txt_name.setText(node.name or "")
        self.txt_description.setText(node.description or "")
        self.cmb_icon.setCurrentText(node.icon or "Server")
        self.txt_hostname.setText(node.hostname or "")
        self.cmb_protocol.setCurrentText(node.protocol or "SSH2")
        self.spn_port.setValue(node.port if node.port else 22)
        self.txt_username.setText(node.username or "")
        self.txt_password.setText(node.password or "")
        self.txt_domain.setText(node.domain or "")
        self.txt_private_key.setText(getattr(node, "private_key_file", ""))
        self.chk_legacy_ssh.setChecked(getattr(node, "legacy_ssh", True))
        self.cmb_rdp_sec.setCurrentText(getattr(node, "rdp_security", "Auto"))
        self.chk_rdp_cert_ignore.setChecked(getattr(node, "rdp_cert_ignore", True))
        self.txt_rdp_cert_path.setText(getattr(node, "rdp_cert_path", ""))
        self.chk_redirect_clipboard.setChecked(getattr(node, "redirect_clipboard", True))
        self.chk_redirect_drives.setChecked(getattr(node, "redirect_drives", True))
        self.txt_rdp_shared_folder.setText(getattr(node, "rdp_shared_folder", ""))
        self.cmb_vnc_engine.setCurrentText(getattr(node, "vnc_engine_type", "Auto"))
        self.cmb_vnc_sec.setCurrentText(getattr(node, "vnc_sec_type", "Auto"))

        is_conn = not node.is_container()
        self.txt_hostname.setEnabled(is_conn)
        self.cmb_protocol.setEnabled(is_conn)
        self.spn_port.setEnabled(is_conn)

        self.loading = False

    def _on_protocol_changed(self, protocol_str: str):
        if self.loading or not self.current_node:
            return

        self.current_node.protocol = protocol_str
        if protocol_str in ("SSH2", "SSH1"):
            self.spn_port.setValue(22)
            self.cmb_icon.setCurrentText("Terminal")
        elif protocol_str == "RDP":
            self.spn_port.setValue(3389)
            self.cmb_icon.setCurrentText("Windows")
        elif protocol_str == "VNC":
            self.spn_port.setValue(5900)
            self.cmb_icon.setCurrentText("VNC")
        elif protocol_str == "Telnet":
            self.spn_port.setValue(23)
            self.cmb_icon.setCurrentText("Connections")
        elif protocol_str == "HTTP":
            self.spn_port.setValue(80)
        elif protocol_str == "HTTPS":
            self.spn_port.setValue(443)

        self._on_field_edited()

    def _on_browse_key(self):
        if self.loading or not self.current_node:
            return
        
        from pyremotempc.ui.dialogs.key_selector_dialog import KeySelectorDialog
        dlg = KeySelectorDialog(
            parent=self,
            current_key_path=getattr(self.current_node, "key_path", "") or getattr(self.current_node, "private_key_file", ""),
            current_auth_method=getattr(self.current_node, "auth_method", "key")
        )
        if dlg.exec():
            self.current_node.auth_method = dlg.selected_auth_method
            self.current_node.key_path = dlg.selected_key_path
            self.current_node.private_key_file = dlg.selected_key_path
            if dlg.passphrase:
                self.current_node.key_passphrase = dlg.passphrase
            
            if dlg.selected_auth_method == "agent":
                self.txt_private_key.setText("[SSH Agent Identity]")
            else:
                self.txt_private_key.setText(dlg.selected_key_path)
            self._on_field_edited()

    def _on_browse_cert(self):
        if self.loading or not self.current_node:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SSL Certificate / CA File", os.path.expanduser("~"), "Certificates (*.crt *.pem *.cer *.key);;All Files (*)"
        )
        if file_path:
            self.txt_rdp_cert_path.setText(file_path)
            self._on_field_edited()

    def _on_browse_rdp_folder(self):
        if self.loading or not self.current_node:
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Select RDP Shared Directory", os.path.expanduser(self.txt_rdp_shared_folder.text() or "~")
        )
        if directory:
            self.txt_rdp_shared_folder.setText(directory)
            self._on_field_edited()

    def _on_field_edited(self):
        if self.loading or not self.current_node:
            return

        self.current_node.name = self.txt_name.text()
        self.current_node.description = self.txt_description.text()
        self.current_node.icon = self.cmb_icon.currentText()
        self.current_node.hostname = self.txt_hostname.text()
        self.current_node.protocol = self.cmb_protocol.currentText()
        self.current_node.port = self.spn_port.value()
        self.current_node.username = self.txt_username.text()
        self.current_node.password = self.txt_password.text()
        self.current_node.domain = self.txt_domain.text()
        self.current_node.private_key_file = self.txt_private_key.text()
        self.current_node.legacy_ssh = self.chk_legacy_ssh.isChecked()
        self.current_node.rdp_security = self.cmb_rdp_sec.currentText()
        self.current_node.rdp_cert_ignore = self.chk_rdp_cert_ignore.isChecked()
        self.current_node.rdp_cert_path = self.txt_rdp_cert_path.text()
        self.current_node.redirect_clipboard = self.chk_redirect_clipboard.isChecked()
        self.current_node.redirect_drives = self.chk_redirect_drives.isChecked()
        self.current_node.rdp_shared_folder = self.txt_rdp_shared_folder.text()
        self.current_node.vnc_engine_type = self.cmb_vnc_engine.currentText()
        self.current_node.vnc_sec_type = self.cmb_vnc_sec.currentText()
        self.property_changed.emit(self.current_node)
