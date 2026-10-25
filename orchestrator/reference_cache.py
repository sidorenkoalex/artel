"""Кэш справочника ядра проекта и единый вход К-3б `get_reference`.

Справочник собирает `scripts/core_reference.py` по исходникам коммита
ветки задачи в клоне проекта (SPEC 01M4S24963R9H18AN2XDP6R15B, К-3а):
пакетно — один `git ls-tree -r -l -z` и один `git cat-file --batch`, без
checkout и рабочего дерева; пределы и общий срок — константы
`config.CORE_REFERENCE_*`, проверяемые по размерам `ls-tree` ДО чтения
blob'ов.

Кэш — `<область проектов>/<проект>/knowledge/derived/core-reference.md`
(ADR-0003 п.3а, п.3б): карта кодовой базы лежит в git артели и коммитится
после мержа, а для внешнего проекта такой путь означал бы запись пульта в
чужой репозиторий; `knowledge/` — дом производных знаний вне git, не
трогает диффы мержа, гейт ёмкости и сторож главной копии; `derived/`
отделяет пересоздаваемое от курируемых карточек К-4а. Файл можно удалить
— следующая сборка его восстановит.

Потребители: бриф и шаг после мержа (`get_reference` по задаче), команда
пульта `reference <проект>` и `target-init` (`get_reference_for_target`
без задачи, повод `reference` — без алертов; SPEC
01M4TVBT9ZCRQDY669QV3S95MA). Порог использования — подполе `min_uses`
настройки проекта либо `config.CORE_REFERENCE_MIN_USES`, в сборке и в
сверке кэша одинаково: кэш с другим порогом не годен.
"""
import contextlib
import hashlib
import os
import re
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from scripts import core_reference

from . import alerts, config, gitcmd, repo_context, store, targets

CACHE_REL = Path("knowledge") / "derived" / "core-reference.md"
ALERT_SOURCES = {"brief": "brief.core_reference", "merge": "fsm.core_reference_regen"}
REFERENCE_REASON = "reference"
MIN_USES_FROM_SETTING = "настройка проекта"
MIN_USES_DEFAULT = "умолчание"
BUILT_ACTION = "справочник ядра: построен"
FAILED_ACTION = "справочник ядра: сбой"
ACTOR = "orchestrator"

SHA_FORM = re.compile(r"[0-9a-f]{40}")
BLOB_MODES = ("100644", "100755")
LISTING_CHUNK = 64 * 1024

# Тексты алертов — без sha, времени и размеров (требование 7): повторная
# сборка с тем же сбоем не заводит второй открытый алерт. Подробности —
# в пометке `note` и записи журнала «справочник ядра: сбой».
SETTING_FAILED = ("справочник ядра: targets.yaml не прочитан или запись "
                  "проекта и её поле core_reference неверны")
GENERATOR_UNREAD = "справочник ядра: файл генератора не прочитан"
HEAD_UNKNOWN = "справочник ядра: голова ветки задачи не узнана"
SHA_MALFORMED = "справочник ядра: sha источника не из 40 шестнадцатеричных знаков"
NO_CLONE = "справочник ядра: клона проекта нет"
SOURCE_FAILED = "справочник ядра: источник недоступен — git не прочитал коммит"
OVER_LIMITS = "справочник ядра: коммит сверх пределов чтения"
DEADLINE = "справочник ядра: общий срок сборки исчерпан"
NOT_WRITTEN = "справочник ядра: кэш не записан"
INTERNAL = "справочник ядра: внутренний сбой сборки"


def _generator_sha256() -> str:
    """sha256 байт файла загруженного модуля генератора — не путь от
    `config.ROOT`: пульт с подменённым корнем считает тот код, что исполняет."""
    try:
        return hashlib.sha256(Path(core_reference.__file__).read_bytes()).hexdigest()
    except OSError:
        return ""


GENERATOR_SHA256 = _generator_sha256()


@dataclass(frozen=True)
class Reference:
    """Ответ `get_reference`: `text` — файл кэша целиком (шапка и тело)
    или пусто, `note` — пометка для брифа, `state` — `off` | `fresh` |
    `cached` | `unverified` | `absent`."""
    text: str = ""
    note: str = ""
    state: str = "absent"


class _Failure(Exception):
    """Сбой сборки: текст алерта и подробность для пометки и журнала."""

    def __init__(self, alert: str, detail: str = ""):
        super().__init__(alert)
        self.alert = alert
        self.detail = detail


def get_reference(conn, task_id: str, *, reason: str,
                  sha: str | None = None) -> Reference:
    """Справочник ядра проекта задачи на коммите `sha` (None — голова ветки
    задачи в клоне проекта); `reason` — `brief` или `merge`.

    Не бросает исключений и не завершает процесс: справочник — подсказка
    роли, его сбой не должен останавливать бриф или шаг после мержа. Сбой,
    которого разбор ниже не предусмотрел, — тоже `absent` с алертом."""
    try:
        # До чтения targets.yaml: в песочнице с боевой областью проектов
        # нельзя ни читать, ни писать кэш, ни звать git (требование 6).
        if repo_context.projects_root() == repo_context.NO_AREA:
            return Reference(state="off")
        target = store.task_target(conn, task_id)
    except Exception as exc:  # noqa: BLE001 — контракт «не бросает», см. docstring
        return _absent(conn, task_id, None, _alert_source(reason),
                       _Failure(INTERNAL, f"{type(exc).__name__}: {exc}"))
    return get_reference_for_target(conn, target, reason=reason, sha=sha,
                                    task_id=task_id)


def get_reference_for_target(conn, target: str, *, reason: str,
                             sha: str | None,
                             task_id: str | None = None) -> Reference:
    """Справочник ядра проекта `target` на коммите `sha` — общий вход без
    задачи (SPEC 01M4TVBT9ZCRQDY669QV3S95MA, требование 3). `task_id` —
    задача записей журнала и голова её ветки при `sha=None`; без задачи
    записи журнала идут с `task_id=None` и явным `target`.

    Повод `reference` (команда пульта) алертов не поднимает и не снимает:
    исход — в возвращённом значении и журнале. Контракт «не бросает» —
    тот же, что у `get_reference`."""
    source = _alert_source(reason)
    try:
        if repo_context.projects_root() == repo_context.NO_AREA:
            return Reference(state="off")
        return _reference(conn, task_id, target, source, reason, sha)
    except Exception as exc:  # noqa: BLE001 — контракт «не бросает», см. docstring
        return _absent(conn, task_id, target, source,
                       _Failure(INTERNAL, f"{type(exc).__name__}: {exc}"))


def min_uses(setting: dict) -> tuple[int, str]:
    """(порог использования, источник) настройки `core_reference`: подполе
    `min_uses` проекта либо умолчание `config.CORE_REFERENCE_MIN_USES`."""
    if targets.REFERENCE_MIN_USES in setting:
        return setting[targets.REFERENCE_MIN_USES], MIN_USES_FROM_SETTING
    return config.CORE_REFERENCE_MIN_USES, MIN_USES_DEFAULT


def _alert_source(reason: str) -> str | None:
    """Источник алертов повода; None — повод `reference` алертов не трогает."""
    if reason == REFERENCE_REASON:
        return None
    return ALERT_SOURCES.get(reason, ALERT_SOURCES["brief"])


def _reference(conn, task_id, target, source, reason, sha) -> Reference:
    try:
        setting = targets.core_reference(target)
    except targets.TargetsError as exc:
        return _absent(conn, task_id, target, source, _Failure(SETTING_FAILED, str(exc)))
    if setting is None:
        return Reference(state="off")
    if not GENERATOR_SHA256:
        return _absent(conn, task_id, target, source,
                       _Failure(GENERATOR_UNREAD, core_reference.__file__))
    cache = repo_context.projects_root() / target / CACHE_REL
    cached_text, cached_sha = _read_cache(cache, setting)
    clone = repo_context.clone_path(target)
    if sha is None:
        sha, why = (_branch_head(conn, task_id, clone) if task_id is not None
                    else (None, "ни задачи, ни sha не названо"))
        if sha is None:
            if cached_text is not None:
                return Reference(cached_text, f"справочник ядра не сверен: {why}, "
                                              f"built_at_sha={cached_sha}", "unverified")
            return _absent(conn, task_id, target, source, _Failure(HEAD_UNKNOWN, why))
    elif not SHA_FORM.fullmatch(sha):
        return _absent(conn, task_id, target, source,
                       _Failure(SHA_MALFORMED, repr(sha)))
    if cached_text is not None and cached_sha == sha:
        return Reference(cached_text, "", "cached")
    return _build(conn, task_id, target, source, reason, sha, setting, clone, cache)


def _build(conn, task_id, target, source, reason, sha, setting, clone,
           cache) -> Reference:
    started = time.monotonic()
    deadline = started + config.CORE_REFERENCE_GIT_TIMEOUT_SEC
    try:
        sources, unparsed, skipped = _read_commit(clone, sha, deadline)
        report = core_reference.build_report(
            sources, setting, sha, min_uses=min_uses(setting)[0],
            generator_sha256=GENERATOR_SHA256, unparsed=unparsed,
            skipped=skipped, deadline=deadline)
    except _Failure as failure:
        return _absent(conn, task_id, target, source, failure)
    except core_reference.DeadlineExceeded as exc:
        return _absent(conn, task_id, target, source, _Failure(DEADLINE, str(exc)))
    elapsed = time.monotonic() - started
    data = report.text.encode("utf-8", "surrogatepass")
    store.journal(conn, task_id, ACTOR, BUILT_ACTION,
                  f"sha={sha} байт={len(data)} записей={report.records} "
                  f"длительность={elapsed:.2f}с повод={reason}", target=target)
    notes = []
    for problem in report.problems:
        _alert(conn, target, source, problem)
        notes.append(problem)
    try:
        _write_atomic(cache, data)
    except OSError as exc:
        _alert(conn, target, source, NOT_WRITTEN)
        notes.append(f"{NOT_WRITTEN}: {exc}")
    return Reference(report.text, "; ".join(notes), "fresh")


def _absent(conn, task_id, target, source, failure: _Failure) -> Reference:
    note = f"{failure.alert}: {failure.detail}" if failure.detail else failure.alert
    with contextlib.suppress(Exception):
        store.journal(conn, task_id, ACTOR, FAILED_ACTION, note, target=target)
    _alert(conn, target, source, failure.alert)
    return Reference("", note, "absent")


def _alert(conn, target, source, message) -> None:
    # Алерт — сигнал Оператору, не условие ответа: его сбой (БД) не
    # отменяет выдачу справочника.
    if source is None:
        return
    with contextlib.suppress(Exception):
        alerts.raise_alert(conn, target, "incident", source, message)


# --- кэш --------------------------------------------------------------------

def _read_cache(cache: Path, setting: dict) -> tuple[str | None, str | None]:
    """(текст, built_at_sha) годного кэша — одно прочтение файла целиком;
    (None, None) — кэша нет или он испорчен: не обычный файл (ссылка не
    разыменовывается), крупнее четырёх `CORE_REFERENCE_MAX_BLOB_BYTES`, не
    UTF-8, чужая настройка, генератор или sha256 тела."""
    limit = 4 * config.CORE_REFERENCE_MAX_BLOB_BYTES

    def opener(path, flags):
        return os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)

    try:
        with open(cache, "rb", opener=opener) as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                return None, None
            data = handle.read(limit + 1)
    except OSError:
        return None, None
    if len(data) > limit:
        return None, None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, None
    built = core_reference.reference_sha(
        text, setting, min_uses=min_uses(setting)[0],
        generator_sha256=GENERATOR_SHA256)
    return (text, built) if built else (None, None)


def _write_atomic(cache: Path, data: bytes) -> None:
    """Временный файл в том же каталоге и замена: сбой замены оставляет
    прежний кэш целым, временный файл не остаётся."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=cache.parent, prefix=".core-reference.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, cache)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# --- источник ---------------------------------------------------------------

def _branch_head(conn, task_id, clone: Path) -> tuple[str | None, str]:
    """(sha головы ветки задачи в клоне, причина, если не узнана)."""
    branch = store.task_branch(conn, task_id)
    if not branch:
        return None, "ветка задачи не записана"
    return branch_commit(clone, branch)


def branch_commit(clone: Path, branch: str) -> tuple[str | None, str]:
    """(sha коммита `refs/heads/<branch>` клона, причина, если не узнан) —
    без `fetch`: локальная ссылка клона как есть."""
    if not clone.is_dir():
        return None, "клона проекта нет"
    try:
        res = gitcmd.read(clone, "rev-parse", "--verify", "--quiet",
                          f"refs/heads/{branch}^{{commit}}", text=True,
                          timeout=config.CORE_REFERENCE_GIT_TIMEOUT_SEC)
    except gitcmd.Timeout:
        return None, "git не ответил (TimeoutExpired)"
    except OSError as exc:
        return None, f"git не ответил ({type(exc).__name__})"
    head = res.stdout.strip()
    if res.returncode != 0 or not SHA_FORM.fullmatch(head):
        return None, f"ветки {branch} нет в клоне проекта"
    return head, ""


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise _Failure(DEADLINE, "срок исчерпан до вызова git")
    return left


def _read_commit(clone: Path, sha: str, deadline: float) -> tuple[dict, int, int]:
    """Исходники `.py` коммита: (путь → текст, не UTF-8, пропущенные)."""
    if not clone.is_dir():
        raise _Failure(NO_CLONE, str(clone))
    entries, skipped = _list_tree(clone, sha, deadline)
    if not entries:
        return {}, 0, skipped
    if len(entries) > config.CORE_REFERENCE_MAX_FILES:
        raise _Failure(OVER_LIMITS, f"файлов {len(entries)} > "
                                    f"{config.CORE_REFERENCE_MAX_FILES}")
    total = sum(size for _path, _obj, size in entries)
    if total > config.CORE_REFERENCE_MAX_SOURCE_BYTES:
        raise _Failure(OVER_LIMITS, f"объём {total} байт > "
                                    f"{config.CORE_REFERENCE_MAX_SOURCE_BYTES}")
    blobs = _cat_blobs(clone, sorted({obj for _path, obj, _size in entries}), deadline)
    sources, unparsed = {}, 0
    for path, obj, _size in entries:
        data = blobs.get(obj)
        if data is None:
            skipped += 1
            continue
        try:
            sources[path] = data.decode("utf-8")
        except UnicodeDecodeError:
            unparsed += 1
    return sources, unparsed, skipped


def _list_tree(clone: Path, sha: str, deadline: float) -> tuple[list, int]:
    """Записи `.py` коммита из `ls-tree -r -l -z`, прочитанного потоком
    с пределом: ([(путь, blob, размер)], пропущенные)."""
    remaining = _remaining(deadline)
    try:
        res = gitcmd.read_stream(clone, "ls-tree", "-r", "-l", "-z", sha,
                                 limit=config.CORE_REFERENCE_MAX_LISTING_BYTES,
                                 timeout=remaining, chunk=LISTING_CHUNK)
    except gitcmd.LaunchFailed as exc:
        error = exc.error
        raise _Failure(SOURCE_FAILED,
                       f"ls-tree: {type(error).__name__}: {error}") from error
    except gitcmd.OverLimit as exc:
        raise _Failure(OVER_LIMITS, f"вывод ls-tree > "
                                    f"{config.CORE_REFERENCE_MAX_LISTING_BYTES} байт") from exc
    except gitcmd.Timeout as exc:
        raise _Failure(DEADLINE, "срок исчерпан на ls-tree") from exc
    if time.monotonic() > deadline:
        raise _Failure(DEADLINE, "срок исчерпан на ls-tree")
    if res.returncode != 0:
        raise _Failure(SOURCE_FAILED, f"ls-tree {sha}: код {res.returncode}")
    entries, skipped = [], 0
    for record in res.stdout.split(b"\0"):
        meta, tab, raw_path = record.partition(b"\t")
        parts = meta.decode("ascii", "replace").split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if not tab or len(parts) != 4 or not path.endswith(".py"):
            continue
        mode, kind, obj, size = parts
        if kind != "blob" or mode not in BLOB_MODES or not size.isdigit():
            skipped += 1
        elif int(size) > config.CORE_REFERENCE_MAX_BLOB_BYTES:
            skipped += 1
        else:
            entries.append((path, obj, int(size)))
    return entries, skipped


def _cat_blobs(clone: Path, objects: list, deadline: float) -> dict:
    """Содержимое blob'ов одним `cat-file --batch`: blob → байты; ответ
    `missing` в словарь не попадает."""
    remaining = _remaining(deadline)
    try:
        res = gitcmd.read(clone, "cat-file", "--batch",
                          input=("\n".join(objects) + "\n").encode("ascii"),
                          timeout=remaining)
    except gitcmd.Timeout as exc:
        raise _Failure(DEADLINE, "срок исчерпан на cat-file") from exc
    except OSError as exc:
        raise _Failure(SOURCE_FAILED, f"cat-file: {type(exc).__name__}: {exc}") from exc
    if time.monotonic() > deadline:
        raise _Failure(DEADLINE, "срок исчерпан после cat-file")
    if res.returncode != 0:
        raise _Failure(SOURCE_FAILED, f"cat-file: код {res.returncode}")
    out, pos, blobs = res.stdout, 0, {}
    while pos < len(out):
        end = out.find(b"\n", pos)
        if end < 0:
            raise _Failure(SOURCE_FAILED, "ответ cat-file оборван")
        header = out[pos:end].decode("ascii", "replace").split()
        pos = end + 1
        if len(header) == 2 and header[1] == "missing":
            continue
        if len(header) != 3 or not header[2].isdigit():
            raise _Failure(SOURCE_FAILED, "ответ cat-file не разобран")
        obj, kind, size = header[0], header[1], int(header[2])
        if pos + size > len(out):
            raise _Failure(SOURCE_FAILED, "ответ cat-file оборван")
        if kind == "blob":
            blobs[obj] = out[pos:pos + size]
        pos += size + 1
    return blobs
