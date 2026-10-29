"""Опциональный автозапуск Windows; без записи секретов и прав администратора."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_NAME = "TODOes"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def supported() -> bool:
    return sys.platform == "win32"


def command() -> str:
    if getattr(sys, "frozen", False):
        args = [sys.executable, "--tray"]
    else:
        python = Path(sys.executable)
        windowed = python.with_name("pythonw.exe")
        args = [str(windowed if windowed.exists() else python),
                str(Path(__file__).resolve().parent.parent / "main.py"), "--tray"]
    return subprocess.list2cmdline(args)


def enabled() -> bool:
    if not supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return value == command()
    except OSError:
        return False


def set_enabled(enable: bool) -> None:
    if not supported():
        raise OSError("Автозапуск поддерживается только в Windows")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
