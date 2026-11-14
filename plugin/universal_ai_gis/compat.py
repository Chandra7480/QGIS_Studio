"""Universal AI GIS Studio — PyQt6/QGIS 4.x Compatibility Layer.

Provides constants and aliases for cross-version compatibility.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QToolButton

# Qt alignment
ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter

# QMessageBox severity
MSG_INFO = 0
MSG_WARNING = 1
MSG_CRITICAL = 2

# QMessageBox standard buttons
MSGBOX_ACCEPT_ROLE = QMessageBox.ButtonRole.AcceptRole
MSGBOX_REJECT_ROLE = QMessageBox.ButtonRole.RejectRole
MSGBOX_QUESTION = QMessageBox.Icon.Question

# QPainter render hints
PAINTER_ANTIALIAS = True  # QPainter.RenderHint.Antialiasing

# QToolButton styles
TOOLBUTTON_ICON_ONLY = QToolButton.ToolButtonStyle.ToolButtonIconOnly
TOOLBUTTON_MENU_POPUP = QToolButton.ToolButtonPopupMode.MenuButtonPopup