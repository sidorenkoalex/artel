"""AC-15: Существующие тесты инвариантов 12 (мержит только `approve` из
`merge_gate`) и 19 (merge требует зелёного CI головного коммита ветки
задачи) остаются кодированы и зелены без ослабления проверяемого ими
утверждения.

Инвариант 12 — `tests/test_invariants.py::MergeOnlyFromMergeGateTest`.
Инвариант 19 — `tests/test_invariants.py::MergeNeedsGreenCiTest`.

Что этот файл делает, и почему НЕ дословным повторным прогоном ВСЕГО
класса каждого инварианта:

- `MergeOnlyFromMergeGateTest.test_no_other_state_and_no_other_command_
  merges` — прогоняется НАПРЯМУЮ (импорт `tests.test_invariants`,
  безопасно: этот модуль не несёт одноимённого локального `_sandbox.py`,
  в отличие от `tasks/T056/acceptance_tests/`, риск коллизии импорта —
  см. докстринг `test_ac11_worktree_invariant_unchanged.py`). Метод
  механически не зависит от МЕХАНИКИ approve (явно пропускает пару
  `state == "merge_gate" and name == "approve"`, строка `continue`
  внутри) — проверяет, что НИ ОДИН ДРУГОЙ переход/команда не мержит,
  что бы ни делал сам approve; безопасно прогнать буквально.
- Тот же класс несёт `test_merge_gate_approve_is_that_path` —
  КОНТРОЛЬНЫЙ тест того же файла, сверяющий порядок git-подкоманд
  `checkout < merge`/`pull < merge` approve. Мандат Оператора (ANSWER-1,
  вопрос 1) явно переносит approve на плотницкую запись БЕЗ `git
  checkout` вовсе — эта проверка порядка ПОДКОМАНД сама специфична
  старому чекаут-механизму, который AC-8 заменяет по мандату; SPEC
  «Не входит» отдельно отмечает, что ADR на этот перенос не требуется
  (мандат уже дан). Дословный повторный прогон ИМЕННО этого метода
  запер бы старую реализацию approve, а не «проверяемое утверждение»
  инварианта 12 (который — «мержит только approve», не «approve мержит
  ИМЕННО чекаутом») — поэтому этот файл проверяет СУТЬ инварианта 19
  (ниже) собственным прогоном через реальный git, не берёт в лок
  чекаут-специфичные подкоманды.
- Инвариант 19 (`MergeNeedsGreenCiTest`) в исходном файле мокает git
  целиком (`SpyRun`) и сверяется по ИМЕНИ подкоманды `"merge"` в списке
  вызовов — та же самая связанность с механизмом approve. Здесь —
  собственная проверка через РЕАЛЬНЫЙ git (`ArtelSelfTargetSandbox`,
  общая с AC-8/9/12): красный/неизвестный CI не продвигает `refs/heads/
  main` origin артели вовсе (задача остаётся на `merge_gate`), зелёный —
  продвигает; проверка ИСХОДА, не конкретных git-команд, поэтому
  остаётся верной вне зависимости от внутренней механики approve.

Зелёный с рождения (обе части): `test_no_other_state_and_no_other_
command_merges` не тронут этой задачей и уже сегодня зелен; собственная
проверка ниже сверяет ИСХОД (двигается/не двигается main), который верен
и до, и после AC-8 — обе части обязаны проходить уже сегодня.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, fsm_merge_gate, store  # noqa: E402
# Импорт МОДУЛЯ, не `from tests.test_invariants import
# MergeOnlyFromMergeGateTest`: связывание класса верхнеуровневым именем
# в ЭТОМ модуле сделало бы его видимым обычному discovery
# (`unittest.TestLoader.loadTestsFromModule` подбирает любой
# `TestCase`-подкласс, доступный атрибутом модуля) — тогда прогонялся бы
# ВЕСЬ класс `MergeOnlyFromMergeGateTest` целиком (включая
# checkout/pull-специфичный `test_merge_gate_approve_is_that_path`,
# который этот файл намеренно не берёт в лок, см. докстринг модуля), а
# не только один выбранный метод ниже.
import tests.test_invariants as _test_invariants  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402

TASK = "01ARTELINV1219CHECK001"


class Invariant12CoreAssertionStillHoldsTest(unittest.TestCase):
    """Прогоняет РОВНО ОДИН метод существующего теста инварианта 12 —
    тот, что не зависит от механики самого approve (см. докстринг модуля)."""

    def test_ac15_no_other_state_or_command_merges(self):
        """`tests.test_invariants.MergeOnlyFromMergeGateTest.
        test_no_other_state_and_no_other_command_merges` по-прежнему
        существует и проходит.

        Ловит мутацию: удаление/переименование метода — `TypeError` при
        конструировании `TestCase` с несуществующим именем метода;
        ослабление его тела (снятие проверки для одного из
        состояний/команд) — сам оригинальный тест покраснеет при
        прогоне.

        Только ЭТОТ ОДИН метод — не весь класс: класс несёт РЯДОМ
        `test_merge_gate_approve_is_that_path` (checkout/pull-специфичный
        контроль, см. докстринг модуля), который прогонять здесь нельзя
        — `TestCase(methodName)` запускает ровно один именованный метод,
        не все методы класса (в отличие от `TestLoader.
        loadTestsFromTestCase`, который взял бы их все).
        """
        test_case = _test_invariants.MergeOnlyFromMergeGateTest(
            "test_no_other_state_and_no_other_command_merges")
        result = unittest.TestResult()
        test_case.run(result)

        self.assertTrue(result.wasSuccessful(),
                        f"инвариант 12 (test_invariants.py) покраснел: "
                        f"{result.failures + result.errors}")


class Invariant19OutcomeThroughRealGitTest(ArtelSelfTargetSandbox):
    """Суть инварианта 19 через реальный git, не через имя git-подкоманды
    (см. докстринг модуля — почему не переиспользуется `MergeNeedsGreenCiTest`
    буквально)."""

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.make_task_branch_in_root(
            self.branch, "feature.txt", "код фичи\n", f"{TASK}: код фичи")
        self.insert_task(TASK, self.branch, "merge_gate")

    def approve(self):
        t = store.get_task(store.db(), TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t)

    def test_ac15_red_ci_does_not_advance_origin_main_task_stays_on_gate(self):
        """Красный CI ветки задачи — `approve` НЕ продвигает `refs/heads/
        main` origin артели, задача остаётся на `merge_gate`.

        Ловит мутацию: любую правку, из-за которой плотницкий merge (AC-8)
        выполняется ДО сверки зелёного CI (перестановка порядка проверок)
        — origin main продвинется даже при красном CI.
        """
        before_origin_main = self.origin_main_sha()
        with mock.patch.object(ci, "branch_status",
                               lambda branch: (False, "failure (тест)")):
            with mock.patch.object(ci, "status_kind", lambda note: "red"), \
                 mock.patch.object(ci, "trigger_rerun", lambda branch: None):
                try:
                    self.approve()
                except SystemExit:
                    pass

        self.assertEqual(self.origin_main_sha(), before_origin_main,
                         "main артели не должен продвинуться при красном CI")
        self.assertEqual(store.get_task(store.db(), TASK)["state"], "merge_gate")

    def test_ac15_green_ci_advances_origin_main_and_reaches_done(self):
        """Контроль: зелёный CI — `approve` продвигает `refs/heads/main`
        origin артели и доводит задачу до `done` (симметрично AC-8)."""
        before_origin_main = self.origin_main_sha()
        with mock.patch.object(ci, "branch_status",
                               lambda branch: (True, "зелёный (тест)")):
            result = self.approve()

        self.assertEqual(result, ("done",))
        self.assertNotEqual(self.origin_main_sha(), before_origin_main)
        self.assertEqual(store.get_task(store.db(), TASK)["state"], "done")


if __name__ == "__main__":
    unittest.main()
