"""Изменение параметров сети: DNS, пароль Wi-Fi, адаптеры, MTU."""
import os
import subprocess
import platform
import re

def _decode_raw(raw: bytes) -> str:
    if not raw: return ""
    for enc in ("utf-8", "cp866", "cp1251"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: continue
    return raw.decode("utf-8", errors="replace")

def _run(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=True)
        return _decode_raw(result.stdout or b"")
    except Exception:
        return ""

def _is_windows(): return platform.system() == "Windows"
def _is_linux(): return platform.system() == "Linux"
def _is_macos(): return platform.system() == "Darwin"

def _is_admin():
    try:
        if _is_windows():
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False

class NetworkConfig:
    def get_dns(self, interface=None):
        if _is_windows():
            name = interface or self._default_windows_interface()
            if not name: return []
            out = _run(f'netsh interface ip show dns "{name}"')
            return re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", out)
        if _is_linux():
            try:
                with open("/etc/resolv.conf") as f:
                    return re.findall(r"nameserver\s+(\S+)", f.read())
            except FileNotFoundError:
                return []
        if _is_macos():
            name = interface or "Wi-Fi"
            out = _run(f"networksetup -getdnsservers {name}")
            if "aren't any" in out.lower(): return []
            return [l.strip() for l in out.splitlines() if l.strip()]
        return []

    def set_dns(self, servers, interface=None, dry_run=False):
        if not servers: return False, "Пустой список DNS"
        for s in servers:
            if not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", s):
                return False, f"Некорректный DNS: {s}"
        if _is_windows():
            name = interface or self._default_windows_interface()
            if not name: return False, "Не удалось определить интерфейс"
            cmds = [f'netsh interface ip set dns "{name}" static {servers[0]}']
            for i, s in enumerate(servers[1:], start=2):
                cmds.append(f'netsh interface ip add dns "{name}" {s} index={i}')
        elif _is_linux():
            conn = interface or self._default_linux_conn()
            if not conn: return False, "Не удалось определить соединение"
            dns_str = " ".join(servers)
            cmds = [f'nmcli con mod "{conn}" ipv4.dns "{dns_str}"', f'nmcli con mod "{conn}" ipv4.ignore-auto-dns yes', f'nmcli con up "{conn}"']
        elif _is_macos():
            name = interface or "Wi-Fi"
            dns_str = " ".join(servers)
            cmds = [f"networksetup -setdnsservers {name} {dns_str}"]
        else: return False, "Неподдерживаемая ОС"
        if dry_run: return True, "DRY-RUN:\n  " + "\n  ".join(cmds)
        if not _is_admin(): return False, "Требуются права администратора"
        for c in cmds: _run(c)
        return True, f"DNS установлен: {', '.join(servers)}"

    def reset_dns(self, interface=None, dry_run=False):
        if _is_windows():
            name = interface or self._default_windows_interface()
            if not name: return False, "Не удалось определить интерфейс"
            cmds = [f'netsh interface ip set dns "{name}" dhcp']
        elif _is_linux():
            conn = interface or self._default_linux_conn()
            if not conn: return False, "Не удалось определить соединение"
            cmds = [f'nmcli con mod "{conn}" ipv4.dns ""', f'nmcli con mod "{conn}" ipv4.ignore-auto-dns no', f'nmcli con up "{conn}"']
        elif _is_macos():
            name = interface or "Wi-Fi"
            cmds = [f"networksetup -setdnsservers {name} Empty"]
        else: return False, "Неподдерживаемая ОС"
        if dry_run: return True, "DRY-RUN:\n  " + "\n  ".join(cmds)
        if not _is_admin(): return False, "Требуются права администратора"
        for c in cmds: _run(c)
        return True, "DNS сброшен на автоматический"

    def change_wifi_password(self, ssid, new_password, dry_run=False):
        if not ssid or not new_password: return False, "Укажите SSID и пароль"
        if _is_windows():
            cmds = [f'netsh wlan set profileparameter name="{ssid}" keyMaterial="{new_password}"']
        elif _is_linux():
            cmds = [f'nmcli con mod "{ssid}" wifi-sec.psk "{new_password}"', f'nmcli con up "{ssid}"']
        elif _is_macos():
            cmds = ["networksetup -removepreferredwirelessnetwork en0 " f'"{ssid}"', f'networksetup -setairportnetwork en0 "{ssid}" "{new_password}"']
        else: return False, "Неподдерживаемая ОС"
        if dry_run: return True, "DRY-RUN:\n  " + "\n  ".join(cmds)
        if not _is_admin(): return False, "Требуются права администратора"
        for c in cmds: _run(c)
        return True, f"Пароль для {ssid} обновлён (возможен разрыв)"

    def list_adapters(self):
        if _is_windows():
            out = _run("netsh interface show interface")
            adapters = []
            for line in out.splitlines():
                parts = re.split(r"\s{2,}", line.strip())
                if len(parts) >= 4 and parts[0] in ("Enabled", "Disabled", "Включен", "Отключен", "Включено", "Отключено"):
                    adapters.append({"admin": parts[0], "state": parts[1], "type": parts[2], "name": parts[3]})
            return adapters
        if _is_linux():
            out = _run("nmcli -t -f DEVICE,TYPE,STATE device")
            adapters = []
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 3: adapters.append({"name": parts[0], "type": parts[1], "state": parts[2]})
            return adapters
        if _is_macos():
            out = _run("networksetup -listallhardwareports")
            adapters = []
            current = {}
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Hardware Port:"):
                    if current: adapters.append(current)
                    current = {"type": line.split(":", 1)[1].strip()}
                elif line.startswith("Device:"):
                    current["name"] = line.split(":", 1)[1].strip()
            if current: adapters.append(current)
            return adapters
        return []

    def set_adapter_state(self, name, enabled, dry_run=False):
        if _is_windows():
            state = "enable" if enabled else "disable"
            cmds = [f'netsh interface set interface "{name}" admin={state}']
        elif _is_linux():
            state = "up" if enabled else "down"
            cmds = [f'nmcli device set "{name}" autoconnect {"yes" if enabled else "no"}', f'ip link set {name} {state}']
        elif _is_macos():
            state = "on" if enabled else "off"
            cmds = [f"networksetup -setnetworkserviceenabled {name} {state}"]
        else: return False, "Неподдерживаемая ОС"
        if dry_run: return True, "DRY-RUN:\n  " + "\n  ".join(cmds)
        if not _is_admin(): return False, "Требуются права администратора"
        for c in cmds: _run(c)
        return True, f"Адаптер {name} {'включён' if enabled else 'выключен'}"

    def get_mtu(self, interface):
        if _is_windows():
            out = _run("netsh interface ipv4 show subinterface")
            for line in out.splitlines():
                if interface in line:
                    parts = line.split()
                    if parts and parts[0].isdigit(): return int(parts[0])
            return None
        if _is_linux():
            out = _run(f"ip link show {interface}")
            m = re.search(r"mtu (\d+)", out)
            return int(m.group(1)) if m else None
        if _is_macos():
            out = _run(f"networksetup -getMTU {interface}")
            m = re.search(r"MTU:\s*(\d+)", out)
            return int(m.group(1)) if m else None
        return None

    def set_mtu(self, interface, mtu, dry_run=False):
        mtu = int(mtu)
        if not (576 <= mtu <= 9000): return False, "MTU должен быть от 576 до 9000"
        if _is_windows():
            cmds = [f'netsh interface ipv4 set subinterface "{interface}" mtu={mtu} store=persistent']
        elif _is_linux():
            cmds = [f'ip link set dev {interface} mtu {mtu}']
        elif _is_macos():
            cmds = [f"networksetup -setMTU {interface} {mtu}"]
        else: return False, "Неподдерживаемая ОС"
        if dry_run: return True, "DRY-RUN:\n  " + "\n  ".join(cmds)
        if not _is_admin(): return False, "Требуются права администратора"
        for c in cmds: _run(c)
        return True, f"MTU {interface} = {mtu}"

    def _default_windows_interface(self):
        out = _run("netsh interface show interface")
        for line in out.splitlines():
            if any(s in line for s in ("Connected", "Подключено")):
                parts = re.split(r"\s{2,}", line.strip())
                if parts: return parts[-1]
        return "Wi-Fi"

    def _default_linux_conn(self):
        out = _run("nmcli -t -f NAME,TYPE,DEVICE con show --active")
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] in ("wifi", "ethernet"): return parts[0]
        return None