"""
run.py - Maya shelf entry point for ReAnimate Tool.
Handles module reloading and tool window launch.
"""

import sys
import importlib
from PySide6 import QtWidgets
import maya.OpenMayaUI as omui
import shiboken6

PROJECT_PATH = r"C:/Users/KaiJu/Documents/GitHub/ReAnimateTool/src"
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

_reanimate_tool_ui = None


def get_maya_main_window():
    """Return Maya's main window as a QWidget."""
    main_window_ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


def reload_reanimate_tool():
    """Reload all ReAnimate modules and relaunch the tool window."""
    global _reanimate_tool_ui

    if _reanimate_tool_ui is not None:
        try:
            _reanimate_tool_ui.close()
        except Exception:
            pass
        _reanimate_tool_ui = None

    for pkg in ["core", "ui"]:
        for name in list(sys.modules):
            if name.startswith(pkg):
                importlib.reload(sys.modules[name])

    import reanimate_tool
    importlib.reload(reanimate_tool)

    from reanimate_tool import show_reanimate_tool
    _reanimate_tool_ui = show_reanimate_tool()