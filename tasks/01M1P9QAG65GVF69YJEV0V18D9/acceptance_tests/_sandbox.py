"""Общая песочница приёмочных тестов 01M1P9QAG65GVF69YJEV0V18D9 («Механика
зон, часть 2: занятость зоны на старте кода»).

## Зависимость от части 1 (01M1NKVPD2A79PQ6K0JVV1B2Q1)

Эта задача читает данные, которые вводит часть 1 (поле `zones` в БД,
`config.COMMON_ZONES`) — SPEC, требование 1; материалы. На момент написания
этих тестов часть 1 одобрена (`REVIEW.md` итерация 2, approved,
8a02199f её ветки), но НЕ смержена в main — старт кода части 2 наступит
после её мержа (SPEC, «Контекст», буквально). Прямо сейчас в этом дереве
НЕТ ни колонки `zones` у таблицы `tasks`, ни `config.COMMON_ZONES`.

Песочница не ждёт мержа части 1, чтобы быть исполнимой уже сегодня (и
остаться исполнимой без изменений после него):
- `_ensure_zones_column` добавляет колонку `zones` таблице `tasks` через
  `ALTER TABLE`, если её ещё нет (идемпотентно) — после мержа части 1
  колонка уже будет в схеме, `ALTER TABLE` увидит существующую и не
  тронет её (SQLite бросает `OperationalError` на повторное добавление —
  перехватывается).
- `COMMON_ZONES` (`config.COMMON_ZONES`) патчится `mock.patch.object(...,
  create=True)` — ЗНАЧЕНИЕМ, которое часть 1 уже зафиксировала и
  провалидировала (`orchestrator/config.py` её ветки, коммит 8920fae2):
  `("orchestrator/config.py", "docs/codebase-map.md", "tests/",
  "roles.yaml")`. `create=True` работает одинаково — патчит атрибут на
  время теста — существует он уже в модуле или нет, поэтому после мержа
  части 1 та же строчка продолжит работать без правки.
- Формат значения `zones` — список путей/масок через запятую в ОДНОЙ
  строке (не список YAML) — часть 1 фиксирует это буквально
  (`tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/protected-paths.patch`,
  `skills/spec-authoring.md`: «...список путей/масок ... через запятую»;
  `orchestrator/yamlmini.py::frontmatter` разбирает frontmatter голым
  скаляром, потокового списка `[a, b]` не понимает). Тесты этого каталога
  используют этот формат для `zones` и НЕ проверяют его сами — это
  планка части 1, не этой задачи.

## Допущения интерфейса, которые вводит этот файл (часть 2 не начата —
SPEC не называет ни один из них по имени)

- Сама проверка занятости зоны перед первым шагом `in_dev` — НЕ отдельная
  публичная функция с зафиксированным именем: тесты AC-1..AC-3, AC-6, AC-7
  бьют по наблюдаемому поведению команд `run`/`auto` (`runner.cmd_run`,
  `auto.cmd_auto`), не по внутренней точке входа — тем же приёмом, что уже
  применён к лимитеру параллельных задач (`tasks/T060/acceptance_tests/
  test_max_parallel_tasks.py`, «Сам лимитер — не отдельная публичная
  функция...») и к мьютексу merge-окна (`tasks/T053/acceptance_tests/
  _mutex_sandbox.py`).
- `doctor.check_zone_waits(conn) -> list[doctor.Check]` — новая точечная
  проверка doctor по образцу уже существующих `doctor.check_leases`/
  `doctor.check_orphans`/`doctor.check_backup_age` (SPEC требование 4);
  тесты AC-5 зовут её напрямую, не через `doctor.all_checks()` — та тянет
  живой смоук CLI и сетевые проверки, не относящиеся к предмету этой
  задачи (тот же приём, что `tasks/T044/acceptance_tests/
  test_lease_readonly_and_doctor.py` уже применил к `doctor.check_leases`).
- Явные операторские команды AC-7/AC-9 (`orchestrator/artel.py` несёт их
  по SPEC, «Оценка объёма и деление», но ни SPEC, ни ТЗ не называют ни
  CLI-глагол, ни модуль/функцию — тем же приёмом, что и «Допущения
  интерфейса» `tasks/T062/acceptance_tests/
  test_ac1_ac2_ac3_ac5_release_command.py` для команды `release`, только
  там SPEC зафиксировал хотя бы внешний глагол, а здесь — ни того, ни
  другого, оба выбора делает этот файл):
    - Новый модуль `orchestrator/zone_lock.py`.
    - `zone_lock.cmd_zone_release(task_id: str) -> None` — снимает
      ожидание зоны ИМЕННО для `task_id` (AC-7): следующий `run`/`auto`
      этой задачи не отказывает по ТЕМ конфликтам, что были причиной
      блокировки на момент вызова, независимо от того, ушла ли занявшая
      зону задача из фазы `in_dev`…`merge_gate`.
    - `zone_lock.queue_order(conn, task_ids: list[str]) -> list[str]` —
      те же id, что и на входе, отсортированные по возрастанию времени
      approve их SPEC (AC-8). Тесты этого файла ФИКСИРУЮТ момент approve
      как `tasks.updated_at` задачи в момент, когда она встала в очередь
      (для задач, заведённых этой песочницей напрямую в `in_dev` без
      прохода через `spec_gate` — `updated_at` в этот момент ничем другим
      не тронут, тот же приём, что уже применяет `heartbeat_ts` в T060
      для симуляции «занятости» без полного FSM-цикла); файл не
      предписывает разработчику брать значение именно оттуда — только
      то, что для задачи, единственный раз вошедшей в свою текущую фазу и
      с тех пор не двигавшейся, `updated_at` этой фазы совпадает с
      моментом, который АС-8 называет «approve её SPEC» (обе задачи,
      блокированные ОДНОЙ зоной, обычно останавливаются именно на входе в
      `in_dev`, следующем сразу за approve, — SPEC требование 1). Реальный
      источник времени (approve-журнал, отдельная колонка) разработчик
      выбирает сам — тест лочит НАБЛЮДАЕМЫЙ порядок, не место его
      хранения.
    - `zone_lock.cmd_zone_reorder(task_ids_in_order: list[str]) -> None`
      — явная операторская перестановка (AC-9): после вызова
      `queue_order` для ТОГО ЖЕ множества id возвращает переданный порядок
      вместо порядка по времени approve.
    - Прогон ДО реализации падает `ModuleNotFoundError: No module named
      'orchestrator.zone_lock'` — ожидаемо (skills/test-authoring:
      «падать на отсутствующей пока реализации — нормально»), не брак
      теста.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, runner, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

# Значение части 1 (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-4), провалидированное
# её собственными приёмочными тестами
# (test_ac4_common_zones_named_list.py) — не изобретение этого файла.
COMMON_ZONES = ("orchestrator/config.py", "docs/codebase-map.md", "tests/",
               "roles.yaml")


def _ensure_zones_column(conn) -> None:
    """Добавляет колонку `zones` таблице `tasks`, если часть 1 ещё не
    смержена и колонка отсутствует (см. докстринг модуля)."""
    if "zones" in store.table_columns(conn, "tasks"):
        return
    conn.execute("ALTER TABLE tasks ADD COLUMN zones TEXT")
    conn.commit()


def _invoke(call) -> str:
    """Стдаут вызова + текст SystemExit (если он был) — отказ зоны мог
    уйти любым из двух путей (`sys.exit`, как `budget_block`/
    `parallel_limit.refusal`, или печать+`return`), тот же приём, что
    `tasks/T060/acceptance_tests/test_max_parallel_tasks.py::_invoke`."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        return buf.getvalue() + str(exc)
    return buf.getvalue()


class ZoneSandbox(FsmTest):
    """`FsmTest` (T001, git/preflight заглушены) + колонка `zones` +
    `config.COMMON_ZONES` патчены на время каждого теста."""

    CALLER_SESSION = "session-caller"

    def setUp(self):
        super().setUp()
        _ensure_zones_column(store.db())
        patcher = mock.patch.object(config, "COMMON_ZONES", COMMON_ZONES,
                                    create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.reset_task()

    def reset_task(self) -> None:
        """Возвращает T001 к нейтральному `in_dev` без зон и чистит чужие
        задачи/lease перед очередным сценарием.

        `write_spec("ready")` (унаследован от `FsmTest`): `_cmd_run`
        собирает бриф разработчика из SPEC.md ветки задачи (`orchestrator/
        brief.py::_developer_spec_text`, `gitcmd.show` здесь патчен на
        чтение `self.tdir` с диска) ДО спавна агента — без него позитивные
        сценарии (запуск проходит — AC-3, AC-6, AC-7) валятся на «бриф не
        собран», не дойдя до проверки занятости зоны вовсе. Не имеет
        отношения к предмету этой задачи — тот же брифинг нужен и
        `tests/test_auto_cycle.py`/T060 для старта `in_dev`."""
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
        """Заводит ДРУГУЮ задачу напрямую в БД (без git/веток/worktree —
        тот же приём, что `seed_busy_task` в T060): `state` — её фаза
        (`in_dev`…`merge_gate` для «занявшей зону», что угодно другое —
        для граничных тестов диапазона), `zones` — её зоны."""
        store.insert_task(store.db(), task_id, title, state,
                          f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, task_id))
        if updated_at is not None:
            conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                         (updated_at, task_id))
        conn.commit()

    def set_task_state(self, task_id: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()

    def task_state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def journal_len(self, task_id: str | None = None) -> int:
        return len(store.task_steps(store.db(), task_id or self.TASK))

    def journal_tail(self, task_id: str, since: int) -> str:
        rows = store.task_steps(store.db(), task_id)[since:]
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows).lower()

    def run_with_fake_agent(self, call) -> tuple[str, mock.Mock]:
        with mock.patch.object(runner, "spawn_agent") as popen:
            from tests.test_invariants import FakeProc
            popen.return_value = FakeProc(["готово\n"])
            out = _invoke(call)
        return out, popen
