"""Фоновая оптимизация сети: TCP_NODELAY, DNS-кэш, keep-alive."""
import socket
import threading
import time
import functools
from collections import OrderedDict


class _DNSCache:
    """Простой TTL-кэш для getaddrinfo."""

    def __init__(self, ttl=60, maxsize=256):
        self.ttl = ttl
        self.maxsize = maxsize
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self._orig = None

    def install(self):
        if self._orig is not None:
            return
        self._orig = socket.getaddrinfo
        cache = self
        orig = self._orig

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
                cache._cache[key] = (now + cache.ttl, result)
                cache._cache.move_to_end(key)
                while len(cache._cache) > cache.maxsize:
                    cache._cache.popitem(last=False)
            return result

        socket.getaddrinfo = cached

    def uninstall(self):
        if self._orig is not None:
            socket.getaddrinfo = self._orig
            self._orig = None

    def size(self):
        with self._lock:
            return len(self._cache)

    def clear_expired(self):
        now = time.time()
        with self._lock:
            expired = [k for k, (exp, _) in self._cache.items() if exp < now]
            for k in expired:
                del self._cache[k]
            return len(expired)


class NetworkOptimizer:
    """Фоновый оптимизатор сети."""

    def __init__(self, dns_ttl=60, keepalive_interval=30):
        self.dns_ttl = dns_ttl
        self.keepalive_interval = keepalive_interval
        self._dns = _DNSCache(ttl=dns_ttl)
        self._thread = None
        self._stop = threading.Event()
        self._running = False

    def enable_tcp_nodelay(self, sock: socket.socket):
        """Отключает алгоритм Нейгла на сокете (снижает задержку)."""
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return True
        except Exception:
            return False

    def enable_dns_cache(self):
        self._dns.install()

    def disable_dns_cache(self):
        self._dns.uninstall()

    def start(self):
        if self._running:
            return
        self.enable_dns_cache()
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.disable_dns_cache()

    def _loop(self):
        while not self._stop.is_set():
            self._dns.clear_expired()
            self._stop.wait(self.keepalive_interval)

    def status(self):
        return {
            "running": self._running,
            "dns_cache_size": self._dns.size(),
            "dns_ttl": self.dns_ttl,
        }