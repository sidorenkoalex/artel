"""Пакет orchestrator/doctor -- pre-flight проверки окружения шага.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path
import os

from orchestrator import doctor


# --- окружение шага (требование 2, 5, 9) ------------------------------

def check_cli_found() -> doctor.Check:
    path = doctor.shutil.which("claude")
    if path is None:
        return doctor.Check("cli-found", "fail",
                     "команда claude не найдена в PATH — установи Claude Code CLI")
    return doctor.Check("cli-found", "ok", path)


def cli_version() -> str | None:
    """Установленная версия CLI, разобранная из `claude --version`; None — не определилась."""
    try:
        res = doctor.subprocess.run(["claude", "--version"], capture_output=True,
                             text=True, timeout=10)
    except (OSError, doctor.subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    match = doctor.VERSION_RE.search(res.stdout)
    return match.group(0) if match else None


def check_cli_version() -> doctor.Check:
    version = doctor.cli_version()
    if version is None:
        return doctor.Check("cli-version", "warn",
                     "версия claude CLI не определилась (`claude --version`)")
    if version != doctor.config.CLI_VERSION_PIN:
        return doctor.Check("cli-version", "warn",
                     f"установлена {version}, пин {doctor.config.CLI_VERSION_PIN} — "
                     f"обновление пина (config.CLI_VERSION_PIN) — осознанный "
                     f"шаг Оператора, не автоматика")
    return doctor.Check("cli-version", "ok", version)


def check_token(role: str) -> doctor.Check:
    """Ambient CLAUDE_CODE_OAUTH_TOKEN/ANTHROPIC_API_KEY, иначе keychain-цепочка
    (roles.yaml token_slot/token_fallback, T019) — те же два источника, что
    и `runner.role_env` (setdefault-приоритет ambient), но без вызова самого
    `role_env()`: preflight зовётся на КАЖДОМ шаге, а `role_env()` тянет
    за собой git-идентичность (подпроцесс `git config`) и побочный эффект
    (mkdir ROLE_CONFIG_DIR) ради значения, которое здесь не нужно.
    """
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
        return doctor.Check("token", "ok", "токен уже в окружении (ambient)")
    token = doctor.runner.role_token(role)
    if token:
        return doctor.Check("token", "ok", f"роль {role}: токен добыт из keychain")
    slots = ", ".join(doctor.roles.token_slots(role)) or "нет"
    return doctor.Check("token", "fail",
                 f"роль {role}: токен не найден в keychain (слоты: {slots}) — "
                 f"`claude setup-token`, затем `security add-generic-password "
                 f"-a artel -s <слот> -U`")


def check_git_identity() -> doctor.Check:
    """Итоговый env роли, не сырой `git config`: ambient GIT_AUTHOR_*
    (setdefault-приоритет в `runner.role_env`) тоже закрывает идентичность.

    `role_env()` может поднять `OSError` (курируемый слой не создался —
    тот же класс отказа, что ловит `check_disk_space`/`live_smoke`) —
    не блок здесь: preflight лишь предупреждает, а настоящий отказ шага
    по этой причине остаётся за существующей обработкой в
    `runner.run_agent_once` (`agent run SKIPPED`).
    """
    try:
        env = doctor.runner.role_env()
    except OSError as exc:
        return doctor.Check("git-identity", "warn",
                     f"окружение роли не подготовлено: {exc}")
    missing = [n for n in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL")
              if not env.get(n)]
    if missing:
        return doctor.Check("git-identity", "warn",
                     f"не задано: {', '.join(missing)} — "
                     f"`git config --global user.name/user.email`")
    return doctor.Check("git-identity", "ok", "git-идентичность задана")


def check_disk_space() -> doctor.Check:
    try:
        free_mb = doctor.shutil.disk_usage(doctor.config.ROOT).free / (1024 * 1024)
    except OSError as exc:
        return doctor.Check("disk-space", "fail", f"диск не прочитан: {exc}")
    if free_mb < doctor.config.DOCTOR_MIN_FREE_MB:
        return doctor.Check("disk-space", "fail",
                     f"{free_mb:.0f} МБ свободно — меньше порога "
                     f"{doctor.config.DOCTOR_MIN_FREE_MB} МБ, освободи место")
    return doctor.Check("disk-space", "ok", f"{free_mb:.0f} МБ свободно")


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


def check_role_home_reference() -> doctor.Check:
    """Сверка развёрнутого курируемого слоя роли с референсом — WARN с
    перечнем отличающихся файлов, без автоправки (SPEC
    01M1RDCEF0JZ4AVQRE43JFH8TN, требование 5, AC-13): деплой
    (`catalog._deploy_role_home_reference`) копирует референс только при
    холодном старте, поэтому расхождение, внесённое Оператором вручную
    позже, никак иначе не всплывает.

    И каталог референса, и имя развёрнутого каталога называет провайдер
    исполнителя роли (`home_reference()`, SPEC
    01M2ZNTHSNFYSTF904P6SZTPYF, требование 7): сверка и развёртывание
    обязаны смотреть на одну и ту же пару путей, иначе на втором
    провайдере они разъедутся молча. Провайдер по умолчанию — проверка
    зеро-арг и говорит про развёрнутый слой пульта целиком, не про
    отдельную роль.
    """
    home = doctor.providers.default().home_reference()
    reference = home.reference
    deployed = doctor.config.ROLE_HOME / home.deployed_name
    if not deployed.is_dir():
        return doctor.Check("role-home-reference", "ok",
                     "курируемый слой ещё не развёрнут")
    if not reference.is_dir():
        return doctor.Check("role-home-reference", "ok",
                     "референс отсутствует — сверка невозможна")
    diffs = doctor._role_home_diff(reference, deployed)
    if diffs:
        return doctor.Check("role-home-reference", "warn",
                     f"развёрнутый слой {deployed} отличается от "
                     f"референса: {', '.join(sorted(diffs))}")
    return doctor.Check("role-home-reference", "ok",
                 "развёрнутый слой совпадает с референсом")


def check_target_layout(target: str) -> doctor.Check:
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
    repo = doctor.config.PROJECTS / target / ".git"
    if not repo.is_dir():
        return doctor.Check("target-layout", "warn",
                     f"артефактный репо {target} не инициализирован — "
                     f"`artel.py target-init {target}`")
    return doctor.Check("target-layout", "ok", "артефактный репо на месте")


# Маркеры агентской обвязки target'а (SPEC T069, требование 3; ADR-0003
# п.14 — «агентская обвязка целевого не наследуется»); тот же список
# путей, что и в docstring `runner.role_cwd` про cwd-вектор конфиг-инъекции.
TARGET_WRAPPER_MARKERS = (".claude", ".mcp.json", "CLAUDE.md", "AGENTS.md")


def check_target_wrapper(target: str) -> doctor.Check:
    """Инвентаризация обвязки target'а (SPEC T069, требование 3; A7,
    требование 2, AC-2 — единая логика для ЛЮБОГО объявленного target,
    включая артель): наличие `.claude/`, `.mcp.json`, `CLAUDE.md`/
    `AGENTS.md` в его workspace — информационно, никогда не блокирует.

    Смотрит `workspace/` — то же дерево, что реально видит cwd шага роли
    (`runner.role_cwd`), не артефактный репозиторий `config.PROJECTS/
    <target>` целиком (туда git-первичка A2b коммитит SPEC/PLAN/REVIEW —
    другое дерево, не задето этой проверкой).
    """
    ws = doctor.config.PROJECTS / target / "workspace"
    found = [name for name in doctor.TARGET_WRAPPER_MARKERS if (ws / name).exists()]
    if found:
        return doctor.Check("target-wrapper", "warn",
                     f"обнаружена агентская обвязка target'а {target}: "
                     f"{', '.join(found)} (ADR-0003 п.14)")
    return doctor.Check("target-wrapper", "ok",
                 f"агентская обвязка target'а {target} не обнаружена")


def agent_roles() -> list:
    """Agent-роли, за которые `doctor` отвечает: те же, по которым он
    искал токены до задачи (`config.STATE_ROLE`), отсортированные."""
    return sorted(set(doctor.config.STATE_ROLE.values()))


def _role_chain(role: str, name: str) -> tuple:
    """(текст цепочки роли, причина отказа либо `None`) для строки
    `check_role_providers` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требование
    11, AC-15): «роль → ярус → модель → провайдер» вместо прежнего «роль
    → провайдер».

    Провайдер берётся из уже прочитанной карты исполнителей (`name`), а
    не из разрешения цепочки: имя незарегистрированного провайдера —
    предмет отдельного отказа этой же строки, и оно обязано печататься
    даже тогда, когда ярус роли не разрешается вовсе.
    """
    try:
        resolved = doctor.models.resolve_role(role)
    except doctor.models.ModelsError as exc:
        return f"{role} → (не разрешено) → {name}", f"{role}: {exc}"
    return f"{role} → {resolved.tier} → {resolved.model} → {name}", None


def check_role_providers() -> doctor.Check:
    """Строка «провайдеры ролей: <роль → ярус → модель → провайдер>»
    (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF, требование 6; SPEC
    01M3009Y9AGGY6ZCFA7H1HJ1TD, требование 11) — и красная, если имя
    провайдера какой-нибудь роли не зарегистрировано в реестре
    (требование 4) либо цепочка роли не разрешается (требование 5):
    иначе пульт узнавал бы о незнакомом имени или незаданном ярусе
    только в момент отказа шага.

    Имя печатается из карты исполнителей как есть, без резолва в
    объект: для незарегистрированного имени именно оно и есть предмет
    починки. Нечитаемая карта (или роль, которой в ней нет) — WARN с
    причиной от `roles`, не исключение и не молчаливый `claude`:
    `doctor` — диагностика, ронять её целиком нечитаемым `roles.yaml`
    значило бы спрятать остальные строки (тот же приём, что
    `stack._model_checks`), а подставить дефолт — соврать, что файл
    прочитан (REVIEW.md итерации 1, R1-F2). Отсюда и чтение через
    `providers.role_providers`, который, в отличие от
    `providers.for_role`, до дефолта не деградирует.
    """
    try:
        pairs = doctor.providers.role_providers(agent_roles())
    except doctor.roles.RolesError as exc:
        return doctor.Check("role-providers", "warn",
                     f"провайдеры ролей: {exc}")
    chains, unresolved = [], []
    for role, name in pairs:
        chain, failure = _role_chain(role, name)
        chains.append(chain)
        if failure is not None:
            unresolved.append(failure)
    listed = ", ".join(chains)
    unknown = [(role, name) for role, name in pairs
               if name not in doctor.providers.PROVIDERS]
    if unknown:
        named = "; ".join(f"провайдер {name} роли {role} не зарегистрирован"
                          for role, name in unknown)
        return doctor.Check(
            "role-providers", "fail",
            f"провайдеры ролей: {listed}; {named} "
            f"(известны: {', '.join(sorted(doctor.providers.PROVIDERS))})")
    if unresolved:
        return doctor.Check(
            "role-providers", "fail",
            f"провайдеры ролей: {listed}; цепочка не разрешена — "
            f"{'; '.join(unresolved)}")
    return doctor.Check("role-providers", "ok", f"провайдеры ролей: {listed}")


def provider_preflight_checks() -> dict:
    """{имя проверки: [проверки]} — `preflight()` провайдера КАЖДОЙ
    agent-роли, склеенный без дублей (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF,
    требование 6, AC-9).

    Проверки, не зависящие от роли (CLI найден, версия CLI, дом роли),
    у одного провайдера выходят одинаковыми — одинаковые отбрасываются,
    и в выводе `doctor` каждая остаётся одна, как до задачи. Проверка
    секрета у каждой роли своя и остаётся по одной на роль. Роль с
    незарегистрированным провайдером пропускается молча: про неё
    говорит красная строка `check_role_providers` выше, дублировать её
    здесь нечем — провайдера, который выполнил бы проверки, нет.
    """
    grouped = {}
    for role in agent_roles():
        try:
            provider = doctor.providers.for_role(role)
        except doctor.providers.UnknownProviderError:
            continue
        for check in provider.preflight(role):
            bucket = grouped.setdefault(check.name, [])
            if check not in bucket:
                bucket.append(check)
    return grouped


def preflight_checks(role: str, target: str) -> list[doctor.Check]:
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

    Проверки исполнителя (CLI, секрет, версия) спрашиваются у провайдера
    роли поимённо, а не списком `preflight()` (SPEC
    01M2ZNTHSNFYSTF904P6SZTPYF, требование 6): порядок здесь свой —
    провайдерские проверки перемежаются общими (диск, layout target'а),
    и блокирующие стоят до дорогих. Сверка дома роли в набор шага не
    входит и здесь: она часть `doctor`, а не предполёта каждого запуска
    (иначе шаг платил бы обходом дерева референса на каждом старте).
    """
    try:
        provider = doctor.providers.for_role(role)
    except doctor.providers.UnknownProviderError as exc:
        # Сюда предполёт доходит только в обход `runner._refuse_before_
        # start` (тот отказывает раньше, требование 4) — но молчать об
        # этом здесь всё равно нельзя: блокирующий провал с тем же
        # именованным текстом.
        return [doctor.Check("role-providers", "fail", str(exc))]
    checks = [provider.check_cli_found()]
    checks.append(provider.check_token(role))
    checks.append(doctor.check_disk_space())
    checks.append(doctor.check_target_layout(target))
    if any(c.status == "fail" for c in checks):
        return checks
    checks.append(doctor.check_git_identity())
    checks.append(provider.check_cli_version())
    return checks


