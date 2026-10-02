"""Документация набора задачи: `docs/stack.md` и `docs/operator-session.md`.

Группа: разовый

Красен до реализации: в `docs/stack.md` нет ни команды `set-models`, ни понятия «набор задачи» (есть только допуск набора части 1), в `docs/operator-session.md` нет пункта с командой `new … --set`.

AC-1…AC-13 покрыты долгоживущим файлом
`tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py` (методы
`test_ac<n>_…`). Документация — код репозитория, не артефакт задачи: файлы
читаются из корня кодовой ветки, рядом с пакетом `orchestrator`, которым
идёт прогон.

Провалидирован временной правкой обеих страниц (зелёный; правка удалена).
"""
import re
import unittest
from pathlib import Path

from orchestrator import config

CODE_ROOT = Path(config.__file__).resolve().parent.parent


def read_doc(name: str) -> str:
    return (CODE_ROOT / "docs" / name).read_text(encoding="utf-8")


class TaskModelSetDocsTest(unittest.TestCase):

    def test_ac14_stack_and_operator_session_describe_the_task_set(self):
        """Обе страницы документации описывают набор задачи.

        Сценарий: `docs/stack.md` называет «набор задачи» и команду
        `set-models` (разрешение модели с учётом задачи и смена набора
        задачи в работе); `docs/operator-session.md` несёт пункт запуска
        задачи на наборе — команду `new` с флагом `--set` в одной
        записи.

        Ловит мутацию: документация не дописана либо дописана на одной
        странице из двух — нужного текста на второй странице нет."""
        stack = read_doc("stack.md")
        self.assertTrue("набор задачи" in stack.lower(),
                        "docs/stack.md не называет «набор задачи»")
        self.assertTrue("set-models" in stack,
                        "docs/stack.md не описывает команду set-models")
        session = read_doc("operator-session.md")
        self.assertTrue(re.search(r"\bnew\b[^`\n]*--set\b", session),
                        "docs/operator-session.md: нет пункта запуска задачи "
                        "на наборе (`new … --set`)")


if __name__ == "__main__":
    unittest.main()
