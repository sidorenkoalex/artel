"""Приёмочные тесты SPEC 01M2ARQD7C472KZACB3SZXGF1N: повтор developer
внутри цикла канарейки на красной приёмочной планке (решение Оператора
12.09, вариант а) — воспроизведение ручного `run <id>` ВНУТРИ
`canary._drive_task`, не трогая поведение `auto` для обычных задач.

Красен до реализации: `config.CANARY_MAX_DEV_RETRIES` ещё не существует
(`orchestrator/config.py`) и `canary._drive_task` не несёт ветки
повтора developer (`orchestrator/canary.py`) — обращение к константе
роняет `AttributeError`, а сценарии ниже, ожидающие вызова
`runner.cmd_run` из цикла на отказе «переход отклонён: приёмочные
тесты», падают на `assert_called_once`/подсчёте вызовов: сегодняшний
код на этом отказе просто копит `stall_streak` и убивает задачу как
стагнацию, ни разу не позвав `runner.cmd_run`.

AC-7/AC-8/AC-9 SPEC называют местом теста `tests/test_canary.py` —
файл вне зоны test_author (зона задачи по фронтматтеру — `tests/`,
зона разработчика; правило «Код репозитория... не трогай» этой роли).
Здесь тесты проверяют ЗАЯВЛЕННОЕ В КРИТЕРИИ ПОВЕДЕНИЕ напрямую против
`orchestrator/canary.py` (тот же приём, каким уже проверены AC-1..AC-5
предыдущей задачи 01M2A22CG2P0E69H00RDHFF3K4, `RunOneTaskReportsTest
AuthorPassageTest`) — генуинно красные сейчас, зелёные после
реализации; факт буквального размещения зеркального теста разработчика
именно в `tests/test_canary.py` — предметная проверка ревьювером
диффа на приёмке (тот же принцип, что и манульная пометка AC-7 той же
предыдущей задачи, `test_spec_gate_artifact_source.py:223`).
"""
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

ACCEPTANCE_REFUSAL = "переход отклонён: приёмочные тесты"
OTHER_CLASS_REFUSAL = "переход отклонён: гейт зон"


class DevRetryConstantTest(unittest.TestCase):
    """AC-1: `config.CANARY_MAX_DEV_RETRIES` — новая именованная
    константа со значением `2`."""

    def test_ac1_dev_retries_constant_equals_two(self):
        """Значение потолка повторов developer — ровно `2` (решение
        Оператора 12.09, вариант а), по образцу соседних потолков цикла
        канарейки (`CANARY_MAX_ESCALATION_CYCLES`, `CANARY_MAX_STALL_
        ITERS`), которые тоже заданы буквальным литералом в `config.py`.

        Ловит мутацию: константа отсутствует, названа иначе, либо несёт
        другое значение (0, 1, 3) — потолок повторов был бы либо
        нерабочим, либо расходился бы с решением Оператора.
        """
        self.assertEqual(config.CANARY_MAX_DEV_RETRIES, 2)


class DriveTaskDevRetryOnAcceptanceRefusalTest(TmpRootTest):
    """AC-2 (прямой путь) и AC-7: `_drive_task` — задача осталась в
    `in_dev` после `auto.cmd_auto`, последняя журнальная запись —
    прямой отказ `fsm` «переход отклонён: приёмочные тесты» (не через
    обёртку «auto остановлен»)."""

    TASK = "ACDEV7"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача AC-7",
                          "in_dev", "task/acdev7-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        self.auto_calls = 0

        def fake_auto(task_id):
            self.auto_calls += 1
            if self.auto_calls == 1:
                store.journal(self.conn, task_id, "fsm", ACCEPTANCE_REFUSAL,
                             "acceptance_tests красные:\n...\nокружение: x")
                return
            # Второй проход — задача сдвинулась дальше `in_dev`: цикл
            # обязан продолжить работу очередным `auto.cmd_auto`, а не
            # застрять/убить задачу на этом отказе навсегда.
            store.set_state(self.conn, task_id, "merge_gate", "test",
                            expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac7_single_dev_retry_calls_runner_cmd_run_once_and_continues(self):
        """Один отказ приёмочной планки в `in_dev` — цикл зовёт
        `runner.cmd_run(task_id)` ровно один раз (воспроизводя ручной
        возврат Оператора `run <id>`) и продолжает работу очередным
        `auto.cmd_auto`, а не стагнирует/убивает задачу на этом же
        проходе.

        Ловит мутацию: «повтор не вызывается» — ветка требования 2 не
        добавлена вовсе, отказ по-прежнему копится `stall_streak`ом без
        единого вызова `runner.cmd_run`.
        """
        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_called_once_with(self.TASK)
        self.assertEqual(self.auto_calls, 2)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)

    def test_ac3_dev_retry_counts_as_progress_and_spends_budget(self):
        """Повтор developer — прогресс цикла, не стагнация: `spent_usd`
        задачи растёт на самом вызове `runner.cmd_run`, а цикл доходит
        до `merge_gate` штатно, не будучи убит стагнацией
        (`_kill_inconclusive`, алерт `kind=threshold`) на этом же отказе.

        Ловит мутацию: повтор developer учтён как обычный проход без
        прогресса генерик-веткой стагнации (не собственной веткой
        требования 2) — тогда либо `spent_usd` не растёт (генерик-ветка
        не зовёт `runner.cmd_run` вовсе), либо задача убивается через
        `_kill_inconclusive` вместо штатного `merge_gate`.
        """
        def fake_cmd_run(task_id):
            t = store.get_task(self.conn, task_id)
            store.update_task(self.conn, task_id, spent_usd=t["spent_usd"] + 3.0)

        canary.runner.cmd_run.side_effect = fake_cmd_run

        canary._drive_task(self.conn, self.TASK)

        self.assertGreater(store.get_task(self.conn, self.TASK)["spent_usd"], 0.0)
        rows = store.open_alerts(self.conn, "threshold")
        self.assertFalse(any(r["target"] == self.TASK for r in rows), list(rows))
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)


class DriveTaskDevRetryViaAutoStoppedWrapperTest(TmpRootTest):
    """AC-2 (второй путь): отказ несёт запись «auto остановлен» (стоп-
    кран T038), несущую тот же текст отказа внутри причины остановки —
    не прямую журнальную запись `fsm`."""

    TASK = "ACDEV2"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача AC-2",
                          "in_dev", "task/acdev2-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        self.auto_calls = 0

        def fake_auto(task_id):
            self.auto_calls += 1
            if self.auto_calls == 1:
                # Тот же формат, каким `auto.auto_stop`/`orchestrator/
                # auto.py:457-476` журналирует остановку стоп-краном
                # T038 на отказе `in_dev`, класса требования 4 auto.py:
                # `f"{state}: {other_class_refusal} — {hint}"`.
                store.journal(
                    self.conn, task_id, "operator", "auto остановлен",
                    f"in_dev: {ACCEPTANCE_REFUSAL} — почини причину и "
                    f"повтори artel.py advance {task_id}")
                return
            store.set_state(self.conn, task_id, "merge_gate", "test",
                            expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac2_dev_retry_detected_when_wrapped_by_auto_stopped(self):
        """Отказ приёмочной планки, видимый ТОЛЬКО как причина остановки
        `auto` стоп-краном («auto остановлен: in_dev: переход отклонён:
        приёмочные тесты — ...»), распознаётся тем же путём, что и
        прямая запись `fsm` — цикл всё равно зовёт `runner.cmd_run`
        ровно один раз и продолжает работу.

        Ловит мутацию: детектор ищет ТОЛЬКО буквальное совпадение
        `action == "переход отклонён: приёмочные тесты"`, не заглядывая
        внутрь `detail` записи «auto остановлен» — тогда этот сценарий
        (единственный, где T038 успел сработать раньше самого отказа)
        не находит причины вовсе, и `runner.cmd_run` ни разу не звонит.
        """
        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_called_once_with(self.TASK)
        self.assertEqual(self.auto_calls, 2)


class DriveTaskDevRetryCounterResetsBetweenVisitsTest(TmpRootTest):
    """AC-4 (обнуление счётчика): визит `in_dev` -> ровно потолок
    повторов -> уход из `in_dev` -> возврат -> снова ровно потолок
    повторов — ни один из двух визитов по отдельности потолок не
    превышает, поэтому задача обязана дожить до `merge_gate`."""

    TASK = "ACDEV4"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача AC-4",
                          "in_dev", "task/acdev4-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        self.auto_calls = 0

        def fake_auto(task_id):
            self.auto_calls += 1
            cap = config.CANARY_MAX_DEV_RETRIES
            n = self.auto_calls
            if n <= cap:
                store.journal(self.conn, task_id, "fsm", ACCEPTANCE_REFUSAL,
                             f"визит 1, попытка {n}")
                return
            if n == cap + 1:
                store.set_state(self.conn, task_id, "review", "test",
                                expected_state="in_dev")
                return
            if n == cap + 2:
                store.set_state(self.conn, task_id, "in_dev", "test",
                                expected_state="review")
                return
            if n <= 2 * cap + 2:
                store.journal(self.conn, task_id, "fsm", ACCEPTANCE_REFUSAL,
                             f"визит 2, попытка {n - (cap + 2)}")
                return
            store.set_state(self.conn, task_id, "merge_gate", "test",
                            expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac4_counter_resets_when_leaving_in_dev_between_visits(self):
        """Два визита `in_dev`, каждый ровно с потолочным числом
        повторов (не больше) — обнуление счётчика при уходе из `in_dev`
        не даёт второму визиту начаться с накопленного значения первого.

        Ловит мутацию: счётчик повторов заведён на всю задачу, а не на
        один визит `in_dev` (не обнуляется при уходе из состояния) —
        тогда первая же попытка ВТОРОГО визита превысила бы потолок
        (унаследовав его от первого визита) и убила бы задачу через
        `_kill_inconclusive`, не дав ей дожить до `merge_gate`.
        """
        canary._drive_task(self.conn, self.TASK)

        cap = config.CANARY_MAX_DEV_RETRIES
        rows = store.open_alerts(self.conn, "threshold")
        self.assertFalse(any(r["target"] == self.TASK for r in rows), list(rows))
        self.assertEqual(canary.runner.cmd_run.call_count, 2 * cap)
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)


class DriveTaskDevRetryCapKillsInconclusiveTest(TmpRootTest):
    """AC-4 (превышение потолка) и AC-8: `config.CANARY_MAX_DEV_RETRIES
    + 1` отказов подряд одной причиной — убивает задачу через
    `_kill_inconclusive`, не давая циклу зациклиться на повторах
    навсегда."""

    TASK = "ACDEV8"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача AC-8",
                          "in_dev", "task/acdev8-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        def fake_auto(task_id):
            store.journal(self.conn, task_id, "fsm", ACCEPTANCE_REFUSAL,
                         "acceptance_tests красные: одна и та же причина")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac8_exceeding_cap_kills_inconclusive_and_bounds_cmd_run_calls(self):
        """`config.CANARY_MAX_DEV_RETRIES + 1` отказов подряд одной и той
        же причиной — цикл убивает задачу через `_kill_inconclusive` с
        текстом требования 3/AC-4, а `runner.cmd_run` за весь визит
        состояния вызван не больше потолка раз (сверх потолка — не
        вызывается).

        Ловит мутацию: потолок не проверяется вовсе (цикл продолжает
        звать `runner.cmd_run` на каждом отказе бесконечно — тест
        завис бы либо `cmd_run.call_count` превысил бы потолок), либо
        текст убийства не совпадает с требованием 3 буквально (Оператор
        не сможет узнать причину в отчёте по образцу соседних потолков).
        """
        canary._drive_task(self.conn, self.TASK)

        cap = config.CANARY_MAX_DEV_RETRIES
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        self.assertEqual(canary.runner.cmd_run.call_count, cap)

        rows = store.open_alerts(self.conn, "threshold")
        matching = [r for r in rows if r["target"] == self.TASK]
        expected_text = (f"canary: {cap} повторов developer на красной "
                         "планке — задача не сходится")
        self.assertTrue(
            any(r["message"] == expected_text for r in matching),
            [r["message"] for r in matching])


class RunOneTaskReportsDevRetriesTest(TmpRootTest):
    """AC-6 и AC-9: строка отчёта задачи прогона канарейки несёт поле
    «повторов developer=<n>» — число выполненных повторов видно в
    отчёте, не только в journal/steps.txt. `_ephemeral_clone` подменена
    целиком (по образцу `canary._CLONE_CONFIG_ATTRS`/`_run_one_task`
    докстринга: реальный git этому сценарию не нужен, `TmpRootTest` уже
    даёт согласованные пути `config`), `catalog.cmd_new`/`workspace.
    ensure` — тонкими стенд-заглушками, заводящими реальную строку
    `tasks` напрямую через `store`, чтобы `_drive_task` внутри работал
    БЕЗ подмены — тот же код, что и в остальных тестах этого файла."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

        @contextmanager
        def fake_ephemeral_clone():
            yield config.ROOT

        patcher = mock.patch.object(canary, "_ephemeral_clone",
                                    fake_ephemeral_clone)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.gitcmd, "head_sha",
                                    return_value="deadbeefcafefeed")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.workspace, "ensure",
                                    return_value=(Path("/fake-wt"), None))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.template_path = self.root / "ac6-ac9-template.md"
        self.template_path.write_text(
            "# Канареечный шаблон AC-6/AC-9\n\nБез маркера эскалации.\n",
            encoding="utf-8")

    @staticmethod
    def _fake_cmd_new(task_id):
        def fake(title, tz_path=None, canary=False):
            store.insert_task(store.db(), task_id, title, "in_dev",
                              f"task/{task_id.lower()}-x",
                              config.DEFAULT_TARGET, 50.0, is_canary=True)
            return task_id
        return fake

    def test_ac6_report_line_carries_dev_retries_count(self):
        """Один повтор developer за прогон задачи — итоговая строка
        отчёта (`шагов=... исход=...`) несёт «повторов developer=1», не
        только журнал/steps.txt диагностики.

        Ловит мутацию: `_run_one_task` не прокидывает число повторов
        `_drive_task` в печатаемую строку вовсе (поле отсутствует), либо
        печатает счётчик стагнации/эскалаций вместо счётчика повторов
        developer.
        """
        task_id = "ACREPORT6"
        calls = {"n": 0}

        def fake_auto(tid):
            calls["n"] += 1
            conn = store.db()
            if calls["n"] == 1:
                store.journal(conn, tid, "fsm", ACCEPTANCE_REFUSAL,
                             "acceptance_tests красные")
                return
            store.set_state(conn, tid, "merge_gate", "test",
                            expected_state="in_dev")

        with mock.patch.object(canary.catalog, "cmd_new",
                              side_effect=self._fake_cmd_new(task_id)), \
             mock.patch.object(canary.auto, "cmd_auto", side_effect=fake_auto), \
             mock.patch.object(canary.runner, "cmd_run"), \
             mock.patch.object(canary.cleanup, "cmd_kill"):
            output = capture(canary._run_one_task, self.template_path,
                            "20260912T000000Z", config.CANARY_DEVIATION_RATIO)

        self.assertIn("повторов developer=1", output, output)

    def test_ac9_other_class_refusal_report_shows_zero_retries_and_no_cmd_run(self):
        """Отказ другого класса (требование 4) на протяжении всего
        прогона задачи — `runner.cmd_run` циклом не вызывается ни разу,
        задача убивается прежним путём стагнации, а отчёт прогона несёт
        «повторов developer=0» (AC-6) при полном отсутствии повторов.

        Ловит мутацию: счётчик повторов инициализируется не нулём (или
        отчёт печатает его только когда повторы были, опуская поле при
        нуле) — «повторов developer=0» пропадает из строки отчёта именно
        на сценарии, где повторов не было вовсе.
        """
        task_id = "ACREPORT9"

        def fake_auto(tid):
            store.journal(store.db(), tid, "fsm", OTHER_CLASS_REFUSAL,
                         "зона занята")

        with mock.patch.object(canary.catalog, "cmd_new",
                              side_effect=self._fake_cmd_new(task_id)), \
             mock.patch.object(canary.auto, "cmd_auto", side_effect=fake_auto), \
             mock.patch.object(canary.runner, "cmd_run") as cmd_run, \
             mock.patch.object(canary.cleanup, "cmd_kill"):
            output = capture(canary._run_one_task, self.template_path,
                            "20260912T000000Z", config.CANARY_DEVIATION_RATIO)

        cmd_run.assert_not_called()
        self.assertIn("повторов developer=0", output, output)

        conn = store.db()
        rows = store.open_alerts(conn, "threshold")
        matching = [r for r in rows if r["target"] == task_id]
        self.assertTrue(
            any("проходов подряд без прогресса" in r["message"]
               for r in matching),
            [r["message"] for r in matching])


if __name__ == "__main__":
    unittest.main()
