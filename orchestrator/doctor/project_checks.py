"""Пакет orchestrator/doctor -- проверки записи внешнего проекта: клон, пуш, CI, защита ветки, токен, no_paths, project_skills.

SPEC 01M545EDTHS47HSB59AKC1EZ9C, требования 5-7. Коллаборанты читаются
лениво через фасад doctor (см. докстринг orchestrator/doctor/__init__.py)
-- не импортируются напрямую.
"""
import json
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
             "token", "no-paths", "skills")]


def project_entry_checks(name: str, entry: dict) -> list:
    """Строки п.5 по записи `name`: у артели — «неприменимо» на каждую
    (требование 6), в процессе роли 5.1/5.2/5.5 — именованный пропуск без
    сети и без связки ключей (требование 7)."""
    names = _names(name)
    if doctor.repo_context.is_artel(name):
        return [doctor.Check(n, "skip", NOT_APPLICABLE) for n in names]
    clone = doctor.repo_context.clone_path(name)
    in_role = doctor.runner.in_role_environment()
    clone_name, push_name, ci_name, prot_name, token_name, paths_name, \
        skills_name = names
    return [
        (doctor.Check(clone_name, "skip", ROLE_SKIP) if in_role
         else check_clone(clone_name, clone, entry)),
        (doctor.Check(push_name, "skip", ROLE_SKIP) if in_role
         else check_artifacts_push(push_name, clone)),
        check_ci_pull_request(ci_name, clone),
        check_base_protection(prot_name, name, entry),
        (doctor.Check(token_name, "skip", ROLE_SKIP) if in_role
         else check_project_token(token_name, name, entry)),
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
