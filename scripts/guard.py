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
    python3 scripts/guard.py --all --artifact-branch   # режим артефактной
                                                        # ветки (ниже)
Выход: 0 — ок, 1 — есть нарушения (список в stdout).

Режим артефактной ветки (`--artifact-branch`, 01M1R66X5SMD3ZEDCVAJ0DR7K2):
CI на пуш ветки `artifact/<id>` видит промежуточные, по определению
неполные артефакты каждого автокоммита шага роли. С этим флагом для
черновика (`status: draft`) типов spec/plan/review/test_report найденное
нарушение содержания (обязательные секции, zones, AC-разметка и т.п.) не
роняет процесс — только печатается предупреждением; нарушение
frontmatter (task/type/schema_version) остаётся ошибкой. Для «сданного»
статуса и для типов tz/questions/answer — поведение как без флага, без
исключений. Первая строка вывода с флагом — сводка «сдано N / черновиков
M / нарушений K». Без флага — поведение и формат вывода прежние.

Посторонний файл в `acceptance_tests/` (режим `--all`, оба варианта — с
`--artifact-branch` и без, SPEC 01M1SAA01YRRTWAVADT2F81RRQ): файл вне
разрешённого набора первого уровня (`test_*.py`, `_sandbox.py`,
`markers.py`, `__init__.py`, `*.md`/`*.txt`) — именованная ошибка
«посторонний файл в каталоге планки», не попытка разбора его как
артефакта с frontmatter.
"""
import ast
import math
import re
import sys
from pathlib import Path

# Файл живёт двумя жизнями — скрипт и модуль (`from scripts import guard`
# в тестах и в FSM). У скрипта в sys.path лежит scripts/, а не корень
# репозитория, поэтому корень кладётся руками: та же схема, что в artel.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, spend, yamlmini  # noqa: E402

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
#
# Версия 5 (01M1THKTJ7YT1K410G1KS17MK6, ADR-0014 часть 1 «потолок ролей»):
# SPEC несёт обязательное поле `budget_usd`, разбираемое как число
# (требование 2, AC-2). Правило применяется только к version >= 5 — тем
# же приёмом версии-гейтинга, что версии 2-4 выше. Отдельно и НЕЗАВИСИМО
# от schema_version — SPEC/PLAN любой версии с `budget_usd` выше
# `config.ROLE_BUDGET_CAP` отказаны (требование 3, AC-3): это проверка
# значения уже существующего необязательного поля, не факта его
# присутствия, версия-гейтинг к ней не применяется.
SUPPORTED_SCHEMA_VERSION = 5

RULES = {
    "spec": {
        "sections": ["Контекст", "Требования", "Критерии приёмки", "Не входит"],
        "statuses": {"draft", "ready", "approved"},
    },
    "plan": {
        "sections": ["Подход", "Шаги", "Покрытие требований",
                     "Влияние на систему"],  # принцип целостности (ADR-0002)
        # "escalate" (SPEC 01M1NKTF173WV5CPDZ1C3WW69K, требование 6, AC-12):
        # единственный законный канал эскалации developer через PLAN.md —
        # без него требование 6 неисполнимо для роли, для которой оно
        # написано (см. «Контекст» SPEC).
        "statuses": {"draft", "ready", "approved", "escalate"},
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
# Пометка критерия без прямого теста: `# AC-n: manual|skip|escalate|ci —
# причина`. `ci` (01M1SHJTT0V516BWHYXWS50F3G, требование 1): критерий
# исполняется зелёным CI кодовой ветки (orchestrator/fsm_autogate.py),
# не отдельным прогоном — допустима только для критериев про
# существующие tests/ (см. `ci_marker_wording_ok` ниже).
#
# Заякорена на начало строки (`^`, `re.M`, без ведущих пробелов — тот же
# приём, что AC_ITEM/AC_ITEM_FULL выше): REVIEW.md этой задачи итерации
# 1, R1-F2 — незаякоренный поиск по всему тексту находил буквальный
# пример синтаксиса пометки внутри докстроки/комментария (например,
# `# (см. ...): буквальный текст "# AC-9: ci — …"`) как настоящую
# пометку постороннего критерия AC-9. Реальные пометки во всех
# acceptance_tests/ пульта сегодня стоят строго в начале строки —
# сужение не отсекает ни одного легитимного случая (проверено grep'ом
# по репозиторию при разборе R1-F2).
AC_MARKER = re.compile(
    r"^#\s*AC-(\d+):\s*(manual|skip|escalate|ci)\b[^\S\n]*(?:[—-]+[^\S\n]*(.*))?",
    re.M)

# Полный текст критерия `AC-n. <текст>` — от начала пункта до следующего
# `AC-m.` в начале строки либо конца раздела. Тот же якорь, что AC_ITEM
# выше, но захватывает содержимое целиком — нужен только для эвристики
# `ci_marker_wording_ok` (сверка формулировки критерия с пометкой `ci`
# того же номера), не для подсчёта номеров.
AC_ITEM_FULL = re.compile(r"^AC-(\d+)\.\s+(.*?)(?=^AC-\d+\.\s|\Z)", re.M | re.S)

# Ключевые слова требования 3/AC-2 (01M1SHJTT0V516BWHYXWS50F3G): пометка
# `ci` допустима только для критерия про существующий набор `tests/`.
# Case-insensitive substring match, fail-closed — ни одного слова не
# нашлось, формулировка не распознана эвристикой.
CI_MARKER_WORDING_KEYWORDS = ("существующ", "tests/", "зелён", "не ослаб")


def ci_marker_wording_ok(criterion_text: str) -> bool:
    """Формулировка критерия `criterion_text` (полный текст пункта
    `AC-n.`, без номера) содержит хотя бы одно ключевое слово требования
    3 — пометка `ci` для него допустима."""
    lowered = criterion_text.lower()
    return any(kw in lowered for kw in CI_MARKER_WORDING_KEYWORDS)

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


# --------------------------------------------------------------------------
# Посторонний файл в каталоге планки (SPEC 01M1SAA01YRRTWAVADT2F81RRQ,
# требование 2/AC-3/AC-6): инцидент 05.09 — `scripts/codebase_map.py`,
# запущенный с cwd внутри `acceptance_tests/`, оставлял на диске
# `acceptance_tests/docs/codebase-map.md`, и guard в режиме `--all`
# честно пытался разобрать его как артефакт с frontmatter вместо
# понятного нарушения структуры. Критерий допустимости — тот же список,
# что называет SPEC (и независимо, той же регуляркой, реализует
# `orchestrator/checkpoint.py::_is_stray_acceptance_test_file` для
# автокоммита — общего модуля под критерий зона задачи не заводит,
# guard сознательно лёгкий скрипт без зависимости на `orchestrator.
# checkpoint`/`store`/`gitcmd`).
EXTRANEOUS_ACCEPTANCE_FILE_REASON = "посторонний файл в каталоге планки"
ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL = re.compile(
    r"^(test_.*\.py|_sandbox\.py|markers\.py|__init__\.py|.+\.md|.+\.txt)$")


def is_extraneous_acceptance_test_file(rel_to_acceptance_tests: str) -> bool:
    """`rel_to_acceptance_tests` — путь файла относительно `acceptance_tests/`
    (`/`-разделённый, например `test_x.py` или `docs/codebase-map.md`).
    `True` — файл вне разрешённого набора первого уровня (AC-1 задачи
    01M1SAA01YRRTWAVADT2F81RRQ)."""
    if "/" in rel_to_acceptance_tests:
        return True
    return not ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL.match(rel_to_acceptance_tests)


def scan_extraneous_acceptance_files(tasks_root: Path) -> list[Path]:
    """Посторонние файлы под `<tasks_root>/*/acceptance_tests/` — по всем
    каталогам задач сразу (режим `--all`, требование 2). `__pycache__/`
    исключён на любой глубине — та же уже игнорируемая директория, что
    `checkpoint.py` пропускает через `.gitignore` (AC-1: критерий
    одинаков независимо от того, git это фильтрует или обычный обход
    диска, каким сканирует guard).

    Задача, уже закрытая ДО появления этого правила (несёт
    `docs/retro/<id>.md`), не сканируется вовсе — тот же принцип, что и
    `_closed_before_split_assessment` ниже (ANSWER-3 tasks/
    01M1KS8K9RXWHX2PW3ZKB0P903, модульный докстринг выше: «новые правила
    guard действуют на живые задачи, история не переписывается»).
    Обнаружено эмпирически прогоном `--all` на реальном дереве пульта:
    несколько давно закрытых задач несут легитимные вспомогательные
    файлы вида `_util.py`/`_race.py` в `acceptance_tests/` — без этого
    исключения новое правило красило бы `guard --all` на main для
    ЛЮБОЙ последующей ветки, не только для задач, реально нарушающих
    AC-1 сегодня.
    """
    if not tasks_root.is_dir():
        return []
    extraneous: list[Path] = []
    for task_dir in sorted(tasks_root.iterdir()):
        if (RETRO_DIR / f"{task_dir.name}.md").exists():
            continue
        tests_dir = task_dir / "acceptance_tests"
        if not tests_dir.is_dir():
            continue
        for f in sorted(tests_dir.rglob("*")):
            if not f.is_file():
                continue
            rel_parts = f.relative_to(tests_dir).parts
            if "__pycache__" in rel_parts:
                continue
            if is_extraneous_acceptance_test_file("/".join(rel_parts)):
                extraneous.append(f)
    return extraneous


# --------------------------------------------------------------------------
# Посторонний файл в корне каталога задачи (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
# требование 1/AC-1/AC-2; формулировка по ANSWER-1, tasks/
# 01M1TNN4TMWAQSQ9Y1PW37J5H0/ANSWER-1.md, вариант A): инцидент 06.09 —
# рабочие файлы роли (пять копий карты кодовой базы вида `_head_map.md`) в
# корне `tasks/<id>/` без единой проверки доехали до артефактной ветки и
# main. Белый список действует ТОЛЬКО для `.md`-имён первого уровня: любой
# `.md`-файл вне перечня — посторонний. Файл ЛЮБОГО другого расширения —
# легальное вложение без ограничений имени (ANSWER-1: буквальный единый
# список без различия расширений конфликтовал с уже залоченными `tests/
# test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`
# и `::test_all_files_binary_still_commits_and_clears_the_dir`). Скрытые
# файлы/каталоги (`.`-префикс любого сегмента пути) и `__pycache__/` —
# посторонние независимо от расширения. `acceptance_tests/` — по
# собственным правилам (см. выше), этим правилом не задета.
EXTRANEOUS_TASK_ROOT_FILE_REASON = "посторонний файл в каталоге задачи"
TASK_ROOT_ALLOWED_MD = re.compile(
    r"^(SPEC|PLAN|REVIEW|TEST_REPORT|QUESTIONS|TZ|ANSWER-\d+)\.md$")


def is_extraneous_task_root_file(rel_to_task_dir: str) -> bool:
    """`rel_to_task_dir` — путь файла относительно `tasks/<id>/` (`/`-
    разделённый, например `_head_map.md` или `__pycache__/junk.pyc`).
    `True` — файл посторонний (требование 1, ANSWER-1): `.md` первого
    уровня вне `TASK_ROOT_ALLOWED_MD`, любой скрытый файл/каталог
    (`.`-префикс любого сегмента пути) или файл внутри `__pycache__/`
    первого уровня. `acceptance_tests/` — по собственным правилам
    (`is_extraneous_acceptance_test_file` выше), не этой функцией."""
    parts = rel_to_task_dir.split("/")
    if parts[0] == "acceptance_tests":
        return False
    if any(p.startswith(".") for p in parts):
        return True
    if parts[0] == "__pycache__":
        return True
    if len(parts) == 1 and parts[0].endswith(".md"):
        return not TASK_ROOT_ALLOWED_MD.match(parts[0])
    return False


def extraneous_task_root_files_in(task_dir: Path) -> list[Path]:
    """Посторонние файлы первого уровня ОДНОГО `tasks/<id>/` — ядро,
    используемое `scan_extraneous_task_root_files` (обход `--all` по всем
    задачам сразу) и `orchestrator/fsm_merge_gate.py` (проверка ОДНОЙ
    задачи в scratch-репозитории ДО push, SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
    AC-7) — один и тот же критерий допустимости, не независимая копия."""
    if not task_dir.is_dir():
        return []
    extraneous: list[Path] = []
    for f in sorted(task_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = "/".join(f.relative_to(task_dir).parts)
        if is_extraneous_task_root_file(rel):
            extraneous.append(f)
    return extraneous


def scan_extraneous_task_root_files(tasks_root: Path) -> list[Path]:
    """Посторонние файлы первого уровня `<tasks_root>/*/` — по всем
    каталогам задач сразу (режим `--all`, требование 1/AC-1/AC-2)."""
    if not tasks_root.is_dir():
        return []
    extraneous: list[Path] = []
    for task_dir in sorted(tasks_root.iterdir()):
        if not task_dir.is_dir():
            continue
        extraneous.extend(extraneous_task_root_files_in(task_dir))
    return extraneous


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
    body = section_body(spec_text, "Критерии приёмки")
    ac_numbers = {int(n) for n in AC_ITEM.findall(body)}
    ac_texts = {int(n): text for n, text in AC_ITEM_FULL.findall(body)}
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
        elif kind in ("skip", "escalate", "ci") and not reason:
            errors.append(
                f"AC-{n}: пометка {kind} без причины — впиши причину после "
                f"тире в той же строке, например "
                f"'# AC-{n}: {kind} — <причина>'")
        elif kind == "ci" and not ci_marker_wording_ok(ac_texts.get(n, "")):
            errors.append(
                f"AC-{n}: пометка ci на критерий, формулировка которого не "
                f"про существующие тесты (нет ни одного из ключевых слов "
                f"«существующ», tests/, «зелён», «не ослаб») — замени "
                f"пометку на 'manual' либо перефразируй критерий")
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
# Эскалация только статусом escalate (SPEC 01M1NKTF173WV5CPDZ1C3WW69K,
# требование 6, AC-11/AC-12): PLAN/REVIEW/SPEC с текстом эскалации
# (раздел «Эскалация» с непустыми «Вопросы» либо «Блокирует» —
# skills/escalation-rules.md, «Как эскалировать») ОБЯЗАН нести
# status: escalate — иначе роль ждёт человеческого прочтения текста,
# которое структурно не гарантировано (класс инцидента 04.09: developer
# держал эскалацию текстом в PLAN.md без смены статуса, `advance`
# буксовал на одном и том же отказе гейта).
ESCALATION_SECTION = "Эскалация"
ESCALATION_STATUS_REASON = "эскалация текстом без статуса escalate"
_ESCALATION_BULLET_TMPL = (
    r"^-\s+\*\*{}\*\*\s*(?:[—-]+\s*)?(.*?)(?=\n-\s+\*\*|\Z)")


def _escalation_bullet_text(body: str, label: str) -> str:
    """Текст пункта `- **label** — ...` раздела «Эскалация» до следующего
    такого же пункта верхнего уровня или конца раздела; пусто — пункта
    нет вовсе."""
    pattern = re.compile(_ESCALATION_BULLET_TMPL.format(re.escape(label)),
                         re.M | re.S)
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def escalation_status_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Раздел «Эскалация» с непустыми «Вопросы» либо «Блокирует», но
    status, отличный от escalate — нарушение (AC-11); status: escalate —
    легален (AC-12, позитивный кейс). `path` — только для текста ошибок
    (см. `schema_errors`).

    Применяется к `type` plan/review/spec (SPEC требование 6) — для
    остальных типов канал эскалации не через этот раздел (analyst,
    например, эскалирует QUESTIONS.md целиком, не разделом внутри
    SPEC.md — см. «Контекст» SPEC: для type: spec это правило —
    страховка от ошибки, не рабочий канал).
    """
    if meta.get("type") not in ("plan", "review", "spec"):
        return []
    status = meta.get("status") or ""
    if status == "escalate":
        return []
    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    if ESCALATION_SECTION not in headers:
        return []
    body = section_body(text, ESCALATION_SECTION)
    questions = _escalation_bullet_text(body, "Вопросы")
    blocks = _escalation_bullet_text(body, "Блокирует")
    if not questions and not blocks:
        return []
    return [f"{path}: {ESCALATION_STATUS_REASON} — раздел «{ESCALATION_SECTION}» "
            f"несёт непустые «Вопросы» и/или «Блокирует», а status '{status}' "
            f"— смени status на 'escalate' либо убери текст эскалации из "
            f"артефакта"]


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


# --------------------------------------------------------------------------
# Потолок ролей и обязательное поле budget_usd в SPEC (ADR-0014 часть 1,
# 01M1THKTJ7YT1K410G1KS17MK6): аналитик обязан назвать сумму (требование 2),
# а ни SPEC, ни PLAN не вправе назвать сумму выше ROLE_BUDGET_CAP без
# участия Оператора (требование 3) — две независимые проверки, версия-
# гейтинг применяется только к первой.

def requires_budget_field(meta: dict) -> bool:
    """SPEC обязан нести поле `budget_usd` (ADR-0014, требование 2).

    Версия ниже 5 — формат SPEC до этой задачи, поля не несёт и не обязан:
    тот же приём версии-гейтинга, что `requires_ac_markup`/
    `requires_registry`/`requires_split_assessment`/`requires_zones` выше
    применяют к своим проверкам.
    """
    version = meta.get("schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        return False
    return version >= 5


def _budget_usd_number(meta: dict) -> float | None:
    """Число `budget_usd` тем же разбором, что и `budget.spec_budget`/
    `spend.cli_number` — `None`, если поля нет, оно `bool`/пусто, или не
    разбирается как положительное конечное число.

    `yamlmini.frontmatter` типизирует незакавыченные числа сам (int/float)
    — значение приходит уже числом в частом случае (`budget_usd: 25`) и
    строкой только в кавычках или при мусоре (`budget_usd: дорого`);
    обе формы приводятся к одному разбору.
    """
    if "budget_usd" not in meta:
        return None
    raw = meta["budget_usd"]
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) and raw > 0 else None
    value = spend.cli_number(str(raw).strip())
    return value if value is not None and value > 0 else None


def spec_budget_field_errors(path: Path | str, meta: dict) -> list[str]:
    """`budget_usd` присутствует и разбирается как число для SPEC версии,
    которая его требует (ADR-0014, требование 2, AC-2). `path` — только
    для текста ошибок (см. `schema_errors`).
    """
    if (meta.get("type") or "") != "spec" or not requires_budget_field(meta):
        return []
    if "budget_usd" not in meta:
        return [f"{path}: SPEC schema_version {meta.get('schema_version')} "
               f"обязан нести поле budget_usd (сумма в долларах) — добавь "
               f"frontmatter-поле budget_usd"]
    if _budget_usd_number(meta) is None:
        return [f"{path}: budget_usd '{meta.get('budget_usd')}' не "
               f"разбирается как число — впиши сумму в долларах, "
               f"например budget_usd: 35"]
    return []


ROLE_BUDGET_CAP_HINT = ("раздели задачу (оценка объёма, "
                        "01M1KS8K9RXWHX2PW3ZKB0P903) либо эскалируй вопрос "
                        "бюджета Оператору")


def role_budget_cap_errors(path: Path | str, meta: dict) -> list[str]:
    """`budget_usd` SPEC или PLAN не выше `config.ROLE_BUDGET_CAP`
    (ADR-0014, требование 3, AC-3) — независимо от `schema_version`:
    проверка значения уже существующего необязательного поля, не факта
    его присутствия. `path` — только для текста ошибок.
    """
    if (meta.get("type") or "") not in ("spec", "plan"):
        return []
    value = _budget_usd_number(meta)
    if value is None or value <= config.ROLE_BUDGET_CAP:
        return []
    return [f"{path}: budget_usd ${value:.2f} выше потолка ролей "
           f"${config.ROLE_BUDGET_CAP:.2f} — {ROLE_BUDGET_CAP_HINT}"]


def _content_errors(label: str, text: str) -> list[str]:
    """Ядро `check` — структурная проверка уже прочитанного текста, без
    чтения файла: `label` — путь или его подобие, только для текста
    ошибок (не обязательно существующий `Path`).

    Артефакт-условие перехода FSM может читаться и с диска, и с ВЕТКИ
    задачи при чужом чекауте рабочей копии (SPEC T031, `orchestrator/
    fsm.py`, `guard_refuses`) — сама структурная проверка не должна
    раздваиваться по источнику текста.

    Полная проверка независимо от `status` — режим артефактной ветки
    (01M1R66X5SMD3ZEDCVAJ0DR7K2) применяет к её результату послабление
    для черновиков СНАРУЖИ, в `check_content`, не здесь: эта функция
    сама ничего не знает о режиме и не должна — единственный источник
    правды о правилах содержания, которым пользуется и старый путь
    (без режима), и «сдан»-ветка нового.
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
        errors.extend(spec_budget_field_errors(label, meta))

    if atype in ("spec", "plan"):
        errors.extend(role_budget_cap_errors(label, meta))

    if atype == "review":
        errors.extend(review_evidence_errors(label, text, meta))
        errors.extend(registry_errors(label, text, meta))

    errors.extend(escalation_status_errors(label, text, meta))

    return errors


# --------------------------------------------------------------------------
# Режим артефактной ветки (01M1R66X5SMD3ZEDCVAJ0DR7K2): черновик четырёх
# типов ниже красит CI только нарушением frontmatter, не содержания —
# автокоммит промежуточного шага не должен гасить каждый прогон CI на
# `artifact/**` (требования 1-3 SPEC).
DRAFT_LENIENT_TYPES = {"spec", "plan", "review", "test_report"}

# Поля, которые режим артефактной ветки проверяет у черновика (требование
# 2): task/type — идентификация артефакта, schema_version — обязана быть
# НА МЕСТЕ здесь (в отличие от `_content_errors`, где её отсутствие —
# версия 1 по умолчанию, не ошибка): без версии нельзя судить, какие
# ПОЗЖЕ, на "сдан", правила content к этому черновику применятся.
BASIC_META_FIELDS = ("task", "type")


def is_draft_lenient(meta: dict) -> bool:
    """Черновик одного из DRAFT_LENIENT_TYPES — правила содержания к нему
    в режиме артефактной ветки не применяются (требование 2), только
    базовые условия frontmatter (`basic_frontmatter_errors`)."""
    return (meta.get("type") in DRAFT_LENIENT_TYPES
            and (meta.get("status") or "") == "draft")


def basic_frontmatter_errors(label: str, meta: dict) -> list[str]:
    """Базовые условия режима артефактной ветки для черновика (требование
    2): frontmatter уже прочитан вызывающим кодом (`check_content`) —
    здесь только task/type/schema_version на месте и schema_version не
    выше `SUPPORTED_SCHEMA_VERSION` (`schema_errors`, та же функция, что
    и полная проверка). Остальные правила содержания (обязательные
    секции, zones, AC-разметка, split-assessment, реестр, эскалация) для
    черновика этой проверкой не покрываются — их по-прежнему находит
    `_content_errors`, а `main()` печатает результат как предупреждение
    (требование 5), не как ошибку выхода.
    """
    errors = list(schema_errors(label, meta))
    missing = [f for f in BASIC_META_FIELDS if meta.get(f) in (None, "")]
    if "schema_version" not in meta:
        missing.append("schema_version")
    if missing:
        errors.append(f"{label}: базовая проверка черновика в режиме "
                      f"артефактной ветки — не заполнены обязательные "
                      f"поля frontmatter: {', '.join(missing)}")
    return errors


def check_content(label: str, text: str, artifact_branch_mode: bool = False) -> list[str]:
    """Структурная проверка уже прочитанного текста (см. `_content_errors`).

    `artifact_branch_mode=False` (по умолчанию) — поведение идентично
    `_content_errors` без единого исключения (требование 1, AC-1): все
    существующие вызыватели (`check`, `orchestrator/fsm.py::guard_refuses`
    и переходы FSM через него, тесты) не передают этот параметр и не
    видят разницы.

    `artifact_branch_mode=True` — режим артефактной ветки (требование
    1): для черновика (`is_draft_lenient`) возвращает только базовые
    нарушения frontmatter (`basic_frontmatter_errors`); для всех
    остальных случаев (не черновик, либо тип вне DRAFT_LENIENT_TYPES,
    т.е. tz/questions/answer — требование 3) — тот же полный список, что
    и без режима (требование 2, вторая часть; требование 3).
    """
    if artifact_branch_mode:
        meta = yamlmini.frontmatter(text)
        if meta is not None and is_draft_lenient(meta):
            return basic_frontmatter_errors(label, meta)
    return _content_errors(label, text)


def check(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Guard зовётся не только из CLI, но и из FSM на переходах (T017,
        # требование 5), а там трейсбек читать некому: нечитаемый файл —
        # такое же нарушение структуры, как отсутствующая секция.
        return [f"{path}: не прочитан: {exc}"]
    return check_content(str(path), text)


ARTIFACT_BRANCH_FLAG = "--artifact-branch"


def _artifact_branch_report(files: list[Path]) -> tuple[list[str], list[str], int, int]:
    """(ошибки, предупреждения, сдано, черновиков) по набору файлов в
    режиме артефактной ветки (требования 2, 4, 5): для черновика
    DRAFT_LENIENT_TYPES найденные нарушения содержания уходят в
    предупреждения, для всех остальных случаев — в ошибки, тем же
    правилом, что и `check_content(..., artifact_branch_mode=True)`.
    """
    errors: list[str] = []
    warnings: list[str] = []
    submitted = 0
    drafts = 0
    for f in files:
        if not f.exists():
            errors.append(f"{f}: файл не найден")
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{f}: не прочитан: {exc}")
            continue

        label = str(f)
        meta = yamlmini.frontmatter(text)
        status = (meta or {}).get("status") or ""
        if status == "draft":
            drafts += 1
        else:
            submitted += 1

        full = _content_errors(label, text)
        if meta is not None and is_draft_lenient(meta):
            file_errors = basic_frontmatter_errors(label, meta)
            file_warnings = [e for e in full if e not in file_errors]
        else:
            file_errors = full
            file_warnings = []
        errors.extend(file_errors)
        warnings.extend(file_warnings)
    return errors, warnings, submitted, drafts


def main() -> int:
    args = sys.argv[1:]
    artifact_branch_mode = ARTIFACT_BRANCH_FLAG in args
    if artifact_branch_mode:
        args = [a for a in args if a != ARTIFACT_BRANCH_FLAG]

    if not args:
        print(__doc__)
        return 1

    extraneous_errors: list[str] = []
    if args == ["--all"]:
        files = sorted(Path("tasks").rglob("*.md"))
        # Посторонние файлы `acceptance_tests/` (SPEC
        # 01M1SAA01YRRTWAVADT2F81RRQ, требование 2) и посторонние `.md`
        # первого уровня `tasks/<id>/` (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
        # требование 1) — исключаются из обычного обхода `*.md` ДО
        # `check`/`_artifact_branch_report` (иначе, например, инцидентный
        # `_head_map.md` попал бы туда и получил ошибку разбора
        # frontmatter вместо именованной причины ниже).
        extraneous = scan_extraneous_acceptance_files(Path("tasks"))
        task_root_extraneous = scan_extraneous_task_root_files(Path("tasks"))
        extraneous_set = set(extraneous) | set(task_root_extraneous)
        files = [f for f in files if f not in extraneous_set]
        extraneous_errors = (
            [f"{f}: {EXTRANEOUS_ACCEPTANCE_FILE_REASON}" for f in extraneous]
            + [f"{f}: {EXTRANEOUS_TASK_ROOT_FILE_REASON}"
              for f in task_root_extraneous])
    else:
        files = [Path(a) for a in args]

    if artifact_branch_mode:
        errors, warnings, submitted, drafts = _artifact_branch_report(files)
        errors = extraneous_errors + errors
        print(f"сдано {submitted} / черновиков {drafts} / "
              f"нарушений {len(errors) + len(warnings)}")
        if warnings:
            print("GUARD: предупреждения (черновики артефактной ветки):")
            for w in warnings:
                print(f"  - {w}")
        if errors:
            print("GUARD: нарушения структуры артефактов (сдано):")
            for e in errors:
                print(f"  - {e}")
            return 1
        print(f"GUARD: ок ({len(files)} файлов)")
        return 0

    all_errors: list[str] = list(extraneous_errors)
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
