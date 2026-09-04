#!/usr/bin/env python3
"""Guard: валидатор СТРУКТУРЫ артефактов задач (frontmatter + обязательные
секции). Содержательность не проверяет — это работа гейтов и людей (§04).

Новые правила guard действуют на живые задачи; история не переписывается —
задача, уже закрытая до появления правила (несёт `docs/retro/<id>.md`), под
это правило задним числом не подпадает (ANSWER-3 tasks/01M1KS8K9RXWHX2PW3ZKB0P903,
пример — `_closed_before_split_assessment`).

Использование:
    python3 scripts/guard.py tasks/T001/SPEC.md [ещё файлы...]
    python3 scripts/guard.py --all          # все артефакты в tasks/
Выход: 0 — ок, 1 — есть нарушения (список в stdout).
"""
import ast
import re
import sys
from pathlib import Path

# Файл живёт двумя жизнями — скрипт и модуль (`from scripts import guard`
# в тестах и в FSM). У скрипта в sys.path лежит scripts/, а не корень
# репозитория, поэтому корень кладётся руками: та же схема, что в artel.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, yamlmini  # noqa: E402

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
#
# Версия 3 (tasks/T100): REVIEW.md несёт секцию «Реестр замечаний» —
# id, статус (пятёрка значений), обязательные поля каждой записи.
# Правило применяется только к version >= 3 (требование 6) — тем же
# приёмом версии-гейтинга, что версия 2 выше применена к SPEC.
#
# Версия 4 (01M1NKVPD2A79PQ6K0JVV1B2Q1, часть 1 нарезки «Механика зон»):
# SPEC несёт обязательное поле `zones:` — машиночитаемый список путей/
# масок зоны задачи (требование 1, AC-1). Правило применяется только к
# version >= 4 — тем же приёмом версии-гейтинга, что версии 2 и 3 выше.
SUPPORTED_SCHEMA_VERSION = 4

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
    # Ответ Оператора на эскалацию (tasks/T075): создаётся и коммитится
    # только командой `artel.py answer <id> <файл>` — Оператору нечего
    # черновить, поэтому единственный валидный статус — "ready".
    "answer": {
        "sections": ["Ответы"],
        "statuses": {"ready"},
    },
}


def schema_errors(path: Path | str, meta: dict) -> list[str]:
    """Совместимость версии схемы артефакта с этим guard'ом.

    `path` — только для текста ошибок (`Path` с диска или строка-label
    ветки задачи, `check_content`, SPEC T031) — не читается здесь."""
    if "schema_version" not in meta:
        return []  # артефакт до T017 — версия 1 по определению
    version = meta["schema_version"]
    # bool — подтип int, а `schema_version: true` версией не является.
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return [f"{path}: schema_version '{version}' — не целое число ≥ 1, "
                f"замени значение на целое число (например {SUPPORTED_SCHEMA_VERSION})"]
    if version > SUPPORTED_SCHEMA_VERSION:
        return [f"{path}: schema_version {version} новее поддерживаемой "
                f"{SUPPORTED_SCHEMA_VERSION} — этот guard не понимает формат "
                f"настолько новой версии; замени значение на "
                f"{SUPPORTED_SCHEMA_VERSION} или ниже, а если тебе действительно "
                f"нужны возможности версии {version} — эскалируй, чтобы Оператор "
                f"обновил guard"]
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

# Маркер причины красноты в докстринге модуля приёмочного теста (SPEC
# T064, требование 1): «Красен до реализации: <объяснение>» или «Зелёный
# с рождения: <объяснение>», непустой текст на той же строке после
# двоеточия. Однострочный по тому же приёму, что AC_MARKER выше.
REDNESS_MARKER = re.compile(
    r"(?:Красен до реализации|Зелёный с рождения):[^\S\n]*(\S.*)")


def section_body(text: str, name: str) -> str:
    """Текст секции `## name` до следующего `## ` заголовка или конца файла.

    Публичная (не `_section_body`): переиспользуется вне этого модуля
    `orchestrator/fsm.py` для ветко-корректного расчёта трассируемости AC
    с ВЕТКИ задачи, не только с диска (SPEC T031).
    """
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


def spec_ac_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """AC-разметка раздела «Критерии приёмки» (SPEC T023, требования 2, 7).

    `path` — только для текста ошибок (см. `schema_errors`)."""
    if not requires_ac_markup(meta):
        return []
    body = section_body(text, "Критерии приёмки")
    ac_numbers = [int(n) for n in AC_ITEM.findall(body)]
    if not ac_numbers:
        return [f"{path}: критерии приёмки не размечены AC-n (AC-1., AC-2., "
                f"…) — размечай каждый пункт в формате 'AC-<номер>. текст' "
                f"с точки в начале строки, либо укажи skip_tests в "
                f"frontmatter, если тесты на этот SPEC осознанно пропущены"]
    if len(set(ac_numbers)) != len(ac_numbers):
        return [f"{path}: номера AC-n повторяются: {ac_numbers} — "
                f"перенумеруй критерии так, чтобы каждый номер AC-n "
                f"встречался ровно один раз"]
    if PLAIN_NUMBERED_ITEM.search(body):
        return [f"{path}: в критериях приёмки остались пункты без "
                f"AC-разметки (обычный '1. текст' вместо 'AC-1. текст') — "
                f"замени нумерацию таких пунктов на формат 'AC-<номер>. "
                f"текст', например 'AC-1.', 'AC-2.'"]
    return []


def scan_ac_content(sources: list[str]) -> tuple[set, dict]:
    """(AC, покрытые тестом) и {AC: (пометка, причина)} по уже прочитанным
    текстам файлов *.py под acceptance_tests/.

    Источник-агностичное ядро `scan_acceptance_tests` (диск) и ветко-
    корректного чтения `orchestrator/fsm.py` (git, SPEC T031, AC-3) — сам
    разбор AC-разметки не должен раздваиваться между источником файлов.
    """
    tested: set = set()
    markers: dict = {}
    for content in sources:
        tested.update(int(n) for n in TEST_AC.findall(content))
        for n, kind, reason in AC_MARKER.findall(content):
            markers[int(n)] = (kind, reason.strip())
    return tested, markers


def scan_acceptance_tests(tdir: Path) -> tuple[set, dict]:
    """(AC, покрытые тестом) и {AC: (пометка, причина)} из acceptance_tests/
    рабочей копии.

    Статический разбор текстом, без импорта файлов — теста без разметки
    `test_ac<n>_` парсер не увидит, и это осознанно: содержательность
    (тест действительно проверяет то, что заявляет) — дело ревью и прогона
    unittest на гейте (orchestrator/acceptance.py), не структурной проверки.

    Только `test_*.py` (SPEC T081) — тот же приём, что `scan_redness_markers`
    (T064): маркер или тест-метод во вспомогательном файле вроде
    `_sandbox.py` (например, литерал-фикстура в исходнике теста другой
    задачи) не должен читаться как настоящая AC-разметка этой задачи.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return set(), {}
    sources: list[str] = []
    for f in sorted(tests_dir.rglob("test_*.py")):
        try:
            sources.append(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return scan_ac_content(sources)


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


def module_docstring(source: str) -> str | None:
    """Докстринг модуля из текста .py-файла; `None` — файл не парсится
    (SyntaxError) или докстринга нет.

    `ast.parse`, не regex по тексту файла: докстринг модуля — синтаксическая
    сущность (первый expression-statement тела модуля), а не «первая
    тройная кавычка», которую перепутал бы regex со строкой внутри функции.
    Тот же приём (без импорта/исполнения файла), что
    `scripts/codebase_map.py::extract_purpose`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def has_redness_marker(docstring: str | None) -> bool:
    """Докстринг несёт «Красен до реализации:»/«Зелёный с рождения:» с
    непустым объяснением (SPEC T064, требования 1, 3 — только формальный
    факт присутствия строки, не оценка смысла)."""
    if not docstring:
        return False
    return bool(REDNESS_MARKER.search(docstring))


def redness_marker_errors_from_files(files: list[tuple[str, str]]) -> list[str]:
    """Ядро проверки маркера красноты (SPEC T064, требования 1–3) по уже
    прочитанным (label, текст) парам файлов `acceptance_tests/test_*.py` —
    без чтения файлов: источник (рабочая копия или ВЕТКА задачи, тот же
    приём, что `traceability_errors_from_content`) выбирает вызывающий код.
    """
    errors: list[str] = []
    for label, source in files:
        if not has_redness_marker(module_docstring(source)):
            errors.append(
                f"{label}: нет маркера «Красен до реализации:» или «Зелёный "
                f"с рождения:» с непустым объяснением на той же строке сразу "
                f"после двоеточия в докстринге модуля — допиши объяснение "
                f"сразу после двоеточия на той же строке, например «Красен "
                f"до реализации: <причина>» (перенос объяснения на "
                f"следующую строку не считается заполненным маркером)")
    return errors


def scan_redness_markers(tdir: Path) -> list[str]:
    """Ошибки маркера красноты для `acceptance_tests/test_*.py` рабочей
    копии (SPEC T064). Только `test_*.py` — SPEC требование 1 называет
    этот шаблон, вспомогательные файлы (`_sandbox.py`, `__init__.py`)
    маркером не размечаются.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files: list[tuple[str, str]] = []
    for f in sorted(tests_dir.rglob("test_*.py")):
        try:
            files.append((str(f), f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return redness_marker_errors_from_files(files)


# --------------------------------------------------------------------------
# Образец формата идентификатора задачи в acceptance_tests/ (SPEC
# 01M1H186VEVG6NF40YKH1338MD, требования 1-2): инцидент 02.09.2026 —
# приёмочный тест зашил формат id («T и три цифры») в проверку вывода, и
# CI-job id-format-greplint (.github/workflows/ci.yml) поймал это только
# на PR, когда acceptance_tests/ уже был зафиксирован локом (ADR-0003,
# инвариант 27). Проверка здесь ловит тот же класс дефекта РАНЬШЕ — на
# выходе из tests_writing, до записи tests_locked_sha.
#
# Набор образцов — общий источник с CI-job (требование 2, AC-3):
# id_format_patterns.txt читают ОБА потребителя (этот модуль и bash-шаг
# job'а через `grep -Ef`) — правка файла меняет поведение обоих без
# правки кода.
ID_FORMAT_PATTERNS_PATH = Path(__file__).resolve().parent / "id_format_patterns.txt"

ID_FORMAT_HINT = ("формат идентификатора знает только генератор; строй "
                  "проверку от фактического идентификатора")


def id_format_patterns() -> list[re.Pattern]:
    """Скомпилированные образцы формата идентификатора задачи из общего
    источника (см. заголовок секции выше)."""
    lines = ID_FORMAT_PATTERNS_PATH.read_text(encoding="utf-8").splitlines()
    return [re.compile(line) for line in lines if line.strip()]


def id_format_sample_errors(files: list[tuple[str, str]]) -> list[str]:
    """Ошибки образца формата идентификатора задачи по уже прочитанным
    (label, текст) парам .py-файлов acceptance_tests/ — источник (диск
    или ВЕТКА задачи) выбирает вызывающий код, тем же приёмом, что
    `redness_marker_errors_from_files`."""
    patterns = id_format_patterns()
    errors: list[str] = []
    for label, source in files:
        for lineno, line in enumerate(source.splitlines(), start=1):
            if any(p.search(line) for p in patterns):
                errors.append(f"{label}:{lineno}: строка несёт образец "
                              f"формата идентификатора задачи — "
                              f"{ID_FORMAT_HINT}")
    return errors


def scan_id_format_samples(tdir: Path) -> list[str]:
    """Ошибки образца формата идентификатора для всех `*.py` под
    acceptance_tests/ рабочей копии — та же область файлов, что источники
    трассируемости AC (`scan_ac_content`), шире `scan_redness_markers`
    (не только `test_*.py`): образец формата может утечь и во
    вспомогательный файл вроде `_sandbox.py`.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files: list[tuple[str, str]] = []
    for f in sorted(tests_dir.rglob("*.py")):
        try:
            files.append((str(f), f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return id_format_sample_errors(files)


def traceability_errors_from_content(spec_text: str, meta: dict, tested: set,
                                     markers: dict) -> list[str]:
    """Ядро проверки трассируемости AC -> тест (SPEC T023, требование 4) по
    уже прочитанным SPEC-тексту и результату `scan_ac_content` — без
    чтения файлов: источник (рабочая копия или ВЕТКА задачи, SPEC T031,
    AC-3) выбирает вызывающий код (`acceptance_traceability_errors` — диск,
    `orchestrator/fsm.py` — git при чужом чекауте), не эта функция.
    """
    if not requires_ac_markup(meta):
        return []
    ac_numbers = {int(n) for n in
                 AC_ITEM.findall(section_body(spec_text, "Критерии приёмки"))}
    errors: list[str] = []
    for n in sorted(ac_numbers):
        if n not in tested and n not in markers:
            errors.append(
                f"AC-{n}: нет теста и нет пометки manual/skip/escalate — "
                f"добавь тестовый метод 'def test_ac{n}_...' в "
                f"acceptance_tests/, либо пометку "
                f"'# AC-{n}: manual|skip|escalate — причина' в том же "
                f"каталоге")
    for n, (kind, reason) in sorted(markers.items()):
        if n not in ac_numbers:
            errors.append(
                f"AC-{n}: пометка на критерий, которого нет в SPEC — убери "
                f"эту пометку либо добавь критерий AC-{n} в раздел «Критерии "
                f"приёмки» SPEC")
        elif kind in ("skip", "escalate") and not reason:
            errors.append(
                f"AC-{n}: пометка {kind} без причины — впиши причину после "
                f"тире в той же строке, например "
                f"'# AC-{n}: {kind} — <причина>'")
    for n in sorted(tested):
        if n not in ac_numbers:
            errors.append(
                f"AC-{n}: тест на критерий, которого нет в SPEC (SPEC T023, "
                f"требование 3 — только из критериев) — переименуй тест на "
                f"существующий AC-номер либо добавь критерий AC-{n} в раздел "
                f"«Критерии приёмки» SPEC")
    return errors


def acceptance_traceability_errors(tdir: Path) -> list[str]:
    """AC без теста и без пометки — невалидный выход из tests_writing
    (SPEC T023, требование 4), рабочая копия.

    SPEC без AC-разметки (версия 1 или `skip_tests`) — tests_writing эту
    задачу не проходит, сверять нечего. Само правило —
    `traceability_errors_from_content`.
    """
    spec_path = tdir / "SPEC.md"
    try:
        text = spec_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{spec_path}: не прочитан: {exc}"]
    meta = yamlmini.frontmatter(text) or {}
    tested, markers = scan_acceptance_tests(tdir)
    return traceability_errors_from_content(text, meta, tested, markers)


# Секция «Проверено исполнением» — обязательна при status: approved
# (tasks/T072/SPEC.md, требования 1–2). Урок ручных гейтов Оператора
# (docs/operator-gates.md, норматив 26.08 «гейт — проверка, а не
# подтверждение приезда») распространяется и на агентское ревью:
# одобрение без исполненной проверки — слепое.
EVIDENCE_SECTION = "Проверено исполнением"


def review_evidence_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Секция «Проверено исполнением» при `status: approved` (SPEC T072,
    требования 1, 2, 4). Для остальных статусов — не требуется (AC-5).

    `path` — только для текста ошибок (см. `schema_errors`). Различает
    «секции нет вовсе» и «секция есть, но пустая» — AC-4 требует, чтобы
    сообщение называло, что именно отсутствует."""
    if meta.get("status") != "approved":
        return []
    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    if EVIDENCE_SECTION not in headers:
        return [f"{path}: approved-ревью без секции '## {EVIDENCE_SECTION}' — "
                f"добавь секцию с перечислением команд/тестов, которые ты "
                f"реально запускал, и что они показали"]
    body = section_body(text, EVIDENCE_SECTION).strip()
    if not body:
        return [f"{path}: секция '## {EVIDENCE_SECTION}' пустая — впиши, "
                f"какие команды/тесты ты реально запускал и что они показали"]
    return []


# --------------------------------------------------------------------------
# Секция «Реестр замечаний» REVIEW.md (tasks/T100, требования 1, 2, 6, 7):
# запись — строка markdown-таблицы с id вида `R<итерация>-F<номер>`,
# статусом из пятёрки {open, fixed, rejected, accepted, needs_work} и
# обязательными полями файл/строка, суть, последствие, решение. Применяется
# только при schema_version >= 3 (требование 6) — та же версия-гейтинг,
# что `requires_ac_markup` выше применяет к AC-разметке SPEC.
REGISTRY_SECTION = "Реестр замечаний"
REGISTRY_STATUSES = {"open", "fixed", "rejected", "accepted", "needs_work"}
REGISTRY_ID = re.compile(r"^R\d+-F\d+$")
# Порядок колонок таблицы фиксирован заголовком секции (см. templates/
# REVIEW.md): id | статус | файл/строка | суть | последствие | решение.
REGISTRY_FIELD_LABELS = ("id", "статус", "файл/строка", "суть",
                         "последствие", "решение")
REGISTRY_FIELD_KEYS = ("id", "status", "location", "gist", "consequence",
                       "decision")
REGISTRY_SEPARATOR_CELL = re.compile(r"^:?-{1,}:?$")


def requires_registry(meta: dict) -> bool:
    """REVIEW.md обязан нести секцию «Реестр замечаний» и пройти её
    структурные проверки (требования 1, 6, 7).

    Версия ниже 3 (или отсутствие поля — версия 1 по умолчанию) — формат
    REVIEW.md до этой задачи, требования 1–5 к нему не применяются (SPEC
    T100, требование 6), тем же приёмом, что `requires_ac_markup` выше.
    """
    version = meta.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        return False
    return version >= 3


def registry_table_rows(body: str) -> list[list[str]]:
    """Строки данных markdown-таблицы реестра — без заголовка ('| id | …')
    и строки-разделителя ('|---|---|…'). Не различает валидные и
    невалидные строки данных (число ячеек, формат id, допустимость
    статуса) — это дело `registry_record_errors`/`registry_records`.
    """
    rows: list[list[str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0].lower() == "id":
            continue  # строка заголовка таблицы
        if all(REGISTRY_SEPARATOR_CELL.fullmatch(c) for c in cells):
            continue  # строка-разделитель '|---|---|…'
        rows.append(cells)
    return rows


def registry_records(text: str) -> list[dict]:
    """Записи реестра как словари ({"id", "status", …}) — только
    well-formed строки (ровно столько колонок, сколько полей записи).

    Источник для гейта требования 5 (`orchestrator/fsm_advance.py::
    review()`): к моменту его вызова guard уже подтвердил структуру
    REVIEW.md на том же переходе (`fsm.guard_refuses`), поэтому здесь
    достаточно молча пропустить малформед-строки, а не повторять
    структурные ошибки `registry_record_errors`.
    """
    body = section_body(text, REGISTRY_SECTION)
    records = []
    for cells in registry_table_rows(body):
        if len(cells) != len(REGISTRY_FIELD_KEYS):
            continue
        records.append(dict(zip(REGISTRY_FIELD_KEYS, cells)))
    return records


def registry_record_errors(path: Path | str, cells: list[str]) -> list[str]:
    """Структурные нарушения одной строки данных таблицы реестра
    (требования 1, 2, 7 — AC-3, AC-4, AC-5). `path` — только для текста
    ошибок (см. `schema_errors`)."""
    if len(cells) != len(REGISTRY_FIELD_LABELS):
        return [f"{path}: строка реестра '{' | '.join(cells)}' — ожидается "
                f"{len(REGISTRY_FIELD_LABELS)} колонок "
                f"({', '.join(REGISTRY_FIELD_LABELS)}), получено "
                f"{len(cells)}"]
    record_id, status, location, gist, consequence, decision = cells
    errors: list[str] = []
    if not REGISTRY_ID.fullmatch(record_id):
        errors.append(f"{path}: id записи реестра '{record_id}' не "
                      f"соответствует формату 'R<итерация>-F<номер>' — "
                      f"например 'R1-F1'")
    if status not in REGISTRY_STATUSES:
        errors.append(f"{path}: запись {record_id} — статус '{status}' не "
                      f"входит в допустимое множество "
                      f"{', '.join(sorted(REGISTRY_STATUSES))}")
    missing = [label for label, value in
              zip(REGISTRY_FIELD_LABELS[2:], (location, gist, consequence, decision))
              if not value]
    if missing:
        errors.append(f"{path}: запись {record_id} — не заполнены "
                      f"обязательные поля: {', '.join(missing)}")
    return errors


def registry_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Структурные проверки секции «Реестр замечаний» целиком: секция на
    месте, id уникальны, каждая запись валидна (SPEC T100, требования 1,
    2, 6, 7 — AC-1..AC-6). `path` — только для текста ошибок."""
    if not requires_registry(meta):
        return []
    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    if REGISTRY_SECTION not in headers:
        return [f"{path}: REVIEW.md со schema_version >= 3 без секции "
                f"'## {REGISTRY_SECTION}' — добавь секцию с записями "
                f"замечаний (id, файл/строка, суть, последствие, решение, "
                f"статус)"]
    body = section_body(text, REGISTRY_SECTION)
    rows = registry_table_rows(body)
    errors: list[str] = []
    seen: dict[str, int] = {}
    for cells in rows:
        errors.extend(registry_record_errors(path, cells))
        if cells and REGISTRY_ID.fullmatch(cells[0]):
            seen[cells[0]] = seen.get(cells[0], 0) + 1
    for record_id in sorted(rid for rid, n in seen.items() if n > 1):
        errors.append(f"{path}: id записи реестра '{record_id}' "
                      f"встречается более одного раза — id обязаны быть "
                      f"уникальны в пределах файла")
    return errors


# --------------------------------------------------------------------------
# Сигналы «подозрения на большой объём» на этапе SPEC
# (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требования 1, 3; ANSWER-1 — правила
# для AC-1 (константы, прогноз диффа) и AC-3 (пересечение зон с
# docs/invariants.md) названы буквально ответом на эскалацию test_author).
#
# Проверка условная, не структурная в обычном смысле: срабатывает не для
# каждого SPEC, а только когда содержимое само указывает на большой
# объём — тот же класс, что «Влияние на систему» PLAN (инвариант 17), но
# УСЛОВНЫЙ (AC-6: без единого сигнала секция не обязательна вовсе).
SPLIT_ASSESSMENT_SECTION = "Оценка объёма и деление"

# Три фразы требования 1/AC-2 — буквально из SPEC. Ищутся по ВСЕМУ тексту
# SPEC, не только по разделу «Зоны»: SPEC не обязан держать «Зоны»
# отдельной секцией (AC-4 требует только секцию «Оценка объёма и
# деление»), а формулировка неопределённости может встретиться в любом
# требовании.
UNCERTAINTY_PHRASES = ("ориентировочно", "весь оркестратор",
                       "по факту затронутых мест")

# Путь вида `orchestrator/<имя>.py`/`scripts/<имя>.py» (ANSWER-1, AC-1/
# AC-3) — источник для двух разных сигналов: числа файлов зоны и
# пересечения с docs/invariants.md. Ищется по ВСЕМУ тексту SPEC, тем же
# доводом, что UNCERTAINTY_PHRASES выше: ни `templates/SPEC.md`, ни
# существующая практика 105 задач не несут отдельного раздела «## Зоны»
# — заголовок, привязка к которому оставляла бы сигнал мёртвым кодом
# (REVIEW.md, итерация 1, замечание R1-F1).
ZONE_PATH = re.compile(r"(?:orchestrator|scripts)/\w+\.py")

# Прогноз диффа строкой секции (ANSWER-1, AC-1) — запасной путь, когда
# frontmatter `diff_forecast_kib` не задан.
DIFF_FORECAST_LINE = re.compile(
    r"Прогноз диффа:\s*(\d+(?:\.\d+)?)\s*КиБ")

INVARIANTS_DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "invariants.md"

# Задача, уже закрытая ДО появления этой проверки (несёт docs/retro/<id>.md),
# под split_assessment_errors не подпадает (ANSWER-3, вариант b): новые
# правила guard действуют на живые задачи, история не переписывается —
# docs/retention.md объявляет SPEC/PLAN/REVIEW смерженных задач вечными,
# backfill секции в них задним числом не требуется.
RETRO_DIR = Path(__file__).resolve().parent.parent / "docs" / "retro"
TASK_ID_FROM_PATH = re.compile(r"(?:^|/)tasks/([^/]+)/")


def _closed_before_split_assessment(path: Path | str) -> bool:
    """`True`, если `path` указывает на SPEC задачи, для которой уже есть
    `docs/retro/<id>.md` — задача закрыта раньше, чем появилась эта
    проверка."""
    match = TASK_ID_FROM_PATH.search(str(path))
    if not match:
        return False
    return (RETRO_DIR / f"{match.group(1)}.md").exists()


def requires_split_assessment(meta: dict) -> bool:
    """SPEC обязан нести проверку сигналов объёма (требования 1, 3).

    Версия ниже 3 (или отсутствие поля — версия 1 по умолчанию) — формат
    SPEC до этой задачи, `budget_usd`/структура которого не рассчитаны на
    новый сигнал (например `budget_usd` выше нового порога в старом
    беклоге без секции «Оценка объёма и деление» ещё не значит нарушение
    ЭТОГО SPEC) — тот же приём версии-гейтинга, что `requires_ac_markup`
    и `requires_registry` выше применяют к своим проверкам.
    """
    version = meta.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        return False
    return version >= 3


def _zone_paths(text: str) -> set[str]:
    """Пути формата `orchestrator/<имя>.py`/`scripts/<имя>.py`, упомянутые
    в тексте SPEC (ANSWER-1) — по ВСЕМУ тексту, не по разделу «Зоны»,
    которого не несёт ни `templates/SPEC.md`, ни существующая практика
    (REVIEW.md, итерация 1, R1-F1)."""
    return set(ZONE_PATH.findall(text))


def _diff_forecast_kib(text: str, meta: dict) -> float | None:
    """Прогноз диффа SPEC в КиБ — frontmatter `diff_forecast_kib` либо
    строка «Прогноз диффа: N КиБ» секции «Оценка объёма и деление»
    (ANSWER-1, AC-1). `None` — поле не задано ни там, ни там."""
    value = meta.get("diff_forecast_kib")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    body = section_body(text, SPLIT_ASSESSMENT_SECTION)
    match = DIFF_FORECAST_LINE.search(body)
    return float(match.group(1)) if match else None


def _invariants_doc_text() -> str:
    """Текст `docs/invariants.md` по требованию, без кеша на импорте (тот
    же приём, что `id_format_patterns` выше) — нечитаемый файл не должен
    ронять guard, только гасить сигнал AC-3 (сравнивать не с чем)."""
    try:
        return INVARIANTS_DOC_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def split_signal_names(text: str, meta: dict) -> list[str]:
    """Имена сработавших сигналов «подозрения на большой объём»
    (требование 1, AC-1..AC-3) — пусто, если ни один не сработал (AC-6).

    Порядок — порядок появления сигналов в требовании 1/критериях
    приёмки SPEC этой задачи, не алфавитный: стабилен для читаемости
    сообщения отказа, не для сравнения множеств.
    """
    names: list[str] = []

    if len(_zone_paths(text)) >= config.SPLIT_SIGNAL_ZONE_FILES:
        names.append("число затрагиваемых модулей/файлов")

    ac_count = len(AC_ITEM.findall(section_body(text, "Критерии приёмки")))
    if ac_count >= config.SPLIT_SIGNAL_AC_COUNT:
        names.append("число критериев приёмки")

    budget = meta.get("budget_usd")
    if (isinstance(budget, (int, float)) and not isinstance(budget, bool)
            and budget >= config.SPLIT_SIGNAL_BUDGET_USD):
        names.append("бюджет")

    if any(phrase in text for phrase in UNCERTAINTY_PHRASES):
        names.append("формулировки неопределённости")

    zone_paths = _zone_paths(text)
    if zone_paths:
        invariants_text = _invariants_doc_text()
        if any(p in invariants_text for p in zone_paths):
            names.append("затронут инвариантный механизм")

    forecast_threshold_kib = ((config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES / 1024)
                              * config.SPLIT_SIGNAL_DIFF_FORECAST_RATIO)
    forecast = _diff_forecast_kib(text, meta)
    if forecast is not None and forecast > forecast_threshold_kib:
        names.append("прогноз диффа")
    elif forecast is None and names:
        # Отсутствие прогноза — само по себе сигнал, но только когда уже
        # сработал хотя бы один ДРУГОЙ (ANSWER-1, редактура Оператора
        # 04.09) — «чистый» SPEC без единого реального сигнала не обязан
        # вписывать прогноз просто по факту отсутствия поля (AC-6).
        names.append("прогноз диффа не дан")

    return names


def split_assessment_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Секция «Оценка объёма и деление» заполнена, если сработал хотя бы
    один сигнал (требование 3, AC-5/AC-7). `path` — только для текста
    ошибок (см. `schema_errors`)."""
    if (meta.get("type") or "") != "spec" or not requires_split_assessment(meta):
        return []
    if _closed_before_split_assessment(path):
        return []
    signals = split_signal_names(text, meta)
    if not signals:
        return []
    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    body = (section_body(text, SPLIT_ASSESSMENT_SECTION).strip()
           if SPLIT_ASSESSMENT_SECTION in headers else "")
    if body:
        return []
    return [f"{path}: сработали сигналы подозрения на большой объём "
           f"({', '.join(signals)}), а секция '## {SPLIT_ASSESSMENT_SECTION}' "
           f"пуста или отсутствует — заполни секцию нарезкой на 2-4 "
           f"подзадачи (границы зон, порядок, обоснование мержимости "
           f"каждой) либо обоснованием монолита (что нельзя разрезать и "
           f"почему)"]


def requires_zones(meta: dict) -> bool:
    """SPEC обязан нести поле `zones:` (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-1).

    Версия ниже 4 — формат SPEC до этой задачи, поля не несёт и не
    обязан: тот же приём версии-гейтинга, что `requires_ac_markup` и
    `requires_split_assessment` выше применяют к своим проверкам.
    """
    version = meta.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        return False
    return version >= 4


def spec_zones_errors(path: Path | str, meta: dict) -> list[str]:
    """Поле `zones:` заполнено для SPEC версии, которая его требует
    (AC-1). `path` — только для текста ошибок (см. `schema_errors`)."""
    if (meta.get("type") or "") != "spec" or not requires_zones(meta):
        return []
    if not meta.get("zones"):
        return [f"{path}: SPEC schema_version {meta.get('schema_version')} "
               f"обязан нести поле zones (список путей/масок) — добавь "
               f"frontmatter-поле zones"]
    return []


def check_content(label: str, text: str) -> list[str]:
    """Ядро `check` — структурная проверка уже прочитанного текста, без
    чтения файла: `label` — путь или его подобие, только для текста
    ошибок (не обязательно существующий `Path`).

    Артефакт-условие перехода FSM может читаться и с диска, и с ВЕТКИ
    задачи при чужом чекауте рабочей копии (SPEC T031, `orchestrator/
    fsm.py`, `guard_refuses`) — сама структурная проверка не должна
    раздваиваться по источнику текста.
    """
    errors: list[str] = []
    meta = yamlmini.frontmatter(text)
    if meta is None:
        return [f"{label}: нет frontmatter (--- ... ---) — добавь в начало "
                f"файла блок между двумя строками '---' с обязательными "
                f"полями {', '.join(sorted(REQUIRED_META))}"]

    errors.extend(schema_errors(label, meta))

    missing = REQUIRED_META - meta.keys()
    if missing:
        errors.append(f"{label}: добавь в frontmatter обязательные поля: "
                      f"{', '.join(sorted(missing))}")

    # `or ""` — пустое значение поля типизированный разбор отдаёт как None,
    # а в тексте нарушения «type ''» читается понятнее, чем «type 'None'».
    atype = meta.get("type") or ""
    rules = RULES.get(atype)
    if rules is None:
        errors.append(f"{label}: неизвестный type '{atype}' — замени поле "
                      f"type в frontmatter на одно из: {', '.join(RULES)}")
        return errors

    status = meta.get("status") or ""
    if status not in rules["statuses"]:
        errors.append(
            f"{label}: недопустимый status '{status}' для {atype} — замени "
            f"поле status в frontmatter на одно из валидных значений: "
            f"{', '.join(sorted(rules['statuses']))}"
        )

    all_headings = re.findall(r"^(#{1,6})\s+(.+?)\s*$", text, re.M)
    headers = {title for hashes, title in all_headings if hashes == "##"}
    levels_by_title: dict[str, set] = {}
    for hashes, title in all_headings:
        levels_by_title.setdefault(title, set()).add(len(hashes))
    for section in rules["sections"]:
        if section in headers:
            continue
        wrong_levels = levels_by_title.get(section, set()) - {2}
        if wrong_levels:
            level = sorted(wrong_levels)[0]
            errors.append(
                f"{label}: заголовок секции '{section}' стоит на уровне H{level} "
                f"('{'#' * level} {section}') — обязательные секции требуют "
                f"уровень H2, ровно два символа '#': переименуй заголовок в "
                f"'## {section}'")
        else:
            errors.append(
                f"{label}: отсутствует обязательная секция '## {section}' — "
                f"добавь в файл заголовок '## {section}' и содержимое под ним")

    if meta.get("task") in (None, "", "TASK_ID"):
        errors.append(f"{label}: поле task не заполнено (осталось TASK_ID) — "
                      f"впиши в frontmatter реальный номер задачи вместо "
                      f"TASK_ID")

    if atype == "spec" and "Критерии приёмки" in headers:
        errors.extend(spec_ac_errors(label, text, meta))

    if atype == "spec":
        errors.extend(split_assessment_errors(label, text, meta))
        errors.extend(spec_zones_errors(label, meta))

    if atype == "review":
        errors.extend(review_evidence_errors(label, text, meta))
        errors.extend(registry_errors(label, text, meta))

    return errors


def check(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Guard зовётся не только из CLI, но и из FSM на переходах (T017,
        # требование 5), а там трейсбек читать некому: нечитаемый файл —
        # такое же нарушение структуры, как отсутствующая секция.
        return [f"{path}: не прочитан: {exc}"]
    return check_content(str(path), text)


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
