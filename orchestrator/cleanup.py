"""kill switch и уборка хвостов задачи: каталог артефактов и ветка."""
import shutil

from . import config, gitcmd, lease, store, workspace


def artifacts_in_main(task_id: str) -> bool | None:
    """Есть ли каталог задачи в дереве main. None — git не ответил.

    Достаточно самого факта наличия: артефакты задачи, убитой после
    мержа, — история (docs/design.md §6), её не трогаем целиком.
    """
    res = gitcmd.git("ls-tree", "-r", "--name-only", config.MAIN_BRANCH, "--",
                     f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def artifacts_tracked_here(task_id: str) -> bool | None:
    """Отслеживается ли каталог задачи здесь и сейчас. None — git не ответил.

    Смотрит индекс, а не дерево HEAD: закоммиченный в текущую ветку и
    просто добавленный `git add` каталоги одинаково опасны для rmtree.
    """
    res = gitcmd.git("ls-files", "--", f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def drop_task_dir(task_id: str) -> str:
    """Убирает каталог артефактов убитой задачи; строка — что вышло."""
    tdir = config.TASKS / task_id
    in_main = artifacts_in_main(task_id)
    if in_main is None:
        return f"каталог tasks/{task_id}/ оставлен: main не прочитан"
    if in_main:
        return f"каталог tasks/{task_id}/ оставлен: артефакты в main"
    if not tdir.exists():
        return f"каталога tasks/{task_id}/ нет"
    # Каталог убитой задачи мог уехать в чужую ветку через `git add -A`
    # разработчика — ровно инцидент T002 из SPEC. rmtree по отслеживаемым
    # файлам оставит в дереве удаления, которые следующий `git add -A`
    # утащит в тот же чужой коммит: мусор вместо уборки.
    tracked = artifacts_tracked_here(task_id)
    if tracked is None:
        return f"каталог tasks/{task_id}/ оставлен: индекс не прочитан"
    if tracked:
        here = gitcmd.current_branch()
        fix = ("сними его из индекса и повтори kill"
               if here == config.MAIN_BRANCH
               else f"перейди на {config.MAIN_BRANCH} и повтори kill")
        return (f"каталог tasks/{task_id}/ оставлен: отслеживается в "
                f"{here or 'текущей ветке'} — {fix}")
    try:
        shutil.rmtree(tdir)
    except OSError as exc:
        return f"каталог tasks/{task_id}/ не удалён: {exc}"
    return f"удалён каталог tasks/{task_id}/"


def drop_task_branch(branch: str) -> str:
    """Убирает локальную ветку убитой задачи; строка — что вышло."""
    if not branch:
        # Строка задачи из БД прошлых версий: ветка не записана — искать нечего.
        return "ветка задачи не записана — нечего удалять"
    if not gitcmd.branch_exists(branch):
        return f"локальной ветки {branch} нет"
    if gitcmd.branch_merged(branch):
        return f"ветка {branch} оставлена: смержена в {config.MAIN_BRANCH}"
    # -D, а не -d: удалить надо именно неслитую ветку, а на ней `-d` откажет.
    res = gitcmd.git("branch", "-D", branch)
    if res.returncode != 0:
        return f"ветка {branch} не удалена: {res.stderr.strip()[:200]}"
    return f"удалена ветка {branch}"


def drop_merged_task_branch(branch: str) -> str:
    """Убирает ветку задачи, ТОЛЬКО ЧТО влитую в main (переход `merge_gate
    -> done`, tasks/T073/SPEC.md, требование 2): строка — что вышло.

    Не `drop_task_branch` (kill): та НАМЕРЕННО оставляет смерженную ветку
    — «история killed-задачи»; здесь наоборот, смержённость — условие
    удаления, не повод оставить (merge остаётся `--no-ff` без squash —
    история мержа в main полная, docs/retention.md). `-d` (safe delete),
    не `-D`: git сам откажет, если ветка внезапно не влита — единственная
    защита, которая тут нужна. Вызывается ПОСЛЕ уборки worktree
    (`workspace.remove`) — `-d` не удалит ветку, пока её держит worktree.
    """
    if not branch:
        return "ветка задачи не записана — нечего удалять"
    if not gitcmd.branch_exists(branch):
        return f"локальной ветки {branch} нет"
    res = gitcmd.git("branch", "-d", branch)
    if res.returncode != 0:
        return f"ветка {branch} не удалена: {res.stderr.strip()[:200]}"
    return f"удалена ветка {branch}"


def cleanup_killed_task(conn, task_id: str, branch: str) -> None:
    """Убирает хвосты убитой задачи и перечисляет сделанное в журнале.

    Уборка идёт после смены состояния и не может её отменить: kill switch
    обязан срабатывать всегда. Поэтому любой невыясненный факт (git
    промолчал, main не найден) — это «оставлено» со своей причиной, а не
    исключение. Логи прогонов в .artel/logs/ не трогаются — история
    наблюдаемости переживает задачу.
    """
    # Не `branch_exists`: кроме факта нужна причина — отсутствующий main и
    # неустановленный git разбираются Оператором по-разному.
    main = gitcmd.git("rev-parse", "--verify", "--quiet",
                      f"refs/heads/{config.MAIN_BRANCH}")
    if main.returncode != 0:
        reason = main.stderr.strip()[:200] or f"ветки {config.MAIN_BRANCH} нет"
        notes = [f"уборка пропущена: {reason} — сверять не с чем"]
    elif gitcmd.current_branch() == branch:
        # Агент шага работает в своём worktree (SPEC T045), а не в главной
        # копии, но Оператор мог руками зачекаутить ветку задачи в ROOT
        # (ADR-0003 3д — главная копия остаётся обычной рабочей копией
        # git). Удалить такую ветку git не даст, а снести закоммиченный
        # в неё каталог — оставить грязное дерево: ровно тот мусор, ради
        # которого уборка и заводилась.
        notes = [f"уборка пропущена: ветка {branch} сейчас checked out — "
                 f"перейди на {config.MAIN_BRANCH} и повтори kill"]
    else:
        # Worktree — первым: ветку с `-D` не удалить, пока её держит
        # worktree (SPEC T045, требование 5, AC-5).
        notes = [workspace.remove(task_id), drop_task_dir(task_id),
                 drop_task_branch(branch)]

    store.journal(conn, task_id, "orchestrator", "уборка", "; ".join(notes))
    for note in notes:
        print(f"  {note}")


def cmd_kill(task_id: str, session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2)."""
    conn = store.db()
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_kill(conn, task_id))



# Литерал действия журнала — источник «Сути» killed-RETRO следующего
# merge_gate (SPEC T048, требование 6, `orchestrator/retro.py`); строка
# сверяется буквально, тем же приёмом, что `retro._actor_costs`/
# `_escalations` уже сверяются с литералами `runner.py`/`store.py`.
KILL_TZ_JOURNAL_ACTION = "kill: TZ.md"


def _journal_tz_before_cleanup(conn, task_id: str, branch: str,
                               target: str) -> None:
    """Полный текст `TZ.md` (если он был) — в журнал БД ДО уборки ветки
    (SPEC T048, требование 5): main для убитой задачи не видел ни SPEC.md,
    ни TZ.md вовсе (требование 4), а сама ветка после `cleanup_killed_task`
    удаляется — читать станет неоткуда. Ветко-корректное чтение
    (`gitcmd.show`), тем же приёмом, что и `runner.step_role` (T031/T047,
    требование 7): TZ.md коммитится `cmd_new` сразу в ветку, не на диск.
    Файла нет (`new` без `--tz`) — журналить нечего, не отказ.

    Внешний target (SPEC T094, требование 10): `tasks/<id>/` живёт в
    артефактной ветке пульта, не в `branch` (та несёт только код целевого
    и пульту вообще не принадлежит) — читается оттуда.
    """
    if target != config.DEFAULT_TARGET:
        from . import artifact_branch
        source_branch = artifact_branch.branch_name(task_id)
    else:
        source_branch = branch
    text, _ = gitcmd.show(source_branch, f"tasks/{task_id}/TZ.md")
    if text is not None:
        store.journal(conn, task_id, "orchestrator",
                      KILL_TZ_JOURNAL_ACTION, text)


# Терминальные состояния FSM: kill из них — no-op на самом переходе
# (SPEC T050, требование 6) — уборка ниже всё равно остаётся безусловной.
TERMINAL_STATES = ("done", "killed")


def _cmd_kill(conn, task_id: str) -> None:
    """Kill switch: убивает задачу из ЛЮБОГО нетерминального состояния,
    даже если конкурентная сессия успела перейти между чтением состояния
    и CAS-попыткой (SPEC T050, требования 6-7, инвариант №14).

    Единственный вызыватель `set_state`, которому разрешено повторять
    проигрыш CAS (требование 6, в отличие от advance/approve/reject/merge
    — требование 4): проигрыш называет фактическое состояние
    (`store.CasConflict.actual`) без лишнего `get_task` — им и
    повторяется попытка. Задача уже терминальна (на входе или гонка
    подвела туда же) — сообщается и завершается без ошибки (требование
    6), но не отменяет уборку хвостов ниже — `test_repeated_kill_finds_
    nothing_and_does_not_fail` (tests/test_kill_cleanup.py) требует, чтобы
    повторный kill на уже killed задаче всё равно доводил её до конца.
    """
    t = store.get_task(conn, task_id)
    target = t["target"] or config.DEFAULT_TARGET
    _journal_tz_before_cleanup(conn, task_id, t["branch"], target)
    state = t["state"]
    won = False
    while not won and state not in TERMINAL_STATES:
        try:
            store.set_state(conn, task_id, "killed", "operator",
                            expected_state=state, detail="kill switch")
            won = True
        except store.CasConflict as exc:
            state = exc.actual
    if not won:
        print(f"[{task_id}] уже {state} — kill не требуется")
    _publish_snapshot_if_pending(conn, task_id, target, bool(t["is_canary"]))
    cleanup_killed_task(conn, task_id, t["branch"])


def _publish_snapshot_if_pending(conn, task_id: str, target: str,
                                 is_canary: bool) -> None:
    """Снапшот закрытия (SPEC T094, требования 12-13, AC-13) — только
    внешний target (требование 16/AC-18) и не канарейка (требование 12,
    AC-13 «исключение канарейки»). `snapshot.pending` — False, если
    задача не заводила артефактную ветку вовсе (self/канарейка) или
    снапшот уже подтверждён в origin целевого раньше (идемпотентность
    повторного `kill`, AC-15).

    Отложенный импорт: `snapshot` -> `retro` -> `cleanup` — прямой
    импорт на уровне модуля замкнул бы этот же файл в цикл.
    """
    if target == config.DEFAULT_TARGET or is_canary:
        return
    from . import snapshot
    if not snapshot.pending(task_id):
        return
    note = snapshot.publish_and_cleanup(conn, task_id, target, "killed")
    print(f"  {note}")
