"""Существующие тесты `tests/` — гейта по исходам, переходов `in_dev`/`verifying`, журнала и песочниц — задача не правит: из прежних файлов `tests/` меняется только файл В1.2 по мандату ANSWER-1.

Группа: разовый
Зелёный с рождения: до реализации ветка задачи не меняет ни одного файла `tests/`, кроме долгоживущих файлов этой задачи; тест держит, что реализация не правит прежние тесты и песочницы (зелёность самих прежних тестов держит полный набор пульта).

Пути задачи — `changed_paths()` помощника пульта (закоммиченный дифф от
базы и неотслеживаемые файлы); долгоживущие файлы задачи узнаются по
префиксу имени.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import TASK_ID, changed_paths  # noqa: E402

MANDATED = "tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py"


def test_ac15_existing_tests_files_not_edited():
    """Среди путей задачи под `tests/` нет прежних файлов, кроме файла В1.2 из мандата.

    Сценарий: `changed_paths()`; каждый путь под `tests/` — либо файл
    В1.2 (`MANDATED`), правка которого разрешена ANSWER-1, либо новый
    долгоживущий файл задачи с префиксом `tests/test_<id задачи>_`.

    Ловит мутацию: реализация правит существующий тест или песочницу
    (`tests/outcome_gate_sandbox.py`, `tests/test_fsm_*.py`, тесты журнала)
    под новое поведение — путь в списке посторонних.
    """
    own = f"tests/test_{TASK_ID.lower()}_"
    foreign = [p for p in changed_paths()
               if p.startswith("tests/") and p != MANDATED
               and not p.startswith(own)]
    assert foreign == [], foreign
