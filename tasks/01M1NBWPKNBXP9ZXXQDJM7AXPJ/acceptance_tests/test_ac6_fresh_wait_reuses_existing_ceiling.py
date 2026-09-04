"""AC-6 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Потолок ожидания CI
на пути «fresh после push» — существующая константа `config.
MERGE_GATE_CI_WAIT_CEILING_SEC` (та же, что уже несёт путь «pulled»);
отдельного нового лимита не заводится.

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-6.

Красен до реализации: сегодня путь "fresh" не ждёт CI циклом вовсе (см.
test_ac5/test_ac7) — понятия «потолок ожидания» там нет,
`config.MERGE_GATE_CI_WAIT_CEILING_SEC` этим путём не читается ни разу.
Патченное здесь маленькое значение константы (виртуальные часы) не
может повлиять на исход, которого сегодня попросту нет: отказ
случается на первом же опросе CI, до истечения любого потолка. Проверено
прогоном на немодифицированном коде при подготовке файла: `SystemExit`
с текстом «нет ни одной проверки», часы (`FakeClock`) не сдвинулись ни
разу (`time.sleep` не вызван).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import NOCHECKS, MergeGateFreshCiWaitSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class Ac6FreshWaitReusesExistingCeilingTest(MergeGateFreshCiWaitSandbox):

    def test_ac6_ceiling_expiry_respects_patched_existing_constant(self):
        """CI не отвечает ничем, кроме «нет ни одной проверки», всё
        время ожидания. Патчим САМУ СУЩЕСТВУЮЩУЮ константу `config.
        MERGE_GATE_CI_WAIT_CEILING_SEC` на маленькое значение — цикл
        ожидания на пути "fresh" обязан истощиться именно к этому
        значению виртуальных часов, а не к другому (захардкоженному
        или независимому от конфига) числу.

        Ловит мутацию: код заводит СВОЙ потолок ожидания для пути
        "fresh" (захардкоженное число секунд или отдельная новая
        константа) — подмена `config.MERGE_GATE_CI_WAIT_CEILING_SEC`
        тогда не повлияет на момент истощения, и часы на выходе не
        совпадут с патченным малым значением (либо тест зависнет/
        уйдёт далеко за него — счётчик итераций страхует от зависания).
        """
        iterations = {"n": 0}

        def counted(branch):
            iterations["n"] += 1
            if iterations["n"] > 1000:
                raise AssertionError("цикл ожидания не истощился за 1000 "
                                     "итераций — потолок не читается")
            return NOCHECKS

        self.patch_branch_status(counted)

        with mock.patch.object(config, "MERGE_GATE_CI_WAIT_CEILING_SEC", 5):
            with self.assertRaises(SystemExit) as exit_:
                self.run_cycle()

        self.assertIn("неизвестен", str(exit_.exception).lower())
        self.assertGreaterEqual(
            self.clock.value, 5,
            "потолок обязан быть исчерпан хотя бы до патченного значения")
        self.assertLess(
            self.clock.value, 5 + config.MERGE_GATE_CI_WAIT_POLL_SEC * 2,
            "часы обязаны остановиться вблизи патченного потолка (5 сек), "
            "не уйти на непропатченную (продовую) величину")


if __name__ == "__main__":
    import unittest
    unittest.main()
