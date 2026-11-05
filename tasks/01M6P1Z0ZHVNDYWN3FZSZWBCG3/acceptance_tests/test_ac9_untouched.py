"""Шесть прежних файлов тестов AC-9 остаются в ветке задачи без правки.

Группа: разовый
Зелёный с рождения: ветка задачи до реализации не трогает ни одного из шести файлов, тест держит этот факт до мержа.

Факт задачи: разница ветки с базой (`changed_paths()` помощника пульта
`_pult.py` — закоммиченный дифф от точки расхождения с `origin` плюс
неотслеживаемые файлы) не содержит ни одного из шести файлов, и каждый из
них есть в рабочей копии. Зелёность этих файлов на коде задачи держит
полный прогон `tests/` пультом (они лежат в `tests/`): их общий прогон —
около двух минут, дольше предела времени одного теста планки.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

FILES = [
    "tests/test_hosting_token_units.py",
    "tests/test_01m545edths47hsb59akc1ez9c_project_token.py",
    "tests/test_doctor_gitlab_ci_file.py",
    "tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py",
    "tests/test_push_hook_units.py",
    "tests/test_push_hook_stand.py",
]


@pytest.mark.parametrize("rel", FILES)
def test_ac9_previous_test_file_not_modified(rel):
    """Файл прежних тестов AC-9 есть в рабочей копии и не входит в дифф задачи.

    Ловит мутацию: разработчик подогнал прежний тест под новое поведение
    (правка, переименование или удаление файла) — путь появляется среди
    изменённых путей задачи либо файла нет.
    """
    assert (Path(CODE_ROOT) / rel).is_file(), f"файла {rel} нет в рабочей копии"
    assert rel not in set(changed_paths()), f"{rel} изменён в ветке задачи"
