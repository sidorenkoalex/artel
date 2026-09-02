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
from datetime import datetime, timezone

from . import config, gitcmd, store, workspace

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


def _dogfood_branch(task_id: str) -> str:
    """Ветка задачи из БД — источник истины для головы sha (SPEC T031,
    AC-4), не HEAD текущего чекаута рабочей копии пульта.

    Открывает свою БД-сессию: `fix()`/`read()` держат сигнатуру
    `(task_id, target)` без `conn` (её же зовут напрямую тесты T031), а
    задача к этому моменту уже существует в БД (это её собственная
    фиксация — `store.get_task` тем же приёмом, что и остальные читатели
    ниже по стеку, `fixation.check_integrity`).
    """
    return store.get_task(store.db(), task_id)["branch"]


def _fix_dogfood(task_id: str) -> tuple[str, bool]:
    """Головной sha ВЕТКИ ЗАДАЧИ + чистота `tasks/<id>` (SPEC, требование 3).

    Рабочее дерево точно на чужой ветке (`gitcmd.on_foreign_branch`,
    SPEC T031, AC-4) — голова берётся с ветки задачи независимо от
    чекаута; иначе (свой чекаут, ветка ещё не создана ролью — легитимный
    ранний момент задачи, git не ответил) — HEAD текущего чекаута, как
    было до T031: тот же вырожденный случай, на котором стоит стенд
    заглушек `gitcmd.git` дотестового кода (песочницы, где своя ветка
    задачи никогда не заводится, а вся работа идёт прямо на `main`, —
    там `on_foreign_branch` остаётся False).

    Чистота — тем же критерием ветки/чекаута (SPEC T048): с `cmd_new`
    задача всегда получает собственный worktree с самого начала, и её
    живые `tasks/<id>` лежат ТАМ, не на диске main — сверка чистоты
    рабочей копии пульта (`config.ROOT`) видела бы ЛЮБУЮ правку в
    worktree как «чисто» (main о ней просто не знает), давая любой правке
    мимо гейта пройти незамеченной. На чужой ветке чистота — по worktree
    задачи (`workspace.path`), иначе — прежнее поведение (main).
    """
    branch = _dogfood_branch(task_id)
    foreign = gitcmd.on_foreign_branch(branch)
    sha = gitcmd.branch_head_sha(branch) if foreign else gitcmd.head_sha()
    clean = (gitcmd.is_clean(f"tasks/{task_id}",
                             repo=workspace.path(task_id))
             if foreign else gitcmd.is_clean(f"tasks/{task_id}"))
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


def external_code_sha(target: str) -> str:
    """sha головы кодовой ветки ЦЕЛЕВОГО (SPEC T094, требование 9, AC-10):
    HEAD клона `config.PROJECTS/<target>/workspace` — тот же клон, в
    котором пишет код роль-разработчик (`runner.role_cwd`). Пустая строка
    — клона ещё нет или git не ответил."""
    return gitcmd.head_sha(config.PROJECTS / target / "workspace")


def external_artifact_sha(task_id: str) -> str:
    """sha головы артефактной ветки ПУЛЬТА задачи (SPEC T094, требование
    9, AC-10) — `orchestrator/artifact_branch.py`. Пустая строка — ветки
    ещё нет (self/канарейка её не заводят вовсе) или git не ответил."""
    from . import artifact_branch
    return gitcmd.branch_head_sha(artifact_branch.branch_name(task_id))


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


def approve_sha_hint(task_id: str, target: str) -> str:
    """Суффикс `" <sha>"`, готовый к вставке в подсказку `artel.py
    approve <id>` (SPEC «approve: полный sha в подсказках», требование
    1) — зафиксированный sha тем же живым чтением, что и `fsm.
    confirm_fixation` (не колонка `tasks.fixed_sha`: подсказка обязана
    называть то же значение, которое approve реально сверит).

    Пусто — фиксации ещё нет (git не ответил, вырожденный случай
    песочниц без реального git): подсказка остаётся без sha, байт-в-байт
    как до этой задачи.
    """
    current, _clean = read(task_id, target)
    return f" {current}" if current else ""


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


def _parse_step_ts(ts: str) -> float:
    """Эпоха UTC записи журнала (`store.now()`, формат
    `%Y-%m-%d %H:%M:%SZ`) — сравнима с committer-эпохой коммита (SPEC
    T076, требование 1)."""
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%SZ").replace(
        tzinfo=timezone.utc).timestamp()


def _own_step_run_windows(conn, task_id: str) -> list[tuple[float, float]]:
    """Замкнутые окна `(started, finished)` агентных прогонов ТЕКУЩЕГО
    шага задачи, в эпохах UTC (SPEC T076, требование 1).

    Якорь — момент последней записи журнала «sha зафиксирован»: она
    пишет `record_fixation` на КАЖДОМ переходе FSM (`store.set_state`),
    в том числе на входе в текущее состояние — записи `agent run
    started`/`agent run finished` раньше этого момента принадлежат
    предыдущему шагу и не в счёт. `refixate_after_rejected_transition`
    сам пишет ДРУГОЕ имя действия («sha перефиксирован после отклонённого
    перехода»), поэтому повторные вызовы этой функции внутри одного и
    того же состояния не сдвигают якорь — только настоящий переход FSM
    может (что и требуется: якорь обязан указывать на вход в состояние).

    Незакрытое окно (`started` без парного `finished` — прогон ещё не
    завершился к моменту сверки, либо завершился неуспехом:
    `agent run TIMEOUT`/`FAILED`/`SKIPPED`) в список не попадает —
    доказательства завершённого шага у него нет, коммиты внутри такого
    окна сверка обязана трактовать как непроверенные (fail-closed,
    требование 3).
    """
    rows = store.task_steps(conn, task_id)
    entry_ts = None
    for r in reversed(rows):
        if r["action"] == "sha зафиксирован":
            entry_ts = r["ts"]
            break
    if entry_ts is None:
        return []
    windows: list[tuple[float, float]] = []
    pending_start = None
    for r in rows:
        if r["ts"] < entry_ts:
            continue
        if r["action"] == "agent run started":
            pending_start = r["ts"]
        elif r["action"] == "agent run finished" and pending_start is not None:
            windows.append((_parse_step_ts(pending_start), _parse_step_ts(r["ts"])))
            pending_start = None
    return windows


def refixate_after_rejected_transition(conn, task_id: str, target: str,
                                       entry_sha: str, current_sha: str) -> bool:
    """`True` — ВСЕ новые коммиты между `entry_sha` и `current_sha`
    порождены собственным шагом задачи (SPEC T076, требования 1-2):
    `fixed_sha` перефиксирован на `current_sha`, журнал несёт запись о
    перефиксации. `False` — среди коммитов есть хотя бы один вне окна
    шага, окон нет вовсе, или git не ответил однозначно: фиксация НЕ
    трогается, дальнейший `check_integrity()` эскалирует «инцидент
    целостности» как и раньше (требование 3, fail-closed тем же
    принципом, что и сам `check_integrity` при неответившем git).

    Зовётся ТОЛЬКО когда переход FSM отклонён и задача осталась в
    прежнем состоянии (`fsm._advance_with_refixation`) — успешные
    переходы перефиксируют sha сами через `store.set_state` ->
    `record_fixation`, эта функция им не нужна (требование 5). Не
    вызывает `fix()`/`record_fixation` — та пишет «sha зафиксирован»,
    служащую якорем `_own_step_run_windows`; путает эту запись с
    результатом отклонённого перехода нельзя (см. докстринг выше).
    """
    repo = None if target == config.DEFAULT_TARGET else config.PROJECTS / target
    dates = gitcmd.commit_committer_dates(entry_sha, current_sha, repo=repo)
    if not dates:
        return False
    windows = _own_step_run_windows(conn, task_id)
    if not windows:
        return False
    for date in dates:
        try:
            commit_ts = datetime.fromisoformat(date).astimezone(
                timezone.utc).timestamp()
        except ValueError:
            return False
        if not any(start <= commit_ts <= finish for start, finish in windows):
            return False
    store.update_task(conn, task_id, fixed_sha=current_sha)
    store.journal(
        conn, task_id, "fsm", "sha перефиксирован после отклонённого перехода",
        f"коммиты шага: было {entry_sha}, сейчас {current_sha}")
    return True
