# platform.py — detect Android vs desktop
import sys

def is_android() -> bool:
    try:
        import android  # noqa: F401 — only exists on python-for-android
        return True
    except ImportError:
        pass
    return sys.platform == "android"

IS_ANDROID = is_android()
