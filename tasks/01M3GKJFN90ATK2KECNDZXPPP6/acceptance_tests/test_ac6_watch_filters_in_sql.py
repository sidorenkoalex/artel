"""AC-6 — 01M3GKJFN90ATK2KECNDZXPPP6: `watch._emit_steps` отбирает новые
записи фильтром в SQL, а печатает то же, что печатал прежде.

Источник — раздел «Критерии приёмки»:

AC-6. `watch._emit_steps` на задаче с историей в N записей и известным
`known_step_id`, равным id предпоследней записи, получает из SQL ровно
одну строку (не N), а печатает те же строки, что печатал прежний код на
той же БД.

«Получает из SQL» планка наблюдает обёрткой соединения
(`_util.RowCountingConn`): `_emit_steps` принимает соединение
параметром, так что подменять внутри него нечего — достаточно передать
обёртку, которая сама вычитывает каждый курсор и помнит число отданных
строк. Эталон печати — прежний способ, выписанный в планке
(`_util.old_emit_steps_output`): полная история задачи из SQL, фильтр
`id > known` в Python, печать теми же `watch._matches_class`/
`watch._print_line`.

Красен до реализации: `_emit_steps` зовёт `store.task_steps`, то есть
берёт из SQL всю историю задачи — обёртка видит N строк вместо одной.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, store, watch  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

TASK = "01M3GKPLANKADOZOR0000000001"

#: История задачи: (актёр, действие, деталь). Последняя запись —
#: переход состояния, то есть единственная НОВАЯ запись сценария и
#: единственная, которую дозор классов `transitions` обязан напечатать;
#: записи между ними — того класса, который этот дозор не печатает
#: (проверка, что фильтр класса остался на месте).
HISTORY = (
    ("autogate", "state -> review", "автогейт планки"),
    ("orchestrator", "карта: размер", '{"bytes_total":100000}'),
    ("developer", "agent run завершён", "шаг агента планки"),
    ("fsm", "переход отклонён: планка", "отказ перехода планки"),
    ("operator", "state -> merge_gate", "гейт Оператора планки"),
    ("autogate", "state -> done", "закрытие планки"),
)

EVENTS = {"transitions"}


class EmitStepsFiltersInSqlTest(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Задача дозора планки", "in_dev",
                          f"task/{TASK.lower()}-planka",
                          config.DEFAULT_TARGET, 25.0)
        for actor, action, detail in HISTORY:
            store.journal(self.conn, TASK, actor, action, detail)
        self.ids = [row["id"] for row in _util.old_task_steps(self.conn, TASK)]
        self.assertEqual(len(HISTORY), len(self.ids))

    def test_ac6_only_the_single_new_row_comes_from_sql(self):
        """Известен id предпоследней записи истории из шести: SQL отдаёт
        дозору ровно одну строку, а напечатанное совпадает со тем, что на
        этой же БД печатал прежний код.

        Ловит мутацию: граница фильтра взята нестрого (`id >= known`
        вместо `id > known`) — из SQL приходило бы две строки вместо одной,
        и уже известная Оператору запись печаталась бы в потоке дозора
        второй раз.
        """
        known = self.ids[-2]
        reference = _util.old_emit_steps_output(self.conn, TASK, EVENTS, known)
        self.assertTrue(
            reference.strip(),
            "эталон печати пуст — сравнение выводов было бы ни о чём")

        counting = _util.RowCountingConn(self.conn)
        printed = io.StringIO()
        with redirect_stdout(printed):
            watch._emit_steps(counting, TASK, EVENTS, {TASK: known}, None)

        self.assertEqual(
            1, counting.steps_rows,
            f"SQL отдал {counting.steps_rows} строк при истории из "
            f"{len(HISTORY)} записей и известной предпоследней: "
            f"запросы — {counting.steps_statements}")
        self.assertEqual(reference, printed.getvalue())


if __name__ == "__main__":
    unittest.main()
