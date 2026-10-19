"""Пакет orchestrator/doctor -- проверки записи внешнего проекта: клон, пуш, CI, защита ветки, токен, права токена на CI, no_paths, project_skills, компоненты.

SPEC 01M545EDTHS47HSB59AKC1EZ9C, требования 5-7; права токена на CI —
SPEC 01M574A6YQHAPASS9716Z11G4Q, требование 8; версии инструментов, карта
путей CI и каталоги компонентов — SPEC 01M58PG72PG64GS790XM2EWS61,
требования 2-8. Коллаборанты читаются лениво через фасад doctor (см.
докстринг orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
import json
import os
import re
import time
from pathlib import Path

from orchestrator import doctor

ROLE_SKIP = "пропуск: только в сессии Оператора (процесс роли)"
NOT_APPLICABLE = "неприменимо: запись артели — проверка внешнего проекта"
# Проба права пуша — имя ссылки, которой у задач не бывает (не ULID).
PUSH_PROBE_REF = "refs/artifacts/doctor-push-probe"
CI_WAIT_WARNING = ("ни один .github/workflows/*.yml клона не объявляет "
                   "триггер pull_request — verifying будет ждать до потолка")

_ON_KEY_RE = re.compile(r"""^(?:on|"on"|'on')\s*:\s*(.*)$""")
_CHILD_RE = re.compile(r"^(\s+)(?:-\s*)?([A-Za-z_][\w-]*)\s*(?::.*)?$")


def _names(project: str) -> list[str]:
    return [f"project-{kind}-{project}" for kind in
            ("clone", "artifacts-push", "ci-pull-request", "base-protection",
             "token", "ci-token", "no-paths", "skills")]


def project_entry_checks(name: str, entry: dict) -> list:
    """Строки п.5 по записи `name`: у артели — «неприменимо» на каждую
    (требование 6), в процессе роли 5.1/5.2/5.5 — именованный пропуск без
    сети и без связки ключей (требование 7)."""
    names = _names(name)
    if doctor.repo_context.is_artel(name):
        return [doctor.Check(n, "skip", NOT_APPLICABLE) for n in names]
    clone = doctor.repo_context.clone_path(name)
    in_role = doctor.runner.in_role_environment()
    clone_name, push_name, ci_name, prot_name, token_name, ci_token_name, \
        paths_name, skills_name = names
    return [
        (doctor.Check(clone_name, "skip", ROLE_SKIP) if in_role
         else check_clone(clone_name, clone, entry)),
        (doctor.Check(push_name, "skip", ROLE_SKIP) if in_role
         else check_artifacts_push(push_name, clone)),
        check_ci_pull_request(ci_name, clone),
        check_base_protection(prot_name, name, entry),
        (doctor.Check(token_name, "skip", ROLE_SKIP) if in_role
         else check_project_token(token_name, name, entry)),
        (doctor.Check(ci_token_name, "skip", ROLE_SKIP) if in_role
         else check_ci_token(ci_token_name, name, entry)),
        check_no_paths(paths_name, clone, entry),
        check_project_skills(skills_name, name, entry),
    ]


def check_clone(check_name: str, clone: Path, entry: dict):
    """5.1: клон есть, `origin` = `url` записи, давность `FETCH_HEAD` до
    собственного fetch, затем fetch (рабочие копии он не трогает)."""
    if not clone.is_dir():
        return doctor.Check(check_name, "fail", f"клона нет: {clone}")
    url = doctor.gitcmd.in_repo(clone, "remote", "get-url", "origin")
    origin = url.stdout.strip() if url is not None and url.returncode == 0 else ""
    if doctor.gitcmd.url_key(origin) != doctor.gitcmd.url_key(str(entry.get("url", ""))):
        return doctor.Check(check_name, "fail",
                            f"origin клона {origin or '(не прочитан)'} не "
                            f"совпадает с url записи {entry.get('url')}")
    fetch_head = clone / ".git" / "FETCH_HEAD"
    try:
        age_hours = (time.time() - fetch_head.stat().st_mtime) / 3600
    except OSError:
        age_hours = None
    res = doctor.gitcmd.in_repo(clone, "fetch", "-q", "origin")
    if res is None or res.returncode != 0:
        err = (res.stderr or res.stdout).strip()[:200] if res is not None else ""
        return doctor.Check(check_name, "fail",
                            f"fetch клона не прошёл: {err or 'git не ответил'}")
    if age_hours is None:
        return doctor.Check(check_name, "warn",
                            f"клон ещё не обновлялся пультом ({clone}); fetch прошёл")
    if age_hours > doctor.config.PROJECT_CLONE_STALE_HOURS:
        return doctor.Check(check_name, "warn",
                            f"клон не обновлялся {int(age_hours)} ч "
                            f"(порог {doctor.config.PROJECT_CLONE_STALE_HOURS} ч); "
                            f"fetch прошёл")
    return doctor.Check(check_name, "ok", f"клон {clone} свежий, fetch прошёл")


def check_artifacts_push(check_name: str, clone: Path):
    """5.2: пробный `push --dry-run` в `refs/artifacts/*` с токеном
    проекта (`gitcmd.git`)."""
    if not clone.is_dir():
        return doctor.Check(check_name, "fail", f"клона нет: {clone}")
    res = doctor.gitcmd.in_repo(clone, "push", "--dry-run", "-q", "origin",
                                f"HEAD:{PUSH_PROBE_REF}")
    if res is None or res.returncode != 0:
        err = (res.stderr or res.stdout).strip()[:200] if res is not None else ""
        return doctor.Check(check_name, "fail",
                            f"пробный push в refs/artifacts/* отказан: "
                            f"{err or 'git не ответил'}")
    return doctor.Check(check_name, "ok",
                        "пробный push --dry-run в refs/artifacts/* прошёл")


def declares_pull_request(text: str) -> bool:
    """Ключ `on:` workflow объявляет `pull_request` — строкой, списком
    или отображением (разбор текста, без сети)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _ON_KEY_RE.match(line)
        if not m:
            continue
        value = m.group(1).split("#", 1)[0].strip()
        if value:
            items = value.strip("[]").split(",")
            return "pull_request" in {s.strip().strip("'\"") for s in items}
        indent = None
        for child in lines[i + 1:]:
            if not child.strip() or child.lstrip().startswith("#"):
                continue
            if not child[:1].isspace():
                break
            c = _CHILD_RE.match(child)
            if c is None:
                continue
            width = len(c.group(1))
            indent = width if indent is None else indent
            if width == indent and c.group(2) == "pull_request":
                return True
        return False
    return False


def check_ci_pull_request(check_name: str, clone: Path):
    """5.3: `.github/workflows/*.yml` дерева клона с триггером
    `pull_request`."""
    workflows = clone / ".github" / "workflows"
    if not clone.is_dir():
        return doctor.Check(check_name, "warn",
                            f"клона нет — {CI_WAIT_WARNING}")
    found = []
    for path in sorted(workflows.glob("*.yml")) if workflows.is_dir() else []:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if declares_pull_request(text):
            found.append(path.name)
    if not found:
        return doctor.Check(check_name, "warn", CI_WAIT_WARNING)
    return doctor.Check(check_name, "ok",
                        f"триггер pull_request: {', '.join(found)}")


def _owner_repo(url: str) -> tuple[str, str] | None:
    parts = [p for p in re.split(r"[/:]", doctor.gitcmd.url_key(url)) if p]
    return (parts[-2], parts[-1]) if len(parts) >= 2 else None


def _protection_summary(data) -> str:
    if not isinstance(data, dict):
        return str(data)[:200]
    reviews = data.get("required_pull_request_reviews") or {}
    admins = data.get("enforce_admins") or {}
    checks = data.get("required_status_checks") or {}
    return (f"одобрений требуется: "
            f"{reviews.get('required_approving_review_count', 'нет')}, "
            f"enforce_admins: {admins.get('enabled', 'нет')}, обязательные "
            f"проверки: {', '.join(checks.get('contexts') or []) or 'нет'}")


def check_base_protection(check_name: str, name: str, entry: dict):
    """5.4 (информационная): защита базовой ветки по `gh api` с токеном
    проекта; данных нет — «недоступно», не fail."""
    base = entry.get("base", doctor.config.MAIN_BRANCH)
    pair = _owner_repo(str(entry.get("url", "")))
    if pair is None:
        return doctor.Check(check_name, "skip",
                            "защита базовой ветки: недоступно — url записи не разобран")
    if doctor.shutil.which("gh") is None:
        return doctor.Check(check_name, "skip",
                            "защита базовой ветки: недоступно — gh CLI не найден")
    env, refusal = doctor.gh_env(name, entry)
    if refusal is not None:
        return doctor.Check(check_name, "skip",
                            f"защита базовой ветки: недоступно — {refusal}")
    owner, repo = pair
    try:
        res = doctor.subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/branches/{base}/protection"],
            capture_output=True, text=True,
            timeout=doctor.config.GH_TIMEOUT_SEC, env=env)
    except (OSError, doctor.subprocess.TimeoutExpired) as exc:
        return doctor.Check(check_name, "skip",
                            f"защита базовой ветки: недоступно — {exc}")
    if res.returncode != 0:
        return doctor.Check(check_name, "skip",
                            f"защита базовой ветки {base}: недоступно — "
                            f"{(res.stderr or res.stdout).strip()[:200]}")
    try:
        summary = _protection_summary(json.loads(res.stdout))
    except ValueError:
        summary = res.stdout.strip()[:200]
    return doctor.Check(check_name, "ok", f"защита базовой ветки {base}: {summary}")


def _operator_gh_token() -> str | None:
    if doctor.shutil.which("gh") is None:
        return None
    try:
        res = doctor.subprocess.run(["gh", "auth", "token"],
                                    capture_output=True, text=True,
                                    timeout=doctor.config.GH_TIMEOUT_SEC)
    except (OSError, doctor.subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def check_project_token(check_name: str, name: str, entry: dict):
    """5.5: токен в слоте `token_slot`; совпадение с токеном `gh`
    Оператора — warn (`docs/triggers.md` №24). Значения в вывод не идут."""
    slot = entry.get("token_slot")
    if not slot:
        return doctor.Check(check_name, "warn",
                            "нет токена проекта: поле token_slot записи не "
                            "задано — операции хостинга идут с авторизацией "
                            "Оператора")
    token = doctor.keychain.token(slot)
    if not token:
        return doctor.Check(check_name, "fail",
                            f"слот {slot} связки ключей пуст — операции "
                            f"хостинга проекта {name} отказывают")
    if token == _operator_gh_token():
        return doctor.Check(check_name, "warn",
                            f"токен слота {slot} совпадает с токеном gh "
                            f"Оператора: одобрение своим же токеном "
                            f"технически возможно — docs/triggers.md №24")
    return doctor.Check(check_name, "ok",
                        f"токен проекта есть в слоте {slot}, отличен от "
                        f"токена gh Оператора")


CI_TOKEN_ACTIONS_WARNING = ("CI читается по Actions runs; для check-runs "
                            "токену нужно право Checks: read")
_HTTP_CODE_RE = re.compile(r"\(HTTP ([1-5][0-9][0-9])\)")


class _GhProbe:
    """Исход одного чтения `gh api`: `http` — код HTTP-отказа (None —
    ответ получен либо HTTP-ответа нет вовсе); `network` — HTTP-ответа нет
    (обрыв, таймаут); `ok` — ответ получен и несёт список `key`."""

    def __init__(self, ok: bool, http: int | None, network: bool, detail: str):
        self.ok, self.http, self.network, self.detail = ok, http, network, detail

    def forbidden(self) -> bool:
        return self.http == 403 and doctor.ci.checks_forbidden(self.detail)

    def throttled(self) -> bool:
        """403 не про права (лимит запросов и пр.) — отказ временный."""
        return self.http == 403 and not self.forbidden()

    def denied(self) -> bool:
        """Отказ правами: 403 «Resource not accessible …», 401, 404
        (ANSWER-1 задачи 01M574A6YQHAPASS9716Z11G4Q)."""
        return self.forbidden() or self.http in (401, 404)


def _gh_probe(endpoint: str, key: str, env) -> _GhProbe:
    try:
        res = doctor.subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True,
            timeout=doctor.config.GH_TIMEOUT_SEC, env=env)
    except doctor.subprocess.TimeoutExpired as exc:
        return _GhProbe(False, None, True, str(exc))
    except OSError as exc:
        return _GhProbe(False, None, True, f"gh не запущен: {exc}")
    if res.returncode != 0:
        detail = (res.stderr or res.stdout).strip()[:200]
        match = _HTTP_CODE_RE.search(res.stderr or "")
        if match is None:
            return _GhProbe(False, None, True,
                            detail or f"код {res.returncode}")
        return _GhProbe(False, int(match.group(1)), False, detail)
    try:
        payload = json.loads(res.stdout)
    except ValueError:
        return _GhProbe(False, None, False, "ответ gh не разобран")
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return _GhProbe(False, None, False, f"в ответе gh нет списка {key}")
    return _GhProbe(True, None, False, "")


def check_ci_token(check_name: str, name: str, entry: dict):
    """Читает ли токен проекта проверки коммита вершины базовой ветки
    (check-runs) и запуски Actions (SPEC 01M574A6YQHAPASS9716Z11G4Q,
    требование 8). Без права Checks статус CI пульт берёт из Actions
    (`ci.checks_forbidden`) — это `warn`; иной отказ check-runs или
    недоступные Actions — `fail`: статус CI проекта пульт не узнает.
    Временный отказ (сеть, 403 лимита, у Actions — всякий отказ не
    правами) прав не определяет — `skip`."""
    base = entry.get("base", doctor.config.MAIN_BRANCH)
    pair = _owner_repo(str(entry.get("url", "")))
    if pair is None:
        return doctor.Check(check_name, "skip",
                            "права токена на CI: не проверены — url записи "
                            "не разобран")
    if doctor.shutil.which("gh") is None:
        return doctor.Check(check_name, "skip",
                            "права токена на CI: не проверены — gh CLI не найден")
    env, refusal = doctor.gh_env(name, entry)
    if refusal is not None:
        return doctor.Check(check_name, "skip",
                            f"права токена на CI: не проверены — {refusal}")
    owner, repo = pair
    checks = _gh_probe(f"repos/{owner}/{repo}/commits/{base}/check-runs"
                       f"?per_page=1", "check_runs", env)
    actions = _gh_probe(f"repos/{owner}/{repo}/actions/runs?branch={base}"
                        f"&per_page=1", "workflow_runs", env)
    for what, probe in (("check-runs", checks), ("Actions", actions)):
        if probe.network:
            return doctor.Check(check_name, "skip",
                                f"права токена на CI: не проверены — {what}: "
                                f"нет ответа GitHub ({probe.detail})")
        if probe.throttled():
            return doctor.Check(check_name, "skip",
                                f"права токена на CI: не проверены — {what}: "
                                f"временный отказ 403 ({probe.detail})")
    # `fail` за Actions — только отказ правами; 5xx и неразобранный ответ
    # прав не определяют (ANSWER-1 задачи 01M574A6YQHAPASS9716Z11G4Q).
    if not actions.ok and not actions.denied():
        return doctor.Check(check_name, "skip",
                            f"права токена на CI: не проверены — Actions: "
                            f"отказ не про права ({actions.detail})")
    if not actions.ok:
        return doctor.Check(check_name, "fail",
                            f"запуски Actions недоступны токену проекта "
                            f"({actions.detail}) — статус CI проекта пульт "
                            f"не увидит")
    if checks.ok:
        return doctor.Check(check_name, "ok",
                            f"токен проекта читает check-runs вершины {base} "
                            f"и запуски Actions")
    if checks.forbidden():
        return doctor.Check(check_name, "warn",
                            f"{CI_TOKEN_ACTIONS_WARNING} ({checks.detail})")
    return doctor.Check(check_name, "fail",
                        f"check-runs вершины {base} не читаются "
                        f"({checks.detail}) — на таком отказе статус CI "
                        f"проекта пульт не узнает")


def check_no_paths(check_name: str, clone: Path, entry: dict):
    """5.6: каждый путь `no_paths` есть в дереве клона; маска — хотя бы
    одним совпадением среди файлов клона."""
    if not clone.is_dir():
        return doctor.Check(check_name, "skip", f"клона нет: {clone}")
    files = None
    missing = []
    for rel in entry.get("no_paths") or []:
        rel = str(rel)
        if "*" in rel:
            if files is None:
                res = doctor.gitcmd.in_repo(clone, "ls-files")
                files = (res.stdout.splitlines()
                         if res is not None and res.returncode == 0 else [])
            if not any(doctor.project_profile.mask_matches(rel, f) for f in files):
                missing.append(rel)
        elif not (clone / rel).exists():
            missing.append(rel)
    if missing:
        return doctor.Check(check_name, "warn",
                            f"пути no_paths нет в дереве клона: {', '.join(missing)}")
    return doctor.Check(check_name, "ok", "все пути no_paths есть в дереве клона")


def check_project_skills(check_name: str, name: str, entry: dict):
    """5.7: `project_skills` записи — проверкой части 1."""
    refusal = doctor.brief.project_skills_refusal(name, entry)
    if refusal:
        return doctor.Check(check_name, "fail", refusal)
    return doctor.Check(check_name, "ok", "project_skills записи годны")


# --- компоненты записи -----------------------------------------------------

# Тот же таймаут, что у `claude --version`/`codex --version` (preflight).
TOOL_VERSION_TIMEOUT_SEC = 10
MULTILINE_VALUE = "многострочное значение не сравнивается"
_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")
_BLOCK_INDICATORS = (">-", ">", "|-", "|")


def component_checks(name: str, entry: dict) -> list:
    """Строки компонентов записи `name`: на каждый инструмент `tools`, на
    компонент с `paths_source`, на компонент с `workdir`. Запись с
    `test_profile` (и без `components:`) строк не получает (требование 8)."""
    comps = entry.get(doctor.targets.COMPONENTS_FIELD)
    if not isinstance(comps, dict):
        return []
    clone = doctor.repo_context.clone_path(name)
    checks = []
    for comp, fields in comps.items():
        prefix = f"{name}-{comp}"
        env = fields.get("env") or {}
        for tool, required in (fields.get("tools") or {}).items():
            checks.append(check_tool_version(
                f"project-tools-{prefix}-{tool}", tool, str(required),
                env.get("PATH")))
        if fields.get("paths_source"):
            checks.append(check_paths_source(f"project-paths-{prefix}",
                                             clone, fields))
        if fields.get("workdir"):
            checks.append(check_workdir(f"project-workdir-{prefix}", clone,
                                        str(fields["workdir"])))
    return checks


def version_matches(required: str, shown: str) -> bool:
    """Версия `shown` совпадает с требуемой по стольким числовым частям,
    сколько их в `required`: числа, не префикс строки (`3.1` ≠ `3.12`)."""
    want = [int(part) for part in required.split(".")]
    got = [int(part) for part in shown.split(".")]
    return got[:len(want)] == want


def check_tool_version(check_name: str, tool: str, required: str,
                       env_path: str | None):
    """`<tool> --version` с `PATH` компонента (`env.PATH`, иначе `PATH`
    процесса doctor) против требуемой версии — текста до первого пробела."""
    path = env_path if env_path is not None else os.environ.get("PATH", "")
    wanted = required.split()[0] if required.split() else ""
    if not re.fullmatch(_VERSION_RE, wanted):
        return doctor.Check(check_name, "skip",
                            f"{tool}: требуемая версия «{required}» не "
                            f"разобрана — ожидаются числа через точку")
    found = doctor.shutil.which(tool, path=path)
    if found is None:
        return doctor.Check(check_name, "fail",
                            f"{tool} не найден в PATH {path or '(пусто)'}")
    try:
        res = doctor.subprocess.run(
            [found, "--version"], capture_output=True, text=True,
            timeout=TOOL_VERSION_TIMEOUT_SEC,
            env={**os.environ, "PATH": path})
    except (OSError, doctor.subprocess.TimeoutExpired) as exc:
        return doctor.Check(check_name, "skip",
                            f"{tool} --version не выполнен: {exc}")
    if res.returncode != 0:
        return doctor.Check(check_name, "skip",
                            f"{tool} --version завершился с кодом "
                            f"{res.returncode}")
    match = (_VERSION_RE.search(res.stdout or "")
             or _VERSION_RE.search(res.stderr or ""))
    if match is None:
        return doctor.Check(check_name, "skip",
                            f"{tool} --version: в выводе нет версии")
    if not version_matches(wanted, match.group(0)):
        return doctor.Check(check_name, "fail",
                            f"{tool} ({found}): версия {match.group(0)}, "
                            f"требуется {wanted}")
    return doctor.Check(check_name, "ok",
                        f"{tool} ({found}): версия {match.group(0)}, "
                        f"требуется {wanted}")


def _unquote(raw: str) -> str:
    """Значение без кавычек; без кавычек — как есть, без хвостового
    комментария ` #…`."""
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        if end > 0:
            return raw[1:end]
        return raw
    return re.sub(r"\s+#.*$", "", raw).strip()


def _block_value(lines: list, indent: int) -> tuple[str | None, str]:
    """Значение блока `>-`/`>`/`|-`/`|`: строки с отступом больше
    `indent`. Одна строка — значение; несколько — не сравнивается."""
    content = []
    for line in lines:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            break
        content.append(line.strip())
    if len(content) > 1:
        return None, MULTILINE_VALUE
    return (content[0] if content else ""), ""


def find_variable(text: str, key: str) -> tuple[str | None, str]:
    """(значение, "") переменной `key` текста файла — ключ YAML (в
    кавычках, без них или блоком) либо присваивание оболочки с `export`
    или без; (None, причина) — не найдено или не сравнивается. Строки-
    комментарии пропускаются (требование 6)."""
    name = re.escape(key)
    yaml_key = re.compile(rf"^(\s*){name}\s*:(?:\s+(.*))?$")
    shell_key = re.compile(rf"^\s*(?:export\s+)?{name}=(.*)$")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        m = yaml_key.match(line)
        if m:
            raw = (m.group(2) or "").strip()
            if re.sub(r"\s+#.*$", "", raw) in _BLOCK_INDICATORS:
                return _block_value(lines[i + 1:], len(m.group(1)))
            return _unquote(raw), ""
        m = shell_key.match(line)
        if m:
            return _unquote(m.group(1).strip()), ""
    return None, f"переменной {key} нет"


def _top_level(body: str) -> tuple[list | None, int | None, str]:
    """(альтернативы по `|` верхнего уровня, индекс скобки, закрывающей
    ведущую `(`, "") либо (None, None, причина) — скобки не
    сбалансированы. `|` внутри `()`/`[]` и после `\\` не делит."""
    parts, start, depth, in_class, escaped = [], 0, 0, False, False
    lead_close = None
    for i, ch in enumerate(body):
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return None, None, "несбалансированные скобки"
            if depth == 0 and lead_close is None and body.startswith("("):
                lead_close = i
        elif ch == "|" and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    if depth or in_class or escaped:
        return None, None, "несбалансированные скобки"
    parts.append(body[start:])
    return parts, lead_close, ""


def regex_alternatives(text: str) -> tuple[set | None, str]:
    """Множество альтернатив верхнего уровня строки регулярного выражения
    (требование 5); (None, причина) — строку не разобрать."""
    if not text:
        return None, "пустое значение"
    body = text[1:] if text.startswith("^") else text
    parts, lead_close, reason = _top_level(body)
    if parts is None:
        return None, reason
    if lead_close is not None:
        if lead_close == len(body) - 1:
            parts, _, reason = _top_level(body[1:-1])
            if parts is None:
                return None, reason
        elif body[lead_close + 1] != "|":
            return None, f"хвост «{body[lead_close + 1:]}» после ведущей группы"
    if not body or any(part == "" for part in parts):
        return None, "пустая альтернатива"
    return set(parts), ""


def _regex_strings(value) -> list:
    if value is None:
        return []
    return [str(value)] if isinstance(value, str) else [str(v) for v in value]


def check_paths_source(check_name: str, clone: Path, fields: dict):
    """Альтернативы переменной `paths_source` в файле клона против
    объединения `paths` компонента и `paths` его `depends_on` вида
    `paths`/`files` (требования 4-6); порядок не важен."""
    source = fields["paths_source"]
    rel, key = str(source.get("file")), str(source.get("key"))
    path = clone / rel
    if not path.is_file():
        return doctor.Check(check_name, "skip", f"файла {rel} в клоне {clone} нет")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return doctor.Check(check_name, "skip", f"{rel} не прочитан: {exc}")
    value, reason = find_variable(text, key)
    if value is None:
        return doctor.Check(check_name, "skip", f"{rel}: {key}: {reason}")
    got, reason = regex_alternatives(value)
    if got is None:
        return doctor.Check(check_name, "skip",
                            f"{rel}: значение {key} «{value}» не разобрано: "
                            f"{reason}")
    strings = _regex_strings(fields.get("paths"))
    for dep in (fields.get("depends_on") or {}).values():
        if dep.get("via") in ("paths", "files"):
            strings += _regex_strings(dep.get("paths"))
    want = set()
    for item in strings:
        alts, reason = regex_alternatives(item)
        if alts is None:
            return doctor.Check(check_name, "skip",
                                f"строка paths «{item}» не разобрана: {reason}")
        want |= alts
    if got == want:
        return doctor.Check(check_name, "ok",
                            f"{rel}: {key} совпадает с paths компонента "
                            f"({len(got)} альтернатив)")
    extra = ", ".join(sorted(got - want)) or "нет"
    missing = ", ".join(sorted(want - got)) or "нет"
    return doctor.Check(check_name, "warn",
                        f"{rel}: {key} «{value}» ≠ paths компонента "
                        f"«{', '.join(strings)}» (лишние в {key}: {extra}; "
                        f"недостающие: {missing})")


def check_workdir(check_name: str, clone: Path, workdir: str):
    """Каталог `workdir` компонента есть в клоне проекта (требование 7)."""
    if (clone / workdir).is_dir():
        return doctor.Check(check_name, "ok", f"каталог {workdir} есть в клоне")
    return doctor.Check(check_name, "fail",
                        f"каталога {workdir} нет в клоне {clone}")
