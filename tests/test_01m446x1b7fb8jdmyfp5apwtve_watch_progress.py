"""Дозор показывает ход живого шага роли: класс `pytest`, сводка, предупреждения, граница строк.

Группа: долгоживущий
Красен до реализации: у `watch` нет класса `pytest` (`--events pytest` — отказ «неизвестные классы событий», записи «прогон pytest» не печатаются), нет строк «ход шага»/«предупреждение» и констант `config.WATCH_*` — сценарии падают на отказе, на `AttributeError` констант или не дожидаются строки; сценарии «строки нет» без контрольной задачи были бы зелены, поэтому каждый из них ждёт контрольную строку живого шага.

Дозор гоняется публичным `watch.cmd_watch(argv)` в фоновом потоке (тем же
приёмом, что `tests/test_watch.py`), stdout потока перехвачен; настоящий
`time.sleep` с интервалом опроса 0.2 с. Песочница — `tests.sandbox.
RealGitSandbox`: у задачи настоящая ветка и рабочая копия по адресу
`workspace.path(<id>)` (`git worktree add` в клоне песочницы), коммиты
ветки датированы сутками раньше начала шага, если сценарий не говорит
иного. Живой шаг — запись «agent run started» с detail «…, лог: <path>, …»,
чья метка `ts` сдвинута в прошлое на нужное число секунд прямой правкой
строки `steps` песочницы; лог шага — файл песочницы, строки вызовов
инструментов в нём отрисованы самим провайдером Claude
(`providers.get("claude").parse_output_line(...).log_text`).

Пороги и периоды — от `config` (`WATCH_PROGRESS_PERIOD_MIN`,
`WATCH_NO_COMMIT_WARN_SEC`, `WATCH_STEP_COST_WARN_USD`,
`WATCH_PROGRESS_LINES_PER_HOUR`, `AGENT_TIMEOUT_SEC`), не литералами.
Идентификаторы задач, сдвиги времени, число изменённых файлов, маркеры
вызовов, итоговые строки и число лишних записей порождаются `random` при
каждом запуске; зерно печатается и входит в текст каждого провала.
"""
import os
import random
import re
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import config, providers, spend, store, watch, workspace
from tests.sandbox import RealGitSandbox

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
PYTEST_ACTION = "прогон pytest"
PROGRESS_ACTION = "ход шага"
WARNING_ACTION = "предупреждение"
NO_COMMIT = "нет коммитов"
STEP_COST = "стоимость шага"
FINISH_ACTIONS = ("agent run finished", "agent run TIMEOUT", "agent run FAILED")
ROLE = "developer"
INTERVAL = "0.2"
TS_FORMAT = "%Y-%m-%d %H:%M:%SZ"
MINUTES_RE = re.compile(r"(\d+)/(\d+) мин")


def random_task_id(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def marker(rng: random.Random, size: int = 10) -> str:
    """Маркер без цифр: число изменённых файлов в строке сводки ищется
    как отдельное число, маркеры не должны его подделать."""
    return "".join(rng.choice(LETTERS) for _ in range(size))


def ts_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        TS_FORMAT)


def claude_call_line(name: str, field: str, value: str) -> str:
    """Строка лога шага с вызовом инструмента — в отрисовке провайдера."""
    raw = ('{"type": "assistant", "message": {"role": "assistant", '
           '"content": [{"type": "tool_use", "id": "toolu_x", "name": "%s", '
           '"input": {"%s": "%s"}}]}}' % (name, field, value))
    return providers.get("claude").parse_output_line(raw).log_text


def usage_line(input_tokens: int) -> str:
    """Сырая строка потока Claude с usage — та форма, из которой
    `spend.partial_tokens_from_log` собирает разбивку лога шага."""
    return ('{"type": "assistant", "message": {"role": "assistant", '
            '"content": [{"type": "text", "text": "работаю"}], '
            '"usage": {"input_tokens": %d, "output_tokens": 0}}}\n'
            % input_tokens)


class WatchStream:
    """Потокобезопасный приёмник stdout фонового потока `watch`."""

    def __init__(self):
        self.chunks = []
        self.lock = threading.Lock()

    def write(self, s):
        with self.lock:
            self.chunks.append(s)

    def flush(self):
        pass

    def getvalue(self) -> str:
        with self.lock:
            return "".join(self.chunks)


class WatchProgressSandbox(RealGitSandbox):
    """Задачи с веткой и рабочей копией, шаги с прошлым началом, дозор в
    фоновом потоке."""

    def setUp(self):
        super().setUp()
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.use_catalog_fixture()
        self.use_role_map()
        # Отслеживаемые файлы и вся история main — сутками раньше любого
        # шага сценария: «коммит новее начала шага» появляется только там,
        # где сценарий кладёт его сам.
        self.old_date = ts_ago(86400).replace("Z", " +0000")
        for number in range(12):
            (self.root / f"file{chr(97 + number)}.txt").write_text(
                f"{number}\n", encoding="utf-8")
        self.git("add", "-A")
        with self.dated(self.old_date):
            self.git("commit", "--amend", "-q", "--no-edit",
                     "--date", self.old_date)
        self.add_synced_origin()
        self.stream = WatchStream()
        self.thread = None
        self.outcome = {}
        self.addCleanup(self.force_stop)

    # ------------------------------------------------------------ фикстуры

    def dated(self, stamp: str):
        return mock.patch.dict(os.environ, {"GIT_AUTHOR_DATE": stamp,
                                            "GIT_COMMITTER_DATE": stamp})

    def note(self, extra: str = "") -> str:
        return (f"зерно {self.seed}: {extra}\nвывод дозора:\n"
                f"{self.stream.getvalue()}")

    def new_task(self, worktree: bool = True) -> str:
        task_id = random_task_id(self.rng)
        branch = f"task/{task_id.lower()}-zadacha"
        store.insert_task(store.db(), task_id, "Задача", "in_dev", branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        if worktree:
            path = workspace.path(task_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.git("worktree", "add", "-q", "-b", branch, str(path))
        return task_id

    def change_files(self, task_id: str, count: int) -> None:
        """`count` отслеживаемых файлов рабочей копии задачи изменены и не
        закоммичены (ветка не ушла от main)."""
        path = workspace.path(task_id)
        for name in self.rng.sample(sorted(p.name for p in path.glob("file*.txt")),
                                    count):
            (path / name).write_text(f"правка {marker(self.rng)}\n",
                                     encoding="utf-8")

    def commit_now(self, task_id: str) -> None:
        """Коммит ветки задачи с датой «сейчас» — новее начала шага."""
        path = workspace.path(task_id)
        (path / "filea.txt").write_text(f"коммит {marker(self.rng)}\n",
                                        encoding="utf-8")
        self.git("-C", str(path), "add", "-A")
        self.git("-C", str(path), "commit", "-q", "-m", "коммит шага")

    def write_log(self, text: str) -> Path:
        config.LOGS.mkdir(parents=True, exist_ok=True)
        path = config.LOGS / f"shag-{marker(self.rng)}.log"
        path.write_text(text, encoding="utf-8")
        return path

    def journal_at(self, task_id: str, actor: str, action: str, detail: str,
                   ago: float) -> None:
        """Запись журнала с меткой `ago` секунд назад."""
        conn = store.db()
        store.journal(conn, task_id, actor, action, detail)
        row_id = store.task_steps(conn, task_id)[-1]["id"]
        conn.execute("UPDATE steps SET ts=? WHERE id=?", (ts_ago(ago), row_id))
        conn.commit()

    def start_step(self, task_id: str, ago: float, log_text: str = "",
                   role: str = ROLE) -> Path:
        """Запись «agent run started» `ago` секунд назад; лог шага — файл
        с `log_text`."""
        log = self.write_log(log_text)
        detail = (f"попытка 1/{config.AGENT_ATTEMPTS}, model=model-x, "
                  f"лог: {log}, промпт: {log.with_suffix('.prompt.txt')}, "
                  f"окружение: песочница")
        self.journal_at(task_id, role, "agent run started", detail, ago)
        return log

    # --------------------------------------------------------------- дозор

    def start(self, argv: list) -> None:
        def worker():
            old = sys.stdout
            sys.stdout = self.stream
            try:
                watch.cmd_watch(argv)
                self.outcome["exit"] = None
            except SystemExit as exc:
                self.outcome["exit"] = exc.code
            except BaseException as exc:  # noqa: BLE001 — диагностика
                self.outcome["exception"] = exc
            finally:
                sys.stdout = old

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def force_stop(self) -> None:
        if self.thread is None or not self.thread.is_alive():
            return
        conn = store.db()
        conn.execute("UPDATE tasks SET state='killed'")
        conn.commit()
        self.thread.join(timeout=5.0)

    def watch_tasks(self, *task_ids: str) -> None:
        self.start(["--tasks", ",".join(task_ids), "--interval", INTERVAL])

    def check_alive(self) -> None:
        if "exception" in self.outcome:
            self.fail(self.note(f"поток watch упал: {self.outcome['exception']!r}"))
        if "exit" in self.outcome:
            self.fail(self.note(f"watch завершился: {self.outcome['exit']!r}"))

    def wait_until(self, predicate, what: str, timeout: float = 12.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check_alive()
            if predicate():
                return
            time.sleep(0.05)
        self.fail(self.note(f"не дождались: {what}"))

    def hold(self, seconds: float) -> None:
        """Несколько итераций опроса подряд."""
        time.sleep(seconds)
        self.check_alive()

    def lines(self, task_id: str, actor: str, action: str) -> list:
        needle = f"  {task_id}  {actor}  {action}"
        return [line for line in self.stream.getvalue().splitlines()
                if needle in line]

    def summaries(self, task_id: str) -> list:
        return self.lines(task_id, "watch", PROGRESS_ACTION)

    def warnings(self, task_id: str, kind: str) -> list:
        return [line for line in self.lines(task_id, "watch", WARNING_ACTION)
                if kind in line]

    def progress_lines(self, task_id: str) -> list:
        """Строки под границей: класс `pytest`, сводки, предупреждения."""
        return [line for line in self.stream.getvalue().splitlines()
                if f"  {task_id}  " in line and (
                    f"  {PYTEST_ACTION}  " in line
                    or f"  watch  {PROGRESS_ACTION}" in line
                    or f"  watch  {WARNING_ACTION}" in line)]

    @staticmethod
    def detail_of(line: str) -> str:
        return line.split("  | ", 1)[1] if "  | " in line else ""


def period_sec() -> int:
    return config.WATCH_PROGRESS_PERIOD_MIN * 60


class Ac3PytestEventClassTest(WatchProgressSandbox):

    def random_summary(self) -> str:
        return (f"{self.rng.randint(1, 30)} failed, "
                f"{self.rng.randint(1, 900)} passed in "
                f"{self.rng.randint(1, 900)}.{self.rng.randint(10, 99)}s")

    def test_ac3_tasks_selector_prints_pytest_line_by_default(self):
        """`watch --tasks <id>` без `--events`: новая запись «прогон pytest»
        печатается строкой «<ts>  <id>  <actor>  прогон pytest  | <строка>».

        Ловит мутацию: класс `pytest` есть в `_EVENT_CLASSES`, но не
        включён в `_DEFAULT_EVENTS` — без `--events` строка не появится;
        либо строка собирается своим форматом, а не `_print_line` — строка
        не совпадёт посимвольно.
        """
        task_id = self.new_task(worktree=False)
        self.watch_tasks(task_id)
        self.hold(0.5)
        detail = self.random_summary()
        store.journal(store.db(), task_id, ROLE, PYTEST_ACTION, detail)
        row = store.task_steps(store.db(), task_id)[-1]
        expected = f"{row['ts']}  {task_id}  {ROLE}  {PYTEST_ACTION}  | {detail}"
        self.wait_until(lambda: expected in self.stream.getvalue().splitlines(),
                        f"строка {expected!r}")

    def test_ac3_observation_selector_prints_pytest_line_by_default(self):
        """`watch --observation <ID>` без `--events` печатает запись «прогон
        pytest» наблюдаемой задачи тем же форматом.

        Ловит мутацию: новый класс подключён только к явному `--events`, а
        режим наблюдения идёт по прежнему набору по умолчанию — строки нет.
        """
        task_id = self.new_task(worktree=False)
        session_id = f"sessiya-{marker(self.rng)}"
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": session_id}):
            observation_id = store.register_observation(
                store.db(), config.DEFAULT_TARGET, "klient", "chat",
                session_id, [task_id])
            self.addCleanup(store.stop_observation, store.db(), observation_id)
            self.start(["--observation", observation_id, "--interval", INTERVAL])
            self.hold(0.5)
            detail = self.random_summary()
            store.journal(store.db(), task_id, ROLE, PYTEST_ACTION, detail)
            row = store.task_steps(store.db(), task_id)[-1]
            expected = (f"{row['ts']}  {task_id}  {ROLE}  {PYTEST_ACTION}  "
                        f"| {detail}")
            self.wait_until(
                lambda: expected in self.stream.getvalue().splitlines(),
                f"строка {expected!r}")

    def test_ac3_events_pytest_is_accepted_and_prints(self):
        """`--events pytest` принимается: дозор работает и печатает запись
        «прогон pytest».

        Ловит мутацию: класс не добавлен в `_EVENT_CLASSES` — `--events
        pytest` даёт отказ «неизвестные классы событий» и поток завершается;
        либо `_matches_class` не знает класса — строка не печатается.
        """
        task_id = self.new_task(worktree=False)
        self.start(["--tasks", task_id, "--events", "pytest",
                    "--interval", INTERVAL])
        self.hold(0.5)
        detail = self.random_summary()
        store.journal(store.db(), task_id, ROLE, PYTEST_ACTION, detail)
        self.wait_until(
            lambda: f"  {task_id}  {ROLE}  {PYTEST_ACTION}  | {detail}"
            in self.stream.getvalue(), "строка «прогон pytest»")

    def test_ac3_unknown_class_refusal_lists_pytest(self):
        """Неизвестный класс у `--events` — отказ, перечисляющий все
        доступные классы, среди них `pytest`.

        Ловит мутацию: класс `pytest` распознаётся отдельной веткой мимо
        `_EVENT_CLASSES`, и перечень отказа его не называет.
        """
        task_id = self.new_task(worktree=False)
        unknown = f"klass-{marker(self.rng)}"
        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--tasks", task_id, "--events", unknown])
        message = str(cm.exception.code)
        self.assertIn(unknown, message, self.note(message))
        available = message.split("доступны", 1)[-1]
        for name in ("pytest", "transitions", "refusals", "gates", "steps",
                     "budget", "alerts", "stops", "ci"):
            self.assertIn(name, available, self.note(message))


class Ac4ProgressSummaryTest(WatchProgressSandbox):

    def tool_calls_log(self) -> tuple:
        """Лог шага: пять коротких вызовов с маркерами, затем длинный
        вызов последним, вперемешку с текстом агента. Возврат — (текст
        лога, маркеры старых вызовов, маркер предпоследнего вызова, текст
        длинного вызова в отрисовке без «· »)."""
        old = [marker(self.rng) for _ in range(3)]
        recent = [marker(self.rng) for _ in range(2)]
        long_pattern = marker(self.rng, 70)
        lines = []
        for mark in old:
            lines.append(claude_call_line("Read", "file_path", f"src/{mark}.py"))
            lines.append("смотрю дальше\n")
        lines.append(claude_call_line("Bash", "command", f"ls {recent[0]}"))
        lines.append(claude_call_line("Bash", "command", f"ls {recent[1]}"))
        long_line = claude_call_line("Grep", "pattern", long_pattern)
        lines.append(long_line)
        return "".join(lines), old, recent[1], long_line.strip().lstrip("· ")

    def test_ac4_one_summary_with_minutes_calls_and_changed_files(self):
        """Живой шаг идёт ≥ N минут: ровно одна сводка, с минутами шага,
        последними вызовами и числом изменённых файлов, не длиннее 240.

        Шаг начат N минут и 5–90 с назад; в рабочей копии задачи изменены
        и не закоммичены K (4–9) отслеживаемых файлов; в логе шага шесть
        вызовов инструментов. За несколько итераций опроса — ровно одна
        строка «ход шага» с actor `watch`: «M/<полные> мин» (M — прошедшие
        минуты, полные — `AGENT_TIMEOUT_SEC` в минутах), предпоследний
        вызов есть, три самых старых — нет, от длинного последнего вызова
        в строке не больше 40 символов подряд, K — отдельным числом, вся
        строка ≤ 240 символов.

        Ловит мутацию: сводка печатается на каждой итерации (нет учёта
        выданного k) — строк станет больше одной; полные минуты литералом
        или из другой константы — «M/<полные>» не совпадёт; берутся первые
        вызовы лога вместо последних — найдётся маркер старого вызова;
        аргумент вызова не сжимается — длинный вызов войдёт подстрокой
        длиннее 40; число файлов берётся из коммитов ветки — K не найдётся.
        """
        task_id = self.new_task()
        changed = self.rng.randint(4, 9)
        self.change_files(task_id, changed)
        log_text, old, recent, long_call = self.tool_calls_log()
        extra = self.rng.randint(5, 90)
        self.start_step(task_id, period_sec() + extra, log_text)
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.summaries(task_id), "строка сводки")
        self.hold(1.2)
        lines = self.summaries(task_id)
        self.assertEqual(len(lines), 1, self.note("сводок не ровно одна"))
        line = lines[0]
        detail = self.detail_of(line)
        self.assertLessEqual(len(line), 240, self.note(f"длина {len(line)}"))

        minutes = MINUTES_RE.search(detail)
        self.assertIsNotNone(minutes, self.note("нет «M/<полные> мин»"))
        full = config.AGENT_TIMEOUT_SEC // 60
        self.assertEqual(int(minutes.group(2)), full, self.note("полные минуты"))
        low = config.WATCH_PROGRESS_PERIOD_MIN
        self.assertTrue(low <= int(minutes.group(1)) <= low + 2,
                        self.note(f"прошедшие минуты {minutes.group(1)}"))

        self.assertIn(recent, detail, self.note("нет предпоследнего вызова"))
        for mark in old:
            self.assertNotIn(mark, detail, self.note(
                "в сводке вызов старше трёх последних"))
        for start in range(len(long_call) - 40):
            self.assertNotIn(long_call[start:start + 41], detail, self.note(
                "вызов в сводке длиннее 40 символов"))

        rest = MINUTES_RE.sub(" ", detail)
        self.assertRegex(rest, rf"(?<!\d){changed}(?!\d)", self.note(
            f"нет числа изменённых файлов {changed}"))

    def test_ac4_next_summary_only_after_next_multiple(self):
        """Следующая сводка — только после следующего кратного N.

        Шаг начат за 4–6 с до отметки 2·N минут: первая сводка выходит
        сразу (прошло ≥ N), до отметки 2·N на итерациях опроса новых сводок
        нет, после неё появляется ровно вторая, и дальше их снова не
        прибавляется.

        Ловит мутацию: следующая сводка ждёт не кратного N, а N минут от
        момента ЗАПУСКА дозора (или от прошлой сводки) — вторая строка не
        выйдет за время сценария; либо выданное k не запоминается — сводки
        идут на каждой итерации.
        """
        task_id = self.new_task()
        lead = self.rng.uniform(4.0, 6.0)
        began = time.monotonic()
        self.start_step(task_id, 2 * period_sec() - lead,
                        claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.summaries(task_id), "первая сводка")
        remaining = lead - (time.monotonic() - began) - 1.5
        if remaining > 0.4:
            self.hold(remaining)
            self.assertEqual(len(self.summaries(task_id)), 1, self.note(
                "вторая сводка до отметки 2·N"))
        self.wait_until(lambda: len(self.summaries(task_id)) >= 2,
                        "вторая сводка после отметки 2·N", timeout=15.0)
        self.hold(1.2)
        self.assertEqual(len(self.summaries(task_id)), 2, self.note(
            "после второй сводки появились лишние"))


class Ac5NoLiveStepTest(WatchProgressSandbox):

    def test_ac5_no_summary_or_warning_without_live_step(self):
        """Без живого шага — ни сводок, ни предупреждений.

        Три задачи в одном дозоре, у каждой изменённые файлы, нет коммитов
        новее «начала», в логе — usage дороже порога: A — записи «agent run
        started» нет вовсе; B — шаг начат 40 минут назад и закрыт случайной
        из «agent run finished»/«TIMEOUT»/«FAILED»; C — контроль: живой шаг
        в тех же условиях. Дождавшись сводки C и ещё нескольких итераций,
        у A и B нет ни одной строки «ход шага» и «предупреждение».

        Ловит мутацию: живой шаг определяется по последней «agent run
        started» без сверки с более поздней записью завершения — у B
        появятся сводка и предупреждения; начало шага при отсутствии записи
        берётся из создания задачи — у A появится сводка.
        """
        elapsed = config.WATCH_NO_COMMIT_WARN_SEC + 300
        tokens = self.rng.randint(5, 9) * 10 ** 7
        log_text = usage_line(tokens) + claude_call_line("Bash", "command", "ls")
        task_a, task_b, task_c = (self.new_task() for _ in range(3))
        for task_id in (task_a, task_b, task_c):
            self.change_files(task_id, 3)
        self.journal_at(task_a, "operator", "created", "задача", elapsed + 60)
        self.start_step(task_b, elapsed, log_text)
        self.journal_at(task_b, ROLE, self.rng.choice(FINISH_ACTIONS),
                        "итог шага", elapsed - 60)
        self.start_step(task_c, elapsed, log_text)

        self.watch_tasks(task_a, task_b, task_c)
        self.wait_until(lambda: self.summaries(task_c), "сводка контрольной задачи")
        self.hold(1.2)
        for task_id, name in ((task_a, "A"), (task_b, "B")):
            for action in (PROGRESS_ACTION, WARNING_ACTION):
                self.assertEqual(self.lines(task_id, "watch", action), [],
                                 self.note(f"задача {name}: строка «{action}» "
                                           f"без живого шага"))


class Ac6NoCommitWarningTest(WatchProgressSandbox):

    def test_ac6_warning_once_per_step_and_again_for_new_step(self):
        """Живой шаг ≥ WATCH_NO_COMMIT_WARN_SEC без коммитов ветки новее начала.

        Предупреждение «нет коммитов» печатается ровно один раз — на
        следующих итерациях того же шага повтора нет. Затем шаг закрыт
        «agent run finished», начат новый (тоже давно и без коммитов) —
        предупреждение выходит снова, ровно второе.

        Ловит мутацию: признак «выдано за шаг» не ведётся — строка на каждой
        итерации; признак ведётся на задачу, а не на шаг (не сбрасывается
        новой «agent run started») — второго предупреждения не будет; порог
        сравнивается в минутах периода сводки, а не в секундах
        `WATCH_NO_COMMIT_WARN_SEC` — строки не будет вовсе.
        """
        task_id = self.new_task()
        first_ago = config.WATCH_NO_COMMIT_WARN_SEC + self.rng.randint(120, 240)
        self.start_step(task_id, first_ago,
                        claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.warnings(task_id, NO_COMMIT),
                        "предупреждение «нет коммитов»")
        self.hold(1.2)
        self.assertEqual(len(self.warnings(task_id, NO_COMMIT)), 1,
                         self.note("повтор предупреждения в том же шаге"))

        self.journal_at(task_id, ROLE, "agent run finished", "итог шага",
                        first_ago - 60)
        self.start_step(task_id, config.WATCH_NO_COMMIT_WARN_SEC + 30,
                        claude_call_line("Bash", "command", "ls"))
        self.wait_until(lambda: len(self.warnings(task_id, NO_COMMIT)) >= 2,
                        "предупреждение нового шага")
        self.hold(1.2)
        self.assertEqual(len(self.warnings(task_id, NO_COMMIT)), 2,
                         self.note("повтор предупреждения во втором шаге"))

    def test_ac6_no_warning_when_branch_has_newer_commit(self):
        """Живой шаг ≥ WATCH_NO_COMMIT_WARN_SEC, но у ветки есть коммит новее
        начала шага — предупреждения «нет коммитов» нет; контроль работы
        дозора — сводка того же шага.

        Ловит мутацию: коммиты сверяются не с веткой задачи (а с main или
        вовсе не сверяются) — предупреждение выйдет при свежем коммите.
        """
        task_id = self.new_task()
        self.commit_now(task_id)
        self.start_step(task_id, config.WATCH_NO_COMMIT_WARN_SEC + 120,
                        claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.summaries(task_id), "сводка шага")
        self.hold(1.5)
        self.assertEqual(self.warnings(task_id, NO_COMMIT), [], self.note(
            "предупреждение при коммите новее начала шага"))


class Ac7StepCostWarningTest(WatchProgressSandbox):

    def cost_of(self, role: str, text: str):
        tokens, _saw = spend.partial_tokens_from_log(self.write_log(text))
        return spend.partial_cost_usd(role, tokens)

    def usage_lines(self) -> tuple:
        """(дорогая, дешёвая) строки usage: по тарифу роли шага первая
        стоит вдвое больше порога, вторая — не больше 0.4 порога."""
        threshold = config.WATCH_STEP_COST_WARN_USD
        unit = self.cost_of(ROLE, usage_line(10 ** 6))
        self.assertTrue(unit, self.note("тариф фикстуры роли не разрешился"))
        dear = usage_line(int(10 ** 6 * threshold * 2 / unit) + 1)
        cheap = usage_line(max(1, int(10 ** 6 * threshold * 0.4 / unit)))
        self.assertGreater(self.cost_of(ROLE, dear), threshold)
        self.assertLessEqual(self.cost_of(ROLE, cheap), threshold)
        return dear, cheap

    def test_ac7_cost_warning_once_above_threshold_none_below(self):
        """Стоимость шага по usage лога: выше порога — одно предупреждение,
        не выше — ни одного.

        Два живых шага одного дозора, начатых 1–4 минуты назад (сводок и
        «нет коммитов» ещё нет): A — usage, лёгший в лог, стоит больше
        `WATCH_STEP_COST_WARN_USD` по тарифу роли шага; B — не больше 0.4
        порога. У A ровно одна строка «предупреждение» со «стоимость шага»
        за несколько итераций, у B — ни одной.

        Ловит мутацию: признак «выдано» не ведётся — у A строка на каждой
        итерации; порог не применяется (любая стоимость больше нуля) —
        строка у B; стоимость считается только по финальному итогу запуска,
        а не по usage, уже лёгшему в лог, — у A строки не будет.
        """
        dear, cheap = self.usage_lines()
        task_a, task_b = self.new_task(), self.new_task()
        call = claude_call_line("Bash", "command", "ls")
        self.start_step(task_a, self.rng.randint(60, 240), dear + call)
        self.start_step(task_b, self.rng.randint(60, 240), cheap + call)
        self.watch_tasks(task_a, task_b)
        self.wait_until(lambda: self.warnings(task_a, STEP_COST),
                        "предупреждение «стоимость шага»")
        self.hold(1.2)
        self.assertEqual(len(self.warnings(task_a, STEP_COST)), 1,
                         self.note("повтор предупреждения о стоимости"))
        self.assertEqual(self.warnings(task_b, STEP_COST), [],
                         self.note("предупреждение ниже порога"))

    def test_ac7_unresolved_cost_gives_no_warning(self):
        """Стоимость не разрешилась — предупреждения «стоимость шага» нет.

        Дорогой usage в логе живого шага, но карта исполнителей сценария
        снимает ярус у роли шага: `spend.partial_cost_usd` по ней даёт
        `None`. Шаг идёт ≥ N минут — контроль работы дозора его сводкой;
        после неё за несколько итераций предупреждения о стоимости нет.

        Ловит мутацию: `None` стоимости трактуется как превышение (или
        подменяется расчётом по чужому тарифу) — строка появится; либо
        сравнение `None > порог` роняет поток дозора — `TypeError`.
        """
        dear, _cheap = self.usage_lines()
        self.use_role_map(roles={ROLE: {"model_tier": None}})
        self.assertIsNone(self.cost_of(ROLE, dear),
                          self.note("тариф роли без яруса разрешился"))
        task_id = self.new_task()
        self.start_step(task_id, period_sec() + self.rng.randint(5, 60),
                        dear + claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.summaries(task_id), "сводка шага")
        self.hold(1.2)
        self.assertEqual(self.warnings(task_id, STEP_COST), [], self.note(
            "предупреждение при неразрешённой стоимости"))


class Ac8LinesPerHourLimitTest(WatchProgressSandbox):

    def flood(self, task_id: str, count: int) -> list:
        details = [f"{self.rng.randint(1, 9)} failed, {number} passed in "
                   f"{self.rng.randint(1, 99)}.{self.rng.randint(10, 99)}s"
                   for number in range(100, 100 + count)]
        conn = store.db()
        for detail in details:
            store.journal(conn, task_id, ROLE, PYTEST_ACTION, detail)
        return details

    def journal_pytest(self, task_id: str) -> list:
        return [row["detail"] for row in store.task_steps(store.db(), task_id)
                if row["action"] == PYTEST_ACTION]

    def test_ac8_pytest_lines_capped_journal_untouched(self):
        """Записей «прогон pytest» больше границы — печатается ровно граница.

        Живой шаг начат 1–4 минуты назад (своих сводок и предупреждений
        нет); после запуска дозора в журнал ложится
        `WATCH_PROGRESS_LINES_PER_HOUR` + 2..6 записей «прогон pytest».
        Печатается ровно граница строк класса `pytest`; все записи остаются
        в журнале.

        Ловит мутацию: граница не применяется к классу `pytest` (считает
        только сводки) — напечатаются все записи; граница режет журнал, а
        не печать (лишние записи удаляются) — журнал станет короче.
        """
        limit = config.WATCH_PROGRESS_LINES_PER_HOUR
        task_id = self.new_task()
        self.start_step(task_id, self.rng.randint(60, 240),
                        claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.hold(0.6)
        details = self.flood(task_id, limit + self.rng.randint(2, 6))
        self.wait_until(lambda: len(self.progress_lines(task_id)) >= limit,
                        f"{limit} строк класса pytest")
        self.hold(1.2)
        self.assertEqual(len(self.progress_lines(task_id)), limit,
                         self.note("напечатано не ровно граница строк"))
        self.assertEqual(self.journal_pytest(task_id), details,
                         self.note("журнал изменился"))

    def test_ac8_limit_counts_pytest_summaries_and_warnings_together(self):
        """Граница общая для класса `pytest`, сводок и предупреждений.

        Живой шаг идёт дольше `WATCH_NO_COMMIT_WARN_SEC` без коммитов
        (выйдут сводка и предупреждение «нет коммитов»); после первой
        сводки в журнал ложится граница + 2..6 записей «прогон pytest».
        Строк всех трёх видов вместе — ровно граница; записи журнала целы.

        Ловит мутацию: у каждого вида свой счётчик границы — строк класса
        `pytest` напечатается граница целиком сверх сводки и
        предупреждения.
        """
        limit = config.WATCH_PROGRESS_LINES_PER_HOUR
        task_id = self.new_task()
        self.start_step(task_id, config.WATCH_NO_COMMIT_WARN_SEC + 60,
                        claude_call_line("Bash", "command", "ls"))
        self.watch_tasks(task_id)
        self.wait_until(lambda: self.summaries(task_id), "сводка шага")
        details = self.flood(task_id, limit + self.rng.randint(2, 6))
        self.wait_until(lambda: len(self.progress_lines(task_id)) >= limit,
                        f"{limit} строк хода шага")
        self.hold(1.2)
        self.assertEqual(len(self.progress_lines(task_id)), limit,
                         self.note("строк хода шага не ровно граница"))
        self.assertTrue(self.summaries(task_id), self.note())
        self.assertEqual(self.journal_pytest(task_id), details,
                         self.note("журнал изменился"))


if __name__ == "__main__":
    unittest.main()
