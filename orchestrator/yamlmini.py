"""Подмножество YAML, которого достаточно системе: frontmatter и roles.yaml.

Один разбор на всех читателей: frontmatter артефактов читают и оркестратор
(`artifacts.frontmatter`), и валидатор (`scripts/guard.py`). Два парсера
означали бы два набора правил на один формат, и расхождение обнаруживалось
бы чужим сбоем, а не проверкой (SPEC T017, требование 2).

Разбирается ровно то, что в репозитории есть:

- скаляры с типом (`scalar`): int, float, bool, null, строка; кавычки
  и хвостовой `# комментарий` снимаются;
- плоское отображение между `---` (`frontmatter`);
- вложенные блочные отображения по отступу и потоковые списки `[a, b]`
  (`mapping`).

Чего нет — того нет намеренно: многострочные скаляры (`|`, `>`), якоря,
блочные списки `- элемент`, несколько документов в файле. Встретив их,
`mapping` отказывается ошибкой с номером строки, а не возвращает молча
половину разобранного.

Полноценный YAML (PyYAML) не берётся сознательно: CI зовёт системный
`python3` без шага установки зависимостей, а `.github/` меняет только
Оператор — см. PLAN T017, «Подход», решение 1.
"""
import re

FENCE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
INT = re.compile(r"\A[+-]?\d+\Z")
# Дробное — только с цифрами и точкой или экспонентой: так `nan` и `inf`,
# которые `float()` принимает, остаются строками и не притворяются числами.
FLOAT = re.compile(r"\A[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?\Z")
# `#` начинает комментарий, только когда стоит в начале или после пробела —
# правило YAML. Значение вида `a#b` остаётся значением целиком.
COMMENT = re.compile(r"(?:\A|\s)#.*\Z", re.S)


class YamlError(ValueError):
    """Конструкция, которую разбор не поддерживает, или сломанный отступ."""


def scalar(raw: str) -> object:
    """Значение скаляра с типом: int, float, bool, None или строка.

    Кавычки — форма записи, а не тип: `"25"` остаётся строкой `25`,
    как этого и ждёт YAML, а превращать её в число — дело читателя поля
    (см. `budget.spec_budget`).
    """
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    text = COMMENT.sub("", text).strip()
    if text in ("", "null", "~"):
        return None
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if INT.match(text):
        return int(text)
    if FLOAT.match(text):
        return float(text)
    return text


def frontmatter(text: str) -> dict | None:
    """Frontmatter артефакта: плоское отображение; None — блока нет вовсе.

    Строка без двоеточия пропускается, а не роняет разбор: frontmatter
    читается и на пути валидации, и на пути FSM, и отсутствие обязательного
    поля guard называет внятнее, чем исключение парсера.
    """
    block = FENCE.match(text)
    if block is None:
        return None
    meta: dict = {}
    for line in block.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        meta[key.strip()] = scalar(value)
    return meta


def mapping(text: str) -> dict:
    """Вложенное блочное отображение YAML → словарь. YamlError — не разобрано."""
    lines = _significant(text)
    if not lines:
        return {}
    block, pos = _block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise YamlError(f"строка {lines[pos][2]}: неожиданный отступ")
    return block


def _significant(text: str) -> list[tuple[int, str, int]]:
    """Строки, несущие данные: (отступ, содержимое, номер строки в файле)."""
    lines = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = raw.lstrip(" ")
        if body != raw.lstrip():
            raise YamlError(f"строка {number}: табуляция в отступе")
        lines.append((len(raw) - len(body), stripped, number))
    return lines


def _block(lines: list, pos: int, indent: int) -> tuple[dict, int]:
    """Отображение с заданным отступом и позиция первой строки за ним."""
    block: dict = {}
    while pos < len(lines):
        current, content, number = lines[pos]
        if current < indent:
            break
        if current > indent:
            raise YamlError(f"строка {number}: неожиданный отступ")
        if content.startswith("- "):
            raise YamlError(f"строка {number}: блочные списки не разбираются")
        key, sep, rest = content.partition(":")
        if not sep:
            raise YamlError(f"строка {number}: не пара «ключ: значение»")
        pos += 1
        rest = rest.strip()
        if rest == "" or rest.startswith("#"):
            # Пустое значение — либо вложенный блок (следующая строка глубже),
            # либо честный null.
            if pos < len(lines) and lines[pos][0] > current:
                block[key.strip()], pos = _block(lines, pos, lines[pos][0])
            else:
                block[key.strip()] = None
        else:
            block[key.strip()] = _value(rest, number)
    return block, pos


def _value(raw: str, number: int) -> object:
    """Значение справа от двоеточия: потоковый список или скаляр."""
    if not raw.startswith("["):
        return scalar(raw)
    end = raw.rfind("]")
    if end == -1:
        raise YamlError(f"строка {number}: список без закрывающей скобки")
    tail = raw[end + 1:].strip()
    if tail and not tail.startswith("#"):
        raise YamlError(f"строка {number}: мусор после списка: '{tail}'")
    inner = raw[1:end].strip()
    return [scalar(item) for item in inner.split(",")] if inner else []
