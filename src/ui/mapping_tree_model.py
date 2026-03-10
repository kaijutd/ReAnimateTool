# ui/mapping_tree_model.py
from PySide6 import QtCore, QtGui
from core import utils
from copy import deepcopy


class MappingTreeItem:
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
    HEADERS = ["Source", "Enabled", "Target", "Attrs", "Mode", "Score", "Frame Offset"]

    def __init__(self, hierarchy=None, parent=None, target_list=None):
        super().__init__(parent)
        self.target_list = target_list or []
        self.root_item = MappingTreeItem({"children": []})

        if hierarchy:
            self.setup_model_data(hierarchy, self.root_item)

        # ----------------
        # Master controller row (always first child)
        # ----------------
        master_data = {
            "name": "Master Controller",
            "enabled": True,
            "target": "---",
            "attrs": {
                "translate": ["X", "Y", "Z"],
                "rotate": ["X", "Y", "Z"],
                "scale": ["X", "Y", "Z"]
            },
            "attr_enabled": {
                "master": True,
                "translate": {"X": True, "Y": True, "Z": True},
                "rotate": {"X": True, "Y": True, "Z": True},
                "scale": {"X": True, "Y": True, "Z": True}
            },
            "mode": "Transfer",
            "score": 1.0,
            "frame_offset": 0,
            "is_master": True
        }
        master_item = MappingTreeItem(master_data, parent=self.root_item)
        # insert as first child
        self.root_item.children.insert(0, master_item)

    # ---------------- Tree construction ----------------
    def setup_model_data(self, node_data, parent_item):
        if not node_data:
            return

        children_data = node_data.get("children", [])
        node_data.setdefault("enabled", True)
        node_data.setdefault("target", "")
        node_data.setdefault("attrs", {
            "translate": ["X", "Y", "Z"],
            "rotate": ["X", "Y", "Z"],
            "scale": ["X", "Y", "Z"]
        })
        node_data.setdefault("attr_enabled", {
            "master": True,
            "translate": {"X": True, "Y": True, "Z": True},
            "rotate": {"X": True, "Y": True, "Z": True},
            "scale": {"X": True, "Y": True, "Z": True}
        })
        node_data.setdefault("mode", "Transfer")
        node_data.setdefault("score", 0.0)
        node_data.setdefault("frame_offset",0)
        # Best-match auto target (logic moved to utils.get_best_match)
        src_name = node_data.get("name", "")
        best_match, score = utils.get_best_match(src_name, self.target_list)
        node_data["target"] = best_match
        node_data["score"] = score

        # Ensure every node has its own deep-copied dicts (avoid shared references)
        node_data["attr_enabled"] = deepcopy(node_data.get("attr_enabled", {}))

        item = MappingTreeItem(node_data, parent=parent_item)
        parent_item.append_child(item)

        for child in children_data:
            self.setup_model_data(child, item)

    # ---------------- QAbstractItemModel ----------------
    def rowCount(self, parent=QtCore.QModelIndex()):
        parent_item = parent.internalPointer() if parent.isValid() else self.root_item
        return parent_item.child_count()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if not item:
            return None
        col = index.column()

        # Color by score (Target column coloring)
        if role == QtCore.Qt.ForegroundRole and col == 2:
            score = item.data.get("score", 0)
            if isinstance(score, str) and score.upper() == "MANUAL":
                return QtGui.QColor("#888888")
            if isinstance(score, (int, float)):
                if score >= 0.8:
                    return QtGui.QColor("#00ff00")
                elif score >= 0.6:
                    return QtGui.QColor("#ffff00")
                else:
                    return QtGui.QColor("#ff5555")

        # Display text
        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return item.data.get("name", "")
            elif col == 2:
                tgt = item.data.get("target", "")
                return tgt.split("|")[-1] if tgt else ""
            elif col == 4:
                return item.data.get("mode", "")
            elif col == 5:
                score = item.data.get("score", 0)
                return f"{score:.2f}" if isinstance(score, float) else score
            elif col == 6:
                return item.data.get("frame_offset", 0)

        # Checkboxes
        if role == QtCore.Qt.CheckStateRole and col == 1:
            return QtCore.Qt.Checked if item.data.get("enabled", True) else QtCore.Qt.Unchecked

        # Custom attributes (for delegate)
        # IMPORTANT: return a deep copy to avoid delegate mutating internal state directly
        if role == QtCore.Qt.UserRole and col == 3:
            return deepcopy(item.data.get("attr_enabled", {}))
        elif col == 6:
            return str(item.data.get("frame_offset", 0))

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        col = index.column()
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        # Editable for Target, Attrs (delegate), and Mode
        if col in (2, 3, 4, 6):
            flags |= QtCore.Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=QtCore.Qt.EditRole):

        if not index.isValid():
            return False

        item = index.internalPointer()
        if not item:
            return False

        col = index.column()
        is_master = item.data.get("is_master", False)

        # ================== MASTER ROW ==================
        if is_master:

            if col == 1 and role == QtCore.Qt.CheckStateRole:
                item.data["enabled"] = (value == QtCore.Qt.Checked)
                for child in self.root_item.children[1:]:
                    self._set_enabled_recursive(child, value == QtCore.Qt.Checked)

                # --- 🔹 Force the view to refresh all enabled states ---
                if self.root_item.children:
                    first_index = self.index(0, 1, QtCore.QModelIndex())
                    last_index = self.index(self.rowCount(QtCore.QModelIndex()) - 1, 1, QtCore.QModelIndex())
                    self.dataChanged.emit(first_index, last_index, [QtCore.Qt.CheckStateRole])
            elif col == 3 and role == QtCore.Qt.UserRole:
                item.data["attr_enabled"] = deepcopy(value)

                attr_axis = getattr(self, "_last_changed_attr", None)
                if attr_axis:
                    attr, axis = attr_axis
                    print(f"[DEBUG] setData propagate -> attr={attr}, axis={axis}, group={value}")

                    def propagate_to_children(parent_item):
                        for child in parent_item.children:
                            child_data = child.data.get("attr_enabled", {}).copy()
                            if attr not in child_data:
                                child_data[attr] = {"X": True, "Y": True, "Z": True}

                            # Update only the affected attr/axis
                            if axis:
                                child_data[attr][axis] = value.get(axis, True)
                            else:
                                child_data[attr].update(value)

                            child.data["attr_enabled"] = child_data
                            propagate_to_children(child)

                    propagate_to_children(item)
                    self._last_changed_attr = None

                else:
                    print("[DEBUG] setData fallback: full sync")
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
                master_offset = int(value)
                item.data["frame_offset"] = master_offset
                for child in self.root_item.children[1:]:
                    self._set_frame_offset_recursive(child, master_offset)

                # 🔹 Recursively collect all indexes in column 6
                def collect_indexes(item):
                    idxs = [self.index(item.row(), 6, self.parent(self.index(item.row(), 0)))]
                    for child in item.children:
                        idxs.extend(collect_indexes(child))
                    return idxs

                all_indexes = collect_indexes(self.root_item.children[0])  # include master
                for idx in all_indexes:
                    self.dataChanged.emit(idx, idx, [QtCore.Qt.DisplayRole])

                return True  # stop further emit

            else:
                return False

        # ================== CHILD ROWS ==================
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

        # ✅ always refresh the edited cell itself
        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
        return True

    # ---------------- Recursive helpers ----------------
    def _set_enabled_recursive(self, item, state):
        item.data["enabled"] = state
        for child in item.children:
            self._set_enabled_recursive(child, state)

    def _set_attr_recursive(self, item, attr_enabled):
        # write a deepcopy so children don't share the same dict instance
        item.data["attr_enabled"] = deepcopy(attr_enabled)
        for child in item.children:
            self._set_attr_recursive(child, attr_enabled)

    def _set_frame_offset_recursive(self, item, value):
        item.data["frame_offset"] = value
        for child in item.children:
            self._set_frame_offset_recursive(child, value)

    def _set_mode_recursive(self, item, mode):
        item.data["mode"] = mode
        for child in item.children:
            self._set_mode_recursive(child, mode)

    def propagate_attr_group_from_master(self, attr, group_data, axis=None):
        """Propagate a master attr change — skip the master row and update the first real row + its descendants.
           This version avoids mutating self.root_item.data and ensures deep copies to prevent shared references.
        """
        from copy import deepcopy
        import pprint

        # --- Diagnostics (call count + snapshots) ---
        self._propagate_call_count = getattr(self, "_propagate_call_count", 0) + 1
        print(f"\n[PROP] call #{self._propagate_call_count}  attr={attr} axis={axis} group={group_data}")
        print(f"[PROP] _last_changed_attr = {getattr(self, '_last_changed_attr', None)}")
        master_item = self.root_item.children[0] if len(self.root_item.children) > 0 else None
        top_row = self.root_item.children[1] if len(self.root_item.children) > 1 else None
        print(f"[PROP] master_item = {getattr(master_item, 'data', {}).get('name') if master_item else None}")
        print(f"[PROP] top_row     = {getattr(top_row, 'data', {}).get('name') if top_row else None}")

        def snap(it):
            if not it:
                return None
            d = deepcopy(it.data.get("attr_enabled", {}))
            return {"name": it.data.get("name"), "is_master": it.data.get("is_master", False), "attr_enabled": d}

        pprint.pprint({"master": snap(master_item), "top_row": snap(top_row)})

        # --- Safety: ensure master exists ---
        if not master_item:
            print("[PROP] No master item found; aborting.")
            return

        # --- Update the top row (first real mapping, index 1) instead of mutating self.root_item.data ---
        if not top_row:
            print("[PROP] No top row found (no child after master) — nothing to propagate to.")
            return

        # Ensure top_row has its own dict
        top_attr = deepcopy(top_row.data.get("attr_enabled", {}))
        if attr not in top_attr:
            top_attr[attr] = {"X": True, "Y": True, "Z": True}

        before_top = deepcopy(top_attr[attr])
        if axis:
            top_attr[attr][axis] = group_data[axis]
        else:
            for ax, val in group_data.items():
                top_attr[attr][ax] = val

        top_row.data["attr_enabled"] = top_attr
        print(
            f"[PROP] Updated TOP ROW '{top_row.data.get('name')}' {attr} BEFORE: {before_top} AFTER: {top_attr[attr]}")

        # --- Recursive propagation: start from top_row's children only (skip master and top_row itself already set) ---
        visited = set()

        def recurse(parent_item, depth=0):
            # simple visited guard (protects against cycles)
            if parent_item in visited:
                return
            visited.add(parent_item)

            for i, child in enumerate(parent_item.children):
                # ensure child's attr_enabled dict exists and is a deepcopy
                cd = deepcopy(child.data.get("attr_enabled", {}))
                if attr not in cd:
                    cd[attr] = {"X": True, "Y": True, "Z": True}

                before = deepcopy(cd[attr])
                if axis:
                    cd[attr][axis] = group_data[axis]
                else:
                    for ax, val in group_data.items():
                        cd[attr][ax] = val

                child.data["attr_enabled"] = cd
                print(
                    f"{'   ' * depth}-> Child[{i}] '{child.data.get('name')}' updated ({attr}/{axis}) BEFORE:{before} AFTER:{cd[attr]}")

                # recurse deeper
                recurse(child, depth + 1)

        # Start recursion from top_row (we already updated top_row itself above; now update its children)
        recurse(top_row, depth=1)

        # Finalize
        print("[PROP] Propagation complete. layoutChanged.emit()")
        self.layoutChanged.emit()

    # ---------------- Indexing ----------------
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
        child_item = index.internalPointer()
        parent_item = child_item.parent_item
        if not parent_item or parent_item == self.root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    # ---------------- Export ----------------
    def get_mappings(self):
        """
        Return flattened mappings suitable for transfer.transfer_animation.
        Skips the master row entirely.
        """
        result = []

        def recurse(item):
            # skip master items explicitly
            if item.data.get("is_master", False):
                # traverse children but don't append master itself
                for child in item.children:
                    recurse(child)
                return

            if item.data.get("enabled", True):
                attrs = []
                for group, axes in item.data.get("attr_enabled", {}).items():
                    if group == "master":
                        continue
                    # axes is expected to be a dict { 'X': True, ... }
                    for axis, enabled in axes.items():
                        if enabled:
                            attrs.append(f"{group}{axis}")
                result.append({
                    "source": item.data.get("name", ""),
                    "target": item.data.get("target", ""),
                    "attrs": attrs,
                    "mode": item.data.get("mode", "Transfer"),
                    "frame_offset": item.data.get("frame_offset", 0),
                })

            for child in item.children:
                recurse(child)

        # root children: skip the master (index 0) at top level by letting recurse start at root
        for child in self.root_item.children:
            recurse(child)

        return result

    # ---------------- Serialization / Deserialization ----------------
    def serialize(self):
        """Return full tree data for saving to JSON, including master row."""

        def recurse(item):
            data = deepcopy(item.data)
            data["children"] = [recurse(child) for child in item.children]
            return data

        return [recurse(child) for child in self.root_item.children]  # include master at index 0

    @classmethod
    def deserialize(cls, data_list, target_list=None):
        """
        Build a MappingTreeModel from saved JSON data.
        data_list: list of serialized MappingTreeItem dicts
        """
        model = cls(hierarchy=None, target_list=target_list)
        model.root_item.children = []  # clear default master

        def recurse(node_data, parent_item):
            item = MappingTreeItem(deepcopy(node_data), parent=parent_item)
            parent_item.append_child(item)
            for child_data in node_data.get("children", []):
                recurse(child_data, item)

        for node_data in data_list:
            recurse(node_data, model.root_item)

        return model
