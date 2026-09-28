"""Общий код приёмочной планки 01M3KE9FZ1YZS5WD5K9M8EKN37 (глубина
рассуждения клиента Codex).

Не `test_*.py` и не копия песочницы переходов: сценариев FSM в этой
планке нет вовсе — проверяются argv команды шага, курируемый образец
настроек дома роли и два текста (комментарий у константы,
`docs/stack.md`). Сюда вынесено ровно то, что нужно больше чем одному
файлу `test_ac*.py` рядом: разбор TOML образца, сборка argv с
подменённым резолвом инструмента и чтение текстов.

Имя с подчёркиванием обязательно: `scripts/guard.py` признаёт на первом
уровне `acceptance_tests/` только `test_*.py`, `markers.py`,
`__init__.py`, `*.md`, `*.txt` и модули `_*.py` — файл с другим именем
checkpoint отбрасывает, а выход из `tests_writing` потом отказывает
переходом «планка ссылается на отброшенные файлы» (регрессия №18).
"""
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

# Корень рабочего дерева кода: планка материализуется в
# `tasks/<id>/acceptance_tests/` того же дерева, в котором гейт
# acceptance гоняет тесты (`orchestrator/acceptance.py::
# materialize_from_branch`), поэтому три уровня вверх — репозиторий.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, providers, runner  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

# Пара из формулировки критериев AC-1/AC-2 — литералом, а не ссылкой на
# константу реализации: планка проверяет ИМЕННО эти ключ и значение, а
# ссылка на константу сделала бы обе проверки тавтологией.
REASONING_KEY = "model_reasoning_effort"
REASONING_VALUE = "high"

# Подставной каталог резолва манифеста: настоящий `codex` на машине
# прогона не нужен и не запускается ни разу.
STUB_BIN = "/artel-plank-stub-bin"

# Модель шага — любая из раздела `codex` каталога; на сборку `-c`-флагов
# её имя не влияет, оно уезжает в `-m` после подкоманды.
STEP_MODEL = "gpt-6-astra"

CURATED_CONFIG_NAME = "config.toml"
STACK_DOC = ("docs", "stack.md")
CODEX_STACK_SECTION = "Провайдер codex"


def _strip_comment(line: str) -> str:
    """Строка без хвостового комментария TOML; `#` внутри кавычек —
    часть значения, а не начало комментария."""
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


def toml_entries(text: str) -> list:
    """[(секция, ключ, значение без кавычек), ...] курируемого TOML.

    Секция сохраняется ОТДЕЛЬНЫМ элементом, а не приписывается к ключу
    точкой: AC-2 требует различать ключ верхнего уровня файла (секция —
    пустая строка) от того же имени внутри секции.
    """
    entries, section = [], ""
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries.append((section, key.strip(),
                        value.strip().strip('"').strip("'")))
    return entries


def curated_config_path() -> Path:
    """Путь курируемого образца настроек дома роли — через сам провайдер
    (`home_reference()`), а не литералом: адрес референса знает
    провайдер, и подмена `config.ROOT` мутацией AC-3 обязана доехать
    сюда тем же путём, что и до тестов `tests/`."""
    return providers.get("codex").home_reference().reference \
        / CURATED_CONFIG_NAME


def curated_config_text() -> str:
    return curated_config_path().read_text(encoding="utf-8")


def codex_source() -> str:
    """Исходный текст `orchestrator/providers/codex.py` — от самого
    импортированного модуля, а не от собранного руками пути."""
    return Path(inspect.getsourcefile(codex_provider)).read_text(
        encoding="utf-8")


def stack_doc_text() -> str:
    path = REPO_ROOT
    for part in STACK_DOC:
        path = path / part
    return path.read_text(encoding="utf-8")


def markdown_section(text: str, title: str) -> str:
    """Текст раздела `## <title>` до следующего заголовка того же или
    более высокого уровня; пустая строка — раздела нет."""
    lines, collected, inside = text.splitlines(), [], False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == title
            continue
        if line.startswith("# ") and inside:
            break
        if inside:
            collected.append(line)
    return "\n".join(collected)


def paragraphs(text: str) -> list:
    """Абзацы текста — куски, разделённые пустой строкой."""
    blocks, current = [], []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def stub_tool_path(testcase) -> list:
    """Подменяет резолв инструмента манифеста на подставной путь и
    отдаёт список спрошенных имён (пополняется по ходу вызовов)."""
    asked = []

    def _path(name: str) -> str:
        asked.append(name)
        return f"{STUB_BIN}/{name}"

    patcher = mock.patch.object(runner, "declared_tool_path", _path)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return asked


def step_argv(testcase, provider_name: str = "codex",
              model: str = STEP_MODEL) -> list:
    """Argv команды шага провайдера с подменённым резолвом инструмента."""
    stub_tool_path(testcase)
    return providers.get(provider_name).command(model)


def dash_c_values(argv: list) -> list:
    """Значения всех `-c`-флагов argv в порядке появления."""
    return [argv[i + 1] for i, item in enumerate(argv)
            if item == "-c" and i + 1 < len(argv)]


def named_string_constants(module, value: str) -> list:
    """Имена констант модуля (ВЕРХНИЙ_РЕГИСТР), равных строке `value`."""
    return sorted(name for name, item in vars(module).items()
                  if name.isupper() and isinstance(item, str)
                  and item == value)


def run_test_case(cls, method_name: str) -> unittest.TestResult:
    """Прогоняет ОДИН метод чужого TestCase и отдаёт его результат."""
    result = unittest.TestResult()
    cls(method_name).run(result)
    return result


def run_suite(suite) -> unittest.TestResult:
    result = unittest.TestResult()
    suite.run(result)
    return result


def reference_copy_without_reasoning(tdir: Path) -> Path:
    """Копия дерева референса дома роли во временном каталоге `tdir`, из
    образца которой снята строка глубины рассуждения, — и корень пульта
    для неё.

    Дерево копируется целиком по частям `HOME_REFERENCE_DIR`, чтобы
    подменённый `config.ROOT` вёл к тому же адресу, что и настоящий:
    мутация AC-3 обязана отличаться от оригинала РОВНО одной снятой
    настройкой, а не отсутствующим каталогом.
    """
    import shutil

    root = tdir / "pult"
    source = providers.get("codex").home_reference().reference
    target = root
    for part in codex_provider.HOME_REFERENCE_DIR:
        target = target / part
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    config_path = target / CURATED_CONFIG_NAME
    kept = [line for line in config_path.read_text(
        encoding="utf-8").splitlines()
        if not line.strip().startswith(REASONING_KEY)]
    config_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return root


def patched_root(testcase, root: Path) -> None:
    patcher = mock.patch.object(config, "ROOT", root)
    patcher.start()
    testcase.addCleanup(patcher.stop)
