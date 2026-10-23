"""`store.db_readonly` — одна функция открытия БД пульта только на чтение.

Группа: долгоживущий

Красен до реализации: функции `store.db_readonly` ещё нет — AC-1, AC-2, AC-3 и AC-5 падают `AttributeError` на её вызове, а линтер AC-4 находит пять копий строки `?mode=ro` вне неё (store.db_usable, knowledge_cards, suite_run, preflight, scripts/test_rule_stats.py).

Свойства функции проверяются модульно, без песочницы пульта: БД — файл
SQLite во временном каталоге, собранный стандартным `sqlite3`; путь по
умолчанию — подменённый `config.DB`. Имена файлов, таблиц и значения — от
зерна; зерно печатается и входит в текст провала.
"""
import ast
import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, store

REPO = Path(__file__).resolve().parent.parent
MARK = "?mode=ro"


def _name(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                            for _ in range(rng.randint(3, 9)))


class DbReadonlyTest(unittest.TestCase):
    """AC-1, AC-2, AC-3, AC-5: поведение и вызов `sqlite3.connect`."""

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def make_db(self, path: Path) -> str:
        """Файл SQLite с одной таблицей и строкой; имя таблицы — результат."""
        table = _name(self.rng, "t_")
        conn = sqlite3.connect(str(path))
        try:
            conn.execute(f"CREATE TABLE {table} (v TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES (?)", ("x",))
            conn.commit()
        finally:
            conn.close()
        return table

    def test_ac1_write_refused_and_row_factory_by_rows(self):
        """Существующая БД с таблицей открыта `db_readonly` трижды: без
        `rows`, с `rows=True` и с `rows=False`.

        Наблюдение: INSERT через каждое соединение отказывает
        `sqlite3.OperationalError` с «readonly» в тексте, таблица после
        попыток несёт одну исходную строку; `row_factory` — `sqlite3.Row`
        по умолчанию и при `rows=True`, `None` при `rows=False`.

        Ловит мутацию: соединение открыто без `?mode=ro` (обычный
        `sqlite3.connect(path)`) — INSERT проходит, отказа нет; либо
        `row_factory` ставится без оглядки на `rows` — при `rows=False`
        он `sqlite3.Row`, а не `None`.
        """
        path = self.tdir / f"{_name(self.rng, 'db_')}.db"
        table = self.make_db(path)
        cases = (({}, sqlite3.Row), ({"rows": True}, sqlite3.Row),
                 ({"rows": False}, None))
        for kwargs, factory in cases:
            with self.subTest(kwargs=kwargs):
                conn = store.db_readonly(path, **kwargs)
                try:
                    self.assertIs(conn.row_factory, factory,
                                  f"зерно: {self.seed}")
                    with self.assertRaises(sqlite3.OperationalError) as ctx:
                        conn.execute(f"INSERT INTO {table} VALUES (?)",
                                     (_name(self.rng, "v_"),))
                        conn.commit()
                    self.assertIn("readonly", str(ctx.exception).lower(),
                                  f"зерно: {self.seed}")
                finally:
                    conn.close()
        check = sqlite3.connect(str(path))
        try:
            count = check.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            check.close()
        self.assertEqual(count, 1, f"зерно: {self.seed}")

    def test_ac2_missing_file_raises_and_is_not_created(self):
        """`db_readonly` зовут на путях несуществующих файлов: в
        существующем каталоге и в несуществующем подкаталоге.

        Наблюдение: каждый вызов поднимает `sqlite3.OperationalError`, файл
        (и подкаталог) после вызова не существуют.

        Ловит мутацию: открытие без `mode=ro` (режим `rwc` по умолчанию)
        либо через `store.db()` — SQLite создаёт пустой файл, исключения нет.
        """
        paths = [self.tdir / f"{_name(self.rng, 'absent_')}.db",
                 self.tdir / _name(self.rng, "dir_") / "state.db"]
        for path in paths:
            with self.subTest(path=str(path)):
                with self.assertRaises(sqlite3.OperationalError):
                    conn = store.db_readonly(path)
                    conn.close()
                self.assertFalse(path.exists(), f"зерно: {self.seed}")

    def test_ac3_connect_gets_resolved_uri_and_uri_keyword(self):
        """Путь к БД содержит символическую ссылку на каталог либо `..`;
        `sqlite3.connect` подменён шпионом.

        Наблюдение: первым позиционным аргументом шпиона — строка
        `path.resolve().as_uri() + "?mode=ro"`, отличная от строки
        неразрешённого пути; `uri=True` передан именованным аргументом.

        Ловит мутацию: URI собирается без `resolve()` (`path.absolute()` или
        `os.path.abspath`) — в строке шпиона остаётся ссылка или `..`; либо
        `uri` передан позиционно/опущен — `kwargs` шпиона без `uri=True`.
        """
        real = self.tdir / _name(self.rng, "real_")
        (real / "sub").mkdir(parents=True)
        link = self.tdir / _name(self.rng, "link_")
        os.symlink(real, link, target_is_directory=True)
        name = f"{_name(self.rng, 'db_')}.db"
        variants = {"symlink": link / name,
                    "dotdot": real / "sub" / ".." / name}
        for kind, path in variants.items():
            with self.subTest(kind=kind):
                expected = f"{path.resolve().as_uri()}{MARK}"
                self.assertNotEqual(expected, f"{path.absolute().as_uri()}{MARK}",
                                    "предпосылка: resolve() меняет путь")
                with mock.patch.object(sqlite3, "connect",
                                       return_value=mock.MagicMock()) as spy:
                    store.db_readonly(path)
                self.assertEqual(spy.call_count, 1, f"зерно: {self.seed}")
                call = spy.call_args
                self.assertTrue(call.args, f"зерно: {self.seed}: {call}")
                self.assertEqual(call.args[0], expected, f"зерно: {self.seed}")
                self.assertIs(call.kwargs.get("uri"), True,
                              f"зерно: {self.seed}: {call}")

    def test_ac5_default_path_is_config_db_at_call_time(self):
        """`config.DB` подменён после импорта `store` на путь во временном
        каталоге; `db_readonly()` зовут без аргументов, `sqlite3.connect` —
        шпион.

        Наблюдение: шпион получает `as_uri()` подменённого пути с
        суффиксом `?mode=ro` — для двух разных подмен подряд.

        Ловит мутацию: путь по умолчанию взят при импорте
        (`def db_readonly(path=config.DB)`) — шпион видит боевой
        `config.DB`, а не подменённый.
        """
        for _ in range(2):
            path = self.tdir / f"{_name(self.rng, 'state_')}.db"
            with mock.patch.object(config, "DB", path), \
                    mock.patch.object(sqlite3, "connect",
                                      return_value=mock.MagicMock()) as spy:
                store.db_readonly()
            self.assertEqual(spy.call_count, 1, f"зерно: {self.seed}")
            self.assertEqual(spy.call_args.args[0],
                             f"{path.resolve().as_uri()}{MARK}",
                             f"зерно: {self.seed}")


def _docstring_nodes(tree: ast.AST) -> set:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                found.add(id(first.value))
    return found


def mode_ro_copies(root: Path) -> list:
    """`файл:строка` строковых констант и частей f-строк с `?mode=ro` вне
    функции `db_readonly` модуля `orchestrator/store.py`; докстринги не в счёт."""
    copies = []
    for top in ("orchestrator", "scripts"):
        for path in sorted((root / top).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            docs = _docstring_nodes(tree)
            parents = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and MARK in node.value) or id(node) in docs:
                    continue
                inside = False
                up = parents.get(node)
                while up is not None:
                    if (isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and up.name == "db_readonly"
                            and isinstance(parents.get(up), ast.Module)):
                        inside = True
                    up = parents.get(up)
                if not (inside and rel == "orchestrator/store.py"):
                    copies.append(f"{rel}:{node.lineno}")
    return copies


class ModeRoLintTest(unittest.TestCase):
    """AC-4: строка `?mode=ro` — только в `store.db_readonly`."""

    def test_ac4_mode_ro_only_inside_store_db_readonly(self):
        """Разбор AST всех `.py` каталогов `orchestrator/` и `scripts/`
        репозитория.

        Наблюдение: ни одна строковая константа и ни одна часть f-строки с
        `?mode=ro` (докстринги модулей, классов и функций не в счёт) не
        лежит вне функции `db_readonly` модуля `orchestrator/store.py`.

        Ловит мутацию: возвращена своя копия открытия `?mode=ro` мимо `store.db_readonly`.
        """
        copies = mode_ro_copies(REPO)
        self.assertEqual(copies, [],
                         "копии открытия `?mode=ro` вне store.db_readonly: "
                         + ", ".join(copies))


if __name__ == "__main__":
    unittest.main()
