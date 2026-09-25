import sys
import ctypes
import subprocess

def add_firewall_rules():
    """إضافة قواعد جدار الحماية تلقائياً للبرنامج وللمنافذ"""
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            # إضافة استثناء لمترجم بايثون وللمنافذ المستهدفة
            cmd = f'netsh advfirewall firewall add rule name="LATAL_Auto_Allow" dir=in action=allow protocol=ANY program="{sys.executable}" enable=yes'
            subprocess.run(cmd, shell=True, capture_output=True)
        else:
            # إعادة تشغيل السكريبت بصلاحيات الأدمن
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    except Exception as e:
        print(f"Firewall setup error: {e}")

# استدعاء الدالة عند بداية التشغيل
if __name__ == "__main__":
    add_firewall_rules()
    # كود تشغيل الواجهة المعتاد...