"""Пакет orchestrator/doctor -- recovery-сверка журнала БД с артефактным репо target'а.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- recovery-сверка (требование 4) -------------------------------------

def recovery_check(conn, target: str) -> list[doctor.Check]:
    """Журнал БД ↔ файлы задач артефактного репо target'а: sha, чистота,
    fsck — единая логика для ЛЮБОГО объявленного target, включая артель
    (A7, требование 2, AC-3). Сверка HEAD главной копии пульта
    (`config.ROOT`) в объём этой проверки не входит — та отдельная
    забота doctor-проверки пина (`check_root_pin`, AC-13): HEAD ROOT
    двигают процессы вне FSM обычной задачи (мерж, `pin-update`), сверка
    sha «как для артефактного репо» дала бы систематические ложные
    инциденты, не имеющие отношения к целостности артефактов.

    Авто-ack трёх под-проверок (SPEC T088, требования 2-4, 6) зовётся на
    каждом прогоне для КОНКРЕТНОГО target — независимо от остальных двух
    под-проверок и от того же source другого target (`_auto_ack_gone`
    получает `target=target`).
    """
    repo = doctor.config.PROJECTS / target
    if not (repo / ".git").is_dir():
        return [doctor.Check("recovery", "skip",
                      f"артефактный репо {target} не инициализирован")]

    results = []
    latest = doctor.store.latest_fixed_sha(conn, target)
    current = doctor.gitcmd.head_sha(repo)
    sha_mismatch = latest is not None and current and current != latest["fixed_sha"]
    if sha_mismatch:
        message = (f"sha головы {current} разошёлся с зафиксированным "
                  f"{latest['fixed_sha']} ({latest['id']})")
        doctor.alerts.raise_alert(conn, target, "incident", "doctor.recovery.sha", message)
        results.append(doctor.Check("recovery-sha", "fail", message))
    else:
        results.append(doctor.Check("recovery-sha", "ok", "sha головы сходится с журналом"))
    doctor._auto_ack_gone(conn, "doctor.recovery.sha", lambda _msg: sha_mismatch,
                  target=target)

    clean = doctor.gitcmd.is_clean(repo=repo)
    dirty = clean is False
    if dirty:
        message = f"артефактный репо {target} грязный"
        doctor.alerts.raise_alert(conn, target, "incident", "doctor.recovery.dirty", message)
        results.append(doctor.Check("recovery-clean", "fail", message))
    else:
        results.append(doctor.Check("recovery-clean", "ok", "рабочая копия чистая"))
    doctor._auto_ack_gone(conn, "doctor.recovery.dirty", lambda _msg: dirty, target=target)

    fsck = doctor.gitcmd.in_repo(repo, "fsck", "--no-progress")
    fsck_failed = fsck.returncode != 0
    if fsck_failed:
        message = (f"git fsck {target}: "
                  f"{fsck.stderr.strip()[:300] or fsck.stdout.strip()[:300]}")
        doctor.alerts.raise_alert(conn, target, "incident", "doctor.recovery.fsck", message)
        results.append(doctor.Check("recovery-fsck", "fail", message))
    else:
        results.append(doctor.Check("recovery-fsck", "ok", "git fsck чисто"))
    doctor._auto_ack_gone(conn, "doctor.recovery.fsck", lambda _msg: fsck_failed,
                  target=target)

    return results


