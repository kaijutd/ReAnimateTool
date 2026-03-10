# ui/anim_noise_widget.py
from PySide6 import QtCore, QtGui, QtWidgets
import maya.cmds as cmds
import random
import math
from core.anim_noise_core import AnimNoiseCore

# Color scheme matching existing delegates
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
    """Widget for adding procedural noise to animation layers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_objects = []
        self.current_layer = None
        self.core = AnimNoiseCore()

        self._setup_ui()
        self._connect_signals()
        self._refresh_timeline_range()
        self._refresh_layer_list()
        self._apply_initial_styles()

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

        scroll_layout.addWidget(self._build_target_section())
        scroll_layout.addWidget(self._build_layer_section())
        scroll_layout.addWidget(self._build_frame_range_section())
        scroll_layout.addWidget(self._build_attributes_section())
        scroll_layout.addWidget(self._build_noise_params_section())
        scroll_layout.addWidget(self._build_preview_section())

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        main_layout.addWidget(self._build_action_buttons())

    def _build_target_section(self):
        """Target selection section."""
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
        """Animation layer section."""
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
        weight_label = QtWidgets.QLabel("Layer Weight:")
        layout.addWidget(weight_label)

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
        """Frame range section."""
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
        """Attributes and amplitude section."""
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
                attr_widget = self._create_attribute_row(label, attr, default, min_val, max_val)
                container_layout.addWidget(attr_widget)

            container.hide()
            layout.addWidget(container)
            self.attr_containers[group_name] = container

            master_cb.toggled.connect(lambda checked, g=group_name: self._on_master_toggle(g, checked))
            layout.addSpacing(8)

        group.setLayout(layout)
        return group

    def _create_attribute_row(self, label, attr, default, min_val, max_val):
        """Create a single attribute row."""
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

        freq_layout = QtWidgets.QHBoxLayout()
        freq_layout.addWidget(QtWidgets.QLabel("Freq:"))
        freq_spin = QtWidgets.QDoubleSpinBox()
        freq_spin.setRange(0.01, 10.0)
        freq_spin.setValue(1.0)
        freq_spin.setSingleStep(0.1)
        freq_spin.setMaximumWidth(60)
        freq_layout.addWidget(freq_spin)
        freq_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        freq_slider.setRange(1, 1000)
        freq_slider.setValue(100)
        freq_layout.addWidget(freq_slider)
        advanced_layout.addLayout(freq_layout)

        oct_layout = QtWidgets.QHBoxLayout()
        oct_layout.addWidget(QtWidgets.QLabel("Oct:"))
        oct_spin = QtWidgets.QSpinBox()
        oct_spin.setRange(1, 8)
        oct_spin.setValue(3)
        oct_spin.setMaximumWidth(60)
        oct_layout.addWidget(oct_spin)
        oct_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        oct_slider.setRange(1, 8)
        oct_slider.setValue(3)
        oct_layout.addWidget(oct_slider)
        advanced_layout.addLayout(oct_layout)

        pers_layout = QtWidgets.QHBoxLayout()
        pers_layout.addWidget(QtWidgets.QLabel("Pers:"))
        pers_spin = QtWidgets.QDoubleSpinBox()
        pers_spin.setRange(0.0, 1.0)
        pers_spin.setValue(0.5)
        pers_spin.setSingleStep(0.1)
        pers_spin.setMaximumWidth(60)
        pers_layout.addWidget(pers_spin)
        pers_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        pers_slider.setRange(0, 100)
        pers_slider.setValue(50)
        pers_layout.addWidget(pers_slider)
        advanced_layout.addLayout(pers_layout)

        seed_layout = QtWidgets.QHBoxLayout()
        seed_layout.addWidget(QtWidgets.QLabel("Seed:"))
        seed_spin = QtWidgets.QSpinBox()
        seed_spin.setRange(0, 999999)
        seed_spin.setValue(1234)
        seed_spin.setMaximumWidth(80)
        seed_layout.addWidget(seed_spin)
        seed_layout.addStretch()
        advanced_layout.addLayout(seed_layout)

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
        """Global noise parameters section with Noise Mode."""
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

        # NOISE MODE DROPDOWN - NEW!
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

        global_layout.addWidget(QtWidgets.QLabel("Frequency:"))
        freq_layout = QtWidgets.QHBoxLayout()
        self.frequency_spinbox = QtWidgets.QDoubleSpinBox()
        self.frequency_spinbox.setRange(0.01, 10.0)
        self.frequency_spinbox.setValue(1.0)
        self.frequency_spinbox.setSingleStep(0.1)
        self.frequency_spinbox.setMaximumWidth(70)
        self.frequency_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.frequency_slider.setRange(1, 1000)
        self.frequency_slider.setValue(100)
        freq_layout.addWidget(self.frequency_spinbox)
        freq_layout.addWidget(self.frequency_slider)
        global_layout.addLayout(freq_layout)

        global_layout.addWidget(QtWidgets.QLabel("Octaves:"))
        oct_layout = QtWidgets.QHBoxLayout()
        self.octaves_spinbox = QtWidgets.QSpinBox()
        self.octaves_spinbox.setRange(1, 8)
        self.octaves_spinbox.setValue(3)
        self.octaves_spinbox.setMaximumWidth(70)
        self.octaves_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.octaves_slider.setRange(1, 8)
        self.octaves_slider.setValue(3)
        oct_layout.addWidget(self.octaves_spinbox)
        oct_layout.addWidget(self.octaves_slider)
        global_layout.addLayout(oct_layout)

        global_layout.addWidget(QtWidgets.QLabel("Persistence:"))
        pers_layout = QtWidgets.QHBoxLayout()
        self.persistence_spinbox = QtWidgets.QDoubleSpinBox()
        self.persistence_spinbox.setRange(0.0, 1.0)
        self.persistence_spinbox.setValue(0.5)
        self.persistence_spinbox.setSingleStep(0.1)
        self.persistence_spinbox.setMaximumWidth(70)
        self.persistence_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.persistence_slider.setRange(0, 100)
        self.persistence_slider.setValue(50)
        pers_layout.addWidget(self.persistence_spinbox)
        pers_layout.addWidget(self.persistence_slider)
        global_layout.addLayout(pers_layout)

        seed_layout = QtWidgets.QHBoxLayout()
        seed_layout.addWidget(QtWidgets.QLabel("Seed:"))
        self.seed_spinbox = QtWidgets.QSpinBox()
        self.seed_spinbox.setRange(0, 999999)
        self.seed_spinbox.setValue(1234)
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
        """Preview graph section."""
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
        """Bottom action buttons."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.apply_btn = QtWidgets.QPushButton("Apply Noise to Layer")
        self.apply_btn.setMinimumHeight(35)

        self.remove_btn = QtWidgets.QPushButton("Remove Selected Layer")
        self.remove_btn.setMinimumHeight(30)

        layout.addWidget(self.apply_btn)
        layout.addWidget(self.remove_btn)

        return widget

    def _connect_signals(self):
        """Connect all UI signals."""
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

        for widget in [self.frequency_spinbox, self.octaves_spinbox, self.persistence_spinbox,
                       self.seed_spinbox, self.noise_type_combo]:
            if hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._update_preview)
            elif hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._update_preview)

        self.apply_btn.clicked.connect(self._on_apply_noise)
        self.remove_btn.clicked.connect(self._on_remove_layer)

    def _apply_initial_styles(self):
        """Apply consistent styling."""
        for master_cb in self.master_checkboxes.values():
            self._update_master_appearance(master_cb, False)

        for attr in self.attr_controls.keys():
            self._update_attr_appearance(attr, False)

    def _on_master_toggle(self, group_name, checked):
        """Toggle all attributes in a group."""
        container = self.attr_containers.get(group_name)
        master_cb = self.master_checkboxes.get(group_name)

        if not container or not master_cb:
            return

        self._update_master_appearance(master_cb, checked)
        container.setVisible(checked)

        group_attrs = {
            'translate': ['tx', 'ty', 'tz'],
            'rotate': ['rx', 'ry', 'rz'],
            'scale': ['sx', 'sy', 'sz']
        }

        for attr in group_attrs.get(group_name, []):
            if attr in self.attr_controls:
                self.attr_controls[attr]['checkbox'].setChecked(checked)

    def _update_master_appearance(self, master_checkbox, enabled):
        """Update master checkbox appearance."""
        if enabled:
            master_checkbox.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        else:
            master_checkbox.setStyleSheet(f"font-weight: bold; color: {TEXT_DISABLED_COLOR.name()};")

    def _update_attr_appearance(self, attr, enabled):
        """Update attribute row appearance."""
        controls = self.attr_controls.get(attr)
        if not controls:
            return

        checkbox = controls['checkbox']
        spinbox = controls['spinbox']
        slider = controls['slider']

        if enabled:
            checkbox.setStyleSheet(f"color: {TEXT_COLOR.name()};")
            spinbox.setEnabled(True)
            slider.setEnabled(True)
        else:
            checkbox.setStyleSheet(f"color: {TEXT_DISABLED_COLOR.name()};")
            spinbox.setEnabled(False)
            slider.setEnabled(False)

        if self.advanced_checkbox.isChecked() and enabled:
            controls['advanced_container'].setVisible(True)
        else:
            controls['advanced_container'].setVisible(False)

    def _on_advanced_mode_toggled(self, checked):
        """Toggle advanced mode."""
        self.global_params_container.setVisible(not checked)
        self.global_note.setVisible(not checked)

        for attr, controls in self.attr_controls.items():
            is_checked = controls['checkbox'].isChecked()
            controls['advanced_container'].setVisible(checked and is_checked)

        self._update_preview()

    def _on_refresh_selection(self):
        """Refresh selected objects."""
        self.selected_objects = cmds.ls(selection=True, type='transform') or []
        count = len(self.selected_objects)
        self.selected_label.setText(f"Selected Objects: {count}")

        if count == 0:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select objects in Maya viewport.")

    def _on_layer_mode_changed(self):
        """Toggle layer name field."""
        create_new = self.create_new_radio.isChecked()
        self.layer_name_field.setEnabled(create_new)
        self.layer_combo.setEnabled(not create_new)

    def _on_weight_changed(self, value):
        """Update layer weight."""
        if self.current_layer:
            weight = value / 100.0
            self.core.set_layer_weight(self.current_layer, weight)

    def _refresh_timeline_range(self):
        """Get timeline range from Maya."""
        try:
            start = int(cmds.playbackOptions(q=True, minTime=True))
            end = int(cmds.playbackOptions(q=True, maxTime=True))
            self.start_frame_spinbox.setValue(start)
            self.end_frame_spinbox.setValue(end)
        except:
            pass

    def _randomize_seed(self):
        """Generate random seed."""
        new_seed = random.randint(0, 999999)
        self.seed_spinbox.setValue(new_seed)

        if self.advanced_checkbox.isChecked():
            for controls in self.attr_controls.values():
                controls['seed_spin'].setValue(random.randint(0, 999999))

    def _update_preview(self):
        """Update preview graph."""
        start = self.start_frame_spinbox.value()
        end = self.end_frame_spinbox.value()
        samples = min(500, end - start + 1)

        advanced_mode = self.advanced_checkbox.isChecked()

        if advanced_mode:
            curves_data = []

            for attr, controls in self.attr_controls.items():
                if not controls['checkbox'].isChecked():
                    continue

                params = self._collect_noise_params(controls)
                amplitude = params.pop('amplitude')  # remove amplitude before passing to _generate_noise_value

                x_values = []
                y_values = []

                for i in range(samples):
                    frame = start + (end - start) * (i / float(samples - 1))
                    noise_val = self._generate_noise_value(
                        frame,
                        noise_type=params['noise_type'],
                        frequency=params['frequency'],
                        octaves=params['octaves'],
                        persistence=params['persistence'],
                        seed=params['seed']
                    )
                    y_values.append(noise_val * amplitude)
                    x_values.append(frame)

                curves_data.append({
                    'x': x_values,
                    'y': y_values,
                    'label': controls['label'],
                    'color': AXIS_COLORS.get(attr, QtGui.QColor(200, 200, 200))
                })

            self.preview_canvas.set_multi_data(curves_data)
        else:
            # global mode
            params = self._collect_noise_params()
            x_values = []
            y_values = []

            for i in range(samples):
                frame = start + (end - start) * (i / float(samples - 1))
                noise_val = self._generate_noise_value(
                    frame,
                    noise_type=params['noise_type'],
                    frequency=params['frequency'],
                    octaves=params['octaves'],
                    persistence=params['persistence'],
                    seed=params['seed']
                )
                y_values.append(noise_val)

                x_values.append(frame)

            self.preview_canvas.set_data(x_values, y_values)

    def _generate_noise_value(self, frame, noise_type, frequency, octaves, persistence, seed):
        """Generate noise value for preview."""
        if noise_type == "Sine Wave":
            return math.sin(frame * frequency * 0.1)
        elif noise_type == "Perlin":
            return self._perlin_noise(frame * frequency, octaves, persistence, seed)
        else:
            return self._perlin_noise(frame * frequency * 0.8, octaves, persistence, seed)

    def _perlin_noise(self, x, octaves, persistence, seed):
        """Multi-octave noise."""
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(octaves):
            val = self._noise1d(x * frequency + seed)
            total += val * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2.0

        return total / max_value if max_value != 0 else 0

    def _noise1d(self, x):
        """1D noise function."""
        i = int(x)
        f = x - i
        f = f * f * (3.0 - 2.0 * f)

        a = math.sin(i * 12.9898 + 78.233) * 43758.5453
        b = math.sin((i + 1) * 12.9898 + 78.233) * 43758.5453

        a = a - math.floor(a)
        b = b - math.floor(b)

        return (a * (1.0 - f) + b * f) * 2.0 - 1.0

    def _on_apply_noise(self):
        """Apply noise using core logic."""
        if not self.selected_objects:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Please select objects first and click 'Refresh Selection'.")
            return

        selected_attrs = [attr for attr, controls in self.attr_controls.items()
                          if controls['checkbox'].isChecked()]

        if not selected_attrs:
            QtWidgets.QMessageBox.warning(self, "No Attributes",
                                          "Please select at least one attribute (enable a master checkbox).")
            return

        start_frame = self.start_frame_spinbox.value()
        end_frame = self.end_frame_spinbox.value()
        sample_rate = self.sample_rate_spinbox.value()

        if end_frame < start_frame:
            QtWidgets.QMessageBox.warning(self, "Invalid Range",
                                          "End frame must be greater than start frame.")
            return

        if self.create_new_radio.isChecked():
            layer_name = self.layer_name_field.text().strip()
            layer_mode = 'create_new'

            if not layer_name:
                QtWidgets.QMessageBox.warning(self, "Invalid Layer Name",
                                              "Please enter a valid layer name.")
                return
        else:
            layer_name = self.layer_combo.currentText()
            layer_mode = 'use_existing'

            if not layer_name or layer_name == "No layers available":
                QtWidgets.QMessageBox.warning(self, "No Layer Selected",
                                              "Please select an existing layer or create a new one.")
                return

        advanced_mode = self.advanced_checkbox.isChecked()

        # Global parameters WITH noise_mode
        global_params = self._collect_noise_params()
        global_params['noise_mode'] = self.noise_mode_combo.currentText()  # explicitly include noise mode

        # Per-attribute parameters
        attr_params = {}
        for attr, controls in self.attr_controls.items():
            if attr in selected_attrs:
                if advanced_mode:
                    attr_params[attr] = self._collect_noise_params(controls)
                else:
                    attr_params[attr] = {'amplitude': controls['spinbox'].value()}

        # Global params


        params = {
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
        }

        total_frames = ((end_frame - start_frame) // sample_rate) + 1
        total_keys = total_frames * len(selected_attrs) * len(self.selected_objects)

        reply = QtWidgets.QMessageBox.question(self, "Apply Noise",
                                               f"This will create:\n"
                                               f"• {total_keys} keyframes\n"
                                               f"• On {len(self.selected_objects)} object(s)\n"
                                               f"• Across {len(selected_attrs)} attribute(s)\n"
                                               f"• From frame {start_frame} to {end_frame}\n"
                                               f"• Mode: {self.noise_mode_combo.currentText()}\n\n"
                                               f"Continue?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

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

        result = self.core.apply_noise(self.selected_objects, selected_attrs, params, progress_callback)

        progress.close()

        if result['success']:
            self.current_layer = result['layer_name']
            self._refresh_layer_list()
            QtWidgets.QMessageBox.information(self, "Success",
                                              f"{result['message']}\nLayer: {result['layer_name']}")
        else:
            QtWidgets.QMessageBox.warning(self, "Failed", result['message'])

    def _on_remove_layer(self):
        """Remove layer using core logic."""
        if self.add_existing_radio.isChecked():
            layer_name = self.layer_combo.currentText()
        else:
            layer_name = self.current_layer

        if not layer_name or layer_name == "No layers available":
            QtWidgets.QMessageBox.warning(self, "No Layer", "No layer selected to remove.")
            return

        reply = QtWidgets.QMessageBox.question(self, "Remove Layer",
                                               f"Are you sure you want to delete layer '{layer_name}'?\nThis cannot be undone.",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            result = self.core.remove_layer(layer_name)

            if result['success']:
                if self.current_layer == layer_name:
                    self.current_layer = None
                self._refresh_layer_list()
                QtWidgets.QMessageBox.information(self, "Success", result['message'])
            else:
                QtWidgets.QMessageBox.critical(self, "Error", result['message'])

    def _refresh_layer_list(self):
        """Refresh layer list."""
        self.layer_combo.clear()
        layers = self.core.get_animation_layers()

        if layers:
            self.layer_combo.addItems(layers)
        else:
            self.layer_combo.addItem("No layers available")

    def _collect_noise_params(self, controls=None):
        """
        Collect noise parameters for either global or per-attribute.

        :param controls: dict of attribute controls, or None for global
        :return: dict of noise parameters
        """
        params = {
            'noise_mode': self.noise_mode_combo.currentText(),
            'noise_type': self.noise_type_combo.currentText(),
        }

        if controls:
            # Per-attribute advanced controls
            params.update({
                'frequency': controls['freq_spin'].value(),
                'octaves': controls['oct_spin'].value(),
                'persistence': controls['pers_spin'].value(),
                'seed': controls['seed_spin'].value(),
                'amplitude': controls['spinbox'].value()
            })
        else:
            # Global controls
            params.update({
                'frequency': self.frequency_spinbox.value(),
                'octaves': self.octaves_spinbox.value(),
                'persistence': self.persistence_spinbox.value(),
                'seed': self.seed_spinbox.value()
            })

        return params


class NoisePreviewCanvas(QtWidgets.QWidget):
    """Custom widget for drawing noise preview graph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.x_data = []
        self.y_data = []
        self.multi_curves = []
        self.setMinimumSize(400, 220)

    def set_data(self, x_data, y_data):
        """Update single curve data."""
        self.x_data = x_data
        self.y_data = y_data
        self.multi_curves = []
        self.update()

    def set_multi_data(self, curves_data):
        """Update multi-curve data."""
        self.multi_curves = curves_data
        self.x_data = []
        self.y_data = []
        self.update()

    def paintEvent(self, event):
        """Draw noise curves."""
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
                             "Click 'Update Preview' to see additive offset curve")

    def _draw_multi_curves(self, painter):
        """Draw multiple curves."""
        if not self.multi_curves:
            return

        w = self.width()
        h = self.height()

        all_x = []
        all_y = []
        for curve in self.multi_curves:
            all_x.extend(curve['x'])
            all_y.extend(curve['y'])

        if not all_x or not all_y:
            return

        x_min = min(all_x)
        x_max = max(all_x)
        y_min = min(all_y)
        y_max = max(all_y)

        if y_max == y_min:
            y_max = y_min + 1.0
        if x_max == x_min:
            x_max = x_min + 1.0

        margins = self._draw_grid(painter, w, h, 20, y_min, y_max)
        left_margin, top_margin, right_margin, bottom_margin = margins

        for curve in self.multi_curves:
            color = curve.get('color', QtGui.QColor(100, 200, 255))
            self._draw_curve_path_with_margins(painter, curve['x'], curve['y'],
                                               x_min, x_max, y_min, y_max,
                                               w, h, left_margin, top_margin, right_margin, bottom_margin, color)

        self._draw_legend(painter, self.multi_curves, w, h)

    def _draw_single_curve(self, painter, x_data, y_data, color):
        """Draw single curve."""
        w = self.width()
        h = self.height()

        x_min = min(x_data)
        x_max = max(x_data)
        y_min = min(y_data)
        y_max = max(y_data)

        if y_max == y_min:
            y_max = y_min + 1.0
        if x_max == x_min:
            x_max = x_min + 1.0

        margins = self._draw_grid(painter, w, h, 20, y_min, y_max)
        left_margin, top_margin, right_margin, bottom_margin = margins
        self._draw_curve_path_with_margins(painter, x_data, y_data, x_min, x_max, y_min, y_max,
                                           w, h, left_margin, top_margin, right_margin, bottom_margin, color)

    def _draw_grid(self, painter, w, h, base_margin, y_min, y_max):
        """Draw grid with axes labels."""
        left_margin = 20
        bottom_margin = 35
        top_margin = 15
        right_margin = 20

        painter.setPen(BORDER_COLOR)
        for i in range(5):
            y = top_margin + (h - top_margin - bottom_margin) * i / 4
            painter.drawLine(left_margin, int(y), w - right_margin, int(y))

        if y_min <= 0 <= y_max:
            zero_y = top_margin + (h - top_margin - bottom_margin) * (1.0 - (0 - y_min) / (y_max - y_min))
            if top_margin <= zero_y <= h - bottom_margin:
                painter.setPen(QtGui.QPen(TEXT_DISABLED_COLOR, 2, QtCore.Qt.DashLine))
                painter.drawLine(left_margin, int(zero_y), w - right_margin, int(zero_y))

        painter.setPen(TEXT_COLOR)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        painter.save()
        painter.translate(12, h / 2)
        painter.rotate(-90)
        painter.drawText(-60, 0, 120, 20, QtCore.Qt.AlignCenter, "Additive Offset")
        painter.restore()

        painter.drawText(left_margin, h - 20, w - left_margin - right_margin, 15,
                         QtCore.Qt.AlignCenter, "Frame")

        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(TEXT_DISABLED_COLOR)

        painter.drawText(left_margin - 42, top_margin - 2, 38, 15,
                         QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, f"{y_max:.1f}")
        painter.drawText(left_margin - 42, h / 2 - 7, 38, 15,
                         QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, "0.0")
        painter.drawText(left_margin - 42, h - bottom_margin - 10, 38, 15,
                         QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom, f"{y_min:.1f}")

        if len(self.x_data) > 0 or len(self.multi_curves) > 0:
            if self.multi_curves and len(self.multi_curves) > 0:
                x_min = min(min(c['x']) for c in self.multi_curves)
                x_max = max(max(c['x']) for c in self.multi_curves)
            else:
                x_min = min(self.x_data) if self.x_data else 0
                x_max = max(self.x_data) if self.x_data else 100

            painter.drawText(left_margin - 10, h - bottom_margin + 10, 40, 15,
                             QtCore.Qt.AlignLeft, f"{int(x_min)}")
            painter.drawText(w - right_margin - 30, h - bottom_margin + 10, 40, 15,
                             QtCore.Qt.AlignRight, f"{int(x_max)}")

        return left_margin, top_margin, right_margin, bottom_margin

    def _draw_curve_path_with_margins(self, painter, x_data, y_data, x_min, x_max, y_min, y_max,
                                      w, h, left_margin, top_margin, right_margin, bottom_margin, color):
        """Draw curve path with proper margins."""
        painter.setPen(QtGui.QPen(color, 2))
        path = QtGui.QPainterPath()

        graph_width = w - left_margin - right_margin
        graph_height = h - top_margin - bottom_margin

        for i, (x, y) in enumerate(zip(x_data, y_data)):
            px = left_margin + graph_width * (x - x_min) / (x_max - x_min)
            py = top_margin + graph_height * (1.0 - (y - y_min) / (y_max - y_min))

            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        painter.drawPath(path)

    def _draw_legend(self, painter, curves, w, h):
        """Draw legend."""
        legend_x = w - 120
        legend_y = 10
        line_height = 16

        painter.setFont(QtGui.QFont("Arial", 8))

        for i, curve in enumerate(curves):
            y = legend_y + i * line_height
            painter.fillRect(legend_x, y + 2, 12, 12, curve['color'])
            painter.setPen(TEXT_COLOR)
            painter.drawText(legend_x + 16, y + 12, curve['label'])


