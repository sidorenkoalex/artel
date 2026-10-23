"""Пять читателей БД пульта открывают её через `store.db_readonly`, а их
отказы на отсутствующей или неоткрываемой БД остаются прежними.

Группа: долгоживущий

Красен до реализации: функции `store.db_readonly` ещё нет — подмена её шпионом в AC-6 падает `AttributeError`; AC-7 держит существующие тексты отказов и коды выхода и зелен с рождения.

Читатели берутся через публичные входы: `store.db_usable`,
`knowledge_cards.cmd_knowledge`, `preflight.cmd_preflight`,
`suite_run.cmd_suite_run` в процессе роли developer (полный прогон ему
отказан до любой записи — задача читается только открытием на чтение) и
`journal` программы `scripts/test_rule_stats.py`, загруженной `runpy`.
Пути `config` — во временном каталоге (`TmpRootTest`); признак роли в
окружении снимается либо ставится сценарием. Шпион `store.db_readonly`
запоминает вызов и поднимает собственное исключение — дальше открытия
БД ни один вход не идёт. Имена, id задач и тексты ошибок — от зерна;
зерно печатается и входит в текст провала.
"""
import contextlib
import inspect
import io
import os
import random
import runpy
import sqlite3
from datetime import date
from pathlib import Path
from unittest import mock

from orchestrator import config, knowledge_cards, preflight, store, suite_run
from tests.sandbox import TmpRootTest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "test_rule_stats.py"


class Opened(Exception):
    """Поднимает шпион `store.db_readonly`: вход дошёл до открытия БД."""


def _word(rng: random.Random, prefix: str) -> str:
    return prefix + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                            for _ in range(rng.randint(3, 8)))


class CallersSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.script = runpy.run_path(str(SCRIPT), run_name="rule_stats_under_test")

    @contextlib.contextmanager
    def environment(self, role: str | None = None):
        """Окружение без признака роли (или с ролью `role`), HOME — не дом роли."""
        with mock.patch.dict(os.environ, {"HOME": str(self.root / "home")}):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            os.environ.pop(config.ARTEL_TASK_ENV, None)
            if role is not None:
                os.environ[config.ARTEL_ROLE_ENV] = role
            yield

    def make_db_file(self) -> Path:
        """Файл БД на месте `config.DB` (содержимое шпиону неважно)."""
        conn = sqlite3.connect(str(config.DB))
        try:
            conn.execute("CREATE TABLE tasks (id TEXT)")
            conn.commit()
        finally:
            conn.close()
        return Path(config.DB)

    def task_arg(self) -> str:
        return "T" + "".join(self.rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                             for _ in range(self.rng.randint(3, 10)))


class OpenThroughDbReadonlyTest(CallersSandbox):
    """AC-6: каждый из пяти читателей зовёт `store.db_readonly`."""

    def test_ac6_each_reader_opens_through_store_db_readonly(self):
        """Файл БД есть; `store.db_readonly` подменён шпионом, который
        поднимает `Opened`. Пять входов зовутся по очереди.

        Наблюдение: каждый вход поднимает `Opened`, шпион зафиксировал ровно
        один вызов на вход; у `db_usable` в аргументах `rows=False`, у
        `journal` — `path`, равный переданному `db_path`, и `rows=False`.

        Ловит мутацию: в любом из пяти мест оставлена своя строка
        `sqlite3.connect(…?mode=ro…)` — вход открывает БД мимо шпиона,
        `Opened` нет (вход доходит до чтения и завершается иначе); либо
        `db_usable`/`journal` зовут `db_readonly` без `rows=False` —
        связанные аргументы шпиона несут `rows=True`.
        """
        db_path = self.make_db_file()
        real = store.db_readonly
        signature = inspect.signature(real)
        journal = self.script["journal"]
        entries = {
            "store.db_usable": (None, lambda: store.db_usable()),
            "knowledge": (None, lambda: knowledge_cards.cmd_knowledge(
                [self.task_arg(), f"{_word(self.rng, 'pkg_')}/mod.py"])),
            "preflight": (None, lambda: preflight.cmd_preflight(self.task_arg())),
            "suite-run": (config.STATE_ROLE["in_dev"],
                          lambda: suite_run.cmd_suite_run([self.task_arg()])),
            "test_rule_stats.journal": (None, lambda: journal(
                db_path, date(2026, self.rng.randint(1, 12), 1))),
        }
        for name, (role, call) in entries.items():
            with self.subTest(entry=name):
                with self.environment(role), \
                        mock.patch.object(store, "db_readonly", autospec=True,
                                          side_effect=Opened) as spy, \
                        contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(Opened,
                                           msg=f"зерно: {self.seed}: {name}"):
                        call()
                self.assertEqual(spy.call_count, 1,
                                 f"зерно: {self.seed}: {name}: {spy.call_args_list}")
                bound = signature.bind(*spy.call_args.args, **spy.call_args.kwargs)
                bound.apply_defaults()
                if name == "store.db_usable":
                    self.assertIs(bound.arguments["rows"], False,
                                  f"зерно: {self.seed}: {spy.call_args}")
                if name == "test_rule_stats.journal":
                    self.assertEqual(bound.arguments["path"], db_path,
                                     f"зерно: {self.seed}: {spy.call_args}")
                    self.assertIs(bound.arguments["rows"], False,
                                  f"зерно: {self.seed}: {spy.call_args}")


class RefusalsUnchangedTest(CallersSandbox):
    """AC-7: тексты отказов и коды выхода на отсутствующей БД."""

    def test_ac7_knowledge_and_preflight_missing_db(self):
        """Файла `config.DB` нет; `knowledge <id> <путь>` и `preflight <id>`
        зовутся вне шага роли.

        Наблюдение: `knowledge` — `SystemExit` с текстом
        «knowledge: БД пульта <config.DB> не найдена»; `preflight` — код 2 и
        «БД пульта <config.DB> не найдена» в stderr; файл БД не появился.

        Ловит мутацию: проверка `config.DB.is_file()` перед открытием снята
        («db_readonly сам откажет») — наружу выходит
        `sqlite3.OperationalError` вместо текста отказа и кода 2.
        """
        self.assertFalse(Path(config.DB).exists())
        with self.environment(), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                knowledge_cards.cmd_knowledge(
                    [self.task_arg(), f"{_word(self.rng, 'pkg_')}/mod.py"])
        self.assertEqual(ctx.exception.code,
                         f"knowledge: БД пульта {config.DB} не найдена",
                         f"зерно: {self.seed}")
        err = io.StringIO()
        with self.environment(), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                preflight.cmd_preflight(self.task_arg())
        self.assertEqual(ctx.exception.code, 2, f"зерно: {self.seed}")
        self.assertIn(f"БД пульта {config.DB} не найдена", err.getvalue(),
                      f"зерно: {self.seed}")
        self.assertFalse(Path(config.DB).exists(), f"зерно: {self.seed}")

    def test_ac7_rule_stats_journal_missing_and_unreadable_db(self):
        """`journal` программы `scripts/test_rule_stats.py`: на пути без
        файла и на существующем файле, открытие которого `sqlite3.connect`
        отказывает `sqlite3.OperationalError` со случайным текстом.

        Наблюдение: в первом случае — `StatsError` «нет БД пульта <путь>»;
        во втором — `StatsError` «БД пульта <путь> не прочитана: <текст>».

        Ловит мутацию: открытие `db_readonly` вынесено из `try … except
        sqlite3.Error` — сбой открытия выходит наружу `sqlite3.OperationalError`,
        а не `StatsError`.
        """
        journal = self.script["journal"]
        stats_error = self.script["StatsError"]
        since = date(2026, self.rng.randint(1, 12), 1)
        missing = self.root / f"{_word(self.rng, 'absent_')}.db"
        with self.assertRaises(stats_error) as ctx:
            journal(missing, since)
        self.assertEqual(str(ctx.exception), f"нет БД пульта {missing}",
                         f"зерно: {self.seed}")
        present = self.make_db_file()
        text = _word(self.rng, "сбой_")
        with mock.patch.object(sqlite3, "connect",
                               side_effect=sqlite3.OperationalError(text)):
            with self.assertRaises(stats_error) as ctx:
                journal(present, since)
        self.assertEqual(str(ctx.exception),
                         f"БД пульта {present} не прочитана: {text}",
                         f"зерно: {self.seed}")

    def test_ac7_db_usable_false_on_missing_and_open_error(self):
        """`store.db_usable` без файла `config.DB` и на существующем файле с
        таблицей `tasks`, открытие которого `sqlite3.connect` отказывает
        `sqlite3.Error`.

        Наблюдение: оба раза `False`, исключение наружу не выходит; без
        подмены `connect` тот же файл — `True` (предпосылка).

        Ловит мутацию: вызов `db_readonly` в `db_usable` вынесен из
        `try … except sqlite3.Error` — сбой открытия выходит наружу
        исключением вместо `False`.
        """
        self.assertIs(store.db_usable(), False, f"зерно: {self.seed}")
        self.make_db_file()
        self.assertIs(store.db_usable(), True, f"зерно: {self.seed}")
        error = self.rng.choice((sqlite3.OperationalError,
                                 sqlite3.DatabaseError, sqlite3.Error))
        with mock.patch.object(sqlite3, "connect",
                               side_effect=error(_word(self.rng, "e_"))):
            self.assertIs(store.db_usable(), False, f"зерно: {self.seed}")
