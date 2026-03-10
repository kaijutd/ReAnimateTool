"""
ui/target_picker_popup.py - Hierarchical joint picker popup for ReAnimate Tool.
Provides live filtering, keyboard navigation, and hierarchy display.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from ui.styles.common_style import apply_style


class TargetPickerPopup(QtWidgets.QFrame):
    """
    Popup for selecting a target joint from a hierarchy.

    Features live search filtering, keyboard navigation (arrows, Enter, Esc),
    indented hierarchy display, and grayed-out non-selectable parent joints.
    """

    joint_selected = QtCore.Signal(str)
    _last_search_text = ""

    def __init__(self, joint_hierarchy, parent=None):
        """
        Args:
            joint_hierarchy (list): List of dicts with 'name' and 'children' keys.
        """
        super().__init__(parent)
        self._close_on_focus_loss = True
        self._all_joints = joint_hierarchy

        self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(4, 4, 4, 4)
        self.layout().setSpacing(4)

        self.search_field = QtWidgets.QLineEdit()
        self.search_field.setPlaceholderText("Filter joints...")
        self.search_field.textChanged.connect(self.filter)
        self.layout().addWidget(self.search_field)

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setUniformRowHeights(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree_widget.setMinimumWidth(220)
        self.tree_widget.setMaximumHeight(400)
        self.tree_widget.itemClicked.connect(self.on_item_clicked)
        self.layout().addWidget(self.tree_widget)

        apply_style(self, "DARK")
        self._populate_tree(joint_hierarchy)
        QtWidgets.QApplication.instance().installEventFilter(self)

        if TargetPickerPopup._last_search_text:
            self.search_field.setText(TargetPickerPopup._last_search_text)
            self.filter(TargetPickerPopup._last_search_text)

        self.search_field.setFocus()

    # --- Tree Population ---

    def _populate_tree(self, joint_list, parent_item=None):
        """Recursively populate the tree widget from a joint hierarchy list."""
        for joint in joint_list:
            name = joint["name"].split("|")[-1]
            item = QtWidgets.QTreeWidgetItem([name])
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            item.setForeground(0, QtGui.QBrush(QtGui.QColor("#e0e0e0")))

            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree_widget.addTopLevelItem(item)

            if joint.get("children"):
                self._populate_tree(joint["children"], parent_item=item)
                item.setExpanded(True)

    # --- Filtering ---

    def filter(self, text):
        """Filter tree items by text, graying out non-matching parents."""
        text = text.strip().lower()
        TargetPickerPopup._last_search_text = text

        def update_item(item):
            is_match = text in item.text(0).lower()
            has_visible_child = any(update_item(item.child(i)) for i in range(item.childCount()))

            if not text:
                item.setHidden(False)
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setForeground(0, QtGui.QBrush(QtGui.QColor("#e0e0e0")))
                return True
            elif is_match:
                item.setHidden(False)
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setForeground(0, QtGui.QBrush(QtGui.QColor("#e0e0e0")))
                return True
            elif has_visible_child:
                item.setHidden(False)
                item.setFlags(QtCore.Qt.ItemIsEnabled)
                item.setForeground(0, QtGui.QBrush(QtGui.QColor("#555555")))
                return True
            else:
                item.setHidden(True)
                return False

        for i in range(self.tree_widget.topLevelItemCount()):
            update_item(self.tree_widget.topLevelItem(i))

    # --- Selection ---

    def on_item_clicked(self, item, column=0):
        """Emit joint_selected signal and close if a selectable item is clicked."""
        if item and item.flags() & QtCore.Qt.ItemIsSelectable:
            self.joint_selected.emit(item.text(0))
            self.cleanup()

    # --- Focus & Closing ---

    def cleanup(self):
        """Save search state, remove event filter, and close the popup."""
        TargetPickerPopup._last_search_text = self.search_field.text().strip()
        QtWidgets.QApplication.instance().removeEventFilter(self)
        self.close()

    def eventFilter(self, obj, event):
        """Close popup on click outside its bounds."""
        if self._close_on_focus_loss and event.type() == QtCore.QEvent.MouseButtonPress:
            if not self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())):
                self.cleanup()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Handle Escape, arrow keys, and Enter for keyboard navigation."""
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            self.cleanup()
        elif key == QtCore.Qt.Key_Down:
            self._move_selection(1)
        elif key == QtCore.Qt.Key_Up:
            self._move_selection(-1)
        elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            selected = self.tree_widget.currentItem()
            if selected and selected.flags() & QtCore.Qt.ItemIsSelectable:
                self.on_item_clicked(selected)
        else:
            super().keyPressEvent(event)

    def _move_selection(self, step):
        """Move selection by step among visible selectable items."""
        visible_items = []

        def collect(item):
            for i in range(item.childCount()):
                c = item.child(i)
                if not c.isHidden() and c.flags() & QtCore.Qt.ItemIsSelectable:
                    visible_items.append(c)
                collect(c)

        collect(self.tree_widget.invisibleRootItem())
        if not visible_items:
            return

        try:
            current = visible_items.index(self.tree_widget.currentItem())
        except ValueError:
            current = 0

        self.tree_widget.setCurrentItem(visible_items[(current + step) % len(visible_items)])