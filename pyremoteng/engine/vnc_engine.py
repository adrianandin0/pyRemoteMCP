import subprocess
import shutil
from typing import Optional, List


class VNCEngine:
    """VNC Engine for launching TigerVNC / TightVNC / RealVNC viewer."""

    @staticmethod
    def get_vnc_executable() -> Optional[str]:
        return shutil.which("vncviewer") or shutil.which("xvncviewer") or shutil.which("gtkvncviewer")

    def __init__(self, hostname: str, port: int = 5900, password: str = ""):
        self.hostname = hostname
        self.port = port
        self.password = password
        self.process: Optional[subprocess.Popen] = None

    def start_session(self, win_id: Optional[int] = None) -> subprocess.Popen:
        exe = self.get_vnc_executable() or "vncviewer"
        cmd: List[str] = [exe, f"{self.hostname}:{self.port}"]
        if win_id:
            cmd.extend(["-via", str(win_id)])

        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.process

    def stop_session(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None
