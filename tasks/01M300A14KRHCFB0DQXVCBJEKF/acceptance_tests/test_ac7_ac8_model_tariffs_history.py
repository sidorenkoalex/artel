"""AC-7 и AC-8 — 01M300A14KRHCFB0DQXVCBJEKF: таблица `model_tariffs`
заводится и в DDL, и в миграции одинаковым составом колонок, а история
пополняется ровно при смене тарифа.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Таблица `model_tariffs` создаётся и в DDL (`schema.create_schema`),
и в миграции (`schema.migrate`) — состав колонок одинаков: модель,
четыре цены, `valid_from`, `source`.

AC-8. Разрешение тарифа модели, отличающегося от последней записи этой
модели в `model_tariffs`, добавляет строку; повторное разрешение того же
тарифа строк не добавляет (число строк по модели не растёт).

Имён колонок цен критерий не называет — их четыре, и это те же четыре
вида токенов, которыми каталог и локальный слой задают тариф
(`models.PRICE_KINDS`), поэтому проверяется вхождение имени вида в имя
колонки, а не буквальное равенство. Точка «разрешения тарифа» —
завершённый шаг: `spend.charge_step` обязан разрешить действующий тариф
модели, чтобы вообще посчитать стоимость.

Красен до реализации: таблицы `model_tariffs` нет ни в `schema.SCHEMA`,
ни в `schema.migrate` (`orchestrator/schema.py:24-70, 94-245`) — запрос
к ней падает `sqlite3.OperationalError: no such table`.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import models, schema  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TABLE = "model_tariffs"


class ModelTariffsTableIsInDdlAndInMigrationTest(TmpRootTest):
    """AC-7: паритет DDL и миграции — тот же класс дефекта, который уже
    сторожит `tests/test_store_schema_migration_parity.py` для `tasks`.

    Песочница временных путей `config` нужна не ради самой схемы, а ради
    `schema.migrate`: он зовёт `store.seed_task_counters`, а тот на
    незасеянном счётчике сканирует наблюдаемый мир пульта (каталоги
    задач, ветки, RETRO) — на настоящем `config.ROOT` это и долго, и
    читает не свой предмет."""

    def setUp(self):
        super().setUp()
        self.conn = sqlite3.connect(self.root / "parity.db")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def test_ac7_ddl_and_migration_create_the_same_columns(self):
        """`create_schema` заводит `model_tariffs`; после удаления
        таблицы `migrate` заводит её заново тем же составом колонок —
        модель, четыре цены, `valid_from`, `source`.

        Ловит мутацию: таблица дописана только в одну из двух точек
        (обычная забывчивость — новая таблица в `SCHEMA`, но не в
        `migrate`, или наоборот) либо составы разъехались на одну колонку
        — БД свежего пульта и БД, догнанная миграцией, перестают быть
        одинаковыми, и `add_column`-гонка/`no such column` всплывают на
        живом пульте.
        """
        schema.create_schema(self.conn)
        ddl_columns = schema.table_columns(self.conn, TABLE)
        self.assertTrue(ddl_columns,
                        f"`schema.create_schema` не заводит таблицу {TABLE}")

        self.conn.execute(f"DROP TABLE {TABLE}")
        self.conn.commit()
        schema.migrate(self.conn)
        migrated_columns = schema.table_columns(self.conn, TABLE)

        self.assertEqual(ddl_columns, migrated_columns)

    def test_ac7_columns_name_the_model_four_prices_and_the_tariff_origin(self):
        """Состав колонок несёт модель, все четыре вида цен тарифа,
        `valid_from` и `source`.

        Ловит мутацию: таблица заведена без даты действия (`valid_from`)
        или без источника — история тарифов перестаёт отвечать на
        вопрос «с какого числа и по чьему основанию действовала эта
        цена», ради которого она и заводится; либо цены сложены в одну
        колонку, и разложить их обратно по видам уже нечем.
        """
        schema.create_schema(self.conn)

        columns = schema.table_columns(self.conn, TABLE)

        self.assertIn("valid_from", columns)
        self.assertIn("source", columns)
        self.assertTrue([c for c in columns if "model" in c],
                        f"в {TABLE} нет колонки модели: {sorted(columns)}")
        for kind in models.PRICE_KINDS:
            with self.subTest(kind=kind):
                self.assertTrue(
                    [c for c in columns if kind in c],
                    f"в {TABLE} нет колонки цены {kind}: {sorted(columns)}")


class TariffHistoryGrowsOnlyOnChangeTest(_tariff.TariffSandbox):
    """AC-8: строка добавляется при смене тарифа и только при ней."""

    def test_ac8_repeated_resolution_of_the_same_tariff_adds_no_row(self):
        """Два подряд учтённых шага на одном и том же тарифе оставляют у
        модели одну запись истории; смена тарифа локальным слоем
        добавляет вторую.

        Ловит мутацию: сравнение с последней записью потеряно (пишется
        на каждое разрешение) — история пухнет строкой на каждый шаг и
        перестаёт быть историей ТАРИФОВ; либо сравнение слишком широкое
        («модель уже есть — не пишем»), и смена цен не фиксируется вовсе,
        то есть пересчитать прошлый шаг по действовавшей цене снова
        нечем.
        """
        calculated = _tariff.expected_cost_usd(_tariff.MODEL_ALFA)
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          calculated, attempt=1)
        after_first = _tariff.model_tariff_rows(self.conn, _tariff.MODEL_ALFA)

        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          calculated, attempt=2)
        after_second = _tariff.model_tariff_rows(self.conn, _tariff.MODEL_ALFA)

        self.assertEqual(1, len(after_first), after_first)
        self.assertEqual(1, len(after_second), after_second)

        self.use_local(overrides={_tariff.MODEL_ALFA:
                                  _tariff.scaled(_tariff.MODEL_ALFA, 2.0)})
        self.charge_known(_tariff.ROLE_ON_ALFA, _tariff.MODEL_ALFA,
                          calculated * 2, attempt=3)
        after_change = _tariff.model_tariff_rows(self.conn, _tariff.MODEL_ALFA)

        self.assertEqual(2, len(after_change), after_change)


if __name__ == "__main__":
    unittest.main()
