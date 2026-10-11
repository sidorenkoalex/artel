"""Приёмочные тесты T082 — AC-14, AC-15, AC-16, AC-17.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-14. Красный статус CI ветки задачи на гейте `merge_gate`
автоматически ре-ранится ровно один раз до отказа гейта переходом.

AC-15. Если ре-ран по AC-14 вернул зелёный статус, гейт `merge_gate`
проходит дальше так же, как если бы исходный статус был зелёным
(флейк не блокирует переход).

AC-16. Если ре-ран по AC-14 вернул статус, всё ещё не зелёный, гейт
`merge_gate` отказывает переходом так же, как сегодня (без ре-рана).

AC-17. Каждое срабатывание AC-14 (независимо от исхода) отражается в
метрике flake-rate журнала (флейк учитывается отдельно от подтверждённо
красного исхода).

Песочница — `tests.test_invariants.FsmTest` (та же тяжёлая фикстура
merge_gate/CI, что уже использует `MergeNeedsGreenCiTest` в
`tests/test_invariants.py` и `tasks/T052/acceptance_tests/
test_ac5_red_ci_keeps_task_in_gate.py`), но вместо статичного
`self.set_ci(...)` (одна фиксированная страница ответа `gh` на весь
прогон) здесь напрямую подменяется `ci.branch_status` — единственная
точка, которую зовёт `fsm.py:1119` (SPEC, «Материалы») — управляемой
последовательностью ответов (`side_effect`): первый вызов — исходный
статус, второй — статус ре-рана. `orchestrator/ci.py` — не предмет
этой задачи (требование 7/«Не входит»: «не про сетевую надёжность
опроса GitHub API»), поэтому сам механизм триггера ре-рана (какая
именно команда `gh` его вызывает) тестами не фиксируется — фиксируется
только НАБЛЮДАЕМЫЙ со стороны `fsm.py` контракт: `ci.branch_status`
запрашивается дважды при красном первом ответе, и второй ответ решает
исход гейта.

AC-17 не называет ни формат метрики, ни конкретные слова — тест ищет
по журналу задачи термин «flake-rate» (дословная цитата SPEC требования
7) и проверяет, что запись про флейк (AC-15) и запись про подтверждённый
красный (AC-16) различимы текстом, а не идентичны — точный словарь вне
критерия, различимость — часть его буквальной формулировки («флейк
учитывается отдельно от подтверждённо красного исхода»).

Красен до реализации: 4 из 5 тестов файла (AC-14, AC-15, оба AC-17) —
сегодня `fsm._cmd_approve_merge_gate` зовёт `ci.branch_status` РОВНО
ОДИН РАЗ (`orchestrator/fsm.py:1119`) и сразу решает по первому ответу
— красный статус немедленно отказывает переходом (`sys.exit`), без
какого-либо повторного запроса и без записи в журнал термина
«flake-rate» (которого в коде сегодня нет вовсе). Проверено прогоном на
немодифицированном коде при подготовке файла.

Зелёный с рождения: `test_ac16_confirmed_red_still_refuses_the_gate` —
критерий буквально о том, что подтверждённый красный статус отказывает
«так же, как сегодня» (без ре-рана); сегодняшнее поведение (единственный
запрос, красный статус — отказ переходом, задача остаётся на
`merge_gate`) уже совпадает с этим по наблюдаемому исходу независимо от
того, был ре-ран или нет (`RED, RED` в этом тесте выглядит как «сегодня»
и для одного вызова, и для двух) — тест ловит регрессию этого исхода,
не сам факт ре-рана (его проверяет AC-14).
"""
import contextlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci, fsm, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

RED = (False, "CI коммита abc12345 не зелёный: python=failure")
GREEN = (True, "CI коммита abc12345 зелёный (1 проверок)")


class CiFlakeRerunTest(FsmTest):

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def patched_branch_status(self, *responses):
        mocked = mock.Mock(side_effect=list(responses))
        patcher = mock.patch.object(ci, "branch_status", mocked)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()

    def flake_rate_lines(self) -> list[str]:
        """Строки журнала, упоминающие метрику flake-rate — только они,
        не весь журнал (в остальных записях гейта могут случайно
        встретиться похожие слова по другому поводу)."""
        return [line for line in self.journal_blob().splitlines()
               if "flake-rate" in line]

    def test_ac14_red_first_status_is_rechecked_exactly_once(self):
        mocked = self.patched_branch_status(RED, RED)

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            mocked.call_count, 2,
            "AC-14: красный первый статус CI обязан быть перепроверен "
            "РОВНО ОДИН РАЗ (ре-ран) до отказа гейта — ci.branch_status "
            "обязан быть вызван дважды (исходный статус + один ре-ран), "
            f"фактически вызван {mocked.call_count} раз(а)")

    def test_ac15_flake_recovery_passes_the_gate_like_originally_green(self):
        self.patched_branch_status(RED, GREEN)

        # Сегодняшний код отказывает переходом (`sys.exit`) уже по первому
        # красному ответу, не дожидаясь ре-рана: `SystemExit` глушится
        # здесь же, чтобы тест упал ЧИТАЕМЫМ ассертом состояния ниже, а
        # не необработанной трассировкой.
        with contextlib.suppress(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "done",
            "AC-15: позеленевший после ре-рана статус обязан провести "
            "гейт дальше так же, как изначально зелёный CI — задача "
            "обязана дойти до done")

    def test_ac16_confirmed_red_still_refuses_the_gate(self):
        self.patched_branch_status(RED, RED)

        with self.assertRaises(SystemExit) as exit_:
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn("merge отклонён", str(exit_.exception))
        self.assertEqual(
            self.state(), "merge_gate",
            "AC-16: статус, оставшийся красным после ре-рана, обязан "
            "отказывать гейт так же, как сегодня — задача остаётся на "
            "гейте merge")

    def test_ac17_flake_outcome_is_recorded_in_the_flake_rate_metric(self):
        self.patched_branch_status(RED, GREEN)

        # Тот же приём, что и в AC-15 выше: сегодняшний код отказывает
        # уже на первом красном ответе — `SystemExit` глушится, чтобы
        # тест упал по содержательному ассерту журнала, а не трассировке.
        with contextlib.suppress(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        lines = self.flake_rate_lines()
        self.assertTrue(
            lines,
            f"AC-17: срабатывание AC-14 обязано отразиться в метрике "
            f"flake-rate журнала; журнал: {self.journal_blob()!r}")
        self.assertTrue(
            any("флейк" in line or "flake" in line for line in lines),
            f"AC-14/AC-15/AC-17: исход «позеленел после ре-рана» обязан "
            f"быть узнаваем как флейк в записи flake-rate; строки: {lines!r}")

    def test_ac17_confirmed_red_outcome_is_distinct_from_flake_in_the_metric(self):
        self.patched_branch_status(RED, RED)

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        lines = self.flake_rate_lines()
        self.assertTrue(
            lines,
            f"AC-17: срабатывание AC-14 обязано отразиться в метрике "
            f"flake-rate журнала даже когда ре-ран подтвердил красный "
            f"статус; журнал: {self.journal_blob()!r}")
        # AC-17: «флейк учитывается отдельно от подтверждённо красного
        # исхода» — запись обязана нести опознаваемое слово ПОДТВЕРЖДЁННОГО
        # исхода (не просто отсутствие слова «флейк», которое могло бы
        # встретиться и в обороте «НЕ флейк» — точный словарь SPEC не
        # называет, поэтому проверяется набор разумных кандидатов).
        self.assertTrue(
            any(kw in line for line in lines
               for kw in ("подтвержд", "confirm", "красн", "red")),
            f"AC-16/AC-17: подтверждённый красный исход обязан быть "
            f"опознаваем в записи flake-rate ОТДЕЛЬНО от флейка; строки: "
            f"{lines!r}")


if __name__ == "__main__":
    unittest.main()
