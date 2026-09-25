import threading
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