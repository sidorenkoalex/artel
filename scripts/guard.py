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

Посторонний файл в `acceptance_tests/` (режим `--all`, SPEC
01M1SAA01YRRTWAVADT2F81RRQ): файл вне
разрешённого набора первого уровня (`test_*.py`, `_sandbox.py`,
`markers.py`, `__init__.py`, `*.md`/`*.txt`) — именованная ошибка
«посторонний файл в каталоге планки», не попытка разбора его как
артефакта с frontmatter.
"""
import ast
import copy
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

# Файл живёт двумя жизнями — скрипт и модуль (`from scripts import guard`
# в тестах и в FSM). У скрипта в sys.path лежит scripts/, а не корень
# репозитория, поэтому корень кладётся руками: та же схема, что в artel.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, idgen, spend, stack, test_lint,  # noqa: E402
                          yamlmini, zone_lock)

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
    # Вердикт аудита SPEC (ADR-0022 п.2, SPEC 01M4MQAGRWMWR0GFDM9086P3TD,
    # требование 8): разделы а–ж аудита; поля вердикта — `SPEC_AUDIT_FIELDS`.
    "spec_audit": {
        "sections": ["ТЗ и SPEC", "Факты против кода",
                     "Проверяемость критериев", "Зоны",
                     "Матрица неослабления", "Пути обхода гейтов", "Вердикт"],
        "statuses": {"draft", "ready", "escalate"},
    },
}

# Вердикты аудита SPEC: `pass`/`concerns` ведут на гейт SPEC, `fail` —
# возврат аналитику (`orchestrator/advance_gates/spec_audit.py`).
SPEC_AUDIT_VERDICTS = ("pass", "concerns", "fail")
# Обязательные поля frontmatter `SPEC-AUDIT.md`: вердикт, сработавшие
# сигналы глубины (или «нет») и sha содержимого проверенного SPEC.md.
SPEC_AUDIT_FIELDS = ("verdict", "signals", "spec_sha")


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
# `async def test_…` — тестовый метод наравне с `def test_…` (SPEC
# 01M56TNX1WWKV8PVQ94FT4ZJQB, требование 6): ast-сборщик
# `_collect_qualified_test_functions` их уже не различает.
TEST_METHOD = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(", re.M)
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

# Тот же текст маркера, но НЕ в начале строки — перед `#` есть пробелы
# или табуляция (01M28NX43ERJGHCJN29HVKMCC3): AC_MARKER выше заякорен на
# `^#` и молча не видит такую строку — критерий тихо остаётся без
# пометки, а инцидент 11.09 (`# AC-7: manual`, поставленный с отступом
# вместо снятого тестового метода) показал, что это должно быть
# именованным отказом guard, а не побочным эффектом «нет теста и нет
# пометки». `indented_ac_marker_errors_from_files`/`scan_indented_ac_markers`
# ниже (после `acceptance_traceability_errors`) используют этот образец.
INDENTED_AC_MARKER = re.compile(
    r"^[ \t]+#\s*AC-(\d+):\s*(manual|skip|escalate|ci)\b", re.M)

# Разметка файла не-pytest компонента планки (SPEC 01M59KMPG2ZMK10V556VZVQD65,
# требование 4): тест критерия — вызов `it`/`test` в начале строки (отступ
# допустим) с цепочкой `.concurrent`/`.sequential` и необязательным
# `.each(…)`, чей первый строковый аргумент начинается строго с `AC-<n>: `;
# пометка — `// AC-<n>: …` в начале строки, тем же разбором, что
# `AC_MARKER`. Голова вызова — регуляркой, скобки `.each(…)` и литерал —
# разбором текста (`plank_test_names`): таблица `.each` бывает многострочной.
TEST_CALL_HEAD = re.compile(
    r"^[ \t]*(?:it|test)(?:\.(?:concurrent|sequential))*", re.M)
AC_LABEL_LITERAL = re.compile(r"AC-(\d+): ")
AC_SLASH_MARKER = re.compile(
    r"^//[^\S\n]*AC-(\d+):[^\S\n]*(manual|skip|escalate|ci)\b[^\S\n]*"
    r"(?:[—-]+[^\S\n]*(.*))?", re.M)
INDENTED_SLASH_AC_MARKER = re.compile(
    r"^[ \t]+//[^\S\n]*AC-(\d+):[^\S\n]*(manual|skip|escalate|ci)\b", re.M)
_JS_QUOTES = "'\"`"


def _skip_js_string(source: str, i: int) -> int | None:
    """Индекс за закрывающей кавычкой строки, открытой в `source[i]`;
    `None` — строка не закрыта (у `'`/`"` — до конца строки файла)."""
    quote = source[i]
    j = i + 1
    while j < len(source):
        ch = source[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote:
            return j + 1
        if ch == "\n" and quote != "`":
            return None
        j += 1
    return None


def _skip_js_comment(source: str, j: int) -> int | None:
    """Индекс за комментарием, начатым в `source[j]` (`//` до конца строки,
    `/* … */` до закрытия); `None` — в `source[j]` комментария нет."""
    if source.startswith("//", j):
        end = source.find("\n", j)
        return len(source) if end < 0 else end
    if source.startswith("/*", j):
        end = source.find("*/", j + 2)
        return len(source) if end < 0 else end + 2
    return None


def _closing_paren(source: str, i: int) -> int | None:
    """Индекс `)`, парной `(` в `source[i]`, мимо скобок внутри строк и
    комментариев (апостроф в `// don't` строки не открывает, SPEC
    01M5AQH8M2DKBV30NBY86J34A7, требование 8); `None` — пары нет."""
    depth = 0
    j = i
    while j < len(source):
        ch = source[j]
        after_comment = _skip_js_comment(source, j)
        if after_comment is not None:
            j = after_comment
            continue
        if ch in _JS_QUOTES:
            end = _skip_js_string(source, j)
            if end is None:
                return None
            j = end
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _js_literal_at(source: str, i: int) -> str | None:
    """Строковый литерал, с которого (после пробелов) начинается
    `source[i:]`; `None` — не литерал либо шаблон с подстановкой `${`."""
    while i < len(source) and source[i].isspace():
        i += 1
    if i >= len(source) or source[i] not in _JS_QUOTES:
        return None
    end = _skip_js_string(source, i)
    if end is None:
        return None
    text = source[i + 1:end - 1]
    if source[i] == "`" and "${" in text:
        return None
    return text


def _test_calls(source: str) -> list[tuple[int, str]]:
    """(строка головы вызова, имя теста) вызовов `plank_test_names`, в
    порядке файла; голова `.each(` с многострочной таблицей — строка, где
    стоит `.each(`. Шаблонная таблица `.each`…`` (SPEC
    01M5GXZK2WTZ89AXQ7QY2RJD9R, требование 5) читается так же: имя — первый
    аргумент вызова сразу за литералом."""
    calls = []
    for m in TEST_CALL_HEAD.finditer(source):
        pos = m.end()
        if source.startswith(".each(", pos):
            close = _closing_paren(source, pos + len(".each"))
            if close is None:
                continue
            pos = close + 1
        elif source.startswith(".each`", pos):
            end = _skip_js_string(source, pos + len(".each"))
            if end is None:
                continue
            pos = end
        if not source.startswith("(", pos):
            continue
        name = _js_literal_at(source, pos + 1)
        if name is not None:
            calls.append((source.count("\n", 0, m.start()) + 1, name))
    return calls


def plank_test_names(source: str) -> list[str]:
    """Имена тестов файла не-pytest компонента — литералы вызовов
    требования 4 (у `.each` — первый аргумент второго вызова), в порядке
    файла."""
    return [name for _line, name in _test_calls(source)]


# Запреты в тексте файла с меткой `AC-<n>: ` (SPEC 01M5AQH8M2DKBV30NBY86J34A7,
# требование 7): конструкции, меняющие исход теста мимо его проверки, —
# фокус, пропуск по условию, ожидаемое падение, повтор и предел времени
# теста. Ищутся текстом без комментариев и строковых литералов, без разбора
# синтаксиса JS (доступ по строке и параметры через переменную — принятое
# ограничение SPEC).
PLANK_BAN_TAIL = "запрещено в тексте планки"
_BANNED_MEMBER = re.compile(r"\.\s*(fails|skipIf|runIf|only)\b")
_BANNED_SET_CONFIG = re.compile(r"(?<![\w$.])vi\s*\.\s*setConfig\b")
_BAN_CALL = re.compile(
    r"(?<![\w$.])(it|test|describe|suite)((?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*\(")
# Шаблонная таблица: цепочка, оканчивающаяся `.each`, и сразу литерал `` ` ``.
_BAN_TABLE = re.compile(
    r"(?<![\w$.])(it|test|describe|suite)"
    r"((?:\s*\.\s*[A-Za-z_$][\w$]*)*?\s*\.\s*each)\s*`")
_BAN_NUMBER = re.compile(
    r"[+-]?(?:0[xXoObB][0-9a-fA-F_]+|(?:\d[\d_]*(?:\.\d*)?|\.\d+)"
    r"(?:[eE][+-]?\d+)?)n?")
_BAN_OBJECT_KEY = re.compile(r"\s*([A-Za-z_$][\w$]*)")
_BAN_KEYS = ("retry", "timeout")
_OPENERS, _CLOSERS = "([{", ")]}"


def _js_mask(source: str) -> str:
    """Текст `source`, где комментарии и содержимое строковых литералов
    заменены пробелами; кавычки, переводы строк и позиции сохранены —
    находку по маске можно читать в исходном тексте по тем же индексам."""
    out = list(source)

    def blank(start: int, end: int) -> None:
        for k in range(start, end):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < len(source):
        end = _skip_js_comment(source, i)
        if end is not None:
            blank(i, end)
            i = end
            continue
        if source[i] in _JS_QUOTES:
            end = _skip_js_string(source, i)
            if end is None:
                line_end = source.find("\n", i)
                stop = len(source) if line_end < 0 or source[i] == "`" \
                    else line_end
                blank(i + 1, stop)
                i = stop
                continue
            blank(i + 1, end - 1)
            i = end
            continue
        i += 1
    return "".join(out)


def _masked_closing(masked: str, i: int) -> int | None:
    """Индекс скобки, закрывающей `masked[i]`, по маске (без строк и
    комментариев); `None` — пары нет."""
    depth = 0
    for j in range(i, len(masked)):
        if masked[j] in _OPENERS:
            depth += 1
        elif masked[j] in _CLOSERS:
            depth -= 1
            if depth == 0:
                return j
    return None


def _top_level_parts(masked: str, start: int, end: int) -> list[tuple[int, int]]:
    """(начало, конец) элементов списка через запятую первого уровня в
    `masked[start:end]`, без пробелов по краям; пустые пропущены."""
    parts, depth, begin = [], 0, start
    for j in range(start, end + 1):
        ch = masked[j] if j < end else ","
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth -= 1
        elif ch == "," and depth == 0:
            left, right = begin, j
            while left < right and masked[left].isspace():
                left += 1
            while right > left and masked[right - 1].isspace():
                right -= 1
            if left < right:
                parts.append((left, right))
            begin = j + 1
    return parts


def _object_keys(source: str, masked: str, start: int, end: int) -> list[str]:
    """Собственные ключи объекта-литерала `masked[start:end]` (`{ … }`):
    имя, ключ в кавычках и сокращение `{ retry }`; объекты глубже не
    рассматриваются."""
    keys = []
    for left, right in _top_level_parts(masked, start + 1, end - 1):
        if source[left] in _JS_QUOTES:
            close = _skip_js_string(source, left)
            if close is not None:
                keys.append(source[left + 1:close - 1])
            continue
        match = _BAN_OBJECT_KEY.match(masked, left, right)
        if match:
            keys.append(match.group(1))
    return keys


def _call_arguments(masked: str, match) -> tuple[int, int] | None:
    """(открывающая, закрывающая) скобки аргументов вызова `match`
    `_BAN_CALL`; у цепочки с `.each` — вторая пара скобок (первая —
    таблица)."""
    open_at = match.end() - 1
    close = _masked_closing(masked, open_at)
    if close is None:
        return None
    chain = [part.strip() for part in match.group(2).split(".") if part.strip()]
    if "each" not in chain:
        return open_at, close
    k = close + 1
    while k < len(masked) and masked[k].isspace():
        k += 1
    if k >= len(masked) or masked[k] != "(":
        return None
    second = _masked_closing(masked, k)
    return None if second is None else (k, second)


def _table_arguments(masked: str, match) -> tuple[int, int] | None:
    """(открывающая, закрывающая) скобки аргументов шаблонной таблицы
    `match` `_BAN_TABLE` (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R, требование 5):
    первая пара скобок после литерала. В маске содержимое литерала
    затёрто, кавычки сохранены — закрывающая `` ` `` следующая."""
    close = masked.find("`", match.end())
    if close < 0:
        return None
    k = close + 1
    while k < len(masked) and masked[k].isspace():
        k += 1
    if k >= len(masked) or masked[k] != "(":
        return None
    end = _masked_closing(masked, k)
    return None if end is None else (k, end)


def _ban_findings(source: str) -> list[tuple[int, str]]:
    """(позиция, что найдено) запретов требования 7 в тексте файла с
    меткой."""
    masked = _js_mask(source)
    found = [(m.start(), f"вызов .{m.group(1)}")
             for m in _BANNED_MEMBER.finditer(masked)]
    found += [(m.start(), "vi.setConfig")
              for m in _BANNED_SET_CONFIG.finditer(masked)]
    calls = [(m, _call_arguments(masked, m)) for m in _BAN_CALL.finditer(masked)]
    calls += [(m, _table_arguments(masked, m))
              for m in _BAN_TABLE.finditer(masked)]
    for m, span in calls:
        callee = m.group(1) + "".join(m.group(2).split())
        if span is None:
            continue
        args = _top_level_parts(masked, span[0] + 1, span[1])
        for left, right in args:
            text = masked[left:right]
            if _BAN_NUMBER.fullmatch(text):
                found.append((left, f"числовой литерал {text} в аргументах "
                                    f"{callee}"))
            elif text.startswith("{") and text.endswith("}"):
                found += [(left, f"объект с ключом {key} в аргументах {callee}")
                          for key in _object_keys(source, masked, left, right)
                          if key in _BAN_KEYS]
        if not args or source[args[0][0]] not in _JS_QUOTES:
            continue
        left, right = args[0]
        name = source[left + 1:right - 1]
        if len(AC_LABEL_LITERAL.findall(name)) > 1:
            found.append((left, f"две метки AC-<n>: в одном литерале имени "
                                f"«{name}»"))
        if m.group(1) in ("describe", "suite") and AC_LABEL_LITERAL.match(name):
            found.append((left, f"литерал {m.group(1)} с меткой AC-<n>: в "
                                f"начале «{name}»"))
    return sorted(set(found))


def plank_ban_errors(files: list[tuple[str, str]],
                     rule: "PlankRule | None") -> list[str]:
    """Запреты в тексте файлов с меткой `AC-<n>: ` по правилу `rule` (SPEC
    01M5AQH8M2DKBV30NBY86J34A7, требование 7): `.fails`, `.skipIf`,
    `.runIf`, `.only`, `vi.setConfig`; объект с ключом `retry`/`timeout`
    или числовой литерал в аргументах первого уровня вызова
    `it`/`test`/`describe`/`suite` (у `.each(t)(…)` — во второй паре
    скобок, у шаблонной таблицы `.each`…`(…)` — в первой паре после
    литерала); две метки `AC-<n>: ` в литерале имени; литерал `describe`
    или `suite` с меткой в начале. Файлы pytest и прочие без метки не
    проверяются.
    Отказ — «<файл>:<строка>: <что найдено> — запрещено в тексте планки»."""
    errors = []
    for label, source in files:
        if rule is None or not rule.is_labelled(Path(label).name):
            continue
        for pos, what in _ban_findings(source):
            line = source.count("\n", 0, pos) + 1
            errors.append(f"{label}:{line}: {what} — {PLANK_BAN_TAIL}")
    return errors


def _labelled_ac_content(content: str) -> tuple[set, dict]:
    """(AC, покрытые тестом) и пометки `//` текста файла с меткой
    `AC-<n>: `."""
    tested = set()
    for name in plank_test_names(content):
        m = AC_LABEL_LITERAL.match(name)
        if m:
            tested.add(int(m.group(1)))
    markers = {int(n): (kind, reason.strip())
               for n, kind, reason in AC_SLASH_MARKER.findall(content)}
    return tested, markers

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

# Заявка мутации в докстринге теста (01M29A0F88P9GKSXFW90F99H2N, требование
# 1): «Ловит мутацию: <что сломали — и тест покраснеет>», непустой текст на
# той же строке после двоеточия — тот же приём, что REDNESS_MARKER выше.
MUTATION_CLAIM = re.compile(r"Ловит мутацию:[^\S\n]*(\S.*)")


def section_body(text: str, name: str) -> str:
    """Текст секции `## name` до следующего `## ` заголовка или конца файла.

    Публичная (не `_section_body`): переиспользуется вне этого модуля
    `orchestrator/fsm.py` для ветко-корректного расчёта трассируемости AC
    с ВЕТКИ задачи, не только с диска (SPEC T031).
    """
    match = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)",
                      text, re.M | re.S)
    return match.group(1) if match else ""


# Приложение PLAN.md к защищённому пути (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF,
# требование 1): роль не вправе править `config.PROTECTED_PATHS` сама и
# предлагает правку unified-диффом, который применяет пульт на мерже.
# Формат сложился практикой (восемь таких разделов в `tasks/` к 20.09) и
# здесь впервые становится машиночитаемым.

# Раздел приложения узнаётся по ПРЕФИКСУ заголовка, а не по точному имени
# (`section_body` выше сверяет имя целиком): практика пишет заголовок с
# хвостом — «## Приложение: правка skills/test-authoring.md».
APPENDIX_SECTION_PREFIX = "Приложение"
_APPENDIX_HEADING = re.compile(rf"^##\s+{re.escape(APPENDIX_SECTION_PREFIX)}",
                               re.M)
# Ограда блока диффа внутри раздела и заголовок пути внутри блока.
# Ограда закреплена на КОЛОНКЕ 0 (R2-F1, REVIEW итерация 2): в unified-
# диффе каждая строка содержимого начинается с пробела, `+` или `-`,
# поэтому ограда, допускавшая ведущие пробелы, закрывалась контекстной
# строкой ` ``` ` — приложение к защищённому markdown-файлу, несущему
# ограду кода (`docs/adr/0003-target-projects.md` — реальный такой файл),
# разбиралось в обрезанный патч, и гейт отказывал переходу диффом,
# в котором роли нечего чинить.
_DIFF_FENCE_OPEN = re.compile(r"^```diff\s*$")
_DIFF_FENCE_CLOSE = re.compile(r"^```\s*$")
_DIFF_GIT_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)\s*$", re.M)
# Начало заголовка файла — по нему узнаётся дифф, оставшийся ВНЕ блоков
# ```diff (ограда набрана голым ```): такой дифф не приложение, но и не
# молчание.
_DIFF_GIT_ANY = re.compile(r"^diff --git ", re.M)

APPENDIX_NO_HEADER_ERROR = "приложение PLAN: нет заголовка diff --git"
# Дифф раздела «## Приложение», не попавший ни в один блок ```diff
# (R1-F1, REVIEW итерация 1): голая ограда ``` вместо ```diff давала ни
# приложения, ни ошибки — правка Оператора пропадала бесследно.
APPENDIX_DIFF_OUTSIDE_BLOCK_ERROR = (
    "приложение PLAN: дифф вне блока ```diff — огороди его ```diff")


def appendix_rename_header_error(old: str, new: str) -> str:
    """Именованная ошибка для заголовка `diff --git a/<старый> b/<новый>`
    (R2-F2, REVIEW итерация 2).

    Переименование приложением не поддерживается: защищённость
    проверялась бы по одному пути, а файл создавался бы по другому,
    сколь угодно постороннему. До этой ошибки такой заголовок отвергался
    текстом «нет заголовка diff --git» — роль читала в брифе, что
    заголовка нет, видела его на месте и чинила наугад, каждый раз ценой
    гарантированного шага developer."""
    return (f"приложение PLAN: заголовок diff --git называет разные пути "
            f"a/{old} и b/{new} — переименование приложением не "
            f"поддерживается")


def appendix_unprotected_path_error(path: str) -> str:
    """Именованная ошибка требования 1 для пути вне `config.PROTECTED_PATHS`:
    такую правку роль вносит сама, в своей ветке, под ревью и CI ветки —
    коммитом Оператора в main ей ехать незачем."""
    return (f"приложение PLAN: путь {path} не защищённый — правь в ветке "
            f"задачи")


class PlanAppendix(NamedTuple):
    """Одно приложение PLAN.md: `paths` — ВСЕ пути из заголовков
    `diff --git` блока (не из заголовка раздела: заголовок раздела —
    свободный текст), `diff` — текст блока ```diff без самой ограды,
    годный на вход `git apply`.

    Путей несколько, потому что `git diff` по двум файлам даёт один текст
    с двумя заголовками, и Оператор вставляет его в PLAN одним блоком
    (образец — `tasks/01M1THKTJ7YT1K410G1KS17MK6/PLAN.md`, пять
    заголовков в одном блоке). До R1-F1 разбор брал только первый: `git
    apply` правил все файлы блока, а `git add` уносил в main один —
    остальная правка Оператора терялась вместе со scratch-деревом."""
    paths: tuple[str, ...]
    diff: str


def _appendix_path_is_protected(path: str, protected=None) -> bool:
    # Общая формула всех мест сверки с перечнем (SPEC
    # 01M3MVXZXF25KYY2P213E0M39X, требование 5); `protected=None` —
    # перечень артели `config.PROTECTED_PATHS`.
    return config.is_protected_path(path, protected)


def _diff_blocks(body: str) -> tuple[list[str], str]:
    """(тексты ВСЕХ блоков ```diff тела раздела в порядке появления без
    строк-оград, остальной текст тела).

    Незакрытый блок в конце тела считается закрытым концом раздела: PLAN
    с оборванной оградой не повод потерять дифф молча (ошибку про него
    всё равно выдаст `git apply`).

    Остаток нужен вызывающему, чтобы заметить дифф, огороженный голым
    ``` (такая ограда блоком ```diff не является и до R1-F1 просто
    растворялась в тексте раздела)."""
    blocks, current, outside = [], None, []
    for line in body.splitlines():
        if current is None:
            if _DIFF_FENCE_OPEN.match(line):
                current = []
            else:
                outside.append(line)
            continue
        if _DIFF_FENCE_CLOSE.match(line):
            blocks.append("\n".join(current) + "\n")
            current = None
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current) + "\n")
    return blocks, "\n".join(outside) + "\n"


def _appendix_section_bodies(text: str) -> list[str]:
    """Тела всех разделов, заголовок которых начинается на «## Приложение»,
    в порядке появления: от конца своего заголовка до следующего `## `
    заголовка любого раздела или конца текста."""
    bodies = []
    for match in _APPENDIX_HEADING.finditer(text):
        start = text.find("\n", match.end())
        if start == -1:
            continue
        nxt = re.search(r"^##\s", text[start:], re.M)
        bodies.append(text[start:start + nxt.start()] if nxt else text[start:])
    return bodies


def plan_appendices(text: str,
                    protected=None) -> tuple[list[PlanAppendix], list[str]]:
    """Приложения PLAN.md и именованные ошибки требования 1 (SPEC
    01M2YSHDKWFJN3XSJ618Z74FNF, AC-1..AC-4).

    `protected` — перечень защищённых путей проекта задачи (SPEC
    01M45FK56DWMNBRKA1VWM12H19, требование 2): вызовы пульта передают его
    явно (`repo_context.protected_paths`); `None` — перечень артели
    `config.PROTECTED_PATHS`, в том числе в самостоятельном запуске guard.

    Разбирается КАЖДЫЙ блок ```diff КАЖДОГО раздела «## Приложение…» —
    и порядок приложений на выходе равен порядку их появления в тексте:
    его читает и гейт применимости на выходе `in_dev`, и применение на
    мерже (приложения к одному и тому же пути обязаны лечь друг на друга
    в том же порядке, в каком их написал Оператор).

    Пути блока берутся из ВСЕХ его заголовков `diff --git` (R1-F1):
    многофайловый дифф — один патч и одно приложение, но `git add` на
    мерже и проверка защищённости обязаны видеть каждый его файл.

    Блок без единого заголовка `diff --git`, блок с заголовком-
    переименованием (`a/` и `b/` называют разные пути), блок с путём вне
    `config.PROTECTED_PATHS` и дифф, оставшийся вне блоков ```diff, в
    список приложений НЕ попадают — про каждый возвращается СВОЯ
    именованная ошибка: молчаливый пропуск означал бы, что Оператор
    узнаёт о потерянной правке только на мерже, а общая ошибка на два
    разных повода посылала бы роль чинить не то (R2-F2). PLAN без
    разделов «## Приложение» — `([], [])`, ни одной ошибки.
    """
    appendices: list[PlanAppendix] = []
    errors: list[str] = []
    for body in _appendix_section_bodies(text):
        blocks, outside = _diff_blocks(body)
        if _DIFF_GIT_ANY.search(outside):
            errors.append(APPENDIX_DIFF_OUTSIDE_BLOCK_ERROR)
        for block in blocks:
            headers = _DIFF_GIT_HEADER.findall(block)
            if not headers:
                errors.append(APPENDIX_NO_HEADER_ERROR)
                continue
            # Заголовок с разными a/ и b/ (переименование) корректным не
            # считается: защищённость проверялась бы по одному пути, а
            # файл создавался бы по другому, сколь угодно постороннему.
            # Ошибка своя (R2-F2): текст про отсутствующий заголовок
            # отправлял роль искать то, что у неё на месте.
            renames = [(old, new) for old, new in headers if old != new]
            if renames:
                errors.extend(appendix_rename_header_error(old, new)
                              for old, new in renames)
                continue
            paths = list(dict.fromkeys(old for old, _new in headers))
            unprotected = [p for p in paths
                           if not _appendix_path_is_protected(p, protected)]
            if unprotected:
                errors.extend(appendix_unprotected_path_error(p)
                              for p in unprotected)
                continue
            appendices.append(PlanAppendix(tuple(paths), block))
    return appendices, errors


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


def scan_ac_content(sources: list, rule: "PlankRule | None" = None
                    ) -> tuple[set, dict]:
    """(AC, покрытые тестом) и {AC: (пометка, причина)} по уже прочитанным
    текстам файлов *.py под acceptance_tests/.

    Источник-агностичное ядро `scan_acceptance_tests` (диск) и ветко-
    корректного чтения `orchestrator/fsm.py` (git, SPEC T031, AC-3) — сам
    разбор AC-разметки не должен раздваиваться между источником файлов.

    Элемент `sources` — текст (разбор Python, как прежде) либо пара (имя
    файла, текст): у пары синтаксис выбирает правило планки `rule` по
    имени файла (SPEC 01M59KMPG2ZMK10V556VZVQD65, требование 3). Тексты
    долгоживущих файлов вызывающие передают текстом — в G2а это Python.
    """
    tested: set = set()
    markers: dict = {}
    for item in sources:
        name, content = ("", item) if isinstance(item, str) else item
        if rule is not None and name and rule.is_labelled(Path(name).name):
            file_tested, file_markers = _labelled_ac_content(content)
            tested |= file_tested
            markers.update(file_markers)
            continue
        tested.update(int(n) for n in TEST_AC.findall(content))
        for n, kind, reason in AC_MARKER.findall(content):
            markers[int(n)] = (kind, reason.strip())
    return tested, markers


def scan_acceptance_tests(tdir: Path, rule: "PlankRule | None" = None
                          ) -> tuple[set, dict]:
    """(AC, покрытые тестом) и {AC: (пометка, причина)} из acceptance_tests/
    рабочей копии.

    Статический разбор текстом, без импорта файлов — теста без разметки
    `test_ac<n>_` парсер не увидит, и это осознанно: содержательность
    (тест действительно проверяет то, что заявляет) — дело ревью и прогона
    pytest на гейте (orchestrator/acceptance.py), не структурной проверки.

    Только `test_*.py` (SPEC T081) — тот же приём, что `scan_redness_markers`
    (T064): маркер или тест-метод во вспомогательном файле вроде
    `_sandbox.py` (например, литерал-фикстура в исходнике теста другой
    задачи) не должен читаться как настоящая AC-разметка этой задачи.

    `rule` не по умолчанию — тестовые файлы планки по правилу, синтаксис
    файла по его компоненту (SPEC 01M59KMPG2ZMK10V556VZVQD65, требования
    3-4); без правила и при правиле-умолчании — прежний разбор.
    """
    if not _by_rule(rule):
        return _scan_acceptance_tests(tdir)
    return scan_ac_content([(f.name, text) for f, text
                            in _rule_plank_files(tdir, rule, tests_only=True)],
                           rule)


def _scan_acceptance_tests(tdir: Path) -> tuple[set, dict]:
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


def count_test_methods(tdir: Path, rule: "PlankRule | None" = None) -> int:
    """Число тестовых методов в acceptance_tests/*.py — статический счёт.

    `rule` не по умолчанию — файлы компонентов планки: у pytest-компонента
    методы всех его файлов, у компонента с меткой `AC-<n>: ` — вызовы
    тестов его тестовых файлов (`plank_test_names`)."""
    if _by_rule(rule):
        count = 0
        for f, content in _rule_plank_files(tdir, rule, tests_only=False):
            if not rule.is_labelled(f.name):
                count += len(TEST_METHOD.findall(content))
            elif rule.is_test(f.name):
                count += len(plank_test_names(content))
        return count
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


def first_comment(source: str) -> str | None:
    """Первый комментарий файла не-pytest компонента (SPEC
    01M59KMPG2ZMK10V556VZVQD65, требование 5): подряд идущие строки `//`
    либо один блок `/* … */` до первой непустой строки кода; `None` —
    файл начинается с кода."""
    lines = source.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i == len(lines):
        return None
    head = lines[i].lstrip()
    if head.startswith("//"):
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("//"):
            block.append(lines[i].lstrip()[2:])
            i += 1
        return "\n".join(block)
    if head.startswith("/*"):
        rest = "\n".join([head] + lines[i + 1:])
        end = rest.find("*/", 2)
        return None if end < 0 else rest[2:end]
    return None


# Место маркера красноты в тексте отказа: Python — докстринг модуля, файл
# не-pytest компонента — первый комментарий (требование 5).
REDNESS_PLACE_DOCSTRING = "в докстринге модуля"
REDNESS_PLACE_FIRST_COMMENT = "в первом комментарии файла"


def redness_marker_errors_from_files(files: list[tuple[str, str]],
                                     rule: "PlankRule | None" = None
                                     ) -> list[str]:
    """Ядро проверки маркера красноты (SPEC T064, требования 1–3) по уже
    прочитанным (label, текст) парам файлов `acceptance_tests/test_*.py` —
    без чтения файлов: источник (рабочая копия или ВЕТКА задачи, тот же
    приём, что `traceability_errors_from_content`) выбирает вызывающий код.

    `rule` — файл компонента с меткой `AC-<n>: ` (по имени из `label`)
    несёт маркер в первом комментарии (`first_comment`).
    """
    errors: list[str] = []
    for label, source in files:
        if rule is not None and rule.is_labelled(Path(label).name):
            text, place = first_comment(source), REDNESS_PLACE_FIRST_COMMENT
        else:
            text, place = module_docstring(source), REDNESS_PLACE_DOCSTRING
        if not has_redness_marker(text):
            errors.append(
                f"{label}: нет маркера «Красен до реализации:» или «Зелёный "
                f"с рождения:» с непустым объяснением на той же строке сразу "
                f"после двоеточия {place} — допиши объяснение "
                f"сразу после двоеточия на той же строке, например «Красен "
                f"до реализации: <причина>» (перенос объяснения на "
                f"следующую строку не считается заполненным маркером)")
    return errors


def scan_redness_markers(tdir: Path, rule: "PlankRule | None" = None
                         ) -> list[str]:
    """Ошибки маркера красноты для `acceptance_tests/test_*.py` рабочей
    копии (SPEC T064). Только `test_*.py` — SPEC требование 1 называет
    этот шаблон, вспомогательные файлы (`_sandbox.py`, `__init__.py`)
    маркером не размечаются.

    `rule` не по умолчанию — тестовые файлы планки по правилу.
    """
    if _by_rule(rule):
        return redness_marker_errors_from_files(
            [(str(f), text) for f, text
             in _rule_plank_files(tdir, rule, tests_only=True)], rule)
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


# Разделитель квалифицированного имени тестового метода: `Class::test_x`
# — тот же разделитель, которым Оператор называет метод в мандате
# «Ослабление тестов разрешено: tests/test_y.py::Class::test_z» (SPEC
# 01M3FQ2V77QNK95Z599DM124QN, требование 4).
TEST_NAME_SEP = "::"


def _collect_qualified_test_functions(tree: ast.Module) -> dict[str, ast.AST]:
    """Функции и методы `test_*` на уровне модуля и внутри классов (не
    глубже) под КВАЛИФИЦИРОВАННЫМ именем: `test_x` для функции модуля,
    `Class::test_x` для метода класса.

    Область та же, что у `_collect_test_functions` ниже — эта функция её
    единственный источник: «что считается тестовым методом» в пульте
    решается здесь и только здесь (SPEC 01M3FQ2V77QNK95Z599DM124QN,
    требование 1). Квалифицированное имя нужно гейту неослабления тестов:
    одноимённые методы двух классов одного файла — разные тесты, и
    исчезновение одного из них обязано называться вместе с классом (AC-3).
    """
    functions: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name.startswith("test_"):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                        sub.name.startswith("test_"):
                    functions[f"{node.name}{TEST_NAME_SEP}{sub.name}"] = sub
    return functions


def _collect_test_functions(tree: ast.Module) -> dict[str, ast.AST]:
    """Те же узлы, что `_collect_qualified_test_functions`, но под ГОЛЫМ
    именем метода — контракт гейта заявки мутации
    (`test_functions_without_mutation_claim` ниже, SPEC
    01M29A0F88P9GKSXFW90F99H2N, требование 1): помощник `test_*`,
    объявленный внутри другой функции, не тестовый метод фреймворка и не
    собирается им. Порядок и правило «последний одноимённый побеждает» —
    те же, что были до выделения квалифицированного сборщика."""
    return {name.rsplit(TEST_NAME_SEP, 1)[-1]: node
            for name, node in _collect_qualified_test_functions(tree).items()}


# Имена декораторов пропуска и ожидаемого провала (SPEC
# 01M3FQ2V77QNK95Z599DM124QN, требование 1, класс находки «г»): решает
# ПОСЛЕДНИЙ сегмент точечного имени — так один набор покрывает и
# `@unittest.skipIf`, и `@skipIf` от `from unittest import skipIf`, и
# `@pytest.mark.xfail`.
SKIP_DECORATOR_NAMES = frozenset((
    "skip", "skipIf", "skipUnless", "expectedFailure", "skipif", "xfail"))

# Вызовы пропуска в теле метода — по паре «последний сегмент имени,
# требуемый префикс»: `self.skipTest(...)` и `pytest.skip(...)`. Голый
# `skip(` в теле маркером не считается: `skipTest` однозначен, а `skip`
# без `pytest.` — обычное имя чего угодно.
SKIP_CALL_NAMES = frozenset(("skipTest", "pytest.skip"))


def _called_dotted_name(node: ast.AST) -> str:
    """Точечное имя декоратора или вызываемого: `unittest.skip`,
    `pytest.mark.xfail`, `self.skipTest`. Пустая строка — имя не
    складывается из цепочки Name/Attribute (вычисляемый декоратор).

    Разбор самой цепочки — общий `_dotted_name` ниже по файлу; здесь
    добавлено только разворачивание вызова: `@unittest.skip` и
    `@unittest.skip("причина")` — один и тот же маркер.
    """
    if isinstance(node, ast.Call):
        node = node.func
    return _dotted_name(node) or ""


def _decorator_skip_markers(node: ast.AST) -> set:
    """Маркеры пропуска среди декораторов `node` — в виде текста, каким их
    видит человек (`@unittest.skip`)."""
    markers = set()
    for decorator in getattr(node, "decorator_list", []):
        dotted = _called_dotted_name(decorator)
        if dotted and dotted.rsplit(".", 1)[-1] in SKIP_DECORATOR_NAMES:
            markers.add(f"@{dotted}")
    return markers


def _body_skip_markers(node: ast.AST) -> set:
    """Маркеры пропуска среди ВЫЗОВОВ в теле `node` (`self.skipTest(`,
    `pytest.skip(`) — декоратора может не быть вовсе, а тест всё равно
    выключен (требование 1, класс «г», вторая половина)."""
    markers = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        dotted = _called_dotted_name(sub.func)
        if not dotted:
            continue
        if dotted.rsplit(".", 1)[-1] == "skipTest" or dotted in SKIP_CALL_NAMES:
            markers.add(f"{dotted}(")
    return markers


def _parse_or_none(source):
    """`ast.Module` из `source`; `None` — текста нет (`source is None`) или
    он не парсится. Не исключение: сведения об одной из двух сторон
    сравнения могут законно отсутствовать (файл добавлен/удалён), а
    непарсящийся файл — забота CI, не повод ронять гейт трейсбеком (тот же
    fail-safe, что у `test_functions_without_mutation_claim` ниже)."""
    if source is None:
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def qualified_test_methods(source) -> dict[str, ast.AST]:
    """Тестовые методы текста `source` по квалифицированному имени
    (`_collect_qualified_test_functions`). Пустой словарь — текста нет либо
    он не парсится."""
    tree = _parse_or_none(source)
    return {} if tree is None else _collect_qualified_test_functions(tree)


def test_skip_markers(source) -> dict[str, set]:
    """Маркеры пропуска и ожидаемого провала текста `source` по имени, на
    котором они стоят: квалифицированное имя метода (`Class::test_x`) —
    его декораторы и вызовы пропуска в теле; имя класса (`Class`) —
    декораторы самого класса (один декоратор над классом гасит все его
    тесты, AC-4).

    Класс без единого тестового метода в результат не попадает: предмет
    рубежа — выключенные тесты, а не любой декорированный класс файла.
    Пустой словарь — текста нет либо он не парсится.
    """
    tree = _parse_or_none(source)
    if tree is None:
        return {}
    markers: dict[str, set] = {}
    for name, node in _collect_qualified_test_functions(tree).items():
        found = _decorator_skip_markers(node) | _body_skip_markers(node)
        if found:
            markers[name] = found
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        has_tests = any(
            isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
            and sub.name.startswith("test_") for sub in node.body)
        if not has_tests:
            continue
        found = _decorator_skip_markers(node)
        if found:
            markers[node.name] = found
    return markers


# Пропуск через имя-метку и модульные пропуски (SPEC
# 01M56TNX1WWKV8PVQ94FT4ZJQB, требования 1, 3, 4). Имя модульной марки
# pytest и вызовы пропуска уровня модуля: `pytest.skip` — тем же точным
# именем, что в теле метода; `importorskip` — последним сегментом, имя
# однозначно.
PYTESTMARK_NAME = "pytestmark"
MODULE_SKIP_CALL_NAMES = frozenset(("pytest.skip",))
MODULE_IMPORTORSKIP_NAME = "importorskip"
MODULE_LEVEL_NOTE = "уровня модуля"


class SkipOccurrence(NamedTuple):
    """Вхождение пропуска, которого не видит `test_skip_markers`: `marker`
    — текст маркера (для метки и `pytestmark` — со значением, чтобы смена
    значения при прежнем имени была новым маркером), `node` — узел марки
    (значение метки, элемент `pytestmark`) либо вызов пропуска уровня
    модуля, `inside_if` — `None` у формы декоратора, у вызова — стоит ли
    он в ветке `if`/`else`."""

    marker: str
    node: ast.AST
    inside_if: bool | None


def _is_skip_mark(node: ast.AST) -> bool:
    """Узел — марка пропуска либо ожидаемого провала тем же правилом
    последнего сегмента, что у прямого декоратора."""
    dotted = _called_dotted_name(node)
    return bool(dotted) and dotted.rsplit(".", 1)[-1] in SKIP_DECORATOR_NAMES


def _module_labels(tree: ast.Module) -> dict:
    """{имя: узел значения} имён-меток модуля — присваивание верхнего
    уровня `имя = <марка пропуска>` (форма (а) требования 1). Последнее
    присваивание имени побеждает: переприсваивание не-меткой метку снимает.
    `pytestmark` меткой не считается — у него своё правило."""
    labels: dict = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or \
                    target.id == PYTESTMARK_NAME:
                continue
            if _is_skip_mark(node.value):
                labels[target.id] = node.value
            else:
                labels.pop(target.id, None)
    return labels


def skip_label_values(source) -> dict:
    """{имя-метка: текст значения} модуля `source` — по нему узел
    сравнения видит метки, сменившие значение, и ищет их импортёров вне
    диффа (требование 3). Пусто — текста нет либо он не парсится."""
    tree = _parse_or_none(source)
    if tree is None:
        return {}
    return {name: ast.unparse(value)
            for name, value in _module_labels(tree).items()}


def _imported_labels(tree: ast.Module, modules: "TestModules | None") -> dict:
    """{имя: узел значения} меток, импортированных `from <модуль> import
    имя` (форма (б) требования 1) из модуля области тестов проекта —
    `modules.module_path` решает, виден ли модуль режиму."""
    if modules is None:
        return {}
    labels: dict = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level or \
                not node.module:
            continue
        path = modules.module_path(node.module)
        if path is None:
            continue
        for alias in node.names:
            if alias.asname is not None:
                continue
            value = modules.labels(path).get(alias.name)
            if value is not None:
                labels[alias.name] = value
    return labels


def _module_level_calls(node: ast.AST, inside_if: bool = False):
    """(вызов, точечное имя, внутри ли ветки `if`/`else`) пропусков уровня
    модуля: любой оператор вне тел функций и классов на любой глубине
    (`try`/`except`/`with` в том числе). Условие самого `if` условным не
    считается — оно вычисляется всегда."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                         ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, ast.If):
        yield from _module_level_calls(node.test, inside_if)
        for sub in node.body + node.orelse:
            yield from _module_level_calls(sub, True)
        return
    if isinstance(node, ast.Call):
        dotted = _called_dotted_name(node.func)
        if dotted in MODULE_SKIP_CALL_NAMES or (
                dotted and dotted.rsplit(".", 1)[-1] ==
                MODULE_IMPORTORSKIP_NAME):
            yield node, dotted, inside_if
    for child in ast.iter_child_nodes(node):
        yield from _module_level_calls(child, inside_if)


def _pytestmark_elements(tree: ast.Module) -> list:
    """Марки пропуска последнего присваивания `pytestmark = …` верхнего
    уровня: одна марка либо элементы списка/кортежа."""
    value = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == PYTESTMARK_NAME
                for t in node.targets):
            value = node.value
    if value is None:
        return []
    elements = value.elts if isinstance(value, (ast.List, ast.Tuple)) \
        else [value]
    return [e for e in elements if _is_skip_mark(e)]


def resolved_skip_markers(source, modules: "TestModules | None" = None) -> dict:
    """{имя: [SkipOccurrence]} пропусков, которых не видит
    `test_skip_markers` (SPEC 01M56TNX1WWKV8PVQ94FT4ZJQB): декоратор-метка
    метода или класса (имя, связанное в этом модуле либо импортированное
    из модуля `modules`), `pytestmark` и вызовы `pytest.skip(`/
    `pytest.importorskip(` уровня модуля — последние два на каждом
    тестовом методе файла. Ключи — те же, что у `test_skip_markers`.

    Маркер метки несёт её значение (`@requires_pg = pytest.mark.skip()`):
    смена значения при прежнем тексте декоратора — новый маркер на том же
    имени (требование 3)."""
    tree = _parse_or_none(source)
    if tree is None:
        return {}
    labels = {**_imported_labels(tree, modules), **_module_labels(tree)}
    methods = _collect_qualified_test_functions(tree)
    found: dict = {}

    def label_occurrences(node) -> list:
        out = []
        for decorator in getattr(node, "decorator_list", []):
            if isinstance(decorator, ast.Name) and decorator.id in labels:
                value = labels[decorator.id]
                out.append(SkipOccurrence(
                    f"@{decorator.id} = {ast.unparse(value)}", value, None))
        return out

    for name, node in methods.items():
        occurrences = label_occurrences(node)
        if occurrences:
            found[name] = occurrences
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(
                isinstance(sub, _FUNCTION_NODES) and sub.name.startswith("test_")
                for sub in node.body):
            occurrences = label_occurrences(node)
            if occurrences:
                found[node.name] = occurrences

    module_wide = [SkipOccurrence(f"{PYTESTMARK_NAME} = {ast.unparse(e)}", e,
                                  None) for e in _pytestmark_elements(tree)]
    for statement in tree.body:
        for call, dotted, inside_if in _module_level_calls(statement):
            module_wide.append(SkipOccurrence(
                f"{dotted}( {MODULE_LEVEL_NOTE}", call, inside_if))
    if module_wide:
        for name in methods:
            found.setdefault(name, []).extend(module_wide)
    return found


# Параметризация тестового метода (SPEC 01M56TNZ3E72XY9XSTAVS99CN2,
# требования 3-5; ANSWER-1 пп. 1-2): узел сравнения гейта неослабления
# сверяет вызов `parametrize` метода, сохранившего имя, — любая смена его
# текста, кроме добавления варианта при прежних, выключает проверку так же,
# как пропуск. Марка опознаётся последним сегментом имени
# (`pytest.mark.parametrize`, `mark.parametrize`), вариант с маркой —
# `pytest.param(…, marks=…)` последним сегментом `param`.
PARAMETRIZE_NAME = "parametrize"
PARAMETRIZE_PARAM_NAME = "param"
# Место списка вариантов в тексте вызова `ParametrizeMark.frame`.
PARAMETRIZE_VARIANTS_SLOT = "__variants__"


class ParametrizeMark(NamedTuple):
    """Одна марка `parametrize`, действующая на тестовый метод: `place` —
    где она стоит («декоратор метода #1», «декоратор класса C #1»,
    «pytestmark класса C #1», «pytestmark модуля #1»), `frame` — текст
    вызова (`ast.unparse`) с литеральным списком вариантов, заменённым
    `PARAMETRIZE_VARIANTS_SLOT`: имена аргументов, `ids=`, `indirect=` и
    аргумент-имя — как написаны, `variants` — тексты элементов литерального
    списка вариантов по порядку, `skipped` — те из них, что несут марку
    пропуска в `pytest.param(…, marks=…)`, `bindings` — строки уровня модуля
    и тела класса, где упомянуто имя, которое вызов берёт из того же модуля
    (`CASES`, элемент-имя набора, и транзитивно имена из их строк)."""

    place: str
    frame: str
    variants: tuple
    skipped: frozenset
    bindings: tuple


def _is_parametrize(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and \
        _called_dotted_name(node.func).rsplit(".", 1)[-1] == PARAMETRIZE_NAME


def _is_pytestmark_assign(node: ast.AST) -> bool:
    return isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == PYTESTMARK_NAME
        for t in node.targets)


def _module_statements(tree: ast.Module) -> list:
    """[(текст строки с областью, имена, которым она присваивает, имена,
    которые упоминает)] — строки уровня модуля и тела классов (ANSWER-1
    п. 1). Тела функций — не строки модуля (значения, вычисляемые
    функцией, — известный пробел); `pytestmark = …` сравнивается как
    марка, а не как строка константы."""
    statements = []

    def add(scope: str, body: list) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or \
                    _is_pytestmark_assign(node):
                continue
            if isinstance(node, ast.ClassDef):
                add(f"{scope}{node.name}.", node.body)
                continue
            names = [n for n in ast.walk(node) if isinstance(n, ast.Name)]
            statements.append((
                f"{scope}{ast.unparse(node)}",
                {n.id for n in names if isinstance(n.ctx, ast.Store)},
                {n.id for n in names}))

    add("", tree.body)
    return statements


def _bindings(call: ast.Call, statements: list) -> tuple:
    """Строки модуля и классов, в которых упомянуто имя, взятое вызовом из
    того же модуля, — с замыканием по именам, упомянутым в этих строках.
    Имя, лишь импортированное, сюда не попадает (известный пробел SPEC)."""
    defined = set().union(*(stored for _t, stored, _m in statements))
    names = {n.id for n in ast.walk(call)
             if isinstance(n, ast.Name)} & defined
    while True:
        wider = names.union(*(mentioned & defined
                              for _t, _s, mentioned in statements
                              if mentioned & names))
        if wider == names:
            break
        names = wider
    return tuple(text for text, _s, mentioned in statements
                 if mentioned & names)


def _pytestmark_marks(body: list) -> list:
    """Элементы последнего присваивания `pytestmark = …` тела `body`
    (модуля или класса) — одна марка либо элементы списка/кортежа."""
    value = None
    for node in body:
        if _is_pytestmark_assign(node):
            value = node.value
    if value is None:
        return []
    return value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]


def _variant_skipped(node: ast.AST) -> bool:
    """Вариант `pytest.param(…, marks=…)` несёт марку пропуска или
    ожидаемого провала (`_is_skip_mark`) в `marks`."""
    if not isinstance(node, ast.Call) or \
            _called_dotted_name(node.func).rsplit(".", 1)[-1] != \
            PARAMETRIZE_PARAM_NAME:
        return False
    return any(_is_skip_mark(sub) for kw in node.keywords if kw.arg == "marks"
               for sub in ast.walk(kw.value))


def _parametrize_mark(call: ast.Call, place: str,
                      statements: list) -> ParametrizeMark:
    frame = copy.deepcopy(call)
    slot = ast.Name(PARAMETRIZE_VARIANTS_SLOT, ast.Load())
    elements: list = []
    if len(frame.args) > 1:
        if isinstance(frame.args[1], (ast.List, ast.Tuple)):
            elements, frame.args[1] = list(frame.args[1].elts), slot
    else:
        for kw in frame.keywords:
            if kw.arg == "argvalues" and isinstance(kw.value,
                                                    (ast.List, ast.Tuple)):
                elements, kw.value = list(kw.value.elts), slot
    return ParametrizeMark(
        place, ast.unparse(frame), tuple(ast.unparse(e) for e in elements),
        frozenset(ast.unparse(e) for e in elements if _variant_skipped(e)),
        _bindings(call, statements))


def parametrize_variants(source) -> dict:
    """{квалифицированное имя тестового метода: (ParametrizeMark, …)} —
    марки `parametrize`, задающие варианты метода, во всех формах
    требования 5: `pytestmark` модуля, декоратор класса, `pytestmark` тела
    класса, декоратор метода. Метод без параметризации в результат не
    попадает; пусто — текста нет либо он не парсится.

    Литералы вариантов здесь только сравниваются как текст и в позиции
    литералов утверждений (`method_literal_keys`) не входят: смену строки
    `parametrize` «Меняемым поведением» не объявить (требование 2)."""
    tree = _parse_or_none(source)
    if tree is None:
        return {}
    statements = _module_statements(tree)

    def marks(nodes, place: str) -> list:
        return [_parametrize_mark(call, f"{place} #{index}", statements)
                for index, call in enumerate(
                    (n for n in nodes if _is_parametrize(n)), 1)]

    module_marks = marks(_pytestmark_marks(tree.body), "pytestmark модуля")
    class_marks: dict = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_marks[node.name] = (
                marks(node.decorator_list, f"декоратор класса {node.name}")
                + marks(_pytestmark_marks(node.body),
                        f"pytestmark класса {node.name}"))
    found: dict = {}
    for name, node in _collect_qualified_test_functions(tree).items():
        owner = name.split(TEST_NAME_SEP)[0] if TEST_NAME_SEP in name else None
        own = module_marks + class_marks.get(owner, []) + \
            marks(node.decorator_list, "декоратор метода")
        if own:
            found[name] = tuple(own)
    return found


# Утверждения тестового метода (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6, требования
# 1-2): гейт неослабления тестов наблюдает замену и удаление утверждения
# внутри метода, сохранившего имя. Утверждение — оператор `assert`, вызов
# атрибута с именем на `assert…` или `fail`, `pytest.raises`/`pytest.warns`.
ASSERTION_FAIL_NAME = "fail"
ASSERTION_PYTEST_CALLS = frozenset(("pytest.raises", "pytest.warns"))

# Число обязательных позиционных аргументов методов `unittest`, у которых
# СЛЕДУЮЩИЙ позиционный аргумент — сообщение (требование 2б). Методов, у
# которых третьим идёт не сообщение (`assertAlmostEqual(first, second,
# places)`, `assertRaises(exc, callable, *args)`), в таблице нет: у них,
# как у любого неизвестного имени, сравниваются все аргументы.
ASSERTION_REQUIRED_ARGS = {
    "fail": 0,
    "assertTrue": 1, "assertFalse": 1, "assertIsNone": 1,
    "assertIsNotNone": 1,
    "assertEqual": 2, "assertNotEqual": 2, "assertIn": 2, "assertNotIn": 2,
    "assertIs": 2, "assertIsNot": 2, "assertIsInstance": 2,
    "assertNotIsInstance": 2, "assertGreater": 2, "assertGreaterEqual": 2,
    "assertLess": 2, "assertLessEqual": 2, "assertRegex": 2,
    "assertNotRegex": 2, "assertCountEqual": 2, "assertListEqual": 2,
    "assertTupleEqual": 2, "assertSetEqual": 2, "assertDictEqual": 2,
    "assertMultiLineEqual": 2, "assertSequenceEqual": 2,
}

# Метки нормальной формы (требование 2в-г): все локальные имена метода —
# одна метка, корень цепочки атрибутов из импортированного модуля — другая.
# Угловые скобки делают метку невозможной как имя Python.
LOCAL_NAME_LABEL = "<локальное имя>"
IMPORT_ROOT_LABEL = "<импорт>"

# Предел длины исходного текста утверждения в тексте находки (требование 4).
ASSERTION_TEXT_LIMIT = 120


def _is_assertion(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute) and (
            node.func.attr.startswith("assert")
            or node.func.attr == ASSERTION_FAIL_NAME):
        return True
    return _called_dotted_name(node.func) in ASSERTION_PYTEST_CALLS


def _local_names(func: ast.AST) -> set:
    """Локальные имена функции на любой глубине (требование 2в): параметры
    кроме `self` (и вложенных функций/лямбд тоже), цели присваивания,
    переменные циклов, `with … as`, генераторов, моржа — всё это `Name` в
    контексте записи; `except … as` и имя вложенной функции — строки
    узлов, их собираем отдельно."""
    names: set = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.Lambda)):
            if node is not func and not isinstance(node, ast.Lambda):
                names.add(node.name)
            a = node.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs:
                names.add(arg.arg)
            for arg in (a.vararg, a.kwarg):
                if arg is not None:
                    names.add(arg.arg)
    names.discard("self")
    return names


def _module_imports(tree: ast.Module) -> set:
    """Имена, связанные на уровне модуля инструкцией `import`/`from …
    import` (требование 2г): `import a.b` связывает `a`, `import a as b` —
    `b`."""
    names: set = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


class _AssertionNormalizer(ast.NodeTransformer):
    """Нормальная форма одного утверждения (требование 2): сообщение
    отброшено, локальные имена и корень импортированного модуля заменены
    метками. Работает на копии узла — исходное дерево нужно для текста
    находки."""

    def __init__(self, local_names: set, imports: set):
        self.local_names = local_names
        self.imports = imports

    def visit_Assert(self, node):
        node.msg = None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if _is_assertion(node):
            node.keywords = [kw for kw in node.keywords if kw.arg != "msg"]
            name = node.func.attr if isinstance(node.func, ast.Attribute) \
                else ""
            required = ASSERTION_REQUIRED_ARGS.get(name)
            if required is not None and len(node.args) > required and \
                    not any(isinstance(a, ast.Starred) for a in node.args):
                node.args = node.args[:required]
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        root = node.value
        # Голое импортированное имя (константа `LIMIT_A`) меткой не
        # заменяется — только корень цепочки атрибутов (`fsm._x`).
        if isinstance(root, ast.Name) and root.id in self.imports and \
                root.id not in self.local_names:
            node.value = ast.Name(id=IMPORT_ROOT_LABEL, ctx=root.ctx)
            return node
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in self.local_names:
            return ast.Name(id=LOCAL_NAME_LABEL, ctx=node.ctx)
        return node


def _assertion_text(source: str, node: ast.AST) -> str:
    """Исходный текст утверждения одной строкой (многострочный вызов
    склеен), не длиннее `ASSERTION_TEXT_LIMIT` знаков."""
    text = " ".join((ast.get_source_segment(source, node) or "").split())
    if len(text) > ASSERTION_TEXT_LIMIT:
        text = text[:ASSERTION_TEXT_LIMIT - 1] + "…"
    return text


def _own_assertions(func: ast.AST, source: str, imports: set) -> list:
    """[(нормальная форма, исходный текст, узел нормальной формы)]
    утверждений тела `func` на любой глубине, в порядке исходного текста.
    Узел нужен различению смены ожидания и ослабления
    (`assertion_changes`): строка `ast.dump` позиций констант не несёт."""
    local_names = _local_names(func)
    found = []
    for node in ast.walk(func):
        if not _is_assertion(node):
            continue
        normal = _AssertionNormalizer(local_names, imports).visit(
            copy.deepcopy(node))
        found.append((node.lineno, node.col_offset, ast.dump(normal),
                      _assertion_text(source, node), normal))
    found.sort(key=lambda item: item[:2])
    return [(key, text, normal) for _line, _col, key, text, normal in found]


# Помощники вне своего класса и своего модуля (SPEC
# 01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 1): методы базовых классов внутри
# пакета `tests` (тот же файл, другой модуль `tests/`, `tests/sandbox.py`) и
# функции `tests/sandbox.py`. Модули ищутся по импорту `tests.<…>`.
TESTS_PACKAGE = "tests"
SANDBOX_MODULE_PATH = "tests/sandbox.py"

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _module_dotted(path: str) -> str:
    """`tests/a/b.py` → `tests.a.b`; `tests/a/__init__.py` → `tests.a`."""
    dotted = path[:-len(".py")].replace("/", ".") if path.endswith(".py") \
        else path.replace("/", ".")
    return dotted[:-len(".__init__")] if dotted.endswith(".__init__") \
        else dotted


def _tests_import_bindings(tree: ast.Module, path) -> dict:
    """{имя модуля: полное точечное имя, к которому оно привязано} по
    инструкциям `import`/`from … import` уровня модуля: `from tests.x import
    B as C` → `C: tests.x.B`, `from tests import sandbox` → `sandbox:
    tests.sandbox`, `import tests.sandbox as sb` → `sb: tests.sandbox`.
    Относительный импорт разрешается от пакета `path`; без пути — не
    разрешается."""
    package = _module_dotted(path).rsplit(".", 1)[0] if path else None
    names: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    root = alias.name.split(".", 1)[0]
                    names[root] = root
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if package is None:
                    continue
                parts = package.split(".")
                parts = parts[:len(parts) - (node.level - 1)]
                base = ".".join(parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    names[alias.asname or alias.name] = f"{base}.{alias.name}"
    return names


class _Module(NamedTuple):
    """Разобранный модуль для поиска помощников: путь (`None` — свой файл
    без названного пути), текст, импортированные имена нормальной формы,
    определения верхнего уровня, привязки импорта и дерево (по нему ищутся
    фикстуры модуля)."""

    path: str | None
    source: str
    imports: set
    defs: dict
    bindings: dict
    tree: ast.Module | None = None


def _tests_module_path(dotted: str) -> str | None:
    """Путь модуля `tests.<…>` артели; модуль вне пакета `tests` — `None`."""
    if dotted.split(".", 1)[0] != TESTS_PACKAGE:
        return None
    return dotted.replace(".", "/") + ".py"


def _module_entry(path, source: str, tree: ast.Module,
                  modules: "TestModules | None" = None) -> _Module:
    defs = {node.name: node for node in tree.body
            if isinstance(node, (*_FUNCTION_NODES, ast.ClassDef))}
    package_path = modules.import_path(path) if modules and path else path
    return _Module(path, source, _module_imports(tree), defs,
                   _tests_import_bindings(tree, package_path), tree)


class TestModules:
    """Модули `tests/` ОДНОЙ стороны сравнения для сбора утверждений
    (SPEC 01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 1): `load(путь)` отдаёт
    текст модуля этой стороны либо `None` (модуля нет, текст не прочитан).
    Разбор кэшируется: один `TestModules` на сторону обслуживает все файлы
    прохода гейта.

    `external` — режим внешнего проекта (SPEC 01M56TNTY7HEC85MC940KZR1ZJ):
    имя модуля импорта переводится в путь от корня проекта под `workdir`
    профиля, модуль виден, только если путь входит в область `in_scope`
    (`weakening_scope` профиля), и его функции — помощники. Режим не
    выводится из `workdir`: без `external` — правило артели (пакет `tests`,
    функции только `tests/sandbox.py`) при любом `workdir`."""

    __test__ = False  # имя на `Test…` — не тестовый класс для pytest

    def __init__(self, load, external: bool = False, workdir: str = "",
                 in_scope=None):
        self._load = load
        self._cache: dict = {}
        self._labels: dict = {}
        self.external = external
        self._workdir = workdir.strip("/") if external else ""
        self._in_scope = in_scope

    def module(self, path: str) -> _Module | None:
        if path not in self._cache:
            source = self._load(path)
            tree = _parse_or_none(source)
            self._cache[path] = None if tree is None else \
                _module_entry(path, source, tree, self)
        return self._cache[path]

    def labels(self, path: str) -> dict:
        """{имя: узел значения} имён-меток модуля `path` этой стороны
        (`_module_labels`, SPEC 01M56TNX1WWKV8PVQ94FT4ZJQB, требование 1б);
        модуля нет либо он не парсится — пусто."""
        if path not in self._labels:
            entry = self.module(path)
            tree = _parse_or_none(entry.source) if entry else None
            self._labels[path] = {} if tree is None else _module_labels(tree)
        return self._labels[path]

    def module_path(self, dotted: str) -> str | None:
        """Путь модуля `dotted` от корня репозитория; `None` — модуль вне
        видимого режиму: у артели — вне пакета `tests`, у внешнего проекта
        — вне области."""
        if not self.external:
            return _tests_module_path(dotted)
        rel = dotted.replace(".", "/") + ".py"
        path = f"{self._workdir}/{rel}" if self._workdir else rel
        if self._in_scope is not None and not self._in_scope(path):
            return None
        return path

    def import_path(self, path: str) -> str:
        """Путь файла, от которого разрешается его относительный импорт: у
        внешнего проекта — без префикса `workdir` (имена модулей импорта
        считаются от `workdir`), иначе — сам путь."""
        prefix = f"{self._workdir}/" if self._workdir else ""
        return path[len(prefix):] if prefix and path.startswith(prefix) \
            else path


class _HelperScope:
    """Поиск помощников первого уровня тестового метода в своём модуле
    `own`: метод своего класса и его базовых классов, функция своего
    модуля, функция `tests/sandbox.py`. Чужие модули — через `modules`
    (`TestModules` той же стороны); без него видны только базовые классы
    своего файла."""

    def __init__(self, own: _Module, modules: TestModules | None):
        self.own = own
        self.modules = modules

    def _module(self, dotted: str) -> _Module | None:
        path = self.modules.module_path(dotted) if self.modules else \
            _tests_module_path(dotted)
        if path is None:
            return None
        if path == self.own.path:
            return self.own
        return self.modules.module(path) if self.modules else None

    def resolve(self, module: _Module, node: ast.AST) -> tuple | None:
        """(модуль, узел определения) имени `node` в пространстве имён
        `module`: своё определение верхнего уровня либо `<модуль>.<имя>`
        через привязку импорта."""
        dotted = _dotted_name(node)
        if not dotted:
            return None
        first, _sep, rest = dotted.partition(".")
        if not rest and first in module.defs:
            return module, module.defs[first]
        qualified = module.bindings.get(first)
        if qualified is None:
            return None
        full = f"{qualified}.{rest}" if rest else qualified
        target_name, _sep, member = full.rpartition(".")
        target = self._module(target_name) if target_name else None
        if target is None or member not in target.defs:
            return None
        return target, target.defs[member]

    def class_chain(self, cls: ast.ClassDef) -> list:
        """[(модуль, класс)] — сам класс своего модуля и его базовые классы
        внутри `tests` в глубину слева направо; цикл и неразрешимая база
        обход не роняют."""
        chain, seen = [], set()

        def visit(module: _Module, node: ast.ClassDef) -> None:
            key = (module.path, node.name)
            if key in seen:
                return
            seen.add(key)
            chain.append((module, node))
            for base in node.bases:
                found = self.resolve(module, base)
                if found and isinstance(found[1], ast.ClassDef):
                    visit(*found)

        visit(self.own, cls)
        return chain

    def method(self, chain: list, name: str) -> tuple | None:
        """(модуль, узел, происхождение) метода `name` по цепочке классов;
        происхождение `None` — метод своего класса (прежняя форма находки),
        иначе (`Класс.метод`, путь файла класса)."""
        for index, (module, cls) in enumerate(chain):
            for sub in cls.body:
                if isinstance(sub, _FUNCTION_NODES) and sub.name == name:
                    origin = None if index == 0 else \
                        (f"{cls.name}.{name}", module.path or "")
                    return module, sub, origin
        return None

    def function(self, callee: ast.AST) -> tuple | None:
        """(модуль, узел, происхождение) вызываемой функции: голое имя
        функции своего модуля без префикса `test_` (происхождение `None`)
        либо функция `tests/sandbox.py` по импорту; у внешнего проекта —
        функция любого модуля его области по импорту."""
        if isinstance(callee, ast.Name):
            node = self.own.defs.get(callee.id)
            if isinstance(node, _FUNCTION_NODES):
                if callee.id.startswith("test_"):
                    return None
                return self.own, node, None
        found = self.resolve(self.own, callee)
        if found is None:
            return None
        module, node = found
        external = self.modules is not None and self.modules.external
        if module is self.own or \
                (not external and module.path != SANDBOX_MODULE_PATH) or \
                not isinstance(node, _FUNCTION_NODES) or \
                node.name.startswith("test_"):
            return None
        return module, node, (node.name, module.path)


def _helper_calls(func: ast.AST, scope: _HelperScope, chain: list) -> list:
    """(модуль, узел, происхождение) вспомогательных функций первого
    уровня, которые зовёт `func` (требование 1; SPEC
    01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 1): `self.<имя>(…)` — метод
    своего класса, затем его базовых классов (`chain`), голое имя — функция
    модуля без префикса `test_`, иначе — функция `tests/sandbox.py`. Каждый
    вызов — отдельный элемент: помощник, вызванный дважды, дважды и
    утверждает."""
    helpers = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Attribute) and \
                isinstance(callee.value, ast.Name) and \
                callee.value.id == "self":
            found = scope.method(chain, callee.attr)
        else:
            found = scope.function(callee)
        if found is not None:
            helpers.append((node.lineno, node.col_offset, found))
    helpers.sort(key=lambda item: item[:2])
    return [helper for _line, _col, helper in helpers]


# Фикстуры pytest (ADR-0027 пп. 3-5; SPEC 01M5N9WK9SGB7KDYJP736DP6CV,
# требования 1-3): фикстура подставляется по имени параметра, а не
# вызовом, и `_helper_calls` её не видит. Утверждений у фикстуры нет
# (ADR-0027 п. 3) — тест получает от неё записи ДАННЫХ: литералы тела
# фикстуры и её помощников первого уровня. Имена pytest распознаются и
# через псевдонимы импорта (`import pytest as pt`, `from pytest import
# fixture`).
PYTEST_MODULE = "pytest"
FIXTURE_DECORATOR = "pytest.fixture"
USEFIXTURES_MARK = "pytest.mark.usefixtures"
FIXTURES_MODULE_PATH = "tests/fixtures.py"
FIXTURE_DATA_KIND = "данные фикстуры"
# Параметры, которые фикстурой своего файла не разрешаются: получатель
# метода и встроенная фикстура `request`.
_NOT_FIXTURE_PARAMS = frozenset(("self", "cls", "request"))


class _FixtureDatum(ast.AST):
    """Узел записи данных фикстуры — свой вид записи `_assertion_records`,
    не утверждение (требование 3): `value` — литерал (константа либо знак
    над числовой константой, как у `_literal`). У него нет `func`, вид
    ему даёт `_assertion_kind`, ролей строгости — нет (`_constant_roles`)."""

    _fields = ("value",)


def _pytest_aliases(tree: ast.Module) -> dict:
    """{имя: точечное имя pytest, к которому оно привязано}: `import
    pytest as pt` → `pt: pytest`, `from pytest import mark as m` → `m:
    pytest.mark`. Само `pytest` видно всегда."""
    names = {PYTEST_MODULE: PYTEST_MODULE}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name.split(".", 1)[0] == PYTEST_MODULE:
                    names[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom) and not node.level and \
                node.module and \
                node.module.split(".", 1)[0] == PYTEST_MODULE:
            for alias in node.names:
                if alias.name != "*":
                    names[alias.asname or alias.name] = \
                        f"{node.module}.{alias.name}"
    return names


def _pytest_name(node: ast.AST, aliases: dict) -> str:
    """Каноническое имя pytest узла (`pt.mark.xfail` → `pytest.mark.xfail`,
    `xfail` после `from pytest import xfail` → `pytest.xfail`); вызов
    разворачивается. Пустая строка — не имя pytest."""
    if isinstance(node, ast.Call):
        node = node.func
    dotted = _dotted_name(node)
    if not dotted:
        return ""
    first, sep, rest = dotted.partition(".")
    bound = aliases.get(first)
    return f"{bound}{sep}{rest}" if bound else ""


def _fixture_decorator(node: ast.AST, aliases: dict) -> ast.AST | None:
    """Декоратор `pytest.fixture` функции `node` (с вызовом или без);
    `None` — функция не фикстура."""
    for decorator in getattr(node, "decorator_list", []):
        if _pytest_name(decorator, aliases) == FIXTURE_DECORATOR:
            return decorator
    return None


def _decorator_keyword(decorator: ast.AST, name: str) -> ast.keyword | None:
    if isinstance(decorator, ast.Call):
        for kw in decorator.keywords:
            if kw.arg == name:
                return kw
    return None


def _fixture_name(node: ast.AST, aliases: dict) -> str | None:
    """Имя, под которым pytest регистрирует фикстуру `node`: строка
    `name=` декоратора либо имя функции; `None` — не фикстура."""
    decorator = _fixture_decorator(node, aliases)
    if decorator is None:
        return None
    kw = _decorator_keyword(decorator, "name")
    if kw is not None and isinstance(kw.value, ast.Constant) and \
            isinstance(kw.value.value, str):
        return kw.value.value
    return node.name


def _is_autouse(node: ast.AST, aliases: dict) -> bool:
    kw = _decorator_keyword(_fixture_decorator(node, aliases), "autouse")
    return kw is not None and isinstance(kw.value, ast.Constant) and \
        kw.value.value is True


def _parameter_names(func: ast.AST) -> list:
    a = func.args
    return [arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs]


class _Fixture(NamedTuple):
    """Объявление фикстуры: модуль, узел функции, имя регистрации,
    класс-владелец (`None` — фикстура уровня модуля)."""

    module: _Module
    node: ast.AST
    name: str
    owner: ast.ClassDef | None


def _fixture_table(module: _Module | None, body=None,
                   owner: ast.ClassDef | None = None) -> dict:
    """{имя регистрации: _Fixture} фикстур тела `body` (по умолчанию —
    верхний уровень модуля); последнее объявление имени побеждает."""
    if module is None or module.tree is None:
        return {}
    aliases = _pytest_aliases(module.tree)
    table: dict = {}
    for node in module.tree.body if body is None else body:
        if isinstance(node, _FUNCTION_NODES):
            name = _fixture_name(node, aliases)
            if name is not None:
                table[name] = _Fixture(module, node, name, owner)
    return table


def _parametrize_argnames(call: ast.Call) -> list:
    """Имена аргументов вызова `parametrize`: строка (через запятую) либо
    список/кортеж строк, первым аргументом или `argnames=`."""
    value = call.args[0] if call.args else next(
        (kw.value for kw in call.keywords if kw.arg == "argnames"), None)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [n.strip() for n in value.value.split(",") if n.strip()]
    if isinstance(value, (ast.List, ast.Tuple)):
        return [e.value for e in value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _indirect_argnames(call: ast.Call, names: list) -> set:
    """Имена `parametrize`, которые `indirect=` отдаёт фикстурам."""
    kw = _decorator_keyword(call, "indirect")
    if kw is None:
        return set()
    if isinstance(kw.value, ast.Constant):
        return set(names) if kw.value.value is True else set()
    if isinstance(kw.value, (ast.List, ast.Tuple)):
        return {e.value for e in kw.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return set()


def _data_literals(func: ast.AST) -> list:
    """Литералы тела функции по порядку обхода (`_literal_positions`):
    константы любых операторов, в том числе аргументы вызовов; знак над
    числом входит в литерал. Докстринг — не данные."""
    body = func.body
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        body = body[1:]
    return [node for statement in body
            for node, _value in _literal_positions(statement)]


class _FixtureScope:
    """Фикстуры, видимые тестам файла `own` (требование 1): своего класса,
    своего модуля, затем `tests/fixtures.py` той же стороны — его подключает
    `pytest_plugins` без импорта (ADR-0027 п. 4). Общий модуль читается
    только при промахе своего файла и только по правилу артели."""

    def __init__(self, own: _Module, modules: TestModules | None):
        self.own = own
        self.modules = modules
        self.table = _fixture_table(own)
        self.aliases = _pytest_aliases(own.tree) if own.tree else {}
        self._shared = None

    def shared(self) -> dict:
        if self._shared is None:
            module = None
            if self.modules is not None and not self.modules.external and \
                    self.own.path != FIXTURES_MODULE_PATH:
                module = self.modules.module(FIXTURES_MODULE_PATH)
            self._shared = _fixture_table(module)
        return self._shared

    def resolve(self, name: str, classwide: dict, requester=None):
        """Фикстура имени `name`; фикстура общего модуля видит только общий
        модуль, одноимённая фикстура не разрешается в саму себя."""
        if requester is not None and requester.module is not self.own:
            levels = (self.shared,)
        else:
            levels = (lambda: classwide, lambda: self.table, self.shared)
        for level in levels:
            found = level().get(name)
            if found is not None and \
                    (requester is None or found.node is not requester.node):
                return found
        return None

    def requested(self, func: ast.AST, cls: ast.ClassDef | None,
                  classwide: dict) -> list:
        """Имена фикстур теста по порядку: `autouse` своего файла, параметры
        (кроме имён аргументов `parametrize`, не отданных `indirect=`),
        `usefixtures` на тесте, на классе и в `pytestmark`."""
        marks = list(func.decorator_list)
        if cls is not None:
            marks += cls.decorator_list + _pytestmark_marks(cls.body)
        marks += _pytestmark_marks(self.own.tree.body)
        parametrized, indirect, used = set(), set(), []
        for mark in marks:
            if not isinstance(mark, ast.Call):
                continue
            if _is_parametrize(mark):
                names = _parametrize_argnames(mark)
                parametrized |= set(names)
                indirect |= _indirect_argnames(mark, names)
            elif _pytest_name(mark, self.aliases) == USEFIXTURES_MARK:
                used += [a.value for a in mark.args
                         if isinstance(a, ast.Constant)
                         and isinstance(a.value, str)]
        autouse = [f.name for table in (self.table, classwide)
                   for f in table.values() if _is_autouse(f.node, self.aliases)]
        params = [p for p in _parameter_names(func)
                  if p not in _NOT_FIXTURE_PARAMS
                  and (p not in parametrized or p in indirect)]
        return list(dict.fromkeys(autouse + params + used))

    def records(self, func: ast.AST, cls: ast.ClassDef | None) -> list:
        """Записи данных фикстур теста `func`: каждая фикстура — с
        помощниками первого уровня, фикстура, запрошенная фикстурой, —
        одним уровнем, без своих помощников."""
        classwide = _fixture_table(self.own, cls.body, cls) \
            if cls is not None else {}
        found, seen = [], set()

        def trace(fixture: _Fixture, nested: bool) -> None:
            if id(fixture.node) in seen:
                return
            seen.add(id(fixture.node))
            found.extend(self._data(fixture, helpers=not nested))
            if nested:
                return
            for name in _parameter_names(fixture.node):
                if name in _NOT_FIXTURE_PARAMS:
                    continue
                inner = self.resolve(
                    name, classwide if fixture.owner is not None else {},
                    fixture)
                if inner is not None:
                    trace(inner, True)

        for name in self.requested(func, cls, classwide):
            fixture = self.resolve(name, classwide)
            if fixture is not None:
                trace(fixture, False)
        return found

    def _data(self, fixture: _Fixture, helpers: bool) -> list:
        module = fixture.module
        path = module.path or ""
        origin = None if module is self.own else \
            (f"фикстура {fixture.name}", path)
        parts = [(None, _data_literals(fixture.node), origin)]
        if helpers:
            # Помощник первого уровня — метод класса фикстуры, функция её
            # модуля либо функция другого модуля `tests/` по импорту
            # (ревью итерации 1, R1-F1); второй уровень в запись не идёт
            # (SPEC, «Не входит»).
            scope = _HelperScope(module, self.modules)
            chain = scope.class_chain(fixture.owner) \
                if fixture.owner is not None else []
            aliases = _pytest_aliases(module.tree)
            for helper_module, helper in _fixture_helper_calls(
                    fixture.node, scope, chain):
                if helper is fixture.node or \
                        _fixture_name(helper, aliases) is not None:
                    continue
                # Помощник чужого файла: находку покрывает мандат на его
                # файл, как у помощника теста из чужого модуля.
                helper_origin = origin if helper_module is module else \
                    (f"фикстура {fixture.name} → {helper.name}",
                     helper_module.path or "")
                parts.append((helper.name, _data_literals(helper),
                              helper_origin))
        records, index = [], 0
        for helper, literals, part_origin in parts:
            where = fixture.name if helper is None else \
                f"{fixture.name} → помощник {helper}"
            for literal in literals:
                text = f"{FIXTURE_DATA_KIND} {where} ({path}): " \
                       f"{ast.unparse(literal)}"
                if len(text) > ASSERTION_TEXT_LIMIT:
                    text = text[:ASSERTION_TEXT_LIMIT - 1] + "…"
                records.append(((path, fixture.name, index, ast.dump(literal)),
                                text, _FixtureDatum(value=copy.deepcopy(literal)),
                                part_origin))
                index += 1
        return records


def _fixture_helper_calls(func: ast.AST, scope: _HelperScope,
                          chain: list) -> list:
    """(модуль, узел) помощников первого уровня фикстуры `func` по порядку
    вызовов: то же, что `_helper_calls`, и сверх того функция любого модуля
    `tests/` (у внешнего проекта — его области) по импорту. У теста
    функции чужих модулей артели, кроме `tests/sandbox.py`, помощником не
    считаются: их утверждения — не данные; у фикстуры помощник несёт
    данные, где бы он ни жил (SPEC 01M5N9WK9SGB7KDYJP736DP6CV, требование
    3)."""
    helpers = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Attribute) and \
                isinstance(callee.value, ast.Name) and \
                callee.value.id == "self":
            found = scope.method(chain, callee.attr)
        else:
            found = scope.function(callee)
            if found is None:
                resolved = scope.resolve(scope.own, callee)
                if resolved is not None and \
                        isinstance(resolved[1], _FUNCTION_NODES) and \
                        not resolved[1].name.startswith("test_"):
                    found = (*resolved, None)
        if found is not None:
            helpers.append((node.lineno, node.col_offset, found[:2]))
    helpers.sort(key=lambda item: item[:2])
    return [helper for _line, _col, helper in helpers]


def test_assertions(source, path=None,
                    modules: TestModules | None = None) -> dict[str, list] | None:
    """Утверждения тестовых методов текста `source` по квалифицированному
    имени (`_collect_qualified_test_functions`): список пар (нормальная
    форма, исходный текст) — свои утверждения метода на любой глубине и
    утверждения вспомогательных функций первого уровня (требования 1-2),
    включая унаследованных помощников и функции `tests/sandbox.py` (SPEC
    01M4G8N9KBTVNNT7YGZ59Q5WBF): `path` — путь самого файла, `modules` —
    модули `tests/` той же стороны.

    `None` — текста нет либо он не парсится: сравнивать утверждения не с
    чем, и вызывающий обязан отличить это от «утверждений нет»."""
    records = _assertion_records(source, path, modules)
    if records is None:
        return None
    return {name: [(key, text) for key, text, _node, _origin in found]
            for name, found in records.items()}


def _assertion_records(source, path=None,
                       modules: TestModules | None = None) -> dict[str, list] | None:
    """То же, что `test_assertions`, но четвёрками (нормальная форма,
    исходный текст, узел нормальной формы, происхождение) — один обход на
    оба вида ответа, чтобы различение смены ожидания не разошлось с
    наблюдением. Происхождение — `None` у утверждений самого метода,
    помощника своего класса и функции своего модуля, иначе (`Класс.метод`
    либо имя функции, путь файла помощника).

    За утверждениями метода идут записи данных фикстур, которые он
    запрашивает (`_FixtureScope`, SPEC 01M5N9WK9SGB7KDYJP736DP6CV,
    требование 3): ключ — (файл фикстуры, имя фикстуры, номер литерала,
    `ast.dump` литерала), узел — `_FixtureDatum`, происхождение — `None` у
    фикстуры своего файла, иначе (`фикстура <имя>`, путь её файла)."""
    tree = _parse_or_none(source)
    if tree is None:
        return None
    own = _module_entry(path, source, tree, modules)
    scope = _HelperScope(own, modules)
    fixtures = _FixtureScope(own, modules)

    result: dict[str, list] = {}
    for name, func in _collect_qualified_test_functions(tree).items():
        owner = name.split(TEST_NAME_SEP, 1)[0] if TEST_NAME_SEP in name \
            else None
        cls = own.defs.get(owner) if owner else None
        chain = scope.class_chain(cls) if isinstance(cls, ast.ClassDef) \
            else []
        found = [(*item, None)
                 for item in _own_assertions(func, source, own.imports)]
        for module, helper, origin in _helper_calls(func, scope, chain):
            if helper is not func:
                found += [(*item, origin) for item in _own_assertions(
                    helper, module.source, module.imports)]
        found += fixtures.records(
            func, cls if isinstance(cls, ast.ClassDef) else None)
        result[name] = found
    return result


def weakened_helpers(base_source, head_source) -> set:
    """Имена функций и методов классов текста base, которые в head
    потеряли хоть одно своё утверждение (по нормальной форме) или исчезли
    вместе с ними: по ним гейт ищет вызывающих в файлах вне диффа (SPEC
    01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 2). Неразбираемая сторона base —
    пусто, head — как пустой файл.

    Утверждений у фикстуры нет, поэтому фикстура и помощник, которого она
    зовёт, называются по смене тела (`_changed_fixture_names`, SPEC
    01M5N9WK9SGB7KDYJP736DP6CV, требование 5)."""
    base, head = _helper_keys(base_source), _helper_keys(head_source)
    return {name for (_cls, name), keys in base.items()
            if Counter(keys) - Counter(head.get((_cls, name), ()))} | \
        _changed_fixture_names(base_source, head_source)


def _function_dumps(tree: ast.Module) -> dict:
    """{(класс либо `None`, имя): `ast.dump` узла} функций модуля и методов
    классов верхнего уровня."""
    found: dict = {}
    for node in tree.body:
        if isinstance(node, _FUNCTION_NODES):
            found[(None, node.name)] = ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, _FUNCTION_NODES):
                    found[(node.name, sub.name)] = ast.dump(sub)
    return found


def _changed_fixture_names(base_source, head_source) -> set:
    """Имена фикстур текста base с иным телом в head (или исчезнувших),
    помощников первого уровня этих фикстур с иным телом и фикстур своего
    файла, которые зовут такого помощника или запрашивают такую фикстуру:
    поиск вызывающих вне диффа идёт по словам, и тест, запросивший
    фикстуру, найдётся только по её имени (требование 5). Сверх того —
    функции модуля (не тесты и не фикстуры) с иными литералами: помощник
    фикстуры чужого файла по импорту."""
    base_tree = _parse_or_none(base_source)
    if base_tree is None:
        return set()
    head_tree = _parse_or_none(head_source) or ast.Module(body=[],
                                                          type_ignores=[])
    before, after = _function_dumps(base_tree), _function_dumps(head_tree)
    aliases = _pytest_aliases(base_tree)
    functions = []
    for node in base_tree.body:
        if isinstance(node, _FUNCTION_NODES):
            functions.append((None, node))
        elif isinstance(node, ast.ClassDef):
            functions += [(node.name, sub) for sub in node.body
                          if isinstance(sub, _FUNCTION_NODES)]
    fixtures = [(owner, func, _fixture_name(func, aliases))
                for owner, func in functions
                if _fixture_name(func, aliases) is not None]

    def altered(key) -> bool:
        return key in before and after.get(key) != before[key]

    changed = {name for owner, func, name in fixtures
               if altered((owner, func.name))}
    names = set(changed)
    for owner, func, name in fixtures:
        for call in ast.walk(func):
            if not isinstance(call, ast.Call):
                continue
            callee = call.func
            if isinstance(callee, ast.Name):
                key = (None, callee.id)
            elif owner is not None and isinstance(callee, ast.Attribute) and \
                    isinstance(callee.value, ast.Name) and \
                    callee.value.id == "self":
                key = (owner, callee.attr)
            else:
                continue
            if key != (owner, func.name) and altered(key):
                names |= {key[1], name}
        if changed & set(_parameter_names(func)) - {name}:
            names.add(name)
    # Функция модуля может быть помощником фикстуры другого файла по
    # импорту (`_fixture_helper_calls`), а у такого помощника запись видит
    # только литералы: функция с иной последовательностью литералов (или
    # исчезнувшая) называется, чтобы нашёлся файл фикстуры, которая её
    # зовёт (ревью итерации 1, R1-F1).
    head_functions = {node.name: node for node in head_tree.body
                      if isinstance(node, _FUNCTION_NODES)}
    for owner, func in functions:
        if owner is not None or func.name.startswith("test_") or \
                _fixture_name(func, aliases) is not None:
            continue
        other = head_functions.get(func.name)
        if other is None or _literal_dumps(other) != _literal_dumps(func):
            names.add(func.name)
    return names


def _literal_dumps(func: ast.AST) -> list:
    return [ast.dump(literal) for literal in _data_literals(func)]


def changed_classes(base_source, head_source, path=None,
                    modules: TestModules | None = None) -> set:
    """Имена классов верхнего уровня текста base, у которых в head иная
    цепочка поиска помощников: класс исчез, сменились его базовые классы
    или набор методов (переопределение помощника без утверждений), либо
    сменились импорты модуля, через которые разрешаются базы, — тогда
    все классы. Наследники таких классов в файлах вне диффа могут потерять
    утверждения, не потеряв ни одного у самих помощников (SPEC
    01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 2). В ответ входят только
    классы, чья цепочка в base (`path`/`modules` — как у `test_assertions`
    стороны base) несёт метод с утверждением: наследнику класса без таких
    методов терять нечего. Неразбираемая сторона base — пусто, head — как
    пустой файл."""
    base_tree = _parse_or_none(base_source)
    if base_tree is None:
        return set()
    head_tree = _parse_or_none(head_source) or ast.Module(body=[],
                                                          type_ignores=[])
    base, head = _class_shapes(base_tree), _class_shapes(head_tree)
    if _import_dumps(base_tree) == _import_dumps(head_tree):
        names = {name for name, shape in base.items()
                 if head.get(name) != shape}
    else:
        names = set(base)
    own = _module_entry(path, base_source, base_tree, modules)
    scope = _HelperScope(own, modules)
    return {name for name in names if any(
        _own_assertions(sub, module.source, module.imports)
        for module, cls in scope.class_chain(own.defs[name])
        for sub in cls.body if isinstance(sub, _FUNCTION_NODES))}


def _class_shapes(tree: ast.Module) -> dict:
    return {node.name: (tuple(ast.dump(b) for b in node.bases),
                        tuple(sorted(sub.name for sub in node.body
                                     if isinstance(sub, _FUNCTION_NODES))))
            for node in tree.body if isinstance(node, ast.ClassDef)}


def _import_dumps(tree: ast.Module) -> list:
    return [ast.dump(node) for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))]


def subclass_names(source, names: set) -> set:
    """Имена классов верхнего уровня текста `source`, среди базовых классов
    которых есть класс из `names` (по последнему компоненту имени базы):
    наследник изменённого класса сам становится источником вызывающих в
    следующем файле цепочки. Неразбираемый текст — пусто."""
    tree = _parse_or_none(source)
    if tree is None:
        return set()
    return {node.name for node in tree.body
            if isinstance(node, ast.ClassDef) and any(
                (_dotted_name(base) or "").rpartition(".")[2] in names
                for base in node.bases)}


def _helper_keys(source) -> dict:
    """{(класс либо `None`, имя): [нормальные формы своих утверждений]} по
    функциям модуля и методам классов верхнего уровня."""
    tree = _parse_or_none(source)
    if tree is None:
        return {}
    imports = _module_imports(tree)
    found: dict = {}
    for node in tree.body:
        if isinstance(node, _FUNCTION_NODES):
            found[(None, node.name)] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, _FUNCTION_NODES):
                    found[(node.name, sub.name)] = sub
    return {key: [k for k, _text, _normal in
                  _own_assertions(func, source, imports)]
            for key, func in found.items()}


def changed_test_assertions(base: dict, head: dict) -> dict[str, list]:
    """{квалифицированное имя: [исходный текст утверждения base]} по
    методам, имя которых есть по обе стороны, — утверждения base, которых
    в head меньше по числу вхождений той же нормальной формы (требование
    3): сравниваются мультимножества, не число утверждений. Добавленное
    утверждение и перестановка находкой не становятся; «сильнее/слабее»
    не оценивается — любая смена вида или аргумента находка.

    `base`/`head` — результат `test_assertions` своей стороны."""
    changed: dict[str, list] = {}
    for name, base_items in base.items():
        if name not in head:
            continue
        left = Counter(key for key, _text in head[name])
        lost = []
        for key, text in base_items:
            if left[key] > 0:
                left[key] -= 1
            else:
                lost.append(text)
        if lost:
            changed[name] = lost
    return changed


# Смена ожидания и ослабление (SPEC 01M45FJD46BX45VHC36S4VS9QN, требования 5
# и 9): различение живёт здесь, рядом с `changed_test_assertions`, — пульт
# и CLI читают одно правило, копии в `orchestrator/` нет. Маскированная
# форма — нормальная форма, где каждая константа-литерал заменена одной
# меткой; угловые скобки делают метку невозможной как имя Python.
LITERAL_MASK_LABEL = "<литерал>"
ASSERTION_CHANGE_EXPECTATION = "смена ожидания"
ASSERTION_CHANGE_OTHER = "ослабление или иная смена"
SIGN_REMOVED = "утверждение удалено"
SIGN_OTHER_KIND = "другой вид утверждения"
SIGN_COMPUTED = "литерал заменён вычисленным значением"
SIGN_OTHER_FORM = "иная смена формы утверждения"
SIGN_UNRATED = "правило не умеет оценить строгость"

# Позиции констант, у которых правило умеет оценить строгость (требование
# 9): методы `unittest`, чьи два первых аргумента сравниваются на
# равенство (сюда же сравниваемые значения `assert[Not]AlmostEqual`: смена
# значения строгость не меняет, допуск оценивается отдельно), вызовы
# `mock`, чьи аргументы сверяются на равенство, и методы порядка с
# оператором, которым они сравнивают первый аргумент со вторым.
_EQUALITY_METHODS = frozenset((
    "assertEqual", "assertNotEqual", "assertIs", "assertIsNot",
    "assertListEqual", "assertTupleEqual", "assertSetEqual",
    "assertDictEqual", "assertMultiLineEqual", "assertSequenceEqual",
    "assertCountEqual", "assertAlmostEqual", "assertNotAlmostEqual"))
_MOCK_CALL_ASSERTS = frozenset((
    "assert_called_with", "assert_called_once_with", "assert_any_call",
    "assert_has_calls"))
_ORDER_METHODS = {"assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE,
                  "assertLess": ast.Lt, "assertLessEqual": ast.LtE}
_REGEX_METHODS = frozenset(("assertRegex", "assertRaisesRegex",
                            "assertWarnsRegex"))
_REGEX_ANCHORS = ("^", "$", "\\A", "\\Z")
_REGEX_WILDCARDS = (".*", ".+")
# Отрицание оператора порядка: `assertFalse(x > c)` — это `x <= c`.
_NEGATED_ORDER = {ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Lt: ast.GtE,
                  ast.LtE: ast.Gt}


class AssertionChange(NamedTuple):
    """Исход различения одного метода, сохранившего имя (требование 5):
    `kind` — `ASSERTION_CHANGE_EXPECTATION` либо `ASSERTION_CHANGE_OTHER`;
    `pairs` — фактическая смена значений смены ожидания, пары (константа
    base, константа head) в порядке появления; `signs` — признаки
    ослабления: у иной смены — почему правило смены ожидания её не
    признало, у смены ожидания — оценка строгости пар (требование 9),
    пусто — строгость не ниже прежней.

    `origins` — происхождение каждого изменённого утверждения base (SPEC
    01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 2): `None` — утверждение самого
    метода, помощника своего класса или функции своего модуля, иначе
    (`Класс.метод` либо имя функции, путь файла помощника)."""

    kind: str
    pairs: tuple
    signs: tuple
    origins: tuple = ()


def _literal(node: ast.AST) -> tuple | None:
    """`(значение,)` литерала на позиции константы, иначе `None`.

    Отрицательное число в исходнике — `UnaryOp(USub, Constant)`, не
    `Constant`: знак над числовой константой — часть литерала, иначе
    `-2` → `-3` читалось бы парой `(2, 3)`, а `1` → `-1` — сдвигом формы
    (ANSWER-3 задачи, R1-F2)."""
    if isinstance(node, ast.Constant):
        return (node.value,)
    if isinstance(node, ast.UnaryOp) and \
            isinstance(node.op, (ast.USub, ast.UAdd)) and \
            isinstance(node.operand, ast.Constant) and \
            isinstance(node.operand.value, (int, float, complex)) and \
            not isinstance(node.operand.value, bool):
        value = node.operand.value
        return (-value if isinstance(node.op, ast.USub) else +value,)
    return None


def _literal_positions(node: ast.AST):
    """Литералы нормальной формы по порядку обхода: `(узел, значение)`.
    У двух форм с равной маскированной формой позиции идут узел в узел."""
    found = _literal(node)
    if found is not None:
        yield node, found[0]
        return
    for child in ast.iter_child_nodes(node):
        yield from _literal_positions(child)


class _LiteralMasker(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.Name(id=LITERAL_MASK_LABEL, ctx=ast.Load())

    def visit_UnaryOp(self, node):
        if _literal(node) is not None:
            return ast.Name(id=LITERAL_MASK_LABEL, ctx=ast.Load())
        return self.generic_visit(node)


def _masked_form(node: ast.AST) -> str:
    return ast.dump(_LiteralMasker().visit(copy.deepcopy(node)))


def _assertion_kind(node: ast.AST) -> str:
    """Вид утверждения: `assert` либо имя вызываемого (последний сегмент);
    у записи данных фикстуры — `FIXTURE_DATA_KIND`."""
    if isinstance(node, ast.Assert):
        return "assert"
    if isinstance(node, _FixtureDatum):
        return FIXTURE_DATA_KIND
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return _called_dotted_name(func) or "?"


def _divergence(base: ast.AST, head: ast.AST) -> str:
    """Первая структурная развилка двух нормальных форм одного вида:
    `SIGN_COMPUTED` — на месте константы base в head вызов, атрибут или
    имя; `SIGN_OTHER_FORM` — любая иная; пустая строка — развилки нет."""
    if _literal(base) is not None:
        if _literal(head) is not None:
            return ""
        if isinstance(head, (ast.Call, ast.Attribute, ast.Name)):
            return SIGN_COMPUTED
        return SIGN_OTHER_FORM
    if type(base) is not type(head):
        return SIGN_OTHER_FORM
    for field, left in ast.iter_fields(base):
        right = getattr(head, field, None)
        if isinstance(left, list):
            if not isinstance(right, list):
                return SIGN_OTHER_FORM
            for x, y in zip(left, right):
                found = _divergence(x, y) if isinstance(x, ast.AST) \
                    else ("" if x == y else SIGN_OTHER_FORM)
                if found:
                    return found
            if len(left) != len(right):
                return SIGN_OTHER_FORM
        elif isinstance(left, ast.AST):
            if not isinstance(right, ast.AST):
                return SIGN_OTHER_FORM
            found = _divergence(left, right)
            if found:
                return found
        elif left != right:
            return SIGN_OTHER_FORM
    return ""


def _other_change_sign(lost: tuple, candidates: list) -> str:
    """Признак утверждения base, которому не нашлось пары с равной
    маскированной формой (требование 5); `candidates` — ещё не
    сопоставленные утверждения head (берётся первое того же вида, иначе
    первое вообще, и оно из кандидатов убирается)."""
    _key, text, node, _origin = lost
    if not candidates:
        return f"{SIGN_REMOVED}: {text}"
    kind = _assertion_kind(node)
    same = [c for c in candidates if _assertion_kind(c[2]) == kind]
    other = (same or candidates)[0]
    candidates.remove(other)
    if not same:
        return (f"{SIGN_OTHER_KIND} ({kind} → {_assertion_kind(other[2])}): "
                f"{text} → {other[1]}")
    return f"{_divergence(node, other[2]) or SIGN_OTHER_FORM}: {text} → {other[1]}"


def _constant_roles(node: ast.AST) -> dict:
    """{id константы нормальной формы: роль} — позиции, у которых правило
    требования 9 умеет оценить строгость. Роль — кортеж: `("equality",)`,
    `("tolerance", имя, слабее_если_больше)`, `("regex",)`,
    `("regex_not",)`, `("membership", отрицание)`, `("order", граница)`;
    константа без роли — «правило не умеет оценить строгость».

    У записи данных фикстуры ролей нет (SPEC 01M5N9WK9SGB7KDYJP736DP6CV,
    требование 3): её правку объявление «Меняемого поведения» не снимает."""
    roles: dict = {}
    if isinstance(node, _FixtureDatum):
        return roles

    def equality(expr):
        if _literal(expr) is not None:
            roles[id(expr)] = ("equality",)
        elif isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            for elt in expr.elts:
                equality(elt)
        elif isinstance(expr, ast.Dict):
            for elt in list(expr.keys) + list(expr.values):
                if elt is not None:
                    equality(elt)
        elif isinstance(expr, ast.UnaryOp) and \
                isinstance(expr.op, (ast.USub, ast.UAdd)):
            equality(expr.operand)
        elif isinstance(expr, ast.Call) and _approx_call(expr):
            if expr.args:
                equality(expr.args[0])
            for index, name in ((1, "rel"), (2, "abs")):
                if len(expr.args) > index:
                    tolerance(expr.args[index], name, True)
            for kw in expr.keywords:
                if kw.arg in ("rel", "abs"):
                    tolerance(kw.value, kw.arg, True)

    def tolerance(expr, name, weaker_if_larger):
        if _literal(expr) is not None:
            roles[id(expr)] = ("tolerance", name, weaker_if_larger)

    def single(expr, role):
        if expr is not None and _literal(expr) is not None:
            roles[id(expr)] = role

    def order(left, op, right, negate):
        if negate:
            op = _NEGATED_ORDER[op]
        greater = op in (ast.Gt, ast.GtE)
        single(left, ("order", "upper" if greater else "lower"))
        single(right, ("order", "lower" if greater else "upper"))

    def compare(expr, negate):
        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
            expr, negate = expr.operand, not negate
        if not isinstance(expr, ast.Compare) or len(expr.ops) != 1:
            return
        op, right = type(expr.ops[0]), expr.comparators[0]
        if op in (ast.Eq, ast.NotEq, ast.Is, ast.IsNot):
            equality(expr.left)
            equality(right)
        elif op in (ast.In, ast.NotIn):
            single(expr.left, ("membership", (op is ast.NotIn) != negate))
        elif op in _NEGATED_ORDER:
            order(expr.left, op, right, negate)

    if isinstance(node, ast.Assert):
        compare(node.test, False)
        return roles
    name = _assertion_kind(node)
    args = node.args
    keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    if name in ("assertTrue", "assertFalse") and args:
        compare(args[0], name == "assertFalse")
    elif name in _ORDER_METHODS and len(args) >= 2:
        order(args[0], _ORDER_METHODS[name], args[1], False)
    elif name in ("assertIn", "assertNotIn") and args:
        single(args[0], ("membership", name == "assertNotIn"))
    elif name in _REGEX_METHODS:
        for expr in args[1:2] + [keywords.get("expected_regex")]:
            single(expr, ("regex",))
    elif name == "assertNotRegex":
        for expr in args[1:2] + [keywords.get("unexpected_regex")]:
            single(expr, ("regex_not",))
    elif name in _EQUALITY_METHODS:
        for expr in args[:2]:
            equality(expr)
        if name in ("assertAlmostEqual", "assertNotAlmostEqual"):
            # У `assertNotAlmostEqual` направление обратное (требование 9).
            direct = name == "assertAlmostEqual"
            if len(args) > 2:
                tolerance(args[2], "places", not direct)
            for kw_name, larger in (("places", not direct), ("delta", direct)):
                if kw_name in keywords:
                    tolerance(keywords[kw_name], kw_name, larger)
    elif name in _MOCK_CALL_ASSERTS:
        for expr in args + list(keywords.values()):
            equality(expr)
    elif name in ("raises", "warns") and "match" in keywords:
        single(keywords["match"], ("regex",))
    return roles


def _approx_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "approx") or \
        (isinstance(func, ast.Name) and func.id == "approx")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strictness_sign(role, old, new) -> str:
    """Признак ослабления одной пары смены ожидания (требование 9); пустая
    строка — строгость не ниже прежней."""
    shown = f"{old!r} → {new!r}"
    unrated = f"{SIGN_UNRATED}: {shown}"
    if role is None:
        return unrated
    kind = role[0]
    if kind == "equality":
        return ""
    if kind == "tolerance":
        _kind, name, weaker_if_larger = role
        if not (_is_number(old) and _is_number(new)):
            return unrated
        if new != old and (new > old) == weaker_if_larger:
            return f"допуск {name} ослаблен: {shown}"
        return ""
    if kind == "regex_not":
        return f"{SIGN_UNRATED} (регулярное выражение assertNotRegex): {shown}"
    if kind == "regex":
        if not (isinstance(old, str) and isinstance(new, str)):
            return unrated
        for anchor in _REGEX_ANCHORS:
            if new.count(anchor) < old.count(anchor):
                return f"регулярное выражение потеряло якорь {anchor}: {shown}"
        for wildcard in _REGEX_WILDCARDS:
            if new.count(wildcard) > old.count(wildcard):
                return f"в регулярное выражение добавлено {wildcard}: {shown}"
        return ""
    if kind == "membership":
        if not (isinstance(old, str) and isinstance(new, str)):
            return unrated
        negated = role[1]
        if not negated and (new == "" or (new != old and new in old)):
            return f"строка вхождения стала собственной подстрокой прежней: {shown}"
        if negated and old != new and old in new:
            return f"прежняя строка невхождения — собственная подстрока новой: {shown}"
        return ""
    if kind == "order":
        if not (_is_number(old) and _is_number(new)):
            return unrated
        lower = role[1] == "lower"
        if (lower and new < old) or (not lower and new > old):
            return f"граница сдвинута в разрешающую сторону: {shown}"
        return ""
    return unrated


def _value_key(value) -> tuple:
    """Сравнение констант по типу и значению (требование 6): `1` и `1.0`,
    `True` и `1` — разные значения."""
    return type(value).__name__, repr(value)


def _expectation_pairs(base_node: ast.AST, head_node: ast.AST) -> list:
    """[(константа base, константа head, признак)] по позициям, где
    литералы двух утверждений с равной маскированной формой различаются
    (литерал — константа либо знак над числовой константой, `_literal`).
    Равная маскированная форма — равная структура вне литералов, поэтому
    позиции литералов обеих сторон идут узел в узел."""
    roles = _constant_roles(base_node)
    pairs = []
    for (left, old), (_right, new) in zip(_literal_positions(base_node),
                                          _literal_positions(head_node)):
        if _value_key(old) != _value_key(new):
            pairs.append((old, new,
                          _strictness_sign(roles.get(id(left)), old, new)))
    return pairs


def assertion_changes(base_source, head_source, paths=(None, None),
                      modules=(None, None)) -> dict | None:
    """{квалифицированное имя: AssertionChange} по методам, имя которых
    есть по обе стороны и у которых изменены утверждения (SPEC
    01M45FJD46BX45VHC36S4VS9QN, требования 5 и 9).

    R — утверждения base, которых в head меньше (то же, что отдаёт
    `changed_test_assertions`), A — утверждения head, которых в base
    меньше; сравниваются мультимножества нормальных форм `test_assertions`.
    R пусто — метода в ответе нет: добавленные и переставленные
    утверждения сменой не являются. Каждое утверждение R сопоставляется
    первому по порядку появления ещё свободному утверждению A с равной
    маскированной формой — все сопоставились: смена ожидания с
    фактическими парами констант; иначе — ослабление или иная смена с
    признаком (утверждений меньше, другой вид, литерал заменён
    вычисленным значением, иной сдвиг маскированной формы).

    `None` — одна из сторон не разбирается (тот же контракт, что у
    `test_assertions`). `paths`/`modules` — путь файла и модули `tests/`
    стороны base и стороны head (`test_assertions`)."""
    base = _assertion_records(base_source, paths[0], modules[0])
    head = _assertion_records(head_source, paths[1], modules[1])
    if base is None or head is None:
        return None
    changes: dict = {}
    for name, base_items in base.items():
        if name not in head:
            continue
        head_items = head[name]
        left = Counter(item[0] for item in head_items)
        lost = []
        for item in base_items:
            if left[item[0]] > 0:
                left[item[0]] -= 1
            else:
                lost.append(item)
        if not lost:
            continue
        right = Counter(item[0] for item in base_items)
        added = []
        for item in head_items:
            if right[item[0]] > 0:
                right[item[0]] -= 1
            else:
                added.append(item)
        free = list(added)
        matched, unmatched = [], []
        for item in lost:
            mask = _masked_form(item[2])
            pair = next((a for a in free if _masked_form(a[2]) == mask), None)
            if pair is None:
                unmatched.append(item)
            else:
                free.remove(pair)
                matched.append((item, pair))
        origins = tuple(item[3] for item in lost)
        if unmatched:
            signs = tuple(_other_change_sign(item, free) for item in unmatched)
            changes[name] = AssertionChange(ASSERTION_CHANGE_OTHER, (), signs,
                                            origins)
            continue
        pairs, signs = [], []
        for item, pair in matched:
            for old, new, sign in _expectation_pairs(item[2], pair[2]):
                pairs.append((old, new))
                if sign:
                    signs.append(sign)
        changes[name] = AssertionChange(ASSERTION_CHANGE_EXPECTATION,
                                        tuple(pairs), tuple(signs), origins)
    return changes


def literal_pair_keys(pairs) -> set | None:
    """Множество пар (база, голова) для сверки с объявленным (требование
    6): каждая сторона — значение, сравниваемое по типу и значению.
    Пары-тексты (из раздела SPEC) читаются `ast.literal_eval`; сторона,
    которая не читается как литерал, ни с чем не совпадает — тогда `None`."""
    keys = set()
    for old, new in pairs:
        sides = []
        for side in (old, new):
            if isinstance(side, str):
                try:
                    side = ast.literal_eval(side)
                except (ValueError, SyntaxError, TypeError, MemoryError,
                        RecursionError):
                    return None
            sides.append(_value_key(side))
        keys.add(tuple(sides))
    return keys


def value_pair_keys(pairs) -> set:
    """То же множество для фактических пар `AssertionChange.pairs` —
    значения уже константы, не тексты."""
    return {(_value_key(old), _value_key(new)) for old, new in pairs}


def test_functions_without_mutation_claim(base_source: str | None,
                                          head_source: str | None) -> list[str]:
    """Имена новых/изменённых функций и методов `test_*` HEAD-версии файла
    без заявки «Ловит мутацию: <непустой текст>» в докстринге (SPEC
    01M29A0F88P9GKSXFW90F99H2N, требования 1-2).

    Новая — имени нет в `base_source` (либо `base_source is None`, файл
    добавлен); изменённая — текст сегмента функции в HEAD отличается от
    текста того же имени в base. Неизменённые функции в результат не
    попадают ни при каких условиях (старые тесты не трогаем).

    `head_source is None` — нет сведений о HEAD (пусто, не ошибка вызывающего
    кода): пустой список, ни одной функции не собрать.

    HEAD не парсится (`SyntaxError`) — список из одного элемента
    «<не парсится: текст ошибки>», не исключение (требование 1/AC-4). Base
    не парсится — трактуется как отсутствие сведений о base (все функции
    HEAD в этом файле — новые): тот же fail-safe отказ, что и `base_source
    is None`, не падение гейта на пустом месте.
    """
    if head_source is None:
        return []
    try:
        head_tree = ast.parse(head_source)
    except SyntaxError as exc:
        return [f"<не парсится: {exc}>"]
    head_funcs = _collect_test_functions(head_tree)

    base_funcs: dict[str, ast.AST] = {}
    if base_source is not None:
        try:
            base_tree = ast.parse(base_source)
        except SyntaxError:
            base_tree = None
        if base_tree is not None:
            base_funcs = _collect_test_functions(base_tree)

    missing: list[str] = []
    for name, node in head_funcs.items():
        base_node = base_funcs.get(name)
        if base_node is not None:
            head_segment = ast.get_source_segment(head_source, node)
            base_segment = ast.get_source_segment(base_source, base_node)
            if head_segment == base_segment:
                continue
        if not MUTATION_CLAIM.search(ast.get_docstring(node) or ""):
            missing.append(name)
    return missing


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


def scan_id_format_samples(tdir: Path, rule: "PlankRule | None" = None
                           ) -> list[str]:
    """Ошибки образца формата идентификатора для всех `*.py` под
    acceptance_tests/ рабочей копии — та же область файлов, что источники
    трассируемости AC (`scan_ac_content`), шире `scan_redness_markers`
    (не только `test_*.py`): образец формата может утечь и во
    вспомогательный файл вроде `_sandbox.py`.

    `rule` не по умолчанию — все файлы компонентов планки, не только `.py`.
    """
    if _by_rule(rule):
        return id_format_sample_errors(
            [(str(f), text) for f, text
             in _rule_plank_files(tdir, rule, tests_only=False)])
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
# Копия лёгкой песочницы переходов вместо импорта из tests/sandbox.py (SPEC
# 01M1TKP45EM16ZMJGQKNZA5T7J, требование 3, AC-8): копилка 06.09 — три
# планки упали за один вечер из-за устаревшей копии, которую тест-автор
# каждый раз переписывал заново вместо импорта эталона (skills/
# test-authoring.md). Предупреждение, не ошибка — планка написана до
# появления эталона (или до правки скила у test_author) не обязана
# ретроактивно переписываться, только новые копии подсвечиваются.
SANDBOX_OWN_DEFINITION_RE = re.compile(
    r"^\s*def\s+(disk_backed_\w+|advance_from_in_dev)\s*\(", re.M)


def sandbox_reuse_check(tdir: Path) -> dict:
    """`{"errors": [], "warnings": [...]}` — предупреждение, если
    `<tdir>/acceptance_tests/_sandbox.py` определяет собственные функции
    `disk_backed_*`/`advance_from_in_dev` вместо импорта их из `tests/
    sandbox.py`. Ищет буквальное `def disk_backed_*`/`def
    advance_from_in_dev` — `from tests.sandbox import (disk_backed_show,
    ...)` тем же именем в импорте не попадает под собственное
    определение. Файла нет вовсе (сценарий не нуждается в локальной
    надстройке) — ни ошибки, ни предупреждения."""
    sandbox_path = tdir / "acceptance_tests" / "_sandbox.py"
    if not sandbox_path.is_file():
        return {"errors": [], "warnings": []}
    try:
        text = sandbox_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"errors": [], "warnings": []}
    if SANDBOX_OWN_DEFINITION_RE.search(text):
        return {"errors": [], "warnings": [
            f"{sandbox_path}: определяет собственные disk_backed_*/"
            f"advance_from_in_dev вместо импорта из tests/sandbox.py "
            f"(skills/test-authoring.md)"]}
    return {"errors": [], "warnings": []}


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
    r"^(test_.*\.py|_[A-Za-z0-9_]+\.py|markers\.py|__init__\.py|.+\.md|.+\.txt)$")

# Паспорт живой задачи пишет пульт: заголовок и строки «<время> <состояние>
# actor=<кто>», frontmatter у него нет — это не артефакт роли (SPEC
# 01M490TDWEMDQ700VXTKYANF7K). С мержа ADR-0021 этапа 3 части 3 паспорт
# ведётся и у задач артели, и проверка артефакта на нём отказывала мерж.
TASK_PASSPORT_NAME = "PASSPORT.md"
PASSPORT_SKIP_NOTE = "паспорт задачи, не артефакт роли — пропущен"


def is_task_passport(path: Path) -> bool:
    """`True` — `path` есть паспорт задачи: файл `PASSPORT.md`, чей каталог
    лежит непосредственно в каталоге `tasks` (первый уровень каталога
    задачи). `PASSPORT.md` в любом другом месте паспортом не считается и
    проверяется как прежде (требование 2, AC-7)."""
    return path.name == TASK_PASSPORT_NAME and path.parent.parent.name == "tasks"


# Записка шага `NOTE-<роль>.md` (SPEC 01M4RZBPG6EXM74MTBPTEGW2D4, требования
# 1-2): свободный текст роли следующему шагу, по одному файлу на роль. Один
# перечень на guard, бриф, миссию и автокоммит — роли `roles.yaml` с
# `executor: agent`.
STEP_NOTE_ROLES = ("analyst", "spec_auditor", "test_author", "developer",
                   "reviewer")
STEP_NOTE_NAMES = tuple(f"NOTE-{role}.md" for role in STEP_NOTE_ROLES)
STEP_NOTE_SKIP_NOTE = "записка шага, свободный текст роли — пропущена"


def step_note_name(role: str) -> str:
    """Имя записки шага роли `role` в каталоге задачи."""
    return f"NOTE-{role}.md"


def is_step_note(path: Path) -> bool:
    """`True` — `path` есть записка шага: имя из `STEP_NOTE_NAMES` первым
    уровнем каталога задачи (тот же признак уровня, что `is_task_passport`).
    Записка в подкаталоге или в `acceptance_tests/` запиской не считается и
    проверяется как прежде (требование 2, AC-3)."""
    path = Path(path)
    return path.name in STEP_NOTE_NAMES and path.parent.parent.name == "tasks"

# Имя помощника пульта рядом с планкой (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V,
# требования 3-5; источник — `orchestrator/plank_helper.py`, выкладка —
# `acceptance.PLANK_HELPER_NAME`). Под `_*.py` подходит, но планке не
# принадлежит: пульт кладёт его при каждой выкладке, и копия, оставшаяся в
# рабочей копии кода, не должна доехать до ссылки документов — поэтому
# автокоммит отбрасывает его как посторонний.
RESERVED_PLANK_HELPER_NAME = "_pult.py"
RESERVED_PLANK_HELPER_HINT = "имя занято помощником пульта"


def is_extraneous_acceptance_test_file(rel_to_acceptance_tests: str,
                                       rule: "PlankRule | None" = None) -> bool:
    """`rel_to_acceptance_tests` — путь файла относительно `acceptance_tests/`
    (`/`-разделённый, например `test_x.py` или `docs/codebase-map.md`).
    `True` — файл вне разрешённого набора первого уровня (AC-1 задачи
    01M1SAA01YRRTWAVADT2F81RRQ) либо зарезервированное имя помощника
    пульта `RESERVED_PLANK_HELPER_NAME`.

    `rule` — допустимые файлы по правилу планки проекта (SPEC
    01M59KMPG2ZMK10V556VZVQD65, требование 1): файл не принадлежит ни
    одному компоненту и не общий."""
    if rule is not None:
        return rule.component_of(rel_to_acceptance_tests) is None
    if "/" in rel_to_acceptance_tests:
        return True
    if rel_to_acceptance_tests == RESERVED_PLANK_HELPER_NAME:
        return True
    # Паспорт законен только первым уровнем каталога задачи (SPEC
    # 01M490TDWEMDQ700VXTKYANF7K, AC-4): здесь `.+\.md` пустил бы его в
    # проверку артефакта, и вместо именованной причины вышло бы «нет
    # frontmatter».
    if rel_to_acceptance_tests == TASK_PASSPORT_NAME:
        return True
    return not ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL.match(rel_to_acceptance_tests)


# --------------------------------------------------------------------------
# Правило планки по компоненту (SPEC 01M59KMPG2ZMK10V556VZVQD65, требования
# 1, 3-5; ADR-0026 пп. 1, 3, 5): какие файлы первого уровня каталога планки
# допустимы и чьи они, какие из них тестовые, вид метки критерия и
# синтаксис пометок. Строит правило по записи проекта
# `orchestrator/project_profile.plank_rule`; здесь — только описание и
# разбор, без зависимостей пульта. Правило без компонентов —
# `DEFAULT_PLANK_RULE`, нынешнее правило: функции разбора с ним идут
# прежним путём побайтно.
LABEL_TEST_AC = "test_ac<n>_"
LABEL_AC = "^AC-<n>: "
MARKER_HASH = "#"
MARKER_SLASH = "//"
# `component_of` у правила-умолчания и у общих файлов (`.md`/`.txt`
# первого уровня, в том числе перечень долгоживущих) — не имя компонента.
DEFAULT_PLANK_COMPONENT = "default"
SHARED_PLANK_FILE = "*"
ALWAYS_STRAY_PLANK_NAMES = (RESERVED_PLANK_HELPER_NAME, TASK_PASSPORT_NAME,
                            "conftest.py")
_SHARED_PLANK_NAME = re.compile(r"^(.+\.md|.+\.txt)$")


def _mask_segment_matches(segment: str, name: str) -> bool:
    regex = "".join("[^/]*" if ch == "*" else re.escape(ch) for ch in segment)
    return re.fullmatch(regex, name) is not None


@dataclass(frozen=True)
class PlankComponent:
    """Компонент правила планки: имя, маски `tests` записи, вид метки и
    синтаксис пометок. pytest-компонент (`LABEL_TEST_AC`) допускает файлы
    по `ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL`; компонент с меткой
    `LABEL_AC` — файлы под последний сегмент масок и помощники
    `_<имя>.<расширение маски>`."""
    name: str
    masks: tuple = ()
    label: str = LABEL_TEST_AC
    marker: str = MARKER_HASH

    def _patterns(self) -> list[str]:
        return [mask.rsplit("/", 1)[-1] for mask in self.masks]

    def is_test(self, name: str) -> bool:
        if self.label != LABEL_AC:
            return name.startswith("test_") and name.endswith(".py")
        return any(_mask_segment_matches(p, name) for p in self._patterns())

    def allows(self, name: str) -> bool:
        if self.label != LABEL_AC:
            return bool(ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL.match(name))
        if self.is_test(name):
            return True
        suffixes = {"." + p.rsplit(".", 1)[1] for p in self._patterns()
                    if "." in p}
        return any(re.fullmatch(r"_[A-Za-z0-9_]+" + re.escape(suffix), name)
                   for suffix in suffixes)


@dataclass(frozen=True)
class PlankRule:
    """Правило планки проекта. `components` — в порядке записи: файл,
    подходящий нескольким, принадлежит первому. `refusal` — причина отказа
    построения правила по записи (правило тогда — умолчание с причиной)."""
    components: tuple = ()
    refusal: str = ""

    @property
    def is_default(self) -> bool:
        return not self.components

    def _component(self, name: str) -> "PlankComponent | None":
        for comp in self.components:
            if comp.allows(name):
                return comp
        return None

    def component_of(self, name: str) -> str | None:
        """Имя компонента файла `name` (путь от `acceptance_tests/`);
        `SHARED_PLANK_FILE` — общий файл; `None` — посторонний."""
        if "/" in name or name in ALWAYS_STRAY_PLANK_NAMES:
            return None
        if not self.components:
            if is_extraneous_acceptance_test_file(name):
                return None
            return (SHARED_PLANK_FILE if _SHARED_PLANK_NAME.match(name)
                    else DEFAULT_PLANK_COMPONENT)
        if _SHARED_PLANK_NAME.match(name):
            return SHARED_PLANK_FILE
        comp = self._component(name)
        return comp.name if comp is not None else None

    def owns(self, name: str) -> bool:
        """Файл принадлежит компоненту (не общий и не посторонний)."""
        return self.component_of(name) not in (None, SHARED_PLANK_FILE)

    def is_test(self, name: str) -> bool:
        if not self.owns(name):
            return False
        if not self.components:
            return name.startswith("test_") and name.endswith(".py")
        return self._component(name).is_test(name)

    def is_labelled(self, name: str) -> bool:
        """Файл размечен меткой `AC-<n>: ` и пометками `//`."""
        comp = self._component(name) if self.owns(name) else None
        return comp is not None and comp.label == LABEL_AC

    def masks(self, component: str) -> tuple:
        for comp in self.components:
            if comp.name == component:
                return tuple(comp.masks)
        return ()

    def labelled_components(self) -> tuple:
        """Имена компонентов с меткой `AC-<n>: ` в порядке записи."""
        return tuple(c.name for c in self.components if c.label == LABEL_AC)


DEFAULT_PLANK_RULE = PlankRule()


def _by_rule(rule: "PlankRule | None") -> bool:
    """Разбор идёт по правилу, а не прежним путём: правило не по
    умолчанию."""
    return rule is not None and not rule.is_default


def _rule_plank_files(tdir: Path, rule: PlankRule,
                      tests_only: bool) -> list[tuple[Path, str]]:
    """(путь, текст) файлов первого уровня `acceptance_tests/` каталога
    `tdir`, принадлежащих компонентам правила (`tests_only` — только
    тестовых)."""
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files = []
    for f in sorted(tests_dir.iterdir()):
        if not f.is_file() or not rule.owns(f.name):
            continue
        if tests_only and not rule.is_test(f.name):
            continue
        try:
            files.append((f, f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return files


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
# собственным правилам (см. выше), этим правилом не задета. Единственный
# разрешённый каталог первого уровня — `acceptance_tests/`: файл внутри
# ЛЮБОГО другого, впервые заведённого каталога первого уровня (например
# `wip/_head_map.md`) — посторонний независимо от расширения, тем же
# классом инцидента на один уровень вложенности глубже (REVIEW.md
# итерации 1, замечание R1-F1: критерий проверял только путь ровно из
# одного сегмента и молчал на файле внутри новой поддиректории).
EXTRANEOUS_TASK_ROOT_FILE_REASON = "посторонний файл в каталоге задачи"
# Hotfix №21 (11.09): PASSPORT.md — паспорт живой задачи, который пишет
# САМ пульт на каждом переходе задачи внешнего target (T094 требование 11,
# `store._append_passport_line`); белый список 01M1TNN4 (06.09) его не
# знал — мерж любой задачи внешнего target отказывал бы «посторонним
# файлом» (нашла планка B2 01M1R5B33C, AC-15).
# SPEC-AUDIT.md — вердикт аудитора SPEC (SPEC 01M4MQAGRWMWR0GFDM9086P3TD,
# требование 9): ровно это имя, не маска — соседние имена остаются
# посторонними.
# Записки шага (SPEC 01M4RZBPG6EXM74MTBPTEGW2D4, требование 1) — точные имена
# из `STEP_NOTE_ROLES`, не маска `NOTE-.*`: `NOTE.md` и `NOTE-<не роль>.md`
# остаются посторонними.
TASK_ROOT_ALLOWED_MD = re.compile(
    r"^(SPEC|SPEC-AUDIT|PLAN|REVIEW|TEST_REPORT|QUESTIONS|TZ|PASSPORT|"
    r"ANSWER-\d+|"
    + "|".join(re.escape(name[:-len(".md")]) for name in STEP_NOTE_NAMES)
    + r")\.md$")


def is_extraneous_task_root_file(rel_to_task_dir: str) -> bool:
    """`rel_to_task_dir` — путь файла относительно `tasks/<id>/` (`/`-
    разделённый, например `_head_map.md`, `__pycache__/junk.pyc` или
    `wip/_head_map.md`). `True` — файл посторонний (требование 1,
    ANSWER-1, R1-F1): `.md` первого уровня вне `TASK_ROOT_ALLOWED_MD`,
    любой скрытый файл/каталог (`.`-префикс любого сегмента пути), файл
    внутри `__pycache__/` первого уровня, либо файл внутри ЛЮБОЙ другой
    поддиректории первого уровня (единственная легальная поддиректория —
    `acceptance_tests/`, по собственным правилам
    `is_extraneous_acceptance_test_file` выше, не этой функцией)."""
    parts = rel_to_task_dir.split("/")
    if parts[0] == "acceptance_tests":
        return False
    if any(p.startswith(".") for p in parts):
        return True
    if parts[0] == "__pycache__":
        return True
    if len(parts) == 1:
        if parts[0].endswith(".md"):
            return not TASK_ROOT_ALLOWED_MD.match(parts[0])
        return False
    return True


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


def _rule_labels(rule: "PlankRule | None") -> set:
    """Виды метки компонентов правила; без правила и у умолчания — pytest."""
    if not _by_rule(rule):
        return {LABEL_TEST_AC}
    return {comp.label for comp in rule.components}


def _missing_test_hint(n: int, labels: set) -> str:
    """Подсказка «нет теста» с формой теста и пометки по видам метки
    правила (SPEC 01M59KMPG2ZMK10V556VZVQD65, требование 4)."""
    if labels == {LABEL_AC}:
        return (f"добавь тест 'it('AC-{n}: …')' в acceptance_tests/, либо "
                f"пометку '// AC-{n}: manual|skip|escalate — причина' в том "
                f"же каталоге")
    if LABEL_AC in labels:
        return (f"добавь тестовый метод 'def test_ac{n}_...' либо тест "
                f"'it('AC-{n}: …')' в acceptance_tests/, либо пометку "
                f"'# AC-{n}: manual|skip|escalate — причина' (в .py) либо "
                f"'// AC-{n}: manual|skip|escalate — причина' в том же "
                f"каталоге")
    return (f"добавь тестовый метод 'def test_ac{n}_...' в "
            f"acceptance_tests/, либо пометку "
            f"'# AC-{n}: manual|skip|escalate — причина' в том же "
            f"каталоге")


def traceability_errors_from_content(spec_text: str, meta: dict, tested: set,
                                     markers: dict,
                                     rule: "PlankRule | None" = None
                                     ) -> list[str]:
    """Ядро проверки трассируемости AC -> тест (SPEC T023, требование 4) по
    уже прочитанным SPEC-тексту и результату `scan_ac_content` — без
    чтения файлов: источник (рабочая копия или ВЕТКА задачи, SPEC T031,
    AC-3) выбирает вызывающий код (`acceptance_traceability_errors` — диск,
    `orchestrator/fsm.py` — git при чужом чекауте), не эта функция.

    `rule` — формы теста и пометки в подсказках по виду метки компонентов
    правила; без правила и при умолчании — прежние тексты.
    """
    if not requires_ac_markup(meta):
        return []
    labels = _rule_labels(rule)
    marker_prefix = MARKER_SLASH if labels == {LABEL_AC} else MARKER_HASH
    body = section_body(spec_text, "Критерии приёмки")
    ac_numbers = {int(n) for n in AC_ITEM.findall(body)}
    ac_texts = {int(n): text for n, text in AC_ITEM_FULL.findall(body)}
    errors: list[str] = []
    for n in sorted(ac_numbers):
        if n not in tested and n not in markers:
            errors.append(
                f"AC-{n}: нет теста и нет пометки manual/skip/escalate — "
                f"{_missing_test_hint(n, labels)}")
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
                f"'{marker_prefix} AC-{n}: {kind} — <причина>'")
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


def acceptance_traceability_errors(tdir: Path,
                                   extra_sources: list[str] = (),
                                   rule: "PlankRule | None" = None
                                   ) -> list[str]:
    """AC без теста и без пометки — невалидный выход из tests_writing
    (SPEC T023, требование 4), рабочая копия.

    SPEC без AC-разметки (версия 1 или `skip_tests`) — tests_writing эту
    задачу не проходит, сверять нечего. Само правило —
    `traceability_errors_from_content`.

    Несёт также ошибки маркера AC-n с отступом
    (01M28NX43ERJGHCJN29HVKMCC3, `scan_indented_ac_markers`) — тот же
    выход из tests_writing обязан отказывать и на этом классе дефекта,
    не только на буквальном «нет теста и нет пометки».

    `extra_sources` — тексты долгоживущих файлов `tests/` кодовой ветки
    этой задачи (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 5): их методы
    `test_ac<n>_…` покрывают критерии наравне с каталогом приёмочных тестов;
    пара (путь, текст) — разбор по правилу `rule`, `it('AC-<n>: …')`
    долгоживущего файла с меткой (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
    требование 7); текст — прежний разбор Python.

    `rule` — правило планки проекта (SPEC 01M59KMPG2ZMK10V556VZVQD65,
    требования 3-4): разбор, подсказки и пометки с отступом по нему.
    """
    spec_path = tdir / "SPEC.md"
    try:
        text = spec_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{spec_path}: не прочитан: {exc}"]
    meta = yamlmini.frontmatter(text) or {}
    tested, markers = scan_acceptance_tests(tdir, rule)
    extra_tested, extra_markers = scan_ac_content(list(extra_sources), rule)
    tested = tested | extra_tested
    markers = {**extra_markers, **markers}
    errors = traceability_errors_from_content(text, meta, tested, markers,
                                              rule)
    return errors + scan_indented_ac_markers(tdir, rule)


# --------------------------------------------------------------------------
# Маркер AC-n с отступом (01M28NX43ERJGHCJN29HVKMCC3): `# AC-n: manual|
# skip|escalate|ci`, поставленный не в начале строки. AC_MARKER (заякорен
# на `^#`, без отступа) молча не видит такую строку — критерий остаётся
# без пометки и без явной причины (инцидент 11.09, `# AC-7: manual`
# вместо снятого тестового метода, ADR-0014 ч.2, 01M1THKWFX). Проверка
# ниже находит такую строку явно и называет её отдельной, именованной
# ошибкой, а не полагается на побочный эффект «нет теста и нет пометки».
INDENTED_AC_MARKER_REASON_TMPL = (
    "маркер '# AC-{n}: {kind}' с отступом не учитывается каталогом — "
    "вынеси в начало строки либо убери")
# Тот же текст для пометки `//` файла не-pytest компонента (SPEC
# 01M59KMPG2ZMK10V556VZVQD65, требование 4): меняется только префикс.
INDENTED_SLASH_AC_MARKER_REASON_TMPL = INDENTED_AC_MARKER_REASON_TMPL.replace(
    "'# AC-", "'// AC-")


def _string_literal_lines(source: str) -> set[int]:
    """Номера строк (1-based) файла `source`, занятые строковыми
    константами (докстринги и любые другие строковые литералы) — `ast.
    parse`, тот же приём, что `module_docstring` выше, но по ВСЕМ
    строковым узлам файла, не только докстрингу модуля (требование 2:
    буквальный пример синтаксиса маркера внутри докстринга/строкового
    литерала — не нарушение).

    Пустое множество — файл не разбирается (`SyntaxError`): вызывающий
    код в этом случае ничего не исключает — остаётся запасная эвристика
    требования 2 («строка начинается с отступа и `#`» — признак
    комментария), допустимая явно, когда guard не различает докстринг.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            end = getattr(node, "end_lineno", None) or node.lineno
            lines.update(range(node.lineno, end + 1))
    return lines


def indented_ac_marker_errors_from_files(files: list[tuple[str, str]],
                                         rule: "PlankRule | None" = None
                                         ) -> list[str]:
    """Ошибки маркера AC-n с отступом (требования 1-2) по уже прочитанным
    (label, текст) парам .py-файлов acceptance_tests/ — источник (диск
    или ВЕТКА задачи) выбирает вызывающий код, тем же приёмом, что
    `redness_marker_errors_from_files`/`id_format_sample_errors`.

    Строка, занятая строковым литералом/докстрингом (`_string_literal_
    lines`), из проверки исключается — требование 2. Строка с
    маркер-подобным текстом, которому предшествуют на той же строке
    кавычки или любой другой символ (не только отступ), под
    `INDENTED_AC_MARKER` не подпадает вовсе — регулярка заякорена на
    `^[ \\t]+#`, ровно тем же приёмом, каким `AC_MARKER` уже отсекает
    текст маркера, не стоящий буквально в начале строки (комментарий
    выше `AC_MARKER`, R1-F2).

    `rule` — файл компонента с пометками `//` (по имени из `label`)
    проверяется образцом `INDENTED_SLASH_AC_MARKER`, без разбора строк
    Python.
    """
    errors: list[str] = []
    for label, source in files:
        if rule is not None and rule.is_labelled(Path(label).name):
            for lineno, line in enumerate(source.splitlines(), start=1):
                m = INDENTED_SLASH_AC_MARKER.match(line)
                if m:
                    reason = INDENTED_SLASH_AC_MARKER_REASON_TMPL.format(
                        n=m.group(1), kind=m.group(2))
                    errors.append(f"{label}:{lineno}: {reason}")
            continue
        string_lines = _string_literal_lines(source)
        for lineno, line in enumerate(source.splitlines(), start=1):
            if lineno in string_lines:
                continue
            m = INDENTED_AC_MARKER.match(line)
            if not m:
                continue
            reason = INDENTED_AC_MARKER_REASON_TMPL.format(
                n=m.group(1), kind=m.group(2))
            errors.append(f"{label}:{lineno}: {reason}")
    return errors


def scan_indented_ac_markers(tdir: Path, rule: "PlankRule | None" = None
                             ) -> list[str]:
    """Ошибки маркера AC-n с отступом для `acceptance_tests/test_*.py`
    рабочей копии `tdir` — тот же набор файлов, что `scan_acceptance_tests`
    читает для AC_MARKER без отступа, сохраняя единый домен между
    признанной и непризнанной разметкой одного и того же критерия.

    `rule` не по умолчанию — тестовые файлы планки по правилу.
    """
    if _by_rule(rule):
        return indented_ac_marker_errors_from_files(
            [(str(f), text) for f, text
             in _rule_plank_files(tdir, rule, tests_only=True)], rule)
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files: list[tuple[str, str]] = []
    for f in sorted(tests_dir.rglob("test_*.py")):
        try:
            files.append((str(f), f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return indented_ac_marker_errors_from_files(files)


# Источник артефактов задачи в планке — только артефактная ветка (SPEC
# 01M2XJKKPHM5XDAE42838AMBQH, требования 1-4). Планка пишется в worktree,
# где `tasks/<id>/` лежит на диске целиком, а прогоняется пультом в среде,
# куда материализован ТОЛЬКО `acceptance_tests/` (`orchestrator/pull.py::
# _materialize_and_run_plank`, `acceptance.materialize_from_branch`):
# тест, читающий `PLAN.md`/`SPEC.md` с диска, зелен у автора и красен на
# гейте (12.09 01M2B6K3EM AC-8, 13.09 01M2CN465W test_ac4 — оба закрыты
# руками через `amend-tests`).
#
# Проверка — по AST, не по тексту строки (требование 2): имя артефакта в
# докстринге/комментарии (в том числе в концевом комментарии строки с
# настоящим чтением ПОСТОРОННЕГО файла) — не нарушение; чтение через
# `gitcmd.show(...)`/`artifact_branch`/`subprocess` с `git show`/`git
# cat-file` — не нарушение, потому что ни один из этих вызовов не входит
# в набор выражений доступа к файловой системе ниже.
#
# Нарушение — только путь, ЯКОРЕННЫЙ на рабочую копию (ANSWER-1 задачи,
# вариант B: уточнение требования 1 и AC-1/AC-5): цепочка от
# `Path(__file__)`, от `config.ROOT`/`config.TASKS`, либо литерал,
# начинающийся с `tasks/`, — включая имена, присвоенные от таких выражений
# (`TASK_DIR = Path(__file__).resolve().parents[1]`). Пути от временных
# каталогов (`tempfile`, `self.tdir` вложенной песочницы FSM-задач, которая
# ПИШЕТ поддельные `SPEC.md`/`PLAN.md` фиктивной задачи) под правило не
# подпадают: такая планка читает не артефакт задачи, а свою фикстуру, и
# в среде гейта она так же зелена, как у автора. До уточнения правило
# «любое выражение доступа с именем артефакта» отклоняло бы 68 из 186
# исторических планок и планку самой задачи (REVIEW.md итерации 1, R1-F1).
#
# Вызывается ТОЛЬКО гейтом выхода `tests_writing` (`orchestrator/
# advance_gates/tests_writing.py`), НЕ из `check()`/`main()` (требование
# 4): режим CI «Валидация артефактов» по всему `tasks/` исторические
# планки, читавшие артефакты с диска до появления правила, не
# переписывает (модульный докстринг: «история не переписывается»).
ARTIFACT_FILE_NAMES = ("PLAN.md", "SPEC.md", "REVIEW.md", "TZ.md",
                       "QUESTIONS.md", "TEST_REPORT.md", "ANSWER-")

# Вызовы доступа к файловой системе по точечному имени функции
# (`Path("…/PLAN.md")`, `open(…)`, `os.path.join(…)`, `os.path.exists(…)`)
# и методы по имени атрибута без учёта получателя (`x.read_text(…)`,
# `x.joinpath("PLAN.md")` — метод-форма операции `/` у Path).
_FS_ACCESS_CALLS = frozenset({"open", "Path", "pathlib.Path",
                              "os.path.join", "os.path.exists"})
_FS_ACCESS_METHODS = frozenset({"read_text", "joinpath"})

# Якоря рабочей копии (ANSWER-1, вариант B): имя `__file__`, атрибуты
# `config.ROOT`/`config.TASKS` (по суффиксу точечного имени — и
# `orchestrator.config.TASKS`), литерал первого сегмента пути `tasks`.
_ANCHOR_NAMES = frozenset({"__file__"})
_ANCHOR_ATTR_SUFFIXES = ("config.ROOT", "config.TASKS")
_ANCHOR_LITERAL_ROOT = "tasks"

# Рецепт называет помощник пульта `_pult.py` (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V,
# требование 6): он читает ссылку документов ревизии выкладки и работает без
# пакета `orchestrator` рабочей копии и без `.artel/`.
ARTIFACT_DISK_READ_RECIPE_TMPL = (
    "читай через помощник пульта рядом с планкой: "
    "from _pult import artifact_text; artifact_text(\"{name}\")")


def _dotted_name(node: ast.AST) -> str | None:
    """`a.b.c` для цепочки Name/Attribute; `None` — узел иной формы
    (вызов, подписка, литерал)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _artifact_name_in_literal(value: str) -> str | None:
    """Имя артефакта, которое несёт строковый литерал `value`; `None` —
    литерал об артефактах не говорит.

    В рецепт уходит имя файла из литерала (`tasks/<id>/ANSWER-1.md` для
    префикса `ANSWER-`) ТОЛЬКО когда basename литерала начинается с имени
    артефакта; иначе — само имя из `ARTIFACT_FILE_NAMES`: часть f-строки
    `f"{TASK}-PLAN.md"` — это литерал `-PLAN.md`, и рецепт с
    `tasks/<id>/-PLAN.md` называл бы несуществующий файл (R1-F2 REVIEW.md
    итерации 1)."""
    for name in ARTIFACT_FILE_NAMES:
        if name not in value:
            continue
        basename = value.rsplit("/", 1)[-1]
        return basename if basename.startswith(name) else name
    return None


def _literal_is_anchored(value: str, root: bool) -> bool:
    """Строковый литерал якорится на рабочую копию, если начинается с
    `tasks/`; голое `tasks` — только в корневой позиции пути (первый
    аргумент `os.path.join("tasks", …)`), не операндом `/` посреди цепочки
    (`Path(tmp) / "tasks" / TASK / "SPEC.md"` — путь от временного
    каталога)."""
    return (value.startswith(_ANCHOR_LITERAL_ROOT + "/")
            or (root and value == _ANCHOR_LITERAL_ROOT))


def _is_anchored(node: ast.AST, names: set[str]) -> bool:
    """Выражение пути якорится на рабочую копию (ANSWER-1, вариант B):
    `__file__`, имя из `names` (присвоенное от якорного выражения),
    `config.ROOT`/`config.TASKS`, корневой литерал `tasks/…`; далее —
    транзитивно по получателю атрибута/подписки/метода (`Path(__file__)
    .resolve().parents[1]`, `TASK_DIR.joinpath(…)`), по первому аргументу
    вызова (`Path(__file__)`, `os.path.join("tasks", …)`, `str(TASK_DIR)`),
    по левому операнду `/` и `+` (`TASK_DIR / "PLAN.md"`, `str(TASK_DIR)
    + "/PLAN.md"`), по началу f-строки (`f"{TASK_DIR}/PLAN.md"`).
    Правый операнд `/` корнем пути не является — литерал там считается
    только с `tasks/`."""
    if isinstance(node, ast.Name):
        return node.id in _ANCHOR_NAMES or node.id in names
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and _literal_is_anchored(node.value, root=True)
    if isinstance(node, ast.JoinedStr):
        if not node.values:
            return False
        first = node.values[0]
        if isinstance(first, ast.FormattedValue):
            return _is_anchored(first.value, names)
        return _is_anchored(first, names)
    if isinstance(node, ast.Attribute):
        dotted = _dotted_name(node)
        if dotted is not None and dotted.endswith(_ANCHOR_ATTR_SUFFIXES):
            return True
        return _is_anchored(node.value, names)
    if isinstance(node, ast.Subscript):
        return _is_anchored(node.value, names)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and _is_anchored(node.func.value, names):
            return True
        return bool(node.args) and _is_anchored(node.args[0], names)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
        if _is_anchored(node.left, names):
            return True
        right = node.right
        return (isinstance(right, ast.Constant) and isinstance(right.value, str)
                and _literal_is_anchored(right.value, root=False))
    return False


def _anchored_names(tree: ast.AST) -> set[str]:
    """Имена, присвоенные от якорных выражений (`TASK_DIR = Path(__file__)
    .resolve().parents[1]`, `PLAN_DIR = TASK_DIR.parent`) — с замыканием
    по цепочке присваиваний. Область видимости не различается (имя
    считается по всему файлу): в планке имя каталога задачи одно, а цена
    ошибки различения — пропуск инцидентного чтения."""
    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            if not _is_anchored(value, names):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return names


def _artifact_literals(node: ast.AST) -> list[tuple[int, str]]:
    """(строка, имя артефакта) для каждого строкового литерала поддерева
    `node` (в т.ч. частей f-строки), несущего имя артефакта задачи."""
    found: list[tuple[int, str]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            name = _artifact_name_in_literal(sub.value)
            if name is not None:
                found.append((sub.lineno, name))
    return found


def _is_fs_access_call(node: ast.Call) -> bool:
    dotted = _dotted_name(node.func)
    if dotted in _FS_ACCESS_CALLS:
        return True
    return (isinstance(node.func, ast.Attribute)
            and node.func.attr in _FS_ACCESS_METHODS)


def artifact_disk_read_errors_from_files(files: list[tuple[str, str]]) -> list[str]:
    """Ошибки чтения артефакта задачи с диска (требования 1-3) по уже
    прочитанным (label, текст) парам `*.py`-файлов `acceptance_tests/` —
    источник выбирает вызывающий код, тем же приёмом, что
    `redness_marker_errors_from_files`/`indented_ac_marker_errors_from_files`.

    Нарушение — строковый литерал с именем артефакта (`ARTIFACT_FILE_
    NAMES`) внутри выражения доступа к файловой системе, путь которого
    ЯКОРИТСЯ на рабочую копию (`_is_anchored`: `__file__`, `config.ROOT`/
    `config.TASKS`, литерал `tasks/…`, имена, присвоенные от них —
    `_anchored_names`; ANSWER-1, вариант B):
    - операнд операции `/` (`Path(__file__).parents[1] / "PLAN.md"`,
      `TASK_DIR / "PLAN.md"` при `TASK_DIR = Path(__file__)…`);
    - поддерево вызова `_FS_ACCESS_CALLS`/`_FS_ACCESS_METHODS`, включая
      цепочку получателя (`TASK_DIR.joinpath("PLAN.md").read_text()`).
    Путь от временного каталога (`Path(tmp) / "tasks" / TASK / "SPEC.md"`,
    `(self.tdir / "SPEC.md").write_text(…)` вложенной песочницы) — не
    нарушение: имя артефакта там называет фикстуру, не артефакт задачи.

    Каждая ошибка: `<label>:<строка литерала>: … — читай через помощник
    пульта рядом с планкой: from _pult import artifact_text;
    artifact_text("<имя>")` (требование 3; рецепт — SPEC
    01M44EP4Q927DJXVX9YMMZ0B7V, требование 6). Один литерал в нескольких
    вложенных выражениях сразу (`open(os.path.join(…, "PLAN.md"))`) —
    одна ошибка, не две. Файл, который не разбирается (`SyntaxError`),
    ошибок здесь не даёт: синтаксис планки — предмет сухого сбора того же
    гейта (`acceptance.collect`), его текст ошибки точнее.
    """
    errors: list[str] = []
    for label, source in files:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        names = _anchored_names(tree)
        hits: set[tuple[int, str]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if not _is_anchored(node, names):
                    continue
                for operand in (node.left, node.right):
                    if isinstance(operand, (ast.Constant, ast.JoinedStr)):
                        hits.update(_artifact_literals(operand))
            elif (isinstance(node, ast.Call) and _is_fs_access_call(node)
                  and _is_anchored(node, names)):
                hits.update(_artifact_literals(node))
        # `ast.walk` обходит дерево в ширину, не по строкам — порядок
        # ошибок внутри файла восстанавливается по номеру строки.
        for lineno, name in sorted(hits):
            errors.append(
                f"{label}:{lineno}: чтение артефакта задачи {name} с диска — "
                + ARTIFACT_DISK_READ_RECIPE_TMPL.format(name=name))
    return errors


def scan_artifact_disk_reads(tdir: Path) -> list[str]:
    """Ошибки чтения артефакта с диска для ВСЕХ `acceptance_tests/**/*.py`
    каталога задачи `tdir` (требование 1, AC-5) — не только `test_*.py`:
    общий модуль планки `_helper.py`, читающий `PLAN.md`, ломает прогон
    точно так же. Метка ошибки — путь относительно `tdir`
    (`acceptance_tests/test_x.py`): каталог `tdir` на гейте — временная
    материализация, её абсолютный путь в истории отказов брифа роли
    ничего не значит.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files: list[tuple[str, str]] = []
    for f in sorted(tests_dir.rglob("*.py")):
        try:
            files.append((str(f.relative_to(tdir)), f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return artifact_disk_read_errors_from_files(files)


# --------------------------------------------------------------------------
# Две группы приёмочных тестов (ADR-0020; SPEC 01M3N0BWYQ9KHVN41Z4G72706R,
# требования 1, 3, 4): строка группы в докстринге модуля `test_*.py` и
# статическая проверка долгоживущего файла. Одно место правила на всех
# потребителей — выход из `tests_writing` и `amend-tests`: оба зовут функции
# ниже, а те читают `GROUP_LINE` глобалом модуля в момент вызова.

GROUP_LONG_LIVED = "долгоживущий"
GROUP_ONE_OFF = "разовый"
GROUP_VALUES = (GROUP_LONG_LIVED, GROUP_ONE_OFF)

# Строка группы — отдельной строкой докстринга, значение на той же строке
# после двоеточия (приём `REDNESS_MARKER`). Якорь начала строки: упоминание
# «Группа:» внутри фразы докстринга строкой группы не считается.
GROUP_LINE = re.compile(r"^[^\S\n]*Группа:[^\S\n]*(\S*)", re.M)


# Ведущая « * » строки блока `/* … */` (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
# требования 5-6): строка группы и заявка мутации читаются без неё.
_BLOCK_COMMENT_STAR = re.compile(r"^[^\S\n]*\*(?!/)[^\S\n]?", re.M)


def plank_file_group(source: str, labelled: bool = False
                     ) -> tuple[str | None, str | None]:
    """(группа, ошибка) файла `test_*.py` по строке группы его докстринга
    модуля: ровно одна из пары не `None`. Файл не разбирается — `(None,
    None)`: синтаксис — предмет сухого сбора, его диагноз точнее.

    `labelled` — файл с меткой `AC-<n>: ` (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
    требование 5): строка группы — в первом комментарии (`first_comment`,
    у блока `/* … */` без ведущей « * »), значения и правила прежние, текст
    называет место «в первом комментарии файла»."""
    if labelled:
        comment = first_comment(source) or ""
        return _group_of(_BLOCK_COMMENT_STAR.sub("", comment),
                         f" {REDNESS_PLACE_FIRST_COMMENT}")
    try:
        docstring = ast.get_docstring(ast.parse(source)) or ""
    except SyntaxError:
        return None, None
    return _group_of(docstring, "")


def _group_of(text: str, place: str) -> tuple[str | None, str | None]:
    """Разбор строки группы текста `text`; `place` — место для текстов
    файла с меткой (у Python тексты прежние, место в первом названо)."""
    values = [m.group(1) for m in GROUP_LINE.finditer(text)]
    if not values:
        return None, (f"нет строки группы "
                      f"{place.strip() or REDNESS_PLACE_DOCSTRING} — допиши "
                      f"«Группа: {GROUP_LONG_LIVED}» или «Группа: "
                      f"{GROUP_ONE_OFF}»")
    unknown = [v for v in values if v not in GROUP_VALUES]
    if unknown:
        return None, (f"неизвестное значение строки группы «{unknown[0]}»"
                      f"{place} — допустимы только «{GROUP_LONG_LIVED}» и "
                      f"«{GROUP_ONE_OFF}»")
    if len(set(values)) > 1:
        return None, (f"строк группы две с разными значениями{place} — "
                      f"оставь одну")
    return values[0], None


def _is_labelled(rule: "PlankRule | None", label: str) -> bool:
    """Файл с меткой `AC-<n>: ` по имени из метки `label` и правилу."""
    return rule is not None and rule.is_labelled(Path(label).name)


def group_line_errors_from_files(files: list[tuple[str, str]],
                                 rule: "PlankRule | None" = None
                                 ) -> list[str]:
    """Ошибки строки группы по (label, текст) парам файлов `test_*.py`
    планки — источник выбирает вызывающий код (приём
    `redness_marker_errors_from_files`). `rule` — файл с меткой несёт
    строку группы в первом комментарии."""
    errors: list[str] = []
    for label, source in files:
        _group, error = plank_file_group(source, _is_labelled(rule, label))
        if error is not None:
            errors.append(f"{label}: {error}")
    return errors


def plank_has_group_lines(files: list[tuple[str, str]]) -> bool:
    """Хоть один `test_*.py` планки несёт распознанную строку группы —
    планка зафиксирована после появления правила (требование 2): до него
    строк группы не писал никто, после — выход из `tests_writing` не
    пропускает `test_*.py` без неё."""
    return any(plank_file_group(source)[0] is not None for _label, source in files)


SIGN_TASKS = "tasks/"
SIGN_GIT_MODULE = "git-модуль"
SIGN_GIT_CALL = "git-вызов"
SIGN_TASK_ID = "номер задачи"
SIGN_SYS_PATH = "sys.path"
SIGN_FOREIGN_IMPORT = "импорт вне перечня"
SIGN_PRIVATE_NAME = "закрытое имя"
SIGN_PATCH_PRIVATE = "patch закрытого"
SIGN_PRIVATE_ATTR = "закрытый атрибут"

_SIGN_EXPLANATIONS = {
    SIGN_TASKS: "долгоживущий файл не знает каталога задачи",
    SIGN_GIT_MODULE: "git-история — факт задачи, не свойство кода",
    SIGN_GIT_CALL: "git-история — факт задачи, не свойство кода",
    SIGN_TASK_ID: "долгоживущий файл не привязан к задаче",
    SIGN_SYS_PATH: "файл обязан собираться из tests/ без правки путей",
    SIGN_FOREIGN_IMPORT: ("только стандартная библиотека, orchestrator, "
                          "scripts, tests — помощники из tests/sandbox.py"),
    SIGN_PRIVATE_NAME: "только публичный интерфейс кода",
    SIGN_PATCH_PRIVATE: "только публичный интерфейс кода",
    SIGN_PRIVATE_ATTR: "только публичный интерфейс кода",
}

_GIT_MODULES = ("orchestrator.gitcmd", "orchestrator.artifact_branch")
_CODE_PACKAGES = ("orchestrator", "scripts")
# Тот же перечень, что `tests/test_invariants.py::StdlibOnlyImportsInvariantTest`.
_LOCAL_PACKAGES = ("orchestrator", "scripts", "tests")
_SYS_PATH_MUTATORS = ("insert", "append", "extend")
_PATCH_NAMES = ("unittest.mock.patch", "mock.patch", "patch")


# Подполе профиля тестов внешнего проекта с перечнем верхних имён импорта
# долгоживущих файлов (`orchestrator/targets.py`, SPEC
# 01M5633WZ3Y3A0P4KKBZDB3KER) — его называет текст признака.
LONG_LIVED_IMPORTS_FIELD = "test_profile.long_lived_imports"


def _allowed_import_tops(project_imports=()) -> frozenset:
    return (frozenset(sys.stdlib_module_names) | frozenset(_LOCAL_PACKAGES)
            | frozenset(name for name, _reason in stack.THIRD_PARTY_EXCEPTIONS)
            | frozenset(project_imports))


def _foreign_import_explanation(project_imports) -> str:
    """Пояснение признака «импорт вне перечня»: `None` — артель, текст
    прежний; иначе — внешний проект, текст называет его перечень либо
    подполе, которое надо заполнить."""
    if project_imports is None:
        return _SIGN_EXPLANATIONS[SIGN_FOREIGN_IMPORT]
    base = "только стандартная библиотека, orchestrator, scripts, tests"
    if project_imports:
        return (f"{base} и перечень проекта {LONG_LIVED_IMPORTS_FIELD}: "
                f"{', '.join(project_imports)}")
    return (f"{base} — имена кода и зависимостей проекта разрешает подполе "
            f"{LONG_LIVED_IMPORTS_FIELD} записи проекта в targets.yaml, "
            f"у проекта оно не заполнено")


def _is_private(segment: str) -> bool:
    """Одно подчёркивание в начале, не dunder (`__init__`)."""
    return segment.startswith("_") and not (
        segment.startswith("__") and segment.endswith("__"))


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Локальное имя -> полный путь модуля/имени, которое к нему привязал
    импорт (`import a.b` -> a: a; `import a.b as x` -> x: a.b; `from m
    import n as k` -> k: m.n). Относительный импорт — пустой путь (ни
    стандартная библиотека, ни `tests`)."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    bindings[top] = top
        elif isinstance(node, ast.ImportFrom):
            module = "" if node.level else (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                full = f"{module}.{alias.name}" if module else ""
                bindings[alias.asname or alias.name] = full
    return bindings


def _resolved_name(node: ast.AST, bindings: dict[str, str]) -> str | None:
    """`_dotted_name` с корнем, заменённым на путь его импорта:
    `mock.patch` при `from unittest import mock` -> `unittest.mock.patch`."""
    dotted = _dotted_name(node)
    if dotted is None:
        return None
    root, _, rest = dotted.partition(".")
    origin = bindings.get(root) or root
    return f"{origin}.{rest}" if rest else origin


def _is_git_command(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        return isinstance(first, ast.Constant) and first.value == "git"
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and (node.value == "git" or node.value.startswith("git ")))


def _private_string_path(node: ast.AST | None) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and any(_is_private(seg) for seg in node.value.split(".")))


def _call_arg(node: ast.Call, index: int, keyword: str) -> ast.AST | None:
    if len(node.args) > index:
        return node.args[index]
    for kw in node.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def _chain_root(node: ast.AST) -> ast.AST:
    """Корень цепочки обращения: `a.b[0].c()._x` -> `a`."""
    while True:
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        elif isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id == "super"):
            node = node.func
        else:
            return node


def _exempt_attribute_root(root: ast.AST, bindings: dict[str, str]) -> bool:
    """Корень цепочки, чьи закрытые атрибуты не признак (требование 3,
    признак 9): `self`/`cls`/`super()` и имя, привязанное импортом из
    стандартной библиотеки или пакета `tests`."""
    if isinstance(root, ast.Call):
        return True  # `super()` — `_chain_root` останавливается только на нём
    if not isinstance(root, ast.Name):
        return False
    if root.id in ("self", "cls"):
        return True
    origin = bindings.get(root.id)
    if not origin:
        return False
    top = origin.split(".")[0]
    return top == "tests" or top in sys.stdlib_module_names


def _import_signs(node: ast.AST, allowed_tops: frozenset) -> list[str]:
    signs: list[str] = []
    if isinstance(node, ast.Import):
        modules = [alias.name for alias in node.names]
        names: list[str] = []
    else:
        if node.level:
            return [SIGN_FOREIGN_IMPORT]
        modules = [node.module or ""]
        names = [alias.name for alias in node.names]
    for module in modules:
        segments = module.split(".")
        if segments[0] not in allowed_tops:
            signs.append(SIGN_FOREIGN_IMPORT)
        full_names = [module] + [f"{module}.{n}" for n in names]
        if any(full == git or full.startswith(git + ".")
               for full in full_names for git in _GIT_MODULES):
            signs.append(SIGN_GIT_MODULE)
        if segments[0] in _CODE_PACKAGES and any(
                _is_private(seg) for seg in segments + names):
            signs.append(SIGN_PRIVATE_NAME)
    return signs


def _call_signs(node: ast.Call, bindings: dict[str, str]) -> list[str]:
    signs: list[str] = []
    name = _resolved_name(node.func, bindings) or ""
    if name.startswith("subprocess.") or name == "os.system":
        args = list(node.args) + [kw.value for kw in node.keywords
                                  if kw.arg == "args"]
        if any(_is_git_command(arg) for arg in args):
            signs.append(SIGN_GIT_CALL)
    if name.rpartition(".")[0] == "sys.path" and (
            name.rpartition(".")[2] in _SYS_PATH_MUTATORS):
        signs.append(SIGN_SYS_PATH)
    if name in _PATCH_NAMES and _private_string_path(
            _call_arg(node, 0, "target")):
        signs.append(SIGN_PATCH_PRIVATE)
    if name in tuple(f"{p}.object" for p in _PATCH_NAMES):
        attribute = _call_arg(node, 1, "attribute")
        if (isinstance(attribute, ast.Constant) and isinstance(attribute.value, str)
                and _is_private(attribute.value)):
            signs.append(SIGN_PATCH_PRIVATE)
    return signs


def _is_sys_path_target(node: ast.AST, bindings: dict[str, str]) -> bool:
    if isinstance(node, ast.Subscript):
        node = node.value
    return _resolved_name(node, bindings) == "sys.path"


def _names_of(node: ast.AST) -> list[str]:
    """Имена, которые узел вводит или называет (признак «номер задачи»)."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, ast.alias):
        return [node.name, node.asname or ""]
    return []


def long_lived_sign_hits(source: str, task_id: str, *,
                         project_imports=()) -> list[tuple[int, str]]:
    """(строка, признак) требования 3 для текста долгоживущего файла, по
    строкам; файл не разбирается — пусто (синтаксис — предмет сухого
    сбора). Признак — формулировка списка требования 3 (`SIGN_*`).

    `project_imports` — верхние имена импорта сверх прежнего набора
    (перечень профиля внешнего проекта), сравнение — точное."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    bindings = _import_bindings(tree)
    allowed_tops = _allowed_import_tops(project_imports)
    task_id_lower = task_id.lower()
    hits: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is None:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "tasks/" in node.value:
                hits.add((lineno, SIGN_TASKS))
            if task_id_lower and task_id_lower in node.value.lower():
                hits.add((lineno, SIGN_TASK_ID))
        if task_id_lower and any(task_id_lower in name.lower()
                                 for name in _names_of(node)):
            hits.add((lineno, SIGN_TASK_ID))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            hits.update((lineno, sign) for sign in _import_signs(node, allowed_tops))
        elif isinstance(node, ast.Call):
            hits.update((lineno, sign) for sign in _call_signs(node, bindings))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_is_sys_path_target(t, bindings) for t in targets):
                hits.add((lineno, SIGN_SYS_PATH))
        elif (isinstance(node, ast.Attribute) and _is_private(node.attr)
              and not _exempt_attribute_root(_chain_root(node.value), bindings)):
            hits.add((lineno, SIGN_PRIVATE_ATTR))
    return sorted(hits)


def _comment_above(lines: list[str], index: int) -> str:
    """Комментарий непосредственно над строкой `lines[index]` (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 6): подряд идущие строки `//`
    либо один блок `/* … */`, кончающийся на строке прямо над ней (у
    строк блока — без ведущей « * »); пустая строка его обрывает. Нет
    комментария — пустая строка."""
    j = index - 1
    if j < 0:
        return ""
    line = lines[j].strip()
    if line.startswith("//"):
        block = []
        while j >= 0 and lines[j].strip().startswith("//"):
            block.append(lines[j].strip()[2:])
            j -= 1
        return "\n".join(reversed(block))
    if not line.endswith("*/"):
        return ""
    block = []
    while j >= 0:
        block.append(lines[j])
        if "/*" in lines[j]:
            text = "\n".join(reversed(block))
            text = text[text.find("/*") + 2:text.rfind("*/")]
            return _BLOCK_COMMENT_STAR.sub("", text)
        j -= 1
    return ""


def _labelled_long_lived_errors(label: str, source: str,
                                task_id: str) -> list[str]:
    """Статика долгоживущего файла с меткой `AC-<n>: ` (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 6) — по тексту, без разбора
    синтаксиса: литерал каталога задач и id задачи без учёта регистра в
    любой строке, включая комментарии; «Ловит мутацию: …» в комментарии
    над каждым вызовом теста `plank_test_names`."""
    errors: list[str] = []
    lines = source.splitlines()
    task_id_lower = task_id.lower()
    for lineno, line in enumerate(lines, start=1):
        signs = []
        if SIGN_TASKS in line:
            signs.append(SIGN_TASKS)
        if task_id_lower and task_id_lower in line.lower():
            signs.append(SIGN_TASK_ID)
        errors += [f"{label}:{lineno}: признак «{sign}» — "
                   f"{_SIGN_EXPLANATIONS[sign]}" for sign in signs]
    for lineno, name in _test_calls(source):
        if not MUTATION_CLAIM.search(_comment_above(lines, lineno - 1)):
            errors.append(f"{label}:{lineno}: тест «{name}» долгоживущего "
                          f"файла без «Ловит мутацию: …» в комментарии над "
                          f"вызовом")
    return errors


def long_lived_errors_from_files(files: list[tuple[str, str]],
                                 task_id: str, *,
                                 network_addresses: bool = True,
                                 project_imports=None,
                                 rule: "PlankRule | None" = None,
                                 lint_base: dict[str, str] | None = None
                                 ) -> list[str]:
    """Ошибки долгоживущих файлов планки (требования 3, 4) по (label,
    текст) парам `test_*.py`: файлы иной группы (и без распознанной
    группы — это ошибка строки группы, не этой проверки) пропускаются.

    Заявка мутации — тем же узлом, что гейт выхода из `in_dev`
    (`test_functions_without_mutation_claim`): файл планки новый, base
    `None`, каждый метод обязан нести «Ловит мутацию: …».

    `network_addresses` — признак сетевых адресов (инвариант 35): правило
    дерева `tests/` пульта, вызывающий снимает его для чужого проекта
    (SPEC 01M4JN2EDQP8Q3WVYK0TS95ZVC, замечание ревью R1-F1).

    `project_imports` — правило импортов по проекту (SPEC
    01M5633WZ3Y3A0P4KKBZDB3KER): `None` — артель, прежний набор и текст;
    перечень (возможно пустой) — внешний проект, его имена разрешены
    сверх прежнего набора, текст признака называет перечень или подполе.

    `rule` — правило планки проекта (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
    требования 5-6): файл с меткой `AC-<n>: ` — строка группы в первом
    комментарии и статика `_labelled_long_lived_errors`; признаки импорта,
    закрытых имён и git у него не проверяются.

    Линт детерминизма (`lint_errors_from_files`, SPEC
    01M5MVSP9YW0DYA4YQ1KSG0AHF, требование 3) — до фильтра по группе:
    каждый `.py` любой группы, только при `network_addresses` (артель).
    `lint_base` — {метка: залоченный текст}; см. `lint_errors_from_files`.
    Там же и при том же условии — стиль pytest
    (`pytest_style_errors_from_files`, SPEC 01M5N9WK9SGB7KDYJP736DP6CV,
    требования 6-7)."""
    errors: list[str] = []
    foreign_explanation = _foreign_import_explanation(project_imports)
    for label, source in files:
        labelled = _is_labelled(rule, label)
        if rule is not None and not labelled and not label.endswith(".py"):
            # Не файл с меткой и не Python — отказ даёт
            # `long_lived_group_errors`, статика не проверяема.
            continue
        if network_addresses and label.endswith(".py"):
            errors += lint_errors_from_files([(label, source)],
                                             lint_base=lint_base)
            errors += pytest_style_errors_from_files([(label, source)],
                                                     lint_base=lint_base)
        group, _error = plank_file_group(source, labelled)
        if group != GROUP_LONG_LIVED:
            continue
        if labelled:
            errors += _labelled_long_lived_errors(label, source, task_id)
            if network_addresses:
                errors += network_address_errors_from_files([(label, source)])
            continue
        for lineno, sign in long_lived_sign_hits(
                source, task_id, project_imports=project_imports or ()):
            explanation = (foreign_explanation if sign == SIGN_FOREIGN_IMPORT
                           else _SIGN_EXPLANATIONS[sign])
            errors.append(f"{label}:{lineno}: признак «{sign}» — {explanation}")
        for method in test_functions_without_mutation_claim(None, source):
            errors.append(f"{label}: метод {method} долгоживущего файла без "
                          f"«Ловит мутацию: …» в докстринге («Зелёный с "
                          f"рождения» её не заменяет)")
        if network_addresses:
            errors += network_address_errors_from_files([(label, source)])
    return errors


def _method_dumps(source: str) -> dict[str, str]:
    """{«Класс::метод» или «функция»: `ast.dump` узла}; сломанный
    исходник — пустой словарь (базы у файла нет)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    return {name: ast.dump(node)
            for name, node in test_lint.top_level_functions(tree)}


def lint_errors_from_files(files: list[tuple[str, str]], *,
                           lint_base: dict[str, str] | None = None
                           ) -> list[str]:
    """Нарушения линта детерминизма (`orchestrator/test_lint.py`) по
    (label, текст) парам: «<метка>::<метод>: строка N: <нарушение>».
    Файл с синтаксической ошибкой пропускается — его называет сухой сбор.

    `lint_base` — {метка: текст залоченного состояния} (`amend-tests`,
    SPEC 01M5MVSP9YW0DYA4YQ1KSG0AHF, требование 4): метод, чей узел в
    базе под тем же «Класс::метод» совпадает по `ast.dump` (без номеров
    строк), нарушения не даёт — задачи, залоченные до правила, не получают
    отказа за старые методы. `None` — проверяются все методы. Перечень
    `_EXCEPTIONS` инварианта дерева `tests/` здесь не читается."""
    errors: list[str] = []
    for label, source in files:
        try:
            found = test_lint.findings(source, label)
        except SyntaxError:
            continue
        base = (_method_dumps(lint_base[label])
                if lint_base is not None and label in lint_base else {})
        current = _method_dumps(source) if base else {}
        for key, hits in found.items():
            qualname = key[len(label) + 2:]
            if qualname in base and base[qualname] == current.get(qualname):
                continue
            errors += [f"{key}: {hit}" for hit in hits]
    return errors


# Стиль pytest в файлах планки и долгоживущих файлах (ADR-0027 пп. 3-5;
# SPEC 01M5N9WK9SGB7KDYJP736DP6CV, требования 6-7): фикстура готовит данные
# и не утверждает, пропуск и варианты видны в сигнатуре и декораторах теста,
# стили в одном файле не смешиваются.
PYTEST_STYLE_MODULE_LABEL = "<модуль>"
_TEST_BODY_SKIP_CALLS = frozenset(("pytest.xfail", "pytest.importorskip"))
_FIXTURE_SKIP_CALLS = frozenset(("pytest.skip", "pytest.xfail",
                                 "pytest.importorskip"))
_PYTEST_ASSERTION_CALLS = ASSERTION_PYTEST_CALLS | {"pytest.fail"}
GENERATE_TESTS_HOOK = "pytest_generate_tests"
GETFIXTUREVALUE_NAME = "getfixturevalue"
STYLE_ASSERTION_IN_FIXTURE = ("утверждение в фикстуре — фикстура готовит "
                              "данные, утверждает тест (ADR-0027)")
STYLE_HIDDEN_SKIP = "скрытый пропуск — пропуск ставится меткой теста с причиной"
STYLE_HIDDEN_VARIANTS = ("скрытые варианты — варианты ставятся "
                         "`parametrize` литералами на тесте")
STYLE_GETFIXTUREVALUE = ("request.getfixturevalue( — фикстура запрашивается "
                         "параметром теста")
STYLE_FIXTURE_NAME = ("@pytest.fixture(name=…) — имя фикстуры расходится с "
                      "именем функции")
STYLE_MIXED = ("смешение стилей: тест-функции модуля и класс с тестовыми "
               "методами в одном файле — выбери один стиль (ADR-0027)")


class _StyleViolation(NamedTuple):
    """Нарушение стиля: адрес («Класс::функция» либо «<модуль>»), строка,
    текст и чем его прощает залоченная база: имена функций, чей `ast.dump`
    обязан совпасть с базой, либо `ast.dump` оператора верхнего уровня."""

    name: str
    line: int
    text: str
    functions: tuple = ()
    statement: str = ""


def _style_assertion(node: ast.AST, aliases: dict) -> bool:
    return _is_assertion(node) or (
        isinstance(node, ast.Call)
        and _pytest_name(node.func, aliases) in _PYTEST_ASSERTION_CALLS)


def _calls_outside_defs(node: ast.AST):
    """Вызовы оператора уровня модуля вне тел функций, классов и лямбд."""
    if isinstance(node, (*_FUNCTION_NODES, ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _calls_outside_defs(child)


def _indirect_marks(marks: list) -> list:
    return [mark for mark in marks if _is_parametrize(mark)
            and _decorator_keyword(mark, "indirect") is not None]


def _style_violations(tree: ast.Module) -> list:
    aliases = _pytest_aliases(tree)
    functions = dict(test_lint.top_level_functions(tree))
    tests = _collect_qualified_test_functions(tree)
    found: list = []

    def add(name, line, text, involved=None, statement=""):
        found.append(_StyleViolation(name, line, text,
                                     tuple(involved or (name,)), statement))

    def calls(node):
        return [sub for sub in ast.walk(node) if isinstance(sub, ast.Call)]

    for qualname, node in functions.items():
        owner = qualname.rpartition(TEST_NAME_SEP)[0]
        decorator = _fixture_decorator(node, aliases)
        if decorator is not None:
            if _decorator_keyword(decorator, "params") is not None:
                add(qualname, decorator.lineno,
                    f"@pytest.fixture(params=…) — {STYLE_HIDDEN_VARIANTS}")
            if _decorator_keyword(decorator, "name") is not None:
                add(qualname, decorator.lineno, STYLE_FIXTURE_NAME)
            for sub in ast.walk(node):
                if _style_assertion(sub, aliases):
                    add(qualname, sub.lineno, STYLE_ASSERTION_IN_FIXTURE)
            for call in calls(node):
                canonical = _pytest_name(call.func, aliases)
                if canonical in _FIXTURE_SKIP_CALLS:
                    add(qualname, call.lineno,
                        f"{canonical}( в фикстуре — {STYLE_HIDDEN_SKIP}")
                # Помощник первого уровня: функция модуля либо метод класса
                # фикстуры — его утверждение тоже утверждение фикстуры.
                callee = call.func
                helper = None
                if isinstance(callee, ast.Name):
                    helper = callee.id
                elif owner and isinstance(callee, ast.Attribute) and \
                        isinstance(callee.value, ast.Name) and \
                        callee.value.id == "self":
                    helper = f"{owner}{TEST_NAME_SEP}{callee.attr}"
                target = functions.get(helper)
                if target is None or target is node or \
                        _fixture_decorator(target, aliases) is not None:
                    continue
                for sub in ast.walk(target):
                    if _style_assertion(sub, aliases):
                        add(helper, sub.lineno,
                            f"утверждение в помощнике фикстуры {qualname} — "
                            f"{STYLE_ASSERTION_IN_FIXTURE}", (helper, qualname))
        if qualname in tests:
            for call in calls(node):
                canonical = _pytest_name(call.func, aliases)
                if canonical in _TEST_BODY_SKIP_CALLS:
                    add(qualname, call.lineno,
                        f"{canonical}( в теле теста — {STYLE_HIDDEN_SKIP}")
            for mark in _indirect_marks(node.decorator_list):
                add(qualname, mark.lineno,
                    f"indirect= у parametrize — {STYLE_HIDDEN_VARIANTS}")
        if node.name == GENERATE_TESTS_HOOK:
            add(qualname, node.lineno,
                f"хук {GENERATE_TESTS_HOOK} — {STYLE_HIDDEN_VARIANTS}")
        for call in calls(node):
            if isinstance(call.func, ast.Attribute) and \
                    call.func.attr == GETFIXTUREVALUE_NAME:
                add(qualname, call.lineno, STYLE_GETFIXTUREVALUE)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            marks = node.decorator_list + _pytestmark_marks(node.body)
            for mark in _indirect_marks(marks):
                add(node.name, mark.lineno,
                    f"indirect= у parametrize — {STYLE_HIDDEN_VARIANTS}")
            continue
        if isinstance(node, _FUNCTION_NODES):
            continue
        statement = ast.dump(node)
        if _is_pytestmark_assign(node):
            for mark in _indirect_marks(_pytestmark_marks([node])):
                add(PYTEST_STYLE_MODULE_LABEL, mark.lineno,
                    f"indirect= у parametrize — {STYLE_HIDDEN_VARIANTS}",
                    (), statement)
            continue
        for call in _calls_outside_defs(node):
            canonical = _pytest_name(call.func, aliases)
            if canonical in _FIXTURE_SKIP_CALLS:
                add(PYTEST_STYLE_MODULE_LABEL, call.lineno,
                    f"{canonical}( на уровне модуля вне pytestmark — "
                    f"{STYLE_HIDDEN_SKIP}", (), statement)
    return found


def _mixes_styles(tree: ast.Module) -> bool:
    """В модуле есть и тест-функция верхнего уровня, и класс с тестовыми
    методами (требование 7)."""
    tests = _collect_qualified_test_functions(tree)
    return any(TEST_NAME_SEP not in name for name in tests) and \
        any(TEST_NAME_SEP in name for name in tests)


def _class_and_function_dumps(tree: ast.Module) -> dict:
    found = {name: ast.dump(node)
             for name, node in test_lint.top_level_functions(tree)}
    found.update({node.name: ast.dump(node) for node in tree.body
                  if isinstance(node, ast.ClassDef)})
    return found


def pytest_style_errors_from_files(files: list[tuple[str, str]], *,
                                   lint_base: dict[str, str] | None = None
                                   ) -> list[str]:
    """Нарушения стиля pytest (SPEC 01M5N9WK9SGB7KDYJP736DP6CV, требования
    6-7) по (label, текст) парам: «<метка>::<функция>: строка N:
    <нарушение>», у модульной формы — «<метка>::<модуль>: …»; смешение
    стилей — «<метка>: <нарушение>». Файл с синтаксической ошибкой
    пропускается — его называет сухой сбор.

    `lint_base` — {метка: залоченный текст} (`amend-tests`), как у
    `lint_errors_from_files`: нарушение не считается, если функции, на
    которых оно стоит, в базе под тем же именем совпадают по `ast.dump`;
    модульное — если среди операторов верхнего уровня базы есть оператор с
    тем же `ast.dump`; смешение — если залоченный текст стили смешивал."""
    errors: list[str] = []
    for label, source in files:
        tree = _parse_or_none(source)
        if tree is None:
            continue
        base_tree = _parse_or_none(lint_base.get(label)) \
            if lint_base is not None else None
        base = _class_and_function_dumps(base_tree) if base_tree else {}
        base_statements = {ast.dump(node) for node in base_tree.body} \
            if base_tree else set()
        current = _class_and_function_dumps(tree)
        for violation in _style_violations(tree):
            if violation.statement:
                if violation.statement in base_statements:
                    continue
            elif all(name in base and base[name] == current.get(name)
                     for name in violation.functions):
                continue
            line = f"{label}::{violation.name}: строка {violation.line}: " \
                   f"{violation.text}"
            if line not in errors:
                errors.append(line)
        if _mixes_styles(tree) and not (base_tree and _mixes_styles(base_tree)):
            errors.append(f"{label}: {STYLE_MIXED}")
    return errors


# --------------------------------------------------------------------------
# Сетевые адреса в `tests/` (инвариант 35, docs/invariants.md; SPEC
# 01M4JN2EDQP8Q3WVYK0TS95ZVC, требование 1): одно место правила на всех
# потребителей — инвариант 35 в `tests/test_invariants.py`, выход из
# `tests_writing` (через `long_lived_errors_from_files`) и рубеж
# `in_dev -> verifying`. Реальный `git fetch` по DNS-имени резолвит его
# настоящим резолвером и виснет на таймауте при обрыве сети (инцидент 05.09,
# SPEC 01M1QHQ277PQQA894X97RVEX9Y).

NETWORK_ADDRESS_RE = re.compile(r"https?://[^\s'\"]+")
NETWORK_EXEMPT_HOSTS = ("localhost", "127.0.0.1")

# (имя файла, хост) -> обоснование: адрес — decorative/тестовый текст,
# никогда не передаётся реальному сетевому вызову, поэтому исключён
# из скана (SPEC 01M1QHQ277PQQA894X97RVEX9Y, требование 3).
NETWORK_ADDRESS_EXCEPTIONS = {
    ("test_github_adapter.py", "github.com"):
        "stdout уже замоканного `gh` (github_adapter.ci.gh подменена "
        "лямбдой в setUp самого теста) — тест не открывает соединение "
        "по этому адресу, строка лишь имитирует формат вывода "
        "`gh pr create`",
    ("test_ci_status.py", "api.github.com"):
        "текст внутри сообщения об ошибке уже замоканного `ci.gh` "
        "(`set_check_runs` подменяет ответ целиком) — адрес не "
        "аргумент реального вызова, тест не обращается к сети",
    ("test_sandbox.py", "example.invalid"):
        "статические строки-фикстуры, проверяющие саму логику "
        "распознавания DNS-адреса (`_is_local_git_address`/"
        "`_network_git_command_denial`) — никогда не передаются "
        "реальному `subprocess.run`, только сравниваются как текст",
    ("test_sandbox.py", "127.0.0.1.evil.example"):
        "та же статическая фикстура — хост, лишь НАЧИНАЮЩИЙСЯ с "
        "loopback-адреса, проверяет точность сравнения хоста в "
        "`_is_local_git_address`, тоже не передаётся `subprocess.run`",
}


def network_address_host(url: str) -> str:
    """Хост адреса `scheme://host[:port][/path]` — без порта и пути."""
    rest = url.split("://", 1)[1]
    return rest.split("/", 1)[0].split(":", 1)[0]


def network_address_hits(name: str, text: str) -> list[tuple[int, str]]:
    """(строка, адрес) каждого адреса `http(s)://<DNS-имя>` текста файла
    `tests/` с именем `name` (имя файла, не путь: так ключуются именованные
    исключения). Хост сравнивается ТОЧНО, не префиксом:
    `127.0.0.1.evil.example` — DNS-имя, лишь начинающееся с исключённого
    `127.0.0.1`, — пойман."""
    hits: list[tuple[int, str]] = []
    for match in NETWORK_ADDRESS_RE.finditer(text):
        url = match.group(0)
        host = network_address_host(url)
        if host in NETWORK_EXEMPT_HOSTS:
            continue
        if (name, host) in NETWORK_ADDRESS_EXCEPTIONS:
            continue
        hits.append((text.count("\n", 0, match.start()) + 1, url))
    return hits


def network_address_errors_from_files(files: list[tuple[str, str]]) -> list[str]:
    """Ошибки правила адресов по (label, текст) парам файлов `tests/`;
    исключения ключуются последним сегментом метки."""
    errors: list[str] = []
    for label, source in files:
        name = label.replace("\\", "/").rsplit("/", 1)[-1]
        for lineno, url in network_address_hits(name, source):
            errors.append(f"{label}:{lineno}: сетевой адрес «{url}» — в "
                          f"tests/ адреса только на "
                          f"{'/'.join(NETWORK_EXEMPT_HOSTS)} (инвариант 35)")
    return errors


def acceptance_test_files(tdir: Path, rule: "PlankRule | None" = None
                          ) -> list[tuple[str, str]]:
    """(путь относительно `tdir`, текст) файлов `acceptance_tests/**/test_*.py`
    каталога задачи `tdir` — те же файлы, что `scan_redness_markers`;
    метка — как у `scan_artifact_disk_reads`.

    `rule` — к ним тестовые файлы с меткой `AC-<n>: ` первого уровня по
    правилу планки (SPEC 01M5AA5TS90RDJ2AFXB882WTPD, требование 5)."""
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return []
    files: list[tuple[str, str]] = []
    for f in sorted(tests_dir.rglob("test_*.py")):
        try:
            files.append((str(f.relative_to(tdir)), f.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    if _by_rule(rule):
        seen = {label for label, _text in files}
        files += [(str(f.relative_to(tdir)), text) for f, text
                  in _rule_plank_files(tdir, rule, tests_only=True)
                  if is_labelled_plank_test(rule, f.name)
                  and str(f.relative_to(tdir)) not in seen]
    return files


def is_labelled_plank_test(rule: "PlankRule", name: str) -> bool:
    """Тестовый файл планки с меткой `AC-<n>: ` по правилу `rule`: `name` —
    путь от `acceptance_tests/`, только первый уровень (SPEC
    01M5GXZK2WTZ89AXQ7QY2RJD9R, требование 6). Один предикат на диск
    (`acceptance_test_files`) и на снимок ветки документов (`amend-tests
    --from-branch`), чтобы их составы не разошлись."""
    return ("/" not in name and rule.owns(name) and rule.is_test(name)
            and rule.is_labelled(name))


# --------------------------------------------------------------------------
# Долгоживущие файлы задачи в `tests/` кодовой ветки (ADR-0020, пункты 3,
# 5, 7; SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, решения Р1, Р2). Одно место
# правила имени и формата перечня на всех потребителей: чекпоинт
# test_author, выход из `tests_writing`, сверка перечня на переходах и на
# гейте мержа.

# Перечень сумм лежит в каталоге приёмочных тестов: имя подходит под
# `ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` (`.+\.txt`), и нынешний лок
# `tests_locked_sha` покрывает его без новой колонки БД (Р2).
LONG_LIVED_MANIFEST_NAME = "long_lived.sha256.txt"
_LONG_LIVED_NAME = re.compile(r"[a-z0-9_]+")
_MANIFEST_LINE = re.compile(r"([0-9a-f]{64})  (\S.*)")


# Каталог и шаблон имени долгоживущего файла по умолчанию — значения
# профиля тестов артели (`targets.yaml`, поле `test_profile`; SPEC
# 01M45FJVGQT1K0P8HDEXZX6HS7, требование 1). Гейты задачи передают
# значения профиля своего проекта явно; умолчание держат потребители вне
# гейтов тестов (чекпоинт, бриф, миссия роли).
LONG_LIVED_DIR = "tests"
LONG_LIVED_TEMPLATE = "test_<id>_<name>.py"


def long_lived_path_prefix(task_id: str, directory: str = LONG_LIVED_DIR,
                           template: str = LONG_LIVED_TEMPLATE) -> str:
    """`<каталог>/` и часть шаблона до `<name>` с подставленным `<id>` —
    у артели `tests/test_<полный id в нижнем регистре>_` (Р1): только
    полный id ULID уникален — первые 10 знаков у него метка времени, и у
    задач, заведённых в одну миллисекунду, совпадают; нижний регистр —
    форма имени ветки и допустимого имени модуля Python."""
    head = template.split("<name>", 1)[0].replace("<id>", task_id.lower())
    return f"{directory}/{head}"


# Сегмент `<dir>` шаблона: не начинается с точки — каталог выкладки
# `.artel-plank` и скрытые каталоги своими не признаются.
_LONG_LIVED_DIR_SEGMENT = r"[A-Za-z0-9_-][A-Za-z0-9_.-]*"


def is_long_lived_test_path(task_id: str, rel: str,
                            directory: str = LONG_LIVED_DIR,
                            template: str = LONG_LIVED_TEMPLATE) -> bool:
    """`rel` — `<каталог>/<шаблон>` с `<id>` задачи и непустым `<имя>` из
    `[a-z0-9_]` (Р1; у артели `tests/test_<id задачи>_<имя>.py`): файл,
    который test_author задачи вправе добавить в кодовую ветку. `<dir>/`
    шаблона — ноль или больше сегментов `_LONG_LIVED_DIR_SEGMENT` (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 3)."""
    parts = re.split(r"(<id>|<name>|<dir>/)", template)
    pattern = re.escape(f"{directory}/") + "".join(
        re.escape(task_id.lower()) if part == "<id>"
        else _LONG_LIVED_NAME.pattern if part == "<name>"
        else f"(?:{_LONG_LIVED_DIR_SEGMENT}/)*" if part == "<dir>/"
        else re.escape(part)
        for part in parts)
    return re.fullmatch(pattern, rel) is not None


def long_lived_example(task_id: str, directory: str = LONG_LIVED_DIR,
                       template: str = LONG_LIVED_TEMPLATE,
                       name: str = "<имя>") -> str:
    """Пример пути долгоживущего файла задачи для подсказок (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 3): `<id>` — id задачи в нижнем
    регистре, `<name>` — `name` (`<имя>` либо `*`), `<dir>` — `<каталог>`."""
    path = (template.replace("<id>", task_id.lower())
            .replace("<name>", name).replace("<dir>", "<каталог>"))
    return f"{directory}/{path}"


def render_long_lived_manifest(digests: dict[str, str]) -> str:
    """Текст перечня по Р2 из {путь: sha256}: строка `<sha256>␣␣<путь>\\n`
    на файл, строки по пути, без комментариев; пустой словарь — пустой
    файл. Формат `sha256sum -c` из корня рабочей копии кодовой ветки."""
    return "".join(f"{digests[path]}  {path}\n" for path in sorted(digests))


def parse_long_lived_manifest(text: str) -> tuple[dict[str, str] | None, str]:
    """({путь: sha256}, "") — перечень разобран; (None, причина) — строка
    не по формату Р2. Разбор строгий: перечень пишет только пульт, и
    строка чужого вида — порча, а не вариант записи."""
    digests: dict[str, str] = {}
    for n, line in enumerate(text.split("\n"), start=1):
        if not line:
            continue
        match = _MANIFEST_LINE.fullmatch(line)
        if match is None:
            return None, f"строка {n} перечня не по формату «<sha256>  <путь>»"
        digests[match.group(2)] = match.group(1)
    return digests, ""


def long_lived_plank_errors(files: list[tuple[str, str]], task_id: str,
                            directory: str = LONG_LIVED_DIR,
                            template: str = LONG_LIVED_TEMPLATE,
                            rule: "PlankRule | None" = None,
                            example: str | None = None) -> list[str]:
    """Долгоживущий файл в каталоге приёмочных тестов (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 4): временная оговорка задачи 1
    снята, место такого файла — каталог долгоживущих тестов кодовой ветки
    по правилу имени Р1 (у артели — `tests/`).

    `rule` — строка группы файла с меткой из первого комментария;
    `example` — пример пути вместо склейки префикса и «<имя>.py» (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 4)."""
    if example is None:
        prefix = long_lived_path_prefix(task_id, directory, template)
        example = f"{prefix}<имя>.py"
    return [f"{label}: «Группа: {GROUP_LONG_LIVED}» в каталоге приёмочных "
            f"тестов — перенеси файл в {example} кодовой ветки"
            for label, source in files
            if plank_file_group(source, _is_labelled(rule, label))[0]
            == GROUP_LONG_LIVED]


LONG_LIVED_UNCHECKABLE = ("не файл с меткой AC-<n>: и не Python — группа и "
                          "статика не проверяемы")


def long_lived_group_errors(files: list[tuple[str, str]], directory: str,
                            rule: "PlankRule | None" = None) -> list[str]:
    """Строка группы долгоживущих файлов кодовой ветки (путь, текст): у
    каждого — «Группа: долгоживущий» (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    требование 3), текст отказа называет каталог `directory`. Одно место
    на выход из `tests_writing` и `preflight`.

    `rule` — правило планки у профиля из шаблона `long_lived` (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 5): у файла с меткой строка
    группы — в первом комментарии, её ошибка — текстом разбора; файл не с
    меткой и не `.py` — отказ `LONG_LIVED_UNCHECKABLE`. `None` — прежний
    разбор Python у всех файлов."""
    errors: list[str] = []
    for path, text in files:
        labelled = _is_labelled(rule, path)
        if rule is not None and not labelled and not path.endswith(".py"):
            errors.append(f"{path}: {LONG_LIVED_UNCHECKABLE}")
            continue
        group, group_error = plank_file_group(text, labelled)
        if labelled and group_error is not None:
            errors.append(f"{path}: {group_error}")
        elif group != GROUP_LONG_LIVED and (group or group_error):
            errors.append(f"{path}: нет строки «Группа: {GROUP_LONG_LIVED}» — "
                          f"в {directory}/ кодовой ветки только долгоживущие "
                          f"файлы")
    return errors


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
REGISTRY_CELL_SPLIT = re.compile(r"(?<!\\)\|")  # черта, не экранированная `\`


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
        # Hotfix №19 (06.09): черта внутри ячейки экранируется по Markdown
        # как `\|` — режем только по НЕэкранированным чертам и снимаем
        # экранирование; иначе пример команды `a \| b` в ячейке давал
        # «8 колонок вместо 6» (канарейка 20260906T194847Z, третий случай).
        cells = [c.strip().replace("\\|", "|")
                 for c in REGISTRY_CELL_SPLIT.split(line.strip("|"))]
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
    страховка от ошибки, не рабочий канал) — и к `spec_audit`: аудитор SPEC
    эскалирует тем же разделом, что developer и ревьювер (SPEC
    01M4MQAGRWMWR0GFDM9086P3TD, требование 11).
    """
    if meta.get("type") not in ("plan", "review", "spec", "spec_audit"):
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


def spec_audit_field_errors(path: Path | str, meta: dict) -> list[str]:
    """Поля вердикта `SPEC-AUDIT.md` (SPEC 01M4MQAGRWMWR0GFDM9086P3TD,
    требование 8): каждое из `SPEC_AUDIT_FIELDS` есть и непусто, `verdict` —
    из `SPEC_AUDIT_VERDICTS`. Пустое значение — отказ так же, как
    отсутствующее поле: `signals:` без значения не говорит ни «нет», ни
    перечня, а пульт переносит его в журнал. `path` — только для текста
    ошибок (см. `schema_errors`)."""
    errors = []
    for field in SPEC_AUDIT_FIELDS:
        value = meta.get(field)
        if value is None or not str(value).strip():
            errors.append(f"{path}: поле {field} не заполнено — впиши его во "
                          f"frontmatter (templates/SPEC-AUDIT.md)")
    verdict = meta.get("verdict")
    if verdict is not None and str(verdict).strip() \
            and verdict not in SPEC_AUDIT_VERDICTS:
        errors.append(f"{path}: verdict '{verdict}' вне перечня — замени на "
                      f"одно из: {', '.join(SPEC_AUDIT_VERDICTS)}")
    return errors


# --------------------------------------------------------------------------
# Матрица последствий в QUESTIONS.md (SPEC 01M4NZ5KT0PX0RYWTSTN1XEFS5,
# требования 2-3; ADR-0022 п.4): у каждого варианта каждого вопроса четыре
# пункта, по которым Оператор принимает решение. Проверяется только форма —
# текст после метки guard не оценивает. Статус не освобождает: черновик,
# по которому задача эскалирует, читает Оператор так же, как `ready`.
QUESTIONS_SECTION = "Вопросы"
QUESTIONS_MATRIX_LABELS = ("ломается", "ослабляется", "цена", "чьё решение")
# Вопрос — строка раздела БЕЗ отступа; вариант, строка дефолта и пункт
# матрицы — строки внутри вопроса, отступ допустим.
_QUESTION_LINE = re.compile(r"^(\d+)\.\s")
_VARIANT_LINE = re.compile(r"^\s*-\s+([A-Z])\)")
# Вариант с буквой не латинского алфавита (`- А)` кириллицей) — не вариант
# и не молчание: иначе его метки ушли бы предыдущему варианту.
_FOREIGN_VARIANT_LINE = re.compile(r"^\s*-\s+([^\W\d_])\)")
_DEFAULT_LINE = re.compile(r"^\s*(?:-\s+)?дефолт:", re.I)
_MATRIX_LABEL_LINE = re.compile(
    rf"^\s*(?:-\s+)?({'|'.join(QUESTIONS_MATRIX_LABELS)}):")


def _questions_batch(body: str) -> list:
    """[(номер вопроса, [(буква, {метки})], [чужие буквы])] раздела
    «Вопросы» по порядку. Граница варианта — следующий вариант (в том числе
    с чужой буквой), строка дефолта или следующий вопрос: метка за ней
    этому варианту не засчитывается."""
    questions: list = []
    variant = None
    for line in body.splitlines():
        question = _QUESTION_LINE.match(line)
        if question:
            questions.append((question.group(1), [], []))
            variant = None
            continue
        if not questions:
            continue
        _number, variants, foreign = questions[-1]
        latin = _VARIANT_LINE.match(line)
        if latin:
            variant = (latin.group(1), set())
            variants.append(variant)
            continue
        other = _FOREIGN_VARIANT_LINE.match(line)
        if other and not other.group(1).isascii():
            foreign.append(other.group(1))
            variant = None
            continue
        if _DEFAULT_LINE.match(line):
            variant = None
            continue
        label = _MATRIX_LABEL_LINE.match(line)
        if label and variant is not None:
            variant[1].add(label.group(1))
    return questions


def questions_matrix_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Нарушения формы матрицы последствий QUESTIONS.md при любом статусе:
    в разделе нет вопроса `<N>. `; у вопроса нет варианта `- <A-Z>) `;
    внутри вопроса вариант с не латинской буквой; у варианта нет хотя бы
    одной из меток `QUESTIONS_MATRIX_LABELS`. Отказ называет номер вопроса
    и букву варианта. `path` — только для текста ошибок."""
    if (meta.get("type") or "") != "questions":
        return []
    shape = (f"форма — templates/QUESTIONS.md: вопрос `<N>. ` без отступа, "
             f"варианты строками `- A) …`, под каждым пункты "
             f"{', '.join(f'`{label}:`' for label in QUESTIONS_MATRIX_LABELS)}, "
             f"затем `- дефолт: …`")
    batch = _questions_batch(section_body(text, QUESTIONS_SECTION))
    if not batch:
        return [f"{path}: в разделе «{QUESTIONS_SECTION}» нет ни одного "
                f"вопроса `<N>. ` — {shape}"]
    errors = []
    for number, variants, foreign in batch:
        for letter in foreign:
            errors.append(f"{path}: вопрос {number}: вариант `- {letter})` "
                          f"с буквой не латинского алфавита — пиши букву "
                          f"варианта латиницей (A, B, …)")
        if not variants:
            errors.append(f"{path}: вопрос {number}: нет ни одного варианта "
                          f"`- <A-Z>) …` — {shape}")
        for letter, labels in variants:
            missing = [label for label in QUESTIONS_MATRIX_LABELS
                       if label not in labels]
            if missing:
                errors.append(
                    f"{path}: вопрос {number}, вариант {letter}: в матрице "
                    f"последствий нет пунктов "
                    f"{', '.join(f'`{label}:`' for label in missing)} — "
                    f"допиши их строками под вариантом до следующего "
                    f"варианта или строки дефолта")
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


# --------------------------------------------------------------------------
# Зависимости мержа `merge_after` (SPEC 01M44EP0D47F498TEE08MNGBYT,
# требование 1): guard проверяет только ФОРМУ поля, без доступа к БД —
# существование, состояние, target и циклы проверяет гейт SPEC
# (`orchestrator/merge_after.py`). Поле необязательное, проверка — для SPEC
# любой `schema_version`, если поле есть.

MERGE_AFTER_FIELD = "merge_after"


def merge_after_items(raw) -> list[str]:
    """Элементы значения `merge_after` в порядке записи: список через
    запятую; `None`/пустая строка — пустой список. Пустые элементы между
    запятыми отбрасываются тем же правилом, что у списка зон."""
    if raw is None:
        return []
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def merge_after_form_errors(items: list[str], own_task_id) -> list[str]:
    """Причины по форме элементов `merge_after`: элемент не в формате id
    задачи пульта (`idgen.is_task_id_form`), повтор, совпадение с id самой
    задачи. Каждая причина называет поле и элемент. Общая для guard и для
    каналов переписывания значения (`orchestrator/merge_after.py`)."""
    errors: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not idgen.is_task_id_form(item):
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» не в формате "
                          f"id задачи (полный id или его префикс)")
        elif item in seen:
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» указан "
                          f"повторно")
        elif own_task_id and item == str(own_task_id):
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» — id самой "
                          f"задачи, задача не может зависеть от себя")
        seen.add(item)
    return errors


def spec_merge_after_errors(path: Path | str, meta: dict) -> list[str]:
    """Форма поля `merge_after` SPEC (требование 1, AC-1); поля нет —
    ошибок нет. `path` — только для текста ошибок."""
    if (meta.get("type") or "") != "spec" or MERGE_AFTER_FIELD not in meta:
        return []
    items = merge_after_items(meta.get(MERGE_AFTER_FIELD))
    return [f"{path}: {e}" for e in merge_after_form_errors(items,
                                                            meta.get("task"))]


# --------------------------------------------------------------------------
# Раздел SPEC «## Меняемое поведение» (SPEC 01M45FJD46BX45VHC36S4VS9QN,
# требования 1-2): существующие тестовые методы, чьё ожидание меняется по
# требованиям SPEC, с конкретными значениями «было → стало». Форма
# проверяется здесь — и в CLI, и на переходе `spec_writing -> spec_gate`
# (`fsm.guard_refuses` зовёт `check_content`); сверку с main делает
# `approve` гейта SPEC, разбор тем же `behavior_change_items`.
BEHAVIOR_CHANGE_SECTION = "Меняемое поведение"
BEHAVIOR_CHANGE_ITEM_PREFIX = "- "
_BEHAVIOR_CHANGE_HEAD = re.compile(r"^-\s+`([^`]*)`\s*:\s*(.*)$")
_BEHAVIOR_CHANGE_TAIL = re.compile(r"^(.*?)\s*\(требование\s+([^)]*)\)\s*$")
_BEHAVIOR_CHANGE_PAIR = re.compile(r"`([^`]*)`\s*→\s*`([^`]*)`")
_REQUIREMENT_NUMBER = re.compile(r"^(\d+)\.\s+\S", re.M)


class BehaviorChange(NamedTuple):
    """Строка раздела «Меняемое поведение»: путь файла `tests/…py`,
    квалифицированное имя метода (`Класс::метод`), пары «было → стало»
    исходным текстом из обратных кавычек, номер требования и сама строка."""

    path: str
    name: str
    pairs: tuple
    requirement: int
    line: str

    @property
    def address(self) -> str:
        return f"{self.path}{TEST_NAME_SEP}{self.name}"


def parse_behavior_change_line(line: str) -> tuple:
    """(BehaviorChange | None, причина) одной строки раздела, начинающейся
    с `- `. Номер требования здесь не сверяется с разделом «Требования» —
    это делает `behavior_change_items`, у которого есть весь SPEC."""
    head = _BEHAVIOR_CHANGE_HEAD.match(line.strip())
    if head is None:
        return None, ("нет имени метода в обратных кавычках вида "
                      "`tests/<путь>.py::<Класс>::<метод>`")
    address, rest = head.group(1).strip(), head.group(2)
    path, _sep, name = address.partition(TEST_NAME_SEP)
    if not path.startswith("tests/") or not path.endswith(".py"):
        return None, f"путь {path!r} не под tests/ или не *.py"
    parts = name.split(TEST_NAME_SEP) if name else []
    if len(parts) < 2 or not all(parts):
        return None, (f"имя {address!r} без класса — нужно "
                      f"`путь::Класс::метод`")
    tail = _BEHAVIOR_CHANGE_TAIL.match(rest)
    if tail is None:
        return None, "нет ссылки «(требование N)»"
    if not tail.group(2).strip().isdigit():
        return None, f"ссылка «(требование {tail.group(2)})» без номера"
    # Пары ищутся по самим обратным кавычкам, а не делением строки по `; `:
    # литерал вправе нести точку с запятой внутри.
    text = tail.group(1).strip()
    pairs, pos = [], 0
    for pair in _BEHAVIOR_CHANGE_PAIR.finditer(text):
        gap = text[pos:pair.start()].strip()
        if gap != ("" if not pairs else ";"):
            return None, (f"текст {gap!r} вне пар `<было>` → `<стало>` "
                          f"(пары разделяются `; `)")
        old, new = pair.group(1).strip(), pair.group(2).strip()
        if not old:
            return None, "пустое «было»"
        if not new:
            return None, "пустое «стало»"
        pairs.append((old, new))
        pos = pair.end()
    if text[pos:].strip():
        return None, (f"текст {text[pos:].strip()!r} вне пар "
                      f"`<было>` → `<стало>`")
    if not pairs:
        return None, "нет ни одной пары `<было>` → `<стало>`"
    return BehaviorChange(path, name, tuple(pairs),
                          int(tail.group(2).strip()), line.strip()), ""


def behavior_change_lines(text: str) -> list[str]:
    """Строки-пункты раздела «Меняемое поведение» (начинаются с `- `);
    раздела нет, он пуст или несёт одну шаблонную заглушку `<…>` — пусто.
    Строки без `- ` — свободный текст раздела."""
    body = section_body(text, BEHAVIOR_CHANGE_SECTION)
    if not body.strip() or _is_template_placeholder(body):
        return []
    return [line.rstrip() for line in body.splitlines()
            if line.startswith(BEHAVIOR_CHANGE_ITEM_PREFIX)]


def behavior_change_items(text: str) -> tuple[list, list[str]]:
    """(пункты раздела «Меняемое поведение» SPEC `text`, нарушения формы).
    Нарушение называет строку раздела (требование 2): путь не под
    `tests/` или не `*.py`, имя без класса, пустое «было»/«стало», нет
    «(требование N)» либо пункта N нет в «Требования», повтор метода."""
    requirements = {int(n) for n in _REQUIREMENT_NUMBER.findall(
        section_body(text, "Требования"))}
    items, errors, seen = [], [], set()
    for line in behavior_change_lines(text):
        item, reason = parse_behavior_change_line(line)
        if item is not None and item.requirement not in requirements:
            item, reason = None, (f"пункта {item.requirement} нет в разделе "
                                  f"«Требования»")
        if item is not None and item.address in seen:
            item, reason = None, f"метод {item.address} назван повторно"
        if item is None:
            errors.append(f"раздел «{BEHAVIOR_CHANGE_SECTION}», строка "
                          f"«{line.strip()}»: {reason}")
            continue
        seen.add(item.address)
        items.append(item)
    return items, errors


def behavior_change_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Нарушения формы раздела «Меняемое поведение» SPEC; раздела нет —
    ошибок нет. `path` — только для текста ошибок."""
    if (meta.get("type") or "") != "spec":
        return []
    return [f"{path}: {e}" for e in behavior_change_items(text)[1]]


# --------------------------------------------------------------------------
# Раздел SPEC «## Заменяемые тесты» (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R,
# требование 1; ADR-0026 «Решение» п. 7): тесты компонента с отчётом,
# которые заменяются тестом критерия `AC-<n>`. Форма проверяется здесь — в
# CLI и на переходе `spec_writing -> spec_gate`; сверку с профилем и `main`
# делает `approve` гейта SPEC, разбор тем же `replaced_test_items`, а
# запись журнала читается обратно `parse_replaced_test_line`.
REPLACED_TESTS_SECTION = "Заменяемые тесты"
_REPLACED_HEAD = re.compile(r"^-\s+`([^`]*)`(.*)$")
_REPLACED_TAIL = re.compile(r"^\s*→\s*AC-(\d+):(.*)$")
_TEST_ID_FORM = ("<компонент>:<путь>::<полное имя>[#<n>]")


class ReplacedTest(NamedTuple):
    """Пункт раздела «Заменяемые тесты»: идентификатор теста компонента,
    номер критерия, причина и строка пункта в разобранной форме."""

    test_id: str
    criterion: int
    reason: str

    @property
    def line(self) -> str:
        return f"- `{self.test_id}` → AC-{self.criterion}: {self.reason}"


def is_test_id_form(text: str) -> bool:
    """Идентификатор теста компонента той же формы, что принимает
    `orchestrator/project_profile.parse_test_id` (guard не импортирует
    профиль: тот сам импортирует guard), — тот же разбор `partition`."""
    component, sep, rest = text.partition(":")
    path, sep2, name = rest.partition(TEST_NAME_SEP)
    return bool(sep and sep2 and component and path and name)


def parse_replaced_test_line(line: str) -> tuple:
    """(ReplacedTest | None, причина) одной строки раздела. Номер критерия
    здесь не сверяется с «Критерии приёмки» — это делает
    `replaced_test_items`, у которого есть весь SPEC."""
    stripped = line.strip()
    if not stripped.startswith(BEHAVIOR_CHANGE_ITEM_PREFIX):
        return None, "строка непустого раздела не начинается с «- »"
    head = _REPLACED_HEAD.match(stripped)
    if head is None:
        return None, ("идентификатор теста не в обратных кавычках — нужно "
                      f"`{_TEST_ID_FORM}`")
    test_id, rest = head.group(1), head.group(2)
    if not is_test_id_form(test_id):
        return None, (f"идентификатор `{test_id}` не той формы — нужно "
                      f"`{_TEST_ID_FORM}`")
    tail = _REPLACED_TAIL.match(rest)
    if tail is None:
        return None, "нет «→ AC-<n>:» после идентификатора"
    reason = tail.group(2).strip()
    if not reason:
        return None, "пустая причина после «→ AC-<n>:»"
    return ReplacedTest(test_id, int(tail.group(1)), reason), ""


def replaced_test_items(text: str) -> tuple[list, list[str]]:
    """(пункты раздела «Заменяемые тесты» SPEC `text`, нарушения формы).
    Раздела нет, он пуст или несёт одну шаблонную заглушку `<…>` — пусто
    без ошибок. Нарушение называет строку раздела: строка не с «- »,
    идентификатор не в обратных кавычках или не той формы, нет
    «→ AC-<n>:», пустая причина, критерия нет в «Критерии приёмки», повтор
    идентификатора. Пустые строки раздела пропускаются."""
    body = section_body(text, REPLACED_TESTS_SECTION)
    if not body.strip() or _is_template_placeholder(body):
        return [], []
    criteria = {int(n) for n in AC_ITEM.findall(
        section_body(text, "Критерии приёмки"))}
    items, errors, seen = [], [], set()
    for line in body.splitlines():
        if not line.strip():
            continue
        item, reason = parse_replaced_test_line(line)
        if item is not None and item.criterion not in criteria:
            item, reason = None, (f"критерия AC-{item.criterion} нет в разделе "
                                  f"«Критерии приёмки»")
        if item is not None and item.test_id in seen:
            item, reason = None, f"идентификатор {item.test_id} назван повторно"
        if item is None:
            errors.append(f"раздел «{REPLACED_TESTS_SECTION}», строка "
                          f"«{line.strip()}»: {reason}")
            continue
        seen.add(item.test_id)
        items.append(item)
    return items, errors


def replaced_tests_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Нарушения формы раздела «Заменяемые тесты» SPEC; раздела нет —
    ошибок нет. `path` — только для текста ошибок."""
    if (meta.get("type") or "") != "spec":
        return []
    return [f"{path}: {e}" for e in replaced_test_items(text)[1]]


# Сверка пар раздела «Меняемое поведение» с кодом main на `approve` гейта
# SPEC (SPEC 01M4NZ5KT0PX0RYWTSTN1XEFS5, требования 4-5, 7): разбор тот же,
# что у гейта неослабления — `_is_assertion`/`_assertion_kind` для вида,
# `literal_pair_keys` для литерала, `_assertion_records` для помощников
# первого уровня и `_literal_positions` для позиций литералов. Пара, которую
# гейт неослабления не засчитает, отказывается уже здесь, а не на
# `in_dev -> verifying`.
BEHAVIOR_NEED_LITERAL = "нужен литерал"
BEHAVIOR_NEED_SCALAR = "нужен скалярный литерал"
_CONTAINER_TYPES = (list, tuple, set, frozenset, dict)
_BEHAVIOR_FIX_HINT = ("исправь строку раздела либо вынеси смену вопросом "
                      "Оператору в батче с матрицей")


def _assertion_call_kind(text: str) -> str | None:
    """Вид утверждения, если `text` — выражение-вызов утверждения, иначе
    `None`."""
    try:
        node = ast.parse(text, mode="eval").body
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    if isinstance(node, ast.Call) and _is_assertion(node):
        return _assertion_kind(node)
    return None


def _side_key(text: str) -> tuple | None:
    """Ключ значения одной стороны пары тем же `literal_pair_keys`, что у
    гейта неослабления; `None` — сторона не читается как литерал."""
    keys = literal_pair_keys([(text, text)])
    return None if keys is None else next(iter(keys))[0]


def method_literal_keys(source, path, name: str,
                        modules: TestModules | None = None) -> set | None:
    """Ключи значений литералов на позициях констант утверждений метода
    `name` (`Класс::метод`) и его помощников первого уровня — те же
    позиции, что сравнивает гейт неослабления. Докстринги и комментарии не
    утверждения и не учитываются. `None` — файл не разбирается или метода
    в нём нет."""
    records = _assertion_records(source, path, modules)
    if records is None or name not in records:
        return None
    return {_value_key(value)
            for _key, _text, node, _origin in records[name]
            for _node, value in _literal_positions(node)}


def behavior_change_refusals(item: BehaviorChange, literals: set) -> list[str]:
    """Причины отказа `approve` по парам строки `item` раздела «Меняемое
    поведение», по одной на пару (требование 5): а) обе стороны — вызовы
    утверждений разного вида; б) сторона не читается литералом; в) сторона —
    контейнер; г) «было» нет среди `literals` (`method_literal_keys`).
    Пункты проверяются по порядку, первый сработавший — причина пары.
    Пусто — пары годны."""
    refusals = []
    for old, new in item.pairs:
        pair = f"`{old}` → `{new}`"
        kinds = (_assertion_call_kind(old), _assertion_call_kind(new))
        if all(kinds) and kinds[0] != kinds[1]:
            refusals.append(
                f"{item.address}: {pair} — {SIGN_OTHER_KIND} ({kinds[0]} → "
                f"{kinds[1]}): смена вида утверждения в «Меняемое поведение» "
                f"не входит — вынеси её вопросом Оператору в батче с "
                f"матрицей (мандат на ослабление даёт Оператор)")
            continue
        keys = {"было": _side_key(old), "стало": _side_key(new)}
        unreadable = [f"«{side}» `{text}`" for side, text in
                      (("было", old), ("стало", new)) if keys[side] is None]
        if unreadable:
            refusals.append(
                f"{item.address}: {BEHAVIOR_NEED_LITERAL} — "
                f"{', '.join(unreadable)} не читается ast.literal_eval "
                f"(слова, имя, выражение или вызов); «было» и «стало» — "
                f"скалярные литералы Python в обратных кавычках; "
                f"{_BEHAVIOR_FIX_HINT}")
            continue
        containers = [f"«{side}» `{text}`" for side, text in
                      (("было", old), ("стало", new))
                      if isinstance(ast.literal_eval(text), _CONTAINER_TYPES)]
        if containers:
            refusals.append(
                f"{item.address}: {BEHAVIOR_NEED_SCALAR} — "
                f"{', '.join(containers)} — контейнер, гейт неослабления "
                f"такую пару не засчитает; {_BEHAVIOR_FIX_HINT}")
            continue
        if keys["было"] not in literals:
            refusals.append(
                f"{item.address}: «было» `{old}` нет среди литералов "
                f"утверждений метода и его помощников первого уровня — "
                f"«было» берётся из кода метода на main; {_BEHAVIOR_FIX_HINT}")
    return refusals


# --------------------------------------------------------------------------
# Заявка на деление секцией «## Деление» SPEC (01M1SHJZCE0Y4DXAAWQ2W585A7,
# требование 1): роль не вправе звать команды пульта из worktree (T056) —
# аналитик оформляет заявку текстом SPEC, заводит подзадачи сам пульт на
# `approve`/`spec_gate` (`orchestrator/fsm.py::_approve_spec_gate`), читая
# уже провалидированный этой проверкой текст (guard уже отказал бы
# переходу `spec_writing -> spec_gate` на невалидной секции).
DIVISION_SECTION = "Деление"
DIVISION_MIN_SUBSECTIONS = 2
DIVISION_MAX_SUBSECTIONS = 4

# Заголовок подраздела `### <название>` — заякорен на начало строки, тем
# же приёмом, что и заголовки `## ` в остальном файле.
_DIVISION_SUBSECTION_SPLIT = re.compile(r"^###[ \t]+", re.M)
_DIVISION_FIELD_LINE = re.compile(r"^(Зоны|Порядок|Рамка):[ \t]*(.*)$")


def parse_division_subsections(text: str) -> list[dict]:
    """Разбор секции «## Деление» на подразделы (требование 1): список
    словарей `title`/`zones`/`order`/`budget`/`tz_text`/`body_raw` — без
    валидации обязательности полей (её несёт `division_section_errors`
    ниже). `[]` — секции нет вовсе либо её тело пусто (AC-9: SPEC без
    заявки на деление ведёт себя как раньше).

    Поля `Зоны:`/`Порядок:`/`Рамка:` ищутся построчно в теле подраздела,
    а не строго следом за заголовком (первое найденное значение поля
    побеждает) — реальный формат Оператора не обязан быть настолько же
    жёстким, насколько жёсткой была бы позиционная привязка; `tz_text` —
    остаток строк подраздела за вычетом строк-полей, `body_raw` — тот же
    остаток БЕЗ вычета строк-полей (требование 2: поля остаются текстом
    внутри `TZ.md` заведённой подзадачи, не только свободный текст).
    """
    body = section_body(text, DIVISION_SECTION)
    if not body.strip() or _is_template_placeholder(body):
        return []
    chunks = _DIVISION_SUBSECTION_SPLIT.split(body)[1:]
    subsections = []
    for chunk in chunks:
        lines = chunk.split("\n")
        title = lines[0].strip()
        rest_lines = lines[1:]
        fields: dict[str, str] = {}
        tz_lines: list[str] = []
        for line in rest_lines:
            m = _DIVISION_FIELD_LINE.match(line)
            if m and m.group(1) not in fields:
                fields[m.group(1)] = m.group(2).strip()
            else:
                tz_lines.append(line)
        subsections.append({
            "title": title,
            "zones": fields.get("Зоны"),
            "order": fields.get("Порядок"),
            "budget": fields.get("Рамка"),
            "tz_text": "\n".join(tz_lines).strip(),
            "body_raw": "\n".join(rest_lines).strip(),
        })
    return subsections


def _is_template_placeholder(body: str) -> bool:
    """Hotfix №23 (11.09): тело секции — один нетронутый заполнитель
    шаблона `<...>` (templates/SPEC.md несёт «## Деление» с примером
    подразделов внутри угловых скобок). SPEC, заведённый `cmd_new` из
    шаблона и не тронутый в этой секции, не является заявкой на деление —
    иначе guard отказывал бы каждому такому SPEC («подраздел '<название
    первой подзадачи>' не несёт поле Зоны»), как 11.09 после применения
    диффа шаблона в main."""
    stripped = body.strip()
    return stripped.startswith("<") and stripped.endswith(">")


def _division_zone_list(raw: str | None) -> list[str]:
    """Список непустых зон подраздела через запятую — тот же разбор, что
    `orchestrator/zone_lock.py::_own_paths` применяет к `zones` задачи."""
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def division_section_errors(path: Path | str, text: str, meta: dict) -> list[str]:
    """Формат секции «## Деление» (требование 1, AC-2..AC-4, AC-13, AC-14).
    `path` — только для текста ошибок (см. `schema_errors`).

    Применяется к любому SPEC независимо от `schema_version` — секция
    необязательна для всех версий (AC-9), версия-гейтинг здесь не нужен,
    в отличие от `spec_zones_errors`/`spec_budget_field_errors` выше.
    """
    if (meta.get("type") or "") != "spec":
        return []
    headers = set(re.findall(r"^##\s+(.+?)\s*$", text, re.M))
    if DIVISION_SECTION not in headers:
        return []
    body = section_body(text, DIVISION_SECTION)
    if not body.strip() or _is_template_placeholder(body):
        return []
    subsections = parse_division_subsections(text)
    if not subsections:
        # Заголовок есть, тело непустое, но ни один `### <название>` не
        # найден (R1-F3, REVIEW.md итерация 1) — намерение аналитика на
        # деление не должно тихо проходить тем же путём, что полное
        # отсутствие секции: раздел без подразделов < DIVISION_MIN_
        # SUBSECTIONS буквально по AC-2.
        return [f"{path}: секция '## {DIVISION_SECTION}' не несёт ни "
               f"одного подраздела '### <название>' — оформи заявку "
               f"подразделами (от {DIVISION_MIN_SUBSECTIONS} до "
               f"{DIVISION_MAX_SUBSECTIONS}) либо убери секцию"]

    errors: list[str] = []
    count = len(subsections)
    if count < DIVISION_MIN_SUBSECTIONS or count > DIVISION_MAX_SUBSECTIONS:
        errors.append(
            f"{path}: секция '## {DIVISION_SECTION}' несёт {count} "
            f"подразделов — допустимо от {DIVISION_MIN_SUBSECTIONS} до "
            f"{DIVISION_MAX_SUBSECTIONS}, приведи число подразделов к "
            f"этому диапазону")

    parent_zones = set(_division_zone_list(meta.get("zones")))
    for sub in subsections:
        title = sub["title"] or "(без названия)"
        if not sub["title"]:
            errors.append(
                f"{path}: подраздел секции '## {DIVISION_SECTION}' без "
                f"названия — заголовок '### <название>' пуст")
        if not sub["zones"]:
            errors.append(
                f"{path}: подраздел '{title}' секции "
                f"'## {DIVISION_SECTION}' не несёт обязательное поле "
                f"'Зоны:' — добавь список зон подзадачи")
        if not sub["order"]:
            errors.append(
                f"{path}: подраздел '{title}' секции "
                f"'## {DIVISION_SECTION}' не несёт обязательное поле "
                f"'Порядок:' — впиши 'первая, без зависимостей' либо "
                f"'после части N'")
        if not sub["tz_text"]:
            errors.append(
                f"{path}: подраздел '{title}' секции "
                f"'## {DIVISION_SECTION}' не несёт текст ТЗ подзадачи — "
                f"добавь свободный текст после полей 'Зоны:'/'Порядок:'")
        for zone in _division_zone_list(sub["zones"]):
            # Покрытие — с учётом вложенности каталог/файл (R1-F1, REVIEW.md
            # итерации 1), тем же приёмом, что `zone_lock._is_common_zone`/
            # `_covered_by`: файл внутри общей/родительской директории-зоны
            # (например `tests/test_x.py` при `COMMON_ZONES`, несущем
            # `"tests/"`) покрыт, а не только буквальное совпадение строк.
            covered = (zone_lock._is_common_zone(zone)
                      or any(zone_lock._covered_by(zone, pz)
                            for pz in parent_zones))
            if not covered:
                errors.append(
                    f"{path}: подраздел '{title}' секции "
                    f"'## {DIVISION_SECTION}' несёт зону '{zone}', не "
                    f"входящую ни в зоны родителя (frontmatter zones:), "
                    f"ни в общие зоны (config.COMMON_ZONES) — сузь зону "
                    f"подраздела либо расширь zones родителя")
    return errors


# --------------------------------------------------------------------------
# Упоминания путей и сверка с зонами (01M2XJKQNFTWHYAY4KBBQ1NVY7): одно
# определение «путь упомянут» для заведения задачи (`catalog.cmd_new` по
# ТЗ) и гейта SPEC (`fsm._approve_spec_gate`). В `check()`/`main()` НЕ
# участвует (требование 7): исторические SPEC не перепроверяются — новые
# правила guard действуют на живые задачи (модульный докстринг).

# Расширения файла-кандидата (требование 1).
PATH_MENTION_EXTENSIONS = ("py", "md", "yaml", "yml", "txt", "json", "toml")

# Сегмент пути — только ASCII: пути репозитория такие и есть, а
# кириллические «и/или», «AC-2/AC-3» и даты кандидатами не становятся.
_PATH_SEGMENT = r"[A-Za-z0-9_.-]+"
# Символ, которым может кончаться кандидат-каталог: конец слова (пробел,
# знак препинания, кавычка, скобка) или конец текста. Шаблонные хвосты
# (`tasks/<id>/`, `orchestrator/*.py`) сюда не попадают: после слэша там
# идёт `<`/`*`, и такой «каталог» кандидатом не считается — он лишь
# префикс шаблона, а не упомянутый путь.
_PATH_DIR_END = r"(?![^\s,.;:!?)\]}»\"'`])"
# Кандидат: `каталог/…/файл.расш` либо `каталог/` с завершающим слэшем.
# Слева — не середина слова/пути (URL-хвост `x.com/a/b.py` берётся
# целиком и отсеивается фильтром существования, не даёт `a/b.py`).
# Справа за расширением — не буква/цифра и не `.буква` (`a.py.bak`), но
# точка конца предложения допустима (`… в tests/test_foo.py.`).
PATH_MENTION = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"(?:" + _PATH_SEGMENT + r"/)+"
    r"(?:" + _PATH_SEGMENT + r"\.(?:" + "|".join(PATH_MENTION_EXTENSIONS)
    + r")(?![A-Za-z0-9_]|\.[A-Za-z0-9_])"
    r"|" + _PATH_DIR_END + r")")

# Подсказка отказа по неклассифицированному пути (требование 3) — одна и
# та же в `new` и на гейте SPEC (требование 6).
UNCLASSIFIED_PATH_HINT = ("назови в Зонах, в «Не входит» или в «Только "
                          "чтение/Приложением»")
# Отказ по защищённому пути в «Зоны:» ТЗ (требование 4).
PROTECTED_ZONE_REFUSAL = "защищённый путь только приложением"

# Разделы SPEC, чьи пути сверяются (требование 6), и разделы, чьё
# упоминание пути его классифицирует (требование 5) — помимо `zones:`.
SPEC_PATH_CHECKED_SECTIONS = ("Контекст", "Требования", "Критерии приёмки")
SPEC_PATH_DECLARING_SECTIONS = ("Не входит", "Материалы")


def _path_mention_candidates(text: str) -> set[str]:
    """Кандидаты-упоминания путей в `text` без фильтра существования."""
    return set(PATH_MENTION.findall(text))


def mentioned_paths(text: str, root: Path | None = None) -> set[str]:
    """Пути, упомянутые в свободном тексте и существующие в репозитории
    (требование 1): кандидаты `PATH_MENTION`, из которых остаются только
    существующие относительно `root` (по умолчанию `config.ROOT`, читается
    в момент вызова — песочницы тестов подменяют его). Кандидат-каталог
    (с завершающим `/`) обязан быть каталогом, файл — файлом; путь,
    которого в репозитории нет (файл, который задача только создаст),
    не возвращается (требование 8)."""
    base = config.ROOT if root is None else Path(root)
    found = set()
    for candidate in _path_mention_candidates(text):
        target = base / candidate
        if candidate.endswith("/"):
            if target.is_dir():
                found.add(candidate)
        elif target.is_file():
            found.add(candidate)
    return found


# Перенос строки ВНУТРИ пути: вёрстка ТЗ по ~72 символа рвёт длинный путь,
# и точка разрыва — `/`, `_` или `-` (`orchestrator/⏎schema.py`,
# `docs/reference/⏎role-home.md`). Разрыв снимается ДО разбора: иначе
# обрывок перед переносом (`orchestrator/`) становится самостоятельной
# зоной-каталогом и накрывает почти любую задачу пульта, а сам путь
# теряется целиком. Снимать ВСЕ переносы нельзя: перенос после слова
# склеил бы прозу с путём в начале следующей строки («… задачи 01M3FQ2V77⏎
# docs/stack.md»), а `PATH_MENTION` запрещает букву/цифру слева от
# кандидата — путь пропал бы. Полное обоснование правила и разбор
# остальных точек разрыва — `orchestrator/catalog.py` над его копией
# `_TZ_WRAPPED_PATH_BREAK`.
#
# Копия, а не один адрес, — по зонному замку: `catalog.py` на время этой
# задачи занят другой задачей в полёте (ТЗ, «Только чтение»), и его
# предварительная склейка снимается следующей задачей. Обе копии обязаны
# нести ОДНО выражение: разойдясь, они дадут разное число зон у одного ТЗ.
_WRAPPED_PATH_BREAK = re.compile(r"(?<=[/_-])\n[ \t]*")


def _zone_line_text(raw) -> str:
    """Строка зон, приведённая к одному виду перед разбором: список (если
    frontmatter отдал `zones:` списком) склеен запятой, перенос внутри
    пути снят. Пустой вход — пустая строка.

    Приведение идемпотентно: `sub` по уже склеенной строке ничего не
    находит — поэтому предварительная склейка в `catalog._tz_zone_items`
    остаётся безвредной, пока её не убрали."""
    if not raw:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = ", ".join(str(item) for item in raw)
    return _WRAPPED_PATH_BREAK.sub("", str(raw))


def zone_line_items(raw) -> list[str]:
    """Элементы ПЕРЕЧНЯ строки зон в порядке записи: деление по запятой —
    тем же разбором, что `zone_lock._own_paths`, — со снятой завершающей
    точкой предложения ТЗ («Зоны: …, tests/.») и без пустых элементов.

    Отдельно от `zone_items`, потому что у перечня два читателя с разными
    нуждами: классификации путей нужны ещё и кандидаты `PATH_MENTION` из
    той же строки (`zone_items`), а счёту зон для калибровки бюджета
    (`budget.count_zone_paths`) — только сами элементы, иначе пояснение в
    скобках рядом с зоной («scripts/guard.py (см. docs/stack.md)»)
    удваивало бы число зон."""
    return [p for p in (piece.strip().rstrip(".")
                        for piece in _zone_line_text(raw).split(","))
            if p]


def zone_items(raw: str | None) -> set[str]:
    """Элементы строки зон («Зоны: …» ТЗ либо frontmatter `zones:` SPEC):
    перечень через запятую (`zone_line_items`) плюс кандидаты
    `PATH_MENTION` из той же строки, чтобы пояснение в скобках рядом с
    путём («scripts/guard.py (только сборщик)») не превращало элемент в
    непуть. Существование не проверяется: зона — заявка, путь в ней может
    ещё не существовать."""
    text = _zone_line_text(raw)
    return set(zone_line_items(text)) | _path_mention_candidates(text)


def _classified(path: str, zones: set[str], declared: set[str]) -> bool:
    """`path` покрыт общей зоной, зоной задачи или объявлен в
    классифицирующем разделе — с учётом вложенности каталог/файл, тем же
    приёмом, что `division_section_errors` (`zone_lock._is_common_zone`/
    `_covered_by`)."""
    if zone_lock._is_common_zone(path):
        return True
    return any(zone_lock._covered_by(path, zone) for zone in zones | declared)


def unclassified_paths(checked_text: str, zones, declared_text: str = "",
                       root: Path | None = None) -> list[str]:
    """Отсортированный список путей `checked_text`, не классифицированных
    ни зонами `zones` (элементы, см. `zone_items`), ни общими зонами
    `config.COMMON_ZONES`, ни упоминанием в `declared_text` (разделы
    «Не входит»/«Только чтение…»/«Приложением» ТЗ, «## Не входит»/
    «## Материалы» SPEC). Пустой список — все пути классифицированы."""
    zone_set = set(zones)
    declared = _path_mention_candidates(declared_text)
    return sorted(p for p in mentioned_paths(checked_text, root)
                  if not _classified(p, zone_set, declared))


def unclassified_paths_refusal(paths) -> str:
    """Текст отказа по неклассифицированным путям (требования 3, 6) —
    перечень путей и подсказка `UNCLASSIFIED_PATH_HINT`."""
    listed = ", ".join(paths)
    return (f"пути упомянуты, но не классифицированы: {listed} — "
            f"{UNCLASSIFIED_PATH_HINT}")


def protected_zones(zones, protected=None) -> list[str]:
    """Элементы зон, попадающие под перечень защищённых путей — с учётом
    вложенности (`templates/SPEC.md` под `templates/`) и маски
    (`tests/sub/conftest.py` под `**/conftest.py`), общей формулой
    `config.is_protected_path` (SPEC 01M3MVXZXF25KYY2P213E0M39X, требования
    5-6: против прежнего `zone_lock._covered_by` расходится только на
    «записи-файле плюс суффикс» и только в сторону «защищён»).

    `protected` — перечень проекта задачи (SPEC 01M45FK56DWMNBRKA1VWM12H19,
    требование 2); `None` — перечень артели `config.PROTECTED_PATHS`."""
    return sorted(z for z in set(zones)
                  if config.is_protected_path(z, protected))


def spec_unclassified_paths(text: str, meta: dict,
                            root: Path | None = None) -> list[str]:
    """Неклассифицированные пути SPEC (требования 5-6): проверяются
    разделы `SPEC_PATH_CHECKED_SECTIONS`, классифицируют frontmatter
    `zones:` (`meta`, с вложенностью и общими зонами) и разделы
    `SPEC_PATH_DECLARING_SECTIONS`.

    Зовётся гейтом `orchestrator/fsm.py::_approve_spec_gate` и вызовом
    `main()` по файлам (`spec_path_errors`, SPEC
    01M42NBCADGSGTCBZB8NKBVDVH, требование 4) — тот прогон, которым
    analyst проверяет SPEC перед сдачей. В `_content_errors`/`check()` и
    `main() --all` не входит (требование 7), исторические SPEC с путями вне
    зон остаются валидными для CI."""
    checked = "\n".join(section_body(text, name)
                        for name in SPEC_PATH_CHECKED_SECTIONS)
    declared = "\n".join(section_body(text, name)
                         for name in SPEC_PATH_DECLARING_SECTIONS)
    return unclassified_paths(checked, zone_items(meta.get("zones")),
                              declared, root)


def spec_path_errors(path: Path) -> list[str]:
    """Находка о неклассифицированных путях SPEC-файла `path` тем же узлом
    и текстом, что отказ `approve` на `spec_gate` (SPEC
    01M42NBCADGSGTCBZB8NKBVDVH, требование 4): без неё guard говорил «ок»,
    а approve отказывал — лишний круг reject + перезапуск analyst. Не SPEC
    или нечитаемый файл — пусто: это уже нарушение `check()`."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    meta = yamlmini.frontmatter(text)
    if meta is None or meta.get("type") != "spec":
        return []
    unclassified = spec_unclassified_paths(text, meta)
    if not unclassified:
        return []
    return [f"{path}: {unclassified_paths_refusal(unclassified)}"]


def plan_appendix_errors(path: Path) -> list[str]:
    """Ошибки разбора разделов «## Приложение» PLAN-файла `path` по
    перечню артели `config.PROTECTED_PATHS` (SPEC
    01M45FK56DWMNBRKA1VWM12H19, требование 2, AC-7) — тем же узлом
    `plan_appendices`, что гейт применимости на выходе `in_dev`: без
    этой находки guard говорил «ок» PLAN'у, чьё приложение гейт отвергнет.
    Перечня проекта самостоятельный запуск не знает. Как
    `spec_path_errors`, только при запуске по файлам: исторические PLAN
    обхода `--all` не перепроверяются. Не PLAN или нечитаемый файл —
    пусто: это уже нарушение `check()`."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    meta = yamlmini.frontmatter(text)
    if meta is None or meta.get("type") != "plan":
        return []
    _appendices, errors = plan_appendices(text)
    return [f"{path}: {error}" for error in errors]


def _content_errors(label: str, text: str) -> list[str]:
    """Ядро `check` — структурная проверка уже прочитанного текста, без
    чтения файла: `label` — путь или его подобие, только для текста
    ошибок (не обязательно существующий `Path`).

    Артефакт-условие перехода FSM может читаться и с диска, и с ВЕТКИ
    задачи при чужом чекауте рабочей копии (SPEC T031, `orchestrator/
    fsm.py`, `guard_refuses`) — сама структурная проверка не должна
    раздваиваться по источнику текста.

    Полная проверка независимо от `status`: черновик проверяется теми же
    правилами содержания, что и «сданный» артефакт.
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
        errors.extend(spec_merge_after_errors(label, meta))
        errors.extend(division_section_errors(label, text, meta))
        errors.extend(behavior_change_errors(label, text, meta))
        errors.extend(replaced_tests_errors(label, text, meta))

    if atype in ("spec", "plan"):
        errors.extend(role_budget_cap_errors(label, meta))

    if atype == "review":
        errors.extend(review_evidence_errors(label, text, meta))
        errors.extend(registry_errors(label, text, meta))

    if atype == "spec_audit":
        errors.extend(spec_audit_field_errors(label, meta))

    if atype == "questions" and QUESTIONS_SECTION in headers:
        errors.extend(questions_matrix_errors(label, text, meta))

    errors.extend(escalation_status_errors(label, text, meta))

    return errors


def check_content(label: str, text: str) -> list[str]:
    """Структурная проверка уже прочитанного текста (см. `_content_errors`).

    Мягкого режима для черновиков нет (ADR-0021 п.4, SPEC
    01M41VTQJ9DSX64NFMFAF9W53B): документы задачи проверяют гейты пульта на
    переходах той же полной проверкой, CI на пуше документов отменён.
    """
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


def main() -> int:
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return 1

    extraneous_errors: list[str] = []
    sandbox_reuse_warnings: list[str] = []
    if args == ["--all"]:
        files = sorted(Path("tasks").rglob("*.md"))
        # Посторонние файлы `acceptance_tests/` (SPEC
        # 01M1SAA01YRRTWAVADT2F81RRQ, требование 2) и посторонние `.md`
        # первого уровня `tasks/<id>/` (SPEC 01M1TNN4TMWAQSQ9Y1PW37J5H0,
        # требование 1) — исключаются из обычного обхода `*.md` ДО
        # `check` (иначе, например, инцидентный
        # `_head_map.md` попал бы туда и получил ошибку разбора
        # frontmatter вместо именованной причины ниже).
        extraneous = scan_extraneous_acceptance_files(Path("tasks"))
        task_root_extraneous = scan_extraneous_task_root_files(Path("tasks"))
        extraneous_set = set(extraneous) | set(task_root_extraneous)
        files = [f for f in files
                 if f not in extraneous_set and not is_task_passport(f)
                 and not is_step_note(f)]
        extraneous_errors = (
            [f"{f}: {EXTRANEOUS_ACCEPTANCE_FILE_REASON}" for f in extraneous]
            + [f"{f}: {EXTRANEOUS_TASK_ROOT_FILE_REASON}"
              for f in task_root_extraneous])
        # Копия лёгкой песочницы переходов (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J,
        # требование 3, AC-8) — предупреждение, не ошибка, собирается по
        # всем каталогам задач сразу, тем же приёмом, что посторонние
        # файлы выше. Маркер AC-n с отступом
        # (01M28NX43ERJGHCJN29HVKMCC3) — по тому же обходу, но ошибка, не
        # предупреждение: `--all` обязан красить дерево ПОСЛЕ
        # `amend-tests`, коммитящего правку планки плотницки мимо
        # `tests_writing -> in_dev` — единственная проверка индента,
        # которую видит именно этот путь. Задача, уже закрытая ДО
        # появления этого правила (несёт `docs/retro/<id>.md`), не
        # сканируется — тот же принцип, что `scan_extraneous_acceptance_
        # files`/`_closed_before_split_assessment` выше (модульный
        # докстринг: «новые правила guard действуют на живые задачи»);
        # без исключения найдено эмпирически: закрытая
        # 01M1THKWFXFYNW28HDJGYHQWH6 несёт в acceptance_tests/ ровно тот
        # исторический индентированный маркер, из-за которого эта задача
        # заведена, и красила бы `--all` на main для любой ветки.
        indented_marker_errors: list[str] = []
        for task_dir in sorted(Path("tasks").iterdir()):
            if task_dir.is_dir():
                sandbox_reuse_warnings.extend(
                    sandbox_reuse_check(task_dir)["warnings"])
                if not (RETRO_DIR / f"{task_dir.name}.md").exists():
                    indented_marker_errors.extend(
                        scan_indented_ac_markers(task_dir))
        extraneous_errors = extraneous_errors + indented_marker_errors
    else:
        files = [Path(a) for a in args]

    all_errors: list[str] = list(extraneous_errors)
    for f in files:
        if not f.exists():
            all_errors.append(f"{f}: файл не найден")
            continue
        if is_task_passport(f):
            print(f"{f}: {PASSPORT_SKIP_NOTE}")
            continue
        if is_step_note(f):
            print(f"{f}: {STEP_NOTE_SKIP_NOTE}")
            continue
        all_errors.extend(check(f))
        if args != ["--all"]:
            all_errors.extend(spec_path_errors(f))
            all_errors.extend(plan_appendix_errors(f))

    if sandbox_reuse_warnings:
        print("GUARD: предупреждения (не блокируют переход гейта):")
        for w in sandbox_reuse_warnings:
            print(f"  - {w}")

    if all_errors:
        print("GUARD: нарушения структуры артефактов:")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print(f"GUARD: ок ({len(files)} файлов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
