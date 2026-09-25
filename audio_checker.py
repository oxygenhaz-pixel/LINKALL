import time
import sys

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("❌ مكتبات sounddevice أو numpy غير مثبتة.")
    print("قم بتثبيتها عبر الأمر: pip install sounddevice numpy")
    sys.exit(1)


def list_audio_devices():
    """عرض كافة أجهزة الصوت المدعومة مع تحديد الأجهزة الافتراضية"""
    print("\n" + "=" * 60)
    print(" 🎙️  قائمة أجهزة الصوت المتاحة على جهازك  🔊")
    print("=" * 60)
    
    devices = sd.query_devices()
    default_in, default_out = sd.default.device

    print("\n--- 🎤 أجهزة الإدخال (الميكروفونات) ---")
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            is_default = " [الافتراضي 🔥]" if idx == default_in else ""
            print(f"[{idx}] {dev['name']}{is_default} (القنوات: {dev['max_input_channels']}, التردد: {int(dev['default_samplerate'])}Hz)")

    print("\n--- 🔊 أجهزة الإخراج (السماعات) ---")
    for idx, dev in enumerate(devices):
        if dev['max_output_channels'] > 0:
            is_default = " [الافتراضي 🔥]" if idx == default_out else ""
            print(f"[{idx}] {dev['name']}{is_default} (القنوات: {dev['max_output_channels']}, التردد: {int(dev['default_samplerate'])}Hz)")
    
    print("=" * 60)
    return default_in, default_out


def test_speaker(device_id=None, duration=3, sample_rate=44100):
    """إرسال نغمة جيبية (440Hz) لاختبار سماعة الإخراج"""
    if device_id is None:
        device_id = sd.default.device[1]

    dev_info = sd.query_devices(device_id)
    print(f"\n🔊 جاري اختبار السماعة: [{device_id}] {dev_info['name']}...")
    
    # توليد نغمة صوتية بـ 440 هرتز
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = 0.3 * np.sin(2 * np.pi * 440 * t)  # شدة الصوت 30%

    try:
        sd.play(tone.astype(np.float32), samplerate=sample_rate, device=device_id)
        sd.wait()
        print("✅ اكتمل اختبار السماعة! هل سمعت النغمة الصوتية؟")
    except Exception as e:
        print(f"❌ فشل تشغيل الصوت على هذه السماعة: {e}")


def test_microphone(device_id=None, duration=4, sample_rate=44100):
    """تسجيل الصوت من المايك وعرض مؤشر قوة التردد"""
    if device_id is None:
        device_id = sd.default.device[0]

    dev_info = sd.query_devices(device_id)
    print(f"\n🎤 جاري اختبار المايك: [{device_id}] {dev_info['name']}...")
    print("تحدث في المايك الآن لمراقبة مستوى التقاط الصوت...")

    def callback(indata, frames, time_info, status):
        volume_norm = np.linalg.norm(indata) * 10
        bars = "|" * int(volume_norm)
        print(f"\rمستوى الصوت: [{bars:<50}]", end="", flush=True)

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', device=device_id, callback=callback):
            sd.sleep(duration * 1000)
        print("\n✅ اكتمل اختبار المايك!")
    except Exception as e:
        print(f"\n❌ فشل التسجيل من هذا المايك: {e}")


def test_loopback(input_id=None, output_id=None, duration=4, sample_rate=44100):
    """تسجيل الصوت من المايك ثم إعادة تشغيله فوراً بالسماعة (Loopback Test)"""
    if input_id is None:
        input_id = sd.default.device[0]
    if output_id is None:
        output_id = sd.default.device[1]

    in_info = sd.query_devices(input_id)
    out_info = sd.query_devices(output_id)

    print(f"\n🔄 اختبار الإعادة المباشرة (Loopback Test):")
    print(f"  • المايك: [{input_id}] {in_info['name']}")
    print(f"  • السماعة: [{output_id}] {out_info['name']}")
    print(f"🎙️ تحدث الآن، سيتم التسجيل لمدة {duration} ثوانٍ...")

    try:
        recording = sd.rec(int(sample_rate * duration), samplerate=sample_rate, channels=1, dtype='int16', device=input_id)
        sd.wait()
        
        max_amplitude = np.max(np.abs(recording))
        print(f"📊 أعلى قوة صوت تم تسجيلها: {max_amplitude} / 32767")
        
        if max_amplitude < 500:
            print("⚠️ تحذير: مستوى الصوت الملتقط ضعيف جداً! تأكد من رفع حجم المايك في إعدادات ويندوز.")

        print("🔊 جاري إعادة تشغيل ما تم تسجيله عبر السماعة...")
        sd.play(recording, samplerate=sample_rate, device=output_id)
        sd.wait()
        print("✅ انتهى اختبار Loopback!")
    except Exception as e:
        print(f"❌ حدث خطأ أثناء اختبار Loopback: {e}")


def main():
    default_in, default_out = list_audio_devices()

    while True:
        print("\n--- اختر خياراً من القائمة ---")
        print("1. 🔊 اختبار السماعة الافتراضية (سماع نغمة)")
        print("2. 🎤 اختبار المايك الافتراضي (قياس حساسية الالتقاط)")
        print("3. 🔄 اختبار Loopback (تسجيل وإعادة تشغيل)")
        print("4. 🎯 اختيار أجهزة محددة بالرقم واختبارها")
        print("5. 📋 إعادة عرض قائمة الأجهزة")
        print("0. 🚪 خروج")
        
        choice = input("\nأدخل رقم الخيار: ").strip()

        if choice == '1':
            test_speaker(default_out)
        elif choice == '2':
            test_microphone(default_in)
        elif choice == '3':
            test_loopback(default_in, default_out)
        elif choice == '4':
            try:
                in_id = int(input("أدخل رقم جهاز المايك (Input ID): "))
                out_id = int(input("أدخل رقم جهاز السماعة (Output ID): "))
                test_loopback(in_id, out_id)
            except ValueError:
                print("❌ يرجى إدخال أرقام صحيحة من القائمة.")
        elif choice == '5':
            default_in, default_out = list_audio_devices()
        elif choice == '0':
            print("👋 تم الخروج.")
            break
        else:
            print("❌ خيار غير صحيح، حاول مرة أخرى.")

if __name__ == '__main__':
    main()