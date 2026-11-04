"""Файл решения Оператора на гейте SPEC: разбор формы, заглушки шаблона, ссылки на прежние решения, мандат тестов (SPEC 01M6KB0SJHDA4D4GNEM7PGZ40P).

`reject <id> --decision <файл>` на `spec_gate` принимает решение только в
форме шаблона: раздел «## Решения», подразделы «### Решение <n>» с шестью
полями сверки следствий. Прецедент 04.11 (01M6JJ4J4NBV): около половины из
десяти кругов SPEC вызвано решениями Оператора, поданными свободным текстом
без сверки — с ложным утверждением о git, невыполнимым в зонах условием,
противоречием двух решений.

Модуль не читает файлов: текст файла решения и тексты ANSWER-n передаёт
вызывающий код (`fsm._cmd_reject`), а форма полей и заглушки шаблона зашиты
здесь (требование 4) — разбор не зависит от того, лежит ли файл шаблона в
каталоге пульта и что в нём написано. Пульт проверяет только форму,
полноту, номера и наличие мандата, не истинность решения.
"""
import re

from .advance_gates import mandate

HEADER = "# Решение Оператора на гейте SPEC"
SECTION = "## Решения"
SUBSECTION = "### Решение"

FIELD_TEXT = "Текст"
FIELD_CLAIMS = "Утверждения о коде и поведении"
FIELD_CHECK = "Чем проверяется"
FIELD_TESTS = "Существующие тесты"
FIELD_PRIOR = "Прежние решения"
FIELD_ZONES = "Зоны"
FIELDS = (FIELD_TEXT, FIELD_CLAIMS, FIELD_CHECK, FIELD_TESTS, FIELD_PRIOR,
          FIELD_ZONES)

# Заглушки — дословно текст каждого поля шаблона после «<Поле>: » (внешняя
# пара «<…>» со всем вложенным, требование 3). Вложенные фрагменты вроде
# «<строка мандата>» заглушкой сами по себе не считаются.
STUBS = {
    FIELD_TEXT: "<что решено — одной-тремя фразами>",
    FIELD_CLAIMS: ("<`файл:строка`; или «опыт: <что сделано и что увидено>»; "
                   "или «нет»>"),
    FIELD_CHECK: ("<критерий AC-n и тест; против чего — «временный дублёр» "
                  "или «не меняет файлов»>"),
    FIELD_TESTS: ("<тесты, вызывающие изменяемые функции, с решением "
                  "«не ломаются»; или «мандат: <строка мандата>»; или «нет»>"),
    FIELD_PRIOR: ("<номера k.n, с которыми сверено, и «противоречий нет»; "
                  "или «первое решение»>"),
    FIELD_ZONES: "<«выполнимо в зонах SPEC» или пути для расширения>",
}

NONE_VALUE = "нет"
EXPERIENCE = "опыт:"
CHECK_MARKS = ("временный дублёр", "не меняет файлов")
NOT_BROKEN = "не ломаются"
MANDATE = "мандат:"
NO_CONTRADICTIONS = "противоречий нет"
FIRST_DECISION = "первое решение"
IN_ZONES = "выполнимо в зонах SPEC"
ONLY_TESTS = "на spec_gate — только мандат тестов"

# Маркеры мандата тестов — тот же перебор, что у `answer` на `spec_gate`
# (`answer._spec_gate_answer_text`).
TEST_MARKERS = (mandate.TEST_WEAKENING_MANDATE_MARKER,
                mandate.TEST_ID_MANDATE_MARKER)

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_AC_RE = re.compile(r"(?<![\w-])AC-\d+")
# `файл:строка` после снятия обрамления токена: путь без пробелов и
# двоеточий, номер строки, необязательный диапазон.
_FILE_LINE_RE = re.compile(r"(?P<path>[^\s:]+):\d+(?:[–-]\d+)?")
# Расширение пути — точка, за которой идёт буква («fsm.py»), не дата «04.11».
_EXTENSION_RE = re.compile(r"\.[^\W\d_]")
_REF_RE = re.compile(r"№(\d+(?:\.\d+)?)")
# Обрамление токена: обратные кавычки и кавычки вокруг, знак препинания
# сразу после (требование 2: «`fsm.py:1863`», «fsm.py:1863,»).
_LEAD = "`«\"'("
_TRAIL = "`»\"'),.;:!?"


class DecisionError(Exception):
    """Файл решения не по форме; текст называет решение и поле."""


def starts_with_header(text: str) -> bool:
    """Единое правило требований 2, 5 и 9: первая непустая строка текста
    после снятия пробелов вокруг — заголовок файла решения."""
    for line in text.splitlines():
        if line.strip():
            return line.strip() == HEADER
    return False


def _tokens(value: str) -> list[str]:
    """Токены значения без пробелов, обрамления и знака препинания после."""
    return [token.lstrip(_LEAD).rstrip(_TRAIL) for token in value.split()]


def _has_file_line(value: str) -> bool:
    for token in value.split():
        match = _FILE_LINE_RE.fullmatch(token.lstrip(_LEAD).rstrip(_TRAIL))
        if match and ("/" in match["path"]
                      or _EXTENSION_RE.search(match["path"])):
            return True
    return False


def _paths(value: str) -> list[str]:
    return [token for token in _tokens(value) if "/" in token]


def _form_problem(field: str, value: str) -> str | None:
    """Почему значение поля не по форме требования 2; `None` — по форме.
    «Прежние решения» сверяется отдельно (`prior_refusal`): ей нужны номера
    прежних решений задачи."""
    if field == FIELD_CLAIMS:
        if (value.strip() == NONE_VALUE or EXPERIENCE in value
                or _has_file_line(value)):
            return None
        return (f"нужно `файл:строка`, «{EXPERIENCE} <что сделано и что "
                f"увидено>» или «{NONE_VALUE}»")
    if field == FIELD_CHECK:
        if _AC_RE.search(value) and any(mark in value for mark in CHECK_MARKS):
            return None
        return (f"нужны критерий AC-<n> и «{CHECK_MARKS[0]}» либо "
                f"«{CHECK_MARKS[1]}»")
    if field == FIELD_TESTS:
        if value.strip() == NONE_VALUE or MANDATE in value:
            return None
        if NOT_BROKEN in value and any(p.startswith("tests/")
                                       for p in _paths(value)):
            return None
        return (f"нужен перечень путей tests/… с «{NOT_BROKEN}», "
                f"«{MANDATE} <строка мандата>» или «{NONE_VALUE}»")
    if field == FIELD_ZONES:
        if IN_ZONES in value or _paths(value):
            return None
        return f"нужно «{IN_ZONES}» или перечень путей"
    return None


def _field_label(line: str) -> tuple[str, str] | None:
    """(поле, остаток строки) — строка начинается меткой поля; иначе `None`.
    Метка в середине строки — часть значения, не метка (требование 2)."""
    stripped = line.lstrip()
    for field in FIELDS:
        if stripped.startswith(f"{field}:"):
            return field, stripped[len(field) + 1:]
    return None


def _subsection_number(line: str) -> str | None:
    stripped = line.strip()
    if stripped == SUBSECTION or stripped.startswith(SUBSECTION + " "):
        return stripped[len(SUBSECTION):].strip()
    return None


def parse(text: str) -> list[dict]:
    """Решения файла по порядку: `{"number": n, "fields": {поле: значение}}`.

    Проверки формы — требования 2 и 3: заголовок, раздел, номера
    подразделов подряд с 1, каждое из шести полей ровно один раз, непустое,
    без заглушки шаблона и по форме. Отказ — `DecisionError` с именем
    решения и поля; порядок проверок поля — заглушка раньше формы (и
    раньше мандата, который сверяет `mandate_refusal`)."""
    if not starts_with_header(text):
        raise DecisionError(f"первая непустая строка файла — не заголовок "
                            f"«{HEADER}»")
    lines = _COMMENT_RE.sub("", text).splitlines()
    try:
        start = next(i for i, line in enumerate(lines)
                     if line.strip() == SECTION)
    except StopIteration:
        raise DecisionError(f"нет раздела «{SECTION}»") from None
    blocks: list[tuple[str, list[str]]] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        number = _subsection_number(line)
        if number is not None:
            blocks.append((number, []))
        elif blocks:
            blocks[-1][1].append(line)
    if not blocks:
        raise DecisionError(f"в разделе «{SECTION}» нет подразделов "
                            f"«{SUBSECTION} <n>»")
    for i, (number, _body) in enumerate(blocks, 1):
        if not number.isdigit():
            raise DecisionError(f"номер подраздела «{SUBSECTION} {number}» — "
                                f"не целое")
        if int(number) != i or number != str(i):
            raise DecisionError(f"номер подраздела «{SUBSECTION} {number}» "
                                f"не по порядку: номера идут подряд с 1, "
                                f"здесь ожидался {i}")
    return [{"number": int(number), "fields": _fields(int(number), body)}
            for number, body in blocks]


def _fields(number: int, body: list[str]) -> dict:
    name = f"Решение {number}"
    fields: dict[str, list[str]] = {}
    current = None
    for line in body:
        label = _field_label(line)
        if label is not None:
            current, rest = label
            if current in fields:
                raise DecisionError(f"{name}, поле «{current}»: поле "
                                    f"повторено")
            fields[current] = [rest]
        elif current is not None:
            fields[current].append(line)
    values = {}
    for field in FIELDS:
        if field not in fields:
            raise DecisionError(f"{name}, поле «{field}»: поля нет")
        value = "\n".join(fields[field]).strip()
        if not value:
            raise DecisionError(f"{name}, поле «{field}»: поле пусто")
        if STUBS[field] in value:
            raise DecisionError(f"{name}, поле «{field}»: оставлена заглушка "
                                f"шаблона")
        problem = _form_problem(field, value)
        if problem is not None:
            raise DecisionError(f"{name}, поле «{field}» не по форме: "
                                f"{problem}")
        values[field] = value
    return values


def prior_refusal(value: str, numbers: list[str]) -> str | None:
    """Почему поле «Прежние решения» не сверено с прежними решениями задачи
    `numbers` («k» / «k.n», требование 6); `None` — сверено.

    Ссылка — только токен «№k» или «№k.n»; знак препинания после — не
    часть номера, прочие числа (даты, AC-3, id задачи) ссылками не
    являются. Номер с ведущим нулём ни с одним номером не совпадёт и
    считается ссылкой на несуществующий номер."""
    refs = _REF_RE.findall(value)
    unknown = [ref for ref in refs if ref not in numbers]
    if unknown:
        return ("ссылка на несуществующий номер: "
                + ", ".join(f"№{ref}" for ref in unknown))
    if not numbers:
        if FIRST_DECISION not in value:
            return f"прежних возвратов нет — нужно «{FIRST_DECISION}»"
        return None
    if FIRST_DECISION in value:
        return (f"«{FIRST_DECISION}» при прежних возвратах — сверь с "
                f"номерами прежних решений")
    missing = [number for number in numbers if number not in refs]
    if missing:
        return ("нет ссылки на прежние решения: "
                + ", ".join(f"№{number}" for number in missing))
    if NO_CONTRADICTIONS not in value:
        return f"нет «{NO_CONTRADICTIONS}»"
    return None


def mandate_lines(value: str) -> list[str]:
    """Строки мандата поля «Существующие тесты»: остаток каждой физической
    строки после «мандат:» целиком (требование 7) — текст после строки
    мандата в той же строке входит в неё."""
    lines = []
    for line in value.splitlines():
        at = line.find(MANDATE)
        if at != -1:
            lines.append(line[at + len(MANDATE):].strip())
    return lines


def mandate_refusal(value: str, answer_texts) -> str | None:
    """Почему мандат поля «Существующие тесты» не подан `answer`; `None` —
    каждый элемент каждой строки «мандат: …» есть среди элементов строк
    того же маркера в ANSWER-n задачи (`answer_texts` — их тексты; ленивый
    вызов — тексты читаются, только если строка мандата есть).

    Элементы обеих сторон — `mandate.line_elements`: у маркера по
    идентификатору — без деления по запятым (`mandate.id_elements`)."""
    lines = mandate_lines(value)
    if not lines:
        return None
    answered: dict[str, set[str]] = {}
    for line in lines:
        marker = next((m for m in TEST_MARKERS
                       if mandate.line_elements(line, m) is not None), None)
        if marker is None:
            return f"{ONLY_TESTS} — строка «{line}»"
        items = mandate.line_elements(line, marker)
        if not items:
            return f"строка мандата «{line}» без элементов"
        if not answered:
            texts = answer_texts()
            if texts is None:
                return "ANSWER-n задачи не прочитаны — мандат не сверен"
            for marker_ in TEST_MARKERS:
                answered[marker_] = {
                    item for text in texts for answer_line in text.splitlines()
                    for item in (mandate.line_elements(answer_line, marker_)
                                 or [])}
        missing = [item for item in items if item not in answered[marker]]
        if missing:
            return ("элемент мандата не подан answer: "
                    + ", ".join(f"«{item}»" for item in missing)
                    + f" (маркер «{marker}»)")
    return None


def numbered(reason: str) -> list[tuple[str, str]] | None:
    """Решения записи возврата `reason` (текст без префикса журнала) для
    нумерации «k.n»: [(n, текст поля «Текст»)] — запись, поданная файлом:
    начинается заголовком и проходит разбор формы (требования 2, 3; ссылки
    и мандат здесь не перепроверяются). `None` — прочий возврат, номер «k»."""
    if not starts_with_header(reason):
        return None
    try:
        decisions = parse(reason)
    except DecisionError:
        return None
    return [(str(d["number"]), d["fields"][FIELD_TEXT]) for d in decisions]
