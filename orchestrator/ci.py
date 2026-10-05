"""Статус CI головного коммита ветки задачи — условие merge (SPEC T017, 6).

До T017 «CI зелёный» на гейте merge проверял глазами Оператор, а код мержил
что дадут. Теперь статус спрашивает код, и молчание CI трактуется как запрет:
неизвестный статус — не зелёный. Иначе первый же сломанный `gh` возвращал бы
систему к «смержим, посмотрим потом».

С T018 «неизвестен» включает и неполный ответ: проверки читаются постранично
и сверяются с `total_count`, потому что решение по первой странице делало
упавшую 31-ю проверку невидимой.
"""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from scripts import ci_push_class

from . import config, gitcmd, workspace

# Заключения проверок, считающиеся зелёными. `skipped` обязателен: job
# `protected-paths` идёт только на pull_request и на push репозитория
# пропускается — без него зелёного CI не бывало бы вовсе.
GREEN = {"success", "skipped", "neutral"}


def gh(*args: str, timeout: int | None = None,
      repo: str | None = None) -> subprocess.CompletedProcess:
    """`gh` в корне репозитория; отсутствие CLI — такой же ненулевой код.

    Как и в `gitcmd.git`: разбирает исход вызывающий, а «команды нет»,
    «команда ответила ошибкой» и «команда не ответила вовсе» для гейта
    означают одно — ответа нет. Предел ожидания обязателен: гейт merge стоит
    на живом пути Оператора, и молчащая сеть не должна вешать `approve`
    без вывода и без конца. `timeout` по умолчанию — `GH_TIMEOUT_SEC`
    (короткий REST-опрос); `trigger_rerun` передаёт свой, куда больший —
    `gh run watch` реально ждёт завершения workflow, не ответа API.

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-2) — адрес форджа
    (`targets.yaml[target]["url"]`) внешнего target: дописывает `--repo
    <repo>` в конец argv, `gh` резолвит владельца/репозиторий по нему,
    не по remote `cwd`. `None` (по умолчанию, self) — argv и `cwd`
    байт-в-байт как до этой задачи, флаг не добавляется вовсе.
    """
    timeout_sec = config.GH_TIMEOUT_SEC if timeout is None else timeout
    full_args = (*args, "--repo", repo) if repo else args
    try:
        return subprocess.run(["gh", *full_args], cwd=config.ROOT,
                              capture_output=True, text=True,
                              timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 1, "", f"gh молчал дольше {timeout_sec} с")
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def _repo_kwargs(repo: Path | None) -> dict:
    """`repo=` для внутренних вызовов модуля: клон артели — умолчание этих
    функций, поэтому для него (и для `None`) вызов идёт прежней формой без
    `repo` — подмены `head_sha`/`first_parent_line` в тестах пульта
    написаны под неё, в том числе `lambda branch:` защищённого
    `tests/test_invariants.py::MergeNeedsGreenCiTest` (инвариант 19);
    внешний клон и любой другой репозиторий (главная копия у `pin-update`
    и `doctor main-ci`) передаются явно. Исход тот же: умолчание этих
    функций — тот же клон артели."""
    if repo is None or repo == workspace.repo(config.DEFAULT_TARGET):
        return {}
    return {"repo": repo}


def head_sha(branch: str, repo: Path | None = None) -> tuple[str, str]:
    """Sha головного коммита ветки задачи и причина, если его нет.

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-3; ADR-0021 п.1-2) — клон,
    в котором читается голова (путь, не URL — в отличие от `repo=` у
    `gh`). `None` (по умолчанию) — клон артели (`workspace.repo
    (config.DEFAULT_TARGET)`), не `config.ROOT`: прежние вызовы без
    `repo` всегда были self-target.
    """
    if repo is None:
        repo = workspace.repo(config.DEFAULT_TARGET)
    args = ("rev-parse", "--verify", f"refs/heads/{branch}")
    res = gitcmd.in_repo(repo, *args)
    sha = res.stdout.strip() if res.returncode == 0 else ""
    if not sha:
        return "", (f"головной коммит ветки {branch} не определён: "
                    f"{res.stderr.strip()[:200] or 'git не ответил'}")
    return sha, ""


def check_runs_page(sha: str, page: int,
                    repo: str | None = None) -> tuple[dict | None, str]:
    """Одна страница проверок коммита; (None, причина) — ответа нет.

    `repo` — адрес форджа (`gh --repo`, SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    AC-2), тот же смысл, что у `gh(repo=...)`. `repo=None` (по умолчанию)
    не подставляется дальше как явная kwarg — байт-в-байт прежний вызов
    `gh(...)`, который существующие заглушки-моки этого модуля (сигнатура
    `(*args)`, без `**kwargs`) продолжают понимать."""
    res = gh("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs"
                    f"?per_page={config.CI_CHECKS_PER_PAGE}&page={page}",
            **({"repo": repo} if repo else {}))
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return None, f"gh не ответил: {detail or f'код {res.returncode}'}"
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, f"ответ gh не разобран: {exc}"
    runs = payload.get("check_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or not all(isinstance(r, dict) for r in runs):
        return None, "в ответе gh нет списка check_runs"
    return payload, ""


def check_runs(sha: str) -> tuple[list | None, str]:
    """Все проверки коммита из GitHub API; (None, причина) — статуса нет.

    Ответ читается постранично и сверяется с `total_count` того же ответа:
    список короче обещанного — это «статуса нет», а не «упавших не видно».
    Решение по первой странице делало 31-ю проверку невидимой — единственный
    вход, где неизвестный статус читался как зелёный вопреки инварианту 19
    (SPEC T018, требования 1–2).

    `total_count` в ответе не названо — сверять полноту не с чем: последней
    считается страница короче запрошенного размера. Это поведение до T018,
    и оно остаётся только для такого ответа; настоящий GitHub счётчик отдаёт.

    Сверка `len(runs) != total` ниже — НЕ гарантия отсутствия дублей: она
    считает записи, не различая их по `id` (SPEC T034, требование 3, ревью
    T018 замечание 1 итерации 1). Повтор одной и той же страницы, где число
    дублей случайно совпало с `total_count`, читался бы как полный ответ.
    Настоящий GitHub API такого не отдаёт (номер страницы двигает выдачу);
    против гипотетического сбоя пагинации сверка защиты не даёт умышленно —
    добавление дедупликации по `id` потребовало бы такого же поля у всех
    существующих тестов модуля (`tests/test_ci_status.py`, хелпер `run()`),
    которые сейчас его не носят, — цена дороже гипотетического сценария.
    """
    runs: list = []
    total = None
    for page in range(1, config.CI_CHECKS_MAX_PAGES + 1):
        payload, why = check_runs_page(sha, page)
        if payload is None:
            return None, why
        if page == 1:
            total = payload.get("total_count")
            # bool — подтип int, а `total_count: true` числом проверок
            # не является: неразобранный счётчик тоже «статус неизвестен».
            if total is not None and (isinstance(total, bool)
                                      or not isinstance(total, int)
                                      or total < 0):
                return None, f"в ответе gh нечисловой total_count: {total!r}"
        page_runs = payload["check_runs"]
        runs.extend(page_runs)
        if total is None:
            if len(page_runs) < config.CI_CHECKS_PER_PAGE:
                return runs, ""
        elif len(runs) >= total or len(page_runs) < config.CI_CHECKS_PER_PAGE:
            # Ответ либо сошёлся с обещанным числом, либо иссяк раньше него.
            break
    else:
        return None, (f"проверок больше, чем помещается в "
                      f"{config.CI_CHECKS_MAX_PAGES} страниц по "
                      f"{config.CI_CHECKS_PER_PAGE}")
    if len(runs) != total:
        return None, (f"получено {len(runs)} проверок из {total} обещанных — "
                      f"список неполон")
    return runs, ""


def run_list(branch: str, repo: str | None = None) -> tuple[list | None, str]:
    """Запуски `gh run list` по ветке; (None, причина) — ответа нет.

    Второй источник статуса CI для `verifying` (роадмап P3, T040; SPEC
    T079, требование 5, AC-6/AC-7): задержка события GitHub оставляет
    check-runs коммита временно пустыми, хотя запуск по ветке уже виден.
    Литерал `run`/`list` в argv — прямая цитата требования 5 («gh run
    list по ветке»), не домысел интерфейса.

    `repo` — адрес форджа (`gh --repo`, SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    AC-3), тот же смысл, что у `gh(repo=...)`. `repo=None` (по умолчанию)
    не подставляется дальше как явная kwarg — тот же довод, что у
    `check_runs_page` выше."""
    res = gh("run", "list", "--branch", branch, "--json",
             "headBranch,status,conclusion", "--limit",
             str(config.CI_RUN_LIST_LIMIT), **({"repo": repo} if repo else {}))
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


# Четыре исхода requirement 5 SPEC T079 (AC-5..AC-8): зелёный, «проверок
# нет вовсе», «проверки идут» (в т.ч. по gh run list), «CI красный».
VERIFYING_GREEN = "green"
VERIFYING_NONE = "none"
VERIFYING_RUNNING = "running"
VERIFYING_RED = "red"
# Пятый исход (SPEC 01M3Y75C9TY76083CG1PK00EM4, требование 2): проверка без
# исхода висит дольше `config.CI_STUCK_CHECK_MINUTES`. Не зелёный и не
# красный — задачу не двигает, но `ci-rerun` в нём перезапускает прогон.
VERIFYING_STUCK = "stuck"
# Начало `note` исхода «голова ветки не в origin» (HTTP 422) у
# `verifying_status` — вход `verifying_head_not_in_origin` ниже. Исход сам
# остаётся `VERIFYING_NONE`: для остальных потребителей это «проверок нет».
HEAD_NOT_IN_ORIGIN_NOTE = "голова ветки не в origin"

# Статусы check-run'а, в которых проверка может зависнуть (требование 2).
_STUCK_STATUSES = {"in_progress", "queued"}

# Ссылка на зависшую проверку в `note` исхода `VERIFYING_STUCK` — вход
# `stuck_check_ids` ниже, тот же приём, что `_RED_NOTE_SHA_RE`.
_STUCK_NOTE_ID_RE = re.compile(r"check-run id (\d+)")


def check_finished(run: dict) -> tuple[bool, str]:
    """(Завершена ли проверка, строка журнала о прочтении вопреки `status`
    или "") — единственное место правила «проверка завершена» для
    `verifying_status` и `branch_status` (SPEC 01M3Y75C9TY76083CG1PK00EM4,
    требование 1).

    GitHub отдаёт check-run с `status=in_progress` при уже известных
    `conclusion` и `completed_at` (инцидент 02.10, задача
    01M3XTFJCC5TG63FHW907GQM4D простояла полтора часа): по одному `status`
    такая проверка «идёт» вечно. Исход и время завершения заданы оба —
    проверка закончилась, и решать по ней надо её `conclusion`. Одно из
    двух без другого — не повод: `status` остаётся главным признаком, а
    поверить ему вопреки — решение, которое журнал называет отдельной
    строкой.
    """
    status = run.get("status")
    if status == "completed":
        return True, ""
    conclusion, completed_at = run.get("conclusion"), run.get("completed_at")
    if conclusion and completed_at:
        return True, (f"{run.get('name', '?')}: GitHub отдаёт status={status} "
                      f"при conclusion={conclusion}, "
                      f"completed_at={completed_at} — считаю завершённой")
    return False, ""


def _unfinished_checks(runs: list) -> tuple[list, list[str]]:
    """(Незавершённые check-run'ы, строки о прочтённых вопреки `status`) —
    по `check_finished`, общему для обоих читателей статуса."""
    unfinished, reread = [], []
    for run in runs:
        finished, line = check_finished(run)
        if not finished:
            unfinished.append(run)
        if line:
            reread.append(line)
    return unfinished, reread


def _with_reread(note: str, reread: list[str]) -> str:
    """`note` статуса и строки о прочтённых вопреки `status` — каждая своей
    строкой (требование 1): итог остаётся первой строкой, на которой
    стоят разборы `verifying_is_red`/`status_kind`/`red_status_sha`."""
    return "\n".join([note, *reread])


def _check_age_minutes(run: dict, now: datetime) -> float | None:
    """Возраст check-run'а в минутах от `started_at`, без него — от
    `created_at` (требование 2); None — ни одна отметка не разобрана."""
    stamp = run.get("started_at") or run.get("created_at")
    if not isinstance(stamp, str):
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (now - moment).total_seconds() / 60


def _stuck_checks(unfinished: list, index: "_RunIndex | None") -> list[str]:
    """Описания зависших проверок среди незавершённых: `in_progress`/
    `queued` без `conclusion` старше `config.CI_STUCK_CHECK_MINUTES`.

    Описание несёт имя, id check-run'а (по нему `ci-rerun` находит прогон
    workflow) и возраст — Оператор отличает зависшую проверку от идущей и
    находит её в GitHub (требование 2, AC-6) — и событие с номером её
    прогона (SPEC 01M46D5ZZQY7GBEW5TBVQ0P3ZV, AC-2): номер прогона стоит
    не в форме «check-run id», и `stuck_check_ids` его не берёт.
    """
    now = datetime.now(timezone.utc)
    stuck = []
    for run in unfinished:
        if run.get("status") not in _STUCK_STATUSES or run.get("conclusion"):
            continue
        age = _check_age_minutes(run, now)
        if age is None or age <= config.CI_STUCK_CHECK_MINUTES:
            continue
        stuck.append(f"{run.get('name', '?')} (check-run id {run.get('id')}, "
                     f"status={run.get('status')}; "
                     f"{_run_label(run, index)}) висит {int(age)} мин "
                     f"без исхода")
    return stuck


# Событие и номер workflow-прогона проверки (SPEC 01M46D5ZZQY7GBEW5TBVQ0P3ZV).
# На один sha бывают два прогона одного workflow (push и pull_request) с
# одноимёнными проверками; текст без события не говорил, какой из двух
# логов читать (05.10, голова 8ddb330d: push зелёный, pull_request красный).
# Check-run события не несёт — его отдаёт прогон коммита.
UNDEFINED_EVENT = "событие не определено"

# Ссылка check-run'а задания Actions: `…/actions/runs/<id прогона>/job/<id>`.
_RUN_URL_RE = re.compile(r"/actions/runs/(\d+)(?:/|$)")


class _RunIndex(NamedTuple):
    """Прогоны коммита: по `check_suite_id` и по id прогона."""
    by_suite: dict
    by_id: dict


def _int_or_none(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) \
        else None


def _check_suite_id(check: dict) -> int | None:
    suite = check.get("check_suite")
    return _int_or_none(suite.get("id")) if isinstance(suite, dict) else None


def _url_run_id(check: dict) -> int | None:
    for key in ("details_url", "html_url"):
        url = check.get(key)
        match = _RUN_URL_RE.search(url) if isinstance(url, str) else None
        if match:
            return int(match.group(1))
    return None


def _commit_workflow_runs(sha: str, checks: list) -> _RunIndex | None:
    """Прогоны коммита для подписи его проверок; `None` — подписывать нечем.

    `None` и при сбое запроса (код `gh`, неразборный ответ), и когда ни
    один check-run не несёт связки с прогоном (`check_suite.id` или ссылки
    на прогон): сопоставлять тогда не с чем, а запрос был бы лишним. Исход
    статуса от этого не зависит — проверки подписываются «событие не
    определено» (требование 3).
    """
    if not any(_check_suite_id(c) is not None or _url_run_id(c) is not None
               for c in checks):
        return None
    res = gh("api", f"repos/{{owner}}/{{repo}}/actions/runs"
                    f"?head_sha={sha}&per_page={config.CI_RUNS_PER_PAGE}")
    if res.returncode != 0:
        return None
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return None
    index = _RunIndex({}, {})
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = _int_or_none(run.get("id", run.get("databaseId")))
        if run_id is None:
            continue
        index.by_id[run_id] = run
        suite = _int_or_none(run.get("check_suite_id"))
        if suite is not None:
            index.by_suite[suite] = run
    return index


def _run_of(check: dict, index: _RunIndex | None) -> dict | None:
    """Прогон check-run'а: по `check_suite.id`, иначе по ссылке на прогон."""
    if index is None:
        return None
    run = index.by_suite.get(_check_suite_id(check))
    if run is None:
        run = index.by_id.get(_url_run_id(check))
    return run


def _run_event(check: dict, index: _RunIndex | None) -> str:
    run = _run_of(check, index)
    event = run.get("event") if run is not None else None
    return event if isinstance(event, str) and event else ""


def _run_label(check: dict, index: _RunIndex | None) -> str:
    """«<событие>, прогон <id прогона>»; событие не узнано — «событие не
    определено» (с номером прогона, если он известен из ссылки)."""
    run = _run_of(check, index)
    run_id = (_int_or_none(run.get("id", run.get("databaseId")))
              if run is not None else None) or _url_run_id(check)
    event = _run_event(check, index)
    head = event or UNDEFINED_EVENT
    return f"{head}, прогон {run_id}" if run_id is not None else head


def _event_divergence(checks: list, index: _RunIndex | None,
                      where: str = "") -> list[str]:
    """Проверки, исполнившиеся зелёными в прогоне одного события и
    красными в прогоне другого (требование 2, AC-6): «<имя><where> —
    зелёная в <события>, красная в <события>». `skipped` зелёным исходом
    здесь не считается: проверка не исполнялась.

    Текст не несёт подстрок, на которых стоят разборщики статуса («не
    зелёный:», «ещё идёт», «неизвестен», «check-run id»)."""
    green: dict[str, list[str]] = {}
    red: dict[str, list[str]] = {}
    for check in checks:
        event = _run_event(check, index)
        if not event or not check_finished(check)[0]:
            continue
        conclusion = check.get("conclusion")
        if conclusion in _EXECUTED_GREEN:
            side = green
        elif conclusion not in GREEN:
            side = red
        else:
            continue
        events = side.setdefault(str(check.get("name", "?")), [])
        if event not in events:
            events.append(event)
    items = []
    for name, red_events in red.items():
        green_events = green.get(name, [])
        if any(g != r for g in green_events for r in red_events):
            items.append(f"{name}{where} — зелёная в {', '.join(green_events)}"
                         f", красная в {', '.join(red_events)}")
    return items


def _divergence_phrase(items: list[str]) -> str:
    """Отдельная фраза о расхождении исхода по событиям, "" — его нет."""
    return (f"; исход по событиям расходится: {'; '.join(items)}"
            if items else "")


def _failed_listing(failed: list, index: _RunIndex | None) -> str:
    """«<имя>=<заключение> (<событие>, прогон <id>)» по каждому check-run'у
    (AC-1)."""
    return ", ".join(f"{r.get('name', '?')}={r.get('conclusion')} "
                     f"({_run_label(r, index)})" for r in failed)


def _running_listing(unfinished: list, index: _RunIndex | None) -> str:
    """«<имя> (<событие>, прогон <id>)» по каждой идущей проверке (AC-2)."""
    return ", ".join(f"{r.get('name', '?')} ({_run_label(r, index)})"
                     for r in unfinished)


def stuck_check_ids(note: str) -> list[str]:
    """Id check-run'ов из `note` исхода `VERIFYING_STUCK`, по порядку и без
    повторов; [] — `note` не про зависшие проверки.

    Тот же приём, что `red_status_sha`: `ci-rerun` берёт адрес перезапуска
    из `note` статуса, который только что прочитал сам, а не опрашивает
    check-runs второй раз.
    """
    return list(dict.fromkeys(_STUCK_NOTE_ID_RE.findall(note)))


def _commit_not_found_in_origin(why: str) -> bool:
    """`why` из `check_runs`/`check_runs_page` называет HTTP 422 — GitHub
    не нашёл коммит вовсе, а не «CI ещё не ответил» (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, требование 4, AC-6): голова ветки задачи
    не в origin, опрос CI по её sha структурно не может дать ответа.
    Сверка по подстроке "422" в сыром тексте `gh` — тот же приём, что
    `verifying_is_red`/`status_kind` уже применяют к своим `note`.
    """
    return "422" in why


def verifying_status(branch: str, repo: Path | None = None) -> tuple[str, str]:
    """Статус CI ветки задачи в состоянии `verifying` (SPEC T079,
    требование 5) — не то же самое, что `branch_status`: тот сворачивает
    любой не-зелёный исход в единое "нельзя мержить" (гейт merge_gate,
    условие которого не различает причины); здесь причины различать
    обязательно — «проверок нет» и «CI красный» ведут к разным записям
    журнала и (со временем) к разным решениям Оператора.

    Не создаёт коммитов и не зовёт ничего, что «будит» CI (требование 5,
    AC-12) — читает только. `repo` — клон проекта задачи, как у
    `head_sha`.
    """
    sha, why = head_sha(branch, **_repo_kwargs(repo))
    if not sha:
        return VERIFYING_NONE, f"статус CI неизвестен: {why}"
    short = sha[:8]

    runs, why = check_runs(sha)
    if runs is None and _commit_not_found_in_origin(why):
        return VERIFYING_NONE, (
            f"{HEAD_NOT_IN_ORIGIN_NOTE} — GitHub не нашёл коммит {short} "
            f"({why}); пульт сам отправит голову ветки {branch} в origin "
            f"(push) при опросе verifying")
    if not runs:
        first_source = (f"у коммита {short} нет ни одной проверки CI"
                        if runs is not None else
                        f"статус check-runs коммита {short} неизвестен ({why})")
        runs_by_branch, run_why = run_list(branch)
        if runs_by_branch:
            return VERIFYING_RUNNING, (f"{first_source}, но `gh run list` "
                                       f"по ветке {branch} показывает "
                                       f"запуск — проверки идут")
        detail = (f"и `gh run list` по ветке {branch} не ответил "
                  f"({run_why})" if runs_by_branch is None else
                  f"и `gh run list` по ветке {branch} не показывает "
                  f"запусков")
        return VERIFYING_NONE, f"{first_source}, {detail} — проверок нет вовсе"

    unfinished, reread = _unfinished_checks(runs)
    failed = [r for r in runs if r.get("conclusion") not in GREEN]
    # Прогоны спрашиваются только на не-зелёном исходе: зелёный текст и
    # число запросов на нём задача не трогает.
    index = (_commit_workflow_runs(sha, runs) if unfinished or failed
             else None)
    divergence = _divergence_phrase(_event_divergence(runs, index))
    stuck = _stuck_checks(unfinished, index)
    if stuck:
        # Зависшая проверка важнее идущих рядом: без перезапуска коммит не
        # станет зелёным, сколько ни жди остальные.
        return VERIFYING_STUCK, _with_reread(
            f"CI коммита {short}: проверка зависла (порог "
            f"{config.CI_STUCK_CHECK_MINUTES} мин) — {'; '.join(stuck)}; "
            f"перезапуск — ci-rerun{divergence}", reread)
    if unfinished:
        return VERIFYING_RUNNING, _with_reread(
            f"CI коммита {short} ещё идёт: "
            f"{_running_listing(unfinished, index)}{divergence}", reread)
    if failed:
        return VERIFYING_RED, _with_reread(
            f"CI коммита {short} не зелёный: "
            f"{_failed_listing(failed, index)}{divergence}", reread)
    return VERIFYING_GREEN, _with_reread(
        f"CI коммита {short} зелёный ({len(runs)} проверок)", reread)


def verifying_is_red(note: str) -> bool:
    """Был ли `note` из `verifying_status` исходом `VERIFYING_RED` (SPEC
    T086, требование 2): тот же приём, что `status_kind` для `note`
    `branch_status` — сверка по подстроке, которую сама `verifying_status`
    кладёт в `note` только для красного исхода ("не зелёный:"), а не
    повторный опрос CI. Позволяет `auto` (orchestrator/auto.py) отличить
    завершённый красный CI от "проверок нет"/"проверки идут" по уже
    прочитанному и журналированному `fsm.cmd_advance` тексту, не опрашивая
    `gh` второй раз за ту же итерацию.
    """
    return "не зелёный:" in note


def verifying_head_not_in_origin(note: str) -> bool:
    """Был ли `note` из `verifying_status` исходом 422 «голова ветки не в
    origin» (SPEC 01M44ENQCRK02T2MWZB9HC3XHH, требование 6): по тексту уже
    прочитанного статуса, как `verifying_is_red`, без второго опроса `gh`.
    Обработчик `verifying` на нём отправляет голову в origin сам."""
    return note.startswith(HEAD_NOT_IN_ORIGIN_NOTE)


# Короткая форма sha, которую `verifying_status`/`branch_status` кладут в
# свой `note` (`short = sha[:8]`) — вход `red_status_sha` ниже.
_RED_NOTE_SHA_RE = re.compile(r"CI коммита ([0-9a-fA-F]+) не зелёный")


def red_status_sha(note: str) -> str:
    """Короткий sha коммита из `note` красного исхода `verifying_status`;
    "" — `note` не про красный исход либо sha в нём не разобран.

    Парная к `verifying_is_red` (тот отвечает «красный ли этот note», эта
    — «про какой коммит он»), тем же приёмом: разбор текста, который сам
    этот модуль и сформировал, а не повторный опрос `gh`. Нужна команде
    `ci-rerun` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87, требование 4): sha, на
    котором остановился цикл, живёт только в уже записанной журналом
    строке `note`, и сверять с ним текущую голову ветки больше нечем.
    """
    match = _RED_NOTE_SHA_RE.search(note)
    return match.group(1) if match else ""


def failed_check_names(sha: str) -> tuple[set[str] | None, str]:
    """Имена ЗАВЕРШЁННЫХ не-зелёных check-run'ов коммита; (None, причина)
    — статус коммита неизвестен.

    Сверка «флейк ветки или дефект главной ветки» (SPEC
    01M3F7C2DVYCEANQ8CF1FCSD87, требование 5) задаёт двум РАЗНЫМ коммитам
    один и тот же вопрос — «какие задания у тебя упали» — поэтому ответ на
    него живёт одной функцией, а не двумя копиями разбора у вызывающего.
    Именно имена: sha и id прогона у двух коммитов различны по
    определению, а форма провала (`failure`/`timed_out`/`cancelled`) у
    одной и той же сломанной проверки различается.

    `status == "completed"` в фильтре обязателен (в отличие от
    `verifying_status`, где к моменту сборки `failed` все проверки уже
    завершены по построению): здесь функция зовётся и для вершины главной
    ветки, чьи проверки могут ещё идти — незавершённая проверка не «упала».

    Пустой список проверок — тоже (None, причина), а не пустое множество:
    у коммита без единого check-run'а сверять краснотУ не с чем, и
    «пересечения нет» было бы ложью в пользу повтора (инвариант 19 —
    неизвестный статус не зелёный). Та же трактовка, что у
    `branch_status` для того же обстоятельства.
    """
    runs, why = check_runs(sha)
    short = sha[:8]
    if runs is None:
        return None, f"статус CI коммита {short} неизвестен: {why}"
    if not runs:
        return None, (f"у коммита {short} нет ни одной проверки CI — "
                      f"статус неизвестен")
    return {str(r.get("name", "?")) for r in runs
            if r.get("status") == "completed"
            and r.get("conclusion") not in GREEN}, ""


def branch_status(branch: str, repo: Path | None = None) -> tuple[bool, str]:
    """(Зелёный ли CI ветки, пояснение для журнала и Оператора).

    Пояснение возвращается и на зелёном исходе: в журнале задачи должно
    остаться, какой именно коммит и сколькими проверками был признан
    годным к мержу.

    `repo` (ADR-0021 п.1-2) — клон, в котором читается голова ветки;
    `None` (по умолчанию) — клон артели, тем же приёмом, что у
    `head_sha`.
    """
    sha, why = head_sha(branch, **_repo_kwargs(repo))
    if not sha:
        return False, f"статус CI неизвестен: {why}"

    runs, why = check_runs(sha)
    short = sha[:8]
    if runs is None:
        return False, f"статус CI коммита {short} неизвестен: {why}"
    if not runs:
        return False, (f"у коммита {short} нет ни одной проверки CI — "
                       f"статус неизвестен")

    # Состояния «проверка зависла» здесь нет (SPEC 01M3Y75C9TY76083CG1PK00EM4,
    # «Не входит»): на гейте мержа проверка без исхода — просто не зелёная.
    unfinished, reread = _unfinished_checks(runs)
    failed = [r for r in runs if r.get("conclusion") not in GREEN]
    index = (_commit_workflow_runs(sha, runs) if unfinished or failed
             else None)
    divergence = _divergence_phrase(_event_divergence(runs, index))
    if unfinished:
        return False, _with_reread(
            f"CI коммита {short} ещё идёт: "
            f"{_running_listing(unfinished, index)}{divergence}", reread)
    if failed:
        return False, _with_reread(
            f"CI коммита {short} не зелёный: "
            f"{_failed_listing(failed, index)}{divergence}", reread)
    return True, _with_reread(
        f"CI коммита {short} зелёный ({len(runs)} проверок)", reread)


def status_kind(note: str) -> str:
    """Подтип не-зелёного `note` из `branch_status`: "running" | "unknown" |
    "red" (SPEC T082, ревью итерации 2, замечание major 1).

    `branch_status` сворачивает три разных обстоятельства в один и тот же
    `green=False`: проверки ещё не завершились, статус вообще не удалось
    узнать (нет проверок / `gh` не ответил / ответ не разобрать) и
    проверки завершились, но с плохим заключением. Только последнее —
    «красный» в смысле требования 7: там есть что подтверждать ре-раном.
    Первые два — «ещё нет ответа», и ре-ран/запись в flake-rate для них
    были бы ложью (ре-ран уже идущего или несуществующего прогона ничего
    не подтверждает, а «ещё идёт»/«неизвестен», записанные как
    «подтверждённый красный», обесценивают саму метрику AC-17). Решает по
    тем же строкам, что сама `branch_status` уже кладёт в `note` для этих
    двух случаев ("ещё идёт", "неизвестен") — отдельного канала передачи
    подтипа заводить не пришлось: `branch_status` остаётся `(bool, str)`,
    как её ожидают все нынешние вызыватели и приёмочные тесты T082
    (`tasks/T082/acceptance_tests/test_ci_flake_rerun.py` мокает её именно
    двухэлементным кортежем).
    """
    if "ещё идёт" in note:
        return "running"
    if "неизвестен" in note:
        return "unknown"
    return "red"


# Цвет CI main (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E, требование 2): по каждой
# проверке отдельно, с последнего коммита первой родительской линии, где она
# реально исполнялась. Цвет одной головы врал: документный коммит main
# пропускает job `python` (ADR-0016), пропуск зелёный — и первый же такой
# коммит маскировал красный код под ним.
MAIN_GREEN = "green"
MAIN_RED = "red"
MAIN_RUNNING = "running"
MAIN_UNKNOWN = "unknown"

# Потолок обхода линии. Документных коммитов подряд поверх последнего кода
# на main бывает два-три десятка (02.10 — 25); проверка, не разрешившаяся
# за потолок, — «не подтверждён», не зелёный.
MAIN_LINE_MAX_COMMITS = 200

# Исполненная и зелёная проверка; `skipped` из `GREEN` здесь — не результат,
# а повод смотреть коммит глубже.
_EXECUTED_GREEN = GREEN - {"skipped"}

_SHA_LINE_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


class MainLineStatus(NamedTuple):
    """Исход `main_line_status`: `kind` — один из `MAIN_*`; `failed` —
    [(проверка, заключение, коммит)], `running` — [(проверка, коммит)];
    `red_since` — самый ранний по линии коммит падения ("" — не красный);
    `note` — текст для журнала и Оператора."""
    kind: str
    sha: str
    failed: list
    running: list
    red_since: str
    note: str


def first_parent_line(sha: str, limit: int,
                      repo: Path | None = None) -> list[str] | None:
    """Коммиты первой родительской линии от `sha` назад (сам `sha` первым),
    не больше `limit`; `None` — git не ответил.

    `repo` (ADR-0021 п.1-2) — клон, в котором читается линия; `None`
    (по умолчанию) — клон артели, тем же приёмом, что у `head_sha`."""
    if repo is None:
        repo = workspace.repo(config.DEFAULT_TARGET)
    res = gitcmd.in_repo(repo, "rev-list", "--first-parent",
                         f"--max-count={limit}", sha)
    if res is None or res.returncode != 0:
        return None
    return [ln.strip() for ln in res.stdout.splitlines()
            if _SHA_LINE_RE.match(ln.strip())]


def _push_touches_code(base: str, head: str, repo: Path | None = None) -> bool:
    """Push с головой `head` меняет не только документы — тем же разбором
    пути, что job `changes` (`scripts/ci_push_class.py`), и тем же
    диапазоном: от предыдущей головы push'а `base` (ближайший глубже по
    линии коммит с проверками — CI гоняет только головы), а не от первого
    родителя. Голова push'а гейта мержа — документный коммит RETRO, код
    лежит в merge-коммите под ней без проверок. На push класса «код»
    проверка, пропущенная на его голове, не исполняется на push в main
    вовсе (`protected-paths`, `id-format-greplint` — только
    `pull_request`), а не пропущена как документная. git не ответил —
    `False`: обход идёт глубже, а не объявляет проверку неисполняемой.

    `repo` (ADR-0021 п.1-2) — клон, в котором считается diff; `None`
    (по умолчанию) — клон артели, тем же приёмом, что у `head_sha`."""
    if repo is None:
        repo = workspace.repo(config.DEFAULT_TARGET)
    res = gitcmd.in_repo(repo, "diff", "--name-only", base, head)
    if res is None or res.returncode != 0:
        return False
    return any(not ci_push_class.is_doc_path(p)
               for p in res.stdout.splitlines() if p.strip())


def _verdict_of_runs(runs: list) -> tuple[str, str] | None:
    """(исход, заключение) одной проверки на коммите по её прогонам: `None`
    — проверка здесь не исполнялась (только `skipped`)."""
    executed = [r for r in runs if not (r.get("status") == "completed"
                                        and r.get("conclusion") == "skipped")]
    if not executed:
        return None
    if any(r.get("status") != "completed" for r in executed):
        return MAIN_RUNNING, ""
    bad = [str(r.get("conclusion")) for r in executed
           if r.get("conclusion") not in _EXECUTED_GREEN]
    if bad:
        return MAIN_RED, bad[0]
    return MAIN_GREEN, ""


def _main_line_runs(failed: list, running: list,
                    runs_at: dict) -> tuple[dict, str]:
    """(Подписи «событие, прогон» по (проверка, коммит), фраза о
    расхождении исхода по событиям) для упавших и идущих проверок линии
    (SPEC 01M46D5ZZQY7GBEW5TBVQ0P3ZV, AC-4/AC-6).

    Прогоны спрашиваются у того коммита линии, где проверка упала или
    идёт, а не у опорного: глубже головы у неё свой прогон."""
    commits = list(dict.fromkeys([c for _n, _c, c in failed]
                                 + [c for _n, c in running]))
    indexes = {c: _commit_workflow_runs(c, runs_at[c]) for c in commits}

    def label(name: str, commit: str, selected) -> str:
        checks = [r for r in runs_at[commit]
                  if str(r.get("name", "?")) == name and selected(r)]
        return "; ".join(_run_label(r, indexes[commit]) for r in checks) \
            or UNDEFINED_EVENT

    labels = {}
    for name, _conclusion, commit in failed:
        labels[(name, commit)] = label(
            name, commit, lambda r: r.get("status") == "completed"
            and r.get("conclusion") not in GREEN)
    for name, commit in running:
        labels[(name, commit)] = label(
            name, commit, lambda r: r.get("status") != "completed")
    items = []
    for commit in dict.fromkeys(c for _n, _c, c in failed):
        names = {n for n, _c, c in failed if c == commit}
        items += _event_divergence(
            [r for r in runs_at[commit] if str(r.get("name", "?")) in names],
            indexes[commit], where=f" на {commit[:8]}")
    return labels, _divergence_phrase(items)


def _main_line_note(kind: str, ref: str, failed: list, running: list,
                    red_since: str, why: str, green_count: int,
                    labels: dict, divergence: str) -> str:
    short = ref[:8]
    if kind == MAIN_RED:
        listing = ", ".join(f"{name}={conclusion} на {sha[:8]} "
                            f"({labels[(name, sha)]})"
                            for name, conclusion, sha in failed)
        return f"main красный с {red_since[:8]}: {listing}{divergence}"
    if kind == MAIN_RUNNING:
        listing = ", ".join(f"{name} на {sha[:8]} ({labels[(name, sha)]})"
                            for name, sha in running)
        return (f"CI main {short} не подтверждён: "
                f"{why or f'проверки ещё идут: {listing}{divergence}'}")
    if kind == MAIN_UNKNOWN:
        return f"CI main {short} не подтверждён: {why}"
    return (f"CI main {short} зелёный по первой родительской линии "
            f"({green_count} проверок)")


def main_line_status(sha: str, repo: Path | None = None) -> MainLineStatus:
    """Цвет CI main от опорного коммита `sha` (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E,
    требование 2) — общее определение для `pin-update`, строки `doctor` и
    гейта мержа.

    Набор проверок — с опорного коммита; у каждой результат берётся с
    первого коммита линии `git rev-list --first-parent`, где она не
    `skipped`: идёт — `running`, исполнена с плохим заключением — упала
    (с этим коммитом), иначе зелёная. Коммит без проверок вовсе
    (промежуточные коммиты мержа — CI гоняет только голову push'а)
    пропускается. Проверка, пропущенная на голове push'а класса «код»
    (диапазон — до следующей глубже головы с проверками), на push в main
    не исполняется вовсе и в цвет не входит; так же — не исполнившаяся до
    начала истории. Не разрешившаяся за `MAIN_LINE_MAX_COMMITS` —
    «неизвестен».

    Итог: есть упавшая — `MAIN_RED` (идущие при этом не спасают); есть
    идущая либо у опорного коммита ещё нет проверок — `MAIN_RUNNING`; сбой
    `gh` на любом коммите — `MAIN_UNKNOWN` (инвариант 19: неизвестное не
    зелёное); иначе `MAIN_GREEN`.

    `repo` (ADR-0021 п.1-2) — клон, в котором читается первая
    родительская линия и дифф пропущенных проверок; `None` (по умолчанию)
    — клон артели, тем же приёмом, что у `head_sha`.
    """
    line = (first_parent_line(sha, MAIN_LINE_MAX_COMMITS, **_repo_kwargs(repo))
            or [sha])
    ref = line[0]
    pending: set[str] | None = None
    failed: list = []
    running: list = []
    green_count = 0
    why = ""
    kind = ""
    # Голова push'а и пропущенные на ней проверки: класс её push'а известен
    # только у следующей глубже головы с проверками.
    skipped_at: tuple[str, list] | None = None
    # Check-run'ы пройденных коммитов — для подписи упавших и идущих
    # проверок прогоном их коммита после обхода.
    runs_at: dict[str, list] = {}
    for commit in line:
        runs, reason = check_runs(commit)
        if runs is None and pending is None \
                and _commit_not_found_in_origin(reason):
            # Сразу после push GitHub ещё не знает голову — CI не начался,
            # а не «gh недоступен».
            why = f"GitHub ещё не видит коммит {ref[:8]} ({reason})"
            kind = MAIN_RUNNING
            break
        if runs is None:
            why = f"статус CI коммита {commit[:8]} неизвестен: {reason}"
            kind = MAIN_UNKNOWN
            break
        if pending is None:
            if not runs:
                why = (f"у коммита {ref[:8]} нет ни одной проверки CI — "
                       f"CI ещё не начался")
                kind = MAIN_RUNNING
                break
            pending = {str(r.get("name", "?")) for r in runs}
        if not runs:
            continue
        runs_at[commit] = runs
        if skipped_at is not None:
            push_head, names = skipped_at
            skipped_at = None
            if _push_touches_code(commit, push_head, **_repo_kwargs(repo)):
                pending.difference_update(names)
                if not pending:
                    break
        skipped_here = []
        for name in sorted(pending):
            verdict = _verdict_of_runs([r for r in runs
                                        if str(r.get("name", "?")) == name])
            if verdict is None:
                if any(str(r.get("name", "?")) == name for r in runs):
                    skipped_here.append(name)
                continue
            outcome, conclusion = verdict
            if outcome == MAIN_RED:
                failed.append((name, conclusion, commit))
            elif outcome == MAIN_RUNNING:
                running.append((name, commit))
            else:
                green_count += 1
            pending.discard(name)
        if skipped_here:
            skipped_at = (commit, skipped_here)
        if not pending:
            break
    else:
        if pending and len(line) >= MAIN_LINE_MAX_COMMITS:
            why = (f"проверки {', '.join(sorted(pending))} не исполнялись на "
                   f"{len(line)} коммитах линии")
            kind = MAIN_UNKNOWN
    red_since = ""
    if failed:
        kind = MAIN_RED
        red_since = max((c for _n, _c, c in failed), key=line.index)
    elif not kind:
        kind = MAIN_RUNNING if running else MAIN_GREEN
    labels, divergence = _main_line_runs(failed, running, runs_at)
    note = _main_line_note(kind, ref, failed, running, red_since, why,
                           green_count, labels, divergence)
    return MainLineStatus(kind, ref, failed, running, red_since, note)


def find_run_id(sha: str) -> tuple[str, str]:
    """Id workflow-прогона головного коммита; ("", причина) — не найден.

    `gh run rerun` адресуется по id прогона (workflow run), не по sha
    коммита — check-run'ы, которые видит `branch_status`, его не несут
    (SPEC T082, требование 7: ре-ран обязан реально перезапустить
    CI-прогон, а не повторно прочитать тот же завершённый статус).

    Один sha может нести НЕСКОЛЬКО прогонов одного workflow (SPEC T082,
    ревью итерации 2, замечание major 2): `.github/workflows/ci.yml`
    триггерится и на `push` (ветки `main`/`task/**`), и на `pull_request`
    — при открытом PR ветки задачи (штатный сценарий этой системы, не
    гипотетический — см. `/code-review ultra <PR#>`) один и тот же
    head-коммит порождает два независимых прогона. «Самый свежий прогон»
    вслепую промахивался бы, если упавший прогон — не он (например,
    push-прогон упал, а более поздний pull_request-прогон того же
    коммита успешен). Эта функция вызывается только когда
    `status_kind(note) == "red"` — то есть ВСЕ проверки коммита уже
    завершены и хотя бы одна не прошла (иначе `branch_status` отдал бы
    "running", и до сюда код не дошёл бы, см. `fsm._cmd_approve_merge_gate`)
    — поэтому среди завершённых прогонов сверяется, у кого заключение
    само не зелёное, и берётся самый свежий из НИХ, а не из всех подряд.
    Ни одного такого не нашлось (гонка API, неполный ответ) — деградация
    на прежнее поведение (самый свежий прогон вообще): ре-ран должен хоть
    на что-то нацелиться, а не отказывать совсем.
    """
    res = gh("api", f"repos/{{owner}}/{{repo}}/actions/runs"
                    f"?head_sha={sha}&per_page={config.CI_RUNS_PER_PAGE}")
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return "", f"gh не ответил: {detail or f'код {res.returncode}'}"
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return "", f"ответ gh не разобран: {exc}"
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if (not isinstance(runs, list) or not runs
            or not all(isinstance(r, dict) for r in runs)):
        return "", f"для коммита {sha[:8]} нет workflow-прогонов"
    failed = [r for r in runs if r.get("status") == "completed"
             and r.get("conclusion") not in GREEN]
    run = (failed or runs)[0]
    run_id = run.get("databaseId", run.get("id"))
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        return "", "у прогона нет числового id"
    return str(run_id), ""


def check_run_workflow_run(check_id: str) -> tuple[str, str]:
    """Id workflow-прогона, которому принадлежит check-run; ("", причина) —
    не найден (SPEC 01M3Y75C9TY76083CG1PK00EM4, требование 3).

    Check-run задания GitHub Actions — это job с тем же id, а job несёт
    `run_id` своего прогона. «Самый свежий прогон коммита» (`find_run_id`)
    здесь не годится: у коммита два прогона (push и pull_request), и в
    инциденте 02.10 оба были `completed/success`, а зависшая проверка
    принадлежала только одному из них.
    """
    res = gh("api", f"repos/{{owner}}/{{repo}}/actions/jobs/{check_id}")
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        return "", f"gh не ответил: {detail or f'код {res.returncode}'}"
    try:
        payload = json.loads(res.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        return "", f"ответ gh не разобран: {exc}"
    run_id = payload.get("run_id") if isinstance(payload, dict) else None
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        return "", f"у задания {check_id} нет числового run_id"
    return str(run_id), ""


def trigger_rerun(branch: str, run_id: str = "") -> str:
    """Настоящий повторный прогон CI головного коммита ветки (SPEC T082,
    требование 7): `gh run rerun <id> --failed` реально запускает упавшие
    job'ы заново (не то же самое, что повторное чтение уже завершённого
    check-run'а `branch_status`'ом), затем `gh run watch` ждёт его
    завершения — до того, как вызывающий код спросит `branch_status`
    снова за итоговым результатом.

    `run_id` задан (SPEC 01M3Y75C9TY76083CG1PK00EM4, требование 3) — это
    прогон зависшей проверки, найденный вызывающим по самой проверке:
    поиск по sha пропускается, а прогон перезапускается целиком, без
    `--failed` — упавших заданий в нём нет, зависшее не «упало».

    Best-effort: любой сбой (gh недоступен, прогон не найден, сеть легла)
    не бросает исключение — гейт не имеет права зависнуть на детекте
    флейка. Причина возвращается для журнала; повторный `branch_status`
    следом честно увидит тот же красный статус, если триггер не удался.
    """
    if run_id:
        rerun = gh("run", "rerun", run_id)
    else:
        sha, why = head_sha(branch)
        if not sha:
            return f"ре-ран CI не запущен: {why}"
        run_id, why = find_run_id(sha)
        if not run_id:
            return f"ре-ран CI не запущен: {why}"
        rerun = gh("run", "rerun", run_id, "--failed")
    if rerun.returncode != 0:
        detail = (rerun.stderr or rerun.stdout).strip()[:200]
        return (f"ре-ран прогона {run_id} не запущен: "
               f"{detail or f'код {rerun.returncode}'}")
    watch = gh("run", "watch", run_id, "--exit-status",
              timeout=config.CI_RERUN_WAIT_SEC)
    detail = (watch.stderr or watch.stdout).strip()[:200]
    return (f"ре-ран прогона {run_id} запущен, ожидание завершения: "
           f"{detail or 'gh run watch завершился'}")


def rerun_started(note: str) -> bool:
    """Дошёл ли `trigger_rerun` до реального запуска повтора — по её же
    `note` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87, требование 8).

    Тот же приём сверки по подстроке, что `verifying_is_red`/`status_kind`:
    `trigger_rerun` — best-effort и возвращает (нарочно) не структуру, а
    строку для журнала, а её единственный вызыватель до этой задачи (гейт
    мержа) исход не различал вовсе — просто перечитывал `branch_status`.
    Команде `ci-rerun` различать обязательно: «повтор не запущен» и
    «повтор запущен, а ожидание не удалось» ведут к одной и той же записи
    журнала «`gh` не ответил» (AC-9), но «повтор запущен» — ещё и к
    честному чтению нового статуса, которого в первом случае не будет.
    Подстрока «не запущен» — та, которую сама `trigger_rerun` кладёт в
    `note` ровно на двух своих путях отказа и ни на одном пути успеха.
    """
    return "не запущен" not in note
