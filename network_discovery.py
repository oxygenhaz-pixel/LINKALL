import socket
import os
import json
import uuid

CONFIG_FILE = "profile_config.json"

# البادئات الخاصّة بكروت الشبكة الوهمية والمحلية المستبعدة
IGNORED_IP_PREFIXES = (
    "127.",          # Loopback
    "169.254.",      # APIPA
    "192.168.56.",   # VirtualBox Host-Only
    "192.168.99.",   # Docker / Minikube
    "172.28.",       # WSL / Hyper-V
    "172.29.",       
    "172.30.",
)

def get_real_local_ip():
    """استخراج عنوان IP الحقيقي الفعّال وتجاهل الشبكات الوهمية"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # محاولة اتصال افتراضية غير حية لتحديد المسار الفعلي للراوتر
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        
        if not any(ip.startswith(prefix) for prefix in IGNORED_IP_PREFIXES):
            return ip
    except Exception:
        pass

    # مسار احتياطي موثوق عبر فحص محولات الجهاز
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not any(ip.startswith(prefix) for prefix in IGNORED_IP_PREFIXES):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def get_or_create_device_id():
    """إنشاء أو قراءة المعرف الفريد للجهاز"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("device_id"):
                    return data["device_id"]
        except Exception:
            pass

    new_id = f"DEV_{socket.gethostname()}_{uuid.uuid4().hex[:6]}"
    return new_id