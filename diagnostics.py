"""Диагностика сети: выявление проблем и рекомендации."""
import socket
from .network_info import NetworkInfo
from .wifi import WiFiScanner
from .network_config import NetworkConfig
from . import charm_enhance as ui

class CheckResult:
    def __init__(self, name, ok, details, recommendation=""):
        self.name, self.ok, self.details, self.recommendation = name, ok, details, recommendation

class NetworkDiagnostics:
    def __init__(self):
        self.info = NetworkInfo()
        self.wifi = WiFiScanner()
        self.config = NetworkConfig()

    def run_checks(self):
        results = []
        adapters = self.config.list_adapters()
        enabled = [a for a in adapters if a.get("state") in ("Connected", "Подключено", "up", "Подключен")]
        if not adapters:
            results.append(CheckResult("Адаптеры", False, "Не найдены сетевые адаптеры", "Проверьте драйверы"))
        elif not enabled:
            results.append(CheckResult("Адаптеры", False, "Все отключены", "Включите сетевой адаптер"))
        else:
            results.append(CheckResult("Адаптеры", True, f"Активен: {enabled[0].get('name', 'Неизвестно')}"))

        wifi_data = self.wifi.current_network()
        if wifi_data:
            results.append(CheckResult("Wi-Fi", True, f"Подключено к {wifi_data.get('ssid', '?')}"))
        else:
            results.append(CheckResult("Wi-Fi", True, "Не активен (возможно Ethernet)"))

        gw = self.info.gateway()
        if not gw:
            results.append(CheckResult("Шлюз", False, "Не найден", "Проверьте DHCP"))
        else:
            gw_ping = self.info.ping(gw, timeout=1)
            if gw_ping is not None:
                results.append(CheckResult("Шлюз", True, f"{gw} ({gw_ping:.0f} ms)"))
            else:
                results.append(CheckResult("Шлюз", False, f"{gw} не отвечает", "Перезагрузите роутер"))

        try:
            socket.gethostbyname("google.com")
            results.append(CheckResult("DNS", True, "Разрешение имён работает"))
        except socket.gaierror:
            results.append(CheckResult("DNS", False, "Домены не резолвятся", "Смените DNS на 1.1.1.1"))

        ping_stats = self.info.ping_series("8.8.8.8", count=3, timeout=1)
        if not ping_stats:
            results.append(CheckResult("Интернет", False, "Нет доступа", "Проверьте кабель/провайдера"))
        else:
            if ping_stats["loss"] > 0:
                results.append(CheckResult("Потери", False, f"Потери: {ping_stats['loss']:.1f}%", "Помехи или перегрузка канала"))
            elif ping_stats["avg"] > 150:
                results.append(CheckResult("Пинг", False, f"Высокий: {ping_stats['avg']:.0f} ms", "Попробуйте Critchers или Polidium"))
            else:
                results.append(CheckResult("Интернет", True, f"Стабильно ({ping_stats['avg']:.0f} ms)"))
        return results

    def get_report(self):
        results = self.run_checks()
        fails = [r for r in results if not r.ok]
        if ui.has_charm():
            rows = [[("✔ OK" if r.ok else "✖ ОШИБКА"), r.name, r.details or "", r.recommendation or ""] for r in results]
            out = [ui.table(["Статус", "Проверка", "Детали", "Рекомендация"], rows), ""]
            out.append(ui.render_warning("Обнаружены проблемы.") if fails else ui.render_success("Сеть работает стабильно."))
            return "\n".join(out)
        out = ["=== Диагностика сети ==="]
        for r in results:
            out.append(f"{'[+]' if r.ok else '[x]'} {r.name}: {r.details}")
            if not r.ok and r.recommendation: out.append(f"    -> {r.recommendation}")
        return "\n".join(out)