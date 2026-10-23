"""Выход `tests_writing` проверяет планку и долгоживущие файлы линтом детерминизма до лока — только у артели.

Группа: долгоживущий
Красен до реализации: гейты выхода `tests_writing` линта детерминизма не зовут — цикл по `time.time()` в долгоживущем файле (AC-3), `time.sleep(1)` и путь к `targets.yaml` в разовом файле планки (AC-4) проходят до `in_dev` и лока; AC-5 (чистые файлы и файл с синтаксической ошибкой) и AC-7 (чужой проект) держат поведение, которое правка обязана сохранить, и зелёные.

Стенд — настоящий git (`tests/sandbox.py::GitignoreCommittedRealGitSandbox`,
тот же каркас, что `tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py`):
клон артели — корень песочницы с синхронным bare `origin`; чужой проект —
`tests.sandbox.make_project_repo` с профилем тестов артели в `targets.yaml`
песочницы. Задача заводится в БД пульта напрямую (`store.insert_task`) в
состоянии `tests_writing`, рабочая копия кода — `workspace.ensure`;
черновик планки лежит в каталоге документов задачи, долгоживущий файл — в
`tests/` рабочей копии кода. Черновик переносится штатными чекпоинтами
шага, затем `fsm.cmd_advance`.

Нарушение в фикстуре — во вспомогательном методе класса (не `test_*`):
сухой сбор его не исполняет, а линт адресует любой метод верхнего уровня.
Имена файлов, классов и методов, положение нарушения и вид чистого
образца — от `random`; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import keyword
import os
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (checkpoint, config, fsm, github_adapter, store,
                          workspace)
from orchestrator.advance_gates import tests_writing as transition_gates
from scripts import guard
from tests.sandbox import (ARTEL_TEST_PROFILE, GitignoreCommittedRealGitSandbox,
                           make_project_repo)

ULID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
DOCS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"

# Тексты нарушений линта (формулировки правила, `tests/test_invariants.py`).
SLEEP_HIT = "time.sleep с ненулевой паузой"
LOOP_HIT = "цикл до срока по time.monotonic()/time.time()"
LIVE_HIT = "путь к живому файлу репозитория"
LINT_HITS = (SLEEP_HIT, LOOP_HIT, LIVE_HIT)

# Нарушения: (имя, тело вспомогательного метода, подстрока строки нарушения).
SLEEP_BODY = ("        time.sleep(1)\n", "time.sleep(1)")
DEADLINE_BODY = ("        deadline = time.time() + 5\n"
                 "        while time.time() < deadline:\n"
                 "            break\n", "while time.time() < deadline")
TARGETS_BODY = ('        return Path(__file__).parent.parent / "targets.yaml"\n',
                '"targets.yaml"')

# Чистые образцы, похожие на нарушения: линт их не ловит.
CLEAN_BODIES = (
    "        time.sleep(0)\n",
    "        time.sleep(secs=0)\n",
    '        return self.root / "targets.yaml"\n',
    "        stamp = time.time()\n        return stamp\n",
    "        for item in range(3):\n            if item > 1:\n                break\n",
)

SYNTAX_BROKEN_TAIL = "\n\ndef (\n"


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(ULID_LETTERS) for _ in range(24))


def word(rng: random.Random, size: int = 7) -> str:
    """Идентификатор из строчных букв: не ключевое слово и не модуль
    стандартной библиотеки."""
    while True:
        value = "".join(rng.choice(LETTERS) for _ in range(size))
        if not keyword.iskeyword(value) and value not in sys.stdlib_module_names:
            return value


def spec_text(task_id: str) -> str:
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура линта детерминизма\n\n## Контекст\n\n"
            "## Требования\n\n## Критерии приёмки\n\n"
            "AC-1. Критерий фикстуры.\n\n## Не входит\n")


def fixture_source(group: str, cls: str, test: str, helper: str,
                   body: str, padding: int, covers: bool = True) -> str:
    """Файл фикстуры группы `group`: класс `cls` с тестом `test` (заявка
    мутации есть) и вспомогательным методом `helper` с телом `body` после
    `padding` строк-заполнителей. `covers` — тест покрывает AC-1 фикстуры."""
    name = f"test_ac1_{test}" if covers else f"test_{test}"
    lines = ['"""Фикстура линта детерминизма.', "",
             "Группа: " + group,
             "Красен " + "до реализации: фикстура ждёт кода.",
             '"""', "import random", "import time", "import unittest",
             "from pathlib import Path", ""]
    lines += [f"# строка-заполнитель {i}" for i in range(padding)]
    lines += ["", "", f"class {cls}(unittest.TestCase):", "",
              "    root = Path('.')", "",
              f"    def {name}(self):",
              '        """Фикстурный метод.', "",
              "        Ловит " + "мутацию: фикстура — сумма перестаёт совпадать.",
              '        """',
              "        seed = random.randrange(1 << 30)",
              '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")', "",
              f"    def {helper}(self):"]
    return "\n".join(lines) + "\n" + body


def line_of(text: str, needle: str) -> int:
    return next(i for i, line in enumerate(text.splitlines(), 1) if needle in line)


class ExitLintSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; чужой проект и задачи заводит сценарий."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        # Отправка головы в origin и Draft MR зовут `gh` — вне предмета.
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda *args, **kwargs: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.conn = store.db()

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def foreign_project(self) -> str:
        """Чужой проект (не артель) с профилем тестов артели."""
        target = "proj" + word(self.rng, 6)
        make_project_repo(target)
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + ARTEL_TEST_PROFILE,
                                  encoding="utf-8")
        return target

    def new_task(self, target: str = config.DEFAULT_TARGET):
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-lint"
        store.insert_task(self.conn, tid, "Фикстура линта детерминизма",
                          "tests_writing", branch, target, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, branch=branch, target=target, wt=Path(wt))
        t.docs = config.PROJECTS / target / DOCS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid), encoding="utf-8")
        return t

    def source(self, group: str, body: str, covers: bool = True) -> SimpleNamespace:
        f = SimpleNamespace(cls="Fixture" + word(self.rng, 6).capitalize() + "Test",
                            test=word(self.rng, 6), helper=word(self.rng, 6))
        f.text = fixture_source(group, f.cls, f.test, f.helper, body,
                                self.rng.randrange(0, 6), covers)
        return f

    def plank_file(self, t, f) -> str:
        name = f"test_{word(self.rng, 6)}.py"
        (t.plank / name).write_text(f.text, encoding="utf-8")
        return f"{PLANK_DIR}/{name}"

    def long_lived_file(self, t, f) -> str:
        rel = "/".join(("tests", f"test_{t.id.lower()}_{word(self.rng, 6)}.py"))
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f.text, encoding="utf-8")
        return rel

    def step_and_advance(self, t) -> tuple:
        """Черновик — в ссылку документов и кодовую ветку чекпоинтами шага,
        затем `advance`: (новые записи журнала, вывод advance)."""
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def row(self, t):
        return store.get_task(self.conn, t.id)

    def details(self, rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    def assert_refused_before_lock(self, t, rows, output, action, needle) -> None:
        details = self.details(rows, action)
        self.assertTrue(details, self.note(
            f"нет записи «{action}»:\n"
            f"{[(r['action'], r['detail']) for r in rows]}\n{output}"))
        self.assertTrue(any(needle in d for d in details), self.note(
            f"«{action}» не называет «{needle}»:\n{details}"))
        self.assertEqual(self.row(t)["state"], "tests_writing", self.note(
            f"задача ушла из tests_writing:\n{output}"))
        self.assertFalse(self.row(t)["tests_locked_sha"], self.note(
            "tests_locked_sha выставлен при отказе"))

    def assert_no_lint(self, rows: list, output: str, what: str) -> None:
        text = "\n".join(str(r["detail"] or "") for r in rows) + "\n" + output
        for hit in LINT_HITS:
            self.assertNotIn(hit, text, self.note(
                f"{what}: отказ линта «{hit}»:\n{text}"))

    def assert_locked(self, t, rows: list, output: str, what: str) -> None:
        self.assertEqual(self.row(t)["state"], "in_dev", self.note(
            f"{what}: выход tests_writing не пройден:\n"
            f"{[(r['action'], r['detail']) for r in rows]}\n{output}"))
        self.assertTrue(self.row(t)["tests_locked_sha"], self.note(
            f"{what}: лок не выставлен"))


class LongLivedDeadlineLoopTest(ExitLintSandbox):

    def test_ac3_long_lived_deadline_loop_refused_before_lock(self):
        """Долгоживущий файл ветки с циклом `while time.time() < deadline` — отказ выхода с адресом метода и строкой, лока нет.

        Сценарий: задача артели; планка — чистый разовый файл, покрывающий
        AC-1 фикстуры; в `tests/` рабочей копии кода — долгоживущий файл
        задачи, у которого вспомогательный метод (имена и положение от
        зерна) ждёт по часам циклом до срока. После `advance` в журнале —
        «переход отклонён: долгоживущие файлы tests/», detail несёт
        «<файл>::<Класс>::<метод>: строка N» со строкой цикла; задача в
        `tests_writing`, `tests_locked_sha` пуст.

        Ловит мутацию: гейт кодовой ветки не зовёт линт (или зовёт его
        только для файлов планки) — задача уходит в `in_dev` с локом;
        адрес нарушения собран без класса или с номером строки начала
        метода — подстроки с файлом, классом, методом и строкой цикла нет.
        """
        t = self.new_task()
        self.plank_file(t, self.source(guard.GROUP_ONE_OFF, "        pass\n"))
        f = self.source(guard.GROUP_LONG_LIVED, DEADLINE_BODY[0], covers=False)
        rel = self.long_lived_file(t, f)
        n = line_of(f.text, DEADLINE_BODY[1])

        rows, output = self.step_and_advance(t)

        self.assert_refused_before_lock(
            t, rows, output, transition_gates.LONG_LIVED_ACTION,
            f"{rel}::{f.cls}::{f.helper}: строка {n}")


class PlankViolationsTest(ExitLintSandbox):

    def test_ac4_one_off_plank_sleep_and_live_file_refused_before_lock(self):
        """Разовый файл планки с `time.sleep(1)` и, отдельно, с путём к `targets.yaml` от `__file__` — отказ гейта групп с адресом, лока нет.

        Сценарий: задача артели; два подтеста — по своей задаче каждый. В
        планке — разовый файл, покрывающий AC-1 фикстуры, у которого
        вспомогательный метод зовёт `time.sleep(1)` либо строит
        `Path(__file__).parent.parent / "targets.yaml"`. После `advance` в
        журнале — «переход отклонён: группы приёмочных тестов», detail
        несёт «acceptance_tests/<файл>::<Класс>::<метод>: строка N: » со
        строкой нарушения; задача в `tests_writing`, лока нет.

        Ловит мутацию: линт перенесён после фильтра по группе (проверяются
        только долгоживущие файлы) — разовый файл проходит, задача уходит
        в `in_dev` с локом; из правила выпало имя живого файла или пауза.
        """
        cases = [("time.sleep(1)", SLEEP_BODY), ("targets.yaml", TARGETS_BODY)]
        self.rng.shuffle(cases)
        for label, (body, needle) in cases:
            with self.subTest(нарушение=label):
                t = self.new_task()
                f = self.source(guard.GROUP_ONE_OFF, body)
                rel = self.plank_file(t, f)
                n = line_of(f.text, needle)

                rows, output = self.step_and_advance(t)

                self.assert_refused_before_lock(
                    t, rows, output, transition_gates.TEST_GROUPS_ACTION,
                    f"{rel}::{f.cls}::{f.helper}: строка {n}: ")


class CleanAndBrokenFilesTest(ExitLintSandbox):

    def test_ac5_clean_files_pass_exit(self):
        """Чистые файлы планки и долгоживущие файлы с похожими на нарушения образцами — выход пройден, лок выставлен.

        Сценарий: задача артели; разовый файл планки и долгоживущий файл
        задачи несут во вспомогательном методе чистый образец (от зерна):
        `time.sleep(0)`, `time.sleep(secs=0)`, путь от корня песочницы,
        чтение часов вне цикла, цикл без часов. После `advance` задача в
        `in_dev`, лок выставлен, в журнале и выводе нет текстов линта.

        Ловит мутацию: правило ловит нулевую паузу, путь не от `__file__`
        или любой вызов часов вне цикла — чистый файл получает отказ, задача
        остаётся в `tests_writing`.
        """
        t = self.new_task()
        self.plank_file(t, self.source(guard.GROUP_ONE_OFF,
                                       self.rng.choice(CLEAN_BODIES)))
        self.long_lived_file(t, self.source(guard.GROUP_LONG_LIVED,
                                            self.rng.choice(CLEAN_BODIES),
                                            covers=False))

        rows, output = self.step_and_advance(t)

        self.assert_no_lint(rows, output, "чистые файлы")
        self.assert_locked(t, rows, output, "чистые файлы")

    def test_ac5_syntax_error_plank_does_not_crash_gate(self):
        """Файл планки с синтаксической ошибкой — гейт не падает исключением `SyntaxError`, отказа линта нет.

        Сценарий: задача артели; в планке — чистый разовый файл, покрывающий
        AC-1, и второй разовый файл, чей текст после класса обрывается
        синтаксической ошибкой. `advance` завершается без исключения
        (кроме `SystemExit`), задача остаётся в `tests_writing` (сбор
        планки не проходит), ни запись журнала, ни вывод не несут текстов
        линта.

        Ловит мутацию: guard передаёт исходник линту без перехвата
        `SyntaxError` — `fsm.cmd_advance` падает исключением, тест
        заканчивается ошибкой вместо отказа перехода.
        """
        t = self.new_task()
        self.plank_file(t, self.source(guard.GROUP_ONE_OFF, "        pass\n"))
        broken = self.source(guard.GROUP_ONE_OFF, SLEEP_BODY[0], covers=False)
        broken.text += SYNTAX_BROKEN_TAIL
        self.plank_file(t, broken)

        rows, output = self.step_and_advance(t)

        self.assert_no_lint(rows, output, "синтаксическая ошибка")
        self.assertEqual(self.row(t)["state"], "tests_writing", self.note(
            f"планка с синтаксической ошибкой прошла выход:\n{output}"))


class ForeignProjectTest(ExitLintSandbox):

    def test_ac7_foreign_project_violations_not_refused(self):
        """Чужой проект: цикл по часам в долгоживущем файле и `time.sleep(1)`/путь к `targets.yaml` в планке — отказа линта нет, выход пройден.

        Сценарий: учебный внешний проект с профилем тестов артели; у его
        задачи долгоживущий файл с циклом `while time.time() < deadline`
        (нарушение AC-3) и разовый файл планки, покрывающий AC-1, с
        `time.sleep(1)` и, отдельным подтестом и задачей, с путём к
        `targets.yaml` (нарушения AC-4). После `advance` в журнале и выводе
        нет текстов линта, задача в `in_dev` с локом.

        Ловит мутацию: признак проекта не передан линту (проверка у всех
        проектов) — чужая задача получает отказ «группы приёмочных тестов»
        или «долгоживущие файлы tests/», остаётся в `tests_writing`.
        """
        target = self.foreign_project()
        for label, (body, _needle) in (("time.sleep(1)", SLEEP_BODY),
                                       ("targets.yaml", TARGETS_BODY)):
            with self.subTest(нарушение=label):
                t = self.new_task(target)
                self.plank_file(t, self.source(guard.GROUP_ONE_OFF, body))
                self.long_lived_file(t, self.source(
                    guard.GROUP_LONG_LIVED, DEADLINE_BODY[0], covers=False))

                rows, output = self.step_and_advance(t)

                self.assert_no_lint(rows, output, f"чужой проект, {label}")
                self.assert_locked(t, rows, output, f"чужой проект, {label}")


if __name__ == "__main__":
    unittest.main()
