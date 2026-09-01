"""WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),
аварийное завершение (SPEC T074), `pause --now` (SPEC T074) и автокоммит
артефактов успешного шага (SPEC T059). Перенесено из orchestrator/runner.py
без изменения поведения (T091, декомпозиция диспетчеров fsm/runner).
"""
from pathlib import Path

from . import config, fixation, gitcmd, store, workspace


def commit_timeout_checkpoint(conn, task_id: str, role: str) -> str:
    """WIP-чекпоинт ветки задачи при таймауте шага — без участия Оператора.

    Таймаут обрывает шаг агента посреди работы (SPEC T041, «Контекст»):
    до этой задачи незакоммиченный WIP оставался в рабочем дереве, и
    сверка целостности на следующем `run` (`fixation.check_integrity`)
    честно встречала грязную копию и уводила задачу в `escalated` —
    рестарт решался только руками Оператора (прецеденты T022, T037).
    Здесь ровно то же действие, что раньше делал Оператор вручную,
    автоматически: `git add -A` + `git commit` поверх текущего рабочего
    дерева (оно и есть ветка задачи — роль создаёт и выписывает её
    первым действием миссии, до всякого таймаута).

    Коммитит, только если реально есть что коммитить (AC-4 — пустой
    коммит не заводится); ничего не коммитит и не журналит при отказе
    git на любом из шагов, а не только при «нечего коммитить» — тихий
    отказ здесь не хуже, чем при таймауте: `check_integrity` следующего
    `run` увидит либо прежнее чистое состояние, либо ту же грязную
    копию, что и до этой задачи, без нового способа сломаться.

    Идентичность коммита — служебная (`fixation.FIXATION_AUTHOR_*`), тем
    же приёмом, что уже применяет `fixation._fix_external` для коммита
    фиксации внешнего target: это действие оркестратора, а не роли и не
    Оператора, поэтому не берёт ни git-конфиг Оператора, ни авторство
    роли. Все git-операции — через `gitcmd`, не через прямой
    `subprocess`/`git` (SPEC требование 7).

    Коммит легитимно сдвигает HEAD ветки задачи мимо `store.set_state` —
    без повторной фиксации (`store.record_fixation`) следующий
    `fixation.check_integrity` увидел бы этот сдвиг как расхождение sha
    с зафиксированным на входе шага и увёл бы рестарт в инцидент
    целостности, ровно то, от чего чекпоинт должен избавить (AC-2).
    `check_integrity`/`fix()` при этом не меняются — фиксация читает их
    как обычно, просто с уже сдвинутым sha.

    Только догфуд (`target == config.DEFAULT_TARGET`, PLAN «Риски»,
    REVIEW.md T041 итерации 1, замечание major). С SPEC T045 (`runner.
    role_cwd`) догфуд-роль работает в СОБСТВЕННОМ worktree задачи
    (`workspace.path`), не в `config.ROOT`, — операции идут через
    `gitcmd.in_repo(workspace.path(task_id), ...)`, тем же приёмом, что
    `fixation._fix_dogfood` уже применяет к сверке чистоты worktree
    (SPEC T048). Коммитить в `config.ROOT` было бы неверно вдвойне — либо
    подхватило бы чужое незакоммиченное состояние главной копии под
    сообщением этой задачи, либо ничего не нашло бы, оставив настоящий
    WIP worktree'а нетронутым (класс-дефект T041×T045, докстринг
    исправлен в T048 — до этой правки функция ошибочно била по ROOT).
    Для внешнего target `check_integrity` смотрит не в workspace, а в
    артефактный репозиторий `.artel/projects/<target>/` (`fixation.read`/
    `_read_external`) — свой workspace ADR-0003 §4 вообще не коммитит
    (тот же довод, что `fsm._dirty_refuses`), поэтому чекпоинт workspace'а
    не решал бы исходную проблему AC-1/AC-2 для внешнего target. Пока
    `targets.yaml` объявляет только догфуд (ADR-0003 3д, «особый случай
    до A7»), эта ветка не задета вживую; расширение на внешний target —
    отдельная задача поверх многотаргетной архитектуры фиксации, не
    точечная правка этой функции.

    Git-обвязка (`add -A` → `diff --cached --quiet` → `commit`) —
    `_commit_worktree_change`, общая с `commit_step_artifacts` (SPEC
    T059): обе функции отличаются только сообщением коммита, текстом
    действия журнала и условием вызова (таймаут здесь, `rc == 0` там).
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    message = f"{task_id}: WIP-чекпоинт после таймаута шага {role}"
    committed, sha = _commit_worktree_change(wt, message)
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator",
                  "WIP-чекпоинт после таймаута шага", detail)
    store.record_fixation(conn, task_id)
    return detail


def commit_abnormal_checkpoint(conn, task_id: str, role: str, cause: str) -> str:
    """WIP-чекпоинт при аварийном завершении шага: rc != 0 или обрыв
    stdout-пайпа без таймаута (SPEC T074, требование 3 — расширение
    правила T041 «чекпоинт только на таймауте»: до этой задачи оба
    случая оставляли WIP как есть — rc != 0 сознательно (T041, «не
    входит»), обрыв пайпа с rc=0 попадал под безусловный успешный
    `commit_step_artifacts` и получал сообщение обычного автокоммита,
    неотличимое от штатного успеха шага (см. `tasks/T074/acceptance_tests/
    test_ac9_checkpoint_on_abnormal_step_end.py`, докстринг модуля).

    Сообщение и действие журнала несут слово «чекпоинт» (та же природа,
    что `commit_timeout_checkpoint`) плюс `cause` — короткая пометка
    причины («rc=1», «обрыв потока»), которую вызыватель формирует под
    свой сценарий; `commit_timeout_checkpoint` не тронут — таймаут
    остаётся отдельной веткой со своим прежним сообщением.

    Остальное поведение — дословно `commit_timeout_checkpoint`: только
    догфуд, коммитит, только если есть что коммитить, тихая деградация
    без git, общая обвязка `_commit_worktree_change` (SPEC T059), повторная
    фиксация (`store.record_fixation`) — тот же довод, что там.
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    message = f"{task_id}: WIP-чекпоинт после аварийного завершения шага {role} ({cause})"
    committed, sha = _commit_worktree_change(wt, message)
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator",
                  "WIP-чекпоинт после аварийного завершения шага", detail)
    store.record_fixation(conn, task_id)
    return detail


def commit_pause_now_checkpoint(conn, task_id: str, role: str) -> str:
    """WIP-чекпоинт при `pause --now` бегущего шага (SPEC T074,
    требования 1 и 3): вызывается `orchestrator.pause.cmd_pause_now`
    ПОСЛЕ того, как процесс шага уже прерван — оркестратор чекпоинтит
    дерево worktree задачи так же, как при таймауте (T041/T059), но из
    ДРУГОГО процесса (того, что выполняет саму `pause --now`), не из
    того, что запускало шаг.

    Сообщение коммита несёт литерал «pause --now» (SPEC, требование 1:
    «пометка причины «pause --now»», AC-3) — им же, а не отдельным
    словом «чекпоинт» в отрыве от причины, ищет пометку приёмочный тест
    (`tasks/T074/acceptance_tests/
    test_ac2_ac3_ac4_ac5_interrupt_sequence.py`).

    Остальное — общая обвязка `_commit_worktree_change` (только догфуд,
    коммитит только при реальном diff, тихая деградация без git,
    `store.record_fixation` — та же фиксация, что не даёт следующему
    `fixation.check_integrity` увидеть сдвиг HEAD как инцидент, AC-14).
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    message = f"{task_id}: WIP-чекпоинт pause --now (шаг {role} прерван)"
    committed, sha = _commit_worktree_change(wt, message)
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator", "WIP-чекпоинт pause --now",
                  detail)
    store.record_fixation(conn, task_id)
    return detail


def commit_step_artifacts(conn, task_id: str, role: str) -> str:
    """Автокоммит незакоммиченных артефактов роли по завершении успешного
    шага (rc=0), до advance-логики (SPEC T059, требования 1-3).

    Класс «роль завершила шаг rc=0, но не закоммитила артефакт»
    повторился 10 раз (REVIEW.md T041, T044, T045, T048, T051, T052) —
    каждый раз отказ `advance`, инцидент целостности и спасение
    Оператором вручную (`git add && git commit`); спасённый Оператором
    артефакт при этом был неотличим от роль-произведённого —
    `author_role` лгал о происхождении (наблюдение ревьювера T052). Эта
    функция делает то же самое действие сама, служебным коммитом
    оркестраторского авторства (`fixation.FIXATION_AUTHOR_*`), а не
    подделкой авторства роли: журнал несёт `actor=orchestrator`, тем же
    правом, каким оркестратор уже коммитит фиксацию и WIP-чекпоинт
    таймаута.

    Коммитит, только если реально есть что коммитить: роль уже
    закоммитила свои изменения сама → `_commit_worktree_change` не
    находит застейдженного диффа, пустой коммит не заводится и запись в
    журнал не пишется (требование 2). Молча отказывает при отказе git
    на любом из шагов — та же деградация без git, что у
    `commit_timeout_checkpoint` (требование 6).

    Только догфуд (`target == config.DEFAULT_TARGET`) — тем же доводом,
    что уже есть в докстринге `commit_timeout_checkpoint`: для внешнего
    target собственная фиксация уже коммитит артефактный репозиторий
    целиком на переходе FSM (`fixation._fix_external`), а свой
    `workspace` внешний target вообще не коммитит (ADR-0003 §4) — новый
    механизм не решал бы для него никакой проблемы.

    `git add` ограничен путями worktree задачи целиком (требование 3):
    `_commit_worktree_change` зовёт `gitcmd.in_repo(wt, "add", "-A")` —
    `-A` без путей добавляет изменения всего рабочего дерева РЕПОЗИТОРИЯ
    `wt` (её отдельного git-worktree, ветка задачи), не произвольного
    дерева и не рабочей копии пульта (урок инцидента T048 с чужой
    сессией пульта — здесь операции вообще не видят `config.ROOT`).
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    message = f"{task_id}: артефакты шага {role} (автокоммит оркестратора)"
    committed, sha = _commit_worktree_change(wt, message)
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator",
                  "автокоммит артефактов шага", detail)
    store.record_fixation(conn, task_id)
    return detail


def _commit_worktree_change(wt: Path, message: str) -> tuple[bool, str]:
    """(закоммичено, sha) — `add -A` + `commit` служебной идентичностью
    В ЗАДАННОМ worktree; `закоммичено=False` — нечего коммитить или git
    не ответил на любом из трёх шагов.

    Общая обвязка `commit_timeout_checkpoint` и `commit_step_artifacts`
    (SPEC T059) — обе отличаются только сообщением коммита и моментом
    вызова, сама последовательность git-операций (и её деградация без
    git) — одна на двоих.
    """
    added = gitcmd.in_repo(wt, "add", "-A")
    if added.returncode != 0:
        return False, ""
    staged = gitcmd.in_repo(wt, "diff", "--cached", "--quiet")
    if staged.returncode != 1:  # 0 — нечего коммитить, иное — git не ответил
        return False, ""
    commit = gitcmd.in_repo(
        wt, "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
        "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
        "commit", "-q", "-m", message)
    if commit.returncode != 0:
        return False, ""
    return True, gitcmd.head_sha(wt)
