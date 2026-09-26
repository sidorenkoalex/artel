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


# --- проверки провайдера `codex` (SPEC 01M32NH6P053978AER66P0X4GN,
#     требование 12) ---------------------------------------------------
#
# Тела живут здесь, как и тела проверок `claude` выше: провайдер
# объявляет СОСТАВ и ПОРЯДОК своего предполёта, а не переписывает
# механику заново (докстринг `providers/base.py`). Имена строк —
# собственные, не совпадающие с именами одноимённых проверок Claude:
# склейка `provider_preflight_checks` отбрасывает одинаковые записи, и
# под общим именем отсутствие ключа Codex исчезло бы за зелёной строкой
# Claude (AC-16).

def codex_cli_version() -> str | None:
    """Установленная версия `codex`, разобранная из `codex --version`;
    `None` — не определилась. Отдельно от `cli_version()` выше: тот
    спрашивает `claude` литералом."""
    try:
        res = doctor.subprocess.run(list(doctor.codex_provider.CLI_VERSION_COMMAND),
                                    capture_output=True, text=True, timeout=10)
    except (OSError, doctor.subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    match = doctor.VERSION_RE.search(res.stdout)
    return match.group(0) if match else None


def check_codex_cli_found() -> doctor.Check:
    """CLI `codex` найден — блокирующая. Отсутствие останавливает шаг
    роли, ИДУЩЕЙ на Codex; пульт без Codex до этой проверки не доходит
    вовсе (её отдаёт только `CodexProvider.preflight`)."""
    path = doctor.shutil.which(doctor.codex_provider.CLI_NAME)
    if path is None:
        return doctor.Check(
            "codex-cli-found", "fail",
            f"команда {doctor.codex_provider.CLI_NAME} не найдена в PATH — "
            f"установи Codex CLI ≥ "
            f"{doctor.stack.version_text(doctor.codex_provider.CLI_MINIMUM)}")
    return doctor.Check("codex-cli-found", "ok", path)


def check_codex_cli_version() -> doctor.Check:
    """Версия `codex` не ниже минимума провайдера — предупреждение, не
    блок (требование 12): сверка идёт с минимумом самого CLI, а не с
    пином (у Codex пина нет — на него не переведена ни одна роль)."""
    minimum = doctor.stack.version_text(doctor.codex_provider.CLI_MINIMUM)
    version = doctor.codex_cli_version()
    if version is None:
        return doctor.Check(
            "codex-cli-version", "warn",
            f"версия codex CLI не определилась (`codex --version`) — "
            f"минимум {minimum}")
    if tuple(int(part) for part in version.split(".")) < \
            doctor.codex_provider.CLI_MINIMUM:
        return doctor.Check(
            "codex-cli-version", "warn",
            f"установлена {version}, минимум {minimum} — обнови Codex CLI")
    return doctor.Check("codex-cli-version", "ok",
                        f"{version} ≥ {minimum}")


CODEX_AUTH_CHECK = "codex-chatgpt-auth"

# Оба однократных шага Оператора одной строкой — она приписывается к
# КАЖДОМУ исходу отказа, не только к «вход не выполнен»: истёкший таймаут и
# незапустившийся CLI тоже оставляют Оператора без авторизованной роли, и
# отказ без рецепта в этих исходах был бы тем же дефектом.
#
# Указатель связки ключей — не теория: живой вход 22.09
# (`docs/research/codex-live-check-2026-09-22.md`) в изолированном `HOME`
# без него не сохранился вовсе (`persist_failed`), то есть Оператор прошёл
# бы OAuth и получил ту же красную строку. Ставит указатель Оператор
# руками — пульт этого не делает (`docs/stack.md`, раздел «Провайдер
# codex»).
CODEX_AUTH_RECIPE = (
    "два однократных шага Оператора: (1) указать дому роли связку ключей "
    "— `security default-keychain -d user -s <путь связки>` с HOME "
    "курируемого дома роли, иначе вход не сохранится; (2) войти — "
    "`codex login` с тем же HOME/CODEX_HOME. Остаток лимита подписки эта "
    "строка не доказывает"
)


def check_codex_chatgpt_auth(role: str) -> doctor.Check:
    """Подписочный вход ChatGPT для роли — блокирующая строка на месте
    прежней проверки ключа API (требование 4, AC-6..AC-10).

    Спрашивает сам CLI (`codex login status`) с окружением курируемого дома
    роли и с теми же двумя переопределениями авторизации, что несёт команда
    шага (`codex_provider.AUTH_OVERRIDES`): без дома роли CLI ответил бы про
    ЛИЧНЫЙ вход Оператора, без переопределений — про способ авторизации,
    отличный от того, каким пойдёт шаг. Прежняя проверка смотрела только
    наличие ключа в слоте keychain и авторизацию не доказывала вовсе —
    `codex exec` читает ключ из другой переменной (живая проверка 22.09).

    `ok` — только код выхода 0 И подтверждённый вход ChatGPT: тем же нулём
    CLI отвечает и на «не вошёл», и на вход ключом API (тот самый ключ без
    баланса, с которым 22.09 живой запуск получил 401).

    Вывод CLI не попадает в `detail` ни в одном исходе: `codex login status`
    печатает адрес связки ключей и состояние авторизации — сведения, которым
    нечего делать в логе `doctor`. Вместо них отказ несёт рецепт.

    Вызов ограничен таймаутом, а истёкший таймаут и незапустившийся CLI
    дают `fail` с названной причиной, а не исключение наружу: точка вызова —
    предполёт шага и прогон диагностики, оба обязаны назвать причину, а не
    упасть трейсбеком (тот же приём, что у `codex_cli_version` выше).
    """
    provider = doctor.providers.get(doctor.codex_provider.CLI_NAME)
    timeout = doctor.codex_provider.LOGIN_STATUS_TIMEOUT_SEC
    try:
        cmd = provider.login_status_command()
        env = provider.environment(role)
    except (OSError, KeyError) as exc:
        return doctor.Check(
            CODEX_AUTH_CHECK, "fail",
            f"роль {role}: вызов `codex login status` не собран ({exc}) — "
            f"{CODEX_AUTH_RECIPE}")
    try:
        res = doctor.subprocess.run(cmd, capture_output=True, text=True,
                                    env=env, timeout=timeout)
    except doctor.subprocess.TimeoutExpired:
        return doctor.Check(
            CODEX_AUTH_CHECK, "fail",
            f"роль {role}: `codex login status` не ответил за {timeout} с — "
            f"{CODEX_AUTH_RECIPE}")
    except OSError as exc:
        return doctor.Check(
            CODEX_AUTH_CHECK, "fail",
            f"роль {role}: `codex login status` не запустился ({exc}) — "
            f"{CODEX_AUTH_RECIPE}")
    if res.returncode != 0:
        return doctor.Check(
            CODEX_AUTH_CHECK, "fail",
            f"роль {role}: `codex login status` ответил кодом "
            f"{res.returncode} (вывод CLI не печатается) — {CODEX_AUTH_RECIPE}")
    output = " ".join((res.stdout or "").lower().split())
    if not doctor.codex_provider.CHATGPT_LOGIN_RE.search(output):
        return doctor.Check(
            CODEX_AUTH_CHECK, "fail",
            f"роль {role}: код выхода 0, но вход ChatGPT не подтверждён — "
            f"дом роли либо не вошёл, либо вошёл ключом API (вывод CLI не "
            f"печатается). {CODEX_AUTH_RECIPE}")
    return doctor.Check(
        CODEX_AUTH_CHECK, "ok",
        f"роль {role}: вход ChatGPT подтверждён для курируемого дома "
        f"{env.get(doctor.codex_provider.HOME_ENV)} (остаток лимита подписки "
        f"не проверяется)")


def check_codex_role_home() -> doctor.Check:
    """Сверка развёрнутого дома роли `codex` с его референсом — та же
    механика, что у провайдера по умолчанию, своя строка (требование 5:
    сверка обязана учитывать ВСЕХ провайдеров реестра, а до этой задачи
    смотрела только на провайдера по умолчанию)."""
    return _provider_home_check("codex-role-home",
                                doctor.providers.get("codex"))


def model_provider_mismatches(role: str | None = None) -> list:
    """[(роль, провайдер роли, провайдер её модели, модель)] — роли, у
    которых ИСПОЛНИТЕЛЬ шага и провайдер разрешившейся модели разные
    (REVIEW.md итерации 1, R1-F1).

    Исполнителя шага выбирает поле `provider:` роли в `roles.yaml`
    (`providers.for_role`, `runner._spawn_and_wait`), а тариф, минимум
    версии CLI и сам идентификатор модели приходят из цепочки «роль →
    ярус → модель → провайдер». Совпадать эти две половины обязаны:
    иначе шаг уходит в CLI одного провайдера с идентификатором модели
    другого — оплаченная попытка, отказ от чужого CLI и расход, учтённый
    по чужому тарифу.

    `role` задан — предмет только эта роль (предполёт конкретного шага);
    `None` — все agent-роли (строка `doctor`).

    Нечитаемая карта исполнителей и неразрешимая цепочка дают ПУСТОЙ
    список, а не исключение: о них говорят собственные именованные
    отказы (`check_role_providers`, `runner._refuse_before_start`), и
    подменять их здесь трейсбеком предполёта незачем — тот же приём
    защитной деградации, что у `stack.model_providers`.
    """
    names = [role] if role is not None else agent_roles()
    try:
        pairs = doctor.providers.role_providers(names)
    except doctor.roles.RolesError:
        return []
    catalog, local = doctor.models.layers_or_none()
    found = []
    for name, provider_name in pairs:
        try:
            resolved = doctor.models.resolve_role(name, catalog, local)
        except doctor.models.ModelsError:
            continue
        if resolved.provider != provider_name:
            found.append((name, provider_name, resolved.provider,
                          resolved.model))
    return found


def check_model_provider_cli(role: str | None = None) -> doctor.Check:
    """CLI провайдеров, в модели которых разрешаются ярусы agent-ролей,
    найдены И провайдер роли не разошёлся с провайдером её модели —
    блокирующая проверка предполёта (SPEC 01M32NH6P053978AER66P0X4GN,
    требование 6, AC-13).

    Смотрит только НЕОБЯЗАТЕЛЬНУЮ часть манифеста: обязательные
    инструменты закрыты `check_cli_found` провайдера и резолвом
    `runner._resolve_declared_tools`. Без этой строки отсутствие
    востребованного CLI всплывало бы `OSError`'ом внутри
    `check_git_identity` — причина верная, но исход шага не назван, и
    Оператор читал бы жёлтую строку про «окружение роли» вместо отказа.

    Вторая половина — расхождение «провайдер роли ≠ провайдер её модели»
    (REVIEW.md итерации 1, R1-F1): исполнителя шага выбирает поле
    `provider:` роли, а идентификатор модели и тариф приходят из
    цепочки яруса, и разойтись им нельзя. До появления раздела `codex` в
    каталоге такая пара останавливалась сама («модель вне каталога» —
    `catalog_model` не находил идентификатор чужого вендора), а с
    появлением раздела этот отказ исчез: шаг ушёл бы в
    `claude --model gpt-…` — оплаченная попытка, отказ от чужого CLI и
    расход по тарифу чужого вендора.

    Обе половины называются ОДНОЙ строкой и в этом порядке: отсутствие
    CLI — то, что чинится установкой, и оно же единственная причина,
    по которой шаг не стартует на пульте БЕЗ второго CLI; расхождение —
    то, что чинится правкой двух файлов. Когда верны оба (ярус переведён,
    а `roles.yaml` нет, и CLI не поставлен), Оператор обязан прочитать
    оба факта, а не чинить их по очереди двумя прогонами.

    Ненайденный CLI перечисляется по ВСЕМ ролям (`role` в этой половине
    не участвует): резолв объявленных инструментов
    (`runner._resolve_declared_tools`) идёт по всему манифесту, и шаг
    любой роли отказывает на отсутствующем инструменте любой другой.
    Расхождение, наоборот, предмет конкретной роли — по ней предполёт
    шага её и спрашивает.

    Стоит в блокирующей группе и не заводит ни одного подпроцесса
    (`shutil.which` + чтение файлов слоёв): `preflight_checks` платит за
    строки только до первого провала, а тесты требуют от провального
    предполёта вообще ни одного subprocess-вызова.
    """
    demanded = doctor.stack.demanded_optional_tools()
    missing = [name for name in demanded
               if doctor.shutil.which(name) is None]
    failures = []
    if missing:
        failures.append(
            f"объявленный инструмент не найден в PATH/системе: "
            f"{', '.join(missing)} — ярус agent-роли разрешается в модель "
            f"его провайдера; установи CLI либо смени модель яруса в "
            f"{doctor.config.MODELS_LOCAL}")
    mismatched = doctor.model_provider_mismatches(role)
    if mismatched:
        named = "; ".join(
            f"роль {name}: исполнитель шага — {own}, но ярус разрешается "
            f"в модель {model} провайдера {model_provider}"
            for name, own, model_provider, model in mismatched)
        failures.append(
            f"провайдер роли и провайдер её модели разошлись — {named}: "
            f"шаг ушёл бы чужим CLI с идентификатором чужой модели; "
            f"приведи в соответствие ярус в {doctor.config.MODELS_LOCAL} "
            f"либо поле `provider:` роли в roles.yaml (путь защищённый — "
            f"меняет Оператор отдельным MR)")
    if failures:
        return doctor.Check("model-provider-cli", "fail",
                            "; ".join(failures))
    if not demanded:
        return doctor.Check(
            "model-provider-cli", "ok",
            "ни один ярус agent-роли не разрешается в модель стороннего "
            "провайдера — сторонних CLI пульту не нужно; провайдер роли и "
            "провайдер её модели совпадают")
    return doctor.Check("model-provider-cli", "ok",
                        f"CLI провайдеров моделей ролей на месте: "
                        f"{', '.join(sorted(demanded))}; провайдер роли и "
                        f"провайдер её модели совпадают")


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


def _provider_home_check(name: str, provider) -> doctor.Check:
    """Сверка развёрнутого курируемого дома ОДНОГО провайдера с его
    референсом — общая механика для всех провайдеров реестра (SPEC
    01M32NH6P053978AER66P0X4GN, требование 5).

    Тело выделено из `check_role_home_reference` без единой правки
    поведения: до этой задачи сверка существовала в одном экземпляре и
    смотрела только на провайдера по умолчанию, так что расхождение
    второго дома (`.artel/home/.codex/`) никто бы не заметил.
    """
    home = provider.home_reference()
    reference = home.reference
    deployed = doctor.config.ROLE_HOME / home.deployed_name
    if not deployed.is_dir():
        return doctor.Check(name, "ok", "курируемый слой ещё не развёрнут")
    if not reference.is_dir():
        return doctor.Check(name, "ok",
                     "референс отсутствует — сверка невозможна")
    diffs = doctor._role_home_diff(reference, deployed)
    if diffs:
        return doctor.Check(name, "warn",
                     f"развёрнутый слой {deployed} отличается от "
                     f"референса: {', '.join(sorted(diffs))}")
    return doctor.Check(name, "ok",
                 "развёрнутый слой совпадает с референсом")


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

    Дома ОСТАЛЬНЫХ провайдеров реестра сверяются их собственными
    строками (`CodexProvider.check_home_reference`, SPEC
    01M32NH6P053978AER66P0X4GN, требование 5) — не этой: у неё своё имя,
    и склейка `provider_preflight_checks` схлопнула бы расхождения двух
    разных домов в одну запись.
    """
    return _provider_home_check("role-home-reference",
                                doctor.providers.default())


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


def _role_chain(role: str, name: str, catalog=None, local=None) -> tuple:
    """(текст цепочки роли, причина отказа либо `None`) для строки
    `check_role_providers` (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требование
    11, AC-15): «роль → ярус → модель → провайдер» вместо прежнего «роль
    → провайдер».

    Провайдер берётся из уже прочитанной карты исполнителей (`name`), а
    не из разрешения цепочки: имя незарегистрированного провайдера —
    предмет отдельного отказа этой же строки, и оно обязано печататься
    даже тогда, когда ярус роли не разрешается вовсе.

    `catalog`/`local` — слои, прочитанные вызывающим один раз на весь
    перебор ролей (REVIEW итерации 1, R1-F3); `None` в любом из них
    означает «читай сам», и отказ по роли остаётся тем же.
    """
    try:
        resolved = doctor.models.resolve_role(role, catalog, local)
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
    catalog, local = doctor.models.layers_or_none()
    chains, unresolved = [], []
    for role, name in pairs:
        chain, failure = _role_chain(role, name, catalog, local)
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
    # CLI провайдера МОДЕЛИ шага (SPEC 01M32NH6P053978AER66P0X4GN,
    # требование 6): провайдер роли и провайдер её модели совпадают не
    # всегда — ярус роли с `provider: claude` вправе разрешаться в
    # модель Codex, и тогда шаг обязан остановиться до старта агента с
    # причиной, называющей ненайденный инструмент, а не платить попыткой.
    # Роль передаётся явно (REVIEW.md итерации 1, R1-F1): расхождение
    # «исполнитель шага ≠ провайдер модели» — предмет КОНКРЕТНОГО шага, и
    # останавливать им чужие роли не за что.
    checks.append(doctor.check_model_provider_cli(role))
    checks.append(provider.check_token(role))
    checks.append(doctor.check_disk_space())
    checks.append(doctor.check_target_layout(target))
    if any(c.status == "fail" for c in checks):
        return checks
    checks.append(doctor.check_git_identity())
    checks.append(provider.check_cli_version())
    return checks


