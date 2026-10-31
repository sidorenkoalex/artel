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
import contextlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextvars import ContextVar
from pathlib import Path

from scripts import guard

from . import (acceptance, alerts, appendix_tree, artifact_branch,
              artifact_source, ci, cleanup, config, forge, fsm, fsm_postmerge,
              gitcmd,
              github_adapter, lease, merge_lock, merge_queue, project_profile,
              reference_cache, repo_context, session, store, targets,
              workspace)
from .advance_gates.acceptance import (_acceptance_lock_refuses,
                                       _long_lived_manifest_refuses)
from .advance_gates import outcome_integrity, plan_appendix
from .advance_gates.test_integrity import merge_gate_escalates

_fresh_suite_for_cycle: ContextVar[bool] = ContextVar(
    "fresh_suite_for_merge_gate_cycle", default=False)

# Предел ожидания CI новой головы main после push мержа (SPEC
# 01M3SF7DPFGEZ7VYEGGXGTX49E, AC-4): полный прогон CI main идёт 3–4
# минуты, очередь раннеров добавляет столько же. Это не
# `MERGE_GATE_CI_WAIT_CEILING_SEC` (час на CI ветки до мержа): здесь мерж
# уже состоялся, и ждать дольше — держать мьютекс мержа ради исхода,
# который следующий мерж всё равно сверит сам.
MAIN_CI_WAIT_LIMIT_SEC = 18 * 60

# Предел одного прогона `guard.py --all` по дереву мержа (на дереве пульта
# — меньше секунды); не ответил — отказ мержа, не пропуск сверки.
GUARD_ALL_TIMEOUT_SEC = 300

# Действие журнала об исходе CI main после мержа (AC-4).
MAIN_CI_AFTER_MERGE_ACTION = "CI main после мержа"

# Пересборка справочника ядра после мержа (SPEC 01M4S24EBVB72B8WYJ3JY96Y0E,
# требование 9): исход шага и его сбой.
REFERENCE_REBUILD_ACTION = "справочник ядра после мержа"
REFERENCE_REBUILD_FAILED_ACTION = "справочник ядра после мержа: сбой"
REFERENCE_REBUILD_FAILED_ALERT = "справочник ядра: пересборка после мержа не удалась"


def _touches_protected_path(path: str, protected=None) -> bool:
    # `protected` — перечень проекта задачи (`repo_context.protected_paths`);
    # `None` — `config.PROTECTED_PATHS`.
    return config.is_protected_path(path, protected)


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

    Любой проект, по перечню защищённых путей проекта задачи
    (`repo_context.protected_paths`, SPEC 01M45FK56DWMNBRKA1VWM12H19,
    требования 1-3): у артели — `config.PROTECTED_PATHS`, у внешнего
    проекта — поле `no_paths` его записи; дифф — в клоне контекста.

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
    base = gitcmd.diff_base(branch, repo=ctx.path)
    if base is None:
        return False
    files = gitcmd.diff_names(base, branch, repo=ctx.path)
    if files is None:
        return False
    perimeter = repo_context.protected_paths(ctx)
    protected = [f for f in files if _touches_protected_path(f, perimeter)]
    if not protected:
        return False
    detail = _protected_path_refusal_detail(protected)
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=state, detail=detail)
    return True


def _test_integrity_diff_gate(conn, task_id: str, state: str, branch: str,
                              ctx: repo_context.RepoContext) -> bool:
    """Тот же узел сравнения `tests/`, что стоит на `in_dev -> verifying`
    (SPEC 01M3FQ2V77QNK95Z599DM124QN, требование 7, AC-12) — сразу за
    `_protected_path_diff_gate` и до попытки merge: ветка могла дойти
    сюда и другим маршрутом (ручной `advance` Оператора, повторный заход
    после эскалации, подтяжка main, добавившая удаление уже после
    `verifying`), а ручная сверка удалённых и ослабленных тестов с этой
    задачи с Оператора снята.

    Любой проект с профилем тестов — область `weakening_scope` профиля,
    дифф в клоне проекта `ctx` (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
    требование 5); у проекта без профиля шаг не выполняется и пишет об
    этом запись в журнал. Отказ по контексту и профилю артели уже дан в
    начале тела гейта (`_profile_refusal_exit`).
    Мандат Оператора читается с ветки-источника `tasks/<id>/`
    (`artifact_source.resolve`), дифф — с кодовой ветки.

    `True` — эскалировано, вызывающий код обязан остановиться.
    """
    decision = project_profile.for_task_target(ctx.target, task_id, conn)
    if decision.profile is None:
        if not decision.refusal:
            project_profile.journal_skip(
                conn, task_id, project_profile.CHECK_WEAKENING, decision)
        elif project_profile.is_multi(ctx.target):
            # Компонент задачи не выбран — отказ, не пропуск гейта текста
            # (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2).
            store.journal(conn, task_id, "fsm", MERGE_PROFILE_REFUSAL_ACTION,
                          decision.refusal)
            print(f"[{task_id}] merge отклонён: {decision.refusal}")
            return True
        return False
    artifact_branch_name, _foreign = artifact_source.resolve(conn, task_id)
    return merge_gate_escalates(conn, task_id, state, branch,
                                artifact_branch_name,
                                scope=decision.profile.in_weakening_scope)


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
    защищённый путь (перечень проекта `repo_context.protected_paths`), в
    `escalated` (AC-4) —
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
    perimeter = repo_context.protected_paths(ctx)
    protected = [f for f in files if _touches_protected_path(f, perimeter)]
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

    Повтор не запущен (`ci.rerun_started`) — запись `flake-rate` называет
    это и причину: перечитанный статус тогда не исход повтора, и ни
    «подтверждённый красный», ни «флейк» о нём не правда (SPEC
    01M55V7WB94C9BZXTXTTH83YWV, требование 7). Исход узла тот же.
    """
    repo = workspace.task_repo(task_id)
    rerun_trigger_note = ci.trigger_rerun(branch, **ci._repo_kwargs(repo))
    store.journal(conn, task_id, "orchestrator", "ре-ран CI запущен",
                  rerun_trigger_note)
    rerun_green, rerun_note = ci.branch_status(branch, repo=repo)
    store.journal(conn, task_id, "orchestrator",
                  "статус CI ветки (ре-ран)", rerun_note)
    if not ci.rerun_started(rerun_trigger_note):
        store.journal(
            conn, task_id, "orchestrator", "flake-rate",
            f"повтор не запущен: {rerun_trigger_note}; первый статус "
            f"красный, статус после — {rerun_note} ({note})")
    elif rerun_green:
        store.journal(
            conn, task_id, "orchestrator", "flake-rate",
            f"флейк: первый статус красный, ре-ран зелёный "
            f"({note} -> {rerun_note})")
    else:
        store.journal(
            conn, task_id, "orchestrator", "flake-rate",
            f"подтверждённый красный: первый статус красный, ре-ран "
            f"тоже красный ({note} -> {rerun_note})")
    if rerun_green:
        return rerun_green, rerun_note
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
    # Ожидание долгое: документы команды — в origin до него (ADR-0021 п.3).
    artifact_branch.send_pending()
    while True:
        green, note = ci.branch_status(branch,
                                       repo=workspace.task_repo(task_id))
        merge_lock.touch_heartbeat(conn, task_id,
                                   session.resolve_session_id())
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


def _task_docs_files(conn, task_id: str) -> tuple[str, list[str] | None, str]:
    """(ревизия, пути файлов `tasks/<id>/` на ней, причина) — дерево ссылки
    документов задачи на ЗАФИКСИРОВАННОЙ голове (`tasks.fixed_sha`; фиксации
    нет — голова ссылки). Пути `None` — ссылки нет либо её дерево не
    читается: причина называет, что именно (SPEC 01M4M67SGNEYMN9F1C7XVX24XE,
    требование 7)."""
    ref = artifact_branch.branch_name(task_id)
    head = artifact_branch.ref_head(task_id)
    if not head:
        return "", None, f"ссылки документов {ref} нет в репозитории задачи"
    fixed = store.get_task(conn, task_id)["fixed_sha"] or head
    paths = artifact_branch.ls_tree(task_id, fixed, f"tasks/{task_id}")
    if paths is None:
        return fixed, None, f"дерево {ref} на {fixed} не читается"
    return fixed, paths, ""


def _task_docs_violations(task_id: str, rev: str, paths: list[str],
                          guard_rules: bool, rule=None) -> list[str]:
    """Нарушения документов задачи на ревизии `rev` ссылки: посторонние
    файлы каталога задачи — у любого проекта (критерий
    `_guard_task_root_or_refuse`, включая подкаталоги); с `guard_rules` —
    ещё правила `guard --all` к каталогу задачи (посторонние файлы
    `acceptance_tests/`, маркер AC-n с отступом, структура `.md`).

    Освобождения «закрытой истории» по `docs/retro/<id>.md`, которое
    `guard --all` даёт задачам дерева, здесь нет: проверяется живая
    мержащаяся задача (требование 6). Нужный правилу файл, который git не
    отдал, — нарушение, как нечитаемый файл у `guard.check`.

    Правило планки проекта (`rule`; не передано — по проекту задачи; SPEC
    01M59KMPG2ZMK10V556VZVQD65, требование 9): не по умолчанию — посторонние
    файлы планки и пометки с отступом по нему и без `guard_rules`; отказ
    построения у внешнего проекта — то же по правилу по умолчанию. Артель
    и записи `test_profile` — как прежде."""
    if rule is None:
        rule = project_profile.plank_rule(workspace.task_target(task_id))
    by_rule = not rule.is_default
    plank_rules = guard_rules or by_rule or bool(rule.refusal)
    prefix = f"tasks/{task_id}/"
    rels = [p[len(prefix):] for p in paths if p.startswith(prefix)]
    violations = [f"{prefix}{rel}: {guard.EXTRANEOUS_TASK_ROOT_FILE_REASON}"
                  for rel in rels if guard.is_extraneous_task_root_file(rel)]
    if not plank_rules:
        return violations
    plank: list[tuple[str, str]] = []
    for rel in rels:
        parts = rel.split("/")
        in_plank = parts[0] == "acceptance_tests" and len(parts) > 1
        if in_plank:
            if "__pycache__" in parts:
                continue
            if guard.is_extraneous_acceptance_test_file(
                    "/".join(parts[1:]), rule if by_rule else None):
                violations.append(f"{prefix}{rel}: "
                                  f"{guard.EXTRANEOUS_ACCEPTANCE_FILE_REASON}")
                continue
        elif guard.is_extraneous_task_root_file(rel):
            continue
        if by_rule:
            is_test = in_plank and rule.is_test("/".join(parts[1:]))
        else:
            is_test = (in_plank and parts[-1].startswith("test_")
                       and rel.endswith(".py"))
        # Структура `.md` — правило `guard --all` артели, не правило планки.
        if not (is_test or (guard_rules and rel.endswith(".md"))):
            continue
        if guard.is_task_passport(Path("tasks") / task_id / rel):
            continue
        # Записка шага — свободный текст роли (SPEC
        # 01M4RZBPG6EXM74MTBPTEGW2D4, требование 2), структурой не проверяется.
        if guard.is_step_note(Path("tasks") / task_id / rel):
            continue
        text, reason = artifact_branch.show(task_id, rev, prefix + rel)
        if text is None:
            violations.append(f"{prefix}{rel}: не прочитан: {reason}")
        elif is_test:
            plank.append((prefix + rel, text))
        else:
            violations.extend(guard.check_content(prefix + rel, text))
    violations.extend(guard.indented_ac_marker_errors_from_files(
        plank, rule=rule if by_rule else None))
    return violations


def _guard_task_docs_or_refuse(conn, task_id: str, scratch: Path,
                               ctx: repo_context.RepoContext) -> None:
    """Документы мержащейся задачи — на дереве `refs/artifacts/<id>`, не на
    дереве мержа (SPEC 01M4M67SGNEYMN9F1C7XVX24XE, требования 6-7; ADR-0021
    п.4): каталог задачи в main больше не накладывается, и проверять его в
    scratch нечего. Стоит до карты, `guard --all`, sha для push и коммита
    закрытия; любой проект.

    Ссылки нет или она не читается — отказ, не пропуск: прежнее наложение
    при сбое материализации проверяло пустой каталог. Отказ — тем же путём,
    что `_guard_task_root_or_refuse`: «merge FAILED», scratch снят,
    `sys.exit`, задача на `merge_gate` без эскалации, main не тронут."""
    rev, paths, reason = _task_docs_files(conn, task_id)
    if paths is None:
        violations = [reason]
    else:
        # Правила `guard --all` — там же, где их сегодня применял guard
        # дерева мержа: артель, в дереве которой guard есть.
        guard_rules = (repo_context.is_artel(ctx)
                       and (scratch / "scripts" / "guard.py").is_file())
        rule = project_profile.plank_rule(ctx.target)
        project_profile.journal_plank_default(conn, task_id, "orchestrator",
                                              rule)
        violations = _task_docs_violations(task_id, rev, paths, guard_rules,
                                           rule)
    if not violations:
        return
    detail = (f"документы задачи на {artifact_branch.branch_name(task_id)}: "
              + "; ".join(violations))
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(ctx, scratch)
    listing = "\n".join(f"  - {v}" for v in violations)
    sys.exit(f"[{task_id}] merge отклонён: документы задачи на "
             f"{artifact_branch.branch_name(task_id)}:\n{listing}\n"
             f"  задача осталась на гейте merge; почини документы задачи "
             f"и повтори: artel.py approve {task_id}")


def _guard_task_root_or_refuse(conn, task_id: str, scratch: Path,
                               ctx: repo_context.RepoContext) -> None:
    """Guard на `tasks/<id>/`, выложенный каталогом на диск под `scratch`
    (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0, AC-7/AC-8) — посторонний файл
    (инцидент 06.09), проникший в документы задачи В ОБХОД автокоммита
    (правка Оператора на гейте, старая ветка, отставшая от фильтра
    `checkpoint.py`). Тело гейта мержа документы задачи на диск больше не
    выкладывает (ADR-0021 п.4) и проверяет их на ссылке тем же критерием —
    `_guard_task_docs_or_refuse`.

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


def _guard_all_violations(scratch: Path) -> list[str] | None:
    """Нарушения `scripts/guard.py --all` дерева мержа, запущенного из его
    корня; `[]` — нарушений нет (предупреждения guard — код 0 — не они);
    `None` — сверять нечем (в дереве нет guard или каталога `tasks`:
    дерево не пульта). Сбой самого запуска — одна строка-нарушение с
    причиной: отказ, не пропуск."""
    script = scratch / "scripts" / "guard.py"
    if not script.is_file() or not (scratch / "tasks").is_dir():
        return None
    try:
        res = subprocess.run([sys.executable, str(script), "--all"],
                             cwd=scratch, capture_output=True, text=True,
                             timeout=GUARD_ALL_TIMEOUT_SEC)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"guard --all не ответил: {exc}"]
    if res.returncode == 0:
        return []
    lines = res.stdout.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if ln.startswith("GUARD: нарушения"))
    except StopIteration:
        tail = (res.stderr or res.stdout).strip()[-500:]
        return [f"guard --all завершился кодом {res.returncode}: "
                f"{tail or 'без вывода'}"]
    return [ln.strip()[2:] for ln in lines[start + 1:]
            if ln.strip().startswith("- ")]


def _guard_all_or_refuse(conn, task_id: str, scratch: Path,
                         ctx: repo_context.RepoContext) -> None:
    """`guard.py --all` по дереву результата мержа — после приложений PLAN
    и карты, до sha для push (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E, требование 1,
    AC-1; SPEC 01M4M67SGNEYMN9F1C7XVX24XE, требование 8): дерево, которое
    уйдёт в main. Документы самой задачи в нём больше не лежат — их
    проверяет `_guard_task_docs_or_refuse` на ссылке документов.

    Guard — того же дерева (`scripts/guard.py` мержа, его правила), не
    пульта. Только self target: у внешнего target'а guard пульта к его
    дереву неприменим. Нарушение — отказ тем же путём, что прочие отказы
    `merge_gate` («merge FAILED», scratch снят, `sys.exit`, задача на
    гейте, main не тронут)."""
    if not repo_context.is_artel(ctx):
        return
    violations = _guard_all_violations(scratch)
    if not violations:
        return
    detail = "guard --all по дереву мержа: " + "; ".join(violations)
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(ctx, scratch)
    listing = "\n".join(f"  - {v}" for v in violations)
    sys.exit(f"[{task_id}] merge отклонён: guard --all по дереву мержа "
             f"нашёл нарушения:\n{listing}\n"
             f"  задача осталась на гейте merge; почини артефакты задачи "
             f"и повтори: artel.py approve {task_id}")


def _refuse_if_main_red(conn, task_id: str, ctx: repo_context.RepoContext,
                        fixes_main: str | None) -> None:
    """Красный CI main отказывает следующему мержу (SPEC
    01M3SF7DPFGEZ7VYEGGXGTX49E, требование 4, AC-5): цвет — по проверкам
    первой родительской линии от головы origin/main (`ci.main_line_status`
    — то же определение, что у `pin-update` и `doctor`), под мьютексом,
    перед плотницким merge. Мерж поверх красного main маскирует, чей
    дефект краснит main, и добавляет к нему следующий.

    Отказ — только на красном: идущий и неизвестный CI (сбой `gh`) — запись
    журнала и проход, иначе недоступный `gh` останавливал бы весь пульт.
    `fixes_main` — основание `approve <id> <sha> --fixes-main
    "<основание>"`: Оператор чинит main этой задачей; основание пишется в
    журнал задачи, а сверка снимается только для этого вызова.

    Только self target: CI main — пульта; у внешнего target'а свой форж."""
    if not repo_context.is_artel(ctx):
        return
    origin_sha = _origin_main_sha(ctx)
    if origin_sha is None:
        store.journal(conn, task_id, "orchestrator", "сверка CI main",
                      f"origin/{ctx.base} не прочитан — цвет CI main не "
                      f"сверен")
        return
    status = ci.main_line_status(origin_sha, repo=ctx.path)
    if fixes_main:
        store.journal(conn, task_id, "operator",
                      "сверка CI main снята: --fixes-main",
                      f"основание: {fixes_main}; {status.note}")
        print(f"[{task_id}] сверка CI main снята (--fixes-main): "
              f"{fixes_main}; {status.note}")
        return
    if status.kind != ci.MAIN_RED:
        store.journal(conn, task_id, "orchestrator", "сверка CI main",
                      status.note)
        return
    detail = (f"main красный с {status.red_since[:8]} — сначала починить "
              f"main ({status.note})")
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; повтори approve, когда "
             f"main позеленеет, либо, если эта задача и чинит main: "
             f"artel.py approve {task_id} <sha> --fixes-main "
             f"\"<основание>\"")


def _await_main_ci(conn, task_id: str, head: str,
                   ctx: repo_context.RepoContext) -> None:
    """Ожидание CI новой головы main после push мержа (SPEC
    01M3SF7DPFGEZ7VYEGGXGTX49E, требование 4, AC-4) — тем же опросом, что
    ожидание `verifying` (пауза `config.VERIFYING_POLL_INTERVAL_SEC`), до
    `MAIN_CI_WAIT_LIMIT_SEC`. Задача к этому моменту уже `done` — исход
    мерж не откатывает, а называет: зелёный, красный с упавшими
    проверками либо «не дождался» — записью журнала задачи и строкой
    вывода. Мьютекс мержа держится всё ожидание (heartbeat продлевается):
    следующий мерж начнётся, когда цвет новой головы уже известен.

    `gh` не ответил — «не дождался» сразу: опросить нечем, и ждать до
    предела значило бы держать мьютекс впустую. Только self target."""
    artifact_branch.send_pending()
    if not repo_context.is_artel(ctx):
        return
    start = time.monotonic()
    while True:
        status = ci.main_line_status(head, repo=ctx.path) if head else None
        merge_lock.touch_heartbeat(conn, task_id,
                                   session.resolve_session_id())
        if status is None:
            outcome = "CI main не дождался: голова main после мержа не определена"
        elif status.kind == ci.MAIN_GREEN:
            outcome = f"CI main {head[:8]} после мержа: {status.note}"
        elif status.kind == ci.MAIN_RED:
            outcome = (f"CI main {head[:8]} после мержа красный — "
                       f"{status.note}")
        elif status.kind == ci.MAIN_UNKNOWN:
            outcome = f"CI main {head[:8]} не дождался — {status.note}"
        elif time.monotonic() - start >= MAIN_CI_WAIT_LIMIT_SEC:
            outcome = (f"CI main {head[:8]} не дождался за "
                       f"{MAIN_CI_WAIT_LIMIT_SEC // 60} мин — {status.note}")
        else:
            time.sleep(config.VERIFYING_POLL_INTERVAL_SEC)
            continue
        store.journal(conn, task_id, "orchestrator",
                      MAIN_CI_AFTER_MERGE_ACTION, outcome)
        print(f"[{task_id}] {outcome}")
        return


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
        # CI ветки читает PLAN.md из origin: документы — раньше кода.
        artifact_branch.send_pending(task_id)
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
# Настройки сбора тестов (`conftest.py` в любом каталоге, корневые
# `pyproject.toml`/`pytest.ini`/`setup.cfg`/`tox.ini`, SPEC
# 01M3MVXZXF25KYY2P213E0M39X, требование 10) — тот же класс, что `tests/`:
# они решают, что и как соберёт сам набор. Записи сверяются общей формулой
# `config.is_protected_path` (маска `**/` — по имени файла).
_FULL_SUITE_APPENDIX_PREFIXES = ("tests/", ".github/", "**/conftest.py",
                                 "pyproject.toml", "pytest.ini", "setup.cfg",
                                 "tox.ini")


def _appendix_needs_full_suite(paths: list[str]) -> bool:
    return any(config.is_protected_path(p, _FULL_SUITE_APPENDIX_PREFIXES)
               for p in paths)


# Действие журнала: у внешнего проекта без профиля тестов применённые
# приложения не прогоняются (SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 6).
FULL_SUITE_SKIPPED_ACTION = "полный прогон приложений не выполнен"


def _full_suite_command(conn, task_id: str, paths: list[str], scratch: Path,
                        ctx: repo_context.RepoContext) -> tuple[bool, list | None]:
    """(нужен ли полный прогон после приложений `paths`, команда прогона;
    `None` — команда пульта) — SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 6.

    Артель — прежние классы `_FULL_SUITE_APPENDIX_PREFIXES` и команда
    пульта. Внешний проект — прогон после КАЖДОГО применённого
    приложения: пульт не знает, какие файлы чужого репозитория влияют на
    сбор и прогон его тестов. Команда — из профиля тестов проекта; профиля
    нет — прогона нет, и журнал задачи несёт об этом запись. Профиль не
    прочитан — отказ мержа (`_profile_refusal_exit` в начале тела уже
    отказал бы; здесь — на случай правки `targets.yaml` посреди окна)."""
    if repo_context.is_artel(ctx):
        return _appendix_needs_full_suite(paths), None
    selected = _selected_components(conn, task_id, paths, ctx)
    if selected is not None:
        # Запись из нескольких компонентов — кортеж профилей затронутых
        # (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требования 10-11).
        return True, selected
    decision = project_profile.decide(ctx.target)
    if decision.profile is not None:
        # `pytest-own` и профиль с отчётом — профилем целиком (argv, `cwd`,
        # окружение по нему, SPEC 01M52EEHSRD93WMPHWB5VJYRKD,
        # 01M590GJAF0EDV4NBC4C99MFVH); `pult-pytest` — прежний список.
        return True, acceptance.place_channel(decision.profile)
    if decision.refusal:
        store.journal(conn, task_id, "fsm", MERGE_PROFILE_REFUSAL_ACTION,
                      decision.refusal)
        _drop_scratch_worktree(ctx, scratch)
        sys.exit(f"[{task_id}] merge отклонён: {decision.refusal}\n"
                 f"  задача осталась на гейте merge; почини targets.yaml и "
                 f"повтори: artel.py approve {task_id}")
    store.journal(conn, task_id, "orchestrator", FULL_SUITE_SKIPPED_ACTION,
                  f"{decision.skip}: нет профиля тестов — приложения "
                  f"{', '.join(paths)} применены без полного прогона")
    return False, None


def _selected_components(conn, task_id: str, paths: list[str],
                         ctx: repo_context.RepoContext) -> tuple | None:
    """Профили компонентов записи из нескольких компонентов, затронутых
    диффом ветки задачи и путями приложений `paths`
    (`project_profile.select_components`, SPEC 01M590GJAF0EDV4NBC4C99MFVH,
    требование 10); `None` — у записи один компонент или она не прочитана
    (решает `decide`). Дифф ветки не прочитан — все компоненты: молча
    сузить выбор нельзя."""
    try:
        if len(project_profile.components(ctx.target)) < 2:
            return None
    except targets.TargetsError:
        return None
    branch = store.task_branch(conn, task_id)
    base = gitcmd.diff_base(branch, repo=ctx.path) if branch else None
    changed = (gitcmd.diff_names(base, branch, repo=ctx.path)
               if base else None)
    if changed is None:
        return project_profile.component_profiles(ctx.target)
    names = project_profile.select_components(ctx.target,
                                              [*changed, *paths])
    return project_profile.component_profiles(ctx.target, names)


def _gate_profiles(conn, task_id: str, paths: list[str],
                   ctx: repo_context.RepoContext) -> tuple:
    """Профили компонентов проекта задачи на гейте мержа — для
    `checks_local` (требование 13): затронутые компоненты записи из
    нескольких компонентов либо профиль единственного; у артели и проекта
    без профиля — пусто."""
    if repo_context.is_artel(ctx):
        return ()
    selected = _selected_components(conn, task_id, paths, ctx)
    if selected is not None:
        return selected
    profile = project_profile.decide(ctx.target).profile
    return (profile,) if profile is not None else ()


CHECKS_LOCAL_REFUSAL_ACTION = "merge FAILED"


def _checks_local_refuse(conn, task_id: str, paths: list[str], scratch: Path,
                         ctx: repo_context.RepoContext) -> bool:
    """`checks_local` затронутых компонентов в дереве мержа после
    приложений — на каждом гейте мержа, с полным прогоном и без него (SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 13). Ненулевой код — отказ
    мержа с выводом проверки: задача остаётся на гейте, scratch убран.
    `True` — отказ напечатан и записан."""
    for profile in _gate_profiles(conn, task_id, paths, ctx):
        ok, text = acceptance.run_checks_local(profile, scratch)
        if not text:
            continue
        store.journal(conn, task_id, "orchestrator",
                      acceptance.CHECKS_LOCAL_ACTION, text)
        if ok:
            continue
        store.journal(conn, task_id, "orchestrator",
                      CHECKS_LOCAL_REFUSAL_ACTION, text)
        _drop_scratch_worktree(ctx, scratch)
        print(f"[{task_id}] merge отклонён: {text}\n"
              f"  задача осталась на гейте merge; почини код под проверку и "
              f"повтори: artel.py approve {task_id}")
        return True
    return False


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
    ничего некорректного в main это не пропускает — не применяется ничего.
    Нечитаемую ссылку документов отказом встретит следом
    `_guard_task_docs_or_refuse`."""
    appendices, errors, unread = appendix_tree.read_plan(
        conn, task_id, repo_context.protected_paths(ctx))
    if unread:
        store.journal(conn, task_id, "orchestrator",
                      "приложения PLAN не прочитаны",
                      f"{unread} — приложения не применяются")
        return []
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


def _appendix_already_in_main(conn, task_id: str, number: int, appendix,
                              scratch: Path) -> bool:
    """Приложение, которое не легло прямым `git apply`, уже наложено в
    подтянутом main (SPEC 01M443HV9SJYVYQTHJSQ87QV68, требование 5):
    `git apply --reverse --check` проходит. Прецедент 04.10
    (01M42PENCS26D0656X8FR7DFA7): Оператор внёс правку защищённого теста
    коммитом в main, и прежние ворота отказывали задаче на уже сделанной
    работе. Такое приложение принимается с записью журнала и не
    накладывается повторно.

    Частично наложенное (ни прямой, ни обратный `--check` не проходят) —
    False, и вызывающий возвращает задачу прежним исходом (требование 6).

    Признание и запись журнала — общий узел `plan_appendix.skip_in_base`
    (SPEC 01M4JD3SRN66SD6BM63XAGHB11, требования 3-4): база здесь —
    подтянутый main, он и назван в подробностях записи."""
    return plan_appendix.skip_in_base(conn, task_id, number, appendix, scratch,
                                      "подтянутом main",
                                      "не накладывается повторно")


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
                          ctx: repo_context.RepoContext,
                          fresh_suite: bool = False) -> None:
    """Полный набор тестов в scratch-дереве, где приложения УЖЕ применены
    (требование 5/AC-10/AC-11) — у артели только для путей
    `_FULL_SUITE_APPENDIX_PREFIXES`, у внешнего проекта — после любого
    приложения, командой его профиля (`_full_suite_command`). Красный
    прогон — именованный отказ мержа: задача остаётся на `merge_gate`,
    scratch убран, main не продвинут, приложения не опубликованы.

    Прогон и разбор его вывода — общий узел `acceptance.full_suite` (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требование 5): detail отказа несёт
    итоговую строку pytest, имена упавших тестов и путь к файлу с полным
    выводом прогона — той же поверхностью, что и автогейт приёмки. До
    этой правки здесь лежал сырой хвост вывода, в котором имена упавших
    тестов тонули.

    Отказ различает исход прогона (SPEC 01M46D5T8SZ9D6S34TZFX8S46V,
    требование 5): поломкой приложений назван только красный прогон.
    Таймаут и «прогон не начат» (замок полных прогонов машины не
    освободился) о приложениях ничего не говорят — 05.10 прогон, оборванный
    на 99% без единого падения, был назван поломкой приложением."""
    needed, command = _full_suite_command(conn, task_id, paths, scratch, ctx)
    if not needed:
        return
    artifact_branch.send_pending()
    if isinstance(command, tuple):
        run = acceptance.components_full_suite(scratch, task_id, command,
                                               fresh=fresh_suite)
    elif command is None:
        run = (acceptance.full_suite(scratch, task_id, fresh=True)
               if fresh_suite else acceptance.full_suite(scratch, task_id))
    else:
        run = (acceptance.full_suite(scratch, task_id, command=command,
                                     fresh=True) if fresh_suite else
               acceptance.full_suite(scratch, task_id, command=command))
    if run.green:
        store.journal(conn, task_id, "orchestrator",
                      "полный прогон после приложений", run.detail)
        return
    if run.outcome == acceptance.FULL_SUITE_TIMEOUT and \
            isinstance(command, tuple):
        # Предел — свой у компонента; его называет деталь прогона.
        detail = (f"прогон не уложился в предел компонента (полный набор "
                  f"после приложений): {run.detail}")
        advice = (f"прогон оборван по пределу времени, это не исход "
                  f"тестов; повтори: artel.py approve {task_id}")
    elif run.outcome == acceptance.FULL_SUITE_TIMEOUT:
        seconds, source = project_profile.full_suite_limit(ctx.target)
        detail = (f"прогон не уложился в {seconds} с "
                  f"(источник: {source}; "
                  f"полный набор tests/ после приложений): {run.detail}")
        advice = (f"прогон оборван по пределу времени, это не исход "
                  f"тестов; повтори: artel.py approve {task_id}")
    elif run.outcome == acceptance.FULL_SUITE_NOT_STARTED:
        detail = f"полный набор tests/ после приложений — {run.detail}"
        # Файлы БД пульта в дереве прогона (SPEC 01M4FYTB8QWJNHYCP35K8QC4E3,
        # требование 4) — тоже «не начат», но ждать освобождения машины тут
        # бессмысленно: команду уборки называет сам `run.detail`.
        if acceptance.is_unknown(run):
            # Прогон был, но итог тестов из отчёта не прочитан (SPEC
            # 01M590GJAF0EDV4NBC4C99MFVH, требование 3): ждать машину
            # бессмысленно — причину называет деталь, вывод — лог прогона.
            advice = (f"исход «{acceptance.UNKNOWN_OUTCOME}» — итог тестов "
                      f"не прочитан из отчёта; разберись в причине по логу "
                      f"прогона и повтори: artel.py approve {task_id}")
        elif "worktree-db-clean" in run.detail:
            advice = ("прогон не запускался; убери файлы БД пульта командой "
                      f"из причины и повтори: artel.py approve {task_id}")
        else:
            advice = (f"прогон не запускался; повтори, когда машина "
                      f"освободится: artel.py approve {task_id}")
    else:
        detail = f"приложения ломают тесты: {run.detail}"
        advice = (f"почини приложение к {', '.join(paths)} и повтори: "
                  f"artel.py approve {task_id}")
    store.journal(conn, task_id, "orchestrator", "merge FAILED", detail)
    _drop_scratch_worktree(ctx, scratch)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge; {advice}")


def _apply_plan_appendices(conn, task_id: str, state: str, scratch: Path,
                           ctx: repo_context.RepoContext,
                           fresh_suite: bool = False):
    """Приложения PLAN к защищённым путям — применение пультом (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, требования 3-6): ПОСЛЕ плотницкого merge и
    ДО карты и `guard --all`, то есть коммит приложений ложится в main
    раньше коммита карты и входит в коммит мержа, на который адресуется
    RETRO закрытия (SPEC 01M4M67SGNEYMN9F1C7XVX24XE, требования 3б, 8).

    До этой задачи защищённый путь в main мог попасть только ручным
    коммитом Оператора; после включения хуков защиты main
    (01M2XMCC83) этот путь закрылся, и приложение 01M2XJKKPH к
    `skills/test-authoring.md` применить стало некому — дыра, которую
    закрывает эта функция.

    Любой проект (SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 3): допуск
    путей — по перечню защищённых путей проекта задачи, полный прогон —
    по правилу проекта (`_full_suite_command`).

    `("ok", пути)` — применять было нечего либо всё применено и
    закоммичено; `("stopped", [])` — приложение неприменимо к подтянутому
    main, задача возвращена в `in_dev` (требование 4)."""
    appendices = _plan_appendices_or_refuse(conn, task_id, scratch, ctx)
    if not appendices:
        return ("ok", [])

    # Пути КАЖДОГО заголовка `diff --git` каждого приложения (R1-F1):
    # многофайловый блок git применяет целиком, и `git add` ниже обязан
    # унести в коммит все его файлы, иначе правка Оператора уезжает в
    # никуда вместе со scratch-деревом.
    # Наложение — общий узел `appendix_tree.apply_in_order` (SPEC
    # 01M46C776SZEMYPBQGPNJN1TXY, требование 7): тем же порядком и тем же
    # `git_apply` приложения ложатся на дерево полного прогона автогейта,
    # approve и `suite-run`.
    paths, failure = appendix_tree.apply_in_order(
        scratch, appendices,
        lambda number, appendix: _appendix_already_in_main(
            conn, task_id, number, appendix, scratch))
    if failure is not None:
        _return_inapplicable_appendix(conn, task_id, state, failure.appendix,
                                      failure.answer, scratch, ctx)
        return ("stopped", [])
    if not paths:
        # Все приложения уже в main: коммитить нечего, `git commit` на
        # пустом индексе отказал бы и сорвал мерж.
        return ("ok", [])

    sha = _commit_applied_appendices(conn, task_id, paths, scratch, ctx)
    # Прогон — после коммита и ДО записи «применены»/push: красный исход
    # означает, что приложения не поедут в main вовсе, и объявлять их
    # применёнными раньше его нечестно.
    _full_suite_or_refuse(conn, task_id, paths, scratch, ctx,
                          fresh_suite=fresh_suite)
    store.journal(conn, task_id, "orchestrator",
                  f"приложения применены: {', '.join(paths)}",
                  f"коммит {sha} в scratch-дереве мержа")
    return ("ok", paths)


MAP_GENERATOR_REL = "scripts/codebase_map.py"
# Действие журнала: в дереве мержа нет генератора карты, шаг карты не
# выполнялся (SPEC 01M45FK56DWMNBRKA1VWM12H19, требование 7).
MAP_SKIPPED_ACTION = "карта кодовой базы не строится"


def _map_step(conn, task_id: str, scratch: Path) -> None:
    """Регенерация и коммит карты кодовой базы — если в дереве мержа есть
    генератор `MAP_GENERATOR_REL` (SPEC 01M45FK56DWMNBRKA1VWM12H19,
    требование 7): признак — само дерево проекта, не имя проекта. Нет
    генератора — ни коммита, ни инцидента, только запись в журнал задачи:
    молча шаг не пропускается."""
    if (scratch / MAP_GENERATOR_REL).is_file():
        fsm_postmerge._regenerate_and_commit_map(conn, task_id, repo=scratch)
        return
    store.journal(conn, task_id, "orchestrator", MAP_SKIPPED_ACTION,
                  f"в дереве мержа нет генератора {MAP_GENERATOR_REL} — "
                  f"карта не регенерируется и не коммитится")


def _publish_merge_artifacts(conn, task_id: str, scratch: Path,
                             ctx: repo_context.RepoContext) -> str:
    """Шаги дерева мержа между приложениями PLAN и push (ADR-0021 п.4; SPEC
    01M4M67SGNEYMN9F1C7XVX24XE): каталог задачи и её RETRO в main больше не
    попадают ни у одного проекта — RETRO живёт только в коммите закрытия
    `refs/artifacts/<id>` (`orchestrator/snapshot.py`), куда перечень
    применённых приложений и sha мержа передаёт тело гейта.

    Первым — проверка документов задачи на её ссылке
    (`_guard_task_docs_or_refuse`): отказ `sys.exit`'ом до карты, push и
    коммита закрытия. Карта кодовой базы (SPEC T042) — у любого проекта, в
    дереве мержа которого есть генератор (`_map_step`), отдельным коммитом
    поверх merge и приложений. `guard --all` по дереву мержа артели (SPEC
    01M3SF7DPFGEZ7VYEGGXGTX49E) — после карты и до sha для push: дерево уже
    несёт приложения. Шаги работают В SCRATCH (AC-9), не в `config.ROOT`.

    Возврат — `final_sha` (после карты) для push явным sha.
    """
    _guard_task_docs_or_refuse(conn, task_id, scratch, ctx)
    _map_step(conn, task_id, scratch)
    _guard_all_or_refuse(conn, task_id, scratch, ctx)
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


MERGE_DURING_CANARY_REFUSED_ACTION = "merge отклонён: идёт канарейка"
MERGE_DURING_CANARY_ACTION = "merge во время канарейки"


def _refuse_during_canary(conn, task_id: str, ctx: repo_context.RepoContext,
                          during_canary: str | None) -> None:
    """Живой прогон канарейки набора по умолчанию держит мерж задачи артели
    (SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0, требования 5-7): канарейка идёт на
    вершине main, которая станет пином. Стоит непосредственно перед push —
    ловит и одобрение, ждавшее очередь или CI, и канарейку, стартовавшую
    после входа в тело. Отказ — `sys.exit`, задача остаётся на
    `merge_gate`, мьютекс снимает `finally` вызывающего цикла. С основанием
    `--during-canary` — строка журнала задачи и прежний путь; без живого
    прогона флаг принимается молча (требование 10)."""
    if not repo_context.is_artel(ctx):
        return
    from . import canary
    note = canary.live_run_note(default_set_only=True)
    if note is None:
        return
    if during_canary is not None:
        store.journal(conn, task_id, "operator", MERGE_DURING_CANARY_ACTION,
                      f"{note}; основание: {during_canary}")
        return
    detail = (f"{note}: мерж сдвинет main под проверяемым коммитом — "
              f"дождись итога или повтори с {canary.DURING_CANARY_FLAG} "
              f'"<основание>"')
    store.journal(conn, task_id, "fsm", MERGE_DURING_CANARY_REFUSED_ACTION,
                  detail)
    sys.exit(f"[{task_id}] merge отклонён: {detail}\n"
             f"  задача осталась на гейте merge")


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


# Литерал действия журнала отказа гейта мержа при документах задачи, не
# совпадающих с `origin` (ADR-0021 п.3).
MERGE_UNSYNCED_JOURNAL_ACTION = "merge отклонён: документы не совпадают с origin"


def _docs_ref_unsynced(conn, task_id: str) -> bool:
    """Гейт мержа отказывает, пока `refs/artifacts/<id>` не совпадает с
    `origin` (ADR-0021 п.3): мерж закрывает задачу, а закрытие поверх
    истории документов, которой нет в `origin` или которая там другая,
    оставило бы её в одном месте. `True` — отказано (журнал и вывод
    называют `origin` и оба sha), задача остаётся на гейте мержа."""
    refusal = artifact_branch.origin_sync_refusal(task_id)
    if refusal is None:
        return False
    store.journal(conn, task_id, "fsm", MERGE_UNSYNCED_JOURNAL_ACTION, refusal)
    print(f"[{task_id}] merge {refusal}\n  задача осталась на гейте merge; "
          f"сведи {artifact_branch.branch_name(task_id)} с origin и повтори: "
          f"artel.py approve {task_id}")
    return True


def _cleanup_merged_task(conn, task_id: str, branch: str,
                         merged_sha: str) -> None:
    """Worktree задачи отслужил (SPEC T045, требование 5, AC-6):
    смержено, дальше агентным шагам там делать нечего. Ветка задачи —
    следом за worktree (tasks/T073/SPEC.md, требование 2): `-d` откажет,
    пока ветку держит worktree, поэтому порядок обязателен. Последней —
    ветка задачи в `origin` проекта, если её голова входит в `merged_sha`,
    ушедший в `origin` (SPEC 01M5FGJW4RBN9C9P48Q8MDHJX1)."""
    note = workspace.remove(task_id)
    store.journal(conn, task_id, "orchestrator", "worktree убран", note)
    branch_note = cleanup.drop_merged_task_branch(
        branch, workspace.task_repo(task_id))
    store.journal(conn, task_id, "orchestrator", "ветка убрана", branch_note)
    cleanup.cleanup_merged_remote(conn, task_id, branch, merged_sha)


def _outcome_integrity_merge_gate(conn, task_id: str, state: str,
                                  ctx: repo_context.RepoContext) -> bool:
    """Гейт неослабления по исходам в окне мержа (SPEC
    01M5DDTVZEA40ZB9BHEH4YDEE7, требования 2-4) — после «fresh» и до
    `_acceptance_locks_refuse`: сравниваются исходы головы, которая уйдёт в
    main, с merge-base её и только что зафетченного main
    (`_origin_main_sha`, не повторный `diff_base`). `True` — эскалировано;
    сбой подготовки — `sys.exit` внутри, задача остаётся на `merge_gate`."""
    return outcome_integrity.merge_gate_escalates(
        conn, task_id, state, lambda: _origin_main_sha(ctx))


def _acceptance_locks_refuse(conn, task_id: str) -> bool:
    """Лок каталога приёмочных тестов (`_acceptance_lock_refuses`) и перечень
    долгоживущих файлов (`_long_lived_manifest_refuses`) на гейте мержа
    после `_sync_main_or_wait` (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования
    7-8): до задачи гейт мержа лок не сверял вовсе, и планку, правленую
    после `in_dev -> verifying`, никто больше не ловил. Расхождение или сбой
    git — остановка тела без merge.

    Любой проект с профилем тестов (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
    требование 5): у проекта без профиля сверка не выполняется и пишет об
    этом запись в журнал; неразрешённый контекст и артель без профиля —
    остановка (отказ уже напечатан и записан). Строка задачи — свежая: `t`
    вызывающего прочитан до подтяжки."""
    decision = project_profile.for_task(conn, task_id)
    if decision.refusal:
        store.journal(conn, task_id, "fsm", MERGE_PROFILE_REFUSAL_ACTION,
                      decision.refusal)
        print(f"[{task_id}] merge отклонён: {decision.refusal}")
        return True
    if decision.profile is None:
        project_profile.journal_skip(conn, task_id,
                                     project_profile.CHECK_MANIFEST, decision)
        return False
    t = store.get_task(conn, task_id)
    artifact_branch_name, foreign = artifact_source.resolve(conn, task_id)
    if _acceptance_lock_refuses(conn, task_id, t, artifact_branch_name, foreign):
        return True
    return _long_lived_manifest_refuses(conn, task_id)


MERGE_PROFILE_REFUSAL_ACTION = "merge отклонён: профиль тестов проекта"


def _profile_refusal_exit(conn, task_id: str, target: str) -> None:
    """Профиль тестов артели не задан или не прочитан — `approve` гейта
    мержа отказывает до первого шага тела, не дойдя до ожидания CI (SPEC
    01M45FJVGQT1K0P8HDEXZX6HS7, требование 4): гейты целостности тестов
    пульта не отключаются и на мерже. Состояние не трогается. У записи из
    нескольких компонентов — решение по компоненту задачи (`for_task`)."""
    decision = project_profile.for_task_target(target, task_id, conn)
    if not decision.refusal:
        return
    store.journal(conn, task_id, "fsm", MERGE_PROFILE_REFUSAL_ACTION,
                  decision.refusal)
    sys.exit(f"[{task_id}] merge отклонён: {decision.refusal}\n"
             f"  задача осталась на гейте merge; почини targets.yaml и "
             f"повтори: artel.py approve {task_id}")


def _cmd_approve_merge_gate(conn, task_id: str, state: str, t,
                            confirmed_ci_note: str | None = None,
                            fixes_main: str | None = None,
                            fresh_suite: bool = False,
                            during_canary: str | None = None) -> tuple:
    """Тело окна `merge_gate -> done`, исполняемое ПОД МЬЮТЕКСОМ merge
    (SPEC T053, требование 1; SPEC T087, требования 1-2, 5-6): короткая
    композиция шагов — защищённые пути в диффе (SPEC
    01M27JPEGCGMDDRX5A98QWJW0Z, требование 3/AC-5) -> неослабление тестов
    в диффе (SPEC 01M3FQ2V77QNK95Z599DM124QN, требование 7/AC-12) ->
    публикация головы ->
    свежесть main -> гейт неослабления по исходам (SPEC
    01M5DDTVZEA40ZB9BHEH4YDEE7) -> зелёный CI -> плотницкий merge в scratch-worktree
    (Stage0, AC-8) -> приложения PLAN к защищённым путям (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, требования 3-6) -> документы задачи на
    ссылке/карта/`guard --all` -> push явным sha -> done -> коммит закрытия
    с RETRO в `refs/artifacts/<id>` -> уборка worktree/ветки. Первым шагом —
    сверка ссылки документов с `origin` (ADR-0021 п.3).

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
    решает, где физически стоит scratch-worktree/куда идёт push и нужен
    ли `guard --all` (только self). Контекст не читается
    (targets.yaml сломан/неизвестный target) — `sys.exit` тем же стилем,
    что и остальные инфраструктурные отказы этого гейта: merge — точка
    без права молча деградировать на чужой репозиторий.

    SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E (требования 1, 4): после зелёного CI
    ветки и до merge — сверка цвета CI main (`_refuse_if_main_red`,
    `fixes_main` — основание флага `--fixes-main`); после push, `done` и
    уборки — ожидание CI новой головы main (`_await_main_ci`); guard по
    дереву мержа и по документам задачи — внутри `_publish_merge_artifacts`.

    SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0 (требование 5): непосредственно перед
    push — сверка живого прогона канарейки (`_refuse_during_canary`,
    `during_canary` — основание флага `--during-canary`).
    """
    target = store.task_target(conn, task_id)
    ctx = repo_context.resolve(target)
    if ctx is None:
        sys.exit(f"[{task_id}] merge отклонён: "
                 f"{project_profile.unresolved_reason(target)}\n"
                 f"  задача осталась на гейте merge; почини targets.yaml "
                 f"и повтори: artel.py approve {task_id}")
    _profile_refusal_exit(conn, task_id, target)
    branch = t["branch"]
    if github_adapter.people_entry(target) is not None:
        return _approve_for_project_people(conn, task_id, state, t, ctx,
                                           confirmed_ci_note, during_canary)
    if _docs_ref_unsynced(conn, task_id):
        return ("stopped",)
    if _protected_path_diff_gate(conn, task_id, state, branch, ctx):
        return ("stopped",)
    if _test_integrity_diff_gate(conn, task_id, state, branch, ctx):
        return ("stopped",)
    if _ensure_branch_head_published(conn, task_id, branch) != "ok":
        return ("stopped",)
    sync_outcome = _sync_main_or_wait(conn, task_id, t, state, branch, ctx)
    if sync_outcome != "fresh":
        return sync_outcome
    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):
        return ("stopped",)
    if _acceptance_locks_refuse(conn, task_id):
        return ("stopped",)
    ci_outcome = _ci_ready_or_wait(task_id, confirmed_ci_note, branch)
    if ci_outcome != "ok":
        return ci_outcome
    _refuse_if_main_red(conn, task_id, ctx, fixes_main)
    merge_kind, scratch = _perform_carpentry_merge(conn, task_id, state,
                                                    branch, ctx)
    if merge_kind != "ok":
        return ("stopped",)
    appendix_kind, applied = _apply_plan_appendices(
        conn, task_id, state, scratch, ctx,
        fresh_suite or _fresh_suite_for_cycle.get())
    if appendix_kind != "ok":
        return ("stopped",)
    if _checks_local_refuse(conn, task_id, applied, scratch, ctx):
        return ("stopped",)
    # Коммит мержа задачи — merge кодовой ветки плюс приложения, без карты:
    # на него адресуется «Итог: done» RETRO закрытия.
    merge_sha = gitcmd.head_sha(scratch)
    final_sha = _publish_merge_artifacts(conn, task_id, scratch, ctx)
    _refuse_during_canary(conn, task_id, ctx, during_canary)
    if _push_merged_main(conn, task_id, final_sha, ctx) == "moved":
        return ("moved", branch)
    _finalize_done_state(conn, task_id, state, branch)
    cleanup._commit_closing(conn, task_id, merge_sha=merge_sha,
                            applied_appendices=applied)
    _cleanup_merged_task(conn, task_id, branch, final_sha)
    _await_main_ci(conn, task_id, final_sha, ctx)
    _rebuild_core_reference(conn, task_id, final_sha)
    return ("done",)


# Гейт мержа проекта, MR которого вливают люди проекта (`merge_gate:
# target-human`; SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требования 1-5; ADR-0029
# п. 1): пульт не сливает и не отправляет `base` — открывает MR через `forge`.
BASE_MOVED_DETAIL = "base сдвинулся — подготовка ветки заново"
APPENDIX_REFUSAL_DETAIL = ("приложения не применяются в проекте с "
                           "target-human — правку вносят люди проекта")
MR_EXISTS_DETAIL = "MR ветки уже существует, ссылки в БД нет"
PEOPLE_REFUSED_ACTION = "approve отклонён"
HEAD_UNCONFIRMED_ACTION = "approve отклонён: голова не подтверждена"
MR_REFUSED_ACTION = "approve отклонён: MR"
MR_DURING_CANARY_REFUSED_ACTION = "MR не открыт: идёт канарейка"
_FIXATION_ACTION = "sha зафиксирован"
# Код ответа хостинга в причине `forge` — текст адаптера GitLab
# (`gitlab_adapter.py:211`, «GitLab ответил кодом 409 на …»).
_HOSTING_CODE = re.compile(r"ответил кодом (\d{3}) на")
_CONFLICT_CODE = "409"


def _approve_for_project_people(conn, task_id: str, state: str, t,
                                ctx: repo_context.RepoContext,
                                confirmed_ci_note: str | None,
                                during_canary: str | None) -> tuple:
    """Тело окна `merge_gate -> awaiting_human` под мьютексом merge-окна:
    сверка ссылки документов с `origin` -> защищённые пути и неослабление
    по тексту -> приложения PLAN (отказ) -> подтверждённая голова -> сдвиг
    `base` (возврат в `in_dev`) -> публикация головы и сверка её на
    сервере -> неослабление по исходам -> лок планки -> зелёный CI головы
    ветки -> канарейка -> предел `max_awaiting` -> MR через `forge`.

    Не исполняются: отказ по красному CI base, подтяжка на гейте, слияние,
    `checks_local`, карта и `guard --all`, отправка `base`, закрытие и
    уборка, ожидание CI base, справочник ядра — пульт в `base` не пишет.
    Сдвиг `base` не подтягивается здесь: голова, уходящая в MR, заново
    проходит `in_dev -> verifying` (сжатие и `freshness`, Б1.2).

    Возврат — сигнал циклу `_cmd_approve_merge_gate_cycle`, как у
    `_cmd_approve_merge_gate`: `("wait", branch)` — ждать CI вне тела."""
    branch = t["branch"]
    if _docs_ref_unsynced(conn, task_id):
        return ("stopped",)
    if _protected_path_diff_gate(conn, task_id, state, branch, ctx):
        return ("stopped",)
    if _test_integrity_diff_gate(conn, task_id, state, branch, ctx):
        return ("stopped",)
    if _appendices_refuse(conn, task_id, ctx):
        return ("stopped",)
    head = _confirmed_code_head(conn, task_id)
    if _local_head_unconfirmed(conn, task_id, branch, head, ctx):
        return ("stopped",)
    if _base_moved_returns(conn, task_id, state, head, ctx):
        return ("stopped",)
    if _ensure_branch_head_published(conn, task_id, branch) != "ok":
        return ("stopped",)
    if _server_head_unconfirmed(conn, task_id, branch, head, ctx):
        return ("stopped",)
    if _outcome_integrity_merge_gate(conn, task_id, state, ctx):
        return ("stopped",)
    if _acceptance_locks_refuse(conn, task_id):
        return ("stopped",)
    ci_outcome = _ci_ready_or_wait(task_id, confirmed_ci_note, branch)
    if ci_outcome != "ok":
        return ci_outcome
    _refuse_mr_during_canary(conn, task_id, during_canary)
    if _awaiting_limit_refuses(conn, task_id, ctx):
        return ("stopped",)
    return _deliver_mr(conn, task_id, state, head, ctx)


def _people_refusal(conn, task_id: str, action: str, detail: str) -> None:
    store.journal(conn, task_id, "fsm", action, detail)
    print(f"[{task_id}] approve отклонён: {detail}\n"
          f"  задача осталась на гейте merge; повтори: artel.py approve "
          f"{task_id}")


def _appendices_refuse(conn, task_id: str,
                       ctx: repo_context.RepoContext) -> bool:
    """Приложения PLAN в проекте с гейтом людей проекта (требование 3):
    правку защищённых путей пульт в `base` не вносит. Разбор с ошибками —
    тоже приложение. `True` — отказано."""
    appendices, errors, _unread = appendix_tree.read_plan(
        conn, task_id, repo_context.protected_paths(ctx))
    if not appendices and not errors:
        return False
    paths = sorted({p for a in appendices for p in a.paths})
    _people_refusal(conn, task_id, PEOPLE_REFUSED_ACTION,
                    f"{APPENDIX_REFUSAL_DETAIL}"
                    + (f" ({', '.join(paths)})" if paths else ""))
    return True


def _confirmed_code_head(conn, task_id: str) -> str:
    """Голова кодовой ветки, подтверждённая Оператором: поле `код=`
    последней записи фиксации с подтверждённым sha (`tasks.fixed_sha`) —
    у внешнего проекта sha `approve` — голова ссылки документов, а голову
    кода называет та же запись. Пусто — записи нет."""
    fixed = store.get_task(conn, task_id)["fixed_sha"] or ""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] != _FIXATION_ACTION:
            continue
        detail = row["detail"] or ""
        if fixed and f"sha={fixed}," not in detail:
            continue
        match = re.search(r"код=([0-9a-f]{40})", detail)
        return match.group(1) if match else ""
    return ""


def _local_head_unconfirmed(conn, task_id: str, branch: str, head: str,
                            ctx: repo_context.RepoContext) -> bool:
    """Голова ветки, которая ушла бы в MR, — не подтверждённая (требование
    1): отказ до публикации, неподтверждённая голова на сервер не идёт."""
    local = gitcmd.branch_head_sha(branch, repo=repo_context.path_or_none(ctx))
    if head and local == head:
        return False
    _people_refusal(conn, task_id, HEAD_UNCONFIRMED_ACTION,
                    f"голова ветки {branch} {local or '(не прочитана)'} — не "
                    f"подтверждённая фиксацией {head or '(нет записи)'}; MR не "
                    f"открыт — проверь ветку и подтверди новую фиксацию")
    return True


def _server_head_unconfirmed(conn, task_id: str, branch: str, head: str,
                             ctx: repo_context.RepoContext) -> bool:
    """Голова ветки на сервере после публикации — не подтверждённая
    (требование 1): MR открылся бы на чужой коммит."""
    remote = gitcmd.remote_branch_sha(branch, repo=repo_context.path_or_none(ctx))
    if remote == head:
        return False
    _people_refusal(conn, task_id, HEAD_UNCONFIRMED_ACTION,
                    f"голова ветки {branch} на сервере "
                    f"{remote or '(не прочитана)'} — не подтверждённая "
                    f"{head}; MR не открыт")
    return True


def _base_moved_returns(conn, task_id: str, state: str, head: str,
                        ctx: repo_context.RepoContext) -> bool:
    """`base` на сервере ушёл вперёд от подтверждённой головы (требование
    2): возврат в `in_dev` без подтяжки здесь. `True` — задача вернулась."""
    origin_sha = _origin_main_sha(ctx)
    if origin_sha is None:
        sys.exit(f"[{task_id}] approve отклонён: git fetch origin "
                 f"{ctx.base} не ответил\n"
                 f"  задача осталась на гейте merge; почини доступ к "
                 f"origin и повтори: artel.py approve {task_id}")
    if gitcmd.is_ancestor(origin_sha, head,
                          repo=repo_context.path_or_none(ctx)):
        return False
    store.set_state(conn, task_id, "in_dev", "fsm", expected_state=state,
                    detail=f"{BASE_MOVED_DETAIL}: {ctx.base} "
                           f"{origin_sha[:8]} не в ветке, MR не открыт")
    return True


def _refuse_mr_during_canary(conn, task_id: str,
                             during_canary: str | None) -> None:
    """Живой прогон канарейки держит и открытие MR (требование 1) — тем же
    правилом и флагом, что мерж задачи артели (`_refuse_during_canary`)."""
    from . import canary
    note = canary.live_run_note(default_set_only=True)
    if note is None:
        return
    if during_canary is not None:
        store.journal(conn, task_id, "operator", MERGE_DURING_CANARY_ACTION,
                      f"{note}; основание: {during_canary}")
        return
    detail = (f"{note}: MR не открывается во время канарейки — дождись "
              f"итога или повтори с {canary.DURING_CANARY_FLAG} "
              f'"<основание>"')
    store.journal(conn, task_id, "fsm", MR_DURING_CANARY_REFUSED_ACTION, detail)
    sys.exit(f"[{task_id}] approve отклонён: {detail}\n"
             f"  задача осталась на гейте merge")


def _awaiting_limit_refuses(conn, task_id: str,
                            ctx: repo_context.RepoContext) -> bool:
    """Предел `policy.max_awaiting` (требование 5): счёт задач этого
    проекта в `awaiting_human` — под мьютексом merge-окна, иначе два
    параллельных `approve` прошли бы оба. `True` — отказано."""
    try:
        limit = targets.delivery_policy(targets.target(ctx.target))["max_awaiting"]
    except targets.TargetsError:
        return False
    if limit is None:
        return False
    waiting = [r["id"] for r in store.project_tasks(conn, ctx.target)
               if r["state"] == fsm.AWAITING_HUMAN and r["id"] != task_id]
    if len(waiting) < limit:
        return False
    _people_refusal(conn, task_id, github_adapter.AWAITING_LIMIT_ACTION,
                    f"предел awaiting_human: задач проекта в awaiting_human "
                    f"{len(waiting)} из {limit} (policy.max_awaiting) — MR не "
                    f"открыт, задача ждёт на гейте")
    return True


def _deliver_mr(conn, task_id: str, state: str, head: str,
                ctx: repo_context.RepoContext) -> tuple:
    """MR через `forge` (требование 4): ссылки в БД нет — открыть MR ветки
    в `base`; ссылка есть — снять черновик и назначить исполнителя у этого
    MR, описание не трогается. Успех — `awaiting_human`; 409 открытия без
    ссылки — эскалация; иной отказ — задача на гейте."""
    row = store.get_task(conn, task_id)
    iid, url = store.mr_link(row)
    if iid is None:
        result = github_adapter.open_forge_mr(conn, task_id, row, head,
                                              draft=False)
        if result.reason:
            code = _HOSTING_CODE.search(result.reason)
            if code is not None and code.group(1) == _CONFLICT_CODE:
                store.set_state(conn, task_id, "escalated", "fsm",
                                expected_state=state,
                                detail=f"{MR_EXISTS_DETAIL}: {result.reason}")
                return ("stopped",)
            _people_refusal(conn, task_id, MR_REFUSED_ACTION,
                            f"MR не открыт: {result.reason}")
            return ("stopped",)
        iid, url = result.iid, result.url
    elif not _ready_existing_mr(conn, task_id, ctx.target, iid):
        return ("stopped",)
    store.set_state(conn, task_id, fsm.AWAITING_HUMAN, "operator",
                    expected_state=state,
                    detail=f"MR !{iid} {url or ''} — вливают люди проекта")
    return ("awaiting",)


def _ready_existing_mr(conn, task_id: str, target: str, iid: int) -> bool:
    """Черновой MR задачи из БД: снять черновик и назначить исполнителя —
    только числовой id (ответ Оператора ANSWER-2 п. 3). `False` — отказ
    хостинга, задача остаётся на гейте."""
    result = forge.undraft_mr(target, iid)
    if result.reason:
        _people_refusal(conn, task_id, MR_REFUSED_ACTION,
                        f"черновик MR !{iid} не снят: {result.reason}")
        return False
    store.journal(conn, task_id, "orchestrator", "MR снят с черновика",
                  f"MR !{iid}")
    policy = targets.delivery_policy(targets.target(target))
    assignee, note = github_adapter.mr_assignee(policy)
    if assignee is None:
        store.journal(conn, task_id, "orchestrator",
                      github_adapter.MR_ASSIGNEE_ACTION, note)
        return True
    result = forge.assign_mr(target, iid, assignee)
    if result.reason:
        _people_refusal(conn, task_id, MR_REFUSED_ACTION,
                        f"исполнитель {assignee} MR !{iid} не назначен: "
                        f"{result.reason}")
        return False
    store.journal(conn, task_id, "orchestrator",
                  github_adapter.MR_ASSIGNEE_ACTION,
                  f"MR !{iid}: исполнитель {assignee}")
    return True


def _rebuild_core_reference(conn, task_id: str, final_sha: str) -> None:
    """Справочник ядра проекта на новой голове main (SPEC
    01M4S24EBVB72B8WYJ3JY96Y0E, требование 9): последний шаг мержа, вне
    его критического пути — задача уже `done`, коммит закрытия и уборка
    исполнены, поэтому сбой шага любого типа, в том числе в собственной
    записи журнала или алерте, мерж не срывает. Шаг ничего не коммитит:
    кэш лежит в области проектов вне git (К-3а). Проект без поля
    `core_reference` — `off`, без записей."""
    try:
        reference = reference_cache.get_reference(
            conn, task_id, reason="merge", sha=final_sha)
        if reference.state != "off":
            detail = f"{reference.state} sha={final_sha}"
            if reference.note:
                detail += f"; {reference.note}"
            store.journal(conn, task_id, "orchestrator",
                          REFERENCE_REBUILD_ACTION, detail)
    except Exception as exc:  # noqa: BLE001 — шаг вне критического пути мержа
        with contextlib.suppress(Exception):
            store.journal(conn, task_id, "orchestrator",
                          REFERENCE_REBUILD_FAILED_ACTION,
                          f"sha={final_sha}; {type(exc).__name__}: {exc}")
        with contextlib.suppress(Exception):
            alerts.raise_alert(conn, store.task_target(conn, task_id),
                               "incident", reference_cache.ALERT_SOURCES["merge"],
                               REFERENCE_REBUILD_FAILED_ALERT)


def _cmd_approve_merge_gate_cycle(conn, task_id: str, sid: str, t,
                                   state: str,
                                   fixes_main: str | None = None,
                                   fresh_suite: bool = False,
                                   during_canary: str | None = None) -> None:
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
    гонку) крутил бы fetch/worktree/merge/карту/push горячим циклом
    без конца. Потолок один и тот же для обоих исходов — не сбрасывается
    (требование 9): истёк — запись «merge FAILED» и `sys.exit` с
    именованным отказом, задача остаётся на `merge_gate`.

    `fixes_main` (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E, AC-5) — основание
    `--fixes-main`, доезжает до каждого захода в тело этого вызова.

    `during_canary` (SPEC 01M5C6QA6S3RY9PS4H9ZJ58WQ0, требование 6) —
    основание `--during-canary`, доезжает до тела только когда передано:
    заглушки тела в существующих тестах держат прежнюю сигнатуру.
    """
    body_extra = ({} if during_canary is None
                  else {"during_canary": during_canary})
    start: float | None = None
    deadline: float | None = None
    confirmed_ci_note: str | None = None
    moved_retries = 0
    refusal = merge_lock.acquire(conn, task_id, sid)
    if refusal is not None:
        merge_queue.wait_for_window(conn, task_id, sid)
    token = _fresh_suite_for_cycle.set(fresh_suite)
    try:
        while True:
            outcome = _cmd_approve_merge_gate(
                conn, task_id, state, t, confirmed_ci_note,
                fixes_main=fixes_main, **body_extra)
            confirmed_ci_note = None
            if outcome[0] not in ("wait", "moved"):
                return
            branch = outcome[1]
            if deadline is None:
                start = time.monotonic()
                deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC
            if outcome[0] == "moved":
                moved_retries += 1
                merge_lock.touch_heartbeat(conn, task_id, sid)
                time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)
                if time.monotonic() >= deadline:
                    _exit_moved_main_ceiling(conn, task_id, branch,
                                             moved_retries, start)
            confirmed_ci_note = _wait_for_branch_ci_green(
                conn, task_id, branch, start, deadline)
    finally:
        _fresh_suite_for_cycle.reset(token)
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
