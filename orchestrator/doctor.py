"""doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI
(A3, tasks/T022/SPEC.md).

Один набор именованных чек-функций (`Check`), два потребителя:

- `runner.cmd_run` берёт `preflight_checks` — быстрые блокирующие проверки
  перед стартом шага (требование 2);
- команда `doctor` (`cmd_doctor`) прогоняет весь набор `all_checks`,
  включая дорогие (живой смоук CLI) и разовые (recovery-сверка, сироты).

Отсутствие токена роли, найденность CLI, свободное место на диске
и layout внешнего target'а — блокирующие (`status="fail"`) в preflight.
Git-идентичность тоже участвует в preflight (текст требования 2
перечисляет её среди «быстрых проверок») — предупреждением
(`"warn"`), не блоком: `runner.run_agent_once` уже проверяет её ещё раз
перед стартом процесса агента и журналит собственным предупреждением
(`agent env WARNING`) с существующим тестом на некритичность отказа
(`tests/test_multitarget.py`, `...identity_is_journalled_before_the_step`)
— превращать её в preflight в блок означало бы сломать тот тест без ADR
(принцип целостности). Двойная проверка (preflight + запуск агента) —
сознательно принятая избыточность ради видимости уже в preflight, а не
молчаливое исключение пункта требования. Она пропускается, если к этому
моменту preflight уже нашёл блокирующий провал (токен/CLI/диск) — шаг
всё равно не стартует, платить subprocess-вызовом `git config` за
дополнительную информацию не о чем не нужно (и, отдельно, ломает тесты,
проверяющие «при провале preflight не происходит вообще никаких
subprocess-вызовов», см. `preflight_checks`).

Версия CLI (требование 5) в per-step preflight НЕ входит — сознательно
суженная трактовка, зафиксированная и подтверждённая измерением, а не
предположением: живой прогон `claude --version` через `subprocess.run`
внутри `preflight_checks()` был реализован и прогнан против полного
набора тестов — 76 упавших тестов в 8+ файлах (`test_multitarget.py`,
`test_step_cost.py`, `test_agent_prompt.py`, `test_auto_cycle.py`,
`test_review_freshness.py`, `test_agent_log.py`, `test_agent_failure.py`,
`test_review_package.py` и др.), все — из-за того, что `subprocess.run`
внутри порождает `Popen`, а десятки существующих тестов подряд
запускают шаг агента через `mock.patch.object(runner.subprocess,
"Popen", ...)` с одним ожидаемым вызовом (сам агент) — лишний вызов
либо ловится тем же фейком не по назначению (падает на распаковке
`.communicate()`), либо рвёт инвариант «Popen вызван ровно один раз».
Почистить это означало бы переписать мокинг подпроцесса в файлах
задач, не входящих в объём T022, — само по себе нарушение «Изменения
вне зоны задачи — дефект» и, для тестов с точным счётчиком вызовов,
риск незаметно ослабить чужую проверку без ADR. `doctor.check_cli_version()`
остаётся частью `all_checks` — реальная сверка `claude --version`
происходит при явном вызове `doctor`, не на каждом шаге; решено
Оператором 25.08 как согласованное сужение требования 5 (SPEC.md
обновлён — см. tasks/T022/PLAN.md, раздел «Риски»); ревизия мокинга
subprocess — отдельная задача в беклоге P3.

Проверки, представляющие операционный инцидент, а не «шаг сейчас не
стартует» (recovery, сироты, давность бэкапа), заводят строку в
`alerts` (kind=incident) — так Оператор может её `alert-ack`. Точечные
блокировки шага (preflight fail) в alerts не дублируются: они уже видны
именованной причиной в журнале конкретной задачи.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path

from . import alerts, config, gitcmd, projects, roles, runner, spend, store, targets

# status: "ok" | "warn" | "fail" | "skip" ("skip" — честный пропуск проверки,
# требование 9: сверка forge-политики без `gh`/сети — не провал и не ок).
Check = namedtuple("Check", "name status detail")

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
ISOLATION_MARKER = "АРТЕЛЬ-ИЗОЛЯЦИЯ-A3-МАРКЕР-НЕ-ДОЛЖЕН-ПРОСОЧИТЬСЯ"
ISOLATION_SMOKE_TARGET = "__doctor_isolation_smoke__"
LIVE_SMOKE_PROMPT = "Ответь одним словом: ок."
LIVE_SMOKE_TIMEOUT_SEC = 120


# --- окружение шага (требование 2, 5, 9) ------------------------------

def check_cli_found() -> Check:
    path = shutil.which("claude")
    if path is None:
        return Check("cli-found", "fail",
                     "команда claude не найдена в PATH — установи Claude Code CLI")
    return Check("cli-found", "ok", path)


def cli_version() -> str | None:
    """Установленная версия CLI, разобранная из `claude --version`; None — не определилась."""
    try:
        res = subprocess.run(["claude", "--version"], capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    match = VERSION_RE.search(res.stdout)
    return match.group(0) if match else None


def check_cli_version() -> Check:
    version = cli_version()
    if version is None:
        return Check("cli-version", "warn",
                     "версия claude CLI не определилась (`claude --version`)")
    if version != config.CLI_VERSION_PIN:
        return Check("cli-version", "warn",
                     f"установлена {version}, пин {config.CLI_VERSION_PIN} — "
                     f"обновление пина (config.CLI_VERSION_PIN) — осознанный "
                     f"шаг Оператора, не автоматика")
    return Check("cli-version", "ok", version)


def check_token(role: str) -> Check:
    """Ambient CLAUDE_CODE_OAUTH_TOKEN/ANTHROPIC_API_KEY, иначе keychain-цепочка
    (roles.yaml token_slot/token_fallback, T019) — те же два источника, что
    и `runner.role_env` (setdefault-приоритет ambient), но без вызова самого
    `role_env()`: preflight зовётся на КАЖДОМ шаге, а `role_env()` тянет
    за собой git-идентичность (подпроцесс `git config`) и побочный эффект
    (mkdir ROLE_CONFIG_DIR) ради значения, которое здесь не нужно.
    """
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
        return Check("token", "ok", "токен уже в окружении (ambient)")
    token = runner.role_token(role)
    if token:
        return Check("token", "ok", f"роль {role}: токен добыт из keychain")
    slots = ", ".join(roles.token_slots(role)) or "нет"
    return Check("token", "fail",
                 f"роль {role}: токен не найден в keychain (слоты: {slots}) — "
                 f"`claude setup-token`, затем `security add-generic-password "
                 f"-a artel -s <слот> -U`")


def check_git_identity() -> Check:
    """Итоговый env роли, не сырой `git config`: ambient GIT_AUTHOR_*
    (setdefault-приоритет в `runner.role_env`) тоже закрывает идентичность.

    `role_env()` может поднять `OSError` (курируемый слой не создался —
    тот же класс отказа, что ловит `check_disk_space`/`live_smoke`) —
    не блок здесь: preflight лишь предупреждает, а настоящий отказ шага
    по этой причине остаётся за существующей обработкой в
    `runner.run_agent_once` (`agent run SKIPPED`).
    """
    try:
        env = runner.role_env()
    except OSError as exc:
        return Check("git-identity", "warn",
                     f"окружение роли не подготовлено: {exc}")
    missing = [n for n in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL")
              if not env.get(n)]
    if missing:
        return Check("git-identity", "warn",
                     f"не задано: {', '.join(missing)} — "
                     f"`git config --global user.name/user.email`")
    return Check("git-identity", "ok", "git-идентичность задана")


def check_disk_space() -> Check:
    try:
        free_mb = shutil.disk_usage(config.ROOT).free / (1024 * 1024)
    except OSError as exc:
        return Check("disk-space", "fail", f"диск не прочитан: {exc}")
    if free_mb < config.DOCTOR_MIN_FREE_MB:
        return Check("disk-space", "fail",
                     f"{free_mb:.0f} МБ свободно — меньше порога "
                     f"{config.DOCTOR_MIN_FREE_MB} МБ, освободи место")
    return Check("disk-space", "ok", f"{free_mb:.0f} МБ свободно")


def check_target_layout(target: str) -> Check:
    """workspace и артефактный репо внешнего target'а (требование 2, 9).

    Не блокирует: `runner.role_cwd` создаёт workspace лениво по требованию
    (существующее поведение, `tests/test_multitarget_invariants.py`
    полагается на него напрямую — задача заведена в БД без предварительного
    `target-init`), а отсутствие артефактного репо `fixation.fix`
    вырождает в «нечего фиксировать», не в отказ (fixation.py, модульный
    докстринг). Предупреждение — не потому что неважно, а потому что
    существующая архитектура уже деградирует по этому пути мягко.
    """
    if target == config.DEFAULT_TARGET:
        return Check("target-layout", "ok", "догфуд — особый случай (ADR-0003 3д)")
    repo = config.PROJECTS / target / ".git"
    if not repo.is_dir():
        return Check("target-layout", "warn",
                     f"артефактный репо {target} не инициализирован — "
                     f"`artel.py target-init {target}`")
    return Check("target-layout", "ok", "артефактный репо на месте")


def preflight_checks(role: str, target: str) -> list[Check]:
    """Быстрые проверки перед стартом шага (SPEC требование 2).

    Блокирующие: CLI найден, токен роли, диск. Warn: layout внешнего
    target'а (`check_target_layout`), git-идентичность. Версия CLI
    (требование 5) сюда не входит — см. модульный докстринг (измеренный
    конфликт с существующими тестами, вопрос в PLAN.md «Риски»).

    Git-идентичность считается, только если ни одна блокирующая проверка
    уже не провалилась: шаг и так не стартует, а `check_git_identity()`
    тянет за собой `runner.role_env()` — подпроцесс `git config`, лишний,
    если исход уже решён (и небезопасный вместе с тестами, которые для
    провала preflight ожидают вообще ни одного subprocess-вызова —
    `tests/test_doctor.py::PreflightBlocksMissingTokenTest`).
    """
    checks = [check_cli_found()]
    checks.append(check_token(role))
    checks.append(check_disk_space())
    checks.append(check_target_layout(target))
    if any(c.status == "fail" for c in checks):
        return checks
    checks.append(check_git_identity())
    return checks


# --- смоук изоляции (требование 6) -------------------------------------

def isolation_smoke(role: str = "developer") -> Check:
    """Маркеры project- и user-слоя не достигают env/промпта роли.

    user-слой: `role_env()` копирует ambient `os.environ`, затем всегда
    переписывает HOME на курируемый `config.ROLE_HOME` — проверка
    подменяет ambient HOME на временный каталог с маркером (НЕ реальный
    $HOME Оператора — офлайн-смоук им не пользуется вовсе) и убеждается,
    что итоговое окружение роли этот каталог не унаследовало.

    project-слой: `role_cwd()` эфемерного target'а — безопасный для записи
    каталог `.artel/projects/<synthetic>/workspace/` (gitignored, не
    реальный клон), маркер в нём проверяется на промпт роли — тот
    собирается только из `config.ROOT/skills/*.md` (`runner.cmd_run`),
    cwd в сборку не входит структурно.
    """
    leaks = []

    prior_home = os.environ.get("HOME")
    with tempfile.TemporaryDirectory() as fake_home:
        (Path(fake_home) / ".claude").mkdir(parents=True)
        (Path(fake_home) / ".claude" / "CLAUDE.md").write_text(
            ISOLATION_MARKER, encoding="utf-8")
        os.environ["HOME"] = fake_home
        try:
            env = runner.role_env(role)
        finally:
            if prior_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prior_home
    if env.get("HOME") == fake_home or any(
            ISOLATION_MARKER in str(v) for v in env.values()):
        leaks.append("user-слой: HOME роли не отведён от ambient-значения")

    project_dir = runner.role_cwd(ISOLATION_SMOKE_TARGET)
    try:
        (project_dir / "CLAUDE.md").write_text(ISOLATION_MARKER, encoding="utf-8")
        try:
            skill_names = roles.skills(role)
            prompt_text = "\n\n".join(
                (config.ROOT / "skills" / f"{s}.md").read_text(encoding="utf-8")
                for s in skill_names)
        except (roles.RolesError, OSError, UnicodeDecodeError) as exc:
            return Check("isolation-smoke", "fail",
                        f"промпт роли не собран для проверки: {exc}")
        if ISOLATION_MARKER in prompt_text:
            leaks.append("project-слой: маркер CLAUDE.md рабочего каталога "
                        "просочился в промпт роли")
    finally:
        shutil.rmtree(config.PROJECTS / ISOLATION_SMOKE_TARGET, ignore_errors=True)

    if leaks:
        return Check("isolation-smoke", "fail", "; ".join(leaks))
    return Check("isolation-smoke", "ok",
                 "маркеры project-/user-слоя не достигли env/промпта роли")


# --- живой смоук CLI (требование 3) -------------------------------------

def live_smoke(conn, role: str = "developer") -> Check:
    """Минимальный реальный вызов `claude`: код возврата и стоимость в потоке.

    НЕ вызывается из pre-flight (дорого); часть `doctor`, обязателен после
    изменения runner/config/roles/пина (SPEC требование 3). Тесты подменяют
    `subprocess.Popen` — настоящий прогон делает Оператор вручную (критерий
    приёмки 8, manual).

    Провал заводит `alerts` (kind=incident, требование 3: «результат в
    журнал») — тем же способом, что и соседние дорогие/разовые проверки
    (`recovery_check`, `check_orphans`, `check_backup_age`): вывод `doctor`
    в терминале, не сохранённый Оператором, иначе теряет провал живого
    смоука бесследно.
    """
    check = _live_smoke_run(role)
    if check.status != "ok":
        alerts.raise_alert(conn, None, "incident", "doctor.live_smoke", check.detail)
    return check


def _live_smoke_run(role: str) -> Check:
    try:
        env = runner.role_env(role)
    except OSError as exc:
        return Check("live-smoke", "fail",
                     f"окружение роли не подготовлено: {exc}")
    try:
        proc = subprocess.Popen(
            ["claude", "-p", LIVE_SMOKE_PROMPT,
             "--output-format", "stream-json", "--verbose"],
            cwd=config.ROOT, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except FileNotFoundError:
        return Check("live-smoke", "fail", "claude CLI не найден")

    try:
        output, _ = proc.communicate(timeout=LIVE_SMOKE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return Check("live-smoke", "fail",
                     f"таймаут живого смоука ({LIVE_SMOKE_TIMEOUT_SEC} с)")

    rc = proc.returncode
    cost = None
    for line in output.splitlines():
        parsed = spend.parse_cost_event(line)
        if parsed is not None:
            cost = parsed
    if rc != 0:
        return Check("live-smoke", "fail", f"rc={rc}; хвост: {output[-500:]}")
    if cost is None:
        return Check("live-smoke", "fail",
                     "нет события со стоимостью в финальном ответе потока")
    return Check("live-smoke", "ok", f"rc=0, стоимость ${cost['usd']:.4f}")


# --- recovery-сверка (требование 4) -------------------------------------

def recovery_check(conn, target: str) -> list[Check]:
    """Журнал БД ↔ файлы задач для ВНЕШНЕГО target: sha, чистота, fsck.

    Догфуд вне объёма сверки: HEAD ветки пульта двигают процессы вне FSM
    (мерж, коммиты Оператора вне цикла задач) — сверка sha дала бы
    систематические ложные инциденты, не имеющие отношения к целостности
    артефактов (tasks/T022/PLAN.md, «Подход»).
    """
    if target == config.DEFAULT_TARGET:
        return [Check("recovery", "skip", "догфуд вне объёма recovery-сверки")]

    repo = config.PROJECTS / target
    if not (repo / ".git").is_dir():
        return [Check("recovery", "skip",
                      f"артефактный репо {target} не инициализирован")]

    results = []
    latest = store.latest_fixed_sha(conn, target)
    current = gitcmd.head_sha(repo)
    if latest is not None and current and current != latest["fixed_sha"]:
        message = (f"sha головы {current} разошёлся с зафиксированным "
                  f"{latest['fixed_sha']} ({latest['id']})")
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.sha", message)
        results.append(Check("recovery-sha", "fail", message))
    else:
        results.append(Check("recovery-sha", "ok", "sha головы сходится с журналом"))

    clean = gitcmd.is_clean(repo=repo)
    if clean is False:
        message = f"артефактный репо {target} грязный"
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.dirty", message)
        results.append(Check("recovery-clean", "fail", message))
    else:
        results.append(Check("recovery-clean", "ok", "рабочая копия чистая"))

    fsck = gitcmd.in_repo(repo, "fsck", "--no-progress")
    if fsck.returncode != 0:
        message = (f"git fsck {target}: "
                  f"{fsck.stderr.strip()[:300] or fsck.stdout.strip()[:300]}")
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.fsck", message)
        results.append(Check("recovery-fsck", "fail", message))
    else:
        results.append(Check("recovery-fsck", "ok", "git fsck чисто"))

    return results


# --- сироты (требование 8) ----------------------------------------------

def _orphan_worktrees() -> list[str]:
    res = gitcmd.git("worktree", "list", "--porcelain")
    if res.returncode != 0:
        return []
    paths = [line.split(" ", 1)[1] for line in res.stdout.splitlines()
            if line.startswith("worktree ")]
    # Первая запись — основной checkout (ROOT). Per-task worktree ещё не
    # реализован (ADR-0003 3д — «полная версия», отложено): любая запись
    # сверх него сегодня сирота по построению.
    return paths[1:]


def check_orphans(conn) -> list[Check]:
    """Требование 8: три под-проверки; каждый найденный факт — incident-алерт."""
    results = []

    known_ids = {r["id"] for r in store.all_tasks(conn)}
    scan = [(config.DEFAULT_TARGET, config.TASKS)]
    try:
        for name in targets.load():
            if name != config.DEFAULT_TARGET:
                scan.append((name, config.PROJECTS / name / "tasks"))
    except targets.TargetsError:
        pass  # сломанный targets.yaml — забота другой проверки doctor'а
    orphan_dirs = [
        (target_name, entry)
        for target_name, tasks_dir in scan if tasks_dir.is_dir()
        for entry in sorted(tasks_dir.iterdir())
        if entry.is_dir() and entry.name not in known_ids
    ]
    if orphan_dirs:
        for target_name, entry in orphan_dirs:
            alerts.raise_alert(conn, target_name, "incident", "doctor.orphans.dir",
                              f"{entry} без строки БД")
        results.append(Check("orphans-dirs", "fail",
                            "; ".join(str(e) for _, e in orphan_dirs)))
    else:
        results.append(Check("orphans-dirs", "ok", "нет каталогов без строки БД"))

    stale = [r for r in store.all_tasks(conn)
            if r["state"] in ("done", "killed") and r["branch"]
            and gitcmd.branch_exists(r["branch"])]
    if stale:
        for r in stale:
            alerts.raise_alert(conn, r["target"] or config.DEFAULT_TARGET,
                              "incident", "doctor.orphans.branch",
                              f"{r['id']} ({r['state']}): ветка {r['branch']} "
                              f"не убрана")
        results.append(Check("orphans-branches", "fail",
                            "; ".join(f"{r['id']}:{r['branch']}" for r in stale)))
    else:
        results.append(Check("orphans-branches", "ok", "нет веток done/killed задач"))

    orphan_worktrees = _orphan_worktrees()
    if orphan_worktrees:
        for path in orphan_worktrees:
            alerts.raise_alert(conn, config.DEFAULT_TARGET, "incident",
                              "doctor.orphans.worktree", f"worktree {path} без задачи")
        results.append(Check("orphans-worktrees", "fail",
                            "; ".join(orphan_worktrees)))
    else:
        results.append(Check("orphans-worktrees", "ok", "лишних worktree нет"))

    return results


# --- прочие проверки (требование 9) --------------------------------------

def check_backup_age(conn) -> Check:
    marker = config.BACKUP_MARKER
    if not marker.exists():
        message = (f"{marker} не найден — бэкап .artel/ не настроен "
                  f"(Time Machine/rsync должен touch'ать этот файл по "
                  f"завершении, ADR-0003 3к)")
        alerts.raise_alert(conn, None, "incident", "doctor.backup_age", message)
        return Check("backup-age", "fail", message)
    age_days = (time.time() - marker.stat().st_mtime) / 86400
    if age_days > config.BACKUP_MAX_AGE_DAYS:
        message = (f"последний бэкап {age_days:.1f} дн. назад — больше "
                  f"порога {config.BACKUP_MAX_AGE_DAYS}")
        alerts.raise_alert(conn, None, "incident", "doctor.backup_age", message)
        return Check("backup-age", "fail", message)
    return Check("backup-age", "ok", f"{age_days:.1f} дн. назад")


def check_remote_empty(target: str) -> Check:
    if target == config.DEFAULT_TARGET:
        return Check("remote-empty", "skip",
                     "догфуд — remote есть, это GitHub пульта (ожидаемо)")
    if not (config.PROJECTS / target / ".git").is_dir():
        return Check("remote-empty", "skip",
                     f"артефактный репо {target} не инициализирован")
    if projects.artifact_repo_has_no_remote(target):
        return Check("remote-empty", "ok", "remote пуст")
    return Check("remote-empty", "fail",
                 f"у артефактного репо {target} есть remote — "
                 f"нарушение периметра (ADR-0003 3д)")


def check_base_branch(name: str, entry: dict) -> Check:
    """Сверка базовой ветки/merge-политики — по возможностям forge, иначе
    честный skip с причиной (SPEC требование 9 явно это допускает)."""
    if name == config.DEFAULT_TARGET:
        return Check("base-branch", "skip",
                     "догфуд — особый случай, не сверка базовой ветки с "
                     "форджем")
    if entry.get("forge") != "github":
        return Check("base-branch", "skip",
                     f"forge {entry.get('forge')} — сверка не реализована")
    gh = shutil.which("gh")
    if gh is None:
        return Check("base-branch", "skip", "gh CLI не найден — сверка пропущена")
    try:
        res = subprocess.run(
            ["gh", "repo", "view", entry["url"], "--json", "defaultBranchRef",
             "-q", ".defaultBranchRef.name"],
            capture_output=True, text=True, timeout=config.GH_TIMEOUT_SEC)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check("base-branch", "skip", f"gh не ответил: {exc}")
    if res.returncode != 0:
        return Check("base-branch", "skip",
                     f"gh repo view отказал: {res.stderr.strip()[:200]}")
    remote_base = res.stdout.strip()
    if not remote_base:
        return Check("base-branch", "skip", "gh не вернул defaultBranchRef")
    if remote_base != entry["base"]:
        return Check("base-branch", "warn",
                     f"targets.yaml base={entry['base']!r}, у форджа "
                     f"{remote_base!r}")
    return Check("base-branch", "ok", f"база сходится: {remote_base}")


# --- команда doctor -------------------------------------------------------

def all_checks(conn) -> list[Check]:
    """Требование 1: прогон всех проверок doctor."""
    checks = [check_cli_found()]
    if checks[-1].status == "ok":
        checks.append(check_cli_version())
    for role in sorted(set(config.STATE_ROLE.values())):
        checks.append(check_token(role))
    checks.append(check_git_identity())
    checks.append(check_disk_space())
    checks.append(check_backup_age(conn))
    checks.append(isolation_smoke())
    checks.append(live_smoke(conn))

    try:
        declared = targets.load()
    except targets.TargetsError as exc:
        checks.append(Check("targets-yaml", "fail", str(exc)))
        declared = {}
    for name, entry in declared.items():
        checks.append(check_target_layout(name))
        checks.append(check_remote_empty(name))
        checks.append(check_base_branch(name, entry))
        checks.extend(recovery_check(conn, name))

    checks.extend(check_orphans(conn))
    return checks


LABELS = {"ok": "ok", "warn": "WARN", "fail": "FAIL", "skip": "skip"}


def cmd_doctor(restore: bool = False) -> None:
    conn = store.db()
    if restore:
        print("Recovery-сверка после восстановления .artel/ из бэкапа:")
    checks = all_checks(conn)
    for c in checks:
        print(f"  [{LABELS[c.status]}] {c.name}: {c.detail}")

    triggers = alerts.open_alerts(conn, "trigger")
    if triggers:
        print("\nОткрытые триггеры (docs/triggers.md) — ack обязан нести решение:")
        for a in triggers:
            print(f"  #{a['id']} [{a['target'] or '-'}] {a['source']}: {a['message']}")

    failed = [c for c in checks if c.status == "fail"]
    if failed:
        print(f"\nDOCTOR: провалов {len(failed)} — чини по причинам выше")
        sys.exit(1)
    print("\nDOCTOR: ок")


def cmd_alert_ack(alert_id: str, resolution: str) -> None:
    conn = store.db()
    try:
        parsed_id = int(alert_id)
    except ValueError:
        sys.exit(f"alert-ack: '{alert_id}' — не номер алерта")
    error = alerts.ack(conn, parsed_id, "operator", resolution)
    if error is not None:
        sys.exit(f"alert-ack: {error}")
    print(f"alert #{parsed_id}: подтверждён")
