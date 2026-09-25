import threading
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