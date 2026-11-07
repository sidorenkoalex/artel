"""Интерфейс хостинга проекта (SPEC 01M5WCXBM7WCMRWCBWNCHMAR3T, ADR-0029 п. 8).

Реализация выбирается одним реестром `IMPLEMENTATIONS` — по значению поля
`forge` записи проекта, индексом словаря, без сравнения значения с
литералами. Параметр `target` функций — имя проекта: запись модуль берёт
сам загрузчиком `targets.target`, вызывающий её не передаёт.

Каждая функция возвращает результат своего типа ниже; у всех типов поле
`reason` — пустое, когда ответ получен, и именованная причина иначе.
Функция, которой у реализации нет, — результат того же типа с причиной
«не реализовано для <хостинг>», без обращения к хостингу.
"""
import dataclasses
import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field

from . import ci, gitlab_adapter, repo_context, targets

# Итоги `pipeline_status` и их старшинство (левее — старше): итог набора
# конвейеров или заданий — старший из итогов его частей.
RED = "red"
UNKNOWN = "unknown"
RUNNING = "running"
NONE = "none"
GREEN = "green"
PRECEDENCE = (RED, UNKNOWN, RUNNING, NONE, GREEN)


def senior(verdicts) -> str:
    """Старший итог из `verdicts`; пустой набор — `GREEN` (возражений нет)."""
    return min(verdicts, key=PRECEDENCE.index, default=GREEN)


@dataclass
class Job:
    name: str = ""
    status: str = ""
    stage: str = ""
    id: int | None = None
    allow_failure: bool = False


@dataclass
class PipelineStatus:
    """Итог CI ровно этого sha; `failed` — имена упавших заданий без права
    падать, `marks` — пометки о допустимых падениях."""
    verdict: str = UNKNOWN
    reason: str = ""
    jobs: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    marks: list = field(default_factory=list)
    # Код HTTP-ответа хостинга, на котором функция отказала (не 2xx); None —
    # ответ получен либо отказ без HTTP-ответа (SPEC 01M6EZXVFGH5Z2876XWMQG35FP).
    http_status: int | None = None


@dataclass
class JobResult:
    status: str | None = None
    reason: str = ""


@dataclass
class TestReport:
    """«`<classname>::<name>` → исход»; `None` — отчёта нет (причина)."""
    outcomes: dict | None = None
    reason: str = ""


@dataclass
class MergeRequest:
    iid: int | None = None
    url: str | None = None
    title: str | None = None
    state: str | None = None
    draft: bool | None = None
    assignee: str | None = None
    reason: str = ""
    # Ветки и коммиты MR (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7, требование 1):
    # по ним `mr-sync` ищет правку задачи в `base`.
    target_branch: str | None = None
    source_branch: str | None = None
    sha: str | None = None
    merge_commit_sha: str | None = None
    squash_commit_sha: str | None = None
    # Отказ открытия: MR этой ветки на хостинге уже есть (SPEC
    # 01M6M1799YCY5HXMHHD71SHJET, требование 3) — ставит только GitHub; у
    # GitLab тот же случай — код 409 в тексте причины.
    already_exists: bool = False


@dataclass
class TokenUser:
    username: str | None = None
    reason: str = ""
    # Отображаемое имя и адрес учётной записи (SPEC 01M6RB74H9BDTJAA5D2S4QPK1E,
    # требование 1): заполняет только адаптер GitLab.
    name: str | None = None
    commit_email: str | None = None


@dataclass
class TokenExpiry:
    """Срок токена: `expires_at` — дата; токен без срока — `expires_at`
    `None` и `note` «без срока»."""
    expires_at: datetime.date | None = None
    note: str = ""
    reason: str = ""


@dataclass
class Protections:
    branches: list | None = None
    tags: list | None = None
    reason: str = ""
    http_status: int | None = None


@dataclass
class ProjectInfo:
    default_branch: str | None = None
    access_level: int | None = None
    reason: str = ""


@dataclass
class BranchPipeline:
    """Последний конвейер ветки: его sha, итог и задания."""
    sha: str | None = None
    verdict: str = UNKNOWN
    reason: str = ""
    jobs: list = field(default_factory=list)
    http_status: int | None = None


# Закрытый список вызовов `gh` функций MR GitHub (SPEC
# 01M6M1799YCY5HXMHHD71SHJET, требование 7): набор полей чтения PR, правило
# имён исполнителя и текст отказа `github_call`.
GH_PR_FIELDS = ("number,url,title,state,isDraft,assignees,baseRefName,"
                "headRefName,headRefOid,mergeCommit")
GH_CALL_REFUSAL = "вызов gh не разрешён адаптеру GitHub — gh не запущен: "
_GH_NAME_RE = re.compile(r"[A-Za-z0-9](?:-?[A-Za-z0-9])*")
_GH_NAME_MAX = 39
_DECIMAL_RE = re.compile(r"[0-9]+")
# Адрес PR в stdout `pr create`: хвост — ровно десятичный номер.
_GH_PR_URL_RE = re.compile(
    r"^https://[^/@\s]+/([^/\s]+)/([^/\s]+)/pull/([0-9]+)$")
# «Не найден» — только код выхода 1 с этим текстом в stderr (ANSWER-1,
# вопрос 2): та же строка при ином коде — не «не найден».
_GH_PR_NOT_FOUND = "Could not resolve to a PullRequest"
_NOT_FOUND_CODE = "(404)"
_GH_STATES = {"OPEN": "opened", "MERGED": "merged", "CLOSED": "closed"}


def github_name_ok(value) -> bool:
    """Значение — имя пользователя GitHub: латинские буквы, цифры, одиночные
    `-` не в начале и не в конце, до 39 знаков."""
    return (isinstance(value, str) and len(value) <= _GH_NAME_MAX
            and _GH_NAME_RE.fullmatch(value) is not None)


def _decimal(value: str) -> bool:
    return _DECIMAL_RE.fullmatch(value) is not None


def _github_form_allowed(args: tuple) -> bool:
    """argv целиком — форма закрытого списка, включая хвост."""
    argv = list(args)
    if not all(isinstance(a, str) for a in argv):
        return False
    if argv[:3] == ["pr", "create", "--head"]:
        if len(argv) < 10 or [argv[i] for i in (4, 6, 8)] != [
                "--base", "--title", "--body"]:
            return False
        rest = argv[10:]
        if rest[:1] == ["--draft"]:
            rest = rest[1:]
        if rest and rest[0].startswith("--assignee="):
            if not github_name_ok(rest[0].split("=", 1)[1]):
                return False
            rest = rest[1:]
        return rest == []
    if argv[:2] == ["pr", "view"]:
        return (len(argv) == 5 and _decimal(argv[2])
                and argv[3:] == ["--json", GH_PR_FIELDS])
    if argv[:2] == ["pr", "ready"]:
        return len(argv) == 3 and _decimal(argv[2])
    if argv[:2] == ["pr", "edit"]:
        return (len(argv) == 4 and _decimal(argv[2])
                and argv[3].startswith("--add-assignee=")
                and github_name_ok(argv[3].split("=", 1)[1]))
    return False


def github_call(target: str, *args) -> subprocess.CompletedProcess:
    """Единственный вход `gh` функций MR GitHub: форма вне закрытого списка,
    артель и проект без контекста — отказ без запуска `gh`. `repo` задан у
    каждого вызова: `ci.gh` без него работает в корне артели и изменил бы PR
    с тем же номером в её репозитории."""
    if not _github_form_allowed(args):
        return subprocess.CompletedProcess(
            args, 1, "", GH_CALL_REFUSAL + " ".join(str(a) for a in args))
    if repo_context.is_artel(target):
        return subprocess.CompletedProcess(args, 1, "", (
            f"проект {target} — артель: адреса её форджа у пульта нет, "
            f"функции MR GitHub ей не служат — gh не запущен"))
    ctx = repo_context.resolve(target)
    if ctx is None or not ctx.remote:
        return subprocess.CompletedProcess(
            args, 1, "", f"адрес проекта {target} не разрешён — gh не запущен")
    return ci.gh(*args, repo=ctx.remote)


def _gh_text(res: subprocess.CompletedProcess) -> str:
    return (res.stderr or res.stdout or "").strip()[:300]


class _GitHub:
    """Хостинг GitHub: итог CI — чтение check runs `ci`; функции MR — `gh pr`
    через `github_call`; прочих функций пока нет (их отказ собирает
    `_call`)."""

    CI_BY_PIPELINE = False
    # Исполнитель MR — имя пользователя (`github_adapter.mr_assignee`).
    ASSIGNEE_BY_NAME = True

    # Порядок требования 2: красный исход старше идущей проверки.
    RED_CONCLUSIONS = {"failure", "cancelled", "timed_out"}
    RUNNING_STATUSES = {"queued", "in_progress"}

    @staticmethod
    def pipeline_status(target: str, sha: str) -> PipelineStatus:
        kwargs = ({} if repo_context.is_artel(target)
                  else {"repo": repo_context.clone_path(target)})
        runs, why = ci.check_runs(sha, **kwargs)
        if runs is None:
            return PipelineStatus(UNKNOWN, f"check runs коммита {sha[:8]} не "
                                           f"прочитаны: {why}")
        jobs = [Job(str(r.get("name", "?")),
                    str(r.get("conclusion") or r.get("status") or ""))
                for r in runs]
        if not runs:
            return PipelineStatus(NONE, f"у коммита {sha[:8]} нет check runs")
        failed = sorted({j.name for r, j in zip(runs, jobs)
                         if r.get("conclusion") in _GitHub.RED_CONCLUSIONS})
        if failed:
            return PipelineStatus(RED, f"упали проверки: {', '.join(failed)}",
                                  jobs, failed)
        if any(r.get("status") in _GitHub.RUNNING_STATUSES for r in runs):
            return PipelineStatus(RUNNING, "проверки не завершены", jobs)
        if all(r.get("status") == "completed" and r.get("conclusion") in ci.GREEN
               for r in runs):
            return PipelineStatus(GREEN, "", jobs)
        odd = sorted({j.name for r, j in zip(runs, jobs)
                      if r.get("status") != "completed"
                      or r.get("conclusion") not in ci.GREEN})
        return PipelineStatus(UNKNOWN, f"исход проверок не установлен: "
                                       f"{', '.join(odd)}", jobs)

    @staticmethod
    def mr_status(target: str, mr) -> MergeRequest:
        res = github_call(target, "pr", "view", str(mr), "--json",
                          GH_PR_FIELDS)
        if res.returncode != 0:
            if res.returncode == 1 and _GH_PR_NOT_FOUND in (res.stderr or ""):
                return MergeRequest(reason=f"PR #{mr} не найден "
                                           f"{_NOT_FOUND_CODE}: {_gh_text(res)}")
            # Текст `gh` сам не делает отказ «не найден»: `mr-sync` ищет код
            # в причине.
            text = _gh_text(res).replace(_NOT_FOUND_CODE, "404")
            return MergeRequest(reason=f"PR #{mr} не прочитан: gh pr view "
                                       f"завершился кодом {res.returncode}: "
                                       f"{text}")
        try:
            data = json.loads(res.stdout or "")
        except ValueError:
            data = None
        number = data.get("number") if isinstance(data, dict) else None
        if not isinstance(number, int) or isinstance(number, bool):
            return MergeRequest(reason=f"PR #{mr} не прочитан: ответ gh pr "
                                       f"view — не JSON PR с полем number")
        assignees = data.get("assignees")
        first = assignees[0] if isinstance(assignees, list) and assignees else None
        merge_commit = data.get("mergeCommit")
        state = data.get("state")
        return MergeRequest(
            iid=number, url=data.get("url"), title=data.get("title"),
            state=_GH_STATES.get(state, state),
            draft=data.get("isDraft") is True,
            assignee=first.get("login") if isinstance(first, dict) else None,
            target_branch=data.get("baseRefName"),
            source_branch=data.get("headRefName"), sha=data.get("headRefOid"),
            merge_commit_sha=(merge_commit.get("oid")
                              if isinstance(merge_commit, dict) else None),
            # GitHub отдаёт коммит вливания одним полем при любом методе.
            squash_commit_sha=None)

    @staticmethod
    def open_mr(target: str, branch: str, base: str, title: str, body: str,
                draft: bool, assignee) -> MergeRequest:
        argv = ["pr", "create", "--head", branch, "--base", base,
                "--title", title, "--body", body]
        if draft:
            argv.append("--draft")
        if assignee is not None:
            argv.append(f"--assignee={assignee}")
        res = github_call(target, *argv)
        if res.returncode != 0:
            # Адрес PR в stderr («already exists») не разбирается: номер —
            # только из stdout успешного создания (требование 1).
            stderr = res.stderr or ""
            exists = (f'a pull request for branch "{branch}" into branch '
                      f'"{base}" already exists' in stderr
                      or "A pull request already exists" in stderr)
            return MergeRequest(reason=f"gh pr create завершился кодом "
                                       f"{res.returncode}: {_gh_text(res)}",
                                already_exists=exists)
        lines = [line.strip() for line in (res.stdout or "").splitlines()
                 if line.strip()]
        match = _GH_PR_URL_RE.match(lines[-1]) if lines else None
        if match is None:
            return MergeRequest(reason=f"gh pr create: адрес PR в выводе не "
                                       f"разобран: "
                                       f"{(res.stdout or '').strip()[:300]!r}")
        # Владелец и имя — разбором адреса проекта, не префиксом: `.git`, scp
        # и регистр букв адреса записи не должны терять номер.
        project = ci._owner_and_name(repo_context.resolve(target).remote)
        url, pr_project = match.group(0), f"{match.group(1)}/{match.group(2)}"
        if project is None or project.lower() != pr_project.lower():
            return MergeRequest(reason=f"gh pr create: адрес PR {url} — не "
                                       f"репозиторий проекта "
                                       f"{project or target}")
        number = int(match.group(3))
        status = _GitHub.mr_status(target, number)
        if status.reason:
            # Частичный успех: PR открыт, чтение отказало — номер и адрес
            # остаются в результате вместе с причиной (требование 2).
            return MergeRequest(iid=number, url=url,
                                reason=f"PR #{number} {url} открыт, чтение не "
                                       f"удалось: {status.reason}")
        return dataclasses.replace(status, iid=number, url=url)

    @staticmethod
    def undraft_mr(target: str, mr) -> MergeRequest:
        current = _GitHub.mr_status(target, mr)
        if current.reason or not current.draft:
            return current
        res = github_call(target, "pr", "ready", str(mr))
        if res.returncode != 0:
            return MergeRequest(reason=f"gh pr ready {mr} завершился кодом "
                                       f"{res.returncode}: {_gh_text(res)}")
        return _GitHub.mr_status(target, mr)

    @staticmethod
    def assign_mr(target: str, mr, assignee) -> MergeRequest:
        # `--add-assignee` добавляет исполнителя, не заменяет (требование 6).
        res = github_call(target, "pr", "edit", str(mr),
                          f"--add-assignee={assignee}")
        if res.returncode != 0:
            return MergeRequest(reason=f"gh pr edit {mr} завершился кодом "
                                       f"{res.returncode}: {_gh_text(res)}")
        return _GitHub.mr_status(target, mr)


# Единственный реестр реализаций: ключ — значение поля `forge` записи.
IMPLEMENTATIONS = {"github": _GitHub, "gitlab": gitlab_adapter}

# Тип результата каждой функции интерфейса — для отказа без реализации.
RESULT_TYPES = {
    "pipeline_status": PipelineStatus, "job_result": JobResult,
    "job_test_report": TestReport, "open_mr": MergeRequest,
    "undraft_mr": MergeRequest, "assign_mr": MergeRequest,
    "mr_status": MergeRequest, "token_user": TokenUser,
    "token_expiry": TokenExpiry, "protections": Protections,
    "project_info": ProjectInfo, "branch_pipeline": BranchPipeline,
}


def _hosting(target: str) -> tuple[str | None, str]:
    """(значение `forge` записи проекта, причина); значение вне реестра —
    (None, причина)."""
    try:
        value = targets.target(target).get("forge")
    except targets.TargetsError as exc:
        return None, f"запись проекта {target} не прочитана: {exc}"
    if value not in IMPLEMENTATIONS:
        return None, f"хостинг {value!r} проекта {target}: адаптера нет"
    return value, ""


def hosting(target: str) -> str:
    """Имя хостинга проекта для текстов отказа; "" — хостинг не определён."""
    return _hosting(target)[0] or ""


def ci_by_pipeline(target: str) -> bool:
    """Итог CI проекта даёт `pipeline_status` этого модуля, а не чтение
    check runs `ci`."""
    value, _why = _hosting(target)
    return value is not None and IMPLEMENTATIONS[value].CI_BY_PIPELINE


def assignee_by_name(target: str) -> bool:
    """Исполнитель MR проекта — имя пользователя: признак `ASSIGNEE_BY_NAME`
    реализации в реестре; хостинг не определён — нет."""
    value, _why = _hosting(target)
    return (value is not None and getattr(IMPLEMENTATIONS[value],
                                          "ASSIGNEE_BY_NAME", False) is True)


def _call(name: str, target: str, *args):
    value, why = _hosting(target)
    if value is None:
        return RESULT_TYPES[name](reason=f"{name}: {why}")
    function = getattr(IMPLEMENTATIONS[value], name, None)
    if function is None:
        return RESULT_TYPES[name](reason=f"{name}: не реализовано для {value}")
    return function(target, *args)


def pipeline_status(target: str, sha: str) -> PipelineStatus:
    """Итог CI ровно коммита `sha` и его задания."""
    return _call("pipeline_status", target, sha)


def job_result(target: str, sha: str, job_name: str) -> JobResult:
    """Статус задания `job_name` в конвейере `sha` (последняя попытка)."""
    return _call("job_result", target, sha, job_name)


def job_test_report(target: str, sha: str, job_name: str) -> TestReport:
    """Отчёт тестов задания: `<classname>::<name>` → исход."""
    return _call("job_test_report", target, sha, job_name)


def open_mr(target: str, branch: str, base: str, title: str, body: str,
            draft: bool, assignee) -> MergeRequest:
    return _call("open_mr", target, branch, base, title, body, draft, assignee)


def undraft_mr(target: str, mr: int) -> MergeRequest:
    return _call("undraft_mr", target, mr)


def assign_mr(target: str, mr: int, assignee) -> MergeRequest:
    return _call("assign_mr", target, mr, assignee)


def mr_status(target: str, mr: int) -> MergeRequest:
    return _call("mr_status", target, mr)


def token_user(target: str) -> TokenUser:
    return _call("token_user", target)


def token_expiry(target: str) -> TokenExpiry:
    return _call("token_expiry", target)


def protections(target: str) -> Protections:
    return _call("protections", target)


def project_info(target: str) -> ProjectInfo:
    """Ветка проекта по умолчанию и уровень доступа пользователя токена."""
    return _call("project_info", target)


def branch_pipeline(target: str, branch: str) -> BranchPipeline:
    """Sha, итог и задания последнего конвейера ветки `branch`."""
    return _call("branch_pipeline", target, branch)
