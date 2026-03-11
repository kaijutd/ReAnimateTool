"""
core/library.py - Global pose and animation library for ReAnimate Tool.
Stores and retrieves JSON entries from a persistent Maya user directory.
"""

import os
import json
from maya import cmds

LIBRARY_DIR = os.path.join(cmds.internalVar(userAppDir=True), "reanimate_library")


def _ensure_library_dir():
    """Create the library directory if it doesn't exist."""
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    return LIBRARY_DIR


def save_entry(entry_type, name, data):
    """
    Save a pose or animation entry to the library.

    Args:
        entry_type (str): "pose" or "animation".
        name (str): User-friendly name for the entry.
        data (dict): JSON-serializable pose or animation data.

    Returns:
        str: Path to the saved file.
    """
    _ensure_library_dir()
    filename = f"{name.replace(' ', '_').lower()}_{entry_type}.json"
    path = os.path.join(LIBRARY_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    cmds.inViewMessage(amg=f"Saved '{name}' {entry_type} to library", pos="midCenter", fade=True)
    return path


def list_entries(entry_type=None):
    """
    List all JSON entries in the library, optionally filtered by type.

    Args:
        entry_type (str): "pose", "animation", or None for all.

    Returns:
        list: Sorted list of matching filenames.
    """
    _ensure_library_dir()
    return sorted(
        f for f in os.listdir(LIBRARY_DIR)
        if f.endswith(".json") and (not entry_type or entry_type in f)
    )


def load_entry(name):
    """
    Load a library entry by filename or partial name match.

    Args:
        name (str): Full or partial filename to search for.

    Returns:
        dict or None: Parsed JSON data, or None if not found.
    """
    _ensure_library_dir()
    for f in os.listdir(LIBRARY_DIR):
        if name.lower() in f.lower():
            with open(os.path.join(LIBRARY_DIR, f), "r") as file:
                return json.load(file)
    cmds.warning(f"No library entry matching '{name}' found.")
    return None