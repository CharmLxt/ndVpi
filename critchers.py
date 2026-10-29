"""Critchers: Агрессивный сетевой бустер и очистка ресурсов (Без psutil)."""
import os
import sys
import json
import ctypes
import platform
import subprocess
import atexit
from pathlib import Path

BACKUP_FILE = Path.home() / ".ndvpi" / "critchers_backup.json"

def _is_windows(): return platform.system() == "Windows"
def _is_admin():
    if not _is_windows(): return False
    try: return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception: return False

def _run_quiet(cmd):
    try:
        subprocess.run(cmd, shell=True, capture_output=True)
        return True
    except Exception: return False

def _get_pids(process_name):
    try:
        cmd = f'tasklist /FI "IMAGENAME eq {process_name}" /FO CSV /NH'
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="cp866").stdout
        pids = []
        for line in out.splitlines():
            if process_name.lower() in line.lower():
                parts = line.split('","')
                if len(parts) > 1:
                    try: pids.append(int(parts[1]))
                    except ValueError: pass
        return pids
    except Exception: return []

def _suspend_process(pid):
    try:
        PROCESS_SUSPEND_RESUME = 0x0800
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ctypes.windll.ntdll.NtSuspendProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
    except Exception: pass
    return False

def _resume_process(pid):
    try:
        PROCESS_SUSPEND_RESUME = 0x0800
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if handle:
            ctypes.windll.ntdll.NtResumeProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
    except Exception: pass
    return False

class Critchers:
    def __init__(self):
        self.backup_data = {}
        self.suspended_pids = []
        atexit.register(self.resume_background_downloads)
        if BACKUP_FILE.exists():
            try: self.backup_data = json.loads(BACKUP_FILE.read_text("utf-8"))
            except Exception: pass

    def _save_backup(self):
        BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_FILE.write_text(json.dumps(self.backup_data, indent=2), "utf-8")

    def clean_standby_list(self):
        if not _is_windows() or not _is_admin(): return False, "Требуются права администратора Windows"
        try:
            ctypes.windll.ntdll.NtSetSystemInformation(-1073744922, ctypes.byref(ctypes.c_int(4)), 4)
            return True, "RAM Standby List очищен"
        except Exception as e: return False, f"Ошибка RAM: {e}"

    def flush_netbios(self):
        if not _is_windows(): return False, "Только для Windows"
        success = True
        success &= _run_quiet("nbtstat -R")
        success &= _run_quiet("nbtstat -RR")
        return True, "NetBIOS кэш очищен" if success else "Ошибка NetBIOS"

    def apply_tcp_tweaks(self, dry_run=False):
        if not _is_windows(): return False, "Только для Windows"
        import winreg
        tweaks = {
            r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters": {
                "NetworkThrottlingIndex": 0xffffffff,
                "TcpAckFrequency": 1,
                "TCPNoDelay": 1,
                "TcpDelAckTicks": 0,
                "TcpMaxDataRetransmissions": 2
            },
            r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces": {}
        }
        if dry_run: return True, "DRY-RUN: Применение агрессивных TCP твиков"
        if not _is_admin(): return False, "Требуются права администратора"
        
        for path, values in tweaks.items():
            if not values: continue
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
                for name, val in values.items():
                    try:
                        orig_val, _ = winreg.QueryValueEx(key, name)
                        self.backup_data[f"{path}\\{name}"] = orig_val
                    except FileNotFoundError:
                        self.backup_data[f"{path}\\{name}"] = None
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, val)
                winreg.CloseKey(key)
            except Exception as e: return False, f"Ошибка реестра: {e}"

        try:
            interfaces_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces", 0, winreg.KEY_READ)
            num_subkeys = winreg.QueryInfoKey(interfaces_key)[0]
            for i in range(num_subkeys):
                subkey_name = winreg.EnumKey(interfaces_key, i)
                sub_path = rf"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{subkey_name}"
                try:
                    sub_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_ALL_ACCESS)
                    try:
                        winreg.QueryValueEx(sub_key, "DhcpIPAddress")
                        for name, val in {"TcpAckFrequency": 1, "TCPNoDelay": 1}.items():
                            try:
                                orig_val, _ = winreg.QueryValueEx(sub_key, name)
                                self.backup_data[f"{sub_path}\\{name}"] = orig_val
                            except FileNotFoundError:
                                self.backup_data[f"{sub_path}\\{name}"] = None
                            winreg.SetValueEx(sub_key, name, 0, winreg.REG_DWORD, val)
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(sub_key)
                except Exception:
                    pass
            winreg.CloseKey(interfaces_key)
        except Exception:
            pass
                
        self._save_backup()
        return True, "Агрессивные TCP твики успешно применены"

    def disable_wifi_power_saving(self, dry_run=False):
        if not _is_windows(): return False, "Только для Windows"
        if dry_run: return True, "DRY-RUN: Отключение энергосбережения Wi-Fi"
        if not _is_admin(): return False, "Требуются права администратора"
        ps_cmd = 'Get-NetAdapter | Where-Object {$_.PhysicalMediaType -match "Native 802.11"} | Disable-NetAdapterPowerManagement -ErrorAction SilentlyContinue'
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            return True, "Энергосбережение Wi-Fi отключено"
        except Exception as e: return False, f"Ошибка: {e}"

    def pause_background_downloads(self):
        if not _is_windows() or not _is_admin(): return False, "Требуются права администратора"
        targets = ["OneDrive.exe", "wuauclt.exe", "SysMain.exe"]
        paused = []
        for proc_name in targets:
            for pid in _get_pids(proc_name):
                if _suspend_process(pid):
                    self.suspended_pids.append(pid)
                    paused.append(f"{proc_name} (PID: {pid})")
        if paused: return True, f"Приостановлены процессы: {', '.join(paused)}"
        return True, "Фоновые качалки не найдены"

    def resume_background_downloads(self):
        if not self.suspended_pids: return
        resumed = [str(pid) for pid in self.suspended_pids if _resume_process(pid)]
        self.suspended_pids = []
        if resumed: print(f"[Critchers] Возобновлены процессы: {', '.join(resumed)}")

    def restore(self):
        if not _is_windows() or not _is_admin(): return False, "Требуются права администратора"
        import winreg
        restored = 0
        for full_key, orig_val in self.backup_data.items():
            path, name = full_key.rsplit("\\", 1)
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
                if orig_val is None:
                    try: winreg.DeleteValue(key, name)
                    except FileNotFoundError: pass
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, orig_val)
                winreg.CloseKey(key)
                restored += 1
            except Exception: pass
        self.backup_data = {}
        if BACKUP_FILE.exists(): BACKUP_FILE.unlink()
        ps_cmd = 'Get-NetAdapter | Where-Object {$_.PhysicalMediaType -match "Native 802.11"} | Enable-NetAdapterPowerManagement -ErrorAction SilentlyContinue'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
        self.resume_background_downloads()
        return True, f"Восстановлено настроек: {restored}. Wi-Fi питание и процессы возвращены."