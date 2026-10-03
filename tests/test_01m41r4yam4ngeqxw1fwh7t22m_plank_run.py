"""Команда `plank-run`: штатный локальный прогон планки задачи в шаге роли.

Команда выкладывает планку в каталог задачи под `tasks` рабочей копии кода
тем же узлом, что пульт, гоняет её тем же раннером и таймаутом, печатает
итог pytest и его код выхода, убирает выкладку — только каталог своей
задачи — на любом исходе. Источник планки: в `tests_writing` — черновик
`acceptance_tests` каталога документов задачи, в остальных состояниях —
зафиксированная планка ссылки документов. Под ролью команда исполняется и
не меняет ни строки задачи, ни журнала, ни ссылок. Задача без планки —
отказ «планки нет» без выкладки и прогона. Миссия шага называет
`plank-run` и не велит копировать планку руками.

Группа: долгоживущий
Красен до реализации: команды plank-run в диспетчере artel.py нет — под ролью отказ «команда недоступна», вне роли «Неизвестная команда», pytest не запускается; миссия docs_dir_note велит copytree и не называет plank-run.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): репозиторий
пульта с bare `origin`, в `main` — отслеживаемые исторические каталоги задач
под `tasks` (случайные имена от зерна), задача target по умолчанию с
рабочей копией кода (`workspace.ensure`). Ссылка документов задачи
`refs/artifacts/<id>` — символическая ссылка на обычную ветку
(`tests/sandbox.py::alias_docs_ref_to_branch`), её коммиты ведёт отдельный
git-worktree песочницы. Черновик планки — файлы каталога документов
`.artel/projects/<target>/` + `tasks` / `<id>` / `acceptance_tests`. Команда
зовётся через `artel.main()`; вывод снимается и с `sys.stdout`/`sys.stderr`,
и с файловых дескрипторов 1/2 (прогон может печатать мимо Python).
Наблюдатель `subprocess.run` пропускает каждый вызов в настоящий, а у
вызова pytest запоминает argv, таймаут и снимок выложенной планки.
"""
import io
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, role_prompt, stack, store, workspace
from tests.sandbox import RealGitSandbox, alias_docs_ref_to_branch

FIXTURE_TASK = "01M0000000000000000000PLNK"
FIXTURE_BRANCH = "task/fixture-plank-run"
LETTERS = "ABCDEFGHJKMNPQRSTVWXYZ"
ROLE_REFUSAL = "команда недоступна процессу роли"

PASSING = "def test_{name}():\n    assert True\n"
FAILING = "def test_{name}():\n    assert False, 'красный тест {name}'\n"


def is_pytest_call(cmd) -> bool:
    argv = [str(a) for a in cmd] if isinstance(cmd, (list, tuple)) else []
    return any(argv[i] == "-m" and argv[i + 1] == "pytest"
               for i in range(len(argv) - 1))


class PlankRunSandbox(RealGitSandbox):
    """Задача с рабочей копией кода, историческими каталогами задач в HEAD
    и ссылкой документов, которую ведёт отдельный worktree песочницы."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.historic = self.seed_historic_task_dirs()
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, FIXTURE_TASK, "Фикстура plank-run",
                          "in_dev", FIXTURE_BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(FIXTURE_TASK, FIXTURE_BRANCH)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.wt = wt
        self.own_dir = self.wt / "tasks" / FIXTURE_TASK
        self.docs_dir = (config.PROJECTS / config.DEFAULT_TARGET / "tasks"
                         / FIXTURE_TASK)
        self.docs_wt = None
        self.commit_docs({"SPEC.md": "---\ntask: x\ntype: spec\n---\n# SPEC\n"})
        self.pytest_calls = []
        self.raise_in_pytest = None
        real_run = subprocess.run

        def observed_run(cmd, *args, **kwargs):
            if is_pytest_call(cmd):
                plank = self.own_dir / "acceptance_tests"
                snapshot = {}
                if plank.is_dir():
                    snapshot = {p.relative_to(plank).as_posix():
                                p.read_text(encoding="utf-8")
                                for p in sorted(plank.rglob("*.py"))}
                self.pytest_calls.append((list(cmd), dict(kwargs), snapshot))
                if self.raise_in_pytest is not None:
                    raise self.raise_in_pytest
            return real_run(cmd, *args, **kwargs)

        patcher = mock.patch.object(subprocess, "run", observed_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- фикстуры ---------------------------------------------------------

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def seed_historic_task_dirs(self) -> dict:
        """Отслеживаемые каталоги прошлых задач в `main` — до рабочей копии."""
        files = {}
        for _ in range(2 + self.rng.randrange(3)):
            task_dir = "H" + self.word()
            for name in self.rng.sample(["SPEC.md", "PLAN.md", "REVIEW.md",
                                         "RETRO.md"], 2):
                rel = "/".join(("tasks", task_dir, name))
                text = f"# {task_dir} {name}\nзерно {self.seed}\n"
                path = self.root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                files[rel] = text
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "исторические каталоги задач")
        return files

    def commit_docs(self, files: dict, remove=()) -> None:
        """Коммит в ссылку документов задачи и фиксация её головы."""
        if self.docs_wt is None:
            branch = alias_docs_ref_to_branch(self.root, FIXTURE_TASK)
            holder = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, holder, ignore_errors=True)
            self.docs_wt = holder / "docs"
            self.git("worktree", "add", "-q", "--orphan", "-b", branch,
                     str(self.docs_wt))
        base = self.docs_wt / "tasks" / FIXTURE_TASK
        for rel, text in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for rel in remove:
            (base / rel).unlink()
        self.git("-C", str(self.docs_wt), "add", "-A")
        self.git("-C", str(self.docs_wt), "commit", "-q", "-m", "документы")
        store.record_fixation(self.conn, FIXTURE_TASK)

    def commit_fixed_plank(self, files: dict) -> None:
        self.commit_docs({f"acceptance_tests/{name}": text
                          for name, text in files.items()})

    def write_draft(self, files: dict) -> None:
        plank = self.docs_dir / "acceptance_tests"
        plank.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (plank / name).write_text(text, encoding="utf-8")

    def set_state(self, state: str) -> None:
        store.update_task(self.conn, FIXTURE_TASK, state=state)

    # --- прогон команды -----------------------------------------------------

    def plank_run(self, *extra: str) -> tuple:
        """(код выхода, весь вывод) `artel.py plank-run <id> [файл]`."""
        argv = ["artel.py", "plank-run", FIXTURE_TASK, *extra]
        out, err = io.StringIO(), io.StringIO()
        code = None
        with tempfile.TemporaryFile() as fd_sink:
            sys.stdout.flush()
            sys.stderr.flush()
            saved = os.dup(1), os.dup(2)
            os.dup2(fd_sink.fileno(), 1)
            os.dup2(fd_sink.fileno(), 2)
            try:
                with mock.patch.object(sys, "argv", argv), \
                        redirect_stdout(out), redirect_stderr(err):
                    try:
                        artel.main()
                    except SystemExit as exc:
                        code = exc.code
            finally:
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                os.close(saved[0])
                os.close(saved[1])
            fd_sink.seek(0)
            fd_text = fd_sink.read().decode("utf-8", errors="replace")
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, "\n".join((out.getvalue(), err.getvalue(), fd_text,
                                  message))

    def explain(self, output: str) -> str:
        return f"зерно: {self.seed}; вывод plank-run:\n{output[-3000:]}"

    def assert_only_own_dir_dropped(self, output: str) -> None:
        self.assertFalse(self.own_dir.exists(),
                         f"каталог задачи остался в рабочей копии; "
                         f"{self.explain(output)}")
        for rel, text in self.historic.items():
            path = self.wt / rel
            self.assertTrue(path.is_file(),
                            f"исторический {rel} удалён; {self.explain(output)}")
            self.assertEqual(path.read_text(encoding="utf-8"), text,
                             f"исторический {rel} изменён; "
                             f"{self.explain(output)}")
        status = self.git("-C", str(self.wt), "status", "--porcelain", "--",
                          "tasks")
        self.assertEqual(status, "", f"git status по tasks не чист; "
                                     f"{self.explain(output)}")

    def exit_code_value(self) -> int:
        """Код выхода pytest, не совпадающий с числами его обычного вывода."""
        busy = {50, 100, stack.PER_TEST_TIMEOUT_SEC}
        return self.rng.choice([n for n in range(61, 100) if n not in busy])


class DraftInTestsWritingTest(PlankRunSandbox):

    def test_ac1_tests_writing_runs_draft_with_pult_runner(self):
        """В `tests_writing` прогоняется черновик каталога документов.

        Сценарий: задача в `tests_writing`; ссылка документов либо не несёт
        планки вовсе, либо несёт зафиксированную планку из двух красных
        тестов `test_fixed_*`; черновик каталога документов — один зелёный
        тест и тест, завершающий pytest кодом выхода от зерна. На время
        вызова pytest в каталоге планки рабочей копии лежат ровно файлы
        черновика; argv — интерпретатор пульта, `-m pytest` и хвост общих
        флагов пульта (`-p no:cacheprovider -p timeout -o timeout=<потолок
        теста>`), таймаут вызова — `config.ACCEPTANCE_TIMEOUT_SEC` (подменён
        случайным); вывод несёт итог pytest «1 passed» и код выхода pytest.

        Ловит мутацию: источник планки не различает состояние и всегда
        выкладывает зафиксированную планку ссылки — в выкладке файлы
        `test_fixed_*`, вывод называет их падение; прогон собран своей
        командой без `-p no:cacheprovider`/`-o timeout=` либо с литеральным
        таймаутом вместо `config.ACCEPTANCE_TIMEOUT_SEC` — хвост argv или
        таймаут вызова не совпадают; код выхода pytest не печатается —
        числа от зерна в выводе нет.
        """
        fixed = {"test_fixed_plank.py": FAILING.format(name="fixed_alpha")
                 + FAILING.format(name="fixed_beta")}
        for variant in ("ссылка без планки", "зафиксированная планка"):
            with self.subTest(variant=variant):
                self.pytest_calls = []
                if variant == "зафиксированная планка":
                    self.commit_fixed_plank(fixed)
                self.set_state("tests_writing")
                code = self.exit_code_value()
                draft = {"test_draft_plank.py": (
                    "import pytest\n\n" + PASSING.format(name="draft_ok")
                    + "\n\ndef test_draft_stop():\n"
                    f"    pytest.exit('черновик остановлен', returncode={code})\n")}
                self.write_draft(draft)
                timeout = 200 + self.rng.randrange(700)
                with mock.patch.object(config, "ACCEPTANCE_TIMEOUT_SEC", timeout):
                    _status, output = self.plank_run()

                self.assertEqual(len(self.pytest_calls), 1,
                                 f"pytest не запущен ровно раз; "
                                 f"{self.explain(output)}")
                cmd, kwargs, snapshot = self.pytest_calls[0]
                self.assertEqual(snapshot, draft,
                                 f"в выкладке не черновик; {self.explain(output)}")
                self.assertEqual(cmd[:3], [stack.pytest_python_executable(),
                                           "-m", "pytest"], self.explain(output))
                self.assertEqual(
                    cmd[-6:], ["-p", "no:cacheprovider", "-p", "timeout", "-o",
                               f"timeout={stack.PER_TEST_TIMEOUT_SEC}"],
                    self.explain(output))
                self.assertEqual(kwargs.get("timeout"), timeout,
                                 f"таймаут прогона не ACCEPTANCE_TIMEOUT_SEC; "
                                 f"{self.explain(output)}")
                self.assertIn("1 passed", output, self.explain(output))
                self.assertRegex(output, rf"(?<![\w.%]){code}(?![\w.%])",
                                 f"код выхода pytest {code} не напечатан; "
                                 f"{self.explain(output)}")
                self.assertNotIn("test_fixed_", output, self.explain(output))


class FixedPlankAfterTestsWritingTest(PlankRunSandbox):

    def setUp(self):
        super().setUp()
        self.fixed = {"test_a_plank.py": PASSING.format(name="a_fixed"),
                      "test_b_plank.py": FAILING.format(name="b_must_not_run")}
        self.commit_fixed_plank(self.fixed)
        self.write_draft({"test_a_plank.py": FAILING.format(name="a_disk"),
                          "test_c_plank.py": FAILING.format(name="c_disk")})

    def test_ac2_later_states_run_fixed_plank_and_single_file(self):
        """После `tests_writing` прогоняется зафиксированная планка ссылки.

        Сценарий: задача в `in_dev` и в `review`; в ссылке документов
        зафиксированы `test_a_plank.py` (зелёный) и `test_b_plank.py`
        (красный `test_b_must_not_run`); на диске каталога документов
        `test_a_plank.py` расходится со ссылкой (красный `test_a_disk`) и
        лежит лишний `test_c_plank.py`. `plank-run <id>` выкладывает ровно
        файлы ссылки; `plank-run <id> test_a_plank.py` исполняет только
        названный файл — «1 passed», `test_b_must_not_run` не исполнялся.

        Ловит мутацию: черновик каталога документов берётся и вне
        `tests_writing` — в выкладке `test_a_disk`/`test_c_plank.py`;
        аргумент файла не передаётся в pytest (гонится вся планка) — в
        выводе падение `test_b_must_not_run`.
        """
        for state in ("in_dev", "review"):
            with self.subTest(state=state):
                self.set_state(state)
                self.pytest_calls = []
                _status, output = self.plank_run()
                self.assertEqual(len(self.pytest_calls), 1, self.explain(output))
                self.assertEqual(self.pytest_calls[0][2], self.fixed,
                                 f"в выкладке не планка ссылки; "
                                 f"{self.explain(output)}")
                self.assertNotIn("test_a_disk", output, self.explain(output))

                self.pytest_calls = []
                _status, output = self.plank_run("test_a_plank.py")
                self.assertEqual(len(self.pytest_calls), 1, self.explain(output))
                self.assertIn("1 passed", output, self.explain(output))
                self.assertNotIn("b_must_not_run", output, self.explain(output))


class DropOnlyOwnDirTest(PlankRunSandbox):

    def test_ac3_only_own_dir_dropped_on_green_red_and_exception(self):
        """Выкладка убирается на любом исходе, исторические каталоги на месте.

        Сценарий: в `tests_writing` (черновик) и в `in_dev` (планка ссылки)
        `plank-run` гоняет зелёную планку, красную планку и прогон, на
        вызове pytest которого поднято исключение. Каждый раз во время
        вызова pytest планка выложена, а после команды каталога задачи в
        рабочей копии нет, все отслеживаемые исторические каталоги `tasks`
        на месте с прежним текстом, `git status` рабочей копии по `tasks`
        пуст.

        Ловит мутацию: уборка выкладки — `shutil.rmtree` всего каталога
        `tasks` рабочей копии вместо каталога своей задачи (случаи
        03.10.2026) — исторические файлы пропадают, `git status` называет
        их удалёнными; уборка стоит после прогона, а не в `finally` — после
        исключения каталог задачи остаётся в рабочей копии.
        """
        outcomes = (("зелёный", PASSING.format(name="green"), None),
                    ("красный", FAILING.format(name="red"), None),
                    ("исключение", PASSING.format(name="raised"),
                     RuntimeError(f"сбой прогона {self.seed}")))
        for state in ("tests_writing", "in_dev"):
            for label, text, raised in outcomes:
                with self.subTest(state=state, outcome=label):
                    files = {f"test_{self.word().lower()}_plank.py": text}
                    if state == "tests_writing":
                        shutil.rmtree(self.docs_dir / "acceptance_tests",
                                      ignore_errors=True)
                        self.write_draft(files)
                    else:
                        self.commit_fixed_plank(files)
                    self.set_state(state)
                    self.pytest_calls = []
                    self.raise_in_pytest = raised
                    try:
                        _status, output = self.plank_run()
                    except Exception as exc:  # исключение прогона наружу — законно
                        output = f"исключение наружу: {exc!r}"
                    finally:
                        self.raise_in_pytest = None
                    self.assertEqual(len(self.pytest_calls), 1,
                                     f"pytest не запущен; {self.explain(output)}")
                    self.assertTrue(self.pytest_calls[0][2],
                                    f"во время прогона планки нет; "
                                    f"{self.explain(output)}")
                    self.assert_only_own_dir_dropped(output)


class RoleProcessTest(PlankRunSandbox):

    def snapshot(self) -> tuple:
        row = dict(store.get_task(self.conn, FIXTURE_TASK))
        steps = [dict(r) for r in store.task_steps(self.conn, FIXTURE_TASK)]
        ref = self.git("rev-parse", f"refs/artifacts/{FIXTURE_TASK}").strip()
        branch = self.git("rev-parse", f"refs/heads/{FIXTURE_BRANCH}").strip()
        return row, steps, ref, branch

    def test_ac4_role_process_runs_without_changing_task_state(self):
        """Процесс роли исполняет `plank-run`, состояние задачи не меняется.

        Сценарий: в окружении шага роли — маркер `ARTEL_ROLE` со случайной
        ролью и HOME дома роли без маркера — задача в `in_dev` и в
        `tests_writing` с планкой; `plank-run` доходит до вызова pytest,
        текста отказа роли в выводе нет; строка задачи в БД (все поля),
        журнал шагов задачи, голова ссылки документов и голова ветки задачи
        до и после прогона совпадают.

        Ловит мутацию: `plank-run` не внесена в перечень команд роли —
        отказ «команда недоступна процессу роли», pytest не запускается;
        прогон пишет запись журнала о себе или перефиксирует ссылку
        (`record_fixation`/`set_state`) — журнал или строка задачи после
        прогона отличаются.
        """
        self.commit_fixed_plank({"test_role_plank.py": PASSING.format(name="role")})
        self.write_draft({"test_role_plank.py": PASSING.format(name="role_draft")})
        role = f"role_{self.word().lower()}"
        variants = (("маркер", {config.ARTEL_ROLE_ENV: role}),
                    ("HOME роли", {"HOME": str(config.ROLE_HOME)}))
        for state in ("in_dev", "tests_writing"):
            self.set_state(state)
            for name, env in variants:
                with self.subTest(state=state, variant=name):
                    before = self.snapshot()
                    self.pytest_calls = []
                    with mock.patch.dict(os.environ, env):
                        if name == "HOME роли":
                            os.environ.pop(config.ARTEL_ROLE_ENV, None)
                        _status, output = self.plank_run()
                    self.assertNotIn(ROLE_REFUSAL, output, self.explain(output))
                    self.assertEqual(len(self.pytest_calls), 1,
                                     f"pytest под ролью не запущен; "
                                     f"{self.explain(output)}")
                    after = self.snapshot()
                    for label, a, b in zip(("строка задачи", "журнал шагов",
                                            "ссылка документов", "ветка задачи"),
                                           before, after):
                        self.assertEqual(a, b, f"{label} изменена прогоном; "
                                               f"{self.explain(output)}")


class NoPlankTest(PlankRunSandbox):

    def test_ac5_no_plank_refuses_without_layout_or_pytest(self):
        """Задача без планки — именованный отказ «планки нет».

        Сценарий: `tests_writing` без черновика в каталоге документов и без
        планки в ссылке; `in_dev` без файлов планки в ссылке документов, хотя
        на диске каталога документов лежит устаревший файл. Оба раза
        команда завершается ненулевым кодом, вывод называет «планки нет»,
        pytest не вызывался, каталога задачи в рабочей копии кода нет.

        Ловит мутацию: отсутствие планки не отличается от пустого прогона —
        pytest запускается на пустом каталоге и команда выходит кодом 0
        (или 5 pytest без текста отказа); вне `tests_writing` источником
        служит диск каталога документов — устаревший файл выложен и
        прогнан.
        """
        for state in ("tests_writing", "in_dev"):
            with self.subTest(state=state):
                shutil.rmtree(self.docs_dir / "acceptance_tests",
                              ignore_errors=True)
                if state == "in_dev":
                    self.write_draft({"test_stale_plank.py":
                                      PASSING.format(name="stale")})
                self.set_state(state)
                self.pytest_calls = []
                status, output = self.plank_run()
                self.assertNotEqual(status, 0, self.explain(output))
                self.assertIn("планки нет", output, self.explain(output))
                self.assertEqual(self.pytest_calls, [], self.explain(output))
                self.assertFalse(self.own_dir.exists(), self.explain(output))


class MissionNamesPlankRunTest(unittest.TestCase):

    def test_ac8_docs_dir_note_names_plank_run_without_copytree(self):
        """Абзац миссии о каталоге документов называет `plank-run`.

        Сценарий: `role_prompt.docs_dir_note` для нескольких случайных id и
        каталогов документов — текст содержит `plank-run` и не содержит
        указания копировать планку (`copytree`).

        Ловит мутацию: миссия по-прежнему велит
        `shutil.copytree(... acceptance_tests ...)` — в тексте `copytree`;
        абзац о прогоне планки снят целиком — `plank-run` в тексте нет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for _ in range(5):
            task_id = "01M" + "".join(rng.choice(LETTERS) for _ in range(23))
            docs = Path(f"/tmp/docs_{rng.randrange(1 << 30):x}") / task_id
            text = role_prompt.docs_dir_note(task_id, docs)
            self.assertIn("plank-run", text, f"зерно: {seed}; {text}")
            self.assertNotIn("copytree", text, f"зерно: {seed}; {text}")


if __name__ == "__main__":
    unittest.main()
