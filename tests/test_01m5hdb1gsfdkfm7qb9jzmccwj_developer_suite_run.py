"""`suite-run` под маркером developer: новый полный прогон отказывает до любых записей, `--wait`/`--failed` и прочие вызывающие — прежние.

Группа: долгоживущий
Красен до реализации: `suite_run.cmd_suite_run` роль не проверяет — под `ARTEL_ROLE=developer` `suite-run <id>` без флагов берёт замок, заводит лог и запускает фоновый процесс, отказа нет; подсказки `--wait`/`--failed` и миссия developer называют `suite-run <id>` без флагов и не говорят о CI и гейте приёмки (AC-1, AC-2, AC-5, миссия AC-7); AC-3, AC-4, AC-6 и миссия ревьювера внешнего проекта держат прежнее поведение и зелены с рождения.

Провалидировано временным стабом реализации (удалён, не закоммичен):
ранний отказ developer с чтением БД `mode=ro`, подсказки по маркеру и
новая `suite_run_note` — все методы зелёные, `MissionTest::test_ac25`
прежнего файла тестов `suite-run` тоже; мутации
«отказ любой роли» и «отказ после `deliver_journal`» красят AC-6 и AC-1.

Стенд — `tests.sandbox.TmpRootTest`: пути `config` (БД, логи, области
проектов, `targets.yaml` с профилем тестов артели) во временном каталоге.
Задачи артели — в БД песочницы, их рабочие копии — пустые каталоги на
месте `workspace.path`. Связка, которую держит стенд: команда
`suite_run.cmd_suite_run` — хозяйство `suite-run` (`suite_lock.directory()`:
замок, отложенный журнал, логи, `run.json`) — БД пульта.

Тяжёлое подменено. Запуск фонового процесса (`subprocess.Popen`
интерпретатора пульта) либо исполняется в процессе теста тем же кодом
(`python -c <код>`, в окружении, которое команда ему передала), либо только
отмечается pid; прочие запуски процессов — настоящие. Прогон набора
(`acceptance.run_full_suite`) отдаёт готовый вывод pytest сценария, дерево
прогона (`appendix_tree.suite_tree`) — сама рабочая копия. Открытие БД
пульта (`store.db`) — подмена, считающая вызовы: обычная БД либо
соединение только на чтение (`mode=ro`, как в стенде `readonly_db`), запись
в котором отказывает. Досыл журнала (`suite_lock.deliver_journal`) — та же
функция под счётчиком вызовов.

Настоящего `sleep` и ожидания фоновых процессов нет: `--wait` зовётся
только с `0`. Идентификаторы задач, префикс id, роль процесса, состав
набора и порядок сценариев — от зерна; зерно печатается и входит в текст
каждого провала.
"""
import contextlib
import io
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, appendix_tree, brief, config, review,
                          role_prompt, store, suite_lock, suite_run, workspace)
from tests.sandbox import TmpRootTest, _dead_pid, artel_target_entry

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
DEVELOPER = "developer"
OTHER_ROLES = tuple(sorted({*config.STATE_ROLE.values(), "analyst"}
                           - {DEVELOPER}))
LAUNCH = re.compile(r"прогон №(\d+) .*?pid (\d+); лог: (\S+)")

EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [uv, run, --frozen, pytest]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: backend
"""


def readonly_db() -> sqlite3.Connection:
    """БД пульта только на чтение: запись отказывает `OperationalError`."""
    conn = sqlite3.connect(f"{Path(config.DB).resolve().as_uri()}?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def bare_full_run(text: str, task_id: str) -> list[str]:
    """Вхождения `suite-run <id>` (полный id либо `<id>`), за которыми не
    идёт ` --failed` или ` --wait`, — совет полного прогона без флагов."""
    found = []
    for name in (re.escape(task_id), re.escape("<id>")):
        for match in re.finditer(rf"suite-run {name}(?! --failed)(?! --wait)",
                                 text):
            found.append(text[max(0, match.start() - 40):match.end() + 40])
    return found


def pytest_output(failing: list[str], passing: list[str]) -> str:
    """Вывод `pytest -vv` сценария: строки хода, короткий итог, сводка."""
    lines = [f"tests/test_probe.py::{name} FAILED [ 50%]" for name in failing]
    lines += [f"tests/test_probe.py::{name} PASSED [100%]" for name in passing]
    if failing:
        lines.append("=========================== short test summary info "
                     "============================")
        lines += [f"FAILED tests/test_probe.py::{name} - AssertionError: "
                  f"{name}" for name in failing]
    counts = ", ".join(part for part in (
        f"{len(failing)} failed" if failing else "",
        f"{len(passing)} passed" if passing else "") if part)
    lines.append(f"==================== {counts} in 0.12s ====================")
    return "\n".join(lines) + "\n"


class DeveloperSuiteRunStand(TmpRootTest):
    """Задачи артели, хозяйство `suite-run` песочницы, подменённые запуск
    фонового процесса, прогон набора, открытие БД и досыл журнала."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.dead_pid = _dead_pid()

        store.create_schema(store.db())
        # Пульт держит БД открытой — файлы WAL на месте, соединение только
        # на чтение их и находит.
        self.conn = store.db()
        self.task = self.new_task()
        self.prefix = self.task[:self.rng.randint(4, len(self.task) - 1)]
        self.other = self.new_task()

        self.readonly = False
        self.child = "dead"
        self.launched = []
        self.suite_answer = (True, pytest_output([], ["test_ok"]))
        real_db, real_deliver = store.db, suite_lock.deliver_journal
        self.db_spy = mock.Mock(side_effect=lambda: (
            readonly_db() if self.readonly else real_db()))
        self.deliver_spy = mock.Mock(side_effect=real_deliver)
        real_popen = subprocess.Popen

        def popen(argv, *args, **kwargs):
            tokens = ([str(t) for t in argv]
                      if isinstance(argv, (list, tuple)) else [])
            if not tokens or tokens[0] != sys.executable:
                return real_popen(argv, *args, **kwargs)
            self.launched.append({"argv": tokens, "env": kwargs.get("env")})
            if self.child == "run":
                self.run_child(tokens, kwargs.get("env"))
                return mock.Mock(pid=self.dead_pid)
            if self.child == "alive":
                return mock.Mock(pid=os.getppid())
            return mock.Mock(pid=self.dead_pid)

        for target, attr, value in (
                (store, "db", self.db_spy),
                (suite_lock, "deliver_journal", self.deliver_spy),
                (subprocess, "Popen", popen),
                (acceptance, "run_full_suite",
                 lambda *a, **k: self.suite_answer),
                (appendix_tree, "suite_tree", lambda conn, task_id, wt, *a, **k:
                 contextlib.nullcontext(
                     appendix_tree.SuiteTree(Path(wt), "", "", "")))):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ задачи

    def new_task(self) -> str:
        while True:
            task_id = "01" + "".join(self.rng.choice(CROCKFORD)
                                     for _ in range(24))
            if not any(task_id[:4] == row["id"][:4]
                       for row in store.all_tasks(self.conn)):
                break
        store.insert_task(self.conn, task_id, "suite-run developer", "in_dev",
                          f"task/{task_id.lower()}-suite-run",
                          config.DEFAULT_TARGET, 25.0)
        workspace.path(task_id, config.DEFAULT_TARGET).mkdir(parents=True,
                                                             exist_ok=True)
        return task_id

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"

    def pult(self) -> str:
        return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'}"

    def name(self) -> str:
        return "test_" + "".join(self.rng.choice(LETTERS) for _ in range(6))

    # ------------------------------------------------------------ процессы

    def run_child(self, tokens: list, env) -> None:
        """Фоновый процесс команды — в процессе теста, тем же кодом."""
        saved = sys.argv
        environ = (mock.patch.dict(os.environ, env, clear=True)
                   if env is not None else contextlib.nullcontext())
        try:
            with environ:
                self.assertEqual(tokens[1], "-c", self.msg(
                    f"фоновый процесс неизвестной формы: {tokens}"))
                sys.argv = ["-c", *tokens[3:]]
                exec(compile(tokens[2], "<suite-run child>", "exec"),
                     {"__name__": "__main__"})
        finally:
            sys.argv = saved

    @contextlib.contextmanager
    def process(self, kind: str, readonly: bool = False):
        """Окружение вызывающего: `operator` — без маркера роли;
        `developer`/`role:<роль>` — маркер `ARTEL_ROLE`; `home` — HOME роли
        без маркера; `empty` — пустой маркер. `readonly` — `store.db` отдаёт
        соединение только на чтение."""
        with mock.patch.dict(os.environ):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            if kind == DEVELOPER or kind.startswith("role:"):
                os.environ[config.ARTEL_ROLE_ENV] = kind.removeprefix("role:")
                os.environ[config.ARTEL_TASK_ENV] = self.task
            elif kind == "home":
                os.environ["HOME"] = str(config.ROLE_HOME)
            elif kind == "empty":
                os.environ[config.ARTEL_ROLE_ENV] = ""
            saved, self.readonly = self.readonly, readonly
            try:
                yield
            finally:
                self.readonly = saved

    def call(self, args: list, kind: str = "operator",
             readonly: bool = False) -> tuple[str, object]:
        """`suite-run <args>`: (вывод вместе с текстом отказа, код выхода;
        `None` — команда вернулась)."""
        buf, code = io.StringIO(), None
        with self.process(kind, readonly), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                suite_run.cmd_suite_run(list(args))
            except SystemExit as exc:
                code = exc.code
        text = buf.getvalue()
        if isinstance(code, str):
            text += code
        return text, code

    def launch(self, child: str, task_id: str | None = None) -> tuple:
        """Полный прогон Оператора: (номер, pid, лог) из вывода запуска."""
        self.child = child
        out, code = self.call([task_id or self.task])
        self.assertIsNone(code, self.msg(f"прогон Оператора не запущен:\n{out}"))
        found = LAUNCH.search(out)
        self.assertIsNotNone(found, self.msg(out))
        return int(found.group(1)), int(found.group(2)), found.group(3)

    def red_run(self) -> list[str]:
        """Завершённый красный прогон Оператора: перечень упавших есть."""
        failing = [self.name() + f"_{i}" for i in range(self.rng.randint(1, 3))]
        self.suite_answer = (False, pytest_output(failing, [self.name()]))
        self.launch("run")
        return failing

    def green_run(self) -> None:
        """Завершённый зелёный прогон Оператора: упавших нет."""
        self.suite_answer = (True, pytest_output(
            [], [self.name() + f"_{i}" for i in range(self.rng.randint(1, 3))]))
        self.launch("run")

    def reset(self) -> None:
        shutil.rmtree(suite_lock.directory(), ignore_errors=True)
        self.launched.clear()

    def defer_record(self) -> None:
        """Отложенная запись журнала задачи — досыл её заберёт."""
        self.assertTrue(suite_lock.defer_journal({
            "task_id": self.task, "action": acceptance.SUITE_NEAR_LIMIT_ACTION,
            "detail": f"сигнал {self.seed}", "session_id": None,
            "at": store.now()}), self.msg("запись не отложена"))

    def near_records(self) -> list:
        return [row for row in store.task_steps(self.conn, self.task)
                if row["action"] == acceptance.SUITE_NEAR_LIMIT_ACTION]

    def snapshot(self) -> dict:
        """Байты файла БД (и WAL), всех файлов хозяйства `suite-run`
        (отложенный журнал, замок, логи, состояние прогонов)."""
        state = {}
        for path in (Path(config.DB), Path(f"{config.DB}-wal")):
            state[f"db:{path.name}"] = (path.read_bytes() if path.exists()
                                        else None)
        folder = suite_lock.directory()
        if folder.exists():
            for path in sorted(folder.rglob("*")):
                state[str(path.relative_to(folder))] = (
                    path.read_bytes() if path.is_file() else "<каталог>")
        return state

    def prior_state(self) -> str:
        """Случайное прошлое задачи без идущего прогона: прогонов не было,
        прогон оборван (фонового процесса нет), прогон завершён."""
        prior = self.rng.choice(("нет", "оборван", "завершён"))
        if prior == "оборван":
            self.launch("dead")
        elif prior == "завершён":
            self.red_run()
        self.launched.clear()
        return prior


class RefusalTest(DeveloperSuiteRunStand):

    def test_ac1_developer_full_run_refused_before_any_write(self):
        """Developer без флагов получает отказ, и ничего не тронуто — при обычной БД и при БД только на чтение.

        Сценарий (оба вида БД в случайном порядке, каждый на свежем
        хозяйстве `suite-run`): у задачи случайное прошлое без идущего
        прогона (не было, оборван, завершён) и отложенная запись журнала;
        процесс с `ARTEL_ROLE=developer` зовёт `suite-run <префикс id>`.
        Код выхода ненулевой; байты БД (и её WAL), всё хозяйство
        `suite-run` (отложенный журнал, замок, логи, `run.json`) до и после
        совпадают; подмены `Popen` интерпретатора, `store.db` и
        `suite_lock.deliver_journal` не вызваны; в тексте отказа — полный
        id; `sqlite3.connect` получил URI БД с `mode=ro` и `uri=True`.

        Ловит мутацию: отказ developer стоит после `deliver_journal` —
        счётчик досыла не ноль и отложенная запись ушла из каталога; отказ
        после замка или `_new_log` — в хозяйстве новый `lock.json` или лог;
        id разрешается через `store.db` (открытие на запись) — счётчик
        `store.db` не ноль; маркер не проверен — фоновый процесс запущен,
        код 0; отказ печатает префикс вместо полного id."""
        cases = [False, True]
        self.rng.shuffle(cases)
        for readonly in cases:
            with self.subTest(readonly=readonly, seed=self.seed):
                self.reset()
                prior = self.prior_state()
                self.defer_record()
                before = self.snapshot()
                self.db_spy.reset_mock()
                self.deliver_spy.reset_mock()
                with mock.patch.object(sqlite3, "connect",
                                       wraps=sqlite3.connect) as connect:
                    out, code = self.call([self.prefix], DEVELOPER, readonly)
                text = self.msg(f"БД только на чтение: {readonly}, прошлое: "
                                f"{prior}, префикс {self.prefix}\n{out}")
                self.assertNotIn(code, (None, 0), text)
                self.assertEqual(self.launched, [], text)
                self.assertEqual(self.db_spy.call_count, 0, text)
                self.assertEqual(self.deliver_spy.call_count, 0, text)
                self.assertEqual(self.snapshot(), before, text)
                self.assertIn(self.task, out, text)
                uris = [(c.args[0] if c.args else c.kwargs.get("database"),
                         c.kwargs.get("uri")) for c in connect.call_args_list]
                self.assertTrue(any("mode=ro" in str(uri) and flag is True
                                    for uri, flag in uris),
                                self.msg(f"{text}\nsqlite3.connect: {uris}"))

    def test_ac2_refusal_text_names_role_id_and_safe_hints(self):
        """Текст отказа developer называет команду, роль, полный id и безопасные пути.

        Сценарий: процесс с `ARTEL_ROLE=developer` (БД — случайно обычная
        или только на чтение) зовёт `suite-run <префикс id>` без флагов.
        Текст отказа содержит `suite-run`, `developer`, полный id, «CI»,
        автопроверку приёмки, `python3 -m pytest tests/` и «переднем плане»,
        `plank-run <полный id>`, `suite-run <полный id> --failed`; в нём нет
        `suite-run <полный id>` (или `<id>`) без ` --failed`/` --wait` —
        ни совета полного прогона, ни формы `suite-run <id> <файлы>`.

        Ловит мутацию: отказ оставил прежнюю подсказку «полный прогон:
        `suite-run <id>`» либо советует `suite-run <id> <файлы>` —
        вхождение без флага; подсказка `plank-run`/`--failed` названа с
        префиксом вместо полного id; роль или CI в тексте не названы."""
        readonly = self.rng.choice((False, True))
        out, code = self.call([self.prefix], DEVELOPER, readonly)
        text = self.msg(f"БД только на чтение: {readonly}\n{out}")
        self.assertNotIn(code, (None, 0), text)
        for part in ("suite-run", DEVELOPER, self.task, "CI",
                     "python3 -m pytest tests/", "переднем плане",
                     f"plank-run {self.task}",
                     f"suite-run {self.task} --failed"):
            with self.subTest(part=part):
                self.assertIn(part, out, text)
        self.assertRegex(out, r"автопроверк\w*\s+приёмки", text)
        self.assertEqual(bare_full_run(out, self.task), [], text)


class RunningTest(DeveloperSuiteRunStand):

    def test_ac3_running_run_answered_without_new_records(self):
        """Идущий прогон задачи developer видит прежним ответом «уже идёт», код 0, без новых записей.

        Сценарий: Оператор запустил полный прогон, фоновый процесс жив
        (pid живого процесса) и держит замок; процесс с
        `ARTEL_ROLE=developer` зовёт `suite-run <id>` без флагов. Вывод —
        «уже идёт … второй не запускаю» с номером прогона, pid и логом
        запуска Оператора; кода выхода нет (0); хозяйство `suite-run` (лог,
        `run.json`, замок) до и после совпадает, фоновый процесс не
        запускался.

        Ловит мутацию: отказ developer стоит до проверки идущего прогона —
        ненулевой код вместо ответа «уже идёт»; ответ для developer
        перезаписывает `run.json` или берёт замок заново — снимок
        хозяйства меняется; при идущем прогоне developer запускает второй
        — фоновый процесс в перечне запусков."""
        run_no, pid, log = self.launch("alive")
        self.assertEqual(pid, os.getppid(), self.msg())
        self.launched.clear()
        before = self.snapshot()
        out, code = self.call([self.rng.choice((self.task, self.prefix))],
                              DEVELOPER, self.rng.choice((False, True)))
        text = self.msg(out)
        self.assertIn(code, (None, 0), text)
        for part in ("уже идёт", "второй не запускаю", f"№{run_no}",
                     f"pid {pid}", log):
            with self.subTest(part=part):
                self.assertIn(part, out, text)
        self.assertEqual(self.launched, [], text)
        self.assertEqual(self.snapshot(), before, text)


class KeptFlagsTest(DeveloperSuiteRunStand):

    def test_ac4_developer_wait_and_failed_under_readonly_db(self):
        """Developer под БД только на чтение: `--wait 0` читает отчёт как Оператор, `--failed` берёт общий замок.

        Сценарий: Оператор провёл красный полный прогон (перечень упавших
        есть). (1) `suite-run <id> --wait 0` developer под БД только на
        чтение печатает тот же отчёт и тот же код, что тот же вызов
        Оператора, досыл журнала вызван. (2) Замок полных прогонов держит
        гейт другой задачи: `--failed` developer отказывает, называя
        задачу гейта, фоновый процесс не запускался. (3) Замок свободен:
        `--failed` developer запускает фоновый повтор упавших (режим
        `suite_run.MODE_FAILED`), замок `suite_lock.path()` — тот, что берёт
        гейт, — за этой задачей и pid фонового процесса, гейт его взять не
        может; досыл журнала вызван. (4) У задачи без прогонов прежние
        отказы `--wait 0` и `--failed` у developer — ненулевой код без
        запуска.

        Ловит мутацию: отказ developer распространён на `--wait` или
        `--failed` — ненулевой код или отчёт не тот; `--failed` developer
        берёт отдельный файл замка или идёт без замка — гейт берёт замок,
        отказа при замке гейта нет; досыл журнала у `--wait`/`--failed`
        developer пропущен — счётчик досыла ноль; прежний отказ «прогона
        нет» снят — фоновый процесс запущен."""
        self.red_run()
        self.launched.clear()

        op_out, op_code = self.call([self.task, "--wait", "0"])
        self.deliver_spy.reset_mock()
        dev_out, dev_code = self.call([self.prefix, "--wait", "0"],
                                      DEVELOPER, readonly=True)
        text = self.msg(f"Оператор:\n{op_out}\ndeveloper:\n{dev_out}")
        self.assertIn("красный прогон", op_out, text)
        self.assertEqual((dev_out, dev_code), (op_out, op_code), text)
        self.assertGreaterEqual(self.deliver_spy.call_count, 1, text)

        gate_task = self.other
        self.assertIsNone(suite_lock.acquire(gate_task,
                                             kind=suite_lock.KIND_GATE),
                          self.msg("замок гейта не взят"))
        try:
            out, code = self.call([self.task, "--failed"], DEVELOPER,
                                  readonly=True)
        finally:
            suite_lock.release()
        text = self.msg(out)
        self.assertNotIn(code, (None, 0), text)
        self.assertIn(gate_task, out, text)
        self.assertEqual(self.launched, [], text)

        self.child = "alive"
        self.deliver_spy.reset_mock()
        out, code = self.call([self.prefix, "--failed"], DEVELOPER,
                              readonly=True)
        text = self.msg(out)
        self.assertIsNone(code, text)
        self.assertEqual(len(self.launched), 1, text)
        self.assertIn(suite_run.MODE_FAILED, self.launched[0]["argv"], text)
        self.assertIn(self.task, self.launched[0]["argv"], text)
        holder = suite_lock.holder() or {}
        self.assertEqual((holder.get("task_id"), holder.get("pid")),
                         (self.task, os.getppid()), self.msg(f"{holder}\n{out}"))
        gate = suite_lock.acquire(gate_task, kind=suite_lock.KIND_GATE)
        self.assertIsNotNone(gate, self.msg("гейт взял замок при повторе "
                                            f"developer\n{out}"))
        self.assertEqual(gate.get("task_id"), self.task, self.msg(f"{gate}"))
        self.assertGreaterEqual(self.deliver_spy.call_count, 1, text)

        self.launched.clear()
        for args in (["--wait", "0"], ["--failed"]):
            with self.subTest(args=args):
                out, code = self.call([self.other, *args], DEVELOPER,
                                      readonly=True)
                text = self.msg(out)
                self.assertNotIn(code, (None, 0), text)
                self.assertEqual(self.launched, [], text)


class HintsTest(DeveloperSuiteRunStand):

    def expected_operator(self, kind: str, run_no=None, pid=None,
                          log=None) -> str:
        head = f"[{self.task}] suite-run"
        cmd = f"{self.pult()} suite-run {self.task}"
        return {
            "wait-none": (f"{head}: отказ — у задачи {self.task} нет ни "
                          f"одного прогона suite-run, ждать нечего; запусти "
                          f"прогон: {cmd}"),
            "wait-aborted": (f"{head}: прогон №{run_no} оборван — фонового "
                             f"процесса (pid {pid}) больше нет, отчёта он не "
                             f"оставил; лог: {log}; новый прогон: {cmd}"),
            "failed-none": (f"{head}: отказ — прошлого прогона suite-run у "
                            f"задачи нет, повторять нечего; сначала полный "
                            f"прогон: {cmd}"),
            "failed-empty": (f"{head}: отказ — в прошлом прогоне упавших "
                             f"нет, повторять нечего; полный прогон: {cmd}"),
        }[kind]

    def test_ac5_developer_hints_skip_bare_full_run_operator_texts_kept(self):
        """Подсказки developer не советуют `suite-run <id>` без флагов; у Оператора тексты прежние.

        Сценарий (БД developer — случайно обычная или только на чтение):
        у задачи нет прогонов — `--wait 0` и `--failed`; прогон оборван
        (фонового процесса нет, отчёта нет) — `--wait 0`; прошлый прогон
        зелёный (упавших нет) — `--failed`; и отказ полного прогона
        developer. Каждый текст developer ненулевой и без `suite-run <id>`
        без ` --failed`/` --wait`; отказ `--failed` «прошлого прогона нет»
        называет запуск упавших тестов CI или гейта по именам. Те же
        вызовы процесса без маркера дают дословно прежние тексты.

        Ловит мутацию: одна из четырёх подсказок осталась «полный прогон:
        `suite-run <id>`» под маркером developer — вхождение без флага;
        развилка по маркеру не проверена и подсказки сменились у всех —
        текст Оператора не прежний; `--failed` «прошлого прогона нет» не
        называет запуск по именам."""
        readonly = self.rng.choice((False, True))
        seen = {}

        def both(kind: str, args: list, **expected) -> None:
            dev, dev_code = self.call([self.task, *args], DEVELOPER, readonly)
            op, op_code = self.call([self.task, *args])
            seen[kind] = dev
            text = self.msg(f"{kind}, БД только на чтение: {readonly}\n"
                            f"developer:\n{dev}\nОператор:\n{op}")
            self.assertNotIn(dev_code, (None, 0), text)
            self.assertEqual(self.launched, [], text)
            self.assertEqual(bare_full_run(dev, self.task), [], text)
            self.assertEqual(op_code, self.expected_operator(kind, **expected),
                             text)

        with self.subTest(case="прогонов нет", seed=self.seed):
            both("wait-none", ["--wait", "0"])
            both("failed-none", ["--failed"])
            text = self.msg(seen.get("failed-none", ""))
            self.assertIn("по именам", seen.get("failed-none", ""), text)
            self.assertRegex(seen.get("failed-none", ""), r"CI|гейт", text)
        with self.subTest(case="оборван", seed=self.seed):
            self.reset()
            run_no, pid, log = self.launch("dead")
            self.launched.clear()
            both("wait-aborted", ["--wait", "0"], run_no=run_no, pid=pid,
                 log=log)
        with self.subTest(case="упавших нет", seed=self.seed):
            self.reset()
            self.green_run()
            self.launched.clear()
            both("failed-empty", ["--failed"])
        with self.subTest(case="отказ полного прогона", seed=self.seed):
            self.reset()
            dev, code = self.call([self.task], DEVELOPER, readonly)
            text = self.msg(dev)
            self.assertNotIn(code, (None, 0), text)
            self.assertEqual(bare_full_run(dev, self.task), [], text)


class OtherCallersTest(DeveloperSuiteRunStand):

    def test_ac6_other_callers_start_full_run_as_before(self):
        """Оператор, другая роль, HOME роли без маркера и пустой маркер запускают полный прогон как прежде.

        Сценарий (в случайном порядке, каждый на свежем хозяйстве
        `suite-run` с отложенной записью журнала): процесс без
        `ARTEL_ROLE`; с маркером случайной роли конвейера, кроме developer;
        с HOME дома роли без маркера; с пустым `ARTEL_ROLE` — зовёт
        `suite-run <id>` без флагов. Команда возвращается без кода; один
        фоновый процесс интерпретатора пульта с id задачи, без `ARTEL_ROLE`
        в его окружении; замок `suite_lock` — за задачей и pid фонового
        процесса; лог из вывода и `run.json` задачи есть; отложенная
        запись журнала дослана в журнал задачи.

        Ловит мутацию: отказ сработал на любой роли (маркер сравнивается с
        «не пусто», а не с `developer`) либо на HOME роли
        (`runner.in_role_environment`) — ненулевой код, фонового процесса
        нет; снятие маркера в окружении фона потеряно — `ARTEL_ROLE` в
        окружении запуска; досыл журнала перенесён за отказ и пропал у
        прочих — записи в журнале нет."""
        kinds = ["operator", f"role:{self.rng.choice(OTHER_ROLES)}", "home",
                 "empty"]
        self.rng.shuffle(kinds)
        self.child = "dead"
        for kind in kinds:
            with self.subTest(kind=kind, seed=self.seed):
                self.reset()
                self.defer_record()
                before = len(self.near_records())
                out, code = self.call([self.task], kind)
                text = self.msg(f"{kind}\n{out}")
                self.assertIsNone(code, text)
                self.assertEqual(len(self.launched), 1, text)
                launched = self.launched[0]
                self.assertIn(self.task, launched["argv"], text)
                self.assertIsNotNone(launched["env"], text)
                self.assertNotIn(config.ARTEL_ROLE_ENV, launched["env"], text)
                holder = suite_lock.holder() or {}
                self.assertEqual((holder.get("task_id"), holder.get("pid")),
                                 (self.task, self.dead_pid),
                                 self.msg(f"{kind}: {holder}\n{out}"))
                found = LAUNCH.search(out)
                self.assertIsNotNone(found, text)
                self.assertTrue(Path(found.group(3)).is_file(), text)
                self.assertTrue(
                    (suite_lock.directory() / self.task / "run.json").is_file(),
                    text)
                self.assertEqual(len(self.near_records()), before + 1, text)


class MissionTest(DeveloperSuiteRunStand):

    def components_empty(self):
        stack = contextlib.ExitStack()
        for target, attr, value in (
                (brief, "developer_brief", ""),
                (brief, "step_notes_block", ""),
                (review, "review_package", ""),
                (review, "previous_verdict_sha", "")):
            stack.enter_context(mock.patch.object(target, attr,
                                                  return_value=value))
        return stack

    def test_ac7_developer_mission_names_failed_wait_and_ci_gate(self):
        """Миссия developer не предлагает полный прогон, называет CI и гейт приёмки, `--failed` и `--wait`.

        Сценарий: миссия developer собрана штатно
        (`role_prompt.mission_brief_package`, компоненты брифа пустые) для
        нескольких случайных id. В ней нет `suite-run <id>` без
        ` --failed`/` --wait`; есть «CI» и гейт приёмки;
        `python3 <config.ROOT>/orchestrator/artel.py suite-run <id> --failed`
        и `… suite-run <id> --wait <минуты`; сказано, что `--failed`
        работает только после прогона Оператора или ревьювера.

        Ловит мутацию: миссия по-прежнему открывается «Полный набор тестов
        — только командой `suite-run <id>`» — вхождение без флага; команды
        названы без полного пути пульта; условие «только после прогона
        Оператора или ревьювера» не сказано."""
        pult = config.ROOT / "orchestrator" / "artel.py"
        with self.components_empty():
            for _ in range(3):
                task_id = "01" + "".join(self.rng.choice(CROCKFORD)
                                         for _ in range(24))
                t = {"branch": f"task/{task_id.lower()}-x", "title": "x",
                     "reviewed_iter": 0}
                docs = config.PROJECTS / "artel" / "tasks" / task_id
                mission, _b, _p = role_prompt.mission_brief_package(
                    None, task_id, t, DEVELOPER, "/tmp/cwd", docs_dir=docs)
                text = self.msg(mission)
                self.assertEqual(bare_full_run(mission, task_id), [], text)
                self.assertIn("CI", mission, text)
                self.assertRegex(mission, r"гейт\w*\s+приёмки", text)
                self.assertIn(f"python3 {pult} suite-run {task_id} --failed",
                              mission, text)
                self.assertIn(f"python3 {pult} suite-run {task_id} --wait <минут",
                              mission, text)
                self.assertRegex(
                    mission,
                    r"только после[^\n]{0,80}(Оператор[^\n]{0,40}ревьювер|"
                    r"ревьювер[^\n]{0,40}Оператор)", text)

    def test_ac7_external_reviewer_mission_keeps_suite_run(self):
        """Миссия ревьювера задачи внешнего проекта несёт правило о полном наборе, `plank-run` и `guard`, но не `suite-run <id>`.

        Сценарий: в `targets.yaml` песочницы — артель и учебный внешний
        проект; задача этого проекта в состоянии ревью; миссия ревьювера
        собрана `role_prompt.mission_brief_package` (компоненты брифа и
        ревью-пакет пустые). Она содержит
        `role_prompt.REVIEWER_FULL_SUITE_RULE`,
        «`python3 <config.ROOT>/orchestrator/artel.py plank-run <id>» и
        «`python3 <config.ROOT>/orchestrator/artel.py guard <id>», и в ней
        нет `suite-run <id>` без ` --failed`/` --wait` (решение Оператора
        23.10, CR-2026-10-22-2, вариант А).

        Ловит мутацию: перечень команд ревьювера внешнего проекта снова
        называет `suite-run <id>` — полный набор тестов; правило
        `REVIEWER_FULL_SUITE_RULE` пропало из миссии; `plank-run` или
        `guard` пропали из перечня либо названы без полного пути пульта."""
        ext = "sled" + "".join(self.rng.choice(LETTERS) for _ in range(6))
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + EXTERNAL_ENTRY.format(
                name=ext, base=config.MAIN_BRANCH), encoding="utf-8")
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, task_id, "Учебная задача", "review",
                          f"task/{task_id.lower()}-x", ext, 25.0)
        t = store.get_task(self.conn, task_id)
        with self.components_empty():
            mission, _b, _p = role_prompt.mission_brief_package(
                self.conn, task_id, t, "reviewer", "/tmp/cwd",
                config.PROJECTS / ext / "tasks" / task_id)
        text = self.msg(mission)
        self.assertIn(role_prompt.REVIEWER_FULL_SUITE_RULE, mission, text)
        self.assertIn(f"`{self.pult()} plank-run {task_id}", mission, text)
        self.assertIn(f"`{self.pult()} guard {task_id}", mission, text)
        self.assertEqual(bare_full_run(mission, task_id), [], text)


if __name__ == "__main__":
    unittest.main()
