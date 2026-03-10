from PySide6 import QtWidgets, QtGui, QtCore
from ui.styles.common_style import apply_style


class ModeDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate for the Mode column (Transfer / Constrain / Ignore)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.modes = ["Transfer (World)", "Transfer (Hybrid Local)","Transfer (Hybrid World)","Transfer (Quaternion)","Transfer (Matrix)","Overwrite", "Ignore","Keep"]

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        value = index.data(QtCore.Qt.DisplayRole) or "Transfer"

        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(rect, QtGui.QColor("#007acc"))
        else:
            painter.fillRect(rect, QtGui.QColor("#2b2b2b"))

        painter.setPen(QtGui.QColor("#e0e0e0"))
        font = option.font
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(rect.adjusted(6, 0, -6, 0),
                         QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                         value)
        painter.restore()

    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.modes)
        combo.setEditable(False)

        apply_style(combo, "DARK")
        combo.setStyleSheet(combo.styleSheet() + """
            QComboBox {
                padding: 2px 6px;
                min-height: 18px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #555;
            }
            QComboBox::down-arrow {
                image: none;  /* keep default arrow */
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                selection-background-color: #007acc;
                color: #e0e0e0;
            }
        """)

        # Connect activated signal to commit and close immediately
        combo.activated.connect(lambda _: self.commit_and_close(combo))

        # Install event filter for instant popup
        combo.installEventFilter(self)
        return combo

    def commit_and_close(self, editor):
        """Commit current value to model and close editor."""
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
        if event.type() == QtCore.QEvent.MouseButtonPress:
            view = option.widget
            if view:
                view.edit(index)
            return True
        return super().editorEvent(event, model, option, index)

    def eventFilter(self, obj, event):
        # Show popup immediately when editor is ready
        if isinstance(obj, QtWidgets.QComboBox):
            if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.FocusIn):
                QtCore.QTimer.singleShot(0, obj.showPopup)
        return super().eventFilter(obj, event)
