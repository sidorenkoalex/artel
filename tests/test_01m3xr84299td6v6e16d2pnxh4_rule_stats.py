"""Программа `scripts/test_rule_stats.py`: окно `--since`, четыре группы
задач, строка порога триггера №31 и открытие БД пульта только на чтение.

Группа: долгоживущий

Красен до реализации: программы `scripts/test_rule_stats.py` ещё нет —
каждый тест падает на проверке существования файла программы перед
прогоном.

Сценарий каждого теста — синтетическая БД пульта (`config.DB` песочницы
`RealGitSandbox`, таблица `steps`) и синтетический git-репозиторий
песочницы с bare-`origin`: мержи задач лежат только в `origin/main`
(локальная `main` остаётся на первом коммите), сеть не нужна. Программа
запускается как команда — `runpy` с `sys.argv = [программа, "--since",
дата]` из корня песочницы (`config.ROOT`, он же текущий каталог), вывод
читается из stdout.

Вывод группы читается так: блок группы начинается строкой, первая
непробельная часть которой — номер группы с точкой («1. …» … «4. …»,
как в черновике Оператора из ТЗ), и продолжается строками с отступом;
задача «попадает в группу N», когда её идентификатор есть в блоке N.
Строка порога — строка со словами «порог» и «достигнут» (без «не
достигнут»).

Идентификаторы задач, дата окна и промежутки между событиями
порождаются `random` при каждом запуске; зерно печатается и входит в
текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import runpy
import sqlite3
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import config
from orchestrator.advance_gates.test_integrity import TEST_INTEGRITY_REFUSAL_ACTION
from tests.sandbox import RealGitSandbox

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "test_rule_stats.py"

EXCEPTION_ACTION = "Разовое исключение: запись ANSWER в in_dev"
ESCALATED_ACTION = "state -> escalated"
DEVELOPER_ESCALATION = "эскалация от разработчика"
EXISTING_TESTS_FILE = "tests/test_existing_rule.py"

_ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_GROUP_HEAD = re.compile(r"^\s*([1-4])\.\s")


def group_blocks(output: str) -> dict:
    """{номер группы: текст блока} по правилу из докстринга модуля."""
    blocks: dict = {}
    current = None
    for line in output.splitlines():
        head = _GROUP_HEAD.match(line)
        if head:
            current = int(head.group(1))
            blocks.setdefault(current, []).append(line)
        elif current is not None and line[:1].isspace():
            blocks[current].append(line)
        else:
            current = None
    return {n: "\n".join(lines) for n, lines in blocks.items()}


def threshold_lines(output: str) -> list:
    lines = []
    for line in output.splitlines():
        low = line.lower()
        if "порог" in low and "достигнут" in low and "не достигнут" not in low:
            lines.append(line)
    return lines


class RuleStatsSandbox(RealGitSandbox):
    """Песочница: БД со схемой пульта, git с `origin` и рабочей веткой
    `work`, на которой копятся мержи задач до публикации в `origin/main`."""

    def setUp(self):
        super().setUp()
        seed = random.randrange(2 ** 32)
        print(f"зерно: {seed}")
        self.seed = seed
        self.rng = random.Random(seed)
        self.since = date(2025, 1, 1) + timedelta(days=self.rng.randrange(600))
        self.add_synced_origin()
        self.checkout("work", create=True)
        base = self.at_day(-30, 10)
        self.commit_files({EXISTING_TESTS_FILE: "def test_old():\n    pass\n",
                           "src_module.py": "VALUE = 0\n"},
                          base, "база: существующие тесты")

    # --- время и идентификаторы ---------------------------------------

    def at_day(self, days: int, hour: int = 0, minute: int = 0,
               second: int = 0) -> datetime:
        """Момент `days` суток от начала дня окна (UTC)."""
        start = datetime.combine(self.since, time(0, 0), tzinfo=timezone.utc)
        return start + timedelta(days=days, hours=hour, minutes=minute,
                                 seconds=second)

    def inside(self) -> datetime:
        """Случайный момент внутри окна, не раньше полудня первых суток."""
        return self.at_day(self.rng.randrange(1, 20), self.rng.randrange(12, 20),
                           self.rng.randrange(60))

    def new_id(self) -> str:
        return "01" + "".join(self.rng.choice(_ID_ALPHABET) for _ in range(24))

    def method_list(self) -> str:
        n = self.rng.randrange(1, 4)
        return ", ".join(
            f"tests/test_mod{self.rng.randrange(100)}.py::"
            f"Case{self.rng.randrange(100)}Test::test_m{self.rng.randrange(1000)}"
            for _ in range(n))

    def msg(self, output: str) -> str:
        return f"зерно {self.seed}, --since {self.since.isoformat()}; вывод:\n{output}"

    # --- журнал steps ---------------------------------------------------

    def put(self, task_id: str, when: datetime, action: str, detail: str = "",
            actor: str = "fsm") -> None:
        with contextlib.closing(sqlite3.connect(config.DB)) as conn:
            conn.execute(
                "INSERT INTO steps (task_id, ts, actor, action, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, when.strftime("%Y-%m-%d %H:%M:%SZ"), actor, action,
                 detail))
            conn.commit()

    def refusal(self, task_id: str, when: datetime) -> None:
        self.put(task_id, when, TEST_INTEGRITY_REFUSAL_ACTION,
                 f"из tests/ пропал метод {self.method_list()}", actor="orchestrator")

    def asked(self, task_id: str, when: datetime) -> None:
        self.put(task_id, when, ESCALATED_ACTION,
                 f"{DEVELOPER_ESCALATION}: прошу мандат — удалить "
                 f"{self.method_list()}; причина: механика заменена; замена: "
                 f"новый тест")

    # --- git ------------------------------------------------------------

    def dated(self, when: datetime):
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
        return mock.patch.dict(os.environ, {"GIT_AUTHOR_DATE": stamp,
                                            "GIT_COMMITTER_DATE": stamp})

    def commit_files(self, files: dict, when: datetime, message: str) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        with self.dated(when):
            self.git("add", "-A")
            self.git("commit", "-q", "-m", message)

    def merge_task(self, task_id: str, when: datetime, files: dict) -> None:
        """Ветка задачи от `work` с правкой `files`, мерж `--no-ff` в `work`
        с темой как у мержа пульта: «<id>: merge task/<id>-…»."""
        branch = f"task/{task_id.lower()}-slug"
        self.checkout(branch, create=True)
        self.commit_files(files, when - timedelta(minutes=5), f"{task_id}: код")
        self.checkout("work")
        with self.dated(when):
            self.git("merge", "-q", "--no-ff", branch, "-m",
                     f"{task_id}: merge {branch}")

    def merge_touching_existing_tests(self, task_id: str, when: datetime) -> None:
        self.merge_task(task_id, when, {
            EXISTING_TESTS_FILE: f"def test_old():\n    assert '{task_id}'\n"})

    def merge_adding_new_tests(self, task_id: str, when: datetime) -> None:
        self.merge_task(task_id, when, {
            f"tests/test_new_{task_id.lower()}.py": "def test_new():\n    pass\n"})

    def publish(self) -> None:
        """`work` -> `origin/main`; локальная `main` остаётся на первом
        коммите, рабочее дерево — на ней."""
        self.git("push", "-q", "origin", f"work:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.checkout(config.MAIN_BRANCH)

    # --- прогон ---------------------------------------------------------

    def run_stats(self) -> str:
        self.assertTrue(SCRIPT.is_file(), f"нет программы {SCRIPT}")
        out = io.StringIO()
        cwd = os.getcwd()
        argv = [str(SCRIPT), "--since", self.since.isoformat()]
        try:
            os.chdir(self.root)
            with mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(out):
                runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as exc:
            self.assertIn(exc.code, (0, None),
                          f"программа завершилась с кодом {exc.code}; "
                          f"{self.msg(out.getvalue())}")
        finally:
            os.chdir(cwd)
        return out.getvalue()

    def assert_in_group(self, output: str, task_id: str, group: int) -> None:
        self.assertIn(task_id, group_blocks(output).get(group, ""),
                      f"задача {task_id} не в группе {group}; {self.msg(output)}")

    def assert_not_in_group(self, output: str, task_id: str, group: int) -> None:
        self.assertNotIn(task_id, group_blocks(output).get(group, ""),
                         f"задача {task_id} в группе {group}; {self.msg(output)}")


class SinceWindowTest(RuleStatsSandbox):

    def test_ac3_since_bounds_journal_and_merges(self):
        """Отказ гейта и мерж до даты окна не считаются, с даты окна — считаются.

        Журнал: отказ гейта неослабления за секунду до полуночи накануне
        `--since` и отказ в первые секунды дня `--since`, ещё отказ внутри
        окна; git: мерж с правкой существующего файла `tests/` за пять
        суток до окна и такой же мерж внутри окна. Первые в выводе
        отсутствуют, вторые — в группах 3 и 2.

        Ловит мутацию: граница окна по дню строгая (дата записи `>`
        даты `--since` вместо «не раньше») — отказ в первые секунды дня
        окна пропадает из группы 3;
        либо фильтр окна не применён к журналу или к `git log` — отказ или
        мерж до окна появляется в выводе.
        """
        before, edge, inner = self.new_id(), self.new_id(), self.new_id()
        self.refusal(before, self.at_day(-1, 23, 59, 59))
        self.refusal(edge, self.at_day(0, 0, 0, self.rng.randrange(1, 30)))
        self.refusal(inner, self.inside())
        old_merge, new_merge = self.new_id(), self.new_id()
        self.merge_touching_existing_tests(old_merge, self.at_day(-5, 12))
        self.merge_touching_existing_tests(new_merge, self.inside())
        self.publish()

        output = self.run_stats()

        self.assert_in_group(output, edge, 3)
        self.assert_in_group(output, inner, 3)
        self.assert_in_group(output, new_merge, 2)
        self.assertNotIn(before, output, self.msg(output))
        self.assertNotIn(old_merge, output, self.msg(output))


class AskedFirstGroupTest(RuleStatsSandbox):

    def test_ac4_escalation_with_method_list_before_refusal_is_group_1(self):
        """Эскалация разработчика с перечнем методов без отказа или до отказа — группа 1.

        Задача A эскалировала с перечнем `tests/<файл>.py::<Класс>::<метод>`
        и отказа гейта не было; задача B эскалировала так же, а отказ
        гейта случился позже эскалации; задача C эскалировала без перечня
        методов. A и B в группе 1 и не в группе 3; C не в группе 1.

        Ловит мутацию: сравнение моментов перевёрнуто (эскалация считается
        предварительной, только если была ПОСЛЕ отказа) — B уходит из
        группы 1 в группу 3; либо проверка перечня методов снята — C
        попадает в группу 1.
        """
        no_refusal, refused_later, no_list = (self.new_id(), self.new_id(),
                                              self.new_id())
        t = self.inside()
        self.asked(no_refusal, t)
        self.asked(refused_later, t)
        self.refusal(refused_later, t + timedelta(minutes=self.rng.randrange(1, 300)))
        self.put(no_list, t, ESCALATED_ACTION,
                 f"{DEVELOPER_ESCALATION}: неясен формат вывода команды")
        self.publish()

        output = self.run_stats()

        self.assert_in_group(output, no_refusal, 1)
        self.assert_in_group(output, refused_later, 1)
        self.assert_not_in_group(output, no_refusal, 3)
        self.assert_not_in_group(output, refused_later, 3)
        self.assert_not_in_group(output, no_list, 1)


class BackgroundGroupTest(RuleStatsSandbox):

    def test_ac5_merge_modifying_existing_tests_is_background(self):
        """Мерж с правкой существующего файла `tests/` без отказа и вопроса — группа 2.

        Внутри окна смержены: задача F с правкой существующего файла
        `tests/` и без записей журнала; задача N, только добавившая новый
        файл `tests/`; задача S, правившая только файл вне `tests/`;
        задача Q с той же правкой `tests/` и эскалацией группы 1; задача R
        с той же правкой `tests/` и отказом гейта неослабления. В группе 2
        только F из них.

        Ловит мутацию: в фон берутся мержи с любым статусом файлов `tests/`
        (не только `M`) — N попадает в группу 2; diff считается не по
        `tests/` — S попадает в группу 2; исключение задач групп 1 и 3 из
        фона снято — Q или R попадают в группу 2; мержи берутся не из
        `origin/main`, а из локальной ветки — F пропадает из группы 2.
        """
        f, n, s, q, r = (self.new_id() for _ in range(5))
        t = self.inside()
        self.asked(q, t - timedelta(hours=2))
        self.refusal(r, t - timedelta(hours=1))
        order = [
            lambda when: self.merge_touching_existing_tests(f, when),
            lambda when: self.merge_adding_new_tests(n, when),
            lambda when: self.merge_task(s, when, {"src_module.py": f"VALUE = '{s}'\n"}),
            lambda when: self.merge_touching_existing_tests(q, when),
            lambda when: self.merge_touching_existing_tests(r, when),
        ]
        self.rng.shuffle(order)
        for i, merge in enumerate(order):
            merge(t + timedelta(hours=i + 1))
        self.publish()

        output = self.run_stats()

        self.assert_in_group(output, f, 2)
        for task_id in (n, s, q, r):
            self.assert_not_in_group(output, task_id, 2)


class SilentRefusalGroupTest(RuleStatsSandbox):

    def test_ac6_refusal_without_prior_escalation_is_group_3(self):
        """Отказ гейта без предварительной эскалации с перечнем — группа 3.

        Задача R получила отказ гейта неослабления и не эскалировала;
        задача L получила отказ, а эскалацию с перечнем методов подала
        ПОСЛЕ него. Обе в группе 3 и ни одна — в группе 1.

        Ловит мутацию: «эскалация была» вместо «эскалация была ДО отказа»
        (сравнение моментов снято) — L уходит в группу 1 вместо группы 3;
        ветка отказа без вопроса потеряна — R не попадает в группу 3.
        """
        silent, late = self.new_id(), self.new_id()
        t = self.inside()
        self.refusal(silent, t)
        self.refusal(late, t)
        self.asked(late, t + timedelta(minutes=self.rng.randrange(1, 300)))
        self.publish()

        output = self.run_stats()

        self.assert_in_group(output, silent, 3)
        self.assert_in_group(output, late, 3)
        self.assert_not_in_group(output, silent, 1)
        self.assert_not_in_group(output, late, 1)


class ExceptionGroupTest(RuleStatsSandbox):

    def test_ac7_one_off_exception_record_is_group_4(self):
        """Запись журнала «Разовое исключение: запись ANSWER в in_dev» — группа 4.

        Задача X несёт запись с этим действием; задача Y — только обычный
        переход состояния. X в группе 4, Y — нет.

        Ловит мутацию: признак группы 4 ищется не по действию записи
        (другая строка действия, поиск в `detail`) — X пропадает из группы
        4; группа 4 набирается из всех задач журнала — Y попадает в неё.
        """
        marked, plain = self.new_id(), self.new_id()
        t = self.inside()
        self.put(marked, t, EXCEPTION_ACTION,
                 "мандат передан Оператором вне escalated", actor="operator")
        self.put(plain, t, "state -> in_dev", "")
        self.publish()

        output = self.run_stats()

        self.assert_in_group(output, marked, 4)
        self.assert_not_in_group(output, plain, 4)


class ThresholdLineTest(RuleStatsSandbox):

    def test_ac8_threshold_line_only_with_nonempty_group_3(self):
        """Строка порога триггера №31 печатается, только когда группа 3 не пуста.

        Первый прогон: в окне есть задачи групп 1, 2 и 4, отказов гейта
        нет — строки порога нет. Затем в журнал добавлен отказ гейта без
        вопроса у новой задачи; второй прогон — строка порога есть.

        Ловит мутацию: строка порога печатается безусловно или по
        непустой группе 1/2/4 — она есть в первом прогоне; условие на
        группу 3 перевёрнуто или строка не печатается вовсе — её нет во
        втором прогоне.
        """
        asked, background, marked = self.new_id(), self.new_id(), self.new_id()
        t = self.inside()
        self.asked(asked, t)
        self.put(marked, t, EXCEPTION_ACTION, "", actor="operator")
        self.merge_touching_existing_tests(background, t + timedelta(hours=1))
        self.publish()

        quiet = self.run_stats()
        self.assertEqual([], threshold_lines(quiet), self.msg(quiet))

        self.refusal(self.new_id(), t + timedelta(hours=2))
        loud = self.run_stats()
        self.assertTrue(threshold_lines(loud), self.msg(loud))


class ReadOnlyDatabaseTest(RuleStatsSandbox):

    def test_ac9_run_leaves_db_unchanged_and_connection_is_read_only(self):
        """Прогон не меняет БД, а каждое соединение программы отказывает в записи.

        В БД записи всех четырёх групп, в `origin/main` — мерж с правкой
        `tests/`. На время прогона `sqlite3.connect` обёрнут: каждое
        открытое программой соединение сразу пробуется записью в `steps`
        внутри точки сохранения (откатывается при любом исходе). Пробы
        обязаны получить отказ «readonly», соединений — хотя бы одно; дамп
        БД до и после прогона совпадает.

        Ловит мутацию: БД открыта обычным `sqlite3.connect(path)` или через
        `store.db()` (чтение-запись, миграции) — проба записи проходит, а
        `store.db()` к тому же меняет схему или журнал; программа пишет в
        БД (журналирует свой прогон) — дамп после прогона расходится.
        """
        t = self.inside()
        self.asked(self.new_id(), t)
        self.refusal(self.new_id(), t)
        self.put(self.new_id(), t, EXCEPTION_ACTION, "", actor="operator")
        self.merge_touching_existing_tests(self.new_id(), t + timedelta(hours=1))
        self.publish()

        before = self.dump()
        real_connect = sqlite3.connect
        probes = []

        def spy_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            probes.append((args, self.write_refusal(conn)))
            return conn

        with mock.patch("sqlite3.connect", spy_connect):
            output = self.run_stats()
        after = self.dump()

        self.assertTrue(probes, f"программа не открыла БД; {self.msg(output)}")
        for args, refusal in probes:
            self.assertIn("readonly", refusal.lower(),
                          f"соединение {args!r} приняло запись или отказало не "
                          f"из-за режима только-чтение: {refusal!r}; "
                          f"{self.msg(output)}")
        self.assertEqual(before, after, f"БД изменилась; {self.msg(output)}")

    def dump(self) -> list:
        with contextlib.closing(sqlite3.connect(config.DB)) as conn:
            return list(conn.iterdump())

    @staticmethod
    def write_refusal(conn) -> str:
        """Текст отказа пробной записи в `steps` ('' — запись прошла);
        проба откатывается точкой сохранения."""
        conn.execute("SAVEPOINT rule_stats_probe")
        try:
            conn.execute("INSERT INTO steps (task_id, action) "
                         "VALUES ('probe', 'probe')")
            refusal = ""
        except sqlite3.Error as exc:
            refusal = str(exc) or type(exc).__name__
        finally:
            conn.execute("ROLLBACK TO rule_stats_probe")
            conn.execute("RELEASE rule_stats_probe")
        return refusal


if __name__ == "__main__":
    unittest.main()
