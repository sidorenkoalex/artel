"""Граница полного suite-run для подтверждённого вызывающего шага.

Группа: долгоживущий
Красен до реализации: cmd_suite_run ещё разрешает новый полный прогон developer и миссия предлагает его.

Песочница нужна для связки публичной команды, БД lease и файлов прогона.
Полные наборы не исполняются: подменяется только запуск фонового процесса.
Живая группа текущего процесса записывается теми же публичными операциями
store, которыми runner регистрирует группу агента; переменные окружения
не являются единственным свидетельством принадлежности.
"""
import contextlib
import builtins
import io
import hashlib
import os
import random
import runpy
import socket
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, appendix_tree, brief, config, review, role_prompt, runner, store, suite_lock, suite_run, workspace
from tests.sandbox import RealGitSandbox


class DeveloperSuiteTest(RealGitSandbox):
    def setUp(self):
        super().setUp()
        self.conn = store.db()
        self.use_role_map()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        self.caller = "01M" + "".join(self.rng.choice(alphabet) for _ in range(23))
        self.target = "01M" + "".join(self.rng.choice(alphabet) for _ in range(23))
        for task in (self.caller, self.target):
            store.insert_task(self.conn, task, "Прогон фикстуры", "in_dev",
                              "task/fixture-" + task.lower(), config.DEFAULT_TARGET, 20)
        self.git("branch", "task/fixture-" + self.target.lower())
        self.git("branch", "task/fixture-" + self.caller.lower())
        self.addCleanup(self.conn.close)
        self.engine_calls = []
        self.green = True
        self.output = "1 passed in 0.01s"
        patcher = mock.patch.object(workspace, "path", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=10)
        self.dead_pid = child.pid
        self.env = dict(os.environ)
        self.env.pop(config.ARTEL_ROLE_ENV, None)
        self.env.pop(config.ARTEL_TASK_ENV, None)
        self.env.pop("CODEX_HOME", None)
        self.env["HOME"] = str(self.root / "operator-home")

    def run_in_agent_process(self):
        """Реальная группа агента: держатель lease — родитель вне этой группы."""
        if os.environ.get("ARTEL_SUITE_CONTRACT_CHILD") == self.id():
            self.assertNotEqual(os.getpgid(os.getppid()), os.getpgrp(), self.msg())
            return False
        env = dict(os.environ, ARTEL_SUITE_CONTRACT_CHILD=self.id())
        proc = runner.spawn_agent(
            [sys.executable, "-m", "unittest", self.id()],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            output, errors = proc.communicate(timeout=90)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        print(output)
        self.assertEqual(proc.returncode, 0, self.msg(errors))
        return True

    def msg(self, value=""):
        return f"зерно: {self.seed}; {value}"

    def live_step(self, role="developer", provider="codex"):
        self.use_role_map(roles={role: {"provider": provider}})
        state = next(state for state, name in config.STATE_ROLE.items() if name == role)
        store.update_task(self.conn, self.caller, state=state)
        store.insert_lease(self.conn, self.caller, "fixture-session", os.getppid(),
                           socket.gethostname(), store.now())
        store.update_lease_pgid(self.conn, self.caller, os.getpgrp())
        store.journal(self.conn, self.caller, role, "agent run started",
                      f"роль {role}, провайдер {provider}")
        self.env.update({config.ARTEL_ROLE_ENV: role,
                         config.ARTEL_TASK_ENV: self.caller,
                         "HOME": str(config.ROLE_HOME)})
        if provider == "codex":
            self.env["CODEX_HOME"] = str(config.ROLE_HOME / ".codex")

    def invoke(self, *args):
        buf = io.StringIO()
        code = 0
        with mock.patch.dict(os.environ, self.env, clear=True), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                suite_run.cmd_suite_run(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, buf.getvalue() + (str(code) if code not in (0, None) else "")

    def snapshot(self, folder=None):
        folder = folder or self.root
        return {str(p.relative_to(folder)): (
                    "sqlite read locks" if p.name.endswith("-shm")
                    else hashlib.sha256(p.read_bytes()).hexdigest())
                for p in folder.rglob("*") if p.is_file()}

    @contextlib.contextmanager
    def launches(self, live=False, finish=False):
        original = subprocess.Popen
        launch = mock.Mock(return_value=mock.Mock(pid=os.getpid() if live else self.dead_pid))

        def dispatch(argv, *args, **kwargs):
            if isinstance(argv, (list, tuple)) and any(t in argv for t in (self.target, self.caller)):
                result = launch(argv, *args, **kwargs)
                if finish:
                    self.complete_spawn(argv, kwargs["env"])
                return result
            return original(argv, *args, **kwargs)

        with mock.patch.object(subprocess, "Popen", side_effect=dispatch):
            yield launch

    def complete_spawn(self, argv, env):
        """Исполняет вход фона, моделируя новую группу и подменяя только набор."""
        @contextlib.contextmanager
        def tree(*args, **kwargs):
            yield appendix_tree.SuiteTree(self.root, "", "", "")

        def engine(root, *args, **kwargs):
            self.engine_calls.append((Path(root), kwargs, dict(os.environ)))
            if kwargs.get("log"):
                Path(kwargs["log"]).write_text(self.output)
            return self.green, self.output

        real_getpgid = os.getpgid
        detached = os.getpid() if os.getpid() != os.getpgrp() else self.dead_pid
        def pgid(pid):
            return detached if pid in (0, os.getpid()) else real_getpgid(pid)

        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(os, "getpgrp", return_value=detached), \
                mock.patch.object(os, "getpgid", side_effect=pgid), \
                mock.patch.object(appendix_tree, "suite_tree", side_effect=tree), \
                mock.patch.object(acceptance, "run_full_suite", side_effect=engine), \
                mock.patch.object(sys, "argv", [argv[1], *argv[3:]]):
            if argv[1] == "-c":
                exec(compile(argv[2], "<suite child>", "exec"), {"__name__": "__main__"})
            elif argv[1] == "-m":
                runpy.run_module(argv[2], run_name="__main__")
            else:
                with mock.patch.object(sys, "argv", list(argv[1:])):
                    runpy.run_path(argv[1], run_name="__main__")

    @contextlib.contextmanager
    def write_attempts(self):
        events = []

        def observer(fn, numeric=False, directory=False):
            def observed(*args, **kwargs):
                path = args[0] if args else kwargs.get("file", kwargs.get("path"))
                field = "flags" if numeric else "mode"
                mode = args[1] if len(args) > 1 else kwargs.get(field, 0 if numeric else "r")
                writing = (directory or bool(mode & (os.O_CREAT | os.O_WRONLY | os.O_RDWR))
                           if numeric else any(char in mode for char in "wax+"))
                if writing and path is not None and not isinstance(path, int):
                    location = Path(path).resolve()
                    if location.is_relative_to(self.root):
                        events.append(str(location))
                return fn(*args, **kwargs)
            return observed

        with mock.patch.object(builtins, "open", observer(builtins.open)), \
                mock.patch.object(io, "open", observer(io.open)), \
                mock.patch.object(os, "open", observer(os.open, numeric=True)), \
                mock.patch.object(os, "mkdir", observer(os.mkdir, numeric=True, directory=True)):
            yield events

    def drop_step(self):
        store.release_lease(self.conn, self.caller, "fixture-session")

    def test_ac2_developer_refusal_precedes_every_side_effect(self):
        """Новый полный запуск отказывает до любой записи, в том числе при чужом замке.

        Связка: cmd_suite_run — живая lease — БД и файловое хозяйство.
        Ловит мутацию: проверка developer поставлена после store.db,
        deliver_journal или создания файлов — наблюдатели фиксируют вызов
        либо изменённый снимок вместо чистого отказа.
        """
        if self.run_in_agent_process():
            return
        self.live_step()
        for occupied in (False, True):
            with self.subTest(occupied=occupied):
                if occupied:
                    self.assertIsNone(suite_lock.acquire(self.target), self.msg())
                before = self.snapshot()
                steps = [dict(row) for row in store.all_steps(self.conn)]
                with mock.patch.object(store, "db", wraps=store.db) as db, \
                        mock.patch.object(sqlite3, "connect", wraps=sqlite3.connect) as connects, \
                        mock.patch.object(suite_lock, "deliver_journal",
                                          wraps=suite_lock.deliver_journal) as deliver, \
                        mock.patch.object(suite_lock, "acquire",
                                          wraps=suite_lock.acquire) as acquire, \
                        self.launches() as launch, self.write_attempts() as writes:
                    code, text = self.invoke(self.target)
                self.assertNotIn(code, (0, None), self.msg(text))
                self.assertIn("developer", text.lower(), self.msg(text))
                self.assertRegex(text.lower(), "контракт", self.msg(text))
                self.assertRegex(text.lower(), "адресн|затронут", self.msg(text))
                self.assertRegex(text.lower(), "планк|plank-run", self.msg(text))
                self.assertIn("--failed", text, self.msg(text))
                self.assertFalse(db.called, self.msg("открыта БД на запись"))
                for call in connects.call_args_list:
                    self.assertTrue(call.kwargs.get("uri"), self.msg(call))
                    self.assertIn("mode=ro", str(call.args[0]), self.msg(call))
                self.assertFalse(deliver.called, self.msg("вызван досыл"))
                self.assertFalse(acquire.called, self.msg("взят замок"))
                self.assertFalse(launch.called, self.msg("запущен процесс"))
                self.assertEqual(writes, [], self.msg("попытки записи файлов"))
                self.assertEqual(self.snapshot(), before, self.msg("изменены файлы"))
                self.assertEqual([dict(row) for row in store.all_steps(self.conn)],
                                 steps, self.msg("изменён журнал"))
                suite_lock.release()

    def test_ac3_confirmed_step_survives_missing_role_marker(self):
        """Одна живая группа developer обращается к своей и другой задаче.

        Контексты обоих провайдеров проверяются с маркером и без него;
        состояние другой задачи — review. Роль определяется вызывающим шагом.
        Ловит мутацию: запрет зависит только от ARTEL_ROLE, провайдера или
        состояния запрошенной задачи — один из вызовов запускает фон.
        """
        if self.run_in_agent_process():
            return
        store.update_task(self.conn, self.target, state="review")
        for provider in ("codex", "claude"):
            for marker in (True, False):
                self.live_step(provider=provider)
                if not marker:
                    self.env.pop(config.ARTEL_ROLE_ENV)
                for requested in (self.caller, self.target):
                    with self.subTest(provider=provider, marker=marker, task=requested), \
                            self.launches() as launch:
                        code, text = self.invoke(requested)
                        self.assertNotIn(code, (0, None), self.msg(text))
                        self.assertIn("developer", text.lower(), self.msg(text))
                        self.assertFalse(launch.called, self.msg(text))
                        suite_lock.release()
                self.drop_step()

    def test_ac4_unconfirmed_environment_does_not_identify_developer(self):
        """Маркер, пара переменных и общий HOME без связи процесса не запрещают запуск.

        Каждый случай доходит до подменённого фонового процесса; ложное
        свидетельство lease относится к другому host и не удостоверяет шаг.
        Ловит мутацию: ARTEL_ROLE/HOME или любая lease задачи принимаются
        за доказательство developer — разрешённый запуск получает отказ.
        """
        if self.run_in_agent_process():
            return
        cases = ({config.ARTEL_ROLE_ENV: "developer"},
                 {config.ARTEL_ROLE_ENV: "developer", config.ARTEL_TASK_ENV: self.caller},
                 {config.ARTEL_ROLE_ENV: "случайная-роль"},
                 {"HOME": str(config.ROLE_HOME)})
        original = dict(self.env)
        for context in ("none", "foreign", "reviewer"):
            if context == "foreign":
                store.insert_lease(self.conn, self.caller, "fixture-session", os.getpid(),
                                   "different-host.invalid", store.now())
                store.update_lease_pgid(self.conn, self.caller, os.getpgrp())
            elif context == "reviewer":
                self.drop_step()
                self.live_step("reviewer")
            for values in cases:
                self.env = {**original, **values}
                with self.subTest(values=values, context=context), \
                        self.launches(finish=True) as launch:
                    # Не оставляем живой прогон между независимыми случаями.
                    code, text = self.invoke(self.target)
                    self.assertIn(code, (0, None), self.msg(text))
                    self.assertEqual(launch.call_count, 1, self.msg(text))
                    code, report = self.invoke(self.target, "--wait", "0")
                    self.assertIn(code, (0, None), self.msg(report))
                    self.assertIn("зелёный прогон", report, self.msg(report))

    def test_ac5_operator_and_other_confirmed_roles_keep_full_launch(self):
        """Оператор и подтверждённые прочие роли запускают полный набор задачи in_dev.

        Наблюдаем границу отделения фона: новый сеанс и очищенное окружение.
        Ловит мутацию: запрет распространён на любую роль или состояние in_dev;
        разрешённый фон наследует ARTEL_ROLE либо остаётся в группе шага.
        """
        if self.run_in_agent_process():
            return
        for role in (None, "reviewer", "test_author", "spec_auditor"):
            with self.subTest(role=role):
                if role:
                    self.live_step(role)
                before_calls = len(self.engine_calls)
                with self.launches(finish=True) as launch:
                    code, text = self.invoke(self.target)
                report_code, report = self.invoke(self.target, "--wait", "0")
                self.assertIn(report_code, (0, None), self.msg(report))
                self.assertIn("зелёный прогон", report, self.msg(report))
                self.assertGreater(len(self.engine_calls), before_calls, self.msg(report))
                for _, _, environment in self.engine_calls[before_calls:]:
                    self.assertNotIn(config.ARTEL_ROLE_ENV, environment, self.msg(report))
                self.assertIn(code, (0, None), self.msg(text))
                self.assertEqual(launch.call_count, 1, self.msg(text))
                self.assertNotIn(config.ARTEL_ROLE_ENV,
                                 launch.call_args.kwargs["env"], self.msg(text))
                self.assertTrue(launch.call_args.kwargs.get("start_new_session"), self.msg(text))
                if role:
                    self.drop_step()
        self.assertTrue(any(root != self.root for root, _, _ in self.engine_calls),
                        self.msg("разрешённый фон не дошёл до базы"))

    def test_ac6_confirmed_developer_reruns_only_failed_checks(self):
        """После красного операторского прогона developer повторяет его упавшие id.

        Связка команды, сохранённого результата и фонового входа проверяется
        подменой двигателя тестов; настоящие наборы не запускаются.
        Ловит мутацию: запрет задевает --failed, повтор запускает весь набор
        или базу, отсутствие перечня подменяется полным запуском.
        """
        if self.run_in_agent_process():
            return
        nodes = [f"tests/test_probe.py::test_case_{number}"
                 for number in self.rng.sample(range(10000), 2)]
        self.green = False
        self.output = ("=== short test summary info ===\n" + "\n".join(f"FAILED {node} - AssertionError: fixture" for node in nodes)
                       + "\n2 failed in 0.01s")
        with self.launches(finish=True):
            code, text = self.invoke(self.target)
        self.assertIn(code, (0, None), self.msg(text))
        self.live_step()
        self.engine_calls.clear()
        self.green, self.output = True, "2 passed in 0.01s"
        with self.launches(finish=True) as launch:
            code, text = self.invoke(self.target, "--failed")
        self.assertIn(code, (0, None), self.msg(text))
        self.assertEqual(launch.call_count, 1, self.msg(text))
        self.assertEqual(len(self.engine_calls), 1, self.msg(self.engine_calls))
        self.assertCountEqual(self.engine_calls[0][1]["targets"], nodes, self.msg(text))
        report_code, report = self.invoke(self.target, "--wait", "0")
        self.assertIn(report_code, (0, None), self.msg(report))
        self.assertIn("зелёный прогон", report, self.msg(report))
        for requested, reason in ((self.target, "упавших нет"), (self.caller, "нет")):
            with self.subTest(requested=requested), self.launches() as launch:
                code, text = self.invoke(requested, "--failed")
                self.assertNotIn(code, (0, None), self.msg(text))
                self.assertIn(reason, text, self.msg(text))
                self.assertFalse(launch.called, self.msg(text))

    def test_ac7_confirmed_developer_can_read_status_and_wait(self):
        """Developer читает живой прогон и его завершение, не меняя прогон.

        Проверены зелёный и красный исходы, исчерпание нулевого ожидания,
        отсутствие прогона и ожидание сверх действующего предела.
        Ловит мутацию: ранний запрет перекрывает статус/--wait либо вместо
        чтения запускает второй процесс, меняет файлы прогона или код отчёта.
        """
        if self.run_in_agent_process():
            return
        for green in (True, False):
            with self.subTest(green=green):
                self.env.pop(config.ARTEL_ROLE_ENV, None)
                with self.launches(live=True) as started:
                    code, text = self.invoke(self.target)
                self.assertIn(code, (0, None), self.msg(text))
                argv, env = started.call_args.args[0], started.call_args.kwargs["env"]
                self.live_step()
                for flags in ((), ("--wait", "0"),
                              ("--wait", str(config.SUITE_RUN_MAX_WAIT_MIN + 1))):
                    before = self.snapshot(suite_lock.directory())
                    with self.subTest(flags=flags), self.launches() as launch:
                        code, text = self.invoke(self.target, *flags)
                        if not flags:
                            self.assertIn(code, (0, None), self.msg(text))
                            self.assertIn("идёт", text, self.msg(text))
                        else:
                            self.assertNotIn(code, (0, None), self.msg(text))
                            self.assertIn("прогон", text, self.msg(text))
                        self.assertFalse(launch.called, self.msg(text))
                        self.assertEqual(self.snapshot(suite_lock.directory()), before, self.msg("прогон изменён"))
                self.green = green
                self.output = "1 passed in 0.01s" if green else "1 failed in 0.01s"
                self.complete_spawn(argv, env)
                with self.launches() as launch:
                    code, text = self.invoke(self.target, "--wait", "0")
                self.assertEqual(code, 0 if green else 1, self.msg(text))
                self.assertIn("зелёный прогон" if green else "красный прогон", text, self.msg(text))
                self.assertFalse(launch.called, self.msg(text))
                self.drop_step()
        self.live_step()
        with self.launches() as launch:
            code, text = self.invoke(self.caller, "--wait", "0")
        self.assertNotIn(code, (0, None), self.msg(text))
        self.assertIn("нет ни одного прогона", text, self.msg(text))
        self.assertFalse(launch.called, self.msg(text))

    def test_ac14_gate_engine_is_not_blocked_by_developer_context(self):
        """Штатный двигатель полного гейта сохраняет запуск при контексте developer.

        Подменён лишь системный вызов pytest; сам run_full_suite и общий
        замок настоящие. Связка гейта, lease и запуска проверяется на двух исходах.
        Ловит мутацию: запрет перенесён из команды в общий двигатель —
        системный вызов гейта не происходит либо меняется его исход.
        """
        if self.run_in_agent_process():
            return
        self.live_step()
        (self.root / "tests").mkdir()
        for code in (0, 1):
            with self.subTest(code=code):
                output = "1 passed in 0.01s" if code == 0 else "1 failed in 0.01s"
                called = []
                original = subprocess.run

                def run(argv, *args, **kwargs):
                    if "pytest" in argv:
                        called.append(argv)
                        return subprocess.CompletedProcess(argv, code, output, "")
                    return original(argv, *args, **kwargs)

                with mock.patch.dict(os.environ, self.env, clear=True), \
                        mock.patch.object(subprocess, "run", side_effect=run):
                    green, result = acceptance.run_full_suite(self.root)
                self.assertEqual(green, code == 0, self.msg(result))
                self.assertTrue(called, self.msg(result))
                self.assertIn("tests", called[0], self.msg(called))


class DeveloperMissionTest(unittest.TestCase):
    def test_ac8_mission_describes_restricted_suite_command(self):
        """Сформированный бриф содержит запрет и все разрешённые формы команды.

        Случайные идентификаторы и пути исключают зашитый пример одной задачи.
        Ловит мутацию: миссия по-прежнему предлагает новый полный прогон или
        теряет команду статуса, --wait, --failed, планку либо адресные тесты.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        with mock.patch.object(brief, "developer_brief", return_value=""), \
                mock.patch.object(brief, "step_notes_block", return_value=""), \
                mock.patch.object(review, "review_package", return_value=""):
            for _ in range(3):
                task = "01M" + "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                                       for _ in range(23))
                row = {"branch": "task/fixture", "title": "Фикстура", "reviewed_iter": 0}
                mission, _, _ = role_prompt.mission_brief_package(
                    None, task, row, "developer", "/tmp/fixture-cwd",
                    docs_dir=Path("/tmp/fixture-docs") / task)
                msg = f"зерно: {seed}\n{mission}"
                command = f"python3 {config.ROOT / 'orchestrator' / 'artel.py'} suite-run {task}"
                for form in (command, command + " --wait", command + " --failed", "plank-run"):
                    self.assertIn(form, mission, msg)
                text = " ".join(mission.lower().split())
                self.assertRegex(text, r"(?:полн.{0,100}(?:запрещ|нельзя)|(?:запрещ|нельзя).{0,100}полн)", msg)
                self.assertRegex(text, r"адресн|затронут", msg)
                self.assertRegex(text, r"(?:статус.{0,100}(?:идущ|идёт)|(?:идущ|идёт).{0,100}статус)", msg)
