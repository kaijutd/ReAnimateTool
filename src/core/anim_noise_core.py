# core/anim_noise_core.py
"""
Animation Noise Core (cleaned + helper extracted + additive/multiplicative mode)
"""

import maya.cmds as cmds
import math


class AnimNoiseCore:
    def __init__(self):
        self.current_layer = None

    # =======================================================================
    # PUBLIC MAIN ENTRY
    # =======================================================================
    def apply_noise(self, objects, attributes, params, progress_callback=None):

        # ---------------------------
        # Validate
        # ---------------------------
        validation = self._validate_inputs(objects, attributes, params)
        if not validation['valid']:
            return {'success': False, 'message': validation['message']}

        start = int(params['start_frame'])
        end = int(params['end_frame'])
        sample_rate = int(params['sample_rate'])
        layer_name = params['layer_name']

        sample_frames = list(range(start, end + 1, sample_rate))

        # ---------------------------
        # 1) SAMPLE BASE BEFORE LAYERS
        # ---------------------------
        base_selected = self._sample_base_selected_attributes(
            objects, attributes, sample_frames
        )

        base_full_bake = self._sample_base_all_keyable_keys(objects)

        # ---------------------------
        # 2) CREATE OVERWRITE LAYER
        # ---------------------------
        layer_name = self._create_or_get_overwrite_layer(objects, layer_name)
        self.current_layer = layer_name

        # ---------------------------
        # 3) BAKE FULL BASE COPY
        # ---------------------------
        self._bake_full_base_copy(layer_name, base_full_bake)

        # ---------------------------
        # 4) APPLY NOISE (additive or multiplicative)
        # ---------------------------
        keys_created = self._apply_noise_to_selected_attributes(
            objects,
            attributes,
            params,
            sample_frames,
            base_selected,
            layer_name,
            progress_callback
        )

        # ---------------------------
        # 5) DIAGNOSTIC
        # ---------------------------
        self._print_diagnostic_table(base_selected)

        return {
            'success': True,
            'message': f"Created {keys_created} keys on layer '{layer_name}'",
            'keys_created': keys_created,
            'layer_name': layer_name
        }

    # =======================================================================
    # HELPERS — BASE SAMPLING
    # =======================================================================
    def _sample_base_selected_attributes(self, objects, attributes, frames):
        out = {}
        for obj in objects:
            for attr in attributes:
                full_attr = f"{obj}.{attr}"
                out.setdefault(full_attr, {})
                for f in frames:
                    try:
                        out[full_attr][f] = cmds.getAttr(full_attr, time=f)
                    except:
                        out[full_attr][f] = None
        return out

    def _sample_base_all_keyable_keys(self, objects):
        out = {}
        for obj in objects:
            keyable = cmds.listAttr(obj, keyable=True) or []
            for attr in keyable:
                full_attr = f"{obj}.{attr}"
                times = cmds.keyframe(full_attr, query=True, timeChange=True) or []
                if not times:
                    continue
                out.setdefault(full_attr, {})
                for t in times:
                    try:
                        out[full_attr][t] = cmds.getAttr(full_attr, time=t)
                    except:
                        out[full_attr][t] = None
        return out

    # =======================================================================
    # HELPERS — LAYER OPS
    # =======================================================================
    def _create_or_get_overwrite_layer(self, objects, layer_name):
        if not cmds.animLayer(layer_name, q=True, exists=True):
            cmds.select(objects, replace=True)
            cmds.animLayer(
                layer_name,
                override=True,
                passthrough=False,
                addSelectedObjects=True
            )
        else:
            cmds.select(objects, replace=True)
            cmds.animLayer(layer_name, edit=True, addSelectedObjects=True)
            cmds.animLayer(layer_name, edit=True, override=True, passthrough=False)
        return layer_name

    def _bake_full_base_copy(self, layer_name, full_bake_map):
        for full_attr, times_map in full_bake_map.items():
            for t, v in times_map.items():
                if v is None:
                    continue
                try:
                    cmds.setKeyframe(full_attr, time=t, value=v, animLayer=layer_name)
                except:
                    pass  # locked/unkeyable plugs are skipped

    # =======================================================================
    # HELPERS — NOISE APPLICATION
    # =======================================================================
    def _apply_noise_to_selected_attributes(
        self, objects, attributes, params, frames, base_samples, layer_name, progress_callback
    ):
        keys_created = 0
        advanced = params['advanced_mode']
        randomize = params['randomize_per_object']
        global_p = params['global_params']
        attr_p = params['attr_params']
        mode = params.get('noise_mode', "Additive")  # Additive / Multiplicative

        total_ops = len(objects) * len(attributes) * len(frames)
        op_index = 0

        for obj_i, obj in enumerate(objects):
            for attr in attributes:

                # get noise params
                if advanced:
                    p = (attr_p.get(attr) or {}).copy()
                else:
                    p = global_p.copy()
                    if attr in attr_p and 'amplitude' in attr_p[attr]:
                        p['amplitude'] = attr_p[attr]['amplitude']

                # defaults
                p.setdefault('noise_type', 'Perlin')
                p.setdefault('amplitude', 1.0)
                p.setdefault('frequency', 1.0)
                p.setdefault('octaves', 1)
                p.setdefault('persistence', 0.5)
                p.setdefault('seed', 0)

                # randomization
                if randomize:
                    p['seed'] += obj_i * 1000

                full_attr = f"{obj}.{attr}"

                # safely add attr to layer
                try:
                    cmds.animLayer(layer_name, edit=True, attribute=full_attr)
                except:
                    pass

                for f in frames:
                    if progress_callback:
                        if not progress_callback(op_index, total_ops, f"Processing {full_attr} frame {f}"):
                            return keys_created

                    base_val = base_samples[full_attr][f]

                    noise_v = self._generate_noise(
                        f,
                        p['noise_type'],
                        p['frequency'],
                        p['octaves'],
                        p['persistence'],
                        p['seed']
                    )

                    amp = p['amplitude']

                    # MATH SECTION — Additive or Multiplicative
                    if mode == "Multiplicative":
                        final_val = base_val * (1 + noise_v * amp)
                    else:  # Additive
                        final_val = base_val + noise_v * amp

                    try:
                        cmds.setKeyframe(full_attr, time=f, value=final_val, animLayer=layer_name)
                        keys_created += 1
                    except:
                        pass

                    op_index += 1

        return keys_created

    # =======================================================================
    # DIAGNOSTIC
    # =======================================================================
    def _print_diagnostic_table(self, base_samples):
        print("\n=== DIAGNOSTIC: Base vs Final Values ===")
        count = 0
        for full_attr, frames in base_samples.items():
            for f, base_val in frames.items():
                if count > 80:
                    print("=== END DIAGNOSTIC ===\n")
                    return
                try:
                    final_val = cmds.getAttr(full_attr, time=f)
                except:
                    final_val = None
                delta = final_val - base_val if (base_val is not None and final_val is not None) else None
                print(f"{full_attr} @ {f} | base={base_val} final={final_val} delta={delta}")
                count += 1
        print("=== END DIAGNOSTIC ===\n")

    # =======================================================================
    # VALIDATION + NOISE GENERATION
    # =======================================================================
    def _validate_inputs(self, objects, attributes, params):
        if not objects:
            return {'valid': False, 'message': 'No objects provided'}
        if not attributes:
            return {'valid': False, 'message': 'No attributes provided'}
        if params['end_frame'] < params['start_frame']:
            return {'valid': False, 'message': 'Invalid frame range'}
        return {'valid': True, 'message': "Valid"}

    def _generate_noise(self, frame, noise_type, frequency, octaves, persistence, seed):
        if noise_type == "Sine Wave":
            return math.sin(frame * frequency * 0.1)
        elif noise_type == "Perlin":
            return self._perlin_noise(frame * frequency, octaves, persistence, seed)
        else:
            return self._perlin_noise(frame * frequency * 0.8, octaves, persistence, seed)

    def _perlin_noise(self, x, octaves, persistence, seed):
        total = 0.0
        freq = 1.0
        amp = 1.0
        max_val = 0.0

        for _ in range(int(octaves)):
            val = self._noise1d(x * freq + seed)
            total += val * amp
            max_val += amp
            amp *= persistence
            freq *= 2.0

        return total / max_val if max_val else 0.0

    def _noise1d(self, x):
        i = int(x)
        f = x - i
        f = f * f * (3.0 - 2.0 * f)
        a = math.sin(i * 12.9898 + 78.233) * 43758.5453
        b = math.sin((i + 1) * 12.9898 + 78.233) * 43758.5453
        a -= math.floor(a)
        b -= math.floor(b)
        return (a * (1 - f) + b * f) * 2.0 - 1.0

    def get_animation_layers(self):
        all_layers = cmds.ls(type='animLayer') or []
        return [l for l in all_layers if l != 'BaseAnimation']