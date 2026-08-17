import os
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QMessageBox, QToolBar,
    QStatusBar, QApplication, QSplitter, QWidget, QVBoxLayout,
    QLineEdit, QComboBox, QSpinBox, QLabel, QInputDialog
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt, QSize

from pyremoteng.config.models import ConnectionNode
from pyremoteng.config.settings import SettingsManager
from pyremoteng.config.i18n import tr
from pyremoteng.config.xml_parser import mRemoteNGXmlParser
from pyremoteng.crypto.master_key_manager import MasterKeyManager
from pyremoteng.ui.tree_widget import ConnectionTreeWidget
from pyremoteng.ui.property_grid import PropertyGridWidget
from pyremoteng.ui.tab_widget import SessionTabWidget
from pyremoteng.ui.preferences_dialog import PreferencesDialog
from pyremoteng.ui.dialogs.master_password_dialog import MasterPasswordDialog


def get_user_config_dir() -> str:
    """Returns ~/.config/pyremoteng directory, creating it if needed."""
    config_dir = os.path.expanduser("~/.config/pyremoteng")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_default_config_path() -> str:
    """Returns ~/.config/pyremoteng/confCons.xml."""
    return os.path.join(get_user_config_dir(), "confCons.xml")


class MainWindow(QMainWindow):
    """
    Main Application Window for pyRemoteNG.
    Compatible with KDE Plasma, GNOME, XFCE and all Linux desktop environments.
    Supports Spanish and English interface languages.
    """

    def __init__(self):
        super().__init__()
        # Settings & Master Security Manager
        self.settings = SettingsManager()
        self.master_key_mgr = MasterKeyManager(self.settings)

        self.setWindowTitle(tr("app_title", self.settings.language))
        self.resize(1280, 850)

        self.master_password = "mR3m"
        self.current_file_path = get_default_config_path()

        # Core central tabs with settings manager
        self.session_tabs = SessionTabWidget(settings_manager=self.settings, parent=self)
        self.setCentralWidget(self.session_tabs)

        # Left Dock: Combined Tree (67%) and Properties (33%) stacked vertically
        self.sidebar_dock = QDockWidget(tr("connections_and_properties", self.settings.language), self)
        sidebar_container = QWidget(self.sidebar_dock)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar_splitter = QSplitter(Qt.Orientation.Vertical, sidebar_container)

        self.tree_widget = ConnectionTreeWidget(self.sidebar_splitter)
        self.prop_grid = PropertyGridWidget(self.sidebar_splitter)

        self.sidebar_splitter.addWidget(self.tree_widget)
        self.sidebar_splitter.addWidget(self.prop_grid)

        # Set 67% height for tree view and 33% height for properties inspector
        self.sidebar_splitter.setSizes([670, 330])
        self.sidebar_splitter.setStretchFactor(0, 67)
        self.sidebar_splitter.setStretchFactor(1, 33)

        sidebar_layout.addWidget(self.sidebar_splitter)
        self.sidebar_dock.setWidget(sidebar_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar_dock)

        # Connect signals for property grid sync and tree updates
        self.tree_widget.node_selected.connect(self.prop_grid.load_node)
        self.tree_widget.node_activated.connect(self.session_tabs.open_session)
        self.prop_grid.property_changed.connect(self._on_property_changed)

        # Setup menus, toolbars and statusbar
        self._create_menus()
        self._create_toolbar()
        self._create_quick_connect_bar()

        self.statusBar().showMessage("Ready / Listo")

        # Auto-load existing connections or default tree
        self._auto_load_connections()

    def _auto_load_connections(self):
        """Loads connections from user config file (~/.config/pyremoteng/confCons.xml) if present."""
        default_path = get_default_config_path()
        if os.path.exists(default_path):
            try:
                parser = mRemoteNGXmlParser(master_password=self.master_password)
                root_node, ver = parser.parse_file(default_path)
                self.tree_widget.load_tree(root_node)
                self.statusBar().showMessage(f"Loaded connections from {default_path}")
                return
            except Exception:
                pass

        self._load_default_tree()

    def _load_default_tree(self):
        root = ConnectionNode(name=tr("connections", self.settings.language), node_type="Container")

        folder_linux = ConnectionNode(name="Linux Servers", node_type="Container", icon="Folder")
        node_local = ConnectionNode(
            name="Local SSH Server",
            node_type="Connection",
            hostname="127.0.0.1",
            protocol="SSH2",
            port=22,
            username=os.environ.get("USER", "root"),
            icon="Server"
        )
        folder_linux.children.append(node_local)
        root.children.append(folder_linux)

        self.tree_widget.load_tree(root)

    def _auto_save_connections(self):
        """Auto-saves current connection tree to ~/.config/pyremoteng/confCons.xml."""
        default_path = get_default_config_path()
        try:
            parser = mRemoteNGXmlParser(master_password=self.master_password)
            parser.export_to_file(self.tree_widget.root_node, default_path, version="2.5")
        except Exception as e:
            print(f"Auto-save connections failed: {e}")

    def _on_property_changed(self, node: ConnectionNode):
        self.tree_widget.update_node_display(node)
        self._auto_save_connections()

    def _create_menus(self):
        menubar = self.menuBar()
        lang = self.settings.language

        # File Menu
        menu_file = menubar.addMenu(tr("file", lang))

        act_new_conn = QAction(QIcon.fromTheme("list-add"), tr("new_connection", lang), self)
        act_new_conn.setShortcut("Ctrl+N")
        act_new_conn.triggered.connect(lambda: self.tree_widget.add_new_connection())
        menu_file.addAction(act_new_conn)

        act_new_folder = QAction(QIcon.fromTheme("folder-new"), tr("new_folder", lang), self)
        act_new_folder.setShortcut("Ctrl+Shift+N")
        act_new_folder.triggered.connect(lambda: self.tree_widget.add_new_folder())
        menu_file.addAction(act_new_folder)

        menu_file.addSeparator()

        act_open = QAction(QIcon.fromTheme("document-open"), tr("import_xml", lang), self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.import_xml)
        menu_file.addAction(act_open)

        act_save = QAction(QIcon.fromTheme("document-save"), tr("export_xml", lang), self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.export_xml)
        menu_file.addAction(act_save)

        menu_file.addSeparator()

        act_exit = QAction(QIcon.fromTheme("application-exit"), tr("exit", lang), self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # View Menu
        menu_view = menubar.addMenu(tr("view", lang))
        menu_view.addAction(self.sidebar_dock.toggleViewAction())

        # Settings Menu
        menu_settings = menubar.addMenu(tr("settings", lang))
        act_prefs = QAction(QIcon.fromTheme("preferences-system"), tr("preferences", lang), self)
        act_prefs.triggered.connect(self._open_preferences)
        menu_settings.addAction(act_prefs)

        act_master_pass = QAction(tr("set_master_pass", lang), self)
        act_master_pass.triggered.connect(self._change_master_password)
        menu_settings.addAction(act_master_pass)

        # Help Menu
        menu_help = menubar.addMenu(tr("help", lang))
        act_about = QAction(tr("about", lang), self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    def _open_preferences(self):
        """Opens the Preferences & Options dialog."""
        dialog = PreferencesDialog(self.settings, self)
        if dialog.exec() == PreferencesDialog.DialogCode.Accepted:
            # Refresh language & window title
            lang = self.settings.language
            self.setWindowTitle(tr("app_title", lang))

            # Apply updated settings across active terminal tabs
            for i in range(self.session_tabs.count()):
                widget = self.session_tabs.widget(i)
                if hasattr(widget, "term"):
                    widget.term.apply_settings()

            self.statusBar().showMessage("Preferences updated successfully.")

    def _create_toolbar(self):
        lang = self.settings.language
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        act_new_conn = QAction(QIcon.fromTheme("list-add"), tr("new_connection", lang), self)
        act_new_conn.triggered.connect(lambda: self.tree_widget.add_new_connection())
        toolbar.addAction(act_new_conn)

        act_new_folder = QAction(QIcon.fromTheme("folder-new"), tr("new_folder", lang), self)
        act_new_folder.triggered.connect(lambda: self.tree_widget.add_new_folder())
        toolbar.addAction(act_new_folder)

        toolbar.addSeparator()

        act_connect = QAction(QIcon.fromTheme("media-playback-start"), tr("connect", lang), self)
        act_connect.triggered.connect(self._connect_selected)
        toolbar.addAction(act_connect)

        toolbar.addSeparator()

        act_import = QAction(QIcon.fromTheme("document-open"), tr("import_xml", lang), self)
        act_import.triggered.connect(self.import_xml)
        toolbar.addAction(act_import)

        act_export = QAction(QIcon.fromTheme("document-save"), tr("export_xml", lang), self)
        act_export.triggered.connect(self.export_xml)
        toolbar.addAction(act_export)

        toolbar.addSeparator()

        act_prefs_tb = QAction(QIcon.fromTheme("preferences-system"), tr("preferences", lang), self)
        act_prefs_tb.triggered.connect(self._open_preferences)
        toolbar.addAction(act_prefs_tb)

    def _create_quick_connect_bar(self):
        """Creates top Quick Connect bar for manual IP/host input, protocol selection and Save option."""
        lang = self.settings.language
        qc_toolbar = QToolBar("Quick Connect Bar", self)
        qc_toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, qc_toolbar)

        qc_toolbar.addWidget(QLabel(f" {tr('quick_connect', lang)}: "))

        self.qc_host = QLineEdit()
        self.qc_host.setPlaceholderText("Hostname / IP (e.g. 192.168.1.50)")
        self.qc_host.setMinimumWidth(180)
        self.qc_host.returnPressed.connect(self._exec_quick_connect)
        qc_toolbar.addWidget(self.qc_host)

        qc_toolbar.addWidget(QLabel(f" {tr('proto', lang)}: "))
        self.qc_proto = QComboBox()
        self.qc_proto.addItems(["SSH2", "SSH1", "RDP", "VNC", "Telnet"])
        self.qc_proto.currentTextChanged.connect(self._on_qc_proto_changed)
        qc_toolbar.addWidget(self.qc_proto)

        qc_toolbar.addWidget(QLabel(f" {tr('port', lang)}: "))
        self.qc_port = QSpinBox()
        self.qc_port.setRange(1, 65535)
        self.qc_port.setValue(22)
        qc_toolbar.addWidget(self.qc_port)

        qc_toolbar.addWidget(QLabel(f" {tr('user', lang)}: "))
        self.qc_user = QLineEdit()
        self.qc_user.setPlaceholderText(tr("user", lang))
        self.qc_user.setMaximumWidth(120)
        qc_toolbar.addWidget(self.qc_user)

        qc_toolbar.addWidget(QLabel(f" {tr('pass', lang)}: "))
        self.qc_pass = QLineEdit()
        self.qc_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.qc_pass.setPlaceholderText(tr("pass", lang))
        self.qc_pass.setMaximumWidth(120)
        qc_toolbar.addWidget(self.qc_pass)

        qc_toolbar.addSeparator()

        # ▶ Quick Connect Action Button
        act_qc_connect = QAction(QIcon.fromTheme("media-playback-start"), f" {tr('connect', lang)}", self)
        act_qc_connect.setToolTip("Connect directly to Hostname / IP")
        act_qc_connect.triggered.connect(self._exec_quick_connect)
        qc_toolbar.addAction(act_qc_connect)

        # 💾 Save Connection Action Button
        act_qc_save = QAction(QIcon.fromTheme("document-save"), f" {tr('save_conn', lang)}", self)
        act_qc_save.setToolTip("Save this Quick Connect entry into the left connections tree")
        act_qc_save.triggered.connect(self._exec_quick_save)
        qc_toolbar.addAction(act_qc_save)

    def _on_qc_proto_changed(self, proto: str):
        if proto in ("SSH2", "SSH1"):
            self.qc_port.setValue(22)
        elif proto == "RDP":
            self.qc_port.setValue(3389)
        elif proto == "VNC":
            self.qc_port.setValue(5900)
        elif proto == "Telnet":
            self.qc_port.setValue(23)

    def _exec_quick_connect(self):
        host = self.qc_host.text().strip()
        if not host:
            QMessageBox.warning(self, tr("quick_connect", self.settings.language), "Please enter a valid Hostname or IP address.")
            return

        quick_node = ConnectionNode(
            name=host,
            node_type="Connection",
            hostname=host,
            protocol=self.qc_proto.currentText(),
            port=self.qc_port.value(),
            username=self.qc_user.text().strip(),
            password=self.qc_pass.text(),
            legacy_ssh=True
        )
        self.session_tabs.open_session(quick_node)

    def _exec_quick_save(self):
        host = self.qc_host.text().strip()
        if not host:
            QMessageBox.warning(self, tr("save_conn", self.settings.language), "Please enter a valid Hostname or IP address to save.")
            return

        conn_name, ok = QInputDialog.getText(
            self, tr("save_conn", self.settings.language), "Enter a name for this connection:", QLineEdit.EchoMode.Normal, host
        )
        if not ok or not conn_name.strip():
            conn_name = host

        new_node = ConnectionNode(
            name=conn_name.strip(),
            node_type="Connection",
            hostname=host,
            protocol=self.qc_proto.currentText(),
            port=self.qc_port.value(),
            username=self.qc_user.text().strip(),
            password=self.qc_pass.text(),
            legacy_ssh=True
        )

        parent_node = self.tree_widget.get_selected_node() or self.tree_widget.root_node
        self.tree_widget.add_new_connection(parent_node=parent_node, new_node=new_node)
        self._auto_save_connections()
        self.statusBar().showMessage(f"Saved connection '{conn_name}' to tree.")

    def _connect_selected(self):
        node = self.tree_widget.get_selected_node()
        if node and not node.is_container():
            self.session_tabs.open_session(node)

    def import_xml(self):
        """Opens dialog to import mRemoteNG confCons.xml connection file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("import_xml", self.settings.language), "", "mRemoteNG XML (*.xml);;All Files (*)"
        )
        if not file_path:
            return

        dialog = MasterPasswordDialog(self, is_default=(self.master_password == "mR3m"))
        if dialog.exec() == MasterPasswordDialog.DialogCode.Accepted:
            self.master_password = dialog.get_password()
            try:
                parser = mRemoteNGXmlParser(master_password=self.master_password)
                root_node, ver = parser.parse_file(file_path, is_import=True)
                self.tree_widget.load_tree(root_node)
                self.current_file_path = file_path
                self._auto_save_connections()
                self.statusBar().showMessage(f"Loaded mRemoteNG connections from {os.path.basename(file_path)} (v{ver})")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to parse mRemoteNG XML:\n{str(e)}")

    def export_xml(self):
        """Exports connection tree to mRemoteNG confCons.xml format."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("export_xml", self.settings.language), "confCons.xml", "mRemoteNG XML (*.xml);;All Files (*)"
        )
        if not file_path:
            return

        try:
            parser = mRemoteNGXmlParser(master_password=self.master_password)
            parser.export_to_file(self.tree_widget.root_node, file_path, version="2.5")
            self.statusBar().showMessage(f"Exported connections to {file_path}")
            QMessageBox.information(self, "Export Successful", f"Successfully exported connections to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export XML:\n{str(e)}")

    def _change_master_password(self):
        dialog = MasterPasswordDialog(self, is_default=(self.master_password == "mR3m"))
        if dialog.exec() == MasterPasswordDialog.DialogCode.Accepted:
            self.master_password = dialog.get_password()
            self.master_key_mgr.set_master_key(self.master_password)
            self._auto_save_connections()
            self.statusBar().showMessage("Updated master encryption password.")

    def _show_about(self):
        QMessageBox.about(
            self,
            tr("about", self.settings.language),
            "<h3>pyRemoteNG v1.3.0</h3>"
            "<p>Clon de mRemoteNG nativo en Python para Linux (KDE, GNOME, XFCE) y Multiplataforma.</p>"
            "<p>Soporte Bilingüe: Español / English.</p>"
            "<p>Motor SSH con soporte legacy (SSH1, SSH2, ciphers/KEX antiguos).</p>"
            "<p>Gestor SFTP/FTP integrado por pestaña de sesión (con reutilización de transporte activo y fallback nativo).</p>"
            "<p>Logs de sesión configurables, buffer de líneas infinitas y exportación a TXT.</p>"
            "<p>Seguridad de clave maestra con PBKDF2-HMAC-SHA256 y Salt único.</p>"
        )

    def closeEvent(self, event):
        self._auto_save_connections()
        super().closeEvent(event)
