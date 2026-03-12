"""
ui/reanimate_ui.py - Main UI layout for ReAnimate Tool.
Defines the tab structure, mapping tree setup, and library controls.
"""

from PySide6 import QtCore, QtGui, QtWidgets
import maya.cmds as cmd
import maya.utils

from ui.target_picker_popup import TargetPickerPopup
from ui.styles.common_style import apply_style
from ui.widgets.anim_noise_widget import AnimationNoiseWidget


class ReAnimateToolUI(QtWidgets.QWidget):
    """Pure UI class for ReAnimate Tool. No logic — wired by ReAnimateToolController."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ReAnimate 0.2")
        self.setMinimumWidth(700)
        self.setLayout(QtWidgets.QVBoxLayout())

        self.tabs = QtWidgets.QTabWidget()
        self.layout().addWidget(self.tabs)

        self.mapping_tab = QtWidgets.QWidget()
        self.anim_noise = AnimationNoiseWidget(self)
        self.library_tab = QtWidgets.QWidget()

        apply_style(self.anim_noise, "DARK")

        self.tabs.addTab(self.mapping_tab, "Animation Transfer")
        self.tabs.addTab(self.library_tab, "Pose & Animation Library")
        self.tabs.addTab(self.anim_noise, "Anim Noise")

        self._target_popup = None

        self._setup_mapping_tab()
        self._setup_library_tab()

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

        apply_style(self, "DARK")

    # --- Mapping Tab ---

    def _setup_mapping_tab(self):
        """Build the Animation Transfer tab with rig selection, mapping tree, and controls."""
        layout = QtWidgets.QVBoxLayout(self.mapping_tab)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

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

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.save_mapping_button)
        btn_layout.addWidget(self.load_mapping_button)
        scroll_layout.addLayout(btn_layout)

        self.mapping_tree = QtWidgets.QTreeView(scroll_content)
        self.mapping_tree.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.mapping_tree.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.mapping_tree.header().setStretchLastSection(True)
        self.mapping_tree.clicked.connect(self.on_tree_clicked)
        scroll_layout.addWidget(self.mapping_tree)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.mapping_scroll = scroll

        maya.utils.executeDeferred(self._deferred_tree_setup)
        self.adjust_window_to_tree(extra_width=175, extra_height=125)

    def _deferred_tree_setup(self):
        """Maya-safe deferred setup for delegates and tree appearance."""
        from ui.mapping_tree_model import MappingTreeModel
        from ui.delegates.left_aligned_checkbox_delegate import LeftAlignedCheckBoxDelegate
        from ui.delegates.attr_group_delegate import AttrGroupDelegate
        from ui.delegates.mode_delegate import ModeDelegate
        from ui.delegates.frame_offset_delegate import FrameOffsetDelegate

        self.mapping_model = MappingTreeModel()
        self.mapping_tree.setModel(self.mapping_model)

        frame_diff = (
            cmd.playbackOptions(animationEndTime=True, q=True) -
            cmd.playbackOptions(animationStartTime=True, q=True)
        )

        left_delegate = LeftAlignedCheckBoxDelegate(self.mapping_tree, box_size=16, left_margin=4)
        attr_delegate = AttrGroupDelegate(self.mapping_tree)
        mode_delegate = ModeDelegate(self.mapping_tree)
        frame_delegate = FrameOffsetDelegate(self.mapping_tree, -frame_diff, frame_diff)

        self.mapping_tree.setItemDelegateForColumn(1, left_delegate)
        self.mapping_tree.setItemDelegateForColumn(3, attr_delegate)
        self.mapping_tree.setItemDelegateForColumn(4, mode_delegate)
        self.mapping_tree.setItemDelegateForColumn(6, frame_delegate)

        self.mapping_tree.setAlternatingRowColors(True)
        self.mapping_tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.mapping_tree.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked |
            QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.mapping_tree.setUniformRowHeights(True)
        self.mapping_tree.setIndentation(18)

        header = self.mapping_tree.header()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.mapping_tree.setColumnWidth(1, 36)
        header.moveSection(1, 0)

        def set_row_height():
            vh = getattr(self.mapping_tree, "verticalHeader", None)
            if vh:
                vh().setDefaultSectionSize(28)
            else:
                QtCore.QTimer.singleShot(50, set_row_height)

        def resize_attrs_column():
            option = QtWidgets.QStyleOptionViewItem()
            index = self.mapping_model.index(0, 3)
            width = attr_delegate.sizeHint(option, index).width()
            self.mapping_tree.setColumnWidth(3, width)

        QtCore.QTimer.singleShot(0, set_row_height)
        QtCore.QTimer.singleShot(100, resize_attrs_column)
        self.mapping_tree.expanded.connect(resize_attrs_column)
        self.mapping_tree.collapsed.connect(resize_attrs_column)

        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.setMaximumHeight(int(screen.height() * 0.7))

        self.mapping_tree.expandAll()
        for i in range(self.mapping_model.columnCount()):
            self.mapping_tree.resizeColumnToContents(i)

    # --- Tree Interaction ---

    def on_tree_clicked(self, index):
        """Open target picker popup when the target column is clicked."""
        if not index.isValid() or index.column() != 2:
            return

        tgt_root = self.target_root_field.text().strip()
        if not tgt_root:
            return

        def build_joint_hierarchy(joint):
            children = cmd.listRelatives(joint, c=True, type="joint") or []
            return {"name": joint, "children": [build_joint_hierarchy(c) for c in children]}

        self._target_popup = TargetPickerPopup([build_joint_hierarchy(tgt_root)], self)
        self._target_popup.joint_selected.connect(lambda j: self.on_target_selected(index, j))

        rect = self.mapping_tree.visualRect(index)
        self._target_popup.move(self.mapping_tree.viewport().mapToGlobal(rect.bottomLeft()))
        self._target_popup.show()

    def on_target_selected(self, index, joint_name):
        """Apply selected joint to model and mark it as manually set."""
        model = self.mapping_tree.model()
        model.setData(index, joint_name, QtCore.Qt.EditRole)
        model.setData(index, QtGui.QColor("#555555"), QtCore.Qt.ForegroundRole)



    # --- Library Tab ---

    def _setup_library_tab(self):
        """Build the Pose and Animation Library tab."""
        from ui.widgets.library_widget import LibraryWidget
        layout = QtWidgets.QVBoxLayout(self.library_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self.library_widget = LibraryWidget(self.library_tab)
        layout.addWidget(self.library_widget)
    # --- Window Sizing ---

    def adjust_window_to_tree(self, extra_width=175, extra_height=125):
        """Animate window resize to fit the current mapping tree content."""
        tree = self.mapping_tree
        model = tree.model()
        if model is None:
            return

        tree.expandAll()
        scroll_content = self.mapping_scroll.widget()
        if scroll_content is None:
            return

        total_width = sum(
            max(tree.sizeHintForColumn(col), tree.header().sectionSizeHint(col))
            for col in range(model.columnCount())
        ) + extra_width

        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        target_width = min(total_width, int(screen.width() * 0.95))
        target_height = min(scroll_content.sizeHint().height() + extra_height, int(screen.height() * 0.7))

        anim = QtCore.QPropertyAnimation(self, b"size")
        anim.setDuration(250)
        anim.setStartValue(self.size())
        anim.setEndValue(QtCore.QSize(target_width, target_height))
        anim.setEasingCurve(QtCore.QEasingCurve.InOutCubic)
        anim.start()
        self._resize_anim = anim