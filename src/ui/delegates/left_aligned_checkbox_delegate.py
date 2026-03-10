from PySide6 import QtCore, QtGui, QtWidgets


class LeftAlignedCheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """
    Delegate that paints checkboxes neatly aligned in a QTreeView column,
    independent of the tree’s indentation for the Source column.

    ✅ Flush-left alignment that respects tree indentation
    ✅ No overlap with expand/collapse arrows
    ✅ Click-to-toggle support
    """

    def __init__(self, parent=None, box_size=16, left_margin=4):
        super().__init__(parent)
        self.box_size = box_size
        self.left_margin = left_margin

    # -------------------------------------------------------------
    # Painting
    # -------------------------------------------------------------
    def paint(self, painter, option, index):
        if not index.isValid():
            return

        value = index.model().data(index, QtCore.Qt.CheckStateRole)
        if value is None:
            super().paint(painter, option, index)
            return

        painter.save()

        rect = option.rect
        tree = self.parent()

        # Base left coordinate for the checkbox
        # Start just inside the cell’s rect with a small margin
        x = rect.left() + self.left_margin
        y = rect.top() + (rect.height() - self.box_size) // 2

        # Style and draw checkbox manually
        checkbox_style = QtWidgets.QStyleOptionButton()
        checkbox_style.state = QtWidgets.QStyle.State_Enabled
        checkbox_style.state |= (
            QtWidgets.QStyle.State_On
            if value == QtCore.Qt.Checked
            else QtWidgets.QStyle.State_Off
        )
        checkbox_style.rect = QtCore.QRect(x, y, self.box_size, self.box_size)

        # Use view's style for consistency
        QtWidgets.QApplication.style().drawControl(
            QtWidgets.QStyle.CE_CheckBox, checkbox_style, painter
        )

        painter.restore()

    # -------------------------------------------------------------
    # Event Handling
    # -------------------------------------------------------------
    def editorEvent(self, event, model, option, index):
        """Handle mouse click toggling."""
        if not index.isValid():
            return False

        if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
            current_value = model.data(index, QtCore.Qt.CheckStateRole)
            new_value = (
                QtCore.Qt.Unchecked if current_value == QtCore.Qt.Checked else QtCore.Qt.Checked
            )
            model.setData(index, new_value, QtCore.Qt.CheckStateRole)
            return True

        return False

    # -------------------------------------------------------------
    # Size Hint
    # -------------------------------------------------------------
    def sizeHint(self, option, index):
        return QtCore.QSize(self.box_size, self.box_size)
