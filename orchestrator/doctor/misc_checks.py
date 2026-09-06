"""Пакет orchestrator/doctor -- разрозненные проверки: бэкап, счётчики, снапшоты, remote, base-branch.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import time

from orchestrator import doctor


# --- прочие проверки (требование 9) --------------------------------------

def check_backup_age(conn) -> doctor.Check:
    """Деградировано до информационной строки (SPEC T049, требование 6;
    легализовано ADR-0005 п.3: отдельный бэкап `.artel/` не ведётся —
    сохранность определяется уровнем target'а, не бэкапом пульта).
    Больше не заводит `incident`: маркер, если Оператор всё же его ведёт
    по своей воле, остаётся диагностической строкой, не гейтом. Любой
    открытый алерт этого источника, заведённый ДО этой правки,
    авто-ack'ается — условие, которое его подняло, снято настоящей
    задачей, не наблюдением doctor.
    """
    doctor._auto_ack_gone(conn, "doctor.backup_age", lambda _msg: False)
    marker = doctor.config.BACKUP_MARKER
    if not marker.exists():
        return doctor.Check("backup-age", "ok",
                     "бэкап .artel/ отдельно не ведётся (ADR-0005 п.3) — "
                     "информационно, не гейт")
    age_days = (time.time() - marker.stat().st_mtime) / 86400
    return doctor.Check("backup-age", "ok",
                 f"маркер найден, {age_days:.1f} дн. назад — информационно "
                 f"(ADR-0005 п.3, бэкап .artel/ не обязателен)")


def check_task_counters(conn) -> doctor.Check:
    """Контур счётчика номеров задач — замороженный legacy (SPEC T094,
    требование 6; ADR-0005 п.5 правки этой же задачи): генератором id
    стал ULID (`orchestrator/idgen.py`), `cmd_new` больше не расходует
    `store.next_task_number` ни для одного target — коллизия номеров,
    которую эта проверка когда-то ловила, для ULID структурно не
    существует. Сверка деградирована до информационной (AC-7): статус
    никогда не `fail`, алерт `doctor.task_counter` не заводится — только
    дословная формулировка «счётчик не движется» в detail.

    Полное удаление самого контура (`task_counters`, `seed_task_counters`,
    `next_task_number`/`peek_task_number`) — отдельная мелочь после M1
    (SPEC «Не входит»); эта функция лишь перестаёт его блокирующе
    сверять. Прежний incident-алерт мог остаться открытым от прогона
    до этой задачи — авто-ack безусловно закрывает его (условие
    «ещё живо» теперь всегда `False`).
    """
    try:
        declared = doctor.targets.load()
    except doctor.targets.TargetsError:
        declared = {}
    checked_targets = ({doctor.config.DEFAULT_TARGET} | doctor.store.counter_targets(conn)
                       | set(declared))
    for target in sorted(checked_targets):
        doctor._auto_ack_gone(conn, "doctor.task_counter", lambda _msg: False,
                      target=target)
    return doctor.Check("task-counters", "ok",
                 "счётчик номеров задач заморожен как legacy (ULID — "
                 "основной генератор, SPEC T094) — счётчик не движется")


def check_pending_snapshots(conn) -> list[doctor.Check]:
    """Дожимает недоставленные снапшоты закрытия (SPEC T094, требование
    13, AC-15): задачи `done`/`killed` внешнего target'а, не канарейка,
    чья артефактная ветка пульта ещё жива — снапшот не подтверждён в
    origin целевого. Каждый прогон `doctor` пробует push заново; успех
    убирает ветку тем же путём, что и повторный `kill`."""
    checks = []
    for row in doctor.store.closed_external_tasks(conn):
        task_id = row["id"]
        target = row["target"] or doctor.config.DEFAULT_TARGET
        if not doctor.snapshot.pending(task_id):
            continue
        state = doctor.store.get_task(conn, task_id)["state"]
        note = doctor.snapshot.publish_and_cleanup(conn, task_id, target, state)
        status = "ok" if "опубликован" in note else "warn"
        checks.append(doctor.Check(f"snapshot-pending:{task_id}", status, note))
    return checks


def check_remote_empty(target: str) -> doctor.Check:
    """Единая логика для ЛЮБОГО объявленного target, включая артель (A7,
    требование 2, AC-2): артефактный репозиторий `.artel/projects/
    <target>/` — не клон целевого форджа, у него нет причин нести
    remote, независимо от того, что сам target объявляет своим
    настоящим GitHub-репозиторием."""
    if not (doctor.config.PROJECTS / target / ".git").is_dir():
        return doctor.Check("remote-empty", "skip",
                     f"артефактный репо {target} не инициализирован")
    if doctor.projects.artifact_repo_has_no_remote(target):
        return doctor.Check("remote-empty", "ok", "remote пуст")
    return doctor.Check("remote-empty", "fail",
                 f"у артефактного репо {target} есть remote — "
                 f"нарушение периметра (ADR-0003 3д)")


def check_base_branch(name: str, entry: dict) -> doctor.Check:
    """Сверка базовой ветки/merge-политики — по возможностям forge, иначе
    честный skip с причиной (SPEC требование 9 явно это допускает).
    Единая логика для ЛЮБОГО объявленного target, включая артель (A7,
    требование 2, AC-2)."""
    if entry.get("forge") != "github":
        return doctor.Check("base-branch", "skip",
                     f"forge {entry.get('forge')} — сверка не реализована")
    gh = doctor.shutil.which("gh")
    if gh is None:
        return doctor.Check("base-branch", "skip", "gh CLI не найден — сверка пропущена")
    try:
        res = doctor.subprocess.run(
            ["gh", "repo", "view", entry["url"], "--json", "defaultBranchRef",
             "-q", ".defaultBranchRef.name"],
            capture_output=True, text=True, timeout=doctor.config.GH_TIMEOUT_SEC)
    except (OSError, doctor.subprocess.TimeoutExpired) as exc:
        return doctor.Check("base-branch", "skip", f"gh не ответил: {exc}")
    if res.returncode != 0:
        return doctor.Check("base-branch", "skip",
                     f"gh repo view отказал: {res.stderr.strip()[:200]}")
    remote_base = res.stdout.strip()
    if not remote_base:
        return doctor.Check("base-branch", "skip", "gh не вернул defaultBranchRef")
    if remote_base != entry["base"]:
        return doctor.Check("base-branch", "warn",
                     f"targets.yaml base={entry['base']!r}, у форджа "
                     f"{remote_base!r}")
    return doctor.Check("base-branch", "ok", f"база сходится: {remote_base}")


