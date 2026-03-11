"""
ui/styles/common_style.py - Shared dark stylesheet for ReAnimate Tool.
"""

DARK_STYLE = """
QFrame {
    background-color: #2b2b2b;
    border: 1px solid #555;
    border-radius: 4px;
}

QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
}

QLineEdit {
    background-color: #3c3c3c;
    color: #e0e0e0;
    border: 1px solid #666;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
}
QLineEdit:focus {
    border: 1px solid #007acc;
}

QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #666;
    border-radius: 3px;
    color: #e0e0e0;
    padding: 2px 8px;
    font-size: 11px;
}
QPushButton:hover { background-color: #4c4c4c; }
QPushButton:pressed { background-color: #007acc; color: white; }

QTreeWidget, QListWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
    border: none;
    font-size: 11px;
}
QTreeWidget::item, QListWidget::item { padding: 4px 8px; }
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #007acc;
    color: white;
}
QTreeWidget::item:hover, QListWidget::item:hover { background-color: #404040; }

QCheckBox {
    color: #e0e0e0;
    spacing: 6px;
    font-size: 11px;
}
QCheckBox::indicator { width: 13px; height: 13px; }
QCheckBox::indicator:unchecked {
    border: 1px solid #666;
    background-color: #3c3c3c;
}
QCheckBox::indicator:checked {
    border: 1px solid #007acc;
    background-color: #007acc;
}

QLabel {
    color: #e0e0e0;
    font-size: 11px;
}
"""


def apply_style(widget, style):
    """Apply a named style to a widget. Currently supports 'DARK'."""
    if style == "DARK":
        widget.setStyleSheet(DARK_STYLE)