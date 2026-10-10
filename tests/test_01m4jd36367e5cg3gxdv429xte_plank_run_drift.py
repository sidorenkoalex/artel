"""`plank-run` не стирает молча незафиксированную правку планки в рабочей копии кода.

Группа: долгоживущий

Красен до реализации: `plank-run` выкладывает зафиксированную планку поверх правки Оператора в каталоге задачи рабочей копии, прогоняет её и убирает каталог — отказа до pytest нет, правка стёрта (AC-6); AC-7 (без расхождения — прогон, как сегодня) держит существующее поведение и зелёный.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): репозиторий
пульта с bare `origin`, задача target по умолчанию в `in_dev` с рабочей
копией кода (`workspace.ensure`). Ссылка документов задачи — символическая
ссылка на обычную ветку (`tests/sandbox.py::alias_docs_ref_to_branch`), её
коммиты ведёт отдельный git-worktree песочницы; в ней зафиксирована планка
из двух зелёных файлов (имена — от зерна). Команда зовётся через
`artel.main()`; наблюдатель `subprocess.run` пропускает каждый вызов в
настоящий и считает вызовы pytest. Вид расхождения и имена файлов — из
`random`, зерно печатается и входит в текст провала.
"""
import io
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, store, workspace
from tests.sandbox import RealGitSandbox, alias_docs_ref_to_branch

FIXTURE_TASK = "01M0000000000000000000DRFT"
FIXTURE_BRANCH = "task/fixture-plank-run-drift"
LETTERS = "abcdefghjkmnpqrstvwxyz"

PASSING = "def test_{name}():\n    assert True\n"


def is_pytest_call(cmd) -> bool:
    argv = [str(a) for a in cmd] if isinstance(cmd, (list, tuple)) else []
    return any(argv[i] == "-m" and argv[i + 1] == "pytest"
               for i in range(len(argv) - 1))


class PlankRunDriftSandbox(RealGitSandbox):
    """Задача в `in_dev` с рабочей копией кода и зафиксированной планкой в
    ссылке документов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        self.conn = store.db()
        store.insert_task(self.conn, FIXTURE_TASK, "Фикстура plank-run",
                          "in_dev", FIXTURE_BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(FIXTURE_TASK, FIXTURE_BRANCH)
        self.assertIsNone(error, f"рабочая копия кода не заведена: {error}")
        self.wt = wt
        self.own_dir = self.wt / "tasks" / FIXTURE_TASK
        self.plank_dir = self.own_dir / "acceptance_tests"
        self.docs_wt = None
        words = [self.word()]
        while len(words) < 2:
            word = self.word()
            if word not in words:
                words.append(word)
        self.fixed = {f"test_{w}.py": PASSING.format(name=w) for w in words}
        self.commit_docs({"SPEC.md": "---\ntask: x\ntype: spec\n---\n# SPEC\n",
                          **{f"acceptance_tests/{n}": t
                             for n, t in self.fixed.items()}})
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pytest_calls = []
        real_run = subprocess.run

        def observed_run(cmd, *args, **kwargs):
            if is_pytest_call(cmd):
                self.pytest_calls.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        patcher = mock.patch.object(subprocess, "run", observed_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- фикстуры ---------------------------------------------------------

    def word(self, size: int = 8) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def commit_docs(self, files: dict) -> None:
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
        self.git("-C", str(self.docs_wt), "add", "-A")
        self.git("-C", str(self.docs_wt), "commit", "-q", "-m", "документы")
        store.record_fixation(self.conn, FIXTURE_TASK)

    def write_plank_copy(self, files: dict) -> None:
        """Файлы в каталог планки задачи рабочей копии кода."""
        self.plank_dir.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (self.plank_dir / name).write_text(text, encoding="utf-8")

    def disk_bytes(self) -> dict:
        if not self.plank_dir.is_dir():
            return {}
        return {p.relative_to(self.plank_dir).as_posix(): p.read_bytes()
                for p in sorted(self.plank_dir.rglob("*")) if p.is_file()
                and "__pycache__" not in p.parts}

    # --- прогон команды -----------------------------------------------------

    def plank_run(self) -> tuple:
        """(код выхода, весь вывод) `artel.py plank-run <id>`."""
        argv = ["artel.py", "plank-run", FIXTURE_TASK]
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

    def explain(self, variant: str, output: str) -> str:
        return (f"зерно: {self.seed}; вариант «{variant}»; вывод plank-run:\n"
                f"{output[-3000:]}")


class DriftRefusedTest(PlankRunDriftSandbox):

    def test_ac6_diverging_plank_file_refused_before_pytest(self):
        """Файл каталога планки рабочей копии расходится со ссылкой — отказ до pytest, файл цел.

        Сценарий: в каталоге планки задачи рабочей копии кода лежит
        зафиксированная планка, и один файл в ней расходится со ссылкой
        документов — изменён (какой из двух — случайно) либо добавлен новый
        (имя — от зерна); варианты перебираются оба. `plank-run` завершается
        ненулевым кодом, pytest не запускался ни разу, вывод называет
        расходящийся файл по имени и содержит `amend-tests`; после отказа
        каталог планки на диске побайтно тот же, что до вызова.

        Ловит мутацию: сверка расхождения не добавлена — `plank-run`
        выкладывает зафиксированную планку поверх правки, запускает pytest и
        убирает каталог (вызов pytest есть, файла правки на диске нет);
        сверка идёт только по набору имён — изменённый файл с тем же именем
        не отказывает; отказ не называет файл или не подсказывает
        `amend-tests`.
        """
        for variant in ("изменённый", "новый"):
            with self.subTest(variant=variant):
                self.pytest_calls = []
                shutil.rmtree(self.own_dir, ignore_errors=True)
                self.write_plank_copy(self.fixed)
                if variant == "изменённый":
                    name = self.rng.choice(sorted(self.fixed))
                    text = self.fixed[name] + f"\n# правка Оператора {self.seed}\n"
                else:
                    name = f"test_{self.word()}_new.py"
                    text = PASSING.format(name=f"new_{self.seed}")
                self.write_plank_copy({name: text})
                before = self.disk_bytes()

                status, output = self.plank_run()

                self.assertNotEqual(status, 0, self.explain(variant, output))
                self.assertEqual(self.pytest_calls, [], (
                    f"pytest запущен при расхождении; {self.explain(variant, output)}"))
                self.assertIn(name, output, (
                    f"отказ не называет файл {name}; {self.explain(variant, output)}"))
                self.assertIn("amend-tests", output, (
                    f"отказ не подсказывает amend-tests; {self.explain(variant, output)}"))
                self.assertEqual(self.disk_bytes(), before, (
                    f"каталог планки изменён отказом; {self.explain(variant, output)}"))


class NoDriftRunsTest(PlankRunDriftSandbox):

    def test_ac7_no_drift_lays_out_and_runs_plank(self):
        """Без расхождения `plank-run` выкладывает и прогоняет планку, итог напечатан.

        Сценарий: каталога планки в рабочей копии кода нет либо в нём лежат
        ровно файлы зафиксированной планки с тем же содержимым; варианты
        перебираются оба. `plank-run` завершается кодом 0, pytest запущен
        ровно раз, вывод несёт итог pytest «2 passed».

        Ловит мутацию: сверка расхождения считает расхождением любой
        непустой каталог планки (или сравнивает с пустым набором) — вариант
        с совпадающими файлами отказывает без прогона; сверка не различает
        «каталога нет» и падает на отсутствующем каталоге.
        """
        for variant in ("каталога нет", "совпадает со ссылкой"):
            with self.subTest(variant=variant):
                self.pytest_calls = []
                shutil.rmtree(self.own_dir, ignore_errors=True)
                if variant == "совпадает со ссылкой":
                    self.write_plank_copy(self.fixed)

                status, output = self.plank_run()

                self.assertEqual(status, 0, self.explain(variant, output))
                self.assertEqual(len(self.pytest_calls), 1, (
                    f"pytest запущен не ровно раз; {self.explain(variant, output)}"))
                self.assertIn("2 passed", output, self.explain(variant, output))


if __name__ == "__main__":
    unittest.main()
