"""Постоянная защита прогона канарейки с `--parallel` и без него (SPEC
01M5HJ4ZWRTB9481JC7SVYQ07B): сценарии одноразовой приёмки Б-1б
(01M5H24PZXZTBM03SF6V576S5P), которых нет в `tests/test_canary_parallel.py`,
и тесты на мутации, пережившие и тот файл, и приёмку.

Дочерний подменяется через `canary._child_argv`: argv настоящей сборки
заменяется интерпретатором с `_CHILD` и хвостом настоящего argv после
`run-task`. `_CHILD` — простой процесс с заданным кодом выхода (`mode:
exit`), процесс с внуком в своей группе (`mode: grandchild`) либо настоящий
`canary.cmd_canary_run_task` с путями песочницы из файла настроек и
`_run_one_task`, заменённым заглушкой на именованном канале (`mode: real`).
Запущенные дочерние учитываются обёрткой `canary._start_child`: сорвавшийся
сценарий снимает их группы SIGKILL, чтобы родитель не завис.

Ожидание — только событиями: дочерний «держится» на чтении своего FIFO, и
открытие FIFO на запись согласующим потоком блокирует, пока дочерний не
дошёл до этой точки. `cmd_canary` идёт в главном потоке; сигнал родителю —
`os.kill(os.getpid(), …)` только после проверки, что родитель поставил свой
обработчик.
"""
import contextlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, gitcmd, store
from tests.sandbox import ALL_CONFIG_ATTRS, InitializedTmpRootTest

REPO = Path(canary.__file__).resolve().parents[1]
FULL_SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
SHORT_SHA = FULL_SHA[:7]
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
STAMP_RE = re.compile(r"\[canary\] прогон ([0-9]{8}T[0-9]{6}Z):")

# Литерал вывода последовательного прогона — снят приёмкой Б-1б на коде до
# её правок (`run_stamp` и путь пула заменены метками).
SEQUENTIAL_LITERAL = """\
[canary] прогон <STAMP>: 2 задач из пула <POOL> в порядке прогона: alfa, beta; целевой sha 3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 (явный --sha), набор nabor-kedr (developer → model-pihta; источник: набор)
[ведение] alfa.md ratio=config sha=3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 метка=явный --sha набор=nabor-kedr сводка=developer → model-pihta; источник: набор codex=None
[ведение] beta.md ratio=config sha=3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 метка=явный --sha набор=nabor-kedr сводка=developer → model-pihta; источник: набор codex=None
[canary] прогон <STAMP> завершён
"""
RECORD_KEYS = {"pid", "process_start", "run_stamp", "sha", "set_name",
               "started_at", "tasks"}

_GRANDCHILD = r'''
import os, signal, sys
fd = os.open(sys.argv[1], os.O_WRONLY)
os.write(fd, str(os.getpid()).encode())
os.close(fd)
signal.pause()
'''

_CHILD = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
settings = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
sys.path.insert(0, settings["repo"])
tpl = sys.argv[2]
spec = {"hold": False} if sys.argv[3] == "rescue" else settings["children"][tpl]
flags = dict(zip(sys.argv[4::2], sys.argv[5::2]))

def note(kind):
    with open(settings["calls"], "a", encoding="utf-8") as out:
        out.write(json.dumps({"kind": kind, "template": tpl}) + "\n")

def hold():
    if spec.get("hold", True):
        fd = os.open(settings["fifos"][tpl], os.O_RDONLY)
        try:
            os.read(fd, 16)
        finally:
            os.close(fd)

note("start")
mode = spec.get("mode", "exit")
if mode == "exit":
    hold()
    sys.exit(spec.get("code", 0))
if mode == "grandchild":
    # Обработчик ставится ДО внука: SIGTERM, пришедший процессу, не выходит
    # и не бросает — дочерний завершится, только когда умрёт внук.
    signal.signal(signal.SIGTERM, lambda signum, frame: None)
    grandchild = subprocess.Popen([sys.executable, "-c", settings["grandchild"],
                                   settings["grandchild_fifo"]])
    grandchild.wait()
    sys.exit(0)

from unittest import mock
from orchestrator import canary, config, store
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
plan = canary.CanarySetPlan(settings["set_name"], {}, None, settings["summary"], ())

def drive(template_path, run_stamp, ratio, target_sha, sha_label, plan_arg, codex_auth):
    note("drive")
    if spec.get("row"):
        store.insert_canary_run(
            store.db(), run_stamp, tpl, "01FIXTURE" + tpl.upper(), 3, 1.5, 0, 0,
            "merged", None, False, False, main_sha=target_sha, verdict="green",
            set_name=plan_arg.name, models_summary=plan_arg.summary or None)
    hold()
    if "code" in spec:
        sys.exit(spec["code"])

def clone(*args, **kwargs):
    note("clone")
    raise RuntimeError("клон в тесте запрещён")

with mock.patch.object(canary, "_set_plan", return_value=plan), \
        mock.patch.object(canary, "_run_one_task", drive), \
        mock.patch.object(canary, "_ephemeral_clone", clone):
    canary.cmd_canary_run_task(
        run_stamp=flags["--stamp"], template_path=Path(flags["--template"]),
        target_sha=flags["--sha"], set_name=flags["--set"],
        summary=flags["--summary"])
'''


def _kill_group(child) -> None:
    # Пожатый процесс — его номер группы уже может носить чужая группа.
    if child.proc.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(child.proc.pid, signal.SIGKILL)


class _Run:
    def __init__(self, exc, out: str):
        self.exc = exc
        self.out = out
        match = STAMP_RE.search(out)
        self.stamp = match.group(1) if match else None


class _ProtectionSandbox(InitializedTmpRootTest):
    """Песочница родителя: пул, план набора и sha подменены; клон, профиль
    Codex, origin и ведение в процессе родителя запрещены."""

    set_name = SET_NAME

    def setUp(self):
        super().setUp()
        self.handlers_before = {s: signal.getsignal(s) for s in SIGNALS}
        self.addCleanup(lambda: [signal.signal(s, h)
                                 for s, h in self.handlers_before.items()])
        self.pool = self.root / "pool"
        self.pool.mkdir()
        for name in ("alfa", "beta", "gamma"):
            (self.pool / f"{name}.md").write_text("# учебная задача\n",
                                                  encoding="utf-8")
        self.registry = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        self.fifo_dir = self.root / "fifo"
        self.fifo_dir.mkdir()
        self.grandchild_fifo = str(self.fifo_dir / "grandchild")
        self.calls_path = self.root / "calls.jsonl"
        self.settings_path = self.root / "child-settings.json"
        self.children = {}
        self.argvs = []
        self.started = []
        self.forbidden = []
        self.rescued = False
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(canary, "_pool_dir",
                                              return_value=self.pool))
        stack.enter_context(mock.patch.object(
            canary, "_set_plan", side_effect=lambda name: canary.CanarySetPlan(
                name, {}, None, SUMMARY, ())))
        stack.enter_context(mock.patch.object(
            canary, "_resolve_target_sha", return_value=(FULL_SHA, None)))
        for name in ("_ephemeral_clone", "_locked_canary_profile",
                     "_canary_profile_auth", "_run_one_task"):
            stack.enter_context(mock.patch.object(
                canary, name, side_effect=self.forbid(name)))
        stack.enter_context(mock.patch.object(
            gitcmd, "fetch_ref_sha", side_effect=self.forbid("fetch_ref_sha")))
        stack.enter_context(mock.patch.object(
            canary, "_child_argv", side_effect=self.child_argv(canary._child_argv)))
        stack.enter_context(mock.patch.object(
            canary, "_start_child", side_effect=self.start_child(canary._start_child)))
        self.addCleanup(self.stop_children)

    def forbid(self, name):
        def refuse(*args, **kwargs):
            self.forbidden.append(name)
            raise AssertionError(f"{name} вызван")
        return refuse

    def child_argv(self, real):
        def build(run_stamp, template_path, target_sha, plan):
            argv = real(run_stamp, template_path, target_sha, plan)
            self.argvs.append((template_path.stem, argv))
            return [sys.executable, "-c", _CHILD, str(self.settings_path),
                    template_path.stem, "rescue" if self.rescued else "-",
                    *argv[argv.index("run-task") + 1:]]
        return build

    def start_child(self, real):
        def start(*args, **kwargs):
            child = real(*args, **kwargs)
            self.started.append(child)
            return child
        return start

    def rescue(self) -> None:
        """Сценарий сорвался: снять группы всех запущенных дочерних, а ещё не
        запущенных — пускать без ожидания, чтобы родитель не завис."""
        self.rescued = True
        for child in list(self.started):
            _kill_group(child)

    def stop_children(self) -> None:
        for child in self.started:
            _kill_group(child)
            with contextlib.suppress(ChildProcessError, OSError):
                child.proc.wait()

    def calls(self) -> list:
        if not self.calls_path.exists():
            return []
        return [json.loads(line) for line in
                self.calls_path.read_text(encoding="utf-8").splitlines() if line]

    def fifo(self, template: str) -> str:
        return str(self.fifo_dir / template)

    def listing(self) -> list:
        if not self.registry.is_dir():
            return []
        return sorted(p.name for p in self.registry.iterdir())

    def rows(self, stamp=None) -> list:
        return [dict(r) for r in store.all_canary_runs(store.db())
                if stamp is None or r["run_stamp"] == stamp]

    def baseline_rows(self) -> list:
        return [tuple(r) for r in store.db().execute(
            "SELECT * FROM canary_baseline ORDER BY title, set_name")]

    def stamp_of_first_child(self) -> str:
        _name, argv = self.argvs[0]
        return argv[argv.index("--stamp") + 1]

    def signal_parent(self, signum: int) -> None:
        if signal.getsignal(signum) == self.handlers_before[signum]:
            raise AssertionError(f"родитель не поставил обработчик "
                                 f"{signal.Signals(signum).name}")
        os.kill(os.getpid(), signum)

    def read_grandchild_pid(self) -> int:
        fd = os.open(self.grandchild_fifo, os.O_RDONLY)
        try:
            data = b""
            while chunk := os.read(fd, 64):
                data += chunk
        finally:
            os.close(fd)
        if not data:
            # Канал закрыт без pid: внук не запустился или вышел, не записав.
            raise AssertionError("внук не появился")
        return int(data)

    def assert_red_row(self, row: dict, stamp: str, template: str) -> None:
        """Красная строка родителя — поля `_report_child_failure`."""
        self.assertEqual(
            {k: row[k] for k in ("run_stamp", "title", "task_id", "steps",
                                 "cost_usd", "outcome", "expected_escalation",
                                 "main_sha", "verdict", "set_name")},
            {"run_stamp": stamp, "title": template, "task_id": None, "steps": 0,
             "cost_usd": 0.0, "outcome": canary._DRIVE_FAILED_OUTCOME,
             "expected_escalation": None, "main_sha": None, "verdict": "red",
             "set_name": self.set_name})

    def run_cli(self, argv, script=None) -> _Run:
        """`artel._cmd_canary(argv)` в главном потоке; `script(reach, release)`
        — согласующий поток. Канал `<шаблон>` держит дочернего в ведении."""
        fifos = list(self.children)
        for key in fifos:
            os.mkfifo(self.fifo(key))
        os.mkfifo(self.grandchild_fifo)
        self.settings_path.write_text(json.dumps({
            "repo": str(REPO), "set_name": self.set_name, "summary": SUMMARY,
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "children": self.children, "calls": str(self.calls_path),
            "fifos": {key: self.fifo(key) for key in fifos},
            "grandchild": _GRANDCHILD, "grandchild_fifo": self.grandchild_fifo},
            ensure_ascii=False), encoding="utf-8")
        held = {}

        def reach(template):
            if template not in held:
                held[template] = os.open(self.fifo(template), os.O_WRONLY)

        def release(template):
            reach(template)
            fd = held.pop(template)
            with contextlib.suppress(BrokenPipeError):
                os.write(fd, b"go\n")
            os.close(fd)

        errors = []

        def coordinate():
            try:
                if script is None:
                    for name, spec in self.children.items():
                        if spec.get("mode") == "real" and spec.get("hold", True):
                            release(name)
                else:
                    script(reach, release)
            except BaseException as exc:  # noqa: BLE001 — исход сценария
                errors.append(repr(exc))
                self.rescue()

        out = io.StringIO()
        exc = None
        thread = threading.Thread(target=coordinate, daemon=True)
        with contextlib.redirect_stdout(out):
            thread.start()
            try:
                artel._cmd_canary(list(argv))
            except BaseException as caught:  # noqa: BLE001 — исход сценария
                exc = caught
            # Согласующий поток, ждущий дочернего или внука, которого уже
            # нет, — отпустить открытием FIFO с другой стороны.
            unblock = [os.open(self.fifo(key), os.O_RDONLY | os.O_NONBLOCK)
                       for key in fifos]
            # Канал внука на запись закрывается сразу: открытый до `join`, он
            # не дал бы читающему потоку дойти до конца данных.
            with contextlib.suppress(OSError):
                os.close(os.open(self.grandchild_fifo,
                                 os.O_WRONLY | os.O_NONBLOCK))
            thread.join()
            for fd in list(held.values()) + unblock:
                os.close(fd)
        run = _Run(exc, out.getvalue())
        self.assertEqual(errors, [], run.out)
        self.assertEqual(self.forbidden, [], run.out)
        self.assertIsNotNone(run.stamp, run.out)
        return run

    def run_parallel(self, templates, script=None, extra=()) -> _Run:
        return self.run_cli(["--k", str(len(templates)), "--sha", SHORT_SHA,
                             "--set", self.set_name, "--template",
                             ",".join(templates), "--parallel", *extra], script)


class SequentialPathTest(_ProtectionSandbox):
    def test_sequential_run_output_rows_result_and_registry_as_before(self):
        """Прогон без `--parallel` — вывод, строки, файл результата и реестр прежние.

        Сценарий: `--k 2 --sha <короткий> --set <набор> --template alfa,beta
        --result-file <путь>`, ведение `_run_one_task` подменено заглушкой,
        печатающей «[ведение] …» и пишущей строку `canary_runs`. Вывод с
        метками `<STAMP>`/`<POOL>` дословно равен литералу; строки и файл
        результата — две зелёные задачи; во время ведения в реестре метка и
        запись прежнего набора полей, после прогона — пусто; дочерних нет.

        Ловит мутацию: строка «прогон <run_stamp> завершён» последовательной
        ветки `cmd_canary` изменена (например, «завершен»); либо ведение ушло
        в дочерние процессы; либо запись реестра получила новые поля.
        """
        seen = []

        def drive(template_path, run_stamp, ratio, target_sha, sha_label, plan,
                  codex_auth):
            record = self.registry / f"{run_stamp}-{os.getpid()}.json"
            seen.append((self.listing(),
                         json.loads(record.read_text(encoding="utf-8"))))
            print(f"[ведение] {template_path.name} "
                  f"ratio={'config' if ratio == config.CANARY_DEVIATION_RATIO else ratio} "
                  f"sha={target_sha} метка={sha_label} набор={plan.name} "
                  f"сводка={plan.summary} codex={codex_auth}")
            store.insert_canary_run(
                store.db(), run_stamp, template_path.stem,
                "01FIXTURE" + template_path.stem.upper(), 3, 1.5, 0, 0, "merged",
                None, False, False, main_sha=target_sha, verdict="green",
                set_name=plan.name, models_summary=plan.summary or None)

        result = self.root / "result.json"
        argv = ["--k", "2", "--sha", SHORT_SHA, "--set", SET_NAME, "--template",
                "alfa,beta", "--result-file", str(result)]
        with mock.patch.object(canary, "_run_one_task", side_effect=drive):
            run = self.run_cli(argv)
        self.assertIsNone(run.exc, run.out)
        self.assertEqual((self.argvs, self.started), ([], []))
        stamp = run.stamp
        self.assertEqual(run.out.replace(stamp, "<STAMP>").replace(str(self.pool),
                                                                   "<POOL>"),
                         SEQUENTIAL_LITERAL)
        self.assertEqual(
            [(r["run_stamp"], r["title"], r["task_id"], r["outcome"], r["main_sha"],
              r["verdict"], r["set_name"], r["models_summary"]) for r in self.rows()],
            [(stamp, name, "01FIXTURE" + name.upper(), "merged", FULL_SHA, "green",
              SET_NAME, SUMMARY) for name in ("alfa", "beta")])
        self.assertEqual(json.loads(result.read_text(encoding="utf-8")), {
            "status": "complete",
            "runs": [{"id": 1, "title": "alfa", "task_id": "01FIXTUREALFA",
                      "verdict": "green", "outcome": "merged"},
                     {"id": 2, "title": "beta", "task_id": "01FIXTUREBETA",
                      "verdict": "green", "outcome": "merged"}]})
        self.assertEqual(len(seen), 2)
        for listing, record in seen:
            self.assertEqual(listing, sorted([f"{stamp}-{os.getpid()}.json",
                                              f"{stamp}.lock"]))
            self.assertEqual(set(record), RECORD_KEYS)
            self.assertEqual((record["pid"], record["run_stamp"], record["sha"],
                              record["set_name"], record["tasks"]),
                             (os.getpid(), stamp, FULL_SHA, SET_NAME, 2))
        self.assertEqual(self.listing(), [])


class DetachTest(InitializedTmpRootTest):
    def test_parallel_with_detach_reaches_detached_process(self):
        """`--parallel --detach` — отвязанный процесс получает `--parallel`.

        Сценарий: `artel._cmd_canary(["--k", "2", "--parallel", "--detach"])`
        при подменённом `artel.subprocess.Popen`: argv отвязанного процесса
        несёт `--parallel` ровно один раз и `--result-file` ровно один раз,
        `--detach` в него не уходит; строка «результат:» в выводе одна.

        Ловит мутацию: `--parallel` снимается из argv до `_detach_canary`
        (фильтр `arg not in ("--detach", "--parallel")`) — отвязанный прогон
        идёт последовательно.
        """
        seen = []

        def popen(argv, *args, **kwargs):
            seen.append([str(a) for a in argv])
            return mock.Mock(pid=4242)

        out = io.StringIO()
        with mock.patch.object(artel.subprocess, "Popen", popen), \
                mock.patch.object(canary, "cmd_canary",
                                  side_effect=AssertionError("cmd_canary")), \
                contextlib.redirect_stdout(out):
            artel._cmd_canary(["--k", "2", "--parallel", "--detach"])
        self.assertEqual(len(seen), 1, out.getvalue())
        argv = seen[0]
        self.assertEqual(argv.count("--parallel"), 1, argv)
        self.assertEqual(argv.count("--result-file"), 1, argv)
        self.assertNotIn("--detach", argv)
        self.assertEqual(out.getvalue().count("результат:"), 1, out.getvalue())


class BaselineTest(_ProtectionSandbox):
    def test_parallel_run_leaves_canary_baseline_unchanged(self):
        """Параллельный прогон с кодом 0 таблицу `canary_baseline` не меняет.

        Сценарий: до прогона заведена базовая строка `alfa` того же набора;
        два дочерних — настоящий `cmd_canary_run_task` — пишут свои строки и
        выходят с 0; прогон возвращается без исключения, строки обоих
        зелёные, содержимое `canary_baseline` равно прежнему.

        Ловит мутацию: родитель в `_finish_child` пишет бейзлайн
        (`store.set_canary_baseline(...)` перед сверкой строки прогона) —
        базовая строка `alfa` перезаписана, у `beta` появилась своя.
        """
        self.children = {"alfa": {"mode": "real", "row": True, "hold": False},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        store.set_canary_baseline(store.db(), "alfa", 3, 1.0, 0, SET_NAME)
        baseline = self.baseline_rows()
        run = self.run_parallel(["alfa", "beta"])
        self.assertIsNone(run.exc, run.out)
        self.assertEqual(sorted((r["title"], r["verdict"])
                                for r in self.rows(run.stamp)),
                         [("alfa", "green"), ("beta", "green")])
        self.assertEqual(self.baseline_rows(), baseline)

    def test_parent_sigterm_leaves_canary_baseline_unchanged(self):
        """SIGTERM родителю: остановка дочерних, очередь не идёт, бейзлайн прежний.

        Сценарий: три шаблона, `alfa` и `beta` (настоящий
        `cmd_canary_run_task`) в ведении, `gamma` в очереди; SIGTERM родителю.
        Код — 128 + SIGTERM, `gamma` не запущен, у обоих строки «оборвана
        сигналом SIGTERM», строки «завершён» нет, реестр пуст, таблица
        `canary_baseline`, заведённая до прогона, равна прежней.

        Ловит мутацию: родитель в `_finish_child` пишет бейзлайн — на пути
        сигнала (остановка и итог живых дочерних) таблица изменилась.
        """
        self.children = {name: {"mode": "real"} for name in ("alfa", "beta", "gamma")}
        store.set_canary_baseline(store.db(), "alfa", 3, 1.0, 0, SET_NAME)
        baseline = self.baseline_rows()

        def script(reach, release):
            reach("alfa")
            reach("beta")
            self.signal_parent(signal.SIGTERM)

        run = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIsInstance(run.exc, SystemExit, run.out)
        self.assertEqual(run.exc.code, 128 + signal.SIGTERM, run.out)
        self.assertEqual([name for name, _argv in self.argvs], ["alfa", "beta"])
        self.assertEqual(sorted((r["title"], r["outcome"]) for r in self.rows()),
                         [("alfa", "оборвана сигналом SIGTERM"),
                          ("beta", "оборвана сигналом SIGTERM")], run.out)
        self.assertNotIn(f"[canary] прогон {run.stamp} завершён", run.out)
        self.assertEqual(self.listing(), [])
        self.assertEqual(self.baseline_rows(), baseline)


class RegistryTest(_ProtectionSandbox):
    def test_parent_death_run_stays_live_by_child_records(self):
        """Гибель родителя смоделирована — прогон держится записями дочерних.

        Сценарий: набор — `config.CANARY_DEFAULT_SET`; оба дочерних
        (настоящий `cmd_canary_run_task`, `--set` — из настоящего argv) в
        ведении; согласующий поток удаляет запись родителя
        `<run_stamp>-<pid родителя>.json` и пишет в метку pid завершившегося
        и пожатого процесса. В этот момент `live_run_note(default_set_only=
        True)` не `None`, называет `run_stamp` и не говорит «запись реестра
        отсутствует».

        Ловит мутацию: в `--set` дочернего уходит не имя набора плана
        (`plan.name.upper()`) — запись дочернего не набора по умолчанию, окно
        мержа держит только метка (или ничего).
        """
        self.set_name = config.CANARY_DEFAULT_SET
        dead = subprocess.Popen([sys.executable, "-c", ""])
        dead.wait()
        self.children = {"alfa": {"mode": "real"}, "beta": {"mode": "real"}}
        seen = {}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            stamp = self.stamp_of_first_child()
            (self.registry / f"{stamp}-{os.getpid()}.json").unlink()
            (self.registry / f"{stamp}.lock").write_text(f"{dead.pid}\n",
                                                        encoding="utf-8")
            seen["note"] = canary.live_run_note(default_set_only=True)
            release("alfa")
            release("beta")

        run = self.run_parallel(["alfa", "beta"], script)
        self.assertIsNotNone(seen.get("note"), run.out)
        self.assertIn(run.stamp, seen["note"])
        self.assertNotIn(canary.LIVE_MARK_ABSENT_NOTE, seen["note"])

    def test_dropped_mark_makes_next_child_refuse_with_red_row(self):
        """`canary live --drop` снимает метку — следующий дочерний отказывает.

        Сценарий: три шаблона; `alfa` и `beta` (настоящий
        `cmd_canary_run_task`, пишут строки) в ведении; согласующий поток
        удаляет все записи `<run_stamp>-*.json` и снимает метку
        `cmd_canary_live(drop=…)`, затем отпускает `alfa`/`beta`. Запущенный
        после них `gamma` отказывает по сверке метки: ни ведения, ни клона,
        у `gamma` ровно одна строка — красная строка родителя.

        Ловит мутацию: сверка метки в `cmd_canary_run_task` отключена (`if
        False:`) — `gamma` доходит до ведения; либо `_finish_child` не пишет
        красную строку дочернему без своей строки — `gamma` пропадает из
        итога.
        """
        self.children = {"alfa": {"mode": "real", "row": True},
                         "beta": {"mode": "real", "row": True},
                         "gamma": {"mode": "real", "hold": False}}
        seen = {}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            stamp = self.stamp_of_first_child()
            for record in self.registry.glob(f"{stamp}-*.json"):
                record.unlink()
            canary.cmd_canary_live(drop=stamp, reason="тест: метка без записей")
            seen["mark"] = (self.registry / f"{stamp}.lock").exists()
            release("alfa")
            release("beta")

        run = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIs(seen.get("mark"), False, run.out)
        self.assertEqual([name for name, _argv in self.argvs],
                         ["alfa", "beta", "gamma"])
        calls = self.calls()
        self.assertIn({"kind": "start", "template": "gamma"}, calls)
        self.assertNotIn({"kind": "drive", "template": "gamma"}, calls)
        self.assertEqual([c for c in calls if c["kind"] == "clone"], [])
        gamma = [r for r in self.rows(run.stamp) if r["title"] == "gamma"]
        self.assertEqual(len(gamma), 1, run.out)
        self.assert_red_row(gamma[0], run.stamp, "gamma")


class OutcomeTest(_ProtectionSandbox):
    def test_child_with_own_row_and_nonzero_code_makes_run_red(self):
        """Дочерний записал свою строку и вышел с ненулевым кодом — прогон красный.

        Сценарий: `alfa` (настоящий `cmd_canary_run_task`) пишет свою строку
        и выходит с кодом 3, `beta` — строку и код 0. Родитель завершается
        `SystemExit` «прогон <run_stamp> красный»; у `alfa` ровно одна строка
        прогона — своя, красной строки родителя нет; строка «прогон
        <run_stamp> завершён» есть; заголовок блока `alfa` называет код 3.

        Ловит мутацию: в `_finish_child` итог шаблона со строкой не смотрит на
        код выхода (`return reason is None and not child.killed`) — прогон с
        кодом 3 считается прошедшим, `cmd_canary` возвращается без отказа.
        """
        self.children = {"alfa": {"mode": "real", "row": True, "hold": False,
                                  "code": 3},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        run = self.run_parallel(["alfa", "beta"])
        self.assertIsInstance(run.exc, SystemExit, run.out)
        self.assertIn(f"прогон {run.stamp} красный", str(run.exc.code))
        alfa = [r for r in self.rows(run.stamp) if r["title"] == "alfa"]
        self.assertEqual([(r["task_id"], r["verdict"]) for r in alfa],
                         [("01FIXTUREALFA", "green")])
        self.assertIn(f"[canary] прогон {run.stamp} завершён", run.out)
        self.assertRegex(run.out, r"\[canary\] alfa: процесс \d+ завершён с "
                                  r"кодом 3, журнал ")


class SigintTest(_ProtectionSandbox):
    def test_parent_sigint_stops_children_with_exit_130(self):
        """SIGINT родителю — тот же путь остановки, что SIGTERM, код 130.

        Сценарий: `alfa` и `beta` (настоящий `cmd_canary_run_task`) в
        ведении; согласующий поток, проверив, что родитель поставил свой
        обработчик SIGINT, шлёт SIGINT. Исход — `SystemExit(128 + SIGINT)`, не
        `KeyboardInterrupt`; у обоих дочерних строки «оборвана сигналом
        SIGTERM», строки «завершён» нет, реестр пуст, обработчики сигналов
        процесса теста восстановлены.

        Ловит мутацию: SIGINT выпал из `_PARALLEL_SIGNALS` — родитель не
        ставит обработчик SIGINT (сценарий отказывает, дочерние сняты
        SIGKILL), а Ctrl-C пришёл бы `KeyboardInterrupt` без кода 130.
        """
        self.children = {"alfa": {"mode": "real"}, "beta": {"mode": "real"}}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            self.signal_parent(signal.SIGINT)

        run = self.run_parallel(["alfa", "beta"], script)
        self.assertIsInstance(run.exc, SystemExit, repr(run.exc) + run.out)
        self.assertEqual(run.exc.code, 128 + signal.SIGINT, run.out)
        self.assertEqual(sorted((r["title"], r["outcome"]) for r in self.rows()),
                         [("alfa", "оборвана сигналом SIGTERM"),
                          ("beta", "оборвана сигналом SIGTERM")])
        self.assertNotIn(f"[canary] прогон {run.stamp} завершён", run.out)
        self.assertEqual(self.listing(), [])
        self.assertEqual({s: signal.getsignal(s) for s in SIGNALS},
                         self.handlers_before)


class GroupSignalTest(_ProtectionSandbox):
    def test_parent_sigterm_reaches_grandchild_in_child_group(self):
        """SIGTERM родителя доходит до всей группы дочернего, не только до него.

        Сценарий: дочерний — простой процесс с пустым обработчиком SIGTERM,
        поставленным до внука; внук в той же группе пишет свой pid в FIFO и
        ждёт сигнала. Согласующий поток, прочитав pid внука, шлёт SIGTERM
        родителю. Дочерний завершается сам после гибели внука — в выводе нет
        причины «снят SIGKILL»; внука больше нет.

        Ловит мутацию: `_signal_group` шлёт сигнал одному процессу
        (`os.kill` вместо `os.killpg`) — внук жив, дочерний снят SIGKILL
        после `PARALLEL_STOP_GRACE_SEC`, группа ведения в клоне осталась бы.
        """
        self.children = {"alfa": {"mode": "grandchild"}}
        seen = {}

        def kill_grandchild():
            with contextlib.suppress(ProcessLookupError):
                os.kill(seen["grandchild"], signal.SIGKILL)

        def script(reach, release):
            seen["grandchild"] = self.read_grandchild_pid()
            self.addCleanup(kill_grandchild)
            self.signal_parent(signal.SIGTERM)

        run = self.run_parallel(["alfa"], script)
        self.assertIsInstance(run.exc, SystemExit, run.out)
        self.assertEqual(run.exc.code, 128 + signal.SIGTERM, run.out)
        self.assertNotIn("снят SIGKILL", run.out)
        self.assertRegex(run.out, r"\[canary\] alfa: процесс \d+ завершён с "
                                  r"кодом 0, журнал ")
        with self.assertRaises(ProcessLookupError):
            os.kill(seen["grandchild"], 0)
