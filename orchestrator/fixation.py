"""Hash-фиксация артефактов на переходах FSM (ADR-0003 п.15, п.17; tasks/T021).

Артефакты — управляющий вход системы (SPEC ведёт разработчика, REVIEW
двигает FSM); их правка в обход гейтов = управление конвейером. Каждый
переход `store.set_state` фиксирует физическое состояние артефактов
задачи в колонку `tasks.fixed_sha` — FSM и `approve` сверяются с ней
одинаково, не зная, откуда взялся sha.

С ADR-0021 (п.3, этап 1) зафиксированное состояние документов — коммит
ссылки `refs/artifacts/<id>` задачи (`fix`/`read`) в репозитории задачи
(`artifact_branch.task_repo`: git пульта для артели, git проекта для
внешнего target): документы живут там от `new` до закрытия. Пишущие места
пульта, двигающие ссылку вне перехода (автокоммит шага, `answer`,
`zones-extend`, `amend-tests`, `doctor --fix`, коммит закрытия),
перефиксируют её сами (`store.record_fixation`); запись мимо них сверка
видит расхождением.

Репозиторий фиксации области проекта `.artel/projects/<target>/`
(ADR-0003 п.15, коммит каталога целиком на каждом переходе) упразднён
(ADR-0021 п.2, этап 1, часть б2): фиксация его не заводит, не коммитит и
не читает. Единая логика для ЛЮБОГО target, включая артель.

`sha == ""` — ссылки нет или git не ответил: вырожденный случай, на
котором `approve`/`run` ведут себя так же, как до T021 (существующие
тесты без реального git в песочнице — тот же путь).

`fix()` — точка ФИКСАЦИИ (`set_state`, `approve`), `read()` — точка
СВЕРКИ (`check_integrity` перед стартом шага, `fsm.confirm_fixation` на
approve, REVIEW.md T021 замечание 1 итераций 1-2). Обе читают голову
ссылки и ничего не коммитят: у ссылки нет рабочей копии, которую можно
было бы закоммитить или найти грязной.
"""
import sys
from datetime import datetime, timezone
from typing import NamedTuple

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
    """(sha, чисто) — фиксация текущего состояния документов задачи:
    голова её ссылки `refs/artifacts/<id>` (ADR-0021 п.3, инвариант 25 —
    «для документов — коммит ссылки»). Коммитить здесь нечего: в ссылку
    пишет только `artifact_branch.commit_files`, у неё нет рабочей копии,
    которая могла бы быть грязной. `target` в сигнатуре — ради
    вызывающего кода."""
    return _read_ref(task_id)


def _read_ref(task_id: str) -> tuple[str, bool]:
    """(голова `refs/artifacts/<id>`, True); ("", False) — ссылки нет или
    git не ответил. Отложенный импорт:
    `artifact_branch` берёт отсюда идентичность коммитов фиксации."""
    from . import artifact_branch
    sha = artifact_branch.ref_head(task_id)
    return (sha, True) if sha else ("", False)


def external_code_sha(target: str) -> str:
    """sha головы кодовой ветки ЦЕЛЕВОГО (SPEC T094, требование 9, AC-10):
    HEAD клона `config.PROJECTS/<target>/workspace` — тот же клон, в
    котором пишет код роль-разработчик (`runner.role_cwd`). Пустая строка
    — клона ещё нет или git не ответил."""
    return gitcmd.head_sha(config.PROJECTS / target / "workspace")


def external_artifact_sha(task_id: str) -> str:
    """sha головы ссылки документов задачи (SPEC T094, требование 9,
    AC-10) в её репозитории — для внешнего target это git проекта
    (`artifact_branch.task_repo`, ADR-0021 п.3). Пустая строка — ссылки
    ещё нет или git не ответил."""
    from . import artifact_branch
    return artifact_branch.ref_head(task_id)


def default_code_sha(conn, task_id: str) -> str:
    """sha головы кодовой ветки задачи self/артели (`config.DEFAULT_TARGET`,
    tasks/01M1P9RJVYHTAC087J4B2CAR44, требование 1) — репозиторий пульта
    (`config.ROOT`), где для self реально живёт код (`runner.role_cwd`:
    собственный worktree задачи, T045), НЕ фиксация документов (SPEC
    «Контекст»: её sha ошибочно уходил базой diff).

    `gitcmd.branch_head_sha` — независимо от текущего чекаута. Пустая строка — задачи нет в БД (`store.task_branch`)
    либо ветки ещё нет физически (вырожденный случай, как и у
    `external_code_sha`/`external_artifact_sha`)."""
    branch = store.task_branch(conn, task_id)
    return gitcmd.branch_head_sha(branch) if branch else ""


def read(task_id: str, target: str) -> tuple[str, bool]:
    """(sha, чисто) для сверки — не мутирует внешний target (единая
    логика для ЛЮБОГО target, A7 требование 2).

    Публичная точка входа для ЛЮБОЙ сверки (не фиксации): `check_integrity`
    (старт шага) и `fsm.confirm_fixation` (approve) обе только сравнивают
    текущее состояние с зафиксированным/переданным sha — ни та, ни другая
    не имеет права коммитить чужой WIP того же target как побочный эффект
    сравнения (REVIEW.md T021, замечание 1 итерации 1 — про
    `check_integrity`; замечание 1 итерации 2 — тот же класс дефекта в
    `confirm_fixation`, закрыт тем же приёмом).
    """
    return _read_ref(task_id)


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


# Именованная причина инцидента: голова ссылки документов ушла от
# `tasks.fixed_sha` мимо записей пульта (каждая запись пульта перефиксирует
# свой коммит сама — расхождение перед следующей записью оставила роль).
DOCS_REF_INCIDENT_ACTION = ("инцидент целостности: ссылка документов "
                            "сдвинута мимо пульта")
DOCS_REF_UNREAD_ACTION = ("фиксация не обновлена: голова ссылки документов "
                          "не прочитана")
LEGITIMIZED_ACTION = "голова ссылки документов узаконена Оператором"


class RefDrift(NamedTuple):
    """Расхождение головы ссылки документов с `tasks.fixed_sha`: `head`
    пуст — git не ответил (голова не прочитана), иначе голова ушла мимо
    пульта."""
    fixed: str
    head: str

    @property
    def moved(self) -> bool:
        return bool(self.head)

    def text(self) -> str:
        head = self.head or "не прочитана (git не ответил)"
        return f"зафиксировано {self.fixed}, голова ссылки {head}"


def ref_drift(conn, task_id: str) -> RefDrift | None:
    """Единственный узел сверки перед записью пульта, которая перефиксирует
    документы задачи (переход FSM, `answer`/`zones-extend`, `amend-tests`,
    коммит закрытия, `doctor --fix`, чекпоинты шага, `kill`): `None` —
    голова ссылки там, где её оставил пульт, или фиксации ещё нет (сверять
    не с чем, как у `check_integrity`). Иначе запись не коммитит поверх
    головы и не перефиксирует её: подмену узаконивает только `approve <id>
    <sha>` (`legitimize`), а при неответившем git фиксация остаётся
    прежней, и сверка на старте шага отказывает fail-closed.

    Голова читается в репозитории задачи (`read` -> `artifact_branch.
    ref_head`): для внешнего проекта — его git, не git главной копии.
    Голова читается и без фиксации — тот же порядок git-вызовов, что у
    прежней сверки чекпоинтов (`checkpoint._docs_ref_moved_past_pult`)."""
    head, _clean = read(task_id, store.task_target(conn, task_id))
    fixed = store.get_task(conn, task_id)["fixed_sha"]
    if not fixed or head == fixed:
        return None
    return RefDrift(fixed, head)


def journal_drift(conn, task_id: str, drift: RefDrift, actor: str,
                  what: str) -> None:
    """Запись журнала о невыполненной записи пульта: инцидент целостности
    при сдвиге мимо пульта, иначе — именованное «голова не прочитана»."""
    action = DOCS_REF_INCIDENT_ACTION if drift.moved else DOCS_REF_UNREAD_ACTION
    store.journal(conn, task_id, actor, action, f"{what}: {drift.text()}")


def incident_refusal(task_id: str, drift: RefDrift, what: str) -> str:
    """Текст именованного отказа команды при сдвиге мимо пульта."""
    return (f"[{task_id}] {what} отклонён: {DOCS_REF_INCIDENT_ACTION} — "
            f"{drift.text()}\n  разберись и: artel.py approve {task_id} "
            f"{drift.head}")


def stop_on_moved_ref(conn, task_id: str, actor: str, what: str) -> None:
    """Команда Оператора, коммитящая в ссылку документов (`answer`,
    `zones-extend`, `amend-tests`), при сдвиге мимо пульта не пишет ничего:
    рабочая задача уходит в эскалацию инцидентом (сам переход не коммитит
    паспорт и не перефиксирует — `store.set_state`), уже эскалированная
    остаётся в эскалации; команда кончается именованным отказом. Голова не
    прочитана — команда идёт дальше: её собственная запись в ссылку
    отказывает сама, а прежняя фиксация не трогается."""
    drift = ref_drift(conn, task_id)
    if drift is None or not drift.moved:
        return
    state = store.get_task(conn, task_id)["state"]
    if state in ("escalated", "done", "killed"):
        journal_drift(conn, task_id, drift, actor, f"{what} не выполнен")
    else:
        store.update_task(conn, task_id, escalated_from=state)
        store.set_state(conn, task_id, "escalated", actor,
                        expected_state=state,
                        detail=f"{DOCS_REF_INCIDENT_ACTION}: {what} не "
                               f"выполнен")
    sys.exit(incident_refusal(task_id, drift, what))


def legitimize(conn, task_id: str) -> None:
    """`approve <id> <sha>` с явным sha, уже сверенным с живой головой
    (`fsm.confirm_fixation`), — решение Оператора: голова, ушедшая мимо
    пульта, становится фиксацией, и переход approve её больше не считает
    инцидентом."""
    drift = ref_drift(conn, task_id)
    if drift is None or not drift.moved:
        return
    store.update_task(conn, task_id, fixed_sha=drift.head)
    store.journal(conn, task_id, "operator", LEGITIMIZED_ACTION,
                  f"approve с явным sha: было {drift.fixed}, "
                  f"теперь {drift.head}")


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
    dates = gitcmd.commit_committer_dates(entry_sha, current_sha)
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
