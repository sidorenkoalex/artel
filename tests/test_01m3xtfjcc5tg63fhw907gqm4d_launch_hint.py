"""Подсказка запуска цикла называет полный порядок шагов наблюдения.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/cycle_hint.py с launch_hint ещё нет — его импорт внутри тестов падает, а места вызова печатают голую строку artel.py run|auto <id>.

Сценарии строятся на временной БД песочницы, наблюдения заводятся
публичными функциями `store` (как в соседних тестах наблюдения), текущая
сессия задаётся переменной окружения `ARTEL_SESSION_ID`, клиент, чат и
сессии выбираются случайно — зерно печатается и входит в текст провала.
"""
import importlib
import inspect
import os
import random
import re
import shlex
import signal
import sys
from pathlib import Path
from unittest import mock

import orchestrator
from orchestrator import artel, auto, config, runner, store
from tests.sandbox import LightTransitionSandbox, TaskSeededTmpRootTest, capture

CLIENTS = ("codex", "claude")
COMMANDS = ("run", "auto")
NOTES = ("(запуск разработчика)", "— продолжит отсюда", "(прогон ревьювера)")
OBSERVATION_TABLES = ("observations", "observation_tasks", "observed_runs")


def cycle_hint_module():
    """Модуль подсказки — импорт в тесте, чтобы файл собирался и до реализации."""
    return importlib.import_module("orchestrator.cycle_hint")


def launch_hint(conn, task_id: str, cmd: str, note: str) -> list:
    return cycle_hint_module().launch_hint(conn, task_id, cmd, note)


def _token(rng: random.Random, prefix: str) -> str:
    return f"{prefix}-{rng.randrange(1 << 40):x}"


def _execution_order(hint: list) -> list:
    """Шаги «сначала:» по порядку, затем сама строка запуска (первый элемент)."""
    return list(hint[1:]) + [hint[0]]


def _index_of(lines: list, needle: str) -> int:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    return -1


class LaunchHintTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.session_id = _token(self.rng, "session")
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "ARTEL_SESSION_ID": self.session_id})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()
        self.target = store.get_task(self.conn, self.TASK)["target"]

    def msg(self, hint) -> str:
        return f"зерно: {self.seed}; подсказка: {hint!r}"

    def observe(self, *, session_id=None, target=None, client=None, chat=None):
        client = client or self.rng.choice(CLIENTS)
        chat = chat or _token(self.rng, "chat")
        observation_id = store.register_observation(
            self.conn, target or self.target, client, chat,
            session_id or self.session_id, [self.TASK])
        store.touch_observation(self.conn, observation_id)
        return observation_id, client, chat

    def snapshot(self) -> dict:
        return {table: sorted(tuple(row) for row in
                              self.conn.execute(f"SELECT * FROM {table}"))
                for table in OBSERVATION_TABLES}

    def assert_case_v(self, hint, cmd: str) -> None:
        text = "\n".join(hint)
        order = _execution_order(hint)
        register = _index_of(order, "observe register")
        watch = _index_of(order, "watch --observation")
        launch = _index_of(order, f"artel.py {cmd} {self.TASK} --client")
        self.assertNotIn("observe add", text, self.msg(hint))
        self.assertGreaterEqual(register, 0, self.msg(hint))
        self.assertIn(f"--tasks {self.TASK}", order[register], self.msg(hint))
        self.assertTrue(register < watch < launch, self.msg(hint))

    def test_ac1_shape_launch_line_then_first_steps(self):
        """Форма подсказки во всех трёх случаях и для обеих команд.

        Для каждой команды run/auto и каждого случая (нет наблюдения, есть
        с включённой задачей, есть с выключенной) первая строка начинается
        с `artel.py <cmd> <id> --client `, несёт `--chat ` и переданное
        пояснение, вторая начинается с `сначала:`.

        Ловит мутацию: launch_hint подставляет зашитую `run` вместо
        переданной `auto` (первая строка начинается не с той команды),
        теряет пояснение note либо кладёт шаги первой строкой.
        """
        observation_id = None
        for case in ("в", "а", "б"):
            if case == "а":
                observation_id, _, _ = self.observe()
            if case == "б":
                store.disable_task_observation(self.conn, self.TASK)
            for cmd in COMMANDS:
                note = self.rng.choice(NOTES)
                with self.subTest(case=case, cmd=cmd, seed=self.seed):
                    hint = launch_hint(self.conn, self.TASK, cmd, note)
                    self.assertIsInstance(hint, list, self.msg(hint))
                    self.assertGreaterEqual(len(hint), 2, self.msg(hint))
                    self.assertTrue(hint[0].startswith(
                        f"artel.py {cmd} {self.TASK} --client "), self.msg(hint))
                    self.assertIn("--chat ", hint[0], self.msg(hint))
                    self.assertIn(note, hint[0], self.msg(hint))
                    self.assertTrue(hint[1].startswith("сначала:"), self.msg(hint))
        self.assertIsNotNone(observation_id)

    def test_ac2_no_observation_register_then_watch_then_launch(self):
        """Без наблюдений подсказка ведёт через register и watch к запуску.

        В БД нет ни одного наблюдения: в подсказке есть `observe register`
        с `--tasks <id>`, затем `watch --observation`, и только потом
        строка запуска `<cmd> <id> --client` — порядок исполнения: шаги
        «сначала:» по списку, затем первая строка.

        Ловит мутацию: шаг `observe register` или `watch` выпал из
        подсказки либо `watch` назван раньше регистрации наблюдения.
        """
        for cmd in COMMANDS:
            with self.subTest(cmd=cmd, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK, cmd,
                                              self.rng.choice(NOTES))
                self.assert_case_v(hint, cmd)

    def test_ac3_active_observation_with_task_gives_its_client_chat_and_watch(self):
        """Активное наблюдение текущей сессии и проекта с включённой задачей.

        Строка запуска несёт `--client <его клиент> --chat <его чат>`,
        шаги называют `watch --observation <его ID>` с оговоркой «если
        ещё не идёт», ни `observe register`, ни `observe add` нет.

        Ловит мутацию: подсказка игнорирует существующее наблюдение и
        печатает заполнители `codex|claude`/`<ID чата>` и шаг register.
        """
        observation_id, client, chat = self.observe()
        for cmd in COMMANDS:
            with self.subTest(cmd=cmd, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK, cmd, "")
                text = "\n".join(hint)
                self.assertIn(f"--client {client} --chat {chat}", hint[0], self.msg(hint))
                watch = _index_of(hint[1:], f"watch --observation {observation_id}")
                self.assertGreaterEqual(watch, 0, self.msg(hint))
                self.assertIn("если ещё не идёт", hint[1:][watch], self.msg(hint))
                self.assertNotIn("observe register", text, self.msg(hint))
                self.assertNotIn("observe add", text, self.msg(hint))

    def test_ac4_disabled_task_suggests_observe_add_before_watch(self):
        """Наблюдение есть, задача в нём выключена тем же путём, что `stop`.

        Предлагается `observe add <ID> --tasks <id>`, а не register; шаг
        add идёт раньше `watch --observation <ID>`; строка запуска несёт
        клиент и чат этого наблюдения.

        Ловит мутацию: выключенная задача не отличается от отсутствия
        наблюдения — подсказка ведёт к register/запуску, который
        откажет «нет активного наблюдения».
        """
        observation_id, client, chat = self.observe()
        store.disable_task_observation(self.conn, self.TASK)
        for cmd in COMMANDS:
            with self.subTest(cmd=cmd, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK, cmd, "")
                text = "\n".join(hint)
                add = _index_of(hint[1:], f"observe add {observation_id} --tasks {self.TASK}")
                watch = _index_of(hint[1:], f"watch --observation {observation_id}")
                self.assertGreaterEqual(add, 0, self.msg(hint))
                self.assertTrue(add < watch, self.msg(hint))
                self.assertNotIn("observe register", text, self.msg(hint))
                self.assertIn(f"--client {client} --chat {chat}", hint[0], self.msg(hint))

    def test_ac5_foreign_stopped_observations_ignored_freshest_chosen(self):
        """Чужие и остановленные наблюдения не годятся, из двух — самое свежее.

        Наблюдение другой сессии, другого проекта и остановленное
        (`store.stop_observation`) — каждое с включённой задачей и свежей
        связью — дают случай «в»: их клиент, чат и ID в подсказку не
        попадают. Затем дважды по паре подходящих наблюдений: связь позже
        обновлена сначала у первого зарегистрированного, затем у второго —
        в строке запуска клиент и чат именно обновлённого.

        Ловит мутацию: выборка наблюдений без фильтра сессии, проекта или
        `state='active'` либо выбор первого зарегистрированного вместо
        самого свежего по `last_seen_at`.
        """
        foreign = [self.observe(session_id=_token(self.rng, "other-session")),
                   self.observe(target=_token(self.rng, "other-project"))]
        stopped = self.observe()
        store.stop_observation(self.conn, stopped[0])
        foreign.append(stopped)
        for cmd in COMMANDS:
            with self.subTest(cmd=cmd, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK, cmd, "")
                text = "\n".join(hint)
                self.assert_case_v(hint, cmd)
                for observation_id, client, chat in foreign:
                    self.assertNotIn(observation_id, text, self.msg(hint))
                    self.assertNotIn(chat, text, self.msg(hint))
                    self.assertNotIn(f"--client {client} ", text, self.msg(hint))

        for fresher_index in (0, 1):
            pair = [self.observe(), self.observe()]
            fresher, staler = pair[fresher_index], pair[1 - fresher_index]
            store.touch_observation(self.conn, fresher[0])
            with self.subTest(fresher_index=fresher_index, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK,
                                              self.rng.choice(COMMANDS), "")
                self.assertIn(f"--client {fresher[1]} --chat {fresher[2]}",
                              hint[0], self.msg(hint))
                self.assertNotIn(staler[2], "\n".join(hint), self.msg(hint))
            for observation_id, _, _ in pair:
                store.stop_observation(self.conn, observation_id)

    def test_ac6_case_a_launch_line_is_accepted_by_cycle_command(self):
        """Строка запуска случая «а» исполняется командой `run`/`auto` как есть.

        Первая строка до пояснения note разбивается на аргументы и
        подаётся в `artel.py` (процесс запуска подменён): разбор флагов
        проходит без отказа и находит то же наблюдение — запуск
        записывается в его `observed_runs`, что возможно только при тех
        же клиенте и чате, что в БД.

        Ловит мутацию: подсказка печатает флаги иначе, чем их разбирает
        команда (`--client=codex`, `--chat` без значения, кавычки) —
        `artel.py` отказывает `SystemExit` либо не находит наблюдение.
        """
        observation_id, _, _ = self.observe()
        for index, cmd in enumerate(COMMANDS):
            note = self.rng.choice(NOTES)
            with self.subTest(cmd=cmd, seed=self.seed):
                hint = launch_hint(self.conn, self.TASK, cmd, note)
                line = hint[0][:hint[0].index(note)]
                argv = shlex.split(line)
                self.assertEqual(argv[:3], ["artel.py", cmd, self.TASK], self.msg(hint))
                store.touch_observation(self.conn, observation_id)
                with mock.patch.object(sys, "argv", argv), \
                        mock.patch.object(artel.subprocess, "Popen",
                                          return_value=mock.Mock(pid=50000 + index)):
                    try:
                        capture(artel.main)
                    except SystemExit as exc:
                        self.fail(f"{self.msg(hint)}; отказ: {exc}")
                runs = store.observed_runs(self.conn, observation_id)
                self.assertIn(50000 + index, [row["pid"] for row in runs], self.msg(hint))

    def test_ac7_no_bare_cycle_hint_literals_outside_cycle_hint(self):
        """Ни один модуль `orchestrator/`, кроме cycle_hint.py, не собирает подсказку сам.

        Ловит мутацию: в одном из тринадцати мест осталась (или
        появилась) f-строка `artel.py run {task_id}` / `artel.py auto
        {task_id}` мимо `launch_hint`.
        """
        package = Path(orchestrator.__file__).resolve().parent
        bare = re.compile(r"artel\.py (run|auto) \{")
        found = []
        for path in sorted(package.rglob("*.py")):
            if path == package / "cycle_hint.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if bare.search(line):
                    found.append(f"{path.relative_to(package.parent)}:{number}: {line.strip()}")
        self.assertEqual(found, [])

    def test_ac8_hint_reads_only_and_has_no_sql(self):
        """Подсказка ничего не пишет в БД и сама не содержит SQL.

        Во всех трёх случаях (нет наблюдения, задача включена, задача
        выключена) снимок таблиц наблюдений до и после `launch_hint`
        совпадает; исходник `cycle_hint.py` не несёт `SELECT`/`execute`.

        Ловит мутацию: подсказка сама регистрирует наблюдение или
        включает в нём задачу (`register_observation`/`add_observation_tasks`
        внутри launch_hint) — снимок таблиц меняется.
        """
        source = inspect.getsource(cycle_hint_module())
        self.assertNotIn("SELECT", source)
        self.assertNotIn("execute", source)
        for case in ("в", "а", "б"):
            if case == "а":
                self.observe()
            if case == "б":
                store.disable_task_observation(self.conn, self.TASK)
            for cmd in COMMANDS:
                with self.subTest(case=case, cmd=cmd, seed=self.seed):
                    before = self.snapshot()
                    launch_hint(self.conn, self.TASK, cmd,
                                           self.rng.choice(NOTES))
                    self.assertEqual(self.snapshot(), before, f"зерно: {self.seed}")


class CommandHintEndToEndTest(LightTransitionSandbox):
    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {
            config.ARTEL_ROLE_ENV: "",
            "ARTEL_SESSION_ID": _token(self.rng, "session")})
        env.start()
        self.addCleanup(env.stop)
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)

    def test_ac9_new_tz_hint_registers_observation(self):
        """`new --tz` без наблюдений печатает подсказку случая «в».

        Оператор заводит задачу из файла ТЗ командой `artel.py new
        "<название>" --tz <файл>`: вывод несёт `observe register` с
        `--tasks <новый id>` и строку `run <новый id> --client`.

        Ловит мутацию: catalog печатает старую голую строку `затем:
        artel.py run <id>  (запуск analyst)` мимо launch_hint.
        """
        tz = self.root / "tz.md"
        tz.write_text("# ТЗ\n\nТребуется:\n1. Сделать отчёт.\n", encoding="utf-8")
        with mock.patch.object(sys, "argv", ["artel.py", "new", "Отчёт", "--tz", str(tz)]):
            out = capture(artel.main)
        ids = [task_id for task_id in re.findall(r"\[([0-9A-Z]{26})\]", out)]
        self.assertTrue(ids, f"зерно: {self.seed}; вывод: {out!r}")
        task_id = ids[0]
        self.assertIn("observe register", out, f"зерно: {self.seed}; вывод: {out!r}")
        self.assertIn(f"--tasks {task_id}", out, f"зерно: {self.seed}; вывод: {out!r}")
        self.assertIn(f"run {task_id} --client", out, f"зерно: {self.seed}; вывод: {out!r}")

    def test_ac9_auto_stopped_by_stop_hints_observe_add(self):
        """`stop` во время `auto` при наблюдении текущей сессии — подсказка случая «б».

        Задача в `in_dev` включена в активное свежее наблюдение текущей
        сессии и проекта; `auto` идёт в процессе теста, шаг роли
        (подменённый `runner.cmd_run`) выполняет `artel.py stop <id>` —
        настоящий SIGTERM своему процессу выключает задачу в наблюдении,
        цикл останавливается на границе шагов. Итог `auto` предлагает
        `observe add <ID наблюдения> --tasks <id>` и `--client/--chat`
        этого наблюдения.

        Ловит мутацию: auto печатает при остановке старую строку
        `artel.py auto <id> — продолжит отсюда` мимо launch_hint, и
        Оператор после `stop` упирается в отказ «нет активного
        наблюдения».
        """
        conn = store.db()
        client = self.rng.choice(CLIENTS)
        chat = _token(self.rng, "chat")
        observation_id = store.register_observation(
            conn, store.task_target(conn, self.TASK), client, chat,
            os.environ["ARTEL_SESSION_ID"], [self.TASK])
        store.touch_observation(conn, observation_id)
        self.set_state("in_dev")
        stops = []

        def role_step_then_stop(task_id, session_id=None):
            if not stops:
                with mock.patch.object(sys, "argv", ["artel.py", "stop", task_id]):
                    stops.append(capture(artel.main))

        with mock.patch.object(runner, "cmd_run", side_effect=role_step_then_stop):
            out = capture(auto.cmd_auto, self.TASK)
        detail = f"зерно: {self.seed}; вывод: {out!r}"
        self.assertEqual(len(stops), 1, detail)
        self.assertEqual(store.observation_tasks(conn, observation_id), [], detail)
        self.assertIn(f"observe add {observation_id} --tasks {self.TASK}", out, detail)
        self.assertIn(f"--client {client} --chat {chat}", out, detail)
        self.assertNotIn("observe register", out, detail)
