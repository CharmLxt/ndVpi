"""Polidium: Безопасная очистка сети и умная оптимизация."""
import socket
import platform
import subprocess
import functools
import time
from collections import OrderedDict

def _run(cmd):
    try:
        subprocess.run(cmd, capture_output=True, shell=True, timeout=10)
        return True
    except Exception:
        return False

class Polidium:
    def __init__(self, dns_ttl=60):
        self.dns_ttl = dns_ttl
        self._cache = OrderedDict()
        self._orig_getaddrinfo = None
        self._lock = __import__("threading").Lock()

    def enable_dns_cache(self):
        if self._orig_getaddrinfo is not None: return
        self._orig_getaddrinfo = socket.getaddrinfo
        cache = self
        orig = self._orig_getaddrinfo

        @functools.wraps(orig)
        def cached(host, port, family=0, type=0, proto=0, flags=0):
            key = (host, port, family, type, proto, flags)
            now = time.time()
            with cache._lock:
                entry = cache._cache.get(key)
                if entry and entry[0] > now:
                    return entry[1]
            result = orig(host, port, family, type, proto, flags)
            with cache._lock:
                cache._cache[key] = (now + cache.dns_ttl, result)
                cache._cache.move_to_end(key)
                while len(cache._cache) > 256:
                    cache._cache.popitem(last=False)
            return result
        socket.getaddrinfo = cached

    def disable_dns_cache(self):
        if self._orig_getaddrinfo:
            socket.getaddrinfo = self._orig_getaddrinfo
            self._orig_getaddrinfo = None

    def flush_dns(self):
        if platform.system() == "Windows": return _run("ipconfig /flushdns")
        return False

    def flush_arp(self):
        if platform.system() == "Windows": return _run("netsh interface ip delete arpcache")
        return False

    def flush_routes(self):
        """Очищает кэш маршрутов (устраняет проблемы с кривыми маршрутами)."""
        if platform.system() == "Windows": return _run("route -f")
        elif platform.system() == "Linux": return _run("ip route flush cache")
        return False

    def benchmark_dns(self):
        """Пингует популярные DNS и возвращает список с задержками."""
        servers = {
            "Cloudflare": "1.1.1.1",
            "Google": "8.8.8.8",
            "Quad9": "9.9.9.9",
            "OpenDNS": "208.67.222.222"
        }
        results = []
        for name, ip in servers.items():
            try:
                start = time.time()
                socket.create_connection((ip, 53), timeout=1.5).close()
                ms = int((time.time() - start) * 1000)
                results.append({"name": name, "ip": ip, "ms": ms})
            except Exception:
                results.append({"name": name, "ip": ip, "ms": 999})
        
        return sorted(results, key=lambda x: x["ms"])

    def enable_tcp_nodelay(self, sock):
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return True
        except Exception:
            return False