"""
core/noise_preset_io.py - Save, load, and list noise presets for ReAnimate Tool.
Built-in presets ship with the tool in src/data/noise_presets/.
User presets are stored in the Maya user directory.
"""

import os
import json
from maya import cmds

# Built-in presets ship with the tool
BUILTIN_PRESETS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "noise_presets")

# User presets stored in Maya's user app dir
USER_PRESETS_DIR = os.path.join(cmds.internalVar(userAppDir=True), "reanimate_library", "noise_presets")


def _ensure_user_dir():
    """Create the user preset directory if it doesn't exist."""
    os.makedirs(USER_PRESETS_DIR, exist_ok=True)
    return USER_PRESETS_DIR


def _load_json(path):
    """Load and return a JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def _save_json(data, path):
    """Write data to a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def list_presets():
    """
    Return a combined list of all available presets.

    Returns:
        list of dicts: Each with 'name', 'path', and 'builtin' keys.
    """
    presets = []

    # Built-in presets
    builtin_dir = os.path.normpath(BUILTIN_PRESETS_DIR)
    if os.path.exists(builtin_dir):
        for f in sorted(os.listdir(builtin_dir)):
            if f.endswith(".json"):
                path = os.path.join(builtin_dir, f)
                try:
                    data = _load_json(path)
                    presets.append({
                        "name": data.get("name", f.replace(".json", "")),
                        "path": path,
                        "builtin": True
                    })
                except Exception:
                    pass

    # User presets
    user_dir = _ensure_user_dir()
    for f in sorted(os.listdir(user_dir)):
        if f.endswith(".json"):
            path = os.path.join(user_dir, f)
            try:
                data = _load_json(path)
                presets.append({
                    "name": data.get("name", f.replace(".json", "")),
                    "path": path,
                    "builtin": False
                })
            except Exception:
                pass

    return presets


def load_preset(path):
    """
    Load a preset from a given file path.

    Args:
        path (str): Full path to the preset JSON file.

    Returns:
        dict: Preset data including settings.
    """
    data = _load_json(path)
    if data.get("type") != "noise_preset":
        raise ValueError(f"File is not a valid noise preset: {path}")
    return data


def save_preset(name, settings, description=""):
    """
    Save a noise preset to the user preset directory.

    Args:
        name (str): Display name for the preset.
        settings (dict): Noise parameter dict to save.
        description (str): Optional description.

    Returns:
        str: Path to the saved preset file.
    """
    _ensure_user_dir()
    filename = f"{name.strip().replace(' ', '_').lower()}.json"
    path = os.path.join(USER_PRESETS_DIR, filename)
    _save_json({
        "type": "noise_preset",
        "name": name,
        "author": "User",
        "description": description,
        "settings": settings
    }, path)
    cmds.inViewMessage(amg=f"Preset '{name}' saved", pos="midCenter", fade=True)
    return path


def delete_preset(path):
    """
    Delete a user preset by file path. Built-in presets cannot be deleted.

    Args:
        path (str): Full path to the preset file.

    Returns:
        bool: True if deleted, False if it was a built-in preset.
    """
    builtin_dir = os.path.normpath(BUILTIN_PRESETS_DIR)
    if os.path.normpath(path).startswith(builtin_dir):
        cmds.warning("Built-in presets cannot be deleted.")
        return False
    if os.path.exists(path):
        os.remove(path)
        cmds.inViewMessage(amg="Preset deleted", pos="midCenter", fade=True)
    return True