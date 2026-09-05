"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-1, AC-2, AC-3 (SPEC.md).

Допущения интерфейса и зависимость от части 1 (01M1NKVPD2A79PQ6K0JVV1B2Q1)
— см. докстринг `_sandbox.py`.

Красен до реализации: в этом дереве (часть 1 не смержена) у таблицы
`tasks` нет колонки `zones` и у `config` нет `COMMON_ZONES` — песочница
(`_sandbox.ZoneSandbox`) сама добавляет их на время тестов (см. её
докстринг), так что прогон падает НЕ на этом, а на отсутствии самой
проверки занятости зоны в `runner._cmd_run`: сегодня `_cmd_run` останавливается
только на `budget_block`/`parallel_limit.refusal`/паузе/чужой ветке
(`orchestrator/runner.py`, строки вокруг `_cmd_run`) — задача с
пересекающимися зонами свободно стартует агента, `run_with_fake_agent`
ниже увидит `popen.called is True` там, где тест ждёт отказа, и упадёт на
`assertFalse`/`popen.assert_not_called()`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox  # noqa: E402

from orchestrator import auto, runner  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac1RunBlockedByEachStateInRangeTest(ZoneSandbox):
    """AC-1: перед первым шагом `in_dev` зоны задачи сверяются с зонами
    ВСЕХ задач в фазах `in_dev`…`merge_gate` — занявшая зону задача в
    ЛЮБОЙ из этих фаз (не только `in_dev`) блокирует запуск.

    Ловит мутацию: проверка занятости зоны сравнивает только с задачами в
    состоянии `in_dev` буквально (забыт диапазон `review`/`verifying`/
    `acceptance`/`merge_gate`) — занявшая зону задача в `review` перестала
    бы блокировать, хотя SPEC требует весь диапазон.
    """

    def test_ac1_occupier_in_review_blocks_run(self):
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "review", CONFLICT_PATH)

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertIn(OCCUPIER.lower(), out.lower(),
                     f"отказ не назвал занявшую зону задачу {OCCUPIER}: {out!r}")

    def test_ac1_occupier_in_merge_gate_blocks_run(self):
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "merge_gate", CONFLICT_PATH)

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertIn(OCCUPIER.lower(), out.lower(),
                     f"отказ не назвал занявшую зону задачу {OCCUPIER}: {out!r}")


class Ac1OutOfRangeStatesDoNotBlockTest(ZoneSandbox):
    """AC-1 (граница диапазона): задача с той же зоной, но ВНЕ фаз
    `in_dev`…`merge_gate` (`tests_writing` до входа в код, `done` после
    закрытия) не считается «занявшей зону» — запуск проходит.

    Ловит мутацию: диапазон расширен на всё множество состояний ( код
    сравнивает зоны вообще со всеми задачами независимо от фазы) —
    `tests_writing`/`done` начали бы ложно блокировать.
    """

    def test_ac1_occupier_in_tests_writing_does_not_block(self):
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Ещё пишет тесты", "tests_writing",
                       CONFLICT_PATH)

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"run отказал из-за задачи в tests_writing (вне диапазона "
            f"in_dev…merge_gate): {out!r}")

    def test_ac1_occupier_done_does_not_block(self):
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Уже закрыта", "done", CONFLICT_PATH)

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"run отказал из-за уже закрытой (done) задачи: {out!r}")


class Ac2NamedRefusalBlocksRunAndAutoTest(ZoneSandbox):
    """AC-2: пересечение зон вне общего списка даёт именованный отказ вида
    «зона <путь> занята задачей <id> (<состояние>)»; сам шаг не
    запускается — ни через `run`, ни через первый шаг `auto`.

    Ловит мутацию: отказ печатается/журналируется, но НЕ называет путь
    зоны, id занявшей задачи или её состояние буквально (например общий
    текст «зона занята» без подстановок) — assertRegex ниже требует все
    три значения одновременно в связке «занята задачей ... (...)».
    """

    def _seed_conflict(self, occupier_state: str = "in_dev") -> None:
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", occupier_state,
                       CONFLICT_PATH)

    def test_ac2_run_refusal_names_path_task_and_state(self):
        self._seed_conflict()
        journalled_before = self.journal_len()

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertEqual(self.task_state(self.TASK), "in_dev",
                         "run отказался стартовать, но состояние задачи сдвинулось")
        journal = self.journal_tail(self.TASK, journalled_before)
        combined = f"{out}\n{journal}".lower()
        self.assertTrue(journal.strip(),
                        "отказ по пересечению зон не записан в журнал задачи")
        self.assertIn(CONFLICT_PATH.lower(), combined,
                     f"отказ не назвал путь зоны {CONFLICT_PATH}")
        self.assertRegex(
            combined,
            rf"занята задачей {OCCUPIER.lower()}\s*\(in_dev\)",
            f"отказ не назвал занявшую задачу и её состояние по образцу "
            f"«занята задачей {OCCUPIER} (in_dev)»: {combined!r}")

    def test_ac2_auto_is_refused_the_same_way_on_first_step(self):
        self._seed_conflict()
        journalled_before = self.journal_len()

        out, popen = self.run_with_fake_agent(
            lambda: auto.cmd_auto(self.TASK, session_id=self.CALLER_SESSION))

        popen.assert_not_called()
        self.assertEqual(self.task_state(self.TASK), "in_dev",
                         "auto не должен был сдвинуть состояние на первом же "
                         "отказавшем шаге")
        combined = f"{out}\n{self.journal_tail(self.TASK, journalled_before)}".lower()
        self.assertIn(CONFLICT_PATH.lower(), combined,
                     f"auto: отказ не назвал путь зоны {CONFLICT_PATH}")
        self.assertRegex(
            combined, rf"занята задачей {OCCUPIER.lower()}\s*\(in_dev\)",
            f"auto: отказ не назвал занявшую задачу и её состояние: {combined!r}")


class Ac3CommonZoneIntersectionDoesNotConflictTest(ZoneSandbox):
    """AC-3: пересечение ТОЛЬКО по путям из общего списка зон (часть 1,
    `config.COMMON_ZONES`) не считается конфликтом при этой проверке —
    запуск проходит.

    Ловит мутацию: общий список не исключён из сравнения (проверка
    сравнивает зоны буквально, не вычитая `COMMON_ZONES`) — пересечение
    по `tests/` (общая зона) начало бы ложно блокировать запуск.
    """

    def test_ac3_intersection_only_on_common_zone_passes(self):
        self.reset_task()
        self.set_own_zones("tests/")
        self.seed_task(OCCUPIER, "Занявшая только общую зону", "in_dev",
                       "tests/")

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"run отказал из-за пересечения ТОЛЬКО по общей зоне tests/ "
            f"(config.COMMON_ZONES): {out!r}")

    def test_ac3_common_zone_path_ignored_even_alongside_real_conflict_absence(self):
        """Смешанный набор: обе задачи несут общую зону `tests/` ПЛЮС по
        одной РАЗНОЙ (непересекающейся) собственной зоне — запуск проходит
        (нет пересечения вне общего списка).

        Ловит мутацию: разбор `zones` по запятой сломан (берётся только
        первый путь, второй теряется) — пропавшая проверка второго пути
        случайно замаскировала бы дефект AC-3 совпадением с первым тестом
        этого класса; здесь конфликта нет ни по одному из путей, поэтому
        любая потеря элемента списка не может дать ложный отказ, а
        разбор должен реально пройтись по ОБОИМ элементам.
        """
        self.reset_task()
        self.set_own_zones("tests/, orchestrator/self_only.py")
        self.seed_task(OCCUPIER, "Общая зона плюс своя", "in_dev",
                       "tests/, orchestrator/other_only.py")

        out, popen = self.run_with_fake_agent(
            lambda: runner.cmd_run(self.TASK, session_id=self.CALLER_SESSION))

        self.assertTrue(
            popen.called,
            f"run отказал при пересечении только по общей зоне tests/ и "
            f"непересекающихся собственных зонах: {out!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
