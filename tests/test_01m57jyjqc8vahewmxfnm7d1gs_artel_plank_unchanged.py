"""Прогоны планки артели (`pult-pytest`, без `workdir`) дают прежние исходы и тексты.

Группа: долгоживущий
Зелёный с рождения: файл закрепляет поведение артели на коде до правки — `acceptance.run`/`collect`, `plank-run` и `amend-tests` гонят каталог планки задачи под `tasks` рабочей копии с прежними строкой-заголовком, текстом пустой планки и текстами таймаута (AC-13).

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): клон артели —
сам репозиторий песочницы с bare `origin`, рабочая копия задачи —
`workspace.ensure`, документы — каталог документов, переносимый в ссылку
документов `checkpoint.commit_step_artifacts`. Профиль артели — посеянный
песочницей `pult-pytest`. Вызов pytest наблюдается подменой
`subprocess.run` (раннер пульта зовёт pytest им): argv, рабочий каталог и
цели (аргументы-пути, разрешённые от рабочего каталога) записываются, а
ответ — исход сценария: зелёный (0), красный (1), пустая планка (5,
«no tests ran») или превышение таймаута (`TimeoutExpired`). Прочие вызовы
(git) идут настоящим `subprocess`. Имена и хвосты вывода — из `random`,
зерно печатается и входит в текст каждого провала.
"""
import io
import os
import random
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, amend, artel, checkpoint, config, idgen,
                          store, workspace)
from tests.sandbox import RealGitSandbox

REAL_RUN = subprocess.run
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
PLANK_DIR = "acceptance_tests"
HEADER = "планка: "
EMPTY_TEXT = "планка не содержит ни одного теста"
NO_PLANK = "планки нет"
OPTIONS_WITH_VALUE = ("-m", "-p", "-o", "-c", "-k", "--rootdir", "--junitxml")

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 30
---

# SPEC: фикстура артели

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""

PLANK_TEXT = '''"""Фикстура планки артели.

Группа: разовый
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_{word}(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''


def is_pytest(argv) -> bool:
    parts = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    return any(Path(p).name in ("pytest", "py.test") for p in parts) or any(
        a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))


def capture_out(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


class ArtelPlankSandbox(RealGitSandbox):
    """Задачи артели с рабочей копией кода; pytest — подменённый."""

    CODES = {"green": 0, "red": 1, "empty": 5}

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.add_synced_origin()
        self.calls: list = []
        self.mode = "green"
        self.collect_mode = None
        self.tail = f"хвост {self.word()} (зерно {self.seed})\n"
        for patcher in (mock.patch.object(subprocess, "run", self.spy_run),
                        mock.patch.dict(os.environ,
                                        {config.ARTEL_ROLE_ENV: ""})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def explain(self, output: str) -> str:
        calls = "\n".join(f"{c['argv']} @ {c['cwd']}" for c in self.calls)
        return self.note(f"вывод:\n{output[-3000:]}\nвызовы pytest:\n{calls}")

    # ------------------------------------------------------------ задача

    def new_task(self, state: str) -> str:
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, ARTEL, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs(task_id, {"SPEC.md": SPEC_TEXT.format(task=task_id)})
        return task_id

    def wt(self, task_id: str) -> Path:
        return workspace.path(task_id, ARTEL)

    def plank_dir(self, task_id: str) -> Path:
        return self.wt(task_id) / "tasks" / task_id / PLANK_DIR

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / ARTEL / "tasks" / task_id

    def write_docs(self, task_id: str, files: dict) -> None:
        for rel, text in files.items():
            path = self.docs_dir(task_id) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_docs(self, task_id: str, files: dict) -> None:
        self.write_docs(task_id, files)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, task_id, "test_author")
        store.record_fixation(self.conn, task_id)

    def plank(self) -> tuple:
        return f"test_ac1_{self.word()}.py", PLANK_TEXT.format(word=self.word())

    # ------------------------------------------------------------ pytest

    def targets_of(self, argv: list, cwd: str) -> list:
        found = []
        for prev, arg in zip(argv, argv[1:]):
            if arg.startswith("-") or prev in OPTIONS_WITH_VALUE:
                continue
            path, _sep, node = arg.partition("::")
            found.append((os.path.realpath(os.path.join(cwd, path)), node))
        return found

    def spy_run(self, argv, *args, **kwargs):
        if not is_pytest(argv):
            return REAL_RUN(argv, *args, **kwargs)
        argv = [str(a) for a in argv]
        cwd = kwargs.get("cwd")
        cwd = os.path.realpath(cwd if cwd is not None else os.getcwd())
        self.calls.append({"argv": argv, "cwd": cwd,
                           "targets": self.targets_of(argv, cwd)})
        collecting = "--collect-only" in argv
        mode = self.collect_mode if collecting and self.collect_mode \
            else self.mode
        if mode == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout") or 1,
                                            output=self.tail, stderr="")
        return subprocess.CompletedProcess(argv, self.CODES[mode], self.tail, "")

    def direct(self, task_id: str, fn, files: dict) -> tuple:
        """(исход, вывод, каталог планки) `fn` по планке `files`,
        выложенной `plank_in_code_copy` в рабочую копию кода."""
        self.calls = []
        wt = self.wt(task_id)
        branch = store.get_task(self.conn, task_id)["branch"]
        with acceptance.plank_in_code_copy(task_id, branch, wt,
                                           files=files) as tdir:
            ok, output = fn(tdir, cwd=wt)
            return ok, output, tdir / PLANK_DIR

    def plank_run(self, task_id: str, *extra: str) -> tuple:
        self.calls = []
        argv = ["artel.py", "plank-run", task_id, *extra]
        out, err = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), \
                redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        message = "" if code is None or isinstance(code, int) else str(code)
        status = code if isinstance(code, int) else (0 if code is None else 1)
        return status, message, "\n".join((out.getvalue(), err.getvalue(),
                                           message))

    def assert_plank_target(self, task_id: str, output: str,
                            rel: str = "") -> None:
        """Ровно один вызов pytest, целью — каталог планки задачи под
        `tasks` рабочей копии (или файл `rel` в нём)."""
        self.assertEqual(len(self.calls), 1, self.explain(output))
        expected = self.plank_dir(task_id) / rel if rel else self.plank_dir(task_id)
        self.assertEqual([p for p, _n in self.calls[0]["targets"]],
                         [os.path.realpath(expected)], self.explain(output))


class Ac13ArtelRunCollectTest(ArtelPlankSandbox):

    def test_ac13_artel_run_and_collect_keep_outcomes_and_texts(self):
        """`acceptance.run` и `collect` артели: прежние исходы, строка-заголовок, текст пустой планки и тексты таймаута.

        Сценарий: задача артели, планка из одного файла, выложенная
        `plank_in_code_copy` в рабочую копию; `run` и `collect` с `cwd` —
        рабочей копией, pytest отвечает зелёным, красным, кодом 5 и
        таймаутом. Каждый раз — один вызов pytest с рабочим каталогом —
        рабочей копией и целью — каталогом планки под `tasks`. `run`:
        зелёный — `True`, иначе `False`; первая строка вывода —
        «планка: <каталог планки>, cwd: <рабочая копия>», на таймауте
        вторая — «прогон превысил <ACCEPTANCE_TIMEOUT_SEC>с — завис или
        ждёт сетевой ответ». `collect`: зелёный — `True` и вывод pytest
        как есть, красный — заголовок первой строкой, код 5 — ровно
        «планка не содержит ни одного теста», таймаут — заголовок и
        «сбор превысил …с — завис или ждёт сетевой ответ».

        Ловит мутацию: выкладка в `long_lived_dir` включается и у артели —
        цель не каталог планки под `tasks`; заголовок начинает называть
        путь выкладки или пропадает — первая строка другая; текст пустой
        планки или таймаута меняется при правке — строка не совпадает.
        """
        task_id = self.new_task("tests_writing")
        name, text = self.plank()
        limit = config.ACCEPTANCE_TIMEOUT_SEC
        expected_run = {"green": True, "red": False, "empty": False,
                        "timeout": False}
        for mode, ok_expected in expected_run.items():
            with self.subTest(place="run", mode=mode, seed=self.seed):
                self.mode = mode
                ok, output, plank = self.direct(task_id, acceptance.run,
                                                {name: text})
                self.assertEqual(ok, ok_expected, self.explain(output))
                self.assert_plank_target(task_id, output)
                self.assertEqual(self.calls[0]["cwd"],
                                 os.path.realpath(self.wt(task_id)),
                                 self.explain(output))
                lines = output.splitlines()
                self.assertEqual(lines[0], f"{HEADER}{plank}, cwd: "
                                           f"{self.wt(task_id)}",
                                 self.explain(output))
                if mode == "timeout":
                    self.assertEqual(lines[1], f"прогон превысил {limit}с — "
                                               f"завис или ждёт сетевой ответ",
                                     self.explain(output))
        for mode in ("green", "red", "empty", "timeout"):
            with self.subTest(place="collect", mode=mode, seed=self.seed):
                self.mode = mode
                ok, output, plank = self.direct(task_id, acceptance.collect,
                                                {name: text})
                self.assertEqual(ok, mode == "green", self.explain(output))
                self.assert_plank_target(task_id, output)
                self.assertIn("--collect-only", self.calls[0]["argv"])
                header = f"{HEADER}{plank}, cwd: {self.wt(task_id)}"
                if mode == "green":
                    self.assertEqual(output, self.tail, self.explain(output))
                elif mode == "empty":
                    self.assertEqual(output, EMPTY_TEXT, self.explain(output))
                else:
                    lines = output.splitlines()
                    self.assertEqual(lines[0], header, self.explain(output))
                    if mode == "timeout":
                        self.assertEqual(
                            lines[1], f"сбор превысил {limit}с — завис или "
                                      f"ждёт сетевой ответ", self.explain(output))


class Ac13ArtelPlankRunTest(ArtelPlankSandbox):

    def test_ac13_artel_plank_run_keeps_targets_codes_and_texts(self):
        """`plank-run` артели: прежняя цель под `tasks`, код прогона, отказ пустой планки и текст таймаута.

        Сценарий: задача артели в `tests_writing`. С черновиком из одного
        файла `plank-run <id>` и `plank-run <id> <файл>` запускают pytest
        ровно раз с целью — каталогом планки под `tasks` рабочей копии
        (или файлом в нём) — и рабочим каталогом — рабочей копией; код
        команды — код pytest (0, 1, 5). На таймауте — ненулевой код, текст
        «прогон превысил <ACCEPTANCE_TIMEOUT_SEC>с и оборван» и строка
        прогона «… — завис или ждёт сетевой ответ». Черновик без файлов
        `test_*.py` — отказ «планки нет» без вызова pytest.

        Ловит мутацию: `plank-run` артели переводится на путь выкладки —
        цель не каталог планки под `tasks`; код прогона сворачивается в
        0/1 — код 5 не возвращается; текст таймаута или отказа пустой
        планки меняется — строки нет в выводе.
        """
        limit = config.ACCEPTANCE_TIMEOUT_SEC
        empty = self.new_task("tests_writing")
        self.write_docs(empty, {f"{PLANK_DIR}/helper_{self.word()}.py": "A = 1\n"})
        status, _message, output = self.plank_run(empty)
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertIn(NO_PLANK, output, self.explain(output))
        self.assertEqual(self.calls, [], self.explain(output))

        task_id = self.new_task("tests_writing")
        name, text = self.plank()
        self.write_docs(task_id, {f"{PLANK_DIR}/{name}": text})
        for mode in ("green", "red", "empty", "timeout"):
            for rel in ("", name):
                with self.subTest(mode=mode, rel=rel, seed=self.seed):
                    self.mode = mode
                    args = (rel,) if rel else ()
                    status, message, output = self.plank_run(task_id, *args)
                    self.assert_plank_target(task_id, output, rel)
                    self.assertEqual(self.calls[0]["cwd"],
                                     os.path.realpath(self.wt(task_id)),
                                     self.explain(output))
                    if mode == "timeout":
                        self.assertNotEqual(status, 0, self.explain(output))
                        self.assertIn(f"прогон превысил {limit}с и оборван",
                                      message, self.explain(output))
                        self.assertIn(f"прогон превысил {limit}с — завис или "
                                      f"ждёт сетевой ответ", output,
                                      self.explain(output))
                    else:
                        self.assertEqual(status, self.CODES[mode],
                                         self.explain(output))


class Ac13ArtelAmendTestsTest(ArtelPlankSandbox):

    def docs_head(self, task_id: str) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        "refs/artifacts/" + task_id).strip()

    def locked_with_edit(self) -> str:
        """Задача артели в `in_dev` с планкой лока и правкой Оператора
        файла планки на диске рабочей копии."""
        task_id = self.new_task("in_dev")
        name, text = self.plank()
        self.commit_docs(task_id, {f"{PLANK_DIR}/{name}": text})
        store.update_task(self.conn, task_id,
                          tests_locked_sha=self.docs_head(task_id),
                          draft_mr_created=1)
        store.record_fixation(self.conn, task_id)
        path = self.plank_dir(task_id) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + f"\n# правка Оператора {self.word()}\n",
                        encoding="utf-8")
        return task_id

    def test_ac13_artel_amend_tests_keeps_outcomes_and_texts(self):
        """`amend-tests` артели: зелёный сдвигает лок, красный без маркера, пустая планка и таймаут сбора — прежние отказы.

        Сценарий: задача артели с планкой лока, Оператор правит файл
        планки на диске рабочей копии; pytest отвечает по сценарию. Сбор и
        прогон идут целью — каталогом планки под `tasks` рабочей копии — из
        корня пульта. Зелёный: отказа нет, лок сдвинут, в журнале правка
        планки. Красный прогон без маркера красноты — отказ «… не «OK», и
        не все падения промаркированы «Красен до реализации»». Код 5
        сбора — отказ «сухой сбор планки не прошёл: планка не содержит ни
        одного теста». Таймаут сбора — отказ с «сбор превысил
        <ACCEPTANCE_TIMEOUT_SEC>с — завис или ждёт сетевой ответ»; лок
        на отказах не сдвинут.

        Ловит мутацию: `amend-tests` артели переводится на путь выкладки
        или на `cwd` рабочей копии — цель или рабочий каталог другие;
        отказ пустой планки или таймаута меняет текст — строки нет в
        выводе; отказ теряется — лок сдвинут на красном прогоне.
        """
        limit = config.ACCEPTANCE_TIMEOUT_SEC
        cases = (
            ("green", None, ""),
            ("red", "green", "не «OK», и не все падения промаркированы "
                             "«Красен до реализации»"),
            ("green", "empty", f"сухой сбор планки не прошёл: {EMPTY_TEXT}"),
            ("green", "timeout", f"сбор превысил {limit}с — завис или ждёт "
                                 f"сетевой ответ"),
        )
        for mode, collect_mode, refusal in cases:
            with self.subTest(mode=mode, collect=collect_mode, seed=self.seed):
                task_id = self.locked_with_edit()
                old = store.get_task(self.conn, task_id)["tests_locked_sha"]
                self.mode, self.collect_mode = mode, collect_mode
                self.calls = []
                output = capture_out(amend.cmd_amend_tests, task_id,
                                     f"правка планки {self.seed}")
                self.assertTrue(self.calls, self.explain(output))
                for call in self.calls:
                    self.assertEqual([p for p, _n in call["targets"]],
                                     [os.path.realpath(self.plank_dir(task_id))],
                                     self.explain(output))
                    self.assertEqual(call["cwd"], os.path.realpath(config.ROOT),
                                     self.explain(output))
                locked = store.get_task(self.conn, task_id)["tests_locked_sha"]
                actions = [r["action"] for r in store.task_steps(self.conn,
                                                                 task_id)]
                if refusal:
                    self.assertIn("отказ", output, self.explain(output))
                    self.assertIn(refusal, output, self.explain(output))
                    self.assertEqual(locked, old, self.explain(output))
                else:
                    self.assertNotIn("отказ", output, self.explain(output))
                    self.assertNotEqual(locked, old, self.explain(output))
                    self.assertIn(amend.AMEND_ACTION, actions,
                                  self.explain(output))
