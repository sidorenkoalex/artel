"""Родитель параллельного прогона канарейки `canary --parallel` (SPEC
01M5H24PZXZTBM03SF6V576S5P, требование 9).

Дочерний подменяется через `canary._child_argv`: argv настоящей сборки
заменяется интерпретатором с `_CHILD` и хвостом настоящего argv после
`run-task`. `_CHILD` — либо простой процесс с заданным кодом выхода
(`mode: exit`; только очередь и коды выхода), либо настоящий
`canary.cmd_canary_run_task` с путями песочницы из файла настроек и
`_run_one_task`, заменённым заглушкой на именованном канале.

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
import signal
import sys
import threading
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, gitcmd, store
from tests.sandbox import ALL_CONFIG_ATTRS, InitializedTmpRootTest

REPO = Path(canary.__file__).resolve().parents[1]
FULL_SHA = "3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93"
SET_NAME = "nabor-kedr"
SUMMARY = "developer → model-pihta; источник: набор"
# Настоящая сборка argv — до подмены песочницы `_ParallelSandbox`.
REAL_CHILD_ARGV = canary._child_argv

_CHILD = r'''
import json, os, signal, sys
from pathlib import Path
settings = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
sys.path.insert(0, settings["repo"])
tpl = sys.argv[2]
flags = dict(zip(sys.argv[3::2], sys.argv[4::2]))
spec = settings["children"][tpl]
live = Path(settings["live_dir"])

def note(kind, **extra):
    with open(settings["calls"], "a", encoding="utf-8") as out:
        out.write(json.dumps({"kind": kind, "template": tpl, **extra}) + "\n")

def wait_fifo(key):
    fd = os.open(settings["fifos"][key], os.O_RDONLY)
    try:
        os.read(fd, 16)
    finally:
        os.close(fd)

def hold():
    if spec.get("hold", True):
        wait_fifo(tpl)

def on_term(signum, frame):
    note("term")
    if spec.get("term_hold"):
        wait_fifo(tpl + ".term")
    os._exit(128 + signum)

def catch_term():
    if spec.get("term_exit") or spec.get("term_hold"):
        signal.signal(signal.SIGTERM, on_term)

catch_term()
note("start")
print(f"дочерний {tpl}: начало", flush=True)
if spec.get("mode", "exit") == "exit":
    hold()
    note("exit")
    sys.exit(spec.get("code", 0))

from unittest import mock
from orchestrator import canary, config, store
for name, value in settings["config"].items():
    setattr(config, name, Path(value))
plan = canary.CanarySetPlan(settings["set_name"], {}, None, settings["summary"], ())

def drive(template_path, run_stamp, ratio, target_sha, sha_label, plan_arg, codex_auth):
    note("drive", record=(live / f"{run_stamp}-{os.getppid()}.json").exists(),
         mark=(live / f"{run_stamp}.lock").exists())
    if spec.get("row"):
        store.insert_canary_run(
            store.db(), run_stamp, tpl, "01FIXTURE" + tpl.upper(), 3, 1.5, 0, 0,
            "merged", None, False, False, main_sha=target_sha, verdict="green",
            set_name=plan_arg.name, models_summary=plan_arg.summary or None)
    if spec.get("ignore_term"):
        signal.signal(signal.SIGTERM, lambda signum, frame: note("term"))
    catch_term()
    hold()

with mock.patch.object(canary, "_set_plan", return_value=plan), \
        mock.patch.object(canary, "_run_one_task", drive):
    canary.cmd_canary_run_task(
        run_stamp=flags["--stamp"], template_path=Path(flags["--template"]),
        target_sha=flags["--sha"], set_name=flags["--set"],
        summary=flags["--summary"])
'''


class _ParallelSandbox(InitializedTmpRootTest):
    """Песочница родителя: пул, план набора и sha подменены; клон, профиль
    Codex, origin и ведение в процессе родителя запрещены."""

    codex_roles = ()

    def setUp(self):
        super().setUp()
        self.handlers_before = {s: signal.getsignal(s)
                                for s in (signal.SIGTERM, signal.SIGHUP,
                                          signal.SIGINT)}
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
        self.calls_path = self.root / "calls.jsonl"
        self.settings_path = self.root / "child-settings.json"
        self.children = {}
        self.argvs = []
        self.forbidden = []
        self.resolved = []
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(canary, "_pool_dir",
                                              return_value=self.pool))
        stack.enter_context(mock.patch.object(
            canary, "_set_plan", side_effect=lambda name: canary.CanarySetPlan(
                name, {}, None, SUMMARY, tuple(self.codex_roles))))
        stack.enter_context(mock.patch.object(
            canary, "_resolve_target_sha", side_effect=self.resolve))
        for name in ("_ephemeral_clone", "_locked_canary_profile",
                     "_canary_profile_auth", "_run_one_task"):
            stack.enter_context(mock.patch.object(
                canary, name, side_effect=self.forbid(name)))
        stack.enter_context(mock.patch.object(
            gitcmd, "fetch_ref_sha", side_effect=self.forbid("fetch_ref_sha")))
        stack.enter_context(mock.patch.object(
            canary, "_child_argv", side_effect=self.child_argv(canary._child_argv)))

    def resolve(self, explicit):
        self.resolved.append(explicit)
        return FULL_SHA, None

    def forbid(self, name):
        def refuse(*args, **kwargs):
            self.forbidden.append(name)
            raise AssertionError(f"{name} вызван")
        return refuse

    def child_argv(self, real):
        def build(run_stamp, template_path, target_sha, plan):
            argv = real(run_stamp, template_path, target_sha, plan)
            self.argvs.append((template_path.stem, argv, self.calls()))
            spec = self.children[template_path.stem]
            if spec.get("missing_interpreter"):
                return [str(self.root / "нет-интерпретатора")]
            return [sys.executable, "-c", _CHILD, str(self.settings_path),
                    template_path.stem, *argv[argv.index("run-task") + 1:]]
        return build

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

    def rows(self) -> list:
        return [dict(r) for r in store.all_canary_runs(store.db())]

    def signal_parent(self, signum: int) -> None:
        if signal.getsignal(signum) == self.handlers_before[signum]:
            raise AssertionError("родитель не поставил обработчик сигнала")
        os.kill(os.getpid(), signum)

    def run_parallel(self, templates, script=None, extra=()):
        """`artel._cmd_canary([... "--parallel"])` в главном потоке;
        `script(reach, release)` — согласующий поток. Канал `<шаблон>` держит
        дочернего в ведении, `<шаблон>.term` — в его обработчике SIGTERM
        (`term_hold`)."""
        fifos = [key for name in self.children for key in (name, name + ".term")]
        for key in fifos:
            os.mkfifo(self.fifo(key))
        self.settings_path.write_text(json.dumps({
            "repo": str(REPO), "set_name": SET_NAME, "summary": SUMMARY,
            "config": {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS},
            "children": self.children, "calls": str(self.calls_path),
            "fifos": {key: self.fifo(key) for key in fifos},
            "live_dir": str(self.registry)}, ensure_ascii=False), encoding="utf-8")
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
                    for name in templates:
                        if self.children[name].get("hold", True):
                            release(name)
                else:
                    script(reach, release)
            except BaseException as exc:  # noqa: BLE001 — исход сценария
                errors.append(repr(exc))

        out = io.StringIO()
        exc = None
        thread = threading.Thread(target=coordinate, daemon=True)
        with contextlib.redirect_stdout(out):
            thread.start()
            try:
                artel._cmd_canary(["--k", str(len(templates)), "--set", SET_NAME,
                                   "--template", ",".join(templates),
                                   "--parallel", *extra])
            except BaseException as caught:  # noqa: BLE001 — исход сценария
                exc = caught
            # Согласующий поток, ждущий дочернего, которого уже нет, —
            # отпустить открытием FIFO на чтение.
            unblock = [os.open(self.fifo(key), os.O_RDONLY | os.O_NONBLOCK)
                       for key in fifos]
            thread.join()
            for fd in list(held.values()) + unblock:
                os.close(fd)
        self.assertEqual(errors, [], out.getvalue())
        self.assertEqual(self.forbidden, [], out.getvalue())
        return exc, out.getvalue()


class ChildArgvTest(_ParallelSandbox):
    def test_child_argv_is_unbuffered_run_task_with_five_flags(self):
        """argv дочернего — интерпретатор пульта с `-u`, `artel.py canary
        run-task` и пять флагов со значениями родителя.

        Ловит мутацию: `-u` потерян либо в `--sha` уходит не переданный
        полный sha, в `--set` — не имя набора плана."""
        plan = canary.CanarySetPlan(SET_NAME, {}, None, SUMMARY, ())
        template = self.pool / "alfa.md"
        argv = REAL_CHILD_ARGV("20310305T101500Z", template, FULL_SHA, plan)
        self.assertEqual(argv[:2], [sys.executable, "-u"])
        self.assertEqual(Path(argv[2]), REPO / "orchestrator" / "artel.py")
        self.assertEqual(argv[3:], [
            "canary", "run-task", "--stamp", "20310305T101500Z",
            "--template", str(template), "--sha", FULL_SHA, "--set", SET_NAME,
            "--summary", SUMMARY])


class QueueTest(_ParallelSandbox):
    def test_at_most_two_children_queue_survives_nonzero_and_missing_rows(self):
        """`--k 3`: `gamma` запускается только после завершения `alfa`; код 3
        `alfa` очередь не останавливает; дочерние без строки прогона получают
        красные строки родителя, код выхода ненулевой; журнал дочернего —
        `<LOGS>/canary/<run_stamp>-<шаблон>.log`.

        Ловит мутацию: предел не держится — `gamma` собирается до выхода
        `alfa`; либо ненулевой код обрывает очередь; либо родитель смотрит
        только на код выхода и не пишет красную строку дочернему с кодом 0."""
        self.children = {"alfa": {"code": 3}, "beta": {"code": 0},
                         "gamma": {"code": 0}}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            release("alfa")
            reach("gamma")
            release("beta")
            release("gamma")

        exc, out = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertNotIn(exc.code, (0, None), out)
        self.assertEqual([name for name, _argv, _calls in self.argvs],
                         ["alfa", "beta", "gamma"])
        _name, _argv, calls_at_gamma = self.argvs[2]
        exited = {c["template"] for c in calls_at_gamma if c["kind"] == "exit"}
        self.assertIn("alfa", exited, out)
        self.assertNotIn("beta", exited, out)
        rows = {r["title"]: r for r in self.rows()}
        self.assertEqual(sorted(rows), ["alfa", "beta", "gamma"])
        for name, code in (("alfa", 3), ("beta", 0), ("gamma", 0)):
            self.assertEqual((rows[name]["outcome"], rows[name]["verdict"],
                              rows[name]["task_id"], rows[name]["main_sha"]),
                             (canary._DRIVE_FAILED_OUTCOME, "red", None, None))
            self.assertIn(f"{name}: учебная задача шаблона {name} не доведена — "
                          f"процесс задачи завершился с кодом {code} без строки "
                          f"прогона", out)
        stamp = rows["alfa"]["run_stamp"]
        log = Path(config.LOGS) / "canary" / f"{stamp}-alfa.log"
        self.assertIn("дочерний alfa: начало", log.read_text(encoding="utf-8"))
        self.assertIn("[canary] alfa: процесс ", out)
        self.assertIn(f"завершён с кодом 3, журнал {log}\nдочерний alfa: начало\n",
                      out)
        self.assertTrue(out.splitlines()[0].endswith(
            " параллельно: не более 2 процессов"), out)
        self.assertIn(f"[canary] прогон {stamp} завершён", out)
        self.assertEqual(self.listing(), [])

    def test_unstarted_child_gets_red_row_and_queue_goes_on(self):
        """Создание процесса `alfa` падает — красная строка «процесс задачи
        не запущен», `beta` запущен, код выхода ненулевой.

        Ловит мутацию: исключение запуска роняет прогон (`beta` не
        запущен) либо глотается без строки и без ненулевого кода."""
        self.children = {"alfa": {"missing_interpreter": True, "hold": False},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        exc, out = self.run_parallel(["alfa", "beta"])
        self.assertIsInstance(exc, SystemExit, out)
        self.assertNotIn(exc.code, (0, None), out)
        rows = {r["title"]: r for r in self.rows()}
        self.assertEqual((rows["alfa"]["outcome"], rows["alfa"]["verdict"]),
                         (canary._DRIVE_FAILED_OUTCOME, "red"))
        self.assertEqual(rows["beta"]["verdict"], "green")
        self.assertIn("alfa не доведена — процесс задачи не запущен: ", out)

    def test_all_children_with_rows_exit_zero(self):
        """Оба дочерних — настоящие `run-task`, записали строку и вышли с 0:
        прогон без красных строк, `cmd_canary` возвращает `run_stamp`.

        Ловит мутацию: родитель пишет красную строку и дочернему со своей
        строкой — дубль и ненулевой код."""
        self.children = {"alfa": {"mode": "real", "row": True, "hold": False},
                         "beta": {"mode": "real", "row": True, "hold": False}}
        exc, out = self.run_parallel(["alfa", "beta"])
        self.assertIsNone(exc, out)
        self.assertEqual(sorted((r["title"], r["verdict"]) for r in self.rows()),
                         [("alfa", "green"), ("beta", "green")])
        for name, argv, _calls in self.argvs:
            self.assertEqual(argv[argv.index("--sha") + 1], FULL_SHA)


class StopTest(_ParallelSandbox):
    def test_parent_sigterm_stops_children_and_skips_queue(self):
        """SIGTERM родителю при двух ведущих задачах и третьей в очереди:
        дочерние пишут «оборвана сигналом SIGTERM», `gamma` не запущен,
        строки «завершён» нет, код 143, реестр пуст; пока шло ведение, запись
        и метка родителя были на месте.

        Ловит мутацию: выход по сигналу мимо остановки дочерних — их строк
        «оборвана» нет; либо очередь запускает `gamma` после сигнала; либо
        запись родителя снята до завершения дочерних."""
        self.children = {name: {"mode": "real"} for name in ("alfa", "beta", "gamma")}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            self.signal_parent(signal.SIGTERM)

        exc, out = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(exc.code, 128 + signal.SIGTERM, out)
        self.assertEqual([name for name, _argv, _calls in self.argvs],
                         ["alfa", "beta"])
        self.assertEqual(sorted((r["title"], r["outcome"]) for r in self.rows()),
                         [("alfa", "оборвана сигналом SIGTERM"),
                          ("beta", "оборвана сигналом SIGTERM")], out)
        self.assertNotRegex(out, r"прогон [0-9]{8}T[0-9]{6}Z завершён")
        drives = [c for c in self.calls() if c["kind"] == "drive"]
        self.assertEqual(sorted((c["template"], c["record"], c["mark"])
                                for c in drives),
                         [("alfa", True, True), ("beta", True, True)])
        self.assertEqual(self.listing(), [])

    def test_term_ignoring_child_is_killed_after_grace(self):
        """Дочерний игнорирует SIGTERM — снят SIGKILL по сроку (подменён на
        1 с): красная строка с причиной «снят SIGKILL после 1 с…», его запись
        реестра, которую он сам не снял, убрана родителем.

        Ловит мутацию: ожидание без SIGKILL — прогон висит; либо запись
        снятого дочернего остаётся в реестре; либо красной строки нет."""
        self.children = {"alfa": {"mode": "real", "ignore_term": True}}

        def script(reach, release):
            reach("alfa")
            self.signal_parent(signal.SIGTERM)

        with mock.patch.object(canary, "PARALLEL_STOP_GRACE_SEC", 1):
            exc, out = self.run_parallel(["alfa"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(exc.code, 128 + signal.SIGTERM, out)
        self.assertEqual([c["kind"] for c in self.calls()].count("term"), 1, out)
        (row,) = self.rows()
        self.assertEqual((row["title"], row["outcome"], row["verdict"]),
                         ("alfa", canary._DRIVE_FAILED_OUTCOME, "red"))
        self.assertIn("alfa не доведена — снят SIGKILL после 1 с; группа ведения "
                      "в клоне могла остаться — проверь doctor", out)
        self.assertIn(f"завершён с кодом {-signal.SIGKILL}, журнал", out)
        self.assertEqual(self.listing(), [])

    def test_killed_child_with_own_row_gets_no_duplicate(self):
        """Дочерний записал свою строку, игнорирует SIGTERM и снят SIGKILL по
        сроку (подменён на 1 с): за шаблон в `canary_runs` и в файле
        результата ровно одна строка — его собственная.

        Ловит мутацию: красная строка «снят SIGKILL…» пишется любому снятому
        SIGKILL дочернему без сверки `canary_runs` — у шаблона две строки."""
        self.children = {"alfa": {"mode": "real", "row": True, "ignore_term": True}}
        result = self.root / "result.json"

        def script(reach, release):
            reach("alfa")
            self.signal_parent(signal.SIGTERM)

        with mock.patch.object(canary, "PARALLEL_STOP_GRACE_SEC", 1):
            exc, out = self.run_parallel(["alfa"], script,
                                         extra=["--result-file", str(result)])
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(exc.code, 128 + signal.SIGTERM, out)
        self.assertIn(f"завершён с кодом {-signal.SIGKILL}, журнал", out)
        self.assertEqual([(r["title"], r["task_id"], r["verdict"], r["outcome"])
                          for r in self.rows()],
                         [("alfa", "01FIXTUREALFA", "green", "merged")])
        runs = json.loads(result.read_text(encoding="utf-8"))["runs"]
        self.assertEqual([(r["title"], r["task_id"]) for r in runs],
                         [("alfa", "01FIXTUREALFA")])
        self.assertNotIn("снят SIGKILL", out)
        self.assertEqual(self.listing(), [])

    def test_second_signal_does_not_interrupt_stop(self):
        """SIGHUP приходит, пока дочерние сидят в обработчике SIGTERM
        родителя: остановка доходит до конца — оба дочерних пожаты, у каждого
        одна красная строка, реестр пуст, код — 128 + SIGTERM (первый).

        Ловит мутацию: остановка не под откладыванием сигналов — SIGHUP рвёт
        ожидание дочерних (красных строк нет, код 129); либо поздний сигнал
        подменяет код выхода первого."""
        self.children = {name: {"term_hold": True} for name in ("alfa", "beta")}

        def script(reach, release):
            reach("alfa")
            reach("beta")
            self.signal_parent(signal.SIGTERM)
            reach("alfa.term")
            reach("beta.term")
            self.signal_parent(signal.SIGHUP)
            release("alfa.term")
            release("beta.term")

        exc, out = self.run_parallel(["alfa", "beta"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(exc.code, 128 + signal.SIGTERM, out)
        self.assertEqual(sorted(c["template"] for c in self.calls()
                                if c["kind"] == "term"), ["alfa", "beta"])
        self.assertEqual(sorted((r["title"], r["verdict"]) for r in self.rows()),
                         [("alfa", "red"), ("beta", "red")])
        self.assertEqual(self.listing(), [])


class _WaitFault:
    """Подмена `canary._wait_child`: первый вызов ждёт `ready` (согласующий
    поток: дочерние в ведении), ставит `raised` и бросает `exc`; остальные —
    настоящая функция."""

    def __init__(self, exc):
        self.real = canary._wait_child
        self.exc = exc
        self.ready = threading.Event()
        self.raised = threading.Event()
        self.lock = threading.Lock()
        self.fired = False

    def __call__(self, proc):
        with self.lock:
            first, self.fired = not self.fired, True
        if not first:
            return self.real(proc)
        self.ready.wait()
        self.raised.set()
        raise self.exc


WAIT_ERROR = "ожидание сорвалось"


class WaitFailureTest(_ParallelSandbox):
    def _wait_exception_run(self, children):
        """`alfa`/`beta` в ведении, первое ожидание бросает `RuntimeError`;
        `gamma` в очереди. Дочерний с прерванным ожиданием — тот, кому
        пришёл SIGTERM."""
        self.children = children
        fault = _WaitFault(RuntimeError(WAIT_ERROR))

        def script(reach, release):
            reach("alfa")
            reach("beta")
            fault.ready.set()
            reach("gamma")
            for name in ("alfa", "beta", "gamma"):
                release(name)

        with mock.patch.object(canary, "_wait_child", fault):
            exc, out = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertNotIn(exc.code, (0, None), out)
        self.assertEqual([name for name, _argv, _calls in self.argvs],
                         ["alfa", "beta", "gamma"])
        terms = [c["template"] for c in self.calls() if c["kind"] == "term"]
        self.assertEqual(len(terms), 1, out)
        self.assertIn(terms[0], ("alfa", "beta"))
        self.assertEqual(self.listing(), [])
        return out, terms[0]

    def test_wait_exception_red_row_group_stopped_queue_goes_on(self):
        """`Exception` из `_wait_child`: группе дочернего — SIGTERM, у шаблона
        одна красная строка с причиной «ожидание процесса задачи прервано»,
        `gamma` запущен, код выхода ненулевой.

        Ловит мутацию: исключение ожидания обрывает очередь (`gamma` не
        запущен); либо глотается без красной строки; либо группа дочернего не
        снимается (SIGTERM не приходит, прогон висит на нём)."""
        out, failed = self._wait_exception_run(
            {"alfa": {"term_exit": True}, "beta": {"term_exit": True},
             "gamma": {}})
        mine = [r for r in self.rows() if r["title"] == failed]
        self.assertEqual([(r["outcome"], r["verdict"], r["task_id"]) for r in mine],
                         [(canary._DRIVE_FAILED_OUTCOME, "red", None)])
        self.assertIn(f"{failed}: учебная задача шаблона {failed} не доведена — "
                      f"ожидание процесса задачи прервано: {WAIT_ERROR}", out)

    def test_wait_exception_no_second_row_when_row_exists(self):
        """`Exception` из `_wait_child` у дочернего, уже записавшего строку:
        второй строки нет — за каждый шаблон одна, собственная зелёная.

        Ловит мутацию: красная строка за прерванное ожидание пишется без
        сверки `canary_runs` — у шаблона две строки."""
        self._wait_exception_run(
            {name: {"mode": "real", "row": True, "term_exit": True}
             for name in ("alfa", "beta", "gamma")})
        self.assertEqual(sorted((r["title"], r["task_id"], r["verdict"])
                                for r in self.rows()),
                         [(name, "01FIXTURE" + name.upper(), "green")
                          for name in ("alfa", "beta", "gamma")])

    def test_base_exception_in_wait_then_signal_during_stop(self):
        """`KeyboardInterrupt` из `_wait_child` при двух живых дочерних, во
        время их остановки — SIGHUP родителю: `gamma` не запущен, оба
        дочерних получили SIGTERM и пожаты, реестр пуст, код — 128 + SIGHUP.

        Ловит мутацию: `KeyboardInterrupt` выходит мимо остановки дочерних
        (исход — сам `KeyboardInterrupt`, SIGTERM дочерним нет); либо
        пришедший во время остановки сигнал не попадает в код выхода."""
        self.children = {name: {"term_hold": True}
                         for name in ("alfa", "beta", "gamma")}
        fault = _WaitFault(KeyboardInterrupt())

        def script(reach, release):
            reach("alfa")
            reach("beta")
            fault.ready.set()
            fault.raised.wait()
            reach("alfa.term")
            reach("beta.term")
            self.signal_parent(signal.SIGHUP)
            release("alfa.term")
            release("beta.term")

        with mock.patch.object(canary, "_wait_child", fault):
            exc, out = self.run_parallel(["alfa", "beta", "gamma"], script)
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(exc.code, 128 + signal.SIGHUP, out)
        self.assertEqual([name for name, _argv, _calls in self.argvs],
                         ["alfa", "beta"])
        self.assertEqual(sorted(c["template"] for c in self.calls()
                                if c["kind"] == "term"), ["alfa", "beta"])
        self.assertEqual(self.listing(), [])


class _FixedDateTime(canary.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2031, 3, 5, 10, 15, 0, tzinfo=canary.timezone.utc)


class ParentRefusalTest(_ParallelSandbox):
    def test_repeated_template_refused_before_sha_and_registry(self):
        """`--parallel` с повтором имени шаблона — прежний отказ
        `_named_pool_templates` до `_resolve_target_sha`, реестра и дочерних.

        Ловит мутацию: параллельная ветка выбирает шаблоны мимо прежней
        сверки повтора — прогон доходит до origin и реестра."""
        self.children = {"alfa": {"hold": False}}
        exc, out = self.run_parallel(["alfa", "alfa"])
        self.assertIsInstance(exc, SystemExit, out)
        self.assertIn("canary: --template повторяет имя шаблона: alfa",
                      str(exc.code))
        self.assertEqual((self.resolved, self.argvs, self.listing()), ([], [], []))

    def test_live_run_stamp_refused_without_receiver_and_children(self):
        """Тот же `run_stamp` уже идёт (чужие метка, запись и строка): отказ
        «прогон <run_stamp> уже идёт», дочерних нет, файл результата пуст,
        чужие метка и запись не тронуты.

        Ловит мутацию: родитель отдаёт `run_stamp` приёмнику до записи
        реестра — файл результата несёт строку чужого прогона; либо дочерние
        запускаются мимо отказа."""
        self.children = {"alfa": {"hold": False}, "beta": {"hold": False}}
        stamp = "20310305T101500Z"
        owner = os.getppid()
        self.registry.mkdir(parents=True, exist_ok=True)
        mark = self.registry / f"{stamp}.lock"
        mark.write_text(f"{owner}\n", encoding="utf-8")
        record = self.registry / f"{stamp}-{owner}.json"
        record.write_text(json.dumps({"pid": owner, "run_stamp": stamp}),
                          encoding="utf-8")
        store.insert_canary_run(store.db(), stamp, "chuzhoy", "01FOREIGN", 1, 0.5,
                                0, 0, "merged", None, False, False,
                                main_sha=FULL_SHA, verdict="green",
                                set_name=SET_NAME, models_summary=SUMMARY)
        result = self.root / "result.json"
        with mock.patch.object(canary, "datetime", _FixedDateTime):
            exc, out = self.run_parallel(["alfa", "beta"],
                                         extra=["--result-file", str(result)])
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(str(exc.code), f"canary: прогон {stamp} уже идёт")
        self.assertEqual(self.argvs, [])
        self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["runs"], [])
        self.assertEqual(mark.read_text(encoding="utf-8"), f"{owner}\n")
        self.assertTrue(record.exists())


class RefusalTest(_ParallelSandbox):
    codex_roles = ("developer", "reviewer")

    def test_codex_set_refused_before_origin_and_registry(self):
        """Набор с ролями Codex и `--parallel` — отказ до origin и реестра.

        Ловит мутацию: проверка `codex_roles` после `_resolve_target_sha`
        или после записи реестра."""
        self.children = {"alfa": {"hold": False}, "beta": {"hold": False}}
        exc, out = self.run_parallel(["alfa", "beta"])
        self.assertIsInstance(exc, SystemExit, out)
        self.assertEqual(str(exc.code), (
            f"canary: --parallel недоступен для набора {SET_NAME}: роли "
            f"developer, reviewer на провайдере codex — профиль Codex канарейки "
            f"один на машину; веди прогон без --parallel"))
        self.assertEqual((self.resolved, self.argvs, self.listing()), ([], [], []))


class RunTaskShaTest(InitializedTmpRootTest):
    def test_short_sha_refused_before_record(self):
        """`cmd_canary_run_task` с коротким sha — отказ до плана и реестра.

        Ловит мутацию: сверка формы sha стоит после записи дочернего либо
        без якоря конца (`match` вместо `fullmatch`)."""
        directory = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        directory.mkdir(parents=True)
        (directory / "20310305T101500Z.lock").write_text(f"{os.getppid()}\n",
                                                         encoding="utf-8")
        with mock.patch.object(canary, "_set_plan",
                               side_effect=AssertionError("план")) as plan:
            for sha in (FULL_SHA[:7], FULL_SHA + "0"):
                with self.subTest(sha), self.assertRaises(SystemExit) as caught:
                    canary.cmd_canary_run_task(
                        run_stamp="20310305T101500Z",
                        template_path=Path("alfa.md"), target_sha=sha,
                        set_name=SET_NAME, summary=SUMMARY)
                self.assertEqual(str(caught.exception.code),
                                 f"canary run-task: --sha {sha} — не полный "
                                 f"40-символьный sha")
        plan.assert_not_called()
        self.assertEqual(sorted(p.name for p in directory.iterdir()),
                         ["20310305T101500Z.lock"])

    def test_upper_case_sha_refused_before_record(self):
        """Полный sha в верхнем регистре — не форма `[0-9a-f]{40}`: отказ до
        плана и реестра.

        Ловит мутацию: сверка формы без учёта регистра (`re.IGNORECASE` или
        `.lower()` перед сверкой)."""
        directory = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        directory.mkdir(parents=True)
        (directory / "20310305T101500Z.lock").write_text(f"{os.getppid()}\n",
                                                         encoding="utf-8")
        sha = FULL_SHA.upper()
        with mock.patch.object(canary, "_set_plan",
                               side_effect=AssertionError("план")) as plan, \
                self.assertRaises(SystemExit) as caught:
            canary.cmd_canary_run_task(
                run_stamp="20310305T101500Z", template_path=Path("alfa.md"),
                target_sha=sha, set_name=SET_NAME, summary=SUMMARY)
        self.assertEqual(str(caught.exception.code),
                         f"canary run-task: --sha {sha} — не полный "
                         f"40-символьный sha")
        plan.assert_not_called()
        self.assertEqual(sorted(p.name for p in directory.iterdir()),
                         ["20310305T101500Z.lock"])


class ParallelFlagParsingTest(InitializedTmpRootTest):
    def test_flag_passed_only_when_given_and_repeat_refused(self):
        """Без флага `cmd_canary` зовётся прежним набором аргументов, с флагом
        — с `parallel=True`; повтор — отказ до `--detach`.

        Ловит мутацию: `parallel=False` передаётся всегда; либо повтор
        флага с `--detach` уходит в отвязанный процесс."""
        with mock.patch.object(canary, "cmd_canary") as call:
            artel._cmd_canary(["--k", "2"])
            artel._cmd_canary(["--k", "2", "--parallel"])
        self.assertNotIn("parallel", call.call_args_list[0].kwargs)
        self.assertIs(call.call_args_list[1].kwargs["parallel"], True)
        with mock.patch.object(artel, "_detach_canary") as detach, \
                self.assertRaises(SystemExit) as caught:
            artel._cmd_canary(["--k", "2", "--parallel", "--detach", "--parallel"])
        self.assertEqual(caught.exception.code, "canary: повторный --parallel")
        detach.assert_not_called()
