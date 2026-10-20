"""Реестр живого прогона канарейки: запись и метка рядом с ней, уборка на любом исходе, повтор run_stamp, run_stamp вызывающему и файл результата отвязанного запуска.

Группа: долгоживущий
Красен до реализации: cmd_canary не пишет ни записи реестра, ни метки, не возвращает run_stamp и не знает параметра-приёмника, а файл результата отбирает строки canary_runs по номеру — строка чужого прогона попадает в файл.

Связка, которую держит файл: «публичная команда канарейки (`canary.cmd_canary`
и `artel.main()` с argv `canary …`) — каталог реестра под корнем песочницы —
БД пульта». Песочница — `tests.sandbox.RealGitSandbox`: настоящий git,
пути `config` во временном каталоге (`ALL_CONFIG_ATTRS`), пул из нескольких
учебных шаблонов в подменённом домашнем каталоге. Ведение задачи в клоне
подменено на уровне `subprocess.Popen` (образец —
`tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`): ролей и сети нет.
Прогон, обрываемый сигналом, и «второй процесс» — настоящий дочерний процесс
с той же командой; о готовности он сообщает строкой в канал (без опроса
по часам).

Имён каталога реестра и формата записи SPEC не задаёт, поэтому запись
ищется по поведению: файл под корнем песочницы (вне `.git` и вне
временных клонов), в имени которого есть `run_stamp` (`ГГГГММДДTччммссZ`)
и pid прогона; метка — файл того же каталога, в имени которого есть тот
же `run_stamp` и нет других цифр. Время старта процесса для проверки
содержимого задаётся подменой ответа `ps -o lstart=` (его читает
`process_start_time`) на случайный момент, порождённый от зерна.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import inspect
import io
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, catalog, config, doctor, runner, store
from tests.sandbox import ALL_CONFIG_ATTRS, RealGitSandbox

REPO = Path(__file__).resolve().parents[1]
STAMP_RE = re.compile(r"\d{8}T\d{6}Z")
STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"
OLD_PARAMS = {"k", "sha", "set_name", "templates"}
TEMPLATES = ("uchebnaya-a", "uchebnaya-b", "uchebnaya-c")

# Дочерний процесс: та же команда `artel.py canary …`, ведение в клоне
# заменено процессом-сном; о старте ведения сообщает строкой JSON в канал.
_CHILD = r'''
import contextlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from orchestrator import artel, canary, catalog, config, runner
settings = json.loads(Path(sys.argv[1]).read_text())
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
ready = int(settings["ready_fd"])
real_popen = subprocess.Popen
real_run = subprocess.run
def run(argv, *args, **kwargs):
    words = [os.fsdecode(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    if settings.get("ps_none") and "lstart=" in words and str(os.getpid()) in words:
        return subprocess.CompletedProcess(argv, 1, "", "")
    return real_run(argv, *args, **kwargs)
def launch(argv, *args, **kwargs):
    words = [os.fsdecode(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    if canary.CANARY_DRIVE_MODULE not in words:
        return real_popen(argv, *args, **kwargs)
    drive = real_popen([sys.executable, "-c", "import time; time.sleep(600)"],
                       *args, **kwargs)
    os.write(ready, (json.dumps({"pid": os.getpid(), "drive_pid": drive.pid})
                     + "\n").encode())
    return drive
class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.strptime(settings["stamp"], "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc)
with contextlib.ExitStack() as stack:
    stack.enter_context(mock.patch.object(Path, "home", return_value=Path(settings["home"])))
    stack.enter_context(mock.patch.object(catalog, "cmd_init"))
    stack.enter_context(mock.patch.object(subprocess, "Popen", launch))
    stack.enter_context(mock.patch.object(subprocess, "run", run))
    stack.enter_context(mock.patch.object(runner, "in_role_environment", return_value=False))
    if settings.get("stamp"):
        stack.enter_context(mock.patch.object(canary, "datetime", FixedDateTime))
    sys.argv = ["artel.py", "canary", *settings["argv"]]
    artel.main()
'''


class _Receiver(dict):
    """Приёмник любой из естественных форм: вызов, `append`, `put`, запись по ключу."""

    def __init__(self, on_value):
        super().__init__()
        self.on_value = on_value

    def __call__(self, *args, **kwargs):
        for value in (*args, *kwargs.values()):
            self.on_value(value)

    def append(self, value):
        self.on_value(value)

    put = append

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.on_value(value)


class CanaryRegistryTest(RealGitSandbox):
    """Пул из нескольких шаблонов, вход ведения в дереве, без ролей и сети."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        self.temp_root = self.root / ".artel" / "canary-test-tmp"
        self.temp_root.mkdir(parents=True)
        temp_patch = mock.patch.object(tempfile, "tempdir", str(self.temp_root))
        temp_patch.start()
        self.addCleanup(temp_patch.stop)
        env_patch = mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# вход заменён процессом теста\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture drive")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.home = Path(tempfile.mkdtemp(prefix="canary-registry-home-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        for name in TEMPLATES:
            (pool / f"{name}.md").write_text(f"# учебная задача {name}\n",
                                             encoding="utf-8")
        self.children = []
        self.stray_pids = []
        self.addCleanup(self.stop_children)

    # ------------------------------------------------------------ фикстуры

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=30)
        for pid in self.stray_pids:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)

    def templates(self, k: int) -> list:
        return self.rng.sample(TEMPLATES, k)

    def scan(self) -> list:
        """Файлы под корнем песочницы с `run_stamp` в имени — вне `.git` и клонов."""
        found = []
        for path in self.root.rglob("*"):
            if ".git" in path.parts or self.temp_root in path.parents:
                continue
            if path.is_file() and STAMP_RE.search(path.name):
                found.append(path)
        return found

    @staticmethod
    def has_pid(name: str, pid: int) -> bool:
        return re.search(rf"(?<!\d){pid}(?!\d)", name) is not None

    @staticmethod
    def is_mark_of(name: str, stamp: str) -> bool:
        return stamp in name and not re.search(r"\d", name.replace(stamp, ""))

    def records(self, pid: int) -> list:
        return [p for p in self.scan() if self.has_pid(p.name, pid)]

    def marks(self, record: Path) -> list:
        stamp = STAMP_RE.search(record.name).group(0)
        return [p for p in record.parent.iterdir()
                if p.is_file() and self.is_mark_of(p.name, stamp)]

    def snapshot(self, pid: int) -> dict:
        """{путь: текст} записей реестра процесса `pid` и их меток."""
        shot = {}
        for record in self.records(pid):
            shot[record] = record.read_text(encoding="utf-8", errors="replace")
            for mark in self.marks(record):
                shot[mark] = mark.read_bytes().decode("utf-8", errors="replace")
        return shot

    def normal_result(self, words: list) -> None:
        result = Path(words[words.index("--result") + 1])
        result.write_text(json.dumps({
            "task_id": "01FIXTURE", "head": self.sha,
            "outcome": "killed", "escalated": False,
            "metrics": {"steps": 1, "cost_usd": 0.0,
                        "review_iterations": 0, "escalations": [],
                        "dev_retries": 0, "outcome": "killed",
                        "kill_note": "штатно", "test_author_visited": False,
                        "ceiling_exhausted": False, "ceiling_raise": None},
            "steps": [],
        }))

    def run_inline(self, outcome: str = "normal", *, k: int = 1, templates=None,
                   kwargs=None, main_argv=None, on_drive=None, ps_text=None,
                   stamp=None) -> dict:
        """Прогон канарейки в процессе теста; ведение — штатный выход либо исключение.

        `ps_text` — ответ `ps -o lstart=` для pid процесса теста; `stamp` —
        фиксированный `run_stamp` (подмена `canary.datetime.now`)."""
        templates = templates or self.templates(k)
        pid = os.getpid()
        seen = {"clones": 0, "at_first_clone": None, "at_drive": None,
                "value": None, "exc": None, "out": ""}
        self.current = seen
        real_popen, real_run = subprocess.Popen, subprocess.run

        def run(argv, *args, **kw):
            words = ([os.fsdecode(a) for a in argv]
                     if isinstance(argv, (list, tuple)) else [])
            if words[:2] == ["git", "clone"]:
                if seen["clones"] == 0:
                    seen["at_first_clone"] = self.snapshot(pid)
                seen["clones"] += 1
            if ps_text is not None and "lstart=" in words and str(pid) in words:
                return subprocess.CompletedProcess(argv, 0, ps_text + "\n", "")
            return real_run(argv, *args, **kw)

        def launch(argv, *args, **kw):
            words = ([os.fsdecode(a) for a in argv]
                     if isinstance(argv, (list, tuple)) else [])
            if canary.CANARY_DRIVE_MODULE not in words:
                return real_popen(argv, *args, **kw)
            if seen["at_drive"] is None:
                seen["at_drive"] = self.snapshot(pid)
            if on_drive is not None:
                on_drive(seen)
            if outcome == "exception":
                raise RuntimeError("подменённое ведение оборвалось")
            self.normal_result(words)
            return real_popen([sys.executable, "-c", "pass"], *args, **kw)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.strptime(stamp, STAMP_FORMAT).replace(
                    tzinfo=timezone.utc)

        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(Path, "home", return_value=self.home))
            stack.enter_context(mock.patch.object(catalog, "cmd_init"))
            stack.enter_context(mock.patch.object(subprocess, "Popen", launch))
            stack.enter_context(mock.patch.object(subprocess, "run", run))
            stack.enter_context(mock.patch.object(runner, "in_role_environment",
                                                  return_value=False))
            if stamp is not None:
                stack.enter_context(mock.patch.object(canary, "datetime",
                                                      FixedDateTime))
            stack.enter_context(contextlib.redirect_stdout(out))
            try:
                if main_argv is not None:
                    with mock.patch.object(sys, "argv", ["artel.py", "canary",
                                                         *main_argv]):
                        artel.main()
                else:
                    seen["value"] = canary.cmd_canary(
                        k=len(templates), sha=self.sha, templates=list(templates),
                        **(kwargs or {}))
            except BaseException as exc:  # noqa: BLE001 — исход сценария
                seen["exc"] = exc
        seen["out"] = out.getvalue()
        return seen

    def start_child(self, *, argv=None, stamp=None, ps_none=False, k: int = 1) -> dict:
        """Канарейка в дочернем процессе; возврат после старта подменённого ведения."""
        argv = argv or ["--k", str(k), "--sha", self.sha,
                        "--template", ",".join(self.templates(k))]
        read_fd, write_fd = os.pipe()
        n = len(self.children)
        settings = self.home / f"settings-{n}.json"
        settings.write_text(json.dumps({
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "home": str(self.home), "argv": argv, "ready_fd": write_fd,
            "stamp": stamp, "ps_none": ps_none}), encoding="utf-8")
        log_path = self.home / f"child-{n}.log"
        with open(log_path, "wb") as log:
            child = subprocess.Popen([sys.executable, "-c", _CHILD, str(settings)],
                                     cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                     pass_fds=(write_fd,), start_new_session=True)
        os.close(write_fd)
        self.children.append(child)
        with os.fdopen(read_fd, encoding="utf-8") as ready:
            line = ready.readline()
        if not line:
            child.wait(timeout=60)
            self.fail(self.msg("дочерняя канарейка не дошла до ведения: "
                               + log_path.read_text(errors="replace")))
        state = json.loads(line)
        self.stray_pids.append(state["drive_pid"])
        state.update(child=child, log=log_path)
        return state

    def stop_child(self, state: dict, signum=signal.SIGTERM) -> str:
        os.kill(state["child"].pid, signum)
        state["child"].wait(timeout=60)
        return state["log"].read_text(errors="replace")

    def stamp_of(self, shot: dict) -> str:
        names = [p.name for p in shot]
        self.assertTrue(names, self.msg("записи реестра нет"))
        return STAMP_RE.search(names[0]).group(0)

    # -------------------------------------------------------------- AC-1

    def test_ac1_record_written_before_first_clone_with_all_fields(self):
        """Прогон из k случайных шаблонов при подменённом ответе `ps`: к первому `git clone` в песочнице лежит запись реестра.

        Наблюдение: файл под корнем песочницы (не в `.git`, не отслеживается
        git), в имени — `run_stamp` прогона и pid процесса; текст несёт pid,
        время старта процесса (значение `process_start_time` при той же
        подмене), `run_stamp`, проверяемый sha, имя набора, число задач k и
        момент начала прогона (время между началом и концом вызова, кроме
        самого `run_stamp`).

        Ловит мутацию: запись пишется после клона (или после первого
        шаблона) — к первому `git clone` её нет; либо поле `число задач`
        либо время старта процесса не записано — текст его не несёт.
        """
        k = self.rng.randint(2, 3)
        fake_start = (datetime(2031, 1, 1) + timedelta(
            seconds=self.rng.randrange(300 * 24 * 3600))).replace(microsecond=0)
        ps_text = fake_start.strftime(LSTART_FORMAT)
        pid = os.getpid()
        before = datetime.now(timezone.utc)
        seen = self.run_inline("exception", k=k, ps_text=ps_text)
        after = datetime.now(timezone.utc)
        shot = seen["at_first_clone"]
        self.assertGreater(seen["clones"], 0, self.msg(seen["out"]))
        records = [p for p in (shot or {}) if self.has_pid(p.name, pid)]
        self.assertEqual(len(records), 1, self.msg(f"записи к первому клону: {shot}"))
        record = records[0]
        text = shot[record]
        stamp = STAMP_RE.search(record.name).group(0)
        self.assertIn(self.root, record.parents, self.msg(record))
        self.assertNotIn(".git", record.relative_to(self.root).parts, self.msg(record))
        tracked = self.git("ls-files", "--", str(record.relative_to(self.root)))
        self.assertEqual(tracked.strip(), "", self.msg(f"запись в git: {record}"))
        for label, value in (("pid", str(pid)), ("run_stamp", stamp),
                             ("sha", self.sha),
                             ("набор", config.CANARY_DEFAULT_SET)):
            self.assertIn(value, text, self.msg(f"{label} нет в записи: {text!r}"))
        self.assertRegex(text, rf"(?<![\d.]){k}(?![\d.])",
                         self.msg(f"число задач {k} нет в записи: {text!r}"))
        with mock.patch.object(subprocess, "run", side_effect=lambda argv, *a, **kw:
                               subprocess.CompletedProcess(argv, 0, ps_text + "\n", "")):
            expected_start = doctor.process_start_time(pid)
        self.assertIsNotNone(expected_start)
        moments = list(_moments(text))
        self.assertTrue(
            any(abs((m - expected_start).total_seconds()) < 1 for m in moments)
            or ps_text in text,
            self.msg(f"время старта {expected_start} нет в записи: {text!r}"))
        stamp_moment = datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc)
        started = [m for m in moments
                   if before - timedelta(seconds=2) <= m <= after + timedelta(seconds=2)]
        self.assertTrue(
            started or text.count(stamp) > 1,
            self.msg(f"момент начала прогона (около {stamp_moment}) нет в записи: {text!r}"))

    # ------------------------------------------------------------ AC-2/3

    def test_ac2_record_removed_after_normal_end(self):
        """Штатный прогон: запись реестра, лежавшая на старте ведения, после возврата `cmd_canary` исчезла.

        Ловит мутацию: снятие записи стоит только в обработчике исключения —
        после штатного конца файл с pid процесса остаётся в каталоге реестра.
        """
        pid = os.getpid()
        seen = self.run_inline("normal", k=1)
        self.assertIsNone(seen["exc"], self.msg(seen["out"]))
        self.assertTrue([p for p in seen["at_drive"] or {} if self.has_pid(p.name, pid)],
                        self.msg("во время ведения записи реестра нет"))
        self.assertEqual(self.records(pid), [], self.msg(seen["out"]))

    def test_ac3_record_removed_after_exception(self):
        """Ведение задачи падает исключением: оно выходит из `cmd_canary`, запись реестра снята.

        Ловит мутацию: снятие записи — строкой после цикла по шаблонам, не в
        `finally` — исключение уносит прогон, запись остаётся.
        """
        pid = os.getpid()
        seen = self.run_inline("exception", k=self.rng.randint(1, 3))
        self.assertIsInstance(seen["exc"], RuntimeError, self.msg(seen["out"]))
        self.assertTrue([p for p in seen["at_drive"] or {} if self.has_pid(p.name, pid)],
                        self.msg("во время ведения записи реестра нет"))
        self.assertEqual(self.records(pid), [], self.msg(seen["out"]))

    # -------------------------------------------------------------- AC-4

    def test_ac4_record_removed_after_signal(self):
        """Дочерняя канарейка получает SIGTERM, затем другая — SIGHUP, посреди ведения задачи.

        Наблюдение: до сигнала в каталоге реестра есть запись с pid ребёнка,
        после его выхода — нет.

        Ловит мутацию: снятие записи висит на `atexit`/штатном конце и не
        срабатывает на выходе через обработчик сигнала — запись с pid
        оборванного прогона остаётся.
        """
        for signum in (signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signal.Signals(signum).name):
                state = self.start_child()
                self.assertTrue(self.records(state["pid"]),
                                self.msg("до сигнала записи реестра нет"))
                log = self.stop_child(state, signum)
                self.assertEqual(self.records(state["pid"]), [], self.msg(log))

    # -------------------------------------------------------------- AC-6

    def fixed_stamp(self) -> str:
        return datetime.now(timezone.utc).strftime(STAMP_FORMAT)

    def assert_refused(self, seen: dict, stamp: str, ctx: str) -> None:
        exc = seen["exc"]
        self.assertIsInstance(exc, SystemExit, self.msg(f"{ctx}: {seen['out']}"))
        self.assertIn(f"прогон {stamp} уже идёт", f"{exc.code}\n{seen['out']}",
                      self.msg(ctx))

    def test_ac6_same_stamp_from_other_process_refused(self):
        """Живой прогон с run_stamp S в дочернем процессе: запуск с тем же S из процесса теста (другой pid) — отказ.

        Наблюдение: отказ «прогон S уже идёт»; метка и запись живого
        прогона после отказа те же (содержимое, inode, время правки), записи
        отказанного процесса нет.

        Ловит мутацию: метка создаётся открытием на запись без `O_EXCL` —
        второй запуск перезаписывает метку и идёт дальше вместо отказа.
        """
        stamp = self.fixed_stamp()
        state = self.start_child(stamp=stamp)
        records = self.records(state["pid"])
        self.assertEqual(len(records), 1, self.msg(records))
        guarded = [records[0], *self.marks(records[0])]
        self.assertEqual(len(guarded), 2, self.msg(f"метки нет рядом с записью: {guarded}"))
        before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                  for p in guarded}
        seen = self.run_inline("normal", stamp=stamp)
        self.assert_refused(seen, stamp, "другой процесс")
        self.assertEqual(self.records(os.getpid()), [], self.msg(seen["out"]))
        self.assertEqual({p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                          for p in guarded}, before, self.msg("метка/запись тронуты"))
        self.assertEqual(self.records(state["pid"]), records,
                         self.msg("запись живого прогона пропала после отказа"))
        self.stop_child(state)

    def test_ac6_existing_mark_alone_refuses_without_registry_read(self):
        """У живого прогона S удалена сама запись реестра, метка S осталась: новый запуск с S — отказ.

        Наблюдение: «прогон S уже идёт», метка не перезаписана (содержимое,
        inode, время правки), записи отказанного процесса нет.

        Ловит мутацию: проверка повтора — «прочитать реестр, потом
        записать» (живых записей с S нет → запуск идёт и перезаписывает
        метку) вместо исключительного создания метки.
        """
        stamp = self.fixed_stamp()
        state = self.start_child(stamp=stamp)
        record = self.records(state["pid"])[0]
        marks = self.marks(record)
        self.assertEqual(len(marks), 1, self.msg(marks))
        mark = marks[0]
        before = (mark.read_bytes(), mark.stat().st_ino, mark.stat().st_mtime_ns)
        record.unlink()
        seen = self.run_inline("normal", stamp=stamp)
        self.assert_refused(seen, stamp, "метка без записи")
        self.assertTrue(mark.exists(), self.msg("метка удалена отказанным запуском"))
        self.assertEqual((mark.read_bytes(), mark.stat().st_ino, mark.stat().st_mtime_ns),
                         before, self.msg("метка перезаписана"))
        self.assertEqual(self.records(os.getpid()), [], self.msg(seen["out"]))

    def test_ac6_mark_removed_on_normal_end_exception_and_signal(self):
        """Метка прогона есть во время ведения и исчезает при штатном конце, исключении и сигнале.

        Ловит мутацию: в `finally` снимается только запись реестра, метка
        `run_stamp` остаётся — следующий прогон в ту же секунду отказан бы
        навсегда, а файл метки виден в каталоге после конца прогона.
        """
        for outcome in ("normal", "exception", "signal"):
            with self.subTest(исход=outcome):
                if outcome == "signal":
                    state = self.start_child()
                    record = self.records(state["pid"])[0]
                    marks = self.marks(record)
                    log = self.stop_child(state)
                else:
                    pid = os.getpid()
                    seen = self.run_inline(outcome)
                    shot = seen["at_drive"] or {}
                    record = next((p for p in shot if self.has_pid(p.name, pid)), None)
                    self.assertIsNotNone(record, self.msg(seen["out"]))
                    marks = [p for p in shot if p != record]
                    log = seen["out"]
                self.assertEqual(len(marks), 1, self.msg(f"метки нет: {marks}; {log}"))
                self.assertFalse(marks[0].exists(), self.msg(f"метка осталась: {log}"))

    # ------------------------------------------------------------- AC-14

    def receiver_param(self) -> str:
        params = inspect.signature(canary.cmd_canary).parameters
        candidates = [name for name, p in params.items()
                      if name not in OLD_PARAMS and p.default is None]
        if len(candidates) > 1:
            candidates = [n for n in candidates if "stamp" in n] or candidates
        self.assertEqual(len(candidates), 1,
                         self.msg(f"необязательный параметр-приёмник не найден: "
                                  f"{list(params)}"))
        return candidates[0]

    def test_ac14_returns_stamp_and_reports_it_before_first_clone(self):
        """`cmd_canary` с приёмником и без него: возврат — run_stamp прогона, приёмник получает его до первого клона.

        Наблюдение: возвращённое значение равно `run_stamp` первой строки
        вывода «[canary] прогон <run_stamp>: …»; приёмник (принимает вызов,
        `append`, `put` или запись по ключу) получил то же значение, когда
        `git clone` ещё не звался; вызов без параметра проходит и
        возвращает свой run_stamp.

        Ловит мутацию: run_stamp сообщается приёмнику после цикла по
        шаблонам (или не сообщается вовсе) — к первому клону приёмник пуст;
        либо `cmd_canary` по-прежнему возвращает `None`.
        """
        plain = self.run_inline("normal")
        self.assertIsNone(plain["exc"], self.msg(plain["out"]))
        printed = re.search(r"\[canary\] прогон (\d{8}T\d{6}Z):", plain["out"])
        self.assertIsNotNone(printed, self.msg(plain["out"]))
        self.assertEqual(plain["value"], printed.group(1), self.msg(plain["out"]))

        name = self.receiver_param()
        got = []
        clones = {"n": None}

        def on_value(value):
            got.append(value)
            if clones["n"] is None:
                clones["n"] = self.current["clones"]

        receiver = _Receiver(on_value)
        seen = self.run_inline("normal", kwargs={name: receiver})
        self.assertIsNone(seen["exc"], self.msg(seen["out"]))
        printed = re.search(r"\[canary\] прогон (\d{8}T\d{6}Z):", seen["out"])
        self.assertIsNotNone(printed, self.msg(seen["out"]))
        self.assertEqual(seen["value"], printed.group(1), self.msg(seen["out"]))
        self.assertIn(printed.group(1), [str(v) for v in got],
                      self.msg(f"приёмник получил {got}"))
        self.assertEqual(clones["n"], 0, self.msg("run_stamp сообщён после клона"))

    def result_rows(self, path: Path) -> list:
        return json.loads(path.read_text(encoding="utf-8"))["runs"]

    def stamp_ids(self, stamp: str) -> set:
        return {row["id"] for row in store.all_canary_runs(store.db())
                if dict(row).get("run_stamp") == stamp}

    def foreign_row(self) -> str:
        stamp = (datetime(2030, 1, 1) + timedelta(
            seconds=self.rng.randrange(10 ** 7))).strftime(STAMP_FORMAT)
        store.insert_canary_run(store.db(), stamp, "chuzhoj-shablon", None, 0, 0.0,
                                0, 0, "чужой прогон", None, False, False,
                                verdict="red")
        return stamp

    def test_ac14_result_file_takes_only_own_stamp_rows(self):
        """Файл результата (`canary … --result-file`) при чужой строке canary_runs, вставленной во время прогона.

        Три исхода: штатный конец и исключение — в процессе теста, сигнал
        SIGTERM — у дочернего процесса. Наблюдение: номера строк файла ровно
        совпадают с номерами строк БД с run_stamp этого прогона; чужой строки
        в файле нет; на сигнале файл несёт строку «оборвана сигналом».

        Ловит мутацию: отбор по-прежнему «номер строки больше запомненного
        до прогона» — чужая строка, вставленная во время прогона, попадает
        в файл результата.
        """
        for outcome in ("normal", "exception", "signal"):
            with self.subTest(исход=outcome):
                result = self.home / f"result-{outcome}.json"
                argv = ["--k", "1", "--sha", self.sha, "--template",
                        self.templates(1)[0], "--result-file", str(result)]
                foreign = {}
                if outcome == "signal":
                    state = self.start_child(argv=argv)
                    stamp = STAMP_RE.search(self.records(state["pid"])[0].name).group(0)
                    foreign["stamp"] = self.foreign_row()
                    log = self.stop_child(state)
                else:
                    pid = os.getpid()

                    def on_drive(_seen):
                        foreign.setdefault("stamp", self.foreign_row())
                        foreign.setdefault("own", self.stamp_of(
                            {p: "" for p in self.records(pid)}))

                    seen = self.run_inline(outcome, main_argv=argv, on_drive=on_drive)
                    stamp = foreign["own"]
                    log = seen["out"]
                rows = self.result_rows(result)
                ids = {row["id"] for row in rows}
                self.assertEqual(ids, self.stamp_ids(stamp), self.msg(f"{rows}; {log}"))
                self.assertFalse(ids & self.stamp_ids(foreign["stamp"]),
                                 self.msg(f"чужая строка в файле: {rows}"))
                if outcome == "signal":
                    self.assertTrue(any("оборвана сигналом" in (row["outcome"] or "")
                                        for row in rows), self.msg(f"{rows}; {log}"))


def _moments(text: str):
    """Моменты времени, записанные в тексте: ISO 8601 (с поясом и без) и секунды эпохи."""
    iso = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
                     r"(?:Z|[+-]\d{2}:?\d{2})?")
    for match in iso.finditer(text):
        raw = match.group(0).replace(" ", "T").replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if moment.tzinfo is None:
            yield moment.replace(tzinfo=timezone.utc)
            yield moment.astimezone(timezone.utc)
        else:
            yield moment.astimezone(timezone.utc)
    for match in re.finditer(r"(?<![\d.])1\d{9}(?:\.\d+)?(?!\d)", text):
        yield datetime.fromtimestamp(float(match.group(0)), timezone.utc)


if __name__ == "__main__":
    unittest.main()
