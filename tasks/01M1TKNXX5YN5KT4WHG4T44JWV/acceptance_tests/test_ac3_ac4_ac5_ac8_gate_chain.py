"""AC-3/AC-4/AC-5/AC-8 (tasks/01M1TKNXX5YN5KT4WHG4T44JWV/SPEC.md): каркас
гейтов перехода `in_dev -> review` — порядок применения, остановка на
первом отказе, ровно одна запись журнала на отказ, отсутствие записей при
полном прохождении. Тесты идут через ПУБЛИЧНУЮ точку входа `fsm.
cmd_advance` (диспетчер зовёт `fsm_advance.in_dev`, чья сигнатура и
модульные имена гейтов `_capacity_gate_refuses`/`_zones_gate_refuses`/
`_review_rework_gate_refuses` зафиксированы AC-6) — не по имени ещё не
написанного каркаса/типа исхода, которое SPEC сознательно не называет.

`GateChainSandbox` (`_sandbox.py`) считает реальные вызовы git-диффа
каждого гейта (`diff_names_calls`/`rework_log_calls`) — прямое
доказательство «гейт не звался», не только «не отказал».

Зелёный с рождения: все четыре сценария ниже уже проходят на СЕГОДНЯШНЕМ
(нерефакторенном) `fsm_advance.py` — последовательность `if _capacity_
gate_refuses(...): return False / if _zones_gate_refuses(...): ... / if
_review_rework_gate_refuses(...): ...` уже устроена как «первый отказ
останавливает цепочку», это и есть ТЕКУЩЕЕ поведение, которое рефакторинг
обязан сохранить byte-for-byte (SPEC, требование 7) — тест фиксирует его
как планку, а не открывает новую дыру. Валидировано прогоном на
сегодняшнем коде перед фиксацией (все проверки уже проходят).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import GateChainSandbox  # noqa: E402


class Ac3StopsAtTheFirstRefusingGateTest(GateChainSandbox):

    def test_ac3_capacity_refusal_stops_before_zones_gate_is_even_called(self):
        """Диф снимка превышает потолок ёмкости И одновременно дифф несёт
        файл вне заявленных зон — оба условия отказа истинны одновременно;
        каркас обязан остановиться на ПЕРВОМ гейте по порядку (ёмкость) и
        не звать зонный гейт вовсе — не просто «не отказать его именем»,
        а не вызвать его git-запрос ни разу.

        Ловит мутацию: цикл каркаса не делает `break`/`return` на первом
        `is not None` (собирает ВСЕ отказы или продолжает список) — тогда
        `diff_names_calls` перестал бы быть пустым, несмотря на уже
        решённый отказ ёмкости.
        """
        self.set_zones("orchestrator/store.py")

        self.advance(code_diff="x" * 300_000, artifacts_diff="",
                    zone_files=["docs/other.py"])

        self.assertEqual(
            self.diff_names_calls, [],
            "гейт зон не имеет права звать git вовсе — гейт ёмкости уже "
            "отказал первым по порядку")
        refusals = self.refusal_rows()
        self.assertEqual(len(refusals), 1)
        self.assertIn("гейт ёмкости", refusals[0][1])


class Ac4ExactlyOneJournalWriteOnRefusalTest(GateChainSandbox):

    def test_ac4_single_refusing_gate_journals_once_prints_hint_keeps_state(self):
        """Ровно один гейт (зоны) отказывает — каркас обязан сделать
        РОВНО одну запись `store.journal` с действием «переход отклонён:
        ...», напечатать подсказку «дальше: ...» и оставить задачу в
        прежнем состоянии `in_dev` (переход не происходит).

        Ловит мутацию: каркас журналирует отказ дважды (например, гейт
        всё ещё журналирует сам ПОВЕРХ каркаса) — счётчик строк журнала
        отказа окажется больше единицы; или каркас не печатает подсказку
        — фрагмент «дальше:» пропадёт из stdout.
        """
        self.set_zones("orchestrator/store.py")

        out = self.advance(code_diff="", artifacts_diff="",
                           zone_files=["docs/other.py"])

        refusals = self.refusal_rows()
        self.assertEqual(
            len(refusals), 1,
            f"ожидалась ровно одна запись отказа, получено: {refusals!r}")
        self.assertIn("гейт зон", refusals[0][1])
        self.assertIn("дальше:", out, "подсказка обязана быть напечатана")
        self.assertEqual(
            self.state(), "in_dev",
            "отказавший гейт не имеет права продвинуть переход")


class Ac5GateOrderMatchesPreRefactorSequenceTest(GateChainSandbox):

    def test_ac5_zones_gate_is_checked_before_the_rework_gate(self):
        """Дифф несёт файл вне зоны И одновременно рубеж «замечания ревью
        не отработаны» тоже открыт (REVIEW.md changes_requested, код не
        менялся после вердикта) — оба условия истинны; порядок ДО
        рефакторинга проверяет зоны раньше рубежа (`orchestrator/
        fsm_advance.py::in_dev`, `_zones_gate_refuses` вызывается строкой
        раньше `_review_rework_gate_refuses`) — этот порядок обязан
        сохраниться (AC-5).

        Ловит мутацию: порядок гейтов в списке каркаса переставлен (рубеж
        перед зонами) — тогда журналировался бы текст рубежа
        («замечания ревью не отработаны»), а не текст зон, и `git log`
        рубежа звался бы, несмотря на уже решённый отказ зон.
        """
        self.set_zones("orchestrator/store.py")
        self.write_review_changes_requested()

        self.advance(code_diff="", artifacts_diff="",
                    zone_files=["docs/other.py"], rework_stale=True)

        refusals = self.refusal_rows()
        self.assertEqual(len(refusals), 1)
        self.assertIn(
            "гейт зон", refusals[0][1],
            f"ожидался отказ ИМЕННО зонного гейта первым (текущий "
            f"порядок), получено: {refusals!r}")
        self.assertEqual(
            self.rework_log_calls, [],
            "гейт рубежа не имеет права звать git log — зонный гейт уже "
            "отказал первым по действующему порядку")


class Ac8AllGatesPassingLeavesNoTraceTest(GateChainSandbox):

    def test_ac8_all_gates_passing_journals_nothing_and_advances(self):
        """Все гейты цепочки проходят (маленький diff, зоны не заявлены,
        REVIEW.md отсутствует) — каркас не делает НИ ОДНОЙ записи
        `store.journal` об отказе, не печатает «переход отклонён», и
        переход происходит (`in_dev` -> `review`).

        Ловит мутацию: каркас журналирует «прохождение» так же, как
        отказ (например, общий `store.journal` вызывается независимо от
        `refusal is None`) — тогда `refusal_rows()` не остался бы пустым.
        """
        out = self.advance(code_diff="", artifacts_diff="", zone_files=[])

        self.assertEqual(
            self.refusal_rows(), [],
            "полное прохождение цепочки не имеет права оставить запись "
            "об отказе")
        self.assertNotIn("переход отклонён", out)
        self.assertEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
