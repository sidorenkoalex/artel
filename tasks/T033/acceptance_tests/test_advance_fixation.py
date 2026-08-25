"""Приёмочные тесты T033: advance по зафиксированному состоянию (AC-1..AC-9).

Источник — tasks/T033/SPEC.md, раздел «Критерии приёмки». Песочница для
AC-1..AC-7 — настоящий git-репозиторий (тот же приём, что и
`RealPultGitTest` в tests/test_git_fixation.py, T021): сверка чистоты
рабочей копии — это её реальное git-состояние (staged/unstaged/untracked),
заглушкой `gitcmd.git` его не подделать. AC-8/AC-9 читают реальный
репозиторий/main напрямую, без песочницы.
"""
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: T033 приёмка — фиктивная задача песочницы

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: T033 приёмка — фиктивная задача песочницы

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def review_md(task: str, status: str = "approved", iteration: int = 1) -> str:
    return f"""---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: T033 приёмка — фиктивная задача песочницы

## Соответствие SPEC

## Замечания

## Вердикт
"""


class AdvanceFixationSandbox(unittest.TestCase):
    """Песочница: ROOT — свежий git-репозиторий с веткой main и задачей
    T001 в spec_writing. Заводит артефакты и продвигает FSM по-настоящему
    (commit/advance/approve), чтобы «грязная копия» и «зафиксировано»
    значили то же самое, что и в реальном пульте.
    """

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n# Карта\n",
            encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = []
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("TARGETS", self.root / "targets.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "T033 приёмка")

    # -------------------------------------------------------- утилиты

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def write(self, name: str, template: str) -> None:
        (config.TASKS / self.TASK / name).write_text(
            template.format(task=self.TASK), encoding="utf-8")

    def commit_task_dir(self, message: str = "артефакт") -> None:
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", message)

    def commit_and_advance(self) -> str:
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        return self.head()

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.task_steps(store.db(), self.TASK)]

    # ------------------------------------------------- сборка состояний

    def reach_spec_gate_cleanly(self) -> str:
        self.write("SPEC.md", SPEC_READY)
        return self.commit_and_advance()

    def reach_in_dev_cleanly(self) -> None:
        sha = self.reach_spec_gate_cleanly()
        self.capture(fsm.cmd_approve, self.TASK, sha)

    def reach_review_cleanly(self) -> None:
        self.reach_in_dev_cleanly()
        self.write("PLAN.md", PLAN_READY)
        self.commit_and_advance()


class Ac1SpecWritingTest(AdvanceFixationSandbox):
    """AC-1: spec_writing -> spec_gate отказывает по грязной копии."""

    def test_ac1_dirty_spec_blocks_spec_writing_to_spec_gate(self):
        self.write("SPEC.md", SPEC_READY)  # написан, но НЕ закоммичен

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_writing",
                         "переход не должен был случиться по грязной копии")
        self.assertIn("SPEC.md", out)
        self.assertIn("не закоммичен", out)


class Ac2InDevTest(AdvanceFixationSandbox):
    """AC-2: in_dev -> review отказывает по тому же условию грязной копии."""

    def test_ac2_dirty_plan_blocks_in_dev_to_review(self):
        self.reach_in_dev_cleanly()
        self.write("PLAN.md", PLAN_READY)  # написан, но НЕ закоммичен

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev",
                         "переход не должен был случиться по грязной копии")
        self.assertIn("PLAN.md", out)
        self.assertIn("не закоммичен", out)


class Ac3ReviewTest(AdvanceFixationSandbox):
    """AC-3: переход из review (в acceptance/in_dev/escalated по вердикту)
    отказывает по тому же условию грязной копии — для любого вердикта."""

    def test_ac3_dirty_review_blocks_transition_for_each_verdict(self):
        self.reach_review_cleanly()

        for verdict in ("approved", "changes_requested", "escalate"):
            with self.subTest(вердикт=verdict):
                self.write("REVIEW.md", review_md(self.TASK, verdict))
                # написан, но НЕ закоммичен

                out = self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), "review",
                                 "переход не должен был случиться по "
                                 "грязной копии")
                self.assertIn("REVIEW.md", out)
                self.assertIn("не закоммичен", out)


class Ac4RefusalNamesTheArtifactTest(AdvanceFixationSandbox):
    """AC-4: причина отказа называет конкретный артефакт перехода и
    формулировку вида «<файл> не закоммичен — роль обязана коммитить
    артефакты (скил conventions-core); закоммить и повтори advance»."""

    @staticmethod
    def expected_message(name: str) -> str:
        return (f"{name} не закоммичен — роль обязана коммитить артефакты "
                f"(скил conventions-core); закоммить и повтори advance")

    def test_ac4_refusal_message_names_spec_plan_and_review_in_turn(self):
        # SPEC.md, spec_writing -> spec_gate
        self.write("SPEC.md", SPEC_READY)
        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertIn(self.expected_message("SPEC.md"), out)
        sha = self.commit_and_advance()
        self.capture(fsm.cmd_approve, self.TASK, sha)

        # PLAN.md, in_dev -> review
        self.write("PLAN.md", PLAN_READY)
        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertIn(self.expected_message("PLAN.md"), out)
        self.commit_and_advance()

        # REVIEW.md, review -> acceptance/in_dev/escalated
        self.write("REVIEW.md", review_md(self.TASK))
        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertIn(self.expected_message("REVIEW.md"), out)


class Ac5RefusalIsNotEscalationTest(AdvanceFixationSandbox):
    """AC-5: отказ — не эскалация (state не меняется), после коммита
    повторный advance продвигает задачу штатно, как и до этой задачи."""

    def test_ac5_state_unchanged_then_recovers_after_commit(self):
        # spec_writing
        before = self.state()
        self.write("SPEC.md", SPEC_READY)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), before)
        self.assertNotEqual(self.state(), "escalated")

        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "spec_gate",
                         "после коммита повторный advance продвигает штатно")
        sha = self.head()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(self.state(), "in_dev")

        # in_dev
        before = self.state()
        self.write("PLAN.md", PLAN_READY)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), before)
        self.assertNotEqual(self.state(), "escalated")

        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review",
                         "после коммита повторный advance продвигает штатно")

        # review
        before = self.state()
        self.write("REVIEW.md", review_md(self.TASK, "approved"))
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), before)
        self.assertNotEqual(self.state(), "escalated")

        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance",
                         "после коммита повторный advance продвигает штатно")


class Ac6RefusalInJournalAndLogTest(AdvanceFixationSandbox):
    """AC-6: причина отказа пишется в журнал задачи и видна в
    `artel.py log <id>` (orchestrator/catalog.py: cmd_log)."""

    def test_ac6_refusal_reason_is_journaled_and_shown_by_log(self):
        self.write("SPEC.md", SPEC_READY)

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details()
        self.assertTrue(
            any("SPEC.md" in d and "не закоммичен" in d for d in details),
            f"причина отказа не найдена в журнале: {details}")

        log_out = self.capture(catalog.cmd_log, self.TASK)
        self.assertIn("SPEC.md", log_out)
        self.assertIn("не закоммичен", log_out)


class Ac7CleanStateUnaffectedTest(AdvanceFixationSandbox):
    """AC-7: поведение advance для чистого состояния не изменилось ни для
    одного из трёх переходов — включая все три ветки вердикта review."""

    def test_ac7_clean_spec_and_plan_still_move_the_task(self):
        sha = self.reach_spec_gate_cleanly()
        self.assertEqual(self.state(), "spec_gate")

        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(self.state(), "in_dev")

        self.write("PLAN.md", PLAN_READY)
        self.commit_and_advance()
        self.assertEqual(self.state(), "review")

    def test_ac7_clean_review_approved_still_moves_to_acceptance(self):
        self.reach_review_cleanly()
        self.write("REVIEW.md", review_md(self.TASK, "approved"))

        self.commit_and_advance()

        self.assertEqual(self.state(), "acceptance")

    def test_ac7_clean_review_changes_requested_still_moves_to_in_dev(self):
        self.reach_review_cleanly()
        self.write("REVIEW.md", review_md(self.TASK, "changes_requested"))

        self.commit_and_advance()

        self.assertEqual(self.state(), "in_dev")

    def test_ac7_clean_review_escalate_still_moves_to_escalated(self):
        self.reach_review_cleanly()
        self.write("REVIEW.md", review_md(self.TASK, "escalate"))

        self.commit_and_advance()

        self.assertEqual(self.state(), "escalated")


# ---------------------------------------------------------------------
# AC-8: тесты покрывают отказ по грязной копии для каждого из трёх типов
# условия отдельно (часть 1 — сама структура Ac1.../Ac2.../Ac3... выше,
# по одному классу-тесту на тип условия) и не ослабляют существующие
# тесты advance (часть 2 — проверка ниже, тот же приём, что
# tasks/T031/acceptance_tests/test_branch_correct_reads.py,
# ExistingTestsNotWeakenedTest, применённый к файлам advance).

TEST_METHOD_DEF = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.M)
SKIP_DECORATED_METHOD = re.compile(
    r"@unittest\.skip\w*\([^)]*\)\s*\n\s*def\s+(test_\w+)\s*\(", re.M)

# «Существующие тесты advance» — файлы, названные в SPEC («Материалы»)
# как проверяющие cmd_advance/фиксацию, которую advance теперь обязан
# сверять (orchestrator/fsm.py cmd_advance; orchestrator/fixation.py —
# образец у approve).
ADVANCE_TEST_FILES = ("tests/test_advance_guard.py", "tests/test_git_fixation.py")


class Ac8ExistingAdvanceTestsNotWeakenedTest(unittest.TestCase):
    """Реальный репозиторий (не песочница) — сравнение файлов текущего
    рабочего дерева с их содержимым на main."""

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_ac8_no_advance_test_method_removed_or_newly_skipped_since_main(self):
        removed: list[str] = []
        newly_skipped: list[str] = []

        for path in ADVANCE_TEST_FILES:
            before = self._git("show", f"main:{path}")
            after_file = REPO_ROOT / path
            self.assertTrue(after_file.exists(), f"{path} удалён")
            after = after_file.read_text(encoding="utf-8")

            missing = (set(TEST_METHOD_DEF.findall(before))
                      - set(TEST_METHOD_DEF.findall(after)))
            if missing:
                removed.append(f"{path}: {sorted(missing)}")

            newly = (set(SKIP_DECORATED_METHOD.findall(after))
                    - set(SKIP_DECORATED_METHOD.findall(before)))
            if newly:
                newly_skipped.append(f"{path}: {sorted(newly)}")

        self.assertEqual(
            removed, [],
            f"тестовые методы advance удалены по сравнению с main "
            f"(SPEC T033 AC-8): {removed}")
        self.assertEqual(
            newly_skipped, [],
            f"тестовые методы advance заскипаны по сравнению с main "
            f"(SPEC T033 AC-8, принцип целостности ADR-0002): {newly_skipped}")


# ---------------------------------------------------------------------
# AC-9: строка беклога «Подметалка minor» лишается предложения про
# асимметрию advance/approve; остальной текст строки не меняется.

REMOVED_SENTENCE = (
    "Из T032: ревьюер может не закоммитить вердикт (миссия требует, "
    "enforcement нет) — advance пропускает переход по грязному "
    "артефакту, approve отказывает: асимметрию закрыть требованием "
    "чистоты и в advance."
)

# T017 открывает вложенную скобку строчной «из» ("... одним проходом
# (из T017: ..."), остальные пункты начинают новое предложение с
# заглавной «Из».
OTHER_BACKLOG_ITEMS = ("из T017:", "Из T018:", "Из T025:", "Из T027:",
                       "Из T031:", "Из T019:")


class Ac9RoadmapBacklogLineTest(unittest.TestCase):
    """Реальный docs/roadmap.md текущего рабочего дерева (эта же задача
    его правит — сверка не с main, а с фактическим содержимым файла)."""

    def line(self) -> str:
        text = (REPO_ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        for raw in text.splitlines():
            if "Подметалка minor" in raw:
                return raw
        self.fail("строка «Подметалка minor» не найдена в docs/roadmap.md")
        return ""

    def test_ac9_t032_asymmetry_sentence_is_removed(self):
        self.assertNotIn(REMOVED_SENTENCE, self.line())

    def test_ac9_other_backlog_items_in_the_same_line_are_untouched(self):
        line = self.line()
        for marker in OTHER_BACKLOG_ITEMS:
            with self.subTest(пункт=marker):
                self.assertIn(marker, line)
        self.assertIn("$15", line)


if __name__ == "__main__":
    unittest.main()
