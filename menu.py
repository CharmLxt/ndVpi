"""Интерактивное меню ndVpi (Дашборд)."""
import sys
import os
from pathlib import Path

from . import charm_enhance as ui
from .wifi import WiFiScanner
from .network_info import NetworkInfo
from .polidium import Polidium
from .critchers import Critchers
from .network_config import NetworkConfig, _is_admin
from .monitor import NetworkMonitor
from .diagnostics import NetworkDiagnostics
from .history import SessionHistory
from .tracer import RouteTracer

def _render_dashboard(info, admin):
    ip = info.local_ip() or "—"
    gw = info.gateway() or "—"
    ping = info.ping() or "—"
    admin_str = "Да" if admin else "Нет"
    
    if ui.has_charm():
        from charmpkk.console import fg_hex
        p = ui.theme("tokyo_night")
        dash = [
            f"IP-адрес:  {ui._c.colorize(ip, fg=fg_hex(p.accent))}",
            f"Шлюз:      {ui._c.colorize(gw, fg=fg_hex(p.fg))}",
            f"Пинг:      {ui._c.colorize(str(ping) + ' ms', fg=fg_hex(p.success if str(ping).isdigit() and int(ping) < 100 else p.warning))}",
            f"Админ:     {ui._c.colorize(admin_str, fg=fg_hex(p.success if admin else p.danger))}"
        ]
        print(ui.box(dash, title="Статус сети", color="#7aa2ff"))
    else:
        print(f"--- Статус сети ---")
        print(f"IP: {ip} | Шлюз: {gw} | Пинг: {ping} ms | Админ: {admin_str}")
        print("-" * 20)

def _menu_network(info, history):
    while True:
        choice = ui.select("Сеть и Мониторинг", [
            "🌐 Текущая Wi-Fi сеть",
            "📡 Ближайшие сети",
            "🔌 Информация о подключении",
            "📊 Real-time монитор",
            "← Назад в главное меню"
        ])
        if not choice or choice.startswith("←"): break
        
        if choice.startswith("🌐"):
            print(ui.banner("Текущая Wi-Fi сеть", color="#7aa2ff"))
            data = WiFiScanner().current_network()
            if data: print(ui.key_value(data))
            else: ui.warning("Нет данных о Wi-Fi.")
            ui.ask("Enter — назад")
        elif choice.startswith("📡"):
            print(ui.banner("Ближайшие сети", color="#7aa2ff"))
            nets = WiFiScanner().available_networks()
            if not nets: ui.warning("Сети не найдены.")
            else:
                headers = ["SSID", "Сигнал", "Канал", "Безопасность"]
                rows = [[n.get("ssid", "?"), n.get("signal", n.get("rssi", "?")), n.get("channel", "?"), n.get("security", "?")] for n in nets]
                print(ui.table(headers, rows))
            ui.ask("Enter — назад")
        elif choice.startswith("🔌"):
            print(ui.banner("Информация о подключении", color="#7aa2ff"))
            print(ui.key_value({
                "IP": info.local_ip() or "—",
                "Шлюз": info.gateway() or "—",
                "DNS": ", ".join(info.dns_servers()) or "—",
                "Скорость линка": f"{info.wifi_details().get('rx_speed', '—')} / {info.wifi_details().get('tx_speed', '—')}"
            }))
            print()
            ui.info(f"Права администратора: {'да' if _is_admin() else 'нет'}")
            ui.ask("Enter — назад")
        elif choice.startswith("📊"):
            print(ui.banner("Real-time монитор", "Ctrl+C — выход", color="#7aa2ff"))
            NetworkMonitor(history=history).run()
            ui.ask("Enter — назад")

def _menu_optimize(polidium, critchers):
    while True:
        choice = ui.select("Оптимизация", [
            "🧹 Polidium (Очистка и DNS Бенчмарк)",
            "🚀 Critchers (Агрессивный буст)",
            "← Назад в главное меню"
        ])
        if not choice or choice.startswith("←"): break

        if choice.startswith("🧹"):
            print(ui.banner("Polidium", "Умная очистка", color="#7aa2ff"))
            ui.info("Очистка DNS, ARP и кэша маршрутов...")
            polidium.flush_dns()
            polidium.flush_arp()
            polidium.flush_routes()
            ui.success("Системные кэши очищены.")
            
            sub_choice = ui.select("Что делаем дальше?", [
                "Запустить DNS Бенчмарк (найти самый быстрый)",
                "Включить кэширование DNS в памяти",
                "← Назад"
            ])
            if sub_choice and sub_choice.startswith("Запустить"):
                ui.info("Тестируем DNS серверы...")
                results = polidium.benchmark_dns()
                rows = [[r["name"], r["ip"], f"{r['ms']} ms"] for r in results]
                print(ui.table(["Провайдер", "IP", "Задержка"], rows))
                ui.success(f"Рекомендуемый DNS: {results[0]['name']} ({results[0]['ip']})")
            elif sub_choice and sub_choice.startswith("Включить"):
                polidium.enable_dns_cache()
                ui.success("DNS-кэш в памяти включён.")
            ui.ask("Enter — назад")

        elif choice.startswith("🚀"):
            print(ui.banner("Critchers", "Агрессивный бустер", color="#ef4444"))
            if not _is_admin():
                ui.error("Critchers требует прав Администратора! Запустите терминал от имени администратора.")
            else:
                sub_choice = ui.select("Что делаем?", [
                    "Очистить RAM (Standby List)",
                    "Очистить NetBIOS кэш",
                    "Применить TCP твики (Реестр)",
                    "Отключить сон Wi-Fi адаптера",
                    "Приостановить фоновые загрузки",
                    "Восстановить всё (Restore)",
                    "← Назад"
                ])
                if sub_choice and not sub_choice.startswith("←"):
                    if sub_choice.startswith("Очистить RAM"):
                        ok, msg = critchers.clean_standby_list()
                        (ui.success if ok else ui.error)(msg)
                    elif sub_choice.startswith("Очистить NetBIOS"):
                        ok, msg = critchers.flush_netbios()
                        (ui.success if ok else ui.error)(msg)
                    elif sub_choice.startswith("Применить TCP"):
                        ok, msg = critchers.apply_tcp_tweaks()
                        (ui.success if ok else ui.error)(msg)
                    elif sub_choice.startswith("Отключить сон"):
                        ok, msg = critchers.disable_wifi_power_saving()
                        (ui.success if ok else ui.error)(msg)
                    elif sub_choice.startswith("Приостановить"):
                        ok, msg = critchers.pause_background_downloads()
                        (ui.success if ok else ui.error)(msg)
                    elif sub_choice.startswith("Восстановить"):
                        ok, msg = critchers.restore()
                        (ui.success if ok else ui.error)(msg)
            ui.ask("Enter — назад")

def _menu_tools(info, cfg, history):
    while True:
        choice = ui.select("Инструменты и Диагностика", [
            "🩺 Диагностика сети",
            "🛤️ Трассировка (RouteTracer)",
            "🔧 Изменить DNS",
            "🔑 Изменить пароль Wi-Fi",
            "🔀 Управление адаптерами",
            "📏 Настроить MTU",
            "💾 История и экспорт",
            "← Назад в главное меню"
        ])
        if not choice or choice.startswith("←"): break

        if choice.startswith("🩺"):
            print(ui.banner("Диагностика сети", color="#7aa2ff"))
            print(NetworkDiagnostics().get_report())
            ui.ask("Enter — назад")
        elif choice.startswith("🛤"):
            print(ui.banner("RouteTracer", "Анализ маршрута", color="#7aa2ff"))
            host = ui.ask("Введите хост (например, google.com или 8.8.8.8)")
            if host:
                ui.info(f"Трассировка до {host}...")
                tracer = RouteTracer()
                hops = tracer.trace(host)
                if hops: print(tracer.format_report(hops, use_charm=ui.has_charm()))
                else: ui.error("Не удалось получить маршрут.")
            ui.ask("Enter — назад")
        elif choice.startswith("🔧"):
            current = cfg.get_dns()
            print(ui.banner("DNS", color="#7aa2ff"))
            print(ui.key_value({"Текущий DNS": ", ".join(current) or "автоматически"}))
            sub_choice = ui.select("Что делаем?", ["Google (8.8.8.8, 8.8.4.4)", "Cloudflare (1.1.1.1, 1.0.0.1)", "Ввести вручную", "Сбросить", "← Назад"])
            if sub_choice and not sub_choice.startswith("←"):
                servers = []
                if sub_choice.startswith("Google"): servers = ["8.8.8.8", "8.8.4.4"]
                elif sub_choice.startswith("Cloudflare"): servers = ["1.1.1.1", "1.0.0.1"]
                elif sub_choice.startswith("Ввести"):
                    raw = ui.ask("IP через запятую", default="8.8.8.8, 8.8.4.4")
                    servers = [s.strip() for s in (raw or "").split(",") if s.strip()]
                elif sub_choice.startswith("Сбросить"):
                    ok, msg = cfg.reset_dns()
                    (ui.success if ok else ui.error)(msg)
                    ui.ask("Enter — назад")
                    continue
                
                ok, msg = cfg.set_dns(servers, dry_run=True)
                print(ui.info(msg))
                if ui.confirm("Применить изменения?", default=False):
                    ok, msg = cfg.set_dns(servers)
                    (ui.success if ok else ui.error)(msg)
            ui.ask("Enter — назад")
        elif choice.startswith("🔑"):
            ssid = ui.ask("SSID сети")
            if ssid:
                pwd = ui.ask("Новый пароль")
                if pwd:
                    ui.warning("Смена пароля может разорвать текущее соединение.")
                    if ui.confirm("Продолжить?", default=False):
                        ok, msg = cfg.change_wifi_password(ssid, pwd)
                        (ui.success if ok else ui.error)(msg)
            ui.ask("Enter — назад")
        elif choice.startswith("🔀"):
            adapters = cfg.list_adapters()
            print(ui.banner("Сетевые адаптеры", color="#7aa2ff"))
            if adapters:
                headers = ["Имя", "Тип", "Состояние"]
                rows = [[a.get("name", "?"), a.get("type", a.get("admin", "?")), a.get("state", "?")] for a in adapters]
                print(ui.table(headers, rows))
                sub_choice = ui.select("Действие", ["Включить", "Выключить", "← Назад"])
                if sub_choice and not sub_choice.startswith("←"):
                    names = [a.get("name") for a in adapters if a.get("name")]
                    target = ui.select("Выберите адаптер", names + ["← Назад"])
                    if target and not target.startswith("←"):
                        ok, msg = cfg.set_adapter_state(target, enabled=(sub_choice == "Включить"))
                        (ui.success if ok else ui.error)(msg)
            else: ui.warning("Не удалось получить список.")
            ui.ask("Enter — назад")
        elif choice.startswith("📏"):
            iface = ui.ask("Интерфейс", default="Wi-Fi")
            if iface:
                current = cfg.get_mtu(iface)
                ui.info(f"Текущий MTU: {current if current is not None else '—'}")
                mtu = ui.ask("Новый MTU (576–9000)", default="1400")
                if mtu:
                    ok, msg = cfg.set_mtu(iface, mtu)
                    (ui.success if ok else ui.error)(msg)
            ui.ask("Enter — назад")
        elif choice.startswith("💾"):
            summary = history.summary()
            print(ui.banner("История сессии", color="#7aa2ff"))
            if summary.get("samples", 0) == 0:
                ui.warning("История пуста. Сначала запустите монитор.")
            else:
                print(ui.key_value(summary))
                sub_choice = ui.select("Действие", ["Экспорт в JSON", "Экспорт в CSV", "Очистить историю", "← Назад"])
                if sub_choice and not sub_choice.startswith("←"):
                    reports_dir = Path.home() / ".ndvpi" / "reports"
                    if sub_choice.startswith("Экспорт в JSON"):
                        ui.success(f"Сохранено: {history.export_json(reports_dir / 'ndvpi_session.json')}")
                    elif sub_choice.startswith("Экспорт в CSV"):
                        ui.success(f"Сохранено: {history.export_csv(reports_dir / 'ndvpi_session.csv')}")
                    elif sub_choice.startswith("Очистить"):
                        if ui.confirm("Точно очистить?", default=False):
                            history.clear()
                            ui.success("История очищена.")
            ui.ask("Enter — назад")

def run():
    polidium = Polidium()
    critchers = Critchers()
    history = SessionHistory()
    info = NetworkInfo()
    cfg = NetworkConfig()
    mode_line = ("CharmPkk: активен" if ui.has_charm() else "CharmPkk: не найден (plain-режим)")

    while True:
        if ui.has_charm(): ui.console().terminal().clear()
        print(ui.banner("ndVpi", mode_line, color="#7aa2ff"))
        _render_dashboard(info, _is_admin())
        
        choice = ui.select("Что делаем?", [
            "🌐 Сеть и Мониторинг",
            "⚡ Оптимизация (Polidium / Critchers)",
            "🛠️ Инструменты и Диагностика",
            "❌ Выход",
        ])
        
        if choice is None or choice.startswith("❌"): break
        
        try:
            if choice.startswith("🌐"): _menu_network(info, history)
            elif choice.startswith("⚡"): _menu_optimize(polidium, critchers)
            elif choice.startswith("🛠"): _menu_tools(info, cfg, history)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            ui.error(f"Ошибка: {type(e).__name__}: {e}")
            ui.ask("Enter — назад")
            
    return 0