"""Общая песочница приёмочных тестов T053 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py) для критериев,
не требующих настоящего git (AC-1, AC-2, AC-5, AC-6): механика мьютекса
merge-окна тестируется через наблюдаемое поведение публичных входов
`fsm.cmd_approve`/`fsm.cmd_reject`/`cleanup.cmd_kill` поверх готовой
песочницы `tests.test_invariants.FsmTest` (git и агент заглушены) — тот же
приём, что `tasks/T044/acceptance_tests/test_lease_enforcement.py` уже
применила к самому lease. Настоящий git нужен только сверке свежести
внутри окна (AC-3) и байт-в-байт неизменности merge (AC-4) —
`tasks/T053/acceptance_tests/_sandbox.py`.

## Допущения интерфейса, которые вводит этот файл

SPEC (требование 1) прямо отсылает к lease (T044) как образцу мьютекса
merge-окна, но не называет ни имя таблицы/модуля, ни то, как задача-
держатель попадает в отказ, — решения разработчика. Тест вводит
минимальный шов, нужный, чтобы СИМУЛИРОВАТЬ «другая сессия удерживает
окно ПРЯМО СЕЙЧАС» (тот же приём, что `seed_lease` в T044, требование 9
которой прямо признаёт это решением теста, а не фактом уже существующего
кода):

- Таблица `merge_locks`, пять колонок по образцу `leases`
  (`orchestrator/store.py`): `task_id, session_id, pid, hostname,
  heartbeat_ts`. Мьютекс один на весь пульт (требование 2) — не более
  одной строки одновременно; тест поддерживает её напрямую SQL, не
  через ещё не существующую функцию взятия (наблюдаемое поведение —
  только через `fsm.cmd_approve`/`cmd_reject`/`cmd_kill`, не через
  внутреннюю функцию мьютекса, которой ещё нет).
- Порог протухания heartbeat — тот же, что и у lease,
  `config.LEASE_STALE_AFTER_SEC` (требование 4, «по аналогии с lease»):
  SPEC T053 не вводит отдельной константы для мьютекса merge, а T044
  уже ввела ровно такой порог для того же механизма «протухший
  heartbeat».
- Держатель мьютекса ссылается на задачу `HOLDER_TASK` — заведённую
  здесь же настоящей строкой `tasks` (не только строкой `merge_locks`):
  отказ обязан «указать... задачу, которую он держит» (требование 2), а
  раз реализация вправе обогатить сообщение чтением строки задачи
  держателя, эта строка обязана существовать, иначе тест бил бы по
  случайному решению реализации, а не по критерию.

Прогон ДО реализации падает на `sqlite3.OperationalError: no such table:
merge_locks` — ожидаемо (скил test-authoring: «падать на отсутствующей
пока реализации — нормально»), не брак теста.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

HOLDER_SESSION = "session-holder"
HOLDER_PID = 424242
HOLDER_HOST = "holder-host"
HOLDER_TASK = "T999"
CALLER_SESSION = "session-caller"


def invoke(call) -> str:
    """Стдаут вызова + текст `SystemExit` (если он был): отказ мог уйти
    любым из двух путей (`sys.exit` — стиль отказа lease/CI выше по
    файлу, либо `print`+`return` — стиль отказа «главная копия не на
    main» ниже), для теста это один и тот же наблюдаемый текст. Тот же
    приём, что `tasks/T044/acceptance_tests/test_lease_enforcement.py::_invoke`.
    """
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue()


class MergeLockFsmTest(FsmTest):
    """T001 в состоянии `merge_gate`, готовый к approve (артефакты гейтов
    ready — тот же приём, что `tasks/T052/acceptance_tests/
    test_ac5_red_ci_keeps_task_in_gate.py`), плюс держатель `HOLDER_TASK`
    и прямые операции над `merge_locks` (см. «Допущения интерфейса»
    выше)."""

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")
        store.insert_task(store.db(), HOLDER_TASK, "Держит окно merge",
                          "merge_gate", "task/t999-holder",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def seed_merge_lock(self, session_id: str, pid: int, hostname: str,
                        heartbeat_ts: str, task_id: str) -> None:
        conn = store.db()
        conn.execute("DELETE FROM merge_locks")
        conn.execute(
            "INSERT INTO merge_locks (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (task_id, session_id, pid, hostname, heartbeat_ts))
        conn.commit()

    def clear_merge_lock(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM merge_locks")
        conn.commit()

    def merge_lock_rows(self) -> list:
        return [dict(r) for r in
               store.db().execute("SELECT * FROM merge_locks")]

    def git_subcommands_since(self, mark: int) -> list:
        """Подкоманды `git`, вызванные ПОСЛЕ отметки `mark` (индекс в
        `self.git_spy.calls` на момент отметки) — по образцу
        `SpyRun.git_subcommands`, но только хвост, накопленный самим
        проверяемым вызовом (`setUp` уже насчитал свои)."""
        return [c[1] for c in self.git_spy.calls[mark:]
               if len(c) > 1 and c[0] == "git"]
