"""Юнит-тесты отвязки `run`/`auto` от процесса сессии Оператора (SPEC
01M1NWCHVTYQ0M8PCJ1YJ2N78P): разбор argv, запуск отвязанного процесса,
`stop`, `force` у lease и точечный SIGKILL держателя при `kill`.

Приёмочные тесты (tasks/01M1TNMBY8G3AH3MYCB07RW14N/acceptance_tests)
кроют AC-1..AC-13 сквозным путём (реальный `python3 orchestrator/artel.py
...` отдельным процессом ОС) — здесь те же модули в изоляции, теми же
мок-приёмами, что уже используют `tests/test_lease.py`/`tests/
test_kill_cleanup.py` (эти два файла не правятся: AC-13 требует их
зелёными БЕЗ изменений, новое покрытие — отдельным файлом).
"""
import os
import signal
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, catalog, cleanup, config, lease, store  # noqa: E402
from tests.sandbox import TmpRootTest, _dead_pid, _ts_ago, capture  # noqa: E402
from tests.test_kill_cleanup import TmpRepoTest  # noqa: E402

_REAL_OS_KILL = os.kill


def _signal_only_kill(mod):
    """`mock.patch.object(mod.os, "kill", side_effect=...)` — `os` один и
    тот же объект модуля для ЛЮБОГО импортёра (`cleanup.os`/`artel.os`/
    `liveness.os`): подмена без разбора перехватила бы и `liveness.
    _pid_alive`'s собственный `os.kill(pid, 0)`, ломая живость проверяемого
    pid внутри самого теста. Сигнал 0 идёт настоящим `os.kill` (только он
    отвечает правду о живости), остальные сигналы — молча записываются
    моком, не долетая до реального процесса."""
    def fake(pid, sig):
        if sig == 0:
            return _REAL_OS_KILL(pid, sig)
        return None
    return mock.patch.object(mod.os, "kill", side_effect=fake)


def _terminating_calls(kill_mock) -> list:
    """Вызовы `kill_mock`, кроме сигнала 0 (проверка живости `liveness`,
    не намеренная отправка сигнала самим тестируемым кодом)."""
    return [c for c in kill_mock.call_args_list if c.args[1] != 0]


class TaskIdAndAttachTest(unittest.TestCase):

    def test_bare_task_id_is_not_attach(self):
        """Ловит мутацию: `attach` по умолчанию `True` (или парсинг вообще
        игнорирует отсутствие флага) — тест красен, если голый id без
        `--attach` даёт что-то, кроме `False`."""
        self.assertEqual(artel._task_id_and_attach(["T001"], "usage"),
                         ("T001", False))

    def test_trailing_attach_flag_is_detected(self):
        """Ловит мутацию: `--attach` ищется только в фиксированной позиции
        (например, только первым аргументом) — тест красен, если флаг
        последним элементом `rest` не распознаётся."""
        self.assertEqual(
            artel._task_id_and_attach(["T001", "--attach"], "usage"),
            ("T001", True))

    def test_leading_attach_flag_is_detected(self):
        """Ловит мутацию: разбор ищет `--attach` только среди хвостовых
        аргументов — тест красен, если флаг ПЕРЕД id остаётся
        незамеченным (например, ошибочно принят за сам task_id)."""
        self.assertEqual(
            artel._task_id_and_attach(["--attach", "T001"], "usage"),
            ("T001", True))

    def test_missing_task_id_exits_with_usage(self):
        """Ловит мутацию: пустой `rest` не завершается `sys.exit` (падает
        позже на `positional[0]` из пустого списка) либо текст usage не
        попадает в сообщение — тест красен на отсутствии `SystemExit`
        или на потере строки usage."""
        with self.assertRaises(SystemExit) as ctx:
            artel._task_id_and_attach([], "auto <id> [--attach]")
        self.assertIn("auto <id> [--attach]", str(ctx.exception))

    def test_bare_attach_flag_without_task_id_exits(self):
        """Ловит мутацию: `--attach` без id не отфильтровывается из
        позиционных аргументов раньше проверки на пустоту — тест красен,
        если такой вызов НЕ кидает `SystemExit` (флаг ошибочно принят за
        task_id)."""
        with self.assertRaises(SystemExit):
            artel._task_id_and_attach(["--attach"], "usage")


class LaunchDetachedTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _popen_mock(self, pid: int = 4242):
        proc = mock.Mock()
        proc.pid = pid
        return mock.patch.object(artel.subprocess, "Popen", return_value=proc)

    def test_spawns_itself_with_attach_and_detached_session(self):
        """Ловит мутацию: детач зовёт `Popen` без `start_new_session=True`
        (процесс не переживёт SIGHUP родителя, AC-5), без `-u` (stdout
        буферизуется, лог выглядит пустым живьём, AC-3), не тем
        executable/файлом (перезапуск не себя же) или не дописывает
        `--attach` последними тремя аргументами (самозапуск зациклился бы
        на повторный детач) — любое из этого красит соответствующий
        assert."""
        with self._popen_mock(pid=4242) as popen:
            out = capture(artel._launch_detached, "auto", self.TASK)

        popen.assert_called_once()
        args, kwargs = popen.call_args
        argv = args[0]
        self.assertEqual(argv[0], sys.executable)
        self.assertIn("-u", argv)
        self.assertEqual(argv[-3:], ["auto", self.TASK, "--attach"])
        self.assertTrue(kwargs["start_new_session"],
                        "не отвязан от группы/сессии — переживёт SIGHUP "
                        "родителя (AC-5)")
        self.assertEqual(kwargs["stderr"], artel.subprocess.STDOUT)
        self.assertEqual(kwargs["stdin"], artel.subprocess.DEVNULL)

        self.assertIn("pid 4242", out)
        self.assertIn(f"artel.py log {self.TASK}", out)

    def test_log_path_follows_task_cmd_n_pattern_and_is_created(self):
        """Ловит мутацию: лог создаётся ЛЕНИВО (открывается только внутри
        отвязанного процесса, не до `Popen` вызывающей командой) — тест
        красен на `expected.exists()`, потому что мок `Popen` не создаёт
        реального дочернего процесса, файл появился бы только от кода
        `_launch_detached` самого. Мутация имени файла (не
        `<id>-<cmd>-<n>.log`) красит `assertIn` на пути."""
        with self._popen_mock():
            out = capture(artel._launch_detached, "auto", self.TASK)

        expected = config.LOGS / f"{self.TASK}-auto-1.log"
        self.assertIn(str(expected), out)
        self.assertTrue(expected.exists(),
                        "лог обязан быть создан ДО возврата команды, не "
                        "лениво отвязанным процессом")

    def test_second_launch_increments_the_log_number(self):
        """Ловит мутацию: номер лога не растёт от уже существующих файлов
        (хардкод `n=1` или счётчик не читает `config.LOGS.glob`) — второй
        вызов переписал бы лог первого поверх, тест красен на имени
        файла второго вызова."""
        with self._popen_mock():
            capture(artel._launch_detached, "auto", self.TASK)
        with self._popen_mock():
            out2 = capture(artel._launch_detached, "auto", self.TASK)

        self.assertIn(str(config.LOGS / f"{self.TASK}-auto-2.log"), out2)

    def test_run_and_auto_logs_do_not_collide(self):
        """Ловит мутацию: счётчик номера лога общий на задачу, не отдельный
        на префикс `<id>-<cmd>-` — `run` и `auto` одной задачи писали бы
        в один и тот же путь (`-1.log` у обоих) вместо раздельных
        `run-1.log`/`auto-1.log`, тест красен на пути второго вызова."""
        with self._popen_mock():
            out_run = capture(artel._launch_detached, "run", self.TASK)
        with self._popen_mock():
            out_auto = capture(artel._launch_detached, "auto", self.TASK)

        self.assertIn(str(config.LOGS / f"{self.TASK}-run-1.log"), out_run)
        self.assertIn(str(config.LOGS / f"{self.TASK}-auto-1.log"), out_auto)

    def test_task_id_prefix_is_resolved_to_full_id_before_spawning(self):
        """Ловит мутацию: `_launch_detached` передаёт дочернему процессу
        сырой (возможно, префиксный) `task_id`, не результат
        `store.resolve_task_id` — тест красен, если argv содержит
        исходный префикс вместо полного id (гонка с новой задачей того
        же префикса адресовала бы не ту задачу)."""
        prefix = self.TASK[:4]
        with self._popen_mock() as popen:
            capture(artel._launch_detached, "auto", prefix)

        args, _ = popen.call_args
        self.assertEqual(args[0][-2], self.TASK,
                         "дочерний процесс обязан получить полный id, не "
                         "префикс — иначе гонка с новой задачей того же "
                         "префикса адресует не ту задачу")

    def test_refuses_to_spawn_when_a_live_lease_already_exists(self):
        """R1-F3 (REVIEW.md итерации 1): дешёвая проверка занятости ДО
        спавна — без неё повторный `run`/`auto` при уже идущем цикле
        молча печатал бы «отвязан: pid …» и падал бы только внутри
        свежего процесса, отказ был бы виден лишь в его логе.

        Ловит мутацию: предспавновая проверка `lease.is_live` отсутствует
        или не останавливает запуск — тест красен, если `Popen`
        вызывается, несмотря на уже живой lease задачи (повторный запуск
        молча плодил бы второй отвязанный процесс поверх идущего цикла)."""
        store.insert_lease(store.db(), self.TASK, "cycle-session", 4242,
                           socket.gethostname(), store.now())

        with self._popen_mock() as popen:
            with self.assertRaises(SystemExit) as ctx:
                artel._launch_detached("auto", self.TASK)

        popen.assert_not_called()
        self.assertIn("живой lease", str(ctx.exception))


class CmdStopTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _seed_lease(self, pid: int, hostname: str) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session", pid,
                           hostname, store.now())

    def test_sends_sigterm_to_the_lease_holder_pid(self):
        """Ловит мутацию: `_cmd_stop` шлёт не `SIGTERM` (например
        `SIGKILL`, смешение с `kill`) или адресует не pid держателя lease
        — `_terminating_calls` не совпал бы с ожидаемым единственным
        `mock.call(os.getpid(), signal.SIGTERM)`."""
        self._seed_lease(os.getpid(), socket.gethostname())

        with _signal_only_kill(artel) as kill:
            out = capture(artel._cmd_stop, self.TASK)

        self.assertEqual(_terminating_calls(kill),
                         [mock.call(os.getpid(), signal.SIGTERM)])
        self.assertIn(str(os.getpid()), out)

    def test_no_lease_exits_without_signalling(self):
        """Ловит мутацию: отсутствие проверки `row is None` — код упал бы
        на `row["hostname"]` необработанным `TypeError` вместо дружелюбного
        `sys.exit`, либо (что опаснее) послал бы сигнал произвольному pid
        по умолчанию; тест красен на отсутствии `SystemExit` или на
        непустом списке отправленных сигналов."""
        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("нечего останавливать", str(ctx.exception))

    def test_foreign_host_holder_is_refused_without_signalling(self):
        """Ловит мутацию: проверка `hostname` пропущена или сравнивает не
        с `socket.gethostname()` — код послал бы `SIGTERM` числу `4242`
        на ЭТОЙ машине по случайному совпадению pid, адресуя посторонний
        процесс; тест красен на непустом списке отправленных сигналов."""
        self._seed_lease(4242, "other-host.invalid")

        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("other-host.invalid", str(ctx.exception))

    def test_already_dead_holder_pid_is_reported_without_signalling(self):
        """Ловит мутацию: проверка `liveness._pid_alive` перед отправкой
        сигнала пропущена — код попытался бы `os.kill` уже мёртвого pid
        (шумный `ProcessLookupError` или, хуже, молчаливое попадание в
        переиспользованный чужой pid); тест красен на непустом списке
        отправленных сигналов или на отсутствии узнаваемого текста отказа."""
        self._seed_lease(_dead_pid(), socket.gethostname())

        with _signal_only_kill(artel) as kill:
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertIn("уже не существует", str(ctx.exception))

    def test_process_lookup_error_race_is_reported_not_raised(self):
        """Pid жив по проверке `liveness`, но успевает умереть между ней и
        самим `os.kill` — гонка, а не отказ, репортится тем же текстом.

        Ловит мутацию: `ProcessLookupError` из `os.kill` не перехвачен —
        исключение всплыло бы необработанным вместо дружелюбного
        `sys.exit`; тест красен на отсутствии узнаваемого текста отказа
        в сообщении `SystemExit`."""
        self._seed_lease(os.getpid(), socket.gethostname())

        def fake(pid, sig):
            if sig == 0:
                return _REAL_OS_KILL(pid, sig)
            raise ProcessLookupError

        with mock.patch.object(artel.os, "kill", side_effect=fake):
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_stop(self.TASK)

        self.assertIn("уже не существует", str(ctx.exception))


class LeaseForceTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def _seed_foreign_fresh_lease(self) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", 999, socket.gethostname(), store.now()))
        conn.commit()

    def test_without_force_a_fresh_foreign_lease_refuses(self):
        """Ловит мутацию: `force` по умолчанию `True` (или отказ проверки
        свежести lease пропущен, когда `force` не передан) — тест красен,
        если вызов БЕЗ `force` всё равно захватывает свежий чужой lease
        (`refusal` вернулось бы `None`)."""
        self._seed_foreign_fresh_lease()

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-kill")

        self.assertIsNotNone(refusal)
        self.assertFalse(fresh)

    def test_force_overrides_a_fresh_foreign_lease(self):
        """AC-10: `kill` обязан прервать задачу немедленно, даже если lease
        держит живой отвязанный цикл со свежим heartbeat.

        Ловит мутацию: `force=True` не реализован (параметр принимается,
        но не меняет исход) — тест красен на `refusal is not None` или на
        том, что `leases.session_id` не переписан на `sess-kill`."""
        self._seed_foreign_fresh_lease()

        refusal, fresh = lease.acquire(store.db(), self.TASK, "sess-kill",
                                       force=True)

        self.assertIsNone(refusal)
        row = store.lease_row(store.db(), self.TASK)
        self.assertEqual(row["session_id"], "sess-kill")

    def test_force_intercept_names_kill_switch_in_the_journal(self):
        """Ловит мутацию: перехват СВЕЖЕГО чужого lease через `force`
        журналируется той же безликой причиной, что и обычный перехват
        протухшего/мёртвого держателя (требование 6 — особая причина
        «kill switch» именно для этого случая) — тест красен, если
        `detail` не содержит «kill switch»."""
        self._seed_foreign_fresh_lease()

        lease.acquire(store.db(), self.TASK, "sess-kill", force=True)

        detail = store.task_steps(store.db(), self.TASK)[-1]["detail"]
        self.assertIn("kill switch", detail)

    def test_force_on_a_stale_lease_keeps_the_pid_dead_cause(self):
        """`force=True` не подменяет причину, когда перехват и без него
        законен (протухший/мёртвый держатель) — специальная причина
        «kill switch» только для СВЕЖЕГО lease (требование 6).

        Ловит мутацию: причина «kill switch» пишется безусловно при
        `force=True`, не только для свежего lease — тест красен, если
        `detail` для СТАРОГО lease содержит «kill switch» вместо
        «мёртв»."""
        conn = store.db()
        stale_ts = _ts_ago(config.LEASE_STALE_AFTER_SEC + 1)
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-holder", _dead_pid(), socket.gethostname(),
             stale_ts))
        conn.commit()

        lease.acquire(store.db(), self.TASK, "sess-kill", force=True)

        detail = store.task_steps(store.db(), self.TASK)[-1]["detail"]
        self.assertNotIn("kill switch", detail)
        self.assertIn("мёртв", detail)


class KillSignalsDetachedHolderTest(TmpRepoTest):
    """`cleanup.cmd_kill` (AC-10): SIGKILL держателя lease, снятого ДО
    `force=True` перезаписи (`holder_before`), если он живой и на этом
    host."""

    def _seed_lease(self, pid: int, hostname: str) -> None:
        store.insert_lease(store.db(), self.TASK, "cycle-session", pid,
                           hostname, store.now())

    def test_kill_sends_sigkill_to_the_live_same_host_holder(self):
        """Ловит мутацию: снимок держателя (`holder_before`) берётся ПОСЛЕ
        `lease.acquire(force=True)`, когда строка уже переписана на
        сессию `kill`, — сигнал ушёл бы не тому pid (себе) или не ушёл
        бы вовсе; тест красен, если `_terminating_calls` не содержит
        ровно `mock.call(os.getpid(), signal.SIGKILL)`."""
        self._seed_lease(os.getpid(), socket.gethostname())

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill),
                         [mock.call(os.getpid(), signal.SIGKILL)])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_does_not_signal_a_foreign_host_holder(self):
        """Ловит мутацию: `cmd_kill` не сверяет `hostname` держателя перед
        SIGKILL — отправил бы сигнал числу `4242` на ЭТОЙ машине по
        случайному совпадению pid, адресуя посторонний процесс; тест
        красен на непустом списке отправленных сигналов."""
        self._seed_lease(4242, "other-host.invalid")

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_does_not_signal_an_already_dead_holder(self):
        """Ловит мутацию: `cmd_kill` не проверяет живость держателя перед
        SIGKILL — попытался бы убить уже мёртвый (возможно, переиспользо-
        ванный чужим процессом) pid; тест красен на непустом списке
        отправленных сигналов."""
        self._seed_lease(_dead_pid(), socket.gethostname())

        with _signal_only_kill(cleanup) as kill:
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(_terminating_calls(kill), [])
        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_completes_even_if_the_signal_itself_fails(self):
        """Ловит мутацию: `OSError` из `os.kill` (SIGKILL держателя) не
        перехвачен внутри `cmd_kill` — уборка (снятие lease, смена
        состояния на `killed`) упала бы вместе с исключением вместо
        того, чтобы завершиться штатно; тест красен, если состояние
        задачи не стало `killed`."""
        self._seed_lease(os.getpid(), socket.gethostname())

        def fake(pid, sig):
            if sig == 0:
                return _REAL_OS_KILL(pid, sig)
            raise OSError

        with mock.patch.object(cleanup.os, "kill", side_effect=fake):
            self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")

    def test_kill_without_any_lease_does_not_crash(self):
        """Ловит мутацию: снимок держателя (`holder_before`) не
        учитывает отсутствие lease (`None`) — обращение к его полям
        (`pid`/`hostname`) упало бы `TypeError` вместо штатного
        перехода в `killed` без единого сигнала."""
        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")


if __name__ == "__main__":
    unittest.main()


class WaitZoneFlagHotfix22Test(TmpRootTest):
    """Hotfix №22 (11.09): `auto <id> --wait-zone` — флаг разбирается,
    едет в отделённый процесс, а неизвестный флаг даёт отказ, а не
    молчаливый старт без ожидания зоны."""
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_wait_zone_flag_reaches_the_detached_child_argv(self):
        """Ловит мутацию: `_cmd_auto_or_detach` роняет `--wait-zone` при
        детаче — дочерний argv обязан нести флаг ПЕРЕД `--attach`."""
        proc = mock.Mock()
        proc.pid = 4242
        with mock.patch.object(artel.subprocess, "Popen",
                               return_value=proc) as popen:
            capture(artel._cmd_auto_or_detach, [self.TASK, "--wait-zone"])
        argv = popen.call_args.args[0]
        self.assertEqual(argv[-4:],
                         ["auto", self.TASK, "--wait-zone", "--attach"])

    def test_attached_auto_passes_wait_zone_to_cmd_auto(self):
        """Ловит мутацию: путь `--attach` зовёт `cmd_auto(task_id)` без
        `wait_zone=True` — режим ожидания зоны терялся бы молча."""
        with mock.patch.object(artel.auto, "cmd_auto") as cmd_auto:
            artel._cmd_auto_or_detach([self.TASK, "--attach", "--wait-zone"])
        cmd_auto.assert_called_once_with(self.TASK, wait_zone=True)

    def test_unknown_flag_is_refused_not_swallowed(self):
        """Ловит мутацию: неизвестный флаг фильтруется как «лишний
        позиционный» и команда стартует, будто флага не было."""
        with self.assertRaises(SystemExit) as ctx:
            artel._task_id_and_attach([self.TASK, "--wait-zon"], "usage")
        self.assertIn("--wait-zon", str(ctx.exception))
        with self.assertRaises(SystemExit) as ctx:
            artel._cmd_run_or_detach([self.TASK, "--wait-zone"])
        self.assertIn("--wait-zone", str(ctx.exception))
