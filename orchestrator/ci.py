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
import subprocess

from . import config, gitcmd

# Заключения проверок, считающиеся зелёными. `skipped` обязателен: job
# `protected-paths` идёт только на pull_request и на push репозитория
# пропускается — без него зелёного CI не бывало бы вовсе.
GREEN = {"success", "skipped", "neutral"}


def gh(*args: str) -> subprocess.CompletedProcess:
    """`gh` в корне репозитория; отсутствие CLI — такой же ненулевой код.

    Как и в `gitcmd.git`: разбирает исход вызывающий, а «команды нет»,
    «команда ответила ошибкой» и «команда не ответила вовсе» для гейта
    означают одно — ответа нет. Предел ожидания обязателен: гейт merge стоит
    на живом пути Оператора, и молчащая сеть не должна вешать `approve`
    без вывода и без конца.
    """
    try:
        return subprocess.run(["gh", *args], cwd=config.ROOT,
                              capture_output=True, text=True,
                              timeout=config.GH_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 1, "", f"gh молчал дольше {config.GH_TIMEOUT_SEC} с")
    except OSError as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def head_sha(branch: str) -> tuple[str, str]:
    """Sha головного коммита ветки задачи и причина, если его нет."""
    res = gitcmd.git("rev-parse", "--verify", f"refs/heads/{branch}")
    sha = res.stdout.strip() if res.returncode == 0 else ""
    if not sha:
        return "", (f"головной коммит ветки {branch} не определён: "
                    f"{res.stderr.strip()[:200] or 'git не ответил'}")
    return sha, ""


def check_runs_page(sha: str, page: int) -> tuple[dict | None, str]:
    """Одна страница проверок коммита; (None, причина) — ответа нет."""
    res = gh("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs"
                    f"?per_page={config.CI_CHECKS_PER_PAGE}&page={page}")
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


def run_list(branch: str) -> tuple[list | None, str]:
    """Запуски `gh run list` по ветке; (None, причина) — ответа нет.

    Второй источник статуса CI для `verifying` (роадмап P3, T040; SPEC
    T079, требование 5, AC-6/AC-7): задержка события GitHub оставляет
    check-runs коммита временно пустыми, хотя запуск по ветке уже виден.
    Литерал `run`/`list` в argv — прямая цитата требования 5 («gh run
    list по ветке»), не домысел интерфейса.
    """
    res = gh("run", "list", "--branch", branch, "--json",
             "headBranch,status,conclusion", "--limit",
             str(config.CI_RUN_LIST_LIMIT))
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


def verifying_status(branch: str) -> tuple[str, str]:
    """Статус CI ветки задачи в состоянии `verifying` (SPEC T079,
    требование 5) — не то же самое, что `branch_status`: тот сворачивает
    любой не-зелёный исход в единое "нельзя мержить" (гейт merge_gate,
    условие которого не различает причины); здесь причины различать
    обязательно — «проверок нет» и «CI красный» ведут к разным записям
    журнала и (со временем) к разным решениям Оператора.

    Не создаёт коммитов и не зовёт ничего, что «будит» CI (требование 5,
    AC-12) — читает только.
    """
    sha, why = head_sha(branch)
    if not sha:
        return VERIFYING_NONE, f"статус CI неизвестен: {why}"
    short = sha[:8]

    runs, why = check_runs(sha)
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

    running = [str(r.get("name", "?")) for r in runs
              if r.get("status") != "completed"]
    if running:
        return VERIFYING_RUNNING, (f"CI коммита {short} ещё идёт: "
                                   f"{', '.join(running)}")

    failed = [f"{r.get('name', '?')}={r.get('conclusion')}" for r in runs
             if r.get("conclusion") not in GREEN]
    if failed:
        return VERIFYING_RED, f"CI коммита {short} не зелёный: {', '.join(failed)}"
    return VERIFYING_GREEN, f"CI коммита {short} зелёный ({len(runs)} проверок)"


def branch_status(branch: str) -> tuple[bool, str]:
    """(Зелёный ли CI ветки, пояснение для журнала и Оператора).

    Пояснение возвращается и на зелёном исходе: в журнале задачи должно
    остаться, какой именно коммит и сколькими проверками был признан
    годным к мержу.
    """
    sha, why = head_sha(branch)
    if not sha:
        return False, f"статус CI неизвестен: {why}"

    runs, why = check_runs(sha)
    short = sha[:8]
    if runs is None:
        return False, f"статус CI коммита {short} неизвестен: {why}"
    if not runs:
        return False, (f"у коммита {short} нет ни одной проверки CI — "
                       f"статус неизвестен")

    running = [str(r.get("name", "?")) for r in runs
               if r.get("status") != "completed"]
    if running:
        return False, f"CI коммита {short} ещё идёт: {', '.join(running)}"

    failed = [f"{r.get('name', '?')}={r.get('conclusion')}" for r in runs
              if r.get("conclusion") not in GREEN]
    if failed:
        return False, f"CI коммита {short} не зелёный: {', '.join(failed)}"
    return True, f"CI коммита {short} зелёный ({len(runs)} проверок)"
