"""Интеграция ndVpi с Collquan (CharmPkk)."""
try:
    from charmpkk.terminals import CollquanShell
except Exception:
    CollquanShell = None

from .wifi import WiFiScanner
from .network_info import NetworkInfo
from .polidium import Polidium
from .critchers import Critchers
from .network_config import NetworkConfig, _is_admin

_polidium = Polidium()
_critchers = Critchers()
_config = NetworkConfig()

def _cmd_scan(args):
    data = WiFiScanner().current_network()
    if not data: print("Нет данных о Wi-Fi."); return
    for k, v in data.items(): print(f"{k}: {v}")

def _cmd_info(args):
    info = NetworkInfo()
    print(f"IP:    {info.local_ip()}")
    print(f"Шлюз:  {info.gateway()}")
    print(f"DNS:   {', '.join(info.dns_servers()) or '—'}")
    print(f"Ping:  {info.ping() or '—'} ms")

def _cmd_poli(args):
    if args and args[0] == "dns":
        _polidium.flush_dns()
        print("[+] DNS кэш очищен")
    elif args and args[0] == "arp":
        _polidium.flush_arp()
        print("[+] ARP кэш очищен")
    else:
        _polidium.flush_dns()
        _polidium.flush_arp()
        print("[+] Polidium: кэши очищены")
        
def _cmd_crit(args):
    if args and args[0] == "ram":
        ok, msg = _critchers.clean_standby_list()
        print(f"[{'x' if not ok else '+'}] {msg}")
    elif args and args[0] == "tcp":
        ok, msg = _critchers.apply_tcp_tweaks()
        print(f"[{'x' if not ok else '+'}] {msg}")
    elif args and args[0] == "restore":
        ok, msg = _critchers.restore()
        print(f"[{'x' if not ok else '+'}] {msg}")
    else:
        print("Использование: ndcrit <ram|tcp|restore>")

def _cmd_dns(args):
    if not args or args[0] == "show":
        servers = _config.get_dns()
        print("DNS:", ", ".join(servers) if servers else "автоматически")
        return
    if args[0] == "set":
        if len(args) < 2: print("Использование: nddns set <ip1> [ip2]..."); return
        ok, msg = _config.set_dns(args[1:])
        print(("[+] " if ok else "[x] ") + msg)
        return
    if args[0] == "reset":
        ok, msg = _config.reset_dns()
        print(("[+] " if ok else "[x] ") + msg)
        return
    print("Использование: nddns [show|set <ip>...|reset]")

def _cmd_pass(args):
    if len(args) < 2: print("Использование: ndpass <ssid> <new_password>"); return
    ssid, pwd = args[0], args[1]
    print(f"[!] Внимание: смена пароля для '{ssid}' может разорвать соединение.")
    if input("Продолжить? [y/N] ").strip().lower() != "y":
        print("Отменено."); return
    ok, msg = _config.change_wifi_password(ssid, pwd)
    print(("[+] " if ok else "[x] ") + msg)

def _cmd_adapters(args):
    if not args or args[0] == "list":
        for a in _config.list_adapters(): print(f"  {a.get('name', '?'):<30} {a}")
        return
    if args[0] in ("enable", "disable") and len(args) >= 2:
        ok, msg = _config.set_adapter_state(args[1], enabled=(args[0] == "enable"))
        print(("[+] " if ok else "[x] ") + msg)
        return
    print("Использование: ndadapters [list|enable|disable <name>]")

def _cmd_mtu(args):
    if not args: print("Использование: ndmtu <interface> [new_mtu]"); return
    iface = args[0]
    if len(args) == 1:
        mtu = _config.get_mtu(iface)
        print(f"MTU {iface} = {mtu if mtu is not None else '—'}")
        return
    ok, msg = _config.set_mtu(iface, args[1])
    print(("[+] " if ok else "[x] ") + msg)

def _cmd_admin(args):
    print("Администратор:", "да" if _is_admin() else "нет")

if CollquanShell is not None:
    CollquanShell.register("ndscan", "Сканировать Wi-Fi")(_cmd_scan)
    CollquanShell.register("ndinfo", "Информация о сети")(_cmd_info)
    CollquanShell.register("ndpoli", "Polidium: очистка DNS/ARP")(_cmd_poli)
    CollquanShell.register("ndcrit", "Critchers: RAM/TCP буст")(_cmd_crit)
    CollquanShell.register("nddns", "DNS: show/set/reset")(_cmd_dns)
    CollquanShell.register("ndpass", "Сменить пароль Wi-Fi: <ssid> <pass>")(_cmd_pass)
    CollquanShell.register("ndadapters", "Адаптеры: list/enable/disable")(_cmd_adapters)
    CollquanShell.register("ndmtu", "MTU: <iface> [new_mtu]")(_cmd_mtu)
    CollquanShell.register("ndadmin", "Проверить права администратора")(_cmd_admin)