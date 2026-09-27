"""Общий код планки задачи 01M3HP7WAXKFK3GYZ3T6HX08M0 — только то, что
нужно больше чем одному `test_*.py` (скил test-authoring: имя с
подчёркиванием, иначе checkpoint отбросит файл как посторонний).

Своих копий песочниц здесь нет: сами песочницы берутся готовыми из
`tests/sandbox.py` (`SchemaConnTmpRootTest`, `RealGitSandbox`) и
`tests/test_runner_model_preflight.py` (`_StepSandbox` — настоящий путь
`runner.cmd_run` с подменённым процессом агента).
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

# Действия журнала трёх подавляемых предупреждений (требование 1 SPEC):
# тексты записей эта задача не меняет (требование 7), поэтому действия
# здесь — литералы существующего журнала, не новые имена.
PREFLIGHT_WARNING_ACTION = "pre-flight WARNING"
SPEC_NOT_APPLIED_ACTION = "бюджет из SPEC не применён"
BUDGET_WARNING_ACTION = "бюджет: предупреждение"

# Действия журнала GitHub-адаптера, которые планка сверяет по имени
# (`orchestrator/github_adapter.py`).
DRAFT_MR_FAILED_ACTION = "Draft MR FAILED"
DRAFT_MR_CREATED_ACTION = "Draft MR заведён"
GITHUB_ADAPTER_ALERT_SOURCE = "github_adapter"


def spend_levels(budget_usd: float, count: int) -> list[float]:
    """`count` расходов СТРОГО между порогом предупреждения и потолком —
    каждый следующий больше предыдущего, поэтому текст предупреждения (он
    несёт текущие суммы) на каждом шаге свой, а пересечённый порог один и
    тот же.

    Считается от `config.BUDGET_ALERT_RATIO`, а не от сегодняшних 0.7:
    Оператор двигает порог крутилкой конфигурации, и фикстура обязана
    переживать её поворот."""
    threshold = budget_usd * config.BUDGET_ALERT_RATIO
    room = budget_usd - threshold
    return [threshold + room * (i + 1) / (count + 1) for i in range(count)]


def capture_value(fn, *args) -> tuple:
    """(результат, напечатанное) вызова `fn` — `tests.sandbox.capture`
    отдаёт только печать, а критериям планки нужны оба: и вердикт функции,
    и число её печатей в stdout."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args)
    return result, buf.getvalue()


def targets_yaml_text(base: str | None = None) -> str:
    """Минимальный `targets.yaml` с записью target'а пульта: `forge:
    github` — предусловие AC-8..AC-10 (github-target). Все поля записи
    обязательны (`orchestrator/targets.py::FIELDS`), поэтому здесь
    перечислены все, а не только читаемые адаптером."""
    return f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: https://github.com/artel/artel
    base: {base or config.MAIN_BRANCH}
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""
