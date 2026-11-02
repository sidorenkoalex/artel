"""Факт задачи: тест-сторож ac9 и его `EXEMPT` не изменены — файл сторожа не входит в пути задачи.

Группа: разовый
Зелёный с рождения: ветка задачи до реализации файл сторожа не трогает — тест держит, чтобы реализация его не правила.

Строки `doctor` по записи `github` + `operator` и артели (вторая половина
AC-15) проверяет долгоживущий файл задачи в `tests/`
(`test_ac15_github_operator_and_artel_lines_unchanged`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

GUARD = "tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py"


def test_ac15_ac9_guard_file_not_changed():
    """Среди путей задачи (закоммиченный дифф от базы и неотслеживаемые файлы) нет файла сторожа ac9.

    Сценарий: помощник пульта `changed_paths()` перечисляет пути задачи
    правилом гейта зон; файла
    `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` среди них
    нет.

    Ловит мутацию: разработчик добавил исключение в `EXEMPT` сторожа ac9
    ради литерала хостинга в `project_checks.py` — файл сторожа появится в
    путях задачи.
    """
    paths = changed_paths()
    assert GUARD not in paths, paths
