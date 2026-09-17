from typing import Optional
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal
from pyremotempc.config.models import ConnectionNode
from pyremotempc.ui.icon_manager import get_icon, get_node_icon


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

        self.root_node: ConnectionNode = ConnectionNode(name="Connections", node_type="Container", icon="Connections")

    def filter_nodes(self, query: str):
        """Filters connection tree items in real-time based on query (name, hostname, username, description)."""
        query = query.strip().lower()

        def _filter_item_recursive(item: QTreeWidgetItem) -> bool:
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            matches = False
            if node:
                name_match = query in (node.name or "").lower()
                host_match = query in (node.hostname or "").lower()
                user_match = query in (node.username or "").lower()
                desc_match = query in (node.description or "").lower()
                matches = name_match or host_match or user_match or desc_match

            any_child_matches = False
            for i in range(item.childCount()):
                child_item = item.child(i)
                if _filter_item_recursive(child_item):
                    any_child_matches = True

            visible = not query or matches or any_child_matches
            item.setHidden(not visible)

            if visible and query:
                item.setExpanded(True)

            return visible

        self.setUpdatesEnabled(False)
        for i in range(self.topLevelItemCount()):
            top_item = self.topLevelItem(i)
            _filter_item_recursive(top_item)
        self.setUpdatesEnabled(True)

    def load_tree(self, root_node: ConnectionNode):
        """Loads a ConnectionNode tree into the widget."""
        if root_node and root_node.name and root_node.name.strip().lower() in ("conexiones", "connections"):
            root_node.name = "Connections"
        self.clear()
        self.root_node = root_node
        self.setUpdatesEnabled(False)
        self._populate_item(self.invisibleRootItem(), root_node)
        self.expandAll()
        self.setUpdatesEnabled(True)

        # Select root "Connections" node by default on startup
        if self.topLevelItemCount() > 0:
            top_item = self.topLevelItem(0)
            self.setCurrentItem(top_item)

    def sync_root_node_from_ui(self):
        """Rebuilds self.root_node.children structure from current visual QTreeWidget hierarchy."""
        if not hasattr(self, "root_node") or not self.root_node:
            return

        def _build_children_from_item(parent_item: QTreeWidgetItem, parent_node: ConnectionNode):
            count = parent_item.childCount()
            new_children = []
            for i in range(count):
                item = parent_item.child(i)
                node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
                if node:
                    node.parent_id = parent_node.id
                    if node.is_container():
                        _build_children_from_item(item, node)
                    new_children.append(node)
            parent_node.children = new_children

        if self.topLevelItemCount() == 1:
            top_item = self.topLevelItem(0)
            top_node: ConnectionNode = top_item.data(0, Qt.ItemDataRole.UserRole)
            if top_node and top_node.id == self.root_node.id:
                _build_children_from_item(top_item, self.root_node)
                return

        count = self.topLevelItemCount()
        new_children = []
        for i in range(count):
            item = self.topLevelItem(i)
            node: ConnectionNode = item.data(0, Qt.ItemDataRole.UserRole)
            if node:
                node.parent_id = self.root_node.id
                if node.is_container():
                    _build_children_from_item(item, node)
                new_children.append(node)
        self.root_node.children = new_children

    def dropEvent(self, event):
        super().dropEvent(event)
        self.sync_root_node_from_ui()
        self.tree_changed.emit()

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
                item.setIcon(0, get_node_icon(target_node))
                return True
            if self._update_item_text_recursive(item, target_node):
                return True
        return False

    def _populate_item(self, parent_item: QTreeWidgetItem, node: ConnectionNode):
        item = QTreeWidgetItem()
        item.setText(0, node.name)
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        item.setIcon(0, get_node_icon(node))

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
        self.sync_root_node_from_ui()
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
        self.sync_root_node_from_ui()
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

    def rename_node(self, node: Optional[ConnectionNode] = None):
        if node is None:
            node = self.get_selected_node()
        if not node or node == self.root_node:
            return

        new_name, ok = QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            text=node.name
        )
        if ok and new_name.strip():
            node.name = new_name.strip()
            self.update_node_display(node)
            self.tree_changed.emit()

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
                action_connect = menu.addAction(get_icon("connect"), "Connect")
                action_connect.triggered.connect(lambda: self.node_activated.emit(node))
                menu.addSeparator()

            action_new_conn = menu.addAction(get_icon("add"), "New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(node))

            action_new_folder = menu.addAction(get_icon("folder"), "New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(node))

            action_rename = menu.addAction(get_icon("edit"), "Rename")
            action_rename.triggered.connect(lambda: self.rename_node(node))

            menu.addSeparator()
            action_delete = menu.addAction(get_icon("trash"), "Delete")
            action_delete.triggered.connect(self.delete_selected_node)
        else:
            action_new_conn = menu.addAction(get_icon("add"), "New Connection")
            action_new_conn.triggered.connect(lambda: self.add_new_connection(self.root_node))

            action_new_folder = menu.addAction(get_icon("folder"), "New Folder")
            action_new_folder.triggered.connect(lambda: self.add_new_folder(self.root_node))

        menu.exec_(self.viewport().mapToGlobal(position))
