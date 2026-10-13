"""Сверка места карточек знаний: `orchestrator.knowledge_cards.match`.

Чистая функция без песочницы: карточки `Card` строятся в тесте, запрос —
строка формы `<путь>`, `<путь>::<символ>` или `::<символ>`; ответ —
кортеж совпавших карточек либо `QueryRefusal`. Имена путей и символов,
ключи карточек и порядок подачи карточек — случайные при каждом запуске;
зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/knowledge_cards.py ещё нет — импорт падает, все тесты файла красны.
"""
import builtins
import os
import random
import sys
import unittest
from unittest import mock

from orchestrator import config
try:
    from orchestrator import knowledge_cards as kc
except ImportError as exc:  # до реализации модуля нет: сбор проходит, тесты красны
    kc = None
    KC_IMPORT_ERROR = exc


def setUpModule() -> None:
    if kc is None:
        raise KC_IMPORT_ERROR

LATIN = "abcdefghijklmnopqrstuvwxyz"

# Пути, открытые на чтение, пока включена запись (`sys.addaudithook` снять
# нельзя — хук один на процесс и пишет только при непустом стеке).
_OPENED: list = []
_RECORDING: list = []


def _audit(event, args):
    if _RECORDING and event == "open":
        _OPENED.append(args[0])


sys.addaudithook(_audit)


class Inputs:

    def __init__(self):
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def name(self, n: int | None = None) -> str:
        while True:
            value = "".join(self.rng.choice(LATIN)
                            for _ in range(n or self.rng.randrange(3, 9)))
            if value not in self.used:
                self.used.add(value)
                return value


def card(key: str, where: tuple, kind: str = "") -> "kc.Card":
    return kc.Card(kind=kind or kc.SYSTEM, key=key, where=tuple(where), rule="правило",
                   why="причина", check="", example="", incidents=())


def keys(result) -> list:
    return [c.key for c in result]


class MatchTest(unittest.TestCase):

    def setUp(self):
        self.inp = Inputs()

    def found(self, query: str, cards) -> list:
        result = kc.match(query, list(cards))
        self.assertNotIsInstance(result, kc.QueryRefusal, self.inp.msg(
            f"запрос {query!r} отвергнут: {result!r}"))
        self.assertIsInstance(result, tuple, self.inp.msg(query))
        return keys(result)

    def assert_hit(self, query: str, item: "kc.Card") -> None:
        self.assertIn(item.key, self.found(query, [item]),
                      self.inp.msg(f"{query!r} не нашёл {item.where}"))

    def assert_miss(self, query: str, item: "kc.Card") -> None:
        self.assertNotIn(item.key, self.found(query, [item]),
                         self.inp.msg(f"{query!r} нашёл {item.where}"))


class MaskAndSymbolTest(MatchTest):

    def test_ac11_mask_star_stays_within_segment_double_star_spans(self):
        """`a/*.py` подходит под `a/b.py`, не под `a/c/b.py`; `a/**/b.py` —
        под `a/c/d/b.py`; маска подходит и под запрос `a/b.py::f`.

        Ловит мутацию: маска сверяется `fnmatch` (`*` пересекает `/`) —
        `a/c/b.py` найден маской `a/*.py`; либо у запроса `путь::символ`
        с маской сверяется вся строка запроса — `a/b.py::f` не найден.
        """
        for _ in range(3):
            a, b, c, d, f = (self.inp.name() for _ in range(5))
            star = card(self.inp.name(), [f"{a}/*.py"])
            deep = card(self.inp.name(), [f"{a}/**/{b}.py"])
            self.assert_hit(f"{a}/{b}.py", star)
            self.assert_miss(f"{a}/{c}/{b}.py", star)
            self.assert_hit(f"{a}/{c}/{d}/{b}.py", deep)
            self.assert_hit(f"{a}/{b}.py::{f}", star)
            self.assert_hit(f"{a}/{b}.py::{f}.{c}", star)

    def test_ac11_path_symbol_element_matches_path_and_symbol_queries(self):
        """Элемент `p::s` находится запросами `p`, `p::s`, `p::s.m`; не
        находится запросами `p::t` и `q::s`.

        Ловит мутацию: элемент `p::s` сверяется только с запросом формы
        `путь::символ` (запрос `p` его не находит) либо путь элемента не
        сравнивается (запрос `q::s` его находит).
        """
        for _ in range(3):
            p = f"{self.inp.name()}/{self.inp.name()}.py"
            q = f"{self.inp.name()}/{self.inp.name()}.py"
            s, t, m = self.inp.name(), self.inp.name(), self.inp.name()
            item = card(self.inp.name(), [f"{p}::{s}"])
            for query in (p, f"{p}::{s}", f"{p}::{s}.{m}"):
                self.assert_hit(query, item)
            for query in (f"{p}::{t}", f"{q}::{s}"):
                self.assert_miss(query, item)

    def test_ac11_symbol_prefix_only_on_dot_boundary(self):
        """`p::Class` подходит под `p::Class.method`; `p::Class.method` не
        подходит под `p::Class`; `p::Class` не подходит под `p::ClassX`.

        Ловит мутацию: префикс символа сверяется `startswith` без границы
        точки (`ClassX` найден элементом `Class`) либо в обратную сторону
        (элемент `Class.method` найден запросом `Class`).
        """
        for _ in range(3):
            p = f"{self.inp.name()}.py"
            cls = self.inp.name().capitalize()
            method = self.inp.name()
            tail = self.inp.name(1).upper()
            short = card(self.inp.name(), [f"{p}::{cls}"])
            longer = card(self.inp.name(), [f"{p}::{cls}.{method}"])
            self.assert_hit(f"{p}::{cls}.{method}", short)
            self.assert_miss(f"{p}::{cls}", longer)
            self.assert_miss(f"{p}::{cls}{tail}", short)
            self.assert_miss(f"{p}::{cls}{tail}.{method}", short)

    def test_ac11_symbol_only_query_across_files_masks_excluded(self):
        """Запрос `::s` находит карточки с символом `s` в разных файлах;
        карточка, у которой в `where` только маски, им не находится.

        Ловит мутацию: `::s` ищет только в первом файле (или требует
        совпадения пути с пустой строкой), либо маска без символа
        засчитывается как совпадение любого символа.
        """
        for _ in range(3):
            s = self.inp.name()
            one = card(self.inp.name(), [f"{self.inp.name()}/x.py::{s}"])
            two = card(self.inp.name(), [f"{self.inp.name()}.py::{s}.{self.inp.name()}",
                                         f"{self.inp.name()}.py::{s}"])
            other = card(self.inp.name(), [f"{self.inp.name()}.py::{self.inp.name()}"])
            masks = card(self.inp.name(), [f"{self.inp.name()}/*.py", "**/*.py"])
            got = self.found(f"::{s}", [one, two, other, masks])
            self.assertEqual(sorted(got), sorted([one.key, two.key]),
                             self.inp.msg(f"::{s} -> {got}"))

    def test_ac11_order_system_then_project_by_key(self):
        """Результат упорядочен: системные, затем проектные, внутри вида —
        по ключу, независимо от порядка подачи.

        Сценарий: 3–5 системных и 3–5 проектных карточек с общей маской
        подаются в случайном порядке.

        Ловит мутацию: порядок подачи сохраняется как есть либо сортировка
        только по ключу (проектная `a…` раньше системной `z…`).
        """
        for _ in range(3):
            path = f"{self.inp.name()}/{self.inp.name()}.py"
            system = [card(self.inp.name(), [path], kc.SYSTEM)
                      for _ in range(self.inp.rng.randrange(3, 6))]
            project = [card(self.inp.name(), [path], kc.PROJECT)
                       for _ in range(self.inp.rng.randrange(3, 6))]
            mixed = system + project
            self.inp.rng.shuffle(mixed)
            got = self.found(path, mixed)
            expected = (sorted(c.key for c in system)
                        + sorted(c.key for c in project))
            self.assertEqual(got, expected, self.inp.msg(f"подано {keys(mixed)}"))

    def test_ac11_match_reads_no_files(self):
        """Сверка места не обращается к файловой системе.

        Сценарий: карточки называют существующие пути репозитория и
        случайные несуществующие; во время вызовов `match` (после
        разогревающего вызова) не открыт ни один файл и не запрошен
        `stat`/`lstat`/листинг каталога.

        Ловит мутацию: `match` проверяет существование пути элемента
        (`Path(p).exists()`) или читает файл ради символа — зафиксировано
        обращение к файловой системе.
        """
        items = [card(self.inp.name(), ["orchestrator/config.py::is_protected_path"]),
                 card(self.inp.name(), [f"{self.inp.name()}/*.py"]),
                 card(self.inp.name(), ["orchestrator/**/*.py"], kc.PROJECT)]
        queries = ["orchestrator/config.py", "orchestrator/config.py::is_protected_path",
                   f"::{self.inp.name()}", f"{self.inp.name()}/x.py"]
        for query in queries:
            kc.match(query, items)
        calls = []

        def spy(real):
            def wrapper(*args, **kwargs):
                calls.append((real.__name__, args[:1]))
                return real(*args, **kwargs)
            return wrapper

        _OPENED.clear()
        with mock.patch.object(os, "stat", spy(os.stat)), \
                mock.patch.object(os, "lstat", spy(os.lstat)), \
                mock.patch.object(os, "listdir", spy(os.listdir)), \
                mock.patch.object(os, "scandir", spy(os.scandir)), \
                mock.patch.object(builtins, "open", spy(builtins.open)):
            _RECORDING.append(True)
            try:
                for query in queries:
                    kc.match(query, items)
            finally:
                _RECORDING.pop()
        self.assertEqual(calls, [], self.inp.msg("обращения к ФС"))
        self.assertEqual(_OPENED, [], self.inp.msg("открытые файлы"))


class QueryFormTest(MatchTest):

    def refused(self, query: str, items) -> None:
        result = kc.match(query, items)
        self.assertIsInstance(result, kc.QueryRefusal, self.inp.msg(
            f"запрос {query!r} принят: {result!r}"))
        self.assertIsInstance(result.detail, str, self.inp.msg(query))
        self.assertTrue(result.detail.strip(), self.inp.msg(query))

    def test_ac12_malformed_queries_refused_without_cards(self):
        """Управляющий символ, абсолютный путь, `..`, префикс `./`, два `::`
        — `QueryRefusal` с текстом формы запроса, карточек не отдаётся.

        Сценарий: карточка с масками `**/*.py` и `**` подходит под любой
        путь — принятый некорректный запрос вернул бы её.

        Ловит мутацию: проверка формы запроса снята или пропускает один из
        случаев (`..` внутри пути, `./` в начале, второй `::`) — запрос
        отдаёт карточку вместо отказа.
        """
        a, b, s = self.inp.name(), self.inp.name(), self.inp.name()
        items = [card(self.inp.name(), ["**/*.py", "**", f"{a}/{b}.py::{s}"])]
        for query in (f"{a}/\x00{b}.py", f"{a}/{b}.py\n", f"{a}\t/{b}.py",
                      f"{a}/{b}\x1b.py", f"/{a}/{b}.py", f"{a}/../{b}.py",
                      f"../{a}.py", f"./{a}/{b}.py", f"{a}/{b}.py::{s}::{s}",
                      f"::{s}::{s}"):
            with self.subTest(query=query):
                self.refused(query, items)

    def test_ac12_length_boundary_from_config(self):
        """Запрос ровно `config.KNOWLEDGE_CARD_QUERY_MAX_CHARS` символов
        принят и сверяется, на символ длиннее — отказ.

        Ловит мутацию: сравнение `>=` вместо `>` (запрос ровно на пределе
        отвергнут) либо длина не проверяется (длинный запрос отдаёт
        карточку).
        """
        limit = config.KNOWLEDGE_CARD_QUERY_MAX_CHARS
        item = card(self.inp.name(), ["**/*.py"])
        for _ in range(3):
            head = f"{self.inp.name()}/"
            filler = "".join(self.inp.rng.choice(LATIN)
                             for _ in range(limit - len(head) - 3))
            query = f"{head}{filler}.py"
            self.assertEqual(len(query), limit)
            self.assertEqual(self.found(query, [item]), [item.key],
                             self.inp.msg(query))
            self.refused(f"{head}{filler}x.py", [item])

    def test_ac12_leading_dot_without_slash_is_valid_query(self):
        """Запрос `.github/workflows/ci.yml` по форме принят и сверяется с
        маской `.github/workflows/*.yml`.

        Ловит мутацию: правило «ведущие точка и косая черта» реализовано
        как запрет любой ведущей точки — запрос `.github/…` отвергнут.
        """
        name = self.inp.name()
        item = card(self.inp.name(), [".github/workflows/*.yml"])
        self.assertEqual(self.found(".github/workflows/ci.yml", [item]),
                         [item.key])
        self.assertEqual(self.found(f".github/workflows/{name}.yml", [item]),
                         [item.key])
        self.assertEqual(self.found(f".{name}/x.yml", [item]), [])


if __name__ == "__main__":
    unittest.main()
