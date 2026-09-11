"""Общая песочница приёмочных тестов задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G:
`amend-tests` гоняет трассируемость AC перед сдвигом лока планки.

Тонкая надстройка над `tests.sandbox.RealGitSandbox` (skills/
test-authoring.md, «Лёгкая песочница переходов — не копия, импорт»): сам
светлый песочный набор (`disk_backed_*`/`advance_from_in_dev`) здесь не
переопределяется вовсе — `amend-tests` сверяет правку НАСТОЯЩИМ git diff
между worktree/веткой и локом, лёгкая заглушка `gitcmd.git` этого не
изображает (тот же довод, что уже несёт `tests/test_amend.py`, классы
`AmendThenReviewGateTest`/`AmendFromBranchDivergenceDetailTest`).

Фикстуры-варианты правки планки (AC_TEST_*) живут ЗДЕСЬ, а не в
test_*.py этой директории: guard.scan_acceptance_tests читает содержимое
`test_*.py` этой директории текстом, не AST (SPEC T081) — буквальная
строка `# AC-2: manual — …`/`def test_ac1_…` внутри строковой фикстуры,
попади она в файл test_*.py ЭТОЙ ЖЕ задачи, читалась бы guard'ом как
настоящая AC-разметка задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G (тот же довод —
tasks/01M287TPG0HAVXS8CHBCY679WN/acceptance_tests/
test_ac7_ac8_ac9_amend_from_branch.py, комментарий у AC_TEST_AMENDED).
`_sandbox.py` этот текст текстом не сканирует вовсе.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (amend, artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import AC_TEST_BOTH_COVERED, SPEC_V2  # noqa: E402

__all__ = [
    "amend", "capture", "capture_new_task_id",
    "WorktreeGateSandbox", "FromBranchGateSandbox", "REFUSAL_PREFIX_RE",
    "AC_TEST_MISSING_AC1_NO_MARKER", "AC_TEST_INDENTED_AC2_MARKER",
    "AC_TEST_VALID_EDIT_BOTH_COVERED",
]

# Префикс формата отказа AC-1 буквально из SPEC: «[<id>] amend-tests:
# отказ — трассируемость AC нарушена: <ошибки guard через '; '>» —
# сверяется ПРЕФИКСОМ (не точным текстом хвоста): дословный список
# ошибок `guard.acceptance_traceability_errors` зависит от того,
# материализует ли реализация SPEC.md на диск worktree ПЕРЕД вызовом
# guard (тем же приёмом, что `_materialize_tests_if_missing` уже делает
# для `acceptance_tests/`) — решение реализации, не буква этого теста;
# префикс и упоминание сломанного критерия — то, что SPEC требует
# буквально и не зависит от этого выбора. Общий и для AC-1
# (worktree-путь), и для AC-3 (--from-branch): «отказ тем же текстом,
# что AC-1».
REFUSAL_PREFIX_RE = re.compile(
    r"^\[(?P<task>[^\]]+)\] amend-tests: отказ — трассируемость AC "
    r"нарушена: ")


class _EnterInDevMixin:
    """Доводит свежую задачу до `in_dev` с зафиксированным
    `tests_locked_sha`: SPEC_V2 (критерии AC-1 тестом, AC-2 меткой
    manual), acceptance_tests/test_ac.py = AC_TEST_BOTH_COVERED — тот же
    рецепт, что `tests/test_amend.py::AmendThenReviewGateTest.
    enter_in_dev`/`AmendFromBranchDivergenceDetailTest._enter_in_dev`."""

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(
            self.TASK, files, f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} не удался")
        return sha

    def _enter_in_dev(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra="")},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.row()["state"], "tests_writing")

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.row()["state"], "in_dev")

    def journal_rows(self) -> list:
        return store.task_steps(self.conn, self.TASK)


class WorktreeGateSandbox(_EnterInDevMixin, RealGitSandbox):
    """Правка Оператора кладётся прямо в `self.tdir/acceptance_tests/
    test_ac.py` (`edit_tests`) — та же поверхность диска worktree, с
    которой читает `_cmd_amend_tests` (SPEC требование 1).

    `self.tdir/SPEC.md` НЕ кладётся сюда сам собой: откуда траектория
    трассируемости берёт текст SPEC.md для `tdir`-based `guard.
    acceptance_traceability_errors(tdir)` (материализация по аналогии с
    `_materialize_tests_if_missing`, либо СПЕК уже на диске с прошлого
    шага роли в этом же worktree) — решение реализации, не этого теста;
    класть файл сюда самим тестом означало бы навязать ЕЩЁ одно
    незакоммиченное изменение worktree ЗА ПРЕДЕЛАМИ `acceptance_tests/`
    — `_worktree_changed_paths` увидело бы его как «изменения снаружи»
    (AC-3 задачи 01M1HNNHDMP2C1AJTH5QF1BTN2) и ломало бы сценарий до
    того, как тест доедет до проверки трассируемости."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "трассируемость AC на amend-tests (worktree)")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt_path = wt_path
        self.tdir = wt_path / "tasks" / self.TASK
        self._enter_in_dev()

    def edit_tests(self, content: str) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(content, encoding="utf-8")


class FromBranchGateSandbox(_EnterInDevMixin, RealGitSandbox):
    """Правка живёт ПРЯМО на артефактной ветке (автокоммит роли, минуя
    `amend-tests`) — источник `_cmd_amend_tests_from_branch` (SPEC
    требование 2), не диск worktree вовсе."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "трассируемость AC на amend-tests (--from-branch)")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self._enter_in_dev()


# Правка, снимающая единственный тест AC-1 БЕЗ пометки (AC-1/AC-2/AC-3/
# AC-5/AC-8): AC-2 остаётся размеченным валидной (без отступа) меткой
# manual — изолирует отказ по признаку «AC-1 без теста и без пометки» от
# ЛЮБОГО отказа по AC-2.
AC_TEST_MISSING_AC1_NO_MARKER = '''"""Красен до реализации: фикстура нарочно СНИМАЕТ тест критерия AC-1
песочницы SPEC_V2 без замены его пометкой — образец правки, которую
`guard.acceptance_traceability_errors` обязан поймать."""
import unittest


class AcceptanceTest(unittest.TestCase):
    pass


# AC-2: manual - Оператор проверяет глазами на приёмке
'''

# Тот же снятый тест AC-1, но метка AC-2 поставлена С ОТСТУПОМ (AC-6,
# инцидент 11.09: «# AC-7: manual», поставленный не в начале строки,
# сдвинул лок мимо трассируемости). AC_MARKER (`scripts/guard.py`)
# заякорен на `^#` без отступа и такую строку не видит вовсе — до мержа
# задачи 01M28NX43E (детекция маркера с отступом) это читается тем же
# путём, что и AC_TEST_MISSING_AC1_NO_MARKER выше («нет теста и нет
# пометки»), без отдельного упоминания отступа в тексте отказа.
AC_TEST_INDENTED_AC2_MARKER = '''"""Красен до реализации: фикстура повторяет AC_TEST_BOTH_COVERED
песочницы SPEC_V2, но метка AC-2 стоит с отступом — имитация инцидента
11.09 (маркер, поставленный не в начале строки)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


    # AC-2: manual - Оператор проверяет глазами на приёмке
'''

# Корректная правка: оба критерия SPEC_V2 по-прежнему покрыты (AC-1
# тестом — теперь ДВУМЯ проверками вместо одной, AC-2 валидной меткой),
# содержательно отличная от AC_TEST_BOTH_COVERED (AC-7/AC-8: и правда
# правка, не побайтная копия зафиксированного содержимого).
AC_TEST_VALID_EDIT_BOTH_COVERED = '''"""Красен до реализации: фикстура покрывает оба критерия SPEC_V2
песочницы — правка Оператора добавляет вторую проверку AC-1, метка AC-2
остаётся валидной."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)


# AC-2: manual - Оператор проверяет глазами на приёмке
'''
