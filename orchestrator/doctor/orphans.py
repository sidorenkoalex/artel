"""Пакет orchestrator/doctor -- сироты: каталоги без строки БД, ветки done/killed, worktree.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import tempfile

from orchestrator import doctor, fsm


# --- сироты (требование 8) ----------------------------------------------

def _is_legit_task_worktree(wt_path: str, known_ids: set) -> bool:
    """Легитимная рабочая копия задачи (SPEC T045, AC-9; ADR-0021 п.1):
    лежит ровно в `.artel/projects/<имя>/worktrees/<id>`, и `<id>` —
    известная задача. Иначе (чужое место, неизвестная задача) — сирота по
    построению."""
    p = Path(wt_path).resolve()
    projects = doctor.config.PROJECTS.resolve()
    return (p.parent.name == "worktrees" and p.parent.parent.parent == projects
            and p.name in known_ids)


def _project_clones() -> list:
    """Существующие клоны проектов `targets.yaml` (ADR-0021 п.1)."""
    try:
        names = list(doctor.targets.load())
    except doctor.targets.TargetsError:
        return []
    return [doctor.workspace.repo(n) for n in names
            if doctor.workspace.repo(n).exists()]


def _orphan_worktrees(known_ids: set) -> list[str]:
    # Первая запись `workspace.registered_paths(clone)` — сам клон, не
    # рабочая копия ни одной задачи.
    paths = [p for clone in _project_clones()
             for p in doctor.workspace.registered_paths(clone)[1:]]
    return [p for p in paths if not doctor._is_legit_task_worktree(p, known_ids)]


def _canary_temp_directory(cwd: str) -> Path | None:
    """Верхний временный каталог известного вида для cwd процесса."""
    root = Path(tempfile.gettempdir()).resolve()
    try:
        relative = Path(cwd).resolve().relative_to(root)
    except (OSError, ValueError):
        return None
    if not relative.parts:
        return None
    name = relative.parts[0]
    if name.startswith(("artel-canary-", "artel-suite-base-")):
        return root / name
    return None


def _live_suite_run_in(path: Path) -> bool:
    # У старого holder нет маркера. Его защищает только прогон, чей pid
    # живёт именно в этом каталоге; чужой run.json не устанавливает связь.
    for run_path in (doctor.config.LOGS / "suite-run").glob("*/run.json"):
        try:
            pid = int(doctor.json.loads(run_path.read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if pid <= 0 or not doctor.liveness._pid_alive(pid):
            continue
        # PATH роли урезан до объявленных инструментов; системный lsof
        # macOS остаётся доступен по абсолютному пути.
        lsof = "/usr/sbin/lsof" if Path("/usr/sbin/lsof").is_file() else "lsof"
        cwd = doctor._process_cwd(pid, executable=lsof)
        if cwd is None:
            continue
        try:
            if Path(cwd).resolve().is_relative_to(path.resolve()):
                return True
        except OSError:
            continue
    return False


# Каталоги выписок гейтов исходов и двустороннего прогона (SPEC
# 01M5FRYVP4NF81VT00FYPHPWJH, требование 6): их записи `git worktree`
# живут в клонах проектов.
GATE_TEMP_PREFIXES = ("artel-outcome-", "artel-two-sided-")


def _temp_owner_alive(path: Path) -> bool:
    # Владелец выписки — только маркер гейта: живой маркер канарейки в
    # таком каталоге его не заменяет.
    if path.name.startswith(GATE_TEMP_PREFIXES):
        return doctor.liveness.owner_alive(path,
                                           doctor.liveness.GATE_OWNER_MARKER)
    if path.name.startswith("artel-canary-origin-"):
        marker_alive = doctor.liveness.owner_alive(path)
        # До записи remote URL origin защищает собственный маркер. После
        # появления связи владельцем считается клон, указавший этот origin.
        for candidate in path.parent.glob("artel-canary-*"):
            if candidate.name.startswith("artel-canary-origin-"):
                continue
            try:
                config_text = (candidate / ".git" / "config").read_text(
                    encoding="utf-8")
            except OSError:
                continue
            if str(path) in config_text:
                return doctor.liveness.owner_alive(candidate)
        return marker_alive
    if doctor.liveness.owner_alive(path):
        return True
    if path.name.startswith("artel-suite-base-"):
        return (doctor.liveness.owner_alive(path, doctor.liveness.SUITE_OWNER_MARKER)
                or _live_suite_run_in(path))
    return False


def _orphan_temp_dirs() -> list[Path]:
    root = Path(tempfile.gettempdir())
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return []
    return [entry for entry in entries
            if entry.is_dir() and not entry.is_symlink()
            and entry.name.startswith(("artel-canary-", "artel-suite-base-",
                                       *GATE_TEMP_PREFIXES))
            and not _temp_owner_alive(entry)]


def _fix_orphan_temp_dirs() -> None:
    # Origin проверяется до удаления связанного клона: после удаления
    # config клона исчезнет, а устаревший маркер origin скроет сироту.
    entries = sorted(_orphan_temp_dirs(),
                     key=lambda p: (not p.name.startswith("artel-canary-origin-"),
                                    str(p)))
    gate_removed = False
    for entry in entries:
        # Повторная проверка сужает окно между наблюдением и удалением.
        if not _temp_owner_alive(entry):
            doctor.shutil.rmtree(entry, ignore_errors=True)
            print(f"  [FIX] временный каталог-сирота удалён: {entry}")
            gate_removed |= entry.name.startswith(GATE_TEMP_PREFIXES)
    # Запись `git worktree` удалённой выписки иначе остаётся в клоне; без
    # удалённых выписок клоны не трогаются вовсе.
    if gate_removed:
        for clone in _project_clones():
            res = doctor.gitcmd.in_repo(clone, "worktree", "prune")
            if res is None or res.returncode != 0:
                print(f"  [FIX] git worktree prune в {clone} не удался: "
                      f"{(res.stderr or '').strip() if res else 'git не ответил'}")


def check_orphans(conn) -> list[doctor.Check]:
    """Требование 8: три под-проверки; каждый найденный факт — incident-алерт."""
    results = []

    known_ids = {r["id"] for r in doctor.store.all_tasks(conn)}
    # Исторический tasks/ пульта сканируется БЕЗ ИЗМЕНЕНИЙ (требование 3
    # SPEC A7) вдобавок к артефактному каталогу КАЖДОГО объявленного
    # target, включая артель — она больше не исключается по имени
    # (A7, требование 2, AC-4): новые задачи артели ведут первичку в
    # `.artel/projects/artel/tasks/`, тем же путём, что и любой другой
    # target.
    scan = [(doctor.config.DEFAULT_TARGET, doctor.config.TASKS)]
    try:
        for name in doctor.targets.load():
            scan.append((name, doctor.config.PROJECTS / name / "tasks"))
    except doctor.targets.TargetsError:
        pass  # сломанный targets.yaml — забота другой проверки doctor'а
    orphan_dirs = [
        (target_name, entry)
        for target_name, tasks_dir in scan if tasks_dir.is_dir()
        for entry in sorted(tasks_dir.iterdir())
        if entry.is_dir() and entry.name not in known_ids
    ]
    if orphan_dirs:
        for target_name, entry in orphan_dirs:
            doctor.alerts.raise_alert(conn, target_name, "incident", "doctor.orphans.dir",
                              f"{entry} без строки БД")
        results.append(doctor.Check("orphans-dirs", "fail",
                            "; ".join(str(e) for _, e in orphan_dirs)))
    else:
        results.append(doctor.Check("orphans-dirs", "ok", "нет каталогов без строки БД"))
    doctor._auto_ack_gone(conn, "doctor.orphans.dir",
                  lambda msg: doctor._dir_alert_live(msg, known_ids))

    stale = [r for r in doctor.store.all_tasks(conn)
            if r["state"] in fsm.TERMINAL_STATES and r["branch"]
            and doctor.gitcmd.branch_exists(
                r["branch"], repo=doctor.workspace.repo(
                    r["target"] or doctor.config.DEFAULT_TARGET))]
    if stale:
        for r in stale:
            doctor.alerts.raise_alert(conn, r["target"] or doctor.config.DEFAULT_TARGET,
                              "incident", "doctor.orphans.branch",
                              f"{r['id']} ({r['state']}): ветка {r['branch']} "
                              f"не убрана")
        results.append(doctor.Check("orphans-branches", "fail",
                            "; ".join(f"{r['id']}:{r['branch']}" for r in stale)))
    else:
        results.append(doctor.Check("orphans-branches", "ok", "нет веток done/killed задач"))
    doctor._auto_ack_gone(conn, "doctor.orphans.branch", doctor._branch_alert_live)

    orphan_worktrees = doctor._orphan_worktrees(known_ids)
    if orphan_worktrees:
        for path in orphan_worktrees:
            doctor.alerts.raise_alert(conn, doctor.config.DEFAULT_TARGET, "incident",
                              "doctor.orphans.worktree", f"worktree {path} без задачи")
        results.append(doctor.Check("orphans-worktrees", "fail",
                            "; ".join(orphan_worktrees)))
    else:
        results.append(doctor.Check("orphans-worktrees", "ok", "лишних worktree нет"))
    current_worktree_paths = set(orphan_worktrees)
    doctor._auto_ack_gone(conn, "doctor.orphans.worktree",
                  lambda msg: doctor._worktree_alert_live(msg, current_worktree_paths))

    temporary = _orphan_temp_dirs()
    if temporary:
        for entry in temporary:
            doctor.alerts.raise_alert(conn, None, "incident", "doctor.orphans.temp",
                                      f"{entry} без живого владельца")
        results.append(doctor.Check("orphans-temp", "fail",
                                    "; ".join(str(p) for p in temporary)))
    else:
        results.append(doctor.Check("orphans-temp", "ok",
                                    "временных каталогов-сирот нет"))
    current = {str(p) for p in temporary}
    doctor._auto_ack_gone(conn, "doctor.orphans.temp",
                          lambda msg: msg.removesuffix(" без живого владельца")
                          in current)
    return results


# --- забытые стенды Compose (SPEC 01M6PAJ61DP2R2CMM71PJ8W0KF, требование 14)
#
# Предмет строки — только стенды Docker: каталоги пульта под `.artel/` она не
# обходит. Стенд пульта — проект Compose формы части 1
# (`acceptance.compose_project_name`) с хотя бы одной меткой живого прогона.

COMPOSE_STANDS_CHECK = "compose-stands"
_COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
_STAND_NAME_RE = re.compile(r"artel-[0-9a-z]{26}-[0-9a-f]{8}")
# Формат `store.now()`: проверяется до `strptime`, чужой формат — порча меток.
_RUN_STARTED_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z")
STANDS_REMOTE = "демон Docker не локальный"
STANDS_NOT_ANSWERING = "Docker не отвечает"
STANDS_LAYER_BROKEN = "слой проектов не прочитан"
STANDS_LABELS_BROKEN = "метки стенда не разобраны"


def _docker_labels(text) -> dict:
    """Поле `Labels` Docker — `ключ=значение` через запятую; фрагмент без
    `=` — продолжение значения предыдущей метки (значение с запятой)."""
    labels, last = {}, None
    for part in (text or "").split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            labels[key] = value
            last = key
        elif last is not None:
            labels[last] += "," + part
    return labels


def _run_verdict(run: dict) -> str:
    """`broken` | `alive` | `dead` по меткам `artel.run-*` ресурса стенда.
    Имя хоста на живость не влияет: имя хоста macOS меняется со сетью."""
    pid_label, _host_label, started_label = doctor.acceptance.COMPOSE_RUN_LABELS
    if any(label not in run for label in doctor.acceptance.COMPOSE_RUN_LABELS):
        return "broken"
    pid_text, started_text = run[pid_label], run[started_label]
    if not re.fullmatch(r"\d+", pid_text) or int(pid_text) <= 0 \
            or not _RUN_STARTED_RE.fullmatch(started_text):
        return "broken"
    try:
        recorded = datetime.strptime(started_text, "%Y-%m-%d %H:%M:%SZ"
                                     ).replace(tzinfo=timezone.utc)
    except ValueError:
        return "broken"
    pid = int(pid_text)
    if not doctor.liveness._pid_alive(pid):
        return "dead"
    started = doctor.process_start_time(pid)
    if started is None or started > recorded:
        return "dead"
    return "alive"


def _has_compose_project(declared) -> bool:
    for project in declared:
        try:
            comps = doctor.project_profile.components(project)
        except doctor.targets.TargetsError:
            continue
        if any(c.fields.get("runner") == doctor.targets.PROFILE_RUNNER_COMPOSE
               for c in comps):
            return True
    return False


def _stands_survey():
    """(строка, мёртвые стенды {проект: имена ресурсов}, docker, окружение
    вызова). Мёртвые стенды непусты, только если Docker опрошен."""
    def done(status, detail):
        return doctor.Check(COMPOSE_STANDS_CHECK, status, detail), {}, None, None
    project_checks = doctor.project_checks
    if doctor.runner.in_role_environment():
        return done("skip", project_checks.DOCKER_ROLE_SKIP)
    try:
        declared = doctor.targets.load()
    except doctor.targets.TargetsError as exc:
        return done("warn", f"{STANDS_LAYER_BROKEN}: {exc}")
    if not _has_compose_project(declared):
        return done("skip", "нет проектов с раннером compose")
    docker = doctor.acceptance.find_docker()
    if docker is None:
        return done("warn", project_checks.DOCKER_NOT_FOUND)
    env = doctor.acceptance.compose_env(None, docker)

    def ask(argv):
        timeout = project_checks.DOCKER_CALL_TIMEOUT_SEC
        code, out, err = project_checks._docker_call(argv, env, None, timeout)
        return out, project_checks._call_failure(argv, code, out, err, timeout)
    host = os.environ.get("DOCKER_HOST") or ""
    if not host:
        out, failure = ask([docker, "context", "inspect", "--format",
                            "{{.Endpoints.docker.Host}}"])
        if failure is not None:
            return done("warn", f"{STANDS_NOT_ANSWERING}: {failure}")
        host = out.strip()
    if not host.startswith("unix://"):
        return done("skip", f"{STANDS_REMOTE} ({host or 'адрес пуст'}) — "
                            f"живость прогона по pid не решается")
    records = []
    for argv, key in (([docker, "ps", "-a"], "Names"),
                      ([docker, "network", "ls"], "Name")):
        out, failure = ask([*argv, "--filter",
                            f"label={_COMPOSE_PROJECT_LABEL}",
                            "--format", "{{json .}}"])
        if failure is not None:
            return done("warn", f"{STANDS_NOT_ANSWERING}: {failure}")
        for line in out.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append((str(record.get(key) or ""),
                                _docker_labels(record.get("Labels"))))
    resources, verdicts = {}, {}
    for name, labels in records:
        project = labels.get(_COMPOSE_PROJECT_LABEL, "")
        if not _STAND_NAME_RE.fullmatch(project):
            continue
        resources.setdefault(project, []).append(name)
        run = {k: labels[k] for k in doctor.acceptance.COMPOSE_RUN_LABELS
               if k in labels}
        if run:
            verdicts.setdefault(project, set()).add(_run_verdict(run))
    broken = sorted(p for p, v in verdicts.items() if "broken" in v)
    dead = {p: resources[p] for p, v in sorted(verdicts.items())
            if v == {"dead"}}
    parts = [f"забытый стенд {p}: {', '.join(names)}"
             for p, names in dead.items()]
    if dead:
        parts.append("снимет doctor --fix (down --remove-orphans, тома "
                     "остаются)")
    if broken:
        parts.append(f"{STANDS_LABELS_BROKEN}: {', '.join(broken)} — --fix "
                     f"их не снимает")
    if parts:
        return (doctor.Check(COMPOSE_STANDS_CHECK, "warn", "; ".join(parts)),
                dead, docker, env)
    return (doctor.Check(COMPOSE_STANDS_CHECK, "ok", "забытых стендов нет"),
            {}, docker, env)


def check_compose_stands(conn) -> doctor.Check:
    """Строка «забытые стенды пульта» (требование 14): только чтение."""
    return _stands_survey()[0]


def _fix_compose_stands(conn) -> None:
    """`docker compose --project-name <имя> down --remove-orphans` на каждый
    забытый стенд — без `-v` и `-f`, в пустом временном каталоге, чтобы
    Compose не прочитал посторонний Compose-файл. Без соединения с БД
    (`cmd_doctor` зовёт починки безусловно) — ничего."""
    if conn is None:
        return
    _check, dead, docker, env = _stands_survey()
    for project in dead:
        argv = [docker, "compose", "--project-name", project, "down",
                "--remove-orphans"]
        timeout = doctor.config.COMPOSE_TEARDOWN_TIMEOUT_SEC
        empty = tempfile.mkdtemp(prefix="artel-compose-down-")
        try:
            code, out, err = doctor.project_checks._docker_call(
                argv, env, empty, timeout)
        finally:
            doctor.shutil.rmtree(empty, ignore_errors=True)
        failure = doctor.project_checks._call_failure(argv, code, out, err,
                                                      timeout)
        if failure is None:
            print(f"  [FIX] забытый стенд compose снят: {project}")
        else:
            print(f"  [FIX] забытый стенд compose не снят: {failure}")
