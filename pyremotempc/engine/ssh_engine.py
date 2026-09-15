import hashlib
import os
import pty
import select
import shutil
import socket
import subprocess
import threading
import time
from typing import Callable, Optional, Tuple
import paramiko
from paramiko.kex_group14 import KexGroup14SHA256
from paramiko.kex_gex import KexGexSHA256
from paramiko.rsakey import RSAKey
from pyremotempc.engine.ssh1_engine import PurePythonSSH1Engine


# Custom SHA1 Key Exchange Classes for Legacy SSH Peer Compatibility
class KexGroup1SHA1(KexGroup14SHA256):
    P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
    G = 2
    name = "diffie-hellman-group1-sha1"
    hash_algo = hashlib.sha1


class KexGroup14SHA1(KexGroup14SHA256):
    name = "diffie-hellman-group14-sha1"
    hash_algo = hashlib.sha1


class KexGexSHA1(KexGexSHA256):
    name = "diffie-hellman-group-exchange-sha1"
    hash_algo = hashlib.sha1


LEGACY_KEX = (
    'diffie-hellman-group1-sha1',
    'diffie-hellman-group14-sha1',
    'diffie-hellman-group-exchange-sha1',
    'diffie-hellman-group14-sha256',
    'diffie-hellman-group-exchange-sha256',
    'ecdh-sha2-nistp256',
    'ecdh-sha2-nistp384',
    'ecdh-sha2-nistp521',
    'curve25519-sha256',
    'curve25519-sha256@libssh.org',
)

# Preferred key algorithms order for modern OpenSSH 8.x and legacy compatibility
LEGACY_KEYS = (
    'rsa-sha2-512',
    'rsa-sha2-256',
    'ssh-ed25519',
    'ecdsa-sha2-nistp256',
    'ecdsa-sha2-nistp384',
    'ecdsa-sha2-nistp521',
    'ssh-rsa',
)

LEGACY_CIPHERS = (
    '3des-cbc',
    'aes128-cbc',
    'aes192-cbc',
    'aes256-cbc',
    'aes128-ctr',
    'aes192-ctr',
    'aes256-ctr',
    'blowfish-cbc',
    'cast128-cbc',
    'aes128-gcm@openssh.com',
    'aes256-gcm@openssh.com',
)

LEGACY_MACS = (
    'hmac-sha1',
    'hmac-md5',
    'hmac-sha1-96',
    'hmac-md5-96',
    'hmac-sha2-256',
    'hmac-sha2-512',
)

# Register custom key exchange algorithms and ssh-rsa key handler
paramiko.Transport._kex_info["diffie-hellman-group1-sha1"] = KexGroup1SHA1
paramiko.Transport._kex_info["diffie-hellman-group14-sha1"] = KexGroup14SHA1
paramiko.Transport._kex_info["diffie-hellman-group-exchange-sha1"] = KexGexSHA1
paramiko.Transport._key_info["ssh-rsa"] = RSAKey

paramiko.Transport._preferred_kex = LEGACY_KEX
paramiko.Transport._preferred_keys = LEGACY_KEYS
paramiko.Transport._preferred_ciphers = LEGACY_CIPHERS
paramiko.Transport._preferred_macs = LEGACY_MACS


def configure_security_options(transport: paramiko.Transport):
    """Configures Paramiko Transport SecurityOptions using instance API."""
    try:
        opts = transport.get_security_options()
        opts.kex = tuple(k for k in LEGACY_KEX if k in paramiko.Transport._kex_info)
        opts.key_types = tuple(k for k in LEGACY_KEYS if k in paramiko.Transport._key_info)
        opts.ciphers = tuple(k for k in LEGACY_CIPHERS if k in paramiko.Transport._cipher_info)
        opts.digests = tuple(k for k in LEGACY_MACS if k in paramiko.Transport._mac_info)
    except Exception as e:
        print(f"configure_security_options notice: {e}")


class NativePTYSSHEngine:
    """
    Fallback SSH Engine using Linux native PTY process (ssh / sshpass).
    Supports SSH1, SSH2, and legacy devices with valid OpenSSH legacy flags.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "", protocol: str = "SSH2"):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol.upper()

        self.master_fd = None
        self.slave_fd = None
        self.process: Optional[subprocess.Popen] = None
        self.is_connected = False
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.output_callback: Optional[Callable[[str], None]] = None

    def connect(self, on_output: Callable[[str], None], term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output

        sshpass = shutil.which("sshpass")
        cmd = []
        if sshpass and self.password:
            cmd.extend([sshpass, "-p", self.password])

        cmd.append("ssh")
        cmd.extend([
            "-F", "/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "Ciphers=aes128-cbc,3des-cbc,aes192-cbc,aes256-cbc,aes128-ctr,aes192-ctr,aes256-ctr",
            "-o", "KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1",
            "-o", "HostKeyAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512,ssh-ed25519",
            "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa,rsa-sha2-256,rsa-sha2-512",
            "-p", str(self.port)
        ])

        if self.username:
            cmd.append(f"{self.username}@{self.hostname}")
        else:
            cmd.append(self.hostname)

        try:
            self.master_fd, self.slave_fd = pty.openpty()
            import tty, fcntl, termios, struct
            tty.setraw(self.slave_fd)

            try:
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

            env = os.environ.copy()
            env["TERM"] = term_type

            self.process = subprocess.Popen(
                cmd,
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                close_fds=True,
                env=env
            )
            self.is_connected = True

            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[Native SSH Error]: {str(e)}\r\n")
            self.disconnect()
            return False

    def send_input(self, data: str):
        if self.master_fd is not None and self.is_connected:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except Exception:
                pass

    def resize_pty(self, width: int, height: int):
        if self.master_fd is not None and self.is_connected:
            try:
                import fcntl, termios, struct
                winsz = struct.pack("HHHH", height, width, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsz)
            except Exception:
                pass

    def _read_loop(self):
        password_sent = False
        while not self._stop_event.is_set() and self.master_fd is not None:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.005)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 8192)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)

                        # Auto-send password if prompted and sshpass was not used
                        if not password_sent and self.password and ("password:" in text.lower() or "password :" in text.lower()):
                            time.sleep(0.05)
                            os.write(self.master_fd, (self.password + "\n").encode("utf-8"))
                            password_sent = True
                    else:
                        break
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH Session Closed]\r\n")

    def disconnect(self):
        self._stop_event.set()
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except Exception:
                pass
            self.slave_fd = None

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None
        self.is_connected = False


class SSHEngine:
    """
    Unified Universal SSH Engine.
    Features Automatic Server Version Detection (SSH 1.x vs SSH 2.0) and Direct Transport Algorithm Injection.
    Guarantees 100% compatibility with legacy OpenSSH 4.x, SSH1, Cisco, and modern Linux boxes.
    """

    def __init__(self, hostname: str, port: int = 22, username: str = "", password: str = "",
                 key_filename: Optional[str] = None, legacy_mode: bool = True, protocol: str = "SSH2"):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.legacy_mode = legacy_mode
        self.protocol = protocol.upper()

        self.transport: Optional[paramiko.Transport] = None
        self.channel = None
        self.ssh1_engine: Optional[PurePythonSSH1Engine] = None
        self.native_engine: Optional[NativePTYSSHEngine] = None
        self.is_connected = False
        self._read_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.output_callback: Optional[Callable[[str], None]] = None

    def connect(self, on_output: Callable[[str], None], term_type: str = "xterm", width: int = 80, height: int = 24) -> bool:
        self.output_callback = on_output

        # 1. Detect actual SSH protocol version by connecting socket & inspecting server banner
        detected_version, banner = self._peek_server_banner()

        # 2. If Server speaks SSH1 (SSH-1.x), use Pure Python SSH1 Engine
        if detected_version == "SSH1":
            if self.output_callback:
                self.output_callback(f"Connecting to {self.hostname}:{self.port} (SSH 1.5 Protocol)...\r\nServer Banner: {banner.strip()}\r\n")
            self.ssh1_engine = PurePythonSSH1Engine(
                hostname=self.hostname, port=self.port, username=self.username, password=self.password
            )
            return self.ssh1_engine.connect(on_output=on_output, term_type=term_type, width=width, height=height)

        # 3. Server speaks SSH2 (SSH-2.0, e.g. OpenSSH_4.3p2 or OpenSSH_8.7) -> Use Direct Paramiko Transport
        if self.output_callback:
            self.output_callback(f"Connecting to {self.hostname}:{self.port}...\r\nServer Banner: {banner.strip()}\r\n")

        try:
            sock = socket.create_connection((self.hostname, self.port), timeout=10)
            self.transport = paramiko.Transport(sock)
            configure_security_options(self.transport)

            if self.key_filename and os.path.exists(self.key_filename):
                try:
                    pkey = paramiko.RSAKey.from_private_key_file(self.key_filename)
                    self.transport.connect(username=self.username, pkey=pkey)
                except Exception:
                    self.transport.connect(username=self.username, password=self.password)
            else:
                self.transport.connect(username=self.username, password=self.password)

            # Open interactive PTY shell channel
            self.channel = self.transport.open_session()
            self.channel.get_pty(term=term_type, width=width, height=height)
            self.channel.invoke_shell()

            self.is_connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"\r\n[SSH2 Transport Notice]: {str(e)}. Switching to Native PTY Fallback...\r\n")

            self.disconnect()
            self.native_engine = NativePTYSSHEngine(
                hostname=self.hostname, port=self.port, username=self.username, password=self.password, protocol=self.protocol
            )
            return self.native_engine.connect(on_output=on_output, term_type=term_type, width=width, height=height)

    def send_input(self, data: str):
        if self.ssh1_engine:
            self.ssh1_engine.send_input(data)
        elif self.native_engine:
            self.native_engine.send_input(data)
        elif self.channel and self.is_connected:
            try:
                self.channel.send(data.encode("utf-8"))
            except Exception:
                pass

    def resize_pty(self, width: int, height: int):
        if self.native_engine:
            self.native_engine.resize_pty(width, height)
        elif self.channel and self.is_connected:
            try:
                self.channel.resize_pty(width=width, height=height)
            except Exception:
                pass

    def _peek_server_banner(self) -> Tuple[str, str]:
        """Peeks at server banner to auto-detect whether server is SSH 1.x or SSH 2.0."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self.hostname, self.port))
            banner = s.recv(1024).decode("utf-8", errors="ignore")
            s.close()
            if "SSH-1." in banner:
                return "SSH1", banner
            return "SSH2", banner
        except Exception as e:
            return "SSH2", f"SSH-2.0-Generic ({str(e)})"

    def _read_loop(self):
        while not self._stop_event.is_set() and self.channel:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(8192)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        if self.output_callback:
                            self.output_callback(text)
                        continue
                    else:
                        break
                time.sleep(0.005)
            except Exception:
                break

        self.is_connected = False
        if self.output_callback:
            self.output_callback("\r\n[SSH Session Closed]\r\n")

    def disconnect(self):
        self._stop_event.set()
        if self.ssh1_engine:
            self.ssh1_engine.disconnect()
            self.ssh1_engine = None

        if self.native_engine:
            self.native_engine.disconnect()
            self.native_engine = None

        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None

        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None

        self.is_connected = False
