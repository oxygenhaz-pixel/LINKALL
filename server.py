import socket
import json

clients = {}

def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # استماع على المنفذ المخصص من السيرفر السحابي
    sock.bind(('0.0.0.0', 10000))
    print("Server running on port 10000...")

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            msg = json.loads(data.decode('utf-8'))
            dev_id = msg.get("device_id")

            # حفظ الـ IP العام والمنفذ الخاص بالجهاز
            clients[dev_id] = {
                "ip": addr[0],
                "port": addr[1],
                "username": msg.get("username", "Unknown")
            }

            # رد بقائمة كل الأجهزة المتصلة حالياً
            response = json.dumps({"type": "PEER_LIST", "peers": clients}).encode('utf-8')
            sock.sendto(response, addr)
        except Exception:
            pass

if __name__ == "__main__":
    start_server()