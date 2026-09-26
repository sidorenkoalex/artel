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
import re

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

# Имена переменных окружения, которыми к шагу мог бы прийти ключ API —
# перечень того, чего в окружении шага быть НЕ ДОЛЖНО, а не канала
# секрета провайдера (решение Оператора 22.09.2026,
# `docs/research/providers-codex-plan.md`, раздел 6 п.1: роли авторизуются
# входом по подписке ChatGPT). Читатель один — смок изоляции
# (`doctor.codex_isolation_smoke`), и он проверяет отсутствие: именованный
# адрес канала внутри пульта был бы приглашением вернуть ключ «по
# аналогии».
#
# Имён три, а не одно: живой запуск 0.155.1 22.09
# (`docs/research/codex-live-check-2026-09-22.md`) показал, что `codex
# exec` читает ключ из `CODEX_API_KEY`, а не из `OPENAI_API_KEY`, —
# проверка на одно имя пропустила бы ровно тот канал, которым ключ и
# подействовал бы на шаг.
FORBIDDEN_KEY_ENV_NAMES = ("OPENAI_API_KEY", "CODEX_API_KEY",
                           "CODEX_ACCESS_TOKEN")

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

# Пары авторизации подписки: где CLI держит токены входа и каким способом
# входит. Стоят ОТДЕЛЬНЫМ именованным кортежем внутри общего
# `CONFIG_OVERRIDES`, потому что у них есть второй читатель — предполётная
# проверка `doctor.check_codex_chatgpt_auth`: требование «вход и шаг задают
# один способ авторизации» держится тождеством константы, а не совпадением
# двух литералов в разных файлах.
#
# `keyring` — системная связка ключей macOS: токены хранит и продлевает сам
# CLI, пульт их не видит и не пишет. `chatgpt` — принудительный способ
# входа: без него `codex exec` молча ушёл бы на ключ API (живая проверка
# 22.09 получила 401 ровно этим путём), а окружение шага ключа больше не
# несёт вовсе.
AUTH_STORE_KEY = "cli_auth_credentials_store"
AUTH_STORE_VALUE = "keyring"
LOGIN_METHOD_KEY = "forced_login_method"
LOGIN_METHOD_VALUE = "chatgpt"
AUTH_OVERRIDES = (
    (AUTH_STORE_KEY, AUTH_STORE_VALUE),
    (LOGIN_METHOD_KEY, LOGIN_METHOD_VALUE),
)
CONFIG_OVERRIDES = (
    (NETWORK_ACCESS_KEY, NETWORK_ACCESS_VALUE),
    (APPROVAL_POLICY_KEY, APPROVAL_POLICY_VALUE),
) + AUTH_OVERRIDES

# Подкоманда шага и позиционный аргумент «промпт со стандартного входа».
EXEC_SUBCOMMAND = "exec"
STDIN_PROMPT = "-"

# Подкоманда проверки подписочного входа и её потолок ожидания. Таймаут
# нужен не теоретически: `codex login status` при `keyring` обращается к
# связке ключей, и связка вправе спросить разрешение — без потолка висящий
# CLI держал бы предполёт шага (и прогон `doctor`) бесконечно.
LOGIN_STATUS_ARGS = ("login", "status")
LOGIN_STATUS_TIMEOUT_SEC = 20

# Подтверждение входа ChatGPT в выводе `codex login status`. 0.155.1
# отвечает `rc=0`, пустым `stdout` и `stderr='Logged in using ChatGPT\n'`
# (живые пробы, REVIEW.md итерации 1, R1-F1; отчёт `docs/research/
# codex-live-check-2026-09-22.md`) — поток разбирает
# `doctor._login_status_lines`, а сверка по точной строке краснела бы
# на любой переформулировке вендора, а сверка по одному слову `chatgpt` —
# зеленела бы на «Not logged in (ChatGPT)». Отсюда регулярка по тексту,
# сведённому к нижнему регистру и одному пробелу: утверждение о входе,
# упоминающее ChatGPT, и негативный lookbehind против отрицания. Код
# выхода 0 сам по себе ничего не доказывает: им же CLI отвечает и на «не
# вошёл», и на вход ключом API.
CHATGPT_LOGIN_RE = re.compile(r"(?<!not )logged in[^.\n]*chatgpt")


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
        """Дом роли — и БОЛЬШЕ НИЧЕГО, поверх общего белого списка
        манифеста (`runner.role_env`).

        Секрета в окружении шага у этого провайдера нет вовсе: роль
        авторизуется входом по подписке ChatGPT, а токены того входа
        хранит и продлевает сам CLI в системной связке ключей
        (`AUTH_OVERRIDES`). Ни ключ из слота keychain, ни ambient-ключ
        Оператора шагу не передаются — keychain здесь не спрашивается ни
        разу, и именованного слота ключа в пульте больше нет. До решения
        Оператора 22.09.2026 было наоборот, и зелёная строка `doctor` по
        наличию ключа не доказывала авторизацию вовсе: `codex exec` читает
        ключ из `CODEX_API_KEY`, а слот отдавался шагу под именем
        `OPENAI_API_KEY`.

        `HOME` и `CODEX_HOME` переписываются ВСЕГДА, а не `setdefault`:
        роль не наследует user-слой Оператора (ADR-0003 п.14), и
        наследование `CODEX_HOME` означало бы его MCP-серверы и правила
        внутри шага — ровно ту конфиг-инъекцию, которую нашёл живой
        запуск 0.155.1. `HOME` нужен ещё и подписочному входу: связку
        ключей CLI ищет по указателю в `$HOME/Library/Preferences`, и без
        отведённого `HOME` он читал бы указатель Оператора.

        Каталог дома создаётся здесь же — тем же приёмом, что
        `ClaudeProvider` создаёт каталог конфига: CLI, не нашедший
        `CODEX_HOME`, завёл бы его сам, и это был бы каталог, о котором
        пульт не знает.
        """
        from .. import config
        home = config.ROLE_HOME / DEPLOYED_HOME_DIR
        home.mkdir(parents=True, exist_ok=True)
        return {
            "HOME": str(config.ROLE_HOME),
            HOME_ENV: str(home),
        }

    def secret_env_names(self):
        """Имена переменных, которыми приходит секрет ЭТОГО провайдера —
        по ним смок изоляции отличает свой секрет от чужого.

        Пуст: секрета в окружении шага у Codex нет (см. `environment`).
        Перечислять здесь `FORBIDDEN_KEY_ENV_NAMES` нельзя — это имена
        того, чего быть не должно, а этот метод называет то, что шагу
        передаётся штатно: жёлтая строка `foreign-provider-secrets` тогда
        горела бы у шагов ролей на Claude на ключ, которого общий белый
        список манифеста уже не копирует никому.
        """
        return ()

    def login_status_command(self):
        """Argv проверки подписочного входа (`codex login status`).

        Те же две пары авторизации, что несёт команда шага, — ОДНОЙ
        константой `AUTH_OVERRIDES`: `codex login status` отвечает про тот
        способ хранения и входа, который ему задан, и без этих пар зелёная
        строка `doctor` доказывала бы не то, чем пойдёт шаг. Пары стоят ДО
        подкоманды по тому же правилу разбора 0.155.1, что и у `command()`.

        Инструмент — абсолютный путь из резолва манифеста, тот же, что у
        команды шага: проверять живость тёзки с PATH роли незачем
        (инцидент 06.09).
        """
        from .. import runner
        cmd = [runner.declared_tool_path(CLI_NAME)]
        for key, value in AUTH_OVERRIDES:
            cmd += ["-c", f"{key}={value}"]
        cmd += list(LOGIN_STATUS_ARGS)
        return cmd

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
        записи, и под общими именами невыполненный вход Codex исчез бы
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
        """Подписочный вход вместо ключа: `codex login status` домом роли.

        Имя метода интерфейса прежнее (`check_token` — «чем шаг
        авторизуется»), предмет другой: у провайдера больше нет секрета,
        приходящего окружением, и доказать авторизацию наличием записи в
        keychain нельзя — записи нет.
        """
        from .. import doctor
        return doctor.check_codex_chatgpt_auth(role)

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
        """Argv минимального живого вызова CLI.

        Сегодня его не запускает НИЧТО (REVIEW.md итерации 1, R1-F3):
        единственный вызывающий — `doctor._live_smoke_run`, а он при
        `live_smoke_in_doctor = False` выходит раньше сборки argv;
        команды пульта для явного запуска нет. Вход появляется во второй
        части линии провайдеров — вместе с разбором вывода, без которого
        итог живого вызова всё равно нечем прочитать.

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
