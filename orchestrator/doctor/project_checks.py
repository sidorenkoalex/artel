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
import shlex
import time
import urllib.parse
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
    # Путь хостинга с конвейерами (GitLab) — по `forge.ci_by_pipeline`, без
    # сравнения значения `forge` с литералом (SPEC 01M6EZXVFGH5Z2876XWMQG35FP,
    # требования 1-2): строки этого пути не зовут `gh`.
    by_pipeline = doctor.forge.ci_by_pipeline(name)
    checks = [
        (doctor.Check(clone_name, "skip", ROLE_SKIP) if in_role
         else check_clone(clone_name, clone, entry)),
        (doctor.Check(push_name, "skip", ROLE_SKIP) if in_role
         else check_artifacts_push(push_name, clone)),
        (check_workflow_rules(ci_name, clone, entry) if by_pipeline
         else check_ci_pull_request(ci_name, clone)),
        (check_forge_protection(prot_name, name, entry) if by_pipeline
         else check_base_protection(prot_name, name, entry)),
        (doctor.Check(token_name, "skip", ROLE_SKIP) if in_role
         else check_project_token(token_name, name, entry,
                                  compare_gh=not by_pipeline)),
        (doctor.Check(ci_token_name, "skip", ROLE_SKIP) if in_role
         else check_forge_ci_token(ci_token_name, name, entry) if by_pipeline
         else check_ci_token(ci_token_name, name, entry)),
        check_no_paths(paths_name, clone, entry),
        check_project_skills(skills_name, name, entry),
    ]
    if doctor.targets.merged_by_project_people(entry):
        # Хостинг без конвейеров (GitHub): каталог workflow правит любой
        # прогон CI ветки, а не только полный набор компонента — строка
        # всегда (SPEC 01M6N7CYKDAMAKENX60CBK7VQX, требование 3).
        if not by_pipeline:
            checks.append(check_workflows_dir_no_paths(
                f"project-ci-file-no-paths-{name}", entry))
        elif _ci_components(entry):
            checks.append(check_ci_file_no_paths(
                f"project-ci-file-no-paths-{name}", entry))
        checks.append(check_submodules(f"project-submodules-{name}", clone,
                                       entry, in_role))
    elif entry.get(doctor.targets.SUBMODULE_TOKENS_FIELD):
        # Подмодули с токенами своих слотов (SPEC 01M6P1Z0ZHVNDYWN3FZSZWBCG3,
        # требование 5): строка — при любом `merge_gate`.
        checks.append(check_submodules(f"project-submodules-{name}", clone,
                                       entry, in_role))
    return checks


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


def check_project_token(check_name: str, name: str, entry: dict,
                        compare_gh: bool = True):
    """5.5: токен в слоте `token_slot`; совпадение с токеном `gh`
    Оператора — warn (`docs/triggers.md` №24). Значения в вывод не идут.
    `compare_gh` ложно (хостинг с конвейерами) — `gh auth token` не
    зовётся, текст называет несделанную сверку (SPEC
    01M6EZXVFGH5Z2876XWMQG35FP, требование 7)."""
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
    if not compare_gh:
        return doctor.Check(check_name, "ok",
                            f"токен проекта есть в слоте {slot}; сверка с "
                            f"токеном gh Оператора не делалась — хостинг "
                            f"проекта читается не через gh")
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
    human = doctor.targets.merged_by_project_people(entry)
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
        if human and fields.get("full_suite") in CI_FULL_SUITES:
            checks.append(check_ci_reruns(f"project-ci-reruns-{prefix}", clone,
                                          fields))
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


# --- хостинг с конвейерами (GitLab) и записи с target-human -----------------
# SPEC 01M6EZXVFGH5Z2876XWMQG35FP, требования 3-14; ANSWER-1 той же задачи.

CI_FILE = ".gitlab-ci.yml"
CI_FILE_MISSING = f"файла {CI_FILE} нет — конвейер ветки не создаётся"
CI_UNPARSED = f"{CI_FILE} не разобран"
CI_FULL_SUITES = ("ci", "both")
# Уровень доступа Maintainer API v4: ниже него защиты отдаются неполно.
MAINTAINER_LEVEL = 40
DENIED_HTTP = (401, 403, 404)
NO_TOKEN_SLOT = "нет token_slot — запрос шёл бы с авторизацией Оператора"
# Образцовые подстановки шаблона ветки задачи (`{id}` — в нижнем регистре,
# как `catalog.branch_name`).
SAMPLE_TASK_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"
SAMPLE_SLUG = "sample-task"
SAMPLE_REF = "ref-1"


def _ci_components(entry: dict) -> list:
    """Компоненты записи с полным прогоном в CI (`full_suite` ci/both)."""
    comps = entry.get(doctor.targets.COMPONENTS_FIELD)
    if not isinstance(comps, dict):
        return []
    return [comp for comp, fields in comps.items()
            if isinstance(fields, dict) and fields.get("full_suite") in CI_FULL_SUITES]


def check_forge_protection(check_name: str, name: str, entry: dict):
    """Защиты проекта по `forge.project_info`/`forge.protections`
    (требование 3); информационная — данных нет — `skip`, не `fail`."""
    if not entry.get("token_slot"):
        return doctor.Check(check_name, "skip", f"защиты: не проверены — {NO_TOKEN_SLOT}")
    info = doctor.forge.project_info(name)
    if info.reason or info.access_level is None:
        return doctor.Check(check_name, "skip",
                            f"защиты: недоступно — "
                            f"{info.reason or 'уровень доступа токена не прочитан'}")
    if info.access_level < MAINTAINER_LEVEL:
        return doctor.Check(check_name, "skip",
                            f"защиты: не проверены — уровень доступа токена "
                            f"{info.access_level}, нужна роль Maintainer "
                            f"({MAINTAINER_LEVEL}): с меньшей ролью API отдаёт "
                            f"защиты неполно")
    prot = doctor.forge.protections(name)
    if prot.reason:
        return doctor.Check(check_name, "skip", f"защиты: недоступно — {prot.reason}")
    return doctor.Check(check_name, "ok",
                        f"защищённые ветки: {', '.join(prot.branches or []) or '(нет)'}; "
                        f"защищённые теги: {', '.join(prot.tags or []) or '(нет)'}")


def check_forge_ci_token(check_name: str, name: str, entry: dict):
    """Читает ли токен проекта конвейер базовой ветки (`forge.branch_pipeline`,
    требование 5): итог прочитан — `ok`; отказ правами по `http_status` —
    `fail`; иной отказ — `skip`. Отказ чтения заданий решает и при
    прочитанном итоге (ANSWER-1 п. 3). Текст `reason` не разбирается."""
    if not entry.get("token_slot"):
        return doctor.Check(check_name, "skip",
                            f"права токена на CI: не проверены — {NO_TOKEN_SLOT}")
    base = entry.get("base", doctor.config.MAIN_BRANCH)
    pipeline = doctor.forge.branch_pipeline(name, base)
    if pipeline.http_status in DENIED_HTTP:
        return doctor.Check(check_name, "fail",
                            f"конвейер ветки {base} недоступен токену проекта "
                            f"({pipeline.reason}) — статус CI проекта пульт "
                            f"не увидит")
    if pipeline.http_status is not None or pipeline.verdict == doctor.forge.UNKNOWN:
        return doctor.Check(check_name, "skip",
                            f"права токена на CI: не проверены — временный "
                            f"отказ ({pipeline.reason or 'итог не прочитан'})")
    return doctor.Check(check_name, "ok",
                        f"токен проекта читает конвейер ветки {base}: итог "
                        f"{pipeline.verdict}")


def check_ci_file_no_paths(check_name: str, entry: dict):
    """Файл CI покрыт `no_paths` записи — путём целиком или маской
    (требование 8): иначе роль может править конвейер своей ветки."""
    for rel in entry.get("no_paths") or []:
        rel = str(rel)
        if rel == CI_FILE or ("*" in rel
                              and doctor.project_profile.mask_matches(rel, CI_FILE)):
            return doctor.Check(check_name, "ok", f"{CI_FILE} покрыт no_paths записи ({rel})")
    return doctor.Check(check_name, "fail",
                        f"{CI_FILE} не покрыт no_paths записи — роль может "
                        f"править файл CI, по которому идёт полный прогон")


CI_WORKFLOWS_DIR = ".github/workflows/"
# Алфавит пробного имени файла каталога workflow.
_PROBE_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"


def _probe_file_name(entries: list) -> str:
    """Имя файла, которое не покрывает ни одна запись `entries`, кроме
    покрывающих весь каталог `CI_WORKFLOWS_DIR`: длиннее любой записи (не
    равно ни одному `**/<имя>`) и с первым символом, отличным от символа
    сразу после каталога в записях с этим началом (не под префиксом,
    длиннее каталога). "" — записи заняли весь `_PROBE_CHARS`: такой набор
    префиксов каталог одной записью не покрывает, строка — `fail`."""
    taken = {e[len(CI_WORKFLOWS_DIR)] for e in entries
             if e.startswith(CI_WORKFLOWS_DIR) and len(e) > len(CI_WORKFLOWS_DIR)}
    first = next((c for c in _PROBE_CHARS if c not in taken), None)
    if first is None:
        return ""
    return first * (max((len(e) for e in entries), default=0) + 1)


def check_workflows_dir_no_paths(check_name: str, entry: dict):
    """Каталог workflow GitHub покрыт `no_paths` записи для КАЖДОГО имени
    файла под ним по формуле гейта `config.is_protected_path` (SPEC
    01M6N7CYKDAMAKENX60CBK7VQX, требование 3): иначе роль может править
    workflow своей ветки. Проба самим путём каталога истинна и для `**/`,
    одним фиксированным именем — и для записи на отдельный файл; поэтому
    проба — имя, которого ни одна запись на отдельный файл не покрывает."""
    entries = [str(rel) for rel in entry.get("no_paths") or []]
    name = _probe_file_name(entries)
    probe = CI_WORKFLOWS_DIR + name
    covering = [rel for rel in entries
                if name and doctor.config.is_protected_path(probe, [rel])]
    if covering:
        return doctor.Check(check_name, "ok",
                            f"каталог {CI_WORKFLOWS_DIR} покрыт no_paths "
                            f"записи ({covering[0]})")
    return doctor.Check(check_name, "fail",
                        f"каталог {CI_WORKFLOWS_DIR} не покрыт no_paths "
                        f"записи целиком — роль может править workflow CI "
                        f"своей ветки")


# --- разбор файла CI (требование 12) ---------------------------------------

class CiFileError(Exception):
    """Форма файла CI вне подмножества разборщика; текст — место и причина."""


_QUOTE_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t"}


def _ci_quoted(text: str, i: int, no: int) -> tuple[str, int]:
    """(значение скаляра в кавычках с позиции `i`, позиция за ним)."""
    quote, out, j = text[i], [], i + 1
    while j < len(text):
        ch = text[j]
        if quote == "'" and ch == "'":
            if text[j + 1:j + 2] == "'":
                out.append("'")
                j += 2
                continue
            return "".join(out), j + 1
        if quote == '"' and ch == "\\" and j + 1 < len(text):
            out.append(_QUOTE_ESCAPES.get(text[j + 1], "\\" + text[j + 1]))
            j += 2
            continue
        if quote == '"' and ch == '"':
            return "".join(out), j + 1
        out.append(ch)
        j += 1
    raise CiFileError(f"строка {no}: незакрытая кавычка")


def _ci_unsupported_start(text: str, no: int) -> None:
    if text[:1] in ("&", "*"):
        raise CiFileError(f"строка {no}: якорь или ссылка ({text.split()[0]}) "
                          f"не поддержаны")
    if text[:1] == "!":
        raise CiFileError(f"строка {no}: тег ({text.split()[0]}) не поддержан")
    if text[:1] in ("|", ">"):
        raise CiFileError(f"строка {no}: многострочный скаляр не поддержан")


def _skip_spaces(text: str, i: int) -> int:
    while i < len(text) and text[i] == " ":
        i += 1
    return i


def _ci_flow(text: str, i: int, no: int, stops: str):
    """(узел потоковой формы `[…]`/`{…}`/скаляра с позиции `i`, позиция за
    ним); `stops` — символы, на которых кончается простой скаляр."""
    i = _skip_spaces(text, i)
    if i >= len(text):
        raise CiFileError(f"строка {no}: незакрытая потоковая форма")
    ch = text[i]
    if ch in "'\"":
        return _ci_quoted(text, i, no)
    if ch not in "[{":
        _ci_unsupported_start(text[i:], no)
        j = i
        while j < len(text) and text[j] not in stops and text[j] not in "[]{}":
            j += 1
        return text[i:j].strip(), j
    close = "]" if ch == "[" else "}"
    items: list = []
    result: dict = {}
    i += 1
    while True:
        i = _skip_spaces(text, i)
        if i >= len(text):
            raise CiFileError(f"строка {no}: незакрытая потоковая форма")
        if text[i] == close:
            return (items if ch == "[" else result), i + 1
        if ch == "[":
            item, i = _ci_flow(text, i, no, ",]")
            items.append(item)
        else:
            key, i = _ci_flow(text, i, no, ":,}")
            if text[i:i + 1] != ":" or not isinstance(key, str):
                raise CiFileError(f"строка {no}: в потоковом отображении нет "
                                  f"«ключ: значение»")
            result[key], i = _ci_flow(text, i + 1, no, ",}")
        i = _skip_spaces(text, i)
        if text[i:i + 1] == ",":
            i += 1
        elif text[i:i + 1] != close:
            raise CiFileError(f"строка {no}: потоковая форма не разобрана")


def _ci_scalar(text: str, no: int):
    """Значение после `ключ:` или `- `: скаляр либо потоковая форма."""
    _ci_unsupported_start(text, no)
    if text[0] not in "'\"[{":
        return text
    value, end = (_ci_quoted(text, 0, no) if text[0] in "'\""
                  else _ci_flow(text, 0, no, ""))
    if text[end:].strip():
        raise CiFileError(f"строка {no}: лишний текст после значения")
    return value


def _ci_strip_comment(text: str) -> str:
    """Строка без комментария ` #…` вне кавычек."""
    quote, escaped = None, False
    for i, ch in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif quote == '"' and ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or text[i - 1] in " \t:-[{,"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def _ci_key_split(content: str) -> tuple[str, str] | None:
    """(ключ, остаток) строки `ключ: значение`; None — строка не пара."""
    quote, depth = None, 0
    for i, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or content[i - 1] in " \t"):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and content[i + 1:i + 2] in ("", " ", "\t"):
            return content[:i].strip(), content[i + 1:].strip()
    return None


def _ci_is_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


class _CiParser:
    """Блочный YAML подмножества файла CI: отображения, блочные списки,
    скаляры, простые потоковые `[…]`/`{…}`. Значения — строки."""

    def __init__(self, text: str):
        self.lines = []
        for no, raw in enumerate(text.splitlines(), 1):
            body = raw.lstrip(" ")
            if not body.strip() or body.lstrip().startswith("#"):
                continue
            if body.startswith("\t"):
                raise CiFileError(f"строка {no}: табуляция в отступе")
            content = _ci_strip_comment(body)
            if not content or (content == "---" and not self.lines):
                continue
            if content in ("---", "...") or content.startswith("--- "):
                raise CiFileError(f"строка {no}: несколько документов не поддержаны")
            self.lines.append([no, len(raw) - len(body), content])
        self.i = 0

    def parse(self):
        if not self.lines:
            return {}
        value = self.block(self.lines[0][1])
        if self.i < len(self.lines):
            raise CiFileError(f"строка {self.lines[self.i][0]}: неожиданный отступ")
        return value

    def block(self, indent: int):
        if _ci_is_item(self.lines[self.i][2]):
            return self.sequence(indent)
        return self.mapping(indent)

    def nested(self, indent: int):
        """Значение пустого ключа или элемента: блок глубже либо None."""
        if self.i < len(self.lines) and self.lines[self.i][1] > indent:
            return self.block(self.lines[self.i][1])
        return None

    def sequence(self, indent: int) -> list:
        items = []
        while self.i < len(self.lines):
            no, ind, content = self.lines[self.i]
            if ind < indent or (ind == indent and not _ci_is_item(content)):
                break
            if ind > indent:
                raise CiFileError(f"строка {no}: неожиданный отступ")
            rest = content[1:].lstrip()
            if not rest:
                self.i += 1
                items.append(self.nested(indent))
            elif _ci_is_item(rest) or (rest[0] not in "'\"[{"
                                       and _ci_key_split(rest) is not None):
                # `- ключ: …` — отображение с отступом по колонке ключа.
                col = ind + len(content) - len(rest)
                self.lines[self.i] = [no, col, rest]
                items.append(self.block(col))
            else:
                items.append(_ci_scalar(rest, no))
                self.i += 1
        return items

    def mapping(self, indent: int) -> dict:
        result: dict = {}
        while self.i < len(self.lines):
            no, ind, content = self.lines[self.i]
            if ind < indent:
                break
            if ind > indent:
                raise CiFileError(f"строка {no}: неожиданный отступ")
            if _ci_is_item(content):
                raise CiFileError(f"строка {no}: элемент списка среди ключей "
                                  f"отображения")
            pair = _ci_key_split(content)
            if pair is None:
                raise CiFileError(f"строка {no}: ожидалась пара «ключ: значение»")
            key, rest = pair
            if key[:1] in ("'", '"'):
                key, _end = _ci_quoted(key, 0, no)
            if not key or key.startswith(("<<", "?", "&", "*", "!")):
                raise CiFileError(f"строка {no}: ключ «{key}» не поддержан")
            self.i += 1
            if rest:
                result[key] = _ci_scalar(rest, no)
            elif (self.i < len(self.lines) and self.lines[self.i][1] == indent
                  and _ci_is_item(self.lines[self.i][2])):
                result[key] = self.sequence(indent)
            else:
                result[key] = self.nested(indent)
        return result


def ci_document(clone: Path) -> tuple[dict | None, str]:
    """(разобранный файл CI клона, "") либо (None, причина): файла нет —
    `CI_FILE_MISSING`, иначе «… не разобран: <место>»."""
    path = clone / CI_FILE
    if not path.is_file():
        return None, CI_FILE_MISSING
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"{CI_UNPARSED}: файл не прочитан ({exc})"
    try:
        doc = _CiParser(text).parse()
    except CiFileError as exc:
        return None, f"{CI_UNPARSED}: {exc}"
    if not isinstance(doc, dict):
        return None, f"{CI_UNPARSED}: строка 1: верхний уровень — не отображение"
    return doc, ""


# --- правила workflow (требование 6) ---------------------------------------

class _Unsupported(Exception):
    """Выражение `if` вне поддержанного вида."""


_EXPR_TOKEN_RE = re.compile(
    r"\s*(?:(?P<var>\$(?:\{[A-Za-z_]\w*\}|[A-Za-z_]\w*))"
    r"|(?P<str>\"(?:[^\"\\]|\\.)*\"|'[^']*')"
    r"|(?P<re>/(?:[^/\\]|\\.)*/[a-z]*)"
    r"|(?P<op>==|!=|=~|!~|&&|\|\||\(|\)))")


def _expr_tokens(text: str) -> list:
    tokens, pos = [], 0
    while text[pos:].strip():
        m = _EXPR_TOKEN_RE.match(text, pos)
        if m is None:
            raise _Unsupported(f"не разобрано с «{text[pos:].strip()}»")
        tokens.append((m.lastgroup, m.group(m.lastgroup)))
        pos = m.end()
    return tokens


class _Expr:
    """Разбор и оценка выражения `if`: `||` слабее `&&`, сравнения
    `==`/`!=`/`=~`/`!~`, скобки; неопределённая переменная — null."""

    def __init__(self, text: str, variables: dict):
        self.tokens, self.i, self.variables = _expr_tokens(text), 0, variables

    def evaluate(self) -> bool:
        if not self.tokens:
            raise _Unsupported("пустое выражение")
        value = self.disjunction()
        if self.i < len(self.tokens):
            raise _Unsupported(f"лишнее «{self.tokens[self.i][1]}»")
        return value

    def peek(self) -> str:
        return self.tokens[self.i][1] if self.i < len(self.tokens) else ""

    def disjunction(self) -> bool:
        value = self.conjunction()
        while self.peek() == "||":
            self.i += 1
            right = self.conjunction()
            value = value or right
        return value

    def conjunction(self) -> bool:
        value = self.comparison()
        while self.peek() == "&&":
            self.i += 1
            right = self.comparison()
            value = value and right
        return value

    def operand(self) -> tuple[str, str | None]:
        if self.i >= len(self.tokens):
            raise _Unsupported("выражение оборвано")
        kind, text = self.tokens[self.i]
        self.i += 1
        if kind == "var":
            return "value", self.variables.get(text.strip("${}"))
        if kind == "str":
            return "value", text[1:-1]
        if kind == "re":
            return "re", text
        raise _Unsupported(f"на месте значения «{text}»")

    def comparison(self) -> bool:
        if self.peek() == "(":
            self.i += 1
            value = self.disjunction()
            if self.peek() != ")":
                raise _Unsupported("нет закрывающей скобки")
            self.i += 1
            return value
        kind, left = self.operand()
        op = self.peek()
        if op not in ("==", "!=", "=~", "!~"):
            if kind == "re":
                raise _Unsupported("регулярное выражение без сравнения")
            return bool(left)
        self.i += 1
        right_kind, right = self.operand()
        if op in ("==", "!="):
            if "re" in (kind, right_kind):
                raise _Unsupported(f"регулярное выражение при {op}")
            return (left == right) == (op == "==")
        if kind == "re" or right_kind != "re":
            raise _Unsupported(f"справа от {op} — не регулярное выражение")
        body, _sep, flags = right[1:].rpartition("/")
        if set(flags) - {"i"}:
            raise _Unsupported(f"флаги регулярного выражения «{flags}»")
        try:
            found = left is not None and re.search(
                body, left, re.IGNORECASE if flags else 0) is not None
        except re.error as exc:
            raise _Unsupported(f"регулярное выражение не разобрано: {exc}") from exc
        return found == (op == "=~")


def _sample_branch(entry: dict) -> str:
    template = str(entry.get("branch_template")
                   or doctor.targets.DEFAULT_BRANCH_TEMPLATE)
    return (template.replace("{id}", SAMPLE_TASK_ID.lower())
            .replace("{slug}", SAMPLE_SLUG).replace("{ref}", SAMPLE_REF))


def _rule_text(number: int, rule: dict) -> str:
    cond = rule.get("if")
    return f"правило workflow №{number}" + (f" (if: {cond})" if cond is not None else "")


def check_workflow_rules(check_name: str, clone: Path, entry: dict):
    """Ветка по шаблону задачи под правилами `workflow:rules` файла CI —
    оценка конвейера отправки ветки (требование 6; ANSWER-1 п. 4)."""
    if not clone.is_dir():
        return doctor.Check(check_name, "warn",
                            f"клона нет: {clone} — правила workflow {CI_FILE} "
                            f"не проверены")
    doc, problem = ci_document(clone)
    if doc is None:
        return doctor.Check(check_name, "warn", problem)
    branch = _sample_branch(entry)
    workflow = doc.get("workflow")
    if workflow is not None and not isinstance(workflow, dict):
        return doctor.Check(check_name, "warn", f"{CI_UNPARSED}: workflow — не отображение")
    rules = workflow.get("rules") if isinstance(workflow, dict) else None
    if rules is not None and (not isinstance(rules, list)
                              or not all(isinstance(r, dict) for r in rules)):
        return doctor.Check(check_name, "warn",
                            f"{CI_UNPARSED}: workflow:rules — не список правил")
    if rules is None:
        if "include" in doc:
            return doctor.Check(check_name, "warn",
                                f"{CI_UNPARSED}: include — workflow может прийти "
                                f"из подключённого файла, не проверено")
        return doctor.Check(check_name, "ok",
                            f"в {CI_FILE} нет workflow:rules — GitLab создаёт "
                            f"конвейер любой ветки, в том числе {branch}")
    variables = {"CI_COMMIT_BRANCH": branch, "CI_COMMIT_REF_NAME": branch,
                 "CI_PIPELINE_SOURCE": "push",
                 "CI_DEFAULT_BRANCH": str(entry.get("base", doctor.config.MAIN_BRANCH))}
    for number, rule in enumerate(rules, 1):
        text = _rule_text(number, rule)
        cond = rule.get("if")
        try:
            hit = cond is None or _Expr(str(cond), variables).evaluate()
        except _Unsupported as exc:
            return doctor.Check(check_name, "warn",
                                f"{text}: выражение не поддержано ({exc}) — правило "
                                f"может сработать, ветка задачи {branch} не проверена")
        if not hit:
            continue
        keys = [key for key in ("changes", "exists") if key in rule]
        if keys:
            return doctor.Check(check_name, "warn",
                                f"{text}: ключи {', '.join(keys)} не оцениваются — "
                                f"правило может сработать, ветка задачи {branch} "
                                f"не проверена")
        if rule.get("when") == "never":
            return doctor.Check(check_name, "warn",
                                f"ветка задачи {branch} не под конвейером: {text} — "
                                f"when: never")
        return doctor.Check(check_name, "ok",
                            f"ветка задачи {branch} под конвейером: {text}")
    every = "; ".join(_rule_text(n, r) for n, r in enumerate(rules, 1)) or "правил нет"
    return doctor.Check(check_name, "warn",
                        f"ветка задачи {branch} не под конвейером: ни одно правило "
                        f"не сработало — {every}")


# --- перезапуски в ci_job (требование 9) ------------------------------------

class _CiShape(Exception):
    """Задание файла CI не собрано; `missing` — по `extends` нет задания."""

    def __init__(self, text: str, missing: bool = False):
        super().__init__(text)
        self.missing = missing


def _deep_merge(base: dict, over: dict) -> dict:
    """Слияние `extends` GitLab: отображения — вглубь, прочее заменяется."""
    out = dict(base)
    for key, value in over.items():
        out[key] = (_deep_merge(out[key], value)
                    if isinstance(out.get(key), dict) and isinstance(value, dict)
                    else value)
    return out


def _merged_job(doc: dict, name: str, seen: tuple = ()) -> dict:
    job = doc.get(name)
    if not isinstance(job, dict):
        raise _CiShape(f"extends {name}: задания нет в файле", missing=True)
    if name in seen:
        raise _CiShape(f"extends: цикл через {name}")
    parents = job.get("extends") or []
    parents = [parents] if isinstance(parents, str) else parents
    if not isinstance(parents, list) or not all(isinstance(p, str) for p in parents):
        raise _CiShape(f"задание {name}: extends — не имя и не список имён")
    merged: dict = {}
    for parent in parents:
        merged = _deep_merge(merged, _merged_job(doc, parent, seen + (name,)))
    return _deep_merge(merged, {k: v for k, v in job.items() if k != "extends"})


def _retry_finding(value) -> str:
    """Находка `retry` (кроме 0; `{max: N}` — по N, ANSWER-1 п. 2)."""
    if isinstance(value, dict):
        value = value.get("max")
    if value is None or str(value).strip() == "0":
        return ""
    return f"retry {value}"


def _split_command(text: str) -> list:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _script_lines(value) -> list:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [line for item in value for line in _script_lines(item)]
    return []


def _rerun_findings(doc: dict, job: dict) -> list:
    """Находки перезапуска задания — семь форм требования 9."""
    default = doc.get("default") if isinstance(doc.get("default"), dict) else {}
    findings = []
    retry = (_retry_finding(job["retry"]) if "retry" in job
             else _retry_finding(default.get("retry")))
    if retry:
        findings.append(retry + ("" if "retry" in job else " (из default)"))
    for key in ("before_script", "script", "after_script"):
        for line in _script_lines(job[key] if key in job else default.get(key)):
            argument = doctor.targets._rerun_argument(_split_command(line))
            if argument:
                findings.append(f"{key}: аргумент {argument}")
            elif re.search(r"\bpytest[-_]rerunfailures\b", line):
                findings.append(f"{key}: установка pytest-rerunfailures")
    for scope, variables in (("задания", job.get("variables")),
                             ("верхнего уровня", doc.get("variables"))):
        for key, value in (variables.items() if isinstance(variables, dict) else []):
            if isinstance(value, dict):
                value = value.get("value")
            argument = (doctor.targets._rerun_argument(_split_command(value))
                        if isinstance(value, str) else "")
            if argument:
                findings.append(f"variables {scope} {key}: аргумент {argument}")
    return findings


def check_ci_reruns(check_name: str, clone: Path, fields: dict):
    """Задание `ci_job` компонента не перезапускает упавшие тесты: повторы
    отчёт хостинга не видит (инвариант 41; требование 9)."""
    job_name = fields.get("ci_job")
    include_text = (f"{CI_UNPARSED}: include — перезапуск может прийти из "
                    f"подключённого файла, не проверено")
    if not clone.is_dir():
        return doctor.Check(check_name, "skip", f"клона нет: {clone}")
    doc, problem = ci_document(clone)
    if doc is None:
        if problem == CI_FILE_MISSING:
            return doctor.Check(check_name, "skip",
                                f"файла {CI_FILE} нет — перезапуски не проверены")
        return doctor.Check(check_name, "warn", problem)
    if not job_name:
        return doctor.Check(check_name, "skip",
                            "у компонента нет ci_job — перезапуски не проверены")
    include = "include" in doc
    if not isinstance(doc.get(job_name), dict):
        if include:
            return doctor.Check(check_name, "warn", include_text)
        return doctor.Check(check_name, "skip", f"задания {job_name} в {CI_FILE} нет")
    try:
        job = _merged_job(doc, str(job_name))
    except _CiShape as exc:
        return doctor.Check(check_name, "warn",
                            include_text if exc.missing and include
                            else f"{CI_UNPARSED}: {exc}")
    findings = _rerun_findings(doc, job)
    if findings:
        return doctor.Check(check_name, "warn",
                            f"задание {job_name} перезапускает упавшие тесты — "
                            f"{'; '.join(findings)}: отчёт хостинга повторов не "
                            f"видит (инвариант 41)")
    if include:
        return doctor.Check(check_name, "warn", include_text)
    return doctor.Check(check_name, "ok",
                        f"в задании {job_name} нет перезапуска упавших тестов")


# --- подмодули (требование 10) ----------------------------------------------

def gitmodules(text: str) -> list:
    """[(путь, адрес)] подмодулей текста `.gitmodules`."""
    return doctor.gitcmd.gitmodules_entries(text)


_SCP_RE = re.compile(r"^((?:[^@/:\s]+@)?([^/:\s]+)):(.*)$")


def _remote_kind(url: str) -> tuple[str, str]:
    """(вид адреса: https | ssh | иной, хост в нижнем регистре)."""
    if "://" in url:
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme.lower()
        kind = ("https" if scheme == "https"
                else "ssh" if scheme in ("ssh", "git+ssh", "ssh+git") else "иной")
        return kind, (parts.hostname or "").lower()
    m = _SCP_RE.match(url)
    if m:
        return "ssh", m.group(2).lower()
    return "иной", ""


def _resolve_submodule(url: str, base: str) -> str:
    """Относительный адрес `./…`/`../…` — от адреса записи, как у git."""
    return doctor.gitcmd.resolve_submodule_url(url, base)


def check_submodules(check_name: str, clone: Path, entry: dict, in_role: bool):
    """Подмодули клона на хосте записи доступны токену слота: проба
    `gitcmd.in_repo(клон, "ls-remote", адрес)` (требование 10); ssh-адрес и
    чужой хост — `warn` (ANSWER-1 пп. 1, 4). Только чтение.

    Подмодуль из `submodule_tokens` (SPEC 01M6P1Z0ZHVNDYWN3FZSZWBCG3,
    требование 5) — правилом помощника: проба идёт с токеном его слота,
    другой хост (`url_host` с портом) — `fail`; путь поля вне `.gitmodules`
    — `warn`, ранних `ok` «подмодулей нет» у такой записи нет."""
    if in_role:
        return doctor.Check(check_name, "skip", ROLE_SKIP)
    if not entry.get("token_slot"):
        return doctor.Check(check_name, "skip", f"подмодули не проверены — {NO_TOKEN_SLOT}")
    if not clone.is_dir():
        return doctor.Check(check_name, "skip", f"клона нет: {clone}")
    field = entry.get(doctor.targets.SUBMODULE_TOKENS_FIELD) or {}
    path = clone / ".gitmodules"
    if not path.is_file() and not field:
        return doctor.Check(check_name, "ok", "подмодулей нет: .gitmodules в клоне нет")
    found = []
    if path.is_file():
        try:
            found = gitmodules(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            return doctor.Check(check_name, "warn", f".gitmodules не прочитан: {exc}")
    if not found and not field:
        return doctor.Check(check_name, "ok", "подмодулей нет: в .gitmodules нет адресов")
    base = str(entry.get("url", ""))
    _kind, host = _remote_kind(base)
    probed, warns, fails = [], [], []
    listed = {sub_path for sub_path, _raw in found}
    for sub_path in field:
        if sub_path not in listed:
            warns.append(f"подмодуль {sub_path}: путь не в .gitmodules клона")
    for sub_path, raw in found:
        address = _resolve_submodule(raw, base)
        if sub_path in field:
            problem = _field_submodule_problem(sub_path, address, base,
                                               field[sub_path])
            if problem is not None:
                (fails if problem[0] == "fail" else warns).append(problem[1])
                continue
        else:
            kind, sub_host = _remote_kind(address)
            if kind == "иной" or sub_host != host:
                warns.append(f"подмодуль {sub_path}: адрес {address} не на хосте "
                             f"записи {host or '(не разобран)'}, токеном слота не "
                             f"проверяется")
                continue
            if kind == "ssh":
                warns.append(f"подмодуль {sub_path}: ssh-адрес, токеном слота не проверяется")
                continue
        res = doctor.gitcmd.in_repo(clone, "ls-remote", address)
        if res is None or res.returncode != 0:
            err = (res.stderr or res.stdout).strip()[:200] if res is not None else ""
            fails.append(f"подмодуль {sub_path}: {address} — {err or 'git не ответил'}")
        else:
            probed.append(f"{sub_path} ({address})")
    if fails:
        return doctor.Check(check_name, "fail", "; ".join(fails + warns))
    if warns:
        tail = [f"доступны токену слота: {', '.join(probed)}"] if probed else []
        return doctor.Check(check_name, "warn", "; ".join(warns + tail))
    return doctor.Check(check_name, "ok",
                        f"подмодули на хосте записи доступны токену слота: "
                        f"{', '.join(probed)}")


def _field_submodule_problem(sub_path: str, address: str, base: str,
                             slot: str) -> tuple | None:
    """(статус, текст) подмодуля из `submodule_tokens`, который не
    проверяется пробой; `None` — проба `ls-remote` токеном его слота.
    Хост — правилом помощника (`gitcmd.same_host`: с портом, имя без учёта
    регистра); пустой слот сильнее `warn` для `http://`."""
    gitcmd = doctor.gitcmd
    if not gitcmd.same_host(address, base):
        return "fail", (f"подмодуль {sub_path}: адрес {address} — другой хост "
                        f"{gitcmd.url_host(address) or '(не разобран)'}, не хост "
                        f"записи {gitcmd.url_host(base) or '(не разобран)'}: "
                        f"токен слота {slot} ему не выдаётся")
    scheme = gitcmd.submodule_scheme(address)
    if scheme in ("ssh", "git+ssh", "ssh+git"):
        return "warn", f"подмодуль {sub_path}: ssh-адрес, токеном слота не проверяется"
    if scheme not in ("http", "https"):
        return "warn", (f"подмодуль {sub_path}: адрес {address} не http(s), "
                        f"токеном слота не проверяется")
    if not doctor.keychain.token(slot):
        return "fail", (f"подмодуль {sub_path}: слот {slot} связки ключей пуст "
                        f"(submodule_tokens записи)")
    if scheme == "http":
        return "warn", (f"подмодуль {sub_path}: адрес http://, токеном слота "
                        f"не проверяется")
    return None
