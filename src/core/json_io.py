"""
core/json_io.py - Pose, animation, and mapping serialization for ReAnimate Tool.
Handles save/load operations for JSON-based rig data.
"""

import json
import os
import datetime
import maya.cmds as cmd


# --- Internal Helpers ---

def _timestamp():
    """Return a formatted timestamp string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_transform_data(joint, frame=None):
    """Return translate/rotate/scale values for a joint at a given frame."""
    if frame is not None:
        cmd.currentTime(frame)
    return {
        "translate": cmd.getAttr(f"{joint}.translate")[0],
        "rotate": cmd.getAttr(f"{joint}.rotate")[0],
        "scale": cmd.getAttr(f"{joint}.scale")[0]
    }


def save_json(data, path):
    """Write data to a JSON file, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def load_json(path):
    """Load and return data from a JSON file."""
    with open(path, "r") as f:
        return json.load(f)


# --- Pose ---

def save_pose(joints, path, frame=None, pose_type="pose"):
    """Save joint transforms at a given frame to a JSON pose file."""
    data = {
        "type": pose_type,
        "timestamp": _timestamp(),
        "frame": frame if frame is not None else cmd.currentTime(q=True),
        "joints": {}
    }
    for jnt in joints:
        if cmd.objExists(jnt):
            data["joints"][jnt] = _get_transform_data(jnt, frame)
    save_json(data, path)


def load_pose(path):
    """Load a pose JSON file."""
    return load_json(path)


def apply_pose(data, mapping=None, set_keys=False):
    """Apply saved pose transforms to the scene, optionally setting keyframes."""
    frame = data.get("frame", cmd.currentTime(q=True))
    cmd.currentTime(frame)
    for src, values in data.get("joints", {}).items():
        tgt = mapping.get(src, src) if mapping else src
        if not cmd.objExists(tgt):
            continue
        try:
            cmd.setAttr(f"{tgt}.translate", *values["translate"])
            cmd.setAttr(f"{tgt}.rotate", *values["rotate"])
            cmd.setAttr(f"{tgt}.scale", *values["scale"])
            if set_keys:
                for attr in ["translate", "rotate", "scale"]:
                    cmd.setKeyframe(tgt, attribute=attr, time=frame)
        except Exception as e:
            cmd.warning(f"Failed to apply pose on {tgt}: {e}")


# --- Animation ---

def save_animation(joints, path, start, end, fps=24):
    """Save per-frame animation data for a joint list to a JSON file."""
    data = {
        "type": "animation",
        "timestamp": _timestamp(),
        "start_frame": start,
        "end_frame": end,
        "fps": fps,
        "joints": {}
    }
    attrs = ["translateX", "translateY", "translateZ",
             "rotateX", "rotateY", "rotateZ",
             "scaleX", "scaleY", "scaleZ"]
    for jnt in joints:
        if not cmd.objExists(jnt):
            continue
        data["joints"][jnt] = {
            attr: [[f, cmd.getAttr(f"{jnt}.{attr}", time=f)] for f in range(int(start), int(end) + 1)]
            for attr in attrs
        }
    save_json(data, path)


def load_animation(path):
    """Load an animation JSON file, raising an error if the type is invalid."""
    data = load_json(path)
    if data.get("type") != "animation":
        raise ValueError("JSON file is not a valid animation file.")
    return data


def apply_animation(data, mapping=None, frame_offset=0):
    """Apply animation keyframes from JSON data to the scene."""
    for src, attrs in data.get("joints", {}).items():
        tgt = mapping.get(src, src) if mapping else src
        if not cmd.objExists(tgt):
            continue
        for attr, keys in attrs.items():
            for frame, val in keys:
                cmd.setKeyframe(f"{tgt}.{attr}", time=frame + frame_offset, value=val)


# --- Mapping ---

def save_mapping(data, path, version="0.2"):
    """Save rig joint mapping to a JSON file."""
    save_json({
        "type": "mapping",
        "version": version,
        "timestamp": _timestamp(),
        "source_root": data.get("source_root"),
        "target_root": data.get("target_root"),
        "mappings": data.get("mappings", [])
    }, path)


def load_mapping(path):
    """Load a mapping JSON file."""
    return load_json(path)


# --- Build Helpers ---

def build_pose_data(joints, frame):
    """Build a pose data dict from the scene without saving."""
    return {
        "frame": frame,
        "joints": {
            j: _get_transform_data(j, frame)
            for j in joints if cmd.objExists(j)
        }
    }


def build_animation_data(joints, start_frame, end_frame, fps=24):
    """Build an animation data dict from existing keyframes without saving."""
    attrs = ["translateX", "translateY", "translateZ",
             "rotateX", "rotateY", "rotateZ",
             "scaleX", "scaleY", "scaleZ"]
    data = {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "fps": fps,
        "joints": {}
    }
    for j in joints:
        data["joints"][j] = {}
        for attr in attrs:
            times = cmd.keyframe(j, at=attr, query=True, time=(start_frame, end_frame))
            values = cmd.keyframe(j, at=attr, query=True, valueChange=True, time=(start_frame, end_frame))
            if times and values:
                data["joints"][j][attr] = list(zip(times, values))
    return data