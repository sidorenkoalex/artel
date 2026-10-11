"""AC-8 (tasks/T087/SPEC.md): истечение потолка ожидания (AC-4) без
зелёного и без подтверждённо красного статуса CI останавливает
`approve` отказом «статус CI неизвестен»; задача остаётся в состоянии
`merge_gate`.

Источник — tasks/T087/SPEC.md, «Критерии приёмки», AC-8.

Потолок — конфиг-константа «порядка 60 минут» (SPEC требование 4), имя
которой SPEC не называет (решение разработчика) — тест не ждёт час
реального времени и не полагается на угаданное имя/значение константы:
`ci.branch_status` всегда отвечает «ещё идёт», а `FakeClock` песочницы
(`_sandbox.py`) продвигает `time.monotonic()` РОВНО на длительность
каждой РЕАЛЬНО запрошенной паузы (`time.sleep`, не угаданной константой)
— после накопления достаточного числа итераций симулированное
прошедшее время обязано перегнать ЛЮБОЙ правдоподобный потолок «порядка
часа», и `approve` обязан остановиться сам. `MAX_ITERATIONS` — только
защитный потолок теста (не предмет критерия): если отказа не случилось
за это число итераций, тест проваливается ЯВНЫМ диагностическим
сообщением, а не зависает.

Красен до реализации: сегодня цикла ожидания нет вовсе — после "pulled"
`approve` останавливается СРАЗУ без единого вызова `ci.branch_status` в
этом вызове (`orchestrator/fsm.py`), а сообщение отказа — "дождись
зелёного CI... и повтори", не «статус CI неизвестен» (то есть даже если
бы это застряло в MAX_ITERATIONS, `assertIn("неизвестен", ...)`
поймал бы неверный текст раньше исчерпания потолка теста).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MergeGateCiWaitTest, RUNNING  # noqa: E402

# Достаточно с большим запасом: даже при паузе на нижней правдоподобной
# границе (порядка секунд) и потолке на верхней (несколько часов) сотни
# итераций перекрывают правдоподобный диапазон конфигурации; если тест
# упирается в потолок — это сигнал, что реализация не считает элапсед
# от РЕАЛЬНО запрошенных пауз (или не имеет потолка вовсе), а не что
# тесту не хватило запаса.
MAX_ITERATIONS = 2000


class Ac8CeilingExpiryRefusesTest(MergeGateCiWaitTest):

    def setUp(self):
        super().setUp()
        self.enter_merge_gate()
        self.install_fake_monotonic_clock()

    def test_ac8_ceiling_expiry_refuses_with_unknown_status_message(self):
        self.add_main_commit()
        calls = {"n": 0}

        def always_running(branch):
            calls["n"] += 1
            if calls["n"] > MAX_ITERATIONS:
                self.fail(
                    f"AC-8: цикл ожидания не остановился сам после "
                    f"{MAX_ITERATIONS} итераций (симулированное прошедшее "
                    f"время {self.clock.value} сек) — потолок ожидания "
                    f"(AC-4) не сработал")
            return RUNNING

        self.patch_branch_status(always_running)

        with self.assertRaises(SystemExit) as exit_:
            self.approve()

        self.assertIn(
            "неизвестен", str(exit_.exception).lower(),
            f"AC-8: отказ по истечении потолка обязан сообщать «статус "
            f"CI неизвестен», получено: {exit_.exception!r}")
        self.assertEqual(
            self.state(), "merge_gate",
            "AC-8: истечение потолка ожидания обязано оставить задачу "
            "на гейте merge_gate")
        self.assertGreater(
            calls["n"], 1,
            "предпосылка теста: потолок обязан сработать ПОСЛЕ хотя бы "
            "нескольких итераций ожидания, не мгновенно на первой")


if __name__ == "__main__":
    import unittest
    unittest.main()
