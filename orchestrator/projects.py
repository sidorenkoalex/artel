"""Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

Единица управления — проект: подключение, отключение и восстановление
это операции над одним каталогом. Здесь заводится сам каталог со всем,
что у проекта есть: эфемерный клон целевого (workspace), первичка
артефактов (tasks), производные знания (knowledge) и логи прогонов.

Git-слой (tasks/T021, ADR-0003 3д, п.15): `git init` каталога без
remote, `workspace/`/`logs/` в его `.gitignore` — носитель коммитов
оркестратора на переходах FSM (`orchestrator.fixation`).
"""
import sys
from pathlib import Path

from . import config, gitcmd, targets

# workspace/ (эфемерный клон целевого) и logs/ (стримы агентов) — не
# артефакты: не входят в hash-фиксацию, поэтому исключены из
# артефактного репо самого каталога проекта (ADR-0003 3д).
ARTIFACT_GITIGNORE = "workspace/\nlogs/\n"


def project_dir(name: str) -> Path:
    return config.PROJECTS / name


def init_artifact_repo(name: str) -> str:
    """git-репо каталога проекта: без remote, workspace/+logs/ в .gitignore.

    Идемпотентно: `git init` повторно не портит существующий репозиторий
    (гарантия самого git), `.gitignore` каждый раз перезаписывается тем
    же содержимым — повторный вызов и ручное вмешательство сходятся
    к одному состоянию (SPEC T021, требование 1).
    """
    path = project_dir(name)
    existed = (path / ".git").is_dir()
    # Настоящий `git init <путь>` заводит каталог сам (implicit `mkdir -p`)
    # — заглушки `gitcmd.git` в лёгких песочницах (`fake_git`/аналоги)
    # отвечают успехом, не трогая диск: без явного `mkdir` здесь
    # `.gitignore` ниже падал бы `FileNotFoundError` на каталоге, которого
    # реально нет (найдено на A7: `fixation._fix_external` теперь сама
    # заводит артефактный репо лениво, и первый такой вызов может прийтись
    # на песочницу без настоящего git).
    path.mkdir(parents=True, exist_ok=True)
    res = gitcmd.in_repo(path, "init", "-q", "-b", config.MAIN_BRANCH)
    if res.returncode != 0:
        return f"git-репо не создано: {res.stderr.strip()[:200]}"
    (path / ".gitignore").write_text(ARTIFACT_GITIGNORE, encoding="utf-8")
    return "git-репо уже было" if existed else "git-репо создано"


def artifact_repo_has_no_remote(name: str) -> bool:
    """True — у артефактного репо target'а нет remote (SPEC T021, требование 7).

    Потребитель — doctor (A3); здесь только сама проверка по имени target.
    """
    return gitcmd.has_no_remote(project_dir(name))


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
    notes.append(init_artifact_repo(name))

    print(f"target {name}: forge {entry['forge']}, база {entry['base']}, "
          f"гейт мержа {entry['merge_gate']}")
    for note in notes:
        print(f"  {note}")
