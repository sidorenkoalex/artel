"""AC-4, AC-5 — 01M3GKJFN90ATK2KECNDZXPPP6: `report` читает журнал одной
выборкой, не меняя ни байта вывода.

Источник — раздел «Критерии приёмки»:

AC-4. На одной песочной БД HTML-вывод `report` побайтно равен эталону
того же вывода, снятому прежним способом чтения журнала (выборка на
каждую задачу) на той же БД.

AC-5. Число SQL-запросов к `steps` при построении `report` на песочной
БД не растёт с числом задач: при 3 и при 6 задачах оно одинаково и
меньше числа запросов прежнего кода на той же БД; оба числа
зафиксированы в тесте счётчиком запросов.

Эталон AC-4 — не «прежний код из git», а прежний СПОСОБ чтения,
выписанный в планке сырым SQL (`_util.old_journal_reading`): подмена
обеих точек, названных требованием 3 SPEC (`report._all_steps`,
`report._map_size_entries`), на выборку `SELECT * FROM steps WHERE
task_id=?` на каждую задачу. Тест отдельно убеждается, что эталон
действительно прошёл через обе подмены: подмена, которую никто не позвал
(разработчик переименовал или встроил функцию), сравнивала бы новый HTML
сам с собой и была бы зелена ни о чём.

Счётчик AC-5 считает запросы ЧИТАТЕЛЕЙ ЖУРНАЛА, названных требованием 3
(`report._all_steps` и блок роста карты, идущий через
`report._map_size_entries`), а не все запросы `report.cmd_report`.
Причина — найденный планкой факт, который ТЗ не называет: `cmd_report`
читает журнал ТРЕТЬИМ путём, `report.token_rate_divergence` ->
`spend.known_cost_pairs` (`orchestrator/spend.py`: `for task in
store.all_tasks(conn)` -> `store.task_steps(conn, task["id"])`), то есть
ещё одним запросом к `steps` НА КАЖДУЮ задачу. `orchestrator/spend.py` не
входит ни в `zones` фронтматтера SPEC, ни в перечень правок «Не входит»
(«прочие места вызова `store.task_steps`, которые ТЗ не называет»), так
что при подсчёте ВСЕХ запросов `cmd_report` число оставалось бы N + const
и при 3, и при 6 задачах — ни одной правкой внутри зон задачи критерий
был бы недостижим. Замер требования 6 в PLAN.md это тоже касается:
суммарное число запросов `report` после правки останется зависящим от
числа задач, пока читатель `spend.py` не тронут. Материал для решения
Оператора на приёмке; планка фиксирует достижимое свойство критерия —
«не растёт с числом задач» для читателей, которые ТЗ называет.

Красен до реализации: `test_ac5_…` — `report._all_steps` и
`report._map_size_entries` берут журнал выборкой на каждую задачу, и
счётчик даёт при 6 задачах ровно вдвое больше запросов, чем при 3.
Зелёный с рождения: `test_ac4_…` — критерий требует НЕИЗМЕННОСТИ вывода,
до правки оба способа чтения совпадают по результату; его работа
начинается на реализации, где он и обязан остаться зелёным.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class ReportJournalReadingTest(_util.JournalSandbox):

    def test_ac4_html_is_byte_identical_to_the_old_way_of_reading(self):
        """Отчёт по одной и той же песочной БД собирается дважды — новым
        чтением журнала и прежним (выборка на каждую задачу); документы
        совпадают побайтно.

        Ловит мутацию: в `_map_size_entries` потерян отбор по target —
        одна выборка `steps` берёт записи «карта: размер» всех задач
        пульта, а джойн к `tasks`, которым прежний код доставал target
        задачи, при переходе к одной выборке просто не дописан: ряд роста
        карты каждого target'а показал бы записи обоих.
        """
        self.seed_tasks(3)
        frame = self.report_frame()

        actual = self.report_html(frame)
        with _util.old_journal_reading() as calls:
            reference = self.report_html(frame)

        self.assertIn("_all_steps", calls,
                      "эталон не прошёл через report._all_steps — сравнение "
                      "новых данных с новыми же ничего не проверяет")
        self.assertIn("_map_size_entries", calls,
                      "эталон не прошёл через report._map_size_entries")
        self.assertIn("01M3GKPLANKA", actual,
                      "отчёт песочной БД не несёт ни одной задачи — "
                      "побайтное сравнение шло бы по пустым таблицам")
        self.assertEqual(reference, actual)

    def test_ac5_steps_queries_do_not_grow_with_the_number_of_tasks(self):
        """Число запросов к `steps` при чтении журнала для отчёта: при 3 и
        при 6 задачах одно и то же, и меньше, чем у прежнего способа
        чтения на той же БД с 6 задачами.

        Ловит мутацию: одна выборка сделана только в `_all_steps`, а
        `_map_size_entries` оставлен как был (три его вызова на target из
        блока роста карты незаметны глазом в дифе) — число запросов
        осталось бы пропорциональным числу задач, и равенство «при 3 и при
        6» покраснело бы.
        """
        self.seed_tasks(3)
        frame_three = self.report_frame()
        with _util.StepsQueries(self.conn) as three:
            self.report_html(frame_three)

        self.seed_tasks(3)
        frame_six = self.report_frame()
        with _util.StepsQueries(self.conn) as six:
            self.report_html(frame_six)

        with _util.StepsQueries(self.conn) as old_six:
            with _util.old_journal_reading():
                self.report_html(frame_six)

        self.assertGreater(
            six.count, 0,
            "счётчик не увидел ни одного запроса к steps — отчёт читает "
            "журнал не через переданное соединение, и AC-5 проверен не был")
        self.assertEqual(
            three.count, six.count,
            f"запросов к steps при 3 задачах {three.count}, при 6 — "
            f"{six.count}: число растёт с числом задач")
        self.assertLess(
            six.count, old_six.count,
            f"запросов к steps у нового чтения {six.count}, у прежнего — "
            f"{old_six.count}: сокращения нет")


if __name__ == "__main__":
    unittest.main()
