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

from orchestrator import config, gitcmd, store

# Все пути `config`, которые сегодня подменяет хотя бы одна песочница
# (SPEC T037, AC-2) — порядок как в orchestrator/config.py.
ALL_CONFIG_ATTRS = (
    "DB", "TASKS", "LOGS", "ROOT", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
)


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
    """Замена `gitcmd.show` (A7): `rel` — всегда `tasks/<id>/<файл>`
    (соглашение всех вызывающих мест — `fsm.py`/`brief.py`/`fsm_advance.py`)
    — `artifact_source.resolve` теперь всегда возвращает `foreign=True`,
    и без этой подмены чтение ушло бы в `gitcmd.git`, заглушенный в этих
    песочницах (генерику или вовсе не исполняемый). Возвращает содержимое
    БУКВАЛЬНО с диска (`_tasks_relative_path`) — ветка (`branch`) не
    участвует: песочницы, которые сюда попадают, ведут ровно ОДИН
    источник истины (диск `config.TASKS`), git branch не заводят."""
    try:
        return _tasks_relative_path(rel).read_text(encoding="utf-8"), ""
    except FileNotFoundError:
        return None, "файла нет на диске"
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
            return _REAL_RUN(cmd, *args, **kwargs)
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
    """
    if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
            and args[-1].startswith("refs/heads/")):
        return subprocess.CompletedProcess(list(args), 1, "", "")
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
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
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
