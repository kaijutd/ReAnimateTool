"""
reanimate_tool.py - Main controller for the ReAnimate Tool.
Manages UI setup, Maya rig integration, and animation transfer logic.
"""

import os
import traceback

from PySide6 import QtWidgets, QtCore
from shiboken6 import wrapInstance
import maya.OpenMayaUI as omui
import maya.cmds as cmd

from core import transfer, utils, json_io
from ui.reanimate_ui import ReAnimateToolUI
from ui.mapping_tree_model import MappingTreeModel


def get_maya_main_window():
    """Return Maya's main window as a QWidget."""
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def delete_existing_window(object_name="ReAnimateToolWindow"):
    """Close and delete any existing tool window by object name."""
    for widget in QtWidgets.QApplication.allWidgets():
        if widget.objectName() == object_name:
            widget.close()
            widget.deleteLater()


class ReAnimateToolController(QtCore.QObject):
    """Main controller connecting the UI to Maya and core logic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        if parent is None:
            parent = get_maya_main_window()

        self.ui = ReAnimateToolUI(parent)
        self.ui.setObjectName("ReAnimateToolWindow")
        self.ui.setWindowFlags(QtCore.Qt.Window)
        self.ui.setWindowTitle("ReAnimate 0.2")

        self.model = MappingTreeModel({})
        self.ui.mapping_tree.setModel(self.model)
        self.ui.mapping_tree.setHeaderHidden(False)
        self.ui.mapping_tree.setAlternatingRowColors(True)
        self.ui.mapping_tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.ui.mapping_tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.ui.mapping_tree.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked |
            QtWidgets.QAbstractItemView.SelectedClicked
        )
        self.ui.mapping_tree.header().setStretchLastSection(True)
        self.ui.mapping_tree.setUniformRowHeights(True)

        self.source_joints = []
        self.target_joints = []

        self.ui.show()
        self._connect_ui_signals()

    def _connect_ui_signals(self):
        """Wire all UI signals to controller methods."""
        u = self.ui
        u.source_pick_button.clicked.connect(self.pick_source_root)
        u.target_pick_button.clicked.connect(self.pick_target_root)
        u.load_rigs_button.clicked.connect(self.populate_mapping_tree)
        u.transfer_anim_button.clicked.connect(self.transfer_animation)
        u.save_mapping_button.clicked.connect(self.save_mapping)
        u.load_mapping_button.clicked.connect(self.load_mapping)
        u.about_btn.clicked.connect(self.show_about)
        u.help_btn.clicked.connect(self.show_help)

    # --- Rig Selection ---

    def pick_source_root(self):
        """Set source root from Maya selection."""
        sel = cmd.ls(selection=True, long=True)
        if sel:
            self.ui.source_root_field.setText(sel[0])

    def pick_target_root(self):
        """Set target root from Maya selection."""
        sel = cmd.ls(selection=True, long=True)
        if sel:
            self.ui.target_root_field.setText(sel[0])

    # --- Mapping Tree ---

    def populate_mapping_tree(self):
        """Build hierarchical mapping tree from source rig with auto target prefill."""
        src_root = self.ui.source_root_field.text().strip()
        tgt_root = self.ui.target_root_field.text().strip()

        if not cmd.objExists(src_root) or not cmd.objExists(tgt_root):
            cmd.warning("Please select valid source and target root joints.")
            return

        def gather_targets(joint):
            children = cmd.listRelatives(joint, c=True, type="joint") or []
            children = [c for c in children if isinstance(c, str)]
            result = [joint]
            for c in children:
                result.extend(gather_targets(c))
            return result

        def build_hierarchy(joint):
            if not cmd.objExists(joint):
                return None
            children = cmd.listRelatives(joint, c=True, type="joint") or []
            children = [c for c in children if isinstance(c, str)]
            return {
                "enabled": True,
                "name": joint.split("|")[-1],
                "target": "",
                "attrs": {
                    "translate": ["X", "Y", "Z"],
                    "rotate": ["X", "Y", "Z"],
                    "scale": ["X", "Y", "Z"]
                },
                "mode": "Transfer",
                "score": 0.0,
                "children": [build_hierarchy(c) for c in children if c]
            }

        def sanitize(node):
            if not isinstance(node, dict):
                return None
            node["children"] = [
                s for c in node.get("children", [])
                if (s := sanitize(c))
            ]
            return node

        hierarchy = sanitize(build_hierarchy(src_root))
        if not isinstance(hierarchy, dict):
            cmd.warning("Failed to build joint hierarchy.")
            return

        target_list = gather_targets(tgt_root)

        try:
            self.model = MappingTreeModel(hierarchy, target_list=target_list)
            self.ui.mapping_tree.setModel(self.model)
            self.ui.mapping_tree.expandAll()
            QtCore.QTimer.singleShot(50, lambda: self.ui.adjust_window_to_tree(extra_height=200))
        except Exception as e:
            traceback.print_exc()
            cmd.warning(f"Failed to populate mapping tree: {e}")

    # --- Save / Load Mapping ---

    def save_mapping(self):
        """Save current joint mapping to a JSON file."""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self.ui, "Save Mapping", "", "JSON Files (*.json)")
        if not file_path:
            return
        data = {
            "type": "mapping",
            "version": 1,
            "source_root": self.ui.source_root_field.text(),
            "target_root": self.ui.target_root_field.text(),
            "mappings": self.model.serialize()
        }
        json_io.save_mapping(data, file_path)
        cmd.inViewMessage(amg=f"Mapping saved: {os.path.basename(file_path)}", pos='midCenter', fade=True)

    def load_mapping(self):
        """Load joint mapping from a JSON file and rebuild the tree."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self.ui, "Load Mapping", "", "JSON Files (*.json)")
        if not file_path:
            return
        data = json_io.load_mapping(file_path)
        self.ui.source_root_field.setText(data.get("source_root", ""))
        self.ui.target_root_field.setText(data.get("target_root", ""))
        self.model = MappingTreeModel.deserialize(data.get("mappings", []))
        self.ui.mapping_tree.setModel(self.model)
        self.ui.mapping_tree.expandAll()
        cmd.inViewMessage(amg=f"Mapping loaded: {os.path.basename(file_path)}", pos='midCenter', fade=True)

    # --- Animation Transfer ---

    def transfer_animation(self):
        """Commit any open editors and transfer animation based on active mappings."""
        tree = self.ui.mapping_tree
        if tree:
            tree.closeEditor(tree.focusWidget(), QtWidgets.QAbstractItemDelegate.SubmitModelCache)
            tree.commitData(tree.focusWidget())
            tree.model().layoutChanged.emit()

        active_mappings = self.model.get_mappings()
        if not active_mappings:
            cmd.warning("No active mappings selected for transfer.")
            return

        try:
            start_frame = int(cmd.playbackOptions(q=True, min=True))
            end_frame = int(cmd.playbackOptions(q=True, max=True))
        except Exception:
            start_frame, end_frame = 1, 100

        bind_pose_frame = self.ui.bind_pose_spin.value() if hasattr(self.ui, "bind_pose_spin") else None
        frame_offset = self.ui.frame_offset_spin.value() if hasattr(self.ui, "frame_offset_spin") else 0

        confirm = QtWidgets.QMessageBox.question(
            self.ui,
            "Transfer Animation",
            f"Transfer animation for {len(active_mappings)} joints ({start_frame}-{end_frame})?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        try:
            transfer.transfer_animation(
                active_mappings,
                start_frame=start_frame,
                end_frame=end_frame,
                bind_pose_frame=bind_pose_frame,
                frame_offset=frame_offset
            )
            cmd.inViewMessage(amg="Animation transfer completed", pos="midCenter", fade=True)
        except Exception as e:
            cmd.warning(f"Transfer failed: {e}")

    # --- Pose & Animation IO ---

    def save_source_pose(self):
        """Save the current source rig pose to a JSON file."""
        if not self.source_joints:
            cmd.warning("No source rig loaded.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.ui, "Save Source Pose", "", "JSON Files (*.json)")
        if not path:
            return
        json_io.save_pose(self.source_joints, path, frame=self.ui.bind_pose_spin.value(), pose_type="source_pose")
        cmd.inViewMessage(amg="Saved source pose", pos='midCenter', fade=True)

    def save_target_pose(self):
        """Save the current target rig pose to a JSON file."""
        if not self.target_joints:
            cmd.warning("No target rig loaded.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.ui, "Save Target Pose", "", "JSON Files (*.json)")
        if not path:
            return
        json_io.save_pose(self.target_joints, path, frame=self.ui.bind_pose_spin.value(), pose_type="target_pose")
        cmd.inViewMessage(amg="Saved target pose", pos='midCenter', fade=True)



    # --- Misc ---

    def go_to_source_bind_pose(self):
        """Jump timeline to the bind pose frame."""
        cmd.currentTime(self.ui.bind_pose_spin.value())

    def go_to_target_bind_pose(self):
        """Jump timeline to the bind pose frame."""
        cmd.currentTime(self.ui.bind_pose_spin.value())

    def show_about(self):
        QtWidgets.QMessageBox.information(self.ui, "About ReAnimate", "ReAnimate Tool v0.2")

    def show_help(self):
        QtWidgets.QMessageBox.information(self.ui, "Help", "Help info placeholder")


def show_reanimate_tool():
    """Instantiate and return the ReAnimate tool controller."""
    delete_existing_window("ReAnimateToolWindow")
    return ReAnimateToolController(get_maya_main_window())