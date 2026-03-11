"""
ui/delegates/mode_delegate.py - Delegate for the transfer mode column.
Renders and edits transfer mode selection via an inline dropdown.
"""

from PySide6 import QtWidgets, QtGui, QtCore
from ui.styles.common_style import apply_style


class ModeDelegate(QtWidgets.QStyledItemDelegate):
    """Inline dropdown delegate for selecting joint transfer modes."""

    MODES = [
        "Transfer (World)", "Transfer (Hybrid Local)", "Transfer (Hybrid World)",
        "Transfer (Quaternion)", "Transfer (Matrix)", "Overwrite", "Ignore", "Keep"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Render the mode value as styled text."""
        painter.save()
        rect = option.rect
        value = index.data(QtCore.Qt.DisplayRole) or "Transfer"

        bg = QtGui.QColor("#007acc") if option.state & QtWidgets.QStyle.State_Selected else QtGui.QColor("#2b2b2b")
        painter.fillRect(rect, bg)

        font = option.font
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#e0e0e0"))
        painter.drawText(rect.adjusted(6, 0, -6, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, value)
        painter.restore()

    def createEditor(self, parent, option, index):
        """Create a styled combo box that commits on selection."""
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.MODES)
        combo.setEditable(False)
        apply_style(combo, "DARK")
        combo.setStyleSheet(combo.styleSheet() + """
            QComboBox { padding: 2px 6px; min-height: 18px; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #555;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                selection-background-color: #007acc;
                color: #e0e0e0;
            }
        """)
        combo.activated.connect(lambda _: self._commit_and_close(combo))
        combo.installEventFilter(self)
        return combo

    def _commit_and_close(self, editor):
        """Commit the selected value and close the editor."""
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QtWidgets.QAbstractItemDelegate.NoHint)

    def setEditorData(self, editor, index):
        value = index.data(QtCore.Qt.DisplayRole) or "Transfer"
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)

    def sizeHint(self, option, index):
        metrics = QtGui.QFontMetrics(option.font)
        return QtCore.QSize(metrics.horizontalAdvance("Constrain") + 24, metrics.height() + 6)

    def editorEvent(self, event, model, option, index):
        """Trigger edit on mouse press."""
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if option.widget:
                option.widget.edit(index)
            return True
        return super().editorEvent(event, model, option, index)

    def eventFilter(self, obj, event):
        """Show dropdown popup immediately when editor appears."""
        if isinstance(obj, QtWidgets.QComboBox):
            if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.FocusIn):
                QtCore.QTimer.singleShot(0, obj.showPopup)
        return super().eventFilter(obj, event)