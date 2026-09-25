import upnpclient

def auto_open_router_ports():
    try:
        # البحث عن أجهزة الراوتر التي تدعم UPnP
        devices = upnpclient.discover()
        if not devices:
            print("لم يتم العثور على راوتر يدعم UPnP")
            return

        for d in devices:
            # البحث عن خدمة التوجيه (WANIPConnection)
            for service in d.services:
                if 'WANIPConnection' in service.service_type or 'WANPPPConnection' in service.service_type:
                    for port in [50005, 50006, 50007, 50008, 50009]:
                        try:
                            service.AddPortMapping(
                                NewRemoteHost='',
                                NewExternalPort=port,
                                NewProtocol='UDP',
                                NewInternalPort=port,
                                NewInternalClient=upnpclient.ip,
                                NewEnabled='1',
                                NewPortMappingDescription='LATAL_Application',
                                NewLeaseDuration=0
                            )
                        except Exception:
                            pass
        print("تمت محاولة فتح منافذ الراوتر تلقائياً عبر UPnP!")
    except Exception as e:
        print(f"UPnP Error: {e}")
import socket
import threading
import json
import os
import time
from config import get_saved_username
from network_discovery import get_real_local_ip, get_or_create_device_id

DISCOVERY_PORT = 50005
CHAT_PORT = 50006
FILE_PORT = 50007
CALL_PORT = 50008
VOICE_PORT = 50009

try:
    import sounddevice as sd
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False


class NetworkManager:
    def __init__(self, device_ip=None, 
                 on_device_discovered=None, 
                 on_file_received=None, 
                 on_message_received=None, 
                 on_call_request=None, 
                 on_call_response=None, 
                 on_call_ended=None):
        
        self.device_ip = device_ip or get_real_local_ip()
        self.device_id = get_or_create_device_id()
        self.username = get_saved_username()

        self.on_device_discovered = on_device_discovered
        self.on_file_received = on_file_received
        self.on_message_received = on_message_received
        self.on_call_request = on_call_request
        self.on_call_response = on_call_response
        self.on_call_ended = on_call_ended

        self.discovered_devices = {}
        self.running = False
        
        self.audio_running = False
        self.is_muted = False
        self.audio_stream_in = None
        self.audio_stream_out = None

    def resolve_ip(self, target):
        if not target:
            return None
        
        if target in self.discovered_devices:
            return self.discovered_devices[target].get("ip", target)
            
        for dev_id, info in self.discovered_devices.items():
            if dev_id == target or info.get("username") == target:
                return info.get("ip", target)
                
        return target

    def start_services(self):
        self.running = True
        
        threading.Thread(target=self._discovery_broadcaster, daemon=True).start()
        threading.Thread(target=self._discovery_listener, daemon=True).start()
        threading.Thread(target=self._chat_listener, daemon=True).start()
        threading.Thread(target=self._file_listener, daemon=True).start()
        threading.Thread(target=self._call_listener, daemon=True).start()

    def stop(self):
        self.running = False
        self.stop_voice_call()

    def _discovery_broadcaster(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                self.username = get_saved_username()
                payload = json.dumps({
                    "type": "DISCOVERY",
                    "device_id": self.device_id,
                    "username": self.username,
                    "ip": self.device_ip
                }).encode('utf-8')

                # إرسال للبث العام ولعنوان Subnet المباشر لضمان الوصول
                sock.sendto(payload, ('255.255.255.255', DISCOVERY_PORT))
                
                # حساب broadcast ip بناءً على IP الجهاز (مثال: 192.168.1.255)
                if '.' in self.device_ip:
                    ip_parts = self.device_ip.split('.')
                    subnet_bc = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                    sock.sendto(payload, (subnet_bc, DISCOVERY_PORT))

            except Exception:
                pass
            time.sleep(2)

        sock.close()
    def _discovery_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            sock.bind(('', DISCOVERY_PORT))
        except Exception as e:
            print(f"Discovery bind error: {e}")
            return

        sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode('utf-8'))

                if msg.get("type") == "DISCOVERY":
                    dev_id = msg.get("device_id")
                    dev_ip = msg.get("ip", addr[0])
                    username = msg.get("username", "Unknown")

                    if dev_ip != self.device_ip and dev_id != self.device_id:
                        self.discovered_devices[dev_id] = {
                            "username": username,
                            "ip": dev_ip,
                            "last_seen": time.time()
                        }
                        if self.on_device_discovered:
                            self.on_device_discovered(self.discovered_devices)
            except socket.timeout:
                continue
            except Exception:
                pass

        sock.close()

    def add_manual_device(self, ip):
        dev_id = f"MANUAL_{ip}"
        self.discovered_devices[dev_id] = {
            "username": f"جهاز يدوي ({ip})",
            "ip": ip,
            "last_seen": time.time()
        }
        if self.on_device_discovered:
            self.on_device_discovered(self.discovered_devices)

    def send_chat_message(self, target, text, avatar_b64=""):
        target_ip = self.resolve_ip(target)
        if not target_ip:
            return

        try:
            payload = json.dumps({
                "type": "CHAT",
                "sender_name": self.username,
                "sender_ip": self.device_ip,
                "text": text,
                "avatar_b64": avatar_b64
            }).encode('utf-8')

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(payload, (target_ip, CHAT_PORT))
            sock.close()
        except Exception as e:
            print(f"Chat send error to {target_ip}: {e}")

    def broadcast_message_to_all(self, text, avatar_b64=""):
        for dev_id, info in list(self.discovered_devices.items()):
            self.send_chat_message(info["ip"], text, avatar_b64)

    def _chat_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', CHAT_PORT))
        except Exception as e:
            print(f"Chat bind error: {e}")
            return

        sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = sock.recvfrom(65535)
                msg = json.loads(data.decode('utf-8'))

                if msg.get("type") == "CHAT":
                    sender_name = msg.get("sender_name", "Unknown")
                    text = msg.get("text", "")
                    avatar_b64 = msg.get("avatar_b64", "")
                    sender_ip = msg.get("sender_ip", addr[0])

                    if self.on_message_received:
                        self.on_message_received(sender_name, text, avatar_b64, sender_ip)
            except socket.timeout:
                continue
            except Exception:
                pass

        sock.close()

    def send_file(self, target, file_path):
        target_ip = self.resolve_ip(target)
        if not target_ip or not os.path.exists(file_path):
            return

        def _send():
            try:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((target_ip, FILE_PORT))

                header = json.dumps({"file_name": file_name, "file_size": file_size}).encode('utf-8')
                sock.sendall(len(header).to_bytes(4, byteorder='big'))
                sock.sendall(header)

                with open(file_path, 'rb') as f:
                    while chunk := f.read(65536):
                        sock.sendall(chunk)

                sock.close()
            except Exception as e:
                print(f"File send error to {target_ip}: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def _file_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', FILE_PORT))
            sock.listen(5)
        except Exception as e:
            print(f"File bind error: {e}")
            return

        sock.settimeout(1.0)
        save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "LATAL_Received")
        os.makedirs(save_dir, exist_ok=True)

        while self.running:
            try:
                conn, addr = sock.accept()
                
                header_len = int.from_bytes(conn.recv(4), byteorder='big')
                header_data = conn.recv(header_len)
                header = json.loads(header_data.decode('utf-8'))

                file_name = header["file_name"]
                file_size = header["file_size"]
                save_path = os.path.join(save_dir, file_name)

                received = 0
                with open(save_path, 'wb') as f:
                    while received < file_size:
                        chunk = conn.recv(min(65536, file_size - received))
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)

                conn.close()

                if self.on_file_received:
                    self.on_file_received(file_name, save_path)
            except socket.timeout:
                continue
            except Exception:
                pass

        sock.close()

    def send_call_request(self, target, call_type="voice"):
        target_ip = self.resolve_ip(target)
        if not target_ip:
            return
        self._send_call_signal(target_ip, {"type": "CALL_REQUEST", "call_type": call_type})

    def send_call_response(self, target, status, call_type="voice"):
        target_ip = self.resolve_ip(target)
        if not target_ip:
            return
        self._send_call_signal(target_ip, {"type": "CALL_RESPONSE", "status": status, "call_type": call_type})

    def send_end_call(self, target):
        target_ip = self.resolve_ip(target)
        if not target_ip:
            return
        self._send_call_signal(target_ip, {"type": "CALL_END"})

    def _send_call_signal(self, target_ip, payload_dict):
        try:
            payload_dict["sender_ip"] = self.device_ip
            data = json.dumps(payload_dict).encode('utf-8')
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, (target_ip, CALL_PORT))
            sock.close()
        except Exception as e:
            print(f"Call signal error: {e}")

    def _call_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', CALL_PORT))
        except Exception as e:
            print(f"Call listener bind error: {e}")
            return

        sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode('utf-8'))
                msg_type = msg.get("type")
                sender_ip = msg.get("sender_ip", addr[0])

                if msg_type == "CALL_REQUEST" and self.on_call_request:
                    self.on_call_request(sender_ip, msg.get("call_type", "voice"))
                elif msg_type == "CALL_RESPONSE" and self.on_call_response:
                    self.on_call_response(sender_ip, msg.get("status"), msg.get("call_type", "voice"))
                elif msg_type == "CALL_END" and self.on_call_ended:
                    self.on_call_ended(sender_ip)
            except socket.timeout:
                continue
            except Exception:
                pass

        sock.close()

    def start_voice_call(self, target_ip):
        if not HAS_AUDIO:
            print("Sounddevice library not installed.")
            return

        target_ip = self.resolve_ip(target_ip)
        self.audio_running = True
        self.is_muted = False

        def _audio_sender():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sample_rate = 16000
            channels = 1
            chunk = 1024

            def callback(indata, frames, time_info, status):
                if self.audio_running and not self.is_muted:
                    try:
                        sock.sendto(indata.tobytes(), (target_ip, VOICE_PORT))
                    except Exception:
                        pass

            try:
                with sd.InputStream(samplerate=sample_rate, channels=channels, dtype='int16', blocksize=chunk, callback=callback):
                    while self.audio_running:
                        sd.sleep(100)
            except Exception as e:
                print(f"Audio input error: {e}")
            sock.close()

        def _audio_receiver():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('0.0.0.0', VOICE_PORT))
            except Exception:
                return

            sample_rate = 16000
            channels = 1

            try:
                with sd.OutputStream(samplerate=sample_rate, channels=channels, dtype='int16') as stream:
                    sock.settimeout(1.0)
                    while self.audio_running:
                        try:
                            data, _ = sock.recvfrom(4096)
                            if data:
                                stream.write(data)
                        except socket.timeout:
                            continue
                        except Exception:
                            pass
            except Exception as e:
                print(f"Audio output error: {e}")
            sock.close()

        threading.Thread(target=_audio_sender, daemon=True).start()
        threading.Thread(target=_audio_receiver, daemon=True).start()

    def toggle_mute_mic(self):
        self.is_muted = not self.is_muted
        return self.is_muted

    def stop_voice_call(self):
        self.audio_running = False