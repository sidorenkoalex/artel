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

from . import (acceptance, artifact_branch, artifact_source, ci, cleanup,
              config, fsm, fsm_postmerge, gitcmd, github_adapter, lease,
              merge_lock, merge_queue, repo_context, store, workspace)
from .advance_gates.plan_appendix import git_apply


def _touches_protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in config.PROTECTED_PATHS)


def _protected_path_refusal_detail(paths: list[str]) -> str:
    """Именованный текст отказа (SPEC 01M27JPEGCGMDDRX5A98QWJW0Z, требование
    4/AC-4) — дословно общий с `fsm_advance._protected_path_refusal_detail`
    (тот же текст на гейте зон и на гейте мержа)."""
    return (f"защищённый путь {', '.join(paths)} — правит только "
           f"Оператор коммитом в main; предложи правку приложением к "
           f"PLAN (unified-дифф)")


def _protected_path_diff_gate(conn, task_id: str, state: str, branch: str,
                              ctx: repo_context.RepoContext) -> bool:
    """Эскалация по защищённому пути в диффе ветки задачи против базы
    сравнения (SPEC 01M27JPEGCGMDDRX5A98QWJW0Z, требование 3, AC-5) — ДО
    попытки `git merge --no-ff`, независимо от того, конфликтует ли она
    содержательно: сегодняшняя эскалация `_handle_merge_conflict` видит
    защищённый путь ТОЛЬКО когда сам merge конфликтует, а бесконфликтный
    дифф (новый файл, не тронутый на main) доходил до `done` молча.

    Self target ТОЛЬКО (`ctx.path == config.ROOT`, тот же довод, что
    карта/RETRO в `_publish_merge_artifacts`): защищённые пути этого
    списка — файлы пульта, у внешнего target'а их либо нет вовсе, либо
    это не те же файлы её репозитория.

    `True` — эскалировано (`store.set_state` уже отжурналировал именованный
    текст AC-4), вызывающий код обязан остановиться; `False` — дифф чист
    либо git не ответил на определение базы/списка файлов. Git не
    ответивший здесь НЕ останавливает процесс `sys.exit`'ом (в отличие
    от инфраструктурных отказов остальных узлов этого гейта): `state` к
    этому моменту ещё не тронут, а сломанный git тем же вызовом всё
    равно упрётся в `sys.exit` чуть ниже (`_ensure_branch_head_published`/
    `_perform_carpentry_merge` сами требуют рабочий git) — расширять
    список мест отказа тем же git-failure не добавляет защиты.
    """
    if ctx.path != config.ROOT:
        return False
    base = gitcmd.diff_base(branch)
    if base is None:
        return False
    files = gitcmd.diff_names(base, branch)
    if files is None:
        return False
    protected = [f for f in files if _touches_protected_path(f)]
    if not protected:
        return False
    detail = _protected_path_refusal_detail(protected)
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=state, detail=detail)
    return True


def _origin_main_sha(ctx: repo_context.RepoContext) -> str | None:
    """sha текущего HEAD `refs/heads/<ctx.base>` main target'а на её
    `origin` — `None`, git не ответил.

    Фетч и чтение результата идут через `gitcmd.fetch_ref_sha` (SPEC
    01M2ARQGY51B99YNP9PY806AN1) — временную приватную ссылку `refs/artel/
    fetch/<pid>-<uuid>`, БЕЗ обращения к общему `FETCH_HEAD` (до этой
    задачи здесь стоял голый `git fetch` + `rev-parse FETCH_HEAD` —
    общий на репозиторий файл, который параллельный шаг ДРУГОЙ задачи в
    том же репозитории (например, `config.ROOT` при self-`ctx`) мог
    переписать между двумя этими вызовами, инцидент 12.09 07:15Z,
    канарейка 01M2A22CG2). `git fetch` пишет только в объектную базу и
    саму приватную ссылку (удаляемую сразу после чтения), никогда в
    локальный `refs/heads/<base>` — рабочее дерево и HEAD клона `ctx` не
    задеты (AC-8).

    `ctx` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 4, AC-12) —
    репозиторный контекст target'а задачи: для self — байт-в-байт
    прежнее поведение (`config.ROOT`, ветка `config.MAIN_BRANCH`); для
    внешнего target — клон `ctx.path`, ветка `ctx.base`, remote —
    литеральное имя `"origin"` (клон внешнего target несёт свой git
    remote `origin` по тому же соглашению, что и `config.ROOT` пульта,
    `orchestrator/repo_context.py` докстринг), не адрес форджа
    `ctx.remote`.
    """
    sha, _ = gitcmd.fetch_ref_sha("origin", ctx.base,
                                  repo=repo_context.path_or_none(ctx))
    return sha or None


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


def _drop_scratch_worktree(ctx: repo_context.RepoContext, repo: Path) -> None:
    """Дерегистрация scratch-worktree ИМЕННО там, где `_scratch_worktree`
    его завёл (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, R1-F1): `git worktree
    remove` — административная команда репозитория-ВЛАДЕЛЬЦА worktree
    (`ctx.path/.git/worktrees/<name>/`), не голая `gitcmd.git` (та всегда
    бьёт в `config.ROOT`) — для внешнего target это чужой репозиторий,
    команда отказала бы `fatal: '<path>' is not a working tree` (код 128)
    и оставляла бы висящую запись `.git/worktrees/` в клоне target'а на
    каждом approve. `repo_context.git(ctx, ...)` для self — байт-в-байт
    прежний вызов (`gitcmd.git`, `cwd=config.ROOT`)."""
    repo_context.git(ctx, "worktree", "remove", "--force", str(repo))
    shutil.rmtree(repo, ignore_errors=True)


def _handle_merge_conflict(conn, task_id: str, state: str, branch: str,
                           merge_res, repo: Path,
                           ctx: repo_context.RepoContext) -> None:
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
        _drop_scratch_worktree(ctx, repo)
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

    _drop_scratch_worktree(ctx, repo)
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
    """Цикл ожидания CI пушнутого head ВНУТРИ мьютекса merge-окна (SPEC
    T087, требования 2-4, 7-9, решение Оператора 31.08, аудит v6 Q-5;
    SPEC 01M291EJMA995AZ61MEMDZKWRY, требования 1, 3: с этой задачи
    мьютекс на время ожидания уже не свободен — держит его вызывающий
    цикл `_cmd_approve_merge_gate_cycle`, здесь только продлевается его
    heartbeat).

    Каждая итерация опрашивает `ci.branch_status`, продлевает heartbeat
    держателя мьютекса (`merge_lock.touch_heartbeat`, требование 3,
    AC-2 — иначе долгое ожидание протухло бы раньше времени и подставило
    живого держателя под перехват `_holder_is_dead`) и журналирует/
    печатает статус и прошедшее с `start` (момент первого пуша ЭТОГО
    вызова `approve`) время (требование 9). «CI ещё идёт»/«статус
    неизвестен» паузит `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)`
    и продолжает цикл (требование 3), пока не истёк общий потолок
    `deadline` (требование 4, `time.monotonic()` — тот же приём часов,
    что уже применяет `orchestrator/pause.py`) — тогда `sys.exit`
    «статус CI неизвестен» (требование 8). Подтверждённо красный статус
    — `_ci_confirm_red_or_flake` (требование 7, тот же узел, что и
    однократная проверка): флейк возвращает зелёный исход, подтверждённый
    красный сам завершает процесс `sys.exit`'ом (требование 7).

    Возврат — `note` зелёного статуса (требование 5: вызывающий код
    передаёт его следующему заходу в тело гейта, чтобы не спрашивать CI
    повторно для того же самого head).
    """
    while True:
        green, note = ci.branch_status(branch)
        merge_lock.touch_heartbeat(conn)
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


def _guard_task_root_or_refuse(conn, task_id: str, scratch: Path,
                               ctx: repo_context.RepoContext) -> None:
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
    _drop_scratch_worktree(ctx, scratch)
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
        _handle_merge_conflict(conn, task_id, state, branch, merge_res,
                               scratch, ctx)
        return ("stopped", None)
    return ("ok", scratch)


# Классы защищённых путей, чья правка приложением обязана пройти ПОЛНЫЙ
# набор тестов в scratch-дереве до push (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF,
# требование 5): приложение к `tests/` правит сам набор, приложение к
# `.github/` — правила его прогона, и ни то ни другое CI main уже не
# поймает — оно и есть то, чем CI main проверяет. Остальные защищённые
# пути (skills, templates, docs/adr, docs/invariants.md, конфигурация) на
# зелёность тестов не влияют — их проверит CI main.
_FULL_SUITE_APPENDIX_PREFIXES = ("tests/", ".github/")


def _appendix_needs_full_suite(paths: list[str]) -> bool:
    return any(p.startswith(prefix) for p in paths
               for prefix in _FULL_SUITE_APPENDIX_PREFIXES)


def _plan_appendices_or_refuse(conn, task_id: str, scratch: Path,
                               ctx: repo_context.RepoContext) -> list:
    """Приложения PLAN.md задачи с ветки-источника артефактов (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, требование 3). Ошибки разбора требования
    1 — отказ мержа `sys.exit`'ом (задача остаётся на `merge_gate`),
    возврата из функции в этом случае нет вовсе.

    Гейт применимости на выходе `in_dev` такие ошибки уже не пропустил
    бы — значит PLAN.md правили ПОСЛЕ него, на самом гейте, и разбирается
    это руками Оператора, а не возвратом задачи разработчику.

    PLAN.md, не прочитанный с ветки (git не ответил, ветки нет), —
    журналируемое предупреждение и «приложений нет», а не отказ мержа:
    тем же принципом деградации, что `_overlay_artifact_snapshot` уже
    применяет к провалу материализации снимка. Ничего некорректного в
    main это не пропускает — не применяется ничего."""
    branch, _foreign = artifact_source.resolve(conn, task_id)
    text, reason = gitcmd.show(branch, f"tasks/{task_id}/PLAN.md")
    if text is None:
        store.journal(conn, task_id, "orchestrator",
                      "приложения PLAN не прочитаны",
                      f"PLAN.md не читается с ветки {branch}: {reason} — "
                      f"приложения не применяются")
        return []
    appendices, errors = guard.plan_appendices(text)
    if errors:
        detail = f"приложения PLAN не разобраны: {'; '.join(errors)}"
        store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
        _drop_scratch_worktree(ctx, scratch)
        sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
                 f"  задача осталась на гейте merge; почини раздел "
                 f"«## Приложение» в PLAN.md и повтори: artel.py approve "
                 f"{task_id}")
    return appendices


def _return_inapplicable_appendix(conn, task_id: str, state: str,
                                  appendix, answer: str, scratch: Path,
                                  ctx: repo_context.RepoContext) -> None:
    """Приложение, применимое к базе сравнения на выходе `in_dev`, но не к
    подтянутому main (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF, требование 4/AC-9):
    main сдвинулся, пока задача шла по конвейеру.

    НЕ `sys.exit` (в отличие от инфраструктурных отказов этого гейта):
    чинит дифф приложения сама роль, в своём PLAN.md, — тем же путём и
    тем же `store.set_state`, что возврат по содержательному конфликту
    merge (`_handle_merge_conflict`), включая Draft-MR. Scratch-дерево
    убирается до перехода: половина применённых хунков в нём никому не
    нужна."""
    _drop_scratch_worktree(ctx, scratch)
    detail = (f"приложение PLAN неприменимо после подтяжки: "
              f"{', '.join(appendix.paths)} — {answer}")
    store.set_state(conn, task_id, "in_dev", "fsm",
                    expected_state=state, detail=detail)
    fsm._maybe_ensure_draft_mr(conn, task_id)


def _commit_applied_appendices(conn, task_id: str, paths: list[str],
                               scratch: Path,
                               ctx: repo_context.RepoContext) -> str:
    """Один коммит на все применённые приложения (требование 3/AC-8):
    «<id>: приложения Оператора — <пути>». Возврат — sha коммита; git
    отказал — отказ мержа `sys.exit`'ом (инфраструктурный сбой того же
    класса, что и прочие отказы этого гейта), и выполнение сюда не
    возвращается."""
    add = gitcmd.in_repo(scratch, "add", "--", *paths)
    commit = (gitcmd.in_repo(
        scratch, "commit", "-m",
        f"{task_id}: приложения Оператора — {', '.join(paths)}")
        if add is not None and add.returncode == 0 else None)
    if commit is not None and commit.returncode == 0:
        return gitcmd.head_sha(scratch)
    failed = commit if commit is not None else add
    reason = (failed.stderr.strip()[:300] if failed is not None
              else "git не ответил")
    detail = f"коммит приложений PLAN не удался: {reason}"
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(ctx, scratch)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; повтори: artel.py approve "
             f"{task_id}")


def _full_suite_or_refuse(conn, task_id: str, paths: list[str], scratch: Path,
                          ctx: repo_context.RepoContext) -> None:
    """Полный набор тестов в scratch-дереве, где приложения УЖЕ применены
    (требование 5/AC-10/AC-11) — только для путей
    `_FULL_SUITE_APPENDIX_PREFIXES`. Красный прогон — именованный отказ
    мержа: задача остаётся на `merge_gate`, scratch убран, main не
    продвинут, приложения не опубликованы."""
    if not _appendix_needs_full_suite(paths):
        return
    green, tail = acceptance.run_full_suite(scratch)
    if green:
        store.journal(conn, task_id, "orchestrator",
                      "полный прогон после приложений", tail)
        return
    detail = f"приложения ломают тесты: {tail}"
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(ctx, scratch)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; почини приложение к "
             f"{', '.join(paths)} и повтори: artel.py approve {task_id}")


def _apply_plan_appendices(conn, task_id: str, state: str, scratch: Path,
                           ctx: repo_context.RepoContext):
    """Приложения PLAN к защищённым путям — применение пультом (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, требования 3-6): ПОСЛЕ плотницкого merge и
    ДО снимка артефактов, то есть коммит приложений ложится в main раньше
    коммита снимка (AC-8) и входит в содержимое, на которое адресуется
    RETRO.

    До этой задачи защищённый путь в main мог попасть только ручным
    коммитом Оператора; после включения хуков защиты main
    (01M2XMCC83) этот путь закрылся, и приложение 01M2XJKKPH к
    `skills/test-authoring.md` применить стало некому — дыра, которую
    закрывает эта функция.

    Только self-target (`ctx.path == config.ROOT`), тем же доводом, что
    карта и RETRO ниже: `config.PROTECTED_PATHS` — файлы пульта, у
    внешнего target'а их либо нет вовсе, либо это не те же файлы.

    `("ok", пути)` — применять было нечего либо всё применено и
    закоммичено; `("stopped", [])` — приложение неприменимо к подтянутому
    main, задача возвращена в `in_dev` (требование 4)."""
    if ctx.path != config.ROOT:
        return ("ok", [])
    appendices = _plan_appendices_or_refuse(conn, task_id, scratch, ctx)
    if not appendices:
        return ("ok", [])

    # Пути КАЖДОГО заголовка `diff --git` каждого приложения (R1-F1):
    # многофайловый блок git применяет целиком, и `git add` ниже обязан
    # унести в коммит все его файлы, иначе правка Оператора уезжает в
    # никуда вместе со scratch-деревом.
    paths: list[str] = []
    for appendix in appendices:
        answer = git_apply(scratch, appendix)
        if answer:
            _return_inapplicable_appendix(conn, task_id, state, appendix,
                                          answer, scratch, ctx)
            return ("stopped", [])
        paths.extend(p for p in appendix.paths if p not in paths)

    sha = _commit_applied_appendices(conn, task_id, paths, scratch, ctx)
    # Прогон — после коммита и ДО записи «применены»/push: красный исход
    # означает, что приложения не поедут в main вовсе, и объявлять их
    # применёнными раньше его нечестно.
    _full_suite_or_refuse(conn, task_id, paths, scratch, ctx)
    store.journal(conn, task_id, "orchestrator",
                  f"приложения применены: {', '.join(paths)}",
                  f"коммит {sha} в scratch-дереве мержа")
    return ("ok", paths)


def _publish_merge_artifacts(conn, task_id: str, scratch: Path,
                             ctx: repo_context.RepoContext,
                             applied_appendices: list[str] | None = None) -> str:
    """Снимок артефактной ветки поверх обычного merge (SPEC
    01M1R9YEK08XEQWBFX0929WFVJ, требование 3; AC-6/AC-7/AC-8/AC-11) —
    ДО sha "коммита мержа" ниже: main обязан унести АРТЕФАКТНЫЙ снимок
    tasks/<id>/, значит это часть содержимого, на которое указывает
    `merge_sha`, а не служебная правка вроде карты/RETRO после него.

    Карта кодовой базы (SPEC T042) и RETRO (SPEC T043, требование 8,
    адресуется на `merge_sha` — сразу после merge/наложения снимка, ДО
    любых последующих служебных коммитов) — оба шага ТОЛЬКО для self
    (`ctx.path == config.ROOT`): SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    требование 4, AC-13 —
    «в пульте — только кухня пульта», для внешнего target ни карта, ни
    RETRO в её main НЕ коммитятся вовсе (RETRO внешнего target остаётся
    только в снапшоте закрытия, `orchestrator/snapshot.py`). Для self —
    оба провала некритичны, push ниже выполняется независимо от их
    исхода; оба шага работают В SCRATCH (AC-9) — не в `config.ROOT`.

    `_guard_task_root_or_refuse` (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
    AC-7/AC-8) — сразу после наложения снимка, ДО карты/RETRO/push:
    посторонний файл `tasks/<id>/` отказывает переходу `sys.exit`'ом,
    дальше этой функции выполнение не идёт.

    `applied_appendices` (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF, требование 6) —
    пути приложений, применённых `_apply_plan_appendices` ДО этого вызова:
    RETRO задачи обязано нести их перечень, а собирается RETRO здесь.

    Возврат — `final_sha` (после карты/RETRO для self) для push явным sha.
    """
    _overlay_artifact_snapshot(conn, task_id, scratch)
    _guard_task_root_or_refuse(conn, task_id, scratch, ctx)
    merge_sha = gitcmd.head_sha(scratch)
    if ctx.path == config.ROOT:
        fsm_postmerge._regenerate_and_commit_map(conn, task_id, repo=scratch)
        fsm_postmerge._generate_and_commit_retro(
            conn, task_id, merge_sha, repo=scratch,
            applied_appendices=applied_appendices)
    final_sha = gitcmd.head_sha(scratch)
    _drop_scratch_worktree(ctx, scratch)
    return final_sha


# Подстроки stderr `git push`, по которым отказ читается как «main
# сдвинулся между `_origin_main_sha` и push» (SPEC
# 01M2XFSE8G3MBRHHQR38H53J1M, требование 8): «cannot lock ref … is at X but
# expected Y» — буквальный текст origin из инцидента 13.09; «non-fast-
# forward»/«fetch first» — тексты самого git на отставшую ветку (те же,
# что различает `artifact_branch._classify_push_failure`). Голое
# «rejected» сюда НЕ входит: «[remote rejected] … (pre-receive hook
# declined)» — отказ прав, а не сдвиг main (требование 9).
_MAIN_MOVED_PUSH_MARKERS = ("cannot lock ref", "non-fast-forward",
                            "fetch first")


def _push_rejected_by_moved_main(stderr: str) -> bool:
    """Отказ push класса «main сдвинулся» — по подстрокам
    `_MAIN_MOVED_PUSH_MARKERS` в stderr git (регистр не важен)."""
    lowered = stderr.lower()
    return any(marker in lowered for marker in _MAIN_MOVED_PUSH_MARKERS)


def _push_merged_main(conn, task_id: str, final_sha: str,
                      ctx: repo_context.RepoContext) -> str:
    """Push ЯВНОГО sha (не текущего чекаута) прямо в `refs/heads/
    <ctx.base>` origin клона `ctx`, чья объектная база уже несёт коммиты
    scratch-worktree (общий `.git`), но чей собственный чекаут/HEAD этот
    push не трогает вовсе (AC-8). Для self — байт-в-байт прежнее
    поведение (`config.ROOT`, `refs/heads/config.MAIN_BRANCH`); для
    внешнего target — её клон и `refs/heads/<ctx.base>` (SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-12).

    `"ok"` — main продвинут. `"moved"` — origin отклонил push классом
    «не fast-forward»/«cannot lock ref» (SPEC 01M2XFSE8G3MBRHHQR38H53J1M,
    требование 8): main сдвинулся между `_origin_main_sha` и push (чужой
    пульт либо второй цикл этого же — инцидент 13.09). Это штатный исход
    движущегося main, не сбой: в журнал — именованная запись «main
    сдвинулся во время окна — повтор подтяжки», процесс НЕ завершается,
    вызывающее тело гейта возвращает `("wait", branch)` и заходит заново в
    том же вызове `approve`. Иные отказы (сеть, права, git не ответил) —
    прежние «merge FAILED» + `sys.exit` (требование 9)."""
    push = repo_context.git(ctx, "push", "origin",
                            f"{final_sha}:refs/heads/{ctx.base}")
    if push is not None and push.returncode == 0:
        return "ok"
    stderr = push.stderr if push is not None else ""
    if push is not None and _push_rejected_by_moved_main(stderr):
        store.journal(conn, task_id, "orchestrator",
                      "main сдвинулся во время окна — повтор подтяжки",
                      stderr.strip()[:500])
        print(f"[{task_id}] main сдвинулся во время merge-окна — повтор "
              f"подтяжки и ожидания CI в этом же вызове approve")
        return "moved"
    store.journal(conn, task_id, "orchestrator", "merge FAILED",
                  stderr.strip()[:500] if push is not None
                  else "git не ответил")
    sys.exit(f"merge упал на git push:\n"
             f"{stderr if push is not None else '—'}")


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
    композиция шагов — защищённые пути в диффе (SPEC
    01M27JPEGCGMDDRX5A98QWJW0Z, требование 3/AC-5) -> публикация головы ->
    свежесть main -> зелёный CI -> плотницкий merge в scratch-worktree
    (Stage0, AC-8) -> приложения PLAN к защищённым путям (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, требования 3-6) -> снимок артефактов/
    карта/RETRO -> push явным sha -> done -> снапшот закрытия -> уборка
    worktree/ветки.

    Возврат — сигнал вызывающему циклу (`_cmd_approve_merge_gate_cycle`):
    `("stopped",)` — окно завершилось без merge (отказ, эскалация,
    конфликт — дальше вызывающему циклу делать нечего); `("done",)` —
    merge выполнен; `("wait", branch)` — дальше вызывающий цикл ждёт CI
    ВНЕ этого мьютекса циклом `_wait_for_branch_ci_green` (требование 2).
    `("moved", branch)` — отказ push «main сдвинулся» (`_push_merged_main`
    -> `"moved"`, SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требования 8-9): повтор
    идёт тем же путём, что и исход подтяжки, — цикл не сбрасывает уже
    идущий отсчёт `MERGE_GATE_CI_WAIT_CEILING_SEC`, подтверждает CI ветки
    (голова не менялась) и заходит в тело заново, где подтяжка увидит
    сдвинутый main. Отдельный тег нужен циклу, чтобы ТОЛЬКО на этом пути
    поставить паузу и сверить общий потолок до нового захода (REVIEW
    итерации 1, R1-F1): при уже зелёном CI `_wait_for_branch_ci_green`
    возвращается сразу, не сверяя `deadline`, и без этой сверки устойчиво
    отвергаемый push (застрявший lock ref, чужой пульт, стабильно
    выигрывающий гонку) крутил бы тело гейта горячим бесконечным циклом.

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
    if _protected_path_diff_gate(conn, task_id, state, branch, ctx):
        return ("stopped",)
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
    appendix_kind, applied = _apply_plan_appendices(conn, task_id, state,
                                                    scratch, ctx)
    if appendix_kind != "ok":
        return ("stopped",)
    final_sha = _publish_merge_artifacts(conn, task_id, scratch, ctx,
                                         applied_appendices=applied)
    if _push_merged_main(conn, task_id, final_sha, ctx) == "moved":
        return ("moved", branch)
    _finalize_done_state(conn, task_id, state, branch)
    if _publish_closing_snapshot_or_wait(conn, task_id, t) == "done":
        return ("done",)
    _cleanup_merged_task(conn, task_id, branch)
    return ("done",)


def _cmd_approve_merge_gate_cycle(conn, task_id: str, sid: str, t,
                                  state: str) -> None:
    """Внешний цикл гейта `merge_gate` (SPEC T087, требования 1-6, 10;
    решение Оператора 31.08, аудит v6 Q-5; SPEC
    01M291EJMA995AZ61MEMDZKWRY, требования 1-2, 4-5): чередует тело
    гейта (`_cmd_approve_merge_gate`) и ожидание CI
    (`_wait_for_branch_ci_green`) — один и тот же вызов `approve`
    доводит задачу до `done` сам, без нового ручного вызова Оператора.

    Мьютекс резервируется на ВЕСЬ цикл, не вокруг каждого отдельного
    захода в тело: `merge_lock.acquire` — один раз ДО `while True`,
    `merge_lock.release` — один раз в `finally` ВОКРУГ всего цикла
    (требования 1-2, 4; AC-1, AC-5, AC-7) — держатель не меняется между
    заходом, вернувшим `("wait", ...)`, и следующим заходом, включая
    время внутри `_wait_for_branch_ci_green` (её heartbeat продлевает
    сама, требование 3). `finally` снимает мьютекс безусловно на любом
    исходе — успешный merge, отказ `sys.exit`, `KeyboardInterrupt`
    (требование 10) — тем же принципом, что и `merge_lock.run_window`,
    только на границе всего цикла, а не одного захода в тело.

    Занятый мьютекс (SPEC 01M291EPQ2VFGCHZTXXC81616V, требования 1-3) не
    отказывает немедленно — `merge_queue.wait_for_window` встаёт в очередь
    FIFO и опрашивает освобождение окна, возвращаясь только с уже взятым
    ЭТИМ процессом мьютексом (либо сама завершает процесс `sys.exit`'ом по
    истечении потолка ожидания очереди, не тронув состояние задачи).
    Держатель мьютекса — процесс, не сессия (SPEC
    01M2XFSE8G3MBRHHQR38H53J1M, требования 1-2): второй цикл `approve`
    той же рабочей копии пульта получает от `merge_lock.acquire` тот же
    отказ, что и чужая сессия, и уходит в очередь этим же путём.

    `deadline`/`start` вычисляются ОДИН раз за весь вызов `approve` — в
    момент первого исхода `("wait", ...)`/`("moved", ...)`, то есть от
    первого пуша (требование 4): повторный уход в `("wait", ...)` после
    новой подтяжки (AC-6) не пересчитывает их. Время, проведённое в
    очереди мержа до входа в окно, в этот отсчёт не входит (SPEC
    01M291EPQ2VFGCHZTXXC81616V, требование 4) — `start` берётся ПОСЛЕ
    возврата `wait_for_window`.

    Исход `("moved", branch)` — отказ push «main сдвинулся» (SPEC
    01M2XFSE8G3MBRHHQR38H53J1M, требования 8-9) — идёт дальше тем же
    путём, что и `("wait", branch)` (ожидание CI, новый заход в тело), но
    с двумя своими шагами ДО него (REVIEW итерации 1, R1-F1):
    пауза `MERGE_GATE_CI_WAIT_POLL_SEC` (heartbeat мьютекса продлевается
    перед ней — тем же приёмом, что итерация `_wait_for_branch_ci_green`)
    и сверка общего `deadline`. Голова ветки при «moved» не менялась, CI
    уже зелёный, и `_wait_for_branch_ci_green` вернулась бы мгновенно, не
    сверив потолок и не паузя, — без этих шагов устойчиво отвергаемый push
    (застрявший lock ref origin, чужой пульт, стабильно выигрывающий
    гонку) крутил бы fetch/worktree/merge/карту/RETRO/push горячим циклом
    без конца. Потолок один и тот же для обоих исходов — не сбрасывается
    (требование 9): истёк — запись «merge FAILED» и `sys.exit` с
    именованным отказом, задача остаётся на `merge_gate`.
    """
    start: float | None = None
    deadline: float | None = None
    confirmed_ci_note: str | None = None
    moved_retries = 0
    refusal = merge_lock.acquire(conn, task_id, sid)
    if refusal is not None:
        merge_queue.wait_for_window(conn, task_id, sid)
    try:
        while True:
            outcome = _cmd_approve_merge_gate(conn, task_id, state, t,
                                              confirmed_ci_note)
            confirmed_ci_note = None
            if outcome[0] not in ("wait", "moved"):
                return
            branch = outcome[1]
            if deadline is None:
                start = time.monotonic()
                deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC
            if outcome[0] == "moved":
                moved_retries += 1
                merge_lock.touch_heartbeat(conn)
                time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)
                if time.monotonic() >= deadline:
                    _exit_moved_main_ceiling(conn, task_id, branch,
                                             moved_retries, start)
            confirmed_ci_note = _wait_for_branch_ci_green(
                conn, task_id, branch, start, deadline)
    finally:
        merge_lock.release(conn, sid)


def _exit_moved_main_ceiling(conn, task_id: str, branch: str,
                             moved_retries: int, start: float) -> None:
    """Общий потолок `MERGE_GATE_CI_WAIT_CEILING_SEC` истёк на пути повтора
    «main сдвинулся» (SPEC 01M2XFSE8G3MBRHHQR38H53J1M, требование 9; REVIEW
    итерации 1, R1-F1): запись «merge FAILED» с числом повторов и
    `sys.exit` тем же стилем, что и отказ `_wait_for_branch_ci_green` по
    истёкшему потолку. Задача остаётся на `merge_gate`, мьютекс снимает
    `finally` вызывающего цикла."""
    elapsed = int(time.monotonic() - start)
    detail = (f"main сдвигался всё окно: потолок ожидания истёк после "
              f"{moved_retries} повтор(ов) подтяжки, {elapsed} сек")
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; проверь, кто двигает "
             f"{config.MAIN_BRANCH} origin, и повтори: artel.py approve "
             f"{task_id} (ветка {branch})")
