from typing import Optional
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal
from pyremotempc.config.models import ConnectionNode


class ConnectionTreeWidget(QTreeWidget):
    """
    Hierarchical Connections and Folders Tree Widget.
    """
    node_selected = Signal(ConnectionNode)
    node_activated = Signal(ConnectionNode)  # Double click / Enter to connect
    tree_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Connections")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Connect both selection and current item signals for instantaneous property inspector update
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)

        self.root_node: ConnectionNode = ConnectionNode(name="Connections", node_type="Container")

    def load_tree(self, root_node: ConnectionNode):
        """Loads a ConnectionNode tree into the widget."""
        self.clear()
        self.root_node = root_node
        self.setUpdatesEnabled(False)
        self._populate_item(self.invisibleRootItem(), root_node)
        self.expandAll()
        self.setUpdatesEnabled(True)

    def update_node_display(self, node: ConnectionNode):
        """Updates the tree item text and icon display for a modified node."""
        self._update_item_text_recursive(self.invisibleRootItem(), node)

    def _update_item_text_recursive(self, parent_item, target_node: ConnectionNode) -> bool:
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            n: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if n and n.id == target_node.id:
                item.setText(0, target_node.name)
                return True
            if self._update_item_text_recursive(item, target_node):
                return True
        return False

    def _populate_item(self, parent_item: QTreeWidgetItem, node: ConnectionNode):
        item = QTreeWidgetItem()
        item.setText(0, node.name)
        item.setData(0, Qt.ItemDataRole.UserRole, node)

        # Apply icon representation
        icon_name = node.icon.lower() if node.icon else "server"
        if node.is_container():
            item.setIcon(0, QIcon.fromTheme("folder", QIcon.fromTheme("system-file-manager")))
        elif "linux" in icon_name or "ssh" in node.protocol.lower():
            item.setIcon(0, QIcon.fromTheme("utilities-terminal", QIcon.fromTheme("terminal")))
        elif "windows" in icon_name or "rdp" in node.protocol.lower():
            item.setIcon(0, QIcon.fromTheme("computer", QIcon.fromTheme("system-run")))
        else:
            item.setIcon(0, QIcon.fromTheme("network-server", QIcon.fromTheme("network-idle")))

        if isinstance(parent_item, QTreeWidgetItem):
            parent_item.addChild(item)
        else:
            self.addTopLevelItem(item)

        for child in node.children:
            self._populate_item(item, child)

    def _on_selection_changed(self):
        items = self.selectedItems()
        if items:
            node: ConnectionNode = items[0].data(0, Qt.ItemDataRole.UserRole)
            if node:
                self.node_selected.emit(node)

    def _on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        if current:
            node: ConnectionNode = current.data(0, Qt.ItemDataRole.UserRole)
            if node:
                self.node_selected.emit(node)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
        if node and not node.is_container():
            self.node_activated.emit(node)

    def get_selected_node(self) -> Optional[ConnectionNode]:
        items = self.selectedItems()
        if items:
            return items[0].data(0, Qt.ItemDataRole.UserRole)
        return None

    def add_new_connection(self, parent_node: Optional[ConnectionNode] = None, new_node: Optional[ConnectionNode] = None) -> ConnectionNode:
        if parent_node is None:
            parent_node = self.get_selected_node() or self.root_node

        if not parent_node.is_container():
            parent_node = self.root_node

        if new_node is None:
            new_node = ConnectionNode(
                name="New Connection",
                node_type="Connection",
                protocol="SSH2",
                port=22,
                hostname="127.0.0.1",
                parent_id=parent_node.id
            )
        else:
            new_node.parent_id = parent_node.id

        parent_node.children.append(new_node)
        self.load_tree(self.root_node)

        # Select the newly added item in tree
        self._select_node_item(self.invisibleRootItem(), new_node.id)
        self.tree_changed.emit()
        return new_node

    def _select_node_item(self, parent_item, target_id: str) -> bool:
        count = parent_item.childCount() if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItemCount()
        for i in range(count):
            item = parent_item.child(i) if isinstance(parent_item, QTreeWidgetItem) else self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node and node.id == target_id:
                self.setCurrentItem(item)
                return True
            if self._select_node_item(item, target_id):
                return True
        return False

    def add_new_folder(self, parent_node: Optional[ConnectionNode] = None) -> ConnectionNode:
        if parent_node is None:
            parent_node = self.get_selected_node() or self.root_node

        if not parent_node.is_container():
            parent_node = self.root_node

        new_folder = ConnectionNode(
            name="New Folder",
            node_type="Container",
            icon="Folder",
            parent_id=parent_node.id
        )
        parent_node.children.append(new_folder)
        self.load_tree(self.root_node)
        self._select_node_item(self.invisibleRootItem(), new_folder.id)
        self.tree_changed.emit()
        return new_folder

    def delete_selected_node(self):
        node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{node.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._remove_node_recursive(self.root_node, node.id)
            self.load_tree(self.root_node)
            self.tree_changed.emit()

    def _remove_node_recursive(self, parent: ConnectionNode, target_id: str) -> bool:
        for child in list(parent.children):
            if child.id == target_id:
                parent.children.remove(child)
                return True
            if child.is_container():
                if self._remove_node_recursive(child, target_id):
                    return True
        return False

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        menu = QMenu(self)

        if item:
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if not node.is_container():
                action_connect = menu.addAction("Connect")
                action_connect.triggered.connect(lambda: self.node_activated.emit(node))
                menu.addSeparator()

            action_new_conn = menu.addAction("New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(node))

            action_new_folder = menu.addAction("New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(node))

            menu.addSeparator()
            action_delete = menu.addAction("Delete")
            action_delete.triggered.connect(self.delete_selected_node)
        else:
            action_new_conn = menu.addAction("New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(self.root_node))

            action_new_folder = menu.addAction("New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(self.root_node))

        menu.exec_(self.viewport().mapToGlobal(position))
