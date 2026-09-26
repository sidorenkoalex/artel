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
    ключа API в собранном окружении шага (`codex_provider.
    FORBIDDEN_KEY_ENV_NAMES`): роль авторизуется входом по подписке, и
    ключ, вернувшийся в окружение любым из трёх имён, — регресс
    требования 2, а не вариант настройки.

    Чужие секреты (токен подписки Claude), оставшиеся в окружении шага
    из ОБЩЕГО белого списка манифеста, — отдельная ЖЁЛТАЯ строка, а не
    молчание: сужение белого списка по провайдеру требует правки
    `orchestrator/runner.py` и в эту задачу не входит, поэтому единственное,
    чем факт утечки может стать заметным, — этот смок. Своим и чужим
    секрет называет реестр (`secret_env_names()` провайдеров), не литерал.

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
    # Ключ API в окружении шага — провал по ИМЕНИ переменной, без значения:
    # роль авторизуется входом по подписке, и наличие ключа означает, что
    # канал, убранный требованием 2, вернулся. Перебираются все три имени, а
    # не одно: `codex exec` читает ключ из `CODEX_API_KEY` (живая проверка
    # 22.09), и проверка на `OPENAI_API_KEY` пропустила бы именно
    # действующий канал.
    leaks += [f"{name}: в окружении шага лежит ключ API (значение не "
              f"читается) — роль авторизуется входом по подписке ChatGPT"
              for name in doctor.codex_provider.FORBIDDEN_KEY_ENV_NAMES
              if name in env]
    return env, leaks


FOREIGN_SECRETS_CHECK = "foreign-provider-secrets"


def check_foreign_provider_secrets() -> doctor.Check:
    """Секреты ЧУЖИХ провайдеров в окружении шага — по одной строке на
    весь `doctor`, симметрично жёлтой строке смока Codex (REVIEW.md
    итерации 1, R1-F4).

    Белый список манифеста (`stack.ROLE_ENV_ALLOWLIST`) общий на пульт, а
    не свой у каждого провайдера: секрет, заданный Оператором для одного
    исполнителя, копируется в окружение КАЖДОГО шага — в том числе шага
    роли на ЧУЖОМ провайдере (требование 12, AC-18). Сегодня такой секрет
    в списке один — токен подписки Claude, и он достаётся шагу на Codex; об
    этом же случае говорит жёлтой строкой `codex_isolation_smoke`. Ключ API
    OpenAI из списка ушёл вместе с каналом ключа (SPEC
    01M3EKCZJY9NGCW6VT878RX9JZ, требование 3), поэтому обратной стороны у
    этой строки больше нет — но сама она остаётся: реестр провайдеров
    открыт, и следующий провайдер со своим секретом в списке попадёт сюда
    записью в реестр, без правки проверки. Отдельной строкой, потому что у
    провайдера по умолчанию своего смока нет, а общий `isolation_smoke` про
    секреты других провайдеров не знает.

    Отдельная строка, а не пункт `isolation_smoke`: там предмет —
    «шаг достаёт то, чего не должен» (маркеры слоёв, хуки, MCP), и его
    зелёность сверяют регрессии, заведённые до реестра провайдеров;
    здесь — «в шаге лежит лишний секрет», состояние машины Оператора,
    которое лечится не кодом шага, а сужением белого списка (отдельная
    задача линии).

    Предупреждение, а не провал: сужение списка по провайдеру требует
    правки `orchestrator/runner.py` и в эту задачу не входит — краснеть
    на то, чего пульт сегодня не умеет иначе, значило бы красить
    `doctor` навсегда.
    """
    found = []
    for role in doctor.agent_roles():
        try:
            provider = doctor.providers.for_role(role)
        except doctor.providers.UnknownProviderError:
            # Про незарегистрированного провайдера роли говорит красная
            # строка `check_role_providers` — дублировать её нечем.
            continue
        names = _foreign_provider_secrets(provider)
        if names:
            found.append(f"{role} ({provider.name}): {', '.join(names)}")
    if not found:
        return doctor.Check(
            FOREIGN_SECRETS_CHECK, "ok",
            "секретов других провайдеров в окружении шагов ролей нет")
    return doctor.Check(
        FOREIGN_SECRETS_CHECK, "warn",
        f"общий белый список манифеста копирует в окружение шага секрет "
        f"ДРУГОГО провайдера — {'; '.join(found)}; значения не читаются и "
        f"не печатаются, сужение списка по провайдеру — отдельная задача "
        f"линии провайдеров")


def _foreign_provider_secrets(provider) -> list:
    """Имена ambient-переменных с секретами ДРУГИХ провайдеров реестра,
    которые общий белый список манифеста скопирует в окружение шага
    (`runner._allowlisted_env`). Значения не читаются и никуда не
    печатаются — только имена."""
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


