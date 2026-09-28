"""AC-21 — задание test_author (`orchestrator/role_prompt.py`) называет
каталог `tests/` кодовой ветки как место долгоживущих файлов, имя
`tests/test_<префикс>_<имя>.py` с конкретным префиксом СВОЕЙ задачи
(полный id в нижнем регистре, Р1) и запрет трогать существующие файлы
`tests/`; задание developer сообщает, что долгоживущие файлы задачи
зафиксированы так же, как приёмочные тесты.

Задание наблюдается через `role_prompt.mission_brief_package` — ту же
сборку, что `cmd_run`; бриф роли (компонент, не задание) подменён пустым,
чтобы задание читалось без БД и артефактов. Id задач — свежие
`idgen.new_task_id()` при каждом запуске.

Группа: разовый
Красен до реализации: задание test_author сегодня ведёт только в `tasks/<id>/acceptance_tests/` — ни `tests/test_<префикс>_…`, ни запрета про существующие файлы `tests/`; задание developer о долгоживущих файлах молчит.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import brief, idgen, role_prompt  # noqa: E402

# Запрет: «существующ…» и отрицание/запрет в пределах одной фразы.
PROHIBITION = re.compile(
    r"(не\s+\w+|нельзя|запрещ\w*)[^.\n]{0,80}существующ"
    r"|существующ[^.\n]{0,80}(не\s+\w+|нельзя|запрещ\w*)", re.I)


def mission(task_id: str, role: str) -> str:
    t = {"branch": f"task/{task_id.lower()}-slug", "reviewed_iter": 0,
         "title": "вложенная"}
    with mock.patch.object(brief, "test_author_answer_component",
                           return_value=""), \
         mock.patch.object(brief, "developer_brief", return_value=""):
        text, _brief, _package = role_prompt.mission_brief_package(
            None, task_id, t, role, Path("/нет/такого/каталога"))
    return text


class RolePromptTest(unittest.TestCase):

    def test_ac21_test_author_mission_names_tests_dir_prefix_and_ban(self):
        """Для трёх свежих id: задание test_author несёт
        `tests/test_<id в нижнем регистре>_` (конкретный префикс своей
        задачи, не шаблон и не чужой id) и фразу-запрет про существующие
        файлы `tests/`.

        Ловит мутацию: в задание подставлен шаблон
        `tests/test_<префикс>_<имя>.py` или id в исходном регистре
        (`task_id`, а не `task_id.lower()`) — строки с фактическим
        префиксом задачи в задании нет.
        """
        ids = [idgen.new_task_id() for _ in range(3)]
        print(f"id: {ids}")
        for task_id in ids:
            with self.subTest(task=task_id):
                text = mission(task_id, "test_author")
                self.assertIn(f"tests/test_{task_id.lower()}_", text)
                for other in ids:
                    if other != task_id:
                        self.assertNotIn(f"test_{other.lower()}_", text)
                self.assertRegex(text, PROHIBITION,
                                 "нет запрета трогать существующие файлы tests/")

    def test_ac21_developer_mission_says_long_lived_files_are_locked(self):
        """Задание developer упоминает долгоживущие файлы задачи рядом с
        фиксацией (лок/зафиксир…) — как приёмочные тесты.

        Ловит мутацию: строка о долгоживущих файлах добавлена только в
        задание test_author — developer не узнаёт, что правка его файлов
        `tests/` с префиксом задачи отклоняется.
        """
        text = mission(idgen.new_task_id(), "developer")
        self.assertRegex(text, re.compile(r"долгожив", re.I))
        self.assertRegex(
            text, re.compile(r"долгожив[^\n]{0,200}(залоч|зафиксир|лок)"
                             r"|(залоч|зафиксир|лок)[^\n]{0,200}долгожив", re.I),
            "задание developer не связывает долгоживущие файлы с фиксацией")


if __name__ == "__main__":
    unittest.main()
