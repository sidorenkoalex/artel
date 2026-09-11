"""Тело и внешний цикл гейта `merge_gate` (SPEC T052, T053, T082, T087):
разбор конфликта merge, ре-ран флейка CI, ожидание CI ветки вне мьютекса,
собственно merge в main. Перенесено из orchestrator/fsm.py без изменения
поведения (T091, декомпозиция диспетчеров fsm/runner).

Stage0 (A7, ANSWER-1 вопрос 1, вариант B): `approve` из `merge_gate`
записывает merge-коммит в `refs/heads/<MAIN_BRANCH>` main артели
(её `origin`) плотницки — через временный detached scratch-worktree
(`_scratch_worktree`) и явный push конкретного sha, — не через `git
checkout`/`git merge`/`git push` рабочего дерева `config.ROOT`:
рабочее дерево и HEAD ROOT остаются на зафиксированном пином sha
непосредственно до и сразу после успешного `approve` (AC-8, AC-9,
AC-12). Единственный способ продвинуть ROOT вперёд — отдельная
операторская команда `pin-update` (`orchestrator/pin.py`, Stage1), вне
цикла FSM.
"""
import shutil
import sys
import tempfile
import time
from pathlib import Path

from scripts import guard

from . import (artifact_branch, ci, cleanup, config, fsm, fsm_postmerge,
              gitcmd, github_adapter, lease, merge_lock, repo_context, store,
              workspace)


def _touches_protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in config.PROTECTED_PATHS)


def _origin_main_sha(ctx: repo_context.RepoContext) -> str | None:
    """sha текущего HEAD `refs/heads/<ctx.base>` main target'а на её
    `origin` — `None`, git не ответил.

    `git fetch` пишет только в объектную базу и `FETCH_HEAD`/
    remote-tracking ref, никогда в локальный `refs/heads/<base>` —
    рабочее дерево и HEAD клона `ctx` не задеты (AC-8).

    `ctx` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 4, AC-12) —
    репозиторный контекст target'а задачи: для self — байт-в-байт
    прежнее поведение (`config.ROOT`, ветка `config.MAIN_BRANCH`); для
    внешнего target — клон `ctx.path`, ветка `ctx.base`, remote —
    литеральное имя `"origin"` (клон внешнего target несёт свой git
    remote `origin` по тому же соглашению, что и `config.ROOT` пульта,
    `orchestrator/repo_context.py` докстринг), не адрес форджа
    `ctx.remote`.
    """
    fetch = repo_context.git(ctx, "fetch", "-q", "origin", ctx.base)
    if fetch is None or fetch.returncode != 0:
        return None
    res = repo_context.git(ctx, "rev-parse", "FETCH_HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else None


def _scratch_worktree(ctx: repo_context.RepoContext,
                      sha: str) -> tuple[Path | None, str | None]:
    """Временный detached git-worktree на `sha`, ВНЕ рабочего дерева
    клона `ctx` (AC-8) — тот же приём, что `orchestrator/workspace.py`
    уже несёт для задач, здесь одноразовый и detached (main target'а —
    не ветка задачи, checkout по имени ветки уже занят самим `ctx.path`).
    `git worktree add` исполняется В `ctx.path` (SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-12): `sha` — объект её собственной
    объектной базы (только что зафетчен туда `_origin_main_sha`), не
    обязательно существующий в `config.ROOT`.
    (путь, None) — успех; (None, причина) — git не ответил.
    """
    scratch = Path(tempfile.mkdtemp(prefix="artel-merge-carpentry-"))
    res = repo_context.git(ctx, "worktree", "add", "--detach", str(scratch), sha)
    if res is None or res.returncode != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        reason = res.stderr.strip()[:300] if res is not None else "git не ответил"
        return None, reason
    return scratch, None


def _drop_scratch_worktree(repo: Path) -> None:
    gitcmd.git("worktree", "remove", "--force", str(repo))
    shutil.rmtree(repo, ignore_errors=True)


def _handle_merge_conflict(conn, task_id: str, state: str, branch: str,
                           merge_res, repo: Path) -> None:
    """Разбор провала `git merge --no-ff <branch>` при `approve` из
    `merge_gate` (SPEC T052, требования 2-3; AC-3, AC-4, AC-5) — merge
    идёт в scratch-worktree `repo` (Stage0, AC-8), не в `config.ROOT`.

    Отличает содержательный конфликт (git начал merge, но не смог
    разрешить его сам) от инфраструктурного отказа: список файлов с
    неразрешённым конфликтом (`git diff --name-only --diff-filter=U`)
    пуст или git не ответил — конфликта в СОДЕРЖИМОМ нет, отказ прежний
    (`sys.exit`, задача остаётся в `merge_gate`, требование 3/AC-5).

    Список не пуст — содержательный конфликт: `git merge --abort`
    возвращает scratch-дерево в чистое состояние (требование 5), а
    задача уходит в `in_dev` (AC-3) либо, если конфликт задевает
    защищённый путь (`config.PROTECTED_PATHS`), в `escalated` (AC-4) —
    оба перехода несут перечень конфликтующих файлов в журнал через
    `detail` `store.set_state`. Если сам `git merge --abort` не удался,
    scratch-дерево остаётся с незавершённым merge НАРОЧНО (для разбора
    Оператором) — переход состояния НЕ выполняется; `config.ROOT`
    (в отличие от прежнего чекаут-механизма) этим отказом не задет
    вовсе — инфраструктурный отказ той же природы, что и «git не
    ответил» выше — `sys.exit`, задача остаётся в `merge_gate`.
    """
    store.journal(conn, task_id, "orchestrator", "merge FAILED",
                  merge_res.stderr.strip()[:500] if merge_res is not None
                  else "git не ответил")
    conflicts = gitcmd.in_repo(repo, "diff", "--name-only", "--diff-filter=U")
    files = sorted(set(conflicts.stdout.split())) \
        if conflicts is not None and conflicts.returncode == 0 else []
    if not files:
        _drop_scratch_worktree(repo)
        sys.exit(f"merge упал на git merge --no-ff {branch}:\n"
                 f"{merge_res.stderr if merge_res is not None else '—'}")

    abort = gitcmd.in_repo(repo, "merge", "--abort")
    if abort is None or abort.returncode != 0:
        abort_err = abort.stderr.strip()[:500] if abort is not None else "git не ответил"
        store.journal(conn, task_id, "orchestrator", "merge --abort FAILED",
                      abort_err)
        sys.exit(f"[{task_id}] merge отклонён: конфликт в файлах "
                 f"{', '.join(files)}, но git merge --abort не смог "
                 f"вернуть scratch-дерево {repo} в чистое состояние "
                 f"({abort_err}); дерево оставлено для разбора Оператором "
                 f"(config.ROOT не задет); задача осталась в merge_gate")

    _drop_scratch_worktree(repo)
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


def _overlay_artifact_snapshot(conn, task_id: str, repo: Path) -> None:
    """Накладывает `tasks/<id>/` из ГОЛОВЫ артефактной ветки поверх
    результата обычного `git merge --no-ff branch` в `repo` (SPEC
    01M1R9YEK08XEQWBFX0929WFVJ, требование 3; AC-6/AC-7/AC-8/AC-11):
    содержимое `tasks/<id>/`, которое попадает в main, обязано быть
    снимком АРТЕФАКТНОЙ ветки на момент `approve`, не тем, что принесла
    легаси-копия кодовой ветки задачи (если она вообще есть — обычно её
    нет, `checkpoint.py` исключает `tasks/<id>/` из коммитов кодовой
    ветки всех ролей, кроме коммита в артефактную ветку).

    Материализация не удалась (`artifact_branch.materialize_task_dir`
    вернула пустую строку — ветка не читается) — журналируется
    предупреждение, main остаётся с тем, что уже принёс обычный merge
    (деградация, не отказ перехода: требование 3 не разрешает провалу
    materialize держать гейт). Наложение не поменяло НИ ОДНОГО файла
    (`git status --porcelain` пуст — легаси-копия и снимок уже
    совпадают, либо легаси не было и снимок пуст тоже) — коммитить
    нечего. Иначе — новый коммит поверх merge; если ДО наложения
    `tasks/<id>/` уже нёс файлы (легаси-копия кодовой ветки
    существовала), расхождение с ней журналируется отдельным
    предупреждением (AC-8) — переход не отказывает по этой причине.
    """
    legacy_dir = repo / "tasks" / task_id
    legacy_present = legacy_dir.is_dir() and any(
        p.is_file() for p in legacy_dir.rglob("*"))

    head = artifact_branch.materialize_task_dir(task_id, repo)
    if not head:
        store.journal(
            conn, task_id, "orchestrator",
            "снимок артефактной ветки не наложен",
            "материализация tasks/<id>/ из артефактной ветки не удалась "
            "— main понесёт содержимое обычного merge")
        return

    status = gitcmd.in_repo(repo, "status", "--porcelain", "--",
                            f"tasks/{task_id}")
    changed = bool(status.stdout.strip()) if (
        status is not None and status.returncode == 0) else False
    if not changed:
        return

    add = gitcmd.in_repo(repo, "add", "-A", "--", f"tasks/{task_id}")
    if add is None or add.returncode != 0:
        store.journal(
            conn, task_id, "orchestrator",
            "снимок артефактной ветки не наложен",
            add.stderr.strip()[:300] if add is not None else "git не ответил")
        return
    commit = gitcmd.in_repo(repo, "commit", "-m",
                            f"{task_id}: снимок артефактной ветки поверх merge")
    if commit is None or commit.returncode != 0:
        store.journal(
            conn, task_id, "orchestrator",
            "снимок артефактной ветки не наложен",
            commit.stderr.strip()[:300] if commit is not None
            else "git не ответил")
        return
    if legacy_present:
        store.journal(
            conn, task_id, "orchestrator",
            "расхождение легаси-копии tasks/<id>/ и снимка артефактной ветки",
            f"легаси-копия tasks/<id>/ кодовой ветки разошлась со снимком "
            f"артефактной ветки {head} — наложен снимок артефактной ветки "
            f"(main несёт его, не легаси-копию)")


def _guard_task_root_or_refuse(conn, task_id: str, scratch: Path) -> None:
    """Guard на `tasks/<id>/` СНИМКА артефактной ветки в scratch-дереве —
    ДО push в main (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0, AC-7/AC-8): вызывается
    ПОСЛЕ `_overlay_artifact_snapshot` (снимок артефактной ветки к этому
    моменту уже наложен на `tasks/<id>/` `scratch`, не легаси-копия
    кодовой ветки), ДО `_push_merged_main` — единственный способ поймать
    посторонний файл (инцидент 06.09), уже проникший в артефактную ветку
    В ОБХОД автокоммита (правка Оператора на гейте, старая ветка,
    отставшая от фильтра `checkpoint.py`).

    Критерий — тот же `scripts.guard`, что `checkpoint.py` уже применяет
    на автокоммите (единый источник истины, не независимая копия).
    Посторонний файл — отказ той же журнальной записью, что и прочие
    отказы `merge_gate` (`"merge FAILED"` — CI красный, конфликт merge,
    push FAILED): `sys.exit` именованной причиной, задача остаётся на
    `merge_gate` БЕЗ эскалации (`store.set_state` не вызывается), main не
    тронут — `_push_merged_main` этой веткой ещё не достигнут.
    """
    task_dir = scratch / "tasks" / task_id
    extraneous = guard.extraneous_task_root_files_in(task_dir)
    if not extraneous:
        return
    rel_names = [str(p.relative_to(scratch)) for p in extraneous]
    detail = (f"guard: {guard.EXTRANEOUS_TASK_ROOT_FILE_REASON} в снимке "
             f"артефактной ветки: {', '.join(rel_names)}")
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(scratch)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; почини нарушения и "
             f"повтори: artel.py approve {task_id}")


def _ensure_branch_head_published(conn, task_id: str, branch: str) -> str:
    """Голова ветки задачи видна в origin — предусловие КАЖДОГО approve
    merge_gate (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, требование 7,
    AC-8/AC-9), самой первой проверкой тела гейта: расхождение может
    появиться уже ПОСЛЕ входа на гейт (новый коммит на ветке задачи
    между заходами approve/цикла ожидания CI), не только на самом
    входе. Провал — graceful отказ, задача остаётся на merge_gate без
    эскалации; повторный approve после починки origin продолжает
    штатно (AC-9). AC-10 (ANSWER-1, вопрос 1): проверка «главная копия
    на main» убрана целиком — плотницкий merge (Stage0, ниже) не читает
    и не требует чекаута `config.ROOT` вовсе, эта проверка про ветку
    ЗАДАЧИ в origin, не про главную копию.

    `"ok"` — голова видна; `"refused"` — журнал/печать уже сделаны.
    """
    push_ok, push_detail = github_adapter.ensure_head_in_origin(
        conn, task_id, branch)
    if not push_ok:
        store.journal(conn, task_id, "orchestrator",
                      "approve отклонён: голова не в origin", push_detail)
        print(f"[{task_id}] approve отклонён: {push_detail}")
        return "refused"
    return "ok"


def _sync_main_or_wait(conn, task_id: str, t, state: str, branch: str,
                       ctx: repo_context.RepoContext):
    """Подтяжка main и проверка свежести ветки ПОД МЬЮТЕКСОМ, до сверки
    CI (SPEC T053, требования 5-8): main мог уйти вперёд, пока задача
    стояла на гейте или ждала освобождения чужого merge-окна — дыра №2
    из «Контекста» SPEC. Подтяжка сдвигает head ветки задачи,
    зафиксированный снимок инвалидируется — merge в main в ЭТОМ ЖЕ
    вызове не выполняется (инвариант 19 не ослабляется), задача
    остаётся на гейте.

    `"fresh"` — голова не сдвинулась, можно проверять CI дальше;
    `("stopped",)` — эскалация/отказ подтяжки; `("wait", branch)` —
    свежая подтяжка уже пушнута в origin (push нового head ДО начала
    цикла ожидания CI, SPEC T087 требование 1), дальше вызывающий цикл
    ждёт CI вне этого мьютекса.
    """
    pull_outcome = fsm._pull_main_or_escalate(conn, task_id, t, state)
    if pull_outcome in ("escalated", "refused"):
        return ("stopped",)
    if pull_outcome == "pulled":
        # Push нового head в origin клона контекста target'а (SPEC
        # 01M1R5B33CC7E6BZK085XV3ZCX, AC-6): для self — из главной копии
        # пульта, не `wt_path` (ref ветки задачи общий для всех worktree
        # одного репозитория, тот же приём, что уже использует
        # `github_adapter.ensure_draft_mr`); для внешнего target — её
        # клон, где подтяжка (`fsm._pull_main_or_escalate`) только что
        # реально смержила голову. Внутри окна мьютекса, до его
        # освобождения (требование 2) — `_cmd_approve_merge_gate_cycle`
        # отпускает мьютекс сразу после возврата тела.
        repo = repo_context.path_or_none(ctx)
        new_head = gitcmd.branch_head_sha(branch, repo=repo)
        push = repo_context.git(ctx, "push", "-u", "origin", branch)
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
    # pull_outcome == "fresh": голова ветки не сдвинулась.
    return "fresh"


def _ci_ready_or_wait(task_id: str, confirmed_ci_note: str | None,
                      branch: str):
    """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ (AC-5..AC-7): «нет проверок ещё»
    типично сразу после первой публикации головы — раньше этот путь
    опрашивал `ci.branch_status` РОВНО один раз и отказывал немедленно
    на любом не-зелёном ответе; теперь, как и путь "pulled", он ждёт
    циклом `_wait_for_branch_ci_green` вне мьютекса — голова уже в
    origin (push здесь не нужен, в отличие от "pulled"). Зелёный CI —
    условие мержа, проверяемое кодом, а не глазами Оператора (SPEC
    T017, требование 6); цикл ожидания сам не считает неизвестный
    статус зелёным.

    `confirmed_ci_note` — статус, уже подтверждённый зелёным циклом
    ожидания предыдущего захода (SPEC T087, требование 5): читается
    РОВНО когда подтяжка на этом заходе снова вернула "fresh" (тот же
    head, статус всё ещё актуален) — повторный `ci.branch_status` не
    зовётся.

    `("wait", branch)` — статус ещё не подтверждён этим вызовом;
    `"ok"` — подтверждён, `note` уже напечатан.
    """
    if confirmed_ci_note is None:
        return ("wait", branch)
    print(f"[{task_id}] {confirmed_ci_note}")
    return "ok"


def _perform_carpentry_merge(conn, task_id: str, state: str, branch: str,
                             ctx: repo_context.RepoContext):
    """Плотницкий merge (Stage0, ANSWER-1 вопрос 1, вариант B; AC-8):
    текущий sha main target'а (её origin) БЕЗ прикосновения к локальному
    `refs/heads/<ctx.base>` (`_origin_main_sha` только фетчит), затем
    `git merge --no-ff` В SCRATCH-WORKTREE клона `ctx`, не в
    `config.ROOT` (для self — тот же `config.ROOT`, что и до этой
    задачи; для внешнего target — `ctx.path`, SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-12).

    `("ok", scratch)` — merge выполнен, scratch-дерево готово к
    публикации артефактов; `("stopped", None)` — конфликт разобран
    `_handle_merge_conflict` (защищённый путь -> escalated, иначе ->
    in_dev), scratch-дерево уже убрано.
    """
    origin_sha = _origin_main_sha(ctx)
    if origin_sha is None:
        sys.exit(f"[{task_id}] merge отклонён: git fetch origin "
                 f"{ctx.base} не ответил\n"
                 f"  задача осталась на гейте merge; почини доступ к "
                 f"origin и повтори: artel.py approve {task_id}")
    scratch, scratch_error = _scratch_worktree(ctx, origin_sha)
    if scratch is None:
        store.journal(conn, task_id, "orchestrator", "merge FAILED",
                      scratch_error)
        sys.exit(f"merge упал на подготовке scratch-дерева: {scratch_error}")

    merge_res = gitcmd.in_repo(scratch, "merge", "--no-ff", branch, "-m",
                               f"{task_id}: merge {branch}")
    if merge_res is None or merge_res.returncode != 0:
        _handle_merge_conflict(conn, task_id, state, branch, merge_res, scratch)
        return ("stopped", None)
    return ("ok", scratch)


def _publish_merge_artifacts(conn, task_id: str, scratch: Path,
                             is_self: bool) -> str:
    """Снимок артефактной ветки поверх обычного merge (SPEC
    01M1R9YEK08XEQWBFX0929WFVJ, требование 3; AC-6/AC-7/AC-8/AC-11) —
    ДО sha "коммита мержа" ниже: main обязан унести АРТЕФАКТНЫЙ снимок
    tasks/<id>/, значит это часть содержимого, на которое указывает
    `merge_sha`, а не служебная правка вроде карты/RETRO после него.

    Карта кодовой базы (SPEC T042) и RETRO (SPEC T043, требование 8,
    адресуется на `merge_sha` — сразу после merge/наложения снимка, ДО
    любых последующих служебных коммитов) — оба шага ТОЛЬКО для self
    (`is_self`): SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 4, AC-13 —
    «в пульте — только кухня пульта», для внешнего target ни карта, ни
    RETRO в её main НЕ коммитятся вовсе (RETRO внешнего target остаётся
    только в снапшоте закрытия, `orchestrator/snapshot.py`). Для self —
    оба провала некритичны, push ниже выполняется независимо от их
    исхода; оба шага работают В SCRATCH (AC-9) — не в `config.ROOT`.

    `_guard_task_root_or_refuse` (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
    AC-7/AC-8) — сразу после наложения снимка, ДО карты/RETRO/push:
    посторонний файл `tasks/<id>/` отказывает переходу `sys.exit`'ом,
    дальше этой функции выполнение не идёт.

    Возврат — `final_sha` (после карты/RETRO для self) для push явным sha.
    """
    _overlay_artifact_snapshot(conn, task_id, scratch)
    _guard_task_root_or_refuse(conn, task_id, scratch)
    merge_sha = gitcmd.head_sha(scratch)
    if is_self:
        fsm_postmerge._regenerate_and_commit_map(conn, task_id, repo=scratch)
        fsm_postmerge._generate_and_commit_retro(conn, task_id, merge_sha,
                                                 repo=scratch)
    final_sha = gitcmd.head_sha(scratch)
    _drop_scratch_worktree(scratch)
    return final_sha


def _push_merged_main(conn, task_id: str, final_sha: str,
                      ctx: repo_context.RepoContext) -> str:
    """Push ЯВНОГО sha (не текущего чекаута) прямо в `refs/heads/
    <ctx.base>` origin клона `ctx`, чья объектная база уже несёт коммиты
    scratch-worktree (общий `.git`), но чей собственный чекаут/HEAD этот
    push не трогает вовсе (AC-8). Для self — байт-в-байт прежнее
    поведение (`config.ROOT`, `refs/heads/config.MAIN_BRANCH`); для
    внешнего target — её клон и `refs/heads/<ctx.base>` (SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-12)."""
    push = repo_context.git(ctx, "push", "origin",
                            f"{final_sha}:refs/heads/{ctx.base}")
    if push is None or push.returncode != 0:
        store.journal(conn, task_id, "orchestrator", "merge FAILED",
                      push.stderr.strip()[:500] if push is not None
                      else "git не ответил")
        sys.exit(f"merge упал на git push:\n"
                 f"{push.stderr if push is not None else '—'}")
    return "ok"


def _finalize_done_state(conn, task_id: str, state: str, branch: str) -> None:
    """`state -> done`, затем безусловное снятие lease «любым путём»
    (SPEC 01M1G..., требование 3, AC-6) — этот путь раньше lease не
    трогал вовсе."""
    store.set_state(conn, task_id, "done", "orchestrator",
                    expected_state=state, detail=f"смержено: {branch}")
    lease.release_any(conn, task_id, "orchestrator", "lease снят: задача done")


def _publish_closing_snapshot_or_wait(conn, task_id: str, t) -> str:
    """Снапшот закрытия (SPEC T094, требования 12-13, AC-13, AC-15) — ДО
    уборки веток ниже, тем же узлом, что и `cleanup._cmd_kill` для пути
    `killed`: внешний target, не канарейка (self/канарейка снапшот не
    заводят вовсе — `_publish_snapshot_if_pending` сама решает). Push
    снапшота не удался — `snapshot.pending` остаётся истинным, и уборка
    worktree/ветки задачи пропускается (AC-15: переход в `done` уже
    совершён, ветки ждут следующего доверенного прогона).

    `"done"` — уборку нужно отложить; `"ok"` — можно убирать worktree/
    ветку сейчас.
    """
    target = t["target"] or config.DEFAULT_TARGET
    is_canary = bool(t["is_canary"])
    cleanup._publish_snapshot_if_pending(conn, task_id, target, is_canary)
    if target != config.DEFAULT_TARGET and not is_canary:
        from . import snapshot
        if snapshot.pending(task_id):
            return "done"
    return "ok"


def _cleanup_merged_task(conn, task_id: str, branch: str) -> None:
    """Worktree задачи отслужил (SPEC T045, требование 5, AC-6):
    смержено, дальше агентным шагам там делать нечего. Ветка задачи —
    следом за worktree (tasks/T073/SPEC.md, требование 2): `-d` откажет,
    пока ветку держит worktree, поэтому порядок обязателен."""
    note = workspace.remove(task_id)
    store.journal(conn, task_id, "orchestrator", "worktree убран", note)
    branch_note = cleanup.drop_merged_task_branch(branch)
    store.journal(conn, task_id, "orchestrator", "ветка убрана", branch_note)


def _cmd_approve_merge_gate(conn, task_id: str, state: str, t,
                            confirmed_ci_note: str | None = None) -> tuple:
    """Тело окна `merge_gate -> done`, исполняемое ПОД МЬЮТЕКСОМ merge
    (SPEC T053, требование 1; SPEC T087, требования 1-2, 5-6): короткая
    композиция шагов — публикация головы -> свежесть main -> зелёный CI
    -> плотницкий merge в scratch-worktree (Stage0, AC-8) -> снимок
    артефактов/карта/RETRO -> push явным sha -> done -> снапшот закрытия
    -> уборка worktree/ветки.

    Возврат — сигнал вызывающему циклу (`_cmd_approve_merge_gate_cycle`):
    `("stopped",)` — окно завершилось без merge (отказ, эскалация,
    конфликт — дальше вызывающему циклу делать нечего); `("done",)` —
    merge выполнен; `("wait", branch)` — дальше вызывающий цикл ждёт CI
    ВНЕ этого мьютекса циклом `_wait_for_branch_ci_green` (требование 2).

    Репозиторный контекст target'а (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    требование 4, AC-12/AC-13): резолвится ОДИН раз здесь (`store.
    task_target`, не `t["target"]` — `t` в некоторых существующих тестах
    несёт только `branch`) и передаётся дальше каждому шагу, который
    решает, где физически стоит scratch-worktree/куда идёт push и нужны
    ли карта/RETRO (только self, AC-13). Контекст не читается
    (targets.yaml сломан/неизвестный target) — `sys.exit` тем же стилем,
    что и остальные инфраструктурные отказы этого гейта: merge — точка
    без права молча деградировать на чужой репозиторий.
    """
    ctx = repo_context.resolve(store.task_target(conn, task_id))
    if ctx is None:
        sys.exit(f"[{task_id}] merge отклонён: репозиторный контекст "
                 f"target'а не читается (targets.yaml)\n"
                 f"  задача осталась на гейте merge; почини targets.yaml "
                 f"и повтори: artel.py approve {task_id}")
    branch = t["branch"]
    if _ensure_branch_head_published(conn, task_id, branch) != "ok":
        return ("stopped",)
    sync_outcome = _sync_main_or_wait(conn, task_id, t, state, branch, ctx)
    if sync_outcome != "fresh":
        return sync_outcome
    ci_outcome = _ci_ready_or_wait(task_id, confirmed_ci_note, branch)
    if ci_outcome != "ok":
        return ci_outcome
    merge_kind, scratch = _perform_carpentry_merge(conn, task_id, state,
                                                    branch, ctx)
    if merge_kind != "ok":
        return ("stopped",)
    final_sha = _publish_merge_artifacts(conn, task_id, scratch,
                                         ctx.path == config.ROOT)
    _push_merged_main(conn, task_id, final_sha, ctx)
    _finalize_done_state(conn, task_id, state, branch)
    if _publish_closing_snapshot_or_wait(conn, task_id, t) == "done":
        return ("done",)
    _cleanup_merged_task(conn, task_id, branch)
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
