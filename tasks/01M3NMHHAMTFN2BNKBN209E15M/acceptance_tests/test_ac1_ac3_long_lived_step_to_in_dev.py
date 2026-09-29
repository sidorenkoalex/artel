"""Сквозной путь «шаг test_author → чекпоинт → advance» для долгоживущего
файла `tests/` с префиксом задачи (SPEC 01M3NMHHAMTFN2BNKBN209E15M,
AC-1, AC-2, AC-3).

Группа: разовый
Зелёный с рождения: песочница пульта на настоящем git проходит путь «runner.cmd_run → чекпоинт → advance» и на коде до задачи — условие канарейки, при котором файл теряется, здесь не воспроизводится (место дефектов А/Б устанавливает разработчик по диагностике, AC-6); планка держит наблюдаемое свойство AC-1…AC-3 после исправления, чувствительность проверена мутацией трассируемости (6 методов/подтестов краснеют).

Почему разовый, хотя предмет — поведение кода: планка подменяет приватные
гейты пульта вне предмета (как `tests/test_long_lived_transitions.py`) и
строится на песочнице `tests/test_git_fixation.py::RealPultGitTest`, а
долгоживущий файл обязан опираться только на публичный интерфейс и
`tests/sandbox.py`. Долгоживущий сторож того же свойства — сквозной тест
разработчика в `tests/` (AC-4/AC-5, его проверяет
`test_ac4_ac5_end_to_end_test_in_tests.py`).

Песочница: пульт на настоящем git с артефактной веткой, bare `origin`,
worktree кодовой ветки задачи target `artel` в `tests_writing`. SPEC несёт
AC-1 и AC-2; в `acceptance_tests/` покрытия нет вовсе — оба критерия
покрыты ТОЛЬКО методами `test_ac1_…`/`test_ac2_…` долгоживущего файла.
Шаг агента разыгран записью файла в `tests/` рабочей копии (вариант (а))
либо записью и коммитом самим «агентом» (вариант (б)); затем — публичный
чекпоинт успешного шага `checkpoint.commit_success_checkpoint(…,
"test_author")` (его зовёт `runner` по штатному завершению шага) и
`fsm.cmd_advance`.
"""
import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (artifact_branch, config, fsm, gitcmd,  # noqa: E402
                          runner, store, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from tests.sandbox import FakeProc, is_claude_call  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: песочница

## Контекст

## Требования

## Критерии приёмки

AC-1. Первый критерий песочницы.

AC-2. Второй критерий песочницы.

## Не входит
"""

# Долгоживущий файл фикстуры: строка группы, «Ловит мутацию» у каждого
# метода, зерно random печатается — проходит статические проверки задачи
# 01M3N0BWYQ9KHVN41Z4G72706R; методы покрывают AC-1 и AC-2.
LONG_LIVED_SOURCE = '''"""Фикстура долгоживущего файла.

{group_line}
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_fixture_sum(self):
        """Фикстурный метод первого критерия.

        {claim}
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        self.assertEqual(seed + 1, 1 + seed, f"зерно: {{seed}}")

    def test_ac2_fixture_product(self):
        """Фикстурный метод второго критерия.

        Ловит мутацию: фикстура песочницы — произведение перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        self.assertEqual(seed * 2, 2 * seed, f"зерно: {{seed}}")
'''

GOOD_GROUP = "Группа: долгоживущий"
GOOD_CLAIM = "Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать."

TRACE_REFUSAL = "переход отклонён: трассируемость AC"
LONG_LIVED_REFUSAL = "переход отклонён: долгоживущие файлы tests/"
MANIFEST_WRITTEN = "перечень долгоживущих тестов записан"


def long_lived_source(group_line: str = GOOD_GROUP,
                      claim: str = GOOD_CLAIM) -> str:
    return LONG_LIVED_SOURCE.format(group_line=group_line, claim=claim)


class _StepSandbox(RealPultGitTest):
    """Задача target `artel` в `tests_writing`, кодовая ветка выписана в
    worktree, SPEC (AC-1, AC-2) — в артефактной ветке и в `tasks/<id>/`
    рабочей копии (как материализует пульт на старте шага)."""

    def setUp(self):
        super().setUp()
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(origin))
        self.git("remote", "add", "origin", str(origin))
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "test_existing.py").write_text(
            '"""Файл базы."""\n', encoding="utf-8")
        self.git("add", "tests")
        self.git("commit", "-q", "-m", "база: tests/")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.branch = self.row()["branch"]
        self.wt, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()
        spec = SPEC_TEXT.format(task=self.TASK)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": spec},
            f"{self.TASK}: SPEC")
        store.update_task(store.db(), self.TASK, state="tests_writing")
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"

    def row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.row()["state"]

    def wt_git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.wt), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid", *args],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def last_step_id(self) -> int:
        row = store.db().execute("SELECT MAX(id) AS m FROM steps WHERE task_id=?",
                                 (self.TASK,)).fetchone()
        return row["m"] or 0

    def steps_after(self, step_id: int) -> list[tuple[str, str]]:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? AND id>? "
            "ORDER BY id", (self.TASK, step_id)).fetchall()
        return [(r["action"], r["detail"] or "") for r in rows]

    def agent(self, rel: str, text: str, commit: bool):
        """`runner.spawn_agent` подменённого агента шага test_author: на
        запуске CLI пишет файл в `tests/` своего рабочего каталога (`cwd`
        запуска); `commit` — ещё и коммитит его в кодовую ветку сам.
        Каталог `acceptance_tests/` (обязательный артефакт шага роли)
        агент оставляет без единого покрытия AC — только `__init__.py`.
        Прочие процессы (git) идут настоящими."""
        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            cwd = Path(kwargs.get("cwd") or self.wt)
            self.agent_cwds.append(cwd)
            plank = cwd / "tasks" / self.TASK / "acceptance_tests"
            plank.mkdir(parents=True, exist_ok=True)
            (plank / "__init__.py").write_text("", encoding="utf-8")
            path = cwd / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            staged = subprocess.run(
                ["git", "-C", str(cwd), "status", "--porcelain", "--", rel],
                capture_output=True, text=True).stdout.strip()
            if commit and staged:
                for args_ in (("add", "--", rel),
                              ("commit", "-q", "-m",
                               "test_author: долгоживущий тест")):
                    subprocess.run(
                        ["git", "-C", str(cwd), "-c", "user.name=agent",
                         "-c", "user.email=agent@example.invalid", *args_],
                        check=True, capture_output=True)
            return FakeProc(["готово\n"])
        return spawn

    def step_and_advance(self, rel: str, text: str,
                         commit: bool) -> tuple[list[tuple[str, str]], str]:
        """Шаг test_author через `runner.cmd_run` (чекпоинт успешного шага
        и автокоммит артефактов — штатным путём раннера) → `advance`;
        (записи журнала с начала шага, печать)."""
        before = self.last_step_id()
        self.agent_cwds = []
        buf = io.StringIO()
        with redirect_stdout(buf):
            with mock.patch.object(runner, "spawn_agent",
                                   side_effect=self.agent(rel, text, commit)):
                try:
                    runner.cmd_run(self.TASK)
                except SystemExit as exc:
                    buf.write(f"\nSystemExit(run): {exc}")
            try:
                fsm.cmd_advance(self.TASK)
            except SystemExit as exc:
                buf.write(f"\nSystemExit(advance): {exc}")
        self.assertTrue(self.agent_cwds,
                        f"агент шага не запускался: {buf.getvalue()}")
        return self.steps_after(before), buf.getvalue()

    @staticmethod
    def render(steps, out: str) -> str:
        return "\n".join(f"{a} {d}" for a, d in steps) + "\n" + out

    def head_bytes(self, rel: str) -> bytes | None:
        head = gitcmd.branch_head_sha(self.branch)
        res = subprocess.run(["git", "-C", str(self.root), "show",
                              f"{head}:{rel}"], capture_output=True)
        return res.stdout if res.returncode == 0 else None


VARIANTS = (("(а) файл только в рабочей копии", False),
            ("(б) файл закоммичен агентом", True))


class LongLivedFileCoversAcTest(_StepSandbox):

    def run_variant(self, commit: bool):
        return self.step_and_advance(self.own, long_lived_source(), commit)

    def test_ac1_worktree_only_file_committed_and_counted(self):
        """Вариант (а): агент оставил долгоживущий файл незакоммиченным.

        После чекпоинта голова кодовой ветки отлична от базы и несёт файл;
        после `advance` задача в `in_dev`, в журнале шага нет отказа
        «трассируемость AC».

        Ловит мутацию: чекпоинт test_author тихо выходит без коммита
        (`_test_author_own_paths` вернул `None`/коммит не состоялся) — голова
        кодовой ветки равна базе, трассируемость отказывает «AC-1: нет теста».
        """
        steps, out = self.run_variant(commit=False)
        text = self.render(steps, out)
        head = gitcmd.branch_head_sha(self.branch)
        self.assertNotEqual(head, self.base_sha,
                            f"чекпоинт не закоммитил файл: {text}")
        self.assertIsNotNone(self.head_bytes(self.own),
                             f"файла нет на голове кодовой ветки: {text}")
        self.assertEqual(self.state(), "in_dev", text)
        self.assertNotIn(TRACE_REFUSAL, [a for a, _ in steps], text)

    def test_ac1_agent_committed_file_counted(self):
        """Вариант (б): агент сам закоммитил долгоживущий файл до конца шага.

        После чекпоинта и `advance` задача в `in_dev`, отказа «трассируемость
        AC» в журнале шага нет.

        Ловит мутацию: трассируемость не получает тексты долгоживущих файлов
        головы кодовой ветки (`long_lived_sources` пуст) — отказ «AC-1: нет
        теста», задача остаётся в `tests_writing`.
        """
        steps, out = self.run_variant(commit=True)
        text = self.render(steps, out)
        self.assertIsNotNone(self.head_bytes(self.own), text)
        self.assertEqual(self.state(), "in_dev", text)
        self.assertNotIn(TRACE_REFUSAL, [a for a, _ in steps], text)

    def test_ac2_manifest_written_in_same_advance(self):
        """В обоих вариантах AC-1 тот же `advance` пишет перечень.

        `long_lived.sha256.txt` в ветке документов несёт строку
        «<sha256 байтов файла на голове кодовой ветки>␣␣<путь>», в журнале
        шага — «перечень долгоживущих тестов записан».

        Ловит мутацию: гейт перечня получает пустой список путей (файл не
        дошёл до `long_lived`) — перечень пуст, строки файла в нём нет.
        """
        for label, commit in VARIANTS:
            with self.subTest(variant=label):
                if commit:
                    self.reset_task()
                steps, out = self.run_variant(commit=commit)
                text = self.render(steps, out)
                self.assertEqual(self.state(), "in_dev", text)
                self.assertIn(MANIFEST_WRITTEN, [a for a, _ in steps], text)
                blob = self.head_bytes(self.own)
                self.assertIsNotNone(blob, text)
                manifest, reason = gitcmd.show(
                    artifact_branch.branch_name(self.TASK),
                    acceptance_gates.long_lived_manifest_rel(self.TASK))
                self.assertIsNotNone(manifest, f"перечня нет: {reason}\n{text}")
                line = f"{hashlib.sha256(blob).hexdigest()}  {self.own}"
                self.assertIn(line, manifest.splitlines(), text)

    def reset_task(self) -> None:
        """Возврат кодовой ветки к базе и задачи в `tests_writing` между
        вариантами одного метода."""
        self.wt_git("reset", "-q", "--hard", self.base_sha)
        self.wt_git("clean", "-q", "-fd", "--", "tests")
        store.update_task(store.db(), self.TASK, state="tests_writing",
                          tests_locked_sha=None)


class BrokenLongLivedFileRefusedTest(_StepSandbox):

    BROKEN = {
        "без строки «Группа: долгоживущий»":
            lambda: long_lived_source(group_line="Фикстура без группы."),
        "метод без «Ловит мутацию»":
            lambda: long_lived_source(claim="Метод без заявки."),
    }

    def test_ac3_broken_file_refused_as_before(self):
        """Файл с префиксом задачи тем же путём, но нарушающий проверки
        задачи 01M3N0BWYQ9KHVN41Z4G72706R, в обоих вариантах AC-1.

        Выход из `tests_writing` отклонён отказом «долгоживущие файлы
        tests/», называющим путь; задача остаётся в `tests_writing`.

        Ловит мутацию: починка засчитывает файл трассируемостью в обход
        гейта долгоживущих файлов (или гейт видит пустой дифф) — файл без
        строки группы или без заявки мутации уходит в `in_dev`.
        """
        for (label, make) in self.BROKEN.items():
            for vlabel, commit in VARIANTS:
                with self.subTest(broken=label, variant=vlabel):
                    self.wt_git("reset", "-q", "--hard", self.base_sha)
                    self.wt_git("clean", "-q", "-fd", "--", "tests")
                    store.update_task(store.db(), self.TASK,
                                      state="tests_writing",
                                      tests_locked_sha=None)
                    steps, out = self.step_and_advance(self.own, make(), commit)
                    text = self.render(steps, out)
                    self.assertEqual(self.state(), "tests_writing", text)
                    refusals = [d for a, d in steps if a == LONG_LIVED_REFUSAL]
                    self.assertTrue(refusals, f"нет отказа гейта: {text}")
                    self.assertIn(self.own, refusals[-1], text)


if __name__ == "__main__":
    unittest.main()
