"""AC-5 (SPEC.md): метрики прогона (шаги ролей, итерации ревью,
эскалации, стоимость, вердикты гейтов — по каждой задаче) сохраняются
в БД пульта отдельной таблицей/пометкой, отличной от журнала живых
продуктовых задач.

«БД пульта» здесь — БД СНАРУЖИ клона (`self.root`/`config.DB` этой
песочницы): требование прямо говорит «БД пульта», а не «БД клона» —
метрики намеренно всплывают наружу, в отличие от самого FSM-цикла
задач (AC-2/AC-3, целиком внутри клона). SPEC разрешает ЛИБО отдельную
таблицу, ЛИБО пометку в существующей («таблицей/пометкой») — тест
проверяет отдельную таблицу как наиболее естественное прочтение (в
`tasks`/`steps` пометке взяться неоткуда: AC-3 требует их нулевыми
после прогона, а остальные существующие таблицы БД, `store.py`
(`task_counters`/`alerts`/`leases`/`merge_locks`), по семантике не
годятся под метрики задачи); если разработчик выберет пометку в ИНОЙ
таблице — эта проверка (по имени новой таблицы) не увидит её, см.
докстринг метода теста.

Красен до реализации: `canary --k` падает на разборе аргументов,
задачи не заводятся, таблиц сверх стартовой схемы (`store.create_schema`)
не появляется — `new_tables` пуст, первая содержательная проверка падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
    "udalenie-rudimenta.md": "Убери неиспользуемый синтетический модуль Y.",
}


class MetricsSeparateFromLiveJournalTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.known_tables_before = self.sqlite_table_names()

    def test_ac5_run_writes_a_new_metrics_table_distinct_from_tasks_and_steps(self):
        """После прогона k=2 в `config.DB` (БД пульта СНАРУЖИ клона)
        появляется хотя бы одна НОВАЯ таблица (сверх стартовой схемы),
        и в ней — минимум 2 строки (по одной на задачу набора); при
        этом `tasks`/`steps` (живой журнал продуктовых задач) остаются
        пустыми (AC-3), т.е. метрики физически лежат ОТДЕЛЬНО, не
        подмешаны в общий журнал.

        Ловит мутацию: разработчик пишет метрики прогона только в
        JSON-файл на диске (буквальный перенос механики v1,
        `orchestrator/canary.py::_write_report`, `.artel/canary/*.json`
        — SPEC требования 4-5 v1) вместо БД пульта, как явно требует
        требование 5 v2 («сохраняются в БД пульта») — тогда
        `sqlite_table_names()` после прогона не отличается от
        `known_tables_before`, тест краснеет по отсутствию новой таблицы.
        """
        out = self.run_canary_pool(2)
        self.assertNotIn("[SystemExit]", out, out)

        from orchestrator import store
        self.assertEqual(
            store.all_tasks(store.db()), [],
            "живой журнал `tasks` не должен нести канареечные задачи "
            "(AC-3) — иначе метрики неотличимы от продуктовых задач")

        tables_after = self.sqlite_table_names()
        new_tables = tables_after - self.known_tables_before
        self.assertTrue(
            new_tables,
            f"после прогона в БД пульта не появилось ни одной новой "
            f"таблицы для метрик: было {sorted(self.known_tables_before)}, "
            f"стало {sorted(tables_after)}")

        conn = store.db()
        rows_total = 0
        for name in new_tables:
            rows_total += conn.execute(
                f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        self.assertGreaterEqual(
            rows_total, 2,
            f"новые таблицы {sorted(new_tables)} несут меньше двух строк "
            f"(k=2 задачи прогона) суммарно: {rows_total}")


if __name__ == "__main__":
    unittest.main()
