from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import time
from importlib import metadata


def cpu_model() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return " ".join(str(value).split())
        if system == "Linux":
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        if system == "Darwin":
            output = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=True
            )
            return output.stdout.strip()
    except (OSError, subprocess.SubprocessError, ImportError):
        pass
    return platform.processor() or "unknown"


def _system_times() -> tuple[int, int]:
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes

        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))

        def combine(value: wintypes.FILETIME) -> int:
            return (value.dwHighDateTime << 32) | value.dwLowDateTime

        total = combine(kernel) + combine(user)
        return combine(idle), total
    with open("/proc/stat", encoding="utf-8") as handle:
        fields = [int(value) for value in handle.readline().split()[1:]]
    return fields[3] + fields[4], sum(fields)


def cpu_utilization(interval: float = 1.0) -> float | None:
    try:
        idle_before, total_before = _system_times()
        time.sleep(interval)
        idle_after, total_after = _system_times()
    except (OSError, ImportError, AttributeError, ValueError):
        return None
    total = total_after - total_before
    if total <= 0:
        return None
    return round(100.0 * (1.0 - (idle_after - idle_before) / total), 1)


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def collect() -> dict[str, object]:
    return {
        "cpu": cpu_model(),
        "logical_cores": os.cpu_count(),
        "os": platform.platform(),
        "python": re.sub(r"\s+", " ", sys.version.split("(")[0]).strip(),
        "numpy": package_version("numpy"),
        "onnxruntime": package_version("onnxruntime"),
        "flask": package_version("flask"),
        "cpu_utilization_before_run_percent": cpu_utilization(),
    }


def raise_priority() -> bool:
    try:
        if platform.system() == "Windows":
            import ctypes

            handle = ctypes.windll.kernel32.GetCurrentProcess()
            return bool(ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000080))
        os.nice(-5)
        return True
    except (OSError, AttributeError, ImportError):
        return False
