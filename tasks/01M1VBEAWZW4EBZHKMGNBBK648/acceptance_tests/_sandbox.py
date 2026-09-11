"""Общая песочница приёмочных тестов 01M1VBEAWZW4EBZHKMGNBBK648 («ожидание
зоны штатно в пульте — `auto --wait-zone`, `escalated` держит зону»).

## Допущения интерфейса, которые вводит этот файл (SPEC не называет ни
одну из этих точек по имени буквально — тот же приём, что уже применён
`tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests/_sandbox.py` к
`zone_lock.cmd_zone_release`/`queue_order` до их существования)

- `auto.cmd_auto(task_id, session_id=None, wait_zone=False)` — новый
  keyword-only по духу (но не обязан быть строго keyword-only) параметр:
  `True` — режим ожидания требования 1. Эффективный режим —
  `wait_zone or config.AUTO_WAIT_ZONE_DEFAULT` (см. ниже) — так работает
  дефолт AC-5, не меняющий поведение, пока Оператор его не включит.
- `config.AUTO_WAIT_ZONE_DEFAULT` — новый флаг конфига (bool, дефолт
  `False`), требование 1/AC-5 буквально просит именно такую настройку,
  но не называет её имя — эта песочница патчит его через
  `mock.patch.object(config, "AUTO_WAIT_ZONE_DEFAULT", ..., create=True)`
  (`create=True`, как и `ZONE_WAIT_POLL_SEC`/`ZONE_WAIT_MAX_SEC` ниже —
  до реализации этих имён в `config.py` нет вовсе).
- `config.ZONE_WAIT_POLL_SEC`/`config.ZONE_WAIT_MAX_SEC` — имена ИЗ
  самого SPEC (требования 1, 3) буквально; здесь только `create=True`,
  раз до реализации их нет в модуле.
- Цикл ожидания спит РЕАЛЬНЫМ `time.sleep(config.ZONE_WAIT_POLL_SEC)`
  внутри `orchestrator/auto.py` — тот же приём, что уже применяет
  `_advance_verifying_poll` (`time.sleep(config.VERIFYING_POLL_INTERVAL_SEC)`
  того же модуля) к опросу CI. Тесты перехватывают именно эту точку
  (`mock.patch.object(auto.time, "sleep", ...)`), не изобретая для неё
  соседнее имя.
- Продление heartbeat lease на каждом опросе (требование 1) проверяется
  НЕ вызовом конкретной функции (`lease.acquire` либо прямой
  `store.update_lease` — SPEC не называет ни то, ни другое), а
  наблюдаемым фактом: `leases.heartbeat_ts` задачи меняется между
  соседними опросами цикла — единственная операция, которая касается
  строки `leases` этой задачи ПОСЛЕ начального захвата lease в
  `lease.run_locked` (сам `cmd_auto` его не отпускает и не берёт заново
  до конца вызова), поэтому любое изменение `heartbeat_ts` между двумя
  последовательными опросами и есть искомое продление.
- Записи журнала входа/выхода ожидания (требования 2, AC-2/AC-3) не
  привязаны тестами к конкретному `actor`/`action` — только к ЛИТЕРАЛЬНОЙ
  подстроке из самого SPEC, разыскиваемой по объединённому тексту
  `actor + action + detail` каждой новой строки журнала (тот же приём,
  что уже применяет `journal_tail` ниже, по образцу
  `_sandbox.ZoneSandbox` соседней задачи).
"""
import itertools
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, runner, store  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402
from tests.sandbox import capture  # noqa: E402


def only_on_poll_interval(handler):
    """Оборачивает обработчик `time.sleep` цикла ожидания зоны: реагирует
    ТОЛЬКО на вызовы РОВНО с `config.ZONE_WAIT_POLL_SEC` — остальные
    (например бэкофф ретрая спавна агента внутри `runner._cmd_run`,
    несвязанный с ожиданием зоны) проходят как настоящий тихий `no-op`
    без вызова `handler`.

    Обнаружено валидацией планки стабом (skills/test-authoring.md,
    «провалидируй тесты временным стабом»): глобальный патч `time.sleep`
    ловит АБСОЛЮТНО все вызовы функции в процессе, включая посторонние —
    без фильтра по значению аргумента тест путает «опрос ожидания зоны»
    с «ретрай подряд неудачного спавна агента» и либо считает опросы
    неверно, либо падает на чужом значении `seconds`."""
    def wrapped(seconds):
        if seconds != config.ZONE_WAIT_POLL_SEC:
            return
        return handler(seconds)
    return wrapped


def fake_now_sequence():
    """Каждый вызов — свой момент времени, СТРОГО возрастающий (шаг 1
    секунда), независимо от реальной скорости выполнения теста: секундная
    точность `store.now()` (`"%Y-%m-%d %H:%M:%SZ"`) иначе схлопывает
    несколько вызовов подряд (опрос ожидания с замоканным `time.sleep` —
    без реальной задержки) в один и тот же штамп, и сравнение «heartbeat
    изменился между опросами» ложно не проходит даже при верной
    реализации. Используется как `side_effect=` патча `store.now`."""
    base = datetime(2026, 9, 6, tzinfo=timezone.utc)
    counter = itertools.count()

    def fake_now() -> str:
        n = next(counter)
        return (base + timedelta(seconds=n)).strftime("%Y-%m-%d %H:%M:%SZ")

    return fake_now


class ZoneWaitSandbox(FsmTest):
    """`FsmTest` (T001, git/preflight заглушены), `self.TASK` уже заведена
    и приведена к нейтральному `in_dev` без зон — тем же приёмом, что
    `ZoneSandbox.reset_task` соседней задачи 01M1P9QAG65GVF69YJEV0V18D9."""

    CALLER_SESSION = "session-caller"

    def setUp(self):
        super().setUp()
        self.reset_task()

    def reset_task(self) -> None:
        self.set_state("in_dev", budget_usd=config.DEFAULT_BUDGET_USD,
                       spent_usd=0.0, escalated_from=None, zones=None)
        self.write_spec("ready")
        conn = store.db()
        conn.execute("DELETE FROM leases")
        conn.execute("DELETE FROM tasks WHERE id != ?", (self.TASK,))
        conn.commit()

    def set_own_zones(self, zones: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, self.TASK))
        conn.commit()

    def seed_task(self, task_id: str, title: str, state: str, zones: str,
                 updated_at: str | None = None) -> None:
        """Заводит ДРУГУЮ задачу напрямую в БД, без git/веток/worktree —
        `state`/`zones` управляют занятостью зоны для сценариев теста."""
        store.insert_task(store.db(), task_id, title, state,
                          f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, task_id))
        if updated_at is not None:
            conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                         (updated_at, task_id))
        conn.commit()

    def mark_already_started(self, task_id: str) -> None:
        """Журналирует маркеры реального держателя зоны (`zone_lock.
        _occupies`): `"state -> in_dev"` + `"agent run started"` актором
        `developer` — тот же приём, что `tests/test_zone_lock.py::
        ZoneLockTest._mark_already_started`."""
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> in_dev", "")
        store.journal(conn, task_id, "developer", "agent run started", "")

    def set_task_state(self, task_id: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()

    def task_state(self, task_id: str | None = None) -> str:
        return store.get_task(store.db(), task_id or self.TASK)["state"]

    def journal_len(self, task_id: str | None = None) -> int:
        return len(store.task_steps(store.db(), task_id or self.TASK))

    def journal_tail(self, task_id: str | None = None, since: int = 0) -> str:
        rows = store.task_steps(store.db(), task_id or self.TASK)[since:]
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows).lower()

    def lease_heartbeat(self, task_id: str | None = None) -> str | None:
        row = store.lease_row(store.db(), task_id or self.TASK)
        return row["heartbeat_ts"] if row is not None else None

    def run_with_fake_agent(self, call) -> tuple[str, mock.Mock]:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = capture(call)
        return out, popen
