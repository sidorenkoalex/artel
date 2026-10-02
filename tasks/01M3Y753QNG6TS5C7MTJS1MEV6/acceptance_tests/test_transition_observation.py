"""Наблюдение за изменёнными утверждениями на переходе `in_dev -> verifying`
(AC-6, AC-9 на переходе) и неизменность гейта для канареечной задачи и
внешнего target (AC-11).

Группа: разовый

Красен до реализации: обёртка гейта перехода записи «изменены утверждения
тестов (наблюдение)» не пишет, а записи «наблюдение не выполнено» нет ни на
сбое git, ни на неразбираемом файле. AC-11 зелёный с рождения: канареечную
задачу и внешний target гейт пропускает до чтения диффа уже сегодня, тест
держит это свойство против постановки наблюдения перед этой проверкой.

Разовый, а не долгоживущий: вход перехода — закрытая обёртка
`fsm_advance._test_integrity_gate_refuses` (публичного входа у одного гейта
перехода нет, `fsm.cmd_advance` прогоняет весь маршрут `in_dev`); то же
свойство после мержа держат тесты требования 10г/10ж в
`tests/test_test_integrity_gate.py` (AC-14). Песочница — настоящий git
(`ObservationSandbox` долгоживущего файла задачи): база на main, голова на
ветке задачи, мандат — `ANSWER-1.md` на артефактной ветке.
"""
import unittest

from orchestrator import fsm_advance, store
from tests.test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation import (
    ALPHA_TWO, ARTIFACT, BROKEN, CHANGED, CONTEXT_BASE, CONTEXT_HEAD,
    NOT_PERFORMED, OBSERVATION_ACTION, TASK, ObservationSandbox)

REFUSAL_PREFIX = "переход отклонён"

ALPHA_VANISHED_AND_CHANGED = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        self.assertEqual(compute(), 2)
'''


class TransitionSandbox(ObservationSandbox):

    def transition_refused(self) -> bool:
        t = store.get_task(self.conn, TASK)
        return fsm_advance._test_integrity_gate_refuses(self.conn, TASK, t,
                                                        ARTIFACT)

    def set_task_fields(self, **fields) -> None:
        assignments = ", ".join(f"{name}=?" for name in fields)
        self.conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                          (*fields.values(), TASK))
        self.conn.commit()

    def refusals(self) -> list:
        return [(a, d) for a, d in self.journal() if a.startswith(REFUSAL_PREFIX)]

    def not_performed(self) -> list:
        return [(a, d) for a, d in self.journal()
                if NOT_PERFORMED in a or NOT_PERFORMED in d]


class TransitionObservationTest(TransitionSandbox):

    def test_ac6_context_cases_pass_transition_with_one_observation_record(self):
        """Оба случая «Контекста» на переходе: переход проходит, журнал несёт одну запись наблюдения.

        Голова меняет `self.pult_home` на `self.clone_home` в
        `assertIn(str(…), defect)` (01M3SK48D7) и заменяет
        `assertIn("ПУТИ", self.body)` другим `assertIn` (01M3V4ZPB6).
        Обёртка гейта не отказывает, записей «переход отклонён» нет, а
        запись «изменены утверждения тестов (наблюдение)» ровно одна и
        называет `путь: утверждения изменены в Класс::метод: …` обоих
        методов.

        Ловит мутацию: находки об утверждениях влиты в узел отказа —
        переход откажет; наблюдение подключено только к гейту мержа —
        записи на переходе нет; запись пишется на каждый файл или каждую
        находку — записей больше одной.
        """
        self.commit_diff({"tests/test_context.py": CONTEXT_BASE},
                         {"tests/test_context.py": CONTEXT_HEAD})
        self.assertFalse(self.transition_refused(), self.journal())
        self.assertEqual([], self.refusals())
        detail = self.observation()
        self.assertIn(f"tests/test_context.py: {CHANGED}"
                      f"CloneHomeTest::test_defect_names_home: ", detail)
        self.assertIn(f"tests/test_context.py: {CHANGED}"
                      f"StackSectionTest::test_section_names_paths: ", detail)

    def test_ac9_transition_unparsable_file_journals_not_performed(self):
        """Неразбираемый base на переходе — запись «наблюдение не выполнено», переход не отклонён.

        Ловит мутацию: неразбираемая сторона пропускается молча — записи
        «наблюдение не выполнено» нет; либо неразбираемость наблюдения
        превращена в отказ перехода.
        """
        self.commit_diff({"tests/test_alpha.py": BROKEN},
                         {"tests/test_alpha.py": ALPHA_TWO})
        self.assertFalse(self.transition_refused(), self.journal())
        self.assertEqual([], self.refusals())
        self.assertTrue(self.not_performed(), self.journal())

    def test_ac9_transition_git_silence_journals_not_performed(self):
        """Молчание git на переходе — запись «наблюдение не выполнено: <причина>».

        Ветки задачи нет — git не называет базу сравнения. Отказ перехода
        на этом сбое — прежнее fail-closed поведение гейта неослабления
        (не наблюдения) и здесь не сверяется; сверяется, что наблюдение
        о своём невыполнении сказало записью.

        Ловит мутацию: на молчании git наблюдение пропускается без
        записи — записи «наблюдение не выполнено» нет.
        """
        self.set_task_fields(branch="task/t001-net-takoy-vetki")
        self.transition_refused()
        self.assertTrue(self.not_performed(), self.journal())


class CanaryAndExternalTargetTest(TransitionSandbox):

    def setUp(self):
        super().setUp()
        self.commit_diff({"tests/test_alpha.py": ALPHA_TWO},
                         {"tests/test_alpha.py": ALPHA_VANISHED_AND_CHANGED})

    def assert_gate_silent(self):
        self.assertFalse(self.transition_refused(), self.journal())
        self.assertEqual([], self.refusals())
        self.assertEqual([], self.observations())
        self.assertEqual([], self.not_performed())

    def test_ac11_canary_task_gate_unchanged(self):
        """Канареечная задача: гейт молчит — ни отказа, ни записи наблюдения.

        В диффе и исчезнувший метод, и изменённое утверждение.

        Ловит мутацию: наблюдение поставлено до проверки `is_canary` —
        у канареечной задачи появится запись наблюдения.
        """
        self.set_task_fields(is_canary=1)
        self.assert_gate_silent()

    def test_ac11_external_target_gate_unchanged(self):
        """Задача внешнего target: гейт молчит — ни отказа, ни записи наблюдения.

        Ловит мутацию: наблюдение поставлено до проверки target — у задачи
        внешнего target появится запись наблюдения (дифф `config.ROOT` к
        её коду отношения не имеет).
        """
        self.set_task_fields(target="external-target")
        self.assert_gate_silent()


if __name__ == "__main__":
    unittest.main()
