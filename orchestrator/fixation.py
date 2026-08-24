"""Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

Артефакты — управляющий вход системы (SPEC ведёт разработчика, REVIEW
двигает FSM); их правка в обход гейтов = управление конвейером. Каждый
переход `store.set_state` фиксирует физическое состояние артефактов
задачи в колонку `tasks.fixed_sha` — FSM и `approve` сверяются с ней
одинаково, не зная, откуда взялся sha:

- **Догфуд** (`config.DEFAULT_TARGET`, особый случай до A7, ADR-0003 3д):
  существующий флоу артефактов не меняется — коммитит их сама роль
  внутри шага; здесь только чтение уже закоммиченного состояния рабочей
  копии пульта (головной sha ветки + чистота `tasks/<id>`).
- **Внешний target**: артефактный git-репозиторий
  `.artel/projects/<target>/` (`projects.init_artifact_repo`) коммитит
  оркестратор целиком на каждом переходе — будущие типы артефактов
  фиксируются тем же коммитом без правки этого модуля (ADR-0003 п.15).

`sha == ""` в обеих ветках — git не ответил или фиксировать нечего:
вырожденный случай, на котором `approve`/`run` ведут себя так же, как до
T021 (существующие тесты без реального git в песочнице — тот же путь).

`fix()` и `check_integrity()` читают состояние по-разному (REVIEW.md
T021, замечание 1, итерация 1): `fix()` — точка ФИКСАЦИИ (`set_state`,
`approve`), ей положено коммитить внешний репо целиком (требование 2).
`check_integrity()` — точка ПРОВЕРКИ перед стартом шага, и коммитить ей
нельзя: коммит здесь как побочный эффект сравнения означал бы, что
чужой незакоммиченный артефакт (роль другой задачи того же target ещё
пишет файл) становится частью коммита фиксации ЭТОЙ задачи и сдвигает
HEAD, который та задача не просила сдвигать — её собственный
`fixed_sha` тут же расходится с новым HEAD, и она уходит в инцидент
целостности, которого не совершала. `check_integrity()` (и `confirm_fixation`
в `fsm.py`, см. REVIEW.md T021 замечание 1 итерации 2) поэтому читают
через `read()`, не через `fix()`: то же самое для догфуда (там `fix()`
и так не коммитит), но для внешнего target — без `add -A`/`commit`.
"""
from . import config, gitcmd, store

# Идентичность коммитов фиксации внешнего target: это действие
# оркестратора, а не роли и не Оператора — коммит служебный (диффов кода
# в нём нет), поэтому не берёт для него ни git-конфиг Оператора (в отличие
# от `runner.git_identity`, который переносит именно человеческое
# авторство роли в коммит РОЛИ), ни GIT_AUTHOR_* из окружения.
# Фиксированная идентичность коммитит и там, где ни то, ни другое не
# настроено (свежая песочница, CI).
FIXATION_AUTHOR_NAME = "Artel Orchestrator"
FIXATION_AUTHOR_EMAIL = "orchestrator@artel.invalid"


def fix(task_id: str, target: str) -> tuple[str, bool]:
    """(sha, чисто) — фиксация текущего состояния артефактов задачи."""
    if target == config.DEFAULT_TARGET:
        return _fix_dogfood(task_id)
    return _fix_external(target)


def _fix_dogfood(task_id: str) -> tuple[str, bool]:
    """Головной sha ветки пульта + чистота `tasks/<id>` (SPEC, требование 3)."""
    sha = gitcmd.head_sha()
    clean = gitcmd.is_clean(f"tasks/{task_id}")
    if not sha or clean is None:
        return "", False
    return sha, clean


def _fix_external(target: str) -> tuple[str, bool]:
    """Коммит артефактного репо target'а целиком (SPEC, требование 2).

    Нечего коммитить (второй переход подряд без правки файлов) — не
    отказ: фиксируется уже существующий HEAD той же операцией.
    """
    repo = config.PROJECTS / target
    added = gitcmd.in_repo(repo, "add", "-A")
    if added.returncode != 0:
        return "", False
    staged = gitcmd.in_repo(repo, "diff", "--cached", "--quiet")
    if staged.returncode not in (0, 1):
        return "", False
    if staged.returncode == 1:  # есть застейдженный дифф — есть что коммитить
        commit = gitcmd.in_repo(
            repo, "-c", f"user.name={FIXATION_AUTHOR_NAME}",
            "-c", f"user.email={FIXATION_AUTHOR_EMAIL}",
            "commit", "-q", "-m", f"fixation: {target}")
        if commit.returncode != 0:
            return "", False
    sha = gitcmd.head_sha(repo)
    clean = gitcmd.is_clean(repo=repo)
    if not sha or clean is None:
        return "", False
    return sha, clean


def _read_external(target: str) -> tuple[str, bool]:
    """(sha, чисто) артефактного репо target'а — БЕЗ `add -A`/`commit`.

    Используется только `check_integrity` (см. модульный докстринг):
    проверка перед стартом шага не имеет права коммитить рабочее дерево
    репо, в отличие от `_fix_external`, которую вызывает сама фиксация
    на переходе FSM.
    """
    repo = config.PROJECTS / target
    sha = gitcmd.head_sha(repo)
    clean = gitcmd.is_clean(repo=repo)
    if not sha or clean is None:
        return "", False
    return sha, clean


def read(task_id: str, target: str) -> tuple[str, bool]:
    """(sha, чисто) для сверки — не мутирует ни догфуд, ни внешний target.

    Публичная точка входа для ЛЮБОЙ сверки (не фиксации): `check_integrity`
    (старт шага) и `fsm.confirm_fixation` (approve) обе только сравнивают
    текущее состояние с зафиксированным/переданным sha — ни та, ни другая
    не имеет права коммитить чужой WIP того же target как побочный эффект
    сравнения (REVIEW.md T021, замечание 1 итерации 1 — про
    `check_integrity`; замечание 1 итерации 2 — тот же класс дефекта в
    `confirm_fixation`, закрыт тем же приёмом).
    """
    if target == config.DEFAULT_TARGET:
        return _fix_dogfood(task_id)
    return _read_external(target)


def check_integrity(conn, task_id: str) -> str | None:
    """None — фиксация не нарушена (или её ещё нет); иначе причина отказа.

    Сверяет ЖИВОЕ состояние с тем, что зафиксировано на последнем
    переходе FSM (`tasks.fixed_sha`) — закрытие TOCTOU approve → старт
    шага (ADR-0003 п.17, SPEC требование 5). Нет исторической фиксации —
    сверять не с чем: тот же вырожденный случай, что у `fsm.cmd_approve`
    (песочницы без git, требование 3 — флоу не меняется). Читает через
    `read()`, не `fix()`: проверка не имеет права коммитить (см.
    модульный докстринг).
    """
    t = store.get_task(conn, task_id)
    fixed = t["fixed_sha"]
    if not fixed:
        return None
    target = store.task_target(conn, task_id)
    current, clean = read(task_id, target)
    if not current:
        return "текущее состояние артефактов не прочитано (git не ответил)"
    if current != fixed:
        return f"sha разошёлся с зафиксированным: было {fixed}, сейчас {current}"
    if not clean:
        return f"грязная копия артефактов при sha {fixed}"
    return None
