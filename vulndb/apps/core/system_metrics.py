from __future__ import annotations

import shutil
from datetime import datetime

import psutil
from django.http import JsonResponse


def collect_system_metrics() -> dict:
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = shutil.disk_usage("/")
    # non-blocking sample; second call after tiny delay improves accuracy — keep simple
    cpu = psutil.cpu_percent(interval=0.2)
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        disks.append(
            {
                "device": part.device,
                "mount": part.mountpoint,
                "fstype": part.fstype,
                "total": u.total,
                "used": u.used,
                "free": u.free,
                "percent": u.percent,
            }
        )
    return {
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "cpu": {
            "percent": cpu,
            "count": psutil.cpu_count() or 1,
            "load_1": load[0],
            "load_5": load[1],
            "load_15": load[2],
        },
        "ram": {
            "total": ram.total,
            "used": ram.used,
            "available": ram.available,
            "percent": ram.percent,
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
        },
        "disk_root": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.used * 100 / disk.total, 1) if disk.total else 0,
        },
        "disks": disks,
    }


def system_metrics_json(request):
    return JsonResponse(collect_system_metrics())
