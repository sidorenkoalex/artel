"""AC-13 — 01M31ZHSA6HMH40C2JTDPQJQNZ: строки журнала «agent cost KNOWN»
и «agent cost PARTIAL» несут имя провайдера шага.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. Строки журнала «agent cost KNOWN» и «agent cost PARTIAL» несут
поле `provider=` с именем провайдера шага рядом с полем `model=` и датой
действующего тарифа.

Строки проверяются такими, какими их пишет ШАГ (`runner.cmd_run` на
поддельном процессе агента), а не прямым вызовом `spend.charge_step`:
довесок `model=` к `numbered` приписывает точка завершения шага, и
строка, собранная в тесте руками, к журналу пульта отношения не имеет.

Красен до реализации: поля `provider=` нет ни в одной строке стоимости —
`orchestrator/spend.py` пишет `model=` (из `numbered`, `runner.
_numbered_with_model`) и дату тарифа, а имя провайдера пульт в учёте
вовсе не знает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _run  # noqa: E402
import _sample  # noqa: E402
from orchestrator import spend  # noqa: E402


class CostLinesCarryProviderTest(_run.StepRunSandbox):

    def expected_field(self) -> str:
        return f"provider={_provider.claude().name}"

    def test_ac13_known_line_names_provider_model_and_tariff_date(self):
        """Строка «agent cost KNOWN» завершённого шага несёт `provider=`,
        `model=` и дату действующего тарифа.

        Ловит мутацию: имя провайдера приписано не к строке стоимости, а
        к какой-нибудь соседней записи шага («agent run started») —
        отчёт и RETRO, читающие именно строку стоимости, так и не
        узнают, на чьём счёте эти деньги.
        """
        self.run_stream(_sample.STREAM)

        detail = self.details(_run.KNOWN)[-1]

        self.assertIn(self.expected_field(), detail)
        self.assertIn("model=", detail)
        self.assertIn(spend.role_tariff(self.ROLE).calibrated_at, detail)

    def test_ac13_partial_line_names_the_provider_too(self):
        """Строка «agent cost PARTIAL» оборвавшегося шага несёт то же
        поле `provider=` рядом с `model=`.

        Ловит мутацию: поле дописано только в ветку KNOWN — шаг,
        посчитанный по тарифу после таймаута, остаётся без провайдера, и
        именно у этих строк (расчётных, а не фактических) вопрос «чей
        тариф» стоит острее всего.
        """
        self.run_timeout(_sample.STREAM_WITHOUT_RESULT)

        detail = self.details(_run.PARTIAL)[-1]

        self.assertIn(self.expected_field(), detail)
        self.assertIn("model=", detail)

    def test_ac13_provider_field_names_the_provider_of_the_step(self):
        """Имя в поле `provider=` — имя провайдера ЭТОЙ роли, а не
        литерал `claude`.

        Ловит мутацию: поле заполнено константой (или именем провайдера
        по умолчанию) — на пульте с двумя провайдерами все строки
        стоимости называют одного, и разрез расхода по провайдерам,
        ради которого поле заводится, врёт.
        """
        stub = _provider.CliPriceFreeProvider()
        _provider.register(self, stub, self.ROLE)

        self.run_stream(_sample.STREAM)

        detail = self.details(_run.KNOWN)[-1]
        self.assertIn(f"provider={stub.name}", detail)


if __name__ == "__main__":
    unittest.main()
