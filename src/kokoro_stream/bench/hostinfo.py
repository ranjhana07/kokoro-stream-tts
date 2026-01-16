from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
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
    }
