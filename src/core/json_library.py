import os
import json
from maya import cmds
from . import json_io

LIBRARY_DIR = os.path.join(cmds.internalVar(userAppDir=True), "reanimate_library")

def ensure_library_dir():
    """Ensure a global library directory exists."""
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
    return LIBRARY_DIR

def save_entry(entry_type, name, data):
    """
    Save a pose or animation entry to the global JSON library.

    Args:
        entry_type (str): "pose" or "animation"
        name (str): A user-friendly name for the entry
        data (dict): JSON data structure (pose or anim)
    """
    ensure_library_dir()
    safe_name = name.replace(" ", "_").lower()
    filename = f"{safe_name}_{entry_type}.json"
    path = os.path.join(LIBRARY_DIR, filename)

    with open(path, "w") as f:
        json.dump(data, f, indent=4)

    cmds.inViewMessage(amg=f"✅ Saved '{name}' {entry_type} to library!", pos="midCenter", fade=True)
    return path

def list_entries(entry_type=None):
    """
    List all available entries in the library.

    Args:
        entry_type (str): "pose", "animation", or None for all.
    """
    ensure_library_dir()
    entries = []
    for f in os.listdir(LIBRARY_DIR):
        if f.endswith(".json"):
            if entry_type and entry_type not in f:
                continue
            entries.append(f)
    return sorted(entries)

def load_entry(name):
    """
    Load a JSON entry by filename or partial name.
    """
    ensure_library_dir()
    for f in os.listdir(LIBRARY_DIR):
        if name.lower() in f.lower():
            path = os.path.join(LIBRARY_DIR, f)
            with open(path, "r") as file:
                return json.load(file)
    cmds.warning(f"⚠️ No entry named '{name}' found.")
    return None
