import os
from PySide6.QtGui import QIcon

ICON_DIR = os.path.join(os.path.dirname(__file__), "iconos")


def get_icon(name: str, fallback_theme: str = "") -> QIcon:
    """
    Returns QIcon from pyremotempc/ui/iconos/<name>.png if present,
    falling back to QIcon.fromTheme(fallback_theme) or empty QIcon.
    """
    path = os.path.join(ICON_DIR, f"{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    
    if not name.endswith(".png"):
        path_png = os.path.join(ICON_DIR, f"{name}.png")
        if os.path.exists(path_png):
            return QIcon(path_png)

    if fallback_theme:
        icon = QIcon.fromTheme(fallback_theme)
        if not icon.isNull():
            return icon

    return QIcon()


def get_node_icon(node) -> QIcon:
    """
    Returns the appropriate QIcon for a ConnectionNode based on node.icon or node.protocol.
    """
    if not node:
        return get_icon("server")

    icon_name = (getattr(node, "icon", "") or "").lower()
    is_cont = getattr(node, "is_container", lambda: False)()

    if is_cont or icon_name == "folder":
        return get_icon("folder")

    proto = (getattr(node, "protocol", "") or "").upper()

    # Protocol defaults if icon is empty or generic 'server'
    if not icon_name or icon_name == "server":
        if proto == "RDP":
            return get_icon("windows")
        elif proto in ("SSH2", "SSH1"):
            return get_icon("terminal")
        elif proto == "VNC":
            return get_icon("vnc")
        elif proto == "TELNET":
            return get_icon("connections")

    if icon_name:
        if "windows" in icon_name:
            return get_icon("windows")
        if "terminal" in icon_name or "shell" in icon_name:
            return get_icon("terminal")
        if "vnc" in icon_name:
            return get_icon("vnc")
        if "connection" in icon_name:
            return get_icon("connections")
        if "linux" in icon_name:
            return get_icon("linux")
        if "router" in icon_name or "switch" in icon_name or "network" in icon_name:
            return get_icon("network")
        if "vm" in icon_name:
            return get_icon("vm")
        if "storage" in icon_name:
            return get_icon("storage")
        if "database" in icon_name:
            return get_icon("database")

        ic = get_icon(icon_name)
        if not ic.isNull():
            return ic

    if proto == "RDP":
        return get_icon("windows")
    elif proto in ("SSH2", "SSH1"):
        return get_icon("terminal")
    elif proto == "VNC":
        return get_icon("vnc")
    elif proto == "TELNET":
        return get_icon("connections")

    return get_icon("server")
