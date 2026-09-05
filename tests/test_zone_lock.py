"""Юнит-тесты orchestrator/zone_lock.py (SPEC 01M1P9QAG65GVF69YJEV0V18D9).

Приёмочные тесты (tasks/01M1P9QAG65GVF69YJEV0V18D9/acceptance_tests) кроют
AC-1..AC-9 сквозным путём через `run`/`auto`/`status`/`doctor`; здесь — сам
модуль `zone_lock.py` в изоляции: чистые функции `blocking_conflict`,
`refusal`, `queue_order`, `queue_position` и CLI-команды `cmd_zone_release`/
`cmd_zone_reorder`, без прогона команд CLI верхнего уровня.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ZoneLockTest(TmpRootTest):
    TASK = "T001"
    OTHER = "T901"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def set_own_zones(self, zones: str | None) -> None:
        store.update_task(store.db(), self.TASK, zones=zones)

    def set_own_state(self, state: str) -> None:
        store.update_task(store.db(), self.TASK, state=state)

    def seed_other(self, state: str, zones: str | None,
                   target: str = config.DEFAULT_TARGET,
                   task_id: str | None = None) -> str:
        task_id = task_id or self.OTHER
        store.insert_task(store.db(), task_id, f"Другая {task_id}", state,
                          f"task/{task_id.lower()}-fake", target,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), task_id, zones=zones)
        return task_id

    def get_task(self, task_id: str | None = None):
        return store.get_task(store.db(), task_id or self.TASK)

    def mark_approved(self, task_id: str) -> None:
        """Помечает `task_id` approved «сейчас» (R1-F2): пишет в общий
        журнал шагов маркер `"state -> spec_gate"`, за ним — `"state ->
        tests_writing"` (штатный переход, следующий за approve). `steps.
        id` — общий монотонный счётчик по ВСЕМ задачам одной БД, поэтому
        задача, для которой этот метод вызван раньше, получает МЕНЬШИЙ
        id маркера — раньше в очереди `queue_order`."""
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> spec_gate", "")
        store.journal(conn, task_id, "system", "state -> tests_writing", "")

    # ----------------------------------------------------------- no conflict

    def test_no_zones_means_no_conflict(self):
        """Ловит мутацию: `blocking_conflict` считает отсутствие
        собственных зон (`own`) конфликтом (пустое множество трактуется
        как «пересекается со всем») вместо явного `None`."""
        self.seed_other("in_dev", "a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_own_state_other_than_in_dev_never_conflicts(self):
        """Ловит мутацию: проверка занятости срабатывает для задачи ВНЕ
        `in_dev` (требование 1 — занятость блокирует только первый шаг
        `in_dev`; задача в `review` не должна снова проверяться)."""
        self.set_own_zones("a/b")
        self.set_own_state("review")
        self.seed_other("in_dev", "a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_disjoint_zones_do_not_conflict(self):
        """Ловит мутацию: `blocking_conflict` считает конфликтом ЛЮБУЮ
        пару задач в блокирующих состояниях, не сверяя зоны вовсе."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "c/d")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_intersection_only_on_common_zone_does_not_conflict(self):
        """Ловит мутацию: `_own_paths` не вычитает `config.COMMON_ZONES`
        (требование 2) — пересечение ТОЛЬКО по общей зоне ложно блокирует
        запуск."""
        common = ("orchestrator/config.py",)
        with mock.patch.object(config, "COMMON_ZONES", common,
                              create=True):
            self.set_own_zones("orchestrator/config.py,a/b")
            self.seed_other("in_dev", "orchestrator/config.py,c/d")

            self.assertIsNone(zone_lock.blocking_conflict(
                store.db(), self.TASK, self.get_task()))

    def test_other_target_never_conflicts(self):
        """Ловит мутацию: `blocking_conflict` не сверяет `target` занявшей
        задачи с `config.DEFAULT_TARGET` (SPEC, «Не входит»: зоны — только
        механика dogfood target'а) — задача внешнего target'а с той же
        зоной ложно блокирует запуск."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b", target="other-target")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_own_task_excluded_from_scan(self):
        """Ловит мутацию: цикл по `store.all_tasks` не исключает саму
        проверяемую задачу — она бы «конфликтовала сама с собой»."""
        self.set_own_zones("a/b")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    # ----------------------------------------------- nesting (R1-F1)

    def test_directory_zone_conflicts_with_file_inside_it(self):
        """Ловит мутацию R1-F1: сравнение зон точным совпадением строк
        (без учёта вложенности) пропускает реальный конфликт между
        зоной-каталогом (`src/`) одной задачи и зоной-файлом (`src/a.py`)
        внутри него у другой — `{"src/"} & {"src/a.py"} == set()` при
        точном сравнении, хотя обе задачи правят один и тот же код."""
        common = ()
        with mock.patch.object(config, "COMMON_ZONES", common, create=True):
            self.set_own_zones("src/")
            occupier = self.seed_other("in_dev", "src/a.py")
            self._mark_already_started(occupier)

            conflict = zone_lock.blocking_conflict(
                store.db(), self.TASK, self.get_task())

            self.assertIsNotNone(conflict)
            self.assertEqual(conflict[0], "src/a.py")

    def test_file_inside_common_directory_zone_is_treated_as_common(self):
        """Ловит мутацию R1-F1: задача указывает зоной конкретный файл
        внутри общей директории (`tests/test_zone_lock.py"` внутри общей
        `"tests/"`), но `_own_paths` вычитает `COMMON_ZONES` только точным
        совпадением строки — файл остаётся «своей» зоной и ложно
        конфликтует с любой другой задачей, тоже добавляющей файл в
        `tests/`, хотя `tests/` объявлена полностью общей (AC-4 части 1)."""
        common = ("tests/",)
        with mock.patch.object(config, "COMMON_ZONES", common, create=True):
            self.set_own_zones("tests/test_zone_lock.py")
            self.seed_other("in_dev", "tests/test_other_module.py")

            self.assertIsNone(zone_lock.blocking_conflict(
                store.db(), self.TASK, self.get_task()))

    def test_own_directory_containing_a_common_file_is_not_itself_common(self):
        """Ловит мутацию R1-F1: `_is_common_zone` симметрично сравнивает
        свою зону с общей (`_paths_overlap`, не направленное покрытие) —
        своя зона-каталог (`src/`), лишь СОДЕРЖАЩАЯ где-то внутри общий
        файл (`src/common.py`), ложно считалась бы самой общей зоной и
        вычиталась бы из сравнения — реальный конфликт с другой задачей
        по остальным файлам `src/` пропал бы."""
        common = ("src/common.py",)
        with mock.patch.object(config, "COMMON_ZONES", common, create=True):
            self.set_own_zones("src/")
            occupier = self.seed_other("in_dev", "src/")
            self._mark_already_started(occupier)

            conflict = zone_lock.blocking_conflict(
                store.db(), self.TASK, self.get_task())

            self.assertIsNotNone(conflict)
            self.assertEqual(conflict[0], "src/")

    # -------------------------------------------------- blocking states range

    def _clear_other_tasks(self) -> None:
        conn = store.db()
        conn.execute("DELETE FROM tasks WHERE id != ?", (self.TASK,))
        conn.commit()

    def test_occupier_in_each_blocking_state_conflicts(self):
        """Ловит мутацию: `BLOCKING_STATES` не покрывает весь диапазон
        `in_dev`…`merge_gate` — задача занявшая зону, оказавшись, например,
        в `verifying`/`acceptance`, перестала бы блокировать первый шаг,
        хотя требование 1 говорит о ВСЁМ диапазоне."""
        self.set_own_zones("a/b")
        for state in ("in_dev", "review", "verifying", "acceptance",
                      "merge_gate"):
            with self.subTest(state=state):
                self._clear_other_tasks()
                occupier = f"T9{state[:3]}"
                self.seed_other(state, "a/b", task_id=occupier)
                self._mark_already_started(occupier)

                conflict = zone_lock.blocking_conflict(
                    store.db(), self.TASK, self.get_task())

                self.assertIsNotNone(conflict)
                self.assertEqual(conflict, ("a/b", occupier, state))

    def test_occupier_outside_range_does_not_conflict(self):
        """Ловит мутацию: диапазон `BLOCKING_STATES` расширен за пределы
        `in_dev`…`merge_gate` (например включает `tests_writing`/`done`/
        `killed`) — задача до кода или уже закрытая ложно блокирует
        первый шаг."""
        self.set_own_zones("a/b")
        for state in ("tests_writing", "spec_writing", "done", "killed"):
            with self.subTest(state=state):
                self._clear_other_tasks()
                occupier = f"T9{state[:3]}"
                self.seed_other(state, "a/b", task_id=occupier)

                self.assertIsNone(zone_lock.blocking_conflict(
                    store.db(), self.TASK, self.get_task()))

    # ------------------------------------------------------------ first-step

    def test_first_step_boundary_uses_current_in_dev_visit(self):
        """Ловит мутацию (SPEC 01M1REVJ8AJDKAMK5VTKES5J6D, требование 2,
        AC-3): маркер `agent run started` из ПРЕДЫДУЩЕГО визита `in_dev`
        того же непрерывного пребывания перестаёт учитываться, если
        граница вычисляется от последней записи `"state -> in_dev"`
        (старое поведение частей 1-3, факт «б» SPEC «Контекст») — задача
        после возврата `review -> in_dev` снова видит соседа конфликтом,
        хотя её код уже стартовал раньше. Верная граница —
        `_stay_since_id` (последняя `"state -> tests_writing"`), которую
        промежуточный визит `in_dev` не сдвигает: результат — `None`, не
        конфликт."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "system",
                     "state -> tests_writing", "")
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")
        store.journal(store.db(), self.TASK, "developer",
                     "agent run started", "визит #1")
        store.set_state(store.db(), self.TASK, "review", "system",
                        expected_state="in_dev")
        store.set_state(store.db(), self.TASK, "in_dev", "system",
                        expected_state="review")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task())

        self.assertIsNone(conflict)

    def test_agent_started_after_in_dev_boundary_lifts_conflict(self):
        """Ловит мутацию: запись `agent run started` ПОСЛЕ границы визита
        `in_dev` не освобождает от проверки — первый шаг считался бы
        «ещё не состоявшимся» вечно, блокируя КАЖДЫЙ последующий
        `run`/`auto`, хотя SPEC требует проверку только перед ПЕРВЫМ."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")
        store.journal(store.db(), self.TASK, "developer",
                     "agent run started", "визит #2")

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_operator_release_after_boundary_lifts_conflict(self):
        """Ловит мутацию: `cmd_zone_release` не влияет на результат
        `blocking_conflict` — операторское снятие ожидания (требование 6)
        не давало бы никакого recourse."""
        self.set_own_zones("a/b")
        self.seed_other("in_dev", "a/b")
        store.journal(store.db(), self.TASK, "system", "state -> in_dev", "")

        zone_lock.cmd_zone_release(self.TASK)

        self.assertIsNone(zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task()))

    def test_release_before_boundary_does_not_lift_a_later_visit(self):
        """Ловит мутацию: снятие ожидания в ПРЕДЫДУЩЕМ пребывании
        переносится на новое (следующая запись `"state -> tests_writing"`,
        `_stay_since_id`) — Оператор снимает риск конкретно для того
        конфликта, что видел, не навсегда."""
        self.set_own_zones("a/b")
        occupier = self.seed_other("in_dev", "a/b")
        self._mark_already_started(occupier)
        zone_lock.cmd_zone_release(self.TASK)
        store.journal(store.db(), self.TASK, "system",
                     "state -> tests_writing", "")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, self.get_task())

        self.assertIsNotNone(conflict)

    # ------------------------------------------------------------ cmd_release

    def test_cmd_zone_release_journals_conscious_risk(self):
        """Ловит мутацию: `cmd_zone_release` не журналирует запись
        `RELEASE_ACTION` актором `operator` со словом «риск» в деталях —
        требование 6 обязывает пометку «осознанный риск», не тихое
        снятие."""
        out = capture(zone_lock.cmd_zone_release, self.TASK)

        tail = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(tail["actor"], "operator")
        self.assertEqual(tail["action"], zone_lock.RELEASE_ACTION)
        self.assertIn("риск", tail["detail"])
        self.assertIn(self.TASK, out)

    def test_cmd_zone_release_resolves_prefix(self):
        """Ловит мутацию: `cmd_zone_release` не резолвит короткий префикс
        id через `store.resolve_task_id` — команда падает или пишет в
        журнал несуществующей задачи вместо `self.TASK`."""
        capture(zone_lock.cmd_zone_release, "T00")

        tail = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(tail["action"], zone_lock.RELEASE_ACTION)

    # ------------------------------------------------------------------- refusal

    def test_refusal_names_path_task_and_state(self):
        """Ловит мутацию: `refusal` возвращает общий текст «зона занята»
        без подстановки пути/id/состояния занявшей задачи (требование 2)."""
        self.set_own_zones("a/b")
        occupier = self.seed_other("review", "a/b")
        self._mark_already_started(occupier)

        text = zone_lock.refusal(store.db(), self.TASK, self.get_task())

        self.assertIsNotNone(text)
        self.assertIn("a/b", text)
        self.assertIn(self.OTHER, text)
        self.assertIn("review", text)

    def test_refusal_is_none_without_conflict(self):
        """Ловит мутацию: `refusal` возвращает непустой текст, даже когда
        `blocking_conflict` вернул `None` — отказ печатался бы там, где
        первый шаг обязан пройти."""
        self.set_own_zones("a/b")

        self.assertIsNone(
            zone_lock.refusal(store.db(), self.TASK, self.get_task()))

    # --------------------------------------------------------------- queue_order

    def test_queue_order_sorts_by_approve_marker_ascending(self):
        """Ловит мутацию R1-F2: `queue_order` сортирует по чему-то, кроме
        реального момента approve (например по порядку id задач в БД или
        по `tasks.updated_at` без учёта маркера) — T903 approved раньше
        T902, ожидаем его первым, независимо от порядка на входе."""
        self.seed_other("in_dev", "a/b", task_id="T902")
        self.seed_other("in_dev", "a/b", task_id="T903")
        self.mark_approved("T903")
        self.mark_approved("T902")

        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T903", "T902"])

    def test_slower_tests_writing_does_not_reorder_earlier_approve(self):
        """Ловит мутацию R1-F2 (REVIEW.md итерации 1): `queue_order`
        использует `tasks.updated_at` вместо реального маркера approve —
        T902 approved РАНЬШЕ T903, но дольше задержался в `tests_writing`
        и получил более ПОЗДНИЙ `updated_at`; если бы очередь читала
        `updated_at`, T902 оказался бы после T903 — обратный требованию 7
        порядок."""
        self.seed_other("in_dev", "a/b", task_id="T902")
        self.seed_other("in_dev", "a/b", task_id="T903")
        self.mark_approved("T902")
        self.mark_approved("T903")
        store.update_task(store.db(), "T902", updated_at="2026-09-05 23:00:00Z")
        store.update_task(store.db(), "T903", updated_at="2026-09-01 00:00:00Z")

        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T902", "T903"])

    def test_queue_order_falls_back_to_updated_at_without_approve_marker(self):
        """Ловит мутацию: задачи без маркера approve в журнале (заведённые
        в обход `set_state` — тот же случай, что приёмочная песочница
        `_sandbox.ZoneSandbox.seed_task`) перестают сортироваться вовсе
        (или падают) вместо фолбэка на `tasks.updated_at` — приёмочные
        тесты AC-8/AC-9 фиксируют именно этот фолбэк буквально."""
        self.seed_other("in_dev", "a/b", task_id="T902")
        store.update_task(store.db(), "T902",
                          updated_at="2026-09-01 10:00:00.000000Z")
        self.seed_other("in_dev", "a/b", task_id="T903")
        store.update_task(store.db(), "T903",
                          updated_at="2026-09-01 09:00:00.000000Z")

        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T903", "T902"])

    def test_explicit_position_overrides_approve_order(self):
        """Ловит мутацию: `zone_queue_position`, выставленный
        `cmd_zone_reorder`, не имеет приоритета над естественным порядком
        approve — требование 9 (Оператор переставляет очередь явно) не
        действовало бы."""
        self.seed_other("in_dev", "a/b", task_id="T902")
        self.seed_other("in_dev", "a/b", task_id="T903")
        self.mark_approved("T902")
        self.mark_approved("T903")

        zone_lock.cmd_zone_reorder(["T903", "T902"])
        order = zone_lock.queue_order(store.db(), ["T902", "T903"])

        self.assertEqual(order, ["T903", "T902"])

    def test_reorder_positions_take_priority_over_unpositioned_natural_order(self):
        """Ловит мутацию: задача с явно выставленной `zone_queue_position`
        сортируется НАРАВНЕ с непереставленными (по approve), а не строго
        раньше их всех — `cmd_zone_reorder` был бы виден только когда ни у
        одной задачи очереди нет естественного порядка вовсе."""
        self.seed_other("in_dev", "a/b", task_id="T902")
        self.seed_other("in_dev", "a/b", task_id="T903")
        self.seed_other("in_dev", "a/b", task_id="T904")
        self.mark_approved("T902")
        self.mark_approved("T903")
        self.mark_approved("T904")

        zone_lock.cmd_zone_reorder(["T904"])
        order = zone_lock.queue_order(store.db(), ["T902", "T903", "T904"])

        self.assertEqual(order, ["T904", "T902", "T903"])

    # ------------------------------------------------------------ queue_position

    def _mark_already_started(self, task_id: str) -> None:
        """Журналирует маркеры реального держателя зоны: уже прошёл СВОЙ
        первый шаг (`agent run started`), поэтому `blocking_conflict` для
        НЕГО САМОГО возвращает `None` (не «ждёт», а «занимает»), хотя он
        всё ещё в `in_dev` и остаётся занявшей зону задачей для других."""
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> in_dev", "")
        store.journal(conn, task_id, "developer", "agent run started", "")

    def test_queue_position_reports_rank_among_same_zone_competitors(self):
        """Ловит мутацию R1-F3: `queue_position` не сверяет конфликтный
        путь конкурента с переданным `path` (считает конкурентом ЛЮБУЮ
        заблокированную задачу, не только тех, кто ждёт ИМЕННО эту зону),
        либо не исключает саму занявшую зону задачу (уже прошедшую свой
        первый шаг) из числа «ожидающих» — переоценивает очередь."""
        self.set_own_zones("a/b")
        occupier = self.seed_other("in_dev", "a/b", task_id="T900")
        self._mark_already_started(occupier)
        self.seed_other("in_dev", "a/b", task_id="T910")
        self.mark_approved("T910")
        self.mark_approved(self.TASK)

        position, total = zone_lock.queue_position(
            store.db(), self.TASK, "a/b")

        self.assertEqual(total, 2)
        self.assertEqual(position, 2)

    def test_queue_position_ignores_competitors_blocked_on_a_different_path(self):
        """Ловит мутацию R1-F3: `queue_position` считает конкурентом
        задачу, заблокированную ДРУГИМ путём (её `blocking_conflict`
        называет иную зону) — очередь смешала бы конкурентов по разным
        зонам в одну позицию."""
        self.set_own_zones("a/b")
        occupier_ab = self.seed_other("in_dev", "a/b", task_id="T900")
        self._mark_already_started(occupier_ab)
        occupier_cd = self.seed_other("in_dev", "c/d", task_id="T950")
        self._mark_already_started(occupier_cd)
        self.seed_other("in_dev", "c/d", task_id="T920")

        position, total = zone_lock.queue_position(
            store.db(), self.TASK, "a/b")

        self.assertEqual(total, 1)
        self.assertEqual(position, 1)


if __name__ == "__main__":
    unittest.main()
