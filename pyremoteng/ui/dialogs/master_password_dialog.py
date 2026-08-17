from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox
)


class MasterPasswordDialog(QDialog):
    """
    Dialog for prompting master password when opening/importing an encrypted mRemoteNG file.
    """

    def __init__(self, parent=None, is_default: bool = True):
        super().__init__(parent)
        self.setWindowTitle("mRemoteNG Encryption Password")
        self.resize(380, 160)

        layout = QVBoxLayout(self)

        lbl = QLabel("Enter password to decrypt mRemoteNG connections file:")
        layout.addWidget(lbl)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setText("mR3m" if is_default else "")
        layout.addWidget(self.txt_password)

        self.chk_default = QCheckBox("Use default mRemoteNG password ('mR3m')")
        self.chk_default.setChecked(is_default)
        self.chk_default.toggled.connect(self._on_default_toggled)
        layout.addWidget(self.chk_default)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_default_toggled(self, checked: bool):
        if checked:
            self.txt_password.setText("mR3m")
        else:
            self.txt_password.clear()

    def get_password(self) -> str:
        return self.txt_password.text() or "mR3m"
