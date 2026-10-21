"""Сводка прогона Vitest в журнале шага: разбор блока, насос с `on_vitest_summary`, выбор насоса по профилю проекта задачи, прежний «прогон pytest».

Группа: долгоживущий
Красен до реализации: в `orchestrator/agent_log.py` нет `VITEST_RUN_ACTION`, у `OutputPump` нет параметра `on_vitest_summary`, `runner._spawn_and_wait` его не передаёт — записей «прогон vitest» в журнале шага нет; методы прежнего поведения (AC-5 для артели, pytest-компонента и неопределённого профиля, AC-6) держат поведение пина и зелены с рождения.

Связка «шаг роли — профиль проекта — насос — журнал»: штатный шаг
`runner.run_agent_once` с подставным агентом (`runner.spawn_agent` →
`tests.sandbox.FakeProc`), чей вывод несёт результаты инструмента
(`tool_result` потока Claude) с выводом прогона, на настоящем git
(`tests.sandbox.RealGitSandbox`). Записи читаются из журнала задачи
(`store.task_steps`); конструктор насоса `agent_log.OutputPump` обёрнут
шпионом, пропускающим вызов в настоящий класс, — так видно, с каким
получателем сводки Vitest шаг его создал. Числа фикстур — из `random`,
зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
разбор блока по требованию 2, `VITEST_RUN_ACTION`, параметр насоса и его
передача в `_spawn_and_wait` по `decide(target).profile.report` — все
методы файла зелёные.
"""
import inspect
import io
import json
import random
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import (agent_log, catalog, config, keychain,
                          project_profile, runner, stack, store, workspace)
from tests.sandbox import (FakeProc, RealGitSandbox, TmpRootTest,
                           artel_target_entry, capture, make_project_repo)

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
VITEST_ACTION = "прогон vitest"
PYTEST_ACTION = "прогон pytest"
RESULT_LINE = '{"type": "result", "total_cost_usd": 0.001}\n'
ROLE = "test_author"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def tool_result_line(text: str, n: int = 1) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": f"toolu_{n}", "content": text,
         "is_error": False}]}}, ensure_ascii=False) + "\n"


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def component_entry(name: str, fields: dict) -> str:
    text = ENTRY_HEAD.format(name=name, base=config.MAIN_BRANCH)
    text += f"    components:\n      c{name}:\n"
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            value = flow(value)
        text += f"        {key}: {value}\n"
    return text


def vitest_entry(name: str) -> str:
    return component_entry(name, {
        "command": list(project_profile.VITEST_BASE_ARGV),
        "report": project_profile.REPORT_VITEST,
        "long_lived_dir": "web/src",
        "long_lived_name": "<id>_<name>.test.js",
        "weakening_scope": ["web/src/**"],
        "mutation_claim_scope": ["web/src/**"],
        "tests": ["web/src/**/*.test.js"]})


def pytest_entry(name: str) -> str:
    return component_entry(name, {
        "command": ["python3", "-m", "pytest"],
        "report": project_profile.REPORT_JUNIT,
        "long_lived_dir": "backend/tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": ["backend/tests/**"],
        "mutation_claim_scope": ["backend/tests/**"],
        "tests": ["backend/tests/test_*.py"]})


class VitestBlocks:
    """Фикстуры вывода Vitest: (текст, ожидаемая деталь либо `None`)."""

    def ms(self) -> int:
        """Миллисекунды без «половинки» в третьем знаке секунд."""
        while True:
            value = self.rng.randrange(11, 999)
            if value % 10 != 5:
                return value

    def seconds_text(self) -> tuple:
        """(текст `<число>s`, ожидаемые секунды с двумя знаками)."""
        whole = self.rng.randrange(1, 40)
        form = self.rng.choice(("int", "one", "two"))
        if form == "int":
            return f"{whole}s", f"{whole}.00"
        if form == "one":
            tenth = self.rng.randrange(1, 10)
            return f"{whole}.{tenth}s", f"{whole}.{tenth}0"
        hundredth = self.rng.randrange(10, 100)
        return f"{whole}.{hundredth}s", f"{whole}.{hundredth}"

    def counts(self, kinds) -> tuple:
        """(текст счётчиков через « | », сумма)."""
        values = {kind: self.rng.randrange(1, 9) for kind in kinds}
        return (" | ".join(f"{v} {k}" for k, v in values.items()),
                sum(values.values()))

    @staticmethod
    def block(files: str, tests: str, duration: str, between=()) -> str:
        lines = ["", f" Test Files  {files}", f"      Tests  {tests}",
                 *(f"   {line}" for line in between),
                 f"   Duration  {duration}", ""]
        return "\n".join(lines)

    def fixtures(self) -> list:
        """Все фикстуры AC-3 по порядку: (имя, текст, деталь либо `None`)."""
        found = []
        # Успешный прогон, Duration в ms.
        n = self.rng.randrange(1, 30)
        ms = self.ms()
        found.append(("успех, ms", self.block(
            f"{self.rng.randrange(1, 5)} passed (4)", f"{n} passed ({n})",
            f"{ms}ms"), f"{n} passed ({n}) in {ms / 1000:.2f}s"))
        # Прогон с падениями, Duration в s.
        text, total = self.counts(("failed", "passed"))
        dur, sec = self.seconds_text()
        found.append(("падения, s", self.block(
            "1 failed | 1 passed (2)", f"{text} ({total})", dur),
            f"{text} ({total}) in {sec}s"))
        # todo/skipped.
        text, total = self.counts(self.rng.sample(
            ("skipped", "todo", "passed"), 3))
        ms = self.ms()
        found.append(("todo/skipped", self.block(
            "1 passed | 1 skipped (2)", f"{text} ({total})", f"{ms}ms"),
            f"{text} ({total}) in {ms / 1000:.2f}s"))
        # no tests.
        ms = self.ms()
        found.append(("no tests", self.block(
            "no tests (0)", "no tests (0)", f"{ms}ms"),
            f"no tests (0) in {ms / 1000:.2f}s"))
        # ANSI.
        n = self.rng.randrange(1, 30)
        ms = self.ms()
        ansi = ("\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[32m1 passed\x1b[39m"
                "\x1b[22m\x1b[90m (1)\x1b[39m\n"
                f"\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m{n} passed\x1b[39m"
                f"\x1b[22m\x1b[90m ({n})\x1b[39m\n"
                f"\x1b[2m   Duration \x1b[22m {ms}ms\x1b[2m (transform 12ms, "
                f"setup 0ms)\x1b[22m\n")
        found.append(("ANSI", ansi, f"{n} passed ({n}) in {ms / 1000:.2f}s"))
        # Хвост Duration и Start at между Tests и Duration.
        text, total = self.counts(("failed", "passed"))
        dur, sec = self.seconds_text()
        found.append(("хвост и Start at", self.block(
            "2 passed (2)", f"{text} ({total})",
            f"{dur} (transform 45ms, setup 0ms, collect 30ms, tests 5ms, "
            f"environment 0ms, prepare 80ms)",
            between=(f"Start at  {self.rng.randrange(10, 24)}:"
                     f"{self.rng.randrange(10, 60)}:"
                     f"{self.rng.randrange(10, 60)}",)),
            f"{text} ({total}) in {sec}s"))
        # Нет Duration в пределах четырёх строк после Tests.
        found.append(("Duration за пределом", self.block(
            "1 passed (1)", "3 passed (3)", f"{self.ms()}ms",
            between=("Start at  12:00:00", "stdout | a.test.js", "привет",
                     "stdout | b.test.js")), None))
        # «Tests» внутри листинга кода, без Test Files перед ней.
        found.append(("листинг", "\n".join((
            "const total = 3;", "      Tests  3 passed (3)",
            f"   Duration  {self.ms()}ms", "")), None))
        return found


# ---------------------------------------------------------------- шаг роли

class StepSandbox(VitestBlocks, RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        stack_ok = [stack.StackCheck(name, "ok", "песочница")
                    for name in ("python", "git", "gh", "claude", "venv")]
        self.pumps: list = []
        real_pump = agent_log.OutputPump

        def spy_pump(*args, **kwargs):
            bound = inspect.signature(real_pump).bind(*args, **kwargs)
            self.pumps.append(dict(bound.arguments))
            return real_pump(*args, **kwargs)

        for patcher in (
                mock.patch.object(stack, "check_stack", lambda: list(stack_ok)),
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: []),
                mock.patch.object(agent_log, "OutputPump", spy_pump)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.names = {"vitest": f"v{self.word()}", "pytest": f"p{self.word()}",
                      "none": f"n{self.word()}"}
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + vitest_entry(self.names["vitest"])
            + pytest_entry(self.names["pytest"])
            + ENTRY_HEAD.format(name=self.names["none"], base=config.MAIN_BRANCH),
            encoding="utf-8")
        for name in self.names.values():
            make_project_repo(name)
        capture(catalog.cmd_init)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def target(self, kind: str) -> str:
        return ARTEL if kind == "artel" else self.names[kind]

    def step(self, target: str, outputs) -> str:
        """Шаг test_author задачи проекта `target`, агент которого выдаёт
        результаты инструмента `outputs`; возврат — id задачи."""
        task_id = ulid(self.rng)
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        lines = [tool_result_line(text, n) for n, text in enumerate(outputs, 1)]
        self.pumps.clear()
        with mock.patch.object(runner, "spawn_agent",
                               return_value=FakeProc(lines + [RESULT_LINE], 0)), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            runner.run_agent_once(self.conn, task_id, ROLE, "промпт шага", 1)
        return task_id

    def details(self, task_id: str, action: str) -> list:
        return [row["detail"] for row in store.task_steps(store.db(), task_id)
                if row["action"] == action]

    def vitest_receiver(self):
        self.assertTrue(self.pumps, self.note("насос шага не создан"))
        return self.pumps[-1].get("on_vitest_summary")


class Ac3Ac4VitestJournalTest(StepSandbox):

    def test_ac3_block_fixtures_give_detail(self):
        """Шаг задачи `pult-vitest` пишет «прогон vitest» с деталью «<сч Tests> (<n>) in <секунды>s» на каждую фикстуру-сводку и ни одной на не-сводки.

        Сценарий: агент выдаёт по результату инструмента на фикстуру —
        успех (`ms`), падения (`s`), `todo`/`skipped`, `no tests`, вывод с
        ANSI, блок с хвостом `(transform …)` у `Duration` и строкой
        `Start at` между `Tests` и `Duration`; ещё два результата — блок,
        где `Duration` пятая строка после `Tests`, и «Tests» в листинге кода
        без `Test Files` перед ней. Детали записей «прогон vitest» в
        журнале — ровно список ожидаемых деталей сводок по порядку: секунды
        всегда с двумя знаками (`523ms` → `0.52s`, `1.5s` → `1.50s`).

        Ловит мутацию: `ms` не переводятся в секунды («523.00s») или
        секунды без двух знаков («1.5s»); ANSI не снимаются — цветной блок
        не узнан; хвост `Duration` или строка `Start at` ломают разбор;
        окно `Duration` шире четырёх строк — пятая строка даёт запись;
        `Test Files` не требуется перед `Tests` — листинг даёт запись;
        деталь несёт счётчики `Test Files` вместо `Tests`.
        """
        fixtures = self.fixtures()
        task_id = self.step(self.target("vitest"), [f[1] for f in fixtures])
        expected = [f[2] for f in fixtures if f[2] is not None]
        got = self.details(task_id, VITEST_ACTION)
        self.assertEqual(got, expected, self.note(
            "фикстуры:\n" + "\n---\n".join(f"{f[0]}:\n{f[1]!r}"
                                           for f in fixtures)))

    def test_ac4_pump_callback_and_journal_record(self):
        """Насос с переданным `on_vitest_summary` зовёт его на блоке Vitest; шаг задачи `pult-vitest` пишет запись `VITEST_RUN_ACTION == "прогон vitest"` с деталью разбора.

        Сценарий: `agent_log.VITEST_RUN_ACTION` равно «прогон vitest»;
        насос `agent_log.OutputPump` с получателем-списком на потоке из
        одного результата инструмента с блоком Vitest зовёт получателя
        ровно один раз; шаг задачи `pult-vitest` с тем же блоком в выводе
        оставляет в журнале задачи запись «прогон vitest» с деталью
        «<сч Tests> (<n>) in <секунды>s», автор записи — роль шага.

        Ловит мутацию: насос разбирает блок, но получателя не зовёт; шаг
        передаёт насосу получатель, не пишущий журнал, или пишет запись
        действием «прогон pytest»; деталь без «(<n>)».
        """
        self.assertEqual(agent_log.VITEST_RUN_ACTION, VITEST_ACTION)
        name, text, detail = self.fixtures()[0]
        seen = []
        log = agent_log.new_agent_log("T001", ROLE)
        pump = agent_log.OutputPump(iter([tool_result_line(text)]), log,
                                    on_vitest_summary=seen.append)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            pump.start()
            pump.join(10)
        self.assertEqual(len(seen), 1, self.note(f"{name}: вызовы {seen}"))
        task_id = self.step(self.target("vitest"), [text])
        rows = [(row["actor"], row["detail"])
                for row in store.task_steps(store.db(), task_id)
                if row["action"] == VITEST_ACTION]
        self.assertEqual(rows, [(ROLE, detail)], self.note(text))


class Ac5PumpChoiceTest(StepSandbox):

    def test_ac5_no_vitest_receiver_without_vitest_report(self):
        """У артели, pytest-компонента и задачи без профиля насос без `on_vitest_summary` и записей «прогон vitest» нет; у `pult-vitest` получатель передан.

        Сценарий: шаг test_author задачи каждого вида проекта — артели,
        компонента `junit-xml` на pytest, записи без профиля тестов
        (`decide(target).profile is None`) — с блоком Vitest в выводе
        инструмента: шаг проходит без исключения, насос создан без
        получателя сводки Vitest (параметра нет или `None`), записей
        «прогон vitest» в журнале задачи нет. Шаг задачи `pult-vitest` —
        насос создан с вызываемым `on_vitest_summary`.

        Ловит мутацию: получатель передаётся всем задачам — у артели
        появляется «прогон vitest»; признак по `report` компонента берётся
        без проверки `profile is None` — шаг задачи без профиля падает
        AttributeError; признак — «не pytest» вместо `== pult-vitest` —
        задача без профиля получает получатель; у `pult-vitest` получатель
        не передан.
        """
        name, text, _detail = self.fixtures()[0]
        self.assertIsNone(project_profile.decide(self.names["none"]).profile,
                          self.note("фикстура: у записи без профиля есть профиль"))
        for kind in ("artel", "pytest", "none"):
            with self.subTest(kind=kind, seed=self.seed):
                task_id = self.step(self.target(kind), [text])
                self.assertIsNone(self.vitest_receiver(), self.note(kind))
                self.assertEqual(self.details(task_id, VITEST_ACTION), [],
                                 self.note(f"{kind}: {name}"))
        with self.subTest(kind="vitest", seed=self.seed):
            self.step(self.target("vitest"), [text])
            self.assertTrue(callable(self.vitest_receiver()),
                            self.note("у pult-vitest нет получателя"))


# ---------------------------------------------------------------- AC-6

PYTEST_FIXTURES = (
    ("== 1 failed, 2 passed, 3 warnings in 12.30s (0:00:12) ==\n",
     ["1 failed, 2 passed, 3 warnings in 12.30s (0:00:12)"]),
    ("\x1b[32m5 passed\x1b[0m\x1b[32m in 0.10s\x1b[0m\n", ["5 passed in 0.10s"]),
    ("182 passed, 99 subtests passed in 62.97s (0:01:02)\n",
     ["182 passed, 99 subtests passed in 62.97s (0:01:02)"]),
    ("============ no tests ran in 0.01s ============\n",
     ["no tests ran in 0.01s"]),
    ("passed in review\n3 passed\n", []),
)


class Ac6PytestUnchangedTest(TmpRootTest):

    def test_ac6_pytest_action_and_parse_unchanged(self):
        """`PYTEST_RUN_ACTION` — «прогон pytest», разбор pytest на прежних выводах даёт прежние детали побайтно.

        Сценарий: константа равна прежнему значению; `pytest_summaries` на
        каждой фикстуре прежнего вывода pytest (рамка «=», ANSI,
        подтесты, «no tests ran», слова без числа и длительности) даёт
        прежний список деталей; насос с `on_pytest_summary` на тех же
        выводах передаёт получателю те же детали.

        Ловит мутацию: общий разбор Vitest и pytest переписан и меняет
        деталь pytest (снимает хвост «(0:00:12)», не снимает рамку);
        константа переименована в «прогон тестов».
        """
        self.assertEqual(agent_log.PYTEST_RUN_ACTION, PYTEST_ACTION)
        for text, expected in PYTEST_FIXTURES:
            with self.subTest(text=text):
                self.assertEqual(agent_log.pytest_summaries(text), expected)
                seen = []
                log = agent_log.new_agent_log("T001", ROLE)
                pump = agent_log.OutputPump(iter([tool_result_line(text)]), log,
                                            on_pytest_summary=seen.append)
                with redirect_stdout(io.StringIO()), \
                        redirect_stderr(io.StringIO()):
                    pump.start()
                    pump.join(10)
                self.assertEqual(seen, expected)


class Ac6PytestJournalTest(StepSandbox):

    def test_ac6_pytest_journal_records_unchanged(self):
        """Шаг артели с прежним выводом pytest пишет «прогон pytest» с прежними деталями побайтно.

        Сценарий: агент артели выдаёт результаты инструмента с прежними
        выводами pytest (и одним блоком Vitest между ними); детали записей
        «прогон pytest» в журнале — ровно прежний список по порядку, блок
        Vitest записей «прогон pytest» не добавляет.

        Ловит мутацию: шаг пишет сводку pytest новым действием или с
        иначе собранной деталью; блок Vitest распознан как итог pytest.
        """
        outputs = [text for text, _expected in PYTEST_FIXTURES]
        outputs.insert(2, self.fixtures()[0][1])
        task_id = self.step(ARTEL, outputs)
        expected = [d for _text, found in PYTEST_FIXTURES for d in found]
        self.assertEqual(self.details(task_id, PYTEST_ACTION), expected,
                         self.note(""))


if __name__ == "__main__":
    unittest.main()
