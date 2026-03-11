"""
ui/delegates/left_aligned_checkbox_delegate.py - Left-aligned checkbox delegate for QTreeView.
Renders checkboxes flush to the cell edge, independent of tree indentation.
"""

from PySide6 import QtCore, QtGui, QtWidgets


class LeftAlignedCheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """
    Renders a checkbox aligned to the left edge of a tree column,
    independent of indentation. Supports click-to-toggle.
    """

    def __init__(self, parent=None, box_size=16, left_margin=4):
        super().__init__(parent)
        self.box_size = box_size
        self.left_margin = left_margin

    def paint(self, painter, option, index):
        """Draw a manually positioned checkbox in the cell."""
        if not index.isValid():
            return

        value = index.model().data(index, QtCore.Qt.CheckStateRole)
        if value is None:
            super().paint(painter, option, index)
            return

        painter.save()

        x = option.rect.left() + self.left_margin
        y = option.rect.top() + (option.rect.height() - self.box_size) // 2

        checkbox_style = QtWidgets.QStyleOptionButton()
        checkbox_style.state = QtWidgets.QStyle.State_Enabled
        checkbox_style.state |= (
            QtWidgets.QStyle.State_On if value == QtCore.Qt.Checked
            else QtWidgets.QStyle.State_Off
        )
        checkbox_style.rect = QtCore.QRect(x, y, self.box_size, self.box_size)

        QtWidgets.QApplication.style().drawControl(
            QtWidgets.QStyle.CE_CheckBox, checkbox_style, painter
        )

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Toggle checkbox state on left mouse click."""
        if not index.isValid():
            return False
        if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
            current = model.data(index, QtCore.Qt.CheckStateRole)
            model.setData(index, 
                QtCore.Qt.Unchecked if current == QtCore.Qt.Checked else QtCore.Qt.Checked,
                QtCore.Qt.CheckStateRole
            )
            return True
        return False

    def sizeHint(self, option, index):
        return QtCore.QSize(self.box_size, self.box_size)