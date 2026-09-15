import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt
from pyremotempc.config.settings import SettingsManager
from pyremotempc.config.i18n import tr
from pyremotempc.crypto.master_key_manager import MasterKeyManager
from pyremotempc.ui.icon_manager import get_icon


class PreferencesDialog(QDialog):
    """
    Preferences and Options Dialog for pyRemoteMPC.
    Allows configuring language (Spanish/English), session logs, infinite console scrollback buffer,
    aesthetic themes/fonts, and Master Encryption Key security settings.
    """

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.lang = self.settings.language
        self.master_key_mgr = MasterKeyManager(self.settings)

        self.setWindowTitle(f"{tr('preferences', self.lang)} - pyRemoteMPC")
        self.setMinimumSize(540, 440)

        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tabs
        self._init_general_tab()
        self._init_terminal_logging_tab()
        self._init_rdp_tab()
        self._init_security_tab()

        # Bottom OK / Cancel Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_save = QPushButton(tr("save_apply", self.lang), self)
        self.btn_save.setIcon(get_icon("check"))
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        self.btn_cancel = QPushButton(tr("cancel", self.lang), self)
        self.btn_cancel.setIcon(get_icon("close"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_box)

    def _init_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox(tr("appearance", self.lang), tab)
        form = QFormLayout(group)

        # Language Selector (English)
        self.combo_lang = QComboBox(group)
        self.combo_lang.addItem("English", "en")
        self.combo_lang.setCurrentIndex(0)
        form.addRow(tr("language", self.lang) + ":", self.combo_lang)

        # Theme Selector
        self.combo_theme = QComboBox(group)
        self.combo_theme.addItems(["Dark", "Classic Green", "Amber", "Light"])
        self.combo_theme.setCurrentText(self.settings.theme)
        form.addRow(tr("theme", self.lang) + ":", self.combo_theme)

        # Font Family Selector
        self.combo_font = QComboBox(group)
        self.combo_font.addItems(["Monospace", "DejaVu Sans Mono", "Courier New", "Consolas", "Liberation Mono"])
        self.combo_font.setCurrentText(self.settings.font_family)
        form.addRow(tr("font_family", self.lang) + ":", self.combo_font)

        # Font Size Selector
        self.spin_font_size = QSpinBox(group)
        self.spin_font_size.setRange(8, 28)
        self.spin_font_size.setValue(self.settings.font_size)
        form.addRow(tr("font_size", self.lang) + ":", self.spin_font_size)

        layout.addWidget(group)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("settings"), tr("appearance", self.lang))

    def _init_terminal_logging_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Logging Group
        group_log = QGroupBox(tr("logging_group", self.lang), tab)
        form_log = QFormLayout(group_log)

        self.chk_logging = QCheckBox(tr("enable_logging", self.lang), group_log)
        self.chk_logging.setChecked(self.settings.enable_logging)
        form_log.addRow(self.chk_logging)

        dir_layout = QHBoxLayout()
        self.edit_log_dir = QLineEdit(group_log)
        self.edit_log_dir.setText(self.settings.get("log_directory", "~/.config/pyremotempc/logs"))
        dir_layout.addWidget(self.edit_log_dir)

        btn_browse = QPushButton("Browse...", group_log)
        btn_browse.setIcon(get_icon("folder"))
        btn_browse.clicked.connect(self._browse_log_dir)
        dir_layout.addWidget(btn_browse)

        form_log.addRow(tr("log_dir", self.lang) + ":", dir_layout)
        layout.addWidget(group_log)

        # Terminal Scrollback Group
        group_term = QGroupBox(tr("scrollback_group", self.lang), tab)
        form_term = QFormLayout(group_term)

        self.spin_scrollback = QSpinBox(group_term)
        self.spin_scrollback.setRange(0, 1000000)
        self.spin_scrollback.setSingleStep(1000)
        self.spin_scrollback.setValue(self.settings.scrollback_lines)
        self.spin_scrollback.setSpecialValueText(tr("infinite_lines", self.lang))
        form_term.addRow(tr("scrollback", self.lang) + ":", self.spin_scrollback)

        lbl_info = QLabel("Note: Set to 0 for no limit on console scrollback lines.", group_term)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #888888; font-size: 11px; font-weight: normal;")
        form_term.addRow(lbl_info)

        layout.addWidget(group_term)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("log"), "Terminal and Logs")

    def _init_security_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group_sec = QGroupBox(tr("master_key", self.lang), tab)
        form_sec = QFormLayout(group_sec)

        lbl_sec_info = QLabel(
            "Security: Master passwords are derived using PBKDF2-HMAC-SHA256 (200,000 iterations + Salt). "
            "Plaintext passwords are NEVER saved to disk.",
            group_sec
        )
        lbl_sec_info.setWordWrap(True)
        lbl_sec_info.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: normal;")

        form_sec.addRow(lbl_sec_info)

        self.edit_curr_pass = QLineEdit(group_sec)
        self.edit_curr_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("current_pass", self.lang) + ":", self.edit_curr_pass)

        self.edit_new_pass = QLineEdit(group_sec)
        self.edit_new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("new_pass", self.lang) + ":", self.edit_new_pass)

        self.edit_confirm_pass = QLineEdit(group_sec)
        self.edit_confirm_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form_sec.addRow(tr("confirm_pass", self.lang) + ":", self.edit_confirm_pass)

        btn_change_key = QPushButton(tr("update_key", self.lang), group_sec)
        btn_change_key.clicked.connect(self._change_master_key)
        form_sec.addRow(btn_change_key)

        layout.addWidget(group_sec)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("security"), "Security")

    def _init_rdp_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group_rdp = QGroupBox("RDP && Remote Desktop Settings", tab)
        form_rdp = QFormLayout(group_rdp)

        self.chk_rdp_clipboard = QCheckBox("Enable Clipboard Sharing (+clipboard)", group_rdp)
        self.chk_rdp_clipboard.setChecked(self.settings.rdp_enable_clipboard)
        form_rdp.addRow(self.chk_rdp_clipboard)

        self.chk_rdp_drive = QCheckBox("Map Local Shared Directory as Network Drive (/drive:Shared)", group_rdp)
        self.chk_rdp_drive.setChecked(self.settings.rdp_enable_drive_redirection)
        form_rdp.addRow(self.chk_rdp_drive)

        folder_layout = QHBoxLayout()
        self.edit_rdp_folder = QLineEdit(group_rdp)
        self.edit_rdp_folder.setText(self.settings.get("rdp_shared_folder", os.path.expanduser("~/RDP_Shared")))
        folder_layout.addWidget(self.edit_rdp_folder)

        btn_browse_rdp = QPushButton("Browse...", group_rdp)
        btn_browse_rdp.setIcon(get_icon("folder"))
        btn_browse_rdp.clicked.connect(self._browse_rdp_folder)
        folder_layout.addWidget(btn_browse_rdp)

        form_rdp.addRow("RDP Shared Local Folder:", folder_layout)

        lbl_info = QLabel(
            "📁 Shared Drive Mapping: The configured folder will be automatically mapped as a network drive "
            "('\\\\tsclient\\Shared' or drive letter) inside all remote Windows RDP sessions.\n"
            "📋 Clipboard: Allows seamless copy && paste of text and data between Linux and RDP servers.",
            group_rdp
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: normal; margin-top: 8px;")
        form_rdp.addRow(lbl_info)

        layout.addWidget(group_rdp)
        layout.addStretch()
        self.tab_widget.addTab(tab, get_icon("windows"), "RDP && Drives")

    def _browse_log_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Log Output Directory", os.path.expanduser(self.edit_log_dir.text())
        )
        if directory:
            self.edit_log_dir.setText(directory)

    def _browse_rdp_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select RDP Shared Directory", os.path.expanduser(self.edit_rdp_folder.text())
        )
        if directory:
            self.edit_rdp_folder.setText(directory)

    def _change_master_key(self):
        curr_pass = self.edit_curr_pass.text()
        new_pass = self.edit_new_pass.text()
        confirm_pass = self.edit_confirm_pass.text()

        if not self.master_key_mgr.verify_master_key(curr_pass):
            QMessageBox.warning(self, "Security Error", "Current master password is incorrect.")
            return

        if not new_pass:
            QMessageBox.warning(self, "Security Error", "New master password cannot be empty.")
            return

        if new_pass != confirm_pass:
            QMessageBox.warning(self, "Security Error", "New master password and confirmation do not match.")
            return

        self.master_key_mgr.set_master_key(new_pass)
        self.edit_curr_pass.clear()
        self.edit_new_pass.clear()
        self.edit_confirm_pass.clear()
        QMessageBox.information(self, "Security Updated", "Master Encryption Password updated successfully.")


    def _on_save(self):
        selected_lang = self.combo_lang.currentData()
        self.settings.set("language", selected_lang)
        self.settings.set("theme", self.combo_theme.currentText())
        self.settings.set("font_family", self.combo_font.currentText())
        self.settings.set("font_size", self.spin_font_size.value())
        self.settings.set("enable_logging", self.chk_logging.isChecked())
        self.settings.set("log_directory", self.edit_log_dir.text().strip())
        self.settings.set("scrollback_lines", self.spin_scrollback.value())
        self.settings.set("rdp_enable_clipboard", self.chk_rdp_clipboard.isChecked())
        self.settings.set("rdp_enable_drive_redirection", self.chk_rdp_drive.isChecked())
        self.settings.set("rdp_shared_folder", self.edit_rdp_folder.text().strip())
        self.accept()

