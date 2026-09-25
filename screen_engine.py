import socket
import threading
import cv2
import numpy as np
import json
from PIL import ImageGrab
from config import SCREEN_PORT, CONTROL_PORT, BUFFER_SIZE

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False

class RemoteHostEngine:
    """محرك بث الشاشة واستقبال أوامر التحكم من الطرف الآخر"""
    def __init__(self, port_screen=SCREEN_PORT, port_control=CONTROL_PORT):
        self.port_screen = port_screen
        self.port_control = port_control
        self.running = False
        self.sock_screen = None
        self.sock_control = None

    def start(self, viewer_ip):
        self.running = True
        threading.Thread(target=self._stream_screen, args=(viewer_ip,), daemon=True).start()
        if HAS_PYAUTOGUI:
            threading.Thread(target=self._listen_control, daemon=True).start()

    def _stream_screen(self, viewer_ip):
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self.running:
            try:
                img = ImageGrab.grab()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                resized = cv2.resize(frame, (1024, 576))
                _, encoded = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 55])
                data = encoded.tobytes()
                
                if len(data) < 65507:
                    self.sock_screen.sendto(data, (viewer_ip, self.port_screen))
            except Exception:
                pass
            cv2.waitKey(40)

    def _listen_control(self):
        if not HAS_PYAUTOGUI:
            return

        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_control.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock_control.bind(('', self.port_control))
        except Exception:
            return

        screen_w, screen_h = pyautogui.size()

        while self.running:
            try:
                data, _ = self.sock_control.recvfrom(BUFFER_SIZE)
                event = json.loads(data.decode('utf-8'))
                event_type = event.get('type')
                
                x = int(event.get('x', 0) * (screen_w / 1024))
                y = int(event.get('y', 0) * (screen_h / 576))

                if event_type == 'move':
                    pyautogui.moveTo(x, y)
                elif event_type == 'click':
                    button = event.get('button', 'left')
                    pyautogui.click(x, y, button=button)
                elif event_type == 'dblclick':
                    pyautogui.doubleClick(x, y)
                elif event_type == 'key':
                    key = event.get('key')
                    if key:
                        pyautogui.press(key)
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.sock_screen:
            try: self.sock_screen.close()
            except: pass
        if self.sock_control:
            try: self.sock_control.close()
            except: pass


class RemoteViewerEngine:
    """محرك استقبال شاشة الطرف الآخر وإرسال إشارات الفأرة ولوحة المفاتيح"""
    def __init__(self, host_ip, port_screen=SCREEN_PORT, port_control=CONTROL_PORT):
        self.host_ip = host_ip
        self.port_screen = port_screen
        self.port_control = port_control
        self.running = False
        self.sock_screen = None
        self.sock_control = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.window_name = f"LATAL Remote Control - {host_ip}"

    def start(self):
        self.running = True
        threading.Thread(target=self._receive_screen, daemon=True).start()

    def _send_control(self, event_data):
        try:
            data = json.dumps(event_data).encode('utf-8')
            self.sock_control.sendto(data, (self.host_ip, self.port_control))
        except Exception:
            pass

    def _on_mouse(self, event, x, y, flags, param):
        if not self.running:
            return
        if event == cv2.EVENT_MOUSEMOVE and (flags & cv2.EVENT_FLAG_LBUTTON):
            self._send_control({'type': 'move', 'x': x, 'y': y})
        elif event == cv2.EVENT_LBUTTONDOWN:
            self._send_control({'type': 'click', 'x': x, 'y': y, 'button': 'left'})
        elif event == cv2.EVENT_RBUTTONDOWN:
            self._send_control({'type': 'click', 'x': x, 'y': y, 'button': 'right'})
        elif event == cv2.EVENT_LBUTTONDBLCLK:
            self._send_control({'type': 'dblclick', 'x': x, 'y': y})

    def _receive_screen(self):
        self.sock_screen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_screen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock_screen.bind(('', self.port_screen))
        except Exception:
            pass

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1024, 576)
        cv2.setMouseCallback(self.window_name, self._on_mouse)

        while self.running:
            try:
                data, _ = self.sock_screen.recvfrom(65507)
                np_arr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow(self.window_name, frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    break
                elif key != 255:
                    key_char = chr(key) if 32 <= key <= 126 else None
                    if key_char:
                        self._send_control({'type': 'key', 'key': key_char})
            except Exception:
                break

        cv2.destroyWindow(self.window_name)

    def stop(self):
        self.running = False
        if self.sock_screen:
            try: self.sock_screen.close()
            except: pass
        if self.sock_control:
            try: self.sock_control.close()
            except: pass
        cv2.destroyAllWindows()