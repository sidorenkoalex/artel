#!/usr/bin/env python3
"""Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные
секции). Содержательность не проверяет — это работа гейтов и людей (§04).

Использование:
    python3 scripts/guard.py tasks/T001/SPEC.md [ещё файлы...]
    python3 scripts/guard.py --all          # все артефакты в tasks/
Выход: 0 — ок, 1 — есть нарушения (список в stdout).
"""
import re
import sys
from pathlib import Path

# Файл живёт двумя жизнями — скрипт и модуль (`from scripts import guard`
# в тестах и в FSM). У скрипта в sys.path лежит scripts/, а не корень
# репозитория, поэтому корень кладётся руками: та же схема, что в artel.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import yamlmini  # noqa: E402

REQUIRED_META = {"task", "type", "author_role", "status"}

# Версия формата артефактов, которую понимает этот guard. Артефакт без поля
# `schema_version` — версия 1: файлы Фазы 0 (T001–T016) писались до его
# появления и остаются валидными. Артефакт версии выше — ошибка: его писал
# более новый формат, и молча читать его старыми правилами значит менять
# сбой проверки на чужой сбой позже (SPEC T017, требование 3).
#
# Версия 2 (tasks/T023): SPEC несёт AC-разметку критериев приёмки
# (`AC-1.`, `AC-2.`, …) и необязательное поле `skip_tests`. Правило
# применяется только к version >= 2 — весь беклог T001–T022 остаётся
# версией 1 и валиден без правок (требование 7).
SUPPORTED_SCHEMA_VERSION = 2

RULES = {
    "spec": {
        "sections": ["Контекст", "Требования", "Критерии приёмки", "Не входит"],
        "statuses": {"draft", "ready", "approved"},
    },
    "plan": {
        "sections": ["Подход", "Шаги", "Покрытие требований",
                     "Влияние на систему"],  # принцип целостности (ADR-0002)
        "statuses": {"draft", "ready", "approved"},
    },
    "review": {
        "sections": ["Соответствие SPEC", "Замечания", "Вердикт"],
        "statuses": {"draft", "approved", "changes_requested", "escalate"},
    },
    "test_report": {
        "sections": ["Матрица критериев", "Вердикт"],
        "statuses": {"draft", "passed", "failed"},
    },
    # ТЗ Оператора (tasks/T025, A5): тело свободное — секций не требуется,
    # структурный контракт исчерпывается фронтматтером (общим для всех
    # типов, см. REQUIRED_META).
    "tz": {
        "sections": [],
        "statuses": {"draft", "ready"},
    },
    # Батч вопросов analyst при неясном ТЗ (tasks/T025, требование 4):
    # содержательность батча (варианты, дефолт, сортировка по
    # блокирующести) — не дело guard'а (докстринг модуля), только форма.
    "questions": {
        "sections": ["Вопросы"],
        "statuses": {"draft", "ready"},
    },
}


def schema_errors(path: Path, meta: dict) -> list[str]:
    """Совместимость версии схемы артефакта с этим guard'ом."""
    if "schema_version" not in meta:
        return []  # артефакт до T017 — версия 1 по определению
    version = meta["schema_version"]
    # bool — подтип int, а `schema_version: true` версией не является.
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return [f"{path}: schema_version '{version}' — не целое число ≥ 1"]
    if version > SUPPORTED_SCHEMA_VERSION:
        return [f"{path}: schema_version {version} новее поддерживаемой "
                f"{SUPPORTED_SCHEMA_VERSION} — артефакт написан более новым "
                f"форматом, обнови guard"]
    return []


# --------------------------------------------------------------------------
# AC-разметка SPEC и трассируемость AC -> тест (tasks/T023, A4).
#
# Обе проверки статические: разбор текста регулярными выражениями, без
# импорта/исполнения .py-файлов — тем же принципом, каким остальной guard
# проверяет структуру, а не содержательность (докстринг модуля выше).
# Прогон самих тестов (SPEC T023, требование 6) — отдельно,
# orchestrator/acceptance.py, не здесь.

# Критерий раздела «Критерии приёмки»: `AC-<n>. текст` строго в начале строки.
AC_ITEM = re.compile(r"^AC-(\d+)\.\s+\S", re.M)
# Пункт нумерованного списка БЕЗ AC-разметки — старый формат ("1. ...", не
# "AC-1. ..."), который не должен молча проходить в SPEC версии 2.
PLAIN_NUMBERED_ITEM = re.compile(r"^\d+\.\s+\S", re.M)
# Тест на AC-n: метод `test_ac<n>_...` в любом test_*.py под acceptance_tests/.
TEST_AC = re.compile(r"def\s+test_ac(\d+)_\w*\s*\(")
# Любой тестовый метод — для числа в сводке гейта (orchestrator/acceptance.py).
# Регуляркой, не `unittest.TestLoader().discover()`: discover импортирует
# модули по голому имени файла в sys.modules процесса, и второй прогон
# в том же процессе на ДРУГОМ каталоге с файлом того же имени (обычное дело
# для test_*.py разных задач) падает ImportError «incorrectly imported
# from» — collect-only обязан быть статическим, не только по духу guard'а,
# но и чтобы не зависеть от истории вызовов процесса.
TEST_METHOD = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.M)
# Пометка критерия без прямого теста: `# AC-n: manual|skip|escalate — причина`.
AC_MARKER = re.compile(
    r"#\s*AC-(\d+):\s*(manual|skip|escalate)\b[^\S\n]*(?:[—-]+[^\S\n]*(.*))?")


def _section_body(text: str, name: str) -> str:
    """Текст секции `## name` до следующего `## ` заголовка или конца файла."""
    match = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
    return match.group(1) if match else ""


def requires_ac_markup(meta: dict) -> bool:
    """SPEC обязан нести AC-разметку и пройти tests_writing.

    Версия ниже 2 — SPEC написан до A4, разметки не несёт и не обязан
    (требование 7). `skip_tests` — явный пропуск стадии (требование 2):
    его причина не пуста ни пустой строкой, ни отсутствием значения.
    """
    version = meta.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 2:
        return False
    return meta.get("skip_tests") in (None, "")


def spec_ac_errors(path: Path, text: str, meta: dict) -> list[str]:
    """AC-разметка раздела «Критерии приёмки» (SPEC T023, требования 2, 7)."""
    if not requires_ac_markup(meta):
        return []
    body = _section_body(text, "Критерии приёмки")
    ac_numbers = [int(n) for n in AC_ITEM.findall(body)]
    if not ac_numbers:
        return [f"{path}: критерии приёмки не размечены AC-n (AC-1., AC-2., "
                f"…) — либо укажи skip_tests в frontmatter"]
    if len(set(ac_numbers)) != len(ac_numbers):
        return [f"{path}: номера AC-n повторяются: {ac_numbers}"]
    if PLAIN_NUMBERED_ITEM.search(body):
        return [f"{path}: в критериях приёмки остались пункты без "
                f"AC-разметки"]
    return []


def scan_acceptance_tests(tdir: Path) -> tuple[set, dict]:
    """(AC, покрытые тестом) и {AC: (пометка, причина)} из acceptance_tests/.

    Статический разбор текстом, без импорта файлов — теста без разметки
    `test_ac<n>_` парсер не увидит, и это осознанно: содержательность
    (тест действительно проверяет то, что заявляет) — дело ревью и прогона
    unittest на гейте (orchestrator/acceptance.py), не структурной проверки.
    """
    tests_dir = tdir / "acceptance_tests"
    tested: set = set()
    markers: dict = {}
    if not tests_dir.is_dir():
        return tested, markers
    for f in sorted(tests_dir.rglob("*.py")):
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        tested.update(int(n) for n in TEST_AC.findall(content))
        for n, kind, reason in AC_MARKER.findall(content):
            markers[int(n)] = (kind, reason.strip())
    return tested, markers


def count_test_methods(tdir: Path) -> int:
    """Число тестовых методов в acceptance_tests/*.py — статический счёт."""
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return 0
    count = 0
    for f in sorted(tests_dir.rglob("*.py")):
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        count += len(TEST_METHOD.findall(content))
    return count


def acceptance_traceability_errors(tdir: Path) -> list[str]:
    """AC без теста и без пометки — невалидный выход из tests_writing
    (SPEC T023, требование 4).

    SPEC без AC-разметки (версия 1 или `skip_tests`) — tests_writing эту
    задачу не проходит, сверять нечего.
    """
    spec_path = tdir / "SPEC.md"
    try:
        text = spec_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{spec_path}: не прочитан: {exc}"]
    meta = yamlmini.frontmatter(text) or {}
    if not requires_ac_markup(meta):
        return []
    ac_numbers = {int(n) for n in
                 AC_ITEM.findall(_section_body(text, "Критерии приёмки"))}
    tested, markers = scan_acceptance_tests(tdir)

    errors: list[str] = []
    for n in sorted(ac_numbers):
        if n not in tested and n not in markers:
            errors.append(f"AC-{n}: нет теста и нет пометки manual/skip")
    for n, (kind, reason) in sorted(markers.items()):
        if n not in ac_numbers:
            errors.append(f"AC-{n}: пометка на критерий, которого нет в SPEC")
        elif kind in ("skip", "escalate") and not reason:
            errors.append(f"AC-{n}: пометка {kind} без причины")
    for n in sorted(tested):
        if n not in ac_numbers:
            errors.append(f"AC-{n}: тест на критерий, которого нет в SPEC "
                          f"(SPEC T023, требование 3 — только из критериев)")
    return errors


def check(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Guard зовётся не только из CLI, но и из FSM на переходах (T017,
        # требование 5), а там трейсбек читать некому: нечитаемый файл —
        # такое же нарушение структуры, как отсутствующая секция.
        return [f"{path}: не прочитан: {exc}"]

    meta = yamlmini.frontmatter(text)
    if meta is None:
        return [f"{path}: нет frontmatter (--- ... ---)"]

    errors.extend(schema_errors(path, meta))

    missing = REQUIRED_META - meta.keys()
    if missing:
        errors.append(f"{path}: frontmatter без полей: {', '.join(sorted(missing))}")

    # `or ""` — пустое значение поля типизированный разбор отдаёт как None,
    # а в тексте нарушения «type ''» читается понятнее, чем «type 'None'».
    atype = meta.get("type") or ""
    rules = RULES.get(atype)
    if rules is None:
        errors.append(f"{path}: неизвестный type '{atype}' (ожидается: {', '.join(RULES)})")
        return errors

    status = meta.get("status") or ""
    if status not in rules["statuses"]:
        errors.append(
            f"{path}: недопустимый status '{status}' для {atype} "
            f"(валидные: {', '.join(sorted(rules['statuses']))})"
        )

    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    for section in rules["sections"]:
        if section not in headers:
            errors.append(f"{path}: отсутствует обязательная секция '## {section}'")

    if meta.get("task") in (None, "", "TASK_ID"):
        errors.append(f"{path}: поле task не заполнено (осталось TASK_ID)")

    if atype == "spec" and "Критерии приёмки" in headers:
        errors.extend(spec_ac_errors(path, text, meta))

    return errors


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args == ["--all"]:
        files = sorted(Path("tasks").rglob("*.md"))
    else:
        files = [Path(a) for a in args]

    all_errors: list[str] = []
    for f in files:
        if not f.exists():
            all_errors.append(f"{f}: файл не найден")
            continue
        all_errors.extend(check(f))

    if all_errors:
        print("GUARD: нарушения структуры артефактов:")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print(f"GUARD: ок ({len(files)} файлов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
