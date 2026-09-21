"""AC-7 — 01M31ZHSA6HMH40C2JTDPQJQNZ: стоимость и токены шага на Claude
не изменились ни в одной из шести точек.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Стоимость и токены шага на Claude не изменились: на том же образце
`OutputPump.cost`, `OutputPump.partial_tokens`, `OutputPump.
saw_usage_event`, `spend.parse_cost_event`, `spend.stream_usage_by_type` и
`spend.partial_tokens_from_log` дают те же значения, что до задачи.

Разбивка по видам сверяется ЗНАЧЕНИЯМИ, приведёнными к общим видам
(`_sample.normalized`), а не именами счётчиков: имена этих же видов
задача меняет на общие (AC-2), и требовать здесь дословных
`input_tokens`/`cache_read_input_tokens` значило бы столкнуть два
критерия лбами. Числа при этом сверяются точно — подмена вида (чтения
кэша посчитаны как вход) красит тест.

Зелёный с рождения: все шесть значений сегодня уже такие — тест
сохранения существующего поведения. Красным он станет, если переезд
разбора к провайдеру потеряет счётчик, просуммирует виды в одно число
или перестанет отличать «usage видели с нулём» от «usage не видели».
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _sample  # noqa: E402
from orchestrator import agent_log, spend  # noqa: E402


class CostAndTokensTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.provider = _provider.claude()

    def pump(self, lines) -> agent_log.OutputPump:
        pump = _sample.flex(agent_log.OutputPump, iter(lines),
                            self.tdir / "step.log", provider=self.provider)
        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)
        return pump

    def test_ac7_parse_cost_event_returns_the_same_price_and_tokens(self):
        """`spend.parse_cost_event` на финальном событии образца отдаёт
        ту же цену, ту же сумму токенов и ту же разбивку по видам.

        Ловит мутацию: разбор итога запуска у провайдера берёт цену из
        другого поля (или теряет `usage` финального события) — шаг
        по-прежнему «учтён», но списанная сумма и разбивка, на которой
        стоит вся сверка тарифа с фактом CLI, становятся другими.
        """
        cost = _sample.flex(spend.parse_cost_event, _sample.RESULT_LINE,
                            provider=self.provider)

        self.assertEqual(cost["usd"], _sample.EXPECTED_COST_USD)
        self.assertEqual(cost["tokens"], _sample.EXPECTED_COST_TOKENS)
        self.assertEqual(_sample.normalized(cost["tokens_by_type"]),
                         _sample.EXPECTED_COST_BY_KIND)

    def test_ac7_stream_usage_by_type_still_reads_any_event(self):
        """`spend.stream_usage_by_type` читает usage и промежуточного
        события, и финального, а на событии без usage отдаёт `None`.

        Ловит мутацию: разбор usage сведён к финальному событию (или,
        наоборот, служебное событие без usage начинает отдавать пустую
        разбивку вместо `None`) — частичная стоимость оборванного шага
        считается не по тем токенам, а «usage не видели» становится
        неотличимо от «видели нулевой».
        """
        by_kind = _sample.normalized(
            _sample.flex(spend.stream_usage_by_type, _sample.TEXT_LINE,
                         provider=self.provider))
        final = _sample.normalized(
            _sample.flex(spend.stream_usage_by_type, _sample.RESULT_LINE,
                         provider=self.provider))
        none_case = _sample.flex(spend.stream_usage_by_type,
                                 _sample.SYSTEM_LINE, provider=self.provider)

        self.assertEqual(by_kind, _sample.EXPECTED_ASSISTANT_BY_KIND)
        self.assertEqual(final, _sample.EXPECTED_COST_BY_KIND)
        self.assertIsNone(none_case)

    def test_ac7_partial_tokens_from_log_sums_the_sample_by_kind(self):
        """`spend.partial_tokens_from_log` по файлу лога образца отдаёт
        ту же сумму по видам и тот же признак «usage видели».

        Ловит мутацию: постфактум-разбор файла переведён на провайдера
        так, что складывает только события `assistant` (или только
        финальное) — `pause --now` и таймаут шага учитывают часть
        потраченного, и недоучёт возвращается тихо.
        """
        path = _sample.log_file(self.tdir / "raw.log", _sample.STREAM)

        tokens, saw = _sample.flex(spend.partial_tokens_from_log, path,
                                   provider=self.provider)

        self.assertEqual(_sample.normalized(tokens),
                         _sample.EXPECTED_PARTIAL_BY_KIND)
        self.assertTrue(saw)

    def test_ac7_pump_keeps_cost_partial_tokens_and_usage_flag(self):
        """Перекачка вывода на образце отдаёт ту же стоимость, ту же
        частичную разбивку и `saw_usage_event=True`; поток без
        usage-событий оставляет разбивку пустой, а признак — ложным.

        Ловит мутацию: `OutputPump` копит токены только до первого
        финального события (или ставит `saw_usage_event` по факту
        ненулевой суммы) — оборвавшийся шаг с нулевым usage начинает
        выглядеть как шаг, у которого usage не было вовсе, и вместо
        частичной стоимости заводится алерт «стоимость неизвестна».
        """
        pump = self.pump(_sample.STREAM)

        self.assertEqual(pump.cost["usd"], _sample.EXPECTED_COST_USD)
        self.assertEqual(_sample.normalized(pump.partial_tokens),
                         _sample.EXPECTED_PARTIAL_BY_KIND)
        self.assertTrue(pump.saw_usage_event)

        silent = self.pump([_sample.SYSTEM_LINE, _sample.PLAIN_LINE])

        self.assertIsNone(silent.cost)
        self.assertEqual(silent.partial_tokens, {})
        self.assertFalse(silent.saw_usage_event)


if __name__ == "__main__":
    unittest.main()
