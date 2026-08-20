"""Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

Реального git и реального CLI здесь нет: `artel.git` подменяется фейком с
заготовленным diff, `subprocess.Popen` — фейковым процессом. Так
проверяется то, что задаёт стоимость прогона: состав и порядок пакета,
усечение большого diff и запись размера в журнал.

Тесты не описывают формулировки миссии — только наблюдаемое: что ушло в
промпт агента, что легло в журнал и какие права у шага остались.
"""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel  # noqa: E402

SPEC_MD = """---
task: T001
type: spec
author_role: analyst
status: approved
---

# SPEC: ревью-пакет

## Требования
1. Пакет собирает оркестратор.
"""

PLAN_MD = """---
task: T001
type: plan
author_role: developer
status: ready
---

# PLAN: ревью-пакет

## Подход
Собрать пакет в cmd_run.
"""

REVIEW_MD = """---
task: T001
type: review
author_role: reviewer
status: changes_requested
iteration: 1
---

# REVIEW: ревью-пакет

## Замечания
major — orchestrator/artel.py:1 — усечение без пометки.
"""


class FakeGit:
    """Подмена `artel.git`: отвечает на diff заготовками, помнит вызовы."""

    def __init__(self, stat="orchestrator/artel.py | 2 +-", diff="diff --git a b",
                 returncode: int = 0, stderr: str = ""):
        self.stat = stat
        self.diff = diff
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        stdout = self.stat if "--stat" in args else self.diff
        return subprocess.CompletedProcess(
            list(args), self.returncode, "" if self.returncode else stdout,
            self.stderr)


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class TruncateDiffTest(unittest.TestCase):
    """Потолок diff: под ним — как есть, над ним — начало и явная пометка."""

    def diff_of(self, lines: int) -> str:
        return "\n".join(f"+строка {n}" for n in range(1, lines + 1))

    def test_diff_under_the_cap_is_untouched(self):
        diff = self.diff_of(artel.REVIEW_DIFF_MAX_LINES)

        text, truncated = artel.truncate_diff(diff, artel.REVIEW_DIFF_MAX_LINES)

        self.assertEqual(text, diff)
        self.assertFalse(truncated)

    def test_big_diff_keeps_the_head_and_says_so(self):
        lines = artel.REVIEW_DIFF_MAX_LINES + 500
        diff = self.diff_of(lines)

        text, truncated = artel.truncate_diff(diff, lines)

        self.assertTrue(truncated)
        body, _, note = text.partition("[diff усечён")
        self.assertEqual(body.strip().splitlines(),
                         diff.splitlines()[:artel.REVIEW_DIFF_MAX_LINES],
                         "в пакет идёт начало diff, а не произвольный кусок")
        self.assertIn(str(artel.REVIEW_DIFF_MAX_LINES), note)
        self.assertIn(str(lines), note, "видно, сколько строк не показано")
        self.assertIn("размере MR", note, "размер сам по себе — повод к замечанию")

    def test_one_line_over_the_cap_is_already_truncated(self):
        lines = artel.REVIEW_DIFF_MAX_LINES + 1

        _, truncated = artel.truncate_diff(self.diff_of(lines), lines)

        self.assertTrue(truncated)


class ReviewPackageTest(unittest.TestCase):
    """Сборка пакета: все части на месте, порядок стабилен, размер посчитан."""

    TASK = "T001"
    BRANCH = "task/t001-revyu-paket"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name) / "tasks" / self.TASK
        self.tdir.mkdir(parents=True)
        patcher = mock.patch.object(artel, "TASKS", Path(tmp.name) / "tasks")
        patcher.start()
        self.addCleanup(patcher.stop)

        self.git = FakeGit()
        git_patcher = mock.patch.object(artel, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        (self.tdir / "SPEC.md").write_text(SPEC_MD, encoding="utf-8")
        (self.tdir / "PLAN.md").write_text(PLAN_MD, encoding="utf-8")

    def build(self) -> dict:
        return artel.review_package(self.TASK, "Ревью-пакет", self.BRANCH)

    def order_of(self, text: str, *marks: str) -> list[int]:
        found = []
        for mark in marks:
            self.assertIn(mark, text)
            found.append(text.index(mark))
        return found

    def test_all_parts_are_present_in_a_stable_order(self):
        """Требование 1: заголовок, SPEC, PLAN, стат-список и diff — по порядку."""
        text = self.build()["text"]

        marks = self.order_of(
            text,
            "### Задача", f"tasks/{self.TASK}/SPEC.md", f"tasks/{self.TASK}/PLAN.md",
            "### Изменённые файлы", "### Diff")

        self.assertEqual(marks, sorted(marks), "порядок частей пакета плавает")
        self.assertIn(self.BRANCH, text)
        self.assertIn("Пакет собирает оркестратор", text, "тело SPEC целиком")
        self.assertIn("Собрать пакет в cmd_run", text, "тело PLAN целиком")
        self.assertIn("orchestrator/artel.py | 2 +-", text)
        self.assertIn("diff --git a b", text)

    def test_stat_and_diff_are_taken_against_main(self):
        self.build()

        self.assertEqual(self.git.calls,
                         [["diff", "--stat", f"{artel.MAIN_BRANCH}...{self.BRANCH}"],
                          ["diff", f"{artel.MAIN_BRANCH}...{self.BRANCH}"]])

    def test_previous_review_is_included_for_iterations(self):
        (self.tdir / "REVIEW.md").write_text(REVIEW_MD, encoding="utf-8")

        text = self.build()["text"]

        marks = self.order_of(text, f"tasks/{self.TASK}/PLAN.md",
                              f"tasks/{self.TASK}/REVIEW.md", "### Изменённые файлы")
        self.assertEqual(marks, sorted(marks), "прошлый REVIEW идёт после PLAN")
        self.assertIn("усечение без пометки", text, "замечания прошлой итерации")

    def test_first_iteration_has_no_review_part(self):
        text = self.build()["text"]

        self.assertNotIn("REVIEW.md", text)

    def test_missing_plan_is_shown_as_missing(self):
        """Пропавший PLAN — факт для ревьювера, а не тихо пустая часть."""
        (self.tdir / "PLAN.md").unlink()

        text = self.build()["text"]

        self.assertIn(f"tasks/{self.TASK}/PLAN.md", text)
        self.assertIn("(файла нет)", text)

    def test_size_is_measured(self):
        package = self.build()

        self.assertEqual(package["chars"], len(package["text"]))
        self.assertEqual(package["diff_lines"], 1)
        self.assertFalse(package["truncated"])

    def test_big_diff_is_truncated_with_a_mark(self):
        """Требование 2: за потолком в пакет идёт усечённый diff с пометкой."""
        lines = artel.REVIEW_DIFF_MAX_LINES + 10
        self.git.diff = "\n".join(f"+строка {n}" for n in range(1, lines + 1))

        package = self.build()

        self.assertTrue(package["truncated"])
        self.assertEqual(package["diff_lines"], lines, "в журнал — полный размер")
        self.assertIn("[diff усечён", package["text"])
        self.assertIn("+строка 1\n", package["text"])
        self.assertNotIn(f"+строка {lines}", package["text"])
        self.assertIn("orchestrator/artel.py | 2 +-", package["text"],
                      "стат-список при усечении остаётся полным")

    def test_silent_git_becomes_a_visible_reason(self):
        """Пустой diff и не собранный diff — разные вещи, и это видно."""
        self.git.returncode = 1
        self.git.stderr = "fatal: bad revision"

        package = self.build()

        self.assertIn("не собран: fatal: bad revision", package["text"])
        self.assertEqual(package["diff_lines"], 0)
        self.assertFalse(package["truncated"])

    def test_empty_diff_is_stated_explicitly(self):
        self.git.diff = ""
        self.git.stat = ""

        self.assertIn("(изменений нет)", self.build()["text"])

    def test_note_shows_size_and_truncation(self):
        note = artel.package_note({"chars": 1234, "diff_lines": 56,
                                   "truncated": False})

        self.assertIn("символов 1234", note)
        self.assertIn("строк diff 56", note)
        self.assertNotIn("усечён", note)
        self.assertIn("усечён", artel.package_note(
            {"chars": 1, "diff_lines": 99999, "truncated": True}))


class CmdRunReviewPackageTest(unittest.TestCase):
    """`run` в review: пакет уходит в промпт, размер — в журнал, права те же."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            patcher = mock.patch.object(artel, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.git = FakeGit()
        git_patcher = mock.patch.object(artel, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        self.capture(artel.cmd_init)
        self.capture(artel.cmd_new, "Ревью-пакет вместо свободного чтения")
        self.tdir = artel.TASKS / self.TASK
        (self.tdir / "SPEC.md").write_text(SPEC_MD, encoding="utf-8")
        (self.tdir / "PLAN.md").write_text(PLAN_MD, encoding="utf-8")

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def set_state(self, state: str) -> None:
        conn = artel.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def run_agent(self, state: str) -> tuple[str, list[str]]:
        """Прогон шага; возвращает вывод и argv запущенного CLI."""
        self.set_state(state)
        with mock.patch.object(artel.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = self.capture(artel.cmd_run, self.TASK)
        return out, popen.call_args.args[0]

    def prompt_of(self, argv: list[str]) -> str:
        return argv[argv.index("-p") + 1]

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in artel.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def test_reviewer_prompt_carries_the_package(self):
        """Критерий приёмки 1: SPEC, PLAN, стат-список и diff — в промпте."""
        _, argv = self.run_agent("review")

        prompt = self.prompt_of(argv)
        self.assertIn("--- РЕВЬЮ-ПАКЕТ ---", prompt)
        self.assertIn("Пакет собирает оркестратор", prompt, "SPEC целиком")
        self.assertIn("Собрать пакет в cmd_run", prompt, "PLAN целиком")
        self.assertIn("orchestrator/artel.py | 2 +-", prompt, "стат-список")
        self.assertIn("diff --git a b", prompt, "diff")
        self.assertIn("review-checklist", prompt, "скилы роли остались в промпте")

    def test_package_size_lands_in_the_journal(self):
        """Критерий приёмки 2: размер входа виден в `log <id>` у старта ревью."""
        out, argv = self.run_agent("review")

        details = self.journal_details("ревью-пакет собран")
        self.assertEqual(len(details), 1)
        package = artel.review_package(self.TASK, "Ревью-пакет вместо свободного чтения",
                                       artel.db().execute(
                                           "SELECT branch FROM tasks WHERE id=?",
                                           (self.TASK,)).fetchone()[0])
        self.assertIn(f"символов {package['chars']}", details[0])
        self.assertIn(f"строк diff {package['diff_lines']}", details[0])
        self.assertIn("символов", self.capture(artel.cmd_log, self.TASK))
        self.assertIn("ревью-пакет:", out, "размер виден Оператору сразу")

    def test_package_is_journaled_before_the_agent_starts(self):
        """Запись о пакете идёт до запуска — иначе она врёт о старте шага."""
        self.run_agent("review")

        actions = [r["action"] for r in artel.db().execute(
            "SELECT action FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]
        self.assertLess(actions.index("ревью-пакет собран"),
                        actions.index("agent run started"))

    def test_truncation_is_journaled_too(self):
        lines = artel.REVIEW_DIFF_MAX_LINES + 7
        self.git.diff = "\n".join(f"+строка {n}" for n in range(1, lines + 1))

        self.run_agent("review")

        self.assertIn("усечён", self.journal_details("ревью-пакет собран")[0])

    def test_developer_step_has_no_package(self):
        """Требование «не входит»: контекст разработчика не меняется."""
        _, argv = self.run_agent("in_dev")

        self.assertNotIn("--- РЕВЬЮ-ПАКЕТ ---", self.prompt_of(argv))
        self.assertEqual(self.journal_details("ревью-пакет собран"), [])
        self.assertEqual(self.git.calls, [], "diff разработчику не собирается")

    def test_reviewer_rights_are_not_narrowed(self):
        """Требование 4: инструменты ревьювера те же, что у разработчика."""
        _, dev_argv = self.run_agent("in_dev")
        _, rev_argv = self.run_agent("review")

        def tools(argv: list[str]) -> str:
            return argv[argv.index("--allowedTools") + 1]

        self.assertEqual(tools(rev_argv), tools(dev_argv))
        self.assertIn("Bash(python3:*)", tools(rev_argv), "тесты запускать можно")


if __name__ == "__main__":
    unittest.main()
