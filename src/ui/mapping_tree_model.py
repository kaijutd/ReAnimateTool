"""
ui/mapping_tree_model.py - Tree model for joint mapping in ReAnimate Tool.
Manages source/target joint pairs, attributes, transfer modes, and frame offsets.
"""

from PySide6 import QtCore, QtGui
from copy import deepcopy
from core import utils


class MappingTreeItem:
    """A single node in the mapping tree, wrapping joint data and child relationships."""

    def __init__(self, data, parent=None):
        self.parent_item = parent
        self.children = []
        self.data = data or {}

    def append_child(self, child):
        self.children.append(child)
        child.parent_item = self

    def child(self, row):
        return self.children[row] if 0 <= row < len(self.children) else None

    def child_count(self):
        return len(self.children)

    def column_count(self):
        return 7  # Source, Enabled, Target, Attrs, Mode, Score, Frame Offset

    def row(self):
        if self.parent_item:
            return self.parent_item.children.index(self)
        return 0


class MappingTreeModel(QtCore.QAbstractItemModel):
    """Tree model backing the mapping QTreeView. Supports master row propagation and serialization."""

    HEADERS = ["Source", "Enabled", "Target", "Attrs", "Mode", "Score", "Frame Offset"]

    _DEFAULT_ATTRS = {
        "translate": ["X", "Y", "Z"],
        "rotate": ["X", "Y", "Z"],
        "scale": ["X", "Y", "Z"]
    }

    _DEFAULT_ATTR_ENABLED = {
        "master": True,
        "translate": {"X": True, "Y": True, "Z": True},
        "rotate": {"X": True, "Y": True, "Z": True},
        "scale": {"X": True, "Y": True, "Z": True}
    }

    def __init__(self, hierarchy=None, parent=None, target_list=None):
        super().__init__(parent)
        self.target_list = target_list or []
        self.root_item = MappingTreeItem({"children": []})

        if hierarchy:
            self.setup_model_data(hierarchy, self.root_item)

        master_data = {
            "name": "Master Controller",
            "enabled": True,
            "target": "---",
            "attrs": deepcopy(self._DEFAULT_ATTRS),
            "attr_enabled": deepcopy(self._DEFAULT_ATTR_ENABLED),
            "mode": "Transfer",
            "score": 1.0,
            "frame_offset": 0,
            "is_master": True
        }
        master_item = MappingTreeItem(master_data, parent=self.root_item)
        self.root_item.children.insert(0, master_item)

    # --- Tree Construction ---

    def setup_model_data(self, node_data, parent_item):
        """Recursively build tree items from a hierarchy dict, auto-filling target matches."""
        if not node_data:
            return

        children_data = node_data.get("children", [])
        node_data.setdefault("enabled", True)
        node_data.setdefault("target", "")
        node_data.setdefault("attrs", deepcopy(self._DEFAULT_ATTRS))
        node_data.setdefault("attr_enabled", deepcopy(self._DEFAULT_ATTR_ENABLED))
        node_data.setdefault("mode", "Transfer")
        node_data.setdefault("score", 0.0)
        node_data.setdefault("frame_offset", 0)

        src_name = node_data.get("name", "")
        node_data["target"], node_data["score"] = utils.get_best_match(src_name, self.target_list)
        node_data["attr_enabled"] = deepcopy(node_data.get("attr_enabled", {}))

        item = MappingTreeItem(node_data, parent=parent_item)
        parent_item.append_child(item)

        for child in children_data:
            self.setup_model_data(child, item)

    # --- QAbstractItemModel ---

    def rowCount(self, parent=QtCore.QModelIndex()):
        parent_item = parent.internalPointer() if parent.isValid() else self.root_item
        return parent_item.child_count()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        parent_item = parent.internalPointer() if parent.isValid() else self.root_item
        child_item = parent_item.child(row)
        return self.createIndex(row, column, child_item) if child_item else QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        parent_item = index.internalPointer().parent_item
        if not parent_item or parent_item == self.root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        if index.column() in (2, 3, 4, 6):
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if not item:
            return None
        col = index.column()

        if role == QtCore.Qt.ForegroundRole and col == 2:
            score = item.data.get("score", 0)
            if isinstance(score, str) and score.upper() == "MANUAL":
                return QtGui.QColor("#888888")
            if isinstance(score, (int, float)):
                if score >= 0.8:   return QtGui.QColor("#00ff00")
                elif score >= 0.6: return QtGui.QColor("#ffff00")
                else:              return QtGui.QColor("#ff5555")

        if role == QtCore.Qt.DisplayRole:
            if col == 0: return item.data.get("name", "")
            if col == 2:
                tgt = item.data.get("target", "")
                return tgt.split("|")[-1] if tgt else ""
            if col == 4: return item.data.get("mode", "")
            if col == 5:
                score = item.data.get("score", 0)
                return f"{score:.2f}" if isinstance(score, float) else score
            if col == 6: return item.data.get("frame_offset", 0)

        if role == QtCore.Qt.CheckStateRole and col == 1:
            return QtCore.Qt.Checked if item.data.get("enabled", True) else QtCore.Qt.Unchecked

        if role == QtCore.Qt.UserRole and col == 3:
            return deepcopy(item.data.get("attr_enabled", {}))

        if col == 6:
            return str(item.data.get("frame_offset", 0))

        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if not index.isValid():
            return False
        item = index.internalPointer()
        if not item:
            return False

        col = index.column()
        is_master = item.data.get("is_master", False)

        if is_master:
            if col == 1 and role == QtCore.Qt.CheckStateRole:
                item.data["enabled"] = (value == QtCore.Qt.Checked)
                for child in self.root_item.children[1:]:
                    self._set_enabled_recursive(child, value == QtCore.Qt.Checked)
                first = self.index(0, 1, QtCore.QModelIndex())
                last = self.index(self.rowCount(QtCore.QModelIndex()) - 1, 1, QtCore.QModelIndex())
                self.dataChanged.emit(first, last, [QtCore.Qt.CheckStateRole])

            elif col == 3 and role == QtCore.Qt.UserRole:
                item.data["attr_enabled"] = deepcopy(value)
                attr_axis = getattr(self, "_last_changed_attr", None)
                if attr_axis:
                    attr, axis = attr_axis
                    def propagate(parent_item):
                        for child in parent_item.children:
                            cd = child.data.get("attr_enabled", {}).copy()
                            cd.setdefault(attr, {"X": True, "Y": True, "Z": True})
                            if axis:
                                cd[attr][axis] = value.get(axis, True)
                            else:
                                cd[attr].update(value)
                            child.data["attr_enabled"] = cd
                            propagate(child)
                    propagate(item)
                    self._last_changed_attr = None
                else:
                    for child in self.root_item.children[1:]:
                        self._set_attr_recursive(child, deepcopy(value))
                self.layoutChanged.emit()

            elif col == 4 and role == QtCore.Qt.EditRole:
                item.data["mode"] = value
                for child in self.root_item.children[1:]:
                    self._set_mode_recursive(child, value)

            elif col == 2 and role == QtCore.Qt.EditRole:
                item.data["target"] = value
                item.data["score"] = "MANUAL"
                for child in self.root_item.children[1:]:
                    child.data["target"] = value
                    child.data["score"] = "MANUAL"

            elif col == 6 and role == QtCore.Qt.EditRole:
                item.data["frame_offset"] = int(value)
                for child in self.root_item.children[1:]:
                    self._set_frame_offset_recursive(child, int(value))

                def collect_indexes(item):
                    idxs = [self.index(item.row(), 6, self.parent(self.index(item.row(), 0)))]
                    for child in item.children:
                        idxs.extend(collect_indexes(child))
                    return idxs

                for idx in collect_indexes(self.root_item.children[0]):
                    self.dataChanged.emit(idx, idx, [QtCore.Qt.DisplayRole])
                return True

            else:
                return False

        else:
            if col == 1 and role == QtCore.Qt.CheckStateRole:
                item.data["enabled"] = (value == QtCore.Qt.Checked)
            elif col == 2 and role == QtCore.Qt.EditRole:
                item.data["target"] = value
                item.data["score"] = "MANUAL"
            elif col == 3 and role == QtCore.Qt.UserRole:
                item.data["attr_enabled"] = deepcopy(value)
            elif col == 4 and role == QtCore.Qt.EditRole:
                item.data["mode"] = value
            elif col == 6 and role == QtCore.Qt.EditRole:
                item.data["frame_offset"] = int(value)
            else:
                return False

        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
        return True

    # --- Recursive Helpers ---

    def _set_enabled_recursive(self, item, state):
        """Recursively set enabled state on all descendants."""
        item.data["enabled"] = state
        for child in item.children:
            self._set_enabled_recursive(child, state)

    def _set_attr_recursive(self, item, attr_enabled):
        """Recursively apply a deep-copied attr_enabled dict to all descendants."""
        item.data["attr_enabled"] = deepcopy(attr_enabled)
        for child in item.children:
            self._set_attr_recursive(child, attr_enabled)

    def _set_frame_offset_recursive(self, item, value):
        """Recursively set frame offset on all descendants."""
        item.data["frame_offset"] = value
        for child in item.children:
            self._set_frame_offset_recursive(child, value)

    def _set_mode_recursive(self, item, mode):
        """Recursively set transfer mode on all descendants."""
        item.data["mode"] = mode
        for child in item.children:
            self._set_mode_recursive(child, mode)

    # --- Export ---

    def get_mappings(self):
        """Return flattened enabled mappings for use by transfer.transfer_animation."""
        result = []

        def recurse(item):
            if item.data.get("is_master", False):
                for child in item.children:
                    recurse(child)
                return
            if item.data.get("enabled", True):
                attrs = [
                    f"{group}{axis}"
                    for group, axes in item.data.get("attr_enabled", {}).items()
                    if group != "master"
                    for axis, enabled in axes.items()
                    if enabled
                ]
                result.append({
                    "source": item.data.get("name", ""),
                    "target": item.data.get("target", ""),
                    "attrs": attrs,
                    "mode": item.data.get("mode", "Transfer"),
                    "frame_offset": item.data.get("frame_offset", 0),
                })
            for child in item.children:
                recurse(child)

        for child in self.root_item.children:
            recurse(child)
        return result

    # --- Serialization ---

    def serialize(self):
        """Serialize the full tree to a list of dicts for JSON saving."""
        def recurse(item):
            data = deepcopy(item.data)
            data["children"] = [recurse(child) for child in item.children]
            return data
        return [recurse(child) for child in self.root_item.children]

    @classmethod
    def deserialize(cls, data_list, target_list=None):
        """Rebuild a MappingTreeModel from saved JSON data."""
        model = cls(hierarchy=None, target_list=target_list)
        model.root_item.children = []

        def recurse(node_data, parent_item):
            item = MappingTreeItem(deepcopy(node_data), parent=parent_item)
            parent_item.append_child(item)
            for child_data in node_data.get("children", []):
                recurse(child_data, item)

        for node_data in data_list:
            recurse(node_data, model.root_item)
        return model