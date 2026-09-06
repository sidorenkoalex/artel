"""Пакет orchestrator/doctor -- сверка артефактной ветки: родитель первого
коммита, синхронность с origin, CI (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH,
01M1TQ0X14Y5B3C87WC0Q31PK2).

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import json

from orchestrator import doctor


def _artifact_branch_first_commit_parent(branch: str) -> str:
    """Родитель самого раннего коммита `branch`, целиком авторства
    плотницкой записи артефактной ветки (`fixation.FIXATION_AUTHOR_EMAIL`
    — единственный автор, которым `artifact_branch.write_commit` подписывает
    ЛЮБОЙ коммит этой ветки, ни один вызывающий код не переопределяет его):
    граница между собственной историей ветки и унаследованным `main`/
    `origin` на момент её создания (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH,
    AC-5). Обход — от головы `branch` назад по первому родителю, пока автор
    совпадает; последний совпавший — искомый ранний коммит, его родитель и
    есть ответ.

    Пустая строка — `branch` пуста, ни один коммит не авторства плотницкой
    записи, либо git не ответил.
    """
    res = doctor.gitcmd.git("log", "--format=%H %ae", "--first-parent", branch)
    if res is None or res.returncode != 0:
        return ""
    boundary = ""
    for line in res.stdout.splitlines():
        sha, _, email = line.partition(" ")
        if email != doctor.fixation.FIXATION_AUTHOR_EMAIL:
            break
        boundary = sha
    if not boundary:
        return ""
    parent = doctor.gitcmd.git("rev-parse", "--verify", "--quiet", f"{boundary}^")
    if parent is None or parent.returncode != 0:
        return ""
    return parent.stdout.strip()


def check_artifact_branch_parent_ancestry(conn) -> list[doctor.Check]:
    """Родитель первого коммита артефактной ветки живой задачи обязан быть
    предком `origin/main` (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH, требование 3,
    AC-5) — иначе ветка заведена от устаревшего/расходящегося пина главной
    копии (инцидент 06.09) и несёт в `tasks/` содержимое, которого уже
    могло не быть в `origin` (в т.ч. удалённые оттуда черновики).

    `origin` недоступен (нет сети, `origin` не настроен, песочница) —
    `skip` целиком: сверять не с чем (тот же приём деградации, что и у
    `check_branch_freshness`, когда `gitcmd.commits_behind` вернул `None`).
    Не incident (тем же доводом, что `check_branch_freshness`/
    `check_target_layout`): расхождение — состояние, требующее внимания
    Оператора, не операционный дефект с жизненным циклом ack.
    """
    origin_head, reason = doctor.gitcmd.fetch_head_sha("origin", doctor.config.MAIN_BRANCH)
    if not origin_head:
        return [doctor.Check("artifact-branch-parent-ancestry", "skip",
                      f"origin недоступен: {reason}")]
    warnings = []
    for t in doctor.store.all_tasks(conn):
        if t["state"] in ("done", "killed"):
            continue
        branch = doctor.artifact_branch.branch_name(t["id"])
        if not doctor.gitcmd.branch_exists(branch):
            continue
        parent = doctor._artifact_branch_first_commit_parent(branch)
        if not parent:
            continue
        res = doctor.gitcmd.git("merge-base", "--is-ancestor", parent, origin_head)
        if res is None or res.returncode not in (0, 1):
            continue
        if res.returncode == 1:
            warnings.append(doctor.Check(
                "artifact-branch-parent-ancestry", "warn",
                f"{t['id']}: родитель первого коммита артефактной ветки "
                f"{parent[:12]} не предок origin/main {origin_head[:12]}"))
    if warnings:
        return warnings
    return [doctor.Check("artifact-branch-parent-ancestry", "ok",
                  "родитель первого коммита артефактной ветки каждой живой "
                  "задачи — предок origin/main")]


# --- сверка артефактной ветки с origin/CI (SPEC ---------------------------
# 01M1TQ0X14Y5B3C87WC0Q31PK2, требования 3-4) ------------------------------

def _artifact_branch_candidates(conn):
    """Нетерминальные задачи target artel (требования 3-4: обе новые
    проверки касаются только их — терминальная задача уже не живёт, а
    внешний target пушит и гоняет CI своей веткой, не этой)."""
    return [t for t in doctor.store.all_tasks(conn)
           if t["target"] == doctor.config.DEFAULT_TARGET
           and t["state"] not in ("done", "killed")]


def _is_ancestor(maybe_ancestor: str, descendant: str) -> bool | None:
    """`True`/`False` — является ли `maybe_ancestor` предком `descendant`
    в истории git; `None` — git не ответил (сбой процесса, а не «нет» —
    `merge-base --is-ancestor` отвечает кодом 1 на честное «нет», не
    ошибкой)."""
    res = doctor.gitcmd.git("merge-base", "--is-ancestor", maybe_ancestor, descendant)
    if res is None:
        return None
    if res.returncode == 0:
        return True
    if res.returncode == 1:
        return False
    return None


def _sync_direction(branch: str, local_sha: str, origin_sha: str) -> str:
    """Направление расхождения `artifact/<id>` (SPEC требование 3, AC-6):
    «локальный отстаёт» — origin ушёл вперёд (Оператор коммитил прямо в
    origin, инцидент 06.09); «origin отстаёт» — локальный ушёл вперёд
    (роль закоммитила, push ещё не случился/отказал); «разошлись» — ни
    один не предок другого (независимые коммиты от общего предка).

    `origin_sha` получен `ls-remote` (`gitcmd.remote_branch_sha`) — сам
    коммит-объект origin при этом может отсутствовать в локальной
    объектной базе пульта (внешний коммит Оператора мимо пульта никогда
    сюда не приезжал), и `merge-base --is-ancestor` без него откажет
    кодом 128 на обеих сверках, что без разбора выглядело бы как
    «разошлись» даже для чисто линейного расхождения. `fetch -q origin
    <branch>` подтягивает нужные объекты БЕЗ подвижки локального ref
    (пишет только `FETCH_HEAD`) — сверка ancestry дальше идёт по самим
    sha, не по `FETCH_HEAD`. Отказ fetch (сеть/`gh` недоступны) —
    деградация в «разошлись» та же, что и у отказа самого merge-base
    (риск, PLAN «Риски»)."""
    doctor.gitcmd.git("fetch", "-q", "origin", branch)
    if doctor._is_ancestor(local_sha, origin_sha) is True:
        return "локальный отстаёт"
    if doctor._is_ancestor(origin_sha, local_sha) is True:
        return "origin отстаёт"
    return "разошлись"


def check_artifact_branch_sync(conn) -> list[doctor.Check]:
    """«Артефактная ветка синхронна» (SPEC требование 3, AC-6): сравнивает
    локальный `artifact/<id>` и `origin/artifact/<id>` для каждой
    нетерминальной задачи target artel — источник инцидента 06.09
    («расхождение происходит между локальным `refs/heads/artifact/<id>`
    пульта и его же origin»). `gitcmd.remote_branch_sha` читает origin
    ЖИВЫМ `ls-remote`, не локальный tracking-ref — ровно то, что нужно
    против внешнего коммита Оператора мимо пульта, о котором локальный
    tracking-ref не узнал бы без `git fetch`.

    Задача без локальной артефактной ветки вовсе (ещё не создана) —
    молча пропускается: сверять нечего, не отказ. Origin недоступен
    (`gitcmd.has_no_remote`) или ветки там ещё нет/ответа не было —
    `skip` с причиной, не `ok`/`warn` по несуществующим данным (AC-6,
    тест `test_ac6_skip_without_origin_with_a_reason` — недоступность
    origin не имеет права трактоваться как «совпадает», fail-open)."""
    checks = []
    for t in doctor._artifact_branch_candidates(conn):
        task_id = t["id"]
        branch = doctor.artifact_branch.branch_name(task_id)
        local_sha = doctor.gitcmd.branch_head_sha(branch)
        if not local_sha:
            continue
        if doctor.gitcmd.has_no_remote(doctor.config.ROOT):
            checks.append(doctor.Check(
                "artifact-branch-sync", "skip",
                f"{task_id}: origin пульта не настроен — сверка "
                f"артефактной ветки {branch} невозможна"))
            continue
        origin_sha = doctor.gitcmd.remote_branch_sha(branch)
        if not origin_sha:
            checks.append(doctor.Check(
                "artifact-branch-sync", "skip",
                f"{task_id}: origin/{branch} недоступен или не ответил"))
            continue
        if local_sha == origin_sha:
            checks.append(doctor.Check(
                "artifact-branch-sync", "ok",
                f"{task_id}: артефактная ветка {branch} синхронна с "
                f"origin (sha {local_sha})"))
            continue
        direction = doctor._sync_direction(branch, local_sha, origin_sha)
        checks.append(doctor.Check(
            "artifact-branch-sync", "warn",
            f"{task_id}: артефактная ветка {branch} разошлась с origin — "
            f"локальный {local_sha}, origin {origin_sha} ({direction})"))
    return checks


# Поля `--json`, которые запрашивает эта проверка у `gh run list` — те же
# `headBranch,status,conclusion`, что уже читает `ci.run_list` (SPEC
# требование 4: «через gh run list, как уже делает verifying»), плюс
# `name`/`workflowName` — имя упавшей джобы для `warn` (AC-7). Отдельный
# запрос, не правка `ci.run_list` — `orchestrator/ci.py` не входит в зону
# этой задачи (PLAN «Подход»), а `ci.gh` уже публичная точка входа,
# которую подменяют и приёмочные тесты этой задачи, и `ci.run_list` сама.
_ARTIFACT_BRANCH_CI_JSON_FIELDS = "headBranch,status,conclusion,name,workflowName"


def _artifact_branch_ci_runs(branch: str) -> tuple[list | None, str]:
    """Прогоны `gh run list` по ветке `branch`; (None, причина) — `gh`/сеть
    недоступны или ответ не разобрать (тот же разбор, что `ci.run_list`)."""
    res = doctor.ci.gh("run", "list", "--branch", branch, "--json",
               doctor._ARTIFACT_BRANCH_CI_JSON_FIELDS, "--limit",
               str(doctor.config.CI_RUN_LIST_LIMIT))
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return None, f"gh run list не ответил: {detail or f'код {res.returncode}'}"
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, f"ответ gh run list не разобран: {exc}"
    if not isinstance(payload, list):
        return None, "в ответе gh run list нет списка запусков"
    return payload, ""


def check_artifact_branch_ci(conn) -> list[doctor.Check]:
    """«CI артефактной ветки» (SPEC требование 4, AC-7): последний прогон
    `gh run list` по ветке `artifact/<id>` для каждой нетерминальной
    задачи target artel — источник инцидента 06.09 («CI артефактных
    веток семи задач был красный... и это ни на что не повлияло:
    зелёность CI артефактной ветки нигде не читается»). Чисто
    информационная (PLAN «Влияние на систему»): ни одна ветка кода не
    зовёт эту функцию из гейта FSM — красный исход здесь никогда не
    блокирует переход, только видимость Оператору через `doctor`.

    `gh`/сеть недоступны, прогонов нет вовсе или последний ещё не
    завершился — `skip` (недоступность/отсутствие ответа не может стать
    ни `ok`, ни `warn` — fail-open по несуществующим данным ровно
    воспроизвёл бы инцидент, AC-7 «gh/сеть недоступны — skip»)."""
    checks = []
    for t in doctor._artifact_branch_candidates(conn):
        task_id = t["id"]
        branch = doctor.artifact_branch.branch_name(task_id)
        runs, why = doctor._artifact_branch_ci_runs(branch)
        if runs is None:
            checks.append(doctor.Check(
                "artifact-branch-ci", "skip",
                f"{task_id}: CI ветки {branch} не проверен — {why}"))
            continue
        if not runs:
            checks.append(doctor.Check(
                "artifact-branch-ci", "skip",
                f"{task_id}: у ветки {branch} нет ни одного прогона CI"))
            continue
        run = runs[0]
        if run.get("status") != "completed":
            checks.append(doctor.Check(
                "artifact-branch-ci", "skip",
                f"{task_id}: CI ветки {branch} ещё идёт"))
            continue
        sha = doctor.gitcmd.branch_head_sha(branch)
        if run.get("conclusion") in doctor.ci.GREEN:
            checks.append(doctor.Check(
                "artifact-branch-ci", "ok",
                f"{task_id}: CI ветки {branch} зелёный (sha {sha})"))
        else:
            job = run.get("name") or run.get("workflowName") or "?"
            checks.append(doctor.Check(
                "artifact-branch-ci", "warn",
                f"{task_id}: CI ветки {branch} не зелёный (sha {sha}), "
                f"джоба {job}"))
    return checks
