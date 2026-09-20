"""Обнаружение функции разбора приложений PLAN.md (требование 1, AC-1..AC-4)
и фикстуры её входного текста — планка задачи 01M2YSHDKWFJN3XSJ618Z74FNF.

Имени функции SPEC не называет («Функция в `scripts/guard.py` (рядом с
`section_body`)»), поэтому планка ищет её ПО КОНТРАКТУ, а не по имени —
тем же приёмом, что `tasks/01M2XJKQNFTWHYAY4KBBQ1NVY7/acceptance_tests/
_util.py::collectors_matching` для сборщика путей той задачи.

Контракт, которому обязана удовлетворять реализация:

- функция живёт в `scripts/guard.py` и вызывается ОДНИМ позиционным
  аргументом — текстом PLAN.md (прочие параметры, если они есть, обязаны
  иметь значения по умолчанию);
- приложения возвращаются СПИСКОМ в порядке появления в тексте; элемент
  списка — не строка, а составное значение (кортеж/NamedTuple/dict/
  объект), из которого читаются и путь заголовка `diff --git`, и текст
  диффа. Список приложений — либо сам возврат, либо элемент возвращённой
  пары «(приложения, ошибки)»;
- ошибки требования 1 — строки; планка признаёт их в любом месте
  возврата (второй элемент пары, поле элемента) и даже в тексте
  исключения, если реализация предпочтёт бросать его: сверяется НАЛИЧИЕ
  именованного текста, а не форма контейнера.

Из-за этой свободы формы helpers ниже собирают строки РЕКУРСИВНО и
сверяют их множеством: сверка «вернулось ровно то, что называет
критерий» остаётся точной (путь, текст диффа, именованный текст
ошибки), а выбор контейнера остаётся за разработчиком.
"""
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

# ------------------------------------------------------------------ пути

# Защищённый путь фикстур — от `config.PROTECTED_PATHS`, не литералом
# (skills/test-authoring.md: предпосылки о конфигурации пишутся
# динамически, крутилку Оператора тест обязан пережить). Нужен
# защищённый путь-ФАЙЛ вне `tests/` и `.github/`: такое приложение по
# AC-11 не требует полного прогона, и на нём же проверяется разбор.
PROTECTED_FILE = next(p for p in config.PROTECTED_PATHS
                      if not p.endswith("/")
                      and not p.startswith("tests/")
                      and not p.startswith(".github"))
# Второй защищённый путь — для сценария «несколько приложений».
PROTECTED_FILE_2 = next(p for p in config.PROTECTED_PATHS
                        if not p.endswith("/") and p != PROTECTED_FILE
                        and not p.startswith("tests/")
                        and not p.startswith(".github"))
# Защищённый путь под `tests/` (требование 5/AC-10: приложение к `tests/`
# требует полного прогона). Каталог `tests/` целиком защищённым НЕ
# является — под запретом именно этот файл, и он же начинается с `tests/`.
PROTECTED_TESTS_FILE = next(p for p in config.PROTECTED_PATHS
                            if p.startswith("tests/"))
# Защищённый путь под `.github/` (второй триггер требования 5): сам
# элемент списка — каталог, поэтому файл под ним дописывается.
PROTECTED_GITHUB_DIR = next(p for p in config.PROTECTED_PATHS
                            if p.startswith(".github"))
PROTECTED_GITHUB_FILE = PROTECTED_GITHUB_DIR.rstrip("/") + "/workflows/ci.yml"

# Путь ВНЕ `config.PROTECTED_PATHS` (AC-3) — проверяется утверждением
# ниже, а не на глаз: список защищённых путей меняет Оператор.
UNPROTECTED_FILE = "docs/appendix_probe.md"
assert not any(UNPROTECTED_FILE == p or UNPROTECTED_FILE.startswith(p)
               for p in config.PROTECTED_PATHS), (
    f"фикстура AC-3 сломана: {UNPROTECTED_FILE} попал в "
    f"config.PROTECTED_PATHS")

# ------------------------------------------------- именованные тексты SPEC

# Ошибки требования 1 (AC-2/AC-3) — дословно из формулировок критериев.
NO_HEADER_ERROR = "приложение PLAN: нет заголовка diff --git"


def unprotected_error(path: str) -> str:
    return (f"приложение PLAN: путь {path} не защищённый — правь в ветке "
            f"задачи")


# ----------------------------------------------------------- фикстуры PLAN

_PLAN_HEAD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: приложения к защищённым путям

## Подход

Разбор приложений PLAN.md и их применение пультом.

## Шаги

1. Шаг фикстуры.

## Покрытие требований

Требование 1 — шаг 1.

## Влияние на систему

Фикстура приёмочной планки.
"""

_APPENDIX_SECTION = """
## Приложение{suffix}

Обоснование: правка защищённого пути, которую роль вносить не вправе.

{blocks}"""


def diff_block(path: str, marker: str, *, header: bool = True,
               old_line: str = "строка базы") -> str:
    """Блок ```diff одного приложения. `header=False` — блок без строки
    `diff --git` (сценарий AC-2). `marker` — уникальный текст добавляемой
    строки: по нему тест отличает текст ОДНОГО приложения от соседнего.
    """
    header_line = f"diff --git a/{path} b/{path}\n" if header else ""
    return ("```diff\n"
            f"{header_line}"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            "@@ -1,2 +1,2 @@\n"
            f"-{old_line}\n"
            f"+{marker}\n"
            " хвост базы\n"
            "```\n")


def plan_text(task: str, sections: list[str] | None = None) -> str:
    """PLAN.md фикстуры: `sections` — готовые разделы «## Приложение …»
    (`appendix_section` ниже); `None`/пустой список — PLAN без приложений
    (AC-4/AC-13)."""
    return _PLAN_HEAD.format(task=task) + "".join(sections or [])


def appendix_section(blocks: list[str], suffix: str = "") -> str:
    """Раздел PLAN.md, заголовок которого НАЧИНАЕТСЯ на «## Приложение»
    (требование 1: именно префикс, а не точное имя раздела), с
    перечисленными блоками ```diff внутри."""
    return _APPENDIX_SECTION.format(suffix=suffix,
                                    blocks="\n".join(blocks))


# ------------------------------------------------------- обнаружение разбора

def _one_positional_functions():
    """Функции `scripts/guard.py`, вызываемые одним позиционным
    аргументом (прочие параметры — со значениями по умолчанию)."""
    found = []
    for name, obj in vars(guard).items():
        if name.startswith("__") or not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != guard.__name__:
            continue
        params = [p for p in inspect.signature(obj).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len([p for p in params if p.default is p.empty]) != 1:
            continue
        found.append((name, obj))
    return found


def call(name: str, text: str):
    """(значение, текст исключения) вызова `guard.<name>(text)` — обе
    формы отчёта об ошибке (возврат и исключение) наблюдаются одинаково."""
    try:
        return getattr(guard, name)(text), ""
    except Exception as exc:  # noqa: BLE001 — чужая функция, не предмет теста
        return None, f"{type(exc).__name__}: {exc}"


def strings_in(value) -> list[str]:
    """Все строки значения, рекурсивно — включая поля NamedTuple/dict/
    обычного объекта (`__dict__`)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings_in(v)]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [s for v in value for s in strings_in(v)]
    fields = getattr(value, "_asdict", None)
    if callable(fields):
        return strings_in(fields())
    slots = getattr(value, "__dict__", None)
    if isinstance(slots, dict):
        return strings_in(slots)
    return []


def _appendix_lists(value) -> list[list]:
    """Все вложенные списки значения, годящиеся на «список приложений»:
    каждый элемент — НЕ строка и несёт хотя бы одну строку. Пустой список
    тоже годится (AC-4). Порядок элементов сохраняется."""
    found = []
    if isinstance(value, (list, tuple)):
        items = list(value)
        if all(not isinstance(i, str) and strings_in(i) for i in items):
            found.append(items)
        for item in items:
            found.extend(_appendix_lists(item))
    return found


def appendix_lists(name: str, text: str) -> list[list]:
    value, _exc = call(name, text)
    return _appendix_lists(value)


def all_strings(name: str, text: str) -> list[str]:
    """Строки возврата + текст исключения — множество, в котором тест
    ищет именованную ошибку требования 1."""
    value, exc = call(name, text)
    return strings_in(value) + ([exc] if exc else [])


def _matches(name: str, text: str, wanted: list[tuple[str, str]]) -> bool:
    """`True` — вызов `guard.<name>(text)` вернул список приложений,
    где по каждому ожидаемому (путь, маркер) есть свой элемент, в том же
    порядке, и длина списка совпадает с ожидаемой."""
    for items in appendix_lists(name, text):
        if len(items) != len(wanted):
            continue
        if all(any(path in s for s in strings_in(item))
               and any(marker in s for s in strings_in(item))
               and any(f"diff --git a/{path} b/{path}" in s
                       for s in strings_in(item))
               for item, (path, marker) in zip(items, wanted)):
            return True
    return False


def parsers(text: str, wanted: list[tuple[str, str]]) -> list[str]:
    """Имена функций `scripts/guard.py`, удовлетворяющих контракту разбора
    на тексте `text` с ожидаемыми приложениями `wanted` (список пар
    «путь, уникальный маркер строки диффа», в порядке появления)."""
    return [name for name, _obj in _one_positional_functions()
            if _matches(name, text, wanted)]


def report(text: str) -> dict:
    """{имя: возврат либо текст исключения} по всем кандидатам — для
    текста провала: Оператор и разработчик видят, что реально вернули
    функции модуля."""
    report_map = {}
    for name, _obj in _one_positional_functions():
        value, exc = call(name, text)
        report_map[name] = exc or value
    return report_map
