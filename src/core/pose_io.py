# ReAnimate/core/pose_io.py
from maya import cmds as cmd

def apply_pose(pose_data, mapping):
    """Apply a saved pose dict to a target rig based on a joint mapping."""
    if not pose_data or "joints" not in pose_data:
        cmd.warning("Invalid pose data.")
        return

    for src, tgt in mapping.items():
        if src not in pose_data["joints"]:
            continue
        if not cmd.objExists(tgt):
            continue

        attrs = pose_data["joints"][src]
        for attr_type, values in attrs.items():
            if len(values) != 3:
                continue
            if attr_type == "translate":
                cmd.setAttr(f"{tgt}.translate", *values)
            elif attr_type == "rotate":
                cmd.setAttr(f"{tgt}.rotate", *values)
            elif attr_type == "scale":
                cmd.setAttr(f"{tgt}.scale", *values)


def apply_animation(anim_data, mapping, frame_offset=0):
    """Apply animation data (keyframes) from JSON to target rig with optional frame offset."""
    if not anim_data or "joints" not in anim_data:
        cmd.warning("Invalid animation data.")
        return

    for src, tgt in mapping.items():
        if src not in anim_data["joints"]:
            continue
        if not cmd.objExists(tgt):
            continue

        joint_data = anim_data["joints"][src]
        for attr, keyframes in joint_data.items():
            tgt_attr = f"{tgt}.{attr}"
            if not cmd.objExists(tgt_attr):
                continue
            for frame, value in keyframes:
                cmd.setKeyframe(tgt_attr, time=(frame + frame_offset), value=value)
