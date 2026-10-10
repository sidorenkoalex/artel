"""Предел полного прогона `notes` из профиля и сигнал «длительность близка к пределу».

Группа: долгоживущий
Красен до реализации: `notes` гоняет набор без предела профиля и не называет источник предела в выводе (AC-1, AC-2), а сигнала «длительность близка к пределу» нет ни у гейта, ни у `suite-run`, ни у `notes` — ни записи журнала, ни строки вывода, ни алерта kind=trigger, ни константы порога в строке docs/triggers.md (AC-3, AC-5..AC-10); зелёны с рождения test_ac4_* (прогон в 70% предела сигнала не даёт и сегодня) и часть AC-5 об исходе прогона.

Гейт — настоящий `acceptance.full_suite` на временном дереве с
настоящим pytest (образец — `tests/test_01m4araxf7vss5xz8c99bx8de2_
suite_observation.py`); `suite-run` — фоновое тело команды
`suite_run.background` на том же дереве (рабочая копия и дерево
приложений подменены временным каталогом); `notes` — настоящий
`notes.cmd_doc_commit` пути конфигурации Оператора на стенде с bare
`origin` и клоном артели (`tests/sandbox.py::RealGitSandbox`,
`clone_artel_from_origin`). Предел полного прогона задаётся полем
`full_suite_timeout_sec` профиля тестов артели в `config.TARGETS`
песочницы, источник предела сверяется с `project_profile.full_suite_limit`.

Часы подменены (`time.monotonic`, `time.perf_counter`, `time.time`):
каждый тест набора дерева прогона, исполняясь, дописывает строку в файл
отметок, и каждая новая строка сдвигает часы процесса пульта на заданную
сценарием долю предела. Так прогон, длящийся секунды, «длится» 85% или
70% предела, не дожидаясь его. Пределы и доли — от зерна; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, alerts, appendix_tree, catalog, config,
                          notes, project_profile, store, suite_lock, suite_run)
from tests.sandbox import (ARTEL_TEST_PROFILE, RealGitSandbox, TmpRootTest,
                           capture, clone_artel_from_origin, init_bare_origin)

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
NEAR = "длительность близка к пределу"
NEAR_ALERT = re.compile(r"(?i)близк\w* к пределу")
LOAD = re.compile(r"(?i)нагрузк|load")
PROFILE_HEAD = "    test_profile:\n"
LIMIT_FIELD = re.compile(r"^ *full_suite_timeout_sec:.*\n", re.MULTILINE)
# Запас на настоящее время прогона поверх сдвига часов: настоящий pytest
# дерева сценария идёт секунды, пределы сценариев — от 1000 с.
SLACK = 120.0
ACK_RESOLUTION = "отложено до следующей задачи о скорости набора"

REAL_MONOTONIC = time.monotonic
REAL_PERF_COUNTER = time.perf_counter
REAL_TIME = time.time


def probe_suite(marks: Path, kind: str) -> str:
    """Текст набора `tests/` дерева прогона: зелёный и красный тест пишут
    отметку прогона; висящий тест держится дольше предела и отметки не
    пишет."""
    mark = (f"    with open({str(marks)!r}, 'a', encoding='utf-8') as fh:\n"
            f"        fh.write('прогон\\n')\n")
    return {
        "green": f"def test_probe():\n{mark}    assert True\n",
        "red": f"def test_probe():\n{mark}    assert False, 'красный намеренно'\n",
        "timeout": "import time\n\n\ndef test_probe():\n    time.sleep(60)\n",
    }[kind]


class ShiftedClock:
    """Часы процесса пульта: каждая новая строка файла отметок сдвигает их
    вперёд на `shift` секунд — прогон «длится» столько, сколько задал
    сценарий."""

    def __init__(self, marks: Path):
        self.marks = marks
        self.shift = 0.0
        self.seen = 0
        self.offset = 0.0

    def current_offset(self) -> float:
        try:
            count = len(self.marks.read_text(encoding="utf-8").splitlines())
        except FileNotFoundError:
            count = 0
        if count > self.seen:
            self.offset += (count - self.seen) * self.shift
            self.seen = count
        return self.offset

    def monotonic(self) -> float:
        return REAL_MONOTONIC() + self.current_offset()

    def perf_counter(self) -> float:
        return REAL_PERF_COUNTER() + self.current_offset()

    def time(self) -> float:
        return REAL_TIME() + self.current_offset()


class NearLimitMixin:
    """Общее обоих стендов: зерно, часы, предел в профиле, чтение сигнала."""

    def start_clock(self) -> None:
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        marks_dir = tempfile.mkdtemp(prefix="artel-marks-")
        self.addCleanup(shutil.rmtree, marks_dir, ignore_errors=True)
        self.marks = Path(marks_dir) / "marks.txt"
        self.clock = ShiftedClock(self.marks)
        for name in ("monotonic", "perf_counter", "time"):
            patcher = mock.patch(f"time.{name}", getattr(self.clock, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        workers = mock.patch.object(config, "FULL_SUITE_WORKERS", 1)
        workers.start()
        self.addCleanup(workers.stop)

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"

    def random_limit(self) -> int:
        return self.rng.randint(1000, 3000)

    def set_profile_limit(self, limit: int | None,
                          with_profile: bool = True) -> tuple[int, str]:
        """Поле `full_suite_timeout_sec` профиля артели в `config.TARGETS`
        песочницы (`None` — без поля; `with_profile=False` — без профиля
        вовсе); возвращает действующий предел и источник пульта."""
        text = LIMIT_FIELD.sub("", config.TARGETS.read_text(encoding="utf-8"))
        if not with_profile:
            text = text.replace(ARTEL_TEST_PROFILE, "")
            self.assertNotIn(PROFILE_HEAD, text, self.msg("профиль не снят"))
        elif limit is not None:
            self.assertIn(PROFILE_HEAD, text, self.msg("нет профиля артели"))
            text = text.replace(
                PROFILE_HEAD,
                f"{PROFILE_HEAD}      full_suite_timeout_sec: {limit}\n", 1)
        config.TARGETS.write_text(text, encoding="utf-8")
        return project_profile.full_suite_limit(config.DEFAULT_TARGET)

    def near_alerts(self) -> list:
        return [row for row in alerts.open_alerts(store.db(), "trigger")
                if NEAR_ALERT.search(f"{row['source']} {row['message']}")]

    def assert_near_alert(self) -> dict:
        found = self.near_alerts()
        self.assertEqual(len(found), 1, self.msg(
            f"открытых алертов «{NEAR}»: {[dict(r) for r in found]}"))
        row = found[0]
        self.assertEqual(row["kind"], "trigger", self.msg())
        self.assertEqual(row["target"], config.DEFAULT_TARGET, self.msg())
        return row

    def assert_signal_data(self, text: str, limit: int, source: str,
                           ratio: float) -> None:
        """Текст сигнала несёт длительность (сдвиг часов сценария плюс
        настоящие секунды прогона), предел, источник предела и нагрузку."""
        self.assertRegex(text, rf"(?<![\d.,]){limit}(?![\d]|[.,]\d)",
                         self.msg(f"нет предела {limit}: {text}"))
        self.assertIn(source, text, self.msg(f"нет источника: {text}"))
        low = ratio * limit
        numbers = [float(n.replace(",", "."))
                   for n in re.findall(r"\d+(?:[.,]\d+)?", text)]
        self.assertTrue(any(low <= n <= low + SLACK for n in numbers),
                        self.msg(f"нет длительности ~{low:.0f} с: {text}"))
        self.assertRegex(text, LOAD, self.msg(f"нет нагрузки: {text}"))


class GateStand(NearLimitMixin, TmpRootTest):
    """Задача артели в БД и дерево прогона с настоящим pytest."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task = "T001"
        store.insert_task(self.conn, self.task, "Прогон у предела", "in_dev",
                          "task/t001-progon", config.DEFAULT_TARGET, 25.0)
        (self.root / "tests").mkdir(exist_ok=True)
        self.start_clock()

    def write_suite(self, kind: str) -> None:
        (self.root / "tests" / "test_probe.py").write_text(
            probe_suite(self.marks, kind), encoding="utf-8")

    def near_records(self) -> list:
        return [row for row in store.task_steps(self.conn, self.task)
                if NEAR in f"{row['action']} {row['detail']}".lower()]

    def run_gate(self, kind: str, ratio: float, limit: int):
        self.write_suite(kind)
        self.clock.shift = ratio * limit
        return acceptance.full_suite(self.root, self.task, fresh=True)

    def run_suite_command(self, ratio: float, limit: int) -> str:
        """Фоновое тело `suite-run` на дереве сценария с настоящим pytest."""
        self.write_suite("green")
        self.clock.shift = ratio * limit
        tree = appendix_tree.SuiteTree(self.root, "", "", "")
        with mock.patch.object(suite_run.workspace, "path",
                               return_value=self.root), \
                mock.patch.object(suite_run.workspace, "repo",
                                  return_value=self.root), \
                mock.patch.object(suite_run.appendix_tree, "suite_tree",
                                  return_value=contextlib.nullcontext(tree)):
            self.assertIsNone(suite_lock.acquire(self.task, 1))
            suite_run.background(self.task, "1", suite_run.MODE_FULL)
        result = config.LOGS / "suite-run" / self.task / "result.json"
        self.assertTrue(result.exists(), self.msg("отчёта suite-run нет"))
        return result.read_text(encoding="utf-8")


class GateNearLimitTest(GateStand):

    def test_ac3_gate_run_at_85_percent_journals_and_raises_alert(self):
        """Гейт: прогон в 85% предела профиля — запись журнала и алерт.

        Сценарий: предел профиля артели — случайный, зелёный прогон гейта
        `acceptance.full_suite` «длится» 85% предела. В журнале задачи
        появляется запись «длительность близка к пределу», несущая
        длительность, предел, источник предела и нагрузку, и открыт один
        алерт kind=trigger проекта.

        Ловит мутацию: сигнал считается от запасного предела
        `config.FULL_SUITE_TIMEOUT_SEC`, а не от действующего предела
        профиля, либо сравнение длительности стоит не с пределом, а с
        временем на тест — записи и алерта нет, либо запись не называет
        источник предела.
        """
        limit, source = self.set_profile_limit(self.random_limit())
        result = self.run_gate("green", 0.85, limit)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_GREEN,
                         self.msg(result.detail))
        records = self.near_records()
        self.assertEqual(len(records), 1, self.msg(str(
            [dict(r) for r in store.task_steps(self.conn, self.task)])))
        row = records[0]
        self.assert_signal_data(f"{row['action']} {row['detail']}", limit,
                                source, 0.85)
        self.assert_near_alert()

    def test_ac4_gate_run_at_70_percent_leaves_no_signal(self):
        """Гейт: прогон в 70% предела (и ниже) не даёт ни записи, ни алерта.

        Сценарий: случайный предел профиля, прогоны гейта «длятся» 70% и
        случайную долю ниже 72% предела.

        Ловит мутацию: порог сравнивается с половиной предела либо
        перевёрнут (`<` вместо `>=`) — запись «длительность близка к
        пределу» и алерт появляются у прогона, далёкого от предела.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        for ratio in (0.70, self.rng.uniform(0.3, 0.72)):
            with self.subTest(ratio=ratio):
                result = self.run_gate("green", ratio, limit)
                self.assertEqual(result.outcome, acceptance.FULL_SUITE_GREEN,
                                 self.msg(result.detail))
                self.assertEqual(self.near_records(), [], self.msg())
                self.assertEqual(self.near_alerts(), [], self.msg())

    def test_ac5_signal_does_not_change_run_outcome(self):
        """Сигнал не меняет исход: красный остаётся красным, таймаут — отказом.

        Сценарий: красный прогон гейта «длится» 85% предела — исход
        «красный прогон», не зелено, а запись журнала и алерт есть; зелёный
        прогон у предела остаётся зелёным; прогон, висящий дольше
        настоящего предела профиля в 3 с, остаётся отказом «таймаут
        прогона».

        Ловит мутацию: прогон у предела сигнал пишет, но исход гейта
        подменяется (красный проходит как «зелёный с предупреждением»,
        таймаут превращается в сигнал вместо отказа) либо красный прогон
        уходит из гейта раньше, чем сигнал записан.
        """
        limit, source = self.set_profile_limit(self.random_limit())
        red = self.run_gate("red", self.rng.uniform(0.8, 0.95), limit)
        self.assertFalse(red.green, self.msg(red.detail))
        self.assertEqual(red.outcome, acceptance.FULL_SUITE_RED,
                         self.msg(red.detail))
        self.assertEqual(len(self.near_records()), 1, self.msg())
        self.assert_near_alert()

        green = self.run_gate("green", 0.85, limit)
        self.assertTrue(green.green, self.msg(green.detail))
        self.assertEqual(green.outcome, acceptance.FULL_SUITE_GREEN,
                         self.msg(green.detail))

        self.set_profile_limit(3)
        timeout = self.run_gate("timeout", 0.0, 3)
        self.assertFalse(timeout.green, self.msg(timeout.detail))
        self.assertEqual(timeout.outcome, acceptance.FULL_SUITE_TIMEOUT,
                         self.msg(timeout.detail))

    def test_ac6_suite_run_at_85_percent_journals_and_raises_alert(self):
        """`suite-run`: прогон в 85% предела — запись журнала задачи и алерт.

        Сценарий: случайный предел профиля, фоновое тело `suite-run`
        гоняет набор дерева задачи, прогон «длится» 85% предела.

        Ловит мутацию: сигнал заведён только в узле гейта `full_suite`, а
        не в общей функции прогона, через которую идёт и `suite-run`, —
        записи «длительность близка к пределу» в журнале задачи и алерта
        после `suite-run` нет.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        report = self.run_suite_command(0.85, limit)
        self.assertGreaterEqual(len(self.near_records()), 1,
                                self.msg(report))
        self.assert_near_alert()

    def test_ac8_status_shows_alert_until_ack(self):
        """`status` показывает неподтверждённый алерт; ack его убирает.

        Сценарий: прогон гейта у предела поднимает алерт; вывод `status`
        содержит строку «…близка к пределу»; подтверждение алерта
        (`alerts.ack` с решением, как требует kind=trigger) — и в выводе
        `status` такой строки больше нет.

        Ловит мутацию: алерт заводится с kind, отличным от trigger
        (incident/threshold), — секция триггеров `status` его не
        показывает; либо сигнал пишет только журнал без алерта.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        self.run_gate("green", 0.85, limit)
        row = self.assert_near_alert()
        shown = capture(catalog.cmd_status)
        self.assertRegex(shown, NEAR_ALERT, self.msg(shown))
        self.assertIsNone(alerts.ack(store.db(), row["id"], "operator",
                                     ACK_RESOLUTION), self.msg())
        shown = capture(catalog.cmd_status)
        self.assertNotRegex(shown, NEAR_ALERT, self.msg(shown))

    def test_ac9_one_open_alert_per_target_until_ack(self):
        """Один открытый алерт на проект; после ack — новый.

        Сценарий: два прогона гейта подряд у предела (разные доли
        предела — разная длительность) дают две записи журнала, но один
        открытый алерт; алерт подтверждён; третий прогон у предела
        поднимает новый алерт (другой id).

        Ловит мутацию: каждый прогон у предела заводит алерт с текстом,
        несущим длительность, — дедуп `raise_alert` по тексту его не
        гасит, и открытых алертов становится два; либо открытость
        проверяется по любому, в том числе подтверждённому, алерту —
        после ack новый не поднимается.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        self.run_gate("green", 0.85, limit)
        first = self.assert_near_alert()
        self.run_gate("green", self.rng.uniform(0.86, 0.95), limit)
        self.assertEqual(len(self.near_records()), 2, self.msg())
        self.assertEqual(self.assert_near_alert()["id"], first["id"],
                         self.msg())
        self.assertIsNone(alerts.ack(store.db(), first["id"], "operator",
                                     ACK_RESOLUTION), self.msg())
        self.assertEqual(self.near_alerts(), [], self.msg())
        self.run_gate("green", 0.85, limit)
        self.assertEqual(len(self.near_records()), 3, self.msg())
        self.assertNotEqual(self.assert_near_alert()["id"], first["id"],
                            self.msg())

    def threshold_constant(self) -> list[tuple[object, str, float]]:
        """Константа порога: имя из строки docs/triggers.md, значение 80% в
        модуле зон задачи — (модуль, имя, значение)."""
        text = (CODE_ROOT / "docs" / "triggers.md").read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("|")]
        found = []
        for row in rows:
            for name in set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", row)):
                for module in (acceptance, suite_lock, notes):
                    value = getattr(module, name, None)
                    if (isinstance(value, (int, float))
                            and not isinstance(value, bool)
                            and value in (0.8, 80)):
                        found.append((module, name, float(value)))
        return found

    def test_ac10_threshold_is_named_constant_in_triggers_row(self):
        """Порог — именованная константа, названная в строке docs/triggers.md.

        Сценарий: в строках таблицы docs/triggers.md находится имя
        константы модуля зоны задачи со значением 80% (0.8 или 80). Её
        подмена на 90% гасит сигнал прогона в 85% предела (ни записи, ни
        алерта), подмена на 50% — зажигает сигнал прогона в 70% предела.

        Ловит мутацию: порог зашит литералом `0.8` в условии сигнала, а
        константа лишь объявлена — подмена константы исход не меняет; либо
        строка триггера в docs/triggers.md не называет константу — она не
        находится.
        """
        found = self.threshold_constant()
        self.assertTrue(found, self.msg(
            "в строках docs/triggers.md нет имени константы со значением "
            "80% из acceptance/suite_lock/notes"))
        limit, _ = self.set_profile_limit(self.random_limit())

        def patched(fraction: float) -> contextlib.ExitStack:
            stack = contextlib.ExitStack()
            for module, name, value in found:
                scale = value / 0.8
                stack.enter_context(
                    mock.patch.object(module, name, fraction * scale))
            return stack

        with patched(0.9):
            self.run_gate("green", 0.85, limit)
        self.assertEqual(self.near_records(), [], self.msg(str(found)))
        self.assertEqual(self.near_alerts(), [], self.msg(str(found)))

        with patched(0.5):
            self.run_gate("green", 0.70, limit)
        self.assertEqual(len(self.near_records()), 1, self.msg(str(found)))
        self.assert_near_alert()


BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""
CONFIG_REL = notes.DOC_COMMIT_CONFIG_PATHS[0]


class NotesStand(NearLimitMixin, RealGitSandbox):
    """Главная копия с bare `origin`, клон артели из него и набор `tests/`
    с тестом-отметкой: `doc-commit` пути конфигурации гоняет этот набор."""

    def setUp(self):
        super().setUp()
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        self.start_clock()
        self.origin = tempfile.mkdtemp(prefix="artel-origin-")
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        init_bare_origin(self.origin, self.git)
        self.git("remote", "add", "origin", self.origin)
        for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                          (CONFIG_REL, "developer:\n  model: opus\n"),
                          ("tests/test_probe.py",
                           probe_suite(self.marks, "green"))):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "стенд")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        clone_artel_from_origin(self.origin)
        self.sources = tempfile.mkdtemp(prefix="artel-src-")
        self.addCleanup(shutil.rmtree, self.sources, ignore_errors=True)
        self.commits = 0

    def doc_commit(self, ratio: float, limit: int) -> str:
        """`doc-commit` новой конфигурации; прогон набора «длится» долю
        `ratio` предела `limit`. Вывод — stdout и stderr вместе."""
        self.commits += 1
        source = Path(self.sources) / f"config-{self.commits}.yaml"
        source.write_text(f"developer:\n  model: m{self.commits}\n",
                          encoding="utf-8")
        self.clock.shift = ratio * limit
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            notes.cmd_doc_commit([CONFIG_REL, "--from", str(source),
                                  "--message", f"крутилка {self.commits}"])
        return buf.getvalue()

    def near_lines(self, output: str) -> list[str]:
        return [line for line in output.splitlines()
                if NEAR in line.lower()]


def passed_limit(spy: mock.MagicMock):
    """Предел, переданный в `acceptance.run_full_suite` последним вызовом
    (именованный `limit` либо шестой позиционный)."""
    call = spy.call_args
    if "limit" in call.kwargs:
        return call.kwargs["limit"]
    return call.args[5] if len(call.args) > 5 else None


class NotesNearLimitTest(NotesStand):

    def test_ac1_notes_takes_limit_from_project_profile(self):
        """`notes` берёт предел из профиля и называет источник в выводе.

        Сценарий: профиль артели несёт предел 1500 с, затем случайный
        предел; `doc-commit` конфигурации гоняет набор. Функция прогона
        получает именно предел профиля с источником пульта
        (`project_profile.full_suite_limit`), а вывод команды несёт строку
        с этим пределом и источником.

        Ловит мутацию: `notes` зовёт `acceptance.run_full_suite(work_dir)`
        без предела, как до задачи, — прогон получает запасные 900 с
        «config», а вывод не называет ни предела, ни источника.
        """
        for wanted in (1500, self.random_limit()):
            with self.subTest(limit=wanted):
                limit, source = self.set_profile_limit(wanted)
                self.assertEqual(limit, wanted, self.msg(source))
                with mock.patch.object(
                        notes.acceptance, "run_full_suite",
                        wraps=acceptance.run_full_suite) as spy:
                    output = self.doc_commit(0.0, limit)
                self.assertTrue(spy.called, self.msg(output))
                self.assertEqual(passed_limit(spy), (limit, source),
                                 self.msg(output))
                lines = [line for line in output.splitlines()
                         if source in line and re.search(
                             rf"(?<!\d){limit}(?!\d)", line)]
                self.assertTrue(lines, self.msg(output))

    def test_ac2_notes_without_profile_uses_config_limit(self):
        """`notes` без профиля: запасной предел `config.FULL_SUITE_TIMEOUT_SEC`.

        Сценарий: запись артели без `test_profile` вовсе; `doc-commit`
        конфигурации гоняет набор. Прогон получает запасной предел
        (явно `(config.FULL_SUITE_TIMEOUT_SEC, "config")` либо без
        предела — тогда его подставляет сама функция прогона), а вывод
        несёт строку с этим пределом и источником «config».

        Ловит мутацию: отсутствие профиля роняет команду отказом «профиль
        не прочитан» либо вывод называет источник только у предела
        профиля — строки с запасным пределом и «config» нет.
        """
        limit, source = self.set_profile_limit(None, with_profile=False)
        self.assertEqual((limit, source),
                         (config.FULL_SUITE_TIMEOUT_SEC, "config"))
        with mock.patch.object(notes.acceptance, "run_full_suite",
                               wraps=acceptance.run_full_suite) as spy:
            output = self.doc_commit(0.0, limit)
        self.assertTrue(spy.called, self.msg(output))
        self.assertIn(passed_limit(spy), (None, (limit, source)),
                      self.msg(output))
        lines = [line for line in output.splitlines()
                 if "config" in line and re.search(
                     rf"(?<!\d){limit}(?!\d)", line)]
        self.assertTrue(lines, self.msg(output))

    def test_ac4_notes_run_at_70_percent_prints_no_signal(self):
        """`notes`: прогон в 70% предела — ни строки сигнала, ни алерта.

        Сценарий: случайный предел профиля, `doc-commit` конфигурации,
        прогон набора «длится» 70% предела.

        Ловит мутацию: `notes` печатает строку «длительность близка к
        пределу» после любого прогона (условие порога пропущено) — строка
        и алерт появляются у прогона, далёкого от предела.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        output = self.doc_commit(0.70, limit)
        self.assertEqual(self.near_lines(output), [], self.msg(output))
        self.assertEqual(self.near_alerts(), [], self.msg(output))

    def test_ac7_notes_run_at_85_percent_prints_line_and_raises_alert(self):
        """`notes`: прогон в 85% предела — строка вывода с данными и алерт.

        Сценарий: случайный предел профиля, `doc-commit` конфигурации,
        прогон набора «длится» 85% предела. Вывод команды несёт строку
        «длительность близка к пределу» с длительностью, пределом,
        источником и нагрузкой; открыт алерт kind=trigger проекта артели.

        Ловит мутацию: `notes` гоняет набор без наблюдения прогона
        (длительность не измеряется) — строки нет; либо строка печатается,
        а алерт заводится только при наличии задачи — у `notes` алерта нет.
        """
        limit, source = self.set_profile_limit(self.random_limit())
        output = self.doc_commit(0.85, limit)
        lines = self.near_lines(output)
        self.assertEqual(len(lines), 1, self.msg(output))
        self.assert_signal_data(lines[0], limit, source, 0.85)
        self.assert_near_alert()

    def test_ac9_notes_second_run_prints_line_without_second_alert(self):
        """`notes`: второй прогон у предела — строка вывода, но не второй алерт.

        Сценарий: два `doc-commit` подряд у предела — каждый печатает
        строку «длительность близка к пределу», открытый алерт проекта
        один; после его подтверждения третий прогон у предела поднимает
        новый алерт.

        Ловит мутацию: `notes`, видя открытый алерт, молчит целиком
        (строки вывода нет) либо заводит второй алерт с новым текстом;
        или после ack новый алерт не поднимается.
        """
        limit, _ = self.set_profile_limit(self.random_limit())
        self.assertEqual(len(self.near_lines(self.doc_commit(0.85, limit))),
                         1, self.msg())
        first = self.assert_near_alert()
        output = self.doc_commit(self.rng.uniform(0.86, 0.95), limit)
        self.assertEqual(len(self.near_lines(output)), 1, self.msg(output))
        self.assertEqual(self.assert_near_alert()["id"], first["id"],
                         self.msg(output))
        self.assertIsNone(alerts.ack(store.db(), first["id"], "operator",
                                     ACK_RESOLUTION), self.msg())
        output = self.doc_commit(0.85, limit)
        self.assertEqual(len(self.near_lines(output)), 1, self.msg(output))
        self.assertNotEqual(self.assert_near_alert()["id"], first["id"],
                            self.msg(output))


if __name__ == "__main__":
    unittest.main()
