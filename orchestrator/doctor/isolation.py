"""Пакет orchestrator/doctor -- офлайн-смоук изоляции project-/user-слоя.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path
import os
import tempfile

from orchestrator import doctor


# --- смоук изоляции (требование 6) -------------------------------------

def isolation_smoke(role: str = "developer") -> doctor.Check:
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
    сборка cmd, а не только константа). И argv, и окружение приходят от
    провайдера исполнителя роли (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF,
    требование 6): `role_cmd()`/`role_env()` — общие точки runner, за
    которыми стоит `providers.for_role(...)`, поэтому смок сверяет
    изоляцию того CLI, который реально запустит шаг, а не литерала. Живая дискриминирующая проверка
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
            doctor.ISOLATION_MARKER, encoding="utf-8")
        os.environ["HOME"] = fake_home
        try:
            env = doctor.runner.role_env(role)
        except (OSError, doctor.providers.UnknownProviderError) as exc:
            # Тот же класс отказа, что уже ловят `check_git_identity`/
            # `_live_smoke_run` (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN, AC-6):
            # объявленный инструмент манифеста не найден — не повод
            # уронить весь `doctor` необработанным исключением. То же
            # самое для незарегистрированного провайдера роли (SPEC
            # 01M2ZNTHSNFYSTF904P6SZTPYF, требование 4): про него
            # говорит именованная красная строка `check_role_providers`,
            # а `doctor` обязан дойти до остальных проверок.
            return doctor.Check("isolation-smoke", "fail",
                        f"окружение роли не подготовлено: {exc}")
        finally:
            if prior_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prior_home
    if env.get("HOME") == fake_home or any(
            doctor.ISOLATION_MARKER in str(v) for v in env.values()):
        leaks.append("user-слой: HOME роли не отведён от ambient-значения")

    project_dir = doctor.runner.role_cwd(None, None, doctor.ISOLATION_SMOKE_TARGET)
    try:
        (project_dir / "CLAUDE.md").write_text(doctor.ISOLATION_MARKER, encoding="utf-8")
        try:
            skill_names = doctor.roles.skills(role)
            prompt_text = "\n\n".join(
                (doctor.config.ROOT / "skills" / f"{s}.md").read_text(encoding="utf-8")
                for s in skill_names)
        except (doctor.roles.RolesError, OSError, UnicodeDecodeError) as exc:
            return doctor.Check("isolation-smoke", "fail",
                        f"промпт роли не собран для проверки: {exc}")
        if doctor.ISOLATION_MARKER in prompt_text:
            leaks.append("project-слой: маркер CLAUDE.md рабочего каталога "
                        "просочился в промпт роли")
    finally:
        doctor.shutil.rmtree(doctor.config.PROJECTS / doctor.ISOLATION_SMOKE_TARGET, ignore_errors=True)

    excluded_sources = {"project", "local"}
    active_sources = {s.strip() for s in doctor.config.AGENT_SETTING_SOURCES.split(",")}
    if active_sources & excluded_sources:
        leaks.append("project-хук: --setting-sources шага роли не "
                    f"исключает {sorted(active_sources & excluded_sources)} "
                    "— project-/local-слой клиентских настроек "
                    "(включая хуки) достижим шагом роли")

    cmd = doctor.runner.role_cmd()
    if "--strict-mcp-config" not in cmd:
        leaks.append("MCP-вектор: --strict-mcp-config отсутствует в "
                    "команде запуска шага роли — .mcp.json рабочего "
                    "каталога достижим шагом")

    if leaks:
        return doctor.Check("isolation-smoke", "fail", "; ".join(leaks))
    return doctor.Check("isolation-smoke", "ok",
                 "маркеры project-/user-слоя не достигли env/промпта роли, "
                 "project-/local-хуки исключены из resolve-сурсов шага, "
                 "MCP-конфиг рабочего каталога изолирован "
                 "(--strict-mcp-config)")


# --- офлайн-смок изоляции провайдера `codex` (SPEC
#     01M32NH6P053978AER66P0X4GN, требование 12) -----------------------

CODEX_SMOKE_CHECK = "codex-isolation-smoke"


def provider_isolation_smokes() -> list:
    """Смоки изоляции провайдеров реестра, у которых он СВОЙ (`isolation_
    smoke()` вернул `Check`, а не `None`) — вход `doctor.all_checks`.

    Перебор по реестру, а не поимённый вызов: следующий провайдер со
    своей изоляцией попадёт в вывод `doctor` записью в реестр, без
    правки списка проверок.
    """
    checks = []
    for provider in doctor.providers.PROVIDERS.values():
        check = provider.isolation_smoke()
        if check is not None:
            checks.append(check)
    return checks


def codex_isolation_smoke(role: str = "developer") -> doctor.Check:
    """Изоляция шага роли на `codex` — БЕЗ запуска CLI и без сети.

    Сверяется РЕАЛЬНО собранная команда шага и РЕАЛЬНО собранное
    окружение (`CodexProvider.command()`/`environment()`), а не
    собственная копия списка флагов рядом с проверкой: копия не заметила
    бы флага, выломанного из сборки, и Оператор читал бы зелёную строку
    про изоляцию, которой у шага уже нет.

    Пять пунктов, каждый называется в тексте провала поимённо:
    песочница `workspace-write`, выключение сети песочницы, выключение
    КАЖДОЙ из одиннадцати функций 0.155.1, ambient-значения `HOME`/
    `CODEX_HOME`, не отведённые от окружения Оператора, и любое из имён
    ключа API в СОБРАННОМ окружении шага (`codex_provider.
    FORBIDDEN_KEY_ENV_NAMES`): роль авторизуется входом по подписке, и
    ключ, вернувшийся в окружение любым из трёх имён, — регресс
    требования 2, а не вариант настройки. Собранное — значит оба канала
    сразу (`_assembled_step_env`): накладка провайдера и общий белый
    список манифеста, которым ключ приезжает в шаг мимо провайдера.

    Чужие секреты (токен подписки Claude), заданные Оператором ambient и
    стоящие в ОБЩЕМ белом списке манифеста, — отдельная ЖЁЛТАЯ строка, а
    не молчание. Предмет её — состояние машины Оператора: в СОБРАННОЕ
    окружение шага такой секрет больше не попадает (сужение по провайдеру,
    SPEC 01M3F7BYE82S9AQCBSP1RTQQTR, требование 4), и про собранное
    окружение отвечает отказом отдельная строка
    `foreign-provider-secrets`. Своим и чужим секрет называет реестр
    (`secret_env_names()` провайдеров), не литерал.

    Инструмент `codex` может вовсе не входить в сегодняшний манифест
    (пульт без Codex, ни один ярус на его модели не указывает) — тогда
    сборка argv отказывает резолвом, и смок честно отдаёт `skip`:
    краснеть на отсутствие того, чем никто не пользуется, `doctor` не
    вправе.
    """
    provider = doctor.providers.get(doctor.codex_provider.CLI_NAME)
    try:
        cmd = provider.command()
    except (OSError, KeyError) as exc:
        return doctor.Check(
            CODEX_SMOKE_CHECK, "skip",
            f"команда шага не собрана ({exc}) — инструмент {doctor.codex_provider.CLI_NAME} "
            f"не объявлен сегодняшним манифестом, изоляция не сверяется")

    leaks = []
    if not _carries_value(cmd, doctor.codex_provider.SANDBOX_MODE):
        leaks.append(f"песочница: в команде шага нет "
                     f"{doctor.codex_provider.SANDBOX_MODE}")
    network = f"{doctor.codex_provider.NETWORK_ACCESS_KEY}=" \
              f"{doctor.codex_provider.NETWORK_ACCESS_VALUE}"
    if not _carries_value(cmd, network):
        leaks.append(f"сеть песочницы: в команде шага нет -c {network}")
    for feature in doctor.codex_provider.DISABLED_FEATURES:
        if not _carries_flag_value(cmd, "--disable", feature):
            leaks.append(f"функция {feature}: в команде шага нет "
                         f"--disable {feature}")

    env, env_leaks = _codex_environment_leaks(provider, role)
    if env is None:
        return doctor.Check(CODEX_SMOKE_CHECK, "fail", env_leaks)
    leaks.extend(env_leaks)

    if leaks:
        return doctor.Check(CODEX_SMOKE_CHECK, "fail", "; ".join(leaks))

    foreign = _foreign_provider_secrets(provider)
    if foreign:
        return doctor.Check(
            CODEX_SMOKE_CHECK, "warn",
            f"изоляция команды и дома роли сошлась, но в окружении шага "
            f"остаётся секрет другого провайдера: {', '.join(foreign)} — "
            f"общий белый список манифеста копирует его любому шагу "
            f"(сужение списка по провайдеру — отдельная задача)")
    return doctor.Check(
        CODEX_SMOKE_CHECK, "ok",
        f"команда шага несёт песочницу {doctor.codex_provider.SANDBOX_MODE}, "
        f"выключенную сеть и выключение всех "
        f"{len(doctor.codex_provider.DISABLED_FEATURES)} функций; окружение несёт "
        f"CODEX_HOME на курируемый дом, не наследует ambient HOME/CODEX_HOME "
        f"и не несёт ни одного имени ключа API")


def _carries_value(cmd, value: str) -> bool:
    """Команда несёт `value` отдельным элементом или хвостом через `=`:
    написание флага — дело провайдера, предмет проверки — значение."""
    return any(item == value or item.endswith(f"={value}") for item in cmd)


def _carries_flag_value(cmd, flag: str, value: str) -> bool:
    """Команда несёт пару `flag value` — раздельно, через `=` или
    слитно."""
    pairs = [(cmd[i], cmd[i + 1]) for i in range(len(cmd) - 1)]
    return ((flag, value) in pairs or f"{flag}={value}" in cmd
            or f"{flag}{value}" in cmd)


def _codex_environment_leaks(provider, role: str):
    """(окружение провайдера, список утечек) либо `(None, текст отказа)`.

    Ambient `HOME`/`CODEX_HOME` подменяются ВРЕМЕННЫМ каталогом-маркером
    (не реальным домом Оператора — офлайн-смок им не пользуется вовсе), и
    проверяется, что собранное окружение этот маркер не унаследовало:
    провайдер обязан переписывать обе переменные всегда, а не
    `setdefault`-ом.
    """
    marker_names = ("HOME", doctor.codex_provider.HOME_ENV)
    prior = {name: os.environ.get(name) for name in marker_names}
    with tempfile.TemporaryDirectory() as fake_home:
        for name in marker_names:
            os.environ[name] = fake_home
        try:
            env = provider.environment(role)
        except OSError as exc:
            return None, f"окружение роли не подготовлено: {exc}"
        finally:
            for name, value in prior.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
    leaks = [f"{name}: окружение шага унаследовало ambient-значение "
             f"Оператора" for name in marker_names
             if env.get(name) == fake_home]
    deployed = str(doctor.config.ROLE_HOME / doctor.codex_provider.DEPLOYED_HOME_DIR)
    if env.get(doctor.codex_provider.HOME_ENV) != deployed:
        leaks.append(f"{doctor.codex_provider.HOME_ENV}: окружение шага не указывает "
                     f"на курируемый дом {deployed}")
    # Ключ API в СОБРАННОМ окружении шага — провал по ИМЕНИ переменной, без
    # значения: роль авторизуется входом по подписке, и наличие ключа
    # означает, что канал, убранный требованием 2, вернулся. Перебираются
    # все три имени, а не одно: `codex exec` читает ключ из `CODEX_API_KEY`
    # (живая проверка 22.09), и проверка на `OPENAI_API_KEY` пропустила бы
    # именно действующий канал.
    step_env = _assembled_step_env(env)
    for name in doctor.codex_provider.FORBIDDEN_KEY_ENV_NAMES:
        if name not in step_env:
            continue
        channel = ("накладка провайдера" if name in env
                   else "общий белый список манифеста")
        leaks.append(f"{name}: в собранном окружении шага лежит ключ API "
                     f"(значение не читается; канал — {channel}) — роль "
                     f"авторизуется входом по подписке ChatGPT")
    return env, leaks


def _assembled_step_env(overlay: dict) -> dict:
    """Окружение шага так, как его соберёт `runner.role_env`: ambient,
    суженный общим белым списком манифеста, плюс накладка провайдера.

    Накладка провайдера — не единственный канал переменной в шаг, и после
    требования 3 не главный: ключ, дописанный в `stack.ROLE_ENV_ALLOWLIST`
    (своей задачей или «по аналогии»), приезжает в окружение КАЖДОГО шага
    мимо провайдера — смок, смотревший только накладку, оставался бы
    зелёным ровно в том сценарии, ради которого заведён (REVIEW.md
    итерации 1, R1-F2).

    Белый список применяется ЕДИНСТВЕННЫМ его определением
    (`runner._allowlisted_env`), а не своей копией правила рядом: копия
    учитывала бы сегодняшние префиксы и молча разъехалась бы с раннером на
    первой же правке — тот же класс расхождения половин, что эта задача
    закрывает у пар авторизации. Сам `runner.role_env` не зовётся: он
    собирает окружение провайдера РОЛИ (роли на Codex сегодня нет ни
    одной), резолвит инструменты манифеста и venv — смок сверяет изоляцию
    шага Codex, а не готовность пульта.
    """
    env = doctor.runner._allowlisted_env(os.environ)
    env.update(overlay)
    return env


FOREIGN_SECRETS_CHECK = "foreign-provider-secrets"


def check_foreign_provider_secrets() -> doctor.Check:
    """Секреты ЧУЖИХ провайдеров в СОБРАННОМ окружении шага — по одной
    строке на весь `doctor`, симметрично жёлтой строке смока Codex
    (REVIEW.md итерации 1, R1-F4).

    Белый список манифеста (`stack.ROLE_ENV_ALLOWLIST`) общий на пульт, а
    не свой у каждого провайдера: секрет, заданный Оператором для одного
    исполнителя, разрешён к копированию в окружение КАЖДОГО шага — в том
    числе шага роли на ЧУЖОМ провайдере (требование 12, AC-18). Сужение по
    провайдеру шага заведено требованием 4 SPEC
    01M3F7BYE82S9AQCBSP1RTQQTR и живёт в `runner.role_env`; эта строка
    сверяет, что оно ДЕЙСТВУЕТ. Отдельной строкой, потому что у провайдера
    по умолчанию своего смока нет, а общий `isolation_smoke` про секреты
    других провайдеров не знает.

    Отказ, а не предупреждение (SPEC 01M3F7BYE82S9AQCBSP1RTQQTR,
    требование 5): до сужения краснеть было не на что — пульт не умел
    иначе, и красная строка горела бы навсегда. Теперь чужой секрет в
    окружении шага означает, что сужение разъехалось с реестром (провайдер
    объявил секрет, а сборка окружения о нём не знает), — состояние,
    которое чинится кодом, а не терпится.

    Предмет — именно СОБРАННОЕ окружение (`runner.role_env`), не ambient и
    не белый список: ambient-переменная Оператора сама по себе ничего о
    шаге не говорит после сужения, и строка, красневшая по ней, осталась бы
    красной на пульте, где утечки уже нет. Значения переменных не читаются
    и не печатаются — только имена.

    Окружение не собралось (`OSError`: объявленный инструмент манифеста не
    найден, venv не согласован) — `warn` «сверка не проведена», тем же
    приёмом, что `check_canary_trigger` при недоступном origin: `skip`
    читался бы как норма, а `fail` называл бы утечкой то, чего не
    проверяли, — про сам отказ сборки говорят предполёт и `isolation-smoke`.
    """
    # Один вызов сборки на РАЗЛИЧНЫЙ провайдер: `role_env` резолвит
    # инструменты манифеста, сверяет venv и спрашивает keychain — платить
    # этим за каждую из agent-ролей, идущих на одном и том же исполнителе,
    # незачем, набор чужих имён у них один и тот же.
    by_provider = {}
    for role in doctor.agent_roles():
        try:
            provider = doctor.providers.for_role(role)
        except doctor.providers.UnknownProviderError:
            # Про незарегистрированного провайдера роли говорит красная
            # строка `check_role_providers` — дублировать её нечем.
            continue
        by_provider.setdefault(provider.name, (role, provider))

    found, unassembled = [], []
    for name in sorted(by_provider):
        role, provider = by_provider[name]
        try:
            step_env = doctor.runner.role_env(role)
        except OSError as exc:
            unassembled.append(f"{role} ({name}): {exc}")
            continue
        leaked = sorted(n for n in doctor.runner.foreign_secret_env_names(provider)
                        if n in step_env)
        if leaked:
            found.append(f"{role} ({name}): {', '.join(leaked)}")
    if found:
        return doctor.Check(
            FOREIGN_SECRETS_CHECK, "fail",
            f"в собранном окружении шага лежит секрет ДРУГОГО провайдера — "
            f"{'; '.join(found)}; значения не читаются и не печатаются. "
            f"Сужение окружения по провайдеру (runner.role_env) разъехалось "
            f"с реестром провайдеров")
    if unassembled:
        return doctor.Check(
            FOREIGN_SECRETS_CHECK, "warn",
            f"окружение шага не собрано, сверка не проведена — "
            f"{'; '.join(unassembled)}")
    return doctor.Check(
        FOREIGN_SECRETS_CHECK, "ok",
        "секретов других провайдеров в собранном окружении шагов ролей нет")


def _foreign_provider_secrets(provider) -> list:
    """Имена AMBIENT-переменных с секретами ДРУГИХ провайдеров реестра,
    стоящие в общем белом списке манифеста. Значения не читаются и никуда
    не печатаются — только имена.

    Предмет — состояние машины Оператора, а НЕ собранное окружение шага:
    после сужения по провайдеру (SPEC 01M3F7BYE82S9AQCBSP1RTQQTR,
    требование 4) такое имя до шага чужого исполнителя уже не доходит.
    Про собранное окружение отвечает `check_foreign_provider_secrets`
    выше — отказом; жёлтая строка смока Codex, единственный читатель
    этой функции, остаётся зафиксированной своей регрессией
    (`tests/test_providers_codex.py::...::test_foreign_provider_secret_
    is_a_separate_yellow_line`) и в эту задачу не входит («Не входит»
    SPEC: ослабление любой проверки `doctor`).
    """
    own = set(provider.secret_env_names())
    found = []
    for other in doctor.providers.PROVIDERS.values():
        if other is provider:
            continue
        for name in other.secret_env_names():
            if name in own or name in found:
                continue
            if name in doctor.stack.ROLE_ENV_ALLOWLIST and os.environ.get(name):
                found.append(name)
    return found


