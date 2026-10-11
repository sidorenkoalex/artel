"""AC-4 (tasks/T065/SPEC.md): задачи, заведённые командой `canary`,
отличимы от продуктовых задач в `status`/БД и в RETRO-статистике по
этой пометке; их расход при этом учтён в `total_spent` наравне с
продуктовыми задачами.

Механизм пометки — SPEC требование 6 (правка Оператора 28.08) сузило его
до КОЛОНКИ БД буквально: пометка в title запрещена (title виден ролям в
промпте — канареечная задача обязана быть неотличимой от продуктовой
ДЛЯ РОЛЕЙ, иначе контаминация бенчмарка). Тест это уважает: не трогает
`title` ни у канареечной, ни у продуктовой задачи, только читает
Operator-facing поверхности (`status`, killed-RETRO) — им положено
показывать пометку, самому title — нет. Слово пометки тест не пинит на
латиницу: `_sandbox.has_canary_mark` принимает и «canary» (буквально из
требования 2 — «с пометкой canary в журнале»), и русское «канаре*»
(естественный вариант для строк, целиком русскоязычных в остальной
кодовой базе) — критерий про факт отличимости, не про язык надписи.

Красен до реализации: команды `canary` нет в таблице `orchestrator/
artel.py::main` — `run_canary` возвращает текст с «Неизвестная команда
canary», ни одна задача не заводится, и `self.task_ids()` после прогона
пуст — `len(canary_ids) == 1` падает `AssertionError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, has_canary_mark  # noqa: E402

from orchestrator import catalog, cleanup, retro, store  # noqa: E402


class CanaryTasksAreMarkedTest(CanarySandbox):

    def test_ac4_canary_tasks_are_distinguishable_and_counted_honestly(self):
        tz_dir = self.write_tz_files(
            {"feature.md": "Добавь маленькую синтетическую фичу с тестами."})
        self.run_canary(tz_dir)
        canary_ids = self.task_ids()
        self.assertEqual(len(canary_ids), 1,
                         f"по 1 ТЗ-файлу заведено задач: {len(canary_ids)} "
                         f"({canary_ids})")
        canary_id = canary_ids[0]
        self.assertEqual(self.task_row(canary_id)["state"], "killed")

        self.capture(catalog.cmd_new, "Обычная продуктовая задача")
        product_id = next(t for t in self.task_ids() if t != canary_id)

        # status/БД: пометка отличает канареечную строку от продуктовой.
        status_out = self.capture(catalog.cmd_status)
        canary_line = next(l for l in status_out.splitlines()
                           if l.startswith(canary_id))
        product_line = next(l for l in status_out.splitlines()
                            if l.startswith(product_id))
        self.assertTrue(
            has_canary_mark(canary_line),
            f"строка status канареечной задачи не несёт пометку canary: "
            f"{canary_line!r}")
        self.assertFalse(
            has_canary_mark(product_line),
            f"строка status продуктовой задачи ошибочно помечена canary: "
            f"{product_line!r}")

        # total_spent: расход канареечной задачи учтён наравне с прочими
        # (требование 6) — колонка `spent_usd` общая для всех строк
        # `tasks`, независимо от механизма пометки.
        conn = store.db()
        conn.execute("UPDATE tasks SET spent_usd=? WHERE id=?",
                    (12.5, canary_id))
        conn.execute("UPDATE tasks SET spent_usd=? WHERE id=?",
                    (3.5, product_id))
        conn.commit()
        self.assertEqual(store.total_spent(conn), 16.0,
                         "total_spent не учитывает расход канареечной "
                         "задачи наравне с продуктовой")

        # RETRO-статистика: killed-RETRO канареечной задачи несёт ту же
        # пометку, продуктовая (тоже killed — для честного сравнения) — нет.
        self.capture(cleanup.cmd_kill, product_id)
        canary_retro = retro.build_killed(conn, canary_id)
        product_retro = retro.build_killed(conn, product_id)
        self.assertTrue(
            has_canary_mark(canary_retro),
            f"killed-RETRO канареечной задачи не несёт пометку canary:\n"
            f"{canary_retro}")
        self.assertFalse(
            has_canary_mark(product_retro),
            f"killed-RETRO продуктовой задачи ошибочно несёт пометку "
            f"canary:\n{product_retro}")


if __name__ == "__main__":
    unittest.main()
