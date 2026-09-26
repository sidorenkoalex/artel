"""Общий код планки 01M3EKCZJY9NGCW6VT878RX9JZ — константы и разбор,
нужные больше чем одному `test_*.py` (скил test-authoring: общий код
планки живёт ТОЛЬКО в модулях `_*.py` рядом с тестами).

Ничего из артефактов задачи здесь не читается: предметы планки — код
пульта (`orchestrator/`), референс дома роли
(`docs/reference/role-home/codex/`), `docs/stack.md` и `models.yaml`,
то есть файлы КОДОВОЙ ветки, которые в среде прогона гейта лежат на
месте (`cwd` прогона — рабочий каталог кода задачи,
`orchestrator/acceptance.py::run`).
"""
import os
import sys
from pathlib import Path
from unittest import mock

# Корень рабочей копии кода: acceptance_tests -> <id> -> tasks -> корень.
REPO_ROOT = Path(__file__).resolve().parents[3]

sys.path.insert(0, str(REPO_ROOT))

# Пин, с которым требование 9/AC-15 сверяет шаг роли на Claude.
PIN = "fd83eb5d"

# Пары авторизации, которые требование 1 добавляет и команде шага, и
# курируемому `config.toml` дома роли (AC-1, AC-2).
AUTH_OVERRIDES = (
    ("cli_auth_credentials_store", "keyring"),
    ("forced_login_method", "chatgpt"),
)

# Прежние `-c`-пары команды шага, которые обязаны остаться (AC-1).
LEGACY_OVERRIDES = (
    ("sandbox_workspace_write.network_access", "false"),
    ("approval_policy", "never"),
)

# Одиннадцать функций 0.155.1, выключаемых флагом `--disable` (AC-1):
# ЛИТЕРАЛОМ, а не через константу провайдера — критерий требует, чтобы
# перечень остался прежним, а сверка с той же константой, которую могли
# переименовать, этого не доказывает.
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

# Три имени, которых не должно быть ни в белом списке, ни в собранном
# окружении шага (требования 2, 3, 5; AC-3, AC-4, AC-11).
FORBIDDEN_ENV_NAMES = ("OPENAI_API_KEY", "CODEX_API_KEY",
                       "CODEX_ACCESS_TOKEN")

# Имя константы слота и сама запись keychain, которые требование 2
# удаляет из кода пульта (AC-5). Сам этот файл живёт под `tasks/` и в
# просматриваемый AC-5 набор (`pult_code_files`) не входит.
SLOT_CONST_NAME = "OPENAI_API_KEY_SLOT"
SLOT_RECORD_NAME = "artel-openai-api-key"

# Имя проверки предполёта, заменяющей `codex-api-key` (AC-6..AC-10).
AUTH_CHECK = "codex-chatgpt-auth"
OLD_CHECK = "codex-api-key"

# Секреты провайдера по умолчанию: гасятся в сценариях, где предмет —
# окружение шага Codex, чтобы жёлтая строка про ЧУЖОЙ секрет не
# перекрывала предмет теста.
CLAUDE_SECRETS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")

STUB_BIN = "/artel-test-stub-bin"


# Каталог референса курируемого дома роли `codex` в репозитории.
CODEX_REFERENCE_DIR = REPO_ROOT / "docs" / "reference" / "role-home" / "codex"

# Раздел `docs/stack.md`, который требование 7 переписывает (AC-13).
STACK_DOC = REPO_ROOT / "docs" / "stack.md"
STACK_DOC_SECTION = "Провайдер codex"


def codex_reference(name: str) -> Path:
    """Файл референса курируемого дома роли `codex` в репозитории."""
    return CODEX_REFERENCE_DIR / name


def drop_ambient(test, *names) -> None:
    """Гасит ambient-переменные УДАЛЕНИЕМ, не пустым значением: белый
    список манифеста копирует и пустое значение, и «переменной нет»
    стало бы неотличимо от «переменная есть и пуста» (тот же приём, что
    `tests/test_providers_codex.py::_drop_ambient`)."""
    patcher = mock.patch.dict(os.environ, {})
    patcher.start()
    test.addCleanup(patcher.stop)
    for name in names:
        os.environ.pop(name, None)


def patch(test, target, attr, value):
    """`mock.patch.object`, снимаемый штатным `addCleanup`."""
    patcher = mock.patch.object(target, attr, value)
    patcher.start()
    test.addCleanup(patcher.stop)
    return value


def stub_tool_path(test):
    """Резолв объявленных инструментов манифеста — заглушкой: настоящий
    `codex` на машине прогона не нужен и не запускается."""
    return patch(test, _runner(), "declared_tool_path",
                 lambda name: f"{STUB_BIN}/{name}")


def _runner():
    from orchestrator import runner
    return runner


def codex_command(model=None) -> list:
    """Реально собранная команда шага роли на Codex — та же точка, что
    зовёт `runner._spawn_and_wait`, а не своя копия списка флагов."""
    from orchestrator import providers
    return providers.get("codex").command(model)


def config_overrides(argv) -> dict:
    """{ключ: значение} `-c`-переопределений команды: пара идёт СЛЕДОМ за
    флагом (`-c key=value`) либо слитно (`-c=key=value`)."""
    pairs = {}
    for index, item in enumerate(argv):
        payload = None
        if item == "-c" and index + 1 < len(argv):
            payload = argv[index + 1]
        elif item.startswith("-c="):
            payload = item[len("-c="):]
        if payload is None or "=" not in payload:
            continue
        key, _, value = payload.partition("=")
        pairs[key.strip()] = value.strip().lower()
    return pairs


def carries_pair(argv, key: str, value: str) -> bool:
    """Argv несёт пару «ключ=значение» отдельным элементом или хвостом
    через `=` — написание флага дело вызывающего кода, предмет проверки
    сама пара (тот же приём, что `doctor/isolation.py::_carries_value`).
    """
    wanted = f"{key}={value}"
    return any(item == wanted or item.endswith(f"={wanted}")
               or item.endswith(f" {wanted}") for item in argv)


def squashed(text: str) -> str:
    """Текст в нижнем регистре, у которого любая цепочка пробельных
    символов сведена к одному пробелу: markdown переносит абзацы по
    ширине, и искать в нём словосочетание построчно нельзя — перенос
    строки внутри фразы не дефект документации."""
    return " ".join(text.lower().split())


def strip_comment(line: str) -> str:
    """Строка TOML без концевого комментария: `#` внутри кавычек
    комментарием не считается."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def toml_pairs(text: str) -> dict:
    """{полный ключ: значение без кавычек, в нижнем регистре} TOML-текста:
    имя секции приписывается точкой, так что запись секцией и точечный
    ключ дают одну и ту же пару."""
    pairs, section = {}, ""
    for raw in text.splitlines():
        line = strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        full = f"{section}.{key.strip()}" if section else key.strip()
        pairs[full] = value.strip().strip('"').strip("'").lower()
    return pairs


def pult_code_files() -> list:
    """Файлы КОДА пульта: `orchestrator/`, `scripts/` и модули верхнего
    уровня. `tests/` сюда не входит намеренно — регрессия, фиксирующая
    исчезновение имени, вправе называть само имя (AC-5 называет только
    пути пульта); `docs/research/` — тем более (SPEC: история слота там
    остаётся)."""
    files = sorted(REPO_ROOT.glob("*.py"))
    for directory in ("orchestrator", "scripts"):
        files.extend(sorted((REPO_ROOT / directory).rglob("*.py")))
    return files
