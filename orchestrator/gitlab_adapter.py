"""Реализация хостинга GitLab для `forge` на HTTP API v4 (SPEC
01M5WCXBM7WCMRWCBWNCHMAR3T, требования 3-7; контракты ANSWER-1 В-1…В-5).

Сеть — только в `transport`, а `transport` зовёт только `request`: в одной
функции стоят таблица разрешённых пар «метод — шаблон пути», проверка
полей тела, токен и повтор. Пара вне таблицы, иное поле правки MR или
иная смена заголовка — отказ до отправки запроса, с именем пары: адаптер
не может слить MR, запустить задание или прочитать участников проекта,
как бы его ни позвали.

Токен проекта (`gitcmd.hosting_token` по слоту `token_slot` записи) идёт
заголовком `PRIVATE-TOKEN` и не попадает ни в одну причину: тексты ошибок
собираются из кода ответа и пары, не из заголовков и не из тела ответа.

Итог CI коммита — по конвейерам ровно этого sha (требование 5): `green`
даёт только явное правило, неполная выдача и незнакомый статус — `unknown`
(инвариант 19: неизвестный статус не зелёный).
"""
from __future__ import annotations

import datetime
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import forge, gitcmd, targets

API_PREFIX = "/api/v4"
TIMEOUT_SEC = 20
# Всего попыток на 429/5xx (первая и повторы); пауза растёт с номером.
RETRY_ATTEMPTS = 3
RETRY_PAUSE_SEC = 2
PER_PAGE = 100
MAX_PAGES = 50
# Пороги строки срока токена (ориентир части 2: `doctor`).
TOKEN_EXPIRY_WARN_DAYS = 14
TOKEN_NO_EXPIRY_TASKS_WARN = 10

# Итог CI проекта даёт `pipeline_status` этого модуля (`forge.ci_by_pipeline`).
CI_BY_PIPELINE = True

DRAFT_PREFIX = "Draft: "
NO_PIPELINE = "конвейер не создан (ветка не под правилом workflow?)"
AMBIGUOUS_ID = "неоднозначный идентификатор"

# Разрешённые пары: `:id` — только проект записи, `:n` — число.
ALLOWED_PAIRS = (
    ("GET", "/projects/:id"),
    ("GET", "/projects/:id/pipelines"),
    ("GET", "/projects/:id/pipelines/:n/jobs"),
    ("GET", "/projects/:id/pipelines/:n/test_report"),
    ("GET", "/projects/:id/merge_requests/:n"),
    ("GET", "/projects/:id/protected_branches"),
    ("GET", "/projects/:id/protected_tags"),
    ("GET", "/user"),
    ("GET", "/personal_access_tokens/self"),
    ("POST", "/projects/:id/merge_requests"),
    ("PUT", "/projects/:id/merge_requests/:n"),
)
QUERY_KEYS = {"sha", "ref", "page", "per_page", "order_by", "sort"}
CREATE_MR_FIELDS = {"source_branch", "target_branch", "title", "description",
                    "assignee_id"}
EDIT_MR_FIELDS = {"assignee_id", "title"}
_MR_PATH_RE = re.compile(r"/projects/[^/]+/merge_requests/\d+")

PIPELINE_GREEN = {"success", "manual"}
PIPELINE_RUNNING = {"running", "pending", "waiting_for_resource", "preparing",
                    "scheduled"}
JOB_RUNNING = PIPELINE_RUNNING


class Reply:
    """Ответ `request`: `reason` пуст — ответ 2xx, `data` — разобранный JSON."""

    def __init__(self, status: int | None = None, headers: dict | None = None,
                 data=None, reason: str = ""):
        self.status = status
        self.headers = headers or {}
        self.data = data
        self.reason = reason

    def __repr__(self) -> str:
        return f"Reply(status={self.status!r}, reason={self.reason!r})"


def transport(method: str, url: str, headers: dict, body: bytes | None,
              timeout: float) -> tuple[int, dict, bytes]:
    """Один HTTP-обмен: (код, заголовки, тело). Ответ 4xx/5xx — числом, не
    исключением; отказ сети — `urllib.error.URLError`, таймаут —
    `TimeoutError`. Единственное место сети модуля — подменяется тестами."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        with exc:
            return (exc.code, dict(exc.headers.items()) if exc.headers else {},
                    exc.read())
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError(str(exc.reason)) from exc
        raise
    except http.client.HTTPException as exc:
        raise urllib.error.URLError(exc) from exc


def _address(entry: dict) -> tuple[str, str, str]:
    """(адрес сервера, путь проекта в виде `:id`, причина) из `url` записи."""
    url = str(entry.get("url") or "").strip()
    scp = re.match(r"^git@([^:/\s]+):(.+)$", url)
    if scp:
        server, path = f"https://{scp.group(1)}", scp.group(2)
    else:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.netloc:
            return "", "", f"адрес проекта {url!r} не разобран"
        server, path = f"{parts.scheme}://{parts.netloc}", parts.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-len(".git")]
    if "/" not in path:
        return "", "", f"в адресе проекта {url!r} нет пути проекта"
    return server, urllib.parse.quote(path, safe=""), ""


def _pair_refusal(method: str, path: str, body, project: str) -> str:
    """Причина отказа пары до отправки; "" — пара и тело разрешены."""
    pair = f"{method} {path}"
    raw, _, query = path.partition("?")
    raw = raw.replace("%2f", "%2F")
    allowed = False
    for allowed_method, template in ALLOWED_PAIRS:
        pattern = "/".join(re.escape(project) if part == ":id"
                           else r"\d+" if part == ":n" else re.escape(part)
                           for part in template.split("/"))
        if method == allowed_method and re.fullmatch(pattern, raw):
            allowed = True
            break
    if not allowed:
        return f"пара {pair} не разрешена адаптеру GitLab — запрос не отправлен"
    keys = {k for k, _v in urllib.parse.parse_qsl(query, keep_blank_values=True)}
    if (method != "GET" and query) or keys - QUERY_KEYS:
        return (f"пара {pair}: параметры запроса не разрешены (разрешены у "
                f"чтения: {', '.join(sorted(QUERY_KEYS))}) — запрос не отправлен")
    if method == "GET":
        return "" if body is None else f"пара {pair}: у чтения нет тела — запрос не отправлен"
    fields = CREATE_MR_FIELDS if method == "POST" else EDIT_MR_FIELDS
    if not isinstance(body, dict) or not body:
        return f"пара {pair}: тело не задано — запрос не отправлен"
    extra = sorted(set(body) - fields)
    if extra:
        return (f"пара {pair}: поля {', '.join(extra)} не разрешены "
                f"(разрешены {', '.join(sorted(fields))}) — запрос не отправлен")
    return ""


def _title_refusal(target: str, method: str, path: str, title) -> str:
    """Новый заголовок MR отличается от текущего только префиксом `Draft: `;
    "" — смена разрешена. Текущий заголовок читается до правки."""
    pair = f"{method} {path}"
    current = request(target, "GET", path.partition("?")[0])
    if current.reason:
        return f"пара {pair}: текущий заголовок MR не прочитан ({current.reason})"
    old = current.data.get("title") if isinstance(current.data, dict) else None
    if not isinstance(old, str) or not isinstance(title, str):
        return f"пара {pair}: заголовок MR не разобран — запрос не отправлен"
    if title in (old, DRAFT_PREFIX + old) or old == DRAFT_PREFIX + title:
        return ""
    return (f"пара {pair}: новый заголовок отличается от текущего не только "
            f"префиксом {DRAFT_PREFIX.strip()!r} — запрос не отправлен")


def _header(headers: dict, name: str) -> str:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value).strip()
    return ""


def _status_reason(status: int, pair: str, attempts: int) -> str:
    if status == 401:
        return f"GitLab не принял токен (401) на {pair}"
    if status == 403:
        return f"доступ запрещён (403) на {pair}"
    if status == 404:
        return f"не найдено (404): {pair}"
    if status == 429:
        return (f"превышен предел частоты запросов (429) на {pair} после "
                f"{attempts} попыток")
    if status >= 500:
        return f"ошибка сервера GitLab ({status}) на {pair} после {attempts} попыток"
    return f"GitLab ответил кодом {status} на {pair}"


def request(target: str, method: str, path: str, body: dict | None = None) -> Reply:
    """Единственная функция запроса к API: `path` — путь под `/api/v4`
    (проект — путь из `url` записи с `/` в виде `%2F`), строка запроса при
    нужде. Отказ — `Reply` с причиной, без исключения."""
    method = str(method).upper()
    pair = f"{method} {path}"
    try:
        entry = targets.target(target)
    except targets.TargetsError as exc:
        return Reply(reason=f"запрос {pair} не отправлен: {exc}")
    server, project, why = _address(entry)
    if why:
        return Reply(reason=f"запрос {pair} не отправлен: {why}")
    refusal = _pair_refusal(method, path, body, project)
    if refusal:
        return Reply(reason=refusal)
    if method == "PUT" and "title" in body:
        refusal = _title_refusal(target, method, path, body["title"])
        if refusal:
            return Reply(reason=refusal)
    token, refusal = gitcmd.hosting_token(target, entry)
    if refusal is not None:
        return Reply(reason=refusal)
    if not token:
        return Reply(reason=(f"токен не получен: у проекта {target} нет токена "
                             f"хостинга (token_slot) — запрос {pair} не отправлен"))
    headers = {"PRIVATE-TOKEN": token, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    url = server + API_PREFIX + path
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            status, reply_headers, raw = transport(method, url, headers, data,
                                                   TIMEOUT_SEC)
        except TimeoutError:
            return Reply(reason=f"таймаут: GitLab не ответил на {pair} за "
                                f"{TIMEOUT_SEC} с")
        except (urllib.error.URLError, OSError) as exc:
            detail = getattr(exc, "reason", None) or exc
            return Reply(reason=f"сеть недоступна: {detail} ({pair})")
        if (status == 429 or status >= 500) and attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_PAUSE_SEC * attempt)
            continue
        break
    reply_headers = dict(reply_headers or {})
    if not 200 <= status < 300:
        return Reply(status, reply_headers,
                     reason=_status_reason(status, pair, attempt))
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, ValueError) as exc:
        return Reply(status, reply_headers,
                     reason=f"ответ GitLab на {pair} не разобран: {exc}")
    return Reply(status, reply_headers, payload)


def _project(target: str) -> tuple[str, dict | None, str]:
    """(`:id` проекта, запись, причина)."""
    try:
        entry = targets.target(target)
    except targets.TargetsError as exc:
        return "", None, f"запись проекта {target} не прочитана: {exc}"
    _server, project, why = _address(entry)
    return project, entry, why


def _read_all(target: str, path: str, query: dict) -> tuple[list | None, str]:
    """Список постранично до конца, сверенный с `X-Total`; (None, причина) —
    ошибка запроса или неполная выдача."""
    items: list = []
    total = ""
    for page in range(1, MAX_PAGES + 1):
        params = dict(query, per_page=PER_PAGE, page=page)
        reply = request(target, "GET", f"{path}?{urllib.parse.urlencode(params)}")
        if reply.reason:
            return None, reply.reason
        if not isinstance(reply.data, list):
            return None, f"ответ GitLab на GET {path} — не список"
        if page == 1:
            total = _header(reply.headers, "X-Total")
        items.extend(reply.data)
        if not _header(reply.headers, "X-Next-Page") or not reply.data:
            break
    else:
        return None, (f"неполная выдача GET {path}: больше {MAX_PAGES} "
                      f"страниц по {PER_PAGE}")
    if not total.isdigit():
        return None, (f"неполная выдача GET {path}: нет числа X-Total, "
                      f"полноту не сверить")
    if len(items) != int(total):
        return None, (f"неполная выдача GET {path}: прочитано {len(items)} "
                      f"из {total} по X-Total")
    return items, ""


def _job(item: dict) -> forge.Job:
    jid = item.get("id")
    return forge.Job(str(item.get("name", "?")), str(item.get("status", "")),
                     str(item.get("stage", "")),
                     jid if isinstance(jid, int) and not isinstance(jid, bool) else None,
                     item.get("allow_failure") is True)


def _latest_by_name(jobs: list) -> list:
    """Последняя попытка (наибольший id) каждого имени задания."""
    latest: dict = {}
    for job in jobs:
        prev = latest.get(job.name)
        if prev is None or (job.id or 0) > (prev.id or 0):
            latest[job.name] = job
    return list(latest.values())


def _job_findings(jobs: list, required: set) -> tuple[list, list, list]:
    """(находки (итог, причина), упавшие без права падать, пометки) заданий
    одного конвейера по правилам требования 5."""
    stage_first: dict = {}
    for job in jobs:
        if job.id is not None:
            stage_first[job.stage] = min(stage_first.get(job.stage, job.id), job.id)
    latest = _latest_by_name(jobs)
    manual_stages = [stage_first[j.stage] for j in latest
                     if j.status == "manual" and j.stage in stage_first]
    findings, failed, marks = [], [], []
    for job in latest:
        name, status = job.name, job.status
        rank = stage_first.get(job.stage)
        after_manual = rank is not None and any(m < rank for m in manual_stages)
        if status == "success":
            continue
        if status in ("failed", "canceled") and job.allow_failure:
            marks.append(f"задание {name} завершилось статусом {status}, но ему "
                         f"разрешено падать (allow_failure)")
        elif status == "failed":
            findings.append((forge.RED, f"задание {name} упало (failed)"))
            failed.append(name)
        elif status == "canceled":
            findings.append((forge.UNKNOWN, f"задание {name} отменено (canceled) — "
                                            f"исход не установлен"))
        elif status in JOB_RUNNING:
            findings.append((forge.RUNNING, f"задание {name}: {status}"))
        elif status == "manual":
            if name in required:
                findings.append((forge.RUNNING, f"обязательное задание {name} "
                                                f"ждёт ручного запуска (manual)"))
        elif status in ("created", "skipped"):
            verdict = forge.RUNNING if status == "created" else forge.UNKNOWN
            if name in required:
                findings.append((verdict, f"обязательное задание {name} не "
                                          f"исполнено ({status})"))
            elif not after_manual:
                findings.append((verdict, f"задание {name} не исполнено "
                                          f"({status}), ручного задания в более "
                                          f"ранней стадии нет"))
        else:
            findings.append((forge.UNKNOWN, f"задание {name}: незнакомый статус "
                                            f"{status!r}"))
    return findings, failed, marks


def _pipeline_findings(target: str, project: str, pipeline: dict,
                       required: set) -> tuple[list, list, list, list]:
    """(находки, задания, упавшие, пометки) одного конвейера: старший итог
    из статуса самого конвейера и его заданий."""
    pid = pipeline.get("id")
    status = str(pipeline.get("status", ""))
    items, why = _read_all(target, f"/projects/{project}/pipelines/{pid}/jobs", {})
    if items is None:
        # Неполная выдача заданий — `unknown` при любых прочитанных статусах.
        return [(forge.UNKNOWN, f"задания конвейера {pid}: {why}")], [], [], []
    jobs = [_job(i) for i in items if isinstance(i, dict)]
    findings, failed, marks = _job_findings(jobs, required)
    if status == "failed":
        findings.append((forge.RED, f"конвейер {pid} завершился статусом failed"))
    elif status in PIPELINE_RUNNING:
        findings.append((forge.RUNNING, f"конвейер {pid}: {status}"))
    elif status not in PIPELINE_GREEN:
        findings.append((forge.UNKNOWN, f"конвейер {pid}: статус {status!r} — "
                                        f"исход не установлен"))
    return findings, jobs, failed, marks


def _verdict(findings: list) -> tuple[str, str]:
    """(старший итог, причины только этого итога)."""
    verdict = forge.senior(v for v, _t in findings)
    return verdict, "; ".join(t for v, t in findings if v == verdict)


def _required(entry: dict) -> set:
    return set(entry.get("ci_required_jobs") or [])


def pipeline_status(target: str, sha: str) -> forge.PipelineStatus:
    project, entry, why = _project(target)
    if why:
        return forge.PipelineStatus(forge.UNKNOWN, why)
    pipelines, why = _read_all(target, f"/projects/{project}/pipelines", {"sha": sha})
    if pipelines is None:
        return forge.PipelineStatus(forge.UNKNOWN, why)
    if not pipelines:
        return forge.PipelineStatus(forge.NONE, NO_PIPELINE)
    findings, jobs, failed, marks = [], [], [], []
    for pipeline in pipelines:
        if not isinstance(pipeline, dict):
            findings.append((forge.UNKNOWN, "конвейер в ответе GitLab не разобран"))
            continue
        found = _pipeline_findings(target, project, pipeline, _required(entry))
        findings += found[0]
        jobs += found[1]
        failed += found[2]
        marks += found[3]
    verdict, reason = _verdict(findings)
    return forge.PipelineStatus(verdict, reason, jobs, sorted(set(failed)), marks)


def _sha_jobs(target: str, sha: str) -> tuple[list | None, str]:
    """[(id конвейера, задание)] всех конвейеров коммита; (None, причина)."""
    project, _entry, why = _project(target)
    if why:
        return None, why
    pipelines, why = _read_all(target, f"/projects/{project}/pipelines", {"sha": sha})
    if pipelines is None:
        return None, why
    found = []
    for pipeline in pipelines:
        pid = pipeline.get("id") if isinstance(pipeline, dict) else None
        items, why = _read_all(target, f"/projects/{project}/pipelines/{pid}/jobs", {})
        if items is None:
            return None, why
        found += [(pid, _job(i)) for i in items if isinstance(i, dict)]
    return found, ""


def _last_attempt(target: str, sha: str, job_name: str):
    """((id конвейера, задание) последней попытки `job_name`, причина)."""
    jobs, why = _sha_jobs(target, sha)
    if jobs is None:
        return None, why
    attempts = [(pid, job) for pid, job in jobs if job.name == job_name]
    if not attempts:
        return None, f"задания «{job_name}» нет в конвейерах коммита {sha[:8]}"
    return max(attempts, key=lambda pair: pair[1].id or 0), ""


def job_result(target: str, sha: str, job_name: str) -> forge.JobResult:
    found, why = _last_attempt(target, sha, job_name)
    if found is None:
        return forge.JobResult(None, why)
    return forge.JobResult(found[1].status)


def job_test_report(target: str, sha: str, job_name: str) -> forge.TestReport:
    found, why = _last_attempt(target, sha, job_name)
    if found is None:
        return forge.TestReport(None, why)
    project, _entry, why = _project(target)
    reply = request(target, "GET", f"/projects/{project}/pipelines/{found[0]}/test_report")
    if reply.reason:
        return forge.TestReport(None, f"отчёта тестов задания {job_name} нет: "
                                      f"{reply.reason}")
    suites = reply.data.get("test_suites") if isinstance(reply.data, dict) else None
    mine = [s for s in suites or [] if isinstance(s, dict) and s.get("name") == job_name]
    if not mine:
        return forge.TestReport(None, f"в отчёте тестов конвейера {found[0]} нет "
                                      f"набора задания {job_name}")
    outcomes: dict = {}
    for suite in mine:
        cases = suite.get("test_cases") or []
        if not cases:
            error = suite.get("suite_error") or "набор без тестов"
            return forge.TestReport(None, f"отчёт тестов задания {job_name} "
                                          f"недоступен: {error}")
        for case in cases:
            key = f"{case.get('classname', '')}::{case.get('name', '')}"
            if key in outcomes:
                return forge.TestReport(None, f"{AMBIGUOUS_ID} {key} в отчёте "
                                              f"задания {job_name}")
            outcomes[key] = str(case.get("status", ""))
    return forge.TestReport(outcomes)


def _merge_request(reply: Reply) -> forge.MergeRequest:
    if reply.reason:
        return forge.MergeRequest(reason=reply.reason)
    data = reply.data if isinstance(reply.data, dict) else {}
    assignee = data.get("assignee")
    draft = data.get("draft", data.get("work_in_progress"))
    return forge.MergeRequest(
        iid=data.get("iid"), url=data.get("web_url"), title=data.get("title"),
        state=data.get("state"), draft=draft is True,
        assignee=assignee.get("username") if isinstance(assignee, dict) else None)


def _mr_path(target: str, mr) -> tuple[str, str]:
    project, _entry, why = _project(target)
    return f"/projects/{project}/merge_requests/{mr}", why


def open_mr(target: str, branch: str, base: str, title: str, body: str,
            draft: bool, assignee) -> forge.MergeRequest:
    project, _entry, why = _project(target)
    if why:
        return forge.MergeRequest(reason=why)
    if draft and not title.startswith(DRAFT_PREFIX):
        title = DRAFT_PREFIX + title
    payload = {"source_branch": branch, "target_branch": base, "title": title,
               "description": body, "assignee_id": assignee}
    return _merge_request(request(target, "POST",
                                  f"/projects/{project}/merge_requests", payload))


def undraft_mr(target: str, mr) -> forge.MergeRequest:
    path, why = _mr_path(target, mr)
    if why:
        return forge.MergeRequest(reason=why)
    current = _merge_request(request(target, "GET", path))
    if current.reason or not (current.title or "").startswith(DRAFT_PREFIX):
        return current
    return _merge_request(request(target, "PUT", path,
                                  {"title": current.title[len(DRAFT_PREFIX):]}))


def assign_mr(target: str, mr, assignee) -> forge.MergeRequest:
    path, why = _mr_path(target, mr)
    if why:
        return forge.MergeRequest(reason=why)
    return _merge_request(request(target, "PUT", path, {"assignee_id": assignee}))


def mr_status(target: str, mr) -> forge.MergeRequest:
    path, why = _mr_path(target, mr)
    if why:
        return forge.MergeRequest(reason=why)
    return _merge_request(request(target, "GET", path))


def token_user(target: str) -> forge.TokenUser:
    reply = request(target, "GET", "/user")
    if reply.reason:
        return forge.TokenUser(reason=reply.reason)
    data = reply.data if isinstance(reply.data, dict) else {}
    if not isinstance(data.get("username"), str):
        return forge.TokenUser(reason="в ответе GET /user нет имени пользователя")
    return forge.TokenUser(data["username"])


def token_expiry(target: str) -> forge.TokenExpiry:
    reply = request(target, "GET", "/personal_access_tokens/self")
    if reply.reason:
        return forge.TokenExpiry(reason=reply.reason)
    data = reply.data if isinstance(reply.data, dict) else {}
    value = data.get("expires_at")
    if value is None and "expires_at" in data:
        return forge.TokenExpiry(note="без срока")
    try:
        return forge.TokenExpiry(datetime.date.fromisoformat(str(value)))
    except ValueError:
        return forge.TokenExpiry(reason=f"срок токена {value!r} не разобран")


def protections(target: str) -> forge.Protections:
    project, _entry, why = _project(target)
    if why:
        return forge.Protections(reason=why)
    names = []
    for kind in ("protected_branches", "protected_tags"):
        items, why = _read_all(target, f"/projects/{project}/{kind}", {})
        if items is None:
            return forge.Protections(reason=why)
        names.append([str(i.get("name")) for i in items if isinstance(i, dict)])
    return forge.Protections(*names)


def project_info(target: str) -> forge.ProjectInfo:
    project, _entry, why = _project(target)
    if why:
        return forge.ProjectInfo(reason=why)
    reply = request(target, "GET", f"/projects/{project}")
    if reply.reason:
        return forge.ProjectInfo(reason=reply.reason)
    data = reply.data if isinstance(reply.data, dict) else {}
    permissions = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}
    levels = [access.get("access_level") for access in permissions.values()
              if isinstance(access, dict)]
    levels = [lv for lv in levels if isinstance(lv, int) and not isinstance(lv, bool)]
    return forge.ProjectInfo(data.get("default_branch"), max(levels, default=None))


def branch_pipeline(target: str, branch: str) -> forge.BranchPipeline:
    project, entry, why = _project(target)
    if why:
        return forge.BranchPipeline(reason=why)
    query = urllib.parse.urlencode({"ref": branch, "order_by": "id", "sort": "desc",
                                    "per_page": 1})
    reply = request(target, "GET", f"/projects/{project}/pipelines?{query}")
    if reply.reason:
        return forge.BranchPipeline(reason=reply.reason)
    pipelines = [p for p in reply.data or [] if isinstance(p, dict)
                 and isinstance(p.get("id"), int)] if isinstance(reply.data, list) else []
    if not pipelines:
        return forge.BranchPipeline(verdict=forge.NONE,
                                    reason=f"у ветки {branch} нет конвейеров")
    last = max(pipelines, key=lambda p: p["id"])
    findings, jobs, _failed, _marks = _pipeline_findings(target, project, last,
                                                         _required(entry))
    verdict, reason = _verdict(findings)
    return forge.BranchPipeline(str(last.get("sha", "")), verdict, reason, jobs)
