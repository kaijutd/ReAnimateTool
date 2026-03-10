# ui/mapping_table_model.py

from PySide6 import QtCore, QtGui

class MappingTableModel(QtCore.QAbstractTableModel):
    """Model for rig joint mappings."""

    HEADERS = ["Enabled", "Source Joint", "Target Joint", "Attributes", "Mode"]

    def __init__(self, mappings=None, parent=None):
        super().__init__(parent)
        self._mappings = mappings or []  # list of dicts

    # --- Required interface ---
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._mappings)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        mapping = self._mappings[row]

        if role == QtCore.Qt.DisplayRole:
            if col == 1:
                return mapping.get("source", "")
            elif col == 2:
                return mapping.get("target", "")
            elif col == 3:
                return ", ".join(mapping.get("attrs", []))
            elif col == 4:
                return mapping.get("mode", "Transfer")

        elif role == QtCore.Qt.CheckStateRole and col == 0:
            return QtCore.Qt.Checked if mapping.get("enabled", True) else QtCore.Qt.Unchecked

        elif role == QtCore.Qt.BackgroundRole:
            if not mapping.get("enabled", True):
                return QtGui.QColor(50, 50, 50)  # dimmed row background

        return None

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        if index.column() == 0:
            flags |= QtCore.Qt.ItemIsUserCheckable
        if index.column() in (2, 4):  # Target / Mode editable
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return False
        row = index.row()
        col = index.column()
        mapping = self._mappings[row]

        if col == 0 and role == QtCore.Qt.CheckStateRole:
            mapping["enabled"] = (value == QtCore.Qt.Checked)
        elif col == 2 and role == QtCore.Qt.EditRole:
            mapping["target"] = value
        elif col == 4 and role == QtCore.Qt.EditRole:
            mapping["mode"] = value
        else:
            return False

        self.dataChanged.emit(index, index)
        return True

    # --- Custom accessors ---
    def get_mappings(self):
        """Return all mappings (filtered by enabled state)."""
        return [m for m in self._mappings if m.get("enabled", True)]

    def set_mappings(self, mappings):
        self.beginResetModel()
        self._mappings = mappings
        self.endResetModel()
