"""Machine load warning for doctor."""

from orchestrator import doctor


def check_machine_load() -> doctor.Check:
    load1, load5, _ = doctor.os.getloadavg()
    cores = doctor.os.cpu_count() or 1
    processes = doctor.acceptance._process_snapshot()
    heavy = next((row for row in processes
                  if row["cpu_percent"] >
                  doctor.config.MACHINE_LOAD_PROCESS_CORES * 100), None)
    detail = f"load average 1/5 мин {load1}/{load5}; ядер {cores}"
    if heavy:
        detail += (f"; процесс pid {heavy['pid']} {heavy['name']} "
                   f"{heavy['cpu_percent']}% живёт {heavy['age']}")
    return doctor.Check("machine-load", "warn" if load5 > cores or heavy else "ok",
                        detail)
