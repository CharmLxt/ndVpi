"""RouteTracer: Продвинутый анализ маршрутов и задержек на узлах."""
import subprocess
import platform
import re
import socket
import time

def _decode_raw(raw: bytes) -> str:
    if not raw: return ""
    for enc in ("utf-8", "cp866", "cp1251"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: continue
    return raw.decode("utf-8", errors="replace")

class RouteTracer:
    def __init__(self, max_hops=15, timeout=1000):
        self.max_hops = max_hops
        self.timeout = timeout
        self.history = []

    def trace(self, host):
        system = platform.system()
        if system == "Windows":
            cmd = f"tracert -d -h {self.max_hops} -w {self.timeout} {host}"
        else:
            cmd = f"traceroute -n -m {self.max_hops} -w {max(1, self.timeout // 1000)} {host}"

        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, timeout=60).stdout
            output_text = _decode_raw(out)
        except Exception:
            return None

        return self._parse_output(output_text, system)

    def _parse_output(self, output, system):
        hops = []
        for line in output.splitlines():
            line = line.strip()
            if not line or "Tracing route" in line or "traceroute to" in line or "over a maximum" in line:
                continue

            if system == "Windows":
                m = re.match(r"^\s*(\d+)\s+(?:<\s*1\s*ms|(\d+)\s*ms)\s+(?:<\s*1\s*ms|(\d+)\s*ms)\s+(?:<\s*1\s*ms|(\d+)\s*ms)\s+([a-zA-Z0-9.:-]+)", line)
                if m:
                    times = [int(x) if x else 1 for x in m.groups()[1:4]]
                    hops.append({"hop": int(m.group(1)), "ip": m.group(5), "times": times})
            else:
                m = re.match(r"^\s*(\d+)\s+([a-zA-Z0-9.:-]+)\s+(.*)$", line)
                if m:
                    times = [int(float(t)) for t in re.findall(r"([\d.]+)\s*ms", m.group(3))]
                    if not times: times = [0]
                    hops.append({"hop": int(m.group(1)), "ip": m.group(2), "times": times})

        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(0.5)
        for h in hops:
            valid_times = [t for t in h["times"] if t > 0]
            h["avg"] = int(sum(valid_times) / len(valid_times)) if valid_times else 0
            h["loss"] = int(((len(h["times"]) - len(valid_times)) / len(h["times"])) * 100) if h["times"] else 100
            try:
                h["hostname"] = socket.gethostbyaddr(h["ip"])[0]
            except Exception:
                h["hostname"] = "-"
        socket.setdefaulttimeout(old_timeout)

        self.history.append({"ts": time.time(), "hops": hops})
        return hops

    def format_report(self, hops, use_charm=False):
        if not hops:
            return "Не удалось получить данные трассировки."

        if use_charm:
            try:
                from charmpkk.console import Table, fg_hex
                t = Table(headers=["Хоп", "IP / Хост", "Ср. пинг", "Потери"], header_fg=fg_hex("#7aa2ff"))
                for h in hops:
                    t.add_row([str(h["hop"]), f"{h['ip']}\n{h['hostname'][:30]}", f"{h['avg']} ms", f"{h['loss']}%"])
                return t.render()
            except ImportError:
                pass

        lines = ["Хоп | IP / Хост                       | Ср. пинг | Потери", "-" * 60]
        for h in hops:
            host_str = f"{h['ip']} ({h['hostname'][:20]})" if h['hostname'] != "-" else h['ip']
            lines.append(f"{h['hop']:>3} | {host_str:<32} | {h['avg']:>5} ms | {h['loss']:>3}%")
        return "\n".join(lines)