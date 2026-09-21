"""AC-9 — 01M300A14KRHCFB0DQXVCBJEKF: строки журнала «agent cost KNOWN» и
«agent cost PARTIAL» несут дату действующего тарифа.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Строки журнала «agent cost KNOWN» и «agent cost PARTIAL» несут дату
действующего тарифа.

Дата берётся нарочно из переопределения локального слоя
(`calibrated_at`), а не из прейскуранта каталога: она не совпадает ни с
сегодняшним днём (`ts` записи), ни с датой прейскуранта, поэтому её
появление в тексте строки нельзя списать на совпадение с чем-то ещё.

Красен до реализации: строка PARTIAL (`orchestrator/spend.py:504-508`)
даты не несёт вовсе, а KNOWN несёт дату калибровки КУРСА РОЛИ
(`config.TOKEN_RATES[role]["calibrated_at"]`, 2026-09-20) — не дату
тарифа модели из локального слоя.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import spend  # noqa: E402

PARTIAL_COST_JOURNAL_ACTION = "agent cost PARTIAL"


class CostLinesCarryTheTariffDateTest(_tariff.TariffSandbox):

    def setUp(self):
        super().setUp()
        # Действующий тариф — собственный тариф локального слоя, значит и
        # дата действующего тарифа — его `calibrated_at`.
        self.use_local(overrides={_tariff.MODEL_ALFA:
                                  _tariff.scaled(_tariff.MODEL_ALFA, 1.5)})

    def test_ac9_known_line_carries_the_date_of_the_effective_tariff(self):
        """Деталь строки «agent cost KNOWN» содержит дату действующего
        тарифа модели шага.

        Ловит мутацию: строка по-прежнему называет дату калибровки курса
        РОЛИ (или перестаёт называть дату вовсе, когда курс роли исчез) —
        RETRO и отчёт, считающие по тарифу, действовавшему НА МОМЕНТ
        шага, теряют единственный признак, по которому этот тариф можно
        опознать в истории.
        """
        self.charge_known(
            _tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
            _tariff.expected_cost_usd(_tariff.MODEL_ALFA), attempt=1)

        detail = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]

        self.assertIn(_tariff.OVERRIDE_CALIBRATED_AT, detail)

    def test_ac9_partial_line_carries_the_date_of_the_effective_tariff(self):
        """Деталь строки «agent cost PARTIAL» (шаг без финального события
        потока, стоимость посчитана по тарифу) содержит ту же дату.

        Ловит мутацию: дата дописана только в ветку KNOWN — шаг,
        посчитанный ПО ТАРИФУ, остаётся без единственного указания на то,
        по какому именно тарифу он посчитан, хотя как раз здесь расчёт и
        есть источник суммы.
        """
        spend.charge_missing_result(
            self.conn, self.TASK, _tariff.ROLE_ON_ALFA,
            _tariff.numbered_for(1, _tariff.MODEL_ALFA), "таймаут шага",
            partial_tokens=dict(_tariff.TOKENS), saw_usage_event=True)

        detail = self.details(PARTIAL_COST_JOURNAL_ACTION)[-1]

        self.assertIn(_tariff.OVERRIDE_CALIBRATED_AT, detail)


if __name__ == "__main__":
    unittest.main()
