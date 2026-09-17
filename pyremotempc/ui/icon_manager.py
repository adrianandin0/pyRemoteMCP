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

    icon_name = (getattr(node, "icon", "") or "").strip().lower()
    is_cont = getattr(node, "is_container", lambda: False)()
    proto = (getattr(node, "protocol", "") or "").upper()

    # 1. If explicit custom icon is set on node, resolve and return it
    if icon_name:
        if "connections" in icon_name:
            return get_icon("connections")
        if "folder" in icon_name:
            return get_icon("folder")
        if "linux" in icon_name:
            return get_icon("linux")
        if "windows" in icon_name:
            return get_icon("windows")
        if "terminal" in icon_name or "shell" in icon_name:
            return get_icon("terminal")
        if "vnc" in icon_name:
            return get_icon("vnc")
        if "connection" in icon_name:
            return get_icon("connections")
        if "router" in icon_name or "switch" in icon_name or "network" in icon_name:
            return get_icon("network")
        if "vm" in icon_name:
            return get_icon("vm")
        if "storage" in icon_name:
            return get_icon("storage")
        if "database" in icon_name:
            return get_icon("database")
        if "serial" in icon_name or "tty" in icon_name or "com" in icon_name:
            return get_icon("serial")
        if "server" in icon_name:
            return get_icon("server")

        ic = get_icon(icon_name)
        if not ic.isNull():
            return ic

    # 2. Defaults if icon_name is not specified
    if is_cont:
        if (getattr(node, "parent_id", None) is None) or (getattr(node, "name", "").lower() in ("connections", "conexiones")):
            return get_icon("connections")
        return get_icon("folder")

    if proto == "RDP":
        return get_icon("windows")
    elif proto in ("SSH2", "SSH1", "SSH"):
        return get_icon("terminal")
    elif proto == "VNC":
        return get_icon("vnc")
    elif proto in ("SFTP", "FTP", "SCP"):
        return get_icon("ftp")
    elif proto == "TELNET":
        return get_icon("connections")
    elif proto == "SERIAL":
        return get_icon("serial")

    return get_icon("server")
