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
import json
import os
import re

from .base import (CliTool, EMPTY_EVENT, FailureSignature, HomeReference,
                   RoleExecutorProvider, RunResult, StreamEvent, ToolCall,
                   ToolResult)

# Имя инструмента и его минимальная версия — то же, что манифест стека
# нёс литералом до задачи (`stack.REQUIRED_TOOLS["claude"]`). Минимум
# инструмента — нижняя граница самого CLI, не связка с моделями: ту
# держит каталог моделей (`models.yaml`, поле `min_cli_version` записи
# модели).
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

# Переменные окружения, которыми приходит секрет этого провайдера: токен
# подписки и альтернативный ambient-канал. Те же два имени читает
# `environment()` ниже, решая, спрашивать ли keychain.
SECRET_ENV_NAMES = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")

# Срез текста ошибки итога запуска в строке лога и срез ключевого
# аргумента в отметке вызова инструмента — те же числа, что несли
# `agent_log.render_agent_line`/`render_block` до переезда разбора сюда
# (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 2: ни один символ строки
# лога не меняется).
ERROR_TEXT_LIMIT = 200
TOOL_ARGUMENT_LIMIT = 100
ERROR_LINE_PREFIX = "! ошибка агента: "
TOOL_CALL_LINE_PREFIX = "· "

# Ключи `input` блока `tool_use`, из которых берётся КЛЮЧЕВОЙ аргумент
# вызова — в порядке предпочтения. Какой из них есть, зависит от
# инструмента (Read/Edit против Bash), поэтому берётся первый
# попавшийся, а не имя, фиксированное заранее.
#
# Порядков два, и они РАЗНЫЕ — так было до переезда разбора сюда, и
# требование 2 не разрешает «заодно» их свести: отметка вызова в логе
# показывала Оператору прежде всего команду (`agent_log.render_block`),
# а ключ сравнения вызовов метрики трения — прежде всего файл
# (`agent_log._tool_use_calls`). Блок, несущий оба поля сразу, дал бы
# под сведёнными порядками другую строку лога или другое число трения.
LOG_ARGUMENT_KEYS = ("command", "file_path", "pattern")
CALL_ARGUMENT_KEYS = ("file_path", "command", "pattern")

# Сигнатуры провалов попытки (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требования
# 9-10) — дословно те же строки, что до задачи жили литералами в
# `orchestrator/failure_classification.py`. Снятые Оператором с логов
# инцидентов T043 (27.08) и T075-T078 (31.08); список класса 2 (session
# limit подписки) — версия 1, предположительная, без живого инцидента
# (tasks/T082/ANSWER-1.md). Классификация идёт по подстроке в
# объединённом stdout+stderr попытки, без учёта регистра.
#
# ПОРЯДОК ЗНАЧИМ и потому задан кортежем, а не отображением: специфичные
# списки обязаны перехватывать текст раньше общего якоря «API Error:»
# (иначе он забирал бы их в «системный кандидат»), а
# «модель не поддерживается» — раньше всех: отказ детерминирован (CLI
# старше модели), повторами не лечится, и любой из списков ниже увёл бы
# его в три попытки с минутным бэкоффом.
MODEL_UNSUPPORTED_SIGNATURE = "does not support this model"
FAILURE_SIGNATURES = (
    FailureSignature("model_unsupported", (MODEL_UNSUPPORTED_SIGNATURE,)),
    FailureSignature("1a", ("403", "failed to authenticate")),
    FailureSignature("1b", ("connection refused", "connectionrefused")),
    FailureSignature("stream_broken", ("connection lost mid-response",)),
    FailureSignature("session_limit", ("session limit", "usage limit",
                                       "5-hour limit", "resets at")),
    FailureSignature("system_candidate", ("api error:",)),
)

# Требуемая версия CLI из текста класса «модель не поддерживается»:
# «API Error: 400 … version 2.1.251 or newer is required» (инцидент
# 19.09). Формулировка своя у каждого CLI — потому и здесь.
MODEL_REQUIRED_VERSION_RE = re.compile(
    r"version\s+(\d+\.\d+\.\d+)\s+or newer is required", re.IGNORECASE)


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

    def secret_env_names(self):
        """Имена переменных, которыми приходит секрет этого провайдера
        (SPEC 01M32NH6P053978AER66P0X4GN, требование 12).

        Читателей два, и оба зовут набор по РЕЕСТРУ: `runner.role_env`
        вычитает эти имена из окружения шага роли на ЧУЖОМ провайдере (SPEC
        01M3F7BYE82S9AQCBSP1RTQQTR, требование 4), а строка
        `foreign-provider-secrets` сверяет отказом, что вычитание
        действует. Жёлтая строка смока Codex по этим же именам называет
        ambient-состояние машины Оператора — не окружение шага."""
        return SECRET_ENV_NAMES

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
        """Сверка модели роли с установленной версией CLI по каталогу
        моделей (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 3; SPEC
        01M3009Y9AGGY6ZCFA7H1HJ1TD, требование 10).

        Минимум версии CLI — поле записи модели в `models.yaml`; модели,
        которой в каталоге нет, соответствует `fail` (до 20.09 —
        предупреждение «модель не в таблице совместимости» и запуск как
        есть). `claude --version` не зовётся, пока модель не найдена в
        каталоге: подпроцесс ради заведомого отказа не нужен.

        Отказ разбора самого каталога (`ModelsError`) тоже `fail`, а не
        исключение наружу: точка вызова — предполёт шага, и он обязан
        назвать причину Оператору, а не уронить `run` трейсбеком.
        """
        from .. import models, stack
        try:
            entry = models.catalog_model(model)
        except models.ModelsError as exc:
            return stack.ModelCliVerdict(
                "fail", f"{stack.MODEL_UNSUPPORTED_PREFIX}: {exc}")
        return stack.model_cli_verdict(model, self.installed_cli_version(),
                                       entry.min_cli_version)

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

    # --- разбор вывода ----------------------------------------------------

    def parse_output_line(self, raw_line):
        """Строка `--output-format stream-json` -> `StreamEvent` (SPEC
        01M31ZHSA6HMH40C2JTDPQJQNZ, требования 1-2).

        Собрано из разбора, жившего до задачи в
        `agent_log.render_agent_line`/`render_block`/`_parse_stream_
        event`/`_tool_use_calls`/`_tool_results` и `spend.parse_cost_
        event`/`stream_usage_by_type`/`usage_tokens_by_type`: те же
        значения на тех же строках (AC-4..AC-7), но ОДНИМ проходом —
        до задачи одна строка потока разбиралась четырьмя независимыми
        функциями, и разойтись они могли молча.

        Строка, не начинающаяся с `{`, и строка с битым JSON — вывод,
        который CLI написал мимо формата событий (stderr агента,
        трейсбек): она уходит в лог КАК ЕСТЬ и ни на что больше не
        влияет. Молча не глотаем ничего.
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
        if kind == "assistant":
            return self._assistant_event(event)
        if kind == "user":
            return self._user_event(event)
        if kind == "result":
            return self._result_event(event)
        return EMPTY_EVENT

    @staticmethod
    def _passthrough(raw_line):
        """Строка мимо формата событий: в лог как есть, больше нигде."""
        return StreamEvent(raw_line, None, (), (), None, None)

    def _assistant_event(self, event):
        """`type: assistant`: текст, вызовы инструментов и учёт токенов.

        Учёт токенов снимается НЕЗАВИСИМО от блоков сообщения (у Claude
        он лежит в `message.usage`, а не в блоке): сообщение с
        нечитаемым `content` всё равно потратило токены.
        """
        message = event.get("message")
        message = message if isinstance(message, dict) else {}
        content = message.get("content")
        blocks = [b for b in content if isinstance(b, dict)] \
            if isinstance(content, list) else []

        texts = []
        calls = []
        rendered = []
        for block in blocks:
            rendered.append(self._render_block(block))
            if block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    texts.append(text)
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(
                    block.get("id"), block.get("name"),
                    self._tool_argument(block, CALL_ARGUMENT_KEYS)))
        return StreamEvent("".join(rendered),
                           "\n".join(texts) if texts else None,
                           tuple(calls), (),
                           self._tokens_by_kind(message.get("usage")), None)

    def _user_event(self, event):
        """`type: user`: результаты вызовов инструментов.

        В лог не идут намеренно (простыня вывода инструмента Оператору
        не нужна), но метрике трения шага нужны: там вызов и его
        результат смотрятся вместе — потому и отдельное поле события, а
        не «погасили и забыли».
        """
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return EMPTY_EVENT
        results = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = block.get("content")
            results.append(ToolResult(block.get("tool_use_id"),
                                      text if isinstance(text, str) else "",
                                      bool(block.get("is_error"))))
        return StreamEvent("", None, (), tuple(results), None, None)

    def _result_event(self, event):
        """`type: result`: итог запуска — разбивка, цена, признак ошибки.

        Цена отсутствует (поля нет, оно не число, отрицательное, `NaN`)
        — `usd is None`, а не ноль: «запуск ничего не стоил» и «CLI цены
        не сообщил» ветвятся по-разному в учёте стоимости (SPEC
        требование 4).
        """
        from .. import spend
        usd = spend.json_number(event.get("total_cost_usd"))
        if usd is not None and usd < 0:
            usd = None
        tokens_by_kind = self._tokens_by_kind(event.get("usage"))
        is_error = bool(event.get("is_error"))
        text = event.get("result")
        text = text if isinstance(text, str) else ("" if text is None
                                                   else str(text))
        log_text = (f"{ERROR_LINE_PREFIX}{text[:ERROR_TEXT_LIMIT]}\n"
                    if is_error else "")
        return StreamEvent(log_text, None, (), (), tokens_by_kind,
                           RunResult(tokens_by_kind, usd, is_error, text))

    @staticmethod
    def _tokens_by_kind(usage):
        """`usage` события -> разбивка по ОБЩИМ видам цены
        (`models.PRICE_KINDS`); `None` — ни одного известного счётчика.

        Только счётчики, реально присутствующие в событии (нулями за
        отсутствующие не дополняется): «вида не было» и «вид нулевой» —
        разные утверждения, и решает, что с этим делать, вызывающий.
        """
        if not isinstance(usage, dict):
            return None
        from .. import config
        counts = {}
        for key, kind in config.LEGACY_TOKEN_KIND_NAMES.items():
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                counts[kind] = value
        return counts or None

    @staticmethod
    def _tool_argument(block, keys):
        """Аргумент вызова инструмента по первому найденному ключу
        `keys` — см. `LOG_ARGUMENT_KEYS`/`CALL_ARGUMENT_KEYS` о том,
        почему порядков два."""
        args = block.get("input") or {}
        if not isinstance(args, dict):
            return ""
        for key in keys:
            value = args.get(key)
            if value:
                return value
        return ""

    @classmethod
    def _render_block(cls, block):
        """Блок сообщения ассистента -> строка Оператору (пустая — не
        показываем). Из потока событий Оператору нужны два: что агент
        сказал и что он делает инструментом, — по ним видно, работает
        шаг или встал."""
        kind = block.get("type")
        if kind == "text":
            text = block.get("text", "").strip()
            return f"{text}\n" if text else ""
        if kind == "tool_use":
            arg = cls._tool_argument(block, LOG_ARGUMENT_KEYS)
            flat = " ".join(str(arg).split())[:TOOL_ARGUMENT_LIMIT]
            return (f"{TOOL_CALL_LINE_PREFIX}{block.get('name')} "
                    f"{flat}").rstrip() + "\n"
        return ""

    # --- сигнатуры провалов ----------------------------------------------

    def failure_signatures(self):
        return FAILURE_SIGNATURES

    def required_cli_version(self, text):
        match = MODEL_REQUIRED_VERSION_RE.search(text)
        return match.group(1) if match else None
