"""Сквозной путь «шаг test_author → чекпоинт → advance» для долгоживущего
файла `tests/` (SPEC 01M3NMHHAMTFN2BNKBN209E15M, требования 1-3; ADR-0020).

`tests/test_long_lived_manifest.py` и `tests/test_long_lived_transitions.py`
проверяют узлы по отдельности; здесь — связка целиком: подменённый агент
шага (`runner.spawn_agent`, `tests/sandbox.py`) пишет файл в `tests/`
рабочей копии задачи, дальше штатный `runner.cmd_run` (чекпоинт успешного
шага, автокоммит артефактов) и `fsm.cmd_advance` на настоящем git:
пульт с артефактной веткой, bare `origin`, worktree кодовой ветки
(`tests/test_timeout_checkpoint.py::_WorktreeCheckpointTest`). Гейты
перехода не подменяются.

Отдельно — записи журнала о выходе чекпоинта test_author без коммита
(`orchestrator/checkpoint.py::_test_author_checkpoint`, дефект А).
"""
import hashlib
import io
import random
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, checkpoint, config, fsm,  # noqa: E402
                          gitcmd, runner, store)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from tests.sandbox import FakeProc, is_claude_call  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402

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

# Проходит статические проверки задачи 01M3N0BWYQ9KHVN41Z4G72706R (строка
# группы, «Ловит мутацию» у каждого метода, зерно печатается); методы
# покрывают оба AC SPEC песочницы.
LONG_LIVED_SOURCE = '''"""Долгоживущий файл фикстуры.

Группа: долгоживущий
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_fixture_sum(self):
        """Ловит мутацию: фикстура — сумма {tag} перестаёт совпадать."""
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        self.assertEqual(seed + 1, 1 + seed, f"зерно: {{seed}}")

    def test_ac2_fixture_product(self):
        """Ловит мутацию: фикстура — произведение перестаёт совпадать."""
        seed = random.randrange(1 << 30)
        print(f"зерно: {{seed}}")
        self.assertEqual(seed * 2, 2 * seed, f"зерно: {{seed}}")
'''

TRACE_REFUSAL = "переход отклонён: трассируемость AC"
LONG_LIVED_REFUSAL = "переход отклонён: долгоживущие файлы tests/"
MANIFEST_WRITTEN = "перечень долгоживущих тестов записан"

VARIANTS = (("(а) файл только в рабочей копии", False),
            ("(б) файл закоммичен агентом", True))


class _StepSandbox(_WorktreeCheckpointTest):
    """Задача target `artel` в `tests_writing`, SPEC (AC-1, AC-2) — в
    артефактной ветке; в `acceptance_tests/` покрытия нет вовсе."""

    def setUp(self):
        super().setUp()
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": SPEC_TEXT.format(task=self.TASK)},
            f"{self.TASK}: SPEC")
        store.update_task(store.db(), self.TASK, state="tests_writing")
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"

    def wt_git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.wt), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid", *args],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def reset_task(self) -> None:
        self.wt_git("reset", "-q", "--hard", self.base_sha)
        self.wt_git("clean", "-q", "-fd", "--", "tests")
        store.update_task(store.db(), self.TASK, state="tests_writing",
                          tests_locked_sha=None)

    def spawn(self, rel: str, text: str, commit: bool):
        """Агент шага test_author: пишет `rel` в свой рабочий каталог, при
        `commit` — ещё и коммитит его сам; `acceptance_tests/` оставляет
        без единого покрытия AC. Прочие процессы (git) — настоящие."""
        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            cwd = Path(kwargs.get("cwd") or self.wt)
            plank = artifact_branch.docs_dir(self.TASK, config.DEFAULT_TARGET) / "acceptance_tests"
            plank.mkdir(parents=True, exist_ok=True)
            (plank / "__init__.py").write_text("", encoding="utf-8")
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_text(text, encoding="utf-8")
            if commit:
                for args_ in (("add", "--", rel),
                              ("commit", "-q", "-m", "test_author: тест")):
                    subprocess.run(
                        ["git", "-C", str(cwd), "-c", "user.name=agent",
                         "-c", "user.email=agent@example.invalid", *args_],
                        check=True, capture_output=True)
            return FakeProc(["готово\n"])
        return spawn

    def step_and_advance(self, rel: str, text: str,
                         commit: bool) -> tuple[list[str], str]:
        """(действия журнала с начала шага, журнал и печать текстом)."""
        before = len(store.task_steps(store.db(), self.TASK))
        buf = io.StringIO()
        with redirect_stdout(buf):
            with mock.patch.object(runner, "spawn_agent",
                                   side_effect=self.spawn(rel, text, commit)):
                try:
                    runner.cmd_run(self.TASK)
                except SystemExit as exc:
                    buf.write(f"\nSystemExit(run): {exc}")
            try:
                fsm.cmd_advance(self.TASK)
            except SystemExit as exc:
                buf.write(f"\nSystemExit(advance): {exc}")
        rows = store.task_steps(store.db(), self.TASK)[before:]
        text_ = "\n".join(f"{r['action']} {r['detail'] or ''}" for r in rows)
        return [r["action"] for r in rows], f"{text_}\n{buf.getvalue()}"

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def head_bytes(self, rel: str) -> bytes | None:
        head = gitcmd.branch_head_sha(self.branch)
        res = subprocess.run(["git", "-C", str(config.ROOT), "show",
                              f"{head}:{rel}"], capture_output=True)
        return res.stdout if res.returncode == 0 else None


class LongLivedStepToInDevTest(_StepSandbox):

    def test_prefixed_file_counts_after_checkpoint_and_advance(self):
        """Файл с префиксом задачи покрывает все AC; `acceptance_tests/`
        пуст. В обоих вариантах AC-1 — (а) файл только в рабочей копии,
        (б) агент закоммитил его сам — после шага и `advance`: файл на
        голове кодовой ветки (в (а) голова отлична от базы), задача в
        `in_dev`, отказа трассируемости нет, журнал несёт «перечень
        долгоживущих тестов записан», а перечень в ветке документов —
        строку «<sha256 байтов головы>␣␣<путь>».

        Ловит мутацию: трассируемость не читает долгоживущие файлы кодовой
        ветки — отказ «нет теста».
        """
        seed = random.randrange(1 << 30)
        for label, commit in VARIANTS:
            with self.subTest(variant=label):
                self.reset_task()
                actions, text = self.step_and_advance(
                    self.own, LONG_LIVED_SOURCE.format(tag=seed), commit)
                text = f"зерно: {seed}\n{text}"
                blob = self.head_bytes(self.own)
                self.assertIsNotNone(blob, f"файла нет на голове: {text}")
                if not commit:
                    self.assertNotEqual(gitcmd.branch_head_sha(self.branch),
                                        self.base_sha, text)
                self.assertNotIn(TRACE_REFUSAL, actions, text)
                self.assertEqual(self.state(), "in_dev", text)
                self.assertIn(MANIFEST_WRITTEN, actions, text)
                manifest, reason = gitcmd.show(
                    artifact_branch.branch_name(self.TASK),
                    acceptance_gates.long_lived_manifest_rel(self.TASK))
                self.assertIsNotNone(manifest, f"{reason}\n{text}")
                self.assertIn(f"{hashlib.sha256(blob).hexdigest()}  {self.own}",
                              manifest.splitlines(), text)

    def test_unprefixed_file_keeps_tests_writing(self):
        """Тот же файл без префикса задачи (`tests/test_alpha_fixture.py`)
        в обоих вариантах: задача остаётся в `tests_writing`, журнал несёт
        отказ трассируемости AC либо гейта «только добавление» (SPEC
        01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ).

        Ловит мутацию: правило имени без префикса задачи — любой
        `tests/test_*.py` засчитан долгоживущим файлом задачи, и чужой файл
        уводит задачу в `in_dev`.
        """
        seed = random.randrange(1 << 30)
        for label, commit in VARIANTS:
            with self.subTest(variant=label):
                self.reset_task()
                actions, text = self.step_and_advance(
                    "tests/test_alpha_fixture.py",
                    LONG_LIVED_SOURCE.format(tag=seed), commit)
                text = f"зерно: {seed}\n{text}"
                self.assertEqual(self.state(), "tests_writing", text)
                self.assertTrue({TRACE_REFUSAL, LONG_LIVED_REFUSAL} & set(actions),
                                text)


class TestAuthorCheckpointNotCommittedJournalTest(_StepSandbox):

    def journal_text(self) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))

    def test_git_silence_on_own_paths_is_journaled(self):
        """git не ответил на базу ветки при отборе своих путей: чекпоинт
        успешного шага не коммитит и не трогает файл, но журнал несёт
        «долгоживущие тесты не закоммичены пультом».

        Ловит мутацию: выход `_test_author_own_paths` → `None` снова тихий —
        записи в журнале нет, отказ «AC-n: нет теста» на `advance` не
        объясним по журналу.
        """
        self.write_code_file(self.own, LONG_LIVED_SOURCE.format(tag=1))
        with mock.patch.object(checkpoint.gitcmd, "diff_base", return_value=None):
            checkpoint.commit_success_checkpoint(store.db(), self.TASK,
                                                 "test_author")
        self.assertEqual(gitcmd.branch_head_sha(self.branch), self.base_sha)
        self.assertTrue((self.wt / self.own).exists())
        self.assertIn(checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION,
                      self.journal_text())

    def test_rejected_commit_is_journaled_with_paths(self):
        """Хук `pre-commit` отказывает коммиту: голова кодовой ветки
        прежняя, файл на диске, журнал несёт «долгоживущие тесты не
        закоммичены пультом» с путём файла.

        Ловит мутацию: выход по `not committed` в `_test_author_checkpoint`
        снова тихий — записи с путём нет.
        """
        hooks = Path(self.git("rev-parse", "--git-common-dir").strip())
        if not hooks.is_absolute():
            hooks = config.ROOT / hooks
        hook = hooks / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        self.addCleanup(hook.unlink)
        self.write_code_file(self.own, LONG_LIVED_SOURCE.format(tag=2))
        checkpoint.commit_success_checkpoint(store.db(), self.TASK, "test_author")
        self.assertEqual(gitcmd.branch_head_sha(self.branch), self.base_sha)
        self.assertTrue((self.wt / self.own).exists())
        journal = self.journal_text()
        self.assertIn(checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION, journal)
        self.assertIn(self.own, journal)


if __name__ == "__main__":
    unittest.main()
