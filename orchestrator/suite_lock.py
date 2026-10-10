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
import sqlite3
import sys
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


def directory() -> Path:
    """Каталог замка и хозяйства `suite-run` — единственный каталог пульта,
    который шаг роли на Codex получает на запись (`--add-dir`, SPEC
    01M4KG7VHHXTVTW5TTX2PGY5RY, требование 2)."""
    return config.LOGS / "suite-run"


def path() -> Path:
    """Файл замка — функция, не константа: `config.LOGS` подменяют тесты."""
    return directory() / "lock.json"


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
    # Ждут замок гейты и `notes` — процессы пульта с правом записи в БД:
    # здесь они досылают журнал прогонов роли без такого права.
    deliver_journal()
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


def holder() -> dict | None:
    """Запись замка как есть (держатель может быть и мёртв); `None` —
    замка нет или он нечитаем."""
    return _read()


def held_by_me() -> bool:
    """Замок держит текущий процесс: прогон внутри уже взятого замка
    (фоновый процесс `suite-run`) идёт без второго взятия."""
    holder = _read()
    return holder is not None and holder.get("pid") == os.getpid()


def my_task_id() -> str | None:
    """Задача прогона, чей замок держит текущий процесс (гейт, фоновый
    процесс `suite-run`); `None` — замок не за этим процессом либо прогон
    без задачи (`notes`). По ней сигнал «длительность близка к пределу»
    находит журнал задачи, не меняя сигнатур вызова прогона."""
    holder = _read()
    if holder is None or holder.get("pid") != os.getpid():
        return None
    return holder.get("task_id") or None


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


# ------------------------------------------------- отложенные записи журнала
#
# Процесс роли на Codex пишет только в рабочий каталог, каталог документов
# и каталог `suite-run`, БД пульта ему недоступна (SPEC
# 01M4KG7VHHXTVTW5TTX2PGY5RY, требование 3). Запись журнала задачи, не
# удавшаяся его прогону, ложится файлом сюда, а пишет её в журнал первый
# процесс с правом записи: команда `suite-run` и ожидание замка гейтом.
#
# Файлы очереди пишет процесс роли — это данные, не доверенный канал: досыл
# принимает только действия закрытого перечня (`deferrable`), автора ставит
# сам и режет текст. Иначе роль подложила бы запись, которой верят гейты
# («объявлена смена поведения тестов», «двусторонний прогон пройден») от
# имени Оператора (REVIEW итерации 1, R1-F1).

DEFERRED_ACTOR = "orchestrator"
# Потолок текста досылаемой записи: сигнал «близко к пределу» — одна строка
# с нагрузкой машины, длиннее ему быть незачем.
DEFERRED_DETAIL_MAX = 2000


def deferrable(action) -> bool:
    """Действие журнала, которое вправе прийти из очереди: только то, что
    пишет полный прогон `suite-run` у предела. «Прогон: время»
    (`acceptance.SUITE_DURATION_ACTION`) прогон `suite-run` не пишет, а
    калибровку `doctor` по нему подменять ролью незачем."""
    from . import acceptance  # acceptance -> suite_lock
    return action == acceptance.SUITE_NEAR_LIMIT_ACTION


def _pending_dir() -> Path:
    return directory() / "pending-journal"


def defer_journal(record: dict) -> bool:
    """Откладывает запись журнала (`task_id`, `action`, `detail`,
    `session_id`, `at`): отдельный файл на запись, атомарно — досылающий не
    прочтёт половину файла. Действие вне `deferrable` не откладывается
    (`False`): досыл его всё равно выбросит."""
    if not deferrable(record.get("action")):
        return False
    folder = _pending_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{time.time_ns()}-{os.getpid()}"
    tmp = folder / f".{name}.tmp"
    tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    tmp.replace(folder / f"{name}.json")
    return True


def _deferred_text(record: dict) -> tuple[str, str]:
    """Задача и текст досылаемой записи; `ValueError` — запись не из
    перечня или не той формы."""
    if not deferrable(record.get("action")):
        raise ValueError(f"действие вне перечня: {record.get('action')!r}")
    task_id, detail, at = record["task_id"], record["detail"], record["at"]
    if not all(isinstance(value, str) for value in (task_id, detail, at)):
        raise ValueError("поля записи — не строки")
    if len(detail) > DEFERRED_DETAIL_MAX:
        detail = detail[:DEFERRED_DETAIL_MAX] + "…"
    return task_id, (f"{detail} [дослано процессом пульта: запись прогона "
                     f"без права записи в БД от {at[:40]}]")


def deliver_journal() -> int:
    """Досылает отложенные записи в журнал их задач; число досланных. Файл
    забирается переименованием — два досылающих одну запись дважды не
    напишут; не удалась запись в БД — файл возвращается до следующего раза.
    Сбой досыла ничего не роняет: досыл — не условие прогона или команды.
    Нечитаемый файл, запись вне перечня `deferrable` и запись о задаче,
    которой в БД нет, убираются: писать их некуда (или нельзя), а возврат
    повторял бы их вечно. Выброшенная запись вне перечня называется в
    stderr — подложенный файл не исчезает бесследно."""
    claimed = []
    with contextlib.suppress(OSError):
        for pending in sorted(_pending_dir().glob("*.json")):
            mine = pending.with_name(f"{pending.name}.{os.getpid()}.claimed")
            with contextlib.suppress(OSError):
                pending.rename(mine)
                claimed.append((pending, mine))
    if not claimed:
        return 0
    from . import store  # store -> ... -> acceptance -> suite_lock
    try:
        conn = store.db()
    except (sqlite3.Error, OSError):
        conn = None
    try:
        return _deliver(store, conn, claimed)
    finally:
        if conn is not None:
            conn.close()


def _deliver(store, conn, claimed: list) -> int:
    delivered = 0
    for pending, mine in claimed:
        try:
            record = json.loads(mine.read_text(encoding="utf-8"))
            task_id, text = _deferred_text(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"suite-run: отложенная запись журнала {pending.name} "
                  f"выброшена: {exc}", file=sys.stderr)
            with contextlib.suppress(OSError):
                mine.unlink()
            continue
        session_id = record.get("session_id")
        try:
            if conn is None:
                raise sqlite3.OperationalError("БД пульта не открылась")
            if store.task_exists(conn, task_id):
                store.journal(conn, task_id, DEFERRED_ACTOR, record["action"],
                              text, session_id=(session_id
                                                if isinstance(session_id, str)
                                                else None))
                delivered += 1
        except sqlite3.Error:
            with contextlib.suppress(OSError):
                mine.rename(pending)
            continue
        with contextlib.suppress(OSError):
            mine.unlink()
    return delivered


def describe(holder: dict) -> str:
    """Держатель словами — для отказа и записи об ожидании: «suite-run
    задачи <id> (pid N)», «гейта задачи <id> (pid N)», «notes (pid N)»."""
    pid = holder.get("pid")
    kind = holder.get("kind", KIND_SUITE_RUN)
    if kind == KIND_NOTES:
        return f"notes (pid {pid})"
    what = "гейта" if kind == KIND_GATE else KIND_SUITE_RUN
    return f"{what} задачи {holder.get('task_id')} (pid {pid})"
