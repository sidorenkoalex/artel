"""Общая тестовая песочница (SPEC T037, требование 1; SPEC T061 —
второй заход: `FakeProc` и claude-only side_effect).

`TmpRootTest`, `capture` и `fake_git` копировались по 9/17/8 тестовым
файлам с расхождениями в наборе подменяемых путей `config` —
непропатченный путь в очередной копии означал тихую утечку теста на
реальное дерево пульта (SPEC T037, «Контекст»). Файлы, которым нужен
не полный набор или доп. подготовка (git-заглушка, `cmd_init`, копия
`skills/`/`templates/`), наследуют `TmpRootTest` и переопределяют
`PATCHED_ATTRS`/`setUp` — см. tasks/T037/PLAN.md, «Таблица переносов».

`FakeProc` и пара `claude_only_run`/`claude_only_popen` копировались
той же дорогой (SPEC T061, находка CR-2026-08-28-2, ★5): подмена
только запуска `claude`, настоящий git — тем же общим `subprocess`,
что и у `runner`/`gitcmd`.

`resilient_tmp_cleanup` (SPEC T083, требование 1) — та же копипаста ещё
раз: `TemporaryDirectory.cleanup()` с настоящим git внутри изредка падает
`OSError: [Errno 39] Directory not empty` при удалении `.git` (гонка ФС
некоторых CI-раннеров между записью git-объекта и `rmtree` того же
каталога; ран post-merge T038, 26.08) — десяток тестовых файлов держали
свою копию `tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.
cleanup)` в обход этого модуля.

`_ts_ago`, `FakeStream` (было приватным `_FakeStream`), `SpyRun`,
`RealGitSandbox`, `_dead_pid` — третье поколение той же копипасты
(SPEC T089, находка CR-2 ревизии 31.08): `_ts_ago` байт-в-байт повторён в
4 файлах (формат метки времени heartbeat lease), `FakeStream` — в 4
копиях, `SpyRun`/`RealGitSandbox`/`_dead_pid` — по 2. `SpyRun` сведён к
варианту-надмножеству (спецкейс `rev-parse --verify refs/heads/*`, тот же
приём, что `fake_git` ниже); `RealGitSandbox` несёт только общую часть
(git-репозиторий с одним коммитом на main + патч `ALL_CONFIG_ATTRS`) —
файл-специфичная надстройка (`head`/`write_and_commit` или
`TASK`/`commit_on_branch`) остаётся локальным подклассом там, где нужна.

`network_guarded_real_run`/`_network_git_command_denial`/
`_is_local_git_address` (SPEC 01M1QHQ277PQQA894X97RVEX9Y, требование 1) —
единая точка перехвата сетевых git-команд (`fetch`/`push`/`ls-remote`/
`clone` с адресом не-`file://`/не-абсолютным путём): `SpyRun.__call__`
зовёт её вместо прямого `_REAL_RUN` в ветке `passthrough_unknown`, и
`tests/test_git_fixation.py::_GitFixationTmpRootTest` патчит ей
`gitcmd.subprocess.run` вместо сырого модульного `subprocess.run` —
без этого DNS-адрес фикстуры target'а (SPEC «Контекст») уходил в
реальный резолвер и висел на таймауте при обрыве сети.
"""
import errno
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import catalog, config, fsm, gitcmd, stack, store, workspace

# Все пути `config`, которые сегодня подменяет хотя бы одна песочница
# (SPEC T037, AC-2) — порядок как в orchestrator/config.py.
ALL_CONFIG_ATTRS = (
    "DB", "TASKS", "LOGS", "ROOT", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
)

# `runner.role_env` (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, требования 1-3)
# резолвит объявленные манифестом инструменты РЕАЛЬНЫМ `shutil.which` при
# старте каждого шага роли — отсутствие любого из них останавливает шаг
# `OSError`'ом ещё до того, как код дойдёт до подменённого `spawn_agent`/
# `Popen`. Машина разработчика несёт `gh`/`claude` физически, раннер CI —
# не обязательно (ANSWER-2 Оператора: «на раннере GitHub нет исполняемых
# claude и gh»): десятки тестов, которым важно поведение шага С УЖЕ
# ПОДДЕЛЬНЫМ CLI (`FakeProc`/подмена `spawn_agent`), а не сам факт
# присутствия этих двух бинарей на машине прогона, иначе ложно падали бы
# на `OSError` до предмета своей проверки — ровно этот класс уводил
# `tests/test_step_cost.py`/`tests/test_step_refixation.py` в красный CI,
# будучи зелёным локально. `python3`/`git` — резолвятся по-настоящему
# (часть тестов реально исполняет git: пробы идентичности `role_env`);
# подмена PATH конкретным тестом (например `tests.test_multitarget.
# RoleEnvTest.test_role_path_is_built_from_declared_tools_not_copied`)
# по-прежнему валит резолвинг до `OSError` — стаб ниже маскирует только
# отсутствие `gh`/`claude` НА МАШИНЕ, не отсутствие инструмента в
# ПОДСУНУТОМ тестом PATH.
_REAL_WHICH = shutil.which


def _stub_which(name, *args, **kwargs):
    found = _REAL_WHICH(name, *args, **kwargs)
    if found is not None or name not in ("gh", "claude"):
        return found
    return f"/artel-test-stub-bin/{name}"


shutil.which = _stub_which

# Тот же класс риска, что и `_stub_which` выше, второй заход: `runner.
# role_env` (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 4) теперь зовёт
# `stack.check_stack()` на КАЖДЫЙ вызов — а он, помимо новой венв-проверки,
# ещё и реально спавнит `git --version`/`gh --version`/`claude --version`
# субпроцессом и заведомо не найдёт согласованный `.artel/venv` во
# временном каталоге песочницы. До этой задачи `role_env()` вообще не знал
# о `check_stack()` — тесты, которые мокают `subprocess.Popen`/
# `subprocess.run` УЗКО под свой сценарий (например `tests.test_doctor.
# LiveSmokeTest`, ждущий РОВНО один спавн агента смоука), не были готовы к
# побочным субпроцессам ИЗНУТРИ `role_env()`.
#
# В отличие от `_stub_which` (переменная модуля, патчится РОВНО ОДИН РАЗ
# на весь процесс — `shutil.which` идемпотентна и не зависит от песочницы
# теста), `stack.check_stack` подменяется ЛОКАЛЬНО, per-instance, в
# `TmpRootTest.setUp()`, тем же приёмом, что и `ALL_CONFIG_ATTRS` ниже:
# модульная переменная от import time до import time одна на весь
# процесс — глобальная замена сломала бы `tests/test_stack.py`/
# `tests.test_multitarget.RoleEnvVenvInterpreterTest`, которым нужен
# РЕАЛЬНЫЙ `stack.check_stack()` и которые в ОДНОМ прогоне `unittest
# discover` делят процесс с файлами, импортирующими эту песочницу.
_STUB_STACK_CHECKS = tuple(
    stack.StackCheck(name, "ok", f"тестовая песочница: {name} не проверяется")
    for name in ("python", "git", "gh", "claude", "venv"))


def _stub_check_stack():
    return list(_STUB_STACK_CHECKS)


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def resilient_tmp_cleanup(tmp: tempfile.TemporaryDirectory) -> None:
    """Устойчивая уборка временной git-песочницы (SPEC T083, требование 1).

    `tmp.cleanup()` на некоторых CI-раннерах изредка падает `OSError:
    [Errno 39] Directory not empty` при удалении `.git` — гонка ФС между
    записью git-объекта и `rmtree` того же каталога уже ПОСЛЕ того, как
    сценарий теста отработал (ран post-merge T038, 26.08 — раннер Linux,
    где `ENOTEMPTY == 39`; на macOS то же условие ОС отдаёт `errno.
    ENOTEMPTY == 66` — сверяемся с обоими числами, не только с локальным
    `errno.ENOTEMPTY`). Повтор `cleanup()` почти всегда проходит:
    `TemporaryDirectory.cleanup()` заново зовёт `rmtree`, пока каталог
    физически существует. Финальный `shutil.rmtree(ignore_errors=True)` —
    страховка на случай, если гонка не улеглась за отведённые попытки, не
    маскировка другой причины: `OSError` с иным `errno` пробрасывается
    сразу, без глотания."""
    retryable = {39, errno.ENOTEMPTY}
    for _ in range(2):
        try:
            tmp.cleanup()
            return
        except OSError as exc:
            if exc.errno not in retryable:
                raise
    shutil.rmtree(tmp.name, ignore_errors=True)


def seed_developer_brief_fixtures(root: Path) -> None:
    """Синтетические `docs/codebase-map.md`/`CLAUDE.md` в `root` (T028):
    бриф роли developer/analyst (`orchestrator/brief.py`) читает оба из
    `config.ROOT` — без них шаг падает ENOENT ещё до сценария, который
    песочница проверяет. Тот же приём, что уже был у `tests/test_doctor.py`
    `_DoctorTmpRootTest.setUp` до этой задачи (SPEC T049 добавила
    сканирование `config.ROOT` холодным стартом и туда, где раньше он
    оставался непропатченным реальным деревом пульта, — остальные
    песочницы, гоняющие `cmd_run` роли developer/analyst, этот же
    минимум теперь заводят себе явно, а не получают его случайно от
    реального ROOT)."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "codebase-map.md").write_text(
        "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
        "---\n\n# Карта\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")


def sync_spec_from_worktree(task_id: str) -> None:
    """Кладёт SPEC.md задачи на диск `config.TASKS/<id>/` (легаси-путь
    чтения брифа разработчика в лёгких песочницах без настоящего git).

    A7 (generic-путь заведения, AC-5): `cmd_new` коммитит SPEC.md в
    АРТЕФАКТНУЮ ВЕТКУ пульта плотницки (`artifact_branch.commit_files`),
    не на диск и не в worktree — в лёгкой песочнице (`fake_git`/`SpyRun`
    без реального git) эта плотницкая запись ничего не пишет по-настоящему
    (нет `.git` дерева, которое реально принять коммит), так что
    содержимого ветки взять неоткуда. `brief._developer_spec_text` (через
    `artifact_source.resolve`, `foreign=True` теперь для ЛЮБОГО target)
    без диска падает `FileNotFoundError`/именованным отказом — здесь
    кладётся тот же шаблон, который РЕАЛЬНО закоммитил бы `cmd_new`
    (`templates/SPEC.md` с подстановкой `TASK_ID`), в паре с патчем
    `gitcmd.show`/`gitcmd.ls_tree_files` на `disk_backed_show`/
    `disk_backed_ls_tree_files` (см. их докстринги) — вместе они делают
    диск `config.TASKS` источником истины для чтения FSM/брифа в этих
    песочницах, тем же приёмом, что уже несёт `tests.test_invariants.
    FsmTest`/`tests.test_auto_cycle.AutoCycleTest`.
    """
    template = (config.TEMPLATES / "SPEC.md").read_text(encoding="utf-8")
    text = template.replace("TASK_ID", task_id)
    dest_dir = config.TASKS / task_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "SPEC.md").write_text(text, encoding="utf-8")


def capture_new_task_id(fn, *args) -> tuple:
    """(текст stdout, возвращённое значение) — `capture()` отбрасывает
    возврат вызываемого; тестам, читавшим id задачи из `catalog.cmd_new`
    буквальным `"T001"` (SPEC T094, требование 2: id — ULID, не
    предсказуемая строка), нужен и печатаемый текст, и сам id."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args)
    return buf.getvalue(), result


def _tasks_relative_path(rel: str):
    """`config.TASKS / <rel без ведущего "tasks/">` — НЕ `config.ROOT /
    rel`: `config.ROOT` в `tests.test_invariants.FsmTest` временно
    подменяется НА ВРЕМЯ САМОГО вызова `fsm.cmd_approve` (`approve_with_
    isolated_root`, изоляция генерации карты/RETRO от реального дерева
    пульта) — `disk_backed_show`, вычисляющий путь от `config.ROOT` в
    момент чтения, получил бы чужой синтетический каталог без tasks/<id>/
    вовсе. `config.TASKS` — независимый атрибут `orchestrator/config.py`
    (посчитан один раз при импорте, `ROOT / "tasks"`), которого эта
    подмена не касается — стабильный путь для всей жизни процесса."""
    from orchestrator import config
    from pathlib import PurePosixPath
    parts = PurePosixPath(rel).parts
    assert parts and parts[0] == "tasks", f"неожиданный rel: {rel!r}"
    return config.TASKS.joinpath(*parts[1:])


def disk_backed_show(branch: str, rel: str) -> tuple:
    """Замена `gitcmd.show` (A7 + tasks/01M1K7KP0D8ZKRM9KTE75DCCYR): `rel`
    либо `tasks/<id>/<файл>` (артефакт задачи — соглашение `fsm.py`/
    `brief.py`/`fsm_advance.py`, `artifact_source.resolve` теперь всегда
    `foreign=True`), либо `skills/<файл>.md`/`CLAUDE.md` (правило системы,
    читается с ГОЛОВЫ `main` — `brief.skills_text`/`brief.
    _main_branch_text`, AC-1/AC-2). Без этой подмены оба чтения ушли бы в
    `gitcmd.git`, заглушенный в этих песочницах (генерику или вовсе не
    исполняемый). Ветка (`branch`) не участвует: песочницы, которые сюда
    попадают, ведут ровно ОДИН источник истины на каждый вид `rel` — диск
    `config.TASKS` для артефактов задачи (`_tasks_relative_path`), диск
    `config.ROOT` для правил системы (тот же корень, где песочница уже
    сеет `skills/`/`CLAUDE.md`, см. `seed_developer_brief_fixtures`) —
    git branch не заводят."""
    path = _tasks_relative_path(rel) if rel.startswith("tasks/") \
        else config.ROOT / rel
    try:
        return path.read_text(encoding="utf-8"), ""
    except FileNotFoundError:
        return None, "файла нет на диске"
    except UnicodeDecodeError as exc:
        # Тот же приём деградации, что и настоящий `gitcmd.show`: файл с
        # непрочитанными байтами — именованный отказ, не трейсбек.
        return None, f"не прочитан: {exc}"
    except OSError as exc:
        return None, str(exc)


def disk_backed_ls_tree_files(branch: str, rel_dir: str) -> list | None:
    """Замена `gitcmd.ls_tree_files` — тот же приём, что `disk_backed_show`
    выше: список файлов `config.TASKS/...` с диска, ветка не участвует.

    `rel_dir` — не обязательно каталог: настоящий `git ls-tree -- <path>`
    принимает и файловый pathspec (существующие вызывающие места, напр.
    `fsm_advance.spec_writing`, зовут его так же для проверки наличия
    ОДНОГО файла, `tasks/<id>/QUESTIONS.md`) — файл возвращает список из
    одного элемента, каталог — список файлов под ним, ничего из двух не
    существует — пустой список (не `None`: тот вырожденный случай «git не
    ответил», не «пусто»)."""
    path = _tasks_relative_path(rel_dir)
    if path.is_file():
        return [rel_dir]
    if not path.is_dir():
        return []
    return sorted(
        f"{rel_dir.rstrip('/')}/{p.relative_to(path).as_posix()}"
        for p in path.rglob("*") if p.is_file())


def fake_git_for(responses: dict) -> callable:
    """Параметризуемая заглушка `gitcmd.git`: подкоманда (первый позиционный
    аргумент вызова) ищется в `responses` и отвечает фиксированным
    `(returncode, stdout, stderr)`; всё остальное — чисто (rc=0, пустой
    вывод), без git-идентичности и отказа `rev-parse --verify`, которые
    несёт `fake_git` (эти сценарии — сверка свежести карты/её регенерация
    в tests/test_brief.py — идентичности и веток не касаются)."""
    def fake(*args: str) -> subprocess.CompletedProcess:
        if args and args[0] in responses:
            rc, out, err = responses[args[0]]
            return subprocess.CompletedProcess(list(args), rc, out, err)
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen

# Сетевые git-подкоманды (SPEC 01M1QHQ277PQQA894X97RVEX9Y, требование 1) —
# единственные, которые реально обращаются наружу; остальные (init/add/
# commit/status/remote/fsck/...) работают только с локальным репозиторием.
_NETWORK_GIT_SUBCOMMANDS = ("fetch", "push", "ls-remote", "clone")
# Хосты, которые НЕ считаются сетью для http(s)-адреса — точное сравнение
# всей хост-части, не префикс (`127.0.0.1.evil.example` — DNS-имя, не
# loopback, несмотря на общий префикс с исключённым `127.0.0.1`).
_LOCAL_LOOPBACK_HOSTS = ("localhost", "127.0.0.1")


def _is_local_git_address(address: str) -> bool:
    """Локальный адрес — `file://`, абсолютный путь или голое имя
    настроенного remote'а (например `origin`: git резолвит его САМ из
    локального конфига репозитория, здесь это не URL и не адрес вовсе —
    так адресуют локальные bare-фикстуры T048/T053, AC-2). Сеть — только
    `http(s)://` с хостом, отличным от `localhost`/`127.0.0.1`.

    Решает по ФОРМЕ адреса (текстовый префикс/хост), не резолвит его:
    AC-9 требует отказа быстрее секунды и без обращения к резолверу даже
    при подменённом `socket.getaddrinfo`."""
    if address.startswith("file://") or address.startswith("/"):
        return True
    if address.startswith("http://") or address.startswith("https://"):
        from urllib.parse import urlsplit
        return urlsplit(address).hostname in _LOCAL_LOOPBACK_HOSTS
    return True


def _network_git_command_denial(cmd, want_text: bool):
    """`CompletedProcess` именованного отказа (SPEC 01M1QHQ277PQQA894X97RVEX9Y,
    AC-1), если `cmd` — сетевая git-команда (`fetch`/`push`/`ls-remote`/
    `clone`, сквозь ведущие `-C <путь>` — тот же пропуск, что `SpyRun.
    git_subcommands`) с адресом, который не является локальным путём;
    `None` — команда не сетевая, адрес не найден или локален (AC-2:
    перехватывать нечего, вызывающий код зовёт настоящий git как раньше)."""
    if not cmd or cmd[0] != "git":
        return None
    i = 1
    while i + 1 < len(cmd) and cmd[i] == "-C":
        i += 2
    if i >= len(cmd) or cmd[i] not in _NETWORK_GIT_SUBCOMMANDS:
        return None
    subcommand = cmd[i]
    address = next((a for a in cmd[i + 1:] if not a.startswith("-")), None)
    if address is None or _is_local_git_address(address):
        return None
    message = f"сеть в тестах запрещена: {subcommand} {address}"
    empty = "" if want_text else b""
    stderr = message if want_text else message.encode()
    return subprocess.CompletedProcess(list(cmd), 1, empty, stderr)


def network_guarded_real_run(cmd, *args, **kwargs) -> subprocess.CompletedProcess:
    """Настоящий `subprocess.run`, но с именованным отказом сетевых
    git-команд (см. `_network_git_command_denial`) — единая точка для
    песочниц, которым нужен НАСТОЯЩИЙ git целиком (не фейковые плотницкие
    примитивы `SpyRun`), но не сеть: `tests/test_git_fixation.py::
    _GitFixationTmpRootTest` патчит этой функцией `gitcmd.subprocess.run`
    вместо сырого модульного `subprocess.run` (SPEC
    01M1QHQ277PQQA894X97RVEX9Y, «Контекст»: без неё DNS-адрес фикстуры
    target'а там уходил в реальный fetch и висел на резолвере)."""
    want_text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                     or kwargs.get("encoding"))
    denial = _network_git_command_denial(cmd, want_text)
    if denial is not None:
        return denial
    return _REAL_RUN(cmd, *args, **kwargs)


def claude_only_run(claude_stdout: str, claude_returncode: int = 0):
    """`subprocess.run` side_effect: отвечает только на `claude ...`, остальное
    (например, `git config --get ...` внутри `gitcmd.git` — тот же общий
    модуль `subprocess`) уходит в настоящий `subprocess.run`: подмена
    атрибута `subprocess.run` глобальна на модуль."""
    def run(args, **kwargs):
        if args and args[0] == "claude":
            return subprocess.CompletedProcess(args, claude_returncode,
                                               claude_stdout, "")
        return _REAL_RUN(args, **kwargs)
    return run


def claude_only_popen(fake_proc):
    """Аналог `claude_only_run` для `subprocess.Popen`/`runner.spawn_agent`."""
    def popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == "claude":
            return fake_proc
        return _REAL_POPEN(cmd, *args, **kwargs)
    return popen


def _ts_ago(seconds: float) -> str:
    """Метка времени heartbeat lease `seconds` секунд назад, в формате,
    который читает `orchestrator.liveness` (SPEC T089: формат heartbeat
    lease знали по отдельности 4 копии этой функции)."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%SZ")


def _dead_pid() -> int:
    """Гарантированно мёртвый pid: дочерний процесс, дождавшийся своего
    завершения."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    proc.wait()
    return proc.pid


class SpyRun:
    """Подмена `subprocess.run`: команда запоминается; исход зависит от
    `passthrough_unknown`.

    По умолчанию (`passthrough_unknown=False`, байт-в-байт прежнее
    поведение) фейкует ЛЮБУЮ команду фиксированным успехом, кроме
    отдельно распознанных плотницких примитивов ниже — так её использует
    `tests/test_invariants.py::FsmTest`/`tests/test_auto_cycle.py`
    (`config.ROOT` там НАСТОЯЩИЙ, не временный каталог: реальный
    `subprocess.run` там недопустим ни для одной команды, не только для
    плотницких).

    `passthrough_unknown=True` (`TmpRootTest.setUp` ниже) фейкует ТОЛЬКО
    плотницкие git-примитивы артефактной ветки (`artifact_branch.
    write_commit`/`commit_files`) — им нужен git-репозиторий, которого в
    лёгкой песочнице `TmpRootTest` нет (`self.root` — обычный временный
    каталог, не git-репо, пока тест сам его не завёл `git init`). Всё
    остальное (`init`, `add`/`commit`, `status`, `remote`, `fsck`,
    `push`, ...) уходит в НАСТОЯЩИЙ `subprocess.run` — безопасно именно
    потому, что `TmpRootTest.self.root` ВСЕГДА временный каталог, никогда
    реальное дерево пульта: код, оперирующий РЕАЛЬНО заведённым по ходу
    теста репозиторием (`projects.cmd_target_init` и подобные), обязан
    видеть настоящий исход, а не молчаливую заглушку — иначе, например,
    dirty-детект `git status --porcelain` не отличил бы правку от чистого
    дерева (находка A7: `tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/
    test_ac2_doctor_generic_checks.py`/`test_ac3_recovery_check_scope.py`
    заводят репозиторий `projects.cmd_target_init` и коммитят в него
    по-настоящему — бланкетный фейк «успех на всё» их ложно зеленил).

    Передача в настоящий `subprocess.run` идёт через
    `network_guarded_real_run` (SPEC 01M1QHQ277PQQA894X97RVEX9Y,
    требование 1): сетевая git-команда (`fetch`/`push`/`ls-remote`/
    `clone`) с адресом не-`file://`/не-абсолютным путём получает
    мгновенный именованный отказ вместо обращения к реальной сети.
    """

    def __init__(self, passthrough_unknown: bool = False):
        self.calls: list = []
        self.passthrough_unknown = passthrough_unknown

    # sha-плейсхолдер для плотницких git-команд ниже — 40 hex-символов,
    # синтаксически валидный sha (git его не проверяет, "не исполняется").
    _FAKE_SHA = "f" * 40
    # Плотницкие примитивы `artifact_branch.write_commit`/`commit_files` —
    # единственное, что здесь фейкуется; `hash-object`/`write-tree`/
    # `commit-tree` несут sha в stdout, `update-index`/`update-ref`/
    # `read-tree` — пустой успех.
    _PLUMBING_SHA = ("hash-object", "write-tree", "commit-tree")
    _PLUMBING_OK = ("update-index", "update-ref", "read-tree")

    def __call__(self, cmd, *args, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        # Тип stdout/stderr — как у настоящего `subprocess.run`: `bytes`,
        # если вызывающий код не просил текст (`text`/`universal_newlines`/
        # `encoding`) — иначе код вроде `artifact_branch.write_commit`
        # (плотницкая запись, `hash-object` без `text=True` — бинарные
        # артефакты, AC-12) получал бы `str` и падал на `.decode()`.
        want_text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                         or kwargs.get("encoding"))
        empty = "" if want_text else b""
        # `rev-parse --verify --quiet refs/heads/*` (`gitcmd.branch_exists`)
        # — отдельно, с отказом (SPEC T048, тот же приём, что и `fake_git`
        # выше): `cmd_new` решает, заводить ли задачу, по ответу этого
        # вызова — отвечай он успехом на всё подряд, `cmd_new` увидел бы
        # любую ветку уже существующей.
        if (len(cmd) >= 4 and cmd[1] == "rev-parse" and cmd[2] == "--verify"
                and cmd[-1].startswith("refs/heads/")):
            return subprocess.CompletedProcess(list(cmd), 1, empty, empty)
        # `hash-object`/`write-tree`/`commit-tree` — плотницкая запись
        # артефактной ветки (`artifact_branch.write_commit`, A7 generic-путь
        # `catalog.cmd_new`, AC-5) читает их stdout как sha и трактует
        # пустой ответ как «git не ответил» (`sys.exit`) — отвечать пустышкой
        # тут значило бы ложно проваливать КАЖДЫЙ `cmd_new` под этим спаем.
        if len(cmd) >= 2 and cmd[1] in self._PLUMBING_SHA:
            sha = self._FAKE_SHA if want_text else self._FAKE_SHA.encode()
            return subprocess.CompletedProcess(list(cmd), 0, sha, empty)
        if len(cmd) >= 2 and cmd[1] in self._PLUMBING_OK:
            return subprocess.CompletedProcess(list(cmd), 0, empty, empty)
        if self.passthrough_unknown:
            return network_guarded_real_run(cmd, *args, **kwargs)
        return subprocess.CompletedProcess(list(cmd), 0, empty, empty)

    def git_subcommands(self) -> list:
        """Подкоманды git по порядку: ['checkout', 'pull', 'merge', ...] —
        сквозь ведущие `-C <путь>` (Stage0, плотницкий merge в scratch-
        worktree, `gitcmd.in_repo`/`in_repo`: `git -C <scratch> merge
        ...`) — без пропуска пар `-C` первый элемент был бы всегда `-C`,
        а не настоящей подкомандой, и `assertIn`/`assertNotIn("merge",
        ...)` проверяли бы не то, что называют."""
        result = []
        for c in self.calls:
            if len(c) < 2 or c[0] != "git":
                continue
            i = 1
            while i + 1 < len(c) and c[i] == "-C":
                i += 2
            if i < len(c):
                result.append(c[i])
        return result


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: git-идентичность роли, без обращения к репозиторию.

    Нужна, потому что подмена `subprocess.Popen` глобальна: настоящий
    `gitcmd.git` (его зовёт `runner.role_env` за авторством коммита шага)
    ушёл бы через неё в фейковый процесс.

    `rev-parse --verify --quiet refs/heads/<ветка>` (`gitcmd.branch_exists`)
    — отдельно, с отказом (SPEC T048): `cmd_new` с этой задачи сам решает,
    заводить ли задачу, по ответу этого вызова (AC-3, требование 1) — если
    отвечать успехом на любой git-вызов, как раньше, `cmd_new` увидел бы
    ЛЮБУЮ ветку как уже существующую и отказывал бы всегда. В лёгких
    песочницах реальных веток нет ни одной — ответ «нет» тут не заглушка
    ради прохождения теста, а корректная симуляция вырожденного случая.

    `show <ветка>:<путь>` (`gitcmd.show`) — тоже отдельно (tasks/
    01M1K7KP0D8ZKRM9KTE75DCCYR, AC-1/AC-2): скилы/CLAUDE.md с этой задачи
    читаются через него с головы `main`, а не с диска напрямую. В лёгких
    песочницах настоящих коммитов нет ни одного — ответом служит диск
    `config.ROOT/<путь>`, который эти же песочницы уже наполняют реальными
    фикстурами (`seed_developer_brief_fixtures`, `shutil.copytree(...,
    "skills")`) как раз для этого чтения; файла на диске нет — тот же
    отказ, что дал бы `git show` на несуществующий путь.
    """
    if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
            and args[-1].startswith("refs/heads/")):
        return subprocess.CompletedProcess(list(args), 1, "", "")
    if len(args) == 2 and args[0] == "show" and ":" in args[1]:
        _, _, rel = args[1].partition(":")
        try:
            content = (config.ROOT / rel).read_text(encoding="utf-8")
        except OSError:
            return subprocess.CompletedProcess(
                list(args), 128, "",
                f"fatal: path '{rel}' does not exist in '{args[1]}'")
        return subprocess.CompletedProcess(list(args), 0, content, "")
    identity = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = identity.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


class TmpRootTest(unittest.TestCase):
    """Общая песочница: пути `config` — во временном каталоге.

    `PATCHED_ATTRS` — параметризуемый набор патчей (SPEC T037,
    требование 1); по умолчанию — все десять путей `config` (AC-2).
    """

    PATCHED_ATTRS = ALL_CONFIG_ATTRS

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name)

        for attr in self.PATCHED_ATTRS:
            patcher = mock.patch.object(config, attr, self._patched_path(attr))
            patcher.start()
            self.addCleanup(patcher.stop)

        # `runner.role_env` сверяет `.artel/venv` через `stack.check_stack()`
        # (см. комментарий у `_stub_check_stack` выше) — без этого патча
        # ЛЮБОЙ путь этой песочницы, доходящий до `role_env()` (напрямую
        # или через `cmd_run`/`live_smoke`/`auto`), отказывал бы `OSError`:
        # временный `self.root` не несёт согласованного `.artel/venv`.
        stack_patcher = mock.patch.object(stack, "check_stack",
                                          _stub_check_stack)
        stack_patcher.start()
        self.addCleanup(stack_patcher.stop)

        # `catalog.cmd_new` (A7, generic-путь, AC-5) для ЛЮБОГО target,
        # включая self/артель, коммитит артефакты плотницки
        # (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git` и любой его мок
        # (`fake_git` и подобные патчат другой атрибут). Без этого патча
        # КАЖДЫЙ `cmd_new` в песочнице без настоящего git-репозитория в
        # `self.root` падает `sys.exit` («git не ответил») ещё до
        # сценария, который тест проверяет — `SpyRun` отвечает
        # правдоподобным sha на `hash-object`/`write-tree`/`commit-tree`
        # (не роняет коммит) и корректно типизирует stdout под `text=`
        # вызывающего кода. Подклассы, которым нужен собственный мок
        # `subprocess.run` (полный контроль над git-вызовами), патчат
        # `gitcmd.subprocess.run` поверх после `super().setUp()` — снятие
        # патчей идёт в LIFO-порядке штатным `addCleanup`.
        # `passthrough_unknown=True` — безопасно именно здесь: `self.root`
        # (и, если он в `PATCHED_ATTRS`, `config.ROOT`) ВСЕГДА временный
        # каталог этой песочницы, никогда реальное дерево пульта — в
        # отличие от `tests/test_invariants.py::FsmTest`/`tests/
        # test_auto_cycle.py`, которые заводят `SpyRun()` сами, с
        # НАСТОЯЩИМ `config.ROOT`, и поэтому обязаны получать классический
        # (полностью фейковый) `SpyRun` — дефолт конструктора без флага.
        self.git_spy = SpyRun(passthrough_unknown=True)
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", self.git_spy)
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)

    def _patched_path(self, attr: str) -> Path:
        return {
            "ROOT": self.root,
            "DB": self.root / ".artel" / "state.db",
            "TASKS": self.root / "tasks",
            "LOGS": self.root / ".artel" / "logs",
            "PROJECTS": self.root / ".artel" / "projects",
            "TARGETS": self.root / "targets.yaml",
            "ROLE_HOME": self.root / ".artel" / "home",
            "ROLE_CONFIG_DIR": self.root / ".artel" / "home" / ".claude",
            "BACKUP_MARKER": self.root / ".artel" / "backup-marker",
            "WORKTREES": self.root / ".artel" / "worktrees",
        }[attr]

    def capture(self, fn, *args) -> str:
        return capture(fn, *args)


class RealGitSandbox(TmpRootTest):
    """`self.root` — свежий git-репозиторий с веткой main и одним коммитом.

    Общая часть двух копий (SPEC T089): предмет проверки у обоих исходных
    файлов — поведение относительно НАСТОЯЩЕГО git-репозитория, заглушкой
    (`fake_git`) это не изобразить. Файл-специфичную надстройку (методы
    `head`/`write_and_commit` или атрибуты `TASK`/`self.branch` и
    `commit_on_branch`) несёт локальный подкласс в каждом тестовом файле —
    здесь только то, что было byte-identical в обеих копиях.
    """

    def setUp(self):
        # `super().setUp()` не зовётся — своего `setUp` целиком заменяет
        # `TmpRootTest.setUp` (нужен свой порядок: git-репозиторий раньше
        # патчей `ALL_CONFIG_ATTRS`).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        # `.artel/` в `.gitignore` ДО первого коммита (tasks/
        # 01M1NGFK3N6MRMYGCC09H975V3, ANSWER-2): `store.create_schema`
        # ниже кладёт настоящую sqlite-БД (WAL/SHM в комплекте) ВНУТРЬ
        # `self.root` — того же дерева, которое подклассы коммитят через
        # `git add -A`. Без этой строки любой подкласс, делающий больше
        # одного коммита и сверяющий их разницу (`gitcmd.diff_names`),
        # рискует поймать в диф WAL-файл БД — тот же приём, что уже несёт
        # реальный `.gitignore` пульта (`.artel/` в корне репозитория).
        (self.root / ".gitignore").write_text(".artel/\n", encoding="utf-8")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr in ALL_CONFIG_ATTRS:
            patcher = mock.patch.object(config, attr, self._patched_path(attr))
            patcher.start()
            self.addCleanup(patcher.stop)

        # Схема БД (SPEC T090, `store.migrate`: «БД ещё не создана — схему
        # ставит init») — `CREATE TABLE IF NOT EXISTS` идемпотентна, так что
        # подклассы, зовущие `catalog.cmd_init` сами (посев счётчиков/
        # ролей/программного расхода — то, что схемой не является), делают
        # это поверх без конфликта. Без строки ниже любой прямой
        # `store.insert_task`/`catalog.cmd_new` до собственного `cmd_init`
        # подкласса падает `sqlite3.OperationalError: no such table: tasks`
        # (см. tasks/T094/acceptance_tests/_sandbox.py:
        # ExternalTargetGitSandbox — заводит внешний target напрямую через
        # store, не через cmd_init).
        store.create_schema(store.db())

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def checkout(self, branch: str, create: bool = False) -> None:
        args = ["checkout", "-q"]
        if create:
            args.append("-b")
        args.append(branch)
        self.git(*args)


def assert_acceptance_run_called(acc_run, tdir: Path, code_root: Path) -> None:
    """`acc_run` (мок `acceptance.run`) обязан быть позван РОВНО с этим
    `tdir` (первый позиционный аргумент) и этим `cwd` (именованный —
    `code_root` переименован в `cwd` задачей SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-11) — оба сверяются отдельно, не
    связкой (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J, требование 1, AC-4): узел
    материализации планки (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS) не имеет
    права спутать рабочий каталог кода задачи с временным каталогом ни
    по одному из двух аргументов."""
    acc_run.assert_called_once()
    called_tdir = acc_run.call_args[0][0]
    called_cwd = acc_run.call_args.kwargs.get("cwd")
    assert called_tdir == tdir, (
        f"acceptance.run вызван с tdir={called_tdir!r}, ожидался {tdir!r}")
    assert called_cwd == code_root, (
        f"acceptance.run вызван с cwd={called_cwd!r}, ожидался "
        f"cwd={code_root!r}")


_PLAN_READY_TEMPLATE = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сценарий лёгкой песочницы переходов

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

_ACCEPTANCE_PLANK_SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка

## Критерии приёмки

AC-1. ...
"""

_ACCEPTANCE_PLANK_STUB_TEST = """import unittest


class StubTest(unittest.TestCase):

    def test_stub(self):
        pass
"""


class LightTransitionSandbox(TmpRootTest):
    """Эталонная лёгкая песочница переходов FSM (SPEC
    01M1TKP45EM16ZMJGQKNZA5T7J, требование 1) — три копии одного и того же
    набора патчей/помощников устаревали одинаково («карта и подтяжка»
    01M1RA0R9A, «причина конфликта подтяжки» 01M1REVMB5, «свежесть ветки»
    01M1NBWP): здесь общий источник, локальный `_sandbox.py`/тестовый файл
    планки несёт только тонкую надстройку сценария (`skills/
    test-authoring.md`).

    Поверх `TmpRootTest` (десять путей `config`, `stack.check_stack`,
    плотницкий `SpyRun(passthrough_unknown=True)` на `gitcmd.subprocess.
    run` — довольно и для плотницких вызовов `catalog.cmd_new` здесь,
    настоящего `gitcmd.git`-трафика в этой песочнице нет ни одного:
    `gitcmd.git` подменён целиком, см. ниже) добавляет:

    - git-идентичность без реального репозитория (`gitcmd.git` ->
      `fake_git`);
    - диск как источник артефактов задачи (`gitcmd.show`/`gitcmd.
      ls_tree_files` -> `disk_backed_show`/`disk_backed_ls_tree_files` —
      `artifact_source.resolve` теперь всегда `foreign=True`, читает
      через эту пару);
    - рабочее дерево задачи как временный подкаталог, не боевой `git
      worktree add` (`workspace.ensure` -> `(self.wt_path, None)`);
    - заведомо не вырожденный origin (`fsm._origin_main_sha` -> константный
      sha) — сценарий «ветка не отстала» подключается через `gitcmd.
      commits_behind`, замокан отдельно каждым тестом, не здесь;
    - белый список безобидных `gitcmd.in_repo` (AC-3) с точкой расширения
      `self.in_repo_handlers` — список хуков `(repo, *args) ->
      CompletedProcess | None`, проверяемых ДО дефолтного ответа: не
      подошёл ни один хук — дефолт делегирует в уже подменённый
      `gitcmd.git("-C", str(repo), *args)` (`fake_git`, тот же приём, что
      настоящий необмокнутый `gitcmd.in_repo`), безусловный успех на
      `checkout`/`commit`/`add`/`reset`/`diff --cached`/`status
      --porcelain` — и на любой другой вызов, которого сценарий не
      предвидел, той же деградацией, что и у остального `gitcmd` (не
      падает «неожиданный вызов» на новом безобидном примитиве, класс
      дефекта из «Контекста» SPEC).
    """

    TASK_TITLE = "Лёгкая песочница переходов"

    def setUp(self):
        super().setUp()

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        origin_sha_patcher = mock.patch.object(
            fsm, "_origin_main_sha", return_value="deadbeefcafefeed")
        origin_sha_patcher.start()
        self.addCleanup(origin_sha_patcher.stop)

        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = self.root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.in_repo_handlers: list = []
        in_repo_patcher = mock.patch.object(
            gitcmd, "in_repo", side_effect=self._in_repo_side_effect)
        in_repo_patcher.start()
        self.addCleanup(in_repo_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TASK_TITLE)
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

    def _in_repo_side_effect(self, repo, *args) -> subprocess.CompletedProcess:
        for handler in self.in_repo_handlers:
            result = handler(repo, *args)
            if result is not None:
                return result
        return gitcmd.git("-C", str(repo), *args)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            _PLAN_READY_TEMPLATE.format(task=self.TASK), encoding="utf-8")

    def write_acceptance_plank(self) -> None:
        """Кладёт `acceptance_tests/` c `SPEC.md` `schema_version: 2` без
        `skip_tests` + непустой `acceptance_tests/` (минимум один
        stub-тест) — обязаны быть на диске ДО перехода (`disk_backed_show`/
        `disk_backed_ls_tree_files` читают ИМЕННО диск, не настоящий git),
        иначе материализация планки (`acceptance.materialize_from_branch`)
        ничего не найдёт и переход уйдёт по вырожденной ветке «планка не
        найдена в источнике», минуя `acceptance.run` вовсе."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            _ACCEPTANCE_PLANK_SPEC_TEMPLATE.format(task=self.TASK),
            encoding="utf-8")
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(
            _ACCEPTANCE_PLANK_STUB_TEST, encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)
