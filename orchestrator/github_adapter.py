"""GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC
T079, требования 1-2). Первый прогон — на самой артели (target `artel`,
targets.yaml).

Операция merge (требование 3) намеренно не несёт отдельного вызова:
ANSWER-1 (вопрос 1) прямо допускает «расчёт на автоопределение GitHub по
коммиту в истории main» как валидный способ реализации — `git merge
--no-ff` (fsm.py) делает head ветки задачи предком коммита main, и
GitHub сам закрывает Draft MR с пометкой merged, обнаружив это после
push; отдельный вызов адаптера здесь добавлял бы вторую точку отказа
ровно там, где GitHub уже даёт наблюдаемый результат бесплатно.

Любой сбой этого модуля — инцидент (журнал + `alerts.raise_alert`), не
отказ перехода FSM: Draft-MR-флоу — побочный эффект входа в `in_dev`/
`merge_gate`, а не условие перехода (тот же приём, что `fsm.py::
_regenerate_and_commit_map`/`_generate_and_commit_retro`, SPEC T042/T043).
"""
from . import (alerts, artifact_branch, ci, config, forge, gitcmd,
               repo_context, store, targets)

# Пропуск черновика на пустой кодовой ветке (SPEC
# 01M3HP7WAXKFK3GYZ3T6HX08M0, требование 8) — запись журнала ОБЫЧНОГО
# уровня: ни `_incident`, ни алерта, потому что пропускать тут нечего
# чинить, это штатное состояние ветки до первого коммита разработчика.
DRAFT_MR_SKIPPED_ACTION = "Draft MR пропущен: в ветке нет коммитов"


def _commits_over_base(branch: str, base: str, repo=None) -> int | None:
    """Число коммитов `branch`, которых нет в голове `base` УДАЛЁННОГО
    `origin`, — git, без единого обращения к форджу (SPEC
    01M3HP7WAXKFK3GYZ3T6HX08M0, требование 8; SPEC
    01M3YDHTY1Y67KB98FVSHREC4N, требование 1).

    База — голова, полученная СВЕЖИМ `gitcmd.fetch_ref_sha`, а не локальная
    ветка `base` и не `refs/remotes/origin/<base>`: локальная `main` главной
    копии — пин, он по построению отстаёт от `origin/main`, от которой
    растут ветки задач, а remote-ref актуализирует только механика подтяжки
    и входа в `verifying` — позже входа в `in_dev`. По отставшей базе
    пустая ветка «имела коммиты», проверка её пропускала, и GitHub отвечал
    «No commits between» (инциденты 28.09–02.10).

    `None` — ответа нет (fetch базы не удался, git не ответил, ветки нет,
    вывод не разобрать числом). Вызывающий код обязан деградировать в то
    поведение, которое у него было ДО проверки, а не додумывать за git ни
    «ноль коммитов», ни «коммиты есть»: единственное решение, которое эти
    числа принимают, — пропустить заведомо отказной вызов форджа, и
    основанием для него служит только положительный ответ git.

    Своего `rev-list` здесь нет — считает `gitcmd.commits_behind` с её же
    деградацией. Аргументы переставлены сознательно: `commits_behind(X, Y)`
    исполняет `rev-list --count X..Y`, то есть «коммиты Y, которых нет в
    X» — нужный вопрос задаётся базой на первом месте и веткой на втором.
    """
    base_sha, _reason = gitcmd.fetch_ref_sha("origin", base, repo=repo)
    if not base_sha:
        return None
    return gitcmd.commits_behind(base_sha, branch, repo=repo)


def _is_github_target(target_name: str) -> bool:
    try:
        return targets.target(target_name).get("forge") == "github"
    except targets.TargetsError:
        return False


def _incident(conn, task_id: str, action: str, message: str) -> None:
    store.journal(conn, task_id, "orchestrator", action, message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "github_adapter", message)


def _touched_protected_paths(branch: str, base: str,
                             repo=None, protected=None) -> list[str]:
    """Пути перечня защищённых путей `protected`, затронутые диффом
    `base...branch` (A7, требование 7, AC-16) — независимо от
    предупреждения, которое уже печатает CI-job protected-paths (не
    заменяет его, дополняет). `protected` — перечень проекта задачи
    (`repo_context.protected_paths`, SPEC 01M45FK56DWMNBRKA1VWM12H19,
    требование 2); `None` — `config.PROTECTED_PATHS`.

    Git не ответил на diff — пустой список (не отказ и не эскалация:
    подсветка в MR — необязательное дополнение, отсутствие ответа не
    имеет права держать заведение Draft MR).

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-8; ADR-0021 п.1-2) — клон
    проекта, в котором считается diff, включая артель."""
    args = ("diff", "--name-only", f"{base}...{branch}")
    res = gitcmd.in_repo(repo, *args)
    if res is None or res.returncode != 0:
        return []
    paths = [p for p in res.stdout.splitlines() if p]
    return [p for p in paths if config.is_protected_path(p, protected)]


def _protected_paths_source(ctx) -> str:
    """Имя перечня в тексте подсветки: у артели — константа пульта, у
    внешнего проекта — поле `no_paths` его записи и обвязка (SPEC
    01M5T19041XE2KB6A52F0AT0NF, требование 11). Без « (»: текст сам стоит
    в скобках комментария."""
    if repo_context.is_artel(ctx):
        return "config.PROTECTED_PATHS"
    return (f"no_paths проекта {ctx.target} в targets.yaml и его агентская "
            f"обвязка: config.AGENT_WRAPPER_MARKERS и agent_wrapper записи")


def _gh_repo_kwargs(target_name: str, ctx) -> dict:
    """`--repo` для `gh`: форндж внешнего target'а — его `remote`; артель —
    без `--repo` (её `ctx.remote` — имя `origin`, не адрес форнджа). Признак
    — проект (`repo_context.is_artel`), не путь клона: путь у артели с
    этапа 2 ADR-0021 тоже клон. Адреса форджа артели взять неоткуда, не
    читая `targets.yaml` (SPEC 01M484RNV3QBDY3B0M16J916ZP, строка 18)."""
    if repo_context.is_artel(target_name) or ctx is None:
        return {}
    return {"repo": ctx.remote}


def ensure_draft_mr(conn, task_id: str, t) -> None:
    """Draft MR ветки задачи — ровно один раз за жизненный цикл (SPEC
    T079, требование 1, AC-1): идемпотентность несёт колонка
    `tasks.draft_mr_created`, не повторный запрос к GitHub на каждый
    повторный вход в `in_dev` (после замечаний ревью или reject из
    `verifying`) — дешевле и не зависит от сети на этих визитах.

    Канареечные задачи (`tasks/T065/SPEC.md`) пропускаются: синтетический
    прогон не должен заводить настоящие MR на настоящем GitHub на каждый
    запуск `canary` — заведение вне объёма ТЗ T079 (границы SPEC,
    «Не входит», песочница/креды — вне объёма).
    """
    if t["draft_mr_created"] or t["is_canary"]:
        return
    target_name = t["target"] or config.DEFAULT_TARGET
    if not _is_github_target(target_name):
        return
    try:
        entry = targets.target(target_name)
        base = entry["base"]
    except targets.TargetsError as exc:
        _incident(conn, task_id, "Draft MR FAILED", f"targets.yaml: {exc}")
        return
    # MR проекта с гейтом людей проекта открывает только `forge`
    # (`ensure_forge_draft_mr`, SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требование
    # 6; ответ Оператора ANSWER-2 п. 1): путь `gh` для него выключен.
    if targets.merged_by_project_people(entry):
        return

    # Репозиторный контекст target'а (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    # AC-6/AC-7; ADR-0021 п.1-2): push ветки идёт в клон target'а, включая
    # артель; `gh` внешнего target — в его форндж, self — без `--repo`
    # (прежнее поведение байт-в-байт).
    ctx = repo_context.resolve(target_name)
    repo = repo_context.path_or_none(ctx)
    gh_repo_kwargs = _gh_repo_kwargs(target_name, ctx)

    branch = t["branch"]
    # Пустая кодовая ветка — ДО push и ДО `gh pr create` (требование 8):
    # GitHub на ветку без коммитов относительно базы отвечает «No commits
    # between main and task/…», и до этой задачи заведомо отказной вызов
    # форджа становился инцидентом `github_adapter` (121 открытый за
    # 05.09–27.09). Признак `draft_mr_created` при пропуске НЕ выставляется:
    # следующий переход (в том числе рубеж `in_dev -> verifying`,
    # требование 9) пробует снова, уже с коммитом в ветке.
    if _commits_over_base(branch, base, repo=repo) == 0:
        store.journal(conn, task_id, "orchestrator", DRAFT_MR_SKIPPED_ACTION,
                      f"{branch}: нет коммитов относительно базы "
                      f"origin/{base} (свежий fetch) — черновик заведётся на "
                      f"первом переходе после первого коммита")
        return

    # CI ветки читает PLAN.md из origin: документы — раньше кода.
    artifact_branch.send_pending(task_id)
    push = gitcmd.in_repo(repo, "push", "-u", "origin", branch)
    if push is not None and gitcmd.IN_FLIGHT_LIMIT_REASON in (push.stderr or ""):
        # Отказ пределом отправок — штатная очередь, не сбой (SPEC
        # 01M5XZ9Z68XE2EKPDHYCAK25KF, требование 7; ANSWER-2 п. 4): причину
        # в журнал задачи уже записала точка отправки, алерта нет.
        return
    if push is None or push.returncode != 0:
        _incident(conn, task_id, "Draft MR FAILED",
                  f"git push -u origin {branch} не удался: "
                  f"{push.stderr.strip()[:300] if push is not None else 'git не ответил'}")
        return

    title = f"{task_id}: {t['title'] or task_id}"
    create = ci.gh("pr", "create", "--draft", "--title", title,
                   "--head", branch, "--base", base, "--body",
                   f"Draft MR задачи {task_id} (заведён автоматически "
                   f"GitHub-адаптером, SPEC T079).", **gh_repo_kwargs)
    if create is None or create.returncode != 0:
        detail = ((create.stderr or create.stdout).strip()[:300]
                  if create is not None else "gh не ответил")
        _incident(conn, task_id, "Draft MR FAILED", detail)
        return

    store.update_task(conn, task_id, draft_mr_created=1)
    store.journal(conn, task_id, "orchestrator", "Draft MR заведён",
                 create.stdout.strip()[:300])

    # Подсветка защищённых путей (A7, требование 7, AC-16): комментарий
    # на MR — в дополнение к предупреждению CI-job protected-paths, не
    # взамен него. Отказ комментария — не отказ Draft MR (та уже
    # заведена): incident тем же приёмом, что и остальные сбои модуля.
    # Перечень — проекта задачи (SPEC 01M45FK56DWMNBRKA1VWM12H19,
    # требование 2); контекст не разрешён — подсветки нет, как и
    # черновика выше (`push` в клон без контекста не дойдёт).
    protected = (_touched_protected_paths(
        branch, base, repo=repo, protected=repo_context.protected_paths(ctx))
        if ctx is not None else [])
    if protected:
        comment = ci.gh(
            "pr", "comment", branch, "--body",
            f"⚠️ Диф задачи {task_id} затрагивает защищённые пути: "
            f"{', '.join(protected)} ({_protected_paths_source(ctx)}).",
            **gh_repo_kwargs)
        if comment is None or comment.returncode != 0:
            detail = ((comment.stderr or comment.stdout).strip()[:300]
                      if comment is not None else "gh не ответил")
            _incident(conn, task_id, "MR protected-paths comment FAILED",
                      detail)


def ensure_head_in_origin(conn, task_id: str, branch: str) -> tuple[bool, str]:
    """Голова `branch` видна в origin — предусловие входа в `verifying`
    (`fsm_advance.py::in_dev`, ADR-0015 требование 2 — рубеж переехал с
    входа `review()`) и КАЖДОГО approve `merge_gate`
    (`fsm_merge_gate.py::_cmd_approve_merge_gate`) (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, 7): опрос CI по sha,
    которого origin не видел, висит до потолка ожидания вместо
    содержательного ответа (тот же класс инцидента, что решает эта
    задача).

    Сверяет ТОЧНЫЙ sha (`gitcmd.remote_branch_sha` vs
    `gitcmd.branch_head_sha`), не факт присутствия имени ветки в origin
    (AC-2) — устаревший коммит там не читается как «уже опубликован».
    Совпадают — no-op, без единой записи в журнал (AC-1/AC-8: «попытки
    push нет»). Расходятся — публикует голову тем же вызовом, которым
    ветка публикуется впервые (`ensure_draft_mr` выше, `git push -u
    origin <branch>`): успех журналируется и возвращает `(True, "")`
    (AC-3/AC-8); провал журналируется и возвращает `(False, <причина>)`
    с ИМЕНОВАННЫМ текстом причины, который SPEC требует байт-в-байт
    (AC-4/AC-9) — решение о смене состояния/эскалации на этом отказе
    остаётся за вызывающим кодом, сам хелпер состояние задачи не трогает.
    """
    target_name = store.task_target(conn, task_id) or config.DEFAULT_TARGET
    ctx = repo_context.resolve(target_name)
    repo = repo_context.path_or_none(ctx)
    local = gitcmd.branch_head_sha(branch, repo=repo)
    remote = gitcmd.remote_branch_sha(branch, repo=repo)
    if local and remote == local:
        return True, ""
    artifact_branch.send_pending(task_id)
    push = gitcmd.in_repo(repo, "push", "-u", "origin", branch)
    if push is None or push.returncode != 0:
        err = ((push.stderr or push.stdout).strip()[:300]
              if push is not None else "git не ответил")
        detail = f"голова ветки не в origin, push не удался: {err}"
        store.journal(conn, task_id, "orchestrator",
                      "push FAILED (голова не в origin)", detail)
        return False, detail
    store.journal(conn, task_id, "orchestrator", "push (голова не в origin)",
                 f"git push -u origin {branch}: "
                 f"{push.stdout.strip()[:300] or 'ok'}")
    _ensure_draft_mr_after_publish(conn, task_id, target_name, branch, local,
                                   repo)
    return True, ""


def _ensure_draft_mr_after_publish(conn, task_id: str, target_name: str,
                                   branch: str, head: str, repo) -> None:
    """Черновик запроса на слияние сразу за публикацией головы ветки (SPEC
    01M3HP7WAXKFK3GYZ3T6HX08M0, требование 9, AC-9).

    На прямом пути без возвратов вход в `in_dev` застаёт кодовую ветку
    пустой, и черновик там законно пропускается (требование 8) — а больше
    `_maybe_ensure_draft_mr` до `verifying` не зовётся ни разу: задача
    входила в `verifying` вовсе без запроса на слияние, при этом запись
    перехода обещала «MR готов — жду зелёного CI ветки», а CI шёл только по
    событию push (наблюдение 27.09). Рубеж `in_dev -> verifying`
    (`advance_gates/tests_writing.py::_origin_push_gate` -> функция выше) —
    первая точка, где коммит в ветке уже есть.

    Зовётся ТОЛЬКО с ветки успешного push, не с ветки «sha уже совпал»:
    та по SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ (AC-1/AC-8) обязана оставаться
    no-op без единого обращения к git и журналу.

    Условие «в ветке есть своя работа» здесь — самое дешёвое из
    достаточных: `head` (голову ветки функция выше уже прочитала) против
    головы базы target'а. Совпали — ветка ЕСТЬ база, открывать запрос на
    слияние не из чего, и рубеж `merge_gate`, куда этот же хелпер приходит
    на КАЖДЫЙ approve, не платит за новый побочный эффект ни чтением строки
    задачи, ни пробуждением адаптера. АВТОРИТЕТНУЮ сверку («коммит
    относительно базы», в том числе случай «ветка отстала от базы, своих
    коммитов ноль») несёт сама `ensure_draft_mr` — единственное место,
    решающее, трогать ли фордж (требование 8); второго такого решения здесь
    сознательно нет. Её же забота и остальные выходы: черновик уже заведён,
    канарейка, не github-target.

    База не прочитана (`targets.yaml` не годен) — ничего: то же поведение,
    что было до этой задачи. Инцидент на этом месте был бы вторым
    сообщением об одной поломке — первое уже напишет `ensure_draft_mr` на
    следующем входе в `in_dev`.
    """
    try:
        base = targets.target(target_name)["base"]
    except (targets.TargetsError, KeyError):
        return
    if head and head == gitcmd.branch_head_sha(base, repo=repo):
        return
    ensure_draft_mr(conn, task_id, store.get_task(conn, task_id))


def undraft_mr(conn, task_id: str, t) -> None:
    """Снимает Draft (SPEC T079, требование 2, AC-2) на входе в
    `merge_gate`; молчит, если Draft MR этой задачи не заводился
    (`ensure_draft_mr` не отработал, canary, forge не github)."""
    if not t["draft_mr_created"] or t["is_canary"]:
        return
    target_name = t["target"] or config.DEFAULT_TARGET
    if not _is_github_target(target_name):
        return
    branch = t["branch"]
    ctx = repo_context.resolve(target_name)
    gh_repo_kwargs = _gh_repo_kwargs(target_name, ctx)
    ready = ci.gh("pr", "ready", branch, **gh_repo_kwargs)
    if ready is None or ready.returncode != 0:
        detail = ((ready.stderr or ready.stdout).strip()[:300]
                  if ready is not None else "gh не ответил")
        _incident(conn, task_id, "MR undraft FAILED", detail)
        return
    store.journal(conn, task_id, "orchestrator", "MR снят с Draft",
                 ready.stdout.strip()[:300] or "ok")


# MR через `forge` проекта с гейтом людей проекта (`merge_gate:
# target-human`, SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требования 4, 6; ADR-0029
# п. 1, 7): одна функция открытия MR и одно описание — для чернового MR на
# входе в `verifying` и для MR гейта мержа.
MR_OPENED_ACTION = "MR открыт"
MR_ASSIGNEE_ACTION = "исполнитель MR"
ASSIGNEE_NOT_NUMERIC = "исполнитель не числовой id — не назначен"
DRAFT_MR_REFUSAL_ACTION = "переход отклонён: черновой MR не открыт"
# Отказ `approve` гейта мержа пределом `policy.max_awaiting` — его читает
# строка `status` (`catalog`), пишет гейт мержа.
AWAITING_LIMIT_ACTION = "approve отклонён: предел awaiting_human"


def people_entry(target_name: str) -> dict | None:
    """Запись проекта, MR которого вливают люди проекта
    (`targets.merged_by_project_people`); None — гейт иной или запись не
    читается."""
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return entry if targets.merged_by_project_people(entry) else None


def mr_assignee(policy: dict) -> tuple[int | None, str]:
    """(id исполнителя для `forge`, запись журнала о неназначенном): id —
    только целое (`targets.delivery_policy` уже сделал целым строку цифр);
    иное значение и отсутствие поля — без исполнителя с записью."""
    value = policy.get("mr_assignee")
    if isinstance(value, int) and not isinstance(value, bool):
        return value, ""
    if value is None:
        return None, f"{ASSIGNEE_NOT_NUMERIC}: policy.mr_assignee не задан"
    return None, f"{ASSIGNEE_NOT_NUMERIC}: policy.mr_assignee = {value!r}"


def mr_description(task_id: str, branch: str, head: str, repo,
                   protected) -> str:
    """Описание MR: защищённые пути проекта, изменённые веткой до `head`
    (дифф от базы сравнения ветки), — не весь перечень проекта. Описание
    пишется только при открытии: правки описания в интерфейсе `forge`
    нет. Git не ответил — описание без подсветки (подсветка — сведение, не
    условие MR)."""
    base = gitcmd.diff_base(branch, repo=repo)
    files = gitcmd.diff_names(base, head, repo=repo) if base and head else None
    touched = [p for p in files or [] if config.is_protected_path(p, protected)]
    text = (f"MR задачи {task_id}: открыт пультом Артели, вливают люди "
            f"проекта.")
    if touched:
        text += (f"\n\n⚠️ Ветка изменяет защищённые пути проекта: "
                 f"{', '.join(touched)}.")
    return text


def open_forge_mr(conn, task_id: str, t, head: str, *,
                  draft: bool) -> forge.MergeRequest:
    """Открывает MR ветки задачи в `base` её проекта через `forge`; успех —
    ссылка (`iid`, `web_url`) в столбцах задачи и в журнале, запись о
    неназначенном исполнителе. Отказ хостинга — результат с `reason`,
    ссылка не пишется; решение — за вызывающим."""
    target_name = t["target"] or config.DEFAULT_TARGET
    try:
        entry = targets.target(target_name)
    except targets.TargetsError as exc:
        return forge.MergeRequest(reason=f"targets.yaml: {exc}")
    ctx = repo_context.resolve(target_name)
    repo = repo_context.path_or_none(ctx)
    protected = repo_context.protected_paths(ctx) if ctx is not None else ()
    assignee, note = mr_assignee(targets.delivery_policy(entry))
    body = mr_description(task_id, t["branch"], head, repo, protected)
    title = f"{task_id}: {t['title'] or task_id}"
    result = forge.open_mr(target_name, t["branch"], entry["base"], title,
                           body, draft, assignee)
    if result.reason:
        return result
    store.set_mr_link(conn, task_id, result.iid, result.url)
    kind = "черновой MR" if draft else "MR"
    store.journal(conn, task_id, "orchestrator", MR_OPENED_ACTION,
                  f"{kind} !{result.iid} {result.url or ''} ветки "
                  f"{t['branch']} в {entry['base']} (голова {head})")
    if note:
        store.journal(conn, task_id, "orchestrator", MR_ASSIGNEE_ACTION, note)
    return result


def ensure_forge_draft_mr(conn, task_id: str, t) -> str | None:
    """Черновой MR через `forge.open_mr(draft=True)` на входе в
    `verifying` (SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требование 6) — проект с
    гейтом людей проекта и `draft_mr: true`, ссылки на MR в БД нет. Зовётся
    после публикации головы ветки при любом её исходе — и тогда, когда
    голова уже была на сервере: отказ прошлого входа повторяется.

    None — черновик открыт, уже есть или не нужен; иначе причина отказа
    хостинга."""
    if t["is_canary"]:
        return None
    target_name = t["target"] or config.DEFAULT_TARGET
    entry = people_entry(target_name)
    if entry is None or not targets.delivery_policy(entry)["draft_mr"]:
        return None
    row = store.get_task(conn, task_id)
    if store.mr_link(row)[0] is not None:
        return None
    ctx = repo_context.resolve(target_name)
    head = gitcmd.branch_head_sha(t["branch"],
                                  repo=repo_context.path_or_none(ctx))
    result = open_forge_mr(conn, task_id, row, head, draft=True)
    return result.reason or None
