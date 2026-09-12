"""Общий код планки задачи 01M2B6K3EM7F2J72RC2F520Y2K (SPEC: «Признак роли
в окружении и conftest вместо хука роли») — путь к корню репозитория и
подпроцесс-обёртка над pytest, которой пользуются несколько test_ac*.py
этой планки (AC-2/AC-3/AC-4/AC-7): не копия друг у друга, единственное
место, где собран рецепт запуска дочернего pytest с/без ARTEL_ROLE.
"""
import os
import subprocess
import sys
from pathlib import Path

# tasks/<id>/acceptance_tests/_helpers.py -> parents[3] == корень репозитория
# (тот же приём, что tasks/T101/acceptance_tests/*.py).
REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "01M2B6K3EM7F2J72RC2F520Y2K"
ACCEPTANCE_TESTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT))

# Требование 1 SPEC: имена переменных окружения — литералы, фиксированные
# самим текстом требования (константы orchestrator/config.py несут ТЕ ЖЕ
# значения под другим именем идентификатора) — тест вправе полагаться на
# сами строки "ARTEL_ROLE"/"ARTEL_TASK", не на то, как developer назовёт
# константу в config.py.
ARTEL_ROLE_VAR = "ARTEL_ROLE"
ARTEL_TASK_VAR = "ARTEL_TASK"


def run_pytest(args, role=None, timeout=100):
    """Подпроцесс `python3 -m pytest <args>` от REPO_ROOT.

    `role=None` — ARTEL_ROLE гарантированно отсутствует в окружении
    дочернего процесса (гасится явно, машина прогона могла бы случайно
    её унаследовать); иначе ARTEL_ROLE=<role>. Отдельный процесс, не
    вызов внутрипроцессных pytest-хуков напрямую — conftest.py смотрит
    окружение ЦЕЛОГО процесса, а не текущего теста (AC-2..AC-4 SPEC прямо
    требуют subprocess-прогон).
    """
    env = dict(os.environ)
    env.pop(ARTEL_ROLE_VAR, None)
    if role is not None:
        env[ARTEL_ROLE_VAR] = role
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
        timeout=timeout,
    )


def combined_output(result: subprocess.CompletedProcess) -> str:
    return (result.stdout or "") + (result.stderr or "")
