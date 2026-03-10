"""
ui/delegates/attr_group_delegate.py - Delegate for attribute channel toggles.

Draws interactive toggle circles for translate, rotate, and scale attributes
with per-axis control (X/Y/Z) and a master toggle per group. Supports master
rows that propagate changes to child rows.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from ui.styles.common_style import apply_style


AXIS_COLORS = {
    "X": QtGui.QColor("#dc3232"),
    "Y": QtGui.QColor("#32dc32"),
    "Z": QtGui.QColor("#3232dc")
}

GREY_COLOR = QtGui.QColor("#777777")
BORDER_COLOR = QtGui.QColor("#555555")
TEXT_COLOR = QtGui.QColor("#e0e0e0")

MASTER_BG_COLOR = QtGui.QColor("#333366")
MASTER_BORDER_COLOR = QtGui.QColor("#007acc")
MASTER_ON_COLOR = QtGui.QColor("#aaaaaa")
MASTER_OFF_COLOR = QtGui.QColor("#444444")


class AttrGroupDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for attribute group toggles with master controller support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.circle_radius = 6
        self.row_height = 24
        self.spacing_x = 10
        self.margin_x = 12
        self.margin_y = 6

    def paint(self, painter, option, index):
        """Draw attribute groups with master toggle and per-axis circles."""
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        item = index.internalPointer()
        if not item:
            painter.restore()
            return

        data = index.model().data(index, QtCore.Qt.UserRole) or {}
        is_master = item.data.get("is_master", False)

        rect = option.rect
        bg_color = MASTER_BG_COLOR if is_master else QtGui.QColor("#2b2b2b")
        painter.fillRect(rect, bg_color)

        if is_master:
            painter.setPen(QtGui.QPen(MASTER_BORDER_COLOR, 1))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        font = option.font
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)

        circle_d = self.circle_radius * 2
        attr_names = ["translate", "rotate", "scale"]

        label_width = max(metrics.horizontalAdvance(attr.capitalize()) for attr in attr_names)
        circles_start_x = rect.left() + self.margin_x + label_width + 20
        y = rect.top() + self.margin_y

        for attr in attr_names:
            painter.setPen(TEXT_COLOR)
            painter.drawText(rect.left() + self.margin_x, y + metrics.ascent(), attr.capitalize())

            x = circles_start_x
            group_data = data.get(attr, {"X": True, "Y": True, "Z": True})
            all_enabled = all(group_data.values())

            # Master toggle circle
            painter.setPen(QtGui.QPen(BORDER_COLOR))
            painter.setBrush(MASTER_ON_COLOR if all_enabled else MASTER_OFF_COLOR)
            painter.drawEllipse(QtCore.QRectF(x, y, circle_d, circle_d))
            x += circle_d + self.spacing_x + 4

            # Axis circles
            for axis in ["X", "Y", "Z"]:
                color = AXIS_COLORS[axis] if group_data.get(axis, False) else GREY_COLOR
                painter.setBrush(QtGui.QBrush(color))
                painter.drawEllipse(QtCore.QRectF(x, y, circle_d, circle_d))
                x += circle_d + self.spacing_x

            y += self.row_height

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handle mouse interaction for attribute toggle circles."""
        if event.type() != QtCore.QEvent.MouseButtonRelease:
            return False

        item = index.internalPointer()
        if not item:
            return False

        is_master = getattr(item, "data", {}).get("is_master", False)
        data = model.data(index, QtCore.Qt.UserRole) or {}

        rect = option.rect
        metrics = QtGui.QFontMetrics(option.font)

        circle_d = self.circle_radius * 2
        attr_names = ["translate", "rotate", "scale"]

        label_width = max(metrics.horizontalAdvance(attr.capitalize()) for attr in attr_names)
        circles_start_x = rect.left() + self.margin_x + label_width + 20
        click_pos = event.pos()

        for attr in attr_names:
            y = rect.top() + self.margin_y + attr_names.index(attr) * self.row_height
            x = circles_start_x

            group_data = data.get(attr, {"X": True, "Y": True, "Z": True}).copy()

            master_rect = QtCore.QRectF(x, y, circle_d, circle_d)

            # Master toggle clicked
            if master_rect.contains(click_pos):
                all_on = all(group_data.values())
                for axis in group_data:
                    group_data[axis] = not all_on

                self._apply_change(model, index, attr, group_data, is_master)
                return True

            x += circle_d + self.spacing_x + 4

            # Axis toggle circles
            for axis in ["X", "Y", "Z"]:
                circle_rect = QtCore.QRectF(x, y, circle_d, circle_d)

                if circle_rect.contains(click_pos):
                    group_data[axis] = not group_data.get(axis, False)

                    self._apply_change(
                        model, index, attr, group_data, is_master, axis
                    )
                    return True

                x += circle_d + self.spacing_x

        return False

    def _apply_change(self, model, index, attr, group_data, is_master, axis=None):
        """Apply attribute changes and propagate master updates to children."""
        if is_master:
            model._last_changed_attr = (attr, axis)

            master_data = model.data(index, QtCore.Qt.UserRole) or {}

            if attr not in master_data:
                master_data[attr] = {"X": True, "Y": True, "Z": True}

            if axis:
                master_data[attr][axis] = group_data[axis]
            else:
                master_data[attr].update(group_data)

            model.setData(index, master_data, QtCore.Qt.UserRole)
            model.dataChanged.emit(index, index, [QtCore.Qt.UserRole])

            model.propagate_attr_group_from_master(
                attr,
                {axis: group_data[axis]} if axis else group_data,
                axis=axis,
            )

        else:
            data = model.data(index, QtCore.Qt.UserRole) or {}

            if attr not in data:
                data[attr] = {"X": True, "Y": True, "Z": True}

            if axis:
                data[attr][axis] = group_data[axis]
            else:
                data[attr].update(group_data)

            model.setData(index, data, QtCore.Qt.UserRole)
            model.dataChanged.emit(index, index, [QtCore.Qt.UserRole])

    def createEditor(self, parent, option, index):
        """Disable text editing for attribute cells."""
        return None

    def sizeHint(self, option, index):
        """Return the preferred delegate size."""
        font = option.font
        metrics = QtGui.QFontMetrics(font)

        total_height = 3 * self.row_height + 8
        label_width = max(
            metrics.horizontalAdvance(n.capitalize())
            for n in ["translate", "rotate", "scale"]
        )

        circle_space = (4 * (12 + self.spacing_x)) + 10
        total_width = label_width + circle_space + 30

        return QtCore.QSize(total_width, total_height)