import os
import socket
import struct
import time
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtGui import QImage, QPainter, QPixmap, QMouseEvent, QKeyEvent, QWheelEvent, QColor, QFont
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QRect


def reverse_bits(b: int) -> int:
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


def vnc_encrypt_password(password: str, challenge: bytes) -> bytes:
    try:
        try:
            from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
        except ImportError:
            from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES
        from cryptography.hazmat.primitives.ciphers import Cipher, modes

        pass_bytes = password.encode('latin-1')[:8].ljust(8, b'\x00')
        key = bytes(reverse_bits(b) for b in pass_bytes)
        cipher = Cipher(TripleDES(key * 3), modes.ECB())
        encryptor = cipher.encryptor()
        return encryptor.update(challenge) + encryptor.finalize()
    except Exception:
        return challenge


def qt_key_to_keysym(key: int, text: str) -> int:
    mapping = {
        Qt.Key.Key_Return: 0xFF0D,
        Qt.Key.Key_Enter: 0xFF0D,
        Qt.Key.Key_Tab: 0xFF09,
        Qt.Key.Key_Backspace: 0xFF08,
        Qt.Key.Key_Escape: 0xFF1B,
        Qt.Key.Key_Delete: 0xFFFF,
        Qt.Key.Key_Home: 0xFF50,
        Qt.Key.Key_Left: 0xFF51,
        Qt.Key.Key_Up: 0xFF52,
        Qt.Key.Key_Right: 0xFF53,
        Qt.Key.Key_Down: 0xFF54,
        Qt.Key.Key_PageUp: 0xFF55,
        Qt.Key.Key_PageDown: 0xFF56,
        Qt.Key.Key_End: 0xFF57,
        Qt.Key.Key_Insert: 0xFF63,
        Qt.Key.Key_Shift: 0xFFE1,
        Qt.Key.Key_Control: 0xFFE3,
        Qt.Key.Key_Alt: 0xFFE9,
        Qt.Key.Key_Meta: 0xFFEB,
        Qt.Key.Key_Caps_Lock: 0xFFE5,
        Qt.Key.Key_F1: 0xFFBE,
        Qt.Key.Key_F2: 0xFFBF,
        Qt.Key.Key_F3: 0xFFC0,
        Qt.Key.Key_F4: 0xFFC1,
        Qt.Key.Key_F5: 0xFFC2,
        Qt.Key.Key_F6: 0xFFC3,
        Qt.Key.Key_F7: 0xFFC4,
        Qt.Key.Key_F8: 0xFFC5,
        Qt.Key.Key_F9: 0xFFC6,
        Qt.Key.Key_F10: 0xFFC7,
        Qt.Key.Key_F11: 0xFFC8,
        Qt.Key.Key_F12: 0xFFC9,
        Qt.Key.Key_Space: 0x0020,
    }
    if key in mapping:
        return mapping[key]
    if text and len(text) == 1:
        return ord(text[0])
    return key & 0xFFFF


class RFBThread(QThread):
    """Background thread handling RFB protocol handshake, socket I/O, and pixel rendering."""

    server_init = Signal(int, int, str)
    raw_rect_update = Signal(int, int, int, int, bytes)
    copy_rect_update = Signal(int, int, int, int, int, int)
    desktop_resize = Signal(int, int)
    status_changed = Signal(str)
    log_output = Signal(str)
    connection_failed = Signal(str)
    fallback_required = Signal(str)

    def __init__(self, hostname: str, port: int = 5900, password: str = "", parent=None):
        super().__init__(parent)
        self.hostname = hostname
        self.port = port
        self.password = password
        self.is_running = True
        self.sock: Optional[socket.socket] = None
        self.width = 0
        self.height = 0
        self.event_queue = []

    def run(self):
        try:
            self.log_output.emit(f"[VNC]: Connecting to {self.hostname}:{self.port}...\n")
            self.sock = socket.create_connection((self.hostname, self.port), timeout=6.0)
            self.sock.settimeout(6.0)

            # 1. Version Handshake
            ver_bytes = self._recv_exact(12)
            if not ver_bytes.startswith(b"RFB"):
                raise Exception("Invalid RFB protocol header from server.")
            self.log_output.emit(f"[VNC]: Server RFB Version: {ver_bytes.decode('utf-8', errors='ignore').strip()}\n")
            self.sock.sendall(b"RFB 003.008\n")

            # 2. Security Handshake
            n_types = self._recv_exact(1)[0]
            if n_types == 0:
                reason_len = struct.unpack(">I", self._recv_exact(4))[0]
                reason = self._recv_exact(reason_len).decode('utf-8', errors='ignore')
                raise Exception(f"VNC Auth Rejected: {reason}")

            sec_types = self._recv_exact(n_types)
            self.log_output.emit(f"[VNC]: Supported Security Types: {list(sec_types)}\n")

            if self.password and 2 in sec_types:
                # Type 2: Standard VNC Authentication (DES Challenge-Response)
                self.sock.sendall(b"\x02")
                challenge = self._recv_exact(16)
                response = vnc_encrypt_password(self.password, challenge)
                self.sock.sendall(response)
                sec_result = struct.unpack(">I", self._recv_exact(4))[0]
                if sec_result != 0:
                    raise Exception("VNC Authentication Failed (Incorrect password).")

            elif 2 in sec_types:
                # Type 2: Standard VNC Authentication (No password stored)
                self.sock.sendall(b"\x02")
                challenge = self._recv_exact(16)
                if not self.password:
                    raise Exception("VNC server requires a password, but none was provided.")
                response = vnc_encrypt_password(self.password, challenge)
                self.sock.sendall(response)
                sec_result = struct.unpack(">I", self._recv_exact(4))[0]
                if sec_result != 0:
                    raise Exception("VNC Authentication Failed (Incorrect password).")

            elif 1 in sec_types:
                # Type 1: None (no password required)
                self.sock.sendall(b"\x01")
                sec_result = struct.unpack(">I", self._recv_exact(4))[0]
                if sec_result != 0:
                    raise Exception("VNC Security authentication failed.")

            else:
                # Server only offers advanced security types (11 = UltraVNC MSLogon / VeNCrypt, 7, 5)
                sec_str = ", ".join(str(s) for s in sec_types)
                msg = f"VNC Security Type [{sec_str}] detected (UltraVNC MSLogon / VeNCrypt). Switching to System VNC Engine..."
                self.log_output.emit(f"[VNC]: {msg}\n")
                self.fallback_required.emit(msg)
                return

            # 3. ClientInit (Shared desktop)
            self.sock.sendall(b"\x01")

            # 4. ServerInit (Width, Height, Pixel Format, Name)
            srv_init = self._recv_exact(24)
            self.width, self.height = struct.unpack(">HH", srv_init[:4])
            name_len = struct.unpack(">I", srv_init[20:24])[0]
            name_bytes = self._recv_exact(name_len)
            desktop_name = name_bytes.decode('utf-8', errors='ignore')
            self.log_output.emit(f"[VNC]: Connected! Desktop: '{desktop_name}' ({self.width}x{self.height})\n")
            self.server_init.emit(self.width, self.height, desktop_name)

            # 5. SetPixelFormat (Request 32 bpp BGRX/RGB32 format)
            # type=0, pad(3), bpp=32, depth=24, big_endian=0, true_color=1, red_max=255, green_max=255, blue_max=255, red_shift=16, green_shift=8, blue_shift=0, pad(3)
            set_fmt = struct.pack(">B3sBBBBHHHBBB3s", 0, b"\x00\x00\x00", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0, b"\x00\x00\x00")
            self.sock.sendall(set_fmt)

            # 6. SetEncodings (Raw=0, CopyRect=1, DesktopSize=-223)
            set_enc = struct.pack(">BBHiii", 2, 0, 3, 0, 1, -223)
            self.sock.sendall(set_enc)

            self.sock.settimeout(0.1)

            # Initial full FramebufferUpdateRequest
            req = struct.pack(">BBHHHH", 3, 0, 0, 0, self.width, self.height)
            self.sock.sendall(req)

            # Main RFB Read Loop
            while self.is_running:
                # Process outgoing events
                while self.event_queue:
                    evt = self.event_queue.pop(0)
                    try:
                        self.sock.sendall(evt)
                    except Exception:
                        pass

                # Request incremental update
                try:
                    req_inc = struct.pack(">BBHHHH", 3, 1, 0, 0, self.width, self.height)
                    self.sock.sendall(req_inc)
                except Exception:
                    pass

                # Read server message
                try:
                    msg_type_bytes = self.sock.recv(1)
                    if not msg_type_bytes:
                        time.sleep(0.02)
                        continue
                    msg_type = msg_type_bytes[0]

                    if msg_type == 0:
                        # FramebufferUpdate
                        pad_and_nrects = self._recv_exact(3)
                        n_rects = struct.unpack(">H", pad_and_nrects[1:3])[0]

                        for _ in range(n_rects):
                            rect_hdr = self._recv_exact(12)
                            rx, ry, rw, rh, encoding = struct.unpack(">HHHHi", rect_hdr)

                            if encoding == 0:
                                # Raw Encoding (rw * rh * 4 bytes)
                                pixel_data = self._recv_exact(rw * rh * 4)
                                self.raw_rect_update.emit(rx, ry, rw, rh, pixel_data)

                            elif encoding == 1:
                                # CopyRect Encoding
                                src_hdr = self._recv_exact(4)
                                src_x, src_y = struct.unpack(">HH", src_hdr)
                                self.copy_rect_update.emit(rx, ry, rw, rh, src_x, src_y)

                            elif encoding == -223:
                                # DesktopSize pseudo-encoding
                                self.width = rw
                                self.height = rh
                                self.desktop_resize.emit(rw, rh)
                    elif msg_type == 2:
                        # Bell
                        pass
                    elif msg_type == 3:
                        # ServerCutText
                        hdr = self._recv_exact(7)
                        txt_len = struct.unpack(">I", hdr[3:7])[0]
                        if txt_len > 0:
                            self._recv_exact(txt_len)

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        self.log_output.emit(f"[VNC Read Warning]: {str(e)}\n")
                    time.sleep(0.05)

        except Exception as e:
            if self.is_running:
                err_msg = str(e)
                self.log_output.emit(f"[VNC Error]: {err_msg}\n")
                self.connection_failed.emit(err_msg)
        finally:
            self.stop()

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n and self.is_running:
            try:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    raise Exception("VNC Socket closed by remote server.")
                buf.extend(chunk)
            except socket.timeout:
                continue
        return bytes(buf)

    def queue_pointer_event(self, button_mask: int, x: int, y: int):
        evt = struct.pack(">BBHH", 5, button_mask, x, y)
        self.event_queue.append(evt)

    def queue_key_event(self, down_flag: int, keysym: int):
        evt = struct.pack(">BBHI", 4, down_flag, 0, keysym)
        self.event_queue.append(evt)

    def stop(self):
        self.is_running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class VNCWidget(QWidget):
    """
    Native PySide6 Canvas Widget for VNC Remote Desktop.
    Renders VNC RFB framebuffer directly onto PySide6 canvas with smooth scaling and mouse/keyboard events.
    """

    log_emitted = Signal(str)
    fallback_required = Signal(str)

    def __init__(self, hostname: str, port: int = 5900, password: str = "", parent=None):
        super().__init__(parent)
        self.hostname = hostname
        self.port = port if port else 5900
        self.password = password

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.rfb_thread: Optional[RFBThread] = None
        self.fb_image: Optional[QImage] = None
        self.desktop_w = 1280
        self.desktop_h = 800
        self.status_msg = f"Connecting VNC to {self.hostname}:{self.port}..."
        self.is_connected = False
        self.error_msg = ""
        self.mouse_button_mask = 0

    def start_session(self):
        """Starts background RFB thread and connects to VNC server."""
        self.stop_session()
        self.status_msg = f"Connecting VNC to {self.hostname}:{self.port}..."
        self.error_msg = ""
        self.is_connected = False
        self.update()

        self.rfb_thread = RFBThread(self.hostname, self.port, self.password, parent=self)
        self.rfb_thread.server_init.connect(self._on_server_init)
        self.rfb_thread.raw_rect_update.connect(self._on_raw_rect)
        self.rfb_thread.copy_rect_update.connect(self._on_copy_rect)
        self.rfb_thread.desktop_resize.connect(self._on_desktop_resize)
        self.rfb_thread.log_output.connect(self.log_emitted.emit)
        self.rfb_thread.connection_failed.connect(self._on_connection_failed)
        self.rfb_thread.fallback_required.connect(self.fallback_required.emit)
        self.rfb_thread.start()

    def stop_session(self):
        """Stops VNC RFB session thread safely, waiting for C++ thread to terminate."""
        if self.rfb_thread:
            thread = self.rfb_thread
            self.rfb_thread = None
            try:
                thread.server_init.disconnect()
                thread.raw_rect_update.disconnect()
                thread.copy_rect_update.disconnect()
                thread.desktop_resize.disconnect()
                thread.log_output.disconnect()
                thread.connection_failed.disconnect()
                thread.fallback_required.disconnect()
            except Exception:
                pass

            thread.stop()
            if thread.isRunning():
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait(500)

        self.is_connected = False
        self.update()

    def closeEvent(self, event):
        self.stop_session()
        super().closeEvent(event)

    def __del__(self):
        try:
            self.stop_session()
        except Exception:
            pass

    def stop(self):
        """Alias for stop_session for interface consistency."""
        self.stop_session()

    def _on_server_init(self, width: int, height: int, name: str):
        self.desktop_w = width
        self.desktop_h = height
        self.fb_image = QImage(width, height, QImage.Format.Format_RGB32)
        self.fb_image.fill(QColor(30, 30, 30))
        self.is_connected = True
        self.status_msg = ""
        self.update()

    def _on_raw_rect(self, x: int, y: int, w: int, h: int, pixel_data: bytes):
        if not self.fb_image or self.fb_image.width() != self.desktop_w or self.fb_image.height() != self.desktop_h:
            self.fb_image = QImage(self.desktop_w, self.desktop_h, QImage.Format.Format_RGB32)

        # Create temporary QImage over pixel_data and paint into fb_image
        rect_img = QImage(pixel_data, w, h, w * 4, QImage.Format.Format_RGB32)
        painter = QPainter(self.fb_image)
        painter.drawImage(x, y, rect_img)
        painter.end()
        self.update(self._map_remote_rect_to_local(x, y, w, h))

    def _on_copy_rect(self, x: int, y: int, w: int, h: int, src_x: int, src_y: int):
        if not self.fb_image:
            return
        src_rect = self.fb_image.copy(src_x, src_y, w, h)
        painter = QPainter(self.fb_image)
        painter.drawImage(x, y, src_rect)
        painter.end()
        self.update(self._map_remote_rect_to_local(x, y, w, h))

    def _on_desktop_resize(self, width: int, height: int):
        self.desktop_w = width
        self.desktop_h = height
        new_img = QImage(width, height, QImage.Format.Format_RGB32)
        new_img.fill(QColor(30, 30, 30))
        if self.fb_image:
            p = QPainter(new_img)
            p.drawImage(0, 0, self.fb_image)
            p.end()
        self.fb_image = new_img
        self.update()

    def _on_connection_failed(self, error: str):
        self.is_connected = False
        self.error_msg = error
        self.status_msg = f"VNC Connection Failed: {error}"
        self.update()

    def _get_target_rect(self) -> QRect:
        """Calculates centered target rectangle preserving aspect ratio."""
        if not self.desktop_w or not self.desktop_h:
            return self.rect()
        w = self.width()
        h = self.height()
        aspect = self.desktop_w / self.desktop_h
        target_w = w
        target_h = int(w / aspect)

        if target_h > h:
            target_h = h
            target_w = int(h * aspect)

        tx = (w - target_w) // 2
        ty = (h - target_h) // 2
        return QRect(tx, ty, target_w, target_h)

    def _map_local_to_remote(self, local_pos: QPoint) -> Optional[tuple]:
        """Translates Qt widget local coordinates to remote VNC framebuffer (rx, ry)."""
        rect = self._get_target_rect()
        if not rect.contains(local_pos):
            return None
        rel_x = (local_pos.x() - rect.x()) / rect.width()
        rel_y = (local_pos.y() - rect.y()) / rect.height()
        rx = int(rel_x * self.desktop_w)
        ry = int(rel_y * self.desktop_h)
        return max(0, min(rx, self.desktop_w - 1)), max(0, min(ry, self.desktop_h - 1))

    def _map_remote_rect_to_local(self, rx: int, ry: int, rw: int, rh: int) -> QRect:
        target = self._get_target_rect()
        scale_x = target.width() / self.desktop_w
        scale_y = target.height() / self.desktop_h
        lx = target.x() + int(rx * scale_x)
        ly = target.y() + int(ry * scale_y)
        lw = int(rw * scale_x) + 2
        lh = int(rh * scale_y) + 2
        return QRect(lx, ly, lw, lh)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self.is_connected and self.fb_image:
            target_rect = self._get_target_rect()
            painter.drawImage(target_rect, self.fb_image)
        else:
            # Draw sleek status overlay
            painter.setPen(QColor(180, 180, 180))
            painter.setFont(QFont("Sans-Serif", 11))

            text = self.status_msg or f"Connecting to {self.hostname}:{self.port}..."
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    # --- Mouse Events ---
    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        remote_coords = self._map_local_to_remote(event.position().toPoint())
        if remote_coords:
            rx, ry = remote_coords
            self.rfb_thread.queue_pointer_event(self.mouse_button_mask, rx, ry)

    def mousePressEvent(self, event: QMouseEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_button_mask |= 1
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.mouse_button_mask |= 2
        elif event.button() == Qt.MouseButton.RightButton:
            self.mouse_button_mask |= 4

        remote_coords = self._map_local_to_remote(event.position().toPoint())
        if remote_coords:
            rx, ry = remote_coords
            self.rfb_thread.queue_pointer_event(self.mouse_button_mask, rx, ry)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_button_mask &= ~1
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.mouse_button_mask &= ~2
        elif event.button() == Qt.MouseButton.RightButton:
            self.mouse_button_mask &= ~4

        remote_coords = self._map_local_to_remote(event.position().toPoint())
        if remote_coords:
            rx, ry = remote_coords
            self.rfb_thread.queue_pointer_event(self.mouse_button_mask, rx, ry)

    def wheelEvent(self, event: QWheelEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        delta = event.angleDelta().y()
        mask = self.mouse_button_mask
        if delta > 0:
            mask |= 8  # Wheel Up
        else:
            mask |= 16  # Wheel Down

        remote_coords = self._map_local_to_remote(event.position().toPoint())
        if remote_coords:
            rx, ry = remote_coords
            self.rfb_thread.queue_pointer_event(mask, rx, ry)
            # Release wheel bit immediately
            self.rfb_thread.queue_pointer_event(self.mouse_button_mask, rx, ry)

    # --- Keyboard Events ---
    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        keysym = qt_key_to_keysym(event.key(), event.text())
        self.rfb_thread.queue_key_event(1, keysym)

    def keyReleaseEvent(self, event: QKeyEvent):
        if not self.is_connected or not self.rfb_thread:
            return
        keysym = qt_key_to_keysym(event.key(), event.text())
        self.rfb_thread.queue_key_event(0, keysym)
