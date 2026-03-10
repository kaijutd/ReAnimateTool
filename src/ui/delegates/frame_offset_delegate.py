"""
ui/delegates/frame_offset_delegate.py - Slider delegate for per-joint frame offset.
Supports drag-to-set, snap-to-zero, and double-click for numeric input.
"""

from PySide6 import QtCore, QtGui, QtWidgets


class FrameOffsetDelegate(QtWidgets.QStyledItemDelegate):
    """Inline slider delegate for setting integer frame offsets with snap-to-zero."""

    def __init__(self, parent=None, slider_min=0, slider_max=100):
        super().__init__(parent)
        self.slider_min = slider_min
        self.slider_max = slider_max
        self._preferred_height = 24
        self._dragging_index = None
        self.snap_threshold = 2

    def createEditor(self, parent, option, index):
        return None

    def paint(self, painter, option, index):
        """Draw a custom slider with knob, fill, zero line, and numeric label."""
        painter.save()
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.widget.style().drawControl(QtWidgets.QStyle.CE_ItemViewItem, opt, painter)

        value = int(index.data(QtCore.Qt.DisplayRole) or 0)
        rect = option.rect.adjusted(6, 6, -35, -6)
        span = max(1, self.slider_max - self.slider_min)

        groove_rect = QtCore.QRect(rect.left(), rect.center().y() - 3, rect.width(), 6)
        painter.setPen(QtGui.QPen(option.palette.dark().color()))
        painter.setBrush(option.palette.mid())
        painter.drawRoundedRect(groove_rect, 3, 3)

        norm = (value - self.slider_min) / span
        knob_x = int(groove_rect.left() + norm * groove_rect.width())

        zero_x = int(groove_rect.left() + (0 - self.slider_min) / span * groove_rect.width())
        painter.setPen(QtGui.QPen(QtGui.QColor("#606060"), 1, QtCore.Qt.DashLine))
        painter.drawLine(zero_x, groove_rect.top() - 3, zero_x, groove_rect.bottom() + 3)

        painter.setBrush(QtGui.QColor("#A0A0A0"))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(QtCore.QRect(groove_rect.left(), groove_rect.top(),
                                      knob_x - groove_rect.left(), groove_rect.height()))

        painter.setBrush(option.palette.button())
        painter.setPen(option.palette.text().color())
        painter.drawEllipse(QtCore.QRect(knob_x - 5, groove_rect.top() - 4, 10, 14))

        text_rect = option.rect.adjusted(rect.width() + 8, 0, -6, 0)
        painter.setPen(option.palette.text().color())
        painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, str(value))

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handle double-click for numeric input and drag for slider interaction."""
        if event.type() == QtCore.QEvent.MouseButtonDblClick:
            self._show_input_popup(model, index, option)
            return True

        if not (event.type() in (QtCore.QEvent.MouseButtonPress,
                                  QtCore.QEvent.MouseMove,
                                  QtCore.QEvent.MouseButtonRelease)
                and event.buttons() & QtCore.Qt.LeftButton):
            return False

        if event.type() == QtCore.QEvent.MouseButtonPress:
            self._dragging_index = QtCore.QPersistentModelIndex(index)

        if not self._dragging_index or not self._dragging_index.isValid():
            return False

        rect = option.rect.adjusted(6, 6, -35, -6)
        x = max(rect.left(), min(event.pos().x(), rect.right()))
        value = int(self.slider_min + (x - rect.left()) / rect.width() * (self.slider_max - self.slider_min))

        if abs(value) <= self.snap_threshold:
            value = 0

        model.setData(self._dragging_index, value, QtCore.Qt.EditRole)
        if option.widget:
            option.widget.viewport().update()

        return True

    def _show_input_popup(self, model, index, option):
        """Show a floating QLineEdit for direct numeric frame offset entry."""
        global_pos = QtGui.QCursor.pos()

        line_edit = QtWidgets.QLineEdit()
        line_edit.setText("0")
        line_edit.setValidator(QtGui.QIntValidator(self.slider_min, self.slider_max))
        line_edit.setFixedWidth(80)
        line_edit.setAlignment(QtCore.Qt.AlignCenter)
        line_edit.setWindowFlags(
            QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint
        )
        line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333;
                color: white;
                border: 1px solid #888;
                border-radius: 4px;
                padding: 2px 6px;
                selection-background-color: #555;
            }
        """)
        line_edit.move(global_pos + QtCore.QPoint(10, 10))
        line_edit.show()
        line_edit.setFocus(QtCore.Qt.PopupFocusReason)
        line_edit.selectAll()

        def accept():
            text = line_edit.text().strip()
            if text:
                model.setData(index, int(text), QtCore.Qt.EditRole)
                if option.widget:
                    option.widget.viewport().update()
            line_edit.close()

        def keyPressEvent(event_):
            if event_.key() == QtCore.Qt.Key_Escape:
                line_edit.close()
                return
            QtWidgets.QLineEdit.keyPressEvent(line_edit, event_)

        line_edit.returnPressed.connect(accept)
        line_edit.keyPressEvent = keyPressEvent

    def sizeHint(self, *args):
        return QtCore.QSize(140, self._preferred_height)