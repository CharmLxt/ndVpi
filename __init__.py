"""ndVpi — фоновая оптимизация сети и сканер Wi-Fi."""
from .version import __version__
from .wifi import WiFiScanner
from .network_info import NetworkInfo
from .polidium import Polidium
from .critchers import Critchers
from .network_config import NetworkConfig
from .monitor import NetworkMonitor
from .diagnostics import NetworkDiagnostics
from .history import SessionHistory
from .tracer import RouteTracer

__all__ = [
    "__version__",
    "WiFiScanner",
    "NetworkInfo",
    "Polidium",
    "Critchers",
    "NetworkConfig",
    "NetworkMonitor",
    "NetworkDiagnostics",
    "SessionHistory",
    "RouteTracer",
]

try:
    from . import collquan_ext  # noqa: F401
except Exception:
    pass