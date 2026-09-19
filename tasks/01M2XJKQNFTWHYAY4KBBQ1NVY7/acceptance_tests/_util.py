"""Общие помощники планки 01M2XJKQNFTWHYAY4KBBQ1NVY7 (skills/
test-authoring.md: общий код нескольких файлов планки — только модуль
`_*.py` рядом с тестами).

Тонкая надстройка сценария поверх `tests/sandbox.py`: фикстуры ТЗ/SPEC,
сев упоминаемых путей во временный корень песочницы и перехват отказа
команды пульта. `disk_backed_*`/`advance_from_in_dev`/патчи `gitcmd`
здесь НЕ переопределяются — они берутся у
`tests.sandbox.LightTransitionSandbox` как есть.

Контракт, по которому планка ищет сборщик путей требования 1 (SPEC имени
функции не называет — только «живёт в `scripts/guard.py`»): сборщик
вызывается ОДНИМ позиционным аргументом-текстом
(`collector(text)` — прочие параметры, если они есть, обязаны иметь
значения по умолчанию) и возвращает коллекцию строк-путей.
"""
import inspect
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

# ------------------------------------------------------------ пути фикстур

# Путь, который фикстуры называют «где-то в тексте» — существующий модуль,
# заведомо не совпадающий с зоной фикстуры (`ZONE_PATH` ниже) и не
# покрытый ни одной общей зоной.
UNCLASSIFIED_PATH = "orchestrator/answer.py"
# Единственная зона фикстур по умолчанию.
ZONE_PATH = "orchestrator/catalog.py"
# Каталог-зона ВНЕ `config.COMMON_ZONES` и файл под ним: на этой паре
# вложенность «каталог покрывает файл» проверяется без подмены общими
# зонами (в отличие от пары `tests/` + `tests/test_foo.py` ниже, которая
# буквально названа в AC-5, но покрыта ещё и `COMMON_ZONES`).
NESTED_DIR_ZONE = "orchestrator/advance_gates/"
NESTED_DIR_FILE = "orchestrator/advance_gates/zones.py"
# Пара из формулировки AC-5 буквально.
SPEC_DIR_ZONE = "tests/"
SPEC_DIR_ZONE_FILE = "tests/test_foo.py"

# Значения — от `config`, не литералом (skills/test-authoring.md: крутилку
# Оператора тест обязан пережить). Общая зона-ФАЙЛ (не каталог): её
# достаточно назвать в тексте, чтобы путь был классифицирован без «Зоны:».
COMMON_ZONE_FILE = next(p for p in config.COMMON_ZONES if not p.endswith("/"))
# Защищённый каталог с обычным (без ведущей точки) именем и файл под ним:
# путь проверяется на попадание в `config.PROTECTED_PATHS` по вложенности,
# как `templates/SPEC.md` из формулировки AC-6.
PROTECTED_DIR = next(p for p in config.PROTECTED_PATHS
                     if p.endswith("/") and not p.startswith("."))
PROTECTED_FILE = PROTECTED_DIR + "SPEC.md"

# Всё, что фикстуры упоминают: сборщик оставляет только СУЩЕСТВУЮЩИЕ
# относительно `config.ROOT` пути (требование 1), а `config.ROOT`
# песочницы — временный каталог, где этих файлов нет, пока их не завести.
SEED_PATHS = (UNCLASSIFIED_PATH, ZONE_PATH, NESTED_DIR_FILE,
              SPEC_DIR_ZONE_FILE, COMMON_ZONE_FILE, PROTECTED_FILE)

# ------------------------------------------------------- тексты отказов

# Подсказка отказа по неклассифицированному пути (AC-2, тот же текст на
# гейте SPEC — AC-8): проверяется по фрагментам, а не целой фразой, чтобы
# сверка не зависела от того, какими кавычками разработчик обрамит
# названия разделов.
UNCLASSIFIED_HINT_FRAGMENTS = ("назови в Зонах", "Не входит", "Только чтение",
                               "Приложением")
# Отказ по защищённому пути в «Зоны:» (AC-6) — буквально из SPEC.
PROTECTED_REFUSAL_TEXT = "защищённый путь только приложением"


def assert_unclassified_refusal(testcase, text: str, path: str) -> None:
    """Отказ называет `path` и несёт подсказку требования 3."""
    testcase.assertIn(path, text,
                      f"отказ не называет неклассифицированный путь:\n{text}")
    for fragment in UNCLASSIFIED_HINT_FRAGMENTS:
        testcase.assertIn(fragment, text,
                          f"в подсказке отказа нет {fragment!r}:\n{text}")


def assert_no_unclassified_refusal(testcase, text: str) -> None:
    """В выводе нет отказа по неклассифицированному пути."""
    testcase.assertNotIn(UNCLASSIFIED_HINT_FRAGMENTS[0], text,
                         f"в выводе отказ по неклассифицированному пути:\n{text}")


# ------------------------------------------------------------- песочница

def seed_paths(root: Path, rels=SEED_PATHS) -> None:
    """Заводит перечисленные пути внутри `root` (корень песочницы)."""
    for rel in rels:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# фикстура планки: {rel}\n", encoding="utf-8")


def run_command(fn, *args) -> str:
    """Весь вывод вызова команды пульта одной строкой.

    Отказ команды — `sys.exit` с текстом ЛИБО печать + мягкий возврат
    (в кодовой базе живут оба стиля: `catalog.cmd_new` против
    `orchestrator/fsm.py::_approve_sha_ok`), поэтому текст собирается и
    из stdout/stderr, и из самого `SystemExit`, а «прошло или нет»
    тесты определяют по НАБЛЮДАЕМОМУ следу команды (строка задачи,
    состояние задачи), не по факту исключения: сам факт `SystemExit`
    формой отказа не является и в критериях не назван.
    """
    buf = io.StringIO()
    exit_exc = None
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:  # noqa: PERF203 — сам предмет проверки
            exit_exc = exc
    text = buf.getvalue()
    if exit_exc is not None and exit_exc.code not in (0, None):
        text = f"{text}\n{exit_exc.code}"
    return text


# ------------------------------------------------------------ фикстуры ТЗ

def tz_text(*, requires: str, zones: str, read_only: str = "",
            not_included: str = "", attachment: str = "") -> str:
    """Свободный текст ТЗ в формате сегодняшних ТЗ Оператора (образец —
    `tasks/01M2XFSE8G3MBRHHQR38H53J1M/TZ.md`, «Материалы» SPEC): строка
    «Зоны:» с начала строки, разделы «Только чтение (не менять):»,
    «Не входит:», «Приложением:» — свободным текстом после метки."""
    parts = ["Источник: фикстура приёмочной планки.", "",
             "Требуется:", f"1. {requires}", "",
             f"Зоны: {zones}"]
    if read_only:
        parts += ["", f"Только чтение (не менять): {read_only}"]
    if not_included:
        parts += ["", f"Не входит: {not_included}"]
    if attachment:
        parts += ["", f"Приложением: {attachment}"]
    parts += ["", "Рамка: $40."]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------- фикстуры SPEC

_SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 35
---

# SPEC: фикстура приёмочной планки

## Контекст

{context}

## Требования

1. {requirement}

## Критерии приёмки

AC-1. Фикстура планки.

## Не входит

{not_included}

## Материалы

{materials}
"""


def spec_text(task: str, *, zones: str = ZONE_PATH, context: str = "Фикстура.",
              requirement: str = "Фикстура.", not_included: str = "Ничего.",
              materials: str = "Нет.") -> str:
    """SPEC в формате `templates/SPEC.md`: классифицирующие множества —
    frontmatter `zones:`, «## Не входит», «## Материалы» (требование 5);
    проверяемые разделы — «## Контекст», «## Требования», «## Критерии
    приёмки» (требование 6)."""
    return _SPEC_TEMPLATE.format(task=task, zones=zones, context=context,
                                 requirement=requirement,
                                 not_included=not_included,
                                 materials=materials)


# --------------------------------------- обнаружение сборщика путей (AC-1)

def collector_results(text: str) -> dict:
    """{имя функции `scripts/guard.py`: множество возвращённых путей} —
    по всем функциям модуля, вызываемым одним позиционным аргументом и
    вернувшим коллекцию строк. Имя сборщика требования 1 SPEC не
    называет, поэтому планка ищет его по контракту (см. докстринг
    модуля), а не по имени."""
    results: dict = {}
    for name, obj in vars(guard).items():
        if name.startswith("__") or not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", None) != guard.__name__:
            continue
        params = [p for p in inspect.signature(obj).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len([p for p in params if p.default is p.empty]) != 1:
            continue
        try:
            value = obj(text)
        except Exception:  # noqa: BLE001 — чужая функция, не предмет теста
            continue
        if (isinstance(value, (set, frozenset, list, tuple))
                and all(isinstance(v, str) for v in value)):
            results[name] = set(value)
    return results


def collectors_matching(text: str, *, must_have: set, must_not_have: set) -> dict:
    """Подмножество `collector_results`, вернувшее все пути `must_have` и
    ни одного из `must_not_have`."""
    return {name: found for name, found in collector_results(text).items()
            if must_have <= found and not (must_not_have & found)}
