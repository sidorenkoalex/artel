"""Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

Единица управления — проект: подключение, отключение и восстановление
это операции над одним каталогом. Здесь заводится сам каталог со всем,
что у проекта есть: эфемерный клон целевого (workspace), первичка
артефактов (tasks), производные знания (knowledge) и логи прогонов.

Git-слоя тут нет: `git init` каталога, коммиты оркестратора на переходах
FSM и sha в журнал — задача A2b (ADR-0003 3д, п.15).
"""
import sys
from pathlib import Path

from . import config, targets


def project_dir(name: str) -> Path:
    return config.PROJECTS / name


def init_project(name: str) -> list[str]:
    """Создаёт каталоги target'а; список строк — что вышло с каждым.

    Идемпотентность — свойство самой операции, а не проверки «уже есть»:
    каталог создаётся с exist_ok, поэтому повторный вызов ничего не
    ломает и после подключения, и после ручного удаления одного из
    подкаталогов (недостающее доводится, существующее не трогается).
    """
    notes = []
    for sub in config.PROJECT_DIRS:
        path = project_dir(name) / sub
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        notes.append(f"{'уже был' if existed else 'создан'}: {path}")
    return notes


def cmd_target_init(name: str) -> None:
    """Подключение target'а: каталог проекта по декларации targets.yaml."""
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        sys.exit(f"target-init: {exc}")

    try:
        notes = init_project(name)
    except OSError as exc:
        sys.exit(f"target-init: каталог проекта {name} не создан: {exc}")

    print(f"target {name}: forge {entry['forge']}, база {entry['base']}, "
          f"гейт мержа {entry['merge_gate']}")
    for note in notes:
        print(f"  {note}")
