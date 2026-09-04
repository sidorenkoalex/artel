"""AC-3 (tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md): Ни одна из трёх
точек вызова `_pull_main_or_escalate` (`in_dev -> review`, `acceptance
-> merge_gate`, окно `merge_gate`) не читает и не использует локальный
`config.MAIN_BRANCH` (пин главной копии) для сверки свежести или
подтяжки.

Источник — tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/SPEC.md, «Критерии
приёмки», AC-3.

Третья точка (окно `merge_gate`, `_cmd_approve_merge_gate`) делит с
двумя точками ниже РОВНО ТОТ ЖЕ узел `_pull_main_or_escalate` (см.
докстринг функции в orchestrator/fsm.py: «один и тот же узел для всех
трёх точек сверки») и покрыта тем же кодом, что и они (AC-1/AC-2/AC-4
проверяют сам узел напрямую); отдельного теста на неё здесь нет —
дублировал бы AC-1/AC-2/AC-4 под третьим именем вызывающего кода, не
поймав ни одной ДОПОЛНИТЕЛЬНОЙ мутации. AC-5/AC-6/AC-7 этой же SPEC
(`test_ac5_*.py`) отдельно проверяют путь `merge_gate` ПОСЛЕ сверки
свежести (обработку статуса CI) — там сверка замокана в `"fresh"`
намеренно, предмет тех тестов начинается позже.

Красен до реализации: под текущим кодом ОБЕ точки, проверяемые здесь
(`in_dev -> review` через `fsm.cmd_advance`, `acceptance -> merge_gate`
через `fsm.cmd_approve`), в сценарии «задача форкнута ДО расхождения
origin» видят ветку НЕ отставшей от локального пина и переходят сразу,
БЕЗ подтяжки — то есть решение принимается по локальному
`config.MAIN_BRANCH`, вопреки требованию. Проверено прогоном на
немодифицированном коде при подготовке файла: оба перехода состоялись
без подтяжки (worktree задачи не заведён, апстрим-файла нет).
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import OriginDivergedSandbox, UPSTREAM_MARKER_REL  # noqa: E402
from orchestrator import acceptance, fsm  # noqa: E402


class Ac3EntryPointsIgnoreLocalPinTest(OriginDivergedSandbox):

    def test_ac3_in_dev_to_review_pulls_despite_matching_local_pin(self):
        """`fsm.cmd_advance` из `in_dev` — ветка задачи форкнута ДО
        расхождения origin (совпадает с локальным пином), origin ушёл
        вперёд. Переход обязан подтянуть свежий origin, а не молча
        пройти мимо сверки, приняв совпадение с пином за «не отстала».

        Ловит мутацию: `in_dev -> review` зовёт `_pull_main_or_escalate`
        так, что её внутренняя сверка снова падает на локальный пин
        (например, копия узла с забытым `base`/`fetch`) — переход в
        review случится БЕЗ подтяжки, и в worktree задачи никогда не
        появится апстрим-файл.
        """
        self.advance_origin_only()
        self.write_plan_ready()
        self.set_state("in_dev")

        with mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review",
                         "переход обязан состояться после подтяжки")
        self.assertTrue(
            self.worktree_file(UPSTREAM_MARKER_REL).exists(),
            "подтяжка обязана была произойти — worktree задачи должен "
            "нести файл, существующий только в main артели на origin")

    def test_ac3_acceptance_to_merge_gate_pulls_despite_matching_local_pin(self):
        """`fsm.cmd_approve` из `acceptance` — тот же сценарий, другая
        точка входа: origin ушёл вперёд, локальный пин на месте.

        Ловит мутацию: та же, что у соседнего теста, но на ВТОРОЙ точке
        вызова того же узла — регрессия, специфичная только для ветки
        `elif state == "acceptance"` в `fsm._cmd_approve` (например,
        обёртка, которая случайно не пробрасывает свежий `base` дальше),
        соседним тестом не поймалась бы.
        """
        self.advance_origin_only()
        self.set_state("acceptance")

        with mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.approve()

        self.assertEqual(self.state(), "merge_gate",
                         "переход обязан состояться после подтяжки")
        self.assertTrue(
            self.worktree_file(UPSTREAM_MARKER_REL).exists(),
            "подтяжка обязана была произойти — worktree задачи должен "
            "нести файл, существующий только в main артели на origin")


if __name__ == "__main__":
    import unittest
    unittest.main()
