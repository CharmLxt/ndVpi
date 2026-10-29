"""Информация о текущем сетевом подключении."""
import socket
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
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return _decode_raw(result.stdout or b"")
    except Exception:
        return ""

_GATEWAY_PATTERNS = [
    r"Default Gateway[.\s]*:\s*([\d.]+)",
    r"(?:Основной шлюз|Шлюз по умолчанию)[.\s]*:\s*([\d.]+)",
    r"default via ([\d.]+)",
    r"default\s+([\d.]+)",
]
_DNS_HEADER = re.compile(r"^(?:DNS Servers|DNS-серверы|DNS серверы)\b", re.IGNORECASE)
_PING_TIME = re.compile(r"(?:time|время)\s*[=<]\s*([\d.,]+)\s*(?:ms|мс)", re.IGNORECASE)

class NetworkInfo:

    def local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def gateway(self):
        system = platform.system()
        if system == "Windows": out = _run("ipconfig")
        elif system == "Linux": out = _run("ip route")
        elif system == "Darwin": out = _run("netstat -nr")
        else: return None
        for pat in _GATEWAY_PATTERNS:
            m = re.search(pat, out, re.IGNORECASE)
            if m: return m.group(1)
        return None

    def dns_servers(self):
        system = platform.system()
        if system == "Windows":
            out = _run("ipconfig /all")
            servers = []
            in_dns = False
            for line in out.splitlines():
                stripped = line.strip()
                if _DNS_HEADER.match(stripped):
                    in_dns = True
                    m = re.search(r"([\d.]+)\s*$", stripped)
                    if m: servers.append(m.group(1))
                    continue
                if in_dns:
                    if re.fullmatch(r"[\d.]+", stripped): servers.append(stripped)
                    else: in_dns = False
            return [s for s in servers if ":" not in s]
        try:
            with open("/etc/resolv.conf") as f:
                return re.findall(r"nameserver\s+([^\s#]+)", f.read())
        except FileNotFoundError:
            return []

    def ping(self, host="8.8.8.8", timeout=2):
        system = platform.system()
        if system == "Windows": out = _run(f"ping -n 1 -w {timeout * 1000} {host}")
        else: out = _run(f"ping -c 1 -W {timeout} {host}")
        m = _PING_TIME.search(out)
        if not m: return None
        try: return float(m.group(1).replace(",", "."))
        except ValueError: return None

    def ping_series(self, host="8.8.8.8", count=5, timeout=1):
        system = platform.system()
        if system == "Windows": cmd = f"ping -n {count} -w {timeout * 1000} {host}"
        else: cmd = f"ping -c {count} -W {timeout} {host}"
        out = _run(cmd)
        times = []
        for line in out.splitlines():
            m = _PING_TIME.search(line)
            if m:
                try: times.append(float(m.group(1).replace(",", ".")))
                except ValueError: pass
        if not times: return None
        jitter = 0.0
        if len(times) > 1:
            diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
            jitter = sum(diffs) / len(diffs)
        return {
            "min": min(times), "max": max(times), "avg": sum(times) / len(times),
            "jitter": jitter, "loss": ((count - len(times)) / count) * 100,
            "success_count": len(times)
        }

    def wifi_details(self):
        out = _run("netsh wlan show interfaces")
        data = {}
        for line in out.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip().lower(), v.strip()
                if "receive rate" in k or "скорость приема" in k: data["rx_speed"] = v
                elif "transmit rate" in k or "скорость передачи" in k: data["tx_speed"] = v
                elif "signal" in k or "сигнал" in k: data["signal"] = v
        return data