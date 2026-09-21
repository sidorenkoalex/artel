"""Провайдер исполнителя роли `codex` (OpenAI Codex CLI, `codex exec`).

Вторая реализация интерфейса `base.RoleExecutorProvider` (SPEC
01M32NH6P053978AER66P0X4GN, требования 1-8, 12): команда шага, окружение
процесса, курируемый дом роли, раздел каталога моделей, предполётные
проверки и офлайн-смок изоляции. Ни одна роль на Codex этой задачей не
переводится — провайдер заводится, но ярусов на его модели нет, и ни
один шаг пульта в него не заходит.

Изоляция здесь не теория: живой запуск 0.155.1 с пользовательским
конфигом Оператора в песочнице `read-only` позвал MCP-сервер `cua_repl`
(«Computer Use») и попытался открыть браузер на машине Оператора — не
вышло только потому, что браузера не было. Отсюда двойная защита: и
курируемый `config.toml` дома роли, и те же значения флагами самой
команды шага (требование 3) — дом роли можно потерять (`.artel/home`
эфемерен, ADR-0005 п.3), команду шага собирает код.

Разбор вывода, учёт стоимости и сигнатуры провалов — ВТОРАЯ часть линии
провайдеров: `parse_output_line`, `failure_signatures` и
`required_cli_version` здесь намеренно не реализованы и громко
отказывают базовым интерфейсом.

Коллаборанты пульта читаются ленивым импортом ВНУТРИ методов — тем же
приёмом и по той же причине, что в `providers/claude.py` (см. докстринг
`base.py` про 3.9-совместимость пути импорта манифеста стека).
"""
import os

from .base import CliTool, HomeReference, RoleExecutorProvider

# Имя инструмента и его минимальная версия — та же 0.155.1, что объявляет
# раздел `codex` каталога моделей (`models.yaml`). Минимум инструмента —
# нижняя граница самого CLI, не связка с моделями: ту держит запись
# модели в каталоге (поле `min_cli_version`).
CLI_NAME = "codex"
CLI_MINIMUM = (0, 155, 1)
CLI_VERSION_COMMAND = (CLI_NAME, "--version")

# Каталог референса курируемого дома роли в репозитории и имя, под
# которым он разворачивается в `.artel/home` — то же правило, что у
# claude: без ведущей точки в самом репозитории, с точкой в развёрнутом
# слое (docs/reference/role-home.md).
HOME_REFERENCE_DIR = ("docs", "reference", "role-home", CLI_NAME)
DEPLOYED_HOME_DIR = ".codex"

# Переменная окружения, которой CLI сообщается адрес его дома. Именно она
# уводит роль от `~/.codex` Оператора — со всеми его MCP-серверами и
# правилами (конфиг-инъекция, ADR-0003 п.14).
HOME_ENV = "CODEX_HOME"

# Переменная окружения ключа OpenAI. Другой авторизации (вход через
# ChatGPT, `auth.json` Оператора) роль не получает: дом роли курируемый и
# пуст, а `CODEX_HOME` переписывается всегда.
API_KEY_ENV = "OPENAI_API_KEY"

# Одиннадцать функций, включённых в 0.155.1 ПО УМОЛЧАНИЮ (факт живого
# запуска, ANSWER-1 родительской задачи 01M32K876ZCDZW8M5CZ1S5WY9J). Тот
# же перечень выключает курируемый `config.toml`; порядок — как в справке
# CLI, он же порядок флагов команды шага.
DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "computer_use",
    "in_app_browser",
    "plugins",
    "remote_plugin",
    "plugin_sharing",
    "skill_mcp_dependency_install",
    "hooks",
)

# Песочница шага: запись разрешена только в рабочем каталоге.
SANDBOX_MODE = "workspace-write"

# `-c`-переопределения команды шага — ТЕ ЖЕ пары «ключ = значение», что
# несёт `docs/reference/role-home/codex/config.toml`. Это не дублирование
# ради надёжности, а два разных рубежа одной изоляции: дом роли
# эфемерен и курируется руками Оператора, команда шага собирается кодом.
# Совпадение пар сверяет тест, а не глаз (требование 3, AC-5).
NETWORK_ACCESS_KEY = "sandbox_workspace_write.network_access"
NETWORK_ACCESS_VALUE = "false"
APPROVAL_POLICY_KEY = "approval_policy"
APPROVAL_POLICY_VALUE = "never"
CONFIG_OVERRIDES = (
    (NETWORK_ACCESS_KEY, NETWORK_ACCESS_VALUE),
    (APPROVAL_POLICY_KEY, APPROVAL_POLICY_VALUE),
)

# Подкоманда шага и позиционный аргумент «промпт со стандартного входа».
EXEC_SUBCOMMAND = "exec"
STDIN_PROMPT = "-"


class CodexProvider(RoleExecutorProvider):
    """OpenAI Codex CLI как исполнитель роли."""

    name = CLI_NAME

    #: Живой смок этого CLI обычный прогон `doctor` не запускает
    #: (требование 12): вызов платный, а провайдер в пульте заведён
    #: раньше, чем на него переведена хоть одна роль.
    live_smoke_in_doctor = False

    def cli_tool(self):
        return CliTool(CLI_NAME, CLI_MINIMUM, CLI_VERSION_COMMAND)

    def command(self, model=None):
        """Argv шага роли (требования 2-3).

        Порядок обязателен и проверяется тестом: 0.155.1 разбирает
        ГЛОБАЛЬНЫЕ флаги (`--disable`, `-c`) только ДО подкоманды, а
        флаги подкоманды (`--json`, `--sandbox`, `--ephemeral`,
        `--ignore-rules`, `-m`) — после неё. Собери список одним куском
        после `exec` — CLI либо откажет разбором аргументов, либо, хуже,
        молча потеряет выключение функций.

        argv[0] — абсолютный путь из резолва манифеста
        (`runner.declared_tool_path`), а не литерал `codex`: литерал
        искался бы по PATH роли в момент запуска, где каталог другого
        объявленного инструмента стоит раньше и может нести одноимённый
        бинарник (инцидент 06.09, см. `providers/claude.py::command`).

        Флага `--ignore-user-config` в команде НЕТ (ANSWER-1, вопрос 1):
        конфиг Оператора и так недостижим переносом `CODEX_HOME`, а флаг
        выключил бы заодно курируемый `config.toml` дома роли — то есть
        снял бы ровно ту защиту, ради которой дом заводится.

        Флага `-C` (рабочий каталог) тоже нет: рабочий каталог шага
        приходит процессу параметром `cwd=` при спавне агента, а у этого
        метода нет ни идентификатора задачи, ни target'а — взять их
        можно было бы только правкой `orchestrator/runner.py`, который
        эта задача оставляет только для чтения.

        Промпт замыкает список позиционным `-`: `codex exec -` читает
        его со стандартного входа, и текст задачи не уезжает в argv
        (а значит, и в вывод `ps` машины Оператора).
        """
        from .. import runner
        cmd = [runner.declared_tool_path(CLI_NAME)]
        # --- глобальные флаги: строго ДО подкоманды
        for feature in DISABLED_FEATURES:
            cmd += ["--disable", feature]
        for key, value in CONFIG_OVERRIDES:
            cmd += ["-c", f"{key}={value}"]
        # --- подкоманда и её флаги
        cmd += [EXEC_SUBCOMMAND, "--json", "--sandbox", SANDBOX_MODE,
                "--ephemeral", "--ignore-rules"]
        if model is not None:
            cmd += ["-m", model]
        cmd.append(STDIN_PROMPT)
        return cmd

    def environment(self, role=None, task_id=None):
        """Дом роли и ключ OpenAI — поверх общего белого списка манифеста
        (`runner.role_env`), требование 4.

        `HOME` и `CODEX_HOME` переписываются ВСЕГДА, а не `setdefault`:
        роль не наследует user-слой Оператора (ADR-0003 п.14), и
        наследование `CODEX_HOME` означало бы его MCP-серверы и правила
        внутри шага — ровно ту конфиг-инъекцию, которую нашёл живой
        запуск 0.155.1. `HOME` требование 4 поимённо не называет, но
        требование 12 требует от смока изоляции, чтобы собранное
        окружение не наследовало ambient `HOME`, — а без этой строки его
        наследовал бы общий белый список манифеста.

        Каталог дома создаётся здесь же — тем же приёмом, что
        `ClaudeProvider` создаёт каталог конфига: CLI, не нашедший
        `CODEX_HOME`, завёл бы его сам, и это был бы каталог, о котором
        пульт не знает.

        Ключ приходит из ОТДЕЛЬНОГО слота keychain
        (`config.OPENAI_API_KEY_SLOT`), а не из слотов роли `roles.yaml`:
        те несут токен подписки Claude, и общий вызов `runner.role_token`
        отдал бы шагу Codex чужой секрет под именем ключа OpenAI.
        Заданная Оператором ambient-переменная сильнее слота — тот же
        приоритет, что у токена Claude, поэтому keychain не спрашивается
        вовсе, когда переменная задана.
        """
        from .. import config, keychain
        home = config.ROLE_HOME / DEPLOYED_HOME_DIR
        home.mkdir(parents=True, exist_ok=True)
        env = {
            "HOME": str(config.ROLE_HOME),
            HOME_ENV: str(home),
        }
        if not os.environ.get(API_KEY_ENV):
            key = keychain.token(config.OPENAI_API_KEY_SLOT)
            if key:
                env[API_KEY_ENV] = key
        return env

    def secret_env_names(self):
        """Имена переменных, которыми приходит секрет ЭТОГО провайдера —
        по ним смок изоляции отличает свой секрет от чужого."""
        return (API_KEY_ENV,)

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
        """Полный набор предполётных проверок провайдера (требование 12).

        Порядок и условие — те же, что у `ClaudeProvider`: версия CLI не
        считается, если самого CLI не нашлось (платить подпроцессом за
        заведомо известный исход не за чем). Имена строк — СВОИ, не
        совпадающие с именами одноимённых проверок Claude: склейка
        `doctor.provider_preflight_checks` отбрасывает одинаковые
        записи, и под общими именами отсутствие ключа Codex исчезло бы
        за зелёной строкой Claude (AC-16).
        """
        checks = [self.check_cli_found()]
        if checks[0].status == "ok":
            checks.append(self.check_cli_version())
        checks.append(self.check_token(role))
        checks.append(self.check_home_reference())
        return checks

    def check_cli_found(self):
        from .. import doctor
        return doctor.check_codex_cli_found()

    def check_cli_version(self):
        from .. import doctor
        return doctor.check_codex_cli_version()

    def check_token(self, role):
        from .. import doctor
        return doctor.check_codex_api_key(role)

    def check_home_reference(self):
        from .. import doctor
        return doctor.check_codex_role_home()

    def isolation_smoke(self, role="developer"):
        """Офлайн-смок изоляции (требование 12) — своя строка `doctor`
        помимо общей `doctor.isolation_smoke`: предметы у них разные
        (там — project-/user-слой Claude, здесь — песочница, сеть и
        одиннадцать функций Codex)."""
        from .. import doctor
        return doctor.codex_isolation_smoke(role)

    # --- модель и живой смок ---------------------------------------------

    def installed_cli_version(self):
        """Версия УСТАНОВЛЕННОГО `codex` — спрашивается у `codex`, не у
        `claude`: вердикт по версии чужого CLI дал бы зелёный предполёт
        при древнем Codex и провал попытки за деньги."""
        from .. import stack
        return stack.installed_cli_version(CLI_NAME)

    def model_verdict(self, model):
        """Сверка модели роли с установленной версией CLI (требование 7)
        — тем же правилом, что у Claude: минимум версии берётся из записи
        модели в каталоге `models.yaml`, модели вне каталога
        соответствует `fail`, нечитаемый каталог — тоже `fail` с
        названной причиной, а не исключение наружу (точка вызова —
        предполёт шага, он обязан назвать причину, а не уронить `run`
        трейсбеком). `codex --version` не зовётся, пока модель не найдена
        в каталоге: подпроцесс ради заведомого отказа не нужен.
        """
        from .. import models, stack
        try:
            entry = models.catalog_model(model)
        except models.ModelsError as exc:
            return stack.ModelCliVerdict(
                "fail", f"{stack.MODEL_UNSUPPORTED_PREFIX}: {exc}")
        return stack.model_cli_verdict(model, self.installed_cli_version(),
                                       entry.min_cli_version, CLI_NAME)

    def live_smoke_command(self, prompt):
        """Argv минимального живого вызова CLI — только по явному запуску
        Оператора (`live_smoke_in_doctor = False`).

        Инструмент берётся из команды шага (`command()[0]`), а не именем:
        смок обязан проверять живость ТОГО САМОГО бинарника, который
        реально запустит шаг. `--skip-git-repo-check` — потому что смок
        гоняется вне рабочей копии, а `codex exec` по умолчанию
        отказывается работать за пределами git-репозитория. Промпт идёт
        аргументом, а не через stdin: смок ничего не правит и рабочей
        обвязки шага (песочница, выключение функций) не несёт.
        """
        return [self.command()[0], EXEC_SUBCOMMAND, "--json",
                "--skip-git-repo-check", prompt]
