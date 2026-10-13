"""Карточки знаний: формат файла, проверка формы, чтение по видам, сверка места.

Знание, которого нет в коде (правило, причина, чем гейт его ловит,
инциденты), хранится карточками (SPEC 01M4S0JVB85W9TY1ESGNBH97FP, К-4а;
ADR-0003 пп. 3а, 3е, 3з). Два вида: системные — файл
`config.KNOWLEDGE_CARD_SYSTEM_REL` репозитория пульта (защищённый путь),
выдаются задачам всех проектов; проектные — файл поля `knowledge` записи
проекта в `targets.yaml`, выдаются только задачам этого проекта.

Образец формы (каркас для Оператора):

cards:
  merge-lock-order:
    where: [orchestrator/merge_lock.py, orchestrator/fsm_merge_gate.py::merge_gate, orchestrator/advance_gates/*.py]
    rule: "Лок мержа берётся до чтения головы main: иначе гонка двух approve"
    why: инцидент двух одновременных мержей — второй перетёр первый
    check: "tests/test_invariants.py::MergeOnlyFromMergeGateTest"
    example: "with merge_lock.held(conn): head = gitcmd.rev_parse('origin/main')"
    incidents: [01M290PS4Z, T043]

Ключ карточки — её тема, `[a-z0-9][a-z0-9-]{0,47}`. `where` — непустой
список масок пути (`*` — внутри сегмента, `**` — любое число сегментов) и
элементов `<путь>::<символ>` (символ — имена через точку). `rule`, `why` —
обязательные непустые строки; `check` (пусто — «гейтом не ловится»),
`example` — необязательные строки; `incidents` — необязательный список.
Идентификаторы инцидентов — только с буквой: число в потоковом списке
`yamlmini` читает числом, а кавычки в потоковом списке не разбираются.
Двойная кавычка внутри значения не допускается: `yamlmini` не снимает
экранирование, и значение молча разошлось бы с написанным.

Формат — подмножество YAML `yamlmini.mapping`. Повтор ключа карточки или
поля `yamlmini` молча затирает последним значением, поэтому повторы (и
отступы, на которых проход их не увидел бы) ищет отдельный построчный
проход `_line_pass`.

Новый код не вызывается ни одной командой роли, гейтом или брифом: в
этой части его зовёт только `doc-commit` (`notes.py`) — проверка формы
файла `knowledge/<имя>.yaml` до коммита.
"""
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from . import config, gitcmd, repo_context, targets, yamlmini

SAMPLE = """\
cards:
  merge-lock-order:
    where: [orchestrator/merge_lock.py, orchestrator/fsm_merge_gate.py::merge_gate, orchestrator/advance_gates/*.py]
    rule: "Лок мержа берётся до чтения головы main: иначе гонка двух approve"
    why: инцидент двух одновременных мержей — второй перетёр первый
    check: "tests/test_invariants.py::MergeOnlyFromMergeGateTest"
    example: "with merge_lock.held(conn): head = gitcmd.rev_parse('origin/main')"
    incidents: [01M290PS4Z, T043]
"""

SYSTEM = "system"
PROJECT = "project"

# Закрытый перечень кодов причины отказа (требование 7): «неизвестный
# раздел», «отступ» и прочие случаи формы — подробности кода FIELD_FORM.
GIT_NO_ANSWER = "git не ответил"
FILE_UNREADABLE = "файл не прочитан"
FILE_UNPARSED = "файл не разобран"
KEY_FORM = "ключ не по форме"
FIELD_FORM = "поле не по форме"
DUPLICATE = "повтор"
SIZE_LIMIT = "предел размера"
COUNT_LIMIT = "предел числа карточек"
REFUSAL_CODES = (GIT_NO_ANSWER, FILE_UNREADABLE, FILE_UNPARSED, KEY_FORM,
                 FIELD_FORM, DUPLICATE, SIZE_LIMIT, COUNT_LIMIT)

CARDS = "cards"
NOT_SET_UP = "not_set_up"
REFUSED = "refused"

SECTION = "cards"
KEY_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_PROJECT_FIELD_RE = re.compile(
    r"\.artel/projects/(?P<project>[^/\\]+)/knowledge/(?P<name>[^/\\]+)")

REQUIRED_TEXT = ("rule", "why")
OPTIONAL_TEXT = ("check", "example")
FIELDS = ("where",) + REQUIRED_TEXT + OPTIONAL_TEXT + ("incidents",)

CARD_INDENT = 2
FIELD_INDENT = 4

QUERY_FORM = "запрос формы <путь>, <путь>::<символ> или ::<символ>"


@dataclass(frozen=True)
class Card:
    kind: str
    key: str
    where: tuple[str, ...]
    rule: str
    why: str
    check: str
    example: str
    incidents: tuple[str, ...]


@dataclass(frozen=True)
class Refusal:
    code: str
    detail: str
    file: str
    key: str | None = None
    field: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class KindRead:
    kind: str
    outcome: str
    cards: tuple[Card, ...] = ()
    file: str | None = None
    sha256: str | None = None
    refusal: Refusal | None = None


@dataclass(frozen=True)
class QueryRefusal:
    detail: str


def refusal_text(refusal: Refusal) -> str:
    """Отказ одной строкой: файл, ключ, поле, строка, код и подробность —
    для вывода команды, где поля записи не видны по отдельности."""
    place = [refusal.file]
    if refusal.key is not None:
        place.append(f"карточка {refusal.key}")
    if refusal.field is not None:
        place.append(f"поле {refusal.field}")
    if refusal.line is not None:
        place.append(f"строка {refusal.line}")
    return f"{', '.join(place)}: {refusal.code} — {refusal.detail}"


def is_card_file(rel: str) -> bool:
    """Путь ровно `knowledge/<имя>.yaml` — файл карточек репозитория пульта
    (имя — та же форма, что у поля `knowledge` в `targets.check`)."""
    head, sep, name = rel.partition("/")
    return (head == "knowledge" and bool(sep)
            and bool(targets.KNOWLEDGE_FILE_NAME.fullmatch(name)))


# --- проверка формы ---

def _line_key(content: str) -> str:
    """Ключ строки так, как его отдаёт `yamlmini`: текст до первого `:` с
    обрезкой пробелов по краям (`a :` и `a:` — один ключ)."""
    return content.partition(":")[0].strip()


def _line_pass(text: str, file: str) -> tuple[Refusal | None, dict, dict]:
    """Построчный проход: неизвестный раздел, отступ, повторы (требование 3).

    Возвращает отказ (или `None`) и номера строк: ключ карточки → строка,
    `(ключ, поле)` → строка — их называют отказы проверки значений."""
    card_lines: dict = {}
    field_lines: dict = {}
    seen_section = False
    current = None
    for number, raw in enumerate(text.splitlines(), 1):
        content = raw.strip()
        if not content or content.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key = _line_key(content)
        if indent == 0:
            if key == SECTION and not seen_section:
                seen_section = True
                continue
            what = f"повтор «{SECTION}:»" if key == SECTION else f"«{key}»"
            return Refusal(FIELD_FORM, f"неизвестный раздел {what}: верхний "
                           f"уровень — ровно один раздел «{SECTION}»", file,
                           line=number), card_lines, field_lines
        if not seen_section or indent not in (CARD_INDENT, FIELD_INDENT):
            return Refusal(FIELD_FORM, f"отступ {indent}: ключ карточки — "
                           f"отступ {CARD_INDENT}, поле — {FIELD_INDENT}",
                           file, line=number), card_lines, field_lines
        if indent == CARD_INDENT:
            if key in card_lines:
                return Refusal(DUPLICATE, f"повтор ключа карточки «{key}» "
                               f"(строки {card_lines[key]} и {number})", file,
                               key=key, line=number), card_lines, field_lines
            card_lines[key] = number
            current = key
            continue
        if current is None:
            return Refusal(FIELD_FORM, f"отступ {indent}: поле вне карточки",
                           file, line=number), card_lines, field_lines
        if (current, key) in field_lines:
            return Refusal(DUPLICATE, f"повтор поля «{key}» карточки "
                           f"«{current}» (строки "
                           f"{field_lines[(current, key)]} и {number})", file,
                           key=current, field=key,
                           line=number), card_lines, field_lines
        field_lines[(current, key)] = number
    return None, card_lines, field_lines


def _not_string(value: object) -> str:
    if isinstance(value, bool):
        return "значение не строка: логическое значение"
    if isinstance(value, (int, float)):
        return "значение не строка: число"
    return f"значение не строка: {type(value).__name__}"


def _text_error(value: object, required: bool) -> str | None:
    if value is None:
        return "пусто" if required else None
    if not isinstance(value, str):
        return _not_string(value)
    if required and not value.strip():
        return "пусто"
    if '"' in value:
        return "двойная кавычка внутри значения"
    return None


def _path_error(path: str) -> str | None:
    if path.startswith("/"):
        return "путь абсолютный"
    if path.startswith("./"):
        return "путь с префиксом ./"
    if ".." in path.split("/"):
        return "путь с .."
    return None


def _where_item_error(item: object) -> str | None:
    if item is None:
        return "элемент where пуст"
    if not isinstance(item, str):
        return f"элемент where: {_not_string(item)}"
    if not item.strip():
        return "элемент where пуст"
    if '"' in item:
        return "элемент where: двойная кавычка внутри значения"
    path, sep, symbol = item.partition("::")
    if sep:
        if not path:
            return f"элемент where «{item}»: путь пуст"
        if "*" in path:
            return f"элемент where «{item}»: * в пути формы путь::символ"
        if not SYMBOL_RE.fullmatch(symbol):
            return f"элемент where «{item}»: символ не по форме"
    error = _path_error(path)
    return f"элемент where «{item}»: {error}" if error else None


def _list_error(name: str, value: object) -> str | None:
    if not isinstance(value, list):
        return f"{name} не список"
    if name == "where":
        if not value:
            return "where — пустой список"
        for item in value:
            error = _where_item_error(item)
            if error:
                return error
        return None
    for item in value:
        error = _text_error(item, required=True)
        if error:
            return f"элемент incidents: {error}"
    return None


def _check_card(key: str, body: object, kind: str, file: str,
                card_lines: dict, field_lines: dict) -> Card | Refusal:
    line = card_lines.get(key)
    if not KEY_RE.fullmatch(key):
        return Refusal(KEY_FORM, f"ключ «{key}» не по форме "
                       f"{KEY_RE.pattern}", file, key=key, line=line)
    if not isinstance(body, dict):
        return Refusal(FIELD_FORM, "значение карточки не отображение", file,
                       key=key, line=line)
    for name in body:
        if name not in FIELDS:
            return Refusal(FIELD_FORM, f"неизвестное поле «{name}» (известны: "
                           f"{', '.join(FIELDS)})", file, key=key, field=name,
                           line=field_lines.get((key, name)))
    for name in ("where",) + REQUIRED_TEXT:
        if name not in body:
            return Refusal(FIELD_FORM, f"нет поля «{name}»", file, key=key,
                           field=name, line=line)
    for name, value in body.items():
        if name in REQUIRED_TEXT or name in OPTIONAL_TEXT:
            error = _text_error(value, required=name in REQUIRED_TEXT)
        elif name == "incidents" and value is None:
            error = None
        else:
            error = _list_error(name, value)
        if error:
            return Refusal(FIELD_FORM, f"{name}: {error}", file, key=key,
                           field=name, line=field_lines.get((key, name)))
    card = Card(kind=kind, key=key, where=tuple(body["where"]),
                rule=body["rule"], why=body["why"],
                check=body.get("check") or "",
                example=body.get("example") or "",
                incidents=tuple(body.get("incidents") or ()))
    size = (len(card.rule) + len(card.why) + len(card.check)
            + len(card.example) + sum(len(item) for item in card.incidents))
    limit = config.KNOWLEDGE_CARD_MAX_CHARS
    if size > limit:
        return Refusal(SIZE_LIMIT, f"суммарная длина текстовых полей {size}, "
                       f"предел {limit}", file, key=key, line=line)
    return card


def check_text(text: str, file: str, kind: str) -> tuple[Card, ...] | Refusal:
    """Карточки файла либо первый отказ формы (требования 1-4). Чистая
    функция: `file` только называется в отказе."""
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        return Refusal(FILE_UNPARSED, str(exc), file)
    refusal, card_lines, field_lines = _line_pass(text, file)
    if refusal is not None:
        return refusal
    if SECTION not in data:
        return Refusal(FIELD_FORM, f"нет раздела «{SECTION}»", file)
    section = data[SECTION]
    if section is None:
        return ()
    if not isinstance(section, dict):
        return Refusal(FIELD_FORM, f"раздел «{SECTION}» не отображение", file)
    limit = config.KNOWLEDGE_CARD_MAX_PER_FILE
    if len(section) > limit:
        return Refusal(COUNT_LIMIT, f"карточек {len(section)}, предел {limit}",
                       file)
    cards = []
    for key, body in section.items():
        result = _check_card(key, body, kind, file, card_lines, field_lines)
        if isinstance(result, Refusal):
            return result
        cards.append(result)
    return tuple(cards)


# --- чтение по видам ---

def _from_text(kind: str, file: str, text: str) -> KindRead:
    # Внутри функции: верхний импорт замкнул бы цикл
    # notes → knowledge_cards → brief → store → models → notes.
    from . import brief
    result = check_text(text, file, kind)
    if isinstance(result, Refusal):
        return KindRead(kind, REFUSED, file=file, refusal=result)
    return KindRead(kind, CARDS, cards=result, file=file,
                    sha256=brief.component_hash(text))


def _refused(kind: str, file: str | None, code: str, detail: str) -> KindRead:
    return KindRead(kind, REFUSED, file=file,
                    refusal=Refusal(code, detail, file or ""))


def _read_main(kind: str, rel: str) -> KindRead:
    """Файл `knowledge/` репозитория пульта — с головы `config.MAIN_BRANCH`
    главной копии, не с диска (требование 8): карточки — правило системы,
    как скилы, и незакоммиченная правка в выдачу не попадает."""
    root = config.ROOT
    # `.git` рабочей копии `git worktree` — файл, и репозиторий там есть.
    if not (root / ".git").exists():
        return KindRead(kind, NOT_SET_UP, file=rel)
    # Отсутствие файла различается через `ls-tree`: `gitcmd.show` отвечает
    # `(None, причина)` и на отсутствие, и на отказ git.
    res = gitcmd.in_repo(root, "ls-tree", "--name-only", config.MAIN_BRANCH,
                         "--", rel)
    if res is None or res.returncode != 0:
        detail = "" if res is None else (res.stderr or "").strip()[:200]
        return _refused(kind, rel, GIT_NO_ANSWER,
                        f"ls-tree {config.MAIN_BRANCH} -- {rel}: "
                        f"{detail or 'нет ответа'}")
    if not res.stdout.strip():
        return KindRead(kind, NOT_SET_UP, file=rel)
    text, reason = gitcmd.show(config.MAIN_BRANCH, rel, repo=root)
    if text is None:
        return _refused(kind, rel, FILE_UNREADABLE,
                        f"show {config.MAIN_BRANCH}:{rel}: {reason}")
    return _from_text(kind, rel, text)


def _read_disk(kind: str, project: str, rel: str) -> KindRead:
    """Файл `.artel/projects/<проект>/knowledge/<имя>.yaml` — с диска
    области проектов (требование 9). Ссылка, специальный файл и выход по
    `resolve()` из каталога знаний проекта — отказ: проектные карточки
    читаются только из каталога пульта, не из клона и не из чужого проекта."""
    match_ = _PROJECT_FIELD_RE.fullmatch(rel)
    if match_ is None or match_["project"] != project:
        return _refused(kind, rel, FILE_UNREADABLE,
                        "путь поля knowledge не в каталоге знаний проекта")
    root = repo_context.projects_root()
    if root == repo_context.NO_AREA:
        # Песочница с подменённым корнем: боевая область не читается.
        return KindRead(kind, NOT_SET_UP, file=rel)
    name = match_["name"]
    path = root / project / "knowledge" / name
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return KindRead(kind, NOT_SET_UP, file=rel)
    except OSError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, f"lstat: {exc}")
    if stat.S_ISLNK(info.st_mode):
        return _refused(kind, rel, FILE_UNREADABLE, "файл — символьная ссылка")
    if not stat.S_ISREG(info.st_mode):
        return _refused(kind, rel, FILE_UNREADABLE, "не обычный файл")
    try:
        expected = root.resolve() / project / "knowledge" / name
        if path.resolve(strict=True) != expected:
            return _refused(kind, rel, FILE_UNREADABLE,
                            "путь вышел по resolve() из каталога знаний "
                            "проекта")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return _refused(kind, rel, FILE_UNREADABLE, "не обычный файл")
            chunks = []
            while chunk := os.read(fd, 1 << 16):
                chunks.append(chunk)
        finally:
            os.close(fd)
        text = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, f"не UTF-8: {exc}")
    except OSError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, str(exc))
    return _from_text(kind, rel, text)


def _project_field(project: str) -> str | None:
    """Поле `knowledge` записи проекта; `None` — поля нет, записи нет или
    `targets.yaml` не годен: чтение карточек не падает на сломанном файле."""
    try:
        entry = targets.target(project)
    except targets.TargetsError:
        return None
    value = entry.get("knowledge")
    return value if isinstance(value, str) else None


def read_cards(project: str) -> tuple[KindRead, KindRead]:
    """Карточки задачи проекта `project` по видам: системный вид первым,
    проектный вторым (требования 6-9)."""
    system = _read_main(SYSTEM, config.KNOWLEDGE_CARD_SYSTEM_REL)
    rel = _project_field(project)
    if rel is None:
        own = KindRead(PROJECT, NOT_SET_UP)
    elif project == config.DEFAULT_TARGET:
        own = _read_main(PROJECT, rel)
    else:
        own = _read_disk(PROJECT, project, rel)
    return system, own


# --- сверка места ---

def _query_error(query: str) -> str | None:
    limit = config.KNOWLEDGE_CARD_QUERY_MAX_CHARS
    if len(query) > limit:
        return f"длина {len(query)} больше {limit}"
    if any(unicodedata.category(ch) == "Cc" for ch in query):
        return "управляющий символ"
    if query.count("::") > 1:
        return "больше одного ::"
    path, sep, symbol = query.partition("::")
    if not path and not sep:
        return "пустой запрос"
    if sep and not symbol:
        return "символ пуст"
    if path:
        return _path_error(path)
    return None


def _symbol_covers(element: str, query: str) -> bool:
    """Символ элемента равен символу запроса или его префиксу по точкам."""
    return query == element or query.startswith(element + ".")


def _element_matches(element: str, path: str, symbol: str | None) -> bool:
    from .project_profile import mask_matches
    e_path, sep, e_symbol = element.partition("::")
    if not sep:
        return bool(path) and mask_matches(element, path)
    if path and e_path != path:
        return False
    return symbol is None or _symbol_covers(e_symbol, symbol)


def match(query: str, cards: Iterable[Card]) -> tuple[Card, ...] | QueryRefusal:
    """Карточки, чьё `where` подходит под место запроса (требование 10):
    системные, затем проектные, внутри вида — по ключу. Файлов не читает."""
    error = _query_error(query)
    if error:
        return QueryRefusal(f"{QUERY_FORM}, относительный путь без .., без "
                            f"префикса ./ и управляющих символов, не длиннее "
                            f"{config.KNOWLEDGE_CARD_QUERY_MAX_CHARS}: {error}")
    path, sep, symbol = query.partition("::")
    wanted = symbol if sep else None
    found = [card for card in cards
             if any(_element_matches(element, path, wanted)
                    for element in card.where)]
    found.sort(key=lambda card: (card.kind != SYSTEM, card.key))
    return tuple(found)
