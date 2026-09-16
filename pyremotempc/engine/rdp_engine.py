import os
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Callable, Tuple
from pyremotempc.engine.base_engine import BaseProtocolEngine


class RDPEngine(BaseProtocolEngine):
    """
    Universal RDP Engine using FreeRDP (xfreerdp / freerdp / rdesktop / remmina).
    Captures process output in real-time and provides clear diagnostic logging.
    Inherits from BaseProtocolEngine and enforces secure credential passing over stdin.
    """

    @staticmethod
    def get_rdp_client_info() -> Tuple[str, str]:
        """Finds available RDP client binary and type."""
        for binary in ["xfreerdp3", "xfreerdp", "freerdp", "wlfreerdp", "sdl-freerdp"]:
            path = shutil.which(binary)
            if path:
                return path, "freerdp"
        if shutil.which("rdesktop"):
            return shutil.which("rdesktop"), "rdesktop"
        if shutil.which("remmina"):
            return shutil.which("remmina"), "remmina"
        return "", "none"

    def __init__(self, hostname: str, port: int = 3389, username: str = "", password: str = "",
                 domain: str = "", rdp_security: str = "Auto", rdp_cert_ignore: bool = True,
                 rdp_cert_path: str = "", redirect_drives: bool = True,
                 redirect_clipboard: bool = True, redirect_sound: bool = True,
                 shared_folder: str = ""):
        super().__init__(hostname, port, username, password)
        self.domain = domain
        self.rdp_security = rdp_security
        self.rdp_cert_ignore = rdp_cert_ignore
        self.rdp_cert_path = rdp_cert_path
        self.redirect_drives = redirect_drives
        self.redirect_clipboard = redirect_clipboard
        self.redirect_sound = redirect_sound
        self.shared_folder = shared_folder

        self.process: Optional[subprocess.Popen] = None
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.width = 1280
        self.height = 720

    def build_cmd(self, win_id: Optional[int] = None, width: int = 1280, height: int = 720) -> List[str]:
        exe_path, client_type = self.get_rdp_client_info()
        if not exe_path:
            raise FileNotFoundError("No RDP client found. Please install xfreerdp, freerdp, or rdesktop.")

        if client_type == "freerdp":
            cmd = [exe_path, f"/v:{self.hostname}:{self.port}"]
            cmd.append("/client-hostname:pyRemoteMPC")
            if self.username:
                cmd.append(f"/u:{self.username}")
            if self.password:
                # Use secure /from-stdin:force to avoid exposing passwords in ps aux process table
                cmd.append("/from-stdin:force")
            if self.domain:
                cmd.append(f"/d:{self.domain}")

            if win_id is not None:
                # /parent-window is X11-only in FreeRDP
                cmd.append(f"/parent-window:{win_id}")
                cmd.append(f"/size:{width}x{height}")
            else:
                cmd.append(f"/size:{width}x{height}")
                cmd.append("/workarea")
                cmd.append("+dynamic-resolution")

            sec = self.rdp_security.lower()
            if sec in ("nla", "rdp", "tls"):
                cmd.append(f"/sec:{sec}")

            if self.redirect_clipboard:
                cmd.append("+clipboard")
            else:
                cmd.append("-clipboard")

            if self.redirect_sound:
                cmd.append("/sound")

            if self.redirect_drives:
                folder_to_share = self.shared_folder
                if not folder_to_share or not os.path.exists(folder_to_share):
                    folder_to_share = os.path.expanduser("~/RDP_Shared")
                try:
                    os.makedirs(folder_to_share, exist_ok=True)
                except Exception:
                    pass
                cmd.append(f"/drive:Shared,{folder_to_share}")

            if self.rdp_cert_path and os.path.exists(self.rdp_cert_path):
                cmd.append(f"/cert:file:{self.rdp_cert_path}")
            elif self.rdp_cert_ignore:
                cmd.append("/cert:ignore")

            # Lower TLS security level to allow connecting to older servers on modern OpenSSL
            cmd.append("/tls:seclevel:0")
            return cmd

        elif client_type == "rdesktop":
            cmd = [exe_path, f"{self.hostname}:{self.port}", "-g", f"{width}x{height}"]
            if self.username:
                cmd.extend(["-u", self.username])
            if self.password:
                cmd.extend(["-p", "-"])
            if self.domain:
                cmd.extend(["-d", self.domain])
            return cmd

        else:
            return [exe_path or "remmina", "-c", f"rdp://{self.hostname}:{self.port}"]

    def connect(self, on_output: Optional[Callable[[str], None]] = None,
                term_type: str = "xterm", width: int = 1280, height: int = 720,
                win_id: Optional[int] = None) -> bool:
        """BaseProtocolEngine interface implementation."""
        return self.start_session(on_output=on_output, win_id=win_id, width=width, height=height)

    def disconnect(self):
        """BaseProtocolEngine interface implementation."""
        self.stop_session()

    def send_input(self, data: str):
        """BaseProtocolEngine interface implementation."""
        pass

    def start_session(self, on_output: Optional[Callable[[str], None]] = None,
                      win_id: Optional[int] = None, width: int = 1280, height: int = 720) -> bool:
        """Launches RDP client process and streams stdout/stderr to callback."""
        self.output_callback = on_output
        self.width = width
        self.height = height
        try:
            cmd = self.build_cmd(win_id=win_id, width=width, height=height)
            if self.output_callback:
                safe_cmd = []
                for token in cmd:
                    if token.startswith("/p:"):
                        safe_cmd.append("/p:********")
                    else:
                        safe_cmd.append(token)
                self.output_callback(f"[RDP Command]: {' '.join(safe_cmd)}\nLaunching RDP session...\n")

            env = os.environ.copy()
            # Force xfreerdp to use X11 so XEmbed works
            if "WAYLAND_DISPLAY" in env:
                del env["WAYLAND_DISPLAY"]

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            # Securely send password over stdin pipe to FreeRDP (/from-stdin:force)
            if self.password and self.process and self.process.stdin:
                try:
                    self.process.stdin.write(f"{self.password}\n")
                    self.process.stdin.flush()
                except Exception:
                    pass

            self.is_connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"[RDP Launch Error]: {str(e)}\n")
            self.is_connected = False
            return False

    def _read_loop(self):
        if not self.process or not self.process.stdout:
            return

        while not self._stop_event.is_set() and self.process.poll() is None:
            line = self.process.stdout.readline()
            if line:
                if self.output_callback:
                    self.output_callback(line)
            else:
                time.sleep(0.05)

        ret = self.process.poll() if self.process else None
        if self.output_callback:
            self.output_callback(f"\n[RDP Process Exited with Return Code: {ret}]\n")

    def stop_session(self):
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None

    def stop(self):
        """Alias for stop_session for engine interface consistency."""
        self.stop_session()

