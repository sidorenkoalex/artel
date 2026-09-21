"""AC-12 — 01M31ZHSA6HMH40C2JTDPQJQNZ: строки стоимости, записанные до и
после задачи, читаются одинаково — разбор принимает обе формы имён видов
токенов.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. `spend.known_cost_breakdown` разбирает и строку с прежними именами
видов токенов, и строку с общими именами, давая для одинаковых чисел
одинаковую разбивку; на журнале, где строки обеих форм лежат вперемешку,
`spend.known_cost_pairs`, отчёт, RETRO и сверка курса считают по всем
строкам, не пропуская ни одной формы.

Строки журнала собираются здесь тем же форматом, каким их пишет
`spend.charge_step` сегодня (прежняя форма) и каким их естественно
запишет разбивка по общим видам (новая форма): предмет критерия — ЧТЕНИЕ
журнала, в котором лежат обе, и такой журнал на живом пульте соберётся
сам собой, первым же шагом после мержа.

Красен до реализации: `spend._TOKEN_FIELD_RE` собран из
`config.USAGE_TOKEN_KEYS` (имена счётчиков Claude) — строка с общими
именами видов даёт пустую разбивку, `known_cost_pairs` её молча
пропускает, и в сверку входит одна строка из двух. Третий тест файла
(RETRO) зелен и сегодня: он сохраняет существующее поведение — сводка
задачи обязана и после задачи считать по ОБОИМ шагам, какой бы формой
имён ни была записана их разбивка.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _run  # noqa: E402
import _sample  # noqa: E402
from orchestrator import models, report, retro, spend, store  # noqa: E402

#: Числа одного и того же шага — по одному на каждый вид токенов.
COUNTS = dict(_sample.USAGE_RESULT)
ACTUAL_USD = 0.5000
FINISHED = "agent run finished"


def legacy_names() -> str:
    """Разбивка прежними именами счётчиков Claude."""
    return ", ".join(f"{key}={COUNTS[key]}" for key in COUNTS)


def common_names() -> str:
    """Та же разбивка общими именами видов цены."""
    return ", ".join(f"{_sample.KIND_FOR_COUNTER[key]}={COUNTS[key]}"
                     for key in COUNTS)


def known_detail(model_id: str, since: str, breakdown: str,
                 attempt: int) -> str:
    """Деталь строки «agent cost KNOWN» — тем же составом полей, каким
    её пишет `spend.charge_step`."""
    return (f"попытка {attempt}/3, model={model_id}: "
            f"стоимость ${ACTUAL_USD:.4f}, токенов {sum(COUNTS.values())}, "
            f"источник=факт CLI, разбивка по видам: {breakdown} | "
            f"actual_usd={ACTUAL_USD!r} | тариф модели с {since}")


class BothTokenNameFormsTest(_run.StepRunSandbox):

    def setUp(self):
        super().setUp()
        self.model_id = models.resolve_role(self.ROLE).model
        self.since = spend.role_tariff(self.ROLE).calibrated_at

    def seed_mixed_journal(self) -> None:
        """Журнал задачи с двумя шагами: один записан прежними именами
        видов токенов, другой — общими."""
        for attempt, breakdown in enumerate((legacy_names(), common_names()),
                                            start=1):
            store.journal(self.conn, self.TASK, self.ROLE, FINISHED,
                          f"rc=0, попытка {attempt}/3, "
                          f"стоимость ${ACTUAL_USD:.4f}, "
                          f"токенов {sum(COUNTS.values())}")
            store.journal(self.conn, self.TASK, self.ROLE, _run.KNOWN,
                          known_detail(self.model_id, self.since, breakdown,
                                       attempt))
        self.set_task(spent_usd=ACTUAL_USD * 2)

    def test_ac12_breakdown_reads_both_name_forms_the_same(self):
        """`spend.known_cost_breakdown` на двух строках с одинаковыми
        числами и разными именами видов даёт одну и ту же разбивку и ту
        же фактическую цену.

        Ловит мутацию: разбор переведён на общие имена без поддержки
        прежних — весь журнал, накопленный до задачи (и вся калибровка
        тарифа на нём), читается пустым, а сверка тарифа с фактом
        молча начинается с нуля.
        """
        legacy = spend.known_cost_breakdown(
            known_detail(self.model_id, self.since, legacy_names(), 1))
        common = spend.known_cost_breakdown(
            known_detail(self.model_id, self.since, common_names(), 2))

        self.assertEqual(legacy[0], ACTUAL_USD)
        self.assertEqual(common[0], ACTUAL_USD)
        self.assertEqual(_sample.normalized(legacy[1]),
                         _sample.normalized(COUNTS))
        self.assertEqual(legacy[1], common[1],
                         "одинаковые числа дали разную разбивку")

    def test_ac12_mixed_journal_is_counted_by_pairs_and_the_report(self):
        """На журнале со строками обеих форм `spend.known_cost_pairs` и
        сверка курса отчёта считают ОБА шага.

        Ловит мутацию: строка непонятной формы пропускается молча (та же
        ветка, которой сегодня пропускается строка старого формата без
        `actual_usd`) — коэффициент расхождения тарифа с фактом считается
        по половине шагов, и решение Оператора о калибровке цены
        принимается по выборке, о неполноте которой никто не сказал.
        """
        self.seed_mixed_journal()

        pairs = spend.known_cost_pairs(self.conn)
        counted = [item for items in pairs.values() for item in items]
        divergence = report.token_rate_divergence(self.conn)

        self.assertEqual(len(counted), 2,
                         f"в сверку вошли не все строки: {pairs}")
        self.assertIn(self.model_id, divergence)
        self.assertEqual(divergence[self.model_id].steps, 2)

    def test_ac12_retro_counts_the_steps_of_both_forms(self):
        """RETRO той же задачи считает стоимость по обоим шагам.

        Ловит мутацию: RETRO переведён на общий разбор строк стоимости,
        знающий только одну форму имён видов, — сводка задачи начинает
        называть половину её расхода, а именно по ней холодный старт
        пересевает программный расход.
        """
        self.seed_mixed_journal()

        text = retro.build_done(self.conn, self.TASK, "0" * 40)

        self.assertIn(f"Стоимость итого: ${ACTUAL_USD * 2:.2f}", text)
        self.assertIn(f"{self.ROLE}: ${ACTUAL_USD * 2:.2f}", text)
        self.assertEqual(retro.parse_total_cost(text), ACTUAL_USD * 2)


if __name__ == "__main__":
    unittest.main()
