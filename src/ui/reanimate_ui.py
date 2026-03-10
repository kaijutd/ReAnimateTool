# ui/reanimate_ui.py
from PySide6 import QtCore, QtGui, QtWidgets
from ui.target_picker_popup import TargetPickerPopup
import maya.cmds as cmd
from ui.styles.common_style import apply_style
from ui.widgets.anim_noise_widget import AnimationNoiseWidget

class ReAnimateToolUI(QtWidgets.QWidget):
    """Pure UI class for ReAnimate Tool."""

    def __init__(self, parent=None):
        super().__init__(parent)  # pass parent to QWidget
        self.setWindowTitle("ReAnimate 0.2")
        self.setMinimumWidth(700)
        self.setLayout(QtWidgets.QVBoxLayout())

        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.layout().addWidget(self.tabs)

        self.mapping_tab = QtWidgets.QWidget()
        self.anim_noise = AnimationNoiseWidget(self)
        apply_style(self.anim_noise,"DARK")
        self.library_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.mapping_tab, "Animation Transfer")
        self.tabs.addTab(self.library_tab, "Pose & Animation Library")
        self.tabs.addTab(self.anim_noise, "Anim Noise")

        # build tab contents
        self._setup_mapping_tab()
        self._setup_library_tab()

        # Initialize popup reference
        self._target_popup = None
        # Connect tree click
        self.mapping_tree.clicked.connect(self.on_tree_clicked)


        # Footer bar (About/Help) — moved to bottom, subtle
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        self.about_btn = QtWidgets.QPushButton("About")
        self.help_btn = QtWidgets.QPushButton("Help")
        for btn in (self.about_btn, self.help_btn):
            btn.setFlat(True)
            btn.setStyleSheet("color: #888;")
        footer.addWidget(self.about_btn)
        footer.addWidget(self.help_btn)
        self.layout().addLayout(footer)

        apply_style(self,"DARK")

    # ----------------------------
    # Mapping Tab
    # ----------------------------
    # ----------------------------
    # Mapping Tab Setup (Option 1)
    # ----------------------------

    def _setup_mapping_tab(self):
        """Builds the Animation Transfer (Mapping) tab with dynamic resizing."""
        layout = QtWidgets.QVBoxLayout(self.mapping_tab)

        # Scrollable content
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        # ------------------------
        # Rig Selection
        # ------------------------
        rig_box = QtWidgets.QGroupBox("Rig Selection")
        rig_layout = QtWidgets.QGridLayout()

        self.source_root_field = QtWidgets.QLineEdit()
        self.target_root_field = QtWidgets.QLineEdit()
        self.source_pick_button = QtWidgets.QPushButton("Pick Source")
        self.target_pick_button = QtWidgets.QPushButton("Pick Target")
        self.load_rigs_button = QtWidgets.QPushButton("Load Rigs")
        self.save_mapping_button = QtWidgets.QPushButton("Save Mapping")
        self.load_mapping_button = QtWidgets.QPushButton("Load Mapping")
        self.transfer_anim_button = QtWidgets.QPushButton("Transfer Animation")

        rig_layout.addWidget(QtWidgets.QLabel("Source Root:"), 0, 0)
        rig_layout.addWidget(self.source_root_field, 0, 1)
        rig_layout.addWidget(self.source_pick_button, 0, 2)
        rig_layout.addWidget(QtWidgets.QLabel("Target Root:"), 1, 0)
        rig_layout.addWidget(self.target_root_field, 1, 1)
        rig_layout.addWidget(self.target_pick_button, 1, 2)
        rig_layout.addWidget(self.load_rigs_button, 2, 0, 1, 3)
        rig_layout.addWidget(self.transfer_anim_button, 3, 0, 1, 3)
        rig_box.setLayout(rig_layout)
        scroll_layout.addWidget(rig_box)

        # ------------------------
        # Save / Load Mapping
        # ------------------------
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.save_mapping_button)
        btn_layout.addWidget(self.load_mapping_button)
        scroll_layout.addLayout(btn_layout)

        # ------------------------
        # Tree View
        # ------------------------
        self.mapping_tree = QtWidgets.QTreeView(scroll_content)
        scroll_layout.addWidget(self.mapping_tree)

        # Allow the tree to resize with content
        self.mapping_tree.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.mapping_tree.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.mapping_tree.header().setStretchLastSection(True)

        # ------------------------
        # Scroll Area Wrapper
        # ------------------------
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.mapping_scroll = scroll

        # ------------------------
        # Deferred Maya-safe setup
        # ------------------------
        import maya.utils

        def deferred_tree_setup():
            from ui.mapping_tree_model import MappingTreeModel
            from ui.delegates.left_aligned_checkbox_delegate import LeftAlignedCheckBoxDelegate
            from ui.delegates.attr_group_delegate import AttrGroupDelegate
            from ui.delegates.mode_delegate import ModeDelegate
            from ui.delegates.frame_offset_delegate import FrameOffsetDelegate

            # Model
            self.mapping_model = MappingTreeModel()
            self.mapping_tree.setModel(self.mapping_model)

            # Delegates
            left_delegate = LeftAlignedCheckBoxDelegate(self.mapping_tree, box_size=16, left_margin=4)
            self.mapping_tree.setItemDelegateForColumn(1, left_delegate)
            attr_delegate = AttrGroupDelegate(self.mapping_tree)
            self.mapping_tree.setItemDelegateForColumn(3, attr_delegate)
            mode_delegate = ModeDelegate(self.mapping_tree)
            self.mapping_tree.setItemDelegateForColumn(4, mode_delegate)
            frame_diff =(cmd.playbackOptions(animationEndTime=True, q=True) - cmd.playbackOptions(animationStartTime=True, q=True))
            frame_delegate = FrameOffsetDelegate(self.mapping_tree,-(frame_diff) , (frame_diff))
            self.mapping_tree.setItemDelegateForColumn(6, frame_delegate)

            # Appearance
            self.mapping_tree.setAlternatingRowColors(True)
            self.mapping_tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.mapping_tree.setEditTriggers(
                QtWidgets.QAbstractItemView.DoubleClicked |
                QtWidgets.QAbstractItemView.SelectedClicked
            )
            self.mapping_tree.setUniformRowHeights(True)
            self.mapping_tree.setIndentation(18)

            # Column sizing
            header = self.mapping_tree.header()
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
            self.mapping_tree.setColumnWidth(1, 36)
            header.moveSection(1, 0)

            # **Wait until tree is visible** before touching verticalHeader
            def set_row_height():
                vh = getattr(self.mapping_tree, "verticalHeader", None)
                if vh:
                    vh().setDefaultSectionSize(28)
                else:
                    # fallback: try again next frame
                    QtCore.QTimer.singleShot(50, set_row_height)

            QtCore.QTimer.singleShot(0, set_row_height)

            # Resize attrs column after small delay
            def resize_attrs_column():
                option = QtWidgets.QStyleOptionViewItem()
                index = self.mapping_model.index(0, 3)
                width = attr_delegate.sizeHint(option, index).width()
                self.mapping_tree.setColumnWidth(3, width)

            QtCore.QTimer.singleShot(100, resize_attrs_column)
            self.mapping_tree.expanded.connect(resize_attrs_column)
            self.mapping_tree.collapsed.connect(resize_attrs_column)

            # Cap the max height to 70% of screen
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            max_height = int(screen.height() * 0.7)
            self.setMaximumHeight(max_height)

            # Expand and resize columns initially
            self.mapping_tree.expandAll()
            for i in range(self.mapping_model.columnCount()):
                self.mapping_tree.resizeColumnToContents(i)



        maya.utils.executeDeferred(deferred_tree_setup)
        self.adjust_window_to_tree(extra_width=175,extra_height=125)




    def on_tree_clicked(self, index):
        """Handle clicks on target and attribute columns."""
        if not index.isValid():
            return

        model = self.mapping_tree.model()
        col = index.column()

        # --- Target Picker ---
        if col == 2:
            tgt_root = self.target_root_field.text().strip()
            if not tgt_root:
                return

            def build_joint_hierarchy(joint):
                children = cmd.listRelatives(joint, c=True, type="joint") or []
                return {"name": joint, "children": [build_joint_hierarchy(c) for c in children]}

            hierarchy = build_joint_hierarchy(tgt_root)
            self._target_popup = TargetPickerPopup([hierarchy], self)
            self._target_popup.joint_selected.connect(lambda j: self.on_target_selected(index, j))

            rect = self.mapping_tree.visualRect(index)
            global_pos = self.mapping_tree.viewport().mapToGlobal(rect.bottomLeft())
            self._target_popup.move(global_pos)
            self._target_popup.show()
            return


    def on_target_selected(self, index, joint_name):
        model = self.mapping_tree.model()
        # Set the selected joint
        model.setData(index, joint_name, QtCore.Qt.EditRole)
        # Mark as manual by coloring gray
        model.setData(index, QtGui.QColor("#555555"), QtCore.Qt.ForegroundRole)

    def show_target_picker(self, index):
        tgt_root = self.target_root_field.text().strip()
        if not tgt_root:
            return

        def gather_targets(joint):
            children = cmd.listRelatives(joint, c=True, type="joint") or []
            result = [joint]
            for c in children:
                result.extend(gather_targets(c))
            return result

        all_joints = gather_targets(tgt_root)


        # Create and position popup
        self._target_popup = TargetPickerPopup(all_joints, self)
        self._target_popup.joint_selected.connect(lambda j: self.on_target_selected(index, j))

        rect = self.mapping_tree.visualRect(index)
        global_pos = self.mapping_tree.viewport().mapToGlobal(rect.bottomLeft())
        self._target_popup.move(global_pos)
        self._target_popup.show()




    def _on_enable_toggle(self, row, state):
        """Dim or enable a row visually when the Enabled checkbox changes."""
        is_enabled = (state == QtCore.Qt.Checked)
        model = self.mapping_tree.model()
        if not model:
            return
        index_count = model.columnCount()
        for col in range(1, index_count):
            idx = model.index(row, col)
            model.setData(idx, QtGui.QColor("#e0e0e0") if is_enabled else QtGui.QColor("#555555"),
                          QtCore.Qt.ForegroundRole)
        self.mapping_tree.viewport().update()


    # ----------------------------
    # Library Tab
    # ----------------------------
    def _setup_library_tab(self):
        layout = QtWidgets.QGridLayout(self.library_tab)
        self.save_source_pose_btn = QtWidgets.QPushButton("💾 Save Source Pose")
        self.save_target_pose_btn = QtWidgets.QPushButton("💾 Save Target Pose")
        self.load_pose_btn = QtWidgets.QPushButton("📂 Load Pose to Target")
        self.save_anim_btn = QtWidgets.QPushButton("🎞️ Save Source Animation")
        self.apply_anim_btn = QtWidgets.QPushButton("📥 Apply Animation to Target")
        self.preview_pose_btn = QtWidgets.QPushButton("👁️ Preview Pose on Target")

        layout.addWidget(self.save_source_pose_btn, 0, 0)
        layout.addWidget(self.save_target_pose_btn, 0, 1)
        layout.addWidget(self.load_pose_btn, 1, 0)
        layout.addWidget(self.save_anim_btn, 1, 1)
        layout.addWidget(self.apply_anim_btn, 2, 0)
        layout.addWidget(self.preview_pose_btn, 2, 1)

    def adjust_window_to_tree(self, extra_width=175, extra_height=125):
        """Resize main window to fit mapping tab content and tree columns."""
        tree = self.mapping_tree
        model = tree.model()
        if model is None:
            return

        tree.expandAll()  # ensure all rows visible

        scroll_content = self.mapping_scroll.widget()
        if scroll_content is None:
            return

        # --- Height ---
        target_height = scroll_content.sizeHint().height() + extra_height

        # --- Width ---
        total_width = 0
        for col in range(model.columnCount()):
            header_width = tree.header().sectionSizeHint(col)
            column_width = max(tree.sizeHintForColumn(col), header_width)
            total_width += column_width
        total_width += extra_width

        # Cap dimensions to screen
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        target_width = min(total_width, int(screen.width() * 0.95))
        target_height = min(target_height, int(screen.height() * 0.7))

        # --- Animate resize ---
        anim = QtCore.QPropertyAnimation(self, b"size")
        anim.setDuration(250)
        anim.setStartValue(self.size())
        anim.setEndValue(QtCore.QSize(target_width, target_height))
        anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        anim.start()
        self._resize_anim = anim


# ----------------------------
# Model for Mapping Table
# ----------------------------
class MappingTableModel(QtCore.QAbstractTableModel):
    HEADERS = ["Enabled", "Source Joint", "Target Joint"]

    def __init__(self, data=None):
        super().__init__()
        self._data = data or []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def data(self, index, role):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        item = self._data[row]

        # Display role
        if role == QtCore.Qt.DisplayRole:
            if col == 1:
                return item["source"]
            elif col == 2:
                return item["target"]

        # CheckBox state
        if role == QtCore.Qt.CheckStateRole and col == 0:
            return QtCore.Qt.Checked if item["enabled"] else QtCore.Qt.Unchecked

        # Dimming disabled rows
        if role == QtCore.Qt.ForegroundRole and not item["enabled"]:
            return QtGui.QColor("#555555")

        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        col = index.column()
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

        if col == 0:
            flags |= QtCore.Qt.ItemIsUserCheckable
        elif col == 2:
            flags |= QtCore.Qt.ItemIsEditable

        return flags

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        row = index.row()
        col = index.column()
        item = self._data[row]

        if col == 0 and role == QtCore.Qt.CheckStateRole:
            item["enabled"] = value == QtCore.Qt.Checked
        elif col == 2 and role == QtCore.Qt.EditRole:
            item["target"] = value
        else:
            return False

        self.dataChanged.emit(index, index, [role])
        return True

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.HEADERS[section]
        return None

