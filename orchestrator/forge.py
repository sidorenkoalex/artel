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
import datetime
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


@dataclass
class TokenUser:
    username: str | None = None
    reason: str = ""


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


class _GitHub:
    """Хостинг GitHub: итог CI — чтение check runs `ci`; прочих функций
    пока нет (их отказ собирает `_call`)."""

    CI_BY_PIPELINE = False

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
