"""История метрик сети за сессию и экспорт в JSON/CSV."""
import json
import csv
import time
from pathlib import Path

class SessionHistory:
    def __init__(self):
        self.records = []

    def add_ping(self, host, stats):
        if stats:
            self.records.append({"ts": time.time(), "type": "ping", "host": host, "data": stats})

    def add_speed(self, download_mbps, upload_mbps):
        self.records.append({"ts": time.time(), "type": "speed", "data": {"download": download_mbps, "upload": upload_mbps}})

    def clear(self):
        self.records.clear()

    def summary(self):
        pings = [r for r in self.records if r["type"] == "ping"]
        speeds = [r for r in self.records if r["type"] == "speed"]
        result = {"samples": len(self.records)}
        if pings:
            result.update({
                "avg_ping_ms": round(sum(p["data"]["avg"] for p in pings) / len(pings), 2),
                "avg_loss_pct": round(sum(p["data"]["loss"] for p in pings) / len(pings), 2),
                "avg_jitter_ms": round(sum(p["data"]["jitter"] for p in pings) / len(pings), 2)
            })
        if speeds:
            result.update({
                "avg_download_mbps": round(sum(s["data"]["download"] for s in speeds) / len(speeds), 2),
                "avg_upload_mbps": round(sum(s["data"]["upload"] for s in speeds) / len(speeds), 2)
            })
        return result

    def export_json(self, filepath):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2, ensure_ascii=False)
        return str(path)

    def export_csv(self, filepath):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Type", "Min/Avg/Download", "Max/Upload", "Loss/Jitter"])
            for r in self.records:
                if r["type"] == "ping":
                    d = r["data"]
                    writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), "Ping", f"{d['avg']:.1f} ms", f"{d['max']:.1f} ms", f"{d['loss']:.1f}% / {d['jitter']:.1f} ms"])
                elif r["type"] == "speed":
                    d = r["data"]
                    writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), "Speed", f"{d['download']:.1f} Mbps", f"{d['upload']:.1f} Mbps", "-"])
        return str(path)