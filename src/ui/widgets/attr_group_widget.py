"""
ui/widgets/attr_group_widget.py - Attribute group checkbox widget for ReAnimate Tool.
Provides a master toggle and individual X/Y/Z axis checkboxes for a transform attribute.
"""

from PySide6 import QtWidgets, QtCore


class AttrGroupWidget(QtWidgets.QWidget):
    """Master checkbox with X/Y/Z axis toggles for a single transform attribute group."""

    axis_changed_signal = QtCore.Signal(object)
    master_changed_signal = QtCore.Signal(object, bool)

    def __init__(self, label="Attr", parent=None):
        super().__init__(parent)
        self.label = label

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.master_chk = QtWidgets.QCheckBox(label)
        self.master_chk.setChecked(True)
        layout.addWidget(self.master_chk)

        self.chk_x = QtWidgets.QCheckBox("X")
        self.chk_y = QtWidgets.QCheckBox("Y")
        self.chk_z = QtWidgets.QCheckBox("Z")
        for chk in (self.chk_x, self.chk_y, self.chk_z):
            chk.setChecked(True)

        axis_layout = QtWidgets.QHBoxLayout()
        axis_layout.setContentsMargins(0, 0, 0, 0)
        for chk in (self.chk_x, self.chk_y, self.chk_z):
            axis_layout.addWidget(chk)
        layout.addLayout(axis_layout)

        self.chk_x.stateChanged.connect(self._on_axis_changed)
        self.chk_y.stateChanged.connect(self._on_axis_changed)
        self.chk_z.stateChanged.connect(self._on_axis_changed)
        self.master_chk.stateChanged.connect(self._on_master_changed)

    @property
    def _axis_checks(self):
        return (self.chk_x, self.chk_y, self.chk_z)

    def _on_axis_changed(self, state):
        """Sync master checkbox state based on whether any axis is checked."""
        any_checked = any(chk.isChecked() for chk in self._axis_checks)
        if any_checked != self.master_chk.isChecked():
            self.master_chk.blockSignals(True)
            self.master_chk.setChecked(any_checked)
            self.master_chk.blockSignals(False)
        self.axis_changed_signal.emit(self)

    def _on_master_changed(self, state):
        """Toggle all axis checkboxes when master is toggled."""
        is_checked = self.master_chk.isChecked()
        for chk in self._axis_checks:
            chk.blockSignals(True)
            chk.setChecked(is_checked)
            chk.blockSignals(False)
        self.master_changed_signal.emit(self, is_checked)

    def set_checked(self, x=None, y=None, z=None):
        """Programmatically set axis states without triggering signals."""
        for chk, val in zip(self._axis_checks, (x, y, z)):
            if val is not None:
                chk.blockSignals(True)
                chk.setChecked(val)
                chk.blockSignals(False)
        self.master_chk.blockSignals(True)
        self.master_chk.setChecked(any(chk.isChecked() for chk in self._axis_checks))
        self.master_chk.blockSignals(False)

    def get_checked_axes(self):
        """Return list of checked axis labels: ['X', 'Y', 'Z']."""
        return [chk.text() for chk in self._axis_checks if chk.isChecked()]

    def get_checked_attr_names(self, prefix=""):
        """Return full attribute names with optional prefix, e.g. 'translateX'."""
        return [f"{prefix}{axis}" for axis in self.get_checked_axes()]