"""Время каждого теста полного прогона `suite-run` по отметкам времени строк
хода: чистый разбор `suite_durations.durations`, файл времени рядом с логом
прогона в файл, блок «самые медленные» в отчёте `suite-run`, неизменность
argv и окружения полного прогона.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/suite_durations.py нет (AC-1 падает на импорте), прогон в файл лога не оставляет файла `<лог>.durations.tsv` (AC-2, AC-3), отчёт suite-run без блока «самые медленные» (AC-5); тест AC-6 зелёный и до реализации — он держит прежние argv и окружение.

Прогоны AC-2, AC-3 и AC-6 — настоящий pytest с xdist интерпретатором пульта
по маленькому проекту во временном каталоге, через публичный
`acceptance.run_full_suite` (с `log=` он идёт в прогон в файл лога, как
`suite-run`); песочница путей `config` — `tests.sandbox.TmpRootTest`.
AC-5 держит связку «фоновый процесс `suite-run` — разбор — отчёт» на
настоящем git проекта песочницы (`tests.sandbox.RealGitSandbox`,
`make_project_repo`): `suite_run.background` с подменой публичного
`acceptance.run_full_suite`, кладущей вывод в лог и файл времени рядом.
Зерно печатается и входит в текст провала.
"""
import importlib
import json
import os
import random
import re
import string
import subprocess
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, config, project_profile, stack, store,
                          suite_lock, suite_run, targets, workspace)
from tests.sandbox import (RealGitSandbox, TmpRootTest, artel_target_entry,
                           make_project_repo)

OUTCOMES = ("PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL", "XPASS")
FAILING = ("FAILED", "ERROR")
REPORT_HEADER = "=" * 35 + " FAILURES " + "=" * 35
TIMEOUT_PREFIX = "прогон полного набора tests/ превысил "
LETTERS = string.ascii_lowercase
ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

FAST = "def test_{name}():\n    assert True\n"
SLEEPING = "import time\n\n\ndef test_{name}():\n    time.sleep({seconds})\n"


def durations_path(log: Path) -> Path:
    """`<имя лога без .log>.durations.tsv` рядом с логом."""
    log = Path(log)
    return log.with_name(log.name[:-len(".log")] + ".durations.tsv")


def read_durations(path: Path) -> dict:
    """(id узла, процесс) -> [исход, секунды] по строкам файла времени:
    повтор id в том же процессе суммируется, исход — худший."""
    rows: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        node, worker, outcome, seconds = line.split("\t")
        entry = rows.setdefault((node, worker), [outcome, 0.0])
        entry[1] += float(seconds)
        if entry[0] not in FAILING:
            entry[0] = outcome
    return rows


def worker_name(worker) -> str:
    text = str(worker)
    return f"gw{text}" if text.isdigit() else text


class DurationsFunctionTest(unittest.TestCase):
    """Чистая функция `suite_durations.durations(marks, start)`."""

    def setUp(self):
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def scenario(self, start: float, workers: list, header: str | None,
                 count: int) -> tuple:
        """(marks, ожидаемые записи) — строки хода `workers` вперемежку,
        строки старта тестов, повторы id, затем секция отчёта со строкой
        вида хода внутри. Ожидание — независимая модель критерия."""
        marks = []
        t = start + self.rng.uniform(0.05, 0.5)
        marks.append((t, "=" * 29 + " test session starts " + "=" * 30))
        marks.append((t, f"created: {len(workers)}/{len(workers)} workers"))
        origin = start
        if header is not None:
            t += self.rng.uniform(0.1, 1.0)
            marks.append((t, header))
            origin = t
        marks.append((t, ""))
        marks.append((t, "scheduling tests via LoadScheduling"))
        last = dict.fromkeys(workers, origin)
        expected: dict = {}
        order = []
        done = []
        for index in range(count):
            worker = workers[index % len(workers)] if index < len(workers) \
                else self.rng.choice(workers)
            if done and self.rng.random() < 0.25:
                node, worker = self.rng.choice(done)
                outcome = self.rng.choice(OUTCOMES)
            else:
                node = (f"tests/test_{self.word()}_{index}.py::"
                        f"test_{self.word()}")
                outcome = self.rng.choice(OUTCOMES)
                marks.append((t, f"{node} "))
            t += self.rng.uniform(0.01, 3.0)
            percent = min(100, (index + 1) * 100 // count)
            marks.append((t, f"[{worker}] [{percent:3d}%] {outcome} {node} "))
            key = (node, worker)
            if key not in expected:
                expected[key] = [outcome, 0.0]
                order.append(key)
                done.append(key)
            elif expected[key][0] not in FAILING:
                expected[key][0] = outcome
            expected[key][1] += t - last[worker]
            last[worker] = t
        t += 0.2
        marks.append((t, REPORT_HEADER))
        marks.append((t, f"[{workers[0]}] [ 50%] PASSED "
                         f"tests/test_after_{self.word()}.py::test_x "))
        marks.append((t, "tests/test_in_report.py::test_y PASSED"))
        marks.append((t, "=" * 20 + f" {count} passed in 9.99s " + "=" * 20))
        return marks, [(node, worker, *expected[(node, worker)])
                       for node, worker in order]

    def check(self, durations, marks, start, expected, label: str) -> None:
        where = f"{label}, зерно {self.seed}"
        records = [tuple(record) for record in durations(marks, start)]
        got = [(str(node), worker_name(worker), str(outcome), float(seconds))
               for node, worker, outcome, seconds in records]
        self.assertEqual([(n, w, o) for n, w, o, _ in got],
                         [(n, w, o) for n, w, o, _ in expected], where)
        for (node, _w, _o, seconds), (_n, _ww, _oo, want) in zip(got, expected):
            self.assertAlmostEqual(seconds, want, places=6,
                                   msg=f"{where}: {node}")

    def test_ac1_durations_by_own_worker_header_start_repeat_and_report(self):
        """Время теста — от прошлой строки своего процесса, первой — от строки рабочих или начала.

        Разыгрываются случайные прогоны: два процесса вперемежку со
        строкой `N workers [M items]`, тот же без строки рабочих (отсчёт
        первой строки процесса от `start`), один процесс со строкой
        `1 worker [1 item]`; в каждом — повторы id в том же процессе
        (`PASSED`, затем иной исход) и секция отчёта со строкой вида хода
        внутри. Запись — одна на (id, процесс) в порядке первого появления,
        секунды — сумма, исход — худший; строки старта тестов, заголовки и
        строки после первой секции отчёта не дают записей.

        Ловит мутацию: разница берётся с прошлой строкой хода любого
        процесса, а не своего — секунды теста, перед которым шла строка
        соседнего процесса, меньше ожидаемых; первая строка процесса
        считается от `start` при наличии строки рабочих (или от строки
        рабочих только формы `workers`, без `1 worker`) — её секунды
        больше; повтор id даёт вторую запись или заменяет время вместо
        суммы; строка вида хода в секции отчёта попадает в записи.
        """
        durations = importlib.import_module(
            "orchestrator.suite_durations").durations
        for round_no in range(3):
            start = self.rng.uniform(100.0, 10_000.0)
            cases = (
                ("два процесса, строка рабочих", ["gw0", "gw1"],
                 "2 workers [{n} items]"),
                ("два процесса без строки рабочих", ["gw0", "gw1"], None),
                ("один процесс, 1 worker", ["gw0"], "1 worker [{n} item]"),
            )
            for label, workers, header in cases:
                count = self.rng.randint(6, 14) if len(workers) > 1 else 1
                if header is not None:
                    header = header.format(n=count)
                with self.subTest(case=label, round=round_no, seed=self.seed):
                    marks, expected = self.scenario(start, workers, header,
                                                    count)
                    self.check(durations, marks, start, expected, label)

        # Строка процесса после строки соседа: «не чужого» — точечно.
        start = 50.0
        marks = [(51.0, "2 workers [3 items]"),
                 (52.0, "[gw0] [ 33%] PASSED tests/test_a.py::test_a "),
                 (55.0, "[gw1] [ 66%] PASSED tests/test_b.py::test_b "),
                 (56.0, "[gw0] [100%] FAILED tests/test_c.py::test_c "),
                 (56.5, "[gw0] [100%] ERROR tests/test_c.py::test_c ")]
        expected = [("tests/test_a.py::test_a", "gw0", "PASSED", 1.0),
                    ("tests/test_b.py::test_b", "gw1", "PASSED", 4.0),
                    ("tests/test_c.py::test_c", "gw0", "FAILED", 4.5)]
        self.check(durations, marks, start, expected, "точечный")


class LoggedRunTest(TmpRootTest):
    """Прогон полного набора в файл лога настоящим pytest с xdist."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def project(self, sources: list) -> Path:
        """Каталог проекта с одним файлом тестов `tests/test_<слово>.py`
        из текстов функций `sources` в порядке перечня."""
        root = self.root / f"proj-{self.word()}"
        (root / "tests").mkdir(parents=True)
        module = f"test_{self.word()}.py"
        (root / "tests" / module).write_text("\n\n".join(sources),
                                             encoding="utf-8")
        self.module = f"tests/{module}"
        return root

    def node(self, name: str) -> str:
        return f"{self.module}::test_{name}"

    def test_ac2_durations_file_times_by_first_bytes_of_progress_line(self):
        """Файл времени рядом с логом: быстрый тест быстр, спящий 3 с — не меньше 1,5 с.

        Проект из двух тестов (быстрый и спящий 3 с), два рабочих процесса
        xdist, `-vv`, вывод в файл лога. Строка хода быстрого теста
        получает перевод строки только со строкой спящего (через 3 с), поэтому
        время по приходу `\\n` дало бы быстрому около 3 с. Проверяется: файл
        `<лог без .log>.durations.tsv` есть, в нём строки обоих id с
        процессом `gwN`, исходом `PASSED` и секундами; у спящего ≥ 1,5 с, у
        быстрого < 1,5 с; ни одна строка файла времени не попала в лог.

        Ловит мутацию: отметка строки по приходу её `\\n`, а не по первым
        байтам — у быстрого около 3 с; разбор лога только после конца
        прогона — у спящего около 0 с; файл назван иначе (`<лог>.log.tsv`,
        без `.durations`) — файла по имени нет; строки времени дописаны в
        сам лог — лог их содержит.
        """
        fast, sleepy = f"fast_{self.word()}", f"sleepy_{self.word()}"
        root = self.project([FAST.format(name=fast),
                             SLEEPING.format(name=sleepy, seconds=3)])
        log = self.root / f"run-{self.word()}.log"
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 2):
            green, output = acceptance.run_full_suite(
                root, extra=("-vv",), log=log, limit=(120, "тест"))
        where = f"зерно {self.seed}; вывод:\n{output[-2000:]}"
        self.assertTrue(green, where)
        path = durations_path(log)
        self.assertTrue(path.is_file(), f"файла времени {path} нет; {where}")
        rows = read_durations(path)
        by_node = {node: (worker, outcome, seconds)
                   for (node, worker), (outcome, seconds) in rows.items()}
        for name in (fast, sleepy):
            self.assertIn(self.node(name), by_node, f"{rows}; {where}")
            worker, outcome, _ = by_node[self.node(name)]
            self.assertRegex(worker, r"^gw\d+$", where)
            self.assertEqual(outcome, "PASSED", where)
        self.assertGreaterEqual(by_node[self.node(sleepy)][2], 1.5,
                                f"{rows}; {where}")
        self.assertLess(by_node[self.node(fast)][2], 1.5, f"{rows}; {where}")
        log_text = log.read_bytes().decode("utf-8", errors="replace")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.assertNotIn(line, log_text, where)
        self.assertNotIn("\t", log_text, where)

    def test_ac3_cut_run_keeps_closed_line_during_run_and_tail_after_cut(self):
        """Оборванный пределом прогон: быстрый 1 в файле до предела, оба быстрых — в итоге.

        Один рабочий процесс, тесты «быстрый 1, быстрый 2, спящий 30 с»,
        предел 5 с параметром `limit`. Пока прогон идёт, наблюдатель в
        процессе теста перечитывает файл времени (свойство «запись по мере
        появления» наблюдаемо только так — прогон настоящий); снимок,
        взятый раньше начала прогона плюс предел, обязан содержать строку
        быстрого 1. После обрыва в файле есть строки обоих быстрых тестов.
        Отсутствие быстрого 2 до обрыва не утверждается: какая строка
        остаётся без перевода строки, решает вывод xdist (у xdist 3.8.0 с
        `-vv` строку хода быстрого 2 закрывает строка старта спящего теста,
        без `\\n` остаётся именно она).

        Ловит мутацию: файл времени пишется одним разом после конца прогона
        или без `flush` — до предела снимки пусты; поток не запущен вовсе
        или запущен только при наблюдении — файла нет; поток читает только
        завершённые прогоны (разбор после `proc.wait`, а по пределу — нет) —
        строк быстрых тестов в файле нет.
        """
        first, second = f"first_{self.word()}", f"second_{self.word()}"
        sleepy = f"sleepy_{self.word()}"
        root = self.project([FAST.format(name=first), FAST.format(name=second),
                             SLEEPING.format(name=sleepy, seconds=30)])
        log = self.root / f"run-{self.word()}.log"
        path = durations_path(log)
        snapshots: list = []
        stop = threading.Event()

        def observe():
            seen = None
            while not stop.is_set():
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    text = None
                if text != seen:
                    snapshots.append((time.monotonic(), text))
                    seen = text
                stop.wait(0.05)

        watcher = threading.Thread(target=observe, daemon=True)
        limit = 5
        started = time.monotonic()
        watcher.start()
        try:
            with mock.patch.object(config, "FULL_SUITE_WORKERS", 1):
                green, output = acceptance.run_full_suite(
                    root, extra=("-vv",), log=log, limit=(limit, "тест"))
        finally:
            stop.set()
            watcher.join(5)
        where = f"зерно {self.seed}; вывод:\n{output[-2000:]}"
        self.assertFalse(green, where)
        self.assertTrue(output.startswith(TIMEOUT_PREFIX), where)
        early = [text for at, text in snapshots
                 if at < started + limit and text]
        self.assertTrue(
            any(self.node(first) in text for text in early),
            f"строки быстрого 1 нет в файле времени до предела; снимки "
            f"{snapshots!r}; {where}")
        self.assertTrue(path.is_file(), f"файла времени {path} нет; {where}")
        nodes = {node for node, _worker in read_durations(path)}
        self.assertIn(self.node(first), nodes, where)
        self.assertIn(self.node(second), nodes, where)


class SuiteRunSlowestBlockTest(RealGitSandbox):
    """Блок «самые медленные» отчёта `suite-run` через фоновый процесс."""

    TARGET_ENTRY = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

    GREEN = ("[gw0] [ 50%] PASSED tests/test_probe.py::test_one \n"
             "[gw1] [100%] PASSED tests/test_probe.py::test_two \n"
             "\n" + "=" * 20 + " 2 passed in 0.10s " + "=" * 20 + "\n")
    RED = ("[gw0] [ 50%] PASSED tests/test_probe.py::test_one \n"
           "[gw1] [100%] FAILED tests/test_probe.py::test_two \n"
           + "=" * 20 + " short test summary info " + "=" * 20 + "\n"
           "FAILED tests/test_probe.py::test_two - ValueError: сломано\n"
           + "=" * 20 + " 1 failed, 1 passed in 0.10s " + "=" * 20 + "\n")
    TIMEOUT = (TIMEOUT_PREFIX + "10с — завис или ждёт сетевой ответ "
               "(источник: config)\n"
               "[gw0] [ 50%] FAILED tests/test_probe.py::test_two \n"
               "tests/test_probe.py::test_one ")
    BASE = ("[gw0] [ 50%] PASSED tests/test_probe.py::test_one \n"
            "[gw1] [100%] FAILED tests/test_probe.py::test_base \n"
            + "=" * 20 + " short test summary info " + "=" * 20 + "\n"
            "FAILED tests/test_probe.py::test_base - KeyError: база\n"
            + "=" * 20 + " 1 failed, 1 passed in 0.10s " + "=" * 20 + "\n")

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.target = "p" + self.word(8)
        config.TARGETS.parent.mkdir(parents=True, exist_ok=True)
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + self.TARGET_ENTRY.format(
                name=self.target, base=config.MAIN_BRANCH), encoding="utf-8")
        clone = make_project_repo(self.target)
        (clone / "tests").mkdir()
        (clone / "tests" / "test_probe.py").write_text(
            "def test_one():\n    assert True\n", encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "тесты проекта")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
        self.conn = store.db()
        self.task = "01M" + "".join(self.rng.choices(ID_ALPHABET, k=23))
        branch = f"task/{self.task.lower()}-slowest"
        store.insert_task(self.conn, self.task, "Фикстура блока", "in_dev",
                          branch, self.target, 25.0)
        wt, error = workspace.ensure(self.task, branch)
        self.assertIsNone(error, f"рабочая копия не заведена: {error}")
        self.run_no = 0

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def where(self, label: str) -> str:
        return f"{label}, зерно {self.seed}"

    # --- фикстура файла времени ---------------------------------------------

    def rows(self, prefix: str) -> dict:
        """Файл времени больше среза: 36–50 тестов в 17–24 файлах,
        секунды — различные целые, и один id, записанный дважды в том же
        процессе: каждая половина ниже среза 30, сумма — выше всех."""
        files = [f"tests/test_{prefix}{i}_{self.word()}.py"
                 for i in range(self.rng.randint(17, 24))]
        count = self.rng.randint(36, 50)
        seconds = self.rng.sample(range(600, 1000), count)
        rows = []
        for index in range(count):
            file = files[index] if index < len(files) else self.rng.choice(files)
            rows.append((f"{file}::test_{self.word()}_{index}",
                         self.rng.choice(["gw0", "gw1"]),
                         self.rng.choice(["PASSED", "FAILED", "SKIPPED"]),
                         seconds[index]))
        twice = f"{self.rng.choice(files)}::test_twice_{self.word()}"
        halves = self.rng.sample(range(510, 600), 2)
        worker = self.rng.choice(["gw0", "gw1"])
        rows.insert(self.rng.randrange(len(rows)),
                    (twice, worker, "PASSED", halves[0]))
        rows.append((twice, worker, "ERROR", halves[1]))
        tests: dict = {}
        for node, _worker, _outcome, value in rows:
            tests[node] = tests.get(node, 0) + value
        by_file: dict = {}
        for node, value in tests.items():
            file = node.split("::")[0]
            by_file[file] = by_file.get(file, 0) + value
        return {"rows": rows, "tests": tests, "files": by_file,
                "twice": twice, "twice_sum": sum(halves)}

    # --- прогон -------------------------------------------------------------

    def run_background(self, mode: str, branch: tuple, rows: dict | None,
                       empty: bool = False) -> dict:
        """Один прогон `suite_run.background` с подменой
        `acceptance.run_full_suite`: вывод `branch` (или `BASE` у прогона
        базы — лог `…-base.log`) в лог, файл времени рядом — `rows` у
        прогона ветки (пустой при `empty`, нет при `None`) и всегда у базы.
        Сохранённые итоги перед прогоном стираются: база идёт заново."""
        for saved in acceptance.suite_results_dir().glob("*.json"):
            saved.unlink()
        self.run_no += 1
        calls = {}
        base_rows = self.rows("base")

        def fake(root, *args, **kwargs):
            log = Path(kwargs["log"])
            base = log.name.endswith("-base.log")
            green, output = (False, self.BASE) if base else branch
            calls["base" if base else "branch"] = log
            log.write_bytes(output.encode("utf-8"))
            data = base_rows if base else rows
            if base or rows is not None or empty:
                lines = [] if (empty and not base) else [
                    f"{node}\t{worker}\t{outcome}\t{value:.3f}\n"
                    for node, worker, outcome, value in data["rows"]]
                durations_path(log).write_text("".join(lines),
                                               encoding="utf-8")
            return green, output

        with mock.patch.object(acceptance, "run_full_suite", side_effect=fake):
            suite_run.background(self.task, str(self.run_no), mode)
        folder = suite_lock.directory() / self.task
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        failed = json.loads((folder / "failed.json").read_text(encoding="utf-8"))
        report = result["report"]
        normal = re.sub(r"№\d+", "№N", report)
        for name, log in calls.items():
            normal = normal.replace(str(log), f"<лог {name}>")
        saved_base = [
            {key: data.get(key) for key in ("outcome", "summary", "failed",
                                            "digest")}
            for data in (json.loads(p.read_text(encoding="utf-8"))
                         for p in sorted(acceptance.suite_results_dir().glob(
                             "base-*.json")))]
        return {"report": report, "normal": normal, "result_keys": set(result),
                "failed": failed.get("failed"),
                "log": calls["branch"].read_bytes(), "saved_base": saved_base,
                "base_rows": base_rows}

    def check_same(self, plain: dict, other: dict, label: str) -> None:
        """Лог, `failed.json`, ключи `result.json` и итог базы — как без
        файла времени."""
        where = self.where(label)
        self.assertEqual(other["log"], plain["log"], f"{where}: лог")
        self.assertEqual(other["failed"], plain["failed"], f"{where}: failed")
        self.assertEqual(other["result_keys"], plain["result_keys"], where)
        self.assertEqual(other["saved_base"], plain["saved_base"],
                         f"{where}: итог базы")

    def check_block(self, plain: dict, with_file: dict, rows: dict,
                    label: str) -> None:
        where = self.where(label)
        report = with_file["normal"]
        self.assertTrue(report.startswith(plain["normal"]),
                        f"{where}: отчёт не продолжает прежний:\n{report}\n"
                        f"--- прежний:\n{plain['normal']}")
        extra = report[len(plain["normal"]):]
        entries = [line for line in extra.splitlines() if line.startswith(" ")]
        test_entries, file_entries = [], []
        for line in entries:
            match = re.match(r"^  (\d+(?:[.,]\d+)?)", line)
            self.assertIsNotNone(match, f"{where}: строка блока «{line}»")
            value = float(match.group(1).replace(",", "."))
            tokens = {token.strip("()[],;«»") for token in line.split()}
            if "::" in line:
                found = tokens & set(rows["tests"])
                self.assertEqual(len(found), 1, f"{where}: «{line}»")
                test_entries.append((found.pop(), value))
            else:
                found = tokens & set(rows["files"])
                self.assertEqual(len(found), 1, f"{where}: «{line}»")
                file_entries.append((found.pop(), value))
        self.assertEqual(len(test_entries), 30, f"{where}:\n{extra}")
        self.assertEqual(len(file_entries), 15, f"{where}:\n{extra}")
        for kind, listed, truth in (("тесты", test_entries, rows["tests"]),
                                    ("файлы", file_entries, rows["files"])):
            values = [value for _name, value in listed]
            self.assertEqual(values, sorted(values, reverse=True),
                             f"{where}: {kind} не по убыванию:\n{extra}")
            names = [name for name, _value in listed]
            self.assertEqual(len(set(names)), len(names), f"{where}: {kind}")
            for name, value in listed:
                self.assertEqual(value, truth[name], f"{where}: {kind} {name}")
            rest = [truth[name] for name in truth if name not in names]
            self.assertGreaterEqual(min(values), max(rest, default=0),
                                    f"{where}: {kind} не самые медленные")
        self.assertIn((rows["twice"], rows["twice_sum"]), test_entries,
                      f"{where}: повтор id не суммирован:\n{extra}")
        self.assertNotIn(extra.strip(), with_file["log"].decode("utf-8"), where)
        for node, *_rest in with_file["base_rows"]["rows"]:
            self.assertNotIn(node, with_file["report"],
                             f"{where}: строка файла времени базы в отчёте")

    def check_no_block(self, plain: dict, rows_seen: list, label: str) -> None:
        where = self.where(label)
        for rows in rows_seen:
            for node in rows["tests"]:
                self.assertNotIn(node, plain["report"], where)
        for node, *_rest in plain["base_rows"]["rows"]:
            self.assertNotIn(node, plain["report"], where)

    def test_ac5_report_gets_slowest_block_and_nothing_else_changes(self):
        """Отчёт `suite-run` дописывает «самые медленные» — 30 тестов и 15 файлов — и больше ничего не меняет.

        По каждому прогону — зелёному, красному, оборванному по пределу и
        повтору `--failed` (после красного полного) — три прогона фонового
        процесса: без файла времени, с файлом больше среза (повтор id в том
        же процессе) и с пустым файлом. С файлом: отчёт — прежний отчёт и
        блок, в блоке ровно 30 тестов и 15 файлов, каждый список по убыванию,
        секунды теста — сумма его строк, файла — сумма его тестов, строки
        блока начинаются с двух пробелов и числа. Без файла и с пустым —
        отчёт прежний. Файл времени базы (рядом с логом базы) в отчёт не
        попадает. Лог, `failed.json`, ключи `result.json` и сохранённый итог
        базы — как без файла времени.

        Ловит мутацию: срез 30/15 перепутан или не применён — число строк
        иное; сортировка по возрастанию или по порядку файла — список не
        по убыванию; повтор id не суммируется (берётся последняя строка) —
        у id время половины, и он не первый; время файла — максимум его
        тестов, а не сумма; блок пишется в лог прогона (через
        `_log_appendix`) или в `output` — лог отличается от лога без файла;
        блок строится по файлу времени базы — в отчёте id базы; пустой файл
        даёт заголовок блока без строк — отчёт отличается от прежнего;
        в режиме `--failed` блок не печатается — строк блока нет.
        """
        cases = (("зелёный", suite_run.MODE_FULL, (True, self.GREEN)),
                 ("красный", suite_run.MODE_FULL, (False, self.RED)),
                 ("оборван по пределу", suite_run.MODE_FULL,
                  (False, self.TIMEOUT)),
                 ("повтор --failed", suite_run.MODE_FAILED, (False, self.RED)))
        for label, mode, branch in cases:
            with self.subTest(case=label, seed=self.seed):
                runs = {}
                rows = self.rows("t")
                for variant in ("без файла", "с файлом", "пустой файл"):
                    if mode == suite_run.MODE_FAILED:
                        self.run_background(suite_run.MODE_FULL,
                                            (False, self.RED), None)
                    runs[variant] = self.run_background(
                        mode, branch,
                        rows if variant == "с файлом" else None,
                        empty=variant == "пустой файл")
                plain = runs["без файла"]
                self.check_no_block(plain, [rows], f"{label}, без файла")
                self.assertEqual(runs["пустой файл"]["normal"], plain["normal"],
                                 self.where(f"{label}, пустой файл"))
                for variant in ("с файлом", "пустой файл"):
                    self.check_same(plain, runs[variant], f"{label}, {variant}")
                self.check_block(plain, runs["с файлом"], rows,
                                 f"{label}, с файлом")


class FakeProc:
    pid = 2_000_000_000
    returncode = 0

    def __init__(self, argv):
        self.args = argv

    def communicate(self, input=None, timeout=None):
        return "1 passed in 0.01s", ""

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass


class FakeSubprocess:
    """Замена модуля `subprocess` у `acceptance`: каждый вызов `run` и
    `Popen` запоминается с argv и копией окружения."""

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    DEVNULL = subprocess.DEVNULL
    TimeoutExpired = subprocess.TimeoutExpired
    SubprocessError = subprocess.SubprocessError
    CalledProcessError = subprocess.CalledProcessError
    CompletedProcess = subprocess.CompletedProcess

    def __init__(self):
        self.calls: list = []

    def remember(self, how, argv, kwargs):
        env = kwargs.get("env")
        self.calls.append({"how": how, "argv": [str(a) for a in argv],
                           "cwd": kwargs.get("cwd"),
                           "env": dict(env) if env is not None else None})

    def run(self, argv, **kwargs):
        self.remember("run", argv, kwargs)
        return subprocess.CompletedProcess(argv, 0, "1 passed in 0.01s", "")

    def Popen(self, argv, **kwargs):
        self.remember("Popen", argv, kwargs)
        return FakeProc(argv)


class LaunchUnchangedTest(TmpRootTest):
    """argv и окружение полного прогона `pult-pytest`; где файла времени нет."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_probe.py").write_text(
            "def test_one():\n    assert True\n\n\n"
            "def test_two():\n    assert True\n", encoding="utf-8")

    def word(self, k: int = 6) -> str:
        return "".join(self.rng.choices(LETTERS, k=k))

    def durations_files(self) -> list:
        return sorted(str(p) for p in self.root.rglob("*.durations.tsv"))

    def test_ac6_spy_argv_env_unchanged_and_no_file_without_log_or_for_own(self):
        """Шпион запуска: argv и окружение прогона с логом и без — прежние; без лога и у `pytest-own` файла времени нет.

        Модуль `subprocess` у `acceptance` подменён шпионом; интерпретатор
        пульта — случайный путь; в окружение вызывающего добавлены случайные
        переменные. Без лога и с логом (`-vv`, как у `suite-run`) — ровно
        один вызов процесса: argv равен литералу команды полного прогона,
        окружение — окружение вызывающего плюс `PYTHONPYCACHEPREFIX` (и
        `PYTHONUNBUFFERED=1` у прогона в файл), других вызовов `subprocess`
        модуля нет. Затем настоящие прогоны: `pult-pytest` без лога и
        `pytest-own` (команда профиля с xdist, `-vv`) с логом — ни одного
        файла `*.durations.tsv` в дереве песочницы.

        Ловит мутацию: к argv полного прогона добавлен флаг (`--durations`,
        `-vv` по умолчанию) или изменено окружение (переменная для потока
        чтения) — сверка с литералом расходится; поток чтения зовёт
        `acceptance.subprocess` (`tail`, `ps`) — лишний вызов шпиона; поток
        запускается у `pytest-own` или файл времени заводится без лога (в
        `cwd`) — файл появляется.
        """
        interpreter = f"/opt/{self.word()}/bin/python3"
        extra_env = {f"ARTEL_PROBE_{self.word().upper()}": self.word(12)
                     for _ in range(self.rng.randint(1, 3))}
        cases = (("без лога", None, ()),
                 ("с логом", self.root / f"run-{self.word()}.log", ("-vv",)))
        for label, log, extra in cases:
            where = f"{label}, зерно {self.seed}"
            with self.subTest(case=label, seed=self.seed):
                fake = FakeSubprocess()
                with mock.patch.dict(os.environ, extra_env), \
                        mock.patch.object(acceptance, "subprocess", fake), \
                        mock.patch.object(acceptance.stack,
                                          "pytest_python_executable",
                                          return_value=interpreter):
                    for name in ("PYTHONPYCACHEPREFIX", "PYTHONUNBUFFERED"):
                        os.environ.pop(name, None)
                    caller = dict(os.environ)
                    acceptance.run_full_suite(self.root, extra=extra, log=log,
                                              limit=(60, "тест"))
                self.assertEqual(len(fake.calls), 1,
                                 f"{where}: вызовы {fake.calls!r}")
                call = fake.calls[0]
                self.assertEqual(call["argv"], [
                    interpreter, "-m", "pytest", "tests", "-p",
                    "no:cacheprovider", "-p", "timeout", "-o",
                    f"timeout={stack.PER_TEST_TIMEOUT_SEC}", "-n",
                    str(config.FULL_SUITE_WORKERS), "-p", "xdist", *extra],
                    where)
                self.assertEqual(str(call["cwd"]), str(self.root), where)
                env = dict(call["env"])
                self.assertIn("PYTHONPYCACHEPREFIX", env, where)
                env.pop("PYTHONPYCACHEPREFIX")
                expected = dict(caller)
                if log is not None:
                    expected["PYTHONUNBUFFERED"] = "1"
                self.assertEqual(env, expected, f"{where}: окружение")

        for name in self.durations_files():
            Path(name).unlink()
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1):
            green, output = acceptance.run_full_suite(
                self.root, extra=("-vv",), limit=(120, "тест"))
        self.assertTrue(green, f"зерно {self.seed}; {output[-2000:]}")
        self.assertEqual(self.durations_files(), [],
                         f"без лога, зерно {self.seed}")

        python = stack.pytest_python_executable()
        own = project_profile.Profile(
            command=(python, "-m", "pytest", "-n", "1", "-p", "xdist"),
            long_lived_dir="tests", long_lived_name="test_<id>_<name>.py",
            weakening_scope=(), mutation_claim_scope=(),
            runner=targets.PROFILE_RUNNER_OWN, workdir="")
        log = self.root / f"own-{self.word()}.log"
        green, output = acceptance.run_full_suite(
            self.root, command=own, extra=("-vv",), log=log,
            limit=(120, "тест"))
        self.assertTrue(green, f"зерно {self.seed}; {output[-2000:]}")
        self.assertIn("[gw0]", output, f"зерно {self.seed}; {output[-2000:]}")
        self.assertEqual(self.durations_files(), [],
                         f"pytest-own, зерно {self.seed}")


if __name__ == "__main__":
    unittest.main()
