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

Версия CLI (требование 5) — часть per-step preflight (T037). Изначально
(T022) сюда не входила: живой прогон `claude --version` через
`subprocess.run` внутри `preflight_checks()` был реализован и прогнан
против полного набора тестов — 76 упавших тестов в 8+ файлах, все —
из-за того, что `subprocess.run` внутри порождает `Popen`, а десятки
существующих тестов подряд мокали `runner.subprocess.Popen` напрямую
(единый модульный объект `subprocess` на весь процесс — подмена ловила
любой Popen-вызов, включая посторонний). Оператор 25.08 сузил
требование 5 до одной проверки в `doctor` (SPEC.md tasks/T022 обновлён,
см. tasks/T022/PLAN.md «Риски»), а ревизию мокинга subprocess вынес
строкой беклога P3. T037 эту ревизию сделала: `runner.spawn_agent` —
отдельная от `subprocess.Popen` точка мокинга cli-вызова агента (по
образцу `gitcmd.git`/`keychain.token`), тесты переведены на её мокинг —
конфликт снят, сверка пина CLI вернулась в `preflight_checks()`.

Проверки, представляющие операционный инцидент, а не «шаг сейчас не
стартует» (recovery, сироты, давность бэкапа), заводят строку в
`alerts` (kind=incident) — так Оператор может её `alert-ack`. Точечные
блокировки шага (preflight fail) в alerts не дублируются: они уже видны
именованной причиной в журнале конкретной задачи.
"""
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path

from . import (alerts, artifact_branch, canary, coldstart, config, fixation,
              gitcmd, liveness, projects, roles, runner, snapshot, spend,
              stack, store, targets, workspace, zone_lock)

# status: "ok" | "warn" | "fail" | "skip" ("skip" — честный пропуск проверки,
# требование 9: сверка forge-политики без `gh`/сети — не провал и не ок).
Check = namedtuple("Check", "name status detail")

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
ISOLATION_MARKER = "АРТЕЛЬ-ИЗОЛЯЦИЯ-A3-МАРКЕР-НЕ-ДОЛЖЕН-ПРОСОЧИТЬСЯ"
ISOLATION_SMOKE_TARGET = "__doctor_isolation_smoke__"
LIVE_SMOKE_PROMPT = "Ответь одним словом: ок."
LIVE_SMOKE_TIMEOUT_SEC = 120
# Анти-race `check_leases` (SPEC 01M1G..., требование 5, AC-9): интервал
# между двумя снимками `liveness._pid_alive` одного и того же lease перед
# тем, как считать его мёртвым — тот же порядок величины, что уже
# использует `pause.TERMINATE_POLL_SEC` для опроса живости pid.
LEASE_DEAD_RECHECK_SEC = 0.05


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


def _role_home_diff(reference: Path, deployed: Path) -> set[str]:
    """Пути (относительно референса), отличающиеся между референсом
    курируемого слоя и его развёрнутой копией — по каждому файлу
    РЕФЕРЕНСА: отсутствует в развёрнутом слое или отличается побайтово
    (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, AC-13).

    Файлы, которых нет в референсе, но которые появились в развёрнутом
    слое, — не расхождение: Оператор легитимно расширяет `.artel/home`
    по ходу работы (docs/reference/role-home.md, «Курирование»), а
    `claude` CLI пишет туда собственные рантайм-файлы на каждом шаге
    роли (`CLAUDE_CONFIG_DIR`) — учёт этих файлов как расхождения дал
    бы WARN постоянно, вне зависимости от реального состояния
    курируемого слоя (REVIEW.md итерации 1, R1-F1)."""
    diffs = set()
    for path in reference.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(reference)
        counterpart = deployed / rel
        if not counterpart.is_file() or counterpart.read_bytes() != path.read_bytes():
            diffs.add(str(rel))
    return diffs


def check_role_home_reference() -> Check:
    """Сверка развёрнутого курируемого слоя роли (`config.ROLE_CONFIG_DIR`)
    с референсом (`docs/reference/role-home/claude`) — WARN с перечнем
    отличающихся файлов, без автоправки (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN,
    требование 5, AC-13): деплой (`catalog._deploy_role_home_reference`)
    копирует референс только при холодном старте, поэтому расхождение,
    внесённое Оператором вручную позже, никак иначе не всплывает.
    """
    reference = config.ROOT / "docs" / "reference" / "role-home" / "claude"
    deployed = config.ROLE_CONFIG_DIR
    if not deployed.is_dir():
        return Check("role-home-reference", "ok",
                     "курируемый слой ещё не развёрнут")
    if not reference.is_dir():
        return Check("role-home-reference", "ok",
                     "референс отсутствует — сверка невозможна")
    diffs = _role_home_diff(reference, deployed)
    if diffs:
        return Check("role-home-reference", "warn",
                     f"развёрнутый слой .artel/home/.claude отличается от "
                     f"референса: {', '.join(sorted(diffs))}")
    return Check("role-home-reference", "ok",
                 "развёрнутый слой совпадает с референсом")


def check_target_layout(target: str) -> Check:
    """workspace и артефактный репо target'а — единая логика для ЛЮБОГО
    объявленного target, включая артель (A7, требование 2, AC-2).

    Не блокирует: `runner.role_cwd` создаёт workspace лениво по требованию
    (существующее поведение, `tests/test_multitarget_invariants.py`
    полагается на него напрямую — задача заведена в БД без предварительного
    `target-init`), а отсутствие артефактного репо `fixation.fix`
    вырождает в «нечего фиксировать», не в отказ (fixation.py, модульный
    докстринг). Предупреждение — не потому что неважно, а потому что
    существующая архитектура уже деградирует по этому пути мягко.
    """
    repo = config.PROJECTS / target / ".git"
    if not repo.is_dir():
        return Check("target-layout", "warn",
                     f"артефактный репо {target} не инициализирован — "
                     f"`artel.py target-init {target}`")
    return Check("target-layout", "ok", "артефактный репо на месте")


# Маркеры агентской обвязки target'а (SPEC T069, требование 3; ADR-0003
# п.14 — «агентская обвязка целевого не наследуется»); тот же список
# путей, что и в docstring `runner.role_cwd` про cwd-вектор конфиг-инъекции.
TARGET_WRAPPER_MARKERS = (".claude", ".mcp.json", "CLAUDE.md", "AGENTS.md")


def check_target_wrapper(target: str) -> Check:
    """Инвентаризация обвязки target'а (SPEC T069, требование 3; A7,
    требование 2, AC-2 — единая логика для ЛЮБОГО объявленного target,
    включая артель): наличие `.claude/`, `.mcp.json`, `CLAUDE.md`/
    `AGENTS.md` в его workspace — информационно, никогда не блокирует.

    Смотрит `workspace/` — то же дерево, что реально видит cwd шага роли
    (`runner.role_cwd`), не артефактный репозиторий `config.PROJECTS/
    <target>` целиком (туда git-первичка A2b коммитит SPEC/PLAN/REVIEW —
    другое дерево, не задето этой проверкой).
    """
    ws = config.PROJECTS / target / "workspace"
    found = [name for name in TARGET_WRAPPER_MARKERS if (ws / name).exists()]
    if found:
        return Check("target-wrapper", "warn",
                     f"обнаружена агентская обвязка target'а {target}: "
                     f"{', '.join(found)} (ADR-0003 п.14)")
    return Check("target-wrapper", "ok",
                 f"агентская обвязка target'а {target} не обнаружена")


def preflight_checks(role: str, target: str) -> list[Check]:
    """Быстрые проверки перед стартом шага (SPEC требование 2).

    Блокирующие: CLI найден, токен роли, диск. Warn: layout внешнего
    target'а (`check_target_layout`), git-идентичность, версия CLI
    (требование 5, T037 — сверка вернулась в pre-flight после того, как
    T037 развязало мокинг Popen на пути запуска агента и мокинг других
    subprocess-вызовов, см. модульный докстринг).

    Git-идентичность и версия CLI считаются, только если ни одна
    блокирующая проверка уже не провалилась: шаг и так не стартует, а
    обе тянут за собой subprocess-вызов (`git config`/`claude --version`),
    лишний, если исход уже решён (и небезопасный вместе с тестами,
    которые для провала preflight ожидают вообще ни одного
    subprocess-вызова — `tests/test_doctor.py::PreflightBlocksMissingTokenTest`).
    """
    checks = [check_cli_found()]
    checks.append(check_token(role))
    checks.append(check_disk_space())
    checks.append(check_target_layout(target))
    if any(c.status == "fail" for c in checks):
        return checks
    checks.append(check_git_identity())
    checks.append(check_cli_version())
    return checks


# --- смоук изоляции (требование 6) -------------------------------------

def isolation_smoke(role: str = "developer") -> Check:
    """Маркеры project- и user-слоя не достигают env/промпта роли.

    user-слой: `role_env()` копирует ambient `os.environ`, затем всегда
    переписывает HOME на курируемый `config.ROLE_HOME` — проверка
    подменяет ambient HOME на временный каталог с маркером (НЕ реальный
    $HOME Оператора — офлайн-смоук им не пользуется вовсе) и убеждается,
    что итоговое окружение роли этот каталог не унаследовало.

    project-слой (CLAUDE.md рабочего каталога): `role_cwd()` эфемерного
    target'а — безопасный для записи каталог `.artel/projects/
    <synthetic>/workspace/` (gitignored, не реальный клон), маркер в нём
    проверяется на промпт роли — тот собирается только из
    `config.ROOT/skills/*.md` (`runner.cmd_run`), cwd в сборку не входит
    структурно.

    project-/local-хуки (SPEC T058, инцидент T046): реальный `claude`
    шага роли резолвит `.claude/settings.json`/`.claude/settings.local.
    json` от cwd через git независимо от того, что несёт промпт, —
    проверка выше это не ловит. Здесь — структурная, офлайн проверка
    (без реального запуска `claude`, тем же приёмом, что и два маркера
    выше): единственная защита от этого вектора — флаг `--setting-
    sources`, реально попадающий в argv `run_agent_once`
    (`orchestrator/runner.py:572`) из `config.AGENT_SETTING_SOURCES`;
    здесь сверяется, что сама константа не включает `project`/`local`.
    Дискриминирующую половину критерия (канарейка реально не/срабатывает)
    проверяют локальные приёмочные `tasks/T058/acceptance_tests/
    test_ac1_ac2_role_hook_isolation.py` — они гоняют настоящий `claude`
    против настоящей канарейки на реально построенных `cmd`/`cwd`/`env`
    шага и не дублируются здесь намеренно (см. PLAN.md T058, «Подход»):
    живой прогон на каждый `doctor` не офлайн и не бесплатен.

    MCP-вектор (SPEC T069, требование 2): `claude` резолвит `.mcp.json`
    рабочего каталога — право коммита в целевой проект означало бы
    возможность подключить произвольный MCP-сервер в шаг роли. Защита —
    флаг `--strict-mcp-config` в реальном argv шага (`runner.role_cmd()`,
    единый источник для запуска и для этой проверки — SPEC T069, «тот же
    приём, что уже применён к --setting-sources», здесь буквально: сама
    сборка cmd, а не только константа). Живая дискриминирующая проверка
    того же класса, что и у project-/local-хуков выше, здесь не
    построена: экспериментально подтверждено (см. докстринг
    `tasks/T069/acceptance_tests/test_ac1_strict_mcp_command.py`), что
    свежий project-scope MCP-сервер в headless `-p`-режиме не
    подключается структурно ни с флагом, ни без него — различающего
    живого сигнала нет.
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
        except OSError as exc:
            # Тот же класс отказа, что уже ловят `check_git_identity`/
            # `_live_smoke_run` (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, AC-6):
            # объявленный инструмент манифеста не найден — не повод
            # уронить весь `doctor` необработанным исключением.
            return Check("isolation-smoke", "fail",
                        f"окружение роли не подготовлено: {exc}")
        finally:
            if prior_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prior_home
    if env.get("HOME") == fake_home or any(
            ISOLATION_MARKER in str(v) for v in env.values()):
        leaks.append("user-слой: HOME роли не отведён от ambient-значения")

    project_dir = runner.role_cwd(None, None, ISOLATION_SMOKE_TARGET)
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

    excluded_sources = {"project", "local"}
    active_sources = {s.strip() for s in config.AGENT_SETTING_SOURCES.split(",")}
    if active_sources & excluded_sources:
        leaks.append("project-хук: --setting-sources шага роли не "
                    f"исключает {sorted(active_sources & excluded_sources)} "
                    "— project-/local-слой клиентских настроек "
                    "(включая хуки) достижим шагом роли")

    cmd = runner.role_cmd()
    if "--strict-mcp-config" not in cmd:
        leaks.append("MCP-вектор: --strict-mcp-config отсутствует в "
                    "команде запуска шага роли — .mcp.json рабочего "
                    "каталога достижим шагом")

    if leaks:
        return Check("isolation-smoke", "fail", "; ".join(leaks))
    return Check("isolation-smoke", "ok",
                 "маркеры project-/user-слоя не достигли env/промпта роли, "
                 "project-/local-хуки исключены из resolve-сурсов шага, "
                 "MCP-конфиг рабочего каталога изолирован "
                 "(--strict-mcp-config)")


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

    Авто-ack (SPEC T088, требование 1) зовётся на каждом прогоне, не
    только при провале — тем же приёмом, что `check_leases`/
    `check_merge_lock`: иначе алерт прошлого провала не закроется в
    прогоне, где очередной вызов уже вернул `status="ok"`, но новых
    находок (по построению) нет.
    """
    check = _live_smoke_run(role)
    if check.status != "ok":
        alerts.raise_alert(conn, None, "incident", "doctor.live_smoke", check.detail)
    _auto_ack_gone(conn, "doctor.live_smoke", lambda _msg: check.status != "ok")
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
    """Журнал БД ↔ файлы задач артефактного репо target'а: sha, чистота,
    fsck — единая логика для ЛЮБОГО объявленного target, включая артель
    (A7, требование 2, AC-3). Сверка HEAD главной копии пульта
    (`config.ROOT`) в объём этой проверки не входит — та отдельная
    забота doctor-проверки пина (`check_root_pin`, AC-13): HEAD ROOT
    двигают процессы вне FSM обычной задачи (мерж, `pin-update`), сверка
    sha «как для артефактного репо» дала бы систематические ложные
    инциденты, не имеющие отношения к целостности артефактов.

    Авто-ack трёх под-проверок (SPEC T088, требования 2-4, 6) зовётся на
    каждом прогоне для КОНКРЕТНОГО target — независимо от остальных двух
    под-проверок и от того же source другого target (`_auto_ack_gone`
    получает `target=target`).
    """
    repo = config.PROJECTS / target
    if not (repo / ".git").is_dir():
        return [Check("recovery", "skip",
                      f"артефактный репо {target} не инициализирован")]

    results = []
    latest = store.latest_fixed_sha(conn, target)
    current = gitcmd.head_sha(repo)
    sha_mismatch = latest is not None and current and current != latest["fixed_sha"]
    if sha_mismatch:
        message = (f"sha головы {current} разошёлся с зафиксированным "
                  f"{latest['fixed_sha']} ({latest['id']})")
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.sha", message)
        results.append(Check("recovery-sha", "fail", message))
    else:
        results.append(Check("recovery-sha", "ok", "sha головы сходится с журналом"))
    _auto_ack_gone(conn, "doctor.recovery.sha", lambda _msg: sha_mismatch,
                  target=target)

    clean = gitcmd.is_clean(repo=repo)
    dirty = clean is False
    if dirty:
        message = f"артефактный репо {target} грязный"
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.dirty", message)
        results.append(Check("recovery-clean", "fail", message))
    else:
        results.append(Check("recovery-clean", "ok", "рабочая копия чистая"))
    _auto_ack_gone(conn, "doctor.recovery.dirty", lambda _msg: dirty, target=target)

    fsck = gitcmd.in_repo(repo, "fsck", "--no-progress")
    fsck_failed = fsck.returncode != 0
    if fsck_failed:
        message = (f"git fsck {target}: "
                  f"{fsck.stderr.strip()[:300] or fsck.stdout.strip()[:300]}")
        alerts.raise_alert(conn, target, "incident", "doctor.recovery.fsck", message)
        results.append(Check("recovery-fsck", "fail", message))
    else:
        results.append(Check("recovery-fsck", "ok", "git fsck чисто"))
    _auto_ack_gone(conn, "doctor.recovery.fsck", lambda _msg: fsck_failed,
                  target=target)

    return results


# --- авто-ack (tasks/T035/SPEC.md, требования 1-7) -----------------------

# Разбор сущности обратно из `message`, который сами же под-проверки ниже
# и составляют (формат стабилен, т.к. это единственный писатель) — `alerts`
# не хранит структурированный идентификатор сущности отдельным полем
# (SPEC этого не просит, заводить миграцию схемы вне зоны задачи).
_BRANCH_ALERT_RE = re.compile(r"ветка (\S+) не убрана$")
_DIR_ALERT_RE = re.compile(r"^(.+) без строки БД$")
_WORKTREE_ALERT_RE = re.compile(r"^worktree (.+) без задачи$")


def _auto_ack_gone(conn, source: str, is_live, target: str | None = None) -> None:
    """Подтверждает открытые алерты `source`, чьё условие `is_live` больше
    не подтверждает (требование 7: пока условие в силе — не трогать).

    Сообщение, не распознанное `is_live` (дрейф формата) — безопасный
    отказ: считается, что условие ещё в силе, ack не проставляется.

    `target`, если задан, дополнительно фильтрует по колонке `target`
    строки алерта (SPEC T088, требование 6): источники, у которых
    несколько target одновременно держат свой открытый алерт того же
    `source` (`doctor.recovery.*`, `doctor.task_counter`), не должны
    получать ack одного target по состоянию другого. По умолчанию
    `None` — прежнее поведение (не фильтровать), которое сохраняют все
    вызовы, где сущность и так уникальна внутри `message`
    (сироты/leases/merge_lock/backup_age).
    """
    for row in alerts.open_alerts(conn, "incident"):
        if row["source"] != source:
            continue
        if target is not None and row["target"] != target:
            continue
        if not is_live(row["message"]):
            alerts.auto_ack(conn, row["id"])


def _branch_alert_live(message: str) -> bool:
    match = _BRANCH_ALERT_RE.search(message)
    return match is None or gitcmd.branch_exists(match.group(1))


def _dir_alert_live(message: str, known_ids: set) -> bool:
    match = _DIR_ALERT_RE.match(message)
    return match is None or Path(match.group(1)).name not in known_ids


def _worktree_alert_live(message: str, current_paths: set) -> bool:
    match = _WORKTREE_ALERT_RE.match(message)
    return match is None or match.group(1) in current_paths


# --- сироты (требование 8) ----------------------------------------------

def _is_legit_task_worktree(wt_path: str, known_ids: set) -> bool:
    """Легитимный per-task worktree (SPEC T045, AC-9): лежит ровно в
    `config.WORKTREES/<id>`, и `<id>` — известная задача. Иначе (чужое
    место, неизвестная задача) — сирота по построению."""
    p = Path(wt_path)
    return p.parent == config.WORKTREES and p.name in known_ids


def _orphan_worktrees(known_ids: set) -> list[str]:
    # Первая запись `workspace.registered_paths()` — основной checkout
    # (ROOT), не worktree ни одной задачи.
    paths = workspace.registered_paths()[1:]
    return [p for p in paths if not _is_legit_task_worktree(p, known_ids)]


def check_orphans(conn) -> list[Check]:
    """Требование 8: три под-проверки; каждый найденный факт — incident-алерт."""
    results = []

    known_ids = {r["id"] for r in store.all_tasks(conn)}
    # Исторический tasks/ пульта сканируется БЕЗ ИЗМЕНЕНИЙ (требование 3
    # SPEC A7) вдобавок к артефактному каталогу КАЖДОГО объявленного
    # target, включая артель — она больше не исключается по имени
    # (A7, требование 2, AC-4): новые задачи артели ведут первичку в
    # `.artel/projects/artel/tasks/`, тем же путём, что и любой другой
    # target.
    scan = [(config.DEFAULT_TARGET, config.TASKS)]
    try:
        for name in targets.load():
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
    _auto_ack_gone(conn, "doctor.orphans.dir",
                  lambda msg: _dir_alert_live(msg, known_ids))

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
    _auto_ack_gone(conn, "doctor.orphans.branch", _branch_alert_live)

    orphan_worktrees = _orphan_worktrees(known_ids)
    if orphan_worktrees:
        for path in orphan_worktrees:
            alerts.raise_alert(conn, config.DEFAULT_TARGET, "incident",
                              "doctor.orphans.worktree", f"worktree {path} без задачи")
        results.append(Check("orphans-worktrees", "fail",
                            "; ".join(orphan_worktrees)))
    else:
        results.append(Check("orphans-worktrees", "ok", "лишних worktree нет"))
    current_worktree_paths = set(orphan_worktrees)
    _auto_ack_gone(conn, "doctor.orphans.worktree",
                  lambda msg: _worktree_alert_live(msg, current_worktree_paths))

    return results


# --- изоляция пула канарейки от ролей (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,
#     требование 13) ---------------------------------------------------

def check_role_log_pool_leak(conn) -> Check:
    """Требование 13б: логи шагов ролей проверяются на упоминание
    каталога пула канарейки — совпадение поднимает incident-алерт
    (AC-15). «На каждом doctor» — буквально из требования; второй
    триггер требования 13б («после каждого прогона канарейки») — часть
    механики `canary`, покрытой отдельно (AC-1..12), не этой проверки.

    Из трёх сигналов утечки, названных требованием 13б (каталог пула,
    имя его репозитория, GUID шаблона), проверяется только каталог пула
    (`config.CANARY_POOL_DIRNAME`) — единственный, зафиксированный кодом
    самого SPEC (требование 1); имя репозитория пула и GUID шаблонов —
    содержимое пула, ручная настройка Оператора («Не входит» SPEC), не
    значение, которое код мог бы знать заранее.

    Не заводит `_auto_ack_gone`, в отличие от `check_orphans`: утечка
    контекста роли — инцидент, требующий разбора Оператором, а не
    состояние, самоустраняющееся ротацией логов (`prune`) без его
    внимания.
    """
    if not config.LOGS.is_dir():
        return Check("canary-pool-leak", "ok", "логов ролей ещё нет")
    marker = config.CANARY_POOL_DIRNAME
    leaking = []
    for path in sorted(config.LOGS.glob("*.log")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker in text:
            leaking.append(path.name)
    if not leaking:
        return Check("canary-pool-leak", "ok",
                     "логи ролей не упоминают каталог пула канарейки")
    for name in leaking:
        alerts.raise_alert(
            conn, None, "incident", "doctor.canary-pool-leak",
            f"лог роли {name} упоминает каталог пула канарейки ({marker}) "
            f"— утечка контекста роли (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, "
            f"требование 13б)")
    return Check("canary-pool-leak", "fail",
                f"логи ролей упоминают каталог пула: {', '.join(leaking)}")


def check_canary_pool_drift() -> Check:
    """AC-8 (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3): предупреждает,
    если открытый пул `~/.artel-canary` разошёлся с запечатанным
    `canary/pool.sealed` — незапечатанные правки Оператора."""
    warning = canary.pool_drift_warning()
    if warning is None:
        return Check("canary-pool-drift", "ok",
                     "открытый пул канарейки не расходится с запечатанным "
                     "(либо пул/pool.sealed не развёрнуты)")
    return Check("canary-pool-drift", "warn", warning)


def check_token_repo_scope() -> list[Check]:
    """Требование 13в: предупреждает, если токен роли (слот keychain)
    виден более чем в одном репозитории GitHub (AC-16).

    Best-effort: единственный источник истины — реальный охват PAT на
    GitHub прямо сейчас — недетерминирован и недоступен offline
    (`markers.py`, AC-16 этой задачи, тот же класс зависимости, что и
    `check_token_repo_scope`'s собственный сетевой поход) — `gh`/сеть
    недоступны или токен не найден — честный `skip`, не блок доктора.
    Токены дедуплицируются по значению: сегодня (Фаза 0, roles.yaml
    `token_fallback`) все роли падают в один и тот же PAT — опрашивать
    его охват от каждой роли отдельно значило бы платить одним и тем же
    сетевым походом N раз.
    """
    if shutil.which("gh") is None:
        return [Check("token-repo-scope", "skip", "gh CLI не найден")]
    try:
        role_names = sorted(
            name for name, entry in roles.load().items()
            if isinstance(entry, dict) and entry.get("executor") == "agent")
    except roles.RolesError as exc:
        return [Check("token-repo-scope", "skip", str(exc))]
    seen: dict = {}
    results = []
    for role in role_names:
        token = runner.role_token(role)
        if not token or token in seen:
            continue
        seen[token] = role
        try:
            res = subprocess.run(
                ["gh", "api", "user/repos", "--paginate", "-q",
                 ".[].full_name"],
                env={**os.environ, "GH_TOKEN": token},
                capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append(Check("token-repo-scope", "skip",
                                f"роль {role}: {exc}"))
            continue
        if res.returncode != 0:
            results.append(Check(
                "token-repo-scope", "skip",
                f"роль {role}: область токена не опрошена — "
                f"{res.stderr.strip()[:150]}"))
            continue
        repos = {line.strip() for line in res.stdout.splitlines() if line.strip()}
        if len(repos) > 1:
            results.append(Check(
                "token-repo-scope", "warn",
                f"роль {role}: токен виден в {len(repos)} репозиториях "
                f"({', '.join(sorted(repos))}) — рекомендуется "
                f"fine-grained токен на один репозиторий (SPEC "
                f"01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13в)"))
        else:
            results.append(Check(
                "token-repo-scope", "ok",
                f"роль {role}: токен виден в {len(repos)} репозитории(ях)"))
    return results or [Check("token-repo-scope", "skip",
                             "ни у одной agent-роли не нашлось токена")]


# --- свежесть ветки (SPEC T051, требование 8) -----------------------------

def check_branch_freshness(conn) -> list[Check]:
    """Активная (нетерминальная) задача, чья ветка отстала от
    `config.MAIN_BRANCH` больше чем на `config.STALE_BRANCH_WARN_COMMITS`
    коммитов, — предупреждение (AC-5).

    Не incident, в отличие от `check_orphans`/`check_leases`: отставание
    ветки — ожидаемое и самоустраняющееся состояние параллельной работы
    (roadmap §4 п.2а), не операционный дефект с жизненным циклом ack —
    тем же приёмом, что `check_cli_version`/`check_target_layout`
    (информационный warn, не incident, ничего не заводит в `alerts`).

    Ветка ещё не существует в git или git не ответил
    (`gitcmd.commits_behind` вернул `None`) — сверять не с чем, задача
    молча пропускается (требование 9: тот же приём деградации, что у
    остальных git-примитивов, на которые уже опирается doctor).
    """
    stale = []
    for t in store.all_tasks(conn):
        if t["state"] in ("done", "killed") or not t["branch"]:
            continue
        behind = gitcmd.commits_behind(t["branch"])
        if behind is not None and behind > config.STALE_BRANCH_WARN_COMMITS:
            stale.append((t, behind))
    if not stale:
        return [Check("branch-freshness", "ok",
                      f"нет активных задач с веткой отставшей больше "
                      f"{config.STALE_BRANCH_WARN_COMMITS} коммитов от "
                      f"{config.MAIN_BRANCH}")]
    return [Check("branch-freshness", "warn",
                  f"{t['id']}: ветка {t['branch']} отстала от "
                  f"{config.MAIN_BRANCH} на {behind} коммитов")
           for t, behind in stale]


def _artifact_branch_first_commit_parent(branch: str) -> str:
    """Родитель самого раннего коммита `branch`, целиком авторства
    плотницкой записи артефактной ветки (`fixation.FIXATION_AUTHOR_EMAIL`
    — единственный автор, которым `artifact_branch.write_commit` подписывает
    ЛЮБОЙ коммит этой ветки, ни один вызывающий код не переопределяет его):
    граница между собственной историей ветки и унаследованным `main`/
    `origin` на момент её создания (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH,
    AC-5). Обход — от головы `branch` назад по первому родителю, пока автор
    совпадает; последний совпавший — искомый ранний коммит, его родитель и
    есть ответ.

    Пустая строка — `branch` пуста, ни один коммит не авторства плотницкой
    записи, либо git не ответил.
    """
    res = gitcmd.git("log", "--format=%H %ae", "--first-parent", branch)
    if res is None or res.returncode != 0:
        return ""
    boundary = ""
    for line in res.stdout.splitlines():
        sha, _, email = line.partition(" ")
        if email != fixation.FIXATION_AUTHOR_EMAIL:
            break
        boundary = sha
    if not boundary:
        return ""
    parent = gitcmd.git("rev-parse", "--verify", "--quiet", f"{boundary}^")
    if parent is None or parent.returncode != 0:
        return ""
    return parent.stdout.strip()


def check_artifact_branch_parent_ancestry(conn) -> list[Check]:
    """Родитель первого коммита артефактной ветки живой задачи обязан быть
    предком `origin/main` (SPEC 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH, требование 3,
    AC-5) — иначе ветка заведена от устаревшего/расходящегося пина главной
    копии (инцидент 06.09) и несёт в `tasks/` содержимое, которого уже
    могло не быть в `origin` (в т.ч. удалённые оттуда черновики).

    `origin` недоступен (нет сети, `origin` не настроен, песочница) —
    `skip` целиком: сверять не с чем (тот же приём деградации, что и у
    `check_branch_freshness`, когда `gitcmd.commits_behind` вернул `None`).
    Не incident (тем же доводом, что `check_branch_freshness`/
    `check_target_layout`): расхождение — состояние, требующее внимания
    Оператора, не операционный дефект с жизненным циклом ack.
    """
    origin_head, reason = gitcmd.fetch_head_sha("origin", config.MAIN_BRANCH)
    if not origin_head:
        return [Check("artifact-branch-parent-ancestry", "skip",
                      f"origin недоступен: {reason}")]
    warnings = []
    for t in store.all_tasks(conn):
        if t["state"] in ("done", "killed"):
            continue
        branch = artifact_branch.branch_name(t["id"])
        if not gitcmd.branch_exists(branch):
            continue
        parent = _artifact_branch_first_commit_parent(branch)
        if not parent:
            continue
        res = gitcmd.git("merge-base", "--is-ancestor", parent, origin_head)
        if res is None or res.returncode not in (0, 1):
            continue
        if res.returncode == 1:
            warnings.append(Check(
                "artifact-branch-parent-ancestry", "warn",
                f"{t['id']}: родитель первого коммита артефактной ветки "
                f"{parent[:12]} не предок origin/main {origin_head[:12]}"))
    if warnings:
        return warnings
    return [Check("artifact-branch-parent-ancestry", "ok",
                  "родитель первого коммита артефактной ветки каждой живой "
                  "задачи — предок origin/main")]


# --- lease с мёртвым pid (SPEC T044, требование 11) ----------------------

# Тот же приём разбора, что у `_branch_alert_live`/`_dir_alert_live`/
# `_worktree_alert_live` выше: сущность восстанавливается из `message`,
# который сами же `check_leases`/`check_merge_lock` и составляют.
_LEASE_ALERT_RE = re.compile(r"^(\S+): lease сессии (\S+) мёртв \(pid \d+ на \S+\)$")
_MERGE_LOCK_ALERT_RE = re.compile(
    r"^(\S+): мьютекс merge сессии (\S+) мёртв \(pid \d+ на \S+\)$")


def _lease_alert_live(message: str, rows_by_task: dict) -> bool:
    """SPEC T054, требование 1: условие живо, пока строка leases с тем же
    task_id/session_id ещё на месте и её (актуальный, не из сообщения) pid
    мёртв. Строки нет, session_id другой (lease перехвачен/переиздан) или
    pid ожил — условие снято."""
    match = _LEASE_ALERT_RE.match(message)
    if match is None:
        return True
    task_id, session_id = match.group(1), match.group(2)
    row = rows_by_task.get(task_id)
    if row is None or row["session_id"] != session_id:
        return False
    return not liveness._pid_alive(row["pid"])


def _merge_lock_alert_live(message: str, row) -> bool:
    """SPEC T054, требование 2: условие живо, пока текущий держатель
    мьютекса — то же (task_id, session_id), что в сообщении, и его
    (актуальный) pid мёртв. Замок пуст, держатель сменился или pid ожил —
    условие снято."""
    match = _MERGE_LOCK_ALERT_RE.match(message)
    if match is None:
        return True
    if row is None:
        return False
    task_id, session_id = match.group(1), match.group(2)
    if row["task_id"] != task_id or row["session_id"] != session_id:
        return False
    return not liveness._pid_alive(row["pid"])


# --- рекон осиротевшего шага (SPEC 01M1G..., требование 4, AC-7/AC-8) ---

# Терминальные события, закрывающие «agent run started» тем же приёмом,
# что уже пишет `orchestrator/runner.py` (`store.journal(..., "agent run
# ...")`): любое из них ПОСЛЕ старта — шаг довели до конца, не сирота.
_STEP_TERMINAL_ACTIONS = {
    "agent run finished", "agent run FAILED", "agent run TIMEOUT",
    "agent run SKIPPED",
}
# Маркер терминального события САМОГО РЕКОНА (см. `_reconcile_orphaned_
# step` ниже) — засчитывается как та же терминальная пара: повторный
# проход по журналу больше не видит уже реконенный старт сиротой
# (идемпотентность, AC-8).
_ORPHAN_ACTION_MARKER = "шаг оборван"


def _orphaned_start_step(steps):
    """Последнее «agent run started» без терминальной пары ГДЕ УГОДНО
    дальше в журнале — не только сравнением с последней записью (реконом
    может быть пропущено другое событие между стартом и обрывом, см.
    докстринг AC-7 приёмочного теста). `steps` — журнал ОДНОЙ задачи по
    порядку записи; `None` — сирот нет."""
    pending = None
    for s in steps:
        action = s["action"] or ""
        if action == "agent run started":
            pending = s
        elif action in _STEP_TERMINAL_ACTIONS or _ORPHAN_ACTION_MARKER in action:
            pending = None
    return pending


def _reconcile_orphaned_step(conn, task_id: str, dead_session_id: str,
                             steps: list) -> None:
    """Дописывает «шаг оборван смертью сессии `<id>`» для «agent run
    started» без терминальной пары, если он есть (SPEC 01M1G..., AC-7).

    `steps` — снимок журнала, снятый ДО этого вызова (в `check_leases`,
    до печати FAIL-строки): реконенное событие не должно само стать
    «последним событием задачи» в FAIL-строке этого же прогона (иначе
    Оператор не увидел бы, что реально происходило до рекона)."""
    orphan = _orphaned_start_step(steps)
    if orphan is None:
        return
    action = f"шаг оборван смертью сессии {dead_session_id}"
    detail = (f"шаг id={orphan['id']} ({orphan['actor']}), старт "
             f"{orphan['ts']}: {orphan['detail'] or '—'}")
    store.journal(conn, task_id, "doctor", action, detail)


def _last_start_step(steps):
    """Последняя запись «agent run started» в журнале задачи, ЗАКРЫТА она
    терминальной парой или нет — в отличие от `_orphaned_start_step`,
    которая ищет только НЕзакрытую (для идемпотентного рекона, AC-7/AC-8).
    Используется в FAIL-строке `check_leases` (AC-10, REVIEW.md
    итерации 1, R1-F1): держатель lease мог умереть МЕЖДУ шагами, когда
    последний запуск агента уже штатно завершился терминальным событием —
    Оператору всё равно нужен номер и время старта ПОСЛЕДНЕГО шага
    задачи, не только оборванного. `None` — агент по этой задаче ещё ни
    разу не запускался (в журнале нет ни одной записи «agent run
    started»)."""
    last = None
    for s in steps:
        if (s["action"] or "") == "agent run started":
            last = s
    return last


def _lease_fail_detail(conn, row, steps: list) -> str:
    """FAIL-строка `check_leases` по мёртвому lease (SPEC 01M1G...,
    требование 5, AC-10): держатель/pid/host (существующий текст,
    прежде байт-в-байт совпадавший с сообщением алерта) + роль держателя,
    номер и время старта последнего шага задачи (не только оборванного —
    R1-F1) и последнее журнальное событие задачи — Оператору не нужно
    отдельно звать `log`, чтобы понять, что произошло."""
    base = (f"{row['task_id']}: lease сессии {row['session_id']} "
           f"мёртв (pid {row['pid']} на {row['hostname']})")
    t = store.get_task(conn, row["task_id"])
    role = config.STATE_ROLE.get(t["state"], t["state"])
    parts = [base, f"роль {role}"]
    last_start = _last_start_step(steps)
    if last_start is not None:
        parts.append(f"шаг {last_start['id']} (старт {last_start['ts']})")
    if steps:
        last = steps[-1]
        parts.append(f"последнее событие: {last['action']} ({last['ts']})")
    return ", ".join(parts)


def check_leases(conn) -> list[Check]:
    """Требование 11 (T044)/5 (01M1G...): lease с мёртвым pid НА ЭТОМ host
    — incident-алерт, по аналогии с `check_orphans`. Чужой host не
    проверяется — pid без доступа к его процессной таблице нельзя ни
    подтвердить, ни опровергнуть.

    Анти-race (AC-9): «мёртв» на первом снимке — не окончательный вердикт,
    пока не подтверждён вторым снимком после `LEASE_DEAD_RECHECK_SEC` —
    ловит гонку между pid'ами двух соседних шагов ОДНОЙ сессии (шаг A уже
    завершился, шаг B ещё не стартовал).

    Каждый подтверждённо мёртвый lease заодно реконит осиротевший шаг
    задачи (AC-7/AC-8) — `doctor.check_leases` уже владеет и мёртвым pid,
    и строкой `leases` в одном месте (SPEC, «Материалы»).

    Авто-ack (SPEC T054, требование 1) зовётся на каждом прогоне, не
    только когда найден свежий мёртвый lease — иначе алерт прошлого
    прогона не закроется в прогоне, где условие уже снято, но новых
    находок нет.
    """
    host = socket.gethostname()
    rows = store.all_leases(conn)
    candidates = [row for row in rows
                 if row["hostname"] == host and not liveness._pid_alive(row["pid"])]
    dead = []
    for row in candidates:
        time.sleep(LEASE_DEAD_RECHECK_SEC)
        if not liveness._pid_alive(row["pid"]):
            dead.append(row)

    if not dead:
        results = [Check("leases", "ok", "нет lease с мёртвым pid на этом host")]
    else:
        results = []
        for row in dead:
            steps = store.task_steps(conn, row["task_id"])
            _reconcile_orphaned_step(conn, row["task_id"], row["session_id"], steps)
            # Сообщение алерта — прежний формат байт-в-байт (не FAIL-строка
            # `Check` ниже): `_LEASE_ALERT_RE`/`_lease_alert_live` разбирают
            # именно его для авто-ack, менять его означало бы сломать AC-1
            # SPEC T054.
            message = (f"{row['task_id']}: lease сессии {row['session_id']} "
                      f"мёртв (pid {row['pid']} на {row['hostname']})")
            alerts.raise_alert(conn, store.task_target(conn, row["task_id"]),
                              "incident", "doctor.leases", message)
            results.append(Check("leases", "fail",
                                 _lease_fail_detail(conn, row, steps)))

    rows_by_task = {row["task_id"]: row for row in rows}
    _auto_ack_gone(conn, "doctor.leases",
                  lambda msg: _lease_alert_live(msg, rows_by_task))
    return results


def check_merge_lock(conn) -> list[Check]:
    """SPEC T053, требование 4: мёртвый держатель мьютекса merge (протухший
    heartbeat/неживой pid) не блокирует merge навечно — `merge_lock.acquire`
    сам перешагивает такой замок при следующем взятии; эта проверка лишь
    делает факт видимым Оператору, тем же приёмом, что `check_leases`
    (требование 11 T044, на которую и ссылается требование 4). Чужой host
    не проверяется — та же причина, что у `check_leases`.

    Авто-ack (SPEC T054, требование 2) — как у `check_leases`: зовётся на
    каждом прогоне перед `return`, не только когда найден свежий мёртвый
    держатель.
    """
    row = store.merge_lock_row(conn)
    if row is None:
        result = [Check("merge-lock", "ok", "мьютекс merge свободен")]
    elif row["hostname"] != socket.gethostname():
        result = [Check("merge-lock", "ok",
                        f"мьютекс merge держит {row['task_id']} на чужом "
                        f"host {row['hostname']} — pid не проверяется")]
    elif liveness._pid_alive(row["pid"]):
        result = [Check("merge-lock", "ok",
                        f"мьютекс merge держит {row['task_id']} (сессия "
                        f"{row['session_id']}), pid жив")]
    else:
        message = (f"{row['task_id']}: мьютекс merge сессии {row['session_id']} "
                  f"мёртв (pid {row['pid']} на {row['hostname']})")
        alerts.raise_alert(conn, store.task_target(conn, row["task_id"]),
                           "incident", "doctor.merge_lock", message)
        result = [Check("merge-lock", "fail", message)]

    _auto_ack_gone(conn, "doctor.merge_lock",
                  lambda msg: _merge_lock_alert_live(msg, row))
    return result


# --- сторож зависших прогонов тестов --------------------------------------
# (SPEC 01M1PNBSHR2PMFECMP7C204MF1, требование 3, AC-8..AC-12/AC-15)

# `python -m unittest`/`pytest` в командной строке процесса (AC-8) — та
# же пара инструментов, что оставила шесть висящих прогонов инцидента
# 04.09 (SPEC «Контекст»).
_HUNG_TEST_CMD_RE = re.compile(r"\bpytest\b|-m\s+unittest\b")
# `ps -o etime=`: `[[дни-]часы:]минуты:секунды` (macOS/BSD и Linux —
# общий формат).
_ETIME_RE = re.compile(r"^(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)$")


def _etime_to_seconds(etime: str) -> float | None:
    match = _ETIME_RE.match(etime.strip())
    if match is None:
        return None
    days, hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    if days:
        total += int(days) * 86400
    return float(total)


def _running_processes() -> list[tuple[int, float, str]]:
    """(pid, возраст в секундах, командная строка) всех процессов машины;
    пустой список — `ps` не ответил (тихая деградация, тот же приём, что
    и у остальных OS-примитивов доктора). `-ww` — без обрезки длинной
    командной строки (BSD `ps`, macOS)."""
    try:
        res = subprocess.run(["ps", "-axww", "-o", "pid=,etime=,command="],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if res.returncode != 0:
        return []
    rows = []
    for line in res.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, etime_s, command = parts
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        age = _etime_to_seconds(etime_s)
        if age is None:
            continue
        rows.append((pid, age, command))
    return rows


def _process_cwd(pid: int) -> str | None:
    """cwd процесса `pid` по `lsof` (`ps` его не несёт вовсе) — `None`,
    если `lsof` не ответил или процесс уже исчез."""
    try:
        res = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    for line in res.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _hung_test_run_task_id(cwd: str) -> str | None:
    """id задачи по cwd процесса — первый сегмент относительно
    `config.WORKTREES` (тот же критерий легитимности, что и
    `_is_legit_task_worktree`); `.resolve()` на обеих сторонах — cwd,
    отданный `lsof`, разрешает симлинки ОС (`/var` -> `/private/var` на
    macOS), путь `config.WORKTREES` из песочницы теста иначе не совпал
    бы с ним побайтово."""
    try:
        rel = Path(cwd).resolve().relative_to(config.WORKTREES.resolve())
    except (ValueError, OSError):
        return None
    return rel.parts[0] if rel.parts else None


def _hung_test_run_task_lease_alive(conn, task_id: str) -> bool:
    """AC-9: «нет живого lease» — тот же критерий «мёртв», что и
    `check_leases`'s кандидаты (свой host и pid не адресуем); лизы нет
    вовсе, чужой host или pid жив — консервативно считается живым (не
    трогать чужое, если есть хоть малейшее сомнение)."""
    row = store.lease_row(conn, task_id)
    if row is None:
        return False
    if row["hostname"] != socket.gethostname():
        return True
    return liveness._pid_alive(row["pid"])


def _find_hung_test_runs(conn) -> list[dict]:
    """Кандидаты сторожа (AC-8/AC-9): `python -m unittest`/`pytest` с cwd
    внутри `.artel/worktrees/<id>`, старше `config.HUNG_TEST_RUN_AGE_SEC`,
    чья задача не держит живой lease."""
    found = []
    for pid, age, command in _running_processes():
        if age < config.HUNG_TEST_RUN_AGE_SEC:
            continue
        if not _HUNG_TEST_CMD_RE.search(command):
            continue
        cwd = _process_cwd(pid)
        if cwd is None:
            continue
        task_id = _hung_test_run_task_id(cwd)
        if task_id is None:
            continue
        if _hung_test_run_task_lease_alive(conn, task_id):
            continue
        found.append({"pid": pid, "age": age, "cwd": cwd, "task_id": task_id})
    return found


_HUNG_TEST_ALERT_RE = re.compile(
    r"^зависший прогон тестов: pid (\d+), worktree .+, возраст \d+ сек$")


def _hung_test_run_alert_live(message: str) -> bool:
    match = _HUNG_TEST_ALERT_RE.match(message)
    if match is None:
        return True
    return liveness._pid_alive(int(match.group(1)))


def check_hung_test_runs(conn) -> list[Check]:
    """AC-8..AC-10: только поиск и алерт — снятие живёт отдельно, под
    `doctor --fix` (`_fix_hung_test_runs`, AC-11/AC-12): тот же водораздел
    «наблюдение/действие», что `check_leases`/`_fix_dead_lease_groups`
    уже применяют к мёртвому lease (ANSWER-1, вариант B)."""
    candidates = _find_hung_test_runs(conn)
    if not candidates:
        results = [Check("hung-test-runs", "ok",
                         "зависших прогонов тестов не найдено")]
    else:
        results = []
        for c in candidates:
            message = (f"зависший прогон тестов: pid {c['pid']}, worktree "
                      f"{c['cwd']}, возраст {int(c['age'])} сек")
            alerts.raise_alert(conn, store.task_target(conn, c["task_id"]),
                               "incident", "doctor.hung_test_runs", message)
            results.append(Check("hung-test-runs", "fail", message))
    _auto_ack_gone(conn, "doctor.hung_test_runs", _hung_test_run_alert_live)
    return results


def _fix_hung_test_runs(conn) -> None:
    """`doctor --fix` (AC-11): снимает найденные `check_hung_test_runs`
    прогоны ГРУППОЙ (лидер + реальные потомки — аналог pytest-xdist
    воркера) и пишет перечень снятых pid в алерт (не только в журнал
    задачи — «в журнал алертов», AC-11). Обычный прогон (без `--fix`,
    AC-12) сюда не заходит вовсе."""
    candidates = _find_hung_test_runs(conn)
    if not candidates:
        return
    fixed = []
    for c in candidates:
        try:
            pgid = os.getpgid(c["pid"])
        except ProcessLookupError:
            continue
        count = liveness.terminate_process_group(pgid)
        fixed.append(f"{c['task_id']}: pid {c['pid']} "
                    f"({count} процесс(ов) группы)")
    if not fixed:
        return
    alerts.raise_alert(conn, None, "incident", "doctor.hung_test_runs.fix",
                       f"зависшие прогоны тестов сняты (doctor --fix): "
                       f"{'; '.join(fixed)}")
    print(f"  зависшие прогоны тестов сняты: {'; '.join(fixed)}")


def _fix_dead_lease_groups(conn) -> None:
    """`doctor --fix` (SPEC 01M1PNBSHR2PMFECMP7C204MF1, AC-6, ANSWER-1
    вариант B): остаточная группа процессов МЁРТВОГО lease — снимается
    ТОЛЬКО здесь, под флагом; `check_leases` остаётся наблюдательным
    (несёт только алерт, как и раньше, не предмет этой задачи)."""
    host = socket.gethostname()
    for row in store.all_leases(conn):
        if row["hostname"] != host or liveness._pid_alive(row["pid"]):
            continue
        if not row["pgid"]:
            continue
        count = liveness.terminate_process_group(row["pgid"])
        store.journal(conn, row["task_id"], "doctor",
                      "doctor --fix: группа процессов мёртвого lease снята",
                      liveness.group_kill_detail(row["pgid"], count))
        print(f"  [FIX] {row['task_id']}: "
              f"{liveness.group_kill_detail(row['pgid'], count)}")
def check_zone_waits(conn) -> list[Check]:
    """SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование 4: задача, чей первый
    шаг developer заблокирован занятостью зоны, — видимая проверка
    doctor, по образцу `check_leases`/`check_orphans`, не только строка в
    журнале САМОЙ заблокированной задачи. Вычисление занятости берётся у
    `zone_lock.blocking_conflict` целиком — та же проверка, что не
    пускает `run`/`auto` дальше, не отдельная копия.

    Не incident-алерт (в отличие от `check_leases`): занятость зоны —
    штатное ожидание, не операционный сбой, снимается сама после мержа/
    kill занявшей задачи (AC-6) или явной командой Оператора (AC-7).

    Позиция в очереди (`zone_lock.queue_position`, R1-F3, REVIEW.md
    итерация 1) — в детали, только когда конкурентов по ЭТОЙ зоне больше
    одного.
    """
    blocked = []
    for row in store.all_tasks(conn):
        if row["state"] != "in_dev":
            continue
        conflict = zone_lock.blocking_conflict(conn, row["id"], row)
        if conflict is None:
            continue
        path, occupier_id, occupier_state = conflict
        position, total = zone_lock.queue_position(conn, row["id"], path)
        queue = f", очередь {position}/{total}" if total > 1 else ""
        blocked.append(Check(
            "zone-waits", "warn",
            f"{row['id']} ждёт зоны {path} — занята {occupier_id} "
            f"({occupier_state}){queue}"))
    if not blocked:
        return [Check("zone-waits", "ok", "нет задач, ожидающих зоны")]
    return blocked


# --- прочие проверки (требование 9) --------------------------------------

def check_backup_age(conn) -> Check:
    """Деградировано до информационной строки (SPEC T049, требование 6;
    легализовано ADR-0005 п.3: отдельный бэкап `.artel/` не ведётся —
    сохранность определяется уровнем target'а, не бэкапом пульта).
    Больше не заводит `incident`: маркер, если Оператор всё же его ведёт
    по своей воле, остаётся диагностической строкой, не гейтом. Любой
    открытый алерт этого источника, заведённый ДО этой правки,
    авто-ack'ается — условие, которое его подняло, снято настоящей
    задачей, не наблюдением doctor.
    """
    _auto_ack_gone(conn, "doctor.backup_age", lambda _msg: False)
    marker = config.BACKUP_MARKER
    if not marker.exists():
        return Check("backup-age", "ok",
                     "бэкап .artel/ отдельно не ведётся (ADR-0005 п.3) — "
                     "информационно, не гейт")
    age_days = (time.time() - marker.stat().st_mtime) / 86400
    return Check("backup-age", "ok",
                 f"маркер найден, {age_days:.1f} дн. назад — информационно "
                 f"(ADR-0005 п.3, бэкап .artel/ не обязателен)")


def check_task_counters(conn) -> Check:
    """Контур счётчика номеров задач — замороженный legacy (SPEC T094,
    требование 6; ADR-0005 п.5 правки этой же задачи): генератором id
    стал ULID (`orchestrator/idgen.py`), `cmd_new` больше не расходует
    `store.next_task_number` ни для одного target — коллизия номеров,
    которую эта проверка когда-то ловила, для ULID структурно не
    существует. Сверка деградирована до информационной (AC-7): статус
    никогда не `fail`, алерт `doctor.task_counter` не заводится — только
    дословная формулировка «счётчик не движется» в detail.

    Полное удаление самого контура (`task_counters`, `seed_task_counters`,
    `next_task_number`/`peek_task_number`) — отдельная мелочь после M1
    (SPEC «Не входит»); эта функция лишь перестаёт его блокирующе
    сверять. Прежний incident-алерт мог остаться открытым от прогона
    до этой задачи — авто-ack безусловно закрывает его (условие
    «ещё живо» теперь всегда `False`).
    """
    try:
        declared = targets.load()
    except targets.TargetsError:
        declared = {}
    checked_targets = ({config.DEFAULT_TARGET} | store.counter_targets(conn)
                       | set(declared))
    for target in sorted(checked_targets):
        _auto_ack_gone(conn, "doctor.task_counter", lambda _msg: False,
                      target=target)
    return Check("task-counters", "ok",
                 "счётчик номеров задач заморожен как legacy (ULID — "
                 "основной генератор, SPEC T094) — счётчик не движется")


def check_pending_snapshots(conn) -> list[Check]:
    """Дожимает недоставленные снапшоты закрытия (SPEC T094, требование
    13, AC-15): задачи `done`/`killed` внешнего target'а, не канарейка,
    чья артефактная ветка пульта ещё жива — снапшот не подтверждён в
    origin целевого. Каждый прогон `doctor` пробует push заново; успех
    убирает ветку тем же путём, что и повторный `kill`."""
    checks = []
    for row in store.closed_external_tasks(conn):
        task_id = row["id"]
        target = row["target"] or config.DEFAULT_TARGET
        if not snapshot.pending(task_id):
            continue
        state = store.get_task(conn, task_id)["state"]
        note = snapshot.publish_and_cleanup(conn, task_id, target, state)
        status = "ok" if "опубликован" in note else "warn"
        checks.append(Check(f"snapshot-pending:{task_id}", status, note))
    return checks


def check_remote_empty(target: str) -> Check:
    """Единая логика для ЛЮБОГО объявленного target, включая артель (A7,
    требование 2, AC-2): артефактный репозиторий `.artel/projects/
    <target>/` — не клон целевого форджа, у него нет причин нести
    remote, независимо от того, что сам target объявляет своим
    настоящим GitHub-репозиторием."""
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
    честный skip с причиной (SPEC требование 9 явно это допускает).
    Единая логика для ЛЮБОГО объявленного target, включая артель (A7,
    требование 2, AC-2)."""
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


# --- пин запущенной версии (A7, Stage1, требования 5-6, AC-13) ----------

def check_root_pin() -> Check:
    """Расхождение пина `config.ROOT` (HEAD главной копии — Stage0
    удерживает его от изменения переходом `merge_gate -> done`,
    `orchestrator/fsm_merge_gate.py`) с текущим HEAD `refs/heads/
    <MAIN_BRANCH>` main артели (её `origin`) — информационно, никогда
    не блокирует прогон doctor (AC-13): пин обновляет только Оператор
    отдельной командой `pin-update` (Stage1, AC-14), не doctor сам.

    `git ls-remote origin` — единственный опрос без единого локального
    side-effect (не трогает объектную базу/индекс/HEAD ROOT, в отличие
    от `git fetch`): доктор не имеет права двигать что-либо сам.

    Git не ответил (нет origin, сеть недоступна, песочница без
    настоящего git) — сверять не с чем, `ok` тем же приёмом деградации,
    что и у остальных git-примитивов doctor'а: отсутствие ответа — не
    расхождение и не повод для warn.
    """
    root_sha = gitcmd.head_sha()
    ls = gitcmd.git("ls-remote", "origin", f"refs/heads/{config.MAIN_BRANCH}")
    if ls is None or ls.returncode != 0 or not ls.stdout.strip() or not root_sha:
        return Check("root-pin", "ok",
                     "main артели (origin) не опрошен — пин не сверен")
    origin_sha = ls.stdout.split()[0]
    if origin_sha == root_sha:
        return Check("root-pin", "ok", f"пин {root_sha} сходится с main "
                     f"артели {origin_sha}")
    return Check("root-pin", "warn",
                 f"пин {root_sha} отстал от main артели {origin_sha} — "
                 f"обнови: artel.py pin-update {origin_sha}")


# --- уборка осиротевших артефактных веток (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T,
# требование 4/AC-4) --------------------------------------------------------

ORPHAN_ARTIFACT_BRANCH_SOURCE = "doctor.cleanup.artifact_branches"

# `git ls-remote --heads origin 'artifact/*'` — сверка веток-кандидатов с
# origin (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1): один и тот же
# glob на весь прогон уборки, не по одному запросу на ветку (AC-3).
_REMOTE_ARTIFACT_GLOB = "artifact/*"
# Сентинел «аргумент не передан», отличимый от легитимных значений
# `None`/`set()`/`[]` (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, «Подход» PLAN):
# явно переданное `remote`/`orphans` (в т.ч. `None`) — используется как
# есть, БЕЗ пересчёта; аргумент не передан — функция вычисляет его сама
# (обратная совместимость с прямыми вызовами существующих юнит-тестов и
# приёмочных `_sandbox.py`, где `doctor._orphan_artifact_branches(conn)`
# зовётся с одним аргументом).
_UNSET = object()


def _remote_artifact_branch_names() -> set[str] | None:
    """Имена веток `artifact/<id>`, присутствующих на `origin` (SPEC
    01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1): единственное место,
    зовущее `git ls-remote --heads origin 'artifact/*'` — ровно один
    запрос на весь прогон уборки, не по одному на ветку-кандидата (AC-3).

    `None` — origin не ответил (git не ответил вовсе или вернул ненулевой
    код возврата, требования 5-6): вызывающий код обязан трактовать это
    как «критерий не вычислим», НЕ как «на origin ничего нет» — в
    отличие от `gitcmd.list_branches`/`remote_branch_sha`, где та же
    деградация к пустоте корректна, здесь пустота означала бы удалить
    ЛЮБУЮ локальную ветку как сироту (fail-closed, принцип целостности).
    """
    res = gitcmd.git("ls-remote", "--heads", "origin", _REMOTE_ARTIFACT_GLOB)
    if res is None or res.returncode != 0:
        return None
    prefix = "refs/heads/"
    names = set()
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith(prefix):
            names.add(ref[len(prefix):])
    return names


def _orphan_artifact_branches(conn, remote=_UNSET) -> list[str] | None:
    """Ветки `artifact/<id>` пульта, для которых НЕТ строки в БД
    (регистронезависимо — `artifact_branch.branch_name` работает с
    `task_id.lower()`) И которых нет среди веток `artifact/*` на origin
    (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1, AC-1/AC-2: ОБА
    условия обязаны быть верны — ветка, живая хотя бы по одному из двух
    источников истины, сиротой не считается). Только чтение, без
    удаления — общая часть между `sweep_orphan_artifact_branches` (сама
    уборка) и `cmd_doctor` (честный CLI-вывод: нужно знать, были ли
    сироты, независимо от того, удалось ли их удалить).

    `remote` — предвычисленный набор веток origin (`_remote_artifact_
    branch_names`); по умолчанию (аргумент не передан) вычисляется
    здесь — вызывающий код, которому важно не делать второй запрос за
    один прогон (`cmd_doctor`, AC-3), передаёт уже вычисленное значение
    явно.

    `None` — origin не ответил (требование 6): вся функция тоже
    возвращает `None`, не пустой список — пустой список уже легитимно
    означает «сирот нет», спутать эти два случая означало бы посчитать
    origin пустым и удалить произвольную локальную ветку.
    """
    if remote is _UNSET:
        remote = _remote_artifact_branch_names()
    if remote is None:
        return None
    known_ids = {r["id"].lower() for r in store.all_tasks(conn)}
    branches = gitcmd.list_branches("artifact/") or []
    return sorted(
        b for b in branches
        if b[len("artifact/"):] not in known_ids and b not in remote)


def sweep_orphan_artifact_branches(conn, orphans=_UNSET) -> list[str] | None:
    """Удаляет ветки `artifact/<id>` пульта, отсутствующие И в БД, И на
    origin (SPEC «Контекст»: источник утечки — тест, заводящий задачу
    через `cmd_new` без подмены `config.ROOT`, коммитивший артефакты
    прямиком в НАСТОЯЩИЙ репозиторий пульта; расширено требованием 1
    задачи 01M1REVP9WGRHDDNVEVE8BBH0Z — на чужой копии, где локальной
    строки БД у живой задачи просто нет, критерий «только БД» сносил бы
    её). Только по явному вызову Оператора (`doctor --fix`), не
    автоматически — ветки живых задач не трогаются.

    `orphans` — предвычисленный список кандидатов (`_orphan_artifact_
    branches`); по умолчанию (аргумент не передан) вычисляется здесь —
    `cmd_doctor` передаёт уже вычисленный список явно, чтобы не делать
    второй запрос origin за один прогон уборки (AC-3).

    `orphans is None` (origin недоступен, требование 5/AC-6): уборка НЕ
    ВЫПОЛНЯЕТСЯ ВООБЩЕ — `git branch -D` не зовётся ни разу, incident не
    заводится, возврат — `None` (fail-closed, принцип целостности).

    Иначе — ровно один incident-алерт на весь прогон уборки, с
    перечислением удалённого в сообщении (не по алерту на каждую ветку —
    Оператору нужна одна строка на уборку, не журнал по счётчику
    находок). Возврат `git branch -D` проверяется (ANSWER-2 п.3, R1-F3):
    ветка, которую не удалось удалить, не попадает ни в возвращаемый
    список, ни в текст алерта как «удалено» — только в отдельную честную
    часть сообщения. Возвращает список ФАКТИЧЕСКИ удалённых имён веток;
    пустой — либо сирот не нашлось, либо ни одно удаление не удалось
    (`cmd_doctor` различает эти два случая в CLI-выводе через `orphans`,
    ANSWER-3 R1-F3).
    """
    if orphans is _UNSET:
        orphans = _orphan_artifact_branches(conn)
    if orphans is None:
        return None
    deleted = []
    failed = []
    for branch in orphans:
        res = gitcmd.git("branch", "-D", branch)
        (deleted if res is not None and res.returncode == 0 else failed).append(branch)
    if orphans:
        parts = []
        if deleted:
            parts.append(f"удалены: {', '.join(deleted)}")
        if failed:
            parts.append(f"НЕ удалены (ошибка git branch -D): {', '.join(failed)}")
        alerts.raise_alert(
            conn, None, "incident", ORPHAN_ARTIFACT_BRANCH_SOURCE,
            f"осиротевшие артефактные ветки: {'; '.join(parts)}")
    return deleted


def _print_orphan_branch_candidates(orphans: list[str]) -> None:
    """Требования 3-4 (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z): число кандидатов
    на удаление ПОЛНОСТЬЮ, но их имён — только первые `config.
    DOCTOR_ORPHAN_PREVIEW_LIMIT`, с пометкой про `doctor --fix`. Общая
    для режима предпросмотра (`doctor`) и для `--fix` (там — печатается
    ДО удаления, требование 4/AC-5)."""
    print(f"Осиротевшие артефактные ветки-кандидаты на удаление: "
         f"{len(orphans)} (первые {config.DOCTOR_ORPHAN_PREVIEW_LIMIT} имён "
         f"ниже; удалит `doctor --fix`)")
    for branch in orphans[:config.DOCTOR_ORPHAN_PREVIEW_LIMIT]:
        print(f"  {branch}")


# --- уборка игнорируемых файлов артефактных веток (SPEC ------------------
# 01M1KVG3KSCY47HWXWF5HM0E76, требование 4, AC-5) -------------------------

def _fix_ignored_artifact_files(conn) -> None:
    """`doctor --fix`: убирает из артефактной ветки КАЖДОЙ живой задачи
    файлы, которые `.gitignore` пульта (`config.ROOT`) считает
    игнорируемыми (тот же критерий, что `checkpoint._commit_external_
    step_artifacts` уже применяет к новым автокоммитам, `gitcmd.
    check_ignore`) — легализация ADR-0013 «вариант A» для файлов,
    занесённых ДО этой задачи (инцидент 03.09, SPEC «Контекст»).

    Плотницкая запись (`artifact_branch.commit_files`, `remove=`) пишет
    прямо в объектную базу `config.ROOT`, не в рабочее дерево — `main`
    этим действием не трогается (AC-5, третья проверка). `done`/`killed`
    задачи пропускаются — их артефактная ветка уже не «живая» (тот же
    фильтр, что `check_branch_freshness`/`check_orphans` уже применяют к
    активным задачам).

    Задача без затронутых файлов — без изменений и без записи в журнал
    (нечего убирать); `git check-ignore` не ответил — тихая деградация,
    та же, что у `checkpoint` (не коммитить вслепую без фильтрации).
    """
    for row in store.all_tasks(conn):
        if row["state"] in ("done", "killed"):
            continue
        task_id = row["id"]
        branch = artifact_branch.branch_name(task_id)
        existing = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
        if not existing:
            continue
        ignored = gitcmd.check_ignore(existing)
        if not ignored:
            continue
        to_remove = sorted(ignored)
        message = (f"{task_id}: уборка игнорируемых файлов артефактной "
                  f"ветки (doctor --fix)")
        commit_sha = artifact_branch.commit_files(task_id, {}, message,
                                                   remove=to_remove)
        if not commit_sha:
            continue
        detail = f"{message} (sha {commit_sha}); убрано: {', '.join(to_remove)}"
        store.journal(conn, task_id, "doctor",
                      "уборка игнорируемых файлов артефактной ветки", detail)
        print(f"  [FIX] {task_id}: убрано {len(to_remove)} игнорируемых "
              f"файлов из артефактной ветки")


# --- наблюдатель роста карты кодовой базы (01M1RFVWV6WWTXRC5F40K61632,
#     требование 3) -------------------------------------------------------

MAP_SIZE_ACTION = "карта: размер"
MAP_GROWTH_SOURCE = "map.growth"

# Sentinel заведомо позже любого реального `ts`/`ack_ts` (формат
# store.now(), лексикографическое сравнение) — использован как cutoff
# `store.alerts_older_than`, чтобы получить ВСЕ алерты существующей
# функцией store, без новой SQL здесь (ADR-0003 3ж): store.py вне зон
# этой задачи, фильтрация target/kind/source/ack_ts — в Python.
_FAR_FUTURE_TS = "9999-12-31 23:59:59Z"


def _all_map_size_steps(conn) -> list:
    """Все записи журнала «карта: размер» по всем задачам, в порядке
    появления (`id` — единый автоинкремент таблицы `steps`, поэтому
    сортировка по нему хронологична и через границы задач). Собрано из
    `store.all_tasks`/`store.task_steps` — существующих функций store,
    без прямой SQL здесь (ADR-0003 3ж)."""
    steps = []
    for task in store.all_tasks(conn):
        steps.extend(store.task_steps(conn, task["id"]))
    steps.sort(key=lambda row: row["id"])
    return [row for row in steps if row["action"] == MAP_SIZE_ACTION]


def _map_growth_reference_point(conn, target: str) -> str | None:
    """Момент последнего подтверждённого алерта `map.growth` этого
    target — `ack` переносит точку отсчёта и тем самым перекалибровывает
    базу (AC-10); подтверждённых алертов нет — начало ряда (`None`)."""
    candidates = [
        row["ack_ts"] for row in store.alerts_older_than(conn, _FAR_FUTURE_TS)
        if row["target"] == target and row["kind"] == "trigger"
        and row["source"] == MAP_GROWTH_SOURCE and row["ack_ts"] is not None
    ]
    return max(candidates) if candidates else None


def _map_growth_series(conn, target: str) -> list:
    """Ряд `detail` (разобранных JSON) записей «карта: размер» этого
    target ПОСЛЕ точки отсчёта, в порядке появления."""
    reference = _map_growth_reference_point(conn, target)
    rows = [row for row in _all_map_size_steps(conn) if row["target"] == target]
    if reference is not None:
        rows = [row for row in rows if row["ts"] > reference]
    return [json.loads(row["detail"]) for row in rows]


def _map_growth_message(compare_from: dict, last: dict) -> str:
    """Текст алерта: каталог верхнего уровня с наибольшим приростом байт
    между сравниваемыми записями и три самые крупные секции текущей
    карты (AC-13) — без времени/id, детерминирован по данным ряда."""
    last_dirs = last["bytes_by_dir"]
    base_dirs = compare_from["bytes_by_dir"]
    grown_dir = max(last_dirs, key=lambda d: last_dirs[d] - base_dirs.get(d, 0))
    top3 = last["top_sections"][:3]
    sections_txt = ", ".join(
        f"{entry['name']} ({entry['bytes']} байт)" for entry in top3)
    return (f"рост карты кодовой базы: сильнее всего вырос каталог "
           f"{grown_dir}; крупнейшие секции карты — {sections_txt}")


def _map_growth_check(conn, target: str) -> Check:
    name = f"map-growth:{target}"
    series = _map_growth_series(conn, target)
    k = config.MAP_GROWTH_CALIBRATION_MERGES
    if len(series) <= k:
        # Ровно на k-й записи окно калибровки (`series[:k]`) совпадает со
        # всем рядом — сравнивать эту запись с базой, посчитанной с её
        # же участием, самоссылочно (R1-F2); молчим ещё один ход, оценка
        # стартует с (k+1)-й записи против уже зафиксированного окна.
        return Check(name, "ok", f"калибровка: {len(series)}/{k} измерений")

    window = series[:k]
    baseline = statistics.median(entry["bytes_total"] for entry in window)
    last = series[-1]
    prev = series[-2] if len(series) >= 2 else None

    creep = last["bytes_total"] > baseline * (1 + config.MAP_GROWTH_RATIO)
    jump = (prev is not None and last["bytes_total"] >
           prev["bytes_total"] * (1 + config.MAP_JUMP_RATIO))
    if not (creep or jump):
        return Check(name, "ok", "рост в пределах нормы")

    compare_from = prev if prev is not None else window[0]
    message = _map_growth_message(compare_from, last)
    alerts.raise_alert(conn, target, "trigger", MAP_GROWTH_SOURCE, message)
    return Check(name, "warn", message)


def check_map_growth(conn) -> list[Check]:
    """Требование 3: по каждому target с хотя бы одной записью «карта:
    размер» — самокалибрующийся относительный порог роста карты
    кодовой базы (AC-8..AC-16). Абсолютный потолок брифа эта проверка не
    читает и не меняет (AC-15) — только относительные сигналы (медиана
    окна калибровки, прирост между соседними записями).
    """
    targets_with_series = sorted({
        row["target"] for row in _all_map_size_steps(conn)
        if row["target"] is not None
    })
    return [_map_growth_check(conn, target) for target in targets_with_series]


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
    checks.append(check_role_home_reference())
    checks.append(check_backup_age(conn))
    checks.append(check_task_counters(conn))
    checks.append(isolation_smoke())
    checks.append(live_smoke(conn))

    try:
        declared = targets.load()
    except targets.TargetsError as exc:
        checks.append(Check("targets-yaml", "fail", str(exc)))
        declared = {}
    for name, entry in declared.items():
        checks.append(check_target_layout(name))
        checks.append(check_target_wrapper(name))
        checks.append(check_remote_empty(name))
        checks.append(check_base_branch(name, entry))
        checks.extend(recovery_check(conn, name))

    checks.extend(check_pending_snapshots(conn))
    checks.extend(check_orphans(conn))
    checks.extend(check_leases(conn))
    checks.extend(check_merge_lock(conn))
    checks.extend(check_hung_test_runs(conn))
    checks.extend(check_zone_waits(conn))
    checks.extend(check_branch_freshness(conn))
    checks.extend(check_artifact_branch_parent_ancestry(conn))
    checks.append(check_root_pin())
    checks.append(check_role_log_pool_leak(conn))
    checks.append(check_canary_pool_drift())
    checks.extend(check_token_repo_scope())
    checks.extend(stack.check_stack())
    checks.extend(check_map_growth(conn))
    return checks


LABELS = {"ok": "ok", "warn": "WARN", "fail": "FAIL", "skip": "skip"}


def cmd_doctor(restore: bool = False, fix: bool = False) -> None:
    """SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требования 3-6: `_orphan_artifact_
    branches(conn)` зовётся РОВНО ОДИН РАЗ за весь прогон (что в режиме
    предпросмотра, что под `--fix`, AC-3) — результат передаётся явно в
    `sweep_orphan_artifact_branches`, чтобы та не переспрашивала origin.

    Origin недоступен (`orphans is None`): без `--fix` — информационная
    строка вместо списка кандидатов (требование 6/AC-7, не FAIL — тем же
    приёмом деградации, что `check_root_pin`); под `--fix` — именованный
    `Check` со статусом `fail` вливается в общий список проверок (тот же
    механизм печати `[FAIL]`/подсчёта провалов/`sys.exit(1)`, что и у
    остальных доктор-проверок) — уборка веток при этом не запускается
    вовсе (требование 5/AC-6). Уборка игнорируемых файлов/мёртвых
    lease-групп/зависших тестов от origin не зависит и продолжает
    работать независимо от исхода сверки веток-сирот.
    """
    conn = store.db()
    if restore:
        print("Recovery-сверка после восстановления .artel/ из бэкапа:")
        # SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3/AC-6: тот же
        # вход восстановления пула, что `catalog.cmd_init()`.
        pool_restore_msg = canary.restore_pool_if_missing(conn)
        if pool_restore_msg:
            print(pool_restore_msg)
    orphans = _orphan_artifact_branches(conn)
    extra_checks = []
    if fix:
        if orphans is None:
            extra_checks.append(Check(
                "orphan-branches-origin", "fail",
                "origin недоступен (git ls-remote --heads origin "
                "'artifact/*' не ответил) — критерий сироты артефактных "
                "веток не вычислим, уборка artifact/*-веток не выполнена"))
        else:
            _print_orphan_branch_candidates(orphans)
            removed = sweep_orphan_artifact_branches(conn, orphans)
            if removed:
                print(f"Осиротевшие артефактные ветки удалены ({len(removed)}):")
                for branch in removed:
                    print(f"  {branch}")
            elif orphans:
                # R1-F3 (ANSWER-3): найдены, но НИ ОДНО удаление не прошло —
                # честно об этом, не «не найдено» (расхождение с журналом
                # алертов, который sweep уже честно ведёт).
                print("Осиротевшие артефактные ветки найдены, но не удалены "
                     "— см. журнал алертов (doctor.cleanup.artifact_branches).")
            else:
                print("Осиротевших артефактных веток не найдено.")
        print("Уборка игнорируемых файлов артефактных веток живых задач:")
        _fix_ignored_artifact_files(conn)
        _fix_dead_lease_groups(conn)
        _fix_hung_test_runs(conn)
    else:
        if orphans is None:
            print("критерий не вычислим без origin")
        else:
            _print_orphan_branch_candidates(orphans)
    checks = extra_checks + all_checks(conn)
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
