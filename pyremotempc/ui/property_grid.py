from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QScrollArea
)
import os
from pathlib import Path
from PySide6.QtCore import Signal
from pyremotempc.config.models import ConnectionNode


class PropertyGridWidget(QWidget):
    """
    Property Grid Inspector Panel for selected connection/folder.
    Updates dynamically whenever a node is selected in the tree.
    """
    property_changed = Signal(ConnectionNode)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node: ConnectionNode = None
        self.loading: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.form_layout = QFormLayout(scroll_content)

        # General Group
        self.txt_name = QLineEdit()
        self.txt_name.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Name:", self.txt_name)

        self.txt_description = QLineEdit()
        self.txt_description.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Description:", self.txt_description)

        self.cmb_icon = QComboBox()
        self.cmb_icon.addItems(["Server", "Folder", "Linux", "Windows", "Router", "Switch"])
        self.cmb_icon.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Icon:", self.cmb_icon)

        # Connection Group
        self.txt_hostname = QLineEdit()
        self.txt_hostname.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Hostname / IP:", self.txt_hostname)

        self.cmb_protocol = QComboBox()
        self.cmb_protocol.addItems(["SSH2", "SSH1", "RDP", "VNC", "Telnet", "HTTP", "HTTPS"])
        self.cmb_protocol.currentTextChanged.connect(self._on_protocol_changed)
        self.form_layout.addRow("Protocol:", self.cmb_protocol)

        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(22)
        self.spn_port.valueChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Port:", self.spn_port)

        # Credentials Group
        self.txt_username = QLineEdit()
        self.txt_username.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Username:", self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Password:", self.txt_password)

        self.txt_domain = QLineEdit()
        self.txt_domain.textChanged.connect(self._on_field_edited)
        self.form_layout.addRow("Domain:", self.txt_domain)

        self.txt_private_key = QLineEdit()
        self.txt_private_key.textChanged.connect(self._on_field_edited)
        self.btn_browse_key = QPushButton("...")
        self.btn_browse_key.setFixedWidth(40)
        self.btn_browse_key.clicked.connect(self._on_browse_key)
        
        key_layout = QHBoxLayout()
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.txt_private_key)
        key_layout.addWidget(self.btn_browse_key)
        self.form_layout.addRow("Private Key File:", key_layout)

        # Protocol Specific Settings
        self.chk_legacy_ssh = QCheckBox("Enable Legacy Security (Old Ciphers/KEX)")
        self.chk_legacy_ssh.setChecked(True)
        self.chk_legacy_ssh.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("SSH Options:", self.chk_legacy_ssh)

        self.cmb_rdp_sec = QComboBox()
        self.cmb_rdp_sec.addItems(["Auto", "NLA", "RDP", "TLS"])
        self.cmb_rdp_sec.currentTextChanged.connect(self._on_field_edited)
        self.form_layout.addRow("RDP Security:", self.cmb_rdp_sec)

        self.chk_redirect_drives = QCheckBox("Redirect Home Drive ($HOME)")
        self.chk_redirect_drives.toggled.connect(self._on_field_edited)
        self.form_layout.addRow("RDP Drives:", self.chk_redirect_drives)

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
        self.chk_redirect_drives.setChecked(getattr(node, "redirect_drives", False))

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
        elif protocol_str == "RDP":
            self.spn_port.setValue(3389)
        elif protocol_str == "VNC":
            self.spn_port.setValue(5900)
        elif protocol_str == "HTTP":
            self.spn_port.setValue(80)
        elif protocol_str == "HTTPS":
            self.spn_port.setValue(443)

        self._on_field_edited()

    def _on_browse_key(self):
        if self.loading or not self.current_node:
            return
        
        default_dir = os.path.expanduser("~/.ssh")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Private Key File", default_dir, "All Files (*);;PEM Keys (*.pem);;PPK Keys (*.ppk)"
        )
        if file_path:
            self.txt_private_key.setText(file_path)
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
        self.current_node.redirect_drives = self.chk_redirect_drives.isChecked()

        self.property_changed.emit(self.current_node)
