"""Юнит-тесты проводки долгоживущих файлов через переходы FSM (SPEC
01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ; ADR-0020, задача 2; инвариант 27): гейт
«только добавление» и перечень на выходе из `tests_writing`
(`orchestrator/advance_gates/tests_writing.py`), трассируемость по
долгоживущим файлам задачи, сверка перечня на рубежах Р4
(`orchestrator/fsm_advance.py`, `orchestrator/fsm.py`,
`orchestrator/fsm_merge_gate.py`), лок каталога на гейте мержа, прогон
`in_dev -> verifying` без рабочей копии на ветке задачи.

Узлы по отдельности — `tests/test_long_lived_manifest.py`; здесь —
переходы через публичные входы (`fsm.cmd_advance`, `fsm.cmd_approve`,
`fsm_merge_gate._cmd_approve_merge_gate`) на настоящем git: пульт с
артефактной веткой (`RealPultGitTest`), bare `origin` и worktree кодовой
ветки. Гейты переходов вне предмета (ёмкость, зоны, приложения, заявка
мутации, неослабление, CI, origin, подтяжка main, полный набор, автогейт)
подменены проходом; лок каталога и прогон приёмки — настоящие.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, artifact_branch, ci, config, fsm,  # noqa: E402
                          fsm_advance, fsm_autogate, fsm_merge_gate,
                          github_adapter, gitcmd, store, workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from tests.test_git_fixation import PLAN_READY, RealPultGitTest  # noqa: E402

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

{criteria}

## Не входит
"""

REVIEW_APPROVED = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: песочница
"""

PLANK_SOURCE = '''"""Фикстура разового файла планки.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def {name}(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

LONG_LIVED_SOURCE = '''"""Фикстура долгоживущего файла.

Группа: {group}
"""
import os
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_long_fixture(self):
        """Фикстурный метод.

        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {{seed}}")
        self.assertNotIn("{red_env}", os.environ)
'''

# Переменная окружения, под которой долгоживущий файл фикстуры красен, —
# без правки его байтов (правку после лока отклонила бы сверка перечня).
RED_ENV = "ARTEL_TEST_LONG_LIVED_FIXTURE_RED"

EXISTING_SOURCE = '''"""Существующий файл tests/ базы."""
import unittest


class ExistingTest(unittest.TestCase):

    def test_ac1_legacy(self):
        """Метод базы, одноимённый критерию AC-1."""
        self.assertTrue(True)
'''


def plank_source(name: str = "test_ac1_plank_fixture") -> str:
    return PLANK_SOURCE.format(name=name)


def long_lived_source(group: str = "долгоживущий", tag: str = "") -> str:
    text = LONG_LIVED_SOURCE.format(group=group, red_env=RED_ENV)
    return text + f"# {tag}\n" if tag else text


def capture_call(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            buf.write(f"\nSystemExit: {exc}")
    return buf.getvalue()


class _TransitionSandbox(RealPultGitTest):
    """Задача target `artel` в `tests_writing`; база ветки несёт
    `tests/test_existing.py` (без префикса задачи, с методом `test_ac1_…`)."""

    CRITERIA = "AC-1. Единственный критерий песочницы."
    EXISTING = "tests/test_existing.py"

    def setUp(self):
        super().setUp()
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(origin))
        self.git("remote", "add", "origin", str(origin))
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / self.EXISTING).write_text(EXISTING_SOURCE, encoding="utf-8")
        self.git("add", "tests")
        self.git("commit", "-q", "-m", "база: существующие tests/")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.branch = self.row()["branch"]
        self.wt, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()
        self.artifact_commit(
            {"SPEC.md": SPEC_TEXT.format(task=self.TASK, criteria=self.CRITERIA),
             "acceptance_tests/test_ac1_plank.py": plank_source()},
            "SPEC и планка")
        self.own = f"tests/test_{self.TASK.lower()}_alpha.py"
        self.set_row(state="tests_writing")

    def set_row(self, **fields) -> None:
        store.update_task(store.db(), self.TASK, **fields)

    def row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.row()["state"]

    def steps_after(self, step_id: int) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? AND id>? "
            "ORDER BY id", (self.TASK, step_id)).fetchall()
        return "\n".join(f"{r['action']} {r['detail'] or ''}" for r in rows)

    def last_step_id(self) -> int:
        row = store.db().execute("SELECT MAX(id) AS m FROM steps WHERE task_id=?",
                                 (self.TASK,)).fetchone()
        return row["m"] or 0

    def wt_git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.wt), "-c", "user.name=artel tests",
             "-c", "user.email=artel@example.invalid", *args],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def wt_commit(self, files=None, remove=(), rename=None) -> None:
        for rel, text in (files or {}).items():
            path = self.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for rel in remove:
            self.wt_git("rm", "-q", "--", rel)
        if rename:
            self.wt_git("mv", *rename)
        self.wt_git("add", "-A", "--", ".", f":(exclude)tasks/{self.TASK}")
        self.wt_git("commit", "-q", "-m", "правка кодовой ветки")

    def reset_branch(self) -> None:
        self.wt_git("reset", "-q", "--hard", self.base_sha)
        self.wt_git("clean", "-q", "-fd", "--", ".", f":(exclude)tasks/{self.TASK}")
        self.set_row(state="tests_writing", tests_locked_sha=None)

    def artifact_commit(self, files: dict, message: str) -> None:
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/{rel}": text
                        for rel, text in files.items()}, f"{self.TASK}: {message}")

    def advance(self) -> str:
        before = self.last_step_id()
        out = capture_call(fsm.cmd_advance, self.TASK)
        return self.steps_after(before) + "\n" + out

    def exit_tests_writing(self) -> str:
        self.set_row(state="tests_writing")
        return self.advance()

    def lock_with_own(self, text: str | None = None) -> None:
        self.wt_commit({self.own: text or long_lived_source()})
        out = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", out)

    def advance_in_dev(self) -> str:
        self.artifact_commit({"PLAN.md": PLAN_READY.format(task=self.TASK)},
                             "PLAN готов")
        self.set_row(state="in_dev")
        with contextlib.ExitStack() as stack:
            for name in ("_capacity_gate_refuses", "_zones_gate_refuses",
                         "_plan_appendix_gate_refuses",
                         "_test_integrity_gate_refuses",
                         "_review_rework_gate_refuses"):
                stack.enter_context(mock.patch.object(fsm_advance, name,
                                                      return_value=False))
            for name in ("_mutation_claim_gate", "_origin_push_gate"):
                stack.enter_context(mock.patch.object(fsm_advance, name,
                                                      return_value=None))
            stack.enter_context(mock.patch.object(
                fsm, "_pull_main_or_escalate", return_value="fresh"))
            return self.advance()

    def advance_verifying(self) -> str:
        self.set_row(state="verifying")
        with mock.patch.object(ci, "verifying_status",
                               return_value=(ci.VERIFYING_GREEN, "CI зелёный")):
            return self.advance()

    def advance_review(self) -> str:
        self.artifact_commit({"REVIEW.md": REVIEW_APPROVED.format(task=self.TASK)},
                             "REVIEW approved")
        self.set_row(state="review", reviewed_iter=0)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(fsm, "guard_refuses",
                                                  return_value=False))
            stack.enter_context(mock.patch.object(fsm, "_dirty_refuses",
                                                  return_value=False))
            stack.enter_context(mock.patch.object(
                fsm_advance, "_review_escalation_sha_gate", return_value=None))
            stack.enter_context(mock.patch.object(
                fsm_autogate, "_maybe_autogate_acceptance", return_value=None))
            return self.advance()

    def approve_acceptance(self) -> str:
        self.set_row(state="acceptance")
        green = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                        "1 passed", None, "зелёный прогон")
        before = self.last_step_id()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(fsm, "confirm_fixation",
                                                  return_value=True))
            stack.enter_context(mock.patch.object(
                fsm, "_pull_main_or_escalate", return_value="fresh"))
            stack.enter_context(mock.patch.object(acceptance, "full_suite",
                                                  return_value=green))
            stack.enter_context(mock.patch.object(github_adapter, "undraft_mr",
                                                  return_value=None))
            out = capture_call(fsm.cmd_approve, self.TASK)
        return self.steps_after(before) + "\n" + out

    def merge_gate_body(self) -> tuple[tuple | None, str]:
        """Тело гейта мержа до CI: ожидание CI (`("wait", …)`) — знак, что
        ни один рубеж после `_sync_main_or_wait` не отказал."""
        self.set_row(state="merge_gate")
        before = self.last_step_id()
        result = {}
        with contextlib.ExitStack() as stack:
            for name in ("_protected_path_diff_gate", "_test_integrity_diff_gate"):
                stack.enter_context(mock.patch.object(fsm_merge_gate, name,
                                                      return_value=False))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_ensure_branch_head_published", return_value="ok"))
            stack.enter_context(mock.patch.object(
                fsm, "_pull_main_or_escalate", return_value="fresh"))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_ci_ready_or_wait",
                side_effect=lambda task_id, note, branch: ("wait", branch)))
            conn = store.db()
            out = capture_call(lambda: result.setdefault(
                "outcome", fsm_merge_gate._cmd_approve_merge_gate(
                    conn, self.TASK, "merge_gate", self.row())))
        return result.get("outcome"), self.steps_after(before) + "\n" + out


class TestsWritingOnlyAdditionGateTest(_TransitionSandbox):

    def assert_refused(self, *needles: str, why: str) -> None:
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "tests_writing",
                         f"{why}: выход обязан быть отклонён: {text}")
        for needle in needles:
            self.assertIn(needle, text, f"{why}: отказ не называет {needle}")

    def test_diff_violations_refused_naming_path(self):
        """Поверх чистого своего файла: правка (`M`), удаление (`D`),
        переименование (`R`) файла базы, файл `tests/` без префикса, путь
        вне `tests/`, файл с префиксом без строки «долгоживущий» — каждое
        отклоняет выход из `tests_writing` и называет путь; без нарушения
        выход проходит.

        Ловит мутацию: `_tests_writing_long_lived_gate` выпал из списка
        гейтов `fsm_advance.tests_writing` (или возвращает `None`) —
        каждое нарушение уходит в `in_dev`.
        """
        self.wt_commit({self.own: long_lived_source()})
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", f"контроль: {text}")
        base_text = (self.root / self.EXISTING).read_text(encoding="utf-8")
        scenarios = {
            "M": (lambda: self.wt_commit({self.EXISTING: base_text + "# M\n"}),
                  self.EXISTING),
            "D": (lambda: self.wt_commit(remove=[self.EXISTING]), self.EXISTING),
            "R": (lambda: self.wt_commit(rename=(
                self.EXISTING, f"tests/test_{self.TASK.lower()}_moved.py")),
                self.EXISTING),
            "без префикса": (lambda: self.wt_commit(
                {"tests/test_noprefix.py": long_lived_source()}),
                "tests/test_noprefix.py"),
            "вне tests/": (lambda: self.wt_commit({"docs/extra.md": "x\n"}),
                           "docs/extra.md"),
            "разовый": (lambda: self.wt_commit(
                {self.own: long_lived_source(group="разовый")}), self.own),
        }
        for label, (make, path) in scenarios.items():
            with self.subTest(scenario=label):
                self.reset_branch()
                self.wt_commit({self.own: long_lived_source()})
                make()
                self.assert_refused(path, why=label)

    def test_path_already_in_origin_main_refused(self):
        """Путь своего файла появился в `origin/main` после ответвления
        ветки: в диффе против базы это `A`, но выход отклонён с путём.

        Ловит мутацию: «путь уже есть» сверяется с деревом базы ветки, а
        не с `origin/main` (или проверка снята) — переход проходит.
        """
        (self.root / self.own).write_text(long_lived_source(tag="main"),
                                          encoding="utf-8")
        self.git("add", self.own)
        self.git("commit", "-q", "-m", "main: тот же путь")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.wt_commit({self.own: long_lived_source(tag="ветка")})
        self.assert_refused(self.own, why="путь в origin/main")


class TestsWritingManifestTest(_TransitionSandbox):

    def manifest_at_lock(self) -> str | None:
        locked = self.row()["tests_locked_sha"]
        self.assertTrue(locked, "лок не записан")
        text, _ = gitcmd.show(locked, acceptance_gates.long_lived_manifest_rel(
            self.TASK))
        return text

    def test_manifest_in_lock_tree_with_head_digest(self):
        """После выхода из `tests_writing` перечень лежит в дереве коммита
        `tests_locked_sha`, его строка — сумма файла на голове кодовой ветки.

        Ловит мутацию: `_tests_writing_manifest_gate` выпал из гейтов
        выхода (или лок пишется раньше перечня) — в дереве лока перечня нет.
        """
        self.lock_with_own()
        head = gitcmd.branch_head_sha(self.branch)
        digest = acceptance_gates.blob_sha256(head, self.own)
        self.assertEqual(self.manifest_at_lock(), f"{digest}  {self.own}\n")

    def test_empty_manifest_written_without_long_lived_files(self):
        """Долгоживущих файлов нет — выход проходит, в дереве лока пустой
        перечень.

        Ловит мутацию: пустой перечень не пишется (гейт перечня
        пропускается при нуле файлов) — в дереве лока файла нет.
        """
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", text)
        self.assertEqual(self.manifest_at_lock(), "")


class LongLivedTraceabilityTest(_TransitionSandbox):

    CRITERIA = ("AC-1. Первый критерий песочницы.\n\n"
                "AC-2. Второй критерий песочницы.")

    def setUp(self):
        super().setUp()
        self.artifact_commit({"acceptance_tests/test_ac1_plank.py":
                              plank_source("test_ac2_plank_fixture")},
                             "планка покрывает только AC-2")

    def test_own_long_lived_method_covers_and_foreign_does_not(self):
        """AC-1 покрыт только методом `test_ac1_…`: в файле базы без
        префикса задачи — выход отклонён с AC-1; в своём долгоживущем
        файле — выход проходит.

        Ловит мутацию: трассируемость не получает долгоживущие источники
        (`long_lived_sources` пуст) либо собирает методы из всего `tests/`
        — один из двух сценариев меняет исход.
        """
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "tests_writing", text)
        self.assertIn("AC-1", text)
        self.wt_commit({self.own: long_lived_source()})
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", text)


class ManifestBoundariesTest(_TransitionSandbox):

    def setUp(self):
        super().setUp()
        self.lock_with_own(long_lived_source() + "# строка с CRLF\r\n")

    def boundaries(self):
        return (("in_dev -> verifying", self.advance_in_dev, "in_dev"),
                ("verifying -> review", self.advance_verifying, "verifying"),
                ("review -> acceptance", self.advance_review, "review"),
                ("approve из acceptance", self.approve_acceptance, "acceptance"))

    def test_changed_file_refused_at_every_boundary(self):
        """Свой файл изменён в кодовой ветке после лока: каждый из четырёх
        переходов Р4 оставляет задачу в исходном состоянии, гейт мержа —
        `("stopped",)`; отказ называет путь и подсказку `amend-tests`.

        Ловит мутацию: вызов `_long_lived_manifest_refuses` снят с любого
        из рубежей (`fsm_advance.in_dev`/`verifying`/`review`,
        `fsm._approve_acceptance`, `fsm_merge_gate._acceptance_locks_refuse`)
        — на этом рубеже правленый тест проходит дальше.
        """
        self.wt_commit({self.own: long_lived_source(tag="правка после лока")})
        for name, call, before in self.boundaries():
            with self.subTest(boundary=name):
                text = call()
                self.assertEqual(self.state(), before, f"{name}: {text}")
                self.assertIn(self.own, text, name)
                self.assertIn(acceptance_gates.LONG_LIVED_MANIFEST_HINT, text, name)
        with self.subTest(boundary="гейт мержа"):
            outcome, text = self.merge_gate_body()
            self.assertEqual(outcome, ("stopped",), text)
            self.assertIn(self.own, text)

    def test_matching_file_passes_every_boundary(self):
        """Контроль: без расхождения (файл с CRLF) все пять рубежей
        проходят подряд, тело гейта мержа доходит до ожидания CI.

        Ловит мутацию: сверка считает сумму от текста с перекодировкой
        концов строк, а не от байтов блоба — совпадающий файл отклонён.
        """
        for name, call, before in self.boundaries():
            with self.subTest(boundary=name):
                text = call()
                self.assertNotEqual(self.state(), before, f"{name}: {text}")
        outcome, text = self.merge_gate_body()
        self.assertEqual(outcome[0] if outcome else None, "wait", text)

    def test_long_lived_file_runs_in_plank_run(self):
        """`in_dev -> verifying` исполняет свой долгоживущий файл вместе с
        планкой: красный (под `RED_ENV`) — переход отклонён с именем файла;
        зелёный — проходит, итог называет обе группы.

        Ловит мутацию: `_acceptance_run_refuses` не передаёт перечень в
        `acceptance.run(..., extra=)` — красный долгоживущий файл не
        исполняется, и переход проходит.
        """
        with mock.patch.dict(os.environ, {RED_ENV: "1"}):
            text = self.advance_in_dev()
        self.assertEqual(self.state(), "in_dev", text)
        self.assertIn(Path(self.own).name, text)
        text = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", text)
        self.assertIn("долгоживущая группа — 1 тест(ов)", text)

    def test_run_refused_without_worktree_on_task_branch(self):
        """Рабочая копия задачи не на ветке задачи, перечень непуст —
        `in_dev -> verifying` отклонён, а не прогнан без долгоживущей
        группы.

        Ловит мутацию: путь без рабочей копии в `_acceptance_run_refuses`
        гоняет одну планку из корня пульта — переход проходит молча.
        """
        with mock.patch.object(workspace, "on_task_branch", return_value=False):
            text = self.advance_in_dev()
        self.assertEqual(self.state(), "in_dev", text)
        self.assertIn("долгоживущие файлы перечня исполнить негде", text)


class MergeGatePlankLockTest(_TransitionSandbox):

    def test_plank_edited_after_lock_stops_merge_gate(self):
        """Файл планки правлен в ветке документов после лока: тело гейта
        мержа — `("stopped",)` с отказом лока; без правки — ожидание CI.

        Ловит мутацию: `_acceptance_locks_refuse` не зовёт
        `_acceptance_lock_refuses` (или трактует расхождение как проход) —
        правленая планка доходит до ожидания CI.
        """
        text = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", text)
        outcome, text = self.merge_gate_body()
        self.assertEqual(outcome[0] if outcome else None, "wait", text)
        self.artifact_commit({"acceptance_tests/test_ac1_plank.py":
                              plank_source() + "# правка после лока\n"},
                             "правка планки после лока")
        outcome, text = self.merge_gate_body()
        self.assertEqual(outcome, ("stopped",), text)
        self.assertIn("лок приёмочных тестов", text)


if __name__ == "__main__":
    unittest.main()
