"""Мониторинг сети в реальном времени (ping, speed, loss, jitter)."""
import time
import threading
import urllib.request
from .network_info import NetworkInfo
from .history import SessionHistory
from . import charm_enhance as ui

class NetworkMonitor:
    def __init__(self, history=None, host="8.8.8.8"):
        self.history = history or SessionHistory()
        self.host = host
        self.ninfo = NetworkInfo()
        self.ping_interval = 1.0
        self.speed_interval = 15.0
        self.last_speed_time = 0.0
        self._last_speed_results = {"download": 0.0, "upload": 0.0}
        self._speed_thread = None
        self._ping_history = [0] * 20

    def _do_speed_test(self):
        try:
            start = time.time()
            urllib.request.urlopen("https://speed.cloudflare.com/__down?bytes=1000000", timeout=5).read()
            down_time = time.time() - start
            down_mbps = (1000000 * 8) / (down_time * 1024 * 1024)
            data = b"0" * 500000
            req = urllib.request.Request("https://speed.cloudflare.com/__up", data=data, method="POST")
            start = time.time()
            urllib.request.urlopen(req, timeout=5).read()
            up_time = time.time() - start
            up_mbps = (500000 * 8) / (up_time * 1024 * 1024)
            return down_mbps, up_mbps
        except Exception:
            return None, None

    def _speed_worker(self):
        d, u = self._do_speed_test()
        if d is not None:
            self._last_speed_results = {"download": d, "upload": u}
            self.history.add_speed(d, u)

    def sample(self):
        stats = self.ninfo.ping_series(host=self.host, count=3, timeout=1)
        if time.time() - self.last_speed_time > self.speed_interval:
            if not self._speed_thread or not self._speed_thread.is_alive():
                self._speed_thread = threading.Thread(target=self._speed_worker, daemon=True)
                self._speed_thread.start()
            self.last_speed_time = time.time()
        if stats:
            self.history.add_ping(self.host, stats)
            self._ping_history.pop(0)
            self._ping_history.append(int(stats["avg"]))
        else:
            self._ping_history.pop(0)
            self._ping_history.append(0)
        return {"ping_stats": stats, "speed": self._last_speed_results}

    def run(self, duration=None):
        end_time = time.time() + duration if duration else None
        with ui.LiveDashboard() as dash:
            try:
                while True:
                    if end_time and time.time() > end_time: break
                    data = self.sample()
                    self._render(dash, data)
                    time.sleep(self.ping_interval)
            except KeyboardInterrupt:
                pass

    def _render(self, dash, data):
        ps, sp = data["ping_stats"], data["speed"]
        spark = ui.sparkline(self._ping_history, fg="#7aa2ff")
        lines = [f"📊 Мониторинг сети (хост: {self.host})", f"  График: {spark}"]
        if ps:
            lines.append(f"  Ping:   {ps['avg']:.0f} ms (min: {ps['min']:.0f}, max: {ps['max']:.0f})")
            lines.append(f"  Jitter: {ps['jitter']:.1f} ms")
            lines.append(f"  Потери: {ps['loss']:.1f}%")
        else:
            lines.append("  Ping:   Нет ответа (100% loss)")
        if sp and sp.get("download"):
            lines.append(f"  Скорость: ↓ {sp['download']:.1f} Mbps | ↑ {sp['upload']:.1f} Mbps")
        else:
            lines.append("  Скорость: ожидание замера...")
        lines.extend(["", "[Ctrl+C] — остановить мониторинг"])
        dash.update("\n".join(lines))