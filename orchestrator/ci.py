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
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from scripts import ci_push_class

from . import config, forge, gitcmd, repo_context, workspace

# Заключения проверок, считающиеся зелёными. `skipped` обязателен: job
# `protected-paths` идёт только на pull_request и на push репозитория
# пропускается — без него зелёного CI не бывало бы вовсе.
GREEN = {"success", "skipped", "neutral"}
# Проверки полного набора собственного workflow. У внешних проектов нет
# объявленного здесь набора, поэтому их `skipped` сохраняет прежний смысл.
FULL_SUITE_CHECKS = frozenset({
    "Синтаксис и тесты оркестратора",
    "Инварианты на минимальной версии Python",
})
# Только это задание запускает весь каталог tests/; python-min исполняет
# лишь tests.test_invariants и само по себе не доказывает полный набор.
FULL_SUITE_JOB = "Синтаксис и тесты оркестратора"


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

    `repo` — `url` записи внешнего проекта: `gh` получает токен слота
    `token_slot` этой записи переменной `GH_TOKEN` своего окружения либо не
    запускается вовсе — отказ `gitcmd.hosting_token` возвращается текстом
    ошибки вызова (SPEC 01M545EDTHS47HSB59AKC1EZ9C, требования 1-3, 7).

    `gh api` флага `--repo` не принимает («unknown flag: --repo»): ему
    репозиторий `repo` задаётся переменной `GH_REPO=<владелец>/<имя>`
    окружения вызова — и у записи без `token_slot` тоже. Адрес, из
    которого владельца и имя не разобрать (`_owner_and_name`), —
    именованный отказ без запуска `gh` (SPEC 01M55V7WB94C9BZXTXTTH83YWV,
    требование 1).
    """
    timeout_sec = config.GH_TIMEOUT_SEC if timeout is None else timeout
    full_args = args
    env_extra = {}
    if repo and args[:1] == ("api",):
        gh_repo = _owner_and_name(repo)
        if gh_repo is None:
            return subprocess.CompletedProcess(args, 1, "", (
                f"адрес проекта {repo}: вид адреса не разобран — ждётся "
                f"https://<хост>/<владелец>/<имя> или "
                f"git@<хост>:<владелец>/<имя>; gh api не запущен"))
        env_extra["GH_REPO"] = gh_repo
    elif repo:
        full_args = (*args, "--repo", repo)
    project = gitcmd.project_by_url(repo) if repo else None
    if project is not None:
        token, refusal = gitcmd.hosting_token(*project)
        if refusal is not None:
            return subprocess.CompletedProcess(args, 1, "", refusal)
        if token is not None:
            env_extra["GH_TOKEN"] = token
    extra = {"env": dict(os.environ, **env_extra)} if env_extra else {}
    try:
        return subprocess.run(["gh", *full_args], cwd=config.ROOT,
                              capture_output=True, text=True,
                              timeout=timeout_sec, **extra)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 1, "", f"gh молчал дольше {timeout_sec} с")
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


# Два вида адреса проекта, из которых берутся владелец и имя для `GH_REPO`
# (решение Оператора 18.10, К-3): https с необязательными `.git` и `/` в
# конце и scp `git@<хост>:…` с необязательным `.git`. Сегмент — непустой и
# без `/`: третий сегмент пути или пустой — не этот вид.
_HTTPS_URL_RE = re.compile(
    r"^https://[^/@\s]+/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_SCP_URL_RE = re.compile(r"^git@[^:/\s]+:([^/\s]+)/([^/\s]+?)(?:\.git)?$")


def _owner_and_name(url: str) -> str | None:
    """«<владелец>/<имя>» адреса проекта; `None` — вид адреса не разобран."""
    for pattern in (_HTTPS_URL_RE, _SCP_URL_RE):
        match = pattern.match(url.strip())
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def _project_area_name(repo: Path) -> str | None:
    """Имя каталога области проектов (`repo_context.projects_root()/<имя>/…`),
    под которым лежит `repo`; `None` — путь не в области проектов. Сверка
    — в абсолютном виде и с раскрытыми ссылками (временный каталог macOS
    живёт под `/private`)."""
    root = repo_context.projects_root()
    for a, b in ((Path(os.path.abspath(repo)), Path(os.path.abspath(root))),
                 (Path(repo).resolve(), Path(root).resolve())):
        try:
            parts = a.relative_to(b).parts
        except ValueError:
            continue
        return parts[0] if parts else None
    return None


def _project_context(repo: Path | None) -> tuple["repo_context.RepoContext | None",
                                                  str]:
    """(контекст внешнего проекта клона `repo`, отказ) для адресации `gh`
    (SPEC 01M55V7WB94C9BZXTXTTH83YWV, требование 1, К-4).

    (None, "") — вызов артели: `None`, клон, который признак
    `repo_context.is_artel` называет артелью, и любой путь вне области
    внешнего проекта (главная копия `config.ROOT` у `pin-update`/`doctor`).
    Путь в области проекта (`repo_context.clone_path(<имя>)` и глубже),
    запись которого не разрешается, — (None, отказ): молчаливый вызов
    артели спросил бы GitHub не о том репозитории (ответ Оператора, Н-4).
    """
    if repo is None or repo_context.is_artel(repo):
        return None, ""
    name = _project_area_name(repo)
    if name is None or repo_context.is_artel(name):
        return None, ""
    ctx = repo_context.resolve(name)
    if ctx is None:
        # Путь — в конце: вызывающие обрезают текст `gh` до 200 знаков.
        return None, (f"gh не запущен: "
                      f"{repo_context.unresolved_reason(name)} (путь {repo})")
    return ctx, ""


def _project_kwargs(repo: Path | None) -> dict:
    """`repo=` внутренних вызовов функций, адресующих `gh`: только для пути
    внешнего проекта (в том числе неразрешённого — отказ назовёт вызов);
    у артели — прежняя форма без `repo`, под которую написаны подмены
    `lambda sha:` в тестах пульта (требование 2). В отличие от
    `_repo_kwargs`, главная копия `config.ROOT` здесь — тоже артель."""
    ctx, refusal = _project_context(repo)
    return {"repo": repo} if ctx is not None or refusal else {}


def _gh_at(repo: Path | None, *args: str, **kwargs) -> subprocess.CompletedProcess:
    """`gh` с адресом проекта клона `repo` (`url` его записи); артель —
    прежний вызов `gh(*args, **kwargs)`; отказ разрешения — ненулевой код
    с текстом отказа, `gh` не запускается."""
    ctx, refusal = _project_context(repo)
    if refusal:
        return subprocess.CompletedProcess(args, 1, "", refusal)
    if ctx is not None:
        kwargs["repo"] = ctx.remote
    return gh(*args, **kwargs)


def _project_url_kwargs(repo: Path | None) -> tuple[dict, str]:
    """({"repo": <url проекта>} или {} у артели, отказ) — для функций,
    чей `repo` — адрес форджа (`check_runs_page`, `run_list`)."""
    ctx, refusal = _project_context(repo)
    return ({"repo": ctx.remote} if ctx is not None else {}), refusal


def _repo_kwargs(repo: Path | None) -> dict:
    """`repo=` для внутренних вызовов модуля: клон артели — умолчание этих
    функций, поэтому для него (и для `None`) вызов идёт прежней формой без
    `repo` — подмены `head_sha`/`first_parent_line` в тестах пульта
    написаны под неё, в том числе `lambda branch:` защищённого
    `tests/test_invariants.py::MergeNeedsGreenCiTest` (инвариант 19);
    внешний клон и любой другой репозиторий (главная копия у `pin-update`
    и `doctor main-ci`) передаются явно. Исход тот же: умолчание этих
    функций — тот же клон артели. Клон артели узнаётся признаком
    `repo_context.is_artel` (SPEC 01M484RNV3QBDY3B0M16J916ZP, строка 19)."""
    if repo is None or repo_context.is_artel(repo):
        return {}
    return {"repo": repo}


def _pipeline_project(repo: Path | None) -> str:
    """Имя проекта клона `repo`, итог CI которого даёт
    `forge.pipeline_status`, а не check runs этого модуля; "" — check runs
    (артель, GitHub, неразрешённый клон). Хостинг различает только реестр
    `forge` (SPEC 01M5WCXBM7WCMRWCBWNCHMAR3T, требование 1)."""
    ctx, _refusal = _project_context(repo)
    if ctx is None or not forge.ci_by_pipeline(ctx.target):
        return ""
    return ctx.target


def _forge_refusal(name: str, what: str) -> str:
    """Отказ функции `ci`, у которой для хостинга проекта `name` нет
    реализации: без `gh` и без HTTP (требование 8)."""
    return f"{what}: не поддержано для {forge.hosting(name)}"


def _pipeline_note(name: str, sha: str) -> "tuple[forge.PipelineStatus, str]":
    """(итог `forge.pipeline_status`, `note` в словах `branch_status`/
    `verifying_status`): красный — «не зелёный:», идущий — «ещё идёт»,
    `none`/`unknown` — «неизвестен» (`status_kind`, `verifying_is_red`)."""
    res = forge.pipeline_status(name, sha)
    short = sha[:8]
    if res.verdict == forge.GREEN:
        marks = f"; {'; '.join(res.marks)}" if res.marks else ""
        return res, f"CI коммита {short} зелёный (конвейеры хостинга){marks}"
    if res.verdict == forge.RED:
        return res, f"CI коммита {short} не зелёный: {res.reason}"
    if res.verdict == forge.RUNNING:
        return res, f"CI коммита {short} ещё идёт: {res.reason}"
    return res, f"статус CI коммита {short} неизвестен: {res.reason}"


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

    `repo` — адрес форджа (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-2), тот же
    смысл, что у `gh(repo=...)`: для `gh api` он становится `GH_REPO`
    окружения вызова. `repo=None` (по умолчанию)
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


def check_runs(sha: str, repo: Path | None = None) -> tuple[list | None, str]:
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

    `repo` — клон проекта, как у `head_sha` (SPEC 01M55V7WB94C9BZXTXTTH83YWV,
    требование 3): проверки спрашиваются у репозитория его проекта.
    """
    url_kwargs, refusal = _project_url_kwargs(repo)
    if refusal:
        return None, refusal
    runs: list = []
    total = None
    for page in range(1, config.CI_CHECKS_MAX_PAGES + 1):
        payload, why = check_runs_page(sha, page, **url_kwargs)
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


def _commit_workflow_runs(sha: str, checks: list,
                          repo: Path | None = None) -> _RunIndex | None:
    """Прогоны коммита для подписи его проверок; `None` — подписывать нечем.

    `None` и при сбое запроса (код `gh`, неразборный ответ), и когда ни
    один check-run не несёт связки с прогоном (`check_suite.id` или ссылки
    на прогон): сопоставлять тогда не с чем, а запрос был бы лишним. Исход
    статуса от этого не зависит — проверки подписываются «событие не
    определено» (требование 3). `repo` — клон проекта, как у `check_runs`.
    """
    if not any(_check_suite_id(c) is not None or _url_run_id(c) is not None
               for c in checks):
        return None
    res = _gh_at(repo, "api", f"repos/{{owner}}/{{repo}}/actions/runs"
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


def _other_branch(check: dict, index: _RunIndex | None, branch: str) -> str:
    """Головная ветка прогона проверки, если она доказанно не `branch`;
    "" — прогон не найден либо его `head_branch` пуст или совпадает.

    Ветка берётся только из `head_branch` ответа `actions/runs`: без
    найденного прогона с непустой чужой веткой проверка остаётся в
    вердикте (SPEC 01M4PMQSYPR2KD6N1JCVG9ZABV, требование 2) — недоказанная
    чужесть не должна делать красное зелёным."""
    run = _run_of(check, index)
    head = run.get("head_branch") if run is not None else None
    return head if isinstance(head, str) and head and head != branch else ""


def _branch_checks(checks: list, index: _RunIndex | None,
                   branch: str) -> tuple[list, list]:
    """(Проверки прогонов ветки задачи, исключённые проверки прогонов других
    веток) — вердикт строится только по первым (требование 1): красный
    прогон `main` на том же коммите не красит задачу."""
    own, excluded = [], []
    for check in checks:
        (excluded if _other_branch(check, index, branch) else own).append(check)
    return own, excluded


def _excluded_phrase(excluded: list, index: _RunIndex | None,
                     branch: str) -> str:
    """Отдельная фраза об исключённых проверках, "" — их нет.

    Текст не несёт подстрок, на которых стоят разборщики статуса («не
    зелёный:», «ещё идёт», «неизвестен», «check-run id») — требование 5."""
    if not excluded:
        return ""
    listing = ", ".join(
        f"{c.get('name', '?')}={c.get('conclusion') or c.get('status')} "
        f"(ветка {_other_branch(c, index, branch)}, {_run_label(c, index)})"
        for c in excluded)
    return f"; вне вердикта — проверки прогонов других веток: {listing}"


def _inherited_from_main(failed: list, repo: Path | None) -> str:
    """Фраза «красный унаследован от main <sha>» по упавшим проверкам ветки,
    упавшим с тем же именем и на вершине main; "" — совпадений нет либо
    вершину main или её проверки узнать не удалось (требование 4).

    У внешнего проекта главная ветка — `base` его записи, вершина —
    `origin/<base>` клона (локальную ветку push мержа не двигает), проверки
    вершины — у репозитория проекта (SPEC 01M55V7WB94C9BZXTXTTH83YWV,
    требование 4). У артели — прежняя локальная `main`."""
    ctx, refusal = _project_context(repo)
    if refusal:
        return ""
    if ctx is None:
        main_name = "main"
        main_sha, _why = head_sha("main", **_repo_kwargs(repo))
    else:
        main_name = ctx.base
        res = gitcmd.in_repo(repo, "rev-parse", "--verify",
                             f"refs/remotes/origin/{ctx.base}^{{commit}}")
        main_sha = (res.stdout.strip()
                    if res is not None and res.returncode == 0 else "")
    if not main_sha:
        return ""
    main_failed, _why = failed_check_names(main_sha, **_project_kwargs(repo))
    if not main_failed:
        return ""
    shared = sorted({str(c.get("name", "?")) for c in failed} & main_failed)
    if not shared:
        return ""
    return (f"; красный унаследован от {main_name} {main_sha[:8]}: "
            f"{', '.join(shared)}")


# Подсказка красного текста `verifying_status` при унаследованном красном.
# Id задачи не подставляется: у читателя статуса его нет.
PULL_MAIN_HINT = ("; подтянуть main в ветку задачи: artel.py pull-main "
                  "<id задачи>")


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


def _unexecuted_full_suite(checks: list, repo: Path | None,
                           index: _RunIndex | None) -> list[str]:
    """Имена пропущенных заданий полного набора без завершённого близнеца.

    При неизвестном событии пропущенного задания решение остаётся закрытым:
    без индекса нельзя подтвердить исполненного близнеца на этом коммите.
    Прочие `skipped` сюда не входят.
    """
    if repo is not None and not repo_context.is_artel(repo):
        return []
    pending = []
    for name in FULL_SUITE_CHECKS:
        siblings = [check for check in checks if check.get("name") == name]
        if not any(check.get("conclusion") == "skipped" for check in siblings):
            continue
        skipped_events = {_run_event(check, index) for check in siblings
                          if check.get("conclusion") == "skipped"}
        executed = any(
            check_finished(check)[0]
            and check.get("conclusion") == "success"
            and _run_event(check, index) in {"push", "pull_request"}
            for check in siblings)
        if (not skipped_events.issubset({"push", "pull_request"})
                or not executed):
            pending.append(name)
    return sorted(pending)


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


# Отказ чтения check-runs правами токена (SPEC 01M574A6YQHAPASS9716Z11G4Q,
# требование 1): токену проекта без права Checks GitHub отвечает 403 с одним
# из этих текстов, а запуски Actions тому же токену доступны. Прочий 403
# (лимит запросов и пр.) — не про права и на Actions не переводится.
CHECKS_FORBIDDEN_TEXTS = ("Resource not accessible by personal access token",
                          "Resource not accessible by integration")
# Строка причины перехода на Actions в `note` каждого такого исхода
# (требование 6) — не первая: на первой стоят разборщики статуса.
ACTIONS_REASON = ("check-runs недоступны токену проекта (403) — итог по "
                  "Actions runs")
# Событие запуска, которым CI проекта проверяет ветку задачи (Draft-MR).
BRANCH_TRIGGER_EVENT = "pull_request"


def checks_forbidden(why: str) -> bool:
    """`why` отказа чтения check-runs (текст `gh`) — HTTP 403 «Resource not
    accessible …», то есть у токена нет права Checks: read."""
    return "403" in why and any(t in why for t in CHECKS_FORBIDDEN_TEXTS)


def _actions_fallback(repo: Path | None, why: str) -> bool:
    """Отказ check-runs `why` переводит статус внешнего проекта на запуски
    Actions; артель (свой репозиторий, токен Оператора) — никогда
    (требование 7)."""
    ctx, refusal = _project_context(repo)
    return ctx is not None and not refusal and checks_forbidden(why)


def _actions_pages(repo: Path | None, endpoint: str,
                   key: str) -> tuple[list | None, str]:
    """Все записи `key` постраничного ответа Actions `endpoint`; (None,
    причина) — ответ не получен, не разобран или неполон (записей меньше,
    чем обещает `total_count`), как у `check_runs`. Без `total_count`
    полноту сверить не с чем — тоже «неизвестен» (инвариант 19)."""
    items: list = []
    total = None
    sep = "&" if "?" in endpoint else "?"
    for page in range(1, config.CI_CHECKS_MAX_PAGES + 1):
        res = _gh_at(repo, "api", f"{endpoint}{sep}per_page="
                                  f"{config.CI_CHECKS_PER_PAGE}&page={page}")
        if res.returncode != 0:
            detail = (res.stderr or res.stdout).strip()[:200]
            return None, f"gh не ответил: {detail or f'код {res.returncode}'}"
        try:
            payload = json.loads(res.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            return None, f"ответ gh не разобран: {exc}"
        chunk = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(chunk, list) or not all(isinstance(i, dict)
                                                  for i in chunk):
            return None, f"в ответе gh нет списка {key}"
        if page == 1:
            total = payload.get("total_count")
            if (isinstance(total, bool) or not isinstance(total, int)
                    or total < 0):
                return None, f"в ответе gh нечисловой total_count: {total!r}"
        items.extend(chunk)
        if len(items) >= total or len(chunk) < config.CI_CHECKS_PER_PAGE:
            break
    else:
        return None, (f"записей {key} больше, чем помещается в "
                      f"{config.CI_CHECKS_MAX_PAGES} страниц по "
                      f"{config.CI_CHECKS_PER_PAGE}")
    if len(items) != total:
        return None, (f"получено {len(items)} записей {key} из {total} "
                      f"обещанных — список неполон")
    return items, ""


class _ActionsRun(NamedTuple):
    """Запуск Actions коммита и его задания."""
    run: dict
    jobs: list


def _actions_runs(sha: str,
                  repo: Path | None) -> tuple[list[_ActionsRun] | None, str]:
    """Запуски Actions коммита `sha` с заданиями каждого; (None, причина) —
    запуски или задания хоть одного запуска не получены, не разобраны или
    неполны. Задания читаются и у зелёных запусков: неполный ответ заданий
    иначе не обнаружить, а имя упавшего — не узнать."""
    runs, why = _actions_pages(
        repo, f"repos/{{owner}}/{{repo}}/actions/runs?head_sha={sha}",
        "workflow_runs")
    if runs is None:
        return None, f"запуски Actions: {why}"
    result = []
    for run in runs:
        run_id = _int_or_none(run.get("id"))
        if run_id is None:
            return None, f"запуск Actions без id: {run.get('name', '?')}"
        jobs, why = _actions_pages(
            repo, f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs",
            "jobs")
        if jobs is None:
            return None, f"задания запуска Actions {run_id}: {why}"
        result.append(_ActionsRun(run, jobs))
    return result, ""


def _actions_finished(run: dict) -> bool:
    return run.get("status") == "completed"


def _actions_failed_names(item: _ActionsRun) -> list[str]:
    """Имена упавших заданий завершённого запуска; у красного запуска без
    красных заданий (заданий нет, `startup_failure`) — имя самого запуска:
    пустой список при красном запуске был бы ложью в пользу зелёного."""
    names = [str(j.get("name", "?")) for j in item.jobs
             if j.get("status") == "completed"
             and j.get("conclusion") not in GREEN]
    if not names and item.run.get("conclusion") not in GREEN:
        names = [str(item.run.get("name", "?"))]
    return names


def _actions_label(run: dict) -> str:
    return f"{run.get('event') or UNDEFINED_EVENT}, прогон {run.get('id')}"


def _actions_failed_listing(red: list[_ActionsRun]) -> str:
    """«<задание>=<заключение> (<событие>, прогон <id>)» по красным
    запускам; у запуска без красных заданий — по самому запуску."""
    parts = []
    for item in red:
        jobs = [j for j in item.jobs if j.get("status") == "completed"
                and j.get("conclusion") not in GREEN]
        for job in jobs or [item.run]:
            parts.append(f"{job.get('name', '?')}={job.get('conclusion')} "
                         f"({_actions_label(item.run)})")
    return ", ".join(parts)


class _ActionsVerdict(NamedTuple):
    """Разбор запусков Actions ветки: `kind` — "unknown" | "red" |
    "running" | "none" | "green"; `first` — первая строка `note` (для
    "none" — источник для `_no_checks_by_branch`); `failed` — упавшие
    (имена, для `_inherited_from_main`); `foreign` — фраза об исключённых."""
    kind: str
    first: str
    failed: list
    foreign: str


def _actions_verdict(sha: str, branch: str,
                     repo: Path | None) -> _ActionsVerdict:
    """Вердикт ветки задачи по запускам Actions коммита (требование 2):
    запуски других веток (непустой чужой `head_branch`) — вне вердикта;
    красный выигрывает у идущего; зелёный — только при завершённом запуске
    события `pull_request` и всех зелёных запусках вердикта."""
    short = sha[:8]
    runs, why = _actions_runs(sha, repo)
    if runs is None:
        return _ActionsVerdict(
            "unknown", f"статус CI коммита {short} неизвестен: {why}", [], "")
    own, excluded = [], []
    for item in runs:
        head = item.run.get("head_branch")
        other = isinstance(head, str) and head and head != branch
        (excluded if other else own).append(item)
    foreign = ""
    if excluded:
        listing = ", ".join(
            f"{i.run.get('name', '?')}={i.run.get('conclusion') or i.run.get('status')}"
            f" (ветка {i.run.get('head_branch')}, {_actions_label(i.run)})"
            for i in excluded)
        foreign = f"; вне вердикта — запуски Actions других веток: {listing}"
    red = [i for i in own if _actions_finished(i.run)
           and i.run.get("conclusion") not in GREEN]
    if red:
        failed = [{"name": n} for i in red for n in _actions_failed_names(i)]
        return _ActionsVerdict(
            "red", f"CI коммита {short} не зелёный: "
                   f"{_actions_failed_listing(red)}", failed, foreign)
    running = [i for i in own if not _actions_finished(i.run)]
    if running:
        listing = ", ".join(f"{i.run.get('name', '?')} "
                            f"({_actions_label(i.run)})" for i in running)
        return _ActionsVerdict(
            "running", f"CI коммита {short} ещё идёт: {listing}", [], foreign)
    if not any(i.run.get("event") == BRANCH_TRIGGER_EVENT for i in own):
        return _ActionsVerdict(
            "none", f"у коммита {short} нет запусков Actions ветки {branch} "
                    f"события {BRANCH_TRIGGER_EVENT}", [], foreign)
    return _ActionsVerdict(
        "green", f"CI коммита {short} зелёный ({len(own)} запусков "
                 f"Actions)", [], foreign)


def _with_actions_reason(note: str) -> str:
    return f"{note}\n{ACTIONS_REASON}"


def _verifying_by_actions(sha: str, branch: str,
                          repo: Path | None) -> tuple[str, str]:
    """Исход `verifying_status` по запускам Actions. «Статус неизвестен» —
    `VERIFYING_NONE`, как у неопределённой головы ветки («статус CI
    неизвестен» в начале `verifying_status`): ответа о CI нет вовсе, а
    «проверки идут» утверждало бы, что запуск виден."""
    verdict = _actions_verdict(sha, branch, repo)
    if verdict.kind == "unknown":
        return VERIFYING_NONE, _with_actions_reason(verdict.first)
    if verdict.kind == "none":
        outcome, note = _no_checks_by_branch(branch, verdict.first,
                                             verdict.foreign, repo)
        return outcome, _with_actions_reason(note)
    if verdict.kind == "red":
        inherited = _inherited_from_main(verdict.failed, repo)
        hint = PULL_MAIN_HINT if inherited else ""
        return VERIFYING_RED, _with_actions_reason(
            f"{verdict.first}{inherited}{hint}{verdict.foreign}")
    outcome = (VERIFYING_RUNNING if verdict.kind == "running"
               else VERIFYING_GREEN)
    return outcome, _with_actions_reason(f"{verdict.first}{verdict.foreign}")


def _branch_by_actions(sha: str, branch: str,
                       repo: Path | None) -> tuple[bool, str]:
    """Исход `branch_status` по запускам Actions; тексты читает
    `status_kind` так же, как тексты пути check-runs."""
    verdict = _actions_verdict(sha, branch, repo)
    if verdict.kind == "none":
        return False, _with_actions_reason(
            f"{verdict.first} — статус неизвестен{verdict.foreign}")
    if verdict.kind == "red":
        return False, _with_actions_reason(
            f"{verdict.first}{_inherited_from_main(verdict.failed, repo)}"
            f"{verdict.foreign}")
    return verdict.kind == "green", _with_actions_reason(
        f"{verdict.first}{verdict.foreign}")


def _failed_names_by_actions(sha: str,
                             repo: Path | None) -> tuple[set[str] | None, str]:
    """`failed_check_names` по запускам Actions (требование 3): все события,
    без отбора по ветке, как на пути check-runs."""
    short = sha[:8]
    runs, why = _actions_runs(sha, repo)
    if runs is None:
        return None, f"статус CI коммита {short} неизвестен: {why}"
    if not runs:
        return None, (f"у коммита {short} нет ни одного запуска Actions — "
                      f"статус неизвестен")
    return {n for item in runs if _actions_finished(item.run)
            for n in _actions_failed_names(item)}, ""


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
    name = _pipeline_project(repo)
    if name:
        res, note = _pipeline_note(name, sha)
        return {forge.GREEN: VERIFYING_GREEN, forge.RED: VERIFYING_RED,
                forge.RUNNING: VERIFYING_RUNNING}.get(res.verdict,
                                                      VERIFYING_NONE), note
    short = sha[:8]
    project = _project_kwargs(repo)

    runs, why = check_runs(sha, **project)
    if runs is None and _commit_not_found_in_origin(why):
        return VERIFYING_NONE, (
            f"{HEAD_NOT_IN_ORIGIN_NOTE} — GitHub не нашёл коммит {short} "
            f"({why}); пульт сам отправит голову ветки {branch} в origin "
            f"(push) при опросе verifying")
    if runs is None and _actions_fallback(repo, why):
        return _verifying_by_actions(sha, branch, repo)
    if not runs:
        first_source = (f"у коммита {short} нет ни одной проверки CI"
                        if runs is not None else
                        f"статус check-runs коммита {short} неизвестен ({why})")
        return _no_checks_by_branch(branch, first_source, "", repo)

    # Индекс прогонов нужен на любом исходе: без него не отделить проверки
    # прогонов других веток (запроса нет, если связки с прогоном нет ни у
    # одной проверки).
    index = _commit_workflow_runs(sha, runs, **project)
    runs, excluded = _branch_checks(runs, index, branch)
    foreign = _excluded_phrase(excluded, index, branch)
    if not runs:
        # Только чужие проверки — то же, что коммит без проверок: зелёным
        # пустой вердикт быть не может (требование 3).
        return _no_checks_by_branch(
            branch, f"у коммита {short} нет проверок прогонов ветки {branch}",
            foreign, repo)

    unfinished, reread = _unfinished_checks(runs)
    failed = [r for r in runs if r.get("conclusion") not in GREEN]
    unexecuted = _unexecuted_full_suite(runs, repo, index)
    divergence = _divergence_phrase(_event_divergence(runs, index))
    stuck = _stuck_checks(unfinished, index)
    if stuck:
        # Зависшая проверка важнее идущих рядом: без перезапуска коммит не
        # станет зелёным, сколько ни жди остальные.
        return VERIFYING_STUCK, _with_reread(
            f"CI коммита {short}: проверка зависла (порог "
            f"{config.CI_STUCK_CHECK_MINUTES} мин) — {'; '.join(stuck)}; "
            f"перезапуск — ci-rerun{divergence}{foreign}", reread)
    if unfinished:
        return VERIFYING_RUNNING, _with_reread(
            f"CI коммита {short} ещё идёт: "
            f"{_running_listing(unfinished, index)}{divergence}{foreign}",
            reread)
    if failed:
        inherited = _inherited_from_main(failed, repo)
        hint = PULL_MAIN_HINT if inherited else ""
        return VERIFYING_RED, _with_reread(
            f"CI коммита {short} не зелёный: "
            f"{_failed_listing(failed, index)}{divergence}{inherited}{hint}"
            f"{foreign}", reread)
    if unexecuted:
        return VERIFYING_RUNNING, _with_reread(
            f"CI коммита {short} ещё идёт: полный набор не исполнен — "
            f"{', '.join(unexecuted)}{foreign}", reread)
    return VERIFYING_GREEN, _with_reread(
        f"CI коммита {short} зелёный ({len(runs)} проверок){foreign}", reread)


def _no_checks_by_branch(branch: str, first_source: str, foreign: str,
                         repo: Path | None = None) -> tuple[str, str]:
    """Исход `verifying_status` без проверок ветки: `gh run list` по ветке
    показывает запуск — «идут», иначе «проверок нет вовсе» (SPEC T079).
    `repo` — клон проекта: `gh run list` идёт с `--repo <url>` проекта."""
    url_kwargs, refusal = _project_url_kwargs(repo)
    runs_by_branch, run_why = ((None, refusal) if refusal
                               else run_list(branch, **url_kwargs))
    if runs_by_branch:
        return VERIFYING_RUNNING, (f"{first_source}, но `gh run list` "
                                   f"по ветке {branch} показывает "
                                   f"запуск — проверки идут{foreign}")
    detail = (f"и `gh run list` по ветке {branch} не ответил "
              f"({run_why})" if runs_by_branch is None else
              f"и `gh run list` по ветке {branch} не показывает "
              f"запусков")
    return VERIFYING_NONE, (f"{first_source}, {detail} — проверок нет "
                            f"вовсе{foreign}")


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


def failed_check_names(sha: str,
                       repo: Path | None = None) -> tuple[set[str] | None, str]:
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

    `repo` — клон проекта коммита, как у `check_runs`. У проекта, итог CI
    которого даёт `forge.pipeline_status`, имена — упавшие задания без
    права падать; красный итог без такого задания — (None, причина).
    """
    name = _pipeline_project(repo)
    if name:
        res, note = _pipeline_note(name, sha)
        if res.verdict in (forge.GREEN, forge.RUNNING):
            return set(), ""
        if res.verdict == forge.RED and res.failed:
            return set(res.failed), ""
        if res.verdict == forge.RED:
            return None, f"{note} — краснота без упавшего задания"
        return None, note
    runs, why = check_runs(sha, **_project_kwargs(repo))
    short = sha[:8]
    if runs is None and _actions_fallback(repo, why):
        return _failed_names_by_actions(sha, repo)
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
    name = _pipeline_project(repo)
    if name:
        res, note = _pipeline_note(name, sha)
        return res.verdict == forge.GREEN, note

    project = _project_kwargs(repo)
    runs, why = check_runs(sha, **project)
    short = sha[:8]
    if runs is None and _actions_fallback(repo, why):
        return _branch_by_actions(sha, branch, repo)
    if runs is None:
        return False, f"статус CI коммита {short} неизвестен: {why}"
    if not runs:
        return False, (f"у коммита {short} нет ни одной проверки CI — "
                       f"статус неизвестен")

    index = _commit_workflow_runs(sha, runs, **project)
    runs, excluded = _branch_checks(runs, index, branch)
    foreign = _excluded_phrase(excluded, index, branch)
    if not runs:
        # «Неизвестен», как у коммита без проверок: гейт мержа ждёт, а не
        # отказывает и не перезапускает CI (требование 3).
        return False, (f"у коммита {short} нет проверок прогонов ветки "
                       f"{branch} — статус неизвестен{foreign}")

    # Состояния «проверка зависла» здесь нет (SPEC 01M3Y75C9TY76083CG1PK00EM4,
    # «Не входит»): на гейте мержа проверка без исхода — просто не зелёная.
    unfinished, reread = _unfinished_checks(runs)
    failed = [r for r in runs if r.get("conclusion") not in GREEN]
    unexecuted = _unexecuted_full_suite(runs, repo, index)
    divergence = _divergence_phrase(_event_divergence(runs, index))
    if unfinished:
        return False, _with_reread(
            f"CI коммита {short} ещё идёт: "
            f"{_running_listing(unfinished, index)}{divergence}{foreign}",
            reread)
    if failed:
        return False, _with_reread(
            f"CI коммита {short} не зелёный: "
            f"{_failed_listing(failed, index)}{divergence}"
            f"{_inherited_from_main(failed, repo)}{foreign}", reread)
    if unexecuted:
        return False, _with_reread(
            f"CI коммита {short} ещё идёт: полный набор не исполнен — "
            f"{', '.join(unexecuted)}{foreign}", reread)
    return True, _with_reread(
        f"CI коммита {short} зелёный ({len(runs)} проверок){foreign}", reread)


def accepted_full_suite(sha: str, repo: Path | None = None) -> tuple[str, str]:
    """(ID прогона, причина отказа): зелёный CI с исполненным полным набором.

    При отсутствии доказуемой связи задания с прогоном результат не
    переиспользуется: локальный гейт остаётся источником истины.
    """
    if repo is not None and not repo_context.is_artel(repo):
        return "", "полный набор CI проекта не идентифицирован"
    runs, why = check_runs(sha)
    if runs is None:
        return "", f"CI не ответил: {why}"
    if not runs:
        return "", "CI не ответил: у коммита нет проверок"
    unfinished, _ = _unfinished_checks(runs)
    if unfinished:
        return "", "CI головного коммита не завершён"
    if any(run.get("conclusion") not in GREEN for run in runs):
        return "", "CI головного коммита не зелёный"
    index = _commit_workflow_runs(sha, runs)
    suite_checks = [run for run in runs
                    if run.get("name") == FULL_SUITE_JOB
                    and run.get("conclusion") == "success"]
    if not suite_checks or _unexecuted_full_suite(runs, repo, index):
        return "", "CI не выполнил полный набор"
    for check in suite_checks:
        run = _run_of(check, index)
        run_id = (_int_or_none(run.get("id", run.get("databaseId")))
                  if run is not None else None) or _url_run_id(check)
        if run_id is not None:
            return str(run_id), ""
    return "", "CI не сообщил ID прогона полного набора"


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


def _main_line_runs(failed: list, running: list, runs_at: dict,
                    repo: Path | None = None) -> tuple[dict, str]:
    """(Подписи «событие, прогон» по (проверка, коммит), фраза о
    расхождении исхода по событиям) для упавших и идущих проверок линии
    (SPEC 01M46D5ZZQY7GBEW5TBVQ0P3ZV, AC-4/AC-6).

    Прогоны спрашиваются у того коммита линии, где проверка упала или
    идёт, а не у опорного: глубже головы у неё свой прогон."""
    commits = list(dict.fromkeys([c for _n, _c, c in failed]
                                 + [c for _n, c in running]))
    project = _project_kwargs(repo)
    indexes = {c: _commit_workflow_runs(c, runs_at[c], **project)
               for c in commits}

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
    — клон артели, тем же приёмом, что у `head_sha`. Клон внешнего проекта
    — ещё и адрес `gh` (`check_runs`, прогоны коммитов); главная копия
    `config.ROOT` — вызов артели. У проекта, итог CI которого даёт
    `forge.pipeline_status`, — `MAIN_UNKNOWN` с отказом без `gh`.
    """
    name = _pipeline_project(repo)
    if name:
        note = _forge_refusal(name, f"цвет CI main {sha[:8]}")
        return MainLineStatus(MAIN_UNKNOWN, sha, [], [], "", note)
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
    project = _project_kwargs(repo)
    for commit in line:
        runs, reason = check_runs(commit, **project)
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
    labels, divergence = _main_line_runs(failed, running, runs_at, repo)
    note = _main_line_note(kind, ref, failed, running, red_since, why,
                           green_count, labels, divergence)
    return MainLineStatus(kind, ref, failed, running, red_since, note)


def find_run_id(sha: str, repo: Path | None = None) -> tuple[str, str]:
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

    `repo` — клон проекта коммита, как у `check_runs`.
    """
    name = _pipeline_project(repo)
    if name:
        return "", _forge_refusal(name, "поиск прогона CI")
    res = _gh_at(repo, "api", f"repos/{{owner}}/{{repo}}/actions/runs"
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
    # Когда красных прогонов несколько, выбираем тот, где задание полного
    # набора действительно шло: порядок выдачи не доказывает исполнение.
    executed_runs: set[int] = set()
    if len(failed) > 1:
        checks, _ = check_runs(sha, **_project_kwargs(repo))
        if checks is not None:
            index = _RunIndex({}, {})
            for item in runs:
                item_id = _int_or_none(item.get("id", item.get("databaseId")))
                suite_id = _int_or_none(item.get("check_suite_id"))
                if item_id is not None:
                    index.by_id[item_id] = item
                    if suite_id is not None:
                        index.by_suite[suite_id] = item
            for check in checks:
                if (check.get("name") not in FULL_SUITE_CHECKS
                        or check.get("conclusion") == "skipped"):
                    continue
                owner = _run_of(check, index)
                if owner is not None:
                    owner_id = _int_or_none(owner.get(
                        "id", owner.get("databaseId")))
                    if owner_id is not None:
                        executed_runs.add(owner_id)
    preferred = [r for r in failed
                 if _int_or_none(r.get("id", r.get("databaseId")))
                 in executed_runs]
    run = (preferred or failed or runs)[0]
    run_id = run.get("databaseId", run.get("id"))
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        return "", "у прогона нет числового id"
    return str(run_id), ""


def check_run_workflow_run(check_id: str,
                           repo: Path | None = None) -> tuple[str, str]:
    """Id workflow-прогона, которому принадлежит check-run; ("", причина) —
    не найден (SPEC 01M3Y75C9TY76083CG1PK00EM4, требование 3).

    Check-run задания GitHub Actions — это job с тем же id, а job несёт
    `run_id` своего прогона. «Самый свежий прогон коммита» (`find_run_id`)
    здесь не годится: у коммита два прогона (push и pull_request), и в
    инциденте 02.10 оба были `completed/success`, а зависшая проверка
    принадлежала только одному из них.

    `repo` — клон проекта задачи, как у `check_runs`.
    """
    name = _pipeline_project(repo)
    if name:
        return "", _forge_refusal(name, "прогон проверки CI")
    res = _gh_at(repo, "api", f"repos/{{owner}}/{{repo}}/actions/jobs/{check_id}")
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


def trigger_rerun(branch: str, run_id: str = "",
                  repo: Path | None = None) -> str:
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

    `repo` — клон проекта задачи: голова ветки читается в нём, поиск
    прогона и сам повтор адресованы репозиторию его проекта.
    """
    name = _pipeline_project(repo)
    if name:
        return f"ре-ран CI не запущен: {_forge_refusal(name, 'повтор прогона')}"
    if run_id:
        rerun = _gh_at(repo, "run", "rerun", run_id)
    else:
        sha, why = head_sha(branch, **_repo_kwargs(repo))
        if not sha:
            return f"ре-ран CI не запущен: {why}"
        run_id, why = find_run_id(sha, **_project_kwargs(repo))
        if not run_id:
            return f"ре-ран CI не запущен: {why}"
        rerun = _gh_at(repo, "run", "rerun", run_id, "--failed")
    if rerun.returncode != 0:
        detail = (rerun.stderr or rerun.stdout).strip()[:200]
        return (f"ре-ран прогона {run_id} не запущен: "
               f"{detail or f'код {rerun.returncode}'}")
    watch = _gh_at(repo, "run", "watch", run_id, "--exit-status",
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
