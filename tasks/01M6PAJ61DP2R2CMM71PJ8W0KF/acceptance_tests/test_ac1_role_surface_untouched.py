"""Задача не меняет `stack.ROLE_ENV_ALLOWLIST` и код окружения шага роли.

Группа: разовый
Зелёный с рождения: до кода задачи её дифф пуст — `orchestrator/stack.py` и `orchestrator/runner.py` в нём нет; тест краснеет, только если задача их тронет.

Окружение `role_env` задачи с профилем `compose` сверяет долгоживущий файл
`tests/test_01m6paj61dp2r2cmm71pj8w0kf_role_env_compose.py` (AC-1); здесь —
факт этой задачи: дифф задачи от точки расхождения с `origin` (помощник
пульта `_pult.changed_paths`) не трогает модули, где живут белый список
переменных роли и сборка её окружения.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402


def test_ac1_allowlist_and_role_env_modules_not_changed():
    """Дифф задачи не содержит `orchestrator/stack.py` (там `ROLE_ENV_ALLOWLIST`) и `orchestrator/runner.py` (там `role_env`).

    Зелёный с рождения: держит неизменность белого списка и сборки
    окружения роли на всём пути задачи.
    """
    touched = set(changed_paths())
    assert "orchestrator/stack.py" not in touched, sorted(touched)
    assert "orchestrator/runner.py" not in touched, sorted(touched)
