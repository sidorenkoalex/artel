"""Прогон и сводка приёмочных тестов задачи: tasks/<id>/acceptance_tests/
(SPEC T023, требование 6).

Разбор AC-разметки и пометок manual/skip/escalate живёт в scripts/guard.py
(`scan_acceptance_tests`) — тот же код держит трассируемость на выходе
из tests_writing (orchestrator/fsm.py) и сводку здесь: расхождение
источников иначе обнаруживалось бы разными числами в разных местах,
а не проверкой. guard.py содержимое файлов принципиально не исполняет
(его докстринг) — прогон и сбор тестов поэтому здесь, не там.
"""
import ast
import contextlib
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sqlite3
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator, NamedTuple
from xml.etree import ElementTree

from scripts import guard

from . import (agent_log, artifact_branch, ci, config, gitcmd, stack,
               suite_lock, targets)


def _pytest_command(*args: str, command: list[str] | None = None) -> list[str]:
    """Общая часть команды pytest обоих раннеров: интерпретатор venv
    пульта (`stack.pytest_python_executable()` — не голый `"python3"`,
    резолвящийся по PATH ВЫЗЫВАЮЩЕГО процесса, а не роли: гейты/
    `amend-tests` пульт зовёт из собственного окружения, не из
    `runner.role_env`, тот PATH только у роли — ANSWER-4, диагноз AC-7),
    без кеша (требование 5), и ЯВНАЯ загрузка `pytest-timeout` по
    каноническому имени точки входа `timeout` (не `pytest_timeout` — имя
    импортируемого модуля: `-p pytest_timeout` заставляет pytest
    импортировать его как отдельный плагин ДО разбора точек входа
    setuptools, и последующая автозагрузка того же модуля под именем
    `timeout` падает `ValueError: Plugin already registered under a
    different name` — эмпирически найдено этим же прогоном). Явная
    загрузка по имени `timeout` — тот же плагин, что и так подключился бы
    автоматически (никакого эффекта, если он уже установлен), но при ЕГО
    ОТСУТСТВИИ в интерпретаторе даёт громкий `ImportError`/красный
    returncode вместо тихого пропуска таймаута отдельного теста.

    `command` — начало команды из профиля тестов проекта
    (`project_profile.Profile.command`, SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
    требование 1): первый элемент `python3` — тот же интерпретатор venv
    пульта, пути тестов и флаги пульта добавляются к нему; не назван —
    команда пульта. Интерпретатор резолвится здесь, при сборке команды
    прогона, а не в гейте: гейт, чей прогон не состоится, venv не ищет."""
    head = (list(command) if command
            else [stack.pytest_python_executable(), "-m", "pytest"])
    if head[0] == "python3":
        head[0] = stack.pytest_python_executable()
    return [*head, *args,
            "-p", "no:cacheprovider", "-p", "timeout",
            "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]


@contextlib.contextmanager
def _pytest_env() -> Iterator[dict[str, str]]:
    """Окружение одного прогона `_pytest_command`: копия `os.environ`
    пульта плюс `PYTHONPYCACHEPREFIX` на свежий временный каталог (SPEC
    01M3Y7G6T3MK7A899521VF9N7B, требования 1, 3, 4).

    Проверка свежести `.pyc` смотрит только на время изменения и размер
    исходника: 02.10 правка с тем же размером в ту же секунду оставила
    `__pycache__` worktree «свежим», и автогейт исполнил старый байткод.
    `PYTHONDONTWRITEBYTECODE` не помогает — уже лежащий `.pyc` всё равно
    читается; отведённый кеш пуст, и исходник компилируется заново.
    Каталог — в системном временном (`tempfile`), то есть вне `cwd`
    прогона и вне `config.ROOT`; рабочие процессы xdist наследуют
    переменную от главного процесса pytest. Уборка — на выходе из блока,
    в том числе по `TimeoutExpired` и любому другому исключению."""
    cache_dir = tempfile.mkdtemp(prefix="artel-pycache-")
    try:
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = cache_dir
        yield env
    finally:
        _remove_cache_dir(cache_dir)


# ------------------------------------------------ раннер `pytest-own`
#
# Профиль тестов проекта с `runner: pytest-own` (ADR-0023, вторая поправка
# 16.10.2026; SPEC 01M52EEFNA1WH31962HVNT0YZ9) приходит в места запуска
# каналом `command` (`run_plank` и `two_sided.run` — параметром `profile`):
# команда профиля как есть в `workdir`, чистое окружение, свой сеанс и
# снятие группы процессов вместо `-p timeout`. Профиль `pult-pytest` —
# только его команда: путь артели не меняется ни argv, ни `cwd`, ни
# окружением.

# Начало текста отказа запуска: `workdir` профиля не каталог внутри дерева
# прогона (требование 3) — pytest не запускается.
WORKDIR_REFUSAL = "отказ запуска pytest-own: workdir профиля"

# Переменные окружения пульта, которые прогон `pytest-own` наследует
# (требование 5); `TMPDIR` — всегда, `HOME` — свой на каждый прогон.
_OWN_INHERITED_VARS = ("PATH", "LANG", "LC_ALL")

# Предел дочитывания вывода после снятия группы: потомок, ушедший в
# собственный сеанс, держал бы канал вывода открытым бесконечно.
_OWN_DRAIN_SEC = 10

# Код выхода `run_plank` на отказе запуска: прогона не было, и это не
# таймаут (`None`) и не зелёный 0; 4 — код pytest «ошибка запуска».
REFUSED_EXIT_CODE = 4


def _own(command):
    """Профиль `pytest-own`, переданный каналом `command`; иначе `None`."""
    return command if getattr(command, "runner", None) == \
        targets.PROFILE_RUNNER_OWN else None


def _head(command) -> list[str] | None:
    """Начало команды раннера пульта: у профиля `pult-pytest` — его
    команда, у списка и `None` — они сами (`_pytest_command`)."""
    if command is None or isinstance(command, (list, tuple)):
        return command
    return list(command.command)


def _place_command(command, *args: str) -> list[str]:
    """argv места запуска: у `pytest-own` — команда профиля как есть,
    аргументы места и `-p no:cacheprovider` (без интерпретатора пульта и
    без `-p timeout`); иначе `_pytest_command`."""
    own = _own(command)
    if own is None:
        return _pytest_command(*args, command=_head(command))
    return [*own.command, *args, "-p", "no:cacheprovider"]


def _place_env(command, run_dir: Path | None = None):
    """Окружение прогона места: `_own_env` у `pytest-own`, иначе
    `_pytest_env` (копия окружения пульта). `run_dir` — каталог прогона
    (`cwd` процесса) для каталога относительной команды профиля в PATH."""
    own = _own(command)
    return _pytest_env() if own is None else _own_env(own, run_dir)


# Системные каталоги в хвосте PATH прогона `pytest-own` (SPEC
# 01M56KCVCTW5BV9TWTH54TW9Q9, требование 1): PATH роли — только каталоги
# объявленных инструментов, и обёртка проекта без них не находит `bash`/`date`.
_OWN_SYSTEM_PATH_DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


def _own_path(profile, run_dir: Path | None) -> str:
    """PATH прогона `pytest-own`: PATH вызывающего без изменений, затем
    каталог `command[0]` и `_OWN_SYSTEM_PATH_DIRS`, которых в нём ещё нет.
    Хвост одинаков для гейтов пульта и шага роли и ничего уже найденного
    не затеняет. Каталог команды: абсолютный путь — его каталог;
    относительный с `/` — от `run_dir` (оттуда его разрешит запуск), без
    `run_dir` пропускается; голое имя — каталог найденного поиском по PATH
    вызывающего, не найдено — пропускается (запуск даст `CommandNotFound`)."""
    caller = os.environ.get("PATH")
    parts = caller.split(os.pathsep) if caller else []
    head = profile.command[0] if profile.command else ""
    command_dir = None
    if os.path.isabs(head):
        command_dir = os.path.dirname(head)
    elif "/" in head:
        if run_dir is not None:
            command_dir = os.path.dirname(
                os.path.normpath(os.path.join(str(run_dir), head)))
    elif head and caller:
        found = shutil.which(head, path=caller)
        if found:
            command_dir = os.path.dirname(found)
    tail = [command_dir] if command_dir else []
    for directory in (*tail, *_OWN_SYSTEM_PATH_DIRS):
        if directory not in parts:
            parts.append(directory)
    return os.pathsep.join(parts)


@contextlib.contextmanager
def _own_env(profile, run_dir: Path | None = None) -> Iterator[dict[str, str]]:
    """Чистое окружение прогона `pytest-own` (требование 5): `PATH`
    (`_own_path`), `LANG`/`LC_ALL` пульта (если заданы), `TMPDIR`,
    `test_profile.env` (его `PATH` перекрывает собранный), затем свой
    `HOME` и `PYTHONPYCACHEPREFIX` (ADR-0023: обязателен на
    каждом прогоне) — оба новые каталоги на этот прогон, убираются на
    выходе из блока, в том числе по таймауту и исключению. Служебные
    переменные места (`PYTHONUNBUFFERED`, плагин двустороннего прогона)
    дописывает вызывающий, как и у `_pytest_env`."""
    home = tempfile.mkdtemp(prefix="artel-own-home-")
    cache_dir = tempfile.mkdtemp(prefix="artel-pycache-")
    try:
        env = {name: os.environ[name] for name in _OWN_INHERITED_VARS
               if name in os.environ}
        env["PATH"] = _own_path(profile, run_dir)
        env["TMPDIR"] = os.environ.get("TMPDIR") or tempfile.gettempdir()
        env.update(profile.env)
        env["HOME"] = home
        env["PYTHONPYCACHEPREFIX"] = cache_dir
        yield env
    finally:
        _remove_cache_dir(cache_dir)
        _remove_cache_dir(home)


def _own_cwd(profile, tree: Path) -> tuple[Path, str]:
    """(рабочий каталог прогона, текст отказа) — `workdir` профиля в
    дереве `tree`. Сверка по `realpath` в момент вызова (требование 3):
    ссылка, ведущая из дерева наружу, — отказ, как и не каталог."""
    tree = Path(tree)
    cwd = tree / profile.workdir if profile.workdir else tree
    real_tree = os.path.realpath(tree)
    real = os.path.realpath(cwd)
    if real != real_tree and not real.startswith(real_tree.rstrip(os.sep) + os.sep):
        return cwd, (f"{WORKDIR_REFUSAL} «{profile.workdir}» ведёт за пределы "
                     f"дерева прогона {tree} (realpath: {real}) — pytest не "
                     f"запускался")
    if not os.path.isdir(real):
        return cwd, (f"{WORKDIR_REFUSAL} «{profile.workdir}» — не каталог в "
                     f"дереве прогона {tree} — pytest не запускался")
    return cwd, ""


def _own_target(profile, arg: str, *, node: bool = False) -> str:
    """Путь `arg` от корня дерева — тот же путь из `workdir` (требование
    4). Абсолютный путь и флаг — как есть; id теста (`::`) — как есть
    (его печатает pytest из `workdir`), а при `node` (узел, собранный
    пультом из пути от корня) переводится его часть пути."""
    path, sep, rest = arg.partition("::")
    if not profile.workdir or os.path.isabs(path) or arg.startswith("-") \
            or (sep and not node):
        return arg
    return os.path.relpath(path, profile.workdir) + sep + rest


class CommandNotFound(OSError):
    """Исполняемого файла команды профиля `pytest-own` нет — запуск процесса
    отказал (SPEC 01M56KCVCTW5BV9TWTH54TW9Q9, требование 3). Наследник
    `OSError`, но не `FileNotFoundError`: `two_sided._run_side` ловит
    `OSError` и сохраняет свой текст отказа, а места `acceptance` ловят
    только этот тип — `FileNotFoundError` прочих операций места (файл лога,
    временные каталоги) отказом о команде не становится."""


def _launch(argv: list[str], cwd: Path, own: bool,
            **kwargs) -> subprocess.Popen:
    """`subprocess.Popen` места запуска. У `pytest-own` (`own`) отсутствие
    `argv[0]` — `CommandNotFound` с текстом «команда профиля <имя> не
    найдена»; `FileNotFoundError` о несуществующем `cwd` Popen называет
    именем каталога — он проходит как есть, как и у `pult-pytest` любой."""
    try:
        return subprocess.Popen(argv, cwd=cwd, **kwargs)
    except FileNotFoundError as exc:
        if not own or exc.filename != argv[0]:
            raise
        raise CommandNotFound(
            f"команда профиля {argv[0]} не найдена") from exc


def _run_in_session(argv: list[str], cwd: Path, env: dict,
                    timeout: float) -> subprocess.CompletedProcess:
    """Прогон `pytest-own` в собственном сеансе (требование 6) — замена
    `subprocess.run(…, capture_output=True, timeout=…)` с тем же
    контрактом исходов, но по таймауту и на любом исключении снимается
    вся группа процессов: дочерние процессы команды профиля не
    переживают прогон. Нет команды профиля — `CommandNotFound`."""
    proc = _launch(argv, cwd, True, env=env, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   text=True, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=_OWN_DRAIN_SEC)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            stdout = stderr = ""
            proc.kill()
            proc.wait()
        raise subprocess.TimeoutExpired(argv, timeout, output=stdout,
                                        stderr=stderr) from None
    except BaseException:
        _kill_group(proc.pid)
        proc.wait()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def _run_pytest(command, argv: list[str], cwd: Path, env: dict,
                timeout: float) -> subprocess.CompletedProcess:
    """Вызов pytest места запуска: у `pytest-own` — `_run_in_session`,
    иначе прежний `subprocess.run`."""
    if _own(command) is not None:
        return _run_in_session(argv, cwd, env, timeout)
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


# Попытки уборки каталога кеша: на таймауте `subprocess.run` убивает
# главный процесс pytest, а рабочие процессы xdist ещё дописывают `.pyc` —
# `rmtree` ловит «Directory not empty» на каталоге, куда только что лёг файл.
_CACHE_RMTREE_ATTEMPTS = 5
_CACHE_RMTREE_PAUSE_SEC = 0.2


def _remove_cache_dir(path: str) -> None:
    """Удаление каталога кеша прогона с повторами; последняя неудача не
    поднимается — сбой уборки временного каталога не имеет права подменить
    исход прогона, который он обслуживал."""
    for _ in range(_CACHE_RMTREE_ATTEMPTS):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(_CACHE_RMTREE_PAUSE_SEC)
    shutil.rmtree(path, ignore_errors=True)


def _timeout_text(value: bytes | str | None) -> str:
    """`subprocess.TimeoutExpired.stdout`/`.stderr` отдаёт `bytes` ДАЖЕ
    при `text=True`, если процесс успел вывести хоть что-то до самого
    таймаута (наблюдаемое поведение `subprocess.run`, не документированный
    контракт `text=`) — с unittest discover это молчало (тест виснет
    раньше первого вывода), pytest печатает заголовок сессии сразу и
    обнажает несовпадение типов."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


# ------------------------------------------------ итог из отчёта компонента
#
# Профиль с отчётом (`project_profile.reported`: компонент записи
# `components:` с `report` либо `test_profile` с `runner: pytest-own` и
# `report`; SPEC 01M590GJAF0EDV4NBC4C99MFVH, требования 1-7, 12) приходит в
# места запуска тем же каналом `command`/`profile`, что `pytest-own`, и
# гонится узлом `_report_run`: команда компонента с `report_args`
# (`{path}` — файл во временном каталоге вне рабочей копии), установка
# зависимостей пультом, `workdir`, чистое окружение, своя группа процессов
# и таймаут. Итог — только из отчёта (`reporters.outcome`); код возврата и
# текст раннера исход зелёным не делают.

# Исход «неизвестно» (требование 3): значение — `FULL_SUITE_NOT_STARTED`,
# деталь начинается с `UNKNOWN_PREFIX`; прогон был, и лог его пишется.
UNKNOWN_PREFIX = "итог неизвестен: "
UNKNOWN_OUTCOME = "неизвестно"
INSTALL_WITHOUT_LOCK = "install без файла блокировки не исполняется"
# Предел одной установки зависимостей компонента и опроса версии Vitest.
INSTALL_TIMEOUT_SEC = 1800
_VERSION_TIMEOUT_SEC = 60
# Отметка завершённой установки в каталоге пульта: сумма файла блокировки и
# имена каталогов, которые подключаются в `workdir` рабочей копии.
_INSTALL_MARK = ".artel-install.json"


def _reported(command):
    """Профиль с итогом из отчёта, переданный каналом `command`; иначе
    `None`."""
    if command is None or isinstance(command, (list, tuple)):
        return None
    from . import project_profile  # project_profile -> store -> … -> acceptance
    return command if project_profile.reported(command) else None


def place_channel(profile):
    """Канал `command` мест прогона для профиля проекта: сам профиль у
    `pytest-own` и у профиля с отчётом, иначе список его команды (раннер
    пульта)."""
    if _own(profile) is not None or _reported(profile) is not None:
        return profile
    return list(profile.command)


def is_unknown(run) -> bool:
    """Итог полного набора — исход «неизвестно» (требование 3)."""
    return run.outcome == FULL_SUITE_NOT_STARTED and \
        run.detail.startswith(UNKNOWN_PREFIX)


class ReportRun(NamedTuple):
    """Исход одного прогона по отчёту: `refusal` — подготовка отказала,
    прогона не было; `timed_out` — оборван по пределу; иначе `state` —
    вердикт `reporters.outcome` с причиной `reason`. `raw` — вывод раннера,
    `block` — сводка итога из отчёта, `code` — код возврата."""
    state: str = ""
    reason: str = ""
    refusal: str = ""
    timed_out: bool = False
    raw: str = ""
    block: str = ""
    tests: tuple = ()
    code: int | None = None

    @property
    def green(self) -> bool:
        from .reporters import outcome
        return not self.refusal and not self.timed_out and \
            self.state == outcome.GREEN

    def text(self, tail: int | None = None) -> str:
        """Текст исхода для человека и журнала: отказ, таймаут, «неизвестно»
        с причиной либо вывод раннера (хвост `tail`) и сводка из отчёта."""
        from .reporters import outcome
        raw = self.raw if tail is None else self.raw[-tail:]
        if self.refusal:
            return self.refusal
        if self.timed_out:
            return raw
        if self.state == outcome.UNKNOWN:
            return f"{unknown_line(self.reason)}\n{raw}"
        return f"{raw.rstrip()}\n{self.block}\n"


def unknown_line(reason: str) -> str:
    return f"{UNKNOWN_PREFIX}{reason} — исход «{UNKNOWN_OUTCOME}»"


def _component_name(profile) -> str:
    from . import project_profile
    return profile.component or project_profile.DEFAULT_COMPONENT


def _pult_dir(profile, kind: str) -> Path:
    """Каталог пульта проекта компонента для `kind` (`deps`, `cache`)."""
    return (config.PROJECTS / (profile.project or config.DEFAULT_TARGET)
            / kind / _component_name(profile))


def _lock_file(cwd: Path) -> Path | None:
    for name in LOCK_FILE_NAMES:
        path = Path(cwd) / name
        if path.is_file():
            return path
    return None


def _chmod_tree(root: Path, read_only: bool) -> None:
    """Права записи дерева `root` (ссылки не трогаются): каталог установки
    пульта подключается к рабочей копии только для чтения (требование 12),
    перед переустановкой — снова на запись."""
    for dirpath, dirnames, filenames in os.walk(root):
        for name in [*dirnames, *filenames]:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            mode = os.stat(path).st_mode
            if os.path.isdir(path):
                mode = 0o555 if read_only else 0o755
            else:
                mode = mode & ~0o222 if read_only else mode | 0o200
            with contextlib.suppress(OSError):
                os.chmod(path, mode)
    with contextlib.suppress(OSError):
        os.chmod(root, 0o555 if read_only else 0o755)


def _drop_install(home: Path) -> None:
    if home.exists():
        _chmod_tree(home, read_only=False)
        shutil.rmtree(home, ignore_errors=True)


def _install(profile, cwd: Path) -> tuple[Path | None, list, str]:
    """(каталог установки пульта, имена подключаемых каталогов, отказ) —
    `install` компонента (требование 12): один раз на сумму файла
    блокировки `workdir` рабочей копии, в каталоге пульта
    `.artel/projects/<проект>/deps/<компонент>/<сумма>` с копией файлов
    верхнего уровня `workdir`; после установки каталог — только для
    чтения. Без `install` — ничего не делается."""
    if not profile.install:
        return None, [], ""
    name, command = _component_name(profile), " ".join(profile.install)
    lock = _lock_file(cwd)
    if lock is None:
        return None, [], (f"{INSTALL_WITHOUT_LOCK}: в {cwd} нет файла "
                          f"блокировки ({', '.join(LOCK_FILE_NAMES)}) — "
                          f"install компонента {name} ({command}); прогон не "
                          f"запускался")
    try:
        digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    except OSError as exc:
        return None, [], (f"файл блокировки {lock} не прочитан ({exc}) — "
                          f"прогон не запускался")
    home = _pult_dir(profile, "deps") / digest
    links = _install_mark(home, digest)
    if links is not None:
        return home, links, ""
    # Каталог установки общий у задач проекта с тем же файлом блокировки, а
    # прогоны планки идут вне замка полных прогонов: проверка отметки и
    # установка — под замком на сумму, иначе параллельная первая установка
    # снесла бы чужое дерево посреди `npm ci`.
    guard = home.parent / f"{digest}.lock"
    try:
        guard.parent.mkdir(parents=True, exist_ok=True)
        fh = guard.open("a")
    except OSError as exc:
        return None, [], (f"замок установки {guard} не заведён ({exc}) — "
                          f"прогон не запускался")
    with fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            links = _install_mark(home, digest)
            if links is not None:
                return home, links, ""
            return _install_locked(profile, cwd, lock, digest, home)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _install_mark(home: Path, digest: str) -> list | None:
    """Подключаемые каталоги завершённой установки `home` по её отметке;
    `None` — установки нет или она не завершена."""
    try:
        mark = json.loads((home / _INSTALL_MARK).read_text(encoding="utf-8"))
        if mark.get("lock") == digest and isinstance(mark.get("links"), list):
            return [str(n) for n in mark["links"]]
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _install_locked(profile, cwd: Path, lock: Path, digest: str,
                    home: Path) -> tuple[Path | None, list, str]:
    """Установка `install` в `home` под замком `_install`."""
    name, command = _component_name(profile), " ".join(profile.install)

    def failed(why: str) -> tuple[None, list, str]:
        _drop_install(home)
        return None, [], (f"установка зависимостей компонента {name} "
                          f"({command}) не удалась: {why}; прогон не "
                          f"запускался")

    _drop_install(home)
    copied = set()
    try:
        home.mkdir(parents=True)
        for entry in Path(cwd).iterdir():
            if entry.is_file() and not entry.is_symlink():
                shutil.copy2(entry, home / entry.name)
                copied.add(entry.name)
    except OSError as exc:
        return failed(f"каталог {home} не подготовлен ({exc})")
    try:
        with _report_env(profile, home) as env:
            res = _run_in_session(list(profile.install), home, env,
                                  INSTALL_TIMEOUT_SEC)
    except CommandNotFound as exc:
        return failed(str(exc))
    except subprocess.TimeoutExpired:
        return failed(f"превышен предел {INSTALL_TIMEOUT_SEC} с")
    except OSError as exc:
        return failed(f"команда не запустилась ({exc})")
    if res.returncode != 0:
        return failed(f"код {res.returncode}: "
                      f"{_bounded(res.stdout + res.stderr)}")
    links = sorted(p.name for p in home.iterdir()
                   if p.is_dir() and not p.is_symlink() and p.name not in copied)
    try:
        (home / _INSTALL_MARK).write_text(json.dumps(
            {"lock": digest, "lock_file": lock.name, "links": links}),
            encoding="utf-8")
    except OSError as exc:
        return failed(f"отметка установки не записана ({exc})")
    _chmod_tree(home, read_only=True)
    return home, links, ""


def _inside_real(path: str, folder: str) -> bool:
    real, base = os.path.realpath(path), os.path.realpath(folder)
    return real == base or real.startswith(base.rstrip(os.sep) + os.sep)


def _link_deps(profile, tree: Path, cwd: Path, home: Path,
               links: list) -> str:
    """Подключение каталогов установки пульта к `workdir` рабочей копии
    символьными ссылками; текст отказа или пусто. Гейт каталогу дерева не
    доверяет (требование 12): на месте ссылки — собственный каталог или
    ссылка мимо каталога пульта — отказ. Ссылка на прежнюю установку того
    же компонента (сменился файл блокировки) — переподключается. Ссылка
    исключена из git (`info/exclude` клона): чекпоинт её не закоммитит."""
    component_root = str(_pult_dir(profile, "deps"))
    for name in links:
        target, link = home / name, Path(cwd) / name
        if os.path.lexists(link):
            real = os.path.realpath(link)
            if os.path.islink(link) and real == os.path.realpath(target):
                continue
            if not (os.path.islink(link) and _inside_real(real, component_root)):
                what = (f"ссылка на {real}" if os.path.islink(link)
                        else "собственный каталог дерева")
                return (f"подключение {link} подменено: {what} — не каталог "
                        f"установки пульта {target}; прогон не запускался")
            os.unlink(link)
        rel = os.path.relpath(link, tree).replace(os.sep, "/")
        refusal = _exclude_pattern(tree, f"/{rel}", "подключения зависимостей")
        if refusal:
            return refusal
        try:
            os.symlink(target, link)
        except OSError as exc:
            return (f"подключение {link} -> {target} не создано ({exc}); "
                    f"прогон не запускался")
    return ""


def _prepare_deps(profile, tree: Path, cwd: Path) -> str:
    """Установка и подключение зависимостей компонента перед прогоном или
    проверкой; текст отказа или пусто."""
    home, links, refusal = _install(profile, cwd)
    if refusal or home is None:
        return refusal
    return _link_deps(profile, tree, cwd, home, links)


@contextlib.contextmanager
def _report_env(profile, run_dir: Path) -> Iterator[dict[str, str]]:
    """Окружение прогона компонента — то же чистое окружение, что у
    `pytest-own` (`_own_env`); у `pult-vitest` ещё `CI=true` (требование 7)."""
    from . import project_profile
    with _own_env(profile, run_dir) as env:
        if profile.report == project_profile.REPORT_VITEST:
            env["CI"] = "true"
        yield env


def _vitest_version(profile, cwd: Path) -> tuple[str, str]:
    """(версия Vitest, отказ): из `tools` компонента, иначе из вывода
    `--version` установленного раннера."""
    declared = (profile.tools or {}).get("vitest")
    if declared:
        return str(declared), ""
    argv = [profile.command[0], "--version"]
    try:
        with _report_env(profile, cwd) as env:
            res = _run_in_session(argv, cwd, env, _VERSION_TIMEOUT_SEC)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", (f"версия Vitest не получена ({' '.join(argv)}: {exc}); "
                    f"прогон не запускался")
    found = re.search(r"(\d+\.\d+(?:\.\d+)?)", res.stdout + res.stderr)
    if res.returncode != 0 or found is None:
        return "", (f"версия Vitest не получена ({' '.join(argv)}: код "
                    f"{res.returncode}); прогон не запускался")
    return found.group(1), ""


def _vitest_head(profile, cwd: Path) -> tuple[list | None, str]:
    """(argv `pult-vitest` до подмножества и `report_args`, отказ):
    базовый argv требования 7 и флаги пульта по таблице версий."""
    from . import project_profile
    base = list(project_profile.VITEST_BASE_ARGV)
    flag = project_profile.VITEST_REQUIRE_ASSERTIONS
    if list(profile.command) != base:
        return None, (f"command компонента {_component_name(profile)} "
                      f"({' '.join(profile.command)}) не совпадает с базовым "
                      f"argv пульта ({' '.join(base)}); {flag} и флаг кэша "
                      f"добавляет пульт — прогон не запускался")
    version, refusal = _vitest_version(profile, cwd)
    if refusal:
        return None, refusal
    major = version.split(".", 1)[0]
    flags = project_profile.vitest_flags(int(major)) if major.isdigit() else None
    if flags is None:
        return None, (f"Vitest {version}: флаг кэша для главной версии "
                      f"{major} не подтверждён (её нет в "
                      f"project_profile.VITEST_VERSION_FLAGS) — прогон не "
                      f"запускался")
    if not flags.require_assertions:
        return None, (f"Vitest {version} не принимает {flag} — без него "
                      f"прогон компонента не исполняется")
    cache = _pult_dir(profile, "cache") / "vitest"
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"каталог кэша {cache} не заведён ({exc})"
    return [*base, flag, f"{flags.cache_flag}={cache}"], ""


def _subset_args(profile, subset: list) -> tuple[list | None, str]:
    """Аргументы подмножества тестов (пути от корня дерева): у `pult-vitest`
    — подстановкой `{tests}` в `select` (без `select` — отказ), иначе — как
    у `pytest-own`, путями от `workdir` после команды."""
    from . import project_profile
    paths = [_own_target(profile, t, node=True) for t in subset]
    if profile.report != project_profile.REPORT_VITEST:
        return paths, ""
    if not profile.select:
        return None, (f"у компонента {_component_name(profile)} нет select — "
                      f"подмножество тестов ({', '.join(subset)}) передать "
                      f"раннеру нечем; прогон не запускался")
    args = []
    for item in profile.select:
        if item == "{tests}":
            args.extend(paths)
        else:
            args.append(item.replace("{tests}", " ".join(paths)))
    return args, ""


def is_pytest_command(command) -> bool:
    """Команда — запуск pytest: исполняемый файл `pytest`/`py.test` или
    `-m pytest`. Имя интерпретатора само по себе ничего не говорит."""
    command = list(command or ())
    if any(Path(part).name in ("pytest", "py.test") for part in command):
        return True
    return any(flag == "-m" and module == "pytest"
               for flag, module in zip(command, command[1:]))


# Ключ прогона планки на базе в гейте честного `FAIL_TO_PASS` (SPEC
# 01M5AQH8M2DKBV30NBY86J34A7, требование 1): ошибка сбора одного файла не
# снимает прогон остальных — у команды pytest и только по флагу гейта.
CONTINUE_ON_COLLECTION_ERRORS = "--continue-on-collection-errors"

# Повторы внутри прогона запрещены (ADR-0026, «Решение» п. 4): в junit-xml
# перезапуск не виден, упавший и повторённый тест выглядел бы зелёным.
NO_RERUN_PLUGINS_ARGS = ("-p", "no:rerunfailures", "-p", "no:flaky")


def _bans_rerun_plugins(profile) -> bool:
    """Прогон профиля несёт запрет плагинов повторов (SPEC
    01M5FRYVP4NF81VT00FYPHPWJH, требования 1-2): условие
    `advance_gates.acceptance.in_outcome_bounds`, повторённое здесь — её
    модуль импортирует этот на уровне модуля, — плюс команда pytest."""
    from . import project_profile
    return (project_profile.reported(profile)
            and bool(getattr(profile, "from_components", False))
            and profile.report != project_profile.REPORT_VITEST
            and is_pytest_command(profile.command))


def _report_argv(profile, tree: Path, cwd: Path, subset: list | None,
                 report: Path, continue_on_collection_errors: bool = False
                 ) -> tuple[list | None, str]:
    """(argv прогона по отчёту, отказ подготовки)."""
    from . import project_profile
    from .reporters import outcome
    args = project_profile.report_args_of(profile)
    vitest = profile.report == project_profile.REPORT_VITEST
    needed = ["{path}", "{pult_reporter}"] if vitest else ["{path}"]
    missing = [mark for mark in needed if not any(mark in a for a in args)]
    if missing:
        return None, (f"в report_args компонента {_component_name(profile)} "
                      f"нет {' и '.join(missing)} — отчёт пульта не "
                      f"подключить; прогон не запускался")
    if vitest:
        if not profile.install:
            return None, (f"компонент {_component_name(profile)} "
                          f"pult-vitest без install: node_modules дерева "
                          f"пульт не исполняет — прогон не запускался")
        head, refusal = _vitest_head(profile, cwd)
        if refusal:
            return None, refusal
    else:
        head = list(profile.command)
        if _bans_rerun_plugins(profile):
            head += NO_RERUN_PLUGINS_ARGS
    # Цель `long_lived_dir`, `--ignore` выкладки и `-p no:cacheprovider` —
    # аргументы pytest: к иной команде компонента (Vitest, свой раннер) их
    # не добавляет и `runner: pytest-own` (требования 4, 7).
    own = _own(profile) if not vitest and is_pytest_command(head) else None
    if subset is not None:
        extra, refusal = _subset_args(profile, subset)
        if refusal:
            return None, refusal
    elif own is not None:
        extra = [_own_target(own, own.long_lived_dir)]
        extra += _layout_ignore(own)
    else:
        extra = []
    if own is not None:
        extra += ["-p", "no:cacheprovider"]
    if continue_on_collection_errors and not vitest and is_pytest_command(head):
        extra.append(CONTINUE_ON_COLLECTION_ERRORS)
    tail = [a.replace("{path}", str(report))
            .replace("{pult_reporter}", str(outcome.VITEST_REPORTER))
            for a in args]
    return [*head, *extra, *tail], ""


def _session_to_log(argv: list, cwd: Path, env: dict, timeout: float,
                    log: Path) -> tuple[int | None, str]:
    """(код возврата или `None` по пределу, вывод) — прогон с выводом прямо
    в файл `log`, группа процессов снимается на пределе и на исключении."""
    with open(log, "wb") as fh:
        proc = _launch(argv, cwd, True, env=env, stdout=fh,
                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                       start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = None
            _kill_group(proc.pid)
            proc.wait()
        except BaseException:
            _kill_group(proc.pid)
            proc.wait()
            raise
    return code, log.read_bytes().decode("utf-8", errors="replace")


def _report_run(profile, tree: Path, subset: list | None, timeout: float,
                log: Path | None = None,
                continue_on_collection_errors: bool = False) -> ReportRun:
    """Прогон компонента по отчёту в дереве `tree`: `subset` — пути тестов
    от корня дерева (планка, повтор, `--failed`), `None` — полный набор.
    Подготовка (сверка `workdir`, `report_args`, команды `pult-vitest`,
    установка и подключение зависимостей, версия Vitest) отказывает до
    запуска — `refusal`; иначе итог читается из отчёта
    (`reporters.outcome`). `continue_on_collection_errors` — ключ pytest
    гейта честного `FAIL_TO_PASS` (`_report_argv`)."""
    from . import project_profile
    from .reporters import outcome
    cwd, refusal = _own_cwd(profile, Path(tree))
    if not refusal:
        refusal = _prepare_deps(profile, Path(tree), cwd)
    if refusal:
        return ReportRun(refusal=refusal)
    holder = Path(tempfile.mkdtemp(prefix="artel-report-"))
    try:
        vitest = profile.report == project_profile.REPORT_VITEST
        report = holder / ("report.json" if vitest else "report.xml")
        argv, refusal = _report_argv(profile, Path(tree), cwd, subset, report,
                                     continue_on_collection_errors)
        if refusal:
            return ReportRun(refusal=refusal)
        try:
            with _report_env(profile, cwd) as env:
                if vitest:
                    env["PULT_VITEST_REPORT"] = str(report)
                if log is not None:
                    code, raw = _session_to_log(argv, cwd, env, timeout, log)
                else:
                    try:
                        res = _run_in_session(argv, cwd, env, timeout)
                        code, raw = res.returncode, res.stdout + res.stderr
                    except subprocess.TimeoutExpired as exc:
                        code = None
                        raw = _timeout_text(exc.stdout) + _timeout_text(exc.stderr)
        except CommandNotFound as exc:
            return ReportRun(refusal=f"{exc}; прогон не запускался")
        if code is None:
            return ReportRun(timed_out=True, raw=raw)
        if vitest:
            records, reason = outcome.parse_vitest(
                report, _component_name(profile), profile.workdir,
                profile.failure_errors)
        else:
            records, reason = outcome.parse_junit(
                report, _component_name(profile), profile.workdir, cwd)
        state, reason = outcome.verdict(records, code, reason)
        block = outcome.summary_block(records) if records is not None else ""
        return ReportRun(state=state, reason=reason, raw=raw, block=block,
                         tests=tuple(records or ()), code=code)
    finally:
        shutil.rmtree(holder, ignore_errors=True)


def _report_file_times(tests, files: list[str]) -> dict[str, float]:
    """Сумма времени тестов каждого файла `files` (пути от корня дерева) по
    записям отчёта."""
    from . import project_profile
    wanted = {os.path.normpath(rel): rel for rel in files}
    times: dict[str, float] = {}
    for record in tests:
        try:
            _comp, path, _name, _n = project_profile.parse_test_id(record.id)
        except ValueError:
            continue
        rel = wanted.get(os.path.normpath(path))
        if rel is not None:
            times[rel] = times.get(rel, 0.0) + record.time
    return times


def _report_reds(run: ReportRun, files: list[str]) -> list:
    """Красные повторы `run_repeat` по прогону из отчёта: упавшие и
    повторённые тесты; отказ, предел и «неизвестно» — красный повтор
    каждого файла с причиной (повтор с неизвестным исходом не зелёный)."""
    from .reporters import outcome
    if run.refusal:
        return [RedTest(rel, (), run.refusal) for rel in files]
    if run.timed_out:
        note = f"прогон превысил {config.ACCEPTANCE_TIMEOUT_SEC}с"
        return [RedTest(rel, (), note) for rel in files]
    if run.state == outcome.UNKNOWN:
        return [RedTest(rel, (), unknown_line(run.reason)) for rel in files]
    return [RedTest(r.id, tuple(dict.fromkeys(_SEED_LINE.findall(r.failure))),
                    r.failure or f"{outcome.RETRY_NOTE}: {r.retries}")
            for r in run.tests
            if r.outcome in (outcome.FAILED, outcome.ERROR) or r.retries > 0]


def run_checks_local(profile, tree: Path) -> tuple[bool, str]:
    """(прошли, текст) — `checks_local` компонента в его `workdir` дерева
    `tree` (требование 13): окружение и зависимости — те же, что у прогона
    компонента. Ненулевой код, отказ подготовки и предел — не прошли, текст
    несёт вывод проверки."""
    command = list(getattr(profile, "checks_local", ()) or ())
    if not command:
        return True, ""
    head = (f"checks_local компонента {_component_name(profile)} "
            f"({' '.join(command)})")
    cwd, refusal = _own_cwd(profile, Path(tree))
    if not refusal:
        refusal = _prepare_deps(profile, Path(tree), cwd)
    if refusal:
        return False, f"{head}: {refusal}"
    try:
        with _report_env(profile, cwd) as env:
            res = _run_in_session(command, cwd, env,
                                  config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return False, (f"{head}: превышен предел "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC} с")
    except OSError as exc:
        return False, f"{head}: не запустилась ({exc})"
    output = _bounded(res.stdout + res.stderr)
    if res.returncode != 0:
        return False, f"{head} — код {res.returncode}:\n{output}"
    return True, f"{head} — код 0"


# ------------------------------------------------ разбор вывода прогона
#
# Один узел разбора на весь пульт (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
# требование 1): до него признак красноты и итоговую строку читали в двух
# местах по-разному — `amend._RUN_SUMMARY` знал только итоговую строку, а
# автогейт приёмки не читал вывод вовсе и писал одну фразу на три разных
# исхода. Имена упавших тестов не читал никто.

# Итоговая строка pytest (перенесена из `orchestrator/amend.py`, SPEC
# 01M1TKP6AAY4W8GDGZNA9R0JZT, требование 2): «N passed in Xs» / «M failed,
# N passed in Xs», в любом порядке категорий (failed/passed/skipped/error/
# xfailed/xpassed/warning) через запятую, завершается «in <секунды>s» — тем
# же местом, где pytest печатает сводку независимо от порядка
# category-групп в конкретном прогоне. `deselected` (SPEC
# 01M56KCVCTW5BV9TWTH54TW9Q9, требование 2): без него разбор брал хвост
# «13 warnings in 52s» и показывал «прошло: 0, упало: 0» красному прогону.
_RUN_CATEGORY = (r"(?:passed|failed|error(?:s)?|skipped|deselected|xfailed|"
                 r"xpassed|warnings?|subtests? (?:passed|failed))")
_RUN_SUMMARY = re.compile(
    rf"\d+ {_RUN_CATEGORY}(?:, \d+ {_RUN_CATEGORY})* in [\d.]+s")

# Строка блока «short test summary info»: имя упавшего теста. `ERROR` —
# та же категория (требование 1): тест не запустился вовсе (сбой setUp/
# импорта), но назван он там же и тем же форматом, а Оператору нужен
# именно nodeid. Якорь на начало строки обязателен — иначе слово FAILED
# внутри traceback или в сообщении ассерта читалось бы как имя теста.
# `SUBFAILED<метка> <nodeid>` — упавший подтест (unittest subTest, фикстура
# `subtests`; SPEC 01M4PMQ5FQMEV11WPY64G0GNXS): pytest считает его в «N
# failed» отдельно, а родитель unittest при этом — «passed».
_FAILED_LINE = re.compile(r"^(?:(?:FAILED|ERROR) \S|SUBFAILED\S).*$",
                          re.MULTILINE)


def run_summary_line(output: str) -> str:
    """Итоговая строка прогона pytest (`N passed in Xs`/`M failed, N
    passed in Xs`) из вывода прогона; пустая строка — строки в выводе
    нет (прогон оборвался раньше сводки, вывод обрезан иначе, чем
    ожидается). Совпадение — последнее: итог pytest печатает в конце, а
    метка подтеста в строке хода и коротком итоге вправе содержать текст
    вида «1 passed in 0.1s» (11.10 первое совпадение дало «прошло: 1,
    упало: 0» красному прогону)."""
    match = None
    for match in _RUN_SUMMARY.finditer(output):
        pass
    return match.group(0).strip() if match else ""


SUITE_DURATION_ACTION = "прогон: время"
_last_full_suite_metrics: dict | None = None
_last_process_snapshot: list[dict] | None = None
_last_run_completed_at: float | None = None
_observe_full_suite = False


@contextlib.contextmanager
def observed_full_suite() -> Iterator[None]:
    global _observe_full_suite
    previous = _observe_full_suite
    _observe_full_suite = True
    try:
        yield
    finally:
        _observe_full_suite = previous


def _process_snapshot(excluded_pid: int | None = None) -> list[dict]:
    """CPU snapshot with the running pytest process tree removed."""
    try:
        result = subprocess.run(
            ["/bin/ps", "-axww", "-o", "pid=,ppid=,%cpu=,etime=,command="],
            capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return _native_process_snapshot(excluded_pid)
        rows = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) != 5:
                continue
            pid, ppid, cpu, age, command = parts
            rows.append({"pid": int(pid), "ppid": int(ppid),
                         "cpu_percent": float(cpu.replace(",", ".")),
                         "age": age, "name": Path(command.split()[0]).name,
                         "command": command})
        if not rows:
            return _native_process_snapshot(excluded_pid)
        excluded = {excluded_pid} if excluded_pid else set()
        while True:
            children = {row["pid"] for row in rows if row["ppid"] in excluded}
            if children <= excluded:
                break
            excluded.update(children)
        return [{"pid": row["pid"], "cpu_percent": row["cpu_percent"],
                 "name": row["name"], "age": row["age"]}
                for row in sorted(rows, key=lambda item: -item["cpu_percent"])
                if row["pid"] not in excluded][:3]
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return _native_process_snapshot(excluded_pid)


def _native_process_snapshot(excluded_pid: int | None) -> list[dict]:
    """macOS libproc fallback when sandbox policy denies ps."""
    import ctypes
    try:
        lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        size = 8192
        buffer = (ctypes.c_int * size)()
        count = lib.proc_listpids(1, 0, buffer, ctypes.sizeof(buffer)) // 4
        pids = [pid for pid in buffer[:count] if pid > 0]

        def sample(pid: int) -> tuple[int, int] | None:
            raw = ctypes.create_string_buffer(96)
            if lib.proc_pidinfo(pid, 4, 0, raw, 96) != 96:
                return None
            return (int.from_bytes(raw.raw[16:24], "little"),
                    int.from_bytes(raw.raw[24:32], "little"))

        before = {pid: sample(pid) for pid in pids}
        sample_started = time.monotonic()
        time.sleep(0.05)
        elapsed = time.monotonic() - sample_started
        rows = []
        for pid in pids:
            earlier = before[pid]
            later = sample(pid)
            if earlier is None or later is None:
                continue
            name_buffer = ctypes.create_string_buffer(256)
            if lib.proc_name(pid, name_buffer, 256) <= 0:
                continue
            bsd = ctypes.create_string_buffer(136)
            if lib.proc_pidinfo(pid, 3, 0, bsd, 136) != 136:
                continue
            ppid = int.from_bytes(bsd.raw[16:20], "little")
            cpu = max(0, sum(later) - sum(earlier)) / (elapsed * 1e7)
            started = int.from_bytes(bsd.raw[120:128], "little")
            age_seconds = max(0, int(time.time() - started)) if started else 0
            age = (f"{age_seconds // 3600:02d}:"
                   f"{age_seconds // 60 % 60:02d}:{age_seconds % 60:02d}")
            rows.append({"pid": pid, "ppid": ppid, "cpu_percent": round(cpu, 1),
                         "name": name_buffer.value.decode(errors="replace"),
                         "age": age})
        excluded = {excluded_pid} if excluded_pid else set()
        while True:
            children = {row["pid"] for row in rows if row["ppid"] in excluded}
            if children <= excluded:
                break
            excluded.update(children)
        return [{key: value for key, value in row.items() if key != "ppid"}
                for row in sorted(rows, key=lambda item: -item["cpu_percent"])
                if row["pid"] not in excluded][:3]
    except (OSError, ValueError):
        return []


def _workers(argv: list[str], output: str) -> int:
    found = re.findall(r"(\d+) workers \[|created: (\d+)/(\d+) workers", output)
    if found:
        return int(next(value for value in found[-1] if value))
    options = [argv[index + 1] for index in range(len(argv) - 1)
               if argv[index] == "-n"]
    value = options[-1] if options else str(config.FULL_SUITE_WORKERS)
    return int(value) if value.isdigit() else (os.cpu_count() or 1)


def _suite_metrics(start: float, load_start: tuple[float, float],
                   argv: list[str], output: str, timeout: bool,
                   processes: list[dict] | None = None,
                   completed_at: float | None = None) -> dict:
    duration = (completed_at or time.monotonic()) - start
    load_end = os.getloadavg()
    summary = run_summary_line(output) if not timeout else ""
    count = sum(int(n) for n in re.findall(r"(\d+) (?:passed|failed|skipped)\b",
                                         summary)) if summary else None
    return {"duration_seconds": duration, "tests": count,
            "seconds_per_test": duration / count if count else None,
            "xdist_workers": _workers(argv, output),
            "load_start_1": load_start[0], "load_start_5": load_start[1],
            "load_end_1": load_end[0], "load_end_5": load_end[1],
            "cpu_cores": os.cpu_count() or 1,
            "top_processes": processes if processes is not None
            else _process_snapshot()}


def suite_load_line(metrics: dict) -> str:
    processes = ", ".join(
        f"pid {row['pid']} {row['cpu_percent']}% {row['name']}"
        for row in metrics["top_processes"])
    return (f"нагрузка: load average 1/5 мин "
            f"{metrics['load_end_1']}/{metrics['load_end_5']}; "
            f"процессы: {processes or 'нет'}")


def journal_suite_metrics(task_id: str, metrics: dict | None) -> None:
    from . import store
    if metrics is None or not store.db_usable():
        return
    conn = store.db()
    if conn is None:
        return
    try:
        store.journal(conn, task_id, "orchestrator", SUITE_DURATION_ACTION,
                      json.dumps(metrics, ensure_ascii=False))
    except sqlite3.Error as exc:
        print(f"[{task_id}] запись измерения прогона не удалась: {exc}",
              file=sys.stderr)


def failed_test_lines(output: str) -> list[str]:
    """Строки `FAILED <nodeid>`/`ERROR <nodeid>`/`SUBFAILED<метка> <nodeid>`
    блока «short test summary info» — имена упавших тестов и подтестов
    вместе с коротким сообщением, которым pytest их сопровождает (оно и
    есть первая версия причины)."""
    return [line.strip() for line in _FAILED_LINE.findall(output)]


def _bounded(text: str) -> str:
    """Текст, ограниченный теми же потолками, что выжимка логов ролей
    (`agent_log.log_tail`, SPEC требование 2): сначала последние
    `config.LOG_TAIL_LINES` строк, затем последние
    `config.LOG_TAIL_CHARS` символов — хвост, а не начало: в конце вывода
    pytest стоит и сводка, и последние упавшие тесты."""
    tail = "\n".join(text.splitlines()[-config.LOG_TAIL_LINES:]).strip()
    return tail[-config.LOG_TAIL_CHARS:]


def run_digest(output: str) -> str:
    """Выжимка вывода прогона pytest для журнала (требование 1): имена
    упавших тестов и итоговая строка; ни того, ни другого в выводе нет
    (сбор оборвался на conftest, вывод не от pytest) — хвост вывода, чтобы
    диагностика не потерялась совсем.

    Объём — `_bounded` (требование 2): запись журнала читают глазами, а
    красный полный набор бывает и на двести тестов."""
    lines = failed_test_lines(output)
    summary = run_summary_line(output)
    if summary:
        lines.append(summary)
    return _bounded("\n".join(lines) if lines else output)


def _run_targets(tests_dir: Path, extra: list[str]) -> list[str]:
    """Пути одного вызова pytest: каталог планки (если есть) и долгоживущие
    файлы `tests/` кодовой ветки задачи (`extra`, пути от `cwd` прогона,
    SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 3, 9) — обе группы в одном
    прогоне, второго не заводится."""
    return ([str(tests_dir)] if plank_present(tests_dir) else []) + list(extra)


def plank_present(tests_dir: Path) -> bool:
    """В каталоге планки есть что-то кроме помощника пульта `_pult.py`
    (`materialize_*` кладут его и к пустой планке) и кеша байткода: только
    помощник — та же «планка не заведена», что и отсутствие каталога.
    Вопрос «есть ли планка» после выкладки задаётся этой функцией, не
    `is_dir()` каталога."""
    if not tests_dir.is_dir():
        return False
    return any(p.name not in (PLANK_HELPER_NAME, "__pycache__")
               for p in tests_dir.iterdir())


# ------------------------------------------------ выкладка планки `pytest-own`
#
# Планка внешнего проекта исполняется из каталога внутри `long_lived_dir`
# рабочей копии (SPEC 01M57JYJQC8VAHEWMXFNM7D1GS): только там pytest видит
# корень, конфиг, `pythonpath` и `conftest.py` проекта так же, как у
# долгоживущего теста. `--rootdir`/`-c` фикстур `conftest.py` не дают — они
# применяются лишь к тестам под его каталогом.
PLANK_LAYOUT_DIR = ".artel-plank"
# Один общий шаблон в `info/exclude` клона (файл общий для всех worktree
# проекта — потому без id задачи): чекпоинт коммитит `git add -A`, и
# неотслеживаемый файл выкладки, переживший обрыв, иначе ушёл бы в ветку.
PLANK_LAYOUT_EXCLUDE = f"**/{PLANK_LAYOUT_DIR}/"
LAYOUT_OUTSIDE_NOTE = ("long_lived_dir профиля «{lld}» лежит вне workdir "
                       "«{workdir}» — планка идёт прежним путём из "
                       "tasks/<id>/acceptance_tests, без выкладки")


def _inside(path: str, folder: str) -> bool:
    path, folder = os.path.normpath(path), os.path.normpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def _layout_mode(own) -> str:
    """«layout» — планка выкладывается под `long_lived_dir`; «outside» —
    `long_lived_dir` вне `workdir`, прежний путь со строкой о случае; «» —
    не `pytest-own` с `workdir`, прежний путь молча."""
    if own is None or not own.workdir:
        return ""
    return "layout" if _inside(own.long_lived_dir, own.workdir) else "outside"


def _layout_ignore(own) -> list[str]:
    """`--ignore` остатка выкладки в аргументах полного набора `pytest-own`
    с командой pytest: у компонента с `report` и `plank_layout` — родитель
    `<id>`, иначе (прежний путь) — `<long_lived_dir>/.artel-plank`; путь
    переведён к `workdir` (SPEC 01M59Z0FW1699SJQ2FA5Y76CZ3, требование 7)."""
    if _uses_plank_layout(own):
        parent = _layout_parent(own.plank_layout)
        return ["--ignore=" + _own_target(own, parent)] if parent else []
    if _layout_mode(own) == "layout":
        return ["--ignore=" + _own_target(
            own, f"{own.long_lived_dir}/{PLANK_LAYOUT_DIR}")]
    return []


def _layout_root(code_root: Path, own, task_id: str) -> Path:
    return Path(code_root) / own.long_lived_dir / PLANK_LAYOUT_DIR / task_id


def _exclude_layout(code_root: Path) -> str:
    """Шаблон выкладки в `info/exclude` клона рабочей копии `code_root`,
    если его там ещё нет; текст отказа — git не ответил или файл не
    записан (выкладку, видимую git, класть нельзя).

    Файл общий для всех worktree клона, и задачи дописывают его
    параллельно: проверка «шаблон уже есть» и дописывание идут под
    `flock` на самом файле, иначе две задачи оставили бы две строки."""
    return _exclude_pattern(code_root, PLANK_LAYOUT_EXCLUDE, "выкладки планки")


def _exclude_pattern(code_root: Path, pattern: str, what: str) -> str:
    """Шаблон `pattern` в `info/exclude` клона рабочей копии `code_root`
    (`_exclude_layout`); текст отказа «отказ <what>: …» или пусто."""
    res = gitcmd.in_repo(Path(code_root), "rev-parse", "--git-path",
                         "info/exclude")
    if res is None or res.returncode != 0 or not res.stdout.strip():
        detail = (res.stderr.strip() if res is not None else "") or "нет ответа"
        return (f"отказ {what}: git не назвал info/exclude рабочей "
                f"копии {code_root} ({detail}) — pytest не запускался")
    path = Path(res.stdout.strip())
    if not path.is_absolute():
        path = Path(code_root) / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.seek(0)
                text = fh.read()
                if pattern not in text.splitlines():
                    fh.write(("" if not text or text.endswith("\n") else "\n")
                             + pattern + "\n")
                    fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except (OSError, UnicodeDecodeError) as exc:
        return (f"отказ {what}: {path} не записан ({exc}) — pytest "
                f"не запускался")
    return ""


def _drop_layout(root: Path) -> None:
    """Каталог выкладки задачи `root` вместе с кешем байткода; пустой
    `.artel-plank/` над ним — тоже."""
    shutil.rmtree(root, ignore_errors=True)
    try:
        root.parent.rmdir()
    except OSError:
        pass


@contextlib.contextmanager
def _plank_layout(task_id: str, tests_dir: Path, code_root: Path,
                  own) -> Iterator[tuple[Path | None, str, str]]:
    """(каталог планки в выкладке или `None`, строка о случае, текст отказа)
    на время блока. Выкладка — копия `tests_dir` (как он лежит на диске:
    штатная выкладка или правка Оператора с помощником) в
    `<code_root>/<long_lived_dir>/.artel-plank/<id>/acceptance_tests`;
    исключение из git — до записи файлов, уборка — в `finally` на любом
    исходе прогона."""
    mode = _layout_mode(own)
    if mode != "layout":
        note = (LAYOUT_OUTSIDE_NOTE.format(lld=own.long_lived_dir,
                                           workdir=own.workdir)
                if mode == "outside" else "")
        yield None, note, ""
        return
    refusal = _exclude_layout(code_root)
    if refusal:
        yield None, "", refusal
        return
    root = _layout_root(code_root, own, task_id)
    try:
        shutil.rmtree(root, ignore_errors=True)
        layout = root / "acceptance_tests"
        shutil.copytree(tests_dir, layout,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        yield layout, "", ""
    finally:
        _drop_layout(root)


# ------------------------------------------------ выкладка по `plank_layout`
#
# Компонент записи `components:` с `report` и `plank_layout` (SPEC
# 01M59Z0FW1699SJQ2FA5Y76CZ3; ADR-0026 п. 5): на время прогона файлы планки
# его компонента лежат прямо в `<plank_layout>` рабочей копии, без
# подкаталога `acceptance_tests`. Родитель `<id>` — скрытый каталог без
# отслеживаемых файлов: шаблон `/<родитель>/` в `info/exclude` прячет только
# выкладку, не код.
PLANK_ABSENT_NOTE = "acceptance_tests/ нет — приёмочные тесты не заведены"
NO_PLANK_LAYOUT = ("у компонента {name} нет plank_layout — выкладка планки "
                   "не определена")
LAYOUT_NOT_NORMAL = "plank_layout должен быть нормализованным путём без «.» и «..»"
LAYOUT_ID_NOT_LAST = "<id> должен быть последним сегментом plank_layout"
LAYOUT_OUTSIDE_WORKDIR = "plank_layout вне рабочего каталога компонента {name}"
LAYOUT_PARENT_NOT_HIDDEN = ("родитель <id> в plank_layout должен быть скрытым "
                            "каталогом (имя с точки)")
LAYOUT_PARENT_TRACKED = ("в каталоге {parent} есть отслеживаемые git файлы — "
                         "выкладка спрятала бы их")
_LAYOUT_ID = "<id>"


def _uses_plank_layout(profile) -> bool:
    """`plank_layout` читается только у компонента записи `components:` с
    `report` (требования 5, 7); у прочих профилей поле не действует."""
    return bool(getattr(profile, "from_components", False)
                and getattr(profile, "report", "")
                and getattr(profile, "plank_layout", ""))


def _layout_parent(layout: str) -> str:
    """Родитель `<id>` в `plank_layout` нормализованной формы с `<id>`
    последним сегментом; пусто — форма не та (`_layout_check`)."""
    parts = layout.split("/")
    if any(p in ("", ".", "..") for p in parts) or parts[-1] != _LAYOUT_ID:
        return ""
    return "/".join(parts[:-1])


def _layout_check(profile, code_root: Path) -> tuple[str, str]:
    """(родитель `<id>` от корня рабочей копии, текст отказа) — форма
    `plank_layout` в порядке требования 3."""
    parts = profile.plank_layout.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return "", LAYOUT_NOT_NORMAL
    if parts[-1] != _LAYOUT_ID:
        return "", LAYOUT_ID_NOT_LAST
    parent = "/".join(parts[:-1])
    workdir = Path(code_root) / profile.workdir if profile.workdir \
        else Path(code_root)
    if not _inside_real(str(Path(code_root) / profile.plank_layout),
                        str(workdir)):
        return "", LAYOUT_OUTSIDE_WORKDIR.format(name=_component_name(profile))
    if not parent or not parts[-2].startswith("."):
        return "", LAYOUT_PARENT_NOT_HIDDEN
    res = gitcmd.in_repo(Path(code_root), "ls-files", "--", parent)
    if res is None or res.returncode != 0:
        detail = (res.stderr.strip() if res is not None else "") or "нет ответа"
        return "", (f"отслеживаемые git файлы каталога {parent} не проверены "
                    f"({detail}) — выкладка планки не идёт")
    if res.stdout.strip():
        return "", LAYOUT_PARENT_TRACKED.format(parent=parent)
    return parent, ""


class _PlankPlan(NamedTuple):
    """Решение по планке места прогона до запуска (требования 1, 5, 6):
    `refusal` — отказ подготовки; `absent` — файлов компонента нет, та же
    «планка не заведена»; `files` — файлы компонента для выкладки по
    `plank_layout` (`tests` — из них тестовые); иначе — прежний путь."""
    refusal: str = ""
    absent: bool = False
    files: tuple = ()
    tests: tuple = ()
    profile: object = None


def _plank_plan(tests_dir: Path, command) -> _PlankPlan:
    """Порядок правил выкладки (требование 5). Без файлов планки (прогон
    только `extra`) и у канала без профиля проекта — прежний путь."""
    if not plank_present(tests_dir) or command is None or \
            isinstance(command, (list, tuple)) or \
            not getattr(command, "project", ""):
        return _PlankPlan()
    from . import project_profile  # project_profile -> acceptance: цикл
    rule = project_profile.plank_rule(command.project)
    if rule.refusal:
        return _PlankPlan(refusal=rule.refusal)
    if not (command.from_components and command.report):
        return _PlankPlan()
    names = sorted(p.name for p in tests_dir.iterdir() if p.is_file())
    files = tuple(n for n in names
                  if (rule.owns(n) if rule.is_default
                      else rule.component_of(n) == command.component))
    if not command.plank_layout:
        if is_pytest_command(command.command):
            return _PlankPlan()
        if files:
            return _PlankPlan(refusal=NO_PLANK_LAYOUT.format(
                name=_component_name(command)))
        return _PlankPlan(absent=True)
    if not files:
        return _PlankPlan(absent=True)
    return _PlankPlan(files=files,
                      tests=tuple(n for n in files if rule.is_test(n)),
                      profile=command)


class _Laid(NamedTuple):
    """Выкладка на время блока: `targets` — цели планки вместо каталога
    планки (`None` — прежние), `root` — каталог, соответствующий каталогу
    планки; `note` — строка о случае; `refusal` — отказ подготовки."""
    targets: list | None = None
    root: Path | None = None
    note: str = ""
    refusal: str = ""


def _drop_component_layout(root: Path) -> None:
    """Каталог `<id>` выкладки; родитель — только если он опустел."""
    shutil.rmtree(root, ignore_errors=True)
    with contextlib.suppress(OSError):
        root.parent.rmdir()


@contextlib.contextmanager
def _component_layout(plan: _PlankPlan, task_id: str, tests_dir: Path,
                      code_root: Path) -> Iterator[_Laid]:
    """Выкладка файлов компонента прямо в `<plank_layout>` (требования 2-4):
    форма пути, затем шаблон родителя в `info/exclude` до записи файлов,
    уборка в `finally` на любом исходе. Цели: у команды pytest — каталог
    выкладки (там же помощник `_pult.py`), у прочих — тестовые файлы."""
    profile = plan.profile
    parent, refusal = _layout_check(profile, code_root)
    if not refusal:
        refusal = _exclude_pattern(code_root, f"/{parent}/", "выкладки планки")
    if refusal:
        yield _Laid(refusal=refusal)
        return
    root = Path(code_root) / parent / task_id
    pytest = is_pytest_command(profile.command)
    try:
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        names = list(plan.files)
        if pytest and (tests_dir / PLANK_HELPER_NAME).is_file():
            names.append(PLANK_HELPER_NAME)
        for name in names:
            shutil.copy2(tests_dir / name, root / name)
        targets = ([str(root)] if pytest or not plan.tests
                   else [str(root / name) for name in plan.tests])
        yield _Laid(targets=targets, root=root)
    finally:
        _drop_component_layout(root)


@contextlib.contextmanager
def _laid_plank(plan: _PlankPlan, task_id: str, tests_dir: Path,
                code_root: Path, own) -> Iterator[_Laid]:
    """Выкладка места прогона: по `plank_layout` (`plan.files`), никакой
    (`plan.absent`) либо прежняя `_plank_layout` под `long_lived_dir`."""
    if plan.files:
        with _component_layout(plan, task_id, tests_dir, code_root) as laid:
            yield laid
        return
    if plan.absent:
        yield _Laid()
        return
    with _plank_layout(task_id, tests_dir, code_root, own) as laid:
        layout, note, refusal = laid
        yield _Laid(targets=None if layout is None else [str(layout)],
                    root=layout, note=note, refusal=refusal)


def run(tdir: Path, cwd: Path | None = None,
        extra: list[str] = (),
        command: list[str] | None = None,
        file_times: dict[str, float] | None = None,
        records: list | None = None,
        continue_on_collection_errors: bool = False) -> tuple[bool, str]:
    """(зелёно, хвост вывода) — детерминированный прогон pytest'ом (SPEC
    01M1TKP6AAY4W8GDGZNA9R0JZT, требование 1) с `cwd`, равным
    рабочему каталогу кода задачи (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS,
    требование 2, AC-2/AC-3; контракт имени параметра — hotfix 88b38022,
    ADR-0013; переименован `code_root` -> `cwd` задачей SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-11 — клон контекста target'а, не
    обязательно рабочая копия КОДА в узком смысле прежнего имени):
    `cwd` прогона — единственный способ, которым pytest находит и
    `orchestrator/`-код ветки задачи (материализация
    `materialize_from_branch` кладёт планку по штатному пути
    `tasks/<id>/acceptance_tests/` ИМЕННО этого каталога), и
    `pyproject.toml` корня репозитория (таймаут отдельного теста,
    требования 4/6) — pytest ищет конфигурацию, поднимаясь от `cwd`, тем
    же приёмом, каким раньше unittest discover неявно вставлял `cwd` в
    `sys.path`. `cwd=None` (вызовы вне зоны этой задачи, например
    `orchestrator/amend.py`) — прежнее поведение, `config.ROOT`.

    `-p no:cacheprovider` (требование 5) — `.pytest_cache/` не создаётся
    вовсе, автокоммиту артефактов задачи (`checkpoint.py`) нечего
    случайно подобрать.

    `-o timeout=…` (требование 4, AC-7) передаёт таймаут отдельного теста
    ЯВНО, не полагаясь на то, что pytest сам найдёт `pyproject.toml` по
    `cwd`: планка задачи (`tests_dir`, `materialize_from_branch`) лежит
    ВНЕ дерева `run_cwd`, и pytest определяет rootdir/inifile по общему
    предку АРГУМЕНТОВ пути, а не по `cwd`, когда путь теста передан
    отдельным аргументом (эмпирически подтверждено ANSWER-3.md — `cwd`
    оказался кандидатом для поиска конфигурации НЕ во всех версиях
    поведения, вопреки прежнему предположению; без явного `-o` таймаут
    отдельного теста тихо не применялся, зависший тест не резался раньше
    общего таймаута всего прогона).

    Каталога нет (`skip_tests` либо задача старше T023) — прогонять
    нечего, переход не блокируется: тот же вырожденный случай, что
    и у fixation.read() без фиксации.

    Отказ (красная планка) называет каталог планки и `cwd` прогона одной
    строкой в начале хвоста вывода (SPEC требование 4, AC-6) — иначе
    разбор класса дефекта регрессии №14 снова требовал бы ручной раскопки
    кода вместо чтения журнала.

    `extra` — долгоживущие файлы `tests/` задачи (`_run_targets`): они
    исполняются тем же вызовом pytest, и при пустой планке тоже.

    `command` — начало команды из профиля тестов проекта
    (`_pytest_command`) либо сам профиль (`pytest-own`: команда профиля в
    `workdir`, пути от `cwd` переведены к нему; `workdir` вне дерева —
    отказ без прогона).

    Профиль компонента с `report`: файлы планки — по правилу планки
    проекта и выкладке `_plank_plan` (SPEC 01M59Z0FW1699SJQ2FA5Y76CZ3).

    `records` (SPEC 01M5AQH8M2DKBV30NBY86J34A7, требование 1) — у профиля с
    отчётом в список ложится исход прогона `ReportRun` (`refusal`,
    `timed_out`, `state`) и его записи `CaseResult`; на ранних выходах
    подготовки — `ReportRun` с отказом. `continue_on_collection_errors` —
    ключ pytest прогона на базе гейта честного `FAIL_TO_PASS`.
    """
    tests_dir = tdir / "acceptance_tests"
    plan = _plank_plan(tests_dir, command)
    targets = list(extra) if plan.absent else _run_targets(tests_dir, extra)
    if not targets:
        return True, PLANK_ABSENT_NOTE
    reported = _reported(command)
    keep = records if reported is not None else None
    tree = run_cwd = cwd if cwd is not None else config.ROOT
    own, refusal = _own(command), ""
    if own is not None:
        run_cwd, refusal = _own_cwd(own, run_cwd)
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    if extra:
        location_note += f", долгоживущие файлы: {', '.join(extra)}"
    refusal = refusal or plan.refusal
    if refusal:
        if keep is not None:
            keep.append(ReportRun(refusal=refusal))
        return False, f"{location_note}\n{refusal}"
    with _laid_plank(plan, Path(tdir).name, tests_dir, tree,
                     own if plank_present(tests_dir) else None) as laid:
        case_note = laid.note
        if case_note:
            location_note += f"\n{case_note}"
        if laid.refusal:
            if keep is not None:
                keep.append(ReportRun(refusal=laid.refusal))
            return False, f"{location_note}\n{laid.refusal}"
        if laid.targets is not None:
            targets = [*laid.targets, *extra]
        if reported is not None:
            return _run_reported(reported, targets, tree, location_note, extra,
                                 file_times, keep, continue_on_collection_errors)
        if own is not None:
            targets = [_own_target(own, t) for t in targets]
        return _run_now(command, targets, run_cwd, location_note, extra,
                        file_times)


def _report_timeout_text(run: ReportRun, what: str = "прогон") -> str:
    return (f"{what} превысил {config.ACCEPTANCE_TIMEOUT_SEC}с — завис или "
            f"ждёт сетевой ответ\n{run.raw[-2000:]}")


def _run_reported(profile, targets: list[str], tree: Path, location_note: str,
                  extra: list[str], file_times: dict[str, float] | None,
                  records: list | None = None,
                  continue_on_collection_errors: bool = False
                  ) -> tuple[bool, str]:
    """`run()` профиля с отчётом: цели — подмножество компонента, исход —
    из отчёта (требования 1, 8); `records` — исход и записи прогона."""
    run = _report_run(profile, tree, list(targets),
                      config.ACCEPTANCE_TIMEOUT_SEC,
                      continue_on_collection_errors=continue_on_collection_errors)
    if records is not None:
        records.append(run)
        records.extend(run.tests)
    if file_times is not None:
        file_times.update(_report_file_times(run.tests, list(extra)))
    text = _report_timeout_text(run) if run.timed_out else run.text(tail=2000)
    return run.green, f"{location_note}\n{text}"


def _run_now(command, targets: list[str], run_cwd: Path, location_note: str,
             extra: list[str], file_times: dict[str, float] | None
             ) -> tuple[bool, str]:
    """Сам вызов pytest `run()` по готовым целям."""
    with tempfile.TemporaryDirectory(prefix="artel-file-times-") as tmp:
        report = Path(tmp) / "junit.xml"
        report_args = [f"--junitxml={report}"] if file_times is not None else []
        try:
            with _place_env(command, run_cwd) as env:
                res = _run_pytest(
                    command, _place_command(command, *targets, *report_args),
                    run_cwd, env, config.ACCEPTANCE_TIMEOUT_SEC)
        except CommandNotFound as exc:
            return False, f"{location_note}\n{exc}"
        except subprocess.TimeoutExpired as exc:
            if file_times is not None:
                file_times.update(_junit_file_times(report, extra))
            tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
            return False, (f"{location_note}\nпрогон превысил "
                           f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                           f"сетевой ответ\n{tail}")
        if file_times is not None:
            file_times.update(_junit_file_times(report, extra))
        tail = (res.stdout + res.stderr)[-2000:]
        return res.returncode == 0, f"{location_note}\n{tail}"


def _junit_file_times(report: Path, files: list[str]) -> dict[str, float]:
    """Сумма времени testcases каждого файла общего прогона pytest."""
    times: dict[str, float] = {}
    try:
        suite = ElementTree.parse(report)
    except (OSError, ElementTree.ParseError):
        return times
    by_stem = {Path(rel).stem: rel for rel in files}
    for case in suite.iter("testcase"):
        module_parts = (case.get("classname") or "").split(".")
        for stem in module_parts:
            if stem in by_stem:
                try:
                    seconds = float(case.get("time") or "0")
                except ValueError:
                    break
                if math.isfinite(seconds) and seconds >= 0:
                    rel = by_stem[stem]
                    times[rel] = times.get(rel, 0.0) + seconds
                break
    return times


LONG_LIVED_FILE_REPORT_ACTION = "приёмка: время долгоживущих файлов"


def long_lived_file_report(file_times: list[tuple[str, float | None]],
                           limit: float) -> str:
    """Время файлов и предупреждения, не влияющие на исход прогона."""
    lines = []
    for rel, seconds in file_times:
        if seconds is None:
            lines.append(f"{rel} — время не измерено (нет результата pytest)")
            continue
        lines.append(f"{rel} — {seconds:.3f} с")
        if seconds > limit:
            lines.append(f"предупреждение: {rel} — {seconds:.3f} с "
                         f"превышает порог {limit:g} с")
    return "\n".join(lines)


def long_lived_file_reports(rows) -> list[str]:
    """Замеры рубежа из журнала задачи по порядку записи."""
    return [row["detail"] for row in rows
            if row["action"] == LONG_LIVED_FILE_REPORT_ACTION]


def collect(tdir: Path, cwd: Path | None = None,
            extra: list[str] = (),
            command: list[str] | None = None) -> tuple[bool, str]:
    """(собралось, хвост вывода) — сухой сбор планки `pytest
    --collect-only -q` (SPEC 01M2ARQRDV4YY9TVPHXN2E7136, требование 1,
    AC-1/AC-2/AC-3): та же команда, тот же интерпретатор и те же флаги
    окружения, что несёт общая часть `_pytest_command` (venv пульта,
    `-p no:cacheprovider`, явная загрузка `-p timeout`), но без прогона
    ТЕЛ тестов — только импорт модулей и сборка списка тестов. `tdir`/
    `cwd` — тот же контракт, что у `run()` выше.

    Различение исходов — по коду возврата pytest (эмпирически проверено
    этой же задачей, не документированный публичный API, но устойчивое
    поведение текущей мажорной версии): `0` — планка собралась, есть хотя
    бы один тест; `5` (`EXIT_NOTESTSCOLLECTED`) — планка синтаксически
    валидна и импортируется, но не содержит ни одного теста (AC-3, текст
    ровно «планка не содержит ни одного теста» — критерий требует точный
    текст); любой другой код (`2` — сбор прерван ошибкой импорта/
    синтаксиса, и т.п.) — красный сбор, хвост сырого вывода pytest
    называет причину (AC-2). Оба «пустых» исхода (синтаксическая ошибка
    и легитимно пустая планка) печатают в stdout фразу «no tests
    collected» — отличить их текстом самого вывода нельзя, только кодом
    возврата: код 5 отдаётся ТОЛЬКО когда pytest успел собрать дерево без
    единой ошибки и в нём действительно ноль тестов.

    Каталога `acceptance_tests/` нет вовсе — тот же вырожденный случай,
    что и у `run()`: собирать нечего, `(True, ...)`, переход не
    блокируется этой функцией.

    `extra` — тот же контракт, что у `run()`: долгоживущие файлы `tests/`
    собираются тем же вызовом из `cwd` — рабочей копии кодовой ветки
    (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 3). `command` — тот же
    контракт, что у `run()`.
    """
    tests_dir = tdir / "acceptance_tests"
    plan = _plank_plan(tests_dir, command)
    targets = list(extra) if plan.absent else _run_targets(tests_dir, extra)
    if not targets:
        return True, PLANK_ABSENT_NOTE
    tree = run_cwd = cwd if cwd is not None else config.ROOT
    own, refusal = _own(command), ""
    if own is not None:
        run_cwd, refusal = _own_cwd(own, run_cwd)
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    if extra:
        location_note += f", долгоживущие файлы: {', '.join(extra)}"
    refusal = refusal or plan.refusal
    if refusal:
        return False, f"{location_note}\n{refusal}"
    with _laid_plank(plan, Path(tdir).name, tests_dir, tree,
                     own if plank_present(tests_dir) else None) as laid:
        case_note = laid.note
        if case_note:
            location_note += f"\n{case_note}"
        if laid.refusal:
            return False, f"{location_note}\n{laid.refusal}"
        if laid.targets is not None:
            targets = [*laid.targets, *extra]
        reported = _reported(command)
        if reported is not None:
            ok, output = _collect_reported(reported, targets, tree,
                                           location_note)
        else:
            if own is not None:
                targets = [_own_target(own, t) for t in targets]
            ok, output = _collect_now(command, targets, run_cwd, location_note)
    # Зелёный и пустой сбор заголовка не несут — строку о случае им дописать.
    if case_note and case_note not in output:
        output = f"{case_note}\n{output}"
    return ok, output


def _collect_reported(profile, targets: list[str], tree: Path,
                      location_note: str) -> tuple[bool, str]:
    """`collect()` профиля с отчётом: сухого сбора у произвольной команды
    компонента нет — подмножество прогоняется, и «собралось» значит «отчёт
    прочитан и назвал хотя бы один тест»; исход тестов (в `tests_writing`
    они красны по построению) сбор не судит. «Неизвестно», отказ и предел —
    не собралось."""
    from .reporters import outcome
    run = _report_run(profile, tree, list(targets),
                      config.ACCEPTANCE_TIMEOUT_SEC)
    if run.timed_out:
        return False, f"{location_note}\n{_report_timeout_text(run, 'сбор')}"
    if run.refusal or run.state == outcome.UNKNOWN:
        return False, f"{location_note}\n{run.text(tail=2000)}"
    if not run.tests:
        return False, "планка не содержит ни одного теста"
    return True, run.text(tail=2000)


def _collect_now(command, targets: list[str], run_cwd: Path,
                 location_note: str) -> tuple[bool, str]:
    """Сам вызов pytest `collect()` по готовым целям."""
    try:
        with _place_env(command, run_cwd) as env:
            res = _run_pytest(
                command, _place_command(command, *targets, "--collect-only",
                                        "-q"),
                run_cwd, env, config.ACCEPTANCE_TIMEOUT_SEC)
    except CommandNotFound as exc:
        return False, f"{location_note}\n{exc}"
    except subprocess.TimeoutExpired as exc:
        tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
        return False, (f"{location_note}\nсбор превысил "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    if res.returncode == 0:
        return True, (res.stdout + res.stderr)[-2000:]
    if res.returncode == 5:
        return False, "планка не содержит ни одного теста"
    tail = (res.stdout + res.stderr)[-2000:]
    return False, f"{location_note}\n{tail}"


# Зерно, которое печатают долгоживущие файлы `tests/` строкой «зерно: N»
# (SPEC 01M48FRD9RJDBBVT2SN0FY5G2A, требование 2).
_SEED_LINE = re.compile(r"зерно: (\d+)")


def carries_random_seed(path: Path) -> bool:
    """Файл импортирует модуль `random` (`import random` или `from random
    import …`) в любом месте — признак «несёт случайное зерно» (SPEC
    01M48FRD9RJDBBVT2SN0FY5G2A, требование 2). Разбор синтаксиса, а не
    поиск подстроки: слово `random` в докстринге или комментарии признаком
    не является. Файл, который не читается или не разбирается, — `False`:
    повторы идут только после зелёного первого прогона, а такой файл
    первый прогон не прошёл бы."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
                alias.name == "random" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 \
                and node.module == "random":
            return True
    return False


class RedTest(NamedTuple):
    """Красный тест одного прогона: узел pytest, зёрна, напечатанные им
    строкой «зерно: N», и пометка, если узел назван не по отчёту pytest."""
    node: str
    seeds: tuple[str, ...]
    note: str = ""


def _junit_node(classname: str, name: str, files: list[str]) -> str:
    """Узел `файл::Класс::метод` по паре `classname`/`name` отчёта junit:
    `classname` — точечный путь модуля (от корня pytest) и класса, файл —
    тот из `files`, чей точечный путь или его хвост (корень pytest бывает
    глубже `cwd`, если над файлами нет файла настроек) начинает
    `classname`; не нашёлся — `classname::name`."""
    for rel in files:
        parts = Path(rel).with_suffix("").parts
        for start in range(len(parts)):
            dotted = ".".join(parts[start:])
            if classname == dotted:
                return f"{rel}::{name}"
            if classname.startswith(dotted + "."):
                return f"{rel}::{classname[len(dotted) + 1:]}::{name}"
    return f"{classname}::{name}"


def _junit_red_tests(report: Path, files: list[str]) -> list[RedTest] | None:
    """Красные тесты отчёта junit (`failure`/`error`) с их зёрнами; `None` —
    отчёта нет или он не разбирается."""
    try:
        root = ElementTree.parse(report).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    reds: list[RedTest] = []
    for case in root.iter("testcase"):
        problems = [el for el in case if el.tag in ("failure", "error")]
        if not problems:
            continue
        text = "\n".join(
            [el.text or "" for el in case if el.tag == "system-out"]
            + [(el.get("message") or "") + "\n" + (el.text or "")
               for el in problems])
        seeds = tuple(dict.fromkeys(_SEED_LINE.findall(text)))
        reds.append(RedTest(_junit_node(case.get("classname") or "",
                                        case.get("name") or "", files),
                            seeds))
    return reds


def run_repeat(files: list[str], cwd: Path,
               command: list[str] | None = None) -> list[RedTest]:
    """Повторный прогон долгоживущих файлов `files` (пути от `cwd`) без
    планки (SPEC 01M48FRD9RJDBBVT2SN0FY5G2A, требование 2): красные тесты
    прогона, пустой список — прогон зелёный.

    Имена и зёрна — из отчёта junit pytest с выводом теста
    (`junit_logging=system-out`): хвост текстового вывода обрезан и не
    связывает зерно с тестом. Прогон ограничен
    `config.ACCEPTANCE_TIMEOUT_SEC`; истёкший предел и красный исход без
    названных отчётом тестов — красный повтор по каждому файлу с пометкой
    причины: повтор, исход которого неизвестен, зелёным не считается.

    `command` — тот же контракт, что у `run()`: отказ запуска `pytest-own`
    — красный повтор каждого файла с текстом отказа; профиль с отчётом —
    красные тесты отчёта (`_report_reds`)."""
    reported = _reported(command)
    if reported is not None:
        return _report_reds(_report_run(reported, cwd, list(files),
                                        config.ACCEPTANCE_TIMEOUT_SEC),
                            list(files))
    run_cwd, args = cwd, list(files)
    own = _own(command)
    if own is not None:
        run_cwd, refusal = _own_cwd(own, cwd)
        if refusal:
            return [RedTest(rel, (), refusal) for rel in files]
        args = [_own_target(own, rel) for rel in files]
    with tempfile.TemporaryDirectory(prefix="artel-seed-repeat-") as tmp:
        report = Path(tmp) / "junit.xml"
        try:
            with _place_env(command, run_cwd) as env:
                res = _run_pytest(
                    command, _place_command(command, *args,
                                            f"--junitxml={report}", "-o",
                                            "junit_logging=system-out"),
                    run_cwd, env, config.ACCEPTANCE_TIMEOUT_SEC)
        except CommandNotFound as exc:
            return [RedTest(rel, (), str(exc)) for rel in files]
        except subprocess.TimeoutExpired as exc:
            seeds = tuple(dict.fromkeys(_SEED_LINE.findall(
                _timeout_text(exc.stdout) + _timeout_text(exc.stderr))))
            note = f"прогон превысил {config.ACCEPTANCE_TIMEOUT_SEC}с"
            return [RedTest(rel, seeds, note) for rel in files]
        if res.returncode == 0:
            return []
        reds = _junit_red_tests(report, files)
    if reds:
        return reds
    note = f"pytest вернул {res.returncode}, отчёт не назвал тестов"
    seeds = tuple(dict.fromkeys(_SEED_LINE.findall(res.stdout + res.stderr)))
    return [RedTest(rel, seeds, note) for rel in files]


def materialize_from_branch(task_id: str, branch: str, code_dir: Path) -> Path:
    """`tasks/<id>/acceptance_tests/` каталога `code_dir` (рабочего
    каталога КОДА задачи — worktree self-target либо workspace внешнего
    target, тот же узел выбора, что `orchestrator/runner.py::role_cwd`),
    материализованный НА МЕСТЕ из ГОЛОВЫ ветки `branch` (SPEC
    01M1RNZ6V7TTTTYAHBMF8JBQQS, требование 1, AC-1) — тот же приём, что
    `artifact_branch.materialize_task_dir` уже применяет к `tasks/<id>/`
    целиком: файл на диске, отсутствующий в ветке (устаревшая копия
    предыдущего прогона — например, от ручного протокола Оператора на
    время бага), убирается, не просто дополняется; поверх временного
    каталога (`tempfile.mkdtemp`, регрессия №14) — планка, резолвящая
    `orchestrator/` от `__file__`, промахивалась мимо кода ветки задачи
    что через `__file__` (вложенность временного каталога не совпадала
    со штатным `tasks/<id>/acceptance_tests/`), что через `cwd`.

    Источник истины остаётся АРТЕФАКТНАЯ ветка задачи (`branch`, решение
    регрессии №12, SPEC «Не входит») — читается всегда через git
    (`gitcmd.ls_tree_files`/`gitcmd.show`), не с диска `code_dir`; меняется
    только каталог, в который планка записывается перед прогоном.

    В ветке нет `acceptance_tests/` — валидный исход: в каталоге планки
    лежит только помощник пульта `_pult.py` (SPEC
    01M44EP4Q927DJXVX9YMMZ0B7V, требование 3), и `run()`/`collect()`/
    `summary()` читают такой каталог через `plank_present` как «тесты не
    заведены», не отказ.

    Git не ответил на `ls_tree_files` (`None`, отдельно от легитимно
    пустой ветки — `[]`, REVIEW.md итерация 1, R1-F1) — тихая деградация,
    тем же приёмом, что `artifact_branch.materialize_task_dir`: диск не
    трогается вовсе, уже материализованная планка остаётся как есть.
    Иначе транзиентный сбой git на повторной материализации (второй
    проход review, повторная подтяжка main) стирал бы прунингом ниже
    уже реально лежащие на диске файлы планки, и `run()` красил бы
    задачу диагнозом «acceptance_tests красные» вместо честного «git не
    ответил, планка не проверена».

    Возврат — `code_dir / "tasks" / task_id` (совместим с `run()`,
    ожидающим `tdir / "acceptance_tests"`).
    """
    tdir = code_dir / "tasks" / task_id
    tests_dir = tdir / "acceptance_tests"
    prefix = f"tasks/{task_id}/acceptance_tests/"
    # Список и тексты читаются по sha, разрешённому один раз: коммит в
    # ссылку посреди выкладки не смешивает две ревизии, а помощник планки
    # (`_pult.py`) называет ровно ту ревизию, с которой выложены файлы.
    revision = _docs_revision(task_id, branch)
    source = revision or branch
    paths = artifact_branch.ls_tree(task_id, source,
                                    f"tasks/{task_id}/acceptance_tests")
    if paths is None:
        return tdir
    wanted: dict[str, str] = {}
    for rel in paths:
        if not rel.startswith(prefix):
            continue
        text, _ = artifact_branch.show(task_id, source, rel)
        if text is not None:
            wanted[rel[len(prefix):]] = text
    _write_plank(tests_dir, _with_plank_helper(task_id, wanted, code_dir,
                                               revision))
    return tdir


# Имя файла помощника пульта в каталоге планки (SPEC
# 01M44EP4Q927DJXVX9YMMZ0B7V, требования 3, 5): зарезервировано — свой файл
# планки с этим именем отклоняет выход из `tests_writing`
# (`advance_gates/tests_writing.py`), а при выкладке побеждает файл пульта.
PLANK_HELPER_NAME = "_pult.py"

# Блок значений выкладки в исходном тексте помощника: строка `ИМЯ = …`
# заменяется целиком подставленным литералом.
_PLANK_HELPER_SOURCE = Path(__file__).with_name("plank_helper.py")
_PLANK_HELPER_VALUE_NAMES = ("TASK_ID", "CODE_ROOT", "DOCS_REPO",
                             "DOCS_REVISION", "DIFF_BASE", "DIFF_BASE_SOURCE")


def _docs_revision(task_id: str, rev: str) -> str:
    """sha коммита `rev` (имя ссылки документов или уже sha) в репозитории
    задачи; пустая строка — git не ответил или ревизии нет."""
    res = artifact_branch.git(task_id, "rev-parse", "--verify", "--quiet",
                              f"{rev}^{{commit}}")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def _plank_helper_text(task_id: str, code_dir: Path, revision: str) -> str:
    """Исходный текст `orchestrator/plank_helper.py` с подставленными
    значениями выкладки. База диффа и её источник — `gitcmd.diff_base`/
    `diff_base_source` той же пары, что у гейта зон (`_zones_gate`): ветка
    задачи из БД в клоне проекта `workspace.task_repo` — рабочая копия
    делит с ним ссылки, а её собственный git на пути выкладки не
    спрашивается. Строки задачи в БД нет (песочница без пульта) — ветка
    под HEAD рабочей копии. Помощник базу сам не считает."""
    from . import store, workspace  # workspace -> runner -> acceptance
    code_dir = Path(code_dir).resolve()
    branch = (store.task_branch(store.db(), task_id)
              if store.db_usable() else "")
    repo = workspace.task_repo(task_id)
    if not branch:
        branch = gitcmd.current_branch(code_dir) or "HEAD"
        repo = code_dir
    values = {
        "TASK_ID": task_id,
        "CODE_ROOT": str(code_dir),
        "DOCS_REPO": str(artifact_branch.task_repo(task_id)),
        "DOCS_REVISION": revision,
        "DIFF_BASE": gitcmd.diff_base(branch, repo=repo),
        "DIFF_BASE_SOURCE": gitcmd.diff_base_source(branch, repo=repo),
    }
    text = _PLANK_HELPER_SOURCE.read_text(encoding="utf-8")
    for name in _PLANK_HELPER_VALUE_NAMES:
        text, count = re.subn(rf"^{name} = .*$",
                              lambda _m, n=name: f"{n} = {values[n]!r}",
                              text, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"{_PLANK_HELPER_SOURCE}: нет строки "
                               f"значения выкладки {name}")
    return text


def _with_plank_helper(task_id: str, wanted: dict[str, str | bytes],
                       code_dir: Path, revision: str
                       ) -> dict[str, str | bytes]:
    """`wanted` плюс помощник пульта: поверх одноимённого файла планки (он
    побеждает) и вне прунинга `_write_plank`. Кладётся и к пустой планке —
    роль, гоняющая свои проверки рядом, получает помощник всегда; каталог,
    где кроме помощника ничего нет, `plank_present` по-прежнему читает как
    «тесты не заведены»."""
    return {**wanted,
            PLANK_HELPER_NAME: _plank_helper_text(task_id, code_dir, revision)}


def _write_plank(tests_dir: Path, wanted: dict[str, str | bytes]) -> None:
    """Каталог планки `tests_dir` ровно с файлами `wanted` (путь от
    каталога планки -> содержимое): лишний файл на диске убирается, не
    просто дополняется — общий узел выкладки из ссылки документов и из
    черновика (`materialize_files`)."""
    if tests_dir.is_dir():
        for path in sorted(tests_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tests_dir).as_posix()
            if rel not in wanted:
                path.unlink()
    for rel, content in wanted.items():
        dest = tests_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            dest.write_bytes(content)
        else:
            dest.write_text(content, encoding="utf-8")


def materialize_files(task_id: str, files: dict[str, str | bytes],
                      code_dir: Path) -> Path:
    """`tasks/<id>/acceptance_tests/` каталога `code_dir` из явного набора
    файлов — черновика планки, ещё не зафиксированного в ссылке документов
    (`plank-run` в `tests_writing`, SPEC 01M41R4YAM4NGEQXW1FWH7T22M,
    требование 1). Возврат — тот же, что у `materialize_from_branch`.

    Ревизия ссылки документов помощника `_pult.py` — голова ссылки на
    момент выкладки: черновик в ссылку ещё не записан, артефакты задачи
    планка читает оттуда."""
    tdir = code_dir / "tasks" / task_id
    revision = _docs_revision(task_id, artifact_branch.branch_name(task_id))
    _write_plank(tdir / "acceptance_tests",
                 _with_plank_helper(task_id, files, code_dir, revision))
    return tdir


@contextlib.contextmanager
def plank_helper_laid_out(task_id: str, code_dir: Path) -> Iterator[Path]:
    """Только помощник пульта в `tasks/<id>/acceptance_tests/` каталога
    `code_dir` на время блока `with`, файлы планки на диске не трогаются:
    правку Оператора для `amend-tests` прунинг `_write_plank` стёр бы (SPEC
    01M4JD36367E5CG3GXDV429XTE, требование 1). Текст и ревизия — те же,
    что у `materialize_files`: правка ещё не в ссылке документов, артефакты
    задачи планка читает с её головы.

    На выходе (в том числе по отказу `sys.exit`) прежнее состояние
    помощника возвращается — отказ `amend-tests` оставляет каталог задачи
    побайтно как был (SPEC 01M42NBCADGSGTCBZB8NKBVDVH, требование 2); если
    каталога планки уже нет (успешная правка убрала `tasks/<id>/`), он не
    воссоздаётся."""
    tests_dir = Path(code_dir) / "tasks" / task_id / "acceptance_tests"
    helper = tests_dir / PLANK_HELPER_NAME
    created_dir = not tests_dir.is_dir()
    before = helper.read_bytes() if helper.is_file() else None
    revision = _docs_revision(task_id, artifact_branch.branch_name(task_id))
    tests_dir.mkdir(parents=True, exist_ok=True)
    try:
        helper.write_text(_plank_helper_text(task_id, code_dir, revision),
                          encoding="utf-8")
        yield helper
    finally:
        if tests_dir.is_dir():
            if before is None:
                helper.unlink(missing_ok=True)
            else:
                helper.write_bytes(before)
            if created_dir and not any(tests_dir.iterdir()):
                tests_dir.rmdir()


def drop_from_code_copy(task_id: str, code_dir: Path) -> None:
    """Убирает `tasks/<id>/` из рабочей копии кода `code_dir` (ADR-0021,
    этап 1): документы задачи там не лежат, планка — только на время
    прогона (`plank_in_code_copy`). Главная копия пульта (`config.ROOT`)
    не трогается: там `tasks/<id>/` — легаси-каталог задач старше T094, не
    выкладка прогона.

    Остаток выкладки `pytest-own` под `long_lived_dir`
    (`_plank_layout`), переживший обрыв прогона, убирается тут же; как и
    остаток выкладки по `plank_layout` (`_component_layout`): каталог `<id>`
    и опустевший родитель, файлы кода в родителе не трогаются."""
    if Path(code_dir).resolve() == config.ROOT.resolve():
        return
    shutil.rmtree(Path(code_dir) / "tasks" / task_id, ignore_errors=True)
    from . import store  # store -> ... -> acceptance
    try:
        own = _task_own_profile(store.db() if store.db_usable() else None,
                                task_id)
    except targets.ComponentsPending:
        # До G1б выкладки по компонентам нет — убирать под ней нечего.
        return
    if _layout_mode(own) == "layout":
        _drop_layout(_layout_root(code_dir, own, task_id))
    if _uses_plank_layout(own):
        # Остаток выкладки по `plank_layout`: только при годной форме —
        # иначе каталога `<id>` выкладка не заводила, и под ним может быть код.
        parent, refusal = _layout_check(own, Path(code_dir))
        if not refusal:
            _drop_component_layout(Path(code_dir) / parent / task_id)


@contextlib.contextmanager
def plank_in_code_copy(task_id: str, branch: str, code_dir: Path,
                       files: dict[str, str | bytes] | None = None
                       ) -> Iterator[Path]:
    """`materialize_from_branch` на время блока `with` и уборка выкладки в
    `finally` — на зелёном, красном исходе и на исключении внутри прогона
    (ADR-0021 п.13, этап 1): прогону планка нужна в рабочей копии кода
    (её `__file__` находит код ветки задачи), после него — нет.

    `files` — выложить этот набор (`materialize_files`) вместо головы
    `branch`: черновик планки `plank-run` в `tests_writing` (SPEC
    01M41R4YAM4NGEQXW1FWH7T22M, требование 1) — уборка та же."""
    try:
        if files is None:
            yield materialize_from_branch(task_id, branch, code_dir)
        else:
            yield materialize_files(task_id, files, code_dir)
    finally:
        drop_from_code_copy(task_id, code_dir)


def run_plank(targets: list[str], cwd: Path,
              profile=None, task_id: str | None = None
              ) -> tuple[int | None, str]:
    """(код выхода pytest, весь вывод) — прогон `targets` тем же раннером
    (`_pytest_command`, `_pytest_env`) и тем же таймаутом
    (`config.ACCEPTANCE_TIMEOUT_SEC`), что `run()` пульта, но для человека
    или роли, а не гейта: вывод не обрезается, код выхода не сворачивается
    в «зелёно/красно» (`plank-run`, SPEC 01M41R4YAM4NGEQXW1FWH7T22M,
    требование 1). `None` — прогон превысил таймаут.

    `profile` — профиль тестов проекта (контракт канала `command` у
    `run()`); не передан — раннер пульта. Отказ запуска `pytest-own` —
    `REFUSED_EXIT_CODE` и текст отказа.

    `task_id` — цели лежат в планке задачи `tasks/<id>/acceptance_tests`
    рабочей копии `cwd`: у `pytest-own` с `long_lived_dir` внутри `workdir`
    они гонятся из выкладки (`_plank_layout`) тем же путём от каталога
    планки; у компонента с `report` — по правилу планки и `plank_layout`
    (`_plank_plan`): каталог планки — выложенные файлы компонента. Не
    передан — цели как есть (долгоживущий файл, раннер пульта)."""
    run_cwd = cwd
    own = _own(profile)
    if own is not None:
        run_cwd, refusal = _own_cwd(own, cwd)
        if refusal:
            return REFUSED_EXIT_CODE, refusal
    tests_dir = Path(cwd) / "tasks" / (task_id or "") / "acceptance_tests"
    plan = _plank_plan(tests_dir, profile) if task_id else _PlankPlan()
    if plan.refusal:
        return REFUSED_EXIT_CODE, plan.refusal
    with _laid_plank(plan, task_id or "", tests_dir, cwd,
                     own if task_id else None) as laid:
        case_note = laid.note
        if laid.refusal:
            return REFUSED_EXIT_CODE, laid.refusal
        if plan.files:
            args = [a for t in targets
                    for a in _component_target(t, cwd, tests_dir, laid)]
        elif plan.absent:
            args = [t for t in targets
                    if _component_target(t, cwd, tests_dir, _Laid()) == [t]]
            if not args:
                return REFUSED_EXIT_CODE, PLANK_ABSENT_NOTE
        else:
            args = [_layout_target(t, cwd, tests_dir, laid.root)
                    for t in targets]
        reported = _reported(profile)
        if reported is not None:
            code, output = _run_plank_reported(reported, args, cwd)
        else:
            if own is not None:
                args = [_own_target(own, t) for t in args]
            code, output = _run_plank_now(profile, args, run_cwd)
    return code, f"{case_note}\n{output}" if case_note else output


def _run_plank_reported(profile, args: list[str],
                        tree: Path) -> tuple[int | None, str]:
    """`run_plank()` профиля с отчётом: код 0 — только зелёный итог из
    отчёта; отказ подготовки — `REFUSED_EXIT_CODE`; предел — `None`;
    иначе код раннера, а при нулевом — 1 (красный или «неизвестно»)."""
    run = _report_run(profile, tree, list(args), config.ACCEPTANCE_TIMEOUT_SEC)
    if run.refusal:
        return REFUSED_EXIT_CODE, run.refusal
    if run.timed_out:
        return None, (f"{run.raw}\nпрогон превысил "
                      f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                      f"сетевой ответ")
    if run.green:
        return 0, run.text()
    return run.code or 1, run.text()


def _layout_target(arg: str, cwd: Path, tests_dir: Path,
                   layout: Path | None) -> str:
    """Цель `arg` (путь от `cwd`, с `::узлом` или без), лежащая в каталоге
    планки, — тот же путь в выкладке `layout` (абсолютный); иначе как есть."""
    if layout is None:
        return arg
    path, sep, node = arg.partition("::")
    rel = os.path.relpath(os.path.join(str(cwd), path), str(tests_dir))
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return arg
    return os.path.normpath(os.path.join(str(layout), rel)) + sep + node


def _component_target(arg: str, cwd: Path, tests_dir: Path,
                      laid: _Laid) -> list[str]:
    """Цели выкладки по `plank_layout` вместо цели `arg`: сам каталог
    планки — цели выкладки (`laid.targets`), файл в нём — тот же файл прямо
    в каталоге выкладки; цель вне каталога планки — как есть."""
    path, sep, node = arg.partition("::")
    rel = os.path.relpath(os.path.join(str(cwd), path), str(tests_dir))
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return [arg]
    if laid.root is None:
        return []
    if rel == os.curdir:
        return list(laid.targets or ())
    return [os.path.normpath(os.path.join(str(laid.root), rel)) + sep + node]


def _run_plank_now(profile, args: list[str],
                   run_cwd: Path) -> tuple[int | None, str]:
    """Сам вызов pytest `run_plank()` по готовым целям."""
    try:
        with _place_env(profile, run_cwd) as env:
            res = _run_pytest(profile, _place_command(profile, *args),
                              run_cwd, env, config.ACCEPTANCE_TIMEOUT_SEC)
    except CommandNotFound as exc:
        return REFUSED_EXIT_CODE, str(exc)
    except subprocess.TimeoutExpired as exc:
        return None, (_timeout_text(exc.stdout) + _timeout_text(exc.stderr)
                      + f"\nпрогон превысил {config.ACCEPTANCE_TIMEOUT_SEC}с "
                        f"— завис или ждёт сетевой ответ")
    return res.returncode, res.stdout + res.stderr


# ----------------------------------------------- полный набор tests/
#
# Исходы прогона полного набора (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
# требование 4): до этой задачи все три не-зелёных схлопывались в одну
# фразу «полный набор tests/ красный», и причину восстанавливали по
# времени событий (26.09).
FULL_SUITE_GREEN = "зелёный прогон"
FULL_SUITE_RED = "красный прогон"
FULL_SUITE_TIMEOUT = "таймаут прогона"
FULL_SUITE_NO_TESTS = "tests/ нет в worktree"
# Прогон не запускался: замок полных прогонов машины занят дольше
# `config.FULL_SUITE_LOCK_WAIT_SEC` (SPEC 01M46D5T8SZ9D6S34TZFX8S46V,
# требование 2) — ни красный прогон, ни таймаут прогона. Константа —
# одновременно начало текста исхода (`_not_started_note`), по которому его
# различает `_full_suite_outcome`.
FULL_SUITE_NOT_STARTED = "прогон не начат"

# Запись журнала задачи об ожидании замка прогоном гейта (требование 2).
FULL_SUITE_LOCK_WAIT_ACTION = "полный прогон ждёт замок"

# Текст вырожденного исхода «в рабочей копии нет каталога tests/» — одна
# константа и для `run_full_suite` (производитель), и для
# `_full_suite_outcome` (потребитель): исход различается по тексту,
# который пульт сам же и написал, и расхождение двух копий этого текста
# молча ломало бы классификацию.
FULL_SUITE_NO_TESTS_NOTE = "tests/ нет в worktree — полный набор не проверен"

# «Роль» в имени файла лога полного набора: `agent_log.new_agent_log`
# складывает имя как `<task>-<role>-<N>.log`, то есть `.artel/logs/
# <id>-fullsuite-<n>.log` (требование 3 прямо разрешает имя по этому
# образцу). Своей нумерации задача не заводит — она там уже есть, и
# второй её источник разошёлся бы с первым.
FULL_SUITE_LOG_KIND = "fullsuite"


def _full_suite_timeout_note(limit: tuple[int, str] | None = None) -> str:
    """Текст исхода «прогон не уложился в потолок» — функция, не
    константа: `config.FULL_SUITE_TIMEOUT_SEC` подменяют тесты, и значение
    обязано читаться в момент вызова (тот же довод, что и у
    `FULL_SUITE_NO_TESTS_NOTE` — один текст на производителя и
    потребителя)."""
    seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
    return (f"прогон полного набора tests/ превысил "
            f"{seconds}с — завис или ждёт сетевой ответ "
            f"(источник: {source})")


def _not_started_note(holder: dict) -> str:
    """Текст исхода «прогон не начат» — функция по тому же доводу, что
    `_full_suite_timeout_note`: предел ожидания подменяют тесты."""
    return (f"{FULL_SUITE_NOT_STARTED}: машина занята прогоном "
            f"{suite_lock.describe(holder)} — замок полных прогонов не "
            f"освободился за {config.FULL_SUITE_LOCK_WAIT_SEC} с ожидания, "
            f"pytest не запускался")


# Флаг `approve <id> --fresh-suite` (`artel.py`): называется в тексте
# итога, взятого из кэша, — как прогнать набор заново (SPEC
# 01M4FYTB8QWJNHYCP35K8QC4E3, требование 5).
FRESH_SUITE_FLAG = "--fresh-suite"

# Пометка записи журнала о файле БД пульта, заведённом самим прогоном
# набора (SPEC 01M4FYTB8QWJNHYCP35K8QC4E3, требование 4).
FULL_SUITE_DB_CREATED_ACTION = ("прогон набора создал файл БД — неполная "
                                "изоляция тестов")


def _db_in_tree_note(root: Path, task_id: str, found: list[str]) -> str:
    """Текст отказа «в дереве прогона файлы БД пульта» (SPEC
    01M4FYTB8QWJNHYCP35K8QC4E3, требование 4). Исход — «прогон не начат»:
    набор не запускался, и все потребители узла (автогейт, `approve`, гейт
    мержа) читают его как «не проверен», а не как красноту задачи. Тест,
    импортировавший пакет из этого дерева, принял бы такой файл за БД
    пульта — 09.10 так краснели одни и те же 7 тестов два прогона подряд."""
    paths = ", ".join(str(Path(root) / rel) for rel in found)
    return (f"{FULL_SUITE_NOT_STARTED}: полный набор tests/ не проверен — в "
            f"дереве прогона лежат файлы БД пульта: {paths}; убрать их: "
            f"artel.py worktree-db-clean {task_id}, затем повторить гейт")


def _journal_db_files_created(root: Path, task_id: str,
                              recordable: bool) -> None:
    """След файла БД пульта, появившегося в дереве за время прогона (до
    прогона их там не было — иначе отказ `_db_in_tree_note`). Исход прогона
    и запись итога от этого не зависят; сбой записи журнала прогон не
    роняет."""
    from . import store  # store -> ... -> acceptance
    created = store.tree_db_files(root)
    if not created:
        return
    detail = ", ".join(str(Path(root) / rel) for rel in created)
    print(f"[{task_id}] {FULL_SUITE_DB_CREATED_ACTION}: {detail}", flush=True)
    if not recordable:
        return
    try:
        store.journal(store.db(), task_id, "orchestrator",
                      FULL_SUITE_DB_CREATED_ACTION, detail)
    except sqlite3.Error as exc:
        print(f"[{task_id}] запись журнала не удалась: {exc}", file=sys.stderr)


class FullSuiteRun(NamedTuple):
    """Исход прогона полного набора с разбором и файлом лога (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требования 3-6) — общий для трёх
    потребителей: автогейта приёмки, гейта мержа и `approve` в
    `acceptance`.

    `outcome` — одна из четырёх констант `FULL_SUITE_*`; `digest` —
    выжимка `run_digest`; `log_path` — файл с ПОЛНЫМ выводом прогона
    (`None`: прогона не было вовсе либо запись лога не удалась);
    `detail` — готовая строка для журнала: различимая причина, выжимка и
    путь к логу. `tests` — итог по каждому тесту из отчёта компонента
    (`reporters.outcome.CaseResult`, SPEC 01M590GJAF0EDV4NBC4C99MFVH,
    ANSWER-2, В3); у прогона без отчёта — пусто.
    """

    green: bool
    outcome: str
    digest: str
    log_path: Path | None
    detail: str
    tests: tuple = ()


def _full_suite_outcome(green: bool, output: str) -> str:
    """Исход прогона по его тексту — по префиксу СВОЕГО ЖЕ сообщения о
    вырожденном исходе (см. `FULL_SUITE_NO_TESTS_NOTE`), не по разбору
    вывода pytest: сам pytest про «каталога нет» и «не уложился в
    потолок» ничего не печатает — это решения `run_full_suite`. Исход
    «неизвестно» (`UNKNOWN_PREFIX`) — значение «прогон не начат»
    (требование 3)."""
    if green:
        return FULL_SUITE_GREEN
    if output.startswith(FULL_SUITE_NO_TESTS_NOTE):
        return FULL_SUITE_NO_TESTS
    if output.startswith(f"{FULL_SUITE_NOT_STARTED}: ") or \
            output.startswith(UNKNOWN_PREFIX):
        return FULL_SUITE_NOT_STARTED
    if output.startswith("прогон полного набора tests/ превысил "):
        return FULL_SUITE_TIMEOUT
    return FULL_SUITE_RED


def _write_full_suite_log(task_id: str, output: str) -> Path | None:
    """Полный вывод прогона — в файл рядом с логами ролей (требование 3);
    `None` — файл не записался.

    Сбой записи лога не имеет права уронить гейт, который этот прогон
    обслуживает (тот же приём деградации, что у `agent_log.stream_to_log`
    для лога шага): запись журнала останется без пути к файлу, но с
    выжимкой разбора."""
    try:
        path = agent_log.new_agent_log(task_id, FULL_SUITE_LOG_KIND)
        path.write_text(output, encoding="utf-8")
        return path
    except OSError:
        return None


def _full_suite_detail(outcome: str, digest: str,
                       log_path: Path | None, note: str = "") -> str:
    """Строка журнала об исходе прогона: различимая причина, выжимка
    разбора и путь к файлу лога (требования 4-6). `note` — текст исхода
    «прогон не начат» с держателем замка."""
    if outcome == FULL_SUITE_NO_TESTS:
        # Прогона не было — ни выжимки, ни лога не существует.
        return FULL_SUITE_NO_TESTS_NOTE
    if outcome == FULL_SUITE_NOT_STARTED:
        return note or FULL_SUITE_NOT_STARTED
    head = {
        FULL_SUITE_GREEN: "полный набор tests/ зелёный",
        FULL_SUITE_RED: "полный набор tests/ красный",
        FULL_SUITE_TIMEOUT: note or _full_suite_timeout_note(),
    }[outcome]
    log_note = f" (лог прогона: {log_path})" if log_path is not None else ""
    return f"{head}: {digest}{log_note}"


def run_full_suite(root: Path, command: list[str] | None = None,
                   targets: tuple = ("tests",), extra: tuple = (),
                   log: Path | None = None,
                   limit: tuple[int, str] | None = None,
                   test_ids: tuple = ()) -> tuple[bool, str]:
    """(зелено, ПОЛНЫЙ вывод прогона) — прогон ПОЛНОГО пакета `tests/`
    каталога `root` через pytest (SPEC T066, требование 2в; переход раннера —
    SPEC 01M1TKP6AAY4W8GDGZNA9R0JZT, требование 1): условие автогейта
    acceptance; штатный CI-джоб `python` (`.github/workflows/ci.yml`)
    остаётся на unittest — переход CI вне зоны этой задачи (SPEC, «Не
    входит»).

    `tests/` нет вовсе — не «зелено»: в отличие от `run()` (отсутствие
    acceptance_tests/ — легитимный «нечего гонять»), отсутствие ПОЛНОГО
    набора в worktree ветки задачи ничего не проверяет и не имеет права
    сойти за пройденное условие автогейта.

    `-p no:cacheprovider` — тот же довод, что у `run()` выше (требование 5).
    `-o timeout=…` — тот же довод, что у `run()` выше (требование 4, AC-7):
    таймаут отдельного теста передаётся явно, не через обнаружение
    `pyproject.toml` pytest'ом самостоятельно.

    `-n config.FULL_SUITE_WORKERS -p xdist` (01M291M2Z76M84GVP25J387A66,
    требование 1/AC-1): параллель только здесь, не в `_pytest_command`
    выше — `run()` (планка задачи) остаётся последовательной (требование
    1, «Не входит»). Явная загрузка `-p xdist`, тем же приёмом, что и
    `-p timeout` в `_pytest_command`: пакета `pytest-xdist` нет в
    интерпретаторе — pytest откажет ненулевым returncode и сообщением о
    неизвестном плагине в stderr, `res.returncode == 0` ниже это ловит
    как обычный красный прогон, без тихого повторного прогона без `-n`
    (AC-3).

    Вывод отдаётся ЦЕЛИКОМ, без прежнего среза `[-2000:]` (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требование 3): полный вывод нужен файлу
    лога (`full_suite` выше), а в журнал уходит уже не он, а выжимка
    `run_digest`, ограниченная `config.LOG_TAIL_*` — записи журнала от
    этого только короче, чем были со срезом.

    Параметры команды `suite-run` (SPEC 01M462QACEH29RPRD2RZHGHQFM,
    требования 1, 6, 10); гейты их не передают, и их прогон не меняется:
    `command` — начало команды из профиля тестов проекта (как у `run()`);
    `targets` — пути или id тестов вместо `tests` (повтор упавших);
    `extra` — флаги pytest после флагов параллели; `log` — вывод идёт
    прямо в этот файл по ходу прогона (ход прогона читается из него, пока
    прогон идёт), а на пределе времени убивается вся группа процессов
    pytest с рабочими xdist — фоновому прогону некому добить сирот.

    Прогон идёт под замком полных прогонов машины (`suite_lock`, SPEC
    01M46D5T8SZ9D6S34TZFX8S46V, требования 1-4), `_machine_lock`: прогон
    без задачи (`notes`) пишет ожидание в вывод; процесс, уже держащий
    замок (`full_suite` гейта, фоновый процесс `suite-run`), идёт без
    второго взятия.

    `command` — профиль `pytest-own` (SPEC 01M52EEFNA1WH31962HVNT0YZ9,
    требования 2-4): команда профиля без параллели пульта, в `workdir`;
    цель полного набора — `long_lived_dir` (и когда передано `tests`),
    прочие пути от корня переведены к `workdir`, id тестов — как есть;
    каталога `long_lived_dir` нет — «тестов нет»; `workdir` вне дерева —
    «прогон не начат» без прогона.

    `test_ids` — id упавших тестов (`suite-run --failed`, ANSWER-1 SPEC
    01M52EEFNA1WH31962HVNT0YZ9) в той форме, в какой их напечатал pytest:
    идут в argv после целей без перевода к `workdir`.
    """
    global _last_full_suite_metrics, _last_process_snapshot, _last_run_completed_at
    global _last_report_tests
    observe = _observe_full_suite
    _last_full_suite_metrics = None
    _last_process_snapshot = None
    _last_run_completed_at = None
    _last_report_tests = ()
    full_run = tuple(targets) == ("tests",) and not test_ids
    reported = _reported(command)
    if reported is not None:
        return _run_full_suite_reported(root, reported, targets, test_ids,
                                        log, limit, full_run)
    own = _own(command)
    run_cwd = root
    if own is None:
        tests_dir = root / "tests"
        if not tests_dir.is_dir():
            return False, FULL_SUITE_NO_TESTS_NOTE
        argv = _pytest_command(*targets, *test_ids, command=_head(command)) + [
            "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist", *extra]
    else:
        run_cwd, refusal = _own_cwd(own, root)
        if refusal:
            return False, f"{FULL_SUITE_NOT_STARTED}: {refusal}"
        if not (root / own.long_lived_dir).is_dir():
            return False, FULL_SUITE_NO_TESTS_NOTE
        args = [_own_target(own, own.long_lived_dir if t == "tests" else t)
                for t in targets]
        # Остаток выкладки планки собирался бы при любом `norecursedirs`
        # проекта.
        args += _layout_ignore(own)
        argv = _place_command(own, *args, *test_ids, *extra)
    limit = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
    with _machine_lock(None, limit) as holder:
        if holder is not None:
            return False, _not_started_note(holder)
        if own is not None:
            # Ожидание замка бывает долгим: `realpath` сверяется заново
            # перед самим прогоном (требование 3, «в момент прогона»).
            run_cwd, refusal = _own_cwd(own, root)
            if refusal:
                return False, f"{FULL_SUITE_NOT_STARTED}: {refusal}"
        start = time.monotonic()
        load_start = os.getloadavg() if observe else (0.0, 0.0)
        try:
            green, output = _run_full_suite_now(argv, run_cwd, log, limit,
                                                observe, profile=own)
        except CommandNotFound as exc:
            # Не красный прогон: pytest не запускался, итог не кешируется.
            return False, f"{FULL_SUITE_NOT_STARTED}: {exc}"
        duration = time.monotonic() - start
        timed_out = output.startswith("прогон полного набора tests/ превысил ")
        if observe:
            _last_full_suite_metrics = _suite_metrics(
                start, load_start, argv, output, timed_out,
                _last_process_snapshot, _last_run_completed_at)
            duration = _last_full_suite_metrics["duration_seconds"]
        # Повтор упавших (`suite-run --failed`) — не полный прогон: его
        # длительность с пределом полного набора не сравнивается.
        if full_run:
            _signal_near_limit(root, duration, limit, _last_full_suite_metrics)
        if observe and timed_out:
            head, newline, rest = output.partition("\n")
            output = f"{head}\n{suite_load_line(_last_full_suite_metrics)}\n{rest}"
        return green, output


# Итог по каждому тесту последнего прогона `run_full_suite` профиля с
# отчётом — его читает `full_suite` в `FullSuiteRun.tests` (вывод
# `run_full_suite` — пара «зелено, текст», её форму знают `suite-run` и
# `notes`).
_last_report_tests: tuple = ()


def _report_subset(profile, targets: tuple, test_ids: tuple) -> list | None:
    """Подмножество полного прогона компонента: `None` — полный набор;
    иначе пути целей, а id `<компонент>:<путь>::<имя>` (`suite-run
    --failed`) — их пути (повтор идёт по файлу)."""
    from . import project_profile
    items = [t for t in (*targets, *test_ids) if t != "tests"]
    if tuple(targets) == ("tests",) and not test_ids:
        return None
    subset = []
    for item in items:
        try:
            comp, path, _name, _n = project_profile.parse_test_id(item)
        except ValueError:
            comp, path = "", item
        if comp != _component_name(profile):
            path = item
        if path not in subset:
            subset.append(path)
    return subset


def _run_full_suite_reported(root: Path, profile, targets: tuple,
                             test_ids: tuple, log: Path | None,
                             limit: tuple[int, str] | None,
                             full_run: bool) -> tuple[bool, str]:
    """`run_full_suite` профиля с отчётом (SPEC 01M590GJAF0EDV4NBC4C99MFVH,
    требования 1, 3, 9): команда компонента без флагов параллели и `-vv`
    пульта (`extra` не передаётся), итог — из отчёта. Отказ подготовки —
    «прогон не начат: …»; «неизвестно» — `unknown_line` первой строкой;
    иначе вывод раннера и сводка из отчёта в конце (её читают
    `run_summary_line`, `failed_entries`, `suite_run.parse`)."""
    global _last_report_tests
    own = _own(profile)
    subset = _report_subset(profile, targets, test_ids)
    if subset is None and own is not None and \
            not (root / own.long_lived_dir).is_dir():
        return False, FULL_SUITE_NO_TESTS_NOTE
    limit = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
    with _machine_lock(None, limit) as holder:
        if holder is not None:
            return False, _not_started_note(holder)
        start = time.monotonic()
        run = _report_run(profile, root, subset, limit[0], log=log)
        if full_run and not run.refusal:
            _signal_near_limit(root, time.monotonic() - start, limit, None)
    if run.refusal:
        return False, f"{FULL_SUITE_NOT_STARTED}: {run.refusal}"
    if run.timed_out:
        return False, f"{_full_suite_timeout_note(limit)}\n{run.raw}"
    _last_report_tests = run.tests
    if log is not None and run.block:
        with contextlib.suppress(OSError), open(log, "a", encoding="utf-8") as fh:
            fh.write(f"\n{run.block}\n")
    return run.green, run.text()


# Порог сигнала «длительность близка к пределу» (SPEC
# 01M4K2767FXKZ8EW7AME81SZ9N, требование 2; строка 32 docs/triggers.md):
# доля предела полного прогона, начиная с которой прогон оставляет запись
# журнала задачи (у `notes` — строку вывода) и алерт kind=trigger. Рост
# времени набора до этой задачи замечали только по отказу «таймаут прогона».
SUITE_NEAR_LIMIT_RATIO = 0.8
SUITE_NEAR_LIMIT_ACTION = "полный прогон: длительность близка к пределу"
# Источник алерта: один открытый алерт на проект, как у `map.growth`
# (ANSWER-1, п.2) — дедуп по источнику, а не по тексту: текст несёт
# длительность и у каждого прогона свой.
SUITE_NEAR_LIMIT_SOURCE = "suite.near_limit"


def _load_text(metrics: dict | None) -> str:
    if metrics is not None:
        return suite_load_line(metrics)
    try:
        load_1, load_5, _ = os.getloadavg()
    except OSError:
        return "нагрузка: load average недоступен"
    return f"нагрузка: load average 1/5 мин {load_1:.2f}/{load_5:.2f}"


def _signal_near_limit(root: Path, duration: float, limit: tuple[int, str],
                       metrics: dict | None) -> None:
    """Сигнал прогона, длившегося не меньше `SUITE_NEAR_LIMIT_RATIO` своего
    предела: строка вывода, запись журнала задачи держателя замка (гейт,
    `suite-run`; у `notes` задачи нет) и алерт kind=trigger проекта, если
    открытого такого же нет. Исход прогона сигнал не меняет, и сбой записи
    прогон не роняет (требование 2)."""
    seconds, source = limit
    if duration < SUITE_NEAR_LIMIT_RATIO * seconds:
        return
    from . import alerts, store  # store -> ... -> acceptance
    task_id = suite_lock.my_task_id()
    detail = (f"полный прогон tests/ ({root}) длился {duration:.1f} с — "
              f"{duration / seconds:.0%} предела {seconds} с (источник: "
              f"{source}), порог {SUITE_NEAR_LIMIT_RATIO:.0%}; "
              f"{_load_text(metrics)}")
    line = f"{SUITE_NEAR_LIMIT_ACTION}: {detail}"
    if store.db_usable():
        try:
            conn = store.db()
            target = config.DEFAULT_TARGET
            if task_id:
                target = store.task_target(conn, task_id) or target
                store.journal(conn, task_id, "orchestrator",
                              SUITE_NEAR_LIMIT_ACTION, detail)
            if not any(row["source"] == SUITE_NEAR_LIMIT_SOURCE
                       and row["target"] == target
                       for row in alerts.open_alerts(conn, "trigger")):
                who = f"задача {task_id}" if task_id else "notes"
                alerts.raise_alert(
                    conn, target, "trigger", SUITE_NEAR_LIMIT_SOURCE,
                    f"длительность полного прогона tests/ близка к пределу: "
                    f"{duration:.0f} с "
                    f"из {seconds} с (источник: {source}), порог "
                    f"{SUITE_NEAR_LIMIT_RATIO:.0%} ({who}) — docs/triggers.md "
                    f"№32")
        except Exception as exc:  # noqa: BLE001 — запись не условие прогона
            line += f" (запись сигнала не удалась: {type(exc).__name__})"
    print(f"[{task_id}] {line}" if task_id else line, flush=True)


@contextlib.contextmanager
def _machine_lock(task_id: str | None,
                  limit: tuple[int, str] | None = None) -> Iterator[dict | None]:
    """Замок полных прогонов машины на время прогона: даёт `None` — замок
    за текущим процессом, иначе держатель, не отпустивший замок за
    `config.FULL_SUITE_LOCK_WAIT_SEC` (прогон тогда не запускается).

    Ожидание — до входа в прогон, поэтому в предел прогона
    `config.FULL_SUITE_TIMEOUT_SEC` не входит (требование 2); взятый здесь
    замок снимается на любом исходе тела — зелёном, красном, таймауте,
    исключении (требование 4). Уже держащий замок процесс его не берёт и
    не снимает: снимет тот, кто брал."""
    if suite_lock.held_by_me():
        yield None
        return
    holder = suite_lock.wait_acquire(
        task_id, suite_lock.KIND_GATE if task_id else suite_lock.KIND_NOTES,
        config.FULL_SUITE_LOCK_WAIT_SEC,
        lambda busy: _journal_lock_wait(task_id, busy, limit))
    if holder is not None:
        yield holder
        return
    try:
        yield None
    finally:
        suite_lock.release()


def _journal_lock_wait(task_id: str | None, holder: dict,
                       limit: tuple[int, str] | None = None) -> None:
    """Запись об ожидании замка: журнал задачи и вывод; без задачи —
    только вывод. Сбой записи журнала прогон не роняет: ожидание и сам
    прогон от неё не зависят."""
    seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
    text = (f"машина занята прогоном {suite_lock.describe(holder)} — "
            f"полный прогон tests/ ждёт замок не дольше "
            f"{config.FULL_SUITE_LOCK_WAIT_SEC} с; ожидание в предел прогона "
            f"{seconds} с (источник: {source}) не входит")
    if task_id:
        from . import store  # store -> ... -> acceptance
        try:
            store.journal(store.db(), task_id, "orchestrator",
                          FULL_SUITE_LOCK_WAIT_ACTION, text)
        except Exception as exc:  # noqa: BLE001 — запись не условие прогона
            text += f" (запись журнала не удалась: {type(exc).__name__})"
    print(f"[{task_id}] {text}" if task_id else text, flush=True)


def _run_full_suite_now(argv: list[str], root: Path,
                        log: Path | None,
                        limit: tuple[int, str],
                        observe: bool = False,
                        profile=None) -> tuple[bool, str]:
    """Сам прогон `run_full_suite` — замок уже взят; предел
    `config.FULL_SUITE_TIMEOUT_SEC` отсчитывается отсюда. `root` — `cwd`
    прогона (у `pytest-own` — `workdir`); `profile` — профиль
    `pytest-own`: его окружение и снятие группы процессов и без
    наблюдения (`_run_pytest`)."""
    if log is not None:
        return _run_full_suite_to_log(argv, root, log, limit, observe,
                                      profile=profile)
    if observe:
        global _last_process_snapshot, _last_run_completed_at
        with _place_env(profile, root) as env:
            proc = _launch(
                argv, root, profile is not None, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True)
            try:
                stdout, stderr = proc.communicate(timeout=limit[0])
            except subprocess.TimeoutExpired as exc:
                _last_run_completed_at = time.monotonic()
                _last_process_snapshot = _process_snapshot(proc.pid)
                _kill_group(proc.pid)
                proc.communicate()
                output = _timeout_text(exc.stdout) + _timeout_text(exc.stderr)
                return False, f"{_full_suite_timeout_note(limit)}\n{output}"
            except BaseException:
                _kill_group(proc.pid)
                proc.communicate()
                raise
        _last_run_completed_at = time.monotonic()
        _last_process_snapshot = _process_snapshot(proc.pid)
        return proc.returncode == 0, stdout + stderr
    try:
        with _place_env(profile, root) as env:
            res = _run_pytest(profile, argv, root, env, limit[0])
    except subprocess.TimeoutExpired as exc:
        output = _timeout_text(exc.stdout) + _timeout_text(exc.stderr)
        return False, f"{_full_suite_timeout_note(limit)}\n{output}"
    return res.returncode == 0, res.stdout + res.stderr


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


@contextlib.contextmanager
def _durations_reader(log: Path, profile) -> Iterator[None]:
    """Поток времени тестов на время тела: начало прогона — вход сюда, до
    запуска pytest; остановка и ожидание потока — на выходе из тела, то
    есть после отметки конца прогона. Сбой потока прогон не меняет."""
    if profile is not None:
        yield
        return
    from . import suite_durations  # suite_durations -> suite_run -> acceptance
    reader = None
    try:
        reader = suite_durations.Reader(log, time.monotonic()).start()
    except Exception:  # noqa: BLE001 — файл времени не условие прогона
        pass
    try:
        yield
    finally:
        if reader is not None:
            reader.stop()


def _run_full_suite_to_log(argv: list[str], root: Path,
                           log: Path,
                           limit: tuple[int, str],
                           observe: bool = False,
                           profile=None) -> tuple[bool, str]:
    """Прогон `run_full_suite` с выводом прямо в файл `log`. Вывод
    читается из файла байтами с заменой не-UTF-8: чужой проект вправе
    печатать что угодно, а разбор не имеет права уронить фоновый прогон.
    `PYTHONUNBUFFERED` — иначе на пределе времени SIGKILL съел бы
    неслитый буфер, и числа успевшей части пропали бы (требование 6).
    `root`/`profile` — тот же контракт, что у `_run_full_suite_now`.

    Раннер `pult-pytest` (`profile is None`) — поток чтения лога пишет
    время каждого теста в файл рядом с логом (`_durations_reader`, SPEC
    01M5MJFSYW6MH0WD05CY8V75TX); его останавливают и ждут после отметки
    `_last_run_completed_at`."""
    timed_out = False
    with _place_env(profile, root) as env, open(log, "wb") as fh, \
            _durations_reader(log, profile):
        env["PYTHONUNBUFFERED"] = "1"
        proc = _launch(argv, root, profile is not None, env=env, stdout=fh,
                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                       start_new_session=True)
        try:
            code = proc.wait(timeout=limit[0])
        except subprocess.TimeoutExpired:
            timed_out = True
            if observe:
                global _last_process_snapshot, _last_run_completed_at
                _last_run_completed_at = time.monotonic()
                _last_process_snapshot = _process_snapshot(proc.pid)
            _kill_group(proc.pid)
            proc.wait()
        except BaseException:
            _kill_group(proc.pid)
            proc.wait()
            raise
        if observe and not timed_out:
            _last_run_completed_at = time.monotonic()
            _last_process_snapshot = _process_snapshot(proc.pid)
    output = log.read_bytes().decode("utf-8", errors="replace")
    if timed_out:
        return False, f"{_full_suite_timeout_note(limit)}\n{output}"
    return code == 0, output


# ----------------------------------------- сохранённые итоги полного набора
#
# Перечень упавших тестов завершённого прогона полного набора по sha дерева,
# на котором он шёл (SPEC 01M462QACEH29RPRD2RZHGHQFM, требования 7-8):
# итог базы для `suite-run` любой задачи с этой базой — второй раз база не
# прогоняется. Пишут его гейты (`full_suite`) и прогон базы `suite-run`.

_FAILED_ENTRY = re.compile(r"^(?:FAILED|ERROR) (.+?)(?: - (.*))?$",
                           re.MULTILINE)
# Упавший подтест в коротком итоге: `SUBFAILED<метка> <nodeid> - <сообщение>`.
# nodeid — слово с `::` перед « - », метка — всё между `SUBFAILED` и nodeid
# (пробелы, скобки и кавычки в ней — как их печатает pytest; вид метки
# зависит от xdist: `(i=1)` без него, `(i='1')` с ним).
_SUBFAILED_ENTRY = re.compile(
    r"^SUBFAILED(.*?) ?(\S*::\S*)(?: - (.*))?$", re.MULTILINE)
_SHORT_SUMMARY_HEADER = re.compile(r"^=+ short test summary info =+$",
                                   re.MULTILINE)
# Разделитель секции вывода pytest («==== FAILURES ====», итоговая строка
# «==== 1 failed in 0.1s ====») — конец блока сводки.
_SECTION_RULE = re.compile(r"^=+ .* =+$", re.MULTILINE)


def short_summary_block(output: str) -> str:
    """Текст блока «short test summary info» — от его заголовка до
    следующего разделителя секции; блока нет — пустая строка. Заголовок —
    последний в выводе: захваченный вывод упавшего теста печатается раньше
    сводки и вправе содержать что угодно, в том числе строки `FAILED …`/
    `ERROR …` (захваченный лог `ERROR    m:файл:строка …`)."""
    headers = list(_SHORT_SUMMARY_HEADER.finditer(output))
    if not headers:
        return ""
    start = headers[-1].end()
    end = _SECTION_RULE.search(output, start)
    return output[start:end.start() if end else len(output)]


def subtest_unit(node: str, label: str) -> str:
    """Единица упавшего подтеста — `<nodeid родителя> <метка>`: один вид для
    строки хода и короткого итога, чтобы один подтест считался один раз, а
    подтесты одного теста на базе и ветке различались."""
    label = label.strip()
    return f"{node.strip()} {label}" if label else node.strip()


def subtest_parents(output: str) -> dict[str, str]:
    """Единица упавшего подтеста короткого итога -> nodeid родителя: повтор
    упавших (`suite-run --failed`) зовёт pytest по nodeid, метку он не
    найдёт."""
    return {subtest_unit(m.group(2), m.group(1)): m.group(2)
            for m in _SUBFAILED_ENTRY.finditer(short_summary_block(output))}


def failed_entries(output: str) -> list[tuple[str, str]]:
    """(id теста, первая строка сообщения) из блока «short test summary
    info» — по одной паре на упавший тест, без повторов; сообщения нет —
    пустая строка. Упавший подтест — парой с единицей `subtest_unit`.
    Строки вне блока не читаются (`short_summary_block`)."""
    block = short_summary_block(output)
    found = [(m.start(), m.group(1), m.group(2))
             for m in _FAILED_ENTRY.finditer(block)]
    found += [(m.start(), subtest_unit(m.group(2), m.group(1)), m.group(3))
              for m in _SUBFAILED_ENTRY.finditer(block)]
    seen = {}
    for _, node, message in sorted(found, key=lambda item: item[0]):
        seen.setdefault(node.strip(), (message or "").strip())
    return list(seen.items())


def suite_results_dir() -> Path:
    """Каталог сохранённых итогов — в каталоге логов пульта; функция, а не
    константа: `config.LOGS` подменяют тесты."""
    return config.LOGS / "fullsuite-results"


def saved_failures(sha: str) -> list[str] | None:
    """Перечень упавших сохранённого итога по `sha`; `None` — итога нет
    или файл не читается (прогон базы тогда идёт заново)."""
    path = suite_results_dir() / f"{sha}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        failed = data["failed"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return [str(n) for n in failed] if isinstance(failed, list) else None


def save_failures(sha: str, failed: list[str], source: str) -> None:
    """Итог завершённого прогона по `sha`. Запись через временный файл и
    `replace` — читатель не увидит половину файла; сбой записи не
    поднимается: итог — ускорение `suite-run`, не условие гейта."""
    folder = suite_results_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".{sha}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps({"sha": sha, "failed": sorted(failed),
                                   "source": source}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(folder / f"{sha}.json")
    except OSError:
        pass


def clean_tree_sha(root: Path) -> str | None:
    """sha HEAD каталога `root`, если его дерево совпадает с коммитом
    (без изменённых и неотслеживаемых файлов вне `tasks/` — туда пульт
    выкладывает планку); иначе `None`: итог грязного дерева не итог sha."""
    head = gitcmd.in_repo(root, "rev-parse", "HEAD")
    if head is None or head.returncode != 0 or not head.stdout.strip():
        return None
    status = gitcmd.in_repo(root, "status", "--porcelain",
                            "--untracked-files=all", "--", ".",
                            ":(exclude)tasks")
    if status is None or status.returncode != 0 or status.stdout.strip():
        return None
    return head.stdout.strip()


def _remember_gate_failures(root: Path, outcome: str, output: str) -> None:
    """Сохранение итога прогона гейта (требование 7): только завершённый
    прогон с итоговой строкой pytest (требование 8) и только чистое
    дерево. Сбой git здесь — молча без сохранения: исход гейта от этого
    не зависит (требование 1)."""
    if outcome not in (FULL_SUITE_GREEN, FULL_SUITE_RED):
        return
    if not run_summary_line(output):
        return
    try:
        sha = clean_tree_sha(root)
    except (OSError, ValueError, AttributeError):
        return
    if sha:
        save_failures(sha, [node for node, _ in failed_entries(output)],
                      "гейт")


def suite_tree_hash(root: Path, *, ref: str = "HEAD", base: bool = False,
                    worktree: bool = True) -> str | None:
    """Снимок git-дерева через отдельный индекс; исходный индекс не меняется."""
    root = Path(root)
    top = gitcmd.in_repo(root, "rev-parse", "--show-toplevel")
    if (top is None or top.returncode != 0 or
            Path(top.stdout.strip()).resolve() != root.resolve()):
        return None
    if worktree:
        untracked = gitcmd.in_repo(root, "ls-files", "--others",
                                   "--exclude-standard", "-z")
        if untracked is None or untracked.returncode != 0:
            return None
        if any(p and not p.startswith("tasks/") for p in
               untracked.stdout.split("\0")):
            return None
    with tempfile.TemporaryDirectory(prefix="artel-suite-index-") as holder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(holder) / "index")}
        if worktree:
            original = gitcmd.in_repo(root, "rev-parse", "--path-format=absolute",
                                      "--git-path", "index")
            if original is None or original.returncode != 0:
                return None
            try:
                shutil.copyfile(original.stdout.strip(), env["GIT_INDEX_FILE"])
            except (OSError, ValueError):
                return None
        def git(*args):
            process = subprocess.Popen(["git", "-C", str(root), *args],
                                       cwd=config.ROOT, env=gitcmd.pult_env(env),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                stdout, _ = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                return None
            return stdout.strip() if process.returncode == 0 else None
        if not worktree and git("read-tree", ref) is None:
            return None
        if worktree and git("add", "-u", "--", ".") is None:
            return None
        if base and git("rm", "-q", "--cached", "-r", "--ignore-unmatch",
                        "--", *config.FULL_SUITE_BASE_EXCLUDED_PATHS) is None:
            return None
        tree = git("write-tree")
        if not tree or not re.fullmatch(r"[0-9a-f]{40}", tree):
            return None
    return _with_tree_db_files(root, tree) if worktree and not base else tree


def _with_tree_db_files(root: Path, tree: str) -> str:
    """Снимок рабочего дерева с учётом файлов БД пульта (SPEC
    01M4FYTB8QWJNHYCP35K8QC4E3, требование 5): git их не видит (`.artel/`
    игнорируется), а итог набора от них зависит — 09.10 после уборки файла
    `approve` выдал прежний красный итог из кэша. Файлов нет — тот же sha
    дерева, что и до задачи (сохранённые итоги чистых деревьев не теряются);
    есть — sha1 от дерева, наличия и sha256 содержимого каждого файла, той
    же формы в 40 знаков, что ждут `suite_result_key`/`saved_suite_result`.
    Итог базы (`base=True`) их не учитывает: его сверяют с деревом коммита
    (`suite-run`), где файлов БД нет по построению."""
    from . import store  # store -> ... -> acceptance
    if not store.tree_db_files(root):
        return tree
    digest = hashlib.sha1(tree.encode())
    for rel in store.TREE_DB_FILES:
        path = Path(root) / rel
        digest.update(f"\0{rel}\0".encode())
        digest.update(b"+" + hashlib.sha256(path.read_bytes()).digest()
                      if path.is_file() else b"-")
    return digest.hexdigest()


def suite_result_key(tree: str, command: list[str] | None = None,
                     *, base: bool = False,
                     root: Path | None = None) -> str | None:
    """Дерево плюс Python, установленные пакеты и команда pytest.

    `command` — и профиль (канал `run_full_suite`): у `pult-pytest` ключ
    — ключ его команды, байт в байт прежний; у `pytest-own` — argv его
    прогона (цель `long_lived_dir` из `workdir`, base-ключ её вычищает)
    плюс `runner`, `workdir` и `env` (SPEC 01M52EEFNA1WH31962HVNT0YZ9,
    требование 7). `root` — рабочая копия дерева `tree`: из неё ключ
    рабочего дерева профиля с `tools` берёт игнорируемые файлы блокировки
    (SPEC 01M58PG72PG64GS790XM2EWS61, требование 10)."""
    if not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree):
        return None
    reported = _reported(command)
    if reported is not None:
        return _report_suite_result_key(tree, reported, base, root)
    own = _own(command)
    if own is not None:
        return _own_suite_result_key(tree, own, base, root)
    command = _head(command)
    try:
        argv = _pytest_command(command=command) if base else (
            _pytest_command("tests", command=command) + [
                "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"])
        if base:
            clean = []
            index = 0
            while index < len(argv):
                arg = argv[index]
                if arg == "-n" or (arg == "-p" and
                                   index + 1 < len(argv) and argv[index + 1] == "xdist"):
                    index += 2
                elif arg == "-vv" or arg == "tests" or arg.startswith("tests/"):
                    index += 1
                else:
                    clean.append(arg)
                    index += 1
            argv = clean
        packages = sorted((d.metadata["Name"].lower(), d.version)
                          for d in importlib.metadata.distributions())
        data = {"tree": tree, "python": sys.version, "packages": packages,
                "command": argv}
        return hashlib.sha256(json.dumps(data, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _own_suite_result_key(tree: str, profile, base: bool,
                          root: Path | None = None) -> str | None:
    """Ключ итога полного набора `pytest-own` (`suite_result_key`).

    Ключ рабочего дерева профиля с непустыми `tools` несёт отдельным
    элементом объявленные версии и суммы файлов блокировки `workdir`
    (SPEC 01M58PG72PG64GS790XM2EWS61, требования 10-12): без `tools`
    данные ключа прежние байт в байт, ключ базы прежний всегда — его
    ищет `suite-run`, чей профиль `tools` не несёт."""
    tools = dict(getattr(profile, "tools", None) or {})
    locks = None
    if tools and not base:
        locks = _lock_sums(root, tree, profile.workdir)
        if locks is None:
            return None
    try:
        target = _own_target(profile, profile.long_lived_dir)
        argv = _place_command(profile) if base else \
            _place_command(profile, target)
        if base:
            inside = target.rstrip("/") + "/"
            argv = [arg for arg in argv
                    if arg != target and not arg.startswith(inside)]
        packages = sorted((d.metadata["Name"].lower(), d.version)
                          for d in importlib.metadata.distributions())
        data = {"tree": tree, "python": sys.version, "packages": packages,
                "command": argv, "runner": profile.runner,
                "workdir": profile.workdir, "env": dict(profile.env)}
        if locks is not None:
            data["tools"] = {"declared": tools, "locks": locks}
        return hashlib.sha256(json.dumps(data, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _report_suite_result_key(tree: str, profile, base: bool,
                             root: Path | None = None) -> str | None:
    """Ключ итога полного набора профиля с отчётом (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 14): дерево, `tools`, суммы
    файлов блокировки `workdir`, команда с действующими `report_args`, имя
    компонента (плюс `runner`, `workdir`, `env`, `select`). Ключ рабочего
    дерева без `root` не считается: игнорируемый файл блокировки иначе не
    прочесть; ключ базы — по дереву коммита, без файлов рабочей копии."""
    from . import project_profile
    locks = None
    if not base:
        locks = _lock_sums(root, tree, profile.workdir)
        if locks is None:
            return None
    try:
        data = {"tree": tree, "base": base, "locks": locks,
                "tools": dict(profile.tools or {}),
                "command": list(profile.command), "report": profile.report,
                "report_args": list(project_profile.report_args_of(profile)),
                "select": list(profile.select),
                "component": _component_name(profile),
                "runner": profile.runner, "workdir": profile.workdir,
                "env": dict(profile.env)}
        # Итог, посчитанный до запрета повторов, переиспользоваться не должен.
        if _bans_rerun_plugins(profile):
            data["no_rerun_plugins"] = True
        return hashlib.sha256(json.dumps(data, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


# Файлы блокировки зависимостей в `workdir` компонента (SPEC
# 01M58PG72PG64GS790XM2EWS61, требование 10).
LOCK_FILE_NAMES = ("uv.lock", "package-lock.json", "poetry.lock", "yarn.lock",
                   "pnpm-lock.yaml")


def _lock_sums(root: Path | None, tree: str, workdir: str) -> dict | None:
    """Суммы файлов блокировки `workdir`, какие есть: отслеживаемый — sha
    блоба из дерева `tree`, игнорируемый git — sha256 рабочей копии
    `root`. `None` — сумм не снять (нет `root`, git не ответил, файл не
    прочитан): ключа тогда нет, и итог не переиспользуется."""
    if root is None:
        return None
    prefix = workdir.strip("/")
    rels = [f"{prefix}/{name}" if prefix else name for name in LOCK_FILE_NAMES]
    res = gitcmd.in_repo(Path(root), "ls-tree", "-z", tree, "--", *rels)
    if res is None or res.returncode != 0:
        return None
    tracked = {}
    for item in res.stdout.split("\0"):
        meta, _, rel = item.partition("\t")
        parts = meta.split()
        if rel and len(parts) == 3 and parts[1] == "blob":
            tracked[rel] = parts[2]
    sums = {}
    for rel in rels:
        if rel in tracked:
            sums[rel] = f"blob:{tracked[rel]}"
            continue
        path = Path(root) / rel
        if not path.is_file():
            continue
        try:
            sums[rel] = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        except OSError:
            return None
    return sums


def _suite_result_path(kind: str, key: str) -> Path:
    return suite_results_dir() / f"{kind}-{key}.json"


def saved_suite_result(kind: str, key: str, *, tree: str | None = None,
                       max_age: int | None = None) -> dict | None:
    """Нечитаемая, неполная и просроченная запись равнозначна отсутствующей."""
    try:
        data = json.loads(_suite_result_path(kind, key).read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("key") != key or
                data.get("source") not in ("gate", "base") or
                data["source"] != kind or
                data.get("outcome") not in (FULL_SUITE_GREEN, FULL_SUITE_RED) or
                not isinstance(data.get("finished_at"), (int, float)) or
                isinstance(data["finished_at"], bool) or
                not math.isfinite(data["finished_at"]) or
                not isinstance(data.get("summary"), str) or not data["summary"] or
                not isinstance(data.get("digest"), str) or not data["digest"] or
                not isinstance(data.get("failed"), list) or
                not all(isinstance(n, str) for n in data["failed"]) or
                not isinstance(data.get("log_path"), str) or not data["log_path"] or
                not isinstance(data.get("tree"), str) or
                not re.fullmatch(r"[0-9a-f]{40}", data["tree"]) or
                (tree is not None and data["tree"] != tree)):
            return None
        age = time.time() - data["finished_at"]
        if age < 0 or (max_age is not None and age > max_age):
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return None


def save_suite_result(kind: str, key: str, tree: str, outcome: str,
                      output: str, log_path: Path | None) -> None:
    if (not key or not tree or log_path is None or
            outcome not in (FULL_SUITE_GREEN, FULL_SUITE_RED)):
        return
    summary = run_summary_line(output)
    if not summary:
        return
    data = {"key": key, "tree": tree, "source": kind,
            "finished_at": time.time(), "outcome": outcome,
            "summary": summary, "failed": [n for n, _ in failed_entries(output)],
            "digest": run_digest(output), "log_path": str(log_path)}
    path = _suite_result_path(kind, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def full_suite(root: Path, task_id: str,
               command: list[str] | None = None,
               fresh: bool = False) -> FullSuiteRun:
    """Прогон полного набора `tests/` каталога `root` с разбором вывода и
    файлом лога (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME, требования 3-6) — узел
    для автогейта приёмки, гейта мержа и `approve` в `acceptance`.

    `command` — начало команды прогона из профиля тестов проекта (как у
    `run_full_suite`): гейт мержа внешнего проекта гоняет приложения его
    командой (SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 6); `None` —
    команда пульта, и `run_full_suite` зовётся без неё, как до задачи.

    Сам прогон идёт через `run_full_suite` выше, а не в обход неё: это
    единственный вход прогона полного набора во всём пульте (и
    единственная точка его подмены в тестах), а различимость исходов
    держит `_full_suite_outcome` по тексту той же функции.

    Пустой вывод (прогона не было вовсе либо он ничего не напечатал) файла
    лога не заводит: пустой файл в каталоге логов только мешает читать
    настоящие.
    """
    # Замок берётся здесь, а не в `run_full_suite`: ожидание пишется в
    # журнал задачи гейта (требование 2), а `run_full_suite` внутри взятого
    # замка идёт без второго взятия.
    global _last_full_suite_metrics
    _last_full_suite_metrics = None
    from . import project_profile, store  # store -> ... -> acceptance
    # Прямой вызов узла без БД (юнит-сценарии и временные деревья) не
    # должен создавать state.db: чтение БД её не заводит (SPEC
    # 01M4FYTB8QWJNHYCP35K8QC4E3, требование 2).
    recordable = store.db_usable()
    target = (store.task_target(store.db(), task_id) if recordable
              else config.DEFAULT_TARGET)
    in_tree = store.tree_db_files(root)
    if in_tree:
        note = _db_in_tree_note(root, task_id, in_tree)
        return FullSuiteRun(False, FULL_SUITE_NOT_STARTED, "", None,
                            _full_suite_detail(FULL_SUITE_NOT_STARTED, "",
                                               None, note))
    reported = _reported(command)
    if reported is not None and reported.from_components and \
            len(project_profile.components(reported.project or target)) > 1:
        # Узел по компонентам записи из нескольких компонентов: предел —
        # свой у каждого (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требование 10).
        limit = project_profile.component_limit(reported)
    elif recordable and project_profile.is_multi(target):
        # Контекст задачи на записи из нескольких компонентов: предел —
        # компонента задачи (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2).
        decision = project_profile.for_task_target(target, task_id,
                                                   store.db())
        if decision.profile is None:
            note = f"предел полного набора не определён: {decision.refusal}"
            return FullSuiteRun(False, FULL_SUITE_NOT_STARTED, "", None,
                                _full_suite_detail(FULL_SUITE_NOT_STARTED,
                                                   "", None, note))
        limit = project_profile.component_limit(decision.profile)
    else:
        limit = project_profile.full_suite_limit(target)
    run_kwargs = {"limit": limit} if limit[1] != "config" else {}
    try:
        tree = suite_tree_hash(root)
        key = suite_result_key(tree, command, root=root) if tree else None
        if key and not fresh:
            saved = saved_suite_result("gate", key, tree=tree,
                                       max_age=config.FULL_SUITE_REUSE_MAX_AGE_SEC)
            if saved is not None:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC",
                                      time.gmtime(saved["finished_at"]))
                note = (f"итог прогона {stamp}, дерево {tree}, лог "
                        f"{saved['log_path']} — использован повторно; "
                        f"прогнать набор заново — флаг {FRESH_SUITE_FLAG} "
                        f"(artel.py approve {task_id} {FRESH_SUITE_FLAG})")
                detail = _full_suite_detail(saved["outcome"],
                                            saved.get("digest") or saved["summary"],
                                            Path(saved["log_path"]))
                return FullSuiteRun(saved["outcome"] == FULL_SUITE_GREEN,
                                    saved["outcome"],
                                    saved.get("digest") or saved["summary"],
                                    Path(saved["log_path"]), f"{detail}; {note}")
    except (OSError, ValueError, TypeError, AttributeError,
            subprocess.TimeoutExpired):
        tree = key = None
    with _machine_lock(task_id, limit) as holder:
        if holder is not None:
            green, output = False, _not_started_note(holder)
        elif recordable:
            with observed_full_suite():
                if command is None:
                    green, output = run_full_suite(root, **run_kwargs)
                else:
                    green, output = run_full_suite(root, command=command,
                                                   **run_kwargs)
        elif command is None:
            green, output = run_full_suite(root, **run_kwargs)
        else:
            green, output = run_full_suite(root, command=command, **run_kwargs)
    _journal_db_files_created(root, task_id, recordable)
    tests = _last_report_tests if reported is not None else ()
    outcome = _full_suite_outcome(green, output)
    unknown = output.startswith(UNKNOWN_PREFIX)
    if outcome == FULL_SUITE_NOT_STARTED and not unknown:
        # Прогона не было: ни лога, ни выжимки, ни итога по sha.
        return FullSuiteRun(green, outcome, "", None,
                            _full_suite_detail(outcome, "", None, output))
    if outcome != FULL_SUITE_NO_TESTS:
        journal_suite_metrics(task_id, _last_full_suite_metrics)
    _remember_gate_failures(root, outcome, output)
    log_path = (_write_full_suite_log(task_id, output)
                 if outcome != FULL_SUITE_NO_TESTS and output.strip() else None)
    if unknown:
        # «Неизвестно» (требование 3): прогон был, лог есть и назван, итог
        # по sha не сохраняется — он не зелёный и не красный.
        head = output.splitlines()[0]
        log_note = f" (лог прогона: {log_path})" if log_path is not None else ""
        return FullSuiteRun(False, outcome, head, log_path,
                            f"{head}{log_note}", tests)
    if key and tree:
        save_suite_result("gate", key, tree, outcome, output, log_path)
        try:
            base_tree = suite_tree_hash(root, base=True)
            base_key = suite_result_key(base_tree, command, base=True) if base_tree else None
            if base_key and base_tree:
                save_suite_result("base", base_key, base_tree, outcome,
                                  output, log_path)
        except (OSError, ValueError, TypeError, AttributeError,
                subprocess.TimeoutExpired):
            pass
    digest_output = "\n".join(line for line in output.splitlines()
                              if not line.startswith("нагрузка: load average"))
    if reported is not None and outcome in (FULL_SUITE_GREEN, FULL_SUITE_RED):
        # Выжимка компонента — из сводки отчёта в конце вывода, не из
        # текста раннера (требование 18).
        headers = list(_SHORT_SUMMARY_HEADER.finditer(digest_output))
        if headers:
            digest_output = digest_output[headers[-1].start():]
    digest = run_digest(digest_output)
    detail = _full_suite_detail(outcome, digest, log_path,
                                output.splitlines()[0] if output else "")
    if outcome == FULL_SUITE_TIMEOUT and _last_full_suite_metrics is not None:
        detail += "\n" + suite_load_line(_last_full_suite_metrics)
    return FullSuiteRun(green, outcome, digest, log_path, detail, tests)


def components_full_suite(root: Path, task_id: str, profiles: tuple,
                          fresh: bool = False) -> FullSuiteRun:
    """Полный набор по каждому компоненту `profiles` (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требования 10-11): каждый — узлом
    `full_suite` со своим пределом; итог зелёный, только если зелены все.
    Не зелёный итог несёт исход и деталь решающего компонента первой
    строкой («неизвестно» и «не начат» решают раньше таймаута, таймаут —
    раньше красного), затем строки остальных."""
    if not profiles:
        note = f"{FULL_SUITE_NOT_STARTED}: компонентов для прогона нет"
        return FullSuiteRun(False, FULL_SUITE_NOT_STARTED, "", None, note)
    runs = [(p, full_suite(root, task_id, command=p, fresh=True) if fresh
             else full_suite(root, task_id, command=p)) for p in profiles]
    tests = tuple(t for _p, run in runs for t in run.tests)
    lines = [f"компонент {p.component}: {run.detail}" for p, run in runs]
    bad = [(p, run) for p, run in runs if not run.green]
    if not bad:
        return FullSuiteRun(True, FULL_SUITE_GREEN,
                            "\n".join(run.digest for _p, run in runs),
                            runs[-1][1].log_path, "\n".join(lines), tests)
    order = (FULL_SUITE_NOT_STARTED, FULL_SUITE_TIMEOUT, FULL_SUITE_NO_TESTS,
             FULL_SUITE_RED)
    p, run = min(bad, key=lambda item: order.index(item[1].outcome)
                 if item[1].outcome in order else len(order))
    rest = [line for (q, _r), line in zip(runs, lines) if q is not p]
    detail = "\n".join([f"{run.detail} [компонент {p.component}]", *rest])
    return FullSuiteRun(False, run.outcome, run.digest, run.log_path, detail,
                        tests)


def acceptance_suite(conn, root: Path, task_id: str, branch: str, repo: Path,
                     *, actor: str, fresh: bool = False) -> FullSuiteRun:
    """Результат полного набора для приёмки с локальным откатом при сомнении.

    Гейт мержа продолжает вызывать `full_suite` напрямую. Сравнивается
    фактическое дерево прогона, включая приложения PLAN и рабочие правки.

    `checks_local` компонента проекта задачи исполняются здесь после
    итога любого источника — CI, повторно взятого и свежего (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 13): узел общий у `approve` и
    автогейта. Проверка не прошла — красный итог с её выводом.
    """
    run = _acceptance_suite_run(conn, root, task_id, branch, repo,
                                actor=actor, fresh=fresh)
    from . import store
    try:
        profile = _task_profile(conn, task_id)
    except targets.ComponentsPending as exc:
        # Компонент задачи не выбран — `checks_local` не определены: отказ
        # с причиной, не зелёный итог без них (SPEC
        # 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2).
        text = f"checks_local компонента задачи не определены: {exc}"
        if isinstance(conn, sqlite3.Connection):
            store.journal(conn, task_id, actor, CHECKS_LOCAL_ACTION, text)
        return FullSuiteRun(False, FULL_SUITE_NOT_STARTED, text, run.log_path,
                            f"{text}\n{run.detail}", run.tests)
    ok, text = run_checks_local(profile, root)
    if not text:
        return run
    if isinstance(conn, sqlite3.Connection):
        store.journal(conn, task_id, actor, CHECKS_LOCAL_ACTION, text)
    if ok:
        return run
    if not run.green:
        # Проверка только добавляет красноту: незелёный исход («неизвестно»,
        # «не начат», таймаут) остаётся прежним — иначе `--accept-red`
        # принял бы его как красный (требование 3, инвариант 41).
        return run._replace(detail=f"{run.detail}\n{text}")
    return FullSuiteRun(False, FULL_SUITE_RED, text, run.log_path,
                        f"{text}\n{run.detail}", run.tests)


# Запись журнала об исполнении `checks_local` компонента (требование 13).
CHECKS_LOCAL_ACTION = "checks_local компонента"


def _acceptance_suite_run(conn, root: Path, task_id: str, branch: str,
                          repo: Path, *, actor: str,
                          fresh: bool) -> FullSuiteRun:
    """Итог полного набора приёмки — тело `acceptance_suite` до
    `checks_local`."""
    from . import store

    reason = "запрошен свежий локальный прогон" if fresh else ""
    if not reason:
        sha, _ = ci.head_sha(branch, repo=repo)
        if not sha:
            reason = "голова ветки не прочитана"
        else:
            try:
                gate_tree = suite_tree_hash(root)
                head_tree = suite_tree_hash(root, ref=sha, worktree=False)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                gate_tree = head_tree = None
            if not head_tree or not gate_tree:
                reason = "дерево гейта или головного коммита не прочитано"
            elif gate_tree != head_tree:
                reason = "дерево гейта отличается от дерева головного коммита"
            elif not gitcmd.is_ancestor(
                    f"refs/remotes/origin/{config.MAIN_BRANCH}", sha,
                    repo=repo):
                reason = f"ветка не свежа относительно origin/{config.MAIN_BRANCH}"
            else:
                run_id, reason = ci.accepted_full_suite(sha, repo=repo)
                if run_id:
                    detail = f"полный набор: принят итог CI {sha}, прогон {run_id}"
                    if isinstance(conn, sqlite3.Connection):
                        store.journal(conn, task_id, actor,
                                      "приёмка: полный набор принят из CI", detail)
                    return FullSuiteRun(True, FULL_SUITE_GREEN, detail, None,
                                        detail)
    if isinstance(conn, sqlite3.Connection):
        store.journal(conn, task_id, actor, "полный набор локально",
                      " ".join(reason.splitlines()))
    own = _task_own_profile(conn, task_id)
    if own is not None:
        return (full_suite(root, task_id, command=own, fresh=True) if fresh
                else full_suite(root, task_id, command=own))
    return (full_suite(root, task_id, fresh=True) if fresh
            else full_suite(root, task_id))


def _task_own_profile(conn, task_id: str):
    """Профиль `pytest-own` или профиль с итогом из отчёта (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 4) проекта задачи для мест
    прогона (SPEC 01M52EEFNA1WH31962HVNT0YZ9, требование 1); `None` — у
    проекта `pult-pytest` без отчёта, профиля нет или он не прочитан: тогда
    места зовутся прежней формой. Строка задачи не прочитана — проект
    артели, тот же откат, что у `store.task_target` для строки без проекта.

    Запись с несколькими компонентами — профиль компонента задачи
    (`project_profile.for_task`), при отказе выбора —
    `targets.ComponentsPending` с его причиной: прежняя форма пульта на ней
    была бы обходом отказа (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование
    2)."""
    profile = _task_profile(conn, task_id)
    return _reported(profile) or _own(profile)


def _task_profile(conn, task_id: str):
    """Профиль тестов проекта задачи (`with_tools`) или `None` — тело
    `_task_own_profile` без фильтра раннера: его `checks_local` нужны и
    профилю без отчёта."""
    from . import project_profile, repo_context, store  # store -> ... -> acceptance
    target = config.DEFAULT_TARGET
    if isinstance(conn, sqlite3.Connection):
        try:
            target = store.task_target(conn, task_id)
        except (sqlite3.Error, TypeError, IndexError, KeyError):
            pass
    answer = repo_context.profile_of(target)
    if answer.outcome == repo_context.PROFILE_UNREAD and answer.multi:
        # Компонент задачи — по зонам её строки (SPEC
        # 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2); `conn=None` сюда не
        # доходит — у него проект артели.
        decision = project_profile.for_task_target(target, task_id, conn)
        if decision.profile is None:
            raise targets.ComponentsPending(decision.refusal)
        return decision.profile
    if answer.outcome != repo_context.PROFILE_PRESENT:
        return None
    try:
        return project_profile.with_tools(
            target, project_profile.Profile.from_values(answer.values))
    except (KeyError, TypeError, ValueError, targets.TargetsError):
        return None


def _summary_plank_rule(tdir: Path):
    """Правило планки проекта задачи каталога `tdir` (имя каталога — id
    задачи; SPEC 01M59KMPG2ZMK10V556VZVQD65, требование 8): проект — по
    БД, если она пригодна (приём `drop_from_code_copy`), иначе артель."""
    from . import project_profile, store  # store -> ... -> acceptance
    target = config.DEFAULT_TARGET
    if store.db_usable():
        try:
            target = store.task_target(store.db(), tdir.name)
        except sqlite3.Error:
            pass
    return project_profile.plank_rule(target)


def summary(tdir: Path, branch: str | None = None,
            long_lived: list[Path] | None = None,
            repo: Path | None = None) -> str:
    """Сводка в карточку гейта acceptance: пройдено/manual/skip/ci.

    Число тестов — статический счёт (`guard.count_test_methods`), не
    запуск: второй документ-сводка не заводится (требование 3), а
    `unittest.TestLoader().discover()` для этого не годится — импортирует
    модуль по голому имени файла в `sys.modules` процесса, и второй
    прогон на другом каталоге с файлом того же имени падает ImportError
    (обычное дело: разные задачи, один и тот же `test_ac.py`).

    `branch` (01M1SHJTT0V516BWHYXWS50F3G, требование 4/AC-6) — имя
    КОДОВОЙ ветки задачи, тот же параметр, что уже несёт
    `materialize_from_branch(task_id, branch, code_dir)`: критерии с
    пометкой `ci` показываются вместе с результатом
    `ci.verifying_status(branch)`, так же явно, как manual-критерии
    сегодня. `None` (вызывающий не назвал ветку) — критерии `ci`
    называются без опроса CI: сводка не имеет права молчать про их
    существование только потому, что вызывающий не передал `branch`.

    `long_lived` — файлы долгоживущей группы задачи в `tests/`, исполненные
    тем же прогоном (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 9): итог
    называет число тестов обеих групп. `None` — у задачи нет перечня, строки
    групп нет, прежний вид сводки.

    Тесты и пометки — по правилу планки проекта задачи
    (`_summary_plank_rule`); у правила-умолчания — прежний счёт.
    """
    tests_dir = tdir / "acceptance_tests"
    if not plank_present(tests_dir) and long_lived is None:
        return "acceptance_tests/ нет — приёмочные тесты не заведены"
    rule = _summary_plank_rule(tdir)
    _, markers = guard.scan_acceptance_tests(tdir, rule=rule)
    manual = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    ci_ns = sorted(n for n, (kind, _) in markers.items() if kind == "ci")
    count = guard.count_test_methods(tdir, rule=rule)
    lines = [f"приёмочные тесты: {count} тест(ов), "
             f"{len(manual)} manual, {len(skip)} skip, {len(ci_ns)} ci"]
    if long_lived is not None:
        long_count = 0
        for path in long_lived:
            try:
                long_count += len(guard.TEST_METHOD.findall(
                    path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
        lines.append(f"одним прогоном: разовая группа — {count} тест(ов), "
                     f"долгоживущая группа — {long_count} тест(ов) в "
                     f"{len(long_lived)} файл(ах) tests/")
    if manual:
        lines.append("manual-критерии (проверяет Оператор на приёмке):")
        for n in manual:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else ""))
    if ci_ns:
        lines.append("ci-критерии (доказательство — CI кодовой ветки):")
        ci_note = ("статус CI не проверен — ветка не названа" if branch is None
                  else ci.verifying_status(branch, repo=repo)[1])
        for n in ci_ns:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else "")
                        + f" — {ci_note}")
    return "\n".join(lines)
