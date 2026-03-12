"""
ui/widgets/library_widget.py - Pose and Animation Library widget for ReAnimate Tool.
Provides a card-based browser for saved poses and animations with integrated mapping.
"""

from PySide6 import QtCore, QtGui, QtWidgets
import maya.cmds as cmds

from core import library_io
from ui.mapping_tree_model import MappingTreeModel
from ui.delegates.left_aligned_checkbox_delegate import LeftAlignedCheckBoxDelegate
from ui.delegates.attr_group_delegate import AttrGroupDelegate
from ui.delegates.mode_delegate import ModeDelegate
from ui.delegates.frame_offset_delegate import FrameOffsetDelegate
from ui.target_picker_popup import TargetPickerPopup

CARD_WIDTH = 180
CARD_HEIGHT = 140
THUMB_HEIGHT = 90
BG_COLOR = QtGui.QColor("#2b2b2b")
CARD_COLOR = QtGui.QColor("#333333")
SELECTED_COLOR = QtGui.QColor("#007acc")
TEXT_COLOR = QtGui.QColor("#e0e0e0")
TEXT_DISABLED_COLOR = QtGui.QColor("#777777")


class LibraryCard(QtWidgets.QWidget):
    """A single clickable card showing a thumbnail and entry name."""

    clicked = QtCore.Signal(dict)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.selected = False
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self):
        """Build card layout with thumbnail and name label."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.thumb_label = QtWidgets.QLabel()
        self.thumb_label.setFixedHeight(THUMB_HEIGHT)
        self.thumb_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumb_label.setStyleSheet("background-color: #222222; border-radius: 4px;")
        self._load_thumbnail()
        layout.addWidget(self.thumb_label)

        self.name_label = QtWidgets.QLabel(self.entry.get("name", ""))
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(f"color: {TEXT_COLOR.name()}; font-size: 10px;")
        layout.addWidget(self.name_label)

        ts = self.entry.get("timestamp", "")
        if ts:
            ts_label = QtWidgets.QLabel(ts)
            ts_label.setAlignment(QtCore.Qt.AlignCenter)
            ts_label.setStyleSheet(f"color: {TEXT_DISABLED_COLOR.name()}; font-size: 8px;")
            layout.addWidget(ts_label)

    def _load_thumbnail(self):
        """Load and display the thumbnail image or sprite sheet."""
        thumb_path = self.entry.get("thumbnail")
        if thumb_path:
            try:
                import os
                if os.path.exists(thumb_path):
                    pixmap = QtGui.QPixmap(thumb_path)
                    self.thumb_label.setPixmap(
                        pixmap.scaled(CARD_WIDTH - 8, THUMB_HEIGHT,
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation)
                    )
                    return
            except Exception:
                pass
        self.thumb_label.setText("No Preview")
        self.thumb_label.setStyleSheet(
            f"color: {TEXT_DISABLED_COLOR.name()}; background-color: #222222; border-radius: 4px;"
        )

    def set_selected(self, selected):
        """Update card selection state and trigger repaint."""
        self.selected = selected
        self.update()

    def paintEvent(self, event):
        """Draw card background with selection highlight."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = SELECTED_COLOR if self.selected else CARD_COLOR
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(color.lighter(130), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

    def mousePressEvent(self, event):
        """Emit clicked signal on left mouse press."""
        print(f"[LibraryCard] mousePressEvent: {self.entry.get('name')}")
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.entry)


class LibraryGrid(QtWidgets.QScrollArea):
    """Scrollable grid of LibraryCard widgets."""

    entry_selected = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._cards = []
        self._selected_card = None

        self._container = QtWidgets.QWidget()
        self._flow_layout = FlowLayout(self._container, margin=10, spacing=8)
        self.setWidget(self._container)

    def populate(self, entries):
        """Clear and repopulate the grid with new entries."""
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        self._selected_card = None

        for entry in entries:
            card = LibraryCard(entry)
            card.clicked.connect(self._on_card_clicked)
            self._flow_layout.addWidget(card)
            self._cards.append(card)

    def _on_card_clicked(self, entry):
        """Handle card selection and emit entry_selected signal."""
        for card in self._cards:
            is_selected = card.entry.get("path") == entry.get("path")
            card.set_selected(is_selected)
            if is_selected:
                self._selected_card = card
        self.entry_selected.emit(entry)

    def selected_entry(self):
        """Return the currently selected entry dict, or None."""
        return self._selected_card.entry if self._selected_card else None


class FlowLayout(QtWidgets.QLayout):
    """A layout that wraps widgets into rows like text flow."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        row_height = 0
        spacing = self.spacing()

        for item in self._items:
            w = item.widget()
            if not w:
                continue
            next_x = x + item.sizeHint().width() + spacing
            if next_x - spacing > rect.right() - margins.right() and row_height > 0:
                x = rect.x() + margins.left()
                y += row_height + spacing
                next_x = x + item.sizeHint().width() + spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = next_x
            row_height = max(row_height, item.sizeHint().height())

        return y + row_height - rect.y() + margins.bottom()


class LibraryBrowserTab(QtWidgets.QWidget):
    """Sub-tab for browsing, saving, and deleting library entries."""

    load_requested = QtCore.Signal(dict)

    def __init__(self, entry_type, parent=None):
        super().__init__(parent)
        self.entry_type = entry_type
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        """Build the browser layout with toolbar and card grid."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        toolbar = QtWidgets.QHBoxLayout()

        self.source_root_field = QtWidgets.QLineEdit()
        self.source_root_field.setPlaceholderText("Source root joint...")
        self.source_root_field.setMaximumWidth(200)
        self.pick_root_btn = QtWidgets.QPushButton("Pick")
        self.pick_root_btn.setMaximumWidth(50)
        self.pick_root_btn.setToolTip("Pick source root from Maya selection.")
        self.pick_root_btn.clicked.connect(self._pick_source_root)

        toolbar.addWidget(QtWidgets.QLabel("Source Root:"))
        toolbar.addWidget(self.source_root_field)
        toolbar.addWidget(self.pick_root_btn)
        toolbar.addSpacing(20)

        if self.entry_type == "pose":
            self.save_btn = QtWidgets.QPushButton("Save Current Pose")
        else:
            self.save_btn = QtWidgets.QPushButton("Save Current Animation")
        self.save_btn.setMaximumWidth(180)
        self.save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(self.save_btn)

        self.delete_btn = QtWidgets.QPushButton("Delete")
        self.delete_btn.setMaximumWidth(80)
        self.delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.grid = LibraryGrid()
        self.grid.entry_selected.connect(self._on_entry_selected)
        layout.addWidget(self.grid)

        self.load_btn = QtWidgets.QPushButton(
            "Load Pose into Mapping →" if self.entry_type == "pose"
            else "Load Animation into Mapping →"
        )
        self.load_btn.setMinimumHeight(32)
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._on_load)
        layout.addWidget(self.load_btn)

    def refresh(self):
        """Reload entries from disk and repopulate the grid."""
        entries = library_io.list_entries(self.entry_type)
        self.grid.populate(entries)
        self.load_btn.setEnabled(False)

    def _pick_source_root(self):
        """Set source root field from Maya selection."""
        sel = cmds.ls(selection=True, long=True)
        if sel:
            self.source_root_field.setText(sel[0])
        else:
            cmds.warning("Nothing selected — please select a root joint.")

    def _on_entry_selected(self, entry):
        """Enable load button when an entry is selected."""
        self.load_btn.setEnabled(True)

    def _on_save(self):
        """Prompt for name and save current pose or animation."""
        root = self.source_root_field.text().strip()
        if not root:
            QtWidgets.QMessageBox.warning(self, "No Source Root",
                                          "Please set a source root joint before saving.")
            return
        if not cmds.objExists(root):
            QtWidgets.QMessageBox.warning(self, "Invalid Root",
                                          f"Joint '{root}' does not exist in the scene.")
            return

        name, ok = QtWidgets.QInputDialog.getText(self, "Save Entry", "Entry name:")
        if not ok or not name.strip():
            return

        if self.entry_type == "pose":
            frame, ok = QtWidgets.QInputDialog.getInt(
                self, "Save Pose", "Frame to capture:",
                int(cmds.currentTime(q=True)), -10000, 10000
            )
            if not ok:
                return
            library_io.save_pose(name.strip(), root, frame)

        else:
            start = int(cmds.playbackOptions(q=True, min=True))
            end = int(cmds.playbackOptions(q=True, max=True))

            dialog = FrameRangeDialog(start, end, self)
            if dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            start, end = dialog.get_range()
            library_io.save_animation(name.strip(), root, start, end)

        self.refresh()

    def _on_delete(self):
        """Delete the selected entry after confirmation."""
        entry = self.grid.selected_entry()
        if not entry:
            QtWidgets.QMessageBox.information(self, "No Selection",
                                              "Please select an entry to delete.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Entry",
            f"Delete '{entry['name']}'? This cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        library_io.delete_entry(entry["path"])
        self.refresh()

    def _on_load(self):
        """Emit load_requested signal with the selected entry."""
        entry = self.grid.selected_entry()
        print(f"[_on_load] entry = {entry}")
        if entry:
            self.load_requested.emit(entry)


class FrameRangeDialog(QtWidgets.QDialog):
    """Simple dialog for entering a start and end frame."""

    def __init__(self, start, end, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Frame Range")
        layout = QtWidgets.QFormLayout(self)

        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setRange(-10000, 10000)
        self.start_spin.setValue(start)
        self.end_spin = QtWidgets.QSpinBox()
        self.end_spin.setRange(-10000, 10000)
        self.end_spin.setValue(end)

        layout.addRow("Start Frame:", self.start_spin)
        layout.addRow("End Frame:", self.end_spin)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_range(self):
        """Return the entered start and end frame as a tuple."""
        return self.start_spin.value(), self.end_spin.value()


class LibraryMappingTab(QtWidgets.QWidget):
    """Sub-tab showing the mapping tree for a loaded library entry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mapping_model = None
        self.current_entry = None
        self._setup_ui()

    def _setup_ui(self):
        """Build the mapping tab with entry info, tree, and apply button."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self.entry_label = QtWidgets.QLabel("No entry loaded.")
        self.entry_label.setStyleSheet("color: #777; font-size: 10px;")
        layout.addWidget(self.entry_label)

        target_layout = QtWidgets.QHBoxLayout()
        target_layout.addWidget(QtWidgets.QLabel("Target Root:"))
        self.target_root_field = QtWidgets.QLineEdit()
        self.target_root_field.setPlaceholderText("Target root joint...")
        self.pick_target_btn = QtWidgets.QPushButton("Pick")
        self.pick_target_btn.setMaximumWidth(50)
        self.pick_target_btn.clicked.connect(self._pick_target_root)
        self.load_tree_btn = QtWidgets.QPushButton("Build Mapping")
        self.load_tree_btn.setMaximumWidth(120)
        self.load_tree_btn.clicked.connect(self._build_mapping)
        target_layout.addWidget(self.target_root_field)
        target_layout.addWidget(self.pick_target_btn)
        target_layout.addWidget(self.load_tree_btn)
        target_layout.addStretch()
        layout.addLayout(target_layout)

        self.mapping_tree = QtWidgets.QTreeView()
        self.mapping_tree.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.mapping_tree.header().setStretchLastSection(True)
        layout.addWidget(self.mapping_tree)

        self.apply_btn = QtWidgets.QPushButton("Apply to Target")
        self.apply_btn.setMinimumHeight(35)
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(self.apply_btn)

    def load_entry(self, entry):
        """Load a library entry and update the info label."""
        self.current_entry = entry
        name = entry.get("name", "").split("|")[-1]
        ts = entry.get("timestamp", "")
        entry_type = entry.get("type", "")

        # Load the full data to get saved frame info
        try:
            if entry_type == "pose":
                data = library_io.load_pose(entry["path"])
                frame_info = f"Saved at frame {data.get('frame', '?')}"
            else:
                data = library_io.load_animation(entry["path"])
                frame_info = f"Frames {data.get('start_frame', '?')} - {data.get('end_frame', '?')}"
        except Exception:
            frame_info = ""

        self.entry_label.setText(
            f"Loaded: {name}  |  {entry_type.capitalize()}  |  {ts}"
            + (f"  |  {frame_info}" if frame_info else "")
        )
        self.apply_btn.setEnabled(False)
        self.mapping_model = None

        if self.target_root_field.text().strip():
            self._build_mapping()

    def _pick_target_root(self):
        """Set target root from Maya selection."""
        sel = cmds.ls(selection=True, long=True)
        if sel:
            self.target_root_field.setText(sel[0])
        else:
            cmds.warning("Nothing selected — please select a root joint.")

    def _build_mapping(self):
        """Build mapping tree from loaded entry's source joints and target root."""
        if not self.current_entry:
            QtWidgets.QMessageBox.warning(self, "No Entry", "Please load an entry first.")
            return

        tgt_root = self.target_root_field.text().strip()
        if not tgt_root or not cmds.objExists(tgt_root):
            QtWidgets.QMessageBox.warning(self, "Invalid Target",
                                          "Please set a valid target root joint.")
            return

        try:
            data = library_io.load_pose(self.current_entry["path"]) \
                if self.current_entry["type"] == "pose" \
                else library_io.load_animation(self.current_entry["path"])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load Failed", f"Could not load entry:\n{e}")
            return

        src_root = data.get("root", "")
        saved_mapping = data.get("mapping")

        def gather_targets(joint):
            children = cmds.listRelatives(joint, c=True, type="joint") or []
            result = [joint]
            for c in children:
                result.extend(gather_targets(c))
            return result

        target_list = gather_targets(tgt_root)

        if saved_mapping:
            self.mapping_model = MappingTreeModel.deserialize(saved_mapping, target_list=target_list)
        else:
            def build_hierarchy(joint):
                if not cmds.objExists(joint):
                    return None
                children = cmds.listRelatives(joint, c=True, type="joint") or []
                return {
                    "enabled": True,
                    "name": joint,
                    "target": "",
                    "attrs": {"translate": ["X", "Y", "Z"],
                              "rotate": ["X", "Y", "Z"],
                              "scale": ["X", "Y", "Z"]},
                    "mode": "Transfer",
                    "score": 0.0,
                    "children": [build_hierarchy(c) for c in children if c]
                }
            hierarchy = build_hierarchy(src_root) if src_root and cmds.objExists(src_root) else None
            self.mapping_model = MappingTreeModel(hierarchy, target_list=target_list)

        self.mapping_tree.setModel(self.mapping_model)
        QtCore.QTimer.singleShot(0, self._setup_tree_delegates)
        QtCore.QTimer.singleShot(100, self.mapping_tree.expandAll)
        self.apply_btn.setEnabled(True)

    def _setup_tree_delegates(self):
        """Apply delegates to the mapping tree columns."""
        frame_diff = (
            cmds.playbackOptions(animationEndTime=True, q=True) -
            cmds.playbackOptions(animationStartTime=True, q=True)
        )
        self.mapping_tree.setItemDelegateForColumn(
            1, LeftAlignedCheckBoxDelegate(self.mapping_tree, box_size=16, left_margin=4))
        self.mapping_tree.setItemDelegateForColumn(
            3, AttrGroupDelegate(self.mapping_tree))
        self.mapping_tree.setItemDelegateForColumn(
            4, ModeDelegate(self.mapping_tree))
        self.mapping_tree.setItemDelegateForColumn(
            6, FrameOffsetDelegate(self.mapping_tree, -frame_diff, frame_diff))

        self.mapping_tree.setAlternatingRowColors(True)
        self.mapping_tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.mapping_tree.setUniformRowHeights(True)
        self.mapping_tree.setIndentation(18)

        header = self.mapping_tree.header()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.mapping_tree.setColumnWidth(1, 36)
        header.moveSection(1, 0)
        self.mapping_tree.setEditTriggers(
        QtWidgets.QAbstractItemView.DoubleClicked |
        QtWidgets.QAbstractItemView.SelectedClicked
        )
    
        self.mapping_tree.clicked.connect(self._on_tree_clicked)

    def _on_tree_clicked(self, index):
        if not index.isValid() or index.column() != 2:
            return

        tgt_root = self.target_root_field.text().strip()
        if not tgt_root or not cmds.objExists(tgt_root):
            return

        def build_joint_hierarchy(joint):
            children = cmds.listRelatives(joint, c=True, type="joint") or []
            return {"name": joint, "children": [build_joint_hierarchy(c) for c in children]}

        self._target_popup = TargetPickerPopup([build_joint_hierarchy(tgt_root)], self)
        self._target_popup.joint_selected.connect(lambda j: self._on_target_selected(index, j))

        rect = self.mapping_tree.visualRect(index)
        self._target_popup.move(self.mapping_tree.viewport().mapToGlobal(rect.bottomLeft()))
        self._target_popup.show()

    def _on_target_selected(self, index, joint):
        self.mapping_model.setData(index, joint, QtCore.Qt.EditRole)
        self.mapping_model.setData(index, QtGui.QColor("#555555"), QtCore.Qt.ForegroundRole)

    def _on_apply(self):
        """Apply the loaded entry to the target using the current mapping."""
        if not self.current_entry or not self.mapping_model:
            return

        mappings = self.mapping_model.get_mappings()
        if not mappings:
            QtWidgets.QMessageBox.warning(self, "No Mappings",
                                          "No enabled mappings to apply.")
            return

        try:
            if self.current_entry["type"] == "pose":
                data = library_io.load_pose(self.current_entry["path"])
                library_io.apply_pose(data, mappings)
            else:
                data = library_io.load_animation(self.current_entry["path"])
                frame_offset, ok = QtWidgets.QInputDialog.getInt(
                    self, "Frame Offset", "Apply with frame offset:",
                    0, -10000, 10000
                )
                if not ok:
                    return
                library_io.apply_animation(data, mappings, frame_offset=frame_offset)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Apply Failed", f"Could not apply entry:\n{e}")


class LibraryWidget(QtWidgets.QWidget):
    """
    Main library widget containing Poses and Animations browser tabs
    and an integrated Mapping tab for applying entries to target rigs.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the two-level tab structure."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.outer_tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.outer_tabs)

        # --- Library tab (Poses + Animations) ---
        library_container = QtWidgets.QWidget()
        library_layout = QtWidgets.QVBoxLayout(library_container)
        library_layout.setContentsMargins(0, 0, 0, 0)

        self.inner_tabs = QtWidgets.QTabWidget()
        self.pose_tab = LibraryBrowserTab("pose")
        self.anim_tab = LibraryBrowserTab("animation")
        self.inner_tabs.addTab(self.pose_tab, "Poses")
        self.inner_tabs.addTab(self.anim_tab, "Animations")
        library_layout.addWidget(self.inner_tabs)

        self.outer_tabs.addTab(library_container, "Library")

        # --- Mapping tab ---
        self.mapping_tab = LibraryMappingTab()
        self.outer_tabs.addTab(self.mapping_tab, "Mapping")

        # Wire load signals to mapping tab
        self.pose_tab.load_requested.connect(self._on_load_requested)
        self.anim_tab.load_requested.connect(self._on_load_requested)

    def _on_load_requested(self, entry):
        """Load entry into mapping tab and switch to it."""
        print(f"[_on_load_requested] entry = {entry}")
        self.mapping_tab.load_entry(entry)
        self.outer_tabs.setCurrentWidget(self.mapping_tab)