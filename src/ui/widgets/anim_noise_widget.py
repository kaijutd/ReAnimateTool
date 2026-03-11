"""
ui/widgets/anim_noise_widget.py - Animation noise UI widget for ReAnimate Tool.
Provides controls for applying procedural noise to Maya animation layers.
"""

from PySide6 import QtCore, QtGui, QtWidgets
import maya.cmds as cmds
import random
import math

from core.anim_noise_core import AnimNoiseCore
from core import noise_preset_io

AXIS_COLORS = {
    "tx": QtGui.QColor("#dc3232"), "ty": QtGui.QColor("#32dc32"), "tz": QtGui.QColor("#3232dc"),
    "rx": QtGui.QColor("#dc6432"), "ry": QtGui.QColor("#64dc32"), "rz": QtGui.QColor("#6432dc"),
    "sx": QtGui.QColor("#dc3264"), "sy": QtGui.QColor("#32dc64"), "sz": QtGui.QColor("#3264dc"),
}

DISABLED_COLOR = QtGui.QColor("#444444")
TEXT_COLOR = QtGui.QColor("#e0e0e0")
TEXT_DISABLED_COLOR = QtGui.QColor("#777777")
BG_COLOR = QtGui.QColor("#2b2b2b")
BORDER_COLOR = QtGui.QColor("#555555")


class AnimationNoiseWidget(QtWidgets.QWidget):
    """Widget for adding procedural noise to Maya animation layers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_objects = []
        self.current_layer = None
        self.core = AnimNoiseCore()
        self._preset_list = []  # [{name, path, builtin}, ...]

        self._setup_ui()
        self._connect_signals()
        self._refresh_timeline_range()
        self._refresh_layer_list()
        self._apply_initial_styles()
        self._refresh_preset_list()

    # --- UI Construction ---

    def _setup_ui(self):
        """Build the complete UI layout."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        for section in [
            self._build_preset_section(),
            self._build_target_section(),
            self._build_layer_section(),
            self._build_frame_range_section(),
            self._build_attributes_section(),
            self._build_noise_params_section(),
            self._build_preview_section(),
        ]:
            scroll_layout.addWidget(section)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        main_layout.addWidget(self._build_action_buttons())

    def _build_preset_section(self):
        """Preset load/save/delete section."""
        group = QtWidgets.QGroupBox("Presets")
        layout = QtWidgets.QHBoxLayout()

        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setMinimumWidth(200)
        self.preset_combo.setToolTip("Select a noise preset to load.")
        layout.addWidget(self.preset_combo)

        self.load_preset_btn = QtWidgets.QPushButton("Load")
        self.load_preset_btn.setMaximumWidth(60)
        self.load_preset_btn.setToolTip("Apply the selected preset to current settings.")
        layout.addWidget(self.load_preset_btn)

        self.save_preset_btn = QtWidgets.QPushButton("Save")
        self.save_preset_btn.setMaximumWidth(60)
        self.save_preset_btn.setToolTip("Save current settings as a new preset.")
        layout.addWidget(self.save_preset_btn)

        self.delete_preset_btn = QtWidgets.QPushButton("Delete")
        self.delete_preset_btn.setMaximumWidth(60)
        self.delete_preset_btn.setToolTip("Delete the selected preset (user presets only).")
        layout.addWidget(self.delete_preset_btn)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _build_target_section(self):
        """Target object selection section."""
        group = QtWidgets.QGroupBox("Target")
        layout = QtWidgets.QVBoxLayout()

        h_layout = QtWidgets.QHBoxLayout()
        self.selected_label = QtWidgets.QLabel("Selected Objects: 0")
        self.refresh_btn = QtWidgets.QPushButton("Refresh Selection")
        self.refresh_btn.setMaximumWidth(150)
        h_layout.addWidget(self.selected_label)
        h_layout.addStretch()
        h_layout.addWidget(self.refresh_btn)
        layout.addLayout(h_layout)

        self.randomize_per_object_cb = QtWidgets.QCheckBox("Randomize seed per object (unique variation)")
        self.randomize_per_object_cb.setToolTip(
            "Each object will get a different noise curve.\n"
            "Useful for creating varied motion across multiple objects."
        )
        layout.addWidget(self.randomize_per_object_cb)
        group.setLayout(layout)
        return group

    def _build_layer_section(self):
        """Animation layer selection and weight section."""
        group = QtWidgets.QGroupBox("Animation Layer")
        layout = QtWidgets.QVBoxLayout()

        layer_select_layout = QtWidgets.QHBoxLayout()
        layer_select_layout.addWidget(QtWidgets.QLabel("Existing Layers:"))
        self.layer_combo = QtWidgets.QComboBox()
        self.layer_combo.setMinimumWidth(200)
        layer_select_layout.addWidget(self.layer_combo)
        layer_select_layout.addStretch()
        layout.addLayout(layer_select_layout)

        self.create_new_radio = QtWidgets.QRadioButton("Create New Layer")
        self.add_existing_radio = QtWidgets.QRadioButton("Add to Existing Layer")
        self.create_new_radio.setChecked(True)
        layout.addWidget(self.create_new_radio)
        layout.addWidget(self.add_existing_radio)

        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("Layer Name:"))
        self.layer_name_field = QtWidgets.QLineEdit("noise_layer_01")
        self.layer_name_field.setMaximumWidth(200)
        name_layout.addWidget(self.layer_name_field)
        name_layout.addStretch()
        layout.addLayout(name_layout)

        layout.addSpacing(10)
        layout.addWidget(QtWidgets.QLabel("Layer Weight:"))

        weight_layout = QtWidgets.QHBoxLayout()
        self.weight_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.weight_slider.setRange(0, 100)
        self.weight_slider.setValue(100)
        self.weight_spinbox = QtWidgets.QDoubleSpinBox()
        self.weight_spinbox.setRange(0.0, 1.0)
        self.weight_spinbox.setValue(1.0)
        self.weight_spinbox.setSingleStep(0.1)
        self.weight_spinbox.setMaximumWidth(70)
        weight_layout.addWidget(self.weight_slider)
        weight_layout.addWidget(self.weight_spinbox)
        layout.addLayout(weight_layout)

        group.setLayout(layout)
        return group

    def _build_frame_range_section(self):
        """Frame range and sample rate section."""
        group = QtWidgets.QGroupBox("Frame Range")
        layout = QtWidgets.QVBoxLayout()

        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(QtWidgets.QLabel("Start:"))
        self.start_frame_spinbox = QtWidgets.QSpinBox()
        self.start_frame_spinbox.setRange(-10000, 10000)
        self.start_frame_spinbox.setValue(1)
        self.start_frame_spinbox.setMaximumWidth(80)
        range_layout.addWidget(self.start_frame_spinbox)
        range_layout.addSpacing(20)
        range_layout.addWidget(QtWidgets.QLabel("End:"))
        self.end_frame_spinbox = QtWidgets.QSpinBox()
        self.end_frame_spinbox.setRange(-10000, 10000)
        self.end_frame_spinbox.setValue(100)
        self.end_frame_spinbox.setMaximumWidth(80)
        range_layout.addWidget(self.end_frame_spinbox)
        range_layout.addStretch()
        layout.addLayout(range_layout)

        self.use_timeline_btn = QtWidgets.QPushButton("Use Timeline Range")
        self.use_timeline_btn.setMaximumWidth(150)
        layout.addWidget(self.use_timeline_btn)

        sample_layout = QtWidgets.QHBoxLayout()
        sample_layout.addWidget(QtWidgets.QLabel("Sample Rate:"))
        self.sample_rate_spinbox = QtWidgets.QSpinBox()
        self.sample_rate_spinbox.setRange(1, 10)
        self.sample_rate_spinbox.setValue(1)
        self.sample_rate_spinbox.setMaximumWidth(60)
        self.sample_rate_spinbox.setSuffix(" frames")
        sample_layout.addWidget(self.sample_rate_spinbox)
        sample_layout.addStretch()
        layout.addLayout(sample_layout)

        group.setLayout(layout)
        return group

    def _build_attributes_section(self):
        """Per-attribute amplitude and enable controls."""
        group = QtWidgets.QGroupBox("Attributes & Amplitude")
        layout = QtWidgets.QVBoxLayout()

        self.attr_controls = {}
        self.master_checkboxes = {}
        self.attr_containers = {}

        self.advanced_checkbox = QtWidgets.QCheckBox("Advanced: Per-Attribute Parameters")
        layout.addWidget(self.advanced_checkbox)
        layout.addSpacing(10)

        attr_groups = {
            'translate': [
                ("Translate X", "tx", 1.0, 0.0, 100.0),
                ("Translate Y", "ty", 2.0, 0.0, 100.0),
                ("Translate Z", "tz", 1.0, 0.0, 100.0),
            ],
            'rotate': [
                ("Rotate X", "rx", 5.0, 0.0, 180.0),
                ("Rotate Y", "ry", 5.0, 0.0, 180.0),
                ("Rotate Z", "rz", 5.0, 0.0, 180.0),
            ],
            'scale': [
                ("Scale X", "sx", 0.1, 0.0, 2.0),
                ("Scale Y", "sy", 0.1, 0.0, 2.0),
                ("Scale Z", "sz", 0.1, 0.0, 2.0),
            ]
        }

        for group_name, attributes in attr_groups.items():
            master_cb = QtWidgets.QCheckBox(f"{group_name.capitalize()} (XYZ)")
            master_cb.setStyleSheet("font-weight: bold;")
            layout.addWidget(master_cb)
            self.master_checkboxes[group_name] = master_cb

            container = QtWidgets.QWidget()
            container_layout = QtWidgets.QVBoxLayout(container)
            container_layout.setContentsMargins(20, 0, 0, 0)
            container_layout.setSpacing(4)

            for label, attr, default, min_val, max_val in attributes:
                container_layout.addWidget(self._create_attribute_row(label, attr, default, min_val, max_val))

            container.hide()
            layout.addWidget(container)
            self.attr_containers[group_name] = container
            master_cb.toggled.connect(lambda checked, g=group_name: self._on_master_toggle(g, checked))
            layout.addSpacing(8)

        group.setLayout(layout)
        return group

    def _create_attribute_row(self, label, attr, default, min_val, max_val):
        """Create a single attribute row with amplitude controls and advanced params."""
        widget = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(widget)
        h_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QtWidgets.QCheckBox(label)
        checkbox.setMinimumWidth(100)
        h_layout.addWidget(checkbox)

        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.setSingleStep(0.1)
        spinbox.setMaximumWidth(70)
        h_layout.addWidget(spinbox)

        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(int(min_val * 10), int(max_val * 10))
        slider.setValue(int(default * 10))
        h_layout.addWidget(slider)

        advanced_container = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(advanced_container)
        advanced_layout.setContentsMargins(20, 5, 0, 5)
        advanced_layout.setSpacing(4)

        def _make_spin_slider_row(label_text, spin_widget, slider_widget):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(label_text))
            row.addWidget(spin_widget)
            row.addWidget(slider_widget)
            advanced_layout.addLayout(row)

        freq_spin = QtWidgets.QDoubleSpinBox()
        freq_spin.setRange(0.01, 10.0); freq_spin.setValue(1.0)
        freq_spin.setSingleStep(0.1); freq_spin.setMaximumWidth(60)
        freq_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        freq_slider.setRange(1, 1000); freq_slider.setValue(100)
        _make_spin_slider_row("Freq:", freq_spin, freq_slider)

        oct_spin = QtWidgets.QSpinBox()
        oct_spin.setRange(1, 8); oct_spin.setValue(3); oct_spin.setMaximumWidth(60)
        oct_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        oct_slider.setRange(1, 8); oct_slider.setValue(3)
        _make_spin_slider_row("Oct:", oct_spin, oct_slider)

        pers_spin = QtWidgets.QDoubleSpinBox()
        pers_spin.setRange(0.0, 1.0); pers_spin.setValue(0.5)
        pers_spin.setSingleStep(0.1); pers_spin.setMaximumWidth(60)
        pers_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        pers_slider.setRange(0, 100); pers_slider.setValue(50)
        _make_spin_slider_row("Pers:", pers_spin, pers_slider)

        seed_spin = QtWidgets.QSpinBox()
        seed_spin.setRange(0, 999999); seed_spin.setValue(1234); seed_spin.setMaximumWidth(80)
        seed_row = QtWidgets.QHBoxLayout()
        seed_row.addWidget(QtWidgets.QLabel("Seed:"))
        seed_row.addWidget(seed_spin)
        seed_row.addStretch()
        advanced_layout.addLayout(seed_row)

        advanced_container.hide()

        row_wrapper = QtWidgets.QWidget()
        row_layout = QtWidgets.QVBoxLayout(row_wrapper)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(widget)
        row_layout.addWidget(advanced_container)

        self.attr_controls[attr] = {
            'checkbox': checkbox, 'spinbox': spinbox, 'slider': slider,
            'label': label, 'row_widget': row_wrapper, 'main_widget': widget,
            'advanced_container': advanced_container,
            'freq_spin': freq_spin, 'freq_slider': freq_slider,
            'oct_spin': oct_spin, 'oct_slider': oct_slider,
            'pers_spin': pers_spin, 'pers_slider': pers_slider,
            'seed_spin': seed_spin
        }

        slider.valueChanged.connect(lambda v, sb=spinbox: sb.setValue(v / 10.0))
        spinbox.valueChanged.connect(lambda v, sl=slider: sl.setValue(int(v * 10)))
        freq_slider.valueChanged.connect(lambda v, sb=freq_spin: sb.setValue(v / 100.0))
        freq_spin.valueChanged.connect(lambda v, sl=freq_slider: sl.setValue(int(v * 100)))
        oct_slider.valueChanged.connect(oct_spin.setValue)
        oct_spin.valueChanged.connect(oct_slider.setValue)
        pers_slider.valueChanged.connect(lambda v, sb=pers_spin: sb.setValue(v / 100.0))
        pers_spin.valueChanged.connect(lambda v, sl=pers_slider: sl.setValue(int(v * 100)))
        checkbox.toggled.connect(lambda checked, a=attr: self._update_attr_appearance(a, checked))

        return row_wrapper

    def _build_noise_params_section(self):
        """Global noise parameters including noise mode, type, and shape controls."""
        group = QtWidgets.QGroupBox("Noise Parameters (Global)")
        layout = QtWidgets.QVBoxLayout()

        self.global_note = QtWidgets.QLabel(
            "Note: These parameters apply to all attributes. "
            "Enable 'Advanced' mode above for per-attribute control."
        )
        self.global_note.setWordWrap(True)
        self.global_note.setStyleSheet(f"color: {TEXT_DISABLED_COLOR.name()}; font-size: 10px;")
        layout.addWidget(self.global_note)
        layout.addSpacing(8)

        self.global_params_container = QtWidgets.QWidget()
        global_layout = QtWidgets.QVBoxLayout(self.global_params_container)
        global_layout.setContentsMargins(0, 0, 0, 0)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("Noise Mode:"))
        self.noise_mode_combo = QtWidgets.QComboBox()
        self.noise_mode_combo.addItems(["Additive", "Multiplicative"])
        self.noise_mode_combo.setMaximumWidth(150)
        self.noise_mode_combo.setToolTip(
            "Additive: Adds offset values to animation (e.g., +5°)\n"
            "Multiplicative: Scales animation by percentage (e.g., ±10%)"
        )
        mode_layout.addWidget(self.noise_mode_combo)
        mode_layout.addStretch()
        global_layout.addLayout(mode_layout)
        global_layout.addSpacing(5)

        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addWidget(QtWidgets.QLabel("Type:"))
        self.noise_type_combo = QtWidgets.QComboBox()
        self.noise_type_combo.addItems(["Perlin", "Simplex", "Sine Wave"])
        self.noise_type_combo.setMaximumWidth(150)
        type_layout.addWidget(self.noise_type_combo)
        type_layout.addStretch()
        global_layout.addLayout(type_layout)

        def _add_param_row(label_text, spin, slider):
            global_layout.addWidget(QtWidgets.QLabel(label_text))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(spin)
            row.addWidget(slider)
            global_layout.addLayout(row)

        self.frequency_spinbox = QtWidgets.QDoubleSpinBox()
        self.frequency_spinbox.setRange(0.01, 10.0); self.frequency_spinbox.setValue(1.0)
        self.frequency_spinbox.setSingleStep(0.1); self.frequency_spinbox.setMaximumWidth(70)
        self.frequency_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.frequency_slider.setRange(1, 1000); self.frequency_slider.setValue(100)
        _add_param_row("Frequency:", self.frequency_spinbox, self.frequency_slider)

        self.octaves_spinbox = QtWidgets.QSpinBox()
        self.octaves_spinbox.setRange(1, 8); self.octaves_spinbox.setValue(3)
        self.octaves_spinbox.setMaximumWidth(70)
        self.octaves_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.octaves_slider.setRange(1, 8); self.octaves_slider.setValue(3)
        _add_param_row("Octaves:", self.octaves_spinbox, self.octaves_slider)

        self.persistence_spinbox = QtWidgets.QDoubleSpinBox()
        self.persistence_spinbox.setRange(0.0, 1.0); self.persistence_spinbox.setValue(0.5)
        self.persistence_spinbox.setSingleStep(0.1); self.persistence_spinbox.setMaximumWidth(70)
        self.persistence_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.persistence_slider.setRange(0, 100); self.persistence_slider.setValue(50)
        _add_param_row("Persistence:", self.persistence_spinbox, self.persistence_slider)

        seed_layout = QtWidgets.QHBoxLayout()
        seed_layout.addWidget(QtWidgets.QLabel("Seed:"))
        self.seed_spinbox = QtWidgets.QSpinBox()
        self.seed_spinbox.setRange(0, 999999); self.seed_spinbox.setValue(1234)
        self.seed_spinbox.setMaximumWidth(100)
        seed_layout.addWidget(self.seed_spinbox)
        self.randomize_seed_btn = QtWidgets.QPushButton("Randomize")
        self.randomize_seed_btn.setMaximumWidth(100)
        seed_layout.addWidget(self.randomize_seed_btn)
        seed_layout.addStretch()
        global_layout.addLayout(seed_layout)

        layout.addWidget(self.global_params_container)
        group.setLayout(layout)
        return group

    def _build_preview_section(self):
        """Noise curve preview section."""
        group = QtWidgets.QGroupBox("Noise Preview")
        layout = QtWidgets.QVBoxLayout()

        self.preview_canvas = NoisePreviewCanvas()
        self.preview_canvas.setMinimumHeight(220)
        self.preview_canvas.setMaximumHeight(300)
        layout.addWidget(self.preview_canvas)

        self.update_preview_btn = QtWidgets.QPushButton("Update Preview")
        self.update_preview_btn.setMaximumWidth(150)
        layout.addWidget(self.update_preview_btn)

        group.setLayout(layout)
        return group

    def _build_action_buttons(self):
        """Apply and remove layer action buttons."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.apply_btn = QtWidgets.QPushButton("Apply Noise to Layer")
        self.apply_btn.setMinimumHeight(35)
        self.remove_btn = QtWidgets.QPushButton("Remove Selected Layer")
        self.remove_btn.setMinimumHeight(30)

        layout.addWidget(self.apply_btn)
        layout.addWidget(self.remove_btn)
        return widget

    # --- Signal Connections ---

    def _connect_signals(self):
        """Connect all UI signals to handlers."""
        self.refresh_btn.clicked.connect(self._on_refresh_selection)

        self.weight_slider.valueChanged.connect(lambda v: self.weight_spinbox.setValue(v / 100.0))
        self.weight_spinbox.valueChanged.connect(lambda v: self.weight_slider.setValue(int(v * 100)))
        self.weight_slider.valueChanged.connect(self._on_weight_changed)
        self.create_new_radio.toggled.connect(self._on_layer_mode_changed)
        self.use_timeline_btn.clicked.connect(self._refresh_timeline_range)
        self.advanced_checkbox.toggled.connect(self._on_advanced_mode_toggled)

        self.frequency_slider.valueChanged.connect(lambda v: self.frequency_spinbox.setValue(v / 100.0))
        self.frequency_spinbox.valueChanged.connect(lambda v: self.frequency_slider.setValue(int(v * 100)))
        self.octaves_slider.valueChanged.connect(self.octaves_spinbox.setValue)
        self.octaves_spinbox.valueChanged.connect(self.octaves_slider.setValue)
        self.persistence_slider.valueChanged.connect(lambda v: self.persistence_spinbox.setValue(v / 100.0))
        self.persistence_spinbox.valueChanged.connect(lambda v: self.persistence_slider.setValue(int(v * 100)))

        self.randomize_seed_btn.clicked.connect(self._randomize_seed)
        self.update_preview_btn.clicked.connect(self._update_preview)

        for widget in (self.frequency_spinbox, self.octaves_spinbox,
                       self.persistence_spinbox, self.seed_spinbox):
            widget.valueChanged.connect(self._update_preview)
        self.noise_type_combo.currentIndexChanged.connect(self._update_preview)

        self.apply_btn.clicked.connect(self._on_apply_noise)
        self.remove_btn.clicked.connect(self._on_remove_layer)

        self.load_preset_btn.clicked.connect(self._on_load_preset)
        self.save_preset_btn.clicked.connect(self._on_save_preset)
        self.delete_preset_btn.clicked.connect(self._on_delete_preset)

    # --- Preset Handling ---

    def _refresh_preset_list(self):
        """Reload preset list from disk and repopulate the combo."""
        self._preset_list = noise_preset_io.list_presets()
        self.preset_combo.clear()
        for preset in self._preset_list:
            label = f"{preset['name']}  {'[built-in]' if preset['builtin'] else '[user]'}"
            self.preset_combo.addItem(label)
        self.delete_preset_btn.setEnabled(bool(self._preset_list))

    def _on_load_preset(self):
        """Load the selected preset and apply it to the UI."""
        idx = self.preset_combo.currentIndex()
        if idx < 0 or idx >= len(self._preset_list):
            return
        try:
            preset = noise_preset_io.load_preset(self._preset_list[idx]['path'])
            self._apply_preset_to_ui(preset['settings'])
            self._update_preview()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load Failed", f"Could not load preset:\n{e}")

    def _on_save_preset(self):
        """Save current UI settings as a named user preset."""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Save Preset", "Preset name:", text="My Preset"
        )
        if not ok or not name.strip():
            return

        desc, ok = QtWidgets.QInputDialog.getText(
            self, "Save Preset", "Description (optional):"
        )
        if not ok:
            return

        settings = self._collect_noise_params()
        settings['attr_params'] = {
            attr: {'amplitude': controls['spinbox'].value()}
            for attr, controls in self.attr_controls.items()
        }
        settings['randomize_per_object'] = self.randomize_per_object_cb.isChecked()

        try:
            noise_preset_io.save_preset(name.strip(), settings, desc.strip())
            self._refresh_preset_list()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save Failed", f"Could not save preset:\n{e}")

    def _on_delete_preset(self):
        """Delete the selected user preset."""
        idx = self.preset_combo.currentIndex()
        if idx < 0 or idx >= len(self._preset_list):
            return
        preset = self._preset_list[idx]
        if preset['builtin']:
            QtWidgets.QMessageBox.information(self, "Cannot Delete", "Built-in presets cannot be deleted.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{preset['name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            noise_preset_io.delete_preset(preset['path'])
            self._refresh_preset_list()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Delete Failed", f"Could not delete preset:\n{e}")

    def _apply_preset_to_ui(self, settings):
        """Populate all UI controls from a preset settings dict."""
        noise_type = settings.get('noise_type', 'Perlin')
        idx = self.noise_type_combo.findText(noise_type)
        if idx >= 0:
            self.noise_type_combo.setCurrentIndex(idx)

        noise_mode = settings.get('noise_mode', 'Additive')
        idx = self.noise_mode_combo.findText(noise_mode)
        if idx >= 0:
            self.noise_mode_combo.setCurrentIndex(idx)

        self.frequency_spinbox.setValue(settings.get('frequency', 1.0))
        self.octaves_spinbox.setValue(settings.get('octaves', 3))
        self.persistence_spinbox.setValue(settings.get('persistence', 0.5))
        self.seed_spinbox.setValue(settings.get('seed', 1234))

        if 'randomize_per_object' in settings:
            self.randomize_per_object_cb.setChecked(settings['randomize_per_object'])

        attr_params = settings.get('attr_params', {})
        if attr_params:
            attr_to_group = {
                'tx': 'translate', 'ty': 'translate', 'tz': 'translate',
                'rx': 'rotate',    'ry': 'rotate',    'rz': 'rotate',
                'sx': 'scale',     'sy': 'scale',     'sz': 'scale',
            }
            groups_to_enable = set()
            for attr, params in attr_params.items():
                if attr not in self.attr_controls:
                    continue
                amplitude = params.get('amplitude', 0.0)
                controls = self.attr_controls[attr]
                controls['spinbox'].setValue(amplitude)
                if amplitude > 0.0:
                    controls['checkbox'].setChecked(True)
                    groups_to_enable.add(attr_to_group.get(attr))

            for group_name in groups_to_enable:
                if group_name and group_name in self.master_checkboxes:
                    self.master_checkboxes[group_name].setChecked(True)

    # --- Appearance ---

    def _apply_initial_styles(self):
        """Set initial disabled appearance for all attribute controls."""
        for master_cb in self.master_checkboxes.values():
            self._update_master_appearance(master_cb, False)
        for attr in self.attr_controls:
            self._update_attr_appearance(attr, False)

    def _update_master_appearance(self, master_checkbox, enabled):
        """Update master checkbox text color based on enabled state."""
        color = TEXT_COLOR.name() if enabled else TEXT_DISABLED_COLOR.name()
        master_checkbox.setStyleSheet(f"font-weight: bold; color: {color};")

    def _update_attr_appearance(self, attr, enabled):
        """Update attribute row enabled state and advanced container visibility."""
        controls = self.attr_controls.get(attr)
        if not controls:
            return
        controls['checkbox'].setStyleSheet(
            f"color: {TEXT_COLOR.name()};" if enabled else f"color: {TEXT_DISABLED_COLOR.name()};"
        )
        controls['spinbox'].setEnabled(enabled)
        controls['slider'].setEnabled(enabled)
        controls['advanced_container'].setVisible(self.advanced_checkbox.isChecked() and enabled)

    # --- Event Handlers ---

    def _on_master_toggle(self, group_name, checked):
        """Show/hide attribute group container and sync child checkboxes."""
        container = self.attr_containers.get(group_name)
        master_cb = self.master_checkboxes.get(group_name)
        if not container or not master_cb:
            return
        self._update_master_appearance(master_cb, checked)
        container.setVisible(checked)
        for attr in {'translate': ['tx', 'ty', 'tz'],
                     'rotate': ['rx', 'ry', 'rz'],
                     'scale': ['sx', 'sy', 'sz']}.get(group_name, []):
            if attr in self.attr_controls:
                self.attr_controls[attr]['checkbox'].setChecked(checked)

    def _on_advanced_mode_toggled(self, checked):
        """Toggle between global and per-attribute parameter controls."""
        self.global_params_container.setVisible(not checked)
        self.global_note.setVisible(not checked)
        for attr, controls in self.attr_controls.items():
            controls['advanced_container'].setVisible(checked and controls['checkbox'].isChecked())
        self._update_preview()

    def _on_refresh_selection(self):
        """Update selected objects from Maya viewport."""
        self.selected_objects = cmds.ls(selection=True, type='transform') or []
        self.selected_label.setText(f"Selected Objects: {len(self.selected_objects)}")
        if not self.selected_objects:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select objects in Maya viewport.")

    def _on_layer_mode_changed(self):
        """Toggle layer name field vs existing layer combo."""
        create_new = self.create_new_radio.isChecked()
        self.layer_name_field.setEnabled(create_new)
        self.layer_combo.setEnabled(not create_new)

    def _on_weight_changed(self, value):
        """Update current layer weight in core."""
        if self.current_layer:
            self.core.set_layer_weight(self.current_layer, value / 100.0)

    def _refresh_timeline_range(self):
        """Sync frame range spinboxes with Maya's timeline."""
        try:
            self.start_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, minTime=True)))
            self.end_frame_spinbox.setValue(int(cmds.playbackOptions(q=True, maxTime=True)))
        except Exception:
            pass

    def _randomize_seed(self):
        """Randomize global seed and all per-attribute seeds."""
        self.seed_spinbox.setValue(random.randint(0, 999999))
        if self.advanced_checkbox.isChecked():
            for controls in self.attr_controls.values():
                controls['seed_spin'].setValue(random.randint(0, 999999))

    # --- Preview ---

    def _update_preview(self):
        """Regenerate and display the noise preview curve(s)."""
        start = self.start_frame_spinbox.value()
        end = self.end_frame_spinbox.value()
        samples = min(500, end - start + 1)
        frames = [start + (end - start) * (i / float(max(samples - 1, 1))) for i in range(samples)]

        if self.advanced_checkbox.isChecked():
            curves_data = []
            for attr, controls in self.attr_controls.items():
                if not controls['checkbox'].isChecked():
                    continue
                params = self._collect_noise_params(controls)
                amplitude = params.pop('amplitude')
                y_values = [
                    self._generate_noise_value(f, params['noise_type'], params['frequency'],
                                               params['octaves'], params['persistence'], params['seed']) * amplitude
                    for f in frames
                ]
                curves_data.append({
                    'x': frames, 'y': y_values,
                    'label': controls['label'],
                    'color': AXIS_COLORS.get(attr, QtGui.QColor(200, 200, 200))
                })
            self.preview_canvas.set_multi_data(curves_data)
        else:
            params = self._collect_noise_params()
            y_values = [
                self._generate_noise_value(f, params['noise_type'], params['frequency'],
                                           params['octaves'], params['persistence'], params['seed'])
                for f in frames
            ]
            self.preview_canvas.set_data(frames, y_values)

    def _generate_noise_value(self, frame, noise_type, frequency, octaves, persistence, seed):
        """Generate a preview noise value for a given frame."""
        if noise_type == "Sine Wave":
            return math.sin(frame * frequency * 0.1)
        return self._perlin_noise(
            frame * frequency if noise_type == "Perlin" else frame * frequency * 0.8,
            octaves, persistence, seed
        )

    def _perlin_noise(self, x, octaves, persistence, seed):
        """Layered 1D Perlin-style noise."""
        total, freq, amp, max_val = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += self._noise1d(x * freq + seed) * amp
            max_val += amp
            amp *= persistence
            freq *= 2.0
        return total / max_val if max_val else 0.0

    def _noise1d(self, x):
        """Smooth 1D noise using sine-based hashing and Hermite interpolation."""
        i = int(x)
        f = x - i
        f = f * f * (3.0 - 2.0 * f)
        a = math.sin(i * 12.9898 + 78.233) * 43758.5453
        b = math.sin((i + 1) * 12.9898 + 78.233) * 43758.5453
        a -= math.floor(a)
        b -= math.floor(b)
        return (a * (1 - f) + b * f) * 2.0 - 1.0

    # --- Apply / Remove ---

    def _on_apply_noise(self):
        """Validate inputs and apply noise via core."""
        if not self.selected_objects:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Please select objects first and click 'Refresh Selection'.")
            return

        selected_attrs = [a for a, c in self.attr_controls.items() if c['checkbox'].isChecked()]
        if not selected_attrs:
            QtWidgets.QMessageBox.warning(self, "No Attributes",
                                          "Please select at least one attribute.")
            return

        start_frame = self.start_frame_spinbox.value()
        end_frame = self.end_frame_spinbox.value()
        if end_frame < start_frame:
            QtWidgets.QMessageBox.warning(self, "Invalid Range",
                                          "End frame must be greater than start frame.")
            return

        if self.create_new_radio.isChecked():
            layer_name = self.layer_name_field.text().strip()
            layer_mode = 'create_new'
            if not layer_name:
                QtWidgets.QMessageBox.warning(self, "Invalid Layer Name", "Please enter a valid layer name.")
                return
        else:
            layer_name = self.layer_combo.currentText()
            layer_mode = 'use_existing'
            if not layer_name or layer_name == "No layers available":
                QtWidgets.QMessageBox.warning(self, "No Layer Selected",
                                              "Please select an existing layer or create a new one.")
                return

        advanced_mode = self.advanced_checkbox.isChecked()
        global_params = self._collect_noise_params()
        global_params['noise_mode'] = self.noise_mode_combo.currentText()

        attr_params = {
            attr: self._collect_noise_params(self.attr_controls[attr]) if advanced_mode
            else {'amplitude': self.attr_controls[attr]['spinbox'].value()}
            for attr in selected_attrs
        }

        sample_rate = self.sample_rate_spinbox.value()
        total_keys = (((end_frame - start_frame) // sample_rate) + 1) * len(selected_attrs) * len(self.selected_objects)

        reply = QtWidgets.QMessageBox.question(
            self, "Apply Noise",
            f"This will create:\n"
            f"  {total_keys} keyframes\n"
            f"  {len(self.selected_objects)} object(s)\n"
            f"  {len(selected_attrs)} attribute(s)\n"
            f"  Frames {start_frame} to {end_frame}\n"
            f"  Mode: {self.noise_mode_combo.currentText()}\n\nContinue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.No:
            return

        progress = QtWidgets.QProgressDialog(
            "Applying noise to animation layer...", "Cancel", 0, total_keys, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)

        def progress_callback(current, total, message):
            progress.setValue(current)
            progress.setLabelText(message)
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        result = self.core.apply_noise(
            self.selected_objects, selected_attrs,
            {
                'layer_name': layer_name,
                'layer_mode': layer_mode,
                'start_frame': start_frame,
                'end_frame': end_frame,
                'sample_rate': sample_rate,
                'advanced_mode': advanced_mode,
                'randomize_per_object': self.randomize_per_object_cb.isChecked(),
                'noise_mode': global_params['noise_mode'],
                'noise_type': global_params['noise_type'],
                'global_params': global_params,
                'attr_params': attr_params
            },
            progress_callback
        )

        progress.close()

        if result['success']:
            self.current_layer = result['layer_name']
            self._refresh_layer_list()
            QtWidgets.QMessageBox.information(self, "Success",
                                              f"{result['message']}\nLayer: {result['layer_name']}")
        else:
            QtWidgets.QMessageBox.warning(self, "Failed", result['message'])

    def _on_remove_layer(self):
        """Remove the selected or current animation layer."""
        layer_name = self.layer_combo.currentText() if self.add_existing_radio.isChecked() else self.current_layer
        if not layer_name or layer_name == "No layers available":
            QtWidgets.QMessageBox.warning(self, "No Layer", "No layer selected to remove.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Remove Layer",
            f"Delete layer '{layer_name}'? This cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        result = self.core.remove_layer(layer_name)
        if result['success']:
            if self.current_layer == layer_name:
                self.current_layer = None
            self._refresh_layer_list()
            QtWidgets.QMessageBox.information(self, "Success", result['message'])
        else:
            QtWidgets.QMessageBox.critical(self, "Error", result['message'])

    def _refresh_layer_list(self):
        """Refresh the layer combo from Maya's current anim layers."""
        self.layer_combo.clear()
        layers = self.core.get_animation_layers()
        self.layer_combo.addItems(layers if layers else ["No layers available"])

    # --- Params Collection ---

    def _collect_noise_params(self, controls=None):
        """
        Collect noise parameters from global or per-attribute controls.

        Args:
            controls (dict): Attribute control dict, or None for global params.

        Returns:
            dict: Noise parameter values.
        """
        params = {
            'noise_mode': self.noise_mode_combo.currentText(),
            'noise_type': self.noise_type_combo.currentText(),
        }
        if controls:
            params.update({
                'frequency': controls['freq_spin'].value(),
                'octaves': controls['oct_spin'].value(),
                'persistence': controls['pers_spin'].value(),
                'seed': controls['seed_spin'].value(),
                'amplitude': controls['spinbox'].value()
            })
        else:
            params.update({
                'frequency': self.frequency_spinbox.value(),
                'octaves': self.octaves_spinbox.value(),
                'persistence': self.persistence_spinbox.value(),
                'seed': self.seed_spinbox.value()
            })
        return params


class NoisePreviewCanvas(QtWidgets.QWidget):
    """Custom widget for rendering a noise curve preview graph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.x_data = []
        self.y_data = []
        self.multi_curves = []
        self.setMinimumSize(400, 220)

    def set_data(self, x_data, y_data):
        """Set single curve data and trigger repaint."""
        self.x_data = x_data
        self.y_data = y_data
        self.multi_curves = []
        self.update()

    def set_multi_data(self, curves_data):
        """Set multiple curve data and trigger repaint."""
        self.multi_curves = curves_data
        self.x_data = []
        self.y_data = []
        self.update()

    def paintEvent(self, event):
        """Render the noise preview graph."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), BG_COLOR)

        if self.multi_curves:
            self._draw_multi_curves(painter)
        elif len(self.x_data) >= 2 and len(self.y_data) >= 2:
            self._draw_single_curve(painter, self.x_data, self.y_data, QtGui.QColor(100, 200, 255))
        else:
            painter.setPen(TEXT_DISABLED_COLOR)
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter,
                             "Click 'Update Preview' to see noise curve")

    def _draw_multi_curves(self, painter):
        """Draw multiple colored curves with shared axes."""
        if not self.multi_curves:
            return
        all_x = [x for c in self.multi_curves for x in c['x']]
        all_y = [y for c in self.multi_curves for y in c['y']]
        if not all_x or not all_y:
            return

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        if y_max == y_min: y_max = y_min + 1.0
        if x_max == x_min: x_max = x_min + 1.0

        margins = self._draw_grid(painter, y_min, y_max)
        for curve in self.multi_curves:
            self._draw_curve_path(painter, curve['x'], curve['y'],
                                  x_min, x_max, y_min, y_max, margins,
                                  curve.get('color', QtGui.QColor(100, 200, 255)))
        self._draw_legend(painter, self.multi_curves)

    def _draw_single_curve(self, painter, x_data, y_data, color):
        """Draw a single curve with its own axes."""
        x_min, x_max = min(x_data), max(x_data)
        y_min, y_max = min(y_data), max(y_data)
        if y_max == y_min: y_max = y_min + 1.0
        if x_max == x_min: x_max = x_min + 1.0

        margins = self._draw_grid(painter, y_min, y_max)
        self._draw_curve_path(painter, x_data, y_data, x_min, x_max, y_min, y_max, margins, color)

    def _draw_grid(self, painter, y_min, y_max):
        """Draw background grid lines, axis labels, and zero line."""
        w, h = self.width(), self.height()
        lm, tm, rm, bm = 20, 15, 20, 35

        painter.setPen(BORDER_COLOR)
        for i in range(5):
            y = tm + (h - tm - bm) * i / 4
            painter.drawLine(lm, int(y), w - rm, int(y))

        if y_min <= 0 <= y_max:
            zero_y = tm + (h - tm - bm) * (1.0 - (0 - y_min) / (y_max - y_min))
            if tm <= zero_y <= h - bm:
                painter.setPen(QtGui.QPen(TEXT_DISABLED_COLOR, 2, QtCore.Qt.DashLine))
                painter.drawLine(lm, int(zero_y), w - rm, int(zero_y))

        painter.setPen(TEXT_COLOR)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.save()
        painter.translate(12, h / 2)
        painter.rotate(-90)
        painter.drawText(-60, 0, 120, 20, QtCore.Qt.AlignCenter, "Additive Offset")
        painter.restore()
        painter.drawText(lm, h - 20, w - lm - rm, 15, QtCore.Qt.AlignCenter, "Frame")

        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(TEXT_DISABLED_COLOR)
        painter.drawText(lm - 42, tm - 2, 38, 15, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, f"{y_max:.1f}")
        painter.drawText(lm - 42, h // 2 - 7, 38, 15, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "0.0")
        painter.drawText(lm - 42, h - bm - 10, 38, 15, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom, f"{y_min:.1f}")

        all_x = ([x for c in self.multi_curves for x in c['x']] if self.multi_curves else self.x_data)
        if all_x:
            x_min, x_max = min(all_x), max(all_x)
            painter.drawText(lm - 10, h - bm + 10, 40, 15, QtCore.Qt.AlignLeft, f"{int(x_min)}")
            painter.drawText(w - rm - 30, h - bm + 10, 40, 15, QtCore.Qt.AlignRight, f"{int(x_max)}")

        return lm, tm, rm, bm

    def _draw_curve_path(self, painter, x_data, y_data, x_min, x_max, y_min, y_max, margins, color):
        """Draw a single curve path within the given margins."""
        lm, tm, rm, bm = margins
        w, h = self.width(), self.height()
        gw = w - lm - rm
        gh = h - tm - bm

        painter.setPen(QtGui.QPen(color, 2))
        path = QtGui.QPainterPath()
        for i, (x, y) in enumerate(zip(x_data, y_data)):
            px = lm + gw * (x - x_min) / (x_max - x_min)
            py = tm + gh * (1.0 - (y - y_min) / (y_max - y_min))
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)
        painter.drawPath(path)

    def _draw_legend(self, painter, curves):
        """Draw a color-coded legend for multi-curve display."""
        legend_x = self.width() - 120
        painter.setFont(QtGui.QFont("Arial", 8))
        for i, curve in enumerate(curves):
            y = 10 + i * 16
            painter.fillRect(legend_x, y + 2, 12, 12, curve['color'])
            painter.setPen(TEXT_COLOR)
            painter.drawText(legend_x + 16, y + 12, curve['label'])