"""Приёмочные тесты 01M28NWPS3PJHJAT4APXRY7MF7 — AC-3, AC-7 (SPEC.md).

`runner.cmd_run` для роли developer, реальный проход через атомарный
захват (AC-1) — но шаг намеренно не стартует ПОСЛЕ захвата: `doctor.
preflight_checks` (уже застабленный `FsmTest.setUp` пустым списком —
см. `_sandbox.py`) переопределяется здесь на отказ, тот же класс причины
остановки, что требование 2 SPEC называет буквально («ошибка окружения»)
— происходит СТРОГО после занятости зоны (`runner._cmd_run`: занятость
проверяется до pre-flight, ADR-0003 п.17) и СТРОГО до сборки промпта и
спавна агента, так что `spawn_agent` не вызывается вовсе — задача
«захватила зону, но код не начала» ровно того класса, что требование 2
описывает.

Красен до реализации: захвата (`zone_lock.CLAIM_ACTION`) сегодня не
существует вовсе — цикл ниже не находит ни одной такой записи в журнале
(`claimed == []`), первый же `assertEqual(len(claimed), 1, ...)` падает
раньше, чем дойдёт до проверки снятия.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneClaimSandbox  # noqa: E402

from orchestrator import doctor, runner, store, zone_lock  # noqa: E402
from tests.sandbox import capture  # noqa: E402

CANDIDATE = "T900"


def _failing_preflight(role, target):
    return [doctor.Check("тест", "fail", "принудительный отказ теста —"
                          " шаг не должен стартовать после захвата зоны")]


class Ac3FailedStartAfterClaimReleasesTheZoneTest(ZoneClaimSandbox):
    """AC-3: если в рамках ТОГО ЖЕ вызова `cmd_run` шаг фактически не
    стартовал после захвата — захват снимается записью `"zone claim
    released"` в той же функции.

    Ловит мутацию: см. докстринг модуля — без снятия `released` остаётся
    пустым, задача, ни разу не запустившая агента, продолжала бы считаться
    занявшей зону бесконечно."""

    def test_ac3_preflight_failure_after_claim_writes_release(self):
        with mock.patch.object(doctor, "preflight_checks", _failing_preflight):
            out = capture(runner.cmd_run, self.TASK)

        self.assertIn("pre-flight провален", out)
        steps = self.steps(self.TASK)
        claimed = [r for r in steps if r["action"] == zone_lock.CLAIM_ACTION]
        released = [r for r in steps if r["action"] == "zone claim released"]
        self.assertEqual(len(claimed), 1,
                         f"ожидался ровно один захват зоны в журнале: {steps}")
        self.assertEqual(len(released), 1,
                         f"ожидалось ровно одно снятие захвата в журнале: {steps}")
        self.assertGreater(released[0]["id"], claimed[0]["id"],
                           "снятие записано РАНЬШЕ захвата — не тот порядок")
        self.assertFalse(zone_lock._occupies(store.db(), self.TASK),
                         "задача, не начавшая код, осталась занявшей зону")


class Ac7NextCandidatePassesTheZoneCheckAfterAutoReleaseTest(ZoneClaimSandbox):
    """AC-7: после автоматического снятия (AC-3) следующий кандидат на ту
    же зону проходит проверку блокировки.

    Ловит мутацию: захват снимается, но `_occupies`/`blocking_conflict`
    не учитывают снятие (регрессия AC-4) — кандидат остался бы
    заблокирован задачей, которая уже провалила старт и код не пишет.
    Явная проверка `claimed` ДО сверки кандидата (не только в AC-3) —
    без неё тест ложно зеленел бы и по мутации «захват вообще не
    записывается»: тогда `self.TASK` никогда не занимал зону, кандидат
    прошёл бы `blocking_conflict` по той же причине, что и настоящее
    снятие, и тест не отличил бы «снято» от «не захватывалось вовсе»."""

    def test_ac7_candidate_passes_blocking_conflict_after_release(self):
        with mock.patch.object(doctor, "preflight_checks", _failing_preflight):
            capture(runner.cmd_run, self.TASK)

        claimed = [r for r in self.steps(self.TASK)
                  if r["action"] == zone_lock.CLAIM_ACTION]
        self.assertEqual(len(claimed), 1,
                         "предпосылка теста не выполнена — зона не была "
                         "захвачена перед провалившимся стартом")
        self.seed_fake_occupant(CANDIDATE, "in_dev", self.ZONE)

        conflict = zone_lock.blocking_conflict(
            store.db(), CANDIDATE, store.get_task(store.db(), CANDIDATE))

        self.assertIsNone(
            conflict,
            f"кандидат остался заблокирован снятым захватом {self.TASK}: "
            f"{conflict}")


if __name__ == "__main__":
    import unittest
    unittest.main()
