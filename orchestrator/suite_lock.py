"""Замок полных прогонов `tests/` машины: одновременно идёт не больше
одного полного прогона (SPEC 01M46D5T8SZ9D6S34TZFX8S46V, требование 1).

05.10 гейт мержа и автогейт приёмки гоняли полный набор с `-n auto`
одновременно; прогон мержа дошёл до 99% и был оборван пределом времени.
Правило «один прогон на машину» живёт здесь одно на все полные прогоны
пульта: гейты и `notes` берут замок в `acceptance.run_full_suite` и ждут
его (`wait_acquire`), `suite-run` берёт его без ожидания и при занятом
отказывает сразу (SPEC 01M462QACEH29RPRD2RZHGHQFM, требование 13 — её
замок стал частным случаем этого).

Замок — файл с pid держателя: создание `O_EXCL` атомарно, замок процесса,
которого больше нет, снимается и берётся заново (требование 4). Путь —
прежний путь замка `suite-run`: идущий на момент обновления пульта прогон
`suite-run` остаётся виден гейтам.
"""
import contextlib
import json
import os
import time
from pathlib import Path

from . import config, liveness

KIND_SUITE_RUN = "suite-run"
KIND_GATE = "гейт"
KIND_NOTES = "notes"

# Замок, только что созданный соседом, ещё может быть пуст: столько секунд
# пустой файл считается занятым, а не брошенным.
FRESH_SEC = 5
# Шаг опроса замка ожидающим прогоном.
POLL_SEC = 1.0

_UNKNOWN = {"task_id": "?", "pid": "?"}


def path() -> Path:
    """Файл замка — функция, не константа: `config.LOGS` подменяют тесты."""
    return config.LOGS / "suite-run" / "lock.json"


def _read() -> dict | None:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write(data: dict) -> None:
    """Запись через временный файл и `replace`: читатель не увидит
    половину файла."""
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)


def _alive(pid) -> bool:
    try:
        return liveness._pid_alive(int(pid))
    except (TypeError, ValueError):
        return False


def _fresh(lock: Path) -> bool:
    try:
        return time.time() - lock.stat().st_mtime < FRESH_SEC
    except OSError:
        return False


def _payload(task_id, run, pid: int, kind: str) -> dict:
    # Запись `suite-run` — прежней формы (задача, pid, номер прогона):
    # вид держателя пишется только у прогонов гейтов и `notes`.
    data = {"task_id": task_id, "pid": pid, "run": run}
    if kind != KIND_SUITE_RUN:
        data["kind"] = kind
    return data


def acquire(task_id, run=None, kind: str = KIND_SUITE_RUN) -> dict | None:
    """Замок за текущим процессом: `None` — взят, иначе держатель (без
    ожидания). Брошенный замок (pid мёртв) снимается и берётся заново."""
    lock = path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_payload(task_id, run, os.getpid(), kind),
                         ensure_ascii=False)
    for _ in range(3):
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            holder = _read()
            if holder is not None and _alive(holder.get("pid")):
                return holder
            if holder is None and _fresh(lock):
                return dict(_UNKNOWN)
            with contextlib.suppress(FileNotFoundError):
                lock.unlink()
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        return None
    return _read() or dict(_UNKNOWN)


def wait_acquire(task_id, kind: str, limit_sec: float,
                 on_wait) -> dict | None:
    """Замок с ожиданием не дольше `limit_sec` секунд: `None` — взят,
    иначе держатель на момент истечения предела. `on_wait(holder)`
    зовётся на первом занятом замке и на каждой смене держателя."""
    deadline = time.monotonic() + limit_sec
    seen = None
    while True:
        holder = acquire(task_id, kind=kind)
        if holder is None:
            return None
        key = (holder.get("task_id"), holder.get("pid"))
        if key != seen:
            seen = key
            on_wait(holder)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return holder
        time.sleep(min(POLL_SEC, remaining))


def held_by_me() -> bool:
    """Замок держит текущий процесс: прогон внутри уже взятого замка
    (фоновый процесс `suite-run`) идёт без второго взятия."""
    holder = _read()
    return holder is not None and holder.get("pid") == os.getpid()


def hand(task_id, run, pid: int) -> None:
    """Замок, взятый процессом команды `suite-run`, — за её фоновым
    процессом: держателем становится `pid`, задача и номер прогона те же."""
    _write(_payload(task_id, run, pid, KIND_SUITE_RUN))


def adopt(task_id, run) -> dict | None:
    """Фоновый процесс `suite-run` принимает замок, переданный ему
    командой (тот же id задачи и номер прогона), — `None`; замка для него
    нет — берёт сам (`acquire`): вызов в обход команды."""
    holder = _read()
    if (holder is not None and holder.get("task_id") == task_id
            and holder.get("run") == run):
        hand(task_id, run, os.getpid())
        return None
    return acquire(task_id, run)


def release() -> None:
    """Снимает замок текущего процесса; чужой замок не трогается."""
    holder = _read()
    if holder is not None and holder.get("pid") == os.getpid():
        with contextlib.suppress(FileNotFoundError):
            path().unlink()


def describe(holder: dict) -> str:
    """Держатель словами — для отказа и записи об ожидании: «suite-run
    задачи <id> (pid N)», «гейта задачи <id> (pid N)», «notes (pid N)»."""
    pid = holder.get("pid")
    kind = holder.get("kind", KIND_SUITE_RUN)
    if kind == KIND_NOTES:
        return f"notes (pid {pid})"
    what = "гейта" if kind == KIND_GATE else KIND_SUITE_RUN
    return f"{what} задачи {holder.get('task_id')} (pid {pid})"
