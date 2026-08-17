import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt
from pyremoteng.config.settings import SettingsManager
from pyremoteng.config.i18n import tr
from pyremoteng.crypto.master_key_manager import MasterKeyManager


class PreferencesDialog(QDialog):
    """
    Preferences and Options Dialog for pyRemoteNG.
    Allows configuring language (Spanish/English), session logs, infinite console scrollback buffer,
    aesthetic themes/fonts, and Master Encryption Key security settings.
    """

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.lang = self.settings.language
        self.master_key_mgr = MasterKeyManager(self.settings)

        self.setWindowTitle(f"{tr('preferences', self.lang)} - pyRemoteNG")
        self.setMinimumSize(540, 440)

        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)

        # Tabs
        self._init_general_tab()
        self._init_terminal_logging_tab()
        self._init_security_tab()

        # Bottom OK / Cancel Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_save = QPushButton(tr("save_apply", self.lang), self)
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        self.btn_cancel = QPushButton(tr("cancel", self.lang), self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_box)

    def _init_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox(tr("appearance", self.lang), tab)
        form = QFormLayout(group)

        # Language Selector (Spanish / English)
        self.combo_lang = QComboBox(group)
        self.combo_lang.addItem("Español (Spanish)", "es")
        self.combo_lang.addItem("English (Inglés)", "en")

        curr_idx = 0 if self.settings.language == "es" else 1
        self.combo_lang.setCurrentIndex(curr_idx)
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
        self.tab_widget.addTab(tab, tr("appearance", self.lang))

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
        self.edit_log_dir.setText(self.settings.get("log_directory", "~/.config/pyremoteng/logs"))
        dir_layout.addWidget(self.edit_log_dir)

        btn_browse = QPushButton("Examinar / Browse...", group_log)
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

        lbl_info = QLabel("Nota: Configurar en 0 para activar líneas infinitas en consola (recomendado para configs largas de Cisco).", group_term)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #888888; font-size: 11px;")
        form_term.addRow(lbl_info)

        layout.addWidget(group_term)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Terminal & Logs")

    def _init_security_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group_sec = QGroupBox(tr("master_key", self.lang), tab)
        form_sec = QFormLayout(group_sec)

        lbl_sec_info = QLabel(
            "Seguridad: Las contraseñas maestras se derivan con PBKDF2-HMAC-SHA256 (200,000 iteraciones + Salt). "
            "Las contraseñas en texto plano NUNCA se guardan en disco.",
            group_sec
        )
        lbl_sec_info.setWordWrap(True)
        lbl_sec_info.setStyleSheet("color: #4ec9b0; font-size: 11px;")
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
        self.tab_widget.addTab(tab, "Seguridad / Security")

    def _browse_log_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Seleccionar Directorio de Logs", os.path.expanduser(self.edit_log_dir.text())
        )
        if directory:
            self.edit_log_dir.setText(directory)

    def _change_master_key(self):
        curr_pass = self.edit_curr_pass.text()
        new_pass = self.edit_new_pass.text()
        confirm_pass = self.edit_confirm_pass.text()

        if not self.master_key_mgr.verify_master_key(curr_pass):
            QMessageBox.warning(self, "Error de Seguridad", "La contraseña maestra actual es incorrecta.")
            return

        if not new_pass:
            QMessageBox.warning(self, "Error de Seguridad", "La nueva contraseña maestra no puede estar vacía.")
            return

        if new_pass != confirm_pass:
            QMessageBox.warning(self, "Error de Seguridad", "La nueva contraseña y la confirmación no coinciden.")
            return

        self.master_key_mgr.set_master_key(new_pass)
        self.edit_curr_pass.clear()
        self.edit_new_pass.clear()
        self.edit_confirm_pass.clear()
        QMessageBox.information(self, "Seguridad Actualizada", "Clave Maestra de Encriptación actualizada con éxito.")

    def _on_save(self):
        selected_lang = self.combo_lang.currentData()
        self.settings.set("language", selected_lang)
        self.settings.set("theme", self.combo_theme.currentText())
        self.settings.set("font_family", self.combo_font.currentText())
        self.settings.set("font_size", self.spin_font_size.value())
        self.settings.set("enable_logging", self.chk_logging.isChecked())
        self.settings.set("log_directory", self.edit_log_dir.text().strip())
        self.settings.set("scrollback_lines", self.spin_scrollback.value())
        self.accept()
