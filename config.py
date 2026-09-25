import os
import json
import socket
import uuid

# المنافذ المعتمدة لكافة خدمات التطبيق
DISCOVERY_PORT = 5000
FILE_PORT = 5001
SIGNALING_PORT = 5002
AUDIO_PORT = 5003
VIDEO_PORT = 5004
CHAT_PORT = 5005
SCREEN_PORT = 5006
CONTROL_PORT = 5007

# عنوان المالتيكاست الجماعي لتجاوز قيود الراوتر والجسور
MULTICAST_GROUP = '239.255.255.250'

# خادم السحابة للربط عبر الإنترنت
CLOUD_SIGNALING_HOST = "127.0.0.1"
CLOUD_SIGNALING_PORT = 5008

BUFFER_SIZE = 65536

def get_device_id():
    """جلب معرف فريد ومستمر للجهاز يعتمد على MAC Address لمنع تكرار الأجهزة نهائياً"""
    try:
        mac = uuid.getnode()
        host = socket.gethostname()
        return f"LATAL-{host}-{hex(mac)[2:]}"
    except Exception:
        return f"LATAL-DEV-{socket.gethostname()}"

def check_internet_connection(host="8.8.8.8", port=53, timeout=2):
    """فحص فوري للتحقق من وجود اتصال بالإنترنت"""
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def get_saved_username():
    """قراءة اسم المستخدم الثابت المعتمد من ملف profile_config.json أو اسم النظام"""
    if os.path.exists("profile_config.json"):
        try:
            with open("profile_config.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                name = data.get("user_name", "").strip()
                if name:
                    return name
        except Exception:
            pass
    return os.environ.get("USERNAME", "مستخدم LATAL")

def get_local_ip():
    """جلب عنوان IP المحلي الرئيسي الفعال للجهاز"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_all_network_interfaces():
    """جلب عناوين IP كروت الشبكة الحقيقية والفعالة فقط واستبعاد العناوين الوهمية والافتراضية"""
    ips = set()
    try:
        hostname = socket.gethostname()
        addresses = socket.gethostbyname_ex(hostname)[2]
        for ip in addresses:
            # فلترة واستبعاد عناوين VirtualBox, VMware, Docker, WSL, APIPA, Loopback
            if (ip.startswith("127.") or 
                ip.startswith("169.254.") or 
                ip.startswith("192.168.56.") or 
                ip.startswith("192.168.99.") or 
                ip.startswith("172.16.") or ip.startswith("172.17.") or 
                ip.startswith("172.18.") or ip.startswith("172.19.") or 
                ip.startswith("172.20.") or ip.startswith("172.21.") or 
                ip.startswith("172.22.") or ip.startswith("172.23.") or 
                ip.startswith("172.24.") or ip.startswith("172.25.") or 
                ip.startswith("172.26.") or ip.startswith("172.27.") or 
                ip.startswith("172.28.") or ip.startswith("172.29.") or 
                ip.startswith("172.30.") or ip.startswith("172.31.")):
                continue
            ips.add(ip)
    except Exception:
        pass

    main_ip = get_local_ip()
    if main_ip and not main_ip.startswith("127.") and not main_ip.startswith("169.254."):
        ips.add(main_ip)

    if not ips:
        ips.add("127.0.0.1")
    return list(ips)

def get_broadcast_addresses():
    """حساب عناوين البث الموجهة لجميع كروت الشبكة المتصلة"""
    broadcast_ips = {"255.255.255.255"}
    for ip in get_all_network_interfaces():
        try:
            parts = ip.split('.')
            if len(parts) == 4 and parts[0] != '127':
                broadcast_ips.add(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
                if parts[0] in ['192', '172', '10']:
                    broadcast_ips.add(f"{parts[0]}.{parts[1]}.255.255")
        except Exception:
            pass
    return list(broadcast_ips)