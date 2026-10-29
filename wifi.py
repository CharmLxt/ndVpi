"""Сканирование Wi-Fi сетей (Windows / Linux / macOS)."""
import subprocess
import platform
import re
import time

def _decode_raw(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "cp866", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

def _run(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return _decode_raw(result.stdout or b"")
    except Exception:
        return ""

class WiFiScanner:
    """Получение информации о Wi-Fi сетях."""

    def current_network(self):
        system = platform.system()
        if system == "Windows": return self._current_windows()
        elif system == "Linux": return self._current_linux()
        elif system == "Darwin": return self._current_macos()
        return None

    def available_networks(self):
        system = platform.system()
        if system == "Windows": return self._available_windows()
        elif system == "Linux": return self._available_linux()
        elif system == "Darwin": return self._available_macos()
        return []

    def _current_windows(self):
        out = _run("netsh wlan show interfaces")
        if not out: return None
        data = {}
        for line in out.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key in ("ssid", "bssid", "signal", "channel", "authentication",
                           "проверка подлинности", "канал", "сигнал"):
                    data[key] = value
        return data if data else None

    def _available_windows(self):
        out = _run("netsh wlan show networks mode=bssid")
        networks = self._parse_windows_networks(out)
        if len(networks) <= 1:
            time.sleep(2)
            out = _run("netsh wlan show networks mode=bssid")
            networks = self._parse_windows_networks(out)
        return networks

    def _parse_windows_networks(self, out):
        if not out: return []
        networks = []
        current = None
        for line in out.splitlines():
            line = line.strip()
            if not line: continue
            m = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line, re.IGNORECASE)
            if m:
                if current: networks.append(current)
                current = {"ssid": m.group(1).strip()}
                continue
            if current is None: continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key.startswith("bssid"): current.setdefault("bssids", []).append(value)
                elif key in ("signal", "сигнал"): current["signal"] = value
                elif key in ("channel", "канал"): current["channel"] = value
                elif key in ("authentication", "проверка подлинности"): current["security"] = value
        if current: networks.append(current)
        return networks

    def _current_linux(self):
        out = _run("nmcli -t -f active,ssid,bssid,signal,chan,security dev wifi")
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 6 and parts[0] == "yes":
                return {"ssid": parts[1], "bssid": parts[2], "signal": parts[3], "channel": parts[4], "security": parts[5]}
        return None

    def _available_linux(self):
        out = _run("nmcli -t -f ssid,bssid,signal,chan,security dev wifi list")
        networks = []
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 5:
                networks.append({"ssid": parts[0], "bssid": parts[1], "signal": parts[2], "channel": parts[3], "security": parts[4]})
        return networks

    def _current_macos(self):
        out = _run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I")
        data = {}
        for line in out.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key in ("ssid", "bssid", "agrctlrssi", "channel"): data[key] = value
        return data if data else None

    def _available_macos(self):
        out = _run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s")
        networks = []
        lines = out.splitlines()
        if not lines: return []
        for line in lines[1:]:
            parts = re.split(r"\s+", line.strip(), maxsplit=6)
            if len(parts) >= 7:
                networks.append({"ssid": parts[0], "bssid": parts[1], "rssi": parts[2], "channel": parts[3], "security": parts[6]})
        return networks