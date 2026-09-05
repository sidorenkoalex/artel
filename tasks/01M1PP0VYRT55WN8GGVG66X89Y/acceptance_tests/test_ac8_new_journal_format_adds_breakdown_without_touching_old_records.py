"""AC-8 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Записи журнала «agent cost PARTIAL», зафиксированные ДО этой
задачи, и уже накопленные ДО этой задачи значения колонки
spent_estimate_usd не пересчитываются задним числом. Формат НОВЫХ
записей журнала шага дополняется разбивкой токенов по видам, не
заменяя существующие поля записи.»

Два независимых свойства критерия — два теста:
1. Старая запись журнала «agent cost PARTIAL», вставленная напрямую (как
   если бы она была записана ДО этой задачи, старым форматом — без
   разбивки), не переписывается и не трогается операциями нового кода
   (`spend.charge_missing_result` на ДРУГОЙ попытке того же шага).
2. НОВАЯ запись журнала известной стоимости шага (`spend.charge_step` с
   `cost["tokens_by_type"]`, интерфейс, зафиксированный AC-6) несёт и
   старые поля (`$`-сумма — тот же текст, что и сегодня даёт
   `cost_note`), и новую разбивку по видам — не одно вместо другого.

Действие журнала `"agent cost KNOWN"` и присутствие разбивки в его
`detail` — тот же интерфейс, что зафиксирован
`test_ac6_calibration_reports_divergence_by_role.py`: `spend.charge_step`
журналирует его, когда `cost` несёт непустой `tokens_by_type`.

Красен до реализации: ни `partial_cost_usd`, ни `charge_step` ещё не
знают про словарь-разбивку токенов по видам (детали по каждому тесту
ниже — оба теста, по разным причинам).
- Первый тест зовёт `spend.charge_missing_result` со словарём-разбивкой
  на месте `partial_tokens` (тот же интерфейс, что AC-2/AC-3/AC-5) —
  сегодняшняя `partial_cost_usd` делает `partial_tokens * effective`
  и падает `TypeError: unsupported operand type(s) for *: 'dict' and
  'float'` раньше, чем дело дойдёт до вопроса «тронута ли старая
  запись». Это не тот сбой, который проверяет сам критерий (сравнение
  старой и новой записи после того, как разбивка заработает), но он
  честно показывает отсутствие ещё не написанного кода задачи — после
  появления поддержки словаря в `partial_cost_usd`/
  `charge_missing_result` (AC-2/AC-3) этот тест либо станет зелёным
  сразу, либо покраснеет уже по своей собственной причине (мутация
  «старая запись тронута»), если разработчик её допустит.
- Второй тест не находит запись `"agent cost KNOWN"` в журнале
  (`spend.charge_step` сегодня её не пишет вовсе, orchestrator/
  spend.py:126-140) — `assertEqual(len(known_cost_rows), 1)` получает
  `0`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import spend  # noqa: E402
from _sandbox import TokenRateTmpRootTest  # noqa: E402

OLD_STYLE_PARTIAL_DETAIL = (
    "попытка 1/3: таймаут шага, финальное событие потока отсутствует — "
    "частичная стоимость по курсу роли 'developer': $0.4500, 1000 токенов")

TOKENS_BY_TYPE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 9000,
}


class NewJournalFormatAddsBreakdownTest(TokenRateTmpRootTest):

    def test_ac8_old_partial_records_are_never_rewritten(self):
        """Запись журнала «agent cost PARTIAL» старого формата (без
        разбивки по видам), вставленная напрямую как снимок ДО этой
        задачи, остаётся байт-в-байт неизменной после того, как код
        задачи журналирует НОВУЮ попытку того же шага.

        Ловит мутацию: реализация «мигрирует» старые записи журнала
        задним числом (например, дописывает им разбивку постфактум при
        следующем обращении к задаче) — `detail` старой записи
        перестанет совпадать с `OLD_STYLE_PARTIAL_DETAIL`,
        `assertEqual` провалится.
        """
        self.conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail) "
            "VALUES (?, 'artel', '2026-09-04T00:00:00', 'developer', "
            "'agent cost PARTIAL', ?)", (self.TASK, OLD_STYLE_PARTIAL_DETAIL))
        self.conn.commit()

        spend.charge_missing_result(
            self.conn, self.TASK, "test_author", "попытка 1/3", "таймаут шага",
            dict(TOKENS_BY_TYPE), saw_usage_event=True)

        old_rows = [detail for actor, action, detail in self.journal_rows()
                   if action == "agent cost PARTIAL" and actor == "developer"]
        self.assertEqual(old_rows, [OLD_STYLE_PARTIAL_DETAIL])

    def test_ac8_new_known_cost_record_carries_both_the_dollar_amount_and_the_breakdown(self):
        """Новая запись журнала известной стоимости шага несёт И
        привычную сумму в $ (существующий формат `cost_note`), И
        разбивку токенов по видам — вторая не заменяет первую.

        Ловит мутацию: реализация заменяет старый текст суммы новой
        разбивкой вместо того, чтобы её ДОПОЛНИТЬ, — `"$0.5000"`
        пропадёт из `detail`, первый `assertIn` провалится.
        """
        cost = {"usd": 0.5, "tokens": sum(TOKENS_BY_TYPE.values()),
               "tokens_by_type": dict(TOKENS_BY_TYPE)}

        spend.charge_step(self.conn, self.TASK, "test_author", cost, "попытка 1/3")

        known_cost_rows = [detail for actor, action, detail in self.journal_rows()
                          if action == "agent cost KNOWN"]
        self.assertEqual(len(known_cost_rows), 1)
        detail = known_cost_rows[0]
        self.assertIn("$0.5000", detail, "старое поле — сумма в $ — на месте")
        for count in TOKENS_BY_TYPE.values():
            self.assertIn(str(count), detail,
                          "разбивка по видам присутствует в записи")


if __name__ == "__main__":
    unittest.main()
