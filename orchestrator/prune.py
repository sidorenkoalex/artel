"""Команда `prune`: исполняет retention-политику docs/retention.md для
`.artel/logs/` и `alerts` (tasks/T073/SPEC.md, требование 3).

Не часть уборки `kill`/`done` (`orchestrator/cleanup.py`) и не реагирует
на переход FSM ни одной задачи — отдельная, явно вызываемая Оператором
операция над всем `.artel/logs/`/`alerts` сразу (инвариант 16,
docs/invariants.md, не ослабляется: уборка ОДНОЙ задачи логи по-прежнему
не трогает — уточнение см. tasks/T073/PLAN.md, «Подход», п.5).

dry-run по умолчанию (`execute=False`): план и факт считаются одним и
тем же расчётом кандидатов — различается только то, исполняется ли
действие (удаление файла / `store.archive_alert`), отчёт печатает
конкретные имена в обоих режимах (AC-7).
"""
import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, gitcmd, idgen, liveness, store, suite_lock


_CLOSE_ACTIONS = ("state -> done", "state -> killed")


def _close_ts(conn, task_id: str) -> str | None:
    """Момент закрытия задачи из журнала (`store.now()`, `%Y-%m-%d
    %H:%M:%SZ` — ширина фиксирована, лексикографическое сравнение строк
    совпадает с хронологическим); `None` — задача ещё не закрыта."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] in _CLOSE_ACTIONS:
            return row["ts"]
    return None


def _kept_task_ids(conn) -> set:
    """id последних `config.LOG_RETENTION_KEEP_TASKS` ЗАКРЫТЫХ задач по
    дате закрытия из журнала (SPEC T094, требование 5, AC-6) — не по
    числовому номеру: ULID id не несёт сравнимого по величине номера
    (требование 2), а `Tnnn`-задачи участвуют в этом же датовом отборе,
    не в отдельном отборе «последние N по номеру». Ещё не закрытая
    задача (нет записи `state -> done`/`state -> killed`) не участвует в
    датовом ранжировании вовсе — её логи retention не трогает независимо
    от возраста, тем же принципом, что и раньше для «последних N»."""
    closed: list[tuple[str, str]] = []
    open_ids: set = set()
    for row in store.all_tasks(conn):
        ts = _close_ts(conn, row["id"])
        if ts is None:
            open_ids.add(row["id"])
        else:
            closed.append((ts, row["id"]))
    closed.sort(reverse=True)
    kept_closed = {task_id for _, task_id in closed[:config.LOG_RETENTION_KEEP_TASKS]}
    return open_ids | kept_closed


_LOG_SUFFIXES = (".log", ".prompt.txt")

# Каталоги механизмов, которых в коде пульта больше нет, — пути от корня
# пульта (SPEC 01M5KBQGMZ051ENRVS8F42MA4V, требование 3).
ABOLISHED_DIRS = (".artel/notes-work",)


def _log_candidates(conn) -> list:
    """Файлы верхнего уровня `.artel/logs/` — логи `*.log` и промпты
    `*.prompt.txt` (SPEC 01M5KBQGMZ051ENRVS8F42MA4V, требование 1),
    ОДНОВРЕМЕННО старше `config.LOG_RETENTION_DAYS` И вне «последних N»
    (AC-5)."""
    if not config.LOGS.is_dir():
        return []
    kept = _kept_task_ids(conn)
    cutoff = time.time() - config.LOG_RETENTION_DAYS * 86400
    candidates = []
    for path in sorted(config.LOGS.iterdir()):
        if not path.name.endswith(_LOG_SUFFIXES) or not path.is_file():
            continue
        task_id = path.name.split("-", 1)[0]
        if task_id in kept:
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        candidates.append(path)
    return candidates


def _tree_files(root: Path) -> list:
    """Файлы под `root` рекурсивно, без перехода по символическим ссылкам
    и без самих ссылок."""
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            if not path.is_symlink():
                files.append(path)
    return files


def _newest_mtime(root: Path, files: list) -> float:
    """Самый свежий mtime среди `files`; каталог без файлов — mtime самого
    каталога (требование 2)."""
    if not files:
        return root.lstat().st_mtime
    return max(path.lstat().st_mtime for path in files)


def _run_pid_alive(run_dir: Path) -> bool:
    """В `<run_dir>/run.json` — pid живого прогона; чтение pid то же, что
    у `doctor.orphans._live_suite_run_in`."""
    try:
        pid = int(json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return pid > 0 and liveness._pid_alive(pid)


def _suite_run_candidates(conn) -> list:
    """Подкаталоги `.artel/logs/suite-run/` с именем формы id задачи, чья
    задача вне `_kept_task_ids`, самый свежий файл старше
    `config.LOG_RETENTION_DAYS`, задача не держит замок и в `run.json` нет
    живого pid (SPEC 01M5KBQGMZ051ENRVS8F42MA4V, требование 2). `lock.json`
    и `pending-journal/` отсекает уже форма имени: в них нет id задачи."""
    root = suite_lock.directory()
    if not root.is_dir():
        return []
    kept = _kept_task_ids(conn)
    cutoff = time.time() - config.LOG_RETENTION_DAYS * 86400
    holder = suite_lock.holder() or {}
    candidates = []
    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_dir():
            continue
        if not idgen.is_task_id_form(path.name) or path.name in kept:
            continue
        if holder.get("task_id") == path.name:
            continue
        if _newest_mtime(path, _tree_files(path)) >= cutoff:
            continue
        if _run_pid_alive(path):
            continue
        candidates.append(path)
    return candidates


def _abolished_candidates() -> list:
    """Каталоги `ABOLISHED_DIRS`, которые есть на диске и не символические
    ссылки (требование 3): по ссылке не переходим, её цель не наша."""
    candidates = []
    for rel in ABOLISHED_DIRS:
        path = config.ROOT / rel
        if path.is_symlink() or not path.is_dir():
            continue
        candidates.append(path)
    return candidates


def _unsaved_work_reason(path: Path) -> str | None:
    """Причина оставить каталог упразднённого механизма; `None` — он корень
    собственного репозитория без несохранённой работы (требование 4).

    Сначала задаются все вопросы git, потом разбираются ответы: сбой
    любого вызова стоит в перечне причин раньше признаков работы, и
    пустой вывод упавшего вызова за чистоту не принимается. Вызовы только
    локальные — сверка с `origin` идёт по его ссылкам `refs/remotes/origin/*`
    без `fetch`."""
    if not (path / ".git").exists():
        return "не собственный репозиторий"
    questions = {
        "toplevel": ("rev-parse", "--show-toplevel"),
        "status": ("status", "--porcelain", "--ignored", "--untracked-files=all"),
        "unpushed": ("rev-list", "-n", "1", "--branches", "--not",
                     "--glob=refs/remotes/origin/*"),
        "stash": ("stash", "list"),
        "head": ("rev-parse", "--symbolic-full-name", "HEAD"),
    }
    answers = {}
    failure = None
    for key, args in questions.items():
        res = gitcmd.in_repo(path, *args)
        if res.returncode == 0:
            answers[key] = res.stdout
        elif failure is None:
            error = (res.stderr or res.stdout or "").strip()
            failure = f"git не ответил: {error or f'код {res.returncode}'}"
        if key == "toplevel" and key in answers:
            # Без своего репозитория `git -C` отвечает о репозитории выше
            # по дереву — остальные вопросы задавались бы уже ему.
            toplevel = answers[key].strip()
            if not toplevel or Path(toplevel).resolve() != path.resolve():
                return "не собственный репозиторий"
    if failure is not None:
        return failure
    entries = [line for line in answers["status"].splitlines() if line]
    if any(not line.startswith(("??", "!!")) for line in entries):
        return "незакоммиченные правки"
    if entries:
        return "неотслеживаемые или игнорируемые файлы"
    if answers["unpushed"].strip():
        return "коммиты вне origin"
    if answers["stash"].strip():
        return "непустой stash"
    if not answers["head"].strip().startswith("refs/heads/"):
        return "отделённый HEAD"
    return None


def _canary_diag_candidates() -> list:
    """Файлы `.artel/canary/**` старше `config.LOG_RETENTION_DAYS` (SPEC
    01M1TKP269W9JN3NBJCR5Q6C3B, требование 4/AC-9) — тот же порог
    давности, что и `.artel/logs/` выше, БЕЗ учёта «последних N закрытых
    задач»: канареечный `task_id` в имени пути — id задачи ЭФЕМЕРНОГО
    клона (`canary._ephemeral_clone`), уже уничтоженного к моменту
    `prune` и никогда не попадающего в `store.all_tasks` пульта, поэтому
    датовый отбор `_kept_task_ids` для него бессмыслен."""
    root = config.ROOT / ".artel" / "canary"
    if not root.is_dir():
        return []
    cutoff = time.time() - config.LOG_RETENTION_DAYS * 86400
    return [path for path in sorted(root.rglob("*"))
           if path.is_file() and path.stat().st_mtime < cutoff]


def _alert_cutoff_ts() -> str:
    when = datetime.now(timezone.utc) - timedelta(days=config.ALERT_ARCHIVE_DAYS)
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


def _alert_candidates(conn) -> list:
    """Alerts старше `config.ALERT_ARCHIVE_DAYS` — кандидаты архивации,
    любой `kind`, вне зависимости от `ack` (AC-6)."""
    return store.alerts_older_than(conn, _alert_cutoff_ts())


def _abolished_rel(path: Path) -> str:
    return path.relative_to(config.ROOT).as_posix()


def _print_report(mode: str, logs: list, alert_rows: list,
                  diag_files: list = (), suite_dirs: list = (),
                  abolished: list = (), abolished_left: list = ()) -> None:
    """`suite_dirs`/`abolished` — пары (каталог, число файлов),
    `abolished_left` — пары (каталог, причина «оставлено»)."""
    log_verb = "удалён" if mode == "исполнено" else "будет удалён"
    diag_verb = "убрана" if mode == "исполнено" else "будет убрана"
    alert_verb = "заархивирован" if mode == "исполнено" else "будет заархивирован"
    print(f"prune ({mode}):")
    if not (logs or alert_rows or diag_files or suite_dirs or abolished
            or abolished_left):
        print("  нечего убирать")
        return
    for path in logs:
        print(f"  лог {path.name} {log_verb}")
    for path, count in suite_dirs:
        print(f"  каталог suite-run {path.name} ({count} файлов) {log_verb}")
    for path, count in abolished:
        print(f"  каталог упразднённого механизма {_abolished_rel(path)} "
              f"({count} файлов) {log_verb}")
    for path, reason in abolished_left:
        print(f"  каталог упразднённого механизма {_abolished_rel(path)} "
              f"оставлено: {reason}")
    for path in diag_files:
        rel = path.relative_to(config.ROOT / ".artel" / "canary")
        print(f"  диагностика канарейки {rel} {diag_verb}")
    for row in alert_rows:
        print(f"  alert «{row['message']}» {alert_verb}")


def _remove_dirs(dirs: list, label) -> list:
    """Удаляет каталоги целиком (`shutil.rmtree` по ссылкам не ходит);
    сбой одного печатается строкой «не удалён» и не останавливает
    остальные. Возвращает удалённые пары (каталог, число файлов)."""
    removed = []
    for path, count in dirs:
        try:
            shutil.rmtree(path)
        except OSError as exc:
            print(f"  {label(path)} не удалён: {exc}")
            continue
        removed.append((path, count))
    return removed


def cmd_prune(execute: bool = False) -> None:
    """dry-run по умолчанию (AC-4): без `execute=True` ничего не удаляет
    и не архивирует, только печатает план. С `execute=True` (AC-5, AC-6)
    исполняет retention-политику `docs/retention.md` и печатает отчёт
    о фактически убранном (AC-7); AC-9 (01M1TKP269W9JN3NBJCR5Q6C3B) —
    та же политика давности для диагностики канарейки `.artel/canary/`;
    SPEC 01M5KBQGMZ051ENRVS8F42MA4V — промпты, каталоги `suite-run` и
    каталоги упразднённых механизмов."""
    conn = store.db()
    logs = _log_candidates(conn)
    suite_dirs = [(path, len(_tree_files(path)))
                  for path in _suite_run_candidates(conn)]
    abolished, abolished_left = [], []
    for path in _abolished_candidates():
        reason = _unsaved_work_reason(path)
        if reason is None:
            # Считается после вопросов git: они вправе обновить файлы `.git`.
            abolished.append((path, len(_tree_files(path))))
        else:
            abolished_left.append((path, reason))
    diag_files = _canary_diag_candidates()
    alert_rows = _alert_candidates(conn)

    if not execute:
        _print_report("план", logs, alert_rows, diag_files, suite_dirs,
                      abolished, abolished_left)
        return

    removed: list[Path] = []
    for path in logs:
        try:
            path.unlink()
        except OSError as exc:
            print(f"  лог {path.name} не удалён: {exc}")
            continue
        removed.append(path)

    removed_suite = _remove_dirs(
        suite_dirs, lambda path: f"каталог suite-run {path.name}")
    removed_abolished = _remove_dirs(
        abolished,
        lambda path: f"каталог упразднённого механизма {_abolished_rel(path)}")

    removed_diag: list[Path] = []
    for path in diag_files:
        try:
            path.unlink()
        except OSError as exc:
            print(f"  диагностика канарейки {path} не убрана: {exc}")
            continue
        removed_diag.append(path)

    archived = []
    for row in alert_rows:
        store.archive_alert(conn, row["id"])
        archived.append(row)

    _print_report("исполнено", removed, archived, removed_diag, removed_suite,
                  removed_abolished, abolished_left)
