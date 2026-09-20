"""Провайдер исполнителя роли `claude` (Claude Code CLI, headless).

Сегодняшнее поведение пульта, собранное в одном месте (SPEC
01M2ZNTHSNFYSTF904P6SZTPYF, требования 2, 9): значения те же, что были
литералами в `orchestrator/runner.py`, `orchestrator/stack.py`,
`orchestrator/doctor/` и `orchestrator/catalog.py`, — любое отличие
argv, окружения или дома роли от сегодняшних является дефектом, а не
улучшением.

Коллаборанты пульта читаются ленивым импортом ВНУТРИ методов (тем же
приёмом, которым `runner` читает `doctor`, а `store` — `fixation`):
`orchestrator/stack.py` импортирует реестр провайдеров на уровне
модуля, чтобы собрать `REQUIRED_TOOLS`, а сам читается точкой входа под
интерпретатором 3.9 — обратный импорт на уровне модуля был бы и циклом,
и нарушением 3.9-совместимости (см. докстринг `base.py`).
"""
import os

from .base import CliTool, HomeReference, RoleExecutorProvider

# Имя инструмента и его минимальная версия — то же, что манифест стека
# нёс литералом до задачи (`stack.REQUIRED_TOOLS["claude"]`). Минимум
# инструмента — нижняя граница самого CLI, не связка с моделями: ту
# держит таблица совместимости `stack.MODEL_MIN_CLI_VERSION`.
CLI_NAME = "claude"
CLI_MINIMUM = (1, 0, 0)
CLI_VERSION_COMMAND = (CLI_NAME, "--version")

# Каталог референса курируемого дома роли в репозитории и имя, под
# которым он разворачивается в `.artel/home`: без ведущей точки в самом
# репозитории (инструментарий трактует `.claude/` как служебный каталог
# настроек агента), с точкой — в развёрнутом слое. Переименование
# происходит ровно при развёртывании (docs/reference/role-home.md).
HOME_REFERENCE_DIR = ("docs", "reference", "role-home", CLI_NAME)
DEPLOYED_HOME_DIR = ".claude"

# Белый список инструментов шага: только git и запуск тестов/guard,
# вместо полного Bash.
ALLOWED_TOOLS = "Bash(git:*),Bash(python3:*)"


class ClaudeProvider(RoleExecutorProvider):
    """Claude Code CLI как исполнитель роли."""

    name = CLI_NAME

    def cli_tool(self):
        return CliTool(CLI_NAME, CLI_MINIMUM, CLI_VERSION_COMMAND)

    def command(self, model=None):
        """Argv шага роли: сборка без побочных эффектов, один источник
        истины для реального запуска (`runner._spawn_and_wait`), для
        зеро-арг `runner.role_cmd()` и для офлайн-сверки
        `doctor.isolation_smoke` (SPEC T069, требование 2) — вместо
        двух списков флагов, синхронизируемых руками.

        argv[0] — абсолютный путь из резолва манифеста (SPEC
        01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 1, AC-1/AC-3): литерал
        `claude` искался бы по PATH роли в момент запуска, где каталог
        другого объявленного инструмента стоит раньше и может нести
        одноимённый бинарник (инцидент 06.09: подставной `claude`
        планки затенён настоящим из каталога `gh`). Обе точки вызова
        стоят после успешного `runner.role_env()` — `OSError` резолва
        там уже отработал бы раньше.

        `--strict-mcp-config` без курируемого `--mcp-config` (пульт его
        пока не заводит, SPEC T069 требование 1) резолвит шагу ноль
        MCP-серверов независимо от `.mcp.json` рабочего каталога —
        конфиг-инъекция через MCP тем же вектором, что уже закрыт
        `--setting-sources` для project-/local-хуков (SPEC T058,
        инцидент T046).

        `--model` — довеском в конец списка, а не внутри него: флаг
        per-role, и порядок остальных флагов от его наличия не зависит
        (SPEC 01M2DTT96FS25SHXP0HDTWARQH, требование 3).
        """
        from .. import config, runner
        cmd = [
            # `claude -p` без аргумента читает промпт со стандартного входа.
            runner.declared_tool_path(CLI_NAME),
            "-p", "--permission-mode", "acceptEdits",
            # stream-json — единственный режим, где строки приходят по
            # ходу шага: text и json отдают всё одним куском в конце
            # (замер в PLAN.md T017). --verbose при нём обязателен,
            # иначе CLI выходит с rc=1.
            "--output-format", "stream-json", "--verbose",
            # белый список вместо полного Bash
            "--allowedTools", ALLOWED_TOOLS,
            # изоляция от project-/local-слоя клиентских настроек
            # репозитория (хуки, MCP) — SPEC T058, инцидент T046
            "--setting-sources", config.AGENT_SETTING_SOURCES,
            # изоляция MCP-вектора: ambient `.mcp.json` рабочего
            # каталога не резолвится — SPEC T069
            "--strict-mcp-config",
        ]
        if model is not None:
            cmd = cmd + ["--model", model]
        return cmd

    def environment(self, role=None, task_id=None):
        """Дом роли, каталог конфига CLI и токен подписки — поверх
        общего белого списка манифеста (`runner.role_env`).

        Роль не наследует user-слой Оператора (ADR-0003 п.14), поэтому
        HOME и `CLAUDE_CONFIG_DIR` переписываются всегда, а не
        `setdefault`. Каталог конфига создаётся здесь же: CLI, не нашедший
        `CLAUDE_CONFIG_DIR`, создал бы его сам — и это был бы каталог, о
        котором пульт не знает.

        Аутентификация CLI живёт в user-слое Оператора (`~/.claude.json`
        + keychain-запись аккаунта) и вместе с ним из-под роли уходит —
        чистый HOME отвечает «Not logged in» (фактура T020, вопрос 18
        ADR-0003 п.14). Токен подписки (`claude setup-token`) кладётся
        Оператором в слот keychain и приходит роли переменной окружения;
        заданный Оператором ambient-токен сильнее слота — поэтому
        keychain спрашивается, только когда ambient-переменных нет
        (сегодняшний `setdefault`-приоритет, читаемый прямо из
        `os.environ`: обе переменные входят в белый список манифеста, то
        есть в собранном окружении они имеют ровно эти значения).
        """
        from .. import config, runner
        config.ROLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        env = {
            "HOME": str(config.ROLE_HOME),
            "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR),
        }
        if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and not os.environ.get(
                "ANTHROPIC_API_KEY"):
            token = runner.role_token(role)
            if token:
                env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        return env

    def home_reference(self):
        """Каталог референса дома роли и имя развёрнутого каталога.

        Путь считается от `config.ROOT` в момент вызова, не при импорте:
        песочницы тестов подменяют корень пульта.
        """
        from .. import config
        reference = config.ROOT
        for part in HOME_REFERENCE_DIR:
            reference = reference / part
        return HomeReference(reference, DEPLOYED_HOME_DIR)

    # --- предполётные проверки ------------------------------------------

    def preflight(self, role):
        """Полный набор предполётных проверок провайдера. Версия CLI не
        считается, если самого CLI не нашлось: платить подпроцессом за
        заведомо известный исход не за чем (тот же порядок, что
        `doctor.all_checks` держал литералами до задачи)."""
        checks = [self.check_cli_found()]
        if checks[0].status == "ok":
            checks.append(self.check_cli_version())
        checks.append(self.check_token(role))
        checks.append(self.check_home_reference())
        return checks

    def check_cli_found(self):
        from .. import doctor
        return doctor.check_cli_found()

    def check_cli_version(self):
        from .. import doctor
        return doctor.check_cli_version()

    def check_token(self, role):
        from .. import doctor
        return doctor.check_token(role)

    def check_home_reference(self):
        from .. import doctor
        return doctor.check_role_home_reference()

    # --- модель и живой смок ---------------------------------------------

    def installed_cli_version(self):
        from .. import stack
        return stack.installed_cli_version()

    def model_verdict(self, model):
        """Сверка модели роли с установленной версией CLI по таблице
        совместимости (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 3).

        `claude --version` зовётся ТОЛЬКО для модели из таблицы: модели
        вне её версия не нужна — вердикт `warn` «модель не в таблице
        совместимости» и запуск как есть.
        """
        from .. import stack
        installed = (self.installed_cli_version()
                     if model in stack.MODEL_MIN_CLI_VERSION else None)
        return stack.model_cli_verdict(model, installed)

    def live_smoke_command(self, prompt):
        """Минимальный живой вызов CLI (`doctor.live_smoke`): промпт
        аргументом, поток разбирается тем же `stream-json`, что и у шага.

        Инструмент берётся из команды шага (`command()[0]`), а не именем:
        живой смок обязан проверять ЖИВОСТЬ ТОГО САМОГО бинарника,
        который реально запустит шаг, — иначе он молчаливо проверял бы
        тёзку с PATH. Рабочая обвязка шага (`--permission-mode`,
        `--allowedTools`, `--setting-sources`, `--strict-mcp-config`)
        сюда не переносится: смок ничего не правит и промпт получает
        аргументом, а не файлом на stdin.
        """
        return [self.command()[0], "-p", prompt,
                "--output-format", "stream-json", "--verbose"]
