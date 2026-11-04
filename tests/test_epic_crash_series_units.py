"""Юнит-тесты счёта аварий дочернего `auto` надзора эпика (SPEC
01M6HVPMYY2Q56JZ64KD28FTWK, требование 4; ANSWER-4) на свойства вне
долгоживущих файлов задачи: запуск и старт дочернего сопоставляются по pid,
а не по порядку записей; выход, заметенный раньше записи `pause --now`,
аварией не засчитывается; подъём бюджета из `escalated` счёт не сбрасывает.
"""
import socket
from datetime import datetime, timezone
from unittest import mock

from orchestrator import auto, config, lease, store, zone_lock
from tests.sandbox import InitializedTmpRootTest

EPIC = "E01M6CRASHSERIES"
TASK = "01M6CRASHSERIES0000000001"


class _EpicTaskJournal(InitializedTmpRootTest):
    """Задача эпика и записи журнала её запусков — общий стенд файла."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_epic(self.conn, EPIC, config.DEFAULT_TARGET, "Эпик", "Цель", None)
        store.insert_task(self.conn, TASK, "Задача", "in_dev",
                          f"task/{TASK.lower()}-epik", config.DEFAULT_TARGET,
                          1000.0, epic_id=EPIC)
        self.conn.commit()

    def journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(self.conn, TASK, actor, action, detail)

    def launch_record(self, pid: int) -> None:
        self.journal(store.EPIC_SUPERVISOR_ACTOR, auto.EPIC_CHILD_LAUNCH_ACTION,
                     f"эпик {EPIC}: pid {pid}")

    def start(self, pid: int) -> None:
        self.journal("operator", zone_lock.AUTO_START_ACTION,
                     f"состояние in_dev, лимит {config.AUTO_MAX_STEPS} шагов, pid {pid}")

    def aborted_run(self, pid: int) -> None:
        self.launch_record(pid)
        self.start(pid)
        self.journal("operator", zone_lock.CYCLE_ABORTED_ACTION, "RuntimeError: обрыв")

    def runs(self) -> list:
        rows = store.task_steps(self.conn, TASK)
        return rows, auto._child_runs(rows, None)


class CrashSeriesTest(_EpicTaskJournal):

    def test_fast_child_start_before_launch_record_counts_by_pid(self):
        """«auto старт» и остановка быстрого дочернего легли раньше записи его запуска — это его запуск, не авария.

        Сценарий: авария первого запуска, `epic retry`; второй дочерний
        успел записать старт со своим pid и штатную остановку раньше, чем
        надзор записал его запуск; затем две аварии. Второй запуск —
        штатная остановка, аварий подряд после `epic retry` — две.

        Ловит мутацию: окно запуска начинается с записи запуска, без
        сверки pid старта (второй запуск — авария «нет старта», аварий
        подряд три — ложный предел).
        """
        self.aborted_run(101)
        self.journal("operator", auto.EPIC_RETRY_ACTION, "перезапуск")
        self.start(202)
        self.journal("operator", zone_lock.AUTO_STOPPED_ACTION, "in_dev: лимит шагов")
        self.launch_record(202)
        self.aborted_run(303)
        self.aborted_run(404)

        rows, runs = self.runs()

        self.assertEqual([run.outcome for run in runs],
                         [auto._RUN_CRASH, auto._RUN_STOPPED,
                          auto._RUN_CRASH, auto._RUN_CRASH])
        self.assertEqual(auto._crash_streak(rows, runs), 2)

    def test_budget_return_from_escalated_does_not_reset(self):
        """`state -> in_dev` актора `operator` с деталью подъёма бюджета счёт аварий не сбрасывает, `approve` — сбрасывает.

        Сценарий: две аварии, переход `operator` «бюджет поднят,
        продолжаем», третья авария — три подряд; тот же сценарий с
        переходом `operator` без этой детали (`approve`) — одна.

        Ловит мутацию: любой `state -> …` актора `operator` считается
        `approve` и сбрасывает счёт (подъём бюджета снимает предел).
        """
        for detail, expected in (("бюджет поднят, продолжаем", 3), ("", 1)):
            with self.subTest(detail=detail):
                self.conn.execute("DELETE FROM steps WHERE task_id=?", (TASK,))
                self.conn.commit()
                self.aborted_run(101)
                self.aborted_run(202)
                self.journal("operator", "state -> in_dev", detail)
                self.aborted_run(303)
                rows, runs = self.runs()
                self.assertEqual(auto._crash_streak(rows, runs), expected)


class PauseNowAfterNoticeTest(_EpicTaskJournal):
    """Выход дочернего заметен опросом раньше, чем `pause --now` записал
    «процесс агента прерван» (ANSWER-4, п. 2)."""

    CHILD = 909090

    def setUp(self):
        super().setUp()
        self.aborted_run(101)
        self.aborted_run(202)
        step_id = self.conn.execute("SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0]
        started = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        store.insert_epic_child(self.conn, EPIC, TASK, self.CHILD,
                                socket.gethostname(), started, step_id)
        self.launch_record(self.CHILD)
        self.start(self.CHILD)
        self.memory = auto._SupervisorMemory()

    def poll(self):
        self.memory.poll += 1
        with mock.patch.object(lease, "process_alive", return_value=False):
            view = auto._epic_view(self.conn, store.get_epic(self.conn, EPIC), self.memory)
        return view.status[TASK]

    def task_alerts(self) -> list:
        return [a for a in store.open_alerts(self.conn, "attention") if a["target"] == TASK]

    def limit_records(self) -> list:
        return [r for r in store.task_steps(self.conn, TASK)
                if r["action"] == auto.EPIC_CRASH_LIMIT_ACTION]

    def test_pause_now_record_after_notice_is_not_a_crash(self):
        """Запись `pause --now` легла после опроса, заметившего выход: следующий опрос аварии не засчитывает.

        Сценарий: две аварии подряд, третий дочерний выходит; первый опрос
        его выход заметил (задача ждёт следующего опроса); затем `pause
        --now` пишет «процесс агента прерван», а пометку паузы ещё не
        поставил; второй опрос — задача держится, записи предела и тревоги
        нет; пауза поставлена — третий опрос тоже.

        Ловит мутацию: исход выхода фиксируется на опросе, заметившем его,
        и не пересчитывается (третья авария подряд — ложная тревога
        предела до пометки паузы).
        """
        self.assertEqual(self.poll(), auto._CRASH_WAIT)
        self.journal("operator", "pause --now: процесс агента прерван",
                     f"pid {self.CHILD} завершён сигналом ОС")

        self.assertEqual(self.poll(), auto._HELD)
        store.update_task(self.conn, TASK, paused=1)
        self.assertEqual(self.poll(), auto._HELD)
        self.assertEqual(self.limit_records(), [])
        self.assertEqual(self.task_alerts(), [])

    def test_third_crash_counted_on_next_poll_once(self):
        """Без записи `pause --now` третья авария засчитана на следующем опросе: одна запись предела и одна тревога за серию.

        Ловит мутацию: предел засчитывается на опросе, заметившем выход
        (нет паузы перед решением); либо запись и тревога повторяются на
        каждом опросе.
        """
        self.assertEqual(self.poll(), auto._CRASH_WAIT)
        self.assertEqual(self.limit_records(), [])
        self.assertEqual(self.poll(), auto._CRASH_LIMIT)
        self.assertEqual(self.poll(), auto._CRASH_LIMIT)
        self.assertEqual(len(self.limit_records()), 1)
        self.assertEqual(len(self.task_alerts()), 1)
