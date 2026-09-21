"""Общий код планки провайдера `codex`: то, что нужно больше чем одному
`test_*.py` (константы критериев, разбор `config.toml`, разбор `-c`
команды, раздел каталога моделей из приложения к PLAN).

Не песочница: собственных копий `disk_backed_*`/`advance_from_in_dev`
здесь нет — лёгкая песочница переходов планке не нужна, шаг роли берётся
готовым `_StepSandbox` из `tests/test_runner_model_preflight.py`.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

#: Идентификатор задачи — от имени каталога планки, не литералом: формат
#: идентификатора знает только генератор.
TASK_ID = Path(__file__).resolve().parents[1].name

#: Имя провайдера и его минимум версии CLI (AC-1, требование 6).
PROVIDER = "codex"
CLI_MINIMUM = (0, 155, 1)
CLI_MINIMUM_TEXT = "0.155.1"

#: Одиннадцать функций 0.155.1, выключаемых и командой шага (AC-4), и
#: курируемым `config.toml` (AC-9), и перечнем `docs/stack.md` (AC-20).
DISABLED_FEATURES = (
    "apps", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "computer_use", "in_app_browser",
    "plugins", "remote_plugin", "plugin_sharing",
    "skill_mcp_dependency_install", "hooks")

#: Пять моделей раздела `codex` каталога и их цены за миллион токенов
#: (AC-14, таблица требования 8): (input, output, cache_write, cache_read)
#: — порядок `models.PRICE_KINDS`, чтобы кортеж сравнивался с `Tariff` как
#: есть.
CODEX_PRICES = {
    "gpt-6-astra": (10.00, 50.00, 10.00, 1.00),
    "gpt-5.6-sol": (4.00, 20.00, 4.00, 0.40),
    "gpt-5.6-terra": (2.00, 12.00, 2.00, 0.20),
    "gpt-5.6-luna": (0.20, 1.20, 0.20, 0.02),
    "gpt-5.5": (5.00, 30.00, 5.00, 0.50),
}
CODEX_PRICE_DATE = "2026-09-21"

#: Модель шага в сценариях команды (AC-2, AC-3).
STEP_MODEL = "gpt-5.6-terra"


# --- курируемый `config.toml` -----------------------------------------

def role_home_reference_dir() -> Path:
    """Каталог референса курируемого дома роли `codex` в репозитории."""
    return REPO_ROOT / "docs" / "reference" / "role-home" / PROVIDER


def strip_toml_comment(line: str) -> str:
    """Строка `config.toml` без хвостового комментария: `#` вне кавычек."""
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


def toml_pairs(text: str) -> list:
    """[(полный ключ, сырое значение)] плоским списком: ключ секции
    приписывается точкой (`[sandbox_workspace_write]` + `network_access`
    -> `sandbox_workspace_write.network_access`), так что запись секцией и
    запись точечным ключом дают одну и ту же пару.

    Полноценный разбор TOML не нужен и намеренно не делается: критерии
    говорят про пары «ключ = значение», а не про типы значений.
    """
    pairs, section = [], ""
    for raw in text.splitlines():
        line = strip_toml_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().strip("[]").strip().strip('"')
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().strip('"')
        pairs.append((f"{section}.{key}" if section else key, value.strip()))
    return pairs


def toml_sections(text: str) -> list:
    """Имена секций `[...]`/`[[...]]` файла — для утверждений «ни одного
    MCP-сервера»."""
    return [strip_toml_comment(raw).strip().strip("[]").strip().strip('"')
            for raw in text.splitlines()
            if strip_toml_comment(raw).strip().startswith("[")]


def normalized(value: str) -> str:
    """Значение без кавычек и регистра — форма, в которой значение
    командной строки (`-c approval_policy=never`) сравнимо со значением
    файла (`approval_policy = "never"`)."""
    return value.strip().strip('"').strip("'").lower()


# --- команда шага ------------------------------------------------------

def config_overrides(argv: list) -> list:
    """[(ключ, нормализованное значение)] переопределений `-c ключ=значение`
    команды шага."""
    pairs = []
    for index, item in enumerate(argv):
        raw = None
        if item == "-c" and index + 1 < len(argv):
            raw = argv[index + 1]
        elif item.startswith("-c") and len(item) > 2 and "=" in item:
            raw = item[2:].lstrip("=") if item[2] == "=" else item[2:]
        if raw and "=" in raw:
            key, value = raw.split("=", 1)
            pairs.append((key.strip(), normalized(value)))
    return pairs


def value_positions(argv: list, value: str) -> list:
    """Индексы элементов argv, несущих значение `value`: отдельным
    элементом (`--sandbox workspace-write`) либо слитно
    (`--sandbox=workspace-write`). Написание флага — дело реализации,
    критерии говорят про само значение."""
    return [index for index, item in enumerate(argv)
            if item == value or item.endswith(f"={value}")]


def flag_positions(argv: list, flag: str) -> list:
    """Индексы элементов argv, которыми записан флаг `flag`: сам флаг,
    его форма через `=` и слитная короткая форма (`-cкл=зн`)."""
    short = len(flag) == 2 and not flag.startswith("--")
    return [index for index, item in enumerate(argv)
            if item == flag or item.startswith(f"{flag}=")
            or (short and item.startswith(flag) and len(item) > len(flag))]


def carries_flag_value(argv: list, flag: str, value: str) -> bool:
    """Команда несёт `flag value` — парой, через `=` или слитно."""
    pairs = [(argv[i], argv[i + 1]) for i in range(len(argv) - 1)]
    return ((flag, value) in pairs or f"{flag}={value}" in argv
            or f"{flag}{value}" in argv)


def carries_disable(argv: list, feature: str) -> bool:
    """Команда несёт выключение функции `feature`."""
    return carries_flag_value(argv, "--disable", feature)


# --- каталог моделей: приложение к PLAN ---------------------------------

def catalog_text_with_appendix() -> str:
    """Текст `models.yaml` с применённым приложением PLAN к нему.

    `models.yaml` — защищённый путь: ветка задачи его не правит, раздел
    `codex` приезжает приложением к PLAN, которое пульт применяет на
    мерже. Планка гоняется ДО мержа, поэтому раздел берётся из самого
    приложения; если приложение уже применено (прогон после мержа) —
    файл возвращается как есть.

    PLAN читается из АРТЕФАКТНОЙ ВЕТКИ (`gitcmd.show`), не с диска: в
    среде прогона гейта на диске лежит только `acceptance_tests/`.
    """
    base = config.MODELS.read_text(encoding="utf-8")
    if re.search(rf"^\s{{2}}{PROVIDER}:\s*$", base, re.MULTILINE):
        return base
    plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    if plan is None:
        raise AssertionError(
            f"PLAN задачи не прочитан из артефактной ветки: {reason}")
    appendices, errors = guard.plan_appendices(plan)
    patches = [a for a in appendices
               if any(path.endswith("models.yaml") for path in a.paths)]
    if not patches:
        raise AssertionError(
            "в PLAN нет приложения к models.yaml — раздел codex каталога "
            f"взять неоткуда (ошибки разбора приложений: {errors})")
    text = base
    for appendix in patches:
        text = apply_patch(text, appendix.diff)
    return text


def apply_patch(text: str, diff: str) -> str:
    """`text` с применённым unified-диффом `diff` к `models.yaml`."""
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        target = tdir / "models.yaml"
        target.write_text(text, encoding="utf-8")
        patch = tdir / "appendix.patch"
        patch.write_text(diff if diff.endswith("\n") else diff + "\n",
                         encoding="utf-8")
        res = subprocess.run(["git", "apply", str(patch)], cwd=tdir,
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError(
                f"приложение PLAN к models.yaml не применяется: "
                f"{res.stdout}{res.stderr}")
        return target.read_text(encoding="utf-8")


# --- окружение прогона --------------------------------------------------

def drop_ambient(test, *names) -> None:
    """Гасит ambient-переменные на время теста УДАЛЕНИЕМ, не пустым
    значением: белый список манифеста копирует и пустое значение, и
    утверждение «ключа в окружении роли нет» стало бы неотличимо от
    «ключ есть и пуст»."""
    patcher = mock.patch.dict(os.environ, {})
    patcher.start()
    test.addCleanup(patcher.stop)
    for name in names:
        os.environ.pop(name, None)


def discover_key_slot(test) -> str:
    """Имя слота keychain, у которого провайдер `codex` спрашивает ключ
    роли — снимается шпионом с самого провайдера, а не угадывается по
    имени константы: критерий говорит «именованная константа
    `orchestrator/config.py`», её имени не называя."""
    from orchestrator import keychain, providers

    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    home = mock.patch.object(config, "ROLE_HOME", Path(tmp.name))
    home.start()
    test.addCleanup(home.stop)
    drop_ambient(test, "OPENAI_API_KEY")
    slots = []

    def spy(slot):
        slots.append(slot)
        return ""

    token = mock.patch.object(keychain, "token", spy)
    token.start()
    test.addCleanup(token.stop)
    providers.get(PROVIDER).environment("developer", TASK_ID)
    if not slots:
        raise AssertionError("провайдер codex не спросил ключ у keychain")
    return slots[-1]
