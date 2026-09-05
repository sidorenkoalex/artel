"""Приёмочные тесты 01M1RHFRQ2C0P4A57XJJ1WZV8N — AC-3, AC-4 (часть
`orchestrator/fsm_advance.py`), AC-6, AC-7: гейт `in_dev -> review`
сверяет REVIEW.md текущей итерации и кодовую ветку «по времени/sha, не по
тексту» (требование 3) — REVIEW.md живёт в АРТЕФАКТНОЙ ветке пульта, код
— в ОТДЕЛЬНОЙ кодовой ветке (`orchestrator/artifact_source.py`, `foreign`
всегда `True`), общего родителя у двух веток нет, поэтому единственный
осмысленный признак «после» — отметка времени коммита, не sha
(рассуждение подробнее — докстринг `_sandbox.py::ReviewGateGitSandbox`).

Красен до реализации: `orchestrator/fsm_advance.py::in_dev` (строки
650-773, прочитано перед написанием этого файла) не читает ни REVIEW.md,
ни время коммитов кодовой ветки вовсе — гейт сегодня смотрит только на
`PLAN.md` (`status`), лок `acceptance_tests/` (`tests_locked_sha`),
свежесть относительно main и ёмкость/зоны диффа; ничего в этом теле не
отказывает переходу на основании «REVIEW.md всё ещё `changes_requested`,
а код не менялся с его коммита» — тесты AC-3/AC-4/AC-7 (неизменённый код)
покраснеют переходом в `review`. AC-6 (код изменился) — контрольный,
проверяет, что реализация НЕ переусердствует и не блокирует переход,
когда developer уже сделал шаг: он должен остаться зелёным и до, и после
фикса (гейта, которого сегодня нет, разумеется, ничто не блокирует).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ReviewGateGitSandbox, RoleTaggedSpy  # noqa: E402
from orchestrator import auto, config, fsm, runner, store  # noqa: E402

REVIEW_COMMIT_TS = "2026-01-01T00:10:00+00:00"
DEVELOPER_FIX_TS = "2026-01-01T00:20:00+00:00"

NAMED_REFUSAL_PHRASE = ("замечания ревью не отработаны: нет шага developer "
                        "после итерации 1")


class GateRefusesUnchangedCodeAfterChangesRequestedTest(ReviewGateGitSandbox):
    """AC-3: REVIEW.md текущей итерации — `changes_requested`, кодовая
    ветка не получила ни одного коммита после его коммита — переход не
    происходит."""

    def test_ac3_gate_refuses_when_no_developer_commit_followed_the_verdict(self):
        """Ловит мутацию: сверка идёт по ТЕКСТУ (например, «PLAN.md status
        не менялся») вместо времени коммитов — тест, где PLAN.md
        буквально не редактировался ни разу (тем же приёмом, каким уже
        сегодня минуют этот гейт задачи без единого шага developer),
        должен отличаться от теста AC-6 именно фактом ОТСУТСТВИЯ нового
        коммита на кодовой ветке, не отсутствием правки PLAN.md — мутация,
        путающая эти два признака, не будет поймана его отсутствием.
        """
        self.enter_in_dev_after_changes_requested(REVIEW_COMMIT_TS)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "переход in_dev -> review прошёл на неизменённом коде после "
            "changes_requested")


class GateNamesTheIterationInTheJournalTest(ReviewGateGitSandbox):
    """AC-4 (часть `fsm_advance.py`): отказ этого рубежа именован и
    журналируется с номером итерации — тем же текстом, что и рубеж
    `auto.py` (AC-1/AC-2), см. `test_ac1_ac4_ac9_auto_developer_step_
    gate.py::NamedAndJournaledAutoRefusalTest`."""

    def test_ac4_gate_names_the_iteration_of_the_unresolved_review(self):
        """Ловит мутацию: рубеж держится (AC-3 зелёный), но отказ
        журналируется обобщённым текстом без номера итерации — assertion
        на буквальную фразу требования 4 падает, даже если сам переход
        уже корректно не пропущен.
        """
        self.enter_in_dev_after_changes_requested(REVIEW_COMMIT_TS)

        self.capture(fsm.cmd_advance, self.TASK)

        rows = self.journal_rows()
        haystacks = [action for _, action, _ in rows] + [detail for _, _, detail in rows]
        self.assertTrue(
            any(NAMED_REFUSAL_PHRASE in text for text in haystacks),
            f"журнал не несёт именованной причины «{NAMED_REFUSAL_PHRASE}»: "
            f"{rows}")


class DeveloperCommitAfterTheVerdictUnblocksTheGateTest(ReviewGateGitSandbox):
    """AC-6: после завершённого шага developer (новый коммит кодовой
    ветки ПОСЛЕ вердикта REVIEW.md, а также запись `agent run finished`
    роли developer с последней `state -> in_dev`) следующий `advance`
    (в т.ч. предварительный внутри `auto`) проходит штатно — рубежи
    AC-1/AC-3 не блокируют его."""

    def test_ac6_developer_step_after_return_unblocks_both_gates(self):
        """Ловит мутацию: гейт AC-3 сравнивает время БЕЗ учёта конкретного
        коммита REVIEW.md (например, «любой коммит кодовой ветки новее
        входа в in_dev», не «новее коммита ИМЕННО REVIEW.md текущей
        итерации») — тест ниже единственный во всём файле, где реальный
        коммит кода существует ПОСЛЕ вердикта, и обязан остаться зелёным;
        также ловит мутацию рубежа `auto.py` (AC-1): развёрнутый до
        предела в `1` `AUTO_MAX_STEPS`, `auto` не имеет права позвать
        `runner.cmd_run` для роли developer повторно — она уже
        зафиксирована журналом как отработавшая.
        """
        self.enter_in_dev_after_changes_requested(REVIEW_COMMIT_TS)
        conn = store.db()
        # Журнал требования 1 (AC-1): запись перехода в `in_dev` и
        # завершённый шаг developer ПОСЛЕ неё — `auto` не обязан (и не
        # должен) звать `cmd_run` для этой роли снова.
        store.journal(conn, self.TASK, "fsm", "state -> in_dev",
                      "замечания ревью, итерация 1")
        self.commit_developer_fix("developer: правка по замечаниям",
                                  DEVELOPER_FIX_TS)
        store.journal(conn, self.TASK, "developer", "agent run finished",
                      "rc=0, тестовая заглушка приёмочного теста")

        spy = RoleTaggedSpy(conn)
        with mock.patch.object(config, "AUTO_MAX_STEPS", 1), \
             mock.patch.object(runner, "cmd_run", spy):
            self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(
            "developer", spy.calls,
            f"developer был запущен снова — шаг уже зафиксирован журналом "
            f"(вызовы: {spy.calls})")
        self.assertEqual(
            self.state(), "review",
            "переход in_dev -> review не прошёл, хотя developer уже "
            "отработал замечания реальным коммитом кодовой ветки")


class ManualAdvanceOnUnchangedCodeIsNamedNotSilentTest(ReviewGateGitSandbox):
    """AC-7: ручной `advance` Оператора (не через `auto`) на неизменённом
    коде после `changes_requested` — именованный отказ (AC-4), а не
    переход в `review`."""

    def test_ac7_manual_advance_on_unchanged_code_refuses_named_not_transitions(self):
        """Ловит мутацию: рубеж AC-3 реализован ТОЛЬКО внутри `auto.py`
        (например, как ещё одно условие пред-advance, а не в самом
        `fsm_advance.in_dev`) — прямой вызов `fsm.cmd_advance` Оператором,
        минуя `auto` целиком (этот тест НЕ зовёт `auto.cmd_auto` ни разу),
        тогда пройдёт беспрепятственно: рубеж обязан жить в самом гейте
        перехода, не только в обёртке цикла.
        """
        self.enter_in_dev_after_changes_requested(REVIEW_COMMIT_TS)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertIn(NAMED_REFUSAL_PHRASE, out)
        self.assertNotIn("MR готов — прогон ревьювера", out)


if __name__ == "__main__":
    import unittest
    unittest.main()
