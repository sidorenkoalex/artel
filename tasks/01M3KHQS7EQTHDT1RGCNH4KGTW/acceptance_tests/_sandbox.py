"""Общая песочница планки 01M3KHQS7EQTHDT1RGCNH4KGTW («ожидание занятой
зоны по умолчанию для всех вызовов `auto`») — тонкая надстройка сценария
над `tests/test_invariants.py::FsmTest`, не собственная копия песочницы:
`disk_backed_*`/`advance_from_in_dev` здесь не переопределяются
(skills/test-authoring.md).

Сценарий один на три критерия (AC-2, AC-3, AC-4): задача `self.TASK` в
`in_dev` со своей зоной, ДРУГАЯ задача держит ту же зону (`in_dev` плюс
маркеры реального старта шага — тот же признак, что разбирает
`zone_lock._occupies`), `runner.spawn_agent` подменён `FakeProc`. Отказ
занятости зоны при этом журналируется НАСТОЯЩИМ `runner._cmd_run`
(`zone_lock.claim` -> `zone_lock.REFUSAL_ACTION`), а не имитацией: предмет
критериев — как цикл `auto` реагирует на реальный отказ.

Приёмы взяты из планки задачи, заведшей сам режим ожидания
(01M1VBEAWZW4EBZHKMGNBBK648, `acceptance_tests/_sandbox.py`) — там они
прошли валидацию стабом и круг ревью:

- `only_on_poll_interval` — фильтр подмены `time.sleep`. Патч
  `auto.time.sleep` глобален (`auto.time` — сам модуль `time`), поэтому
  без фильтра обработчик теста ловит и посторонние паузы (бэкофф ретрая
  спавна агента внутри `runner._cmd_run`) и считает опросы ожидания
  неверно.
- `run_with_fake_agent` — подмена `runner.spawn_agent` на `FakeProc`:
  настоящий CLI в планке не зовётся.

Ни `config.AUTO_WAIT_ZONE_DEFAULT`, ни `config.ZONE_WAIT_POLL_SEC` этот
модуль не патчит: AC-2 прямо требует сценария БЕЗ подмены настройки, а
интервал опроса не влияет на длительность прогона, раз сам `time.sleep`
подменён. Потолок `config.ZONE_WAIT_MAX_SEC` патчит только файл AC-4 —
там он и есть предмет критерия.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, runner, store  # noqa: E402
from tests.sandbox import capture  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402

#: Зона, которую задача планки делит с держателем, и id держателя.
CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


def only_on_poll_interval(handler):
    """Оборачивает обработчик `time.sleep`: реагирует ТОЛЬКО на паузы
    РОВНО в `config.ZONE_WAIT_POLL_SEC` (опрос цикла ожидания зоны).
    Остальные паузы процесса — тихий `no-op` без вызова `handler`: патч
    `auto.time.sleep` глобален и ловит в том числе бэкофф ретрая спавна
    агента, никак с ожиданием зоны не связанный."""
    def wrapped(seconds):
        if seconds != config.ZONE_WAIT_POLL_SEC:
            return
        return handler(seconds)
    return wrapped


class ZoneWaitSandbox(FsmTest):
    """`FsmTest` (БД и артефакты во временном каталоге, git не
    исполняется), задача приведена к `in_dev`, зона занята чужой
    задачей."""

    CALLER_SESSION = "session-caller"

    def setUp(self):
        super().setUp()
        self.set_state("in_dev")
        self.write_spec("ready")
        conn = store.db()
        conn.execute("DELETE FROM leases")
        conn.commit()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_occupier(OCCUPIER, CONFLICT_PATH)

    # ----------------------------------------------------------- фикстура

    def set_own_zones(self, zones: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, self.TASK))
        conn.commit()

    def seed_occupier(self, task_id: str, zones: str) -> None:
        """Заводит ДРУГУЮ задачу прямо в БД и помечает её реальным
        держателем зоны: `state -> in_dev` плюс `agent run started` —
        те же маркеры, что разбирает `zone_lock._occupies` (тот же приём,
        что `tests/test_auto_cycle.py::WaitForZoneTest._seed_occupier`)."""
        conn = store.db()
        store.insert_task(conn, task_id, f"Держатель зоны {task_id}", "in_dev",
                          f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, task_id))
        conn.commit()
        store.journal(conn, task_id, "system", "state -> in_dev", "")
        store.journal(conn, task_id, "developer", "agent run started", "")

    def release_zone(self, task_id: str = OCCUPIER) -> None:
        """Держатель уходит из блокирующей фазы — зона свободна."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state='done' WHERE id=?", (task_id,))
        conn.commit()

    # ----------------------------------------------------------- наблюдение

    def task_state(self, task_id: str | None = None) -> str:
        return store.get_task(store.db(), task_id or self.TASK)["state"]

    def journal_rows(self, task_id: str | None = None) -> list:
        return store.task_steps(store.db(), task_id or self.TASK)

    def wait_enter_actions(self) -> list:
        """Действия журнала задачи, начинающиеся с «ждёт зоны » —
        буквальный префикс входа в ожидание из формулировки AC-2."""
        return [r["action"] for r in self.journal_rows()
                if r["action"].startswith("ждёт зоны ")]

    def zone_wait_stop_rows(self) -> list:
        """Записи остановки цикла причиной `config.AUTO_STOP_ZONE_WAIT`:
        `auto.auto_stop` пишет причину в `detail` формой «<состояние>:
        <причина>» — причина берётся из конфига, не литералом."""
        reason = config.AUTO_STOP_ZONE_WAIT[0]
        return [dict(r) for r in self.journal_rows()
                if r["detail"].endswith(f": {reason}")]

    def run_with_fake_agent(self, call) -> tuple:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = capture(call)
        return out, popen
