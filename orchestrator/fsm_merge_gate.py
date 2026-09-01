"""Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):
разбор конфликта merge, ре-ран флейка CI, ожидание CI ветки вне мьютекса,
собственно merge в main. Перенесено из orchestrator/fsm.py без изменения
поведения (T091, декомпозиция диспетчеров fsm/runner).
"""
import sys
import time

from . import ci, cleanup, config, fsm, fsm_postmerge, gitcmd, merge_lock, store, workspace


def _touches_protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in config.PROTECTED_PATHS)


def _handle_merge_conflict(conn, task_id: str, state: str, branch: str,
                           merge_res) -> None:
    """Разбор провала `git merge --no-ff <branch>` при `approve` из
    `merge_gate` (SPEC T052, требования 2-3; AC-3, AC-4, AC-5).

    Отличает содержательный конфликт (git начал merge, но не смог
    разрешить его сам) от инфраструктурного отказа: список файлов с
    неразрешённым конфликтом (`git diff --name-only --diff-filter=U`)
    пуст или git не ответил — конфликта в СОДЕРЖИМОМ нет, отказ прежний
    (`sys.exit`, задача остаётся в `merge_gate`, требование 3/AC-5).

    Список не пуст — содержательный конфликт: `git merge --abort`
    возвращает main в чистое состояние (требование 5), а задача уходит
    в `in_dev` (AC-3) либо, если конфликт задевает защищённый путь
    (`config.PROTECTED_PATHS`), в `escalated` (AC-4) — оба перехода
    несут перечень конфликтующих файлов в журнал через `detail`
    `store.set_state`. Если сам `git merge --abort` не удался, main
    остаётся с незавершённым merge — переход состояния НЕ выполняется
    (иначе main тихо остался бы грязным при формально успешном
    переходе, ломая последующие approve других задач); это
    инфраструктурный отказ той же природы, что и «git не ответил»
    выше — `sys.exit`, задача остаётся в `merge_gate`.
    """
    store.journal(conn, task_id, "orchestrator", "merge FAILED",
                  merge_res.stderr.strip()[:500])
    conflicts = gitcmd.git("diff", "--name-only", "--diff-filter=U")
    files = sorted(set(conflicts.stdout.split())) \
        if conflicts is not None and conflicts.returncode == 0 else []
    if not files:
        sys.exit(f"merge упал на git merge --no-ff {branch}:\n"
                 f"{merge_res.stderr}")

    abort = gitcmd.git("merge", "--abort")
    if abort is None or abort.returncode != 0:
        abort_err = abort.stderr.strip()[:500] if abort is not None else "git не ответил"
        store.journal(conn, task_id, "orchestrator", "merge --abort FAILED",
                      abort_err)
        sys.exit(f"[{task_id}] merge отклонён: конфликт в файлах "
                 f"{', '.join(files)}, но git merge --abort не смог "
                 f"вернуть main в чистое состояние ({abort_err}); "
                 f"main требует ручной уборки Оператором; задача осталась "
                 f"в merge_gate")

    file_list = ", ".join(files)
    protected = [f for f in files if _touches_protected_path(f)]
    if protected:
        detail = (f"конфликт merge затрагивает защищённый путь "
                  f"({', '.join(protected)}); конфликтующие файлы: "
                  f"{file_list}")
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state, detail=detail)
    else:
        detail = (f"содержательный конфликт merge — возврат в разработку; "
                  f"конфликтующие файлы: {file_list}")
        store.set_state(conn, task_id, "in_dev", "fsm",
                        expected_state=state, detail=detail)
        fsm._maybe_ensure_draft_mr(conn, task_id)


def _ci_confirm_red_or_flake(conn, task_id: str, branch: str,
                             note: str) -> tuple[bool, str]:
    """Ре-ран однократного ПОДТВЕРЖДЁННО красного статуса (SPEC T082,
    требование 7, AC-14..17) — общий узел однократной проверки CI (ветка
    `"fresh"` ниже) и цикла ожидания CI после подтяжки
    (`_wait_for_branch_ci_green`, SPEC T087 требование 3). Флейк (ре-ран
    зелёный) — возврат зелёного исхода ре-рана вызывающему коду; красный
    статус, подтверждённый ре-раном, — `sys.exit` тем же текстом, что и
    раньше (не возвращается).
    """
    rerun_trigger_note = ci.trigger_rerun(branch)
    store.journal(conn, task_id, "orchestrator", "ре-ран CI запущен",
                  rerun_trigger_note)
    rerun_green, rerun_note = ci.branch_status(branch)
    store.journal(conn, task_id, "orchestrator",
                  "статус CI ветки (ре-ран)", rerun_note)
    if rerun_green:
        store.journal(
            conn, task_id, "orchestrator", "flake-rate",
            f"флейк: первый статус красный, ре-ран зелёный "
            f"({note} -> {rerun_note})")
        return rerun_green, rerun_note
    store.journal(
        conn, task_id, "orchestrator", "flake-rate",
        f"подтверждённый красный: первый статус красный, ре-ран "
        f"тоже красный ({note} -> {rerun_note})")
    sys.exit(f"[{task_id}] merge отклонён: {rerun_note}\n"
             f"  задача осталась на гейте merge; почини CI ветки "
             f"{branch} и повтори: artel.py approve {task_id}")


def _wait_for_branch_ci_green(conn, task_id: str, branch: str,
                              start: float, deadline: float) -> str:
    """Цикл ожидания CI пушнутого head ВНЕ мьютекса merge-окна (SPEC T087,
    требования 2-4, 7-9; решение Оператора 31.08, аудит v6 Q-5).

    Каждая итерация опрашивает `ci.branch_status` и журналирует/печатает
    статус и прошедшее с `start` (момент первого пуша ЭТОГО вызова
    `approve`) время (требование 9). «CI ещё идёт»/«статус неизвестен»
    паузит `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)` и продолжает
    цикл (требование 3), пока не истёк общий потолок `deadline` (требование
    4, `time.monotonic()` — тот же приём часов, что уже применяет
    `orchestrator/pause.py`) — тогда `sys.exit` «статус CI неизвестен»
    (требование 8). Подтверждённо красный статус — `_ci_confirm_red_or_
    flake` (требование 7, тот же узел, что и однократная проверка): флейк
    возвращает зелёный исход, подтверждённый красный сам завершает
    процесс `sys.exit`'ом (требование 7).

    Возврат — `note` зелёного статуса (требование 5: вызывающий код
    передаёт его следующему заходу в тело гейта, чтобы не спрашивать CI
    повторно для того же самого head).
    """
    while True:
        green, note = ci.branch_status(branch)
        elapsed = int(time.monotonic() - start)
        detail = f"{note} (ожидание {elapsed} сек)"
        store.journal(conn, task_id, "orchestrator",
                      "ожидание CI (цикл merge_gate)", detail)
        print(f"[{task_id}] {detail}")
        if green:
            return note
        if ci.status_kind(note) == "red":
            _, confirmed_note = _ci_confirm_red_or_flake(conn, task_id,
                                                          branch, note)
            return confirmed_note
        if time.monotonic() >= deadline:
            sys.exit(f"[{task_id}] merge отклонён: статус CI неизвестен — "
                     f"потолок ожидания истёк ({note})\n"
                     f"  задача осталась на гейте merge; почини CI ветки "
                     f"{branch} и повтори: artel.py approve {task_id}")
        time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)


def _cmd_approve_merge_gate(conn, task_id: str, state: str, t,
                            confirmed_ci_note: str | None = None) -> tuple:
    """Тело окна `merge_gate -> done`, исполняемое ПОД МЬЮТЕКСОМ merge
    (SPEC T053, требование 1; SPEC T087, требования 1-2, 5-6): сверка
    главной копии -> сверка свежести ветки внутри окна (требования 5-8
    T053) -> зелёный CI -> checkout/pull/merge -> карта/RETRO -> push ->
    done.

    Возврат — сигнал вызывающему циклу (`_cmd_approve_merge_gate_cycle`):
    `"stopped"` — окно завершилось без merge (эскалация, красная главная
    копия, подтверждённо красный/неизвестный CI на пути `"fresh"` —
    прежнее поведение AC-11 байт-в-байт, дальше вызывающему циклу делать
    нечего); `"done"` — merge выполнен; `("wait", branch)` — свежая
    подтяжка пушнута в origin (требование 1), дальше вызывающий цикл ждёт
    CI ВНЕ этого мьютекса (требование 2).

    `confirmed_ci_note` — статус, уже подтверждённый зелёным циклом
    ожидания предыдущего захода (требование 5): потребляется РОВНО когда
    подтяжка на этом заходе снова вернула `"fresh"` (тот же head, статус
    всё ещё актуален) — повторный `ci.branch_status` не зовётся. Новый
    уход main вперёд (`"pulled"`, требование 6/AC-6) делает кэш
    неактуальным для НОВОГО head — параметр просто отбрасывается, ветка
    `"pulled"` ниже его не читает.
    """
    branch = t["branch"]
    # Рабочая поверхность оркестратора (SPEC T045, требования 3-4,
    # AC-8 сценарий 2): merge — территория главной копии пульта на
    # main, не чужой ветки Оператора/сессии. Проверяется ДО двухшаговой
    # sha-сверки `confirm_fixation` выше (та уже пройдена к этой
    # точке) — отказ здесь не имеет права сам переключать главную
    # копию, только останавливать команду; не `sys.exit` (в отличие от
    # красного CI/провала git ниже — там инфраструктурный отказ, а не
    # рутинная сверка поверхности): задача остаётся на гейте
    # merge_gate, чтобы Оператор мог повторить approve тем же
    # процессом после перехода на main. Пустая строка — git не ответил
    # (вырожденный случай песочниц без реального git, тот же приём
    # деградации, что у `gitcmd.on_foreign_branch`) — сверять не с чем,
    # пропускается.
    root_branch = gitcmd.current_branch()
    if root_branch and root_branch != config.MAIN_BRANCH:
        detail = (f"главная копия пульта стоит на {root_branch}, не "
                  f"на {config.MAIN_BRANCH} — merge не выполняется; "
                  f"перейди на {config.MAIN_BRANCH} и повтори "
                  f"artel.py approve {task_id}")
        store.journal(conn, task_id, "fsm",
                      "approve отклонён: главная копия не на main",
                      detail)
        print(f"[{task_id}] approve отклонён: {detail}")
        return ("stopped",)
    # Сверка свежести ветки ПОД МЬЮТЕКСОМ, до сверки CI (SPEC T053,
    # требования 5-8): main мог уйти вперёд, пока задача стояла на гейте
    # или ждала освобождения чужого merge-окна — дыра №2 из «Контекста»
    # SPEC. Подтяжка сдвигает head ветки задачи, зафиксированный снимок
    # инвалидируется — merge в main в ЭТОМ ЖЕ вызове не выполняется
    # (инвариант 19 не ослабляется), задача остаётся на гейте.
    pull_outcome = fsm._pull_main_or_escalate(conn, task_id, t, state)
    if pull_outcome == "escalated":
        return ("stopped",)
    if pull_outcome == "pulled":
        # Push нового head в origin ДО начала цикла ожидания CI (SPEC
        # T087, требование 1) — из главной копии пульта, не `wt_path`:
        # ref ветки задачи общий для всех worktree одного репозитория
        # (тот же приём, что уже использует `github_adapter.
        # ensure_draft_mr`). Внутри окна мьютекса, до его освобождения
        # (требование 2) — `_cmd_approve_merge_gate_cycle` отпускает
        # мьютекс сразу после возврата этой функции.
        new_head = gitcmd.branch_head_sha(branch)
        push = gitcmd.git("push", "-u", "origin", branch)
        if push is None or push.returncode != 0:
            detail = (push.stderr.strip()[:500] if push is not None
                      else "git не ответил")
            store.journal(conn, task_id, "orchestrator",
                          "push FAILED (подтяжка merge_gate)", detail)
            sys.exit(f"[{task_id}] push ветки {branch} упал: {detail}\n"
                     f"  задача осталась на гейте merge_gate; почини "
                     f"доступ к origin и повтори: artel.py approve "
                     f"{task_id}")
        print(f"[{task_id}] ветка подтянута к {config.MAIN_BRANCH} и "
              f"запушена (head {new_head}) — жду зелёного CI")
        return ("wait", branch)
    # pull_outcome == "fresh": прежнее поведение байт-в-байт (SPEC T087,
    # требование 11/AC-11) — единственная проверка CI, без цикла ожидания.
    # Зелёный CI — условие мержа, проверяемое кодом, а не глазами
    # Оператора (SPEC T017, требование 6). Неизвестный статус — это
    # «нельзя»: иначе сломанный или неавторизованный `gh` бесшумно
    # возвращал бы систему к «смержим, посмотрим потом».
    if confirmed_ci_note is not None:
        # Цикл ожидания предыдущего захода уже подтвердил зелёный статус
        # ЭТОГО ЖЕ head (свежесть выше вернула "fresh" — head не сдвинулся)
        # — повторный `ci.branch_status` был бы лишним чтением того же
        # самого факта (SPEC T087, требование 5).
        note = confirmed_ci_note
    else:
        green, note = ci.branch_status(branch)
        store.journal(conn, task_id, "orchestrator", "статус CI ветки", note)
        if not green:
            # Ре-ран флейка (SPEC T082, требование 7, AC-14..17) — только
            # для ПОДТВЕРЖДЁННО красного статуса: «CI ещё идёт»/«статус
            # неизвестен» — это «ещё нет ответа», не «не прошли»,
            # ре-ран/flake-rate для них были бы ложью (прежнее поведение —
            # отказ без ре-рана: подожди ещё).
            if ci.status_kind(note) != "red":
                sys.exit(f"[{task_id}] merge отклонён: {note}\n"
                         f"  задача осталась на гейте merge; почини CI "
                         f"ветки {branch} и повтори: artel.py approve "
                         f"{task_id}")
            _, note = _ci_confirm_red_or_flake(conn, task_id, branch, note)
    print(f"[{task_id}] {note}")
    for cmd in (["git", "checkout", config.MAIN_BRANCH],
                ["git", "pull", "--ff-only"]):
        res = gitcmd.git(*cmd[1:])
        if res.returncode != 0:
            store.journal(conn, task_id, "orchestrator", "merge FAILED",
                          res.stderr.strip()[:500])
            sys.exit(f"merge упал на {' '.join(cmd)}:\n{res.stderr}")
    merge_res = gitcmd.git("merge", "--no-ff", branch, "-m",
                           f"{task_id}: merge {branch}")
    if merge_res.returncode != 0:
        _handle_merge_conflict(conn, task_id, state, branch, merge_res)
        return ("stopped",)
    # sha КОММИТА МЕРЖА — сразу после успешного merge, ДО любых
    # последующих служебных коммитов (карты, RETRO): адрес артефактов
    # RETRO (SPEC T043, требование 8) обязан указывать именно на этот
    # коммит, а не на более поздний, который сдвинул бы HEAD дальше.
    merge_sha = gitcmd.head_sha()
    # Карта кодовой базы (SPEC T042): после merge, до push; провал
    # шага карты не отменяет merge (требование 5) — push ниже
    # выполняется независимо от исхода `_regenerate_and_commit_map`.
    fsm_postmerge._regenerate_and_commit_map(conn, task_id)
    # Дайджест задачи в main (SPEC T043): после карты, до push, тем же
    # принципом некритичности — провал не отменяет переход.
    fsm_postmerge._generate_and_commit_retro(conn, task_id, merge_sha)
    push = gitcmd.git("push")
    if push.returncode != 0:
        store.journal(conn, task_id, "orchestrator", "merge FAILED",
                      push.stderr.strip()[:500])
        sys.exit(f"merge упал на git push:\n{push.stderr}")
    store.set_state(conn, task_id, "done", "orchestrator",
                    expected_state=state, detail=f"смержено: {branch}")
    # Снапшот закрытия (SPEC T094, требования 12-13, AC-13, AC-15) — ДО
    # уборки веток ниже, тем же узлом, что и `cleanup._cmd_kill` для
    # пути `killed`: внешний target, не канарейка (self/канарейка снапшот
    # не заводят вовсе — `_publish_snapshot_if_pending` сама решает).
    # Push снапшота не удался — `snapshot.pending` остаётся истинным, и
    # уборка worktree/ветки задачи ниже пропускается (AC-15: переход в
    # `done` уже совершён, ветки ждут следующего доверенного прогона).
    target = t["target"] or config.DEFAULT_TARGET
    is_canary = bool(t["is_canary"])
    cleanup._publish_snapshot_if_pending(conn, task_id, target, is_canary)
    if target != config.DEFAULT_TARGET and not is_canary:
        from . import snapshot
        if snapshot.pending(task_id):
            return ("done",)
    # Worktree задачи отслужил (SPEC T045, требование 5, AC-6):
    # смержено, дальше агентным шагам там делать нечего.
    note = workspace.remove(task_id)
    store.journal(conn, task_id, "orchestrator", "worktree убран", note)
    # Ветка задачи — следом за worktree (tasks/T073/SPEC.md, требование 2):
    # `-d` откажет, пока ветку держит worktree, поэтому порядок обязателен.
    branch_note = cleanup.drop_merged_task_branch(branch)
    store.journal(conn, task_id, "orchestrator", "ветка убрана", branch_note)
    return ("done",)


def _cmd_approve_merge_gate_cycle(conn, task_id: str, sid: str, t,
                                  state: str) -> None:
    """Внешний цикл гейта `merge_gate` (SPEC T087, требования 1-6, 10;
    решение Оператора 31.08, аудит v6 Q-5): чередует тело гейта
    (`_cmd_approve_merge_gate`, ПОД мьютексом merge-окна) и ожидание CI
    вне мьютекса (`_wait_for_branch_ci_green`) — один и тот же вызов
    `approve` доводит задачу до `done` сам, без нового ручного вызова
    Оператора.

    Мьютекс берётся/отпускается ЭТИМ циклом напрямую (`merge_lock.
    acquire`/`release`), не через `merge_lock.run_window`: тот держит
    мьютекс на весь вызов тела, а здесь между заходами в тело мьютекс
    обязан быть свободен (требование 2) — `finally` вокруг каждого захода
    снимает его безусловно, включая `sys.exit`/`KeyboardInterrupt`
    (требование 10), тем же принципом, что и `run_window`.

    `deadline`/`start` вычисляются ОДИН раз за весь вызов `approve` — в
    момент первого исхода `("wait", ...)`, то есть от первого пуша
    (требование 4): повторный уход в `("wait", ...)` после новой подтяжки
    (AC-6) не пересчитывает их.
    """
    start: float | None = None
    deadline: float | None = None
    confirmed_ci_note: str | None = None
    while True:
        refusal = merge_lock.acquire(conn, task_id, sid)
        if refusal is not None:
            sys.exit(refusal)
        try:
            outcome = _cmd_approve_merge_gate(conn, task_id, state, t,
                                              confirmed_ci_note)
        finally:
            merge_lock.release(conn, sid)
        confirmed_ci_note = None
        if outcome[0] != "wait":
            return
        branch = outcome[1]
        if deadline is None:
            start = time.monotonic()
            deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC
        confirmed_ci_note = _wait_for_branch_ci_green(conn, task_id, branch,
                                                       start, deadline)
