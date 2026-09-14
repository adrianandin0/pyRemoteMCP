# pyRemoteMPC

**pyRemoteMPC** is a native multi-protocol remote connections manager for GNU/Linux (compatible with KDE Plasma, GNOME, XFCE, Cinnamon, MATE, and cross-platform desktop environments).

The project serves as a **modern, native Python replacement and spiritual successor to mRemoteNG for Linux environments**, built entirely with PySide6 (Qt6) and native connectivity engines.

---

## Key Features

- **Direct mRemoteNG Replacement**: Full import and export compatibility for mRemoteNG `confCons.xml` (v2.5) configuration files, preserving folder hierarchies, server settings, and encrypted credentials.
- **Modern & Fluid Qt6 UI**:
  - Dockable sidebar with horizontal slide toggle button.
  - Hierarchical connection tree with dedicated icons per OS / service (`windows`, `terminal`, `vnc`, `connections`, etc.).
  - Real-time search filter across names, hostnames/IPs, usernames, and descriptions.
  - Full Property Inspector (`PropertyGridWidget`) collapsible vertically with a dedicated toggle button.
  - Window Geometry & State Persistence: Automatically saves and restores exact position $(X, Y)$, window dimensions, active screen, and maximized/normal state upon closing and opening the app.
- **Quick Connect Toolbar**: Connect instantly or save entries directly specifying `IP/HOSTNAME` - `PROTOCOL` - `PORT` - `DOMAIN` - `USER` - `PASSWORD`.
- **Standardized Session Titles & Info Banners**:
  - Saved Connections: `PROTOCOL: SavedName (IP:Port)`
  - Quick Connections: `PROTOCOL: IP/Hostname (IP:Port)`
- **Security & Encryption**:
  - Master Password protection.
  - PBKDF2-HMAC-SHA256 key derivation with AES symmetric encryption for secure password storage.

---

## Supported Protocols

| Protocol | Internal Engine | Highlight Features |
| :--- | :--- | :--- |
| **RDP** | `xfreerdp` (FreeRDP 2/3) | Native tab embedding via X11 XEmbed container (works under Wayland via `xcb` backend). Dynamic resolution matching, credential redirection, and diagnostic log panel disabled by default. |
| **SSH2** | `paramiko` + `pyte` | Integrated VT100/xterm terminal emulator, infinite scrollback buffer, SSH private key support (RSA, ED25519, ECDSA, OpenSSH PEM, PuTTY `.ppk`), visual key selector dialog, and integrated **SFTP/FTP** file manager per session. |
| **SSH1 (Legacy)** | Legacy Crypto Engine | Dedicated engine specifically designed for legacy routers, switches, and ancient network hardware requiring obsolete ciphers (`3des-cbc`, `blowfish-cbc`, `diffie-hellman-group1-sha1`, `ssh-rsa`). |
| **VNC** | Native / Embedded Viewers | Remote desktop support via integration with `vinagre`, `remmina`, `vncviewer`, or `tigervnc`. |
| **Telnet** | `telnetlib` + `pyte` | Interactive terminal console for unencrypted network devices. |
| **SFTP / FTP** | `paramiko` / `ftplib` | Integrated file transfer tab per active session with upload, download, and local/remote filesystem browsing. |

---

## Architecture & Internal Details

For developers and users interested in cloning, auditing, or contributing to the repository:

### 1. Native X11/Wayland Integration for RDP
On modern Linux systems running Wayland, embedding external process windows like `xfreerdp` often creates unwanted floating windows. `pyRemoteMPC` resolves this by automatically setting the Qt platform backend to `xcb` (`os.environ["QT_QPA_PLATFORM"] = "xcb"`), ensuring valid X11 window handles (`winId()`) can be passed to `xfreerdp /parent:<winId>` for seamless tab embedding.

### 2. Project Directory Structure
```
pyRemoteMPC/
├── pyremotempc/
│   ├── app.py                    # Main Qt application entry point
│   ├── config/
│   │   ├── models.py             # Data models (ConnectionNode, etc.)
│   │   ├── settings.py           # JSON preferences manager (~/.config/pyremotempc/settings.json)
│   │   ├── i18n.py               # Internationalization & localization system (English / Spanish)
│   │   └── xml_parser.py         # mRemoteNG confCons.xml import/export parser
│   ├── crypto/
│   │   └── master_key_manager.py # AES encryption and PBKDF2 Master Password security
│   ├── engine/
│   │   ├── rdp_engine.py         # RDP session orchestrator using xfreerdp
│   │   ├── ssh_engine.py         # SSH2 engine with Paramiko and pyte terminal emulator
│   │   ├── ssh1_engine.py        # SSH1 engine for legacy hardware
│   │   ├── vnc_engine.py         # VNC session engine
│   │   ├── telnet_engine.py      # Telnet console engine
│   │   ├── sftp_engine.py        # SFTP/FTP file manager engine
│   │   └── file_transfer.py      # File transfer helpers
│   └── ui/
│       ├── main_window.py        # Main window, layouts, toolbars, and menus
│       ├── tree_widget.py        # Hierarchical connection tree
│       ├── property_grid.py      # Node property inspector
│       ├── tab_widget.py         # Active session tab manager
│       ├── terminal_widget.py    # Terminal console renderer
│       ├── sftp_widget.py        # Graphic file transfer interface
│       ├── icon_manager.py       # PNG icon loader per protocol and node type
│       └── iconos/               # Application icon assets (`pyremotempc.png`, etc.)
├── install.sh                    # Automated cross-distro installation script
├── uninstall.sh                  # Automated cross-distro uninstallation script
├── pyremotempc.desktop            # Linux desktop launcher entry
├── requirements.txt              # Python dependencies
└── setup.py                      # Package installation script
```

---

## Requirements & Installation

### System Requirements
- **Python**: 3.10 or higher.
- **Operating System**: GNU/Linux (KDE Plasma, GNOME, XFCE, Cinnamon, MATE, etc.).
- **System Dependencies**: `freerdp` (FreeRDP 2 or 3).

### Automated Installation
You can automatically detect your Linux distribution, install required system packages, Python dependencies, application binary wrapper, icons, and desktop entries by running:

```bash
chmod +x install.sh
sudo ./install.sh
```

### Manual Installation
```bash
# 1. Clone the repository
git clone https://github.com/your-username/pyRemoteMPC.git
cd pyRemoteMPC

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the application
python3 -m pyremotempc.app
```

---

## License
This project is licensed under the MIT License. See [LICENSE](file:///home/adrian/.gemini/antigravity/scratch/pyRemoteMPC/LICENSE) for details.
