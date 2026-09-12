"""Общие помощники приёмочной планки очереди мержа FIFO (задача
01M291EPQ2VFGCHZTXXC81616V).

Тонкая надстройка НАД `tests.sandbox.TmpRootTest` (не копия её патчей —
`gitcmd.show`/`ls_tree_files`/workspace здесь не нужны, тесты этой планки
не проходят FSM-переходы, только вызывают `fsm_merge_gate.
_cmd_approve_merge_gate_cycle` напрямую на уже заведённых задачах
`merge_gate`, тем же приёмом, что `tests/test_merge_gate_ci_wait.py`).

`QueueSandbox` даёт три готовые задачи (A/B/C) на `merge_gate` и
управляемую точку приостановки цикла approve на каждом опросе очереди:
`time.sleep` подменён диспетчером по task_id ТЕКУЩЕГО потока
(`threading.local`), который блокируется на своём `threading.Event`,
пока тест явно не разрешит следующий шаг (`advance`). Это позволяет
держать несколько approve «застрявшими» на разных опросах одновременно
и продвигать их по одному — тот же класс приёма, что
`tests/test_merge_lock.py::ConcurrentAcquireTest` (отдельный поток на
участника, общая БД), расширенный управляемой, а не гоночной,
синхронизацией (нужно детерминированно проверить ИМЕННО порядок и то,
кто получает освободившееся окно, не просто «ровно один выигрывает»).
"""
import threading
import time
from unittest import mock

from orchestrator import catalog, config, fsm_merge_gate, store
from tests.sandbox import TmpRootTest, capture, _dead_pid, _ts_ago  # noqa: F401


class QueueSandbox(TmpRootTest):
    TASK_A = "T001"
    TASK_B = "T002"
    TASK_C = "T003"
    BRANCH = {
        "T001": "task/t001-a",
        "T002": "task/t002-b",
        "T003": "task/t003-c",
    }

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for tid in (self.TASK_A, self.TASK_B, self.TASK_C):
            store.insert_task(store.db(), tid, tid, "merge_gate",
                              self.BRANCH[tid], config.DEFAULT_TARGET, 25.0)
        self._local = threading.local()
        self.ready: dict[str, threading.Event] = {}
        self.proceed: dict[str, threading.Event] = {}
        self.done: list[str] = []
        self.body_calls: list[str] = []
        self.sleep_seconds: dict[str, list[float]] = {}
        self._threads: list[threading.Thread] = []
        self._real_sleep = time.sleep
        self._sleep_patcher = mock.patch.object(time, "sleep",
                                                self._sleep_dispatch)
        self._body_patcher = mock.patch.object(
            fsm_merge_gate, "_cmd_approve_merge_gate", self._fake_body)
        self._sleep_patcher.start()
        self._body_patcher.start()
        self.addCleanup(self._sleep_patcher.stop)
        self.addCleanup(self._body_patcher.stop)
        self.addCleanup(self._drain_threads)

    def _drain_threads(self) -> None:
        """Не даёт застрявшему потоку одного теста переживать его и
        ловить чужие моки следующего (`mock.patch.object` глобален на
        модуль) — до 2 секунд реального времени методично снимает все
        `proceed`, пока хоть один поток этой песочницы жив, затем
        джойнит всех с запасом. Обнаружено на первом прогоне этой планки:
        поток одного теста, не дождавшийся `join` в его же коде, поймал
        `_wait_for_branch_ci_green`, подменённый ДРУГИМ, следующим тестом."""
        deadline = time.monotonic() + 2.0
        while any(t.is_alive() for t in self._threads) and time.monotonic() < deadline:
            for event in self.proceed.values():
                event.set()
            self._real_sleep(0.02)
        for t in self._threads:
            t.join(timeout=2)

    def _fake_body(self, conn, task_id, state, t, confirmed_ci_note=None):
        self.body_calls.append(task_id)
        return ("done",)

    def _sleep_dispatch(self, seconds: float) -> None:
        tid = self._local.task_id
        self.sleep_seconds.setdefault(tid, []).append(seconds)
        self.ready[tid].set()
        self.proceed[tid].wait(timeout=5)
        self.proceed[tid].clear()

    def start_waiting(self, task_id: str, sid: str | None = None) -> threading.Thread:
        """Стартует цикл approve этой задачи в отдельном потоке и блокирует
        тест до её первого опроса (первый вызов `time.sleep` внутри цикла
        ожидания очереди/CI) — имитирует «застрявший на опросе» реальный
        процесс без настоящего ожидания."""
        sid = sid or f"sess-{task_id.lower()}"
        self.ready[task_id] = threading.Event()
        self.proceed[task_id] = threading.Event()

        def worker():
            self._local.task_id = task_id
            fsm_merge_gate._cmd_approve_merge_gate_cycle(
                store.db(), task_id, sid,
                {"branch": self.BRANCH[task_id]}, "merge_gate")
            self.done.append(task_id)

        t = threading.Thread(target=worker, daemon=True)
        self._threads.append(t)
        t.start()
        self.assertTrue(self.ready[task_id].wait(timeout=5),
                        f"{task_id} обязана дойти до первого опроса")
        return t

    def advance(self, task_id: str, timeout: float = 5) -> bool:
        """Пропускает задаче ровно один опрос и ждёт следующего (либо
        завершения цикла — тогда `ready[task_id]` больше никогда не
        взводится, вызывающий код должен ждать завершения потока отдельно)."""
        self.ready[task_id].clear()
        self.proceed[task_id].set()
        return self.ready[task_id].wait(timeout=timeout)

    def seed_holder(self, task_id: str, session_id: str) -> None:
        """Держатель мьютекса на ЧУЖОМ host (тот же приём, что все сценарии
        «отказа» `tests/test_merge_lock.py` — `RunWindowTest.test_refusal_
        exits_without_running_the_body` и др.): `_holder_is_dead` не
        проверяет pid чужого host вовсе, значит держатель гарантированно
        считается живым независимо от того, существует ли переданный pid
        реально — без этого приёма держатель со случайным pid на ЭТОМ host
        воспринимался бы мёртвым и перехватывался немедленно, что и
        произошло на первом прогоне этой планки (pid 111 почти наверняка
        не запущен на машине теста — не мутация, баг самого теста)."""
        store.set_merge_lock(store.db(), task_id, session_id, 111,
                             "holder-host", store.now())
