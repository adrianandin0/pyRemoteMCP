import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QLabel, QMessageBox, QFileDialog, QHeaderView, QPlainTextEdit, QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QTextCursor
from pyremoteng.engine.sftp_engine import SFTPEngine
from pyremoteng.config.settings import SettingsManager
from pyremoteng.config.i18n import tr


class SFTPWidget(QWidget):
    """
    Integrated SFTP File Manager Widget.
    Provides dual-panel file management (Local Linux system vs Remote Host) per active session.
    Includes live Diagnostic Log console for immediate troubleshooting.
    """

    def __init__(self, node, ssh_engine=None, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.node = node
        self.ssh_engine = ssh_engine
        self.settings = settings_manager or SettingsManager()
        self.lang = self.settings.language

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.lbl_status = QLabel(f"SFTP Session: {self.node.username}@{self.node.hostname}:{self.node.port}", self)
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()

        self.btn_toggle_log = QPushButton(tr("sftp_log_btn", self.lang), self)
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.clicked.connect(self._toggle_log_view)
        top_bar.addWidget(self.btn_toggle_log)

        self.btn_connect = QPushButton(tr("connect_sftp", self.lang), self)
        self.btn_connect.clicked.connect(self.connect_sftp)
        top_bar.addWidget(self.btn_connect)

        self.chk_show_hidden = QCheckBox(tr("show_hidden_files", self.lang), self)
        self.chk_show_hidden.setChecked(False)
        self.chk_show_hidden.toggled.connect(self.refresh_all)
        top_bar.addWidget(self.chk_show_hidden)

        self.btn_refresh = QPushButton(tr("refresh", self.lang), self)
        self.btn_refresh.clicked.connect(self.refresh_all)
        top_bar.addWidget(self.btn_refresh)

        layout.addLayout(top_bar)

        # Main Vertical Splitter: Files on Top, Diagnostic Log on Bottom
        main_vsplitter = QSplitter(Qt.Orientation.Vertical, self)

        # Dual Panel Splitter (Local vs Remote)
        splitter = QSplitter(Qt.Orientation.Horizontal, main_vsplitter)

        # --- Left Panel: Local Machine ---
        local_container = QWidget()
        local_vbox = QVBoxLayout(local_container)
        local_vbox.setContentsMargins(0, 0, 0, 0)
        self.lbl_local_title = QLabel(f"<b>{tr('local_machine', self.lang)}</b>")
        local_vbox.addWidget(self.lbl_local_title)

        loc_nav = QHBoxLayout()
        self.edit_local_path = QLineEdit(os.path.expanduser("~"))
        self.edit_local_path.returnPressed.connect(self.load_local_dir)
        loc_nav.addWidget(self.edit_local_path)
        self.btn_loc_up = QPushButton(tr("up", self.lang), self)
        self.btn_loc_up.clicked.connect(self._local_up)
        loc_nav.addWidget(self.btn_loc_up)
        local_vbox.addLayout(loc_nav)

        self.tree_local = QTreeWidget(self)
        self.tree_local.setHeaderLabels([tr("col_name", self.lang), tr("col_size", self.lang), tr("col_perms", self.lang)])
        self.tree_local.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_local.itemDoubleClicked.connect(self._on_local_double_click)
        self.tree_local.itemActivated.connect(self._on_local_double_click)
        local_vbox.addWidget(self.tree_local)

        splitter.addWidget(local_container)

        # --- Transfer Action Buttons Panel (Center) ---
        transfer_bar = QVBoxLayout()
        transfer_bar.addStretch()

        self.btn_upload = QPushButton(tr("upload", self.lang), self)
        self.btn_upload.clicked.connect(self.upload_selected)
        transfer_bar.addWidget(self.btn_upload)

        self.btn_download = QPushButton(tr("download", self.lang), self)
        self.btn_download.clicked.connect(self.download_selected)
        transfer_bar.addWidget(self.btn_download)

        transfer_bar.addStretch()

        transfer_widget = QWidget()
        transfer_widget.setLayout(transfer_bar)
        splitter.addWidget(transfer_widget)

        # --- Right Panel: Remote Server ---
        remote_container = QWidget()
        remote_vbox = QVBoxLayout(remote_container)
        remote_vbox.setContentsMargins(0, 0, 0, 0)
        self.lbl_remote_title = QLabel(f"<b>{tr('remote_host', self.lang)} ({self.node.hostname})</b>")
        remote_vbox.addWidget(self.lbl_remote_title)

        rem_nav = QHBoxLayout()
        self.edit_remote_path = QLineEdit("/")
        self.edit_remote_path.returnPressed.connect(self.load_remote_dir)
        rem_nav.addWidget(self.edit_remote_path)
        self.btn_rem_up = QPushButton(tr("up", self.lang), self)
        self.btn_rem_up.clicked.connect(self._remote_up)
        rem_nav.addWidget(self.btn_rem_up)
        remote_vbox.addLayout(rem_nav)

        self.tree_remote = QTreeWidget(self)
        self.tree_remote.setHeaderLabels([tr("col_name", self.lang), tr("col_size", self.lang), tr("col_perms", self.lang)])
        self.tree_remote.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_remote.itemDoubleClicked.connect(self._on_remote_double_click)
        self.tree_remote.itemActivated.connect(self._on_remote_double_click)
        remote_vbox.addWidget(self.tree_remote)

        splitter.addWidget(remote_container)
        main_vsplitter.addWidget(splitter)

        # --- Bottom Panel: Live Diagnostic Log ---
        self.group_log = QGroupBox(tr("sftp_log_title", self.lang), main_vsplitter)
        log_vbox = QVBoxLayout(self.group_log)
        log_vbox.setContentsMargins(2, 2, 2, 2)

        self.txt_log = QPlainTextEdit(self.group_log)
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #111111; color: #4ec9b0; font-family: Monospace; font-size: 11px;")
        log_vbox.addWidget(self.txt_log)

        main_vsplitter.addWidget(self.group_log)
        self.group_log.setVisible(False)
        main_vsplitter.setSizes([450, 150])

        layout.addWidget(main_vsplitter)

        # Instantiate SFTPEngine with log_callback
        self.sftp_engine = SFTPEngine(
            hostname=node.hostname,
            port=node.port,
            username=node.username,
            password=node.password,
            key_filename=getattr(node, "private_key_file", ""),
            ssh_engine=self.ssh_engine,
            log_callback=self.append_log
        )

        # Load local directory right away
        self.load_local_dir()

    def append_log(self, text: str):
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.txt_log.setTextCursor(cursor)
        self.txt_log.ensureCursorVisible()

    def _toggle_log_view(self):
        self.group_log.setVisible(self.btn_toggle_log.isChecked())

    def connect_sftp(self):
        """Initializes SFTP connection to the remote host."""
        try:
            self.lbl_status.setText(f"{tr('connect_sftp', self.lang)}...")
            connected = self.sftp_engine.connect()
            if connected:
                self.lbl_status.setText(f"SFTP Connected: {self.node.username}@{self.node.hostname}")
                current_dir = self.sftp_engine.get_current_dir()
                self.edit_remote_path.setText(current_dir if current_dir != "." else "/")
                self.load_remote_dir()
            else:
                self.lbl_status.setText("SFTP Connection Failed.")
                self.group_log.setVisible(True)
                self.btn_toggle_log.setChecked(True)
        except Exception as e:
            self.lbl_status.setText("SFTP Connection Error.")
            self.group_log.setVisible(True)
            self.btn_toggle_log.setChecked(True)
            QMessageBox.critical(self, "SFTP Connection Error", f"SFTP Failed:\n{str(e)}")

    def refresh_all(self):
        self.load_local_dir()
        if not self.sftp_engine.is_connected:
            self.connect_sftp()
        else:
            self.load_remote_dir()

    def load_local_dir(self):
        path = os.path.expanduser(self.edit_local_path.text().strip())
        if not os.path.isdir(path):
            return

        self.tree_local.clear()
        try:
            entries = os.listdir(path)

            def _safe_is_dir(entry_name):
                try:
                    return os.path.isdir(os.path.join(path, entry_name))
                except Exception:
                    return False

            entries.sort(key=lambda x: (not _safe_is_dir(x), x.lower()))

            # Add parent directory ".."
            parent_path = os.path.dirname(path)
            if parent_path != path:
                parent_item = QTreeWidgetItem(["..", "<DIR>", ""])
                parent_item.setData(0, Qt.ItemDataRole.UserRole, parent_path)
                parent_item.setData(1, Qt.ItemDataRole.UserRole, True)
                self.tree_local.addTopLevelItem(parent_item)

            for entry in entries:
                if not self.chk_show_hidden.isChecked() and entry.startswith('.'):
                    continue

                full_path = os.path.join(path, entry)
                is_dir = False
                size_str = "0 B"

                try:
                    is_dir = os.path.isdir(full_path)
                    if is_dir:
                        size_str = "<DIR>"
                    else:
                        try:
                            size_str = f"{os.path.getsize(full_path)} B"
                        except Exception:
                            size_str = "<LINK>"
                except Exception:
                    is_dir = False
                    size_str = "<LINK>"

                item = QTreeWidgetItem([entry, size_str, "rw-r--r--"])
                item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                item.setData(1, Qt.ItemDataRole.UserRole, is_dir)
                self.tree_local.addTopLevelItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Local File Error", f"Cannot read directory:\n{str(e)}")

    def load_remote_dir(self):
        if not self.sftp_engine.is_connected:
            return

        path = self.edit_remote_path.text().strip()
        self.tree_remote.clear()
        try:
            items = self.sftp_engine.list_remote_dir(path)
            for item in items:
                name = item.get("name", "")
                if not self.chk_show_hidden.isChecked() and name.startswith('.') and name != "..":
                    continue

                is_dir = item.get("is_dir", False)
                size_str = "<DIR>" if is_dir else f"{item['size']} B"
                tree_item = QTreeWidgetItem([name, size_str, item["permissions"]])
                tree_item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(path, name))
                tree_item.setData(1, Qt.ItemDataRole.UserRole, is_dir)
                self.tree_remote.addTopLevelItem(tree_item)
        except Exception as e:
            self.group_log.setVisible(True)
            self.btn_toggle_log.setChecked(True)
            QMessageBox.warning(self, "Remote SFTP Error", f"Cannot list remote dir:\n{str(e)}")

    def _local_up(self):
        curr = os.path.expanduser(self.edit_local_path.text().strip())
        parent = os.path.dirname(curr)
        if parent and parent != curr:
            self.edit_local_path.setText(parent)
            self.load_local_dir()

    def _remote_up(self):
        curr = self.edit_remote_path.text().strip()
        parent = os.path.dirname(curr.rstrip("/"))
        if not parent:
            parent = "/"
        self.edit_remote_path.setText(parent)
        self.load_remote_dir()

    def _on_local_double_click(self, item: QTreeWidgetItem, column: int):
        if not item:
            return
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(1, Qt.ItemDataRole.UserRole) or (full_path and os.path.isdir(full_path))
        if is_dir:
            self.edit_local_path.setText(full_path)
            self.load_local_dir()

    def _on_remote_double_click(self, item: QTreeWidgetItem, column: int):
        if not item:
            return
        full_path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(1, Qt.ItemDataRole.UserRole) or item.text(1) == "<DIR>"
        if is_dir:
            self.edit_remote_path.setText(full_path)
            self.load_remote_dir()

    def upload_selected(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Upload", "SFTP is not connected. Click 'Connect SFTP' first.")
            return

        item = self.tree_local.currentItem()
        if not item:
            QMessageBox.warning(self, "SFTP Upload", "Select a local file to upload.")
            return

        local_path = item.data(0, Qt.ItemDataRole.UserRole)
        filename = os.path.basename(local_path)
        remote_dir = self.edit_remote_path.text().strip()
        remote_target = os.path.join(remote_dir, filename).replace("\\", "/")

        is_dir = item.data(1, Qt.ItemDataRole.UserRole)
        if is_dir:
            try:
                self.sftp_engine.upload_directory(local_path, remote_target)
                QMessageBox.information(self, "Upload Complete", f"Successfully uploaded directory '{filename}' to remote server.")
                self.load_remote_dir()
            except Exception as e:
                QMessageBox.critical(self, "Upload Failed", f"SFTP Directory Upload error:\n{str(e)}")
            return

        try:
            self.sftp_engine.upload_file(local_path, remote_target)
            QMessageBox.information(self, "Upload Complete", f"Successfully uploaded '{filename}' to remote server.")
            self.load_remote_dir()
        except Exception as e:
            QMessageBox.critical(self, "Upload Failed", f"SFTP Upload error:\n{str(e)}")

    def download_selected(self):
        if not self.sftp_engine.is_connected:
            QMessageBox.warning(self, "SFTP Download", "SFTP is not connected. Click 'Connect SFTP' first.")
            return

        item = self.tree_remote.currentItem()
        if not item:
            QMessageBox.warning(self, "SFTP Download", "Select a remote file to download.")
            return

        remote_path = item.data(0, Qt.ItemDataRole.UserRole)
        filename = os.path.basename(remote_path)
        local_dir = os.path.expanduser(self.edit_local_path.text().strip())
        local_target = os.path.join(local_dir, filename)

        is_dir = item.data(1, Qt.ItemDataRole.UserRole)
        if is_dir:
            try:
                self.sftp_engine.download_directory(remote_path, local_target)
                QMessageBox.information(self, "Download Complete", f"Successfully downloaded directory '{filename}' to local directory.")
                self.load_local_dir()
            except Exception as e:
                QMessageBox.critical(self, "Download Failed", f"SFTP Directory Download error:\n{str(e)}")
            return

        try:
            self.sftp_engine.download_file(remote_path, local_target)
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded '{filename}' to local directory.")
            self.load_local_dir()
        except Exception as e:
            QMessageBox.critical(self, "Download Failed", f"SFTP Download error:\n{str(e)}")

    def closeEvent(self, event):
        self.sftp_engine.disconnect()
        super().closeEvent(event)
