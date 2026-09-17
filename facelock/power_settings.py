import ctypes
import re
import subprocess


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("Reserved1", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_uint32),
        ("BatteryFullLifeTime", ctypes.c_uint32),
    ]


def _on_ac_power() -> bool:
    status = _SYSTEM_POWER_STATUS()
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return status.ACLineStatus == 1
    return True  # assume AC if it can't be determined


def get_display_timeout_seconds():
    """Reads Windows' own "turn off display after" setting for the active
    power scheme and power source (AC/battery). Returns None if it can't be
    read, or if the user has it set to "Never" (0)."""
    try:
        output = subprocess.run(
            ["powercfg", "/query", "SCHEME_CURRENT", "SUB_VIDEO", "VIDEOIDLE"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
    except Exception:
        return None

    key = "Current AC Power Setting Index" if _on_ac_power() else "Current DC Power Setting Index"
    match = re.search(rf"{re.escape(key)}:\s*0x([0-9a-fA-F]+)", output)
    if not match:
        return None
    seconds = int(match.group(1), 16)
    return seconds if seconds > 0 else None
