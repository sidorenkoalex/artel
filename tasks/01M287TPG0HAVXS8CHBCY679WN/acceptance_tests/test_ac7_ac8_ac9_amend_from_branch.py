"""Приёмочные тесты AC-7/AC-8/AC-9 задачи 01M287TPG0HAVXS8CHBCY679WN:
`amend-tests <id> --reason "<основание>" --from-branch` (SPEC,
требование 3).

Красен до реализации: `orchestrator/artel.py::main` собирает вызов
`amend-tests` без разбора флага `--from-branch` (`amend.cmd_amend_tests
(rest[0], _reason_arg(rest))`, artel.py:751) — флаг тихо игнорируется,
и `_cmd_amend_tests` (`orchestrator/amend.py`) всегда сверяет worktree,
как и до этой задачи. Красны
`test_ac7_divergence_journals_files_and_moves_lock_to_branch_head`
(вместо фиксации расхождения ветки команда отказывает «нет изменений» —
worktree не тронут) и
`test_ac8_no_divergence_refuses_with_no_divergence_message` (тот же
неигнорируемый флаг: сообщение отказа сегодня — «нет изменений», не
«нет расхождения», которого требует AC-8 буквально).
`test_ac9_without_flag_ignores_divergence_that_exists_only_on_the_branch`
УЖЕ зелёный на текущем коде — контроль, не молчаливый пропуск: без
`--from-branch` команда и сегодня сверяет worktree, а не ветку, ровно
то поведение, которое требует сохранить AC-9.

Через CLI (`artel.main()`), не прямым вызовом `amend.cmd_amend_tests` —
SPEC называет только форму `amend-tests <id> --reason "<основание>"
--from-branch`, разбор флага — дело диспетчера `artel.py`, не
обязательно `cmd_amend_tests` сам его видит (сигнатура функции после
этой задачи документом не зафиксирована). Настоящий git
(`RealGitSandbox`) — источник правки AC-7/AC-8 (расхождение между
`tests_locked_sha` и головой артефактной ветки) без настоящего git не
проверить.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (amend, artel, artifact_branch, catalog, config,  # noqa: E402
                          fsm, gitcmd, store)
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import (  # noqa: E402
    AC_TEST_BOTH_COVERED, SPEC_V2)

# Правка планки, содержательно отличная от AC_TEST_BOTH_COVERED, — только
# для создания настоящего расхождения git-содержимого acceptance_tests/
# между tests_locked_sha и головой артефактной ветки (AC-7/AC-8). Имена
# намеренно БЕЗ префикса test_ac<n>_ и БЕЗ строк «# AC-n: kind — причина»:
# guard.scan_acceptance_tests читает содержимое *.py текстом, не AST — эта
# строка живёт ВНУТРИ файла тестов ЭТОЙ ЖЕ задачи (tasks/
# 01M287TPG0HAVXS8CHBCY679WN/acceptance_tests/), и разметка вида test_ac1_/
# «AC-2: manual», случайно попавшая в строковую фикстуру, читалась бы
# guard'ом как настоящая AC-разметка ЭТОЙ задачи (в отличие от
# tests/test_amend.py::AC_TEST_AMENDED — тот файл вне tasks/<id>/
# acceptance_tests/, guard его не сканирует вовсе).
AC_TEST_AMENDED = '''"""Стаб для теста amend-tests --from-branch: содержимое
не имеет отношения к критериям SPEC этой задачи, нужно только как ВТОРОЕ,
отличное от AC_TEST_BOTH_COVERED содержимое той же планки."""
import unittest


class StubAcceptanceTest(unittest.TestCase):
    def test_stub_first_check(self):
        self.assertTrue(True)

    def test_stub_second_check(self):
        self.assertEqual(1 + 1, 2)
'''


class _FromBranchAmendSandbox(RealGitSandbox):
    """Задача доведена до `in_dev` с уже зафиксированным `tests_locked_
    sha` — тот же рецепт, что `tests/test_amend.py::
    AmendThenReviewGateTest.enter_in_dev` (SPEC_V2/AC_TEST_BOTH_COVERED
    того же файла-образца)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "amend-tests --from-branch")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self._enter_in_dev()

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(
            self.TASK, files, f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} на артефактную ветку не удался")
        return sha

    def _enter_in_dev(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra="")},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.state(), "in_dev")

    def journal_texts(self) -> list:
        return [f"{s['action']} {s['detail']}"
               for s in store.task_steps(self.conn, self.TASK)]

    def run_amend(self, reason: str, *, from_branch: bool) -> str:
        argv = ["artel.py", "amend-tests", self.TASK, "--reason", reason]
        if from_branch:
            argv.append("--from-branch")
        with mock.patch.object(sys, "argv", argv):
            return capture(artel.main)


class Ac7FromBranchDivergenceMovesLockTest(_FromBranchAmendSandbox):
    """AC-7."""

    def test_ac7_divergence_journals_files_and_moves_lock_to_branch_head(self):
        """Содержимое `acceptance_tests/` на голове артефактной ветки
        разошлось с `tests_locked_sha` (например автокоммит шага роли
        унёс правку, минуя `amend-tests`, — SPEC «Контекст») —
        `amend-tests ... --from-branch` журналирует список отличающихся
        файлов и сдвигает `tests_locked_sha` на голову артефактной
        ветки с записью «правка планки».

        Ловит мутацию: `--from-branch` продолжает сверять с worktree
        (тот же путь, что и без флага) — расхождение, УЖЕ существующее
        только на ветке, не на диске worktree, никогда не находится, и
        команда отказывает «нет изменений» вместо фиксации.
        """
        new_sha = self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_AMENDED},
            "правка планки (автокоммит шага роли, минуя amend-tests)")

        out = self.run_amend("синхронизация с веткой", from_branch=True)

        self.assertEqual(
            self.row()["tests_locked_sha"], new_sha,
            f"tests_locked_sha не сдвинут на голову ветки: {out}")
        texts = self.journal_texts()
        matched = [t for t in texts if amend.AMEND_ACTION in t]
        self.assertTrue(matched, f"нет записи «{amend.AMEND_ACTION}» в журнале: {texts}")
        self.assertIn("test_ac.py", matched[-1],
                      "журнал обязан назвать отличающийся файл")


class Ac8FromBranchNoDivergenceRefusesTest(_FromBranchAmendSandbox):
    """AC-8."""

    def test_ac8_no_divergence_refuses_with_no_divergence_message(self):
        """Содержимое `acceptance_tests/` головы артефактной ветки
        побайтно совпадает с зафиксированным `tests_locked_sha` —
        `amend-tests ... --from-branch` отказывает («нет расхождения»),
        `tests_locked_sha` не меняется.

        Ловит мутацию: проверка «есть ли расхождение» убрана/ослаблена
        (например сравнение всегда истинно) — команда сдвигала бы лок
        на тот же самый sha без единой реальной правки, легализуя
        воображаемое расхождение.
        """
        old_locked = self.row()["tests_locked_sha"]

        with self.assertRaises(SystemExit) as ctx:
            with mock.patch.object(
                    sys, "argv",
                    ["artel.py", "amend-tests", self.TASK, "--reason",
                     "проверка без правки", "--from-branch"]):
                artel.main()

        self.assertIn("нет расхождения", str(ctx.exception))
        self.assertEqual(self.row()["tests_locked_sha"], old_locked)


class Ac9WithoutFlagBehaviorUnchangedTest(_FromBranchAmendSandbox):
    """AC-9."""

    def test_ac9_without_flag_ignores_divergence_that_exists_only_on_the_branch(self):
        """`amend-tests <id> --reason "<основание>"` БЕЗ `--from-branch`
        ведёт себя так же, как до этой задачи: источник правки — diff
        worktree против артефактной ветки, не сама артефактная ветка
        напрямую. Расхождение, унесённое ПРЯМО на артефактную ветку
        (минуя worktree), без флага не считается правкой — команда
        отказывает «нет изменений», `tests_locked_sha` не меняется, хотя
        ТОТ ЖЕ сценарий с `--from-branch` (AC-7) фиксирует его успешно.

        Ловит мутацию: разбор `--from-branch` просачивается в путь по
        умолчанию (например ветка чтения выбирается по наличию
        расхождения, а не по явному флагу) — команда без флага начинает
        видеть и легализовывать правки, унесённые на ветку в обход
        `amend-tests`, регрессия к смешению источников правки.
        """
        old_locked = self.row()["tests_locked_sha"]
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_AMENDED},
            "правка планки (автокоммит шага роли, минуя amend-tests)")

        with self.assertRaises(SystemExit) as ctx:
            self.run_amend("без флага", from_branch=False)

        self.assertIn("нет изменений", str(ctx.exception))
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "без --from-branch расхождение НА ВЕТКЕ не должно легализовываться")


if __name__ == "__main__":
    unittest.main()
