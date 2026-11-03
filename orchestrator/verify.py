"""Профиль проверок этапа `verifying`: ожидание ручной проверки
`human:<имя>` и команды Оператора `verify-ok`/`verify-fail` (SPEC
01M6F3DKM3KB2JYMD0J50YRBPE; ADR-0029 п. 10).

Профиль — поле `description.verify` записи проекта (`targets.verify_checks`).
После зелёного CI головы и прохода гейта по исходам опрос `verifying`
(`fsm_advance.verifying`) не уводит задачу в `review`, а входит в
ожидание: пишет одну запись журнала `WAIT_ACTION` «ждёт проверки <имя> по
sha <sha>» на визит `verifying` и голову. Визит — отрезок журнала после
последней записи входа `state -> verifying`. Ожидание держится, пока
последняя из записей «ожидание» / «статус CI» визита — запись ожидания:
опрос после новой головы пишет статус CI, и прежнее ожидание снято.

Отметка `verify-ok` действительна для своей головы и своего визита
(таблица `verify_marks`); переход в `review` — когда по текущей голове в
этом визите отмечены все проверки профиля. `verify-fail` — возврат в
`in_dev` с пределом `config.LIMIT_REVIEW_ITERS` по своему счётчику
`tasks.verify_fails`. Пульт стенд не разворачивает и конвейер не
запускает: этап только ждёт отметок (требование 6).

`lease`, `gitcmd`, `workspace`, `fsm` импортируются отложенно: модуль
читают `board` и `watch`, которые сами входят в граф импортов `fsm`.
"""
import re
import sys

from . import config, store, targets

WAIT_ACTION = "ожидание ручной проверки"
WAIT_TEXT = "ждёт проверки"
OK_ACTION = "verify-ok: проверка отмечена"
FAIL_ACTION = "verify-fail: проверка не пройдена"
VISIT_ACTION = "state -> verifying"
NOT_EXPECTED = "проверка не ожидается для этой головы"
OTHER_HEAD = "отметка для другой головы"
# Причина и подсказка остановки `auto` на ожидании отметки (требование 5):
# без алерта, как на гейте Оператора.
AUTO_STOP_REASON = "ждёт ручной проверки Оператора"
AUTO_STOP_HINT = ('verify-ok {id} <имя> <sha> "<итог>" | '
                  'verify-fail {id} <имя> "<причина>"')
_MIN_SHA = 7
_WAIT_RE = re.compile(rf"{WAIT_TEXT} (\S+) по sha ([0-9a-f]+)")


class Wait:
    """Ожидание отметки текущего визита: запись входа в визит и голова."""

    def __init__(self, visit_step_id: int, name: str, sha: str):
        self.visit_step_id = visit_step_id
        self.name = name
        self.sha = sha


def wait_text(name: str, sha: str) -> str:
    return f"{WAIT_TEXT} {name} по sha {sha}"


def checks(target: str | None) -> list:
    """Имена проверок `human:*` профиля проекта; [] — профиля нет.
    TargetsError — запись проекта не прочитана. Артель профиля не несёт:
    поле `verify` в слое репозитория — отказ загрузки (требование 1)."""
    if (target or config.DEFAULT_TARGET) == config.DEFAULT_TARGET:
        return []
    return targets.verify_checks(targets.target(target))


def head(task_id: str, branch: str) -> str:
    """sha головы ветки задачи в её репозитории; "" — git не ответил."""
    from . import gitcmd, workspace
    return gitcmd.branch_head_sha(branch, repo=workspace.task_repo(task_id))


def current_wait(conn, task_id: str) -> Wait | None:
    """Ожидание отметки текущего визита `verifying`; None — его нет."""
    from . import fsm
    visit = store.last_task_step_of(conn, task_id, (VISIT_ACTION,))
    if visit is None:
        return None
    last = store.last_task_step_of(conn, task_id,
                                   (WAIT_ACTION, fsm.VERIFYING_STATUS_ACTION))
    if last is None or last["action"] != WAIT_ACTION or last["id"] < visit["id"]:
        return None
    match = _WAIT_RE.search(last["detail"] or "")
    if match is None:
        return None
    return Wait(visit["id"], match.group(1), match.group(2))


def waiting(conn, t) -> bool:
    """Задача в `verifying` ждёт отметки Оператора (требование 2)."""
    return t["state"] == "verifying" and current_wait(conn, t["id"]) is not None


def _unmarked(conn, task_id: str, wait: Wait, names: list) -> list:
    marked = store.verify_marked_names(conn, task_id, wait.sha,
                                       wait.visit_step_id)
    return [name for name in names if name not in marked]


def status_text(conn, t) -> str | None:
    """«ждёт проверки <первая неотмеченная> по sha <голова>» задачи в
    ожидании отметки; None — задача отметки не ждёт."""
    if t["state"] != "verifying":
        return None
    wait = current_wait(conn, t["id"])
    if wait is None:
        return None
    try:
        rest = _unmarked(conn, t["id"], wait, checks(t["target"]))
    except targets.TargetsError:
        rest = []
    return wait_text(rest[0] if rest else wait.name, wait.sha)


def _to_review(conn, task_id: str, state: str, sha: str, names: list,
               actor: str) -> None:
    store.set_state(conn, task_id, "review", actor, expected_state=state,
                    detail=f"ручные проверки пройдены по sha {sha}: "
                           f"{', '.join(names)}")


def hold(conn, task_id: str, state: str, names: list, sha: str) -> bool:
    """Опрос задачи, уже ждущей отметки по голове `sha`: True — опрос
    исчерпан здесь (ожидание держится или все проверки отмечены и задача
    ушла в `review`); False — ожидания по этой голове нет, опрос идёт
    прежним путём CI. Потолок `VERIFYING_CEILING_SEC` сюда не доходит:
    ожидание человека, не CI (требование 2)."""
    wait = current_wait(conn, task_id)
    if wait is None or wait.sha != sha:
        return False
    rest = _unmarked(conn, task_id, wait, names)
    if not rest:
        _to_review(conn, task_id, state, sha, names, "fsm")
        return True
    print(f"[{task_id}] {wait_text(rest[0], sha)} — verify-ok/verify-fail "
          f"Оператора")
    return True


def enter_wait(conn, task_id: str, state: str, names: list, sha: str) -> None:
    """Вход в ожидание после зелёного CI головы `sha` и прохода гейта по
    исходам в этом визите: одна запись журнала на визит и голову —
    повторные опросы её не повторяют, их забирает `hold`."""
    visit = store.last_task_step_of(conn, task_id, (VISIT_ACTION,))
    marked = (store.verify_marked_names(conn, task_id, sha, visit["id"])
              if visit is not None else set())
    rest = [name for name in names if name not in marked]
    if not rest:
        _to_review(conn, task_id, state, sha, names, "fsm")
        return
    text = wait_text(rest[0], sha)
    store.journal(conn, task_id, "fsm", WAIT_ACTION, text)
    print(f"[{task_id}] {text} — verify-ok/verify-fail Оператора")


# ------------------------------------------------------- команды Оператора


def _refuse(task_id: str, command: str, text: str) -> None:
    sys.exit(f"[{task_id}] {command}: отказ — {text}")


def _profile_name(task_id: str, command: str, t, name: str) -> list:
    """Имена профиля проекта задачи; отказ — имени `name` в профиле нет."""
    if t["state"] != "verifying":
        _refuse(task_id, command,
                f"применим только в verifying (сейчас {t['state']})")
    try:
        names = checks(t["target"])
    except targets.TargetsError as exc:
        _refuse(task_id, command, f"запись проекта не прочитана: {exc}")
    if name not in names:
        known = ", ".join(f"human:{n}" for n in names) or "профиль пуст"
        _refuse(task_id, command, f"проверки human:{name} нет в профиле "
                                  f"verify проекта {t['target']} ({known})")
    return names


def cmd_verify_ok(task_id: str, name: str, sha: str, summary: str,
                  session_id: str | None = None) -> None:
    """`verify-ok <id> <имя> <sha> "<итог>"` — Оператор отмечает ручную
    проверку `human:<имя>` по текущей голове (требование 3)."""
    from . import lease
    lease.run_task_command(
        task_id, session_id,
        lambda conn, tid: _verify_ok(conn, tid, name, sha, summary))


def _verify_ok(conn, task_id: str, name: str, sha: str, summary: str) -> None:
    command = "verify-ok"
    t = store.get_task(conn, task_id)
    names = _profile_name(task_id, command, t, name)
    if not summary.strip():
        _refuse(task_id, command, "итог проверки пуст")
    current = head(task_id, t["branch"])
    if not current:
        _refuse(task_id, command, "голова ветки задачи не прочитана")
    given = sha.strip().lower()
    if len(given) < _MIN_SHA or not current.startswith(given):
        _refuse(task_id, command, f"{OTHER_HEAD}: {sha} — текущая голова "
                                  f"{current}")
    wait = current_wait(conn, task_id)
    if wait is None or wait.sha != current:
        _refuse(task_id, command, f"{NOT_EXPECTED} ({current}): записи "
                                  f"«{WAIT_TEXT} … по sha {current}» в этом "
                                  f"визите verifying нет — CI головы не "
                                  f"зелёный или гейт по исходам не пройден")
    rest = _unmarked(conn, task_id, wait, names)
    if name not in rest:
        _refuse(task_id, command, f"проверка {name} по sha {current} уже "
                                  f"отмечена")
    store.insert_verify_mark(conn, task_id, name, current, summary,
                             wait.visit_step_id, "operator")
    store.journal(conn, task_id, "operator", OK_ACTION,
                  f"{name} по sha {current}: {summary}")
    rest.remove(name)
    if rest:
        print(f"[{task_id}] проверка {name} отмечена; "
              f"{wait_text(rest[0], current)}")
        return
    _to_review(conn, task_id, "verifying", current, names, "operator")
    print(f"[{task_id}] проверка {name} отмечена; все проверки пройдены — "
          f"review")


def cmd_verify_fail(task_id: str, name: str, reason: str,
                    session_id: str | None = None) -> None:
    """`verify-fail <id> <имя> "<причина>"` — проверка не пройдена: возврат
    в `in_dev` с пределом `config.LIMIT_REVIEW_ITERS` (требование 4)."""
    from . import lease
    lease.run_task_command(
        task_id, session_id,
        lambda conn, tid: _verify_fail(conn, tid, name, reason))


def _verify_fail(conn, task_id: str, name: str, reason: str) -> None:
    from . import fsm
    command = "verify-fail"
    t = store.get_task(conn, task_id)
    _profile_name(task_id, command, t, name)
    if not reason.strip():
        _refuse(task_id, command, "причина возврата пуста")
    limit = config.LIMIT_REVIEW_ITERS
    fails = (t["verify_fails"] or 0) + 1
    # Счётчик растёт на каждом возврате и эскалацией не сбрасывается
    # (инвариант 3): после возврата из эскалации следующий `verify-fail`
    # снова доводит его до предела.
    store.update_task(conn, task_id, verify_fails=fails)
    store.journal(conn, task_id, "operator", FAIL_ACTION,
                  f"{name} ({fails}/{limit}): {reason}")
    if fails >= limit:
        store.set_state(conn, task_id, "escalated", "operator",
                        expected_state="verifying",
                        detail=f"лимит возвратов verify-fail {limit} "
                               f"исчерпан — проверка {name} не пройдена: "
                               f"{reason}")
        print(f"[{task_id}] лимит возвратов verify-fail исчерпан — эскалация")
        return
    store.set_state(conn, task_id, "in_dev", "operator",
                    expected_state="verifying",
                    detail=f"проверка {name} не пройдена (verify-fail "
                           f"{fails}/{limit}): {reason}")
    fsm._maybe_ensure_draft_mr(conn, task_id)
    print(f"[{task_id}] проверка {name} не пройдена — in_dev")
