import os

files = {
    "config.py": """import socket
import os
import json

DISCOVERY_PORT = 5000
FILE_PORT = 5001
SIGNALING_PORT = 5002
AUDIO_PORT = 5003
VIDEO_PORT = 5004
CHAT_PORT = 5005
SCREEN_PORT = 5006
CONTROL_PORT = 5007
BUFFER_SIZE = 4096

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_saved_username():
    if os.path.exists("profile_config.json"):
        try:
            with open("profile_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("user_name"):
                    return data["user_name"]
        except Exception:
            pass
    return os.getlogin() or "User_" + get_local_ip().split('.')[-1]
""",

    "db_manager.py": """import sqlite3
import threading

class DBManager:
    def __init__(self, db_name="latal_local.db"):
        self.db_name = db_name
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT,
                    sender TEXT,
                    message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    def save_message(self, room, sender, message):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (room, sender, message) VALUES (?, ?, ?)", (room, sender, message))
            conn.commit()
            conn.close()

    def get_messages(self, room="Broadcast", limit=50):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT sender, message, timestamp FROM messages WHERE room = ? ORDER BY id ASC LIMIT ?", (room, limit))
            rows = cursor.fetchall()
            conn.close()
            return rows
""",

    "audio_engine.py": """import threading
import socket
import sounddevice as sd
import numpy as np
from config import AUDIO_PORT, BUFFER_SIZE

class AudioEngine:
    def __init__(self, target_ip, port=AUDIO_PORT):
        self.target_ip = target_ip
        self.port = port
        self.running = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(('', self.port))
        except Exception:
            pass

    def start(self):
        self.running = True
        threading.Thread(target=self._receive_audio, daemon=True).start()
        threading.Thread(target=self._send_audio, daemon=True).start()

    def _send_audio(self):
        def callback(indata, frames, time, status):
            if self.running:
                try:
                    self.sock.sendto(indata.tobytes(), (self.target_ip, self.port))
                except Exception:
                    pass

        try:
            with sd.InputStream(channels=1, samplerate=16000, blocksize=1024, dtype=np.float32, callback=callback):
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Audio send error: {e}")

    def _receive_audio(self):
        def callback(outdata, frames, time, status):
            if self.running:
                try:
                    data, _ = self.sock.recvfrom(BUFFER_SIZE * 4)
                    if data:
                        audio_data = np.frombuffer(data, dtype=np.float32)
                        if len(audio_data) == len(outdata):
                            outdata[:] = audio_data.reshape(-1, 1)
                        else:
                            outdata.fill(0)
                    else:
                        outdata.fill(0)
                except Exception:
                    outdata.fill(0)

        try:
            with sd.OutputStream(channels=1, samplerate=16000, blocksize=1024, dtype=np.float32, callback=callback):
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Audio receive error: {e}")

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass
""",

    "call_engines.py": """import threading
import socket
import cv2
import numpy as np
from audio_engine import AudioEngine
from config import VIDEO_PORT

class VoiceCallEngine:
    def __init__(self, target_ip):
        self.audio = AudioEngine(target_ip)

    def start_call(self):
        self.audio.start()

    def stop_call(self):
        self.audio.stop()

class VideoCallEngine:
    def __init__(self, target_ip, port=VIDEO_PORT):
        self.target_ip = target_ip
        self.port = port
        self.running = False
        self.sock = None

    def start_call(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(('', self.port))
        except Exception:
            pass
        
        threading.Thread(target=self._send_video, daemon=True).start()
        threading.Thread(target=self._receive_video, daemon=True).start()

    def _send_video(self):
        cap = cv2.VideoCapture(0)
        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (320, 240))
            _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            data = encoded.tobytes()
            if len(data) < 65507:
                try:
                    self.sock.sendto(data, (self.target_ip, self.port))
                except Exception:
                    pass
            cv2.waitKey(30)
        cap.release()

    def _receive_video(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(65507)
                np_arr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow(f"LATAL Video Call - {self.target_ip}", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
            except Exception:
                break
        cv2.destroyAllWindows()

    def stop_call(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        cv2.destroyAllWindows()
""",

    "screen_engine.py": """import socket
import threading
import cv2
import numpy as np
import json
import pyautogui
from PIL import ImageGrab
from config import SCREEN_PORT, CONTROL_PORT, BUFFER_SIZE

pyautogui.FAILSAFE = False

class RemoteHostEngine:
    def __init__(self, port_screen=SCREEN_PORT, port_control=CONTROL_PORT):
        self.port_screen = port_screen
        self.port_control = port_control
        self.running = False
        self.sock_screen = None
        self.sock_control = None

    def start(self, viewer_ip):
        self.running = True
        threading.Thread(target=self._stream_screen, args=(viewer_ip,), daemon=True).start()
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
""",

    "avatar_widget.py": """import os
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFileDialog, QDialog)
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QPainterPath, QColor, QConicalGradient, QPen, QBrush

class AnimatedAvatarWidget(QWidget):
    def __init__(self, size=90, parent=None):
        super().__init__(parent)
        self.avatar_size = size
        self.setFixedSize(size + 20, size + 20)
        
        self.image_path = None
        self.pixmap = None
        
        self.angle = 0
        self.glow_alpha = 120
        self.alpha_step = 3
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_avatar_image(self, path):
        if path and os.path.exists(path):
            self.image_path = path
            self.pixmap = QPixmap(path)
            self.update()

    def update_animation(self):
        self.angle = (self.angle + 3) % 360
        self.glow_alpha += self.alpha_step
        if self.glow_alpha >= 245:
            self.glow_alpha = 245
            self.alpha_step = -3
        elif self.glow_alpha <= 60:
            self.glow_alpha = 60
            self.alpha_step = 3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = self.avatar_size / 2.0
        border_width = 4
        
        gradient = QConicalGradient(center, self.angle)
        gradient.setColorAt(0.00, QColor(255, 0, 128, self.glow_alpha))
        gradient.setColorAt(0.25, QColor(0, 220, 255, self.glow_alpha))
        gradient.setColorAt(0.50, QColor(0, 255, 136, self.glow_alpha))
        gradient.setColorAt(0.75, QColor(255, 180, 0, self.glow_alpha))
        gradient.setColorAt(1.00, QColor(255, 0, 128, self.glow_alpha))
        
        pen = QPen(QBrush(gradient), border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius + 2, radius + 2)
        
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        painter.setClipPath(path)
        
        if self.pixmap and not self.pixmap.isNull():
            scaled_pixmap = self.pixmap.scaled(
                int(self.avatar_size), int(self.avatar_size),
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = int(center.x() - scaled_pixmap.width() / 2)
            y = int(center.y() - scaled_pixmap.height() / 2)
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#1e293b"))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "صورة")

class ProfileSettingsDialog(QDialog):
    def __init__(self, on_profile_updated_callback=None, parent=None):
        super().__init__(parent)
        self.on_profile_updated = on_profile_updated_callback
        self.setWindowTitle("تخصيص الملف الشخصي")
        self.setFixedSize(360, 320)
        self.setStyleSheet("background-color: #0f172a; color: white; font-family: Segoe UI;")
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        self.avatar_widget = AnimatedAvatarWidget(size=100)
        layout.addWidget(self.avatar_widget, alignment=Qt.AlignCenter)
        
        self.btn_change_photo = QPushButton("📷 تغيير الصورة الشخصية")
        self.btn_change_photo.setStyleSheet('''
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #38bdf8;
                border-radius: 6px; padding: 5px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #38bdf8; color: #0f172a; }
        ''')
        self.btn_change_photo.clicked.connect(self.select_photo)
        layout.addWidget(self.btn_change_photo, alignment=Qt.AlignCenter)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("أدخل اسمك الشخصي لتظهر للآخرين...")
        self.name_input.setStyleSheet('''
            QLineEdit {
                background-color: #1e293b; border: 1px solid #475569;
                border-radius: 8px; padding: 8px; color: white; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #38bdf8; }
        ''')
        layout.addWidget(self.name_input)
        
        self.btn_save = QPushButton("حفظ التغيرات 💾")
        self.btn_save.setStyleSheet('''
            QPushButton {
                background-color: #0284c7; color: white; border-radius: 8px;
                padding: 8px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #0369a1; }
        ''')
        self.btn_save.clicked.connect(self.save_profile)
        layout.addWidget(self.btn_save)
        
        self.setLayout(layout)
        self.load_profile()

    def select_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة شخصية", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.avatar_widget.set_avatar_image(file_path)

    def load_profile(self):
        if os.path.exists("profile_config.json"):
            try:
                with open("profile_config.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.name_input.setText(data.get("user_name", ""))
                    photo_path = data.get("photo_path", "")
                    if photo_path and os.path.exists(photo_path):
                        self.avatar_widget.set_avatar_image(photo_path)
            except Exception:
                pass

    def save_profile(self):
        user_name = self.name_input.text().strip() or "مستخدم محلي"
        photo_path = self.avatar_widget.image_path or ""
        
        profile_data = {
            "user_name": user_name,
            "photo_path": photo_path
        }
        
        with open("profile_config.json", "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=4)
            
        if self.on_profile_updated:
            self.on_profile_updated(user_name, photo_path)
            
        self.accept()
""",

    "network_manager.py": """import socket
import threading
import os
import json
from config import DISCOVERY_PORT, FILE_PORT, SIGNALING_PORT, CHAT_PORT, BUFFER_SIZE, get_saved_username

class NetworkManager:
    def __init__(self, device_ip, on_device_discovered=None, on_file_received=None, on_message_received=None, on_call_request=None, on_call_response=None):
        self.device_ip = device_ip
        self.on_device_discovered = on_device_discovered
        self.on_file_received = on_file_received
        self.on_message_received = on_message_received
        self.on_call_request = on_call_request
        self.on_call_response = on_call_response
        
        self.discovered_devices = {}
        self.running = False
        self.udp_socket = None
        self.file_server_socket = None
        self.signaling_socket = None
        self.chat_server_socket = None

    def get_username(self):
        return get_saved_username()

    def start_services(self):
        self.running = True
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.bind(('', DISCOVERY_PORT))
            threading.Thread(target=self._listen_broadcast, daemon=True).start()
            threading.Thread(target=self._send_broadcast_beacon, daemon=True).start()
        except Exception as e:
            print(f"Error starting discovery: {e}")

        try:
            self.file_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.file_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.file_server_socket.bind(('', FILE_PORT))
            self.file_server_socket.listen(5)
            threading.Thread(target=self._listen_file_transfers, daemon=True).start()
        except Exception as e:
            print(f"Error starting file server: {e}")

        try:
            self.signaling_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.signaling_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.signaling_socket.bind(('', SIGNALING_PORT))
            self.signaling_socket.listen(5)
            threading.Thread(target=self._listen_signaling, daemon=True).start()
        except Exception as e:
            print(f"Error starting signaling: {e}")

        try:
            self.chat_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.chat_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.chat_server_socket.bind(('', CHAT_PORT))
            self.chat_server_socket.listen(5)
            threading.Thread(target=self._listen_chat, daemon=True).start()
        except Exception as e:
            print(f"Error starting chat server: {e}")

    def _listen_broadcast(self):
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(BUFFER_SIZE)
                message = json.loads(data.decode('utf-8'))
                if message.get('type') == 'LATAL_BEACON':
                    ip = addr[0]
                    username = message.get('username', 'Unknown')
                    if ip != self.device_ip:
                        self.discovered_devices[ip] = {'username': username, 'ip': ip}
                        if self.on_device_discovered:
                            self.on_device_discovered(self.discovered_devices)
            except Exception:
                pass

    def _send_broadcast_beacon(self):
        import time
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                beacon_data = json.dumps({
                    'type': 'LATAL_BEACON',
                    'username': self.get_username(),
                    'ip': self.device_ip
                }).encode('utf-8')
                broadcast_sock.sendto(beacon_data, ('255.255.255.255', DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(4)

    def _listen_file_transfers(self):
        while self.running:
            try:
                conn, addr = self.file_server_socket.accept()
                threading.Thread(target=self._handle_incoming_file, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_incoming_file(self, conn):
        try:
            header_len_bytes = conn.recv(4)
            if not header_len_bytes:
                return
            header_len = int.from_bytes(header_len_bytes, 'big')
            header_data = json.loads(conn.recv(header_len).decode('utf-8'))
            
            file_name = header_data['filename']
            file_size = header_data['size']
            
            downloads_dir = os.path.join(os.getcwd(), 'downloads')
            os.makedirs(downloads_dir, exist_ok=True)
            save_path = os.path.join(downloads_dir, file_name)

            received = 0
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk = conn.recv(min(BUFFER_SIZE, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            if self.on_file_received:
                self.on_file_received(file_name, save_path)
        except Exception as e:
            print(f"File receive error: {e}")
        finally:
            conn.close()

    def send_file(self, target_ip, file_path):
        def _transfer():
            try:
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((target_ip, FILE_PORT))
                
                header = json.dumps({'filename': file_name, 'size': file_size}).encode('utf-8')
                s.sendall(len(header).to_bytes(4, 'big') + header)
                
                with open(file_path, 'rb') as f:
                    while chunk := f.read(BUFFER_SIZE):
                        s.sendall(chunk)
                s.close()
            except Exception as e:
                print(f"File send error: {e}")

        threading.Thread(target=_transfer, daemon=True).start()

    def _listen_chat(self):
        while self.running:
            try:
                conn, addr = self.chat_server_socket.accept()
                threading.Thread(target=self._handle_chat_conn, args=(conn, addr[0]), daemon=True).start()
            except Exception:
                break

    def _handle_chat_conn(self, conn, sender_ip):
        try:
            data = conn.recv(BUFFER_SIZE).decode('utf-8')
            if data:
                message_data = json.loads(data)
                sender_name = message_data.get('username', sender_ip)
                text = message_data.get('message', '')
                if self.on_message_received:
                    self.on_message_received(sender_name, text)
        except Exception as e:
            print(f"Chat receive error: {e}")
        finally:
            conn.close()

    def send_chat_message(self, target_ip, message):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, CHAT_PORT))
            payload = json.dumps({'username': self.get_username(), 'message': message})
            s.sendall(payload.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"Chat send error: {e}")

    def broadcast_message_to_all(self, message):
        for ip in list(self.discovered_devices.keys()):
            self.send_chat_message(ip, message)

    def _listen_signaling(self):
        while self.running:
            try:
                conn, addr = self.signaling_socket.accept()
                threading.Thread(target=self._handle_signaling_conn, args=(conn, addr[0]), daemon=True).start()
            except Exception:
                break

    def _handle_signaling_conn(self, conn, sender_ip):
        try:
            data = conn.recv(1024).decode('utf-8')
            if data:
                message = json.loads(data)
                action = message.get('action')
                if action == 'CALL_REQUEST':
                    call_type = message.get('call_type', 'voice')
                    if self.on_call_request:
                        self.on_call_request(sender_ip, call_type)
                elif action == 'CALL_RESPONSE':
                    status = message.get('status')
                    call_type = message.get('call_type', 'voice')
                    if self.on_call_response:
                        self.on_call_response(sender_ip, status, call_type)
        except Exception as e:
            print(f"Signaling error: {e}")

    def send_call_request(self, target_ip, call_type='voice'):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, SIGNALING_PORT))
            payload = json.dumps({'action': 'CALL_REQUEST', 'call_type': call_type, 'username': self.get_username()})
            s.sendall(payload.encode('utf-8'))
            s.close()
            return True
        except Exception as e:
            print(f"Call request error: {e}")
            return False

    def send_call_response(self, target_ip, status, call_type='voice'):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, SIGNALING_PORT))
            payload = json.dumps({'action': 'CALL_RESPONSE', 'status': status, 'call_type': call_type})
            s.sendall(payload.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"Call response error: {e}")

    def stop(self):
        self.running = False
        for sock in [self.udp_socket, self.file_server_socket, self.signaling_socket, self.chat_server_socket]:
            if sock:
                try:
                    sock.close()
                except:
                    pass
""",

    "main.py": """import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QTextEdit, QLineEdit, 
                             QPushButton, QLabel, QFileDialog, QMessageBox)
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
from config import get_local_ip, get_saved_username
from db_manager import DBManager
from network_manager import NetworkManager
from call_engines import VoiceCallEngine, VideoCallEngine
from screen_engine import RemoteHostEngine, RemoteViewerEngine
from avatar_widget import AnimatedAvatarWidget, ProfileSettingsDialog

class LATALMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.local_ip = get_local_ip()
        
        self.db = DBManager()
        self.network_manager = NetworkManager(
            device_ip=self.local_ip,
            on_device_discovered=self.safe_update_devices_list,
            on_file_received=self.safe_handle_file_received,
            on_message_received=self.safe_handle_incoming_message,
            on_call_request=self.safe_handle_incoming_call,
            on_call_response=self.safe_handle_call_response
        )
        
        self.voice_engine = None
        self.video_engine = None
        self.remote_host_engine = None
        self.remote_viewer_engine = None
        
        self.init_ui()
        self.load_profile_header()
        self.load_chat_history()
        self.network_manager.start_services()

    def init_ui(self):
        self.setWindowTitle(f"LATAL - نظام التواصل والتحكم المحلي ({get_saved_username()} @ {self.local_ip})")
        self.resize(1150, 750)
        self.setLayoutDirection(Qt.RightToLeft)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
        profile_box = QHBoxLayout()
        self.my_avatar_widget = AnimatedAvatarWidget(size=60)
        profile_box.addWidget(self.my_avatar_widget)
        
        profile_info = QVBoxLayout()
        self.lbl_my_name = QLabel(f"<b>{get_saved_username()}</b>")
        self.lbl_my_ip = QLabel(f"<span style='color: #64748b; font-size: 11px;'>IP: {self.local_ip}</span>")
        
        self.btn_edit_profile = QPushButton("⚙️ تعديل الملف الشخصي")
        self.btn_edit_profile.setStyleSheet("padding: 4px 8px; font-size: 11px; background-color: #334155;")
        self.btn_edit_profile.clicked.connect(self.open_profile_dialog)
        
        profile_info.addWidget(self.lbl_my_name)
        profile_info.addWidget(self.lbl_my_ip)
        profile_info.addWidget(self.btn_edit_profile)
        profile_box.addLayout(profile_info)
        left_layout.addLayout(profile_box)

        left_layout.addWidget(QLabel("<b>الأجهزة المكتشفة على الشبكة:</b>"))
        self.devices_list_widget = QListWidget()
        left_layout.addWidget(self.devices_list_widget)

        self.btn_send_file = QPushButton("📁 إرسال ملف")
        self.btn_send_file.clicked.connect(self.send_file_action)
        left_layout.addWidget(self.btn_send_file)

        self.btn_voice_call = QPushButton("📞 مكالمة صوتية")
        self.btn_voice_call.clicked.connect(lambda: self.start_call('voice'))
        left_layout.addWidget(self.btn_voice_call)

        self.btn_video_call = QPushButton("📹 مكالمة فيديو")
        self.btn_video_call.clicked.connect(lambda: self.start_call('video'))
        left_layout.addWidget(self.btn_video_call)

        self.btn_screen_share = QPushButton("🖥️ مشاركة الشاشة والتحكم")
        self.btn_screen_share.clicked.connect(lambda: self.start_call('screen'))
        left_layout.addWidget(self.btn_screen_share)

        main_layout.addLayout(left_layout, 1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        right_layout.addWidget(QLabel("<b>سجل المحادثة والبث العام:</b>"))
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("اكتب رسالة للبث لجميع الأجهزة على الشبكة...")
        self.msg_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.msg_input)

        self.btn_send_msg = QPushButton("إرسال رسالة")
        self.btn_send_msg.clicked.connect(self.send_message)
        input_layout.addWidget(self.btn_send_msg)

        right_layout.addLayout(input_layout)
        main_layout.addLayout(right_layout, 2)

        self.apply_stylesheet()

    def open_profile_dialog(self):
        dialog = ProfileSettingsDialog(on_profile_updated_callback=self.on_profile_updated, parent=self)
        dialog.exec_()

    def on_profile_updated(self, user_name, photo_path):
        self.lbl_my_name.setText(f"<b>{user_name}</b>")
        if photo_path and os.path.exists(photo_path):
            self.my_avatar_widget.set_avatar_image(photo_path)
        self.setWindowTitle(f"LATAL - نظام التواصل والتحكم المحلي ({user_name} @ {self.local_ip})")

    def load_profile_header(self):
        if os.path.exists("profile_config.json"):
            try:
                with open("profile_config.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    photo_path = data.get("photo_path", "")
                    if photo_path and os.path.exists(photo_path):
                        self.my_avatar_widget.set_avatar_image(photo_path)
            except Exception:
                pass

    def apply_stylesheet(self):
        stylesheet = '''
            QMainWindow { background-color: #f1f5f9; }
            QLabel { color: #1e293b; font-size: 13px; font-weight: bold; }
            QListWidget { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px; font-size: 13px; }
            QTextEdit { background-color: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px; font-size: 14px; }
            QLineEdit { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
            QPushButton { background-color: #0284c7; color: white; border: none; border-radius: 8px; padding: 9px 14px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #0369a1; }
            QPushButton:pressed { background-color: #075985; }
        '''
        self.setStyleSheet(stylesheet)

    def load_chat_history(self):
        messages = self.db.get_messages(room="Broadcast", limit=100)
        current_name = get_saved_username()
        for sender, msg, timestamp in messages:
            time_str = timestamp.split(" ")[-1][:5] if timestamp else ""
            if sender == current_name:
                bubble = f'''
                <div style="margin: 6px 0; text-align: right;">
                    <div style="background-color: #dbeafe; border: 1px solid #bfdbfe; padding: 8px 12px; border-radius: 12px; display: inline-block; max-width: 75%; text-align: right;">
                        <span style="color: #1e40af; font-weight: bold; font-size: 11px;">أنت ({sender})</span><br>
                        <span style="color: #1e293b; font-size: 13px;">{msg}</span><br>
                        <span style="color: #64748b; font-size: 9px; float: left; margin-top: 3px;">{time_str}</span>
                    </div>
                </div>
                '''
            else:
                bubble = f'''
                <div style="margin: 6px 0; text-align: left;">
                    <div style="background-color: #ffffff; border: 1px solid #cbd5e1; padding: 8px 12px; border-radius: 12px; display: inline-block; max-width: 75%; text-align: right;">
                        <span style="color: #0284c7; font-weight: bold; font-size: 11px;">{sender}</span><br>
                        <span style="color: #1e293b; font-size: 13px;">{msg}</span><br>
                        <span style="color: #64748b; font-size: 9px; float: left; margin-top: 3px;">{time_str}</span>
                    </div>
                </div>
                '''
            self.chat_display.append(bubble)

    def safe_update_devices_list(self, devices):
        QMetaObject.invokeMethod(self, "_update_devices_ui", Qt.QueuedConnection, Q_ARG(dict, devices))

    def _update_devices_ui(self, devices):
        self.devices_list_widget.clear()
        for ip, info in devices.items():
            self.devices_list_widget.addItem(f"{info['username']} ({ip})")

    def send_message(self):
        text = self.msg_input.text().strip()
        if text:
            time_str = datetime.now().strftime("%H:%M")
            my_name = get_saved_username()
            bubble = f'''
            <div style="margin: 6px 0; text-align: right;">
                <div style="background-color: #dbeafe; border: 1px solid #bfdbfe; padding: 8px 12px; border-radius: 12px; display: inline-block; max-width: 75%; text-align: right;">
                    <span style="color: #1e40af; font-weight: bold; font-size: 11px;">أنت ({my_name})</span><br>
                    <span style="color: #1e293b; font-size: 13px;">{text}</span><br>
                    <span style="color: #64748b; font-size: 9px; float: left; margin-top: 3px;">{time_str}</span>
                </div>
            </div>
            '''
            self.chat_display.append(bubble)
            self.db.save_message("Broadcast", my_name, text)
            self.network_manager.broadcast_message_to_all(text)
            self.msg_input.clear()

    def safe_handle_incoming_message(self, sender_name, message):
        QMetaObject.invokeMethod(self, "_append_incoming_msg", Qt.QueuedConnection, Q_ARG(str, sender_name), Q_ARG(str, message))

    def _append_incoming_msg(self, sender_name, message):
        time_str = datetime.now().strftime("%H:%M")
        bubble = f'''
        <div style="margin: 6px 0; text-align: left;">
            <div style="background-color: #ffffff; border: 1px solid #cbd5e1; padding: 8px 12px; border-radius: 12px; display: inline-block; max-width: 75%; text-align: right;">
                <span style="color: #0284c7; font-weight: bold; font-size: 11px;">{sender_name}</span><br>
                <span style="color: #1e293b; font-size: 13px;">{message}</span><br>
                <span style="color: #64748b; font-size: 9px; float: left; margin-top: 3px;">{time_str}</span>
            </div>
        </div>
        '''
        self.chat_display.append(bubble)
        self.db.save_message("Broadcast", sender_name, message)

    def send_file_action(self):
        selected_item = self.devices_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار جهاز من القائمة أولاً!")
            return
        
        target_ip = selected_item.text().split('(')[-1].strip(')')
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر ملف للإرسال")
        if file_path:
            self.network_manager.send_file(target_ip, file_path)
            QMessageBox.information(self, "نجاح", "تم بدء إرسال الملف بنجاح.")

    def safe_handle_file_received(self, filename, save_path):
        QMetaObject.invokeMethod(self, "_show_file_msg", Qt.QueuedConnection, Q_ARG(str, filename), Q_ARG(str, save_path))

    def _show_file_msg(self, filename, save_path):
        QMessageBox.information(self, "ملف مستلم", f"تم استقبال الملف: {filename}\\nمحفوظ في مجلد downloads/")

    def start_call(self, call_type):
        selected_item = self.devices_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "تحذير", f"اختر جهازا لبدء خدمة ({call_type}).")
            return
        target_ip = selected_item.text().split('(')[-1].strip(')')
        QMessageBox.information(self, "طلب اتصال", f"جارٍ إرسال طلب ({call_type})، في انتظار الموافقة...")
        self.network_manager.send_call_request(target_ip, call_type=call_type)

    def safe_handle_incoming_call(self, sender_ip, call_type):
        QMetaObject.invokeMethod(self, "_prompt_incoming_call", Qt.QueuedConnection, Q_ARG(str, sender_ip), Q_ARG(str, call_type))

    def _prompt_incoming_call(self, sender_ip, call_type):
        type_str = "صوتية" if call_type == 'voice' else "فيديو" if call_type == 'video' else "مشاركة الشاشة والتحكم"
        reply = QMessageBox.question(
            self, 
            "طلب وارد", 
            f"تلقيت طلب ({type_str}) من الجهاز: {sender_ip}\\nهل تريد القبول؟",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.network_manager.send_call_response(sender_ip, 'accepted', call_type=call_type)
            if call_type == 'voice':
                self.voice_engine = VoiceCallEngine(target_ip=sender_ip)
                self.voice_engine.start_call()
            elif call_type == 'video':
                self.video_engine = VideoCallEngine(target_ip=sender_ip)
                self.video_engine.start_call()
            elif call_type == 'screen':
                self.remote_host_engine = RemoteHostEngine()
                self.remote_host_engine.start(viewer_ip=sender_ip)
            QMessageBox.information(self, "اتصال نشط", f"تم بدء جلسة ({type_str}) بنجاح مع {sender_ip}.")
        else:
            self.network_manager.send_call_response(sender_ip, 'rejected', call_type=call_type)

    def safe_handle_call_response(self, sender_ip, status, call_type):
        if status == 'accepted':
            if call_type == 'screen':
                self.remote_viewer_engine = RemoteViewerEngine(host_ip=sender_ip)
                self.remote_viewer_engine.start()
            QMessageBox.information(self, "اتصال نشط", f"تم قبول الطلب من قِبل {sender_ip}.")
        else:
            QMessageBox.warning(self, "رفض الطلب", f"تم رفض الطلب من قِبل {sender_ip}.")

    def closeEvent(self, event):
        if self.voice_engine: self.voice_engine.stop_call()
        if self.video_engine: self.video_engine.stop_call()
        if self.remote_host_engine: self.remote_host_engine.stop()
        if self.remote_viewer_engine: self.remote_viewer_engine.stop()
        self.network_manager.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LATALMainWindow()
    window.show()
    sys.exit(app.exec_())
"""
}

for filename, content in files.items():
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"تم إنشاء وتحديث الملف بنجاح: {filename}")

print("\nاكتمل إنشاء وتحديث كافة الملفات بنجاح!")
print("لتشغيل البرنامج قم بتنفيذ الأمر: python main.py")