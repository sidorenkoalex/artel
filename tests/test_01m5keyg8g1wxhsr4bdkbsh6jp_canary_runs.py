"""Команда `canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]`: история прошедших прогонов канарейки из `canary_runs`.

Группа: долгоживущий
Красен до реализации: подкоманды `canary runs` нет — `artel.py canary runs …` уходит в разбор прогона канарейки и отказывает «нужен параметр --k»: заголовков прогонов нет, тексты отказов разбора не те, справка подкоманду не называет, константы `canary.CANARY_RUNS_DEFAULT_COUNT` нет.

Связка, которую держит файл: «публичный вход `artel.main()` с argv
`canary runs …` — таблица `canary_runs` БД песочницы — каталог диагностики
под корнем пульта». Песочница — `tests.sandbox.InitializedTmpRootTest`:
пути `config` во временном каталоге, БД со схемой (прогрета `init`).
Строки прогонов заводятся прямым `INSERT` в `canary_runs` песочницы с явным
`created_at` (формат `store.now()`); таблица перед вставкой заводится тем же
ленивым путём, что у читателя (`store.all_canary_runs`).

Ожидаемые строки вывода собираются по формату требования 4 SPEC (`NULL` —
`—`, деньги — два знака). Пустые строки вывода при сверке отбрасываются,
хвостовые пробелы строк — тоже.

Метки `run_stamp`, имена шаблонов, id задач, стоимости, вердикты и даты
порождаются от зерна; зерно печатается и входит в текст каждого провала.

AC-1 (сверка причины отказа с `canary._acceptance_summary`) и AC-12
(подмена `canary._live_dir`) требуют закрытых имён `orchestrator` и
поэтому живут в разовом файле планки задачи.
"""
import contextlib
import io
import random
import re
import socket
import sqlite3
import string
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, store
from tests.sandbox import InitializedTmpRootTest

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
CREATED_FORMAT = "%Y-%m-%d %H:%M:%SZ"
USAGE = "canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]"
EMPTY = "прогонов канарейки нет"
SINCE_REFUSAL = "canary runs: --since ждёт дату ГГГГ-ММ-ДД"
OLD_PARSER_REFUSAL = "нужен параметр --k"
HEADER_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z  ")
COLUMNS = ("run_stamp", "title", "task_id", "steps", "cost_usd",
           "review_iterations", "escalations", "outcome",
           "expected_escalation", "actual_escalation", "marker_mismatch",
           "created_at", "main_sha", "verdict", "set_name", "models_summary",
           "acceptance_route", "autogate_refusal", "escalation_roles")


def stamp_refusal(value: str) -> str:
    return f"canary runs: run_stamp {value} не по шаблону ГГГГММДДTЧЧММССZ"


def absent_refusal(value: str) -> str:
    return f"canary runs: прогона {value} нет"


def incompatible_refusal(value: str) -> str:
    return f"canary runs: --since и {value} несовместимы"


def text(value) -> str:
    return "—" if value is None else str(value)


def money(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def header_line(stamp: str, rows: list) -> str:
    """Заголовок прогона по требованию 4; `rows` — строки группы по `id`."""
    first = rows[0]
    sha = "—" if first["main_sha"] is None else first["main_sha"][:8]
    green = sum(1 for r in rows if r["verdict"] == "green")
    total = sum(r["cost_usd"] or 0 for r in rows)
    return (f"{stamp}  набор={text(first['set_name'])}  sha={sha}  "
            f"задач={len(rows)}  зелёных={green}  ${total:.2f}")


def task_line(row: dict) -> str:
    """Строка задачи по требованию 4 (с отступом в два пробела)."""
    line = (f"  {row['title']}  {row['task_id']}  вердикт={text(row['verdict'])}"
            f"  исход={text(row['outcome'])}  ${money(row['cost_usd'])}"
            f"  шагов={text(row['steps'])}"
            f"  ревью-итераций={text(row['review_iterations'])}"
            f"  эскалаций={text(row['escalations'])}")
    if row["escalation_roles"]:
        line += f" (роли: {row['escalation_roles']})"
    if row["marker_mismatch"] == 1:
        line += "  [расхождение маркера]"
    return line


class CanaryRunsCommandTest(InitializedTmpRootTest):
    """Таблица `canary_runs` песочницы, наполняемая прямой вставкой."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used_stamps = set()
        self.used_ids = set()
        self.next_created = datetime(2030, 1, 1, tzinfo=timezone.utc)
        store.all_canary_runs(store.db())

    # ------------------------------------------------------------ фикстуры

    def msg(self, note) -> str:
        return f"зерно: {self.seed}; {note}"

    def token(self, n: int = 8) -> str:
        return "".join(self.rng.choice(string.ascii_lowercase) for _ in range(n))

    def stamp(self) -> str:
        while True:
            moment = datetime(2031, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=self.rng.randrange(300 * 24 * 3600))
            value = moment.strftime(STAMP_FORMAT)
            if value not in self.used_stamps:
                self.used_stamps.add(value)
                return value

    def task_id(self) -> str:
        alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        while True:
            value = "01" + "".join(self.rng.choice(alphabet) for _ in range(24))
            if value not in self.used_ids:
                self.used_ids.add(value)
                return value

    def created(self) -> str:
        self.next_created += timedelta(seconds=self.rng.randrange(1, 600))
        return self.next_created.strftime(CREATED_FORMAT)

    def row(self, stamp: str, **fields) -> dict:
        """Строка `canary_runs` со случайными значениями; `fields` — поверх."""
        values = {
            "run_stamp": stamp, "title": f"canary-{self.token()}",
            "task_id": self.task_id(), "steps": self.rng.randrange(1, 30),
            "cost_usd": self.rng.randrange(1, 2000) / 100,
            "review_iterations": self.rng.randrange(0, 4),
            "escalations": self.rng.randrange(0, 3),
            "outcome": self.rng.choice(["merged", "escalated", "timeout"]),
            "expected_escalation": None, "actual_escalation": 0,
            "marker_mismatch": 0, "created_at": self.created(),
            "main_sha": f"{self.rng.randrange(16 ** 40):040x}",
            "verdict": self.rng.choice(["green", "red"]),
            "set_name": config.CANARY_DEFAULT_SET, "models_summary": None,
            "acceptance_route": None, "autogate_refusal": None,
            "escalation_roles": self.rng.choice([None, ""]),
        }
        values.update(fields)
        return values

    def insert(self, *rows: dict) -> None:
        conn = store.db()
        for values in rows:
            conn.execute(
                f"INSERT INTO canary_runs ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in COLUMNS)})",
                tuple(values[c] for c in COLUMNS))
        conn.commit()

    def cli(self, *argv: str) -> tuple:
        """(код выхода, stdout+stderr) `artel.main()` с argv Оператора."""
        out = io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if isinstance(exc.code, str):
                    out.write(f"\n{exc.code}")
                    code = 1
                else:
                    code = exc.code or 0
        return code, out.getvalue()

    @staticmethod
    def lines(output: str) -> list:
        return [line.rstrip() for line in output.splitlines() if line.strip()]

    def headers(self, output: str) -> list:
        """`run_stamp` заголовков вывода по порядку."""
        return [line.split("  ", 1)[0] for line in self.lines(output)
                if HEADER_RE.match(line)]

    def groups(self, output: str) -> dict:
        """`run_stamp` -> строки вывода под его заголовком (без заголовка)."""
        result, current = {}, None
        for line in self.lines(output):
            if HEADER_RE.match(line):
                current = line.split("  ", 1)[0]
                result[current] = []
            elif current is not None:
                result[current].append(line)
        return result

    @staticmethod
    def task_lines(group: list) -> list:
        return [line for line in group
                if line.startswith("  ") and not line.startswith("   ")]

    # -------------------------------------------------------------- тесты

    def test_ac2_groups_ordered_by_run_stamp_not_by_id(self):
        """Прогон с самым ранним `run_stamp` вставлен последним, строки двух других перемежаются по `id`.

        Заголовки идут по убыванию `run_stamp`, строки задач внутри группы —
        по возрастанию `id`; второй вариант — строки трёх прогонов вставлены
        в случайном порядке.

        Ловит мутацию: группы упорядочены по наибольшему (или наименьшему)
        `id` группы либо по `created_at` вместо `run_stamp` — порядок
        заголовков в выводе становится «старый прогон первым»; строки
        группы выведены в обратном порядке `id` — порядок `task_id` под
        заголовком меняется."""
        for variant in ("перемежение", "случайный порядок"):
            with self.subTest(variant=variant):
                store.db().execute("DELETE FROM canary_runs").connection.commit()
                old, mid, new = sorted(self.stamp() for _ in range(3))
                plan = [new, mid, new, mid, old, old]
                if variant == "случайный порядок":
                    plan = [old, old, mid, mid, new, new]
                    self.rng.shuffle(plan)
                rows = [self.row(s) for s in plan]
                self.insert(*rows)
                code, out = self.cli("canary", "runs")
                self.assertEqual(code, 0, self.msg(out))
                self.assertEqual(self.headers(out), [new, mid, old],
                                 self.msg(f"план {plan}; вывод:\n{out}"))
                groups = self.groups(out)
                for s in (new, mid, old):
                    expected = [task_line(r) for r in rows if r["run_stamp"] == s]
                    self.assertEqual(self.task_lines(groups[s]), expected,
                                     self.msg(f"группа {s}; вывод:\n{out}"))

    def test_ac3_default_shows_newest_ten_runs(self):
        """Двенадцать прогонов вставлены в случайном порядке; без аргументов видны десять с наибольшими `run_stamp`.

        Ловит мутацию: отбор «последних» по `id` вместо `run_stamp` — в выводе
        оказывается прогон с малым `run_stamp`, вставленный поздно; срез без
        предела или с пределом на строки, а не на прогоны (по две строки в
        прогоне) — число заголовков не 10."""
        self.assertEqual(canary.CANARY_RUNS_DEFAULT_COUNT, 10)
        count = canary.CANARY_RUNS_DEFAULT_COUNT
        stamps = [self.stamp() for _ in range(count + 2)]
        rows = [self.row(s) for s in stamps for _ in range(2)]
        self.rng.shuffle(rows)
        self.insert(*rows)
        code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        self.assertEqual(self.headers(out), sorted(stamps, reverse=True)[:count],
                         self.msg(f"вывод:\n{out}"))

    def test_ac4_since_filters_by_earliest_row_inclusive(self):
        """`--since <дата>` отбирает прогоны по самой ранней строке группы, граница `<дата> 00:00:00Z` включительно.

        Прогон с самой ранней строкой ровно в полночь даты выводится, прогон
        позже даты — тоже; прогон, начавшийся за секунду до полуночи и
        имеющий строку после неё, не выводится; прогон целиком раньше даты
        не выводится.

        Ловит мутацию: сравнение `>` вместо `>=` — прогон с полуночной
        строкой пропадает; отбор «есть строка не раньше даты» или по самой
        поздней строке — в выводе появляется прогон, начавшийся накануне;
        сравнение без времени суток с датой предыдущего дня — появляется
        прогон, целиком лежащий раньше даты."""
        day = datetime(2032, 1, 1, tzinfo=timezone.utc) + timedelta(
            days=self.rng.randrange(365))
        since = day.strftime("%Y-%m-%d")

        def at(delta: timedelta) -> str:
            return (day + delta).strftime(CREATED_FORMAT)

        exact, after, straddle, before = (self.stamp() for _ in range(4))
        self.insert(
            self.row(exact, created_at=at(timedelta(0))),
            self.row(exact, created_at=at(timedelta(hours=2))),
            self.row(straddle, created_at=at(timedelta(seconds=-1))),
            self.row(straddle, created_at=at(timedelta(hours=1))),
            self.row(after, created_at=at(timedelta(days=1, minutes=3))),
            self.row(before, created_at=at(timedelta(days=-3))),
            self.row(before, created_at=at(timedelta(days=-2))),
        )
        code, out = self.cli("canary", "runs", "--since", since)
        self.assertEqual(code, 0, self.msg(out))
        self.assertEqual(sorted(self.headers(out)), sorted([exact, after]),
                         self.msg(f"--since {since}; вывод:\n{out}"))

    def test_ac5_single_run_stamp_and_unknown_stamp(self):
        """`canary runs <run_stamp>` выводит один этот прогон; неизвестная метка по шаблону — отказ с ненулевым кодом.

        Ловит мутацию: позиционный аргумент проигнорирован (вывод по
        умолчанию) — в выводе три заголовка; отбор по префиксу или «не
        раньше метки» — лишние прогоны; неизвестная метка даёт пустой вывод
        «прогонов канарейки нет» с кодом 0 вместо отказа."""
        stamps = [self.stamp() for _ in range(3)]
        rows = [self.row(s) for s in stamps for _ in range(2)]
        self.rng.shuffle(rows)
        self.insert(*rows)
        chosen = self.rng.choice(stamps)
        code, out = self.cli("canary", "runs", chosen)
        self.assertEqual(code, 0, self.msg(out))
        self.assertEqual(self.headers(out), [chosen], self.msg(out))
        self.assertEqual(self.task_lines(self.groups(out)[chosen]),
                         [task_line(r) for r in rows if r["run_stamp"] == chosen],
                         self.msg(out))
        unknown = self.stamp()
        code, out = self.cli("canary", "runs", unknown)
        self.assertNotEqual(code, 0, self.msg(out))
        self.assertIn(absent_refusal(unknown), out, self.msg(out))
        self.assertEqual(self.headers(out), [], self.msg(out))

    def test_ac6_parse_refusals_before_db(self):
        """Каждый отказ разбора — ненулевой код, свой текст и ни одного вызова `store.db`.

        `store.db` подменён функцией, падающей при вызове; перебираются все
        argv критерия, метки — от зерна.

        Ловит мутацию: проверка аргументов после чтения БД — подмена
        `store.db` вызвана; `--since` без значения читает `rest[i + 1]` без
        сверки длины — `IndexError` вместо текста использования; значение
        проверено только регулярным выражением — `2026-02-30` проходит;
        метка проверена `match` вместо `fullmatch` — `…Zxx` проходит;
        повторный `--since` или второй позиционный молча берут последний —
        кода отказа нет."""
        a, b = self.stamp(), self.stamp()
        cases = [
            (["--bogus"], USAGE),
            ([a, b], USAGE),
            (["--since", "2026-10-01", "--since", "2026-10-02"], USAGE),
            (["--since"], USAGE),
            (["--since", "--x"], USAGE),
            (["--since", "20261023"], SINCE_REFUSAL),
            (["--since", "2026-1-5"], SINCE_REFUSAL),
            (["--since", "2026-02-30"], SINCE_REFUSAL),
            ([a + "xx"], stamp_refusal(a + "xx")),
            (["foo"], stamp_refusal("foo")),
            (["--since", "2026-10-01", a], incompatible_refusal(a)),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                boom = mock.Mock(side_effect=AssertionError("store.db вызван"))
                with mock.patch.object(store, "db", boom):
                    code, out = self.cli("canary", "runs", *argv)
                self.assertNotEqual(code, 0, self.msg(f"{argv}: {out}"))
                self.assertIn(expected, out, self.msg(f"{argv}: {out}"))
                self.assertFalse(boom.called, self.msg(f"{argv}: store.db вызван"))

    def test_ac7_empty_table_prints_single_line(self):
        """Пустая `canary_runs` (и до ленивого заведения, и после удаления строк) — одна строка «прогонов канарейки нет», код 0.

        Ловит мутацию: пустой вывод без строки либо отказ `sys.exit` на
        пустом отборе — вывод или код выхода расходятся; заголовок таблицы
        печатается и при пустом отборе — строк больше одной."""
        for variant in ("таблица не заведена", "таблица пуста"):
            with self.subTest(variant=variant):
                conn = store.db()
                if variant == "таблица не заведена":
                    conn.execute("DROP TABLE IF EXISTS canary_runs")
                else:
                    store.all_canary_runs(conn)
                    self.insert(self.row(self.stamp()))
                    conn = store.db()
                    conn.execute("DELETE FROM canary_runs")
                conn.commit()
                code, out = self.cli("canary", "runs")
                self.assertEqual(code, 0, self.msg(out))
                self.assertEqual(self.lines(out), [EMPTY], self.msg(out))

    def test_ac8_tables_row_counts_unchanged(self):
        """После `canary runs` (без аргументов, с `--since`, с меткой) число строк `steps`, `canary_runs`, `canary_baseline` прежнее.

        Ловит мутацию: команда пишет строку журнала «просмотр истории» —
        растёт `steps`; команда заводит или перезаписывает бейзлайн по
        прочитанным строкам — растёт `canary_baseline`."""
        stamps = [self.stamp() for _ in range(3)]
        self.insert(*[self.row(s) for s in stamps for _ in range(2)])
        store.set_canary_baseline(store.db(), f"canary-{self.token()}", 3, 1.5, 0)
        store.journal(store.db(), "", "operator", f"запись {self.token()}")

        def counts() -> dict:
            conn = store.db()
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("steps", "canary_runs", "canary_baseline")}

        before = counts()
        for argv in ([], ["--since", "2031-01-01"], [self.rng.choice(stamps)]):
            with self.subTest(argv=argv):
                code, out = self.cli("canary", "runs", *argv)
                self.assertEqual(code, 0, self.msg(out))
                self.assertEqual(counts(), before, self.msg(f"{argv}: {out}"))

    def test_ac9_header_from_first_row_null_and_marks(self):
        """`NULL` и пометки строки задачи: `sha=—`, значения заголовка из первой по `id` строки, `NULL` в `cost_usd` — ноль в сумме и `$—`.

        Строка с `marker_mismatch` = 1 и непустым `escalation_roles` несёт
        ` (роли: …)` и `  [расхождение маркера]`.

        Ловит мутацию: набор и sha заголовка берутся из последней строки
        группы — в заголовке чужие значения; `NULL` в `main_sha` срезается
        как строка — `sha=None`; `NULL` в `cost_usd` печатается как `$0.00`
        или ломает сумму (`TypeError`); пометка расхождения маркера или
        ролей пропущена — строка задачи короче ожидаемой."""
        stamp_null, stamp_diff = self.stamp(), self.stamp()
        roles = f"developer,{self.token(5)}"
        first_set, other_set = f"set-{self.token(4)}", f"set-{self.token(5)}"
        null_group = [
            self.row(stamp_null, main_sha=None, set_name=first_set),
            self.row(stamp_null, set_name=other_set, cost_usd=None,
                     marker_mismatch=1, escalation_roles=roles),
        ]
        diff_group = [
            self.row(stamp_diff, set_name=first_set),
            self.row(stamp_diff, set_name=other_set),
            self.row(stamp_diff, set_name=other_set, marker_mismatch=1),
        ]
        self.insert(*null_group, *diff_group)
        code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        lines = self.lines(out)
        for stamp, group in ((stamp_null, null_group), (stamp_diff, diff_group)):
            header = header_line(stamp, group)
            self.assertIn(header, lines, self.msg(f"ждали {header!r}; вывод:\n{out}"))
            self.assertEqual(self.task_lines(self.groups(out)[stamp]),
                             [task_line(r) for r in group], self.msg(out))
        null_header = next(line for line in lines if line.startswith(stamp_null))
        self.assertIn(f"набор={first_set}  sha=—  ", null_header, self.msg(out))
        marked = next(line for line in lines if null_group[1]["task_id"] in line)
        self.assertTrue(marked.endswith(f" (роли: {roles})  [расхождение маркера]"),
                        self.msg(out))
        self.assertIn("  $—  ", marked, self.msg(out))

    def test_ac10_diagnostics_line_only_when_dir_exists(self):
        """Каталог `.artel/canary/<run_stamp>/<task_id>/` есть у одной задачи прогона — строка `диагностика:` только под ней.

        Ловит мутацию: строка печатается безусловно — она появляется у
        задачи без каталога; путь абсолютный или с завершающей `/` —
        строка не совпадает; проверка каталога по `<task_id>` без
        `<run_stamp>` — строка появляется у задачи, чей каталог лежит под
        чужим прогоном."""
        stamp, other = self.stamp(), self.stamp()
        with_dir, without_dir, foreign_dir = (self.row(stamp) for _ in range(3))
        self.insert(with_dir, without_dir, foreign_dir)
        base = Path(config.ROOT) / ".artel" / "canary"
        (base / stamp / with_dir["task_id"]).mkdir(parents=True)
        (base / other / foreign_dir["task_id"]).mkdir(parents=True)
        code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        group = self.groups(out)[stamp]
        blocks, current = {}, None
        for line in group:
            if line.startswith("  ") and not line.startswith("   "):
                current = line
                blocks[current] = []
            elif current is not None:
                blocks[current].append(line)
        expected = f"    диагностика: .artel/canary/{stamp}/{with_dir['task_id']}"
        self.assertIn(expected, blocks.get(task_line(with_dir), []), self.msg(out))
        for row in (without_dir, foreign_dir):
            self.assertFalse(
                any("диагностика:" in line for line in blocks.get(task_line(row), [])),
                self.msg(f"{row['task_id']}; вывод:\n{out}"))
        self.assertIn(task_line(without_dir), blocks, self.msg(out))
        self.assertIn(task_line(foreign_dir), blocks, self.msg(out))

    def test_ac11_sqlite_connect_only_from_store(self):
        """`sqlite3.connect` подменён обёрткой, падающей при вызове вне `orchestrator.store`; команда печатает прогоны.

        Ловит мутацию: команда открывает `sqlite3.connect(config.DB)` сама,
        минуя `store.db()`, — обёртка фиксирует вызов из `orchestrator.canary`
        (или `orchestrator.artel`) и падает."""
        stamps = [self.stamp() for _ in range(2)]
        self.insert(*[self.row(s) for s in stamps])
        real_connect = sqlite3.connect
        outsiders = []

        def guarded(*args, **kwargs):
            caller = sys._getframe(1).f_globals.get("__name__")
            if caller != "orchestrator.store":
                outsiders.append(caller)
                raise AssertionError(f"sqlite3.connect из {caller}")
            return real_connect(*args, **kwargs)

        with mock.patch.object(sqlite3, "connect", guarded):
            code, out = self.cli("canary", "runs")
        self.assertEqual(outsiders, [], self.msg(out))
        self.assertEqual(code, 0, self.msg(out))
        self.assertEqual(self.headers(out), sorted(stamps, reverse=True), self.msg(out))

    def test_ac12_public_no_live_registry_no_network(self):
        """Публичная половина AC-12: при `canary.live_runs`, `subprocess.Popen` и `socket.socket`, падающих при вызове, команда печатает прогоны.

        Подмену закрытого `canary._live_dir` держит разовый файл планки.

        Ловит мутацию: команда сверяет прогоны с реестром живых через
        `canary.live_runs` или узнаёт sha через `git` (`subprocess`) —
        подмена вызвана, вывода прогонов нет."""
        stamps = [self.stamp() for _ in range(2)]
        self.insert(*[self.row(s) for s in stamps for _ in range(2)])
        live = mock.Mock(side_effect=AssertionError("canary.live_runs вызван"))
        popen = mock.Mock(side_effect=AssertionError("subprocess.Popen вызван"))
        sock = mock.Mock(side_effect=AssertionError("socket.socket вызван"))
        with mock.patch.object(canary, "live_runs", live), \
                mock.patch.object(subprocess, "Popen", popen), \
                mock.patch.object(socket, "socket", sock):
            code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        self.assertEqual(self.headers(out), sorted(stamps, reverse=True), self.msg(out))
        for name, fake in (("live_runs", live), ("Popen", popen), ("socket", sock)):
            self.assertFalse(fake.called, self.msg(f"{name} вызван"))

    def test_ac13_help_line_and_old_k_refusal(self):
        """Справка `artel.py --help` несёт строку `canary runs …` рядом со строкой `canary live`; `canary` без `--k` с прочими аргументами отказывает прежним текстом.

        Ловит мутацию: строка справки не добавлена или стоит вдали от
        `canary live` — сверка соседства падает; ветка `runs` перехватывает
        прочие аргументы (например, любой позиционный) — вместо «нужен
        параметр --k» печатается отказ `canary runs`."""
        code, out = self.cli("--help")
        self.assertEqual(code, 0, self.msg(out))
        lines = out.splitlines()
        runs_at = [i for i, line in enumerate(lines) if USAGE in line]
        live_at = [i for i, line in enumerate(lines) if "canary live" in line]
        self.assertTrue(runs_at, self.msg("строки canary runs в справке нет"))
        self.assertTrue(live_at, self.msg("строки canary live в справке нет"))
        self.assertTrue(
            any(abs(r - l) <= 2 for r in runs_at for l in live_at),
            self.msg(f"canary runs (строки {runs_at}) не рядом с canary live ({live_at})"))
        cases = [[self.token()], ["--set", self.token()],
                 ["--template", self.token()], ["--sha", f"{self.rng.randrange(16 ** 8):08x}"]]
        for argv in cases:
            with self.subTest(argv=argv):
                code, out = self.cli("canary", *argv)
                self.assertNotEqual(code, 0, self.msg(out))
                self.assertIn(OLD_PARSER_REFUSAL, out, self.msg(f"{argv}: {out}"))


if __name__ == "__main__":
    unittest.main()
