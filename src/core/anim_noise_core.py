"""
core/anim_noise_core.py - Animation noise generation and application.
Supports additive and multiplicative noise modes via animation layers.
"""

import math
import maya.cmds as cmds


class AnimNoiseCore:
    """Applies procedural noise to animation curves via an override anim layer."""

    def __init__(self):
        self.current_layer = None

    # --- Public ---

    def apply_noise(self, objects, attributes, params, progress_callback=None):
        """
        Main entry point. Samples base animation, creates an override layer,
        and applies noise to the specified attributes.

        Returns:
            dict: success status, message, keys created, and layer name.
        """
        validation = self._validate_inputs(objects, attributes, params)
        if not validation['valid']:
            return {'success': False, 'message': validation['message']}

        start = int(params['start_frame'])
        end = int(params['end_frame'])
        sample_rate = int(params['sample_rate'])
        layer_name = params['layer_name']
        sample_frames = list(range(start, end + 1, sample_rate))

        base_selected = self._sample_base_selected_attributes(objects, attributes, sample_frames)
        base_full_bake = self._sample_base_all_keyable_keys(objects)

        layer_name = self._create_or_get_overwrite_layer(objects, layer_name)
        self.current_layer = layer_name

        self._bake_full_base_copy(layer_name, base_full_bake)

        keys_created = self._apply_noise_to_selected_attributes(
            objects, attributes, params, sample_frames,
            base_selected, layer_name, progress_callback
        )

        return {
            'success': True,
            'message': f"Created {keys_created} keys on layer '{layer_name}'",
            'keys_created': keys_created,
            'layer_name': layer_name
        }

    def get_animation_layers(self):
        """Return all anim layers excluding the base layer."""
        return [l for l in (cmds.ls(type='animLayer') or []) if l != 'BaseAnimation']

    # --- Base Sampling ---

    def _sample_base_selected_attributes(self, objects, attributes, frames):
        """Sample attribute values at specified frames before noise is applied."""
        out = {}
        for obj in objects:
            for attr in attributes:
                full_attr = f"{obj}.{attr}"
                out.setdefault(full_attr, {})
                for f in frames:
                    try:
                        out[full_attr][f] = cmds.getAttr(full_attr, time=f)
                    except Exception:
                        out[full_attr][f] = None
        return out

    def _sample_base_all_keyable_keys(self, objects):
        """Sample all existing keyframe values for all keyable attributes."""
        out = {}
        for obj in objects:
            for attr in (cmds.listAttr(obj, keyable=True) or []):
                full_attr = f"{obj}.{attr}"
                times = cmds.keyframe(full_attr, query=True, timeChange=True) or []
                if not times:
                    continue
                out.setdefault(full_attr, {})
                for t in times:
                    try:
                        out[full_attr][t] = cmds.getAttr(full_attr, time=t)
                    except Exception:
                        out[full_attr][t] = None
        return out

    # --- Layer Operations ---

    def _create_or_get_overwrite_layer(self, objects, layer_name):
        """Create or update an override anim layer for the given objects."""
        cmds.select(objects, replace=True)
        if not cmds.animLayer(layer_name, q=True, exists=True):
            cmds.animLayer(layer_name, override=True, passthrough=False, addSelectedObjects=True)
        else:
            cmds.animLayer(layer_name, edit=True, addSelectedObjects=True)
            cmds.animLayer(layer_name, edit=True, override=True, passthrough=False)
        return layer_name

    def _bake_full_base_copy(self, layer_name, full_bake_map):
        """Write base keyframe values into the override layer."""
        for full_attr, times_map in full_bake_map.items():
            for t, v in times_map.items():
                if v is None:
                    continue
                try:
                    cmds.setKeyframe(full_attr, time=t, value=v, animLayer=layer_name)
                except Exception:
                    pass

    # --- Noise Application ---

    def _apply_noise_to_selected_attributes(
        self, objects, attributes, params, frames, base_samples, layer_name, progress_callback
    ):
        """Apply noise to each attribute at each frame on the override layer."""
        keys_created = 0
        advanced = params['advanced_mode']
        randomize = params['randomize_per_object']
        global_p = params['global_params']
        attr_p = params['attr_params']
        mode = params.get('noise_mode', "Additive")

        total_ops = len(objects) * len(attributes) * len(frames)
        op_index = 0

        for obj_i, obj in enumerate(objects):
            for attr in attributes:
                p = (attr_p.get(attr) or {}).copy() if advanced else global_p.copy()
                if not advanced and attr in attr_p and 'amplitude' in attr_p[attr]:
                    p['amplitude'] = attr_p[attr]['amplitude']

                p.setdefault('noise_type', 'Perlin')
                p.setdefault('amplitude', 1.0)
                p.setdefault('frequency', 1.0)
                p.setdefault('octaves', 1)
                p.setdefault('persistence', 0.5)
                p.setdefault('seed', 0)

                if randomize:
                    p['seed'] += obj_i * 1000

                full_attr = f"{obj}.{attr}"
                try:
                    cmds.animLayer(layer_name, edit=True, attribute=full_attr)
                except Exception:
                    pass

                for f in frames:
                    if progress_callback:
                        if not progress_callback(op_index, total_ops, f"Processing {full_attr} frame {f}"):
                            return keys_created

                    base_val = base_samples[full_attr][f]
                    if base_val is None:
                        op_index += 1
                        continue
                    noise_v = self._generate_noise(
                        f, p['noise_type'], p['frequency'],
                        p['octaves'], p['persistence'], p['seed']
                    )
                    amp = p['amplitude']
                    final_val = base_val * (1 + noise_v * amp) if mode == "Multiplicative" else base_val + noise_v * amp

                    try:
                        cmds.setKeyframe(full_attr, time=f, value=final_val, animLayer=layer_name)
                        keys_created += 1
                    except Exception:
                        pass

                    op_index += 1

        return keys_created

    # --- Validation & Noise Generation ---

    def _validate_inputs(self, objects, attributes, params):
        """Validate objects, attributes, and frame range before processing."""
        if not objects:
            return {'valid': False, 'message': 'No objects provided'}
        if not attributes:
            return {'valid': False, 'message': 'No attributes provided'}
        if params['end_frame'] < params['start_frame']:
            return {'valid': False, 'message': 'Invalid frame range'}
        return {'valid': True, 'message': 'Valid'}

    def _generate_noise(self, frame, noise_type, frequency, octaves, persistence, seed):
        """Generate a noise value for a given frame using the specified noise type."""
        if noise_type == "Sine Wave":
            return math.sin(frame * frequency * 0.1)
        return self._perlin_noise(
            frame * frequency if noise_type == "Perlin" else frame * frequency * 0.8,
            octaves, persistence, seed
        )

    def _perlin_noise(self, x, octaves, persistence, seed):
        """Layered 1D Perlin-style noise with configurable octaves."""
        total, freq, amp, max_val = 0.0, 1.0, 1.0, 0.0
        for _ in range(int(octaves)):
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