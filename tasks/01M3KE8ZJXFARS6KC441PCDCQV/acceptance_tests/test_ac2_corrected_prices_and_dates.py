"""AC-2 — 01M3KE8ZJXFARS6KC441PCDCQV: сверенные цены шести записей, снятая
пометка «ЦЕНЫ НЕ СВЕРЕНЫ» и общая дата прейскуранта.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Цены шести записей `models.yaml` исправлены по таблице требования 1
(`claude-fable-5-1` — 10.00 / 50.00 / 12.50 / 0.25; `claude-sonnet-5` —
2.00 / 10.00 / 2.50 / 0.20; запись в кэш: `gpt-6-astra` — 12.50,
`gpt-5.6-sol` — 5.00, `gpt-5.6-terra` — 2.50, `gpt-5.6-luna` — 0.25);
пометки «ЦЕНЫ НЕ СВЕРЕНЫ» у `claude-fable-5-1` в файле нет; `price_date`
всех правленых и добавленных записей — включая `claude-opus-5`, у которой
меняется только она — равен `2026-09-28`.

Предмет — каталог ВЕТКИ (`models.yaml` рабочей копии): редакция 2 планки
по ANSWER-1, вопрос 1, вариант (а) — прежняя редакция читала те же шесть
записей из результата применения приложения PLAN к базе сравнения, а
коммит `ae3370c5` сделал это измерение неисполнимым (докстринг
`_catalog.py`). Проверяемые числа и записи те же.

Красен до реализации: пока каталог не правлен, `claude-sonnet-5` стоит
на курсе 3.00 / 15.00 / 3.75 / 0.30, `claude-fable-5-1` — на ценах
`claude-opus-5` с пометкой «ЦЕНЫ НЕ СВЕРЕНЫ», запись в кэш раздела
`codex` везде равна входу, а `price_date` — `2026-09-20`/`2026-09-21`:
краснеет каждый тест файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402


class CorrectedPricesTest(unittest.TestCase):
    """Шесть записей, чьи цены разошлись с действующим прейскурантом."""

    def test_ac2_full_price_sets_match_the_verified_table(self):
        """Весь прейскурант `claude-fable-5-1` и `claude-sonnet-5` —
        числа сверенной таблицы требования 1.

        Ловит мутацию: правка дошла до половины записи — например,
        `claude-sonnet-5` получил новые вход и выход (2.00 / 10.00), а
        запись в кэш и чтение остались прежними (3.75 / 0.30): учёт шага
        считал бы кэш по цене старшей модели, и `assertAlmostEqual` по
        виду `cache_write` покраснеет на 3.75 против 2.5.
        """
        for model_id, prices in sorted(_catalog.CORRECTED_PRICES.items()):
            _catalog.assert_prices(self, model_id, prices)

    def test_ac2_codex_cache_write_no_longer_equals_input(self):
        """Цена записи в кэш четырёх записей раздела `codex` равна
        сверенному числу и больше не повторяет цену входа.

        Ловит мутацию: правка прошла по трём записям из четырёх (правка
        однотипная, и одна строка теряется глазом) — у пропущенной
        `cache_write` остаётся равной `input`, ассерт равенства
        сверенному числу покраснеет, а второй ассерт назовёт причину:
        запись в кэш снова совпала со входом.
        """
        for model_id, cache_write in sorted(
                _catalog.CORRECTED_CACHE_WRITE.items()):
            entry = _catalog.record(self, model_id)
            with self.subTest(model=model_id):
                self.assertAlmostEqual(cache_write, entry.list_price.cache_write,
                                       places=6)
                self.assertNotAlmostEqual(
                    entry.list_price.input, entry.list_price.cache_write,
                    places=6,
                    msg=f"{model_id}: запись в кэш снова равна цене входа")

    def test_ac2_unverified_price_mark_is_gone(self):
        """Текст каталога ветки не несёт пометки «ЦЕНЫ НЕ СВЕРЕНЫ» — ни у
        `claude-fable-5-1`, ни где-либо ещё.

        Ловит мутацию: цены `claude-fable-5-1` исправлены, а
        комментарий-пометка над ними оставлен — файл утверждал бы, что
        сверенные Оператором числа сверки ждут, и следующая правка цен
        пошла бы по несуществующему поводу.
        """
        self.assertNotIn(_catalog.UNVERIFIED_PRICE_MARK,
                         _catalog.catalog().text)

    def test_ac2_price_date_of_every_touched_record_is_the_audit_day(self):
        """`price_date` каждой добавленной и каждой правленой записи —
        `2026-09-28`, включая `claude-opus-5`, у которой меняется только
        она.

        Ловит мутацию: дату проставили только там, где менялись цифры, а
        `claude-opus-5` (цены те же, сверка та же) оставили с
        `2026-09-20` — `doctor.check_model_tariff_freshness` считает
        давность тарифа именно от этой даты, и модель ролей начала бы
        протухать с чужого отсчёта.
        """
        for model_id in sorted(_catalog.DATED_RECORDS):
            entry = _catalog.record(self, model_id)
            with self.subTest(model=model_id):
                self.assertEqual(_catalog.PRICE_DATE, entry.price_date)


if __name__ == "__main__":
    unittest.main()
