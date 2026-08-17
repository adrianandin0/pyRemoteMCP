# PyRemoteNG

A modern, fast, and native Linux multi-protocol remote desktop manager designed for Wayland/X11. PyRemoteNG aims to be a spiritual successor and compatible client for mRemoteNG XML configurations, fully built in Python and PySide6.

## Features
- **Multi-Protocol Support:** RDP, SSH, SFTP, and VNC support (using native engines like FreeRDP, OpenSSH, and Pyte).
- **mRemoteNG Compatibility:** Import connections from `confCons.xml` (supports base connections and directory structures).
- **Native UI:** Clean Qt6 interface with dark mode and tabbed session management.
- **Wayland/X11 Native Integration:** Perfect embedding and auto-resizing via advanced X11 integration, built to handle older RDP servers securely and efficiently.

## Requirements
- Python 3.9+
- FreeRDP (xfreerdp)
- OpenSSH client (ssh, scp)

## Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python3 -m pyremoteng.app`
