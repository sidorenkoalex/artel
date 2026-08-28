"""AC-1 (tasks/T049/SPEC.md): холодный старт — `init` сеет счётчик номеров
задач от наблюдаемого max, а не от пустой БД.

«На копии проекта без `.artel` команда `init` сеет счётчик номеров от
наблюдаемого max: задача, созданная сразу после `init`, получает номер
строго больше всех номеров, видимых в `tasks/T*`, `task/t*`,
`docs/retro/T*.md` (сценарий «въезд в готовый проект»).»

Три источника из требования 1 SPEC заведены тестом БЕЗ строк БД (каталог
задачи, ветка задачи, файл RETRO) — именно это и есть «холодный старт»:
БД (`.artel/state.db`) не существует вовсе на момент `init`, наблюдаемый
мир — единственное, откуда есть что взять максимум. Тест не зовёт
внутренние функции разбора источников напрямую (SPEC называет только
`store.seed_task_counters` как расширяемую функцию, не как публичный
контракт для теста) — только наблюдаемое поведение команд `init`/`new`,
дословно как сформулирован критерий.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, store  # noqa: E402
from _sandbox import ColdStartGitRepoTest, capture  # noqa: E402


class ColdStartCounterSeedTest(ColdStartGitRepoTest):

    OBSERVED_MAX = 10  # max(T005 каталог, task/t010-* ветка, T007 RETRO)

    def setUp(self):
        super().setUp()
        self.make_task_dir("T005")
        self.make_branch("task/t010-vetka-bez-stroki-bd")
        self.make_retro("T007")

    def test_ac1_task_created_right_after_init_gets_number_above_observed_max(self):
        capture(catalog.cmd_init)

        capture(catalog.cmd_new, "Задача сразу после холодного старта")

        row = store.db().execute(
            "SELECT id FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(row, "cmd_new не завёл строку задачи")
        number = store.task_number(row["id"])

        self.assertGreater(
            number, self.OBSERVED_MAX,
            f"новая задача {row['id']} обязана получить номер строго "
            f"больше {self.OBSERVED_MAX} — максимума среди наблюдаемых "
            f"источников (tasks/T005, ветка task/t010-*, "
            f"docs/retro/T007.md), а не считать от пустой БД")


if __name__ == "__main__":
    unittest.main()
