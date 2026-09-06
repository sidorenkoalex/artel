"""AC-4, AC-9 (SPEC 01M1VBEFR987MGAK0XAFMVVYZY): `amend-tests <id>
--reason … --from-branch` источником правки берёт расхождение
`acceptance_tests/` между `tests_locked_sha` и головой артефактной ветки
(не рабочим деревом). При расхождении — журналирует список изменившихся
файлов и сдвигает `tests_locked_sha` на голову артефактной ветки с
записью «правка планки», как обычный `amend-tests`. Без расхождения —
отказ «нет расхождения». Без флага `--from-branch` поведение команды не
меняется. AC-9 — те же три сценария, поставленные SPEC как отдельный
обязательный тест критерия, с явным акцентом на мутацию «сдвиг лока без
расхождения — красный».

Смешанная краснота — по тестам, не по файлу целиком:
- `test_..._moves_lock_to_divergent_artifact_branch_head` (AC-4/AC-9,
  happy path) — Красен до реализации: флаг `--from-branch` сегодня нигде
  не разбирается (`orchestrator/artel.py::_reason_arg`/диспетчер команды
  `amend-tests` не знают о нём) — команда молча исполняет СТАРЫЙ путь по
  worktree, который в этом сценарии видит `disk == baseline` (оба —
  текущая голова артефактной ветки) и отказывает «нет изменений»,
  вместо ожидаемого успешного сдвига лока.
- `test_..._without_divergence_refuses_with_no_divergence_message` и
  `test_ac9_no_divergence_lock_stays_put` — Красен до реализации: то же
  отсутствие разбора флага — сегодняшний код честно откажет «нет
  изменений» (не «нет расхождения» — другая формулировка), значит
  сравнение точного текста сообщения обязано покраснеть до реализации.
- `test_..._without_from_branch_flag_keeps_worktree_only_comparison`
  (AC-4/AC-9, регрессия) — Зелёный с рождения: без `--from-branch`
  команда сегодня уже сравнивает только worktree, и сценарий теста
  (расхождение только на ветке, worktree материализуется из текущей
  головы и потому совпадает с ней же) уже сегодня даёт «нет изменений» —
  это ожидаемая планка, которую реализация `--from-branch` не имеет
  права затронуть.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import amend, gitcmd  # noqa: E402
from _sandbox import AC_TEST_DIVERGED, TaskSandbox  # noqa: E402

REASON = "правка автокоммита шага роли (регресс 06.09, легализация Оператором)"


class Ac4FromBranchDivergenceTest(TaskSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.old_locked = self.row()["tests_locked_sha"]

    def _diverge_artifact_branch(self) -> str:
        """Симулирует «правку, унесённую автокоммитом шага роли» (SPEC
        «Контекст») — новый коммит на артефактной ветке, изменяющий
        `acceptance_tests/`, БЕЗ единого вызова `amend-tests`."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_DIVERGED},
            "автокоммит шага developer (WIP)")
        return gitcmd.branch_head_sha(self.branch)

    def test_ac4_from_branch_moves_lock_to_divergent_artifact_branch_head(self):
        """Расхождение между `tests_locked_sha` и головой артефактной
        ветки (автокоммит шага роли уже изменил `acceptance_tests/`) —
        `amend-tests --from-branch` обязана сдвинуть `tests_locked_sha`
        РОВНО на текущую голову артефактной ветки, записать «правка
        планки» и назвать в журнале изменившийся файл.

        Ловит мутацию: команда сравнивает worktree (старый путь) вместо
        `tests_locked_sha` vs голова ветки — расхождение, реально
        случившееся ТОЛЬКО на ветке, осталось бы незамеченным, и лок не
        сдвинулся бы вовсе."""
        new_head = self._diverge_artifact_branch()
        self.assertNotEqual(new_head, self.old_locked)

        self.run_cli("amend-tests", self.TASK, "--reason", REASON,
                     "--from-branch")

        self.assertEqual(self.row()["tests_locked_sha"], new_head)
        self.assertTrue(
            any(amend.AMEND_ACTION in a for a in self.journal_actions()))
        self.assertTrue(
            any(f"tasks/{self.TASK}/acceptance_tests/test_ac.py" in d
               for d in self.journal_details()),
            f"журнал обязан назвать изменившийся файл: {self.journal_details()}")

    def test_ac4_from_branch_without_divergence_refuses_with_no_divergence_message(self):
        """Голова артефактной ветки совпадает с `tests_locked_sha` (никто
        не менял `acceptance_tests/` после лока) — `amend-tests
        --from-branch` обязана отказать именно словами «нет расхождения»
        (SPEC AC-4 дословно), не сдвигая лок.

        Ловит мутацию: отказ использует старую формулировку «нет
        изменений» (скопированную с worktree-пути) вместо «нет
        расхождения» — Оператор/лог не отличили бы источник сравнения
        друг от друга по тексту сообщения."""
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("amend-tests", self.TASK, "--reason", REASON,
                         "--from-branch")

        self.assertIn("нет расхождения", str(ctx.exception))
        self.assertEqual(self.row()["tests_locked_sha"], self.old_locked)

    def test_ac4_without_from_branch_flag_keeps_worktree_only_comparison(self):
        """Без флага `--from-branch` поведение не меняется: расхождение
        ЕСТЬ на ветке (автокоммит шага роли), но worktree Оператора
        девственно чист (материализуется из ТЕКУЩЕЙ головы ветки) —
        старый (worktree-based) отказ «нет изменений» обязан сработать
        как раньше, несмотря на реальное расхождение по ветке.

        Ловит мутацию: `--from-branch` реализован как НОВОЕ поведение ПО
        УМОЛЧАНИЮ (флаг влияет только на текст сообщения, но не на то,
        какой путь сравнения включается) — команда без флага ошибочно
        сдвинула бы лок на голову ветки, хотя SPEC требует, чтобы «без
        флага поведение команды не менялось»."""
        self._diverge_artifact_branch()

        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("amend-tests", self.TASK, "--reason", REASON)

        self.assertIn("нет изменений", str(ctx.exception))
        self.assertEqual(self.row()["tests_locked_sha"], self.old_locked)


class Ac9FromBranchMutationFocusedTest(TaskSandbox):
    """AC-9 дословно: обязательный тест `amend-tests --from-branch",
    ставящий во главу угла именно мутацию «сдвиг лока без расхождения —
    красный»."""

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.old_locked = self.row()["tests_locked_sha"]

    def test_ac9_divergence_moves_lock_with_file_list_in_journal(self):
        """Тот же happy path, что AC-4, — расхождение сдвигает лок на
        голову ветки, журнал называет изменившийся файл.

        Ловит мутацию: журнал пишет только факт «правка планки» без
        перечня файлов — Оператор не смог бы понять постфактум, ЧТО
        именно легализовал, читая только журнал (SPEC требование 3:
        «журналирует диф (список файлов)»)."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_DIVERGED},
            "автокоммит шага developer (WIP)")
        new_head = gitcmd.branch_head_sha(self.branch)

        self.run_cli("amend-tests", self.TASK, "--reason", REASON,
                     "--from-branch")

        self.assertEqual(self.row()["tests_locked_sha"], new_head)
        self.assertTrue(
            any(f"tasks/{self.TASK}/acceptance_tests/test_ac.py" in d
               for d in self.journal_details()))

    def test_ac9_no_divergence_lock_stays_put_despite_command_invocation(self):
        """Без единой правки `acceptance_tests/` после лока — команда
        обязана отказать «нет расхождения» И оставить `tests_locked_sha`
        нетронутым — именно эта пара (отказ + неподвижный лок) и есть
        мутация, названная AC-9 буквально: «сдвиг лока без расхождения —
        красный».

        Ловит мутацию: ранний выход «нет расхождения» убран/ослаблен —
        команда создаёт «холостой» коммит-подтверждение с тем же
        деревом и переставляет `tests_locked_sha` на его sha даже без
        единой реальной правки Оператора, обесценивая сам смысл лока."""
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("amend-tests", self.TASK, "--reason", REASON,
                         "--from-branch")

        self.assertIn("нет расхождения", str(ctx.exception))
        self.assertEqual(self.row()["tests_locked_sha"], self.old_locked)

    def test_ac9_without_flag_worktree_only_behavior_is_unchanged(self):
        """Без `--from-branch`, при том же расхождении по ветке —
        прежнее поведение по worktree (отказ «нет изменений»).

        Ловит мутацию: как в AC-4 — `--from-branch` становится
        поведением по умолчанию независимо от присутствия флага."""
        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_DIVERGED},
            "автокоммит шага developer (WIP)")

        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("amend-tests", self.TASK, "--reason", REASON)

        self.assertIn("нет изменений", str(ctx.exception))
        self.assertEqual(self.row()["tests_locked_sha"], self.old_locked)


if __name__ == "__main__":
    unittest.main()
