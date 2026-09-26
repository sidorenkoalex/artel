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

Разбор вывода, учёт стоимости шага и сигнатуры провалов — ВТОРАЯ часть
линии провайдеров (SPEC 01M32NH9QTC1T6FNH8JD79662R, требования 1-3):
`parse_output_line` переводит строки `codex exec --json` в событие общего
вида, итог запуска несёт разбивку токенов БЕЗ цены (`usd is None` —
расход шага считает пульт по тарифу модели, `cost_from_cli: false` в
каталоге), а провалы получают собственный набор сигнатур с общими
именами классов.

Коллаборанты пульта читаются ленивым импортом ВНУТРИ методов — тем же
приёмом и по той же причине, что в `providers/claude.py` (см. докстринг
`base.py` про 3.9-совместимость пути импорта манифеста стека).
"""
import json
import re

from .base import (CliTool, EMPTY_EVENT, HomeReference, RoleExecutorProvider,
                   RunResult, StreamEvent, ToolCall, ToolResult)

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

# --- разбор вывода `codex exec --json` (требования 1-2) -----------------
#
# Виды СОБЫТИЙ образца 0.155.1. Служебные (`thread.started`,
# `turn.started`) названы наравне с остальными, хотя пульту сказать им
# нечего: так «знаем и показывать нечего» отличимо от «имени не знаем», а
# незнакомое имя обслуживается одной веткой — ею же гасятся `item.updated`
# и прочее, чего образцы не несут, а живой поток несёт (требование 1,
# последний абзац).
THREAD_STARTED_EVENT = "thread.started"
TURN_STARTED_EVENT = "turn.started"
ITEM_STARTED_EVENT = "item.started"
ITEM_COMPLETED_EVENT = "item.completed"
TURN_COMPLETED_EVENT = "turn.completed"
SILENT_EVENTS = (THREAD_STARTED_EVENT, TURN_STARTED_EVENT)

# Виды ЭЛЕМЕНТОВ, несущих вызов инструмента: `item.started` даёт вызов,
# `item.completed` ТОГО ЖЕ `item.id` — его результат. `reasoning` в перечень
# не входит намеренно: размышления исполнителя — не вызов и не сказанное
# словами, и у Claude блок мышления тоже не даёт ни строки лога, ни текста
# события (`claude._render_block`).
COMMAND_ITEM = "command_execution"
WEB_SEARCH_ITEM = "web_search"
MCP_ITEM = "mcp_tool_call"
FILE_CHANGE_ITEM = "file_change"
TOOL_ITEMS = (COMMAND_ITEM, WEB_SEARCH_ITEM, MCP_ITEM, FILE_CHANGE_ITEM)

# Элемент, несущий сказанное словами.
AGENT_MESSAGE_ITEM = "agent_message"

# Ключевой аргумент вызова — первый найденный ключ элемента, в порядке
# предпочтения. Перечень, а не имя на вид элемента: `command_execution`
# несёт `command`, `mcp_tool_call` — `arguments`, а имена полей `web_search`
# и `file_change` материалы задачи не называют вовсе, и отсутствие ключа
# обязано давать пустой аргумент, а не пропавший вызов (тот же приём, что
# `claude.LOG_ARGUMENT_KEYS`).
ITEM_ARGUMENT_KEYS = ("command", "query", "arguments", "path", "changes",
                      "text")

# Текст результата вызова — первый ключ, который у элемента ЕСТЬ (пусть и
# пустой): `aggregated_output` команды бывает пустой строкой, и это
# «результат без вывода», а не «результата нет».
RESULT_TEXT_KEYS = ("aggregated_output", "result", "error", "text")

# Признак ошибки результата — ТОЛЬКО состояние элемента. Поле `error` не
# читается ни одной веткой: живой запуск 0.155.1 завершил `mcp_tool_call`
# состоянием `failed` при `error: null` (требование 1), и чтение `error`
# пропустило бы провалившийся вызов как успешный.
ITEM_STATUS_KEY = "status"
FAILED_STATUS = "failed"

# Счётчики `usage` итога запуска -> ОБЩИЕ виды цены (`models.PRICE_KINDS`).
# Отображение стоит здесь, а не собирается из `models`: имена видов общие,
# а вот КАКОЙ счётчик CLI какому виду отвечает — знание провайдера, и у
# Codex оно не совпадает с Claude ни полями, ни арифметикой (вход приходит
# с кэшем внутри, см. `_tokens_by_kind`).
USAGE_INPUT_KEY = "input_tokens"
USAGE_CACHE_READ_KEY = "cached_input_tokens"
USAGE_CACHE_WRITE_KEY = "cache_write_input_tokens"
USAGE_OUTPUT_KEY = "output_tokens"

# Отметка вызова инструмента в логе шага: префикс строки и срез ключевого
# аргумента. Символ и число повторяют `claude.py`, а не импортируются из
# него: формат строки лога — провайдерское знание (докстринг `base.py`), а у
# Claude оно вдобавок заморожено требованием «ни один символ строки лога не
# меняется» (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ) — общий адрес превратил бы
# любую правку вида строки Codex в правку поведения Claude.
TOOL_CALL_LINE_PREFIX = "· "
TOOL_ARGUMENT_LIMIT = 100

# --- сигнатуры провалов (требование 3) ----------------------------------
#
# ПУСТ намеренно и с адресом: тексты, которыми Codex CLI сообщает о лимите
# подписки, неверном входе, недоступной модели и обрыве, снимаются с ЖИВЫХ
# случаев задачей 6 линии, а выдумывать их эта задача не вправе (SPEC
# требование 3 и «Не входит»).
#
# Пустота — не «механизма нет». Набор спрашивает общий классификатор
# (`failure_classification.classify_attempt_failure`) у провайдера РОЛИ
# шага, и одна строка здесь включает класс целиком, вместе с его
# последствиями. Поведение по умолчанию от пустоты не страдает: провал с
# текстом, не совпавшим ни с одной сигнатурой, остаётся неклассифицированным
# и идёт в повтор с бэкоффом — то же, что делает у Claude «системный
# кандидат». Чего нельзя — отдать здесь набор Claude: его слов («does not
# support this model», «api error:») Codex не произносит, а класс
# детерминированного отказа оборвал бы повторы шага на чужом тексте.
FAILURE_SIGNATURES = ()

# Регулярки, которыми текст провалившейся попытки называет минимальную
# версию СВОЕГО CLI: первая совпавшая группа 1 и есть версия. Перечень свой
# и сегодня пустой по той же причине — формулировка Claude («version X or
# newer is required») здесь не годится, это слова другого CLI. Мёртвого пути
# пустота не оставляет: единственный читатель
# (`runner._model_unsupported_after_attempt`) работает ровно на классе
# `model_unsupported`, сигнатуры которого у Codex появятся той же задачей 6,
# — версия без своей сигнатуры была бы недостижима.
REQUIRED_VERSION_PATTERNS = ()


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
        команды пульта для явного запуска нет. Вход заводит задача 6
        линии, где живой запуск Codex нужен для канарейки и калибровки
        расхода (решение Оператора,
        `tasks/01M32NH9QTC1T6FNH8JD79662R/ANSWER-1.md`, п.2): разбор
        вывода, без которого итог живого вызова нечем прочитать, есть
        уже здесь, а командного слоя пульта эта задача не касается.

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

    # --- разбор вывода ----------------------------------------------------

    def parse_output_line(self, raw_line):
        """Строка `codex exec --json` -> `StreamEvent` (требование 1).

        Пять видов события образца 0.155.1 разбираются, остальные дают
        пустое событие: незнакомое имя — не ошибка и не исключение, иначе
        первая же строка вида, которого не было в образцах (`item.updated`
        живого потока), роняла бы разбор шага либо помечала бы шаг
        провалившимся. Тем же правилом гасится элемент `item.type=error`
        переключения транспорта — не отдельная механика, а незнакомый вид
        элемента (требование 1, последний абзац).

        Строка, не разобравшаяся как JSON-ОБЪЕКТ (трейсбек CLI, stderr,
        обрезанная строка, JSON-массив), уходит в лог шага как есть и ни
        на что больше не влияет: молча не глотаем ничего.
        """
        stripped = raw_line.lstrip()
        if not stripped.startswith("{"):
            return self._passthrough(raw_line)
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            return self._passthrough(raw_line)
        if not isinstance(event, dict):
            return self._passthrough(raw_line)

        kind = event.get("type")
        if kind in SILENT_EVENTS:
            return EMPTY_EVENT
        if kind == TURN_COMPLETED_EVENT:
            return self._run_result_event(event)
        if kind == ITEM_STARTED_EVENT:
            return self._tool_call_event(event)
        if kind == ITEM_COMPLETED_EVENT:
            return self._item_completed_event(event)
        return EMPTY_EVENT

    @staticmethod
    def _passthrough(raw_line):
        """Строка мимо формата событий: в лог как есть, больше нигде."""
        return StreamEvent(raw_line, None, (), (), None, None)

    @staticmethod
    def _item(event):
        """Элемент события либо пустое отображение — событие об элементе
        без самого элемента разбирается как незнакомое, а не падает."""
        item = event.get("item")
        return item if isinstance(item, dict) else {}

    def _tool_call_event(self, event):
        """`item.started`: начало вызова инструмента.

        Результата здесь нет и быть не может — он придёт `item.completed`
        того же `item.id`. Вид элемента, который вызовом не является
        (`agent_message`, `reasoning`, незнакомый), даёт пустое событие:
        «исполнитель начал говорить» пульту сказать нечего, текст приедет
        завершением.
        """
        item = self._item(event)
        if item.get("type") not in TOOL_ITEMS:
            return EMPTY_EVENT
        name = self._tool_name(item)
        argument = self._argument(item)
        call = ToolCall(item.get("id"), name, argument)
        return StreamEvent(self._call_line(name, argument), None, (call,), (),
                           None, None)

    def _item_completed_event(self, event):
        """`item.completed`: результат вызова либо сказанный текст."""
        item = self._item(event)
        kind = item.get("type")
        if kind in TOOL_ITEMS:
            return self._tool_result_event(item)
        if kind == AGENT_MESSAGE_ITEM:
            return self._agent_message_event(item)
        return EMPTY_EVENT

    def _tool_result_event(self, item):
        """Результат вызова инструмента: тот же `item.id`, текст и признак
        ошибки из СОСТОЯНИЯ элемента.

        В лог результат не идёт намеренно — простыня вывода инструмента
        Оператору не нужна (то же решение, что у Claude), но метрике
        трения шага он нужен вместе со своим вызовом: потому и отдельное
        поле события, а не «погасили и забыли».
        """
        result = ToolResult(item.get("id"), self._result_text(item),
                            item.get(ITEM_STATUS_KEY) == FAILED_STATUS)
        return StreamEvent("", None, (), (result,), None, None)

    @staticmethod
    def _agent_message_event(item):
        """`agent_message`: то, что исполнитель сказал словами — и в поле
        `text` события, и строкой лога. Пустой текст — пустое событие:
        показывать и пересказывать нечего."""
        text = item.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            return EMPTY_EVENT
        return StreamEvent(f"{text}\n", text, (), (), None, None)

    def _run_result_event(self, event):
        """`turn.completed`: итог запуска — разбивка токенов и ОТСУТСТВИЕ
        цены (требование 2).

        `usd` — `None` безусловно, а не «если поля нет»: `codex exec
        --json` доллары не считает в принципе, и условная ветка читалась
        бы как «иногда считает». `None`, не `0.0`: «CLI цены не сообщил»
        и «запуск был бесплатен» ветвятся в учёте по-разному
        (`spend.charge_step`) — расход шага считает пульт по действующему
        тарифу модели, раздел `codex` каталога объявил
        `cost_from_cli: false`.

        Признака ошибки у `turn.completed` образцы 0.155.1 не несут,
        поэтому итог запуска — всегда «не ошибка»: провал попытки пульт
        узнаёт кодом возврата CLI и классифицирует сигнатурами
        (`failure_signatures`), а выдуманное поле состояния молча
        помечало бы провалившимися успешные шаги.
        """
        tokens_by_kind = self._tokens_by_kind(event.get("usage"))
        return StreamEvent("", None, (), (), tokens_by_kind,
                           RunResult(tokens_by_kind, None, False, ""))

    @classmethod
    def _tokens_by_kind(cls, usage):
        """`usage` итога запуска -> разбивка по ОБЩИМ видам цены
        (`models.PRICE_KINDS`); `None` — расход неизвестен.

        Арифметика — не переименование полей (требование 2):

        - `input` = `input_tokens` МИНУС `cached_input_tokens`:
          кэшированный вход ВХОДИТ в `input_tokens`, и без вычитания
          дешёвые чтения кэша тарифицировались бы вторично ценой входа;
        - `cache_read` = `cached_input_tokens`;
        - `cache_write` = `cache_write_input_tokens`, отсутствие поля —
          ноль (`docs/research/codex-live-check-2026-09-22.md`, п.5);
        - `output` = `output_tokens` БЕЗ `reasoning_output_tokens`: токены
          рассуждений — ЧАСТЬ выхода (живой запуск: `output_tokens` 8513
          при `reasoning_output_tokens` 997), и сложение завысило бы
          выход по самой дорогой цене тарифа.

        Неполный `usage` (не отображение, нет входа или выхода, счётчик не
        целое число) — `None`, то есть «расход неизвестен», а не нули: та
        же деградация, что назвал отчёт живых проверок (п.5). Нули ушли бы
        в `spent_usd` бесплатным шагом, а `None` уводит учёт на
        именованную запись `agent cost UNCHARGED` с алертом
        (`spend._charge_by_tariff`).

        Вычитание берётся с нижней границей ноль: `cached_input_tokens`
        больше `input_tokens` — испорченный `usage`, и отрицательный
        счётчик вычел бы деньги из потраченного по задаче.
        """
        if not isinstance(usage, dict):
            return None
        total_input = cls._counter(usage.get(USAGE_INPUT_KEY))
        output = cls._counter(usage.get(USAGE_OUTPUT_KEY))
        if total_input is None or output is None:
            return None
        cache_read = cls._counter(usage.get(USAGE_CACHE_READ_KEY)) or 0
        cache_write = cls._counter(usage.get(USAGE_CACHE_WRITE_KEY)) or 0
        return {"input": max(total_input - cache_read, 0),
                "output": output,
                "cache_write": cache_write,
                "cache_read": cache_read}

    @staticmethod
    def _counter(value):
        """Счётчик токенов из события; `None` — не целое число. `bool` —
        не счётчик: `True` не равен одному токену (то же правило, что у
        `spend.json_number` про доллары)."""
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    @staticmethod
    def _tool_name(item):
        """Имя инструмента вызова.

        У `mcp_tool_call` это `сервер/инструмент`, а не имя вида: вид —
        конверт, а инструментов внутри него столько, сколько серверов у
        роли, и под общим именем метрика трения считала бы повтором два
        разных вызова MCP. Сервер или инструмент не назван — остаётся вид
        элемента: имя вызова обязано быть непустым.
        """
        kind = item.get("type")
        if kind == MCP_ITEM:
            server, tool = item.get("server"), item.get("tool")
            if server and tool:
                return f"{server}/{tool}"
        return kind

    @classmethod
    def _argument(cls, item):
        """Ключевой аргумент вызова по первому найденному ключу
        `ITEM_ARGUMENT_KEYS`; пустая строка — ни одного из них нет."""
        for key in ITEM_ARGUMENT_KEYS:
            value = item.get(key)
            if value:
                return cls._text_of(value)
        return ""

    @classmethod
    def _result_text(cls, item):
        """Текст результата вызова по первому ключу `RESULT_TEXT_KEYS`,
        который у элемента ЕСТЬ и не пуст значением `null`.

        Проверяется наличие ключа, а не его правдивость: пустой
        `aggregated_output` — это «команда ничего не написала», и
        проваливаться по нему в соседние ключи значило бы показывать на
        месте вывода команды чужое поле.
        """
        for key in RESULT_TEXT_KEYS:
            if key in item and item[key] is not None:
                return cls._text_of(item[key])
        return ""

    @staticmethod
    def _text_of(value):
        """Значение поля элемента как текст: строка — как есть, остальное
        (аргументы MCP, результат-структура, перечень правок файлов) —
        компактным JSON с сохранением букв, чтобы Оператор читал русский
        текст, а не escape-последовательности."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _call_line(name, argument):
        """Отметка вызова инструмента в логе шага: имя и срез ключевого
        аргумента в одну строку — по ней Оператору видно, работает шаг или
        встал."""
        flat = " ".join(str(argument).split())[:TOOL_ARGUMENT_LIMIT]
        return f"{TOOL_CALL_LINE_PREFIX}{name} {flat}".rstrip() + "\n"

    # --- сигнатуры провалов ----------------------------------------------

    def failure_signatures(self):
        """Сигнатуры провалов попытки — свой набор, см.
        `FAILURE_SIGNATURES` о том, почему он сегодня пуст и что это
        значит для поведения шага."""
        return FAILURE_SIGNATURES

    def required_cli_version(self, text):
        """Версия CLI, которую текст попытки называет минимальной; `None`
        — текст её не несёт. Разбор свой: формулировку Claude метод не
        понимает намеренно (требование 3), см.
        `REQUIRED_VERSION_PATTERNS`."""
        for pattern in REQUIRED_VERSION_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                return match.group(1)
        return None
