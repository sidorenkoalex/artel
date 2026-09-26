"""Сторож таблицы паритета безопасности роли в `docs/stack.md` (SPEC
01M3F7BYE82S9AQCBSP1RTQQTR, требования 1-3).

Документ проверяется как данные, а не как проза: таблица разбирается,
каждая её строка обязана опознаваться одним из восьми запретов перечня
требования 1 и нести либо имя ЖИВОЙ проверки `doctor`, либо честную
пометку «не закрыт» с компенсацией. Имена проверок собираются из
исходников `orchestrator/doctor/`, а не переписаны сюда литералами:
таблица обязана называть проверку, которая в пульте есть сегодня, а не ту,
что была на день правки документа.

Собираются они по МЕСТУ ОБЪЯВЛЕНИЯ (разбором `ast`), а не по форме
литерала (REVIEW.md итерации 1, R1-F2): сбор «любой дефисный литерал минус
ручной чёрный список» ослабевал бы сам — дефисное слово, именем строки не
являющееся (`read-only`, `workspace-write`, `ls-files`; `workspace-write`
уже стоит в тексте двух строк таблицы), делало бы строку «подтверждённой»
проверкой, которой нет, и свойство AC-2 выключалось бы молча, на зелёном
тесте.

Таблица ищется ПОКРЫТИЕМ (та из таблиц документа, которая опознаёт больше
всего запретов), а не заголовком раздела: предмет требования — строка на
каждый запрет, и привязка к формулировке заголовка сделала бы тест
заложником этой формулировки.
"""
import ast
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
#: Суффикс константы, несущей имя строки: `FOREIGN_SECRETS_CHECK = "…"`.
_CHECK_CONST_SUFFIX = "_CHECK"
#: Суффикс имени фабрики строки: `doctor.Check(...)` сама запись строки,
#: `_provider_home_check("codex-role-home", …)` — фабрика над ней.
_CHECK_FACTORY_SUFFIX = "_check"


def stack_md_text() -> str:
    return config.ROOT.joinpath(*STACK_MD_REL).read_text(encoding="utf-8")


def _callee_name(func) -> str:
    """Имя вызываемого: `doctor.Check` и `Check` — одинаково `Check`."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def _declared_name(arg):
    """Имя строки из первого аргумента фабрики либо `None`.

    Литерал — целиком; параметризованное имя (`f"map-growth:{target}"`,
    `f"snapshot-pending:{task_id}"`) — своим постоянным префиксом: строка
    таблицы называет семейство, а не отдельный target. Первый аргумент,
    пришедший параметром (`Check(name, …)` внутри фабрики), именем не
    является — имя такой строки стоит литералом на вызове фабрики.
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr) and arg.values:
        head = arg.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value.rstrip(":")
    return None


def doctor_check_names() -> set:
    """Имена строк `doctor`, какими их ОБЪЯВЛЯЕТ код `orchestrator/doctor/`:
    первый аргумент записи строки (`Check(...)`) и её фабрик (`*_check(...)`)
    плюс константы `*_CHECK`.

    Разбор `ast`, а не регулярка по тексту: предмет — место объявления имени,
    и строка, чьё имя пришло откуда-то ещё, в набор не попадёт вовсе
    (сторож покраснеет громко), тогда как литерал ЛЮБОГО дефисного слова
    молча пополнял бы набор именами, которых у `doctor` нет.
    """
    names = set()
    for path in sorted(config.ROOT.joinpath(*DOCTOR_REL).glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                callee = _callee_name(node.func)
                if callee == "Check" or callee.endswith(_CHECK_FACTORY_SUFFIX):
                    name = _declared_name(node.args[0])
                    if name:
                        names.add(name)
            elif isinstance(node, ast.Assign):
                value = node.value
                if not (isinstance(value, ast.Constant)
                        and isinstance(value.value, str)):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Name)
                            and target.id.endswith(_CHECK_CONST_SUFFIX)):
                        names.add(value.value)
    return names


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

    def test_check_names_come_from_declaration_sites_only(self):
        """Набор «живых» имён собран по ТРЁМ местам объявления имени строки
        `doctor` — литералу в `Check(...)`, фабрике строки (`*_check(...)`) и
        константе `*_CHECK` — и не несёт дефисных слов, именами строк не
        являющихся.

        Ловит мутацию: сбор возвращается к форме литерала (любой
        `имя-через-дефис` в исходниках `orchestrator/doctor/` минус ручной
        чёрный список) — набор молча пополняется словами вроде
        `workspace-write`, `read-only`, `ls-remote`, и строка таблицы, где
        такое слово стоит в тексте механизма, считается подтверждённой
        проверкой, которой нет: свойство AC-2 выключается на зелёном тесте.
        Вторая мутация того же класса: сбор теряет одно из трёх мест
        объявления — имя, объявленное фабрикой или константой, перестаёт
        считаться живым, и строка таблицы, называющая ровно его, краснеет
        ложно (этот исход громкий, тем и отличается от первого).
        """
        self.assertIn("canary-pool-leak", self.known,
                      "литерал имени в Check(...) не собран")
        self.assertIn("foreign-provider-secrets", self.known,
                      "имя из константы *_CHECK не собрано")
        self.assertIn("codex-role-home", self.known,
                      "имя с вызова фабрики строки не собрано")

        for word in ("utf-8", "workspace-write", "read-only", "ls-remote",
                     "rev-parse", "merge-base", "pre-commit", "pre-push"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.known)

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
