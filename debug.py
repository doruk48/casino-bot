import subprocess
import sys

print("Python:", sys.version)
print()

# pip listesini al
result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
print("YÜKLÜ PAKETLER:")
print(result.stdout)

# pytgcalls kontrolü
try:
    import pytgcalls
    print(f"✅ pytgcalls: {pytgcalls.__version__}")
    from pytgcalls import types
    print(f"   types içindekiler: {[x for x in dir(types) if not x.startswith('_')]}")
except Exception as e:
    print(f"❌ pytgcalls: {e}")

# py-tgcalls kontrolü
try:
    import py_tgcalls
    print(f"✅ py-tgcalls: {py_tgcalls.__version__}")
except Exception as e:
    print(f"❌ py-tgcalls: {e}")

# FFmpeg kontrolü
result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
if result.returncode == 0:
    print(f"✅ FFmpeg: {result.stdout.split(chr(10))[0]}")
else:
    print("❌ FFmpeg: YOK")
