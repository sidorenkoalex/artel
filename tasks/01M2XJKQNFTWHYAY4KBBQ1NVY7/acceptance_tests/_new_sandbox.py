"""Песочница `new --tz` для планки 01M2XJKQNFTWHYAY4KBBQ1NVY7 —
надстройка над `tests.sandbox.LightTransitionSandbox` (skills/
test-authoring.md: лёгкая песочница переходов импортируется, не
копируется).

Собственных `disk_backed_*`/`advance_from_in_dev`/патчей `gitcmd` здесь
нет: добавляется только то, чего эталон не знает — сев упоминаемых ТЗ
путей во временный `config.ROOT` и запуск `catalog.cmd_new` с файлом ТЗ.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

sys.path.insert(0, str(_util.REPO_ROOT))

from orchestrator import catalog, store  # noqa: E402
from tests import sandbox  # noqa: E402


class NewWithTzSandbox(sandbox.LightTransitionSandbox):
    """`LightTransitionSandbox` + пути фикстур в корне песочницы.

    Эталон уже завёл одну задачу своим `setUp` (`cmd_new` без `--tz`) —
    она и есть базовая отметка, относительно которой тесты считают
    появление/отсутствие новой строки в `tasks`.
    """

    def setUp(self):
        super().setUp()
        _util.seed_paths(self.root)
        self.tz_file = self.root / "TZ_fixture.md"
        self.tasks_before = self.task_count()

    @staticmethod
    def task_count() -> int:
        return store.db().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    def run_new(self, tz_body: str, title: str = "Фикстура планки") -> str:
        """Весь вывод `new --tz` по тексту ТЗ `tz_body`. Прошла команда
        или отказала — видно по числу строк в `tasks`, не по форме
        отказа (`sys.exit` против мягкого возврата)."""
        self.tz_file.write_text(tz_body, encoding="utf-8")
        return _util.run_command(catalog.cmd_new, title, str(self.tz_file))

    def assert_task_created(self, text: str) -> None:
        self.assertEqual(self.task_count(), self.tasks_before + 1,
                         f"задача не заведена:\n{text}")

    def assert_no_task_created(self, text: str) -> None:
        self.assertEqual(self.task_count(), self.tasks_before,
                         f"строка задачи появилась вопреки отказу:\n{text}")
