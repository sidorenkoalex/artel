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
import io
import json
import re
import subprocess
import tempfile
import urllib.parse
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from . import ci, config, gitlab_adapter, repo_context, targets

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
class BaseCommit:
    """Последний зелёный коммит ветки, у которого задание исполнено
    (строка `doctor` об отчёте базы, SPEC 01M6TRM6H57TN8V14HGFV0NQXJ,
    требование 8); `None` — не найден (причина)."""
    sha: str | None = None
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
    """Хостинг GitHub: итог CI, статус и отчёт задания — чтение check runs
    и артефактов прогона Actions через `gh api` (вход — как у
    `pipeline_status`, не `github_call`: тот отказывает артели); функции
    MR — `gh pr` через `github_call`; прочих функций пока нет (их отказ
    собирает `_call`)."""

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
        # `id` — номер check run у каждого, в том числе пропущенного:
        # сверка «одна попытка» `ci.job_full_suite` (требование 7).
        jobs = [Job(str(r.get("name", "?")),
                    str(r.get("conclusion") or r.get("status") or ""),
                    id=_check_run_number(r))
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

    @staticmethod
    def job_result(target: str, sha: str, job_name: str) -> JobResult:
        run, why = _gh_attempt(target, sha, job_name)
        if run is None:
            return JobResult(None, why)
        return JobResult(*_gh_job_status(run, job_name))

    @staticmethod
    def job_test_report(target: str, sha: str, job_name: str) -> TestReport:
        artifact, why = _gh_report_artifact(target, job_name)
        if why:
            return TestReport(None, why)
        run, why = _gh_attempt(target, sha, job_name)
        if run is None:
            return TestReport(None, why)
        number = _check_run_number(run)
        what = f"отчёт задания «{job_name}» (check run {number})"
        start = _gh_time(run.get("started_at"))
        end = _gh_time(run.get("completed_at"))
        if run.get("status") != "completed" or start is None or end is None:
            return TestReport(None, f"{what}: попытка не завершена — окна "
                                    f"started_at–completed_at нет")
        remote, why = _gh_remote(target)
        if why:
            return TestReport(None, f"{what}: {why}")
        job, why = _gh_json(remote, f"repos/{{owner}}/{{repo}}/actions/jobs/"
                                    f"{number}")
        run_id = job.get("run_id") if isinstance(job, dict) else None
        if not isinstance(run_id, int) or isinstance(run_id, bool):
            return TestReport(None, f"{what}: прогон Actions попытки не "
                                    f"прочитан: {why or 'в ответе нет run_id'}")
        items, why = _gh_run_artifacts(remote, run_id, artifact)
        if items is None:
            return TestReport(None, f"{what}: артефакты прогона {run_id} не "
                                    f"прочитаны: {why}")
        # Перезапуск задания идёт в том же прогоне: артефакт прежней попытки
        # отсекает окно этой попытки (требование 3).
        fit = [a for a in items if a.get("name") == artifact
               and _in_window(_gh_time(a.get("created_at")), start, end)]
        if not fit:
            return TestReport(None, f"{what}: у прогона {run_id} нет годного "
                                    f"артефакта «{artifact}», созданного между "
                                    f"started_at и completed_at попытки")
        if len(fit) > 1:
            ids = ", ".join(str(a.get("id")) for a in fit)
            return TestReport(None, f"{what}: у прогона {run_id} больше одного "
                                    f"годного артефакта «{artifact}»: {ids}")
        found = fit[0]
        aid = found.get("id")
        if found.get("expired") is not False:
            return TestReport(None, f"{what}: срок хранения артефакта "
                                    f"«{artifact}» {aid} истёк")
        if not isinstance(aid, int) or isinstance(aid, bool):
            return TestReport(None, f"{what}: у артефакта «{artifact}» нет "
                                    f"номера")
        limit = config.CI_REPORT_ARCHIVE_MAX_BYTES
        declared = found.get("size_in_bytes")
        if isinstance(declared, int) and declared > limit:
            return TestReport(None, f"{what}: размер архива артефакта "
                                    f"«{artifact}» {declared} байт больше "
                                    f"предела {limit} байт")
        got = ci.gh_bytes("api", f"repos/{{owner}}/{{repo}}/actions/artifacts/"
                                 f"{aid}/zip",
                          max_bytes=limit,
                          timeout=config.CI_REPORT_DOWNLOAD_TIMEOUT_SEC,
                          **({"repo": remote} if remote else {}))
        if got.data is None:
            return TestReport(None, f"{what}: архив артефакта «{artifact}» "
                                    f"{aid} не скачан: {got.reason}")
        return _junit_report(got.data, f"{what}: архив артефакта "
                                       f"«{artifact}» {aid}")

    @staticmethod
    def green_base_commit(target: str, branch: str,
                          job_name: str) -> BaseCommit:
        remote, why = _gh_remote(target)
        if why:
            return BaseCommit(None, why)
        data, why = _gh_json(remote, (
            f"repos/{{owner}}/{{repo}}/actions/runs?branch="
            f"{urllib.parse.quote(branch, safe='')}&status=success"
            f"&per_page={config.CI_RUN_LIST_LIMIT}"))
        runs = data.get("workflow_runs") if isinstance(data, dict) else None
        if not isinstance(runs, list):
            return BaseCommit(None, f"зелёные прогоны ветки {branch} не "
                                    f"прочитаны: {why or 'нет workflow_runs'}")
        for item in runs:
            run_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(run_id, int) or isinstance(run_id, bool):
                continue
            jobs, why = _gh_json(remote, f"repos/{{owner}}/{{repo}}/actions/"
                                         f"runs/{run_id}/jobs?per_page=100")
            jobs = jobs.get("jobs") if isinstance(jobs, dict) else None
            if not isinstance(jobs, list):
                return BaseCommit(None, f"задания прогона {run_id} ветки "
                                        f"{branch} не прочитаны: "
                                        f"{why or 'нет jobs'}")
            if any(isinstance(j, dict) and j.get("name") == job_name
                   and j.get("conclusion") not in (None, "skipped")
                   for j in jobs):
                return BaseCommit(str(item.get("head_sha") or "") or None,
                                  "" if item.get("head_sha") else
                                  f"у прогона {run_id} нет head_sha")
        return BaseCommit(None, f"среди {len(runs)} последних зелёных прогонов "
                                f"ветки {branch} нет прогона с исполненным "
                                f"заданием «{job_name}»")


# Перевод check run в статус `JobResult` (требование 2): заключение
# завершённого и состояние незавершённого. Прочие значения — негодный
# статус `UNFIT_STATUS:<значение>`: не итог задания и не ожидание.
_GH_CONCLUSION_STATUS = {"success": "success", "failure": "failed",
                         "timed_out": "failed", "cancelled": "canceled",
                         "skipped": "skipped"}
_GH_UNFINISHED_STATES = ("queued", "in_progress", "waiting", "pending",
                         "requested")
UNFIT_STATUS = "unfit"


def _check_run_number(run: dict) -> int | None:
    value = run.get("id")
    return value if isinstance(value, int) and not isinstance(value, bool) \
        else None


def _gh_time(value) -> datetime.datetime | None:
    """Время ответа GitHub с точностью до секунды; `None` — не разобрано."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _in_window(moment, start, end) -> bool:
    """Момент лежит между `start` и `end` включительно; неразобранный — нет."""
    return moment is not None and start <= moment <= end


def _gh_attempt(target: str, sha: str, job_name: str) -> tuple:
    """(попытка задания `job_name` коммита `sha` — check run с наибольшим
    номером среди исполненных, иначе среди пропущенных; причина её
    отсутствия). Вход `gh` — как у `_GitHub.pipeline_status`."""
    kwargs = ({} if repo_context.is_artel(target)
              else {"repo": repo_context.clone_path(target)})
    runs, why = ci.check_runs(sha, **kwargs)
    if runs is None:
        return None, (f"задание «{job_name}»: check runs коммита {sha[:8]} не "
                      f"прочитаны: {why}")
    mine = [r for r in runs if r.get("name") == job_name]
    if not mine:
        return None, (f"задания «{job_name}» нет среди check runs коммита "
                      f"{sha[:8]}")
    executed = [r for r in mine if r.get("conclusion") != "skipped"]
    return max(executed or mine,
               key=lambda r: _check_run_number(r) or 0), ""


def _gh_job_status(run: dict, job_name: str) -> tuple[str, str]:
    state = run.get("status")
    what = f"check run {_check_run_number(run)} задания «{job_name}»"
    if state == "completed":
        conclusion = run.get("conclusion")
        if conclusion in _GH_CONCLUSION_STATUS:
            return _GH_CONCLUSION_STATUS[conclusion], ""
        return (f"{UNFIT_STATUS}:{conclusion}",
                f"{what}: заключение {conclusion!r} — не итог задания")
    if state in _GH_UNFINISHED_STATES:
        return "running", ""
    return (f"{UNFIT_STATUS}:{state}",
            f"{what}: состояние {state!r} — не итог и не ожидание")


def _gh_report_artifact(target: str, job_name: str) -> tuple[str, str]:
    """(имя артефакта отчёта компонента записи с `ci_job == job_name`,
    причина отказа): компонент должен быть ровно один."""
    try:
        entry = targets.target(target)
    except targets.TargetsError as exc:
        return "", f"запись проекта {target} не прочитана: {exc}"
    comps = entry.get(targets.COMPONENTS_FIELD)
    mine = [fields for fields in (comps.values() if isinstance(comps, dict)
                                  else [])
            if isinstance(fields, dict) and fields.get("ci_job") == job_name]
    if len(mine) != 1:
        return "", (f"у задания «{job_name}» {len(mine)} компонентов записи "
                    f"проекта {target} с этим ci_job — ждётся ровно один")
    return str(mine[0].get("ci_report_artifact",
                           targets.CI_REPORT_ARTIFACT_DEFAULT)), ""


def _gh_remote(target: str) -> tuple[str | None, str]:
    """(адрес проекта для `gh`, отказ): артель — `None` (вызов без `repo`,
    как у `_GitHub.pipeline_status`), прочие — `url` записи."""
    if repo_context.is_artel(target):
        return None, ""
    ctx = repo_context.resolve(target)
    if ctx is None or not ctx.remote:
        return None, f"адрес проекта {target} не разрешён — gh не запущен"
    return ctx.remote, ""


def _gh_json(remote: str | None, path: str) -> tuple:
    """(JSON-ответ `gh api <path>`, причина его отсутствия)."""
    res = ci.gh("api", path, **({"repo": remote} if remote else {}))
    if res.returncode != 0:
        return None, f"gh api завершился кодом {res.returncode}: {_gh_text(res)}"
    try:
        return json.loads(res.stdout or ""), ""
    except ValueError:
        return None, "ответ gh api — не JSON"


def _gh_run_artifacts(remote: str | None, run_id: int,
                      name: str) -> tuple[list | None, str]:
    """Артефакты прогона `run_id` с именем `name` постранично, со сверкой
    `total_count`; (None, причина) — список не прочитан целиком."""
    items: list = []
    quoted = urllib.parse.quote(name, safe="")
    for page in range(1, config.CI_CHECKS_MAX_PAGES + 1):
        data, why = _gh_json(remote, (
            f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/artifacts"
            f"?name={quoted}&per_page={config.CI_CHECKS_PER_PAGE}&page={page}"))
        batch = data.get("artifacts") if isinstance(data, dict) else None
        if not isinstance(batch, list) or not all(isinstance(a, dict)
                                                  for a in batch):
            return None, why or "в ответе нет списка artifacts"
        items.extend(batch)
        total = data.get("total_count")
        if isinstance(total, int) and not isinstance(total, bool) \
                and len(items) >= total:
            return items, ""
        if len(batch) < config.CI_CHECKS_PER_PAGE:
            if isinstance(total, int) and not isinstance(total, bool) \
                    and len(items) != total:
                return None, (f"получено {len(items)} артефактов из {total} "
                              f"обещанных — список неполон")
            return items, ""
    return None, (f"артефактов больше, чем помещается в "
                  f"{config.CI_CHECKS_MAX_PAGES} страниц")


def _unsafe_member(name: str) -> bool:
    """Путь элемента архива ведёт за пределы каталога распаковки."""
    parts = name.replace("\\", "/").split("/")
    return (name.startswith(("/", "\\")) or ".." in parts
            or (len(name) > 1 and name[1] == ":"))


def _junit_report(data: bytes, what: str) -> TestReport:
    """Отчёт junit из архива артефакта: пути элементов проверяются до
    распаковки, содержимое распаковывается во временный каталог с пределом
    суммарного размера, ровно один `*.xml` разбирается своим кодом
    (требования 3-5); каталог удаляется после разбора."""
    limit = config.CI_REPORT_UNPACKED_MAX_BYTES
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        return TestReport(None, f"{what}: архив не разобран: {exc}")
    with archive:
        infos = archive.infolist()
        unsafe = [i.filename for i in infos if _unsafe_member(i.filename)]
        if unsafe:
            return TestReport(None, f"{what}: путь {unsafe[0]!r} в архиве ведёт "
                                    f"за пределы каталога распаковки")
        declared = sum(i.file_size for i in infos)
        if declared > limit:
            return TestReport(None, f"{what}: размер содержимого после "
                                    f"распаковки {declared} байт больше "
                                    f"предела {limit} байт")
        reports = [i.filename for i in infos
                   if not i.is_dir() and i.filename.lower().endswith(".xml")]
        if len(reports) != 1:
            return TestReport(None, f"{what}: в архиве {len(reports)} файлов "
                                    f"*.xml — ждётся ровно один")
        with tempfile.TemporaryDirectory(prefix="artel-ci-report-") as tmp:
            root = Path(tmp).resolve()
            written = 0
            try:
                for info in infos:
                    if info.is_dir():
                        continue
                    path = (root / info.filename).resolve()
                    if root not in path.parents:
                        return TestReport(None, f"{what}: путь "
                                                f"{info.filename!r} в архиве "
                                                f"ведёт за пределы каталога "
                                                f"распаковки")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, open(path, "wb") as dst:
                        while True:
                            block = src.read(65536)
                            if not block:
                                break
                            written += len(block)
                            if written > limit:
                                return TestReport(
                                    None, f"{what}: размер содержимого после "
                                          f"распаковки больше предела "
                                          f"{limit} байт")
                            dst.write(block)
            except (zipfile.BadZipFile, OSError, EOFError,
                    NotImplementedError, RuntimeError) as exc:
                return TestReport(None, f"{what}: архив не распакован: {exc}")
            text = (root / reports[0]).read_bytes()
    return _parse_junit(text, f"{what}, файл {reports[0]}")


# Вложенный элемент `testcase` → исход `ci.JOB_REPORT_OUTCOMES`
# (требование 4); порядок — старшинство при нескольких вложенных.
_JUNIT_CHILD_OUTCOMES = (("failure", "failed"), ("error", "error"),
                         ("skipped", "skipped"))


def _parse_junit(text: bytes, what: str) -> TestReport:
    """«`<classname>::<name>` → исход» отчёта junit; повтор ключа — отказ,
    как у адаптера GitLab. Объявления DTD отказываются до разбора: отчёту
    pytest они не нужны, а сущности DTD раздувают разбор."""
    if b"<!DOCTYPE" in text.upper() or b"<!ENTITY" in text.upper():
        return TestReport(None, f"{what}: отчёт с объявлением DTD не "
                                f"разбирается")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        return TestReport(None, f"{what}: отчёт junit не разобран: {exc}")
    outcomes: dict = {}
    for case in root.iter("testcase"):
        key = f"{case.get('classname', '')}::{case.get('name', '')}"
        if key in outcomes:
            return TestReport(None, f"{what}: ключ {key} встречается в отчёте "
                                    f"больше одного раза")
        tags = {child.tag for child in case}
        outcomes[key] = next((outcome for tag, outcome in _JUNIT_CHILD_OUTCOMES
                              if tag in tags), "success")
    return TestReport(outcomes)


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
    "green_base_commit": BaseCommit,
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


def implements(target: str, name: str) -> bool:
    """У реализации хостинга проекта в реестре есть функция `name`;
    хостинг не определён — нет. Без обращения к хостингу."""
    value, _why = _hosting(target)
    return value is not None and getattr(IMPLEMENTATIONS[value], name,
                                         None) is not None


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


def green_base_commit(target: str, branch: str, job_name: str) -> BaseCommit:
    """Последний зелёный коммит ветки `branch`, у которого задание
    `job_name` исполнено."""
    return _call("green_base_commit", target, branch, job_name)


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
