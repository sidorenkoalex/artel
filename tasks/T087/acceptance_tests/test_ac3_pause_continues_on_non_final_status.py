"""AC-3 (tasks/T087/SPEC.md): цикл ожидания повторяет проверку статуса
CI пушнутого head с паузой между попытками — конфиг-константа порядка
60-120 секунд; статус «CI ещё идёт» или «статус неизвестен» продолжает
цикл, а не завершает команду.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-3.

Длительность паузы не сверяется с литеральной константой (SPEC не
называет её имя — решение разработчика, `tasks/T087/SPEC.md` требование
12 отдаёт имя новой конфиг-константы на усмотрение реализации; тест не
имеет права навязать имя, которого нет в SPEC) — сверяется НАБЛЮДАЕМАЯ
длительность запрошенной паузы (`FakeClock.sleep_calls`, песочница
`_sandbox.py`) с формулировкой критерия «порядка 60-120 секунд»: полоса
допуска [30, 240] сек — вдвое шире буквального диапазона в обе стороны,
чтобы не цепляться к пограничному выбору разработчика (SPEC говорит
«порядка», не «ровно»), но при этом ловить явно неправильный порядок
величины (доли секунды или часы).

Красен до реализации: сегодня после исхода "pulled" `approve`
останавливается СРАЗУ, `ci.branch_status` не вызывается вовсе в этом
вызове (`orchestrator/fsm.py`), а после единственного вызова из
СЛЕДУЮЩЕГО `approve` красный/неизвестный статус не паузит и не
продолжает цикл — либо отказывает переходом (красный), либо (для
"ещё идёт"/"неизвестен", `ci.status_kind(note) != "red"`) тоже отказывает
`sys.exit` без единой паузы. И то и другое ловится
`self.assertEqual(self.state(), "done", ...)` ниже — сегодняшний код
оставляет задачу на `merge_gate`, не `done`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import GREEN, MergeGateCiWaitTest, RUNNING, UNKNOWN  # noqa: E402

MIN_PLAUSIBLE_PAUSE_SEC = 30
MAX_PLAUSIBLE_PAUSE_SEC = 240


class Ac3PauseContinuesOnNonFinalStatusTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()

    def test_ac3_running_then_unknown_then_green_reaches_done(self):
        self.add_main_commit()
        responses = [RUNNING, UNKNOWN, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        self.approve()

        self.assertGreaterEqual(
            calls["n"], 3,
            f"предпосылка теста: обязаны быть прочитаны все три статуса "
            f"(идёт/неизвестен/зелёный), фактически {calls['n']}")
        self.assertEqual(
            self.state(), "done",
            "AC-3: статусы «ещё идёт» и «неизвестен» обязаны продолжать "
            "цикл ожидания (не останавливать approve) — команда обязана "
            "довести задачу до done после последующего зелёного статуса")

    def test_ac3_pause_between_attempts_is_on_the_order_of_60_to_120_seconds(self):
        self.add_main_commit()
        responses = [RUNNING, UNKNOWN, GREEN]
        calls = {"n": 0}

        def sequenced(branch):
            resp = responses[min(calls["n"], len(responses) - 1)]
            calls["n"] += 1
            return resp

        self.patch_branch_status(sequenced)

        self.approve()

        self.assertGreaterEqual(
            len(self.clock.sleep_calls), 2,
            f"AC-3: между непоследними итерациями обязана быть пауза — "
            f"ожидались минимум 2 паузы (после «идёт» и после "
            f"«неизвестен»), зафиксировано {self.clock.sleep_calls!r}")
        for duration in self.clock.sleep_calls:
            self.assertTrue(
                MIN_PLAUSIBLE_PAUSE_SEC <= duration <= MAX_PLAUSIBLE_PAUSE_SEC,
                f"AC-3: пауза между попытками обязана быть порядка "
                f"60-120 сек, зафиксирована пауза {duration} сек — вне "
                f"правдоподобной полосы "
                f"[{MIN_PLAUSIBLE_PAUSE_SEC}, {MAX_PLAUSIBLE_PAUSE_SEC}]")


if __name__ == "__main__":
    import unittest
    unittest.main()
