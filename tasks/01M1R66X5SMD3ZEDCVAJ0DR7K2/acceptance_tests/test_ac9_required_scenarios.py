"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-9 (SPEC перечисляет
буквально сценарии, которые планка обязана закодировать: draft-SPEC без
zones, ready-SPEC без zones, ANSWER без секции «Ответы» — плюс регрессия
`tests/test_guard*.py`/`tests/test_invariants.py::
GuardKeepsTheIntegritySectionTest`, за которую отвечает НЕ добавление
новых тестов, а неослабление уже существующих: см. примечание в конце
файла).

Красен до реализации: три класса ниже красны по трём разным причинам —
`DraftSpecScenarioTest` и `ReadySpecScenarioTest` — по причине
`test_ac5_*`/`test_ac2_*` (флаг `--artifact-branch` не распознан
сегодня, см. их докстринги); `DraftSpecStillBlocksAdvanceTest` — по
СОВСЕМ другой причине: `fsm.guard_refuses` уже СЕГОДНЯ отказывает
черновику без `zones` (это существующее с 01M1NKVPD2A79PQ6K0JVV1B2Q1
поведение, которое эта задача обязана СОХРАНИТЬ, не создать) — эта
проверка уже зелёная и останется зелёной после реализации; красный она
станет только если разработчик СЛОМАЕТ существующее поведение (см.
докстринг класса — «Зелёный с рождения»).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (GuardRefusesSandbox, answer_missing_section_text,  # noqa: E402
                      run_main, spec_zones_text)


class DraftSpecScenarioTest(unittest.TestCase):
    """draft-SPEC (schema_version 4) без `zones` — предупреждение в
    режиме артефактной ветки, ошибка при вызове guard без режима."""

    def test_ac9_draft_spec_without_zones_warns_with_mode_and_errors_without(self):
        """Один и тот же черновик SPEC без `zones` — без флага
        `--artifact-branch` отказывает (exit 1, есть «zones» в выводе), с
        флагом — проходит (exit 0).

        Ловит мутацию: разработчик считает СПЕЦИФИЧНО отсутствие `zones`
        особым случаем, не подпадающим под общее понижение до
        предупреждения (например явно перечисляет типы нарушений для
        понижения и забывает zones-специфичную проверку) — тогда прогон
        с флагом продолжил бы отказывать (exit 1) для этого конкретного
        нарушения, хотя AC-2 не делает исключения по ВИДУ нарушения
        внутри «содержательных» проверок.
        """
        text = spec_zones_text(status="draft", zones=None)

        code_off, out_off = run_main({"tasks/T1/SPEC.md": text},
                                     artifact_branch=False)
        code_on, out_on = run_main({"tasks/T1/SPEC.md": text},
                                   artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertIn("zones", out_off)
        self.assertEqual(code_on, 0, out_on)


class DraftSpecStillBlocksAdvanceTest(GuardRefusesSandbox):
    """«В т.ч. эмуляция перехода advance»: тот же draft-SPEC без `zones`,
    прогнанный через РЕАЛЬНУЮ `fsm.guard_refuses` (та функция, которую
    сегодня зовут все переходы `orchestrator/fsm_advance.py`, без нового
    аргумента режима) — обязан отказать, как отказывает и сегодня.

    Зелёный с рождения: `guard.check_content` УЖЕ СЕГОДНЯ (до кода этой
    задачи, с 01M1NKVPD2A79PQ6K0JVV1B2Q1) требует `zones` для SPEC
    schema_version 4 независимо от status — этот тест проверяет, что
    задача НЕ ЛОМАЕТ существующее поведение вызова без режима (AC-1: «в
    т.ч. всё, что сегодня зовёт guard.check/guard.check_content из
    orchestrator/fsm.py»), а не что она его создаёт.
    """

    def test_ac9_draft_spec_without_zones_still_refused_via_fsm_guard_call(self):
        """Ловит мутацию: разработчик протаскивает режим артефактной
        ветки внутрь `check_content`/`check` со значением по умолчанию
        `True` (вместо `False`) — тогда ЛЮБОЙ существующий вызов, включая
        `fsm.guard_refuses` без нового аргумента, начал бы трактовать
        draft SPEC мягко, и этот черновик без `zones` перестал бы
        отказывать.
        """
        text = spec_zones_text(status="draft", zones=None)

        refused = self.guard_refuses(text)

        self.assertTrue(refused, "guard_refuses должен отказать draft SPEC "
                                 "без zones — как и до этой задачи")


class ReadySpecScenarioTest(unittest.TestCase):
    """ready-SPEC без `zones` — ошибка в обоих случаях (с флагом и без)."""

    def test_ac9_ready_spec_without_zones_errors_in_both_modes(self):
        """Ловит мутацию: разработчик путает направление сравнения статуса
        (например `if status != "ready": suppress()` вместо `if status ==
        "draft": suppress()`) — тогда именно `ready`-статус, а не
        `draft`, получил бы мягкий проход с флагом, и этот тест
        покраснел бы вместо `test_ac9_draft_spec_without_zones_warns_
        with_mode_and_errors_without`.
        """
        text = spec_zones_text(status="ready", zones=None)

        code_off, out_off = run_main({"tasks/T1/SPEC.md": text},
                                     artifact_branch=False)
        code_on, out_on = run_main({"tasks/T1/SPEC.md": text},
                                   artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertIn("zones", out_off)
        self.assertEqual(code_on, 1, out_on)
        self.assertIn("zones", out_on)


class AnswerScenarioTest(unittest.TestCase):
    """ANSWER без секции «## Ответы» — ошибка независимо от режима."""

    def test_ac9_answer_without_section_errors_regardless_of_mode(self):
        text = answer_missing_section_text()

        code_off, out_off = run_main({"tasks/T1/ANSWER.md": text},
                                     artifact_branch=False)
        code_on, out_on = run_main({"tasks/T1/ANSWER.md": text},
                                   artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertIn("Ответы", out_off)
        self.assertEqual(code_on, 1, out_on)
        self.assertIn("Ответы", out_on)


if __name__ == "__main__":
    unittest.main()

# Примечание к AC-9 (не пометка critерия — тест на сами сценарии выше
# уже написан): «tests/test_guard*.py и tests/test_invariants.py::
# GuardKeepsTheIntegritySectionTest остаются зелёными без ослабления
# проверяемого ими поведения» — это ограничение НА РЕАЛИЗАЦИЮ
# разработчика (не трогать/не ослаблять существующие тесты), а не
# отдельный сценарий, который нужно закодировать НОВЫМ тестом: сам факт
# зелёного прогона `tests/test_guard*.py`/`tests/test_invariants.py`
# проверяется штатным CI-джобом на ветке задачи и гейтом приёмки
# (docs/operator-gates.md, «Гейт приёмки») — тем же приёмом, что AC-16 в
# tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/test_scope_markers.py
# («существующий набор тестов остаётся зелёным» — уже покрыто штатным
# CI-джобом, повтор подпроцессом внутри своего же acceptance_tests ловил
# бы окружение машины, не дефект задачи).
