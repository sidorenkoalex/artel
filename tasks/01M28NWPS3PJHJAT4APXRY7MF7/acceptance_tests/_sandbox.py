"""Общая песочница приёмочных тестов 01M28NWPS3PJHJAT4APXRY7MF7 («гонка
гейта зон при одновременном старте»).

Поверх `tests.test_invariants.FsmTest` (SPEC skills/test-authoring: «не
переписывать заново, импортировать») — та же песочница, которой уже
пользовались приёмочные тесты родительской задачи зон
(`tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests/_sandbox.py::ZoneSandbox`,
теперь смержена в main — колонка `zones` и `config.COMMON_ZONES` уже в
схеме, `_ensure_zones_column`/патч `COMMON_ZONES` того файла здесь не
нужны). `FsmTest.setUp` уже заводит T001 в `spec_writing`, стабит
`doctor.preflight_checks`/`stack.check_stack`/keychain, ведёт `ROOT`
настоящим (skills/roles.yaml читаются по-настоящему).

## Допущения интерфейса (SPEC не называет ни один из них по имени —
задача не начата на момент написания этих тестов)

- Атомарный захват — НЕ отдельная публичная функция с зафиксированным
  именем: SPEC (требование 1) описывает его как правку `runner._cmd_run`
  внутри одной транзакции, а не новый публичный API. Тесты AC-1/AC-6 бьют
  по наблюдаемому поведению `runner.cmd_run` (два потока, общая БД), не по
  внутренней точке входа — тот же приём, что уже применён к лимитеру
  параллельных задач (`tasks/T060/acceptance_tests/
  test_max_parallel_tasks.py`) и к мьютексу merge-окна
  (`tasks/T053/acceptance_tests/_mutex_sandbox.py`).
- `zone_lock.CLAIM_ACTION` — единственное имя, которое SPEC называет
  буквально (требование 1: «отдельная журнальная запись `zone claimed`
  актора `developer` (`zone_lock.CLAIM_ACTION`)») — тесты AC-2/AC-3/AC-5
  журналируют через эту константу напрямую, не через литеральную строку.
- Текст снятия захвата («`zone claim released`», требование 2, AC-3/AC-4)
  SPEC называет только буквальным текстом действия, без имени константы
  — тесты сверяют журнал по этой литеральной строке (`row["action"] ==
  "zone claim released"`), не изобретая имя атрибута `zone_lock.py`.
- Прогон ДО реализации падает `AttributeError: module 'orchestrator.
  zone_lock' has no attribute 'CLAIM_ACTION'` в тестах, журналирующих
  захват вручную (AC-2/AC-4/AC-5), и просто наблюдаемым несоответствием
  поведения (оба потока стартуют одновременно вместо одного) в AC-1/AC-6
  — оба исхода ожидаемы (skills/test-authoring: «падать на отсутствующей
  пока реализации — нормально»), не брак теста.
"""
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import capture_new_task_id  # noqa: E402
from tests.test_invariants import SPEC_MD, FsmTest  # noqa: E402


class ZoneClaimSandbox(FsmTest):
    """T001 (`FsmTest`) заведён в `in_dev`, с собственной зоной `ZONE`,
    рабочий каталог роли developer несёт обязательный маркер `PLAN.md`
    (`seed_worktree_plan`) — успешный (rc=0) прогон агента принимается с
    первой попытки, без ретрая «нет артефакта»."""

    ZONE = "orchestrator/fsm_advance.py"

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.seed_worktree_plan()
        self.set_state("in_dev", zones=self.ZONE)

    def seed_fake_occupant(self, task_id: str, state: str, zones: str) -> None:
        """Заводит ДРУГУЮ задачу напрямую в БД, без git/веток/worktree
        (тот же приём, что `_sandbox.ZoneSandbox.seed_task` родительской
        задачи 01M1P9QAG65GVF69YJEV0V18D9) — годится для сценариев,
        сверяющих ТОЛЬКО занятость (`zone_lock`/`catalog`), не спавнящих
        для неё настоящий агентный шаг."""
        store.insert_task(store.db(), task_id, f"Другая {task_id}", state,
                          f"task/{task_id.lower()}-fake",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (zones, task_id))
        conn.commit()

    def spawn_second_real_task(self, title: str = "Гонка B") -> str:
        """Второй РЕАЛЬНЫЙ (через `catalog.cmd_new`) кандидат developer —
        для AC-1/AC-6, где обе стороны гонки должны реально пройти
        `runner.cmd_run` целиком, не быть данными для сканирования
        `blocking_conflict` со стороны первой задачи. Повторяет для него
        ровно ту же подготовку, что `setUp` уже сделал для `self.TASK`
        (SPEC.md `ready`, маркер `PLAN.md`, `in_dev` со своей зоной)."""
        _, task_id = capture_new_task_id(catalog.cmd_new, title)
        tdir = config.TASKS / task_id
        # `config.TASKS` здесь = РЕАЛЬНЫЙ `ROOT/tasks` (см. докстринг
        # `FsmTest`, «ROOT намеренно НЕ подменяется целиком») — каталог
        # физически лежит в рабочем дереве пульта, как и `self.tdir`
        # самого `FsmTest`; без явной уборки он остался бы в репозитории
        # после прогона (тот же риск, что `FsmTest.setUp` уже закрывает
        # для `self.tdir` своим `addCleanup`).
        self.addCleanup(shutil.rmtree, tdir, ignore_errors=True)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=task_id, status="ready"), encoding="utf-8")
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev', zones=? WHERE id=?",
                    (self.ZONE, task_id))
        conn.commit()
        wt = config.WORKTREES / task_id / "tasks" / task_id
        wt.mkdir(parents=True, exist_ok=True)
        (wt / "PLAN.md").write_text("маркер\n", encoding="utf-8")
        return task_id

    def steps(self, task_id: str | None = None):
        return store.task_steps(store.db(), task_id or self.TASK)

    def journal(self, task_id: str, actor: str, action: str,
               detail: str = "") -> None:
        store.journal(store.db(), task_id, actor, action, detail)

    def task_state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]
