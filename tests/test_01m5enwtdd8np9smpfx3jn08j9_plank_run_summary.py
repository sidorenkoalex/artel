"""Итоговые строки `plank-run`: «итог vitest» у компонента `pult-vitest`, прежние «итог pytest» у артели, pytest-компонента и задачи с неопределённым профилем.

Группа: долгоживущий
Красен до реализации: `plank-run` у любой задачи пишет «итог pytest: …» по итоговой строке pytest — у компонента `pult-vitest` нет «итог vitest: <деталь>; код выхода vitest: …» и строки оборванного прогона «итог vitest: …»; строки артели, pytest-компонента и неопределённого профиля держат поведение пина и зелены с рождения.

Команда — публичный `plank_run.cmd_plank_run` задачи в `tests_writing`
с черновиком планки в каталоге документов (`config.PROJECTS/<проект>`) и
каталогом рабочей копии кода (`workspace.path`). Выкладка
(`acceptance.plank_in_code_copy`) подменена каталогом без записи файлов,
прогон (`acceptance.run_plank`) — заготовленным ответом (код выхода,
вывод): предмет — только итоговые строки команды по выводу. Учебные
проекты — в `config.TARGETS` песочницы (`tests.sandbox.TmpRootTest`);
числа вывода — из `random`, зерно печатается и входит в текст каждого
провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
у задачи с `decide(target).profile.report == pult-vitest` обе строки
итога пишут «итог vitest: <деталь разбора требования 2>» и «код выхода
vitest» — все методы файла зелёные.
"""
import contextlib
import io
import random
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import (acceptance, config, plank_run, project_profile,
                          store, workspace)
from tests.sandbox import TmpRootTest, artel_target_entry, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
NO_SUMMARY = "итоговой строки нет"
DOCS_DIR = "tasks"

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


class PlankRunSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
        self.names = {"vitest": f"v{self.word()}", "pytest": f"p{self.word()}",
                      "skip": f"s{self.word()}", "unresolved": f"u{self.word()}"}
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + component_entry(self.names["vitest"], {
                "command": list(project_profile.VITEST_BASE_ARGV),
                "report": project_profile.REPORT_VITEST,
                "long_lived_dir": "web/src",
                "long_lived_name": "<id>_<name>.test.js",
                "weakening_scope": ["web/src/**"],
                "mutation_claim_scope": ["web/src/**"],
                "tests": ["web/src/**/*.test.js"]})
            + component_entry(self.names["pytest"], {
                "command": ["python3", "-m", "pytest"],
                "report": project_profile.REPORT_JUNIT,
                "long_lived_dir": "backend/tests",
                "long_lived_name": "test_<id>_<name>.py",
                "weakening_scope": ["backend/tests/**"],
                "mutation_claim_scope": ["backend/tests/**"],
                "tests": ["backend/tests/test_*.py"]})
            + ENTRY_HEAD.format(name=self.names["skip"], base=config.MAIN_BRANCH)
            + ENTRY_HEAD.format(name=self.names["unresolved"],
                                base=config.MAIN_BRANCH),
            encoding="utf-8")
        for kind in ("vitest", "pytest", "skip"):
            make_project_repo(self.names[kind], origin=False)
        self.answer = (0, "")
        for patcher in (
                mock.patch.object(acceptance, "plank_in_code_copy",
                                  self.fake_copy),
                mock.patch.object(acceptance, "run_plank", self.fake_run)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    @contextlib.contextmanager
    def fake_copy(self, task_id, _branch, code_dir, files=None):
        yield code_dir / DOCS_DIR / task_id

    def fake_run(self, *args, **kwargs):
        return self.answer

    def target(self, kind: str) -> str:
        return ARTEL if kind == "artel" else self.names[kind]

    def task(self, kind: str) -> str:
        """Задача вида `kind` в `tests_writing` с черновиком планки и
        каталогом рабочей копии кода."""
        target = self.target(kind)
        task_id = ulid(self.rng)
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          f"task/{task_id.lower()}-{self.word()}", target,
                          config.DEFAULT_BUDGET_USD)
        workspace.path(task_id, target).mkdir(parents=True, exist_ok=True)
        name = "a.test.js" if kind == "vitest" else "test_a.py"
        plank = (config.PROJECTS / target / DOCS_DIR / task_id
                 / "acceptance_tests")
        plank.mkdir(parents=True, exist_ok=True)
        (plank / name).write_text("// тест\n" if kind == "vitest"
                                  else "def test_a():\n    pass\n",
                                  encoding="utf-8")
        return task_id

    def plank_run(self, task_id: str, code, output: str) -> tuple:
        """(вывод команды, текст отказа `SystemExit` либо код)."""
        self.answer = (code, output)
        out = io.StringIO()
        exit_value = None
        with redirect_stdout(out), redirect_stderr(out):
            try:
                plank_run.cmd_plank_run(task_id)
            except SystemExit as exc:
                exit_value = exc.code
        return out.getvalue(), exit_value

    def vitest_block(self) -> tuple:
        """(вывод Vitest, деталь разбора)."""
        failed = self.rng.randrange(0, 4)
        passed = self.rng.randrange(1, 30)
        counts = (f"{failed} failed | {passed} passed" if failed
                  else f"{passed} passed")
        ms = self.rng.randrange(11, 999)
        while ms % 10 == 5:
            ms = self.rng.randrange(11, 999)
        text = (f"\n Test Files  1 passed (1)\n"
                f"      Tests  {counts} ({failed + passed})\n"
                f"   Start at  10:20:30\n"
                f"   Duration  {ms}ms (transform 5ms, setup 0ms)\n")
        return text, f"{counts} ({failed + passed}) in {ms / 1000:.2f}s"

    def pytest_line(self) -> tuple:
        """(вывод pytest, итоговая строка)."""
        summary = (f"{self.rng.randrange(1, 40)} passed in "
                   f"{self.rng.randrange(0, 9)}.{self.rng.randrange(10, 100)}s")
        return f"collected 3 items\n\n=== {summary} ===\n", summary


class Ac8VitestSummaryTest(PlankRunSandbox):

    def test_ac8_vitest_summary_and_exit_code(self):
        """`plank-run` задачи `pult-vitest` печатает «итог vitest: <деталь>; код выхода vitest: <код>».

        Сценарий: прогон отвечает кодом 0 и 1 с блоком Vitest в выводе —
        вывод команды несёт «итог vitest: <сч Tests> (<n>) in
        <секунды>s; код выхода vitest: <код>», «итог pytest» нет; при
        коде 1 команда выходит с этим кодом.

        Ловит мутацию: строка итога берётся `run_summary_line` (pytest) и
        у Vitest — «итоговой строки нет»; слово «pytest» в строке не
        заменено; признак компонента не тот, что у runner, — строка
        прежняя.
        """
        for code in (0, 1):
            task_id = self.task("vitest")
            text, detail = self.vitest_block()
            out, exit_value = self.plank_run(task_id, code, text)
            with self.subTest(code=code, seed=self.seed):
                self.assertIn(f"итог vitest: {detail}; код выхода vitest: "
                              f"{code}", out, self.note(out))
                self.assertNotIn("итог pytest", out, self.note(out))
                self.assertEqual(exit_value, None if code == 0 else code,
                                 self.note(out))

    def test_ac8_vitest_timeout_line(self):
        """Оборванный по таймауту прогон задачи `pult-vitest` — отказ «итог vitest: <деталь>; прогон превысил …с и оборван».

        Сценарий: прогон отвечает кодом `None` (оборван) с блоком Vitest в
        выводе — команда выходит отказом, текст которого несёт «итог
        vitest: <деталь>; прогон превысил <секунды>с и оборван».

        Ловит мутацию: новое слово подставлено только в строку кода
        выхода — строка оборванного прогона прежняя «итог pytest».
        """
        task_id = self.task("vitest")
        text, detail = self.vitest_block()
        out, exit_value = self.plank_run(task_id, None, text)
        self.assertIsInstance(exit_value, str, self.note(out))
        self.assertRegex(exit_value, re.escape(f"итог vitest: {detail}; "
                                               f"прогон превысил ")
                         + r"\d+с и оборван", self.note(out))

    def test_ac8_no_vitest_block_detail(self):
        """Без блока Vitest в выводе деталь `plank-run` задачи `pult-vitest` — «итоговой строки нет», в обеих строках итога.

        Сценарий: вывод прогона несёт только итоговую строку pytest, без
        блока Vitest: при коде 0 — «итог vitest: итоговой строки нет; код
        выхода vitest: 0», при оборванном прогоне — отказ «итог vitest:
        итоговой строки нет; прогон превысил …».

        Ловит мутацию: при отсутствии блока Vitest берётся строка pytest —
        деталь «N passed in Xs».
        """
        text, _summary = self.pytest_line()
        task_id = self.task("vitest")
        out, _exit = self.plank_run(task_id, 0, text)
        self.assertIn(f"итог vitest: {NO_SUMMARY}; код выхода vitest: 0", out,
                      self.note(out))
        task_id = self.task("vitest")
        out, exit_value = self.plank_run(task_id, None, text)
        self.assertIn(f"итог vitest: {NO_SUMMARY}; прогон превысил ",
                      str(exit_value), self.note(out))


class Ac9OldSummaryTest(PlankRunSandbox):

    def test_ac9_old_lines_for_artel_pytest_and_undefined_profile(self):
        """`plank-run` у артели, pytest-компонента и задачи с `decide(target).profile is None` печатает обе строки итога прежними побайтно.

        Сценарий: для каждого вида задачи — артель, компонент `junit-xml` на
        pytest, запись без профиля с клоном (пропуск) и без клона (отказ) —
        вывод прогона несёт итоговую строку pytest и блок Vitest; при коде
        0 и 1 последняя строка вывода команды — ровно «[<id>] plank-run:
        итог pytest: <строка>; код выхода pytest: <код>»; при оборванном
        прогоне отказ — ровно «[<id>] plank-run: итог pytest: <строка>;
        прогон превысил <ACCEPTANCE_TIMEOUT_SEC>с и оборван»; без
        итоговой строки pytest — «итоговой строки нет».

        Ловит мутацию: выбор слова по содержимому вывода (есть блок
        Vitest — «итог vitest») вместо профиля; признак читает
        `decide(target).profile.report` без проверки `None` — задача без
        профиля падает AttributeError; новое слово у всех задач.
        """
        for kind in ("artel", "pytest", "skip", "unresolved"):
            if kind in ("skip", "unresolved"):
                self.assertIsNone(
                    project_profile.decide(self.target(kind)).profile,
                    self.note(f"фикстура: у {kind} есть профиль"))
            vitest, _detail = self.vitest_block()
            pytest_text, summary = self.pytest_line()
            for code, text, shown in ((0, pytest_text + vitest, summary),
                                      (1, vitest + pytest_text, summary),
                                      (0, vitest, NO_SUMMARY)):
                task_id = self.task(kind)
                out, _exit = self.plank_run(task_id, code, text)
                last = out.rstrip("\n").rsplit("\n", 1)[-1]
                with self.subTest(kind=kind, code=code, seed=self.seed):
                    self.assertEqual(
                        last, f"[{task_id}] plank-run: итог pytest: {shown}; "
                              f"код выхода pytest: {code}", self.note(out))
            task_id = self.task(kind)
            out, exit_value = self.plank_run(task_id, None,
                                             pytest_text + vitest)
            with self.subTest(kind=kind, code=None, seed=self.seed):
                self.assertEqual(
                    exit_value, f"[{task_id}] plank-run: итог pytest: "
                                f"{summary}; прогон превысил "
                                f"{config.ACCEPTANCE_TIMEOUT_SEC}с и оборван",
                    self.note(out))


if __name__ == "__main__":
    unittest.main()
