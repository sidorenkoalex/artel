"""Сторож таблицы паритета безопасности роли в `docs/stack.md` (SPEC
01M3F7BYE82S9AQCBSP1RTQQTR, требования 1-3).

Документ проверяется как данные, а не как проза: таблица разбирается,
каждая её строка обязана опознаваться одним из восьми запретов перечня
требования 1 и нести либо имя ЖИВОЙ проверки `doctor`, либо честную
пометку «не закрыт» с компенсацией. Имена проверок собираются из
исходников `orchestrator/doctor/`, а не переписаны сюда литералами:
таблица обязана называть проверку, которая в пульте есть сегодня, а не ту,
что была на день правки документа.

Таблица ищется ПОКРЫТИЕМ (та из таблиц документа, которая опознаёт больше
всего запретов), а не заголовком раздела: предмет требования — строка на
каждый запрет, и привязка к формулировке заголовка сделала бы тест
заложником этой формулировки.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402

#: Документ и каталог проверок — от `config.ROOT` в момент вызова: тот же
#: корень, которым пульт адресует свои файлы.
STACK_MD_REL = ("docs", "stack.md")
DOCTOR_REL = ("orchestrator", "doctor")

#: Восемь запретов перечня требования 1 SPEC: название и альтернативы
#: опознания строки (альтернатива срабатывает, когда в строке есть ВСЕ её
#: подстроки; регистр не важен). Набор широкий намеренно — требование
#: называет предмет запрета, а не формулировку ячейки.
PROHIBITIONS = (
    ("файлы вне рабочего каталога",
     (("вне рабочего каталога",), ("файлы вне",), ("вне рабочей копии",))),
    ("сеть", (("сеть",), ("сети",), ("сетев",), ("network",))),
    ("Связка ключей и секреты",
     (("связка ключей",), ("связки ключей",), ("связке ключей",),
      ("keychain",), ("секрет",))),
    ("инструменты и MCP", (("mcp",),)),
    ("хуки", (("хук",),)),
    ("чтение user-слоя Оператора",
     (("user", "сло"), ("пользовательск", "сло"), ("user-layer",))),
    ("пул канарейки", (("пул",),)),
    ("посторонние файлы и защищённые пути",
     (("посторонние файлы",), ("посторонних файл",), ("защищённ",),
      ("защищен",))),
)

#: Пометка «не закрыт» — тремя родами.
NOT_CLOSED = ("не закрыт", "не закрыто", "не закрыта")

#: Компенсация строки «не закрыт» (требование 2): гейт пульта после шага
#: либо явная пометка принятого риска.
COMPENSATION = ("гейт", "риск")

_SEPARATOR_ROW = re.compile(r"^\|[\s:|-]+\|?\s*$")
#: Имя строки `doctor` — `имя-через-дефис` в двойных кавычках исходника.
_CHECK_LITERAL = re.compile(r'"([a-z][a-z0-9]*(?:-[a-z0-9]+)+)"')
#: Литералы той же формы, именами проверок не являющиеся.
_NOT_A_CHECK = frozenset({"utf-8", "ls-remote", "rev-parse", "merge-base",
                          "pre-commit", "pre-push"})


def stack_md_text() -> str:
    return config.ROOT.joinpath(*STACK_MD_REL).read_text(encoding="utf-8")


def doctor_check_names() -> set:
    """Имена строк `doctor`, какими их знает код `orchestrator/doctor/`."""
    names = set()
    for path in sorted(config.ROOT.joinpath(*DOCTOR_REL).glob("*.py")):
        names.update(_CHECK_LITERAL.findall(path.read_text(encoding="utf-8")))
    return names - _NOT_A_CHECK


def markdown_tables(text: str) -> list:
    """Таблицы документа: подряд идущие строки, начинающиеся с `|`."""
    tables, current = [], []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def data_rows(table: list) -> list:
    """Строки-данные: без заголовка и без разделителя `|---|---|`."""
    rows = [line for line in table if not _SEPARATOR_ROW.match(line.strip())]
    return rows[1:] if len(rows) > 1 else []


def row_matches(row: str, alternatives) -> bool:
    lowered = row.lower()
    return any(all(part in lowered for part in alt) for alt in alternatives)


def missing_prohibitions(rows: list) -> list:
    return [name for name, alternatives in PROHIBITIONS
            if not any(row_matches(row, alternatives) for row in rows)]


def parity_table(text: str) -> list:
    """Строки-данные таблицы паритета: та таблица документа, которая
    покрывает БОЛЬШЕ всего запретов перечня."""
    best, best_score = [], -1
    for table in markdown_tables(text):
        rows = data_rows(table)
        score = sum(1 for _name, alts in PROHIBITIONS
                    if any(row_matches(row, alts) for row in rows))
        if score > best_score:
            best, best_score = rows, score
    return best


def checks_named_in(row: str, known: set) -> list:
    """Имена проверок из `known`, названные строкой, по границам слова:
    `isolation-smoke` не считается названным внутри
    `codex-isolation-smoke`."""
    lowered = row.lower()
    return sorted(name for name in known
                  if re.search(rf"(?<![a-z0-9-]){re.escape(name)}(?![a-z0-9-])",
                               lowered))


def row_is_open(row: str) -> bool:
    lowered = row.lower()
    return any(mark in lowered for mark in NOT_CLOSED)


class StackParityTableTest(unittest.TestCase):
    """Таблица паритета безопасности роли — требования 1-3."""

    def setUp(self):
        self.text = stack_md_text()
        self.rows = parity_table(self.text)
        self.known = doctor_check_names()

    def test_the_table_carries_a_row_for_each_of_the_eight_prohibitions(self):
        """В `docs/stack.md` есть таблица, в строках которой опознаются все
        восемь запретов перечня требования 1: файлы вне рабочего каталога,
        сеть, Связка ключей и секреты, инструменты и MCP, хуки, чтение
        user-слоя Оператора, пул канарейки, посторонние файлы и защищённые
        пути.

        Ловит мутацию: из таблицы исчезает строка запрета, которого у
        Claude не видно с первого взгляда (хуки или посторонние файлы и
        защищённые пути) — документ продолжает выглядеть полным, а предмет,
        ради которого таблица заведена, потерян; `assertEqual` назовёт
        потерянный запрет по имени.
        """
        self.assertTrue(self.rows,
                        "в docs/stack.md нет ни одной markdown-таблицы — "
                        "таблица паритета безопасности роли обязательна")
        self.assertEqual([], missing_prohibitions(self.rows),
                         f"строк таблицы: {len(self.rows)}")

    def test_each_row_names_a_live_doctor_check_or_is_honestly_open(self):
        """Каждая строка таблицы несёт либо имя ЖИВОЙ проверки `doctor`
        (имя, которое есть в исходниках `orchestrator/doctor/`), либо
        пометку «не закрыт».

        Ловит мутацию: строка о запрете, который у Codex ничем не закрыт,
        заполняется прочерком или обещанием «закрыто песочницей» без
        подтверждающей проверки — таблица обещает Оператору рубеж, о
        котором `doctor` ничего не знает. Вторая мутация того же класса:
        строка называет проверку, переименованную или удалённую из
        `orchestrator/doctor/`.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет")
        self.assertTrue(self.known, "имена проверок doctor не собраны")

        no_evidence = [row.strip() for row in self.rows
                       if not checks_named_in(row, self.known)
                       and not row_is_open(row)]

        self.assertEqual([], no_evidence,
                         "строка(и) без имени живой проверки doctor и без "
                         "пометки «не закрыт»: " + " || ".join(no_evidence))

    def test_open_rows_name_a_compensating_gate_or_an_accepted_risk(self):
        """Каждая строка с пометкой «не закрыт» называет компенсирующий
        гейт пульта после шага либо явно помечена принятым риском.

        Ловит мутацию: честная пометка «не закрыт» ставится, и на этом
        разговор заканчивается — Оператор видит дыру и не видит, чем она
        держится.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет")

        uncompensated = [
            row.strip() for row in self.rows if row_is_open(row)
            and not any(word in row.lower() for word in COMPENSATION)]

        self.assertEqual([], uncompensated,
                         "строка(и) «не закрыт» без компенсации: "
                         + " || ".join(uncompensated))


if __name__ == "__main__":
    unittest.main()
