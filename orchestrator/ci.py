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


def gh(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    """`gh` в корне репозитория; отсутствие CLI — такой же ненулевой код.

    Как и в `gitcmd.git`: разбирает исход вызывающий, а «команды нет»,
    «команда ответила ошибкой» и «команда не ответила вовсе» для гейта
    означают одно — ответа нет. Предел ожидания обязателен: гейт merge стоит
    на живом пути Оператора, и молчащая сеть не должна вешать `approve`
    без вывода и без конца. `timeout` по умолчанию — `GH_TIMEOUT_SEC`
    (короткий REST-опрос); `trigger_rerun` передаёт свой, куда больший —
    `gh run watch` реально ждёт завершения workflow, не ответа API.
    """
    timeout_sec = config.GH_TIMEOUT_SEC if timeout is None else timeout
    try:
        return subprocess.run(["gh", *args], cwd=config.ROOT,
                              capture_output=True, text=True,
                              timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 1, "", f"gh молчал дольше {timeout_sec} с")
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


def trigger_rerun(branch: str) -> str:
    """Настоящий повторный прогон CI головного коммита ветки (SPEC T082,
    требование 7): `gh run rerun <id> --failed` реально запускает упавшие
    job'ы заново (не то же самое, что повторное чтение уже завершённого
    check-run'а `branch_status`'ом), затем `gh run watch` ждёт его
    завершения — до того, как вызывающий код спросит `branch_status`
    снова за итоговым результатом.

    Best-effort: любой сбой (gh недоступен, прогон не найден, сеть легла)
    не бросает исключение — гейт не имеет права зависнуть на детекте
    флейка. Причина возвращается для журнала; повторный `branch_status`
    следом честно увидит тот же красный статус, если триггер не удался.
    """
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
