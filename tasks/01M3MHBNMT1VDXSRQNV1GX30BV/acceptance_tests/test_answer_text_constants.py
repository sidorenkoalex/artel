"""AC-3, AC-5, AC-6 — текст ответа как ОДНА константа модуля с
именованными якорями, не ветвящаяся по состоянию, и происхождение
механизма, оставшееся в докстринге.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Текст содержит дословно все четыре якоря требования 6, и каждый
якорь адресуем тесту именованной константой модуля
`orchestrator/canary.py` (тест сверяет вхождение константы в текст,
своей копии литерала не держит).

AC-5. Записанный в `ANSWER-n.md` текст совпадает с константой модуля при
любом состоянии `escalated_from` (`spec_writing`, `tests_writing`,
`in_dev`, `review`): ни по роли, ни по состоянию текст не ветвится.

AC-6. Докстринг или комментарий `_pass_escalated_with_synthetic_answer`
называет SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 6 — а текст ответа
этого номера не несёт (то же вхождение, что AC-1, проверенное адресно).

Красен до реализации: сегодня текст ответа собран литералами прямо в теле
`_pass_escalated_with_synthetic_answer` — константы модуля, равной тексту,
нет вовсе (AC-5), констант-якорей нет ни одной (AC-3), а номер SPEC
механизма стоит в самом тексте, не в докстринге (AC-6).

Своей копии литерала якорей планка не держит сознательно: AC-3 требует
адресовать якорь ИМЕНЕМ константы модуля, поэтому якоря опознаются как
строковые константы модульного уровня, входящие в текст дословно
(`_synthetic_answer.anchor_constants`). Сверка с копией четырёх фраз
здесь означала бы, что тест держит второй экземпляр той же истины — ровно
то, что критерий запрещает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _synthetic_answer  # noqa: E402
from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

# Номер SPEC, которым механизм введён (AC-6 называет его дословно) —
# проверяется в докстринге функции и его ОТСУТСТВИЕ в тексте ответа.
ORIGIN_SPEC_ID = "01M1NEEWH5K1XPFRDGRMPYSBXJ"

# Число якорей требования 6 (AC-3): четыре утверждения требования 4.
ANCHOR_COUNT = 4


class AnswerTextConstantsTest(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, _synthetic_answer.TASK,
                          "Канареечная задача прогона", "escalated",
                          f"task/{_synthetic_answer.TASK.lower()}-kanareyka",
                          config.DEFAULT_TARGET, 25.0, is_canary=True)
        self.text = _synthetic_answer.answer_text(self.conn,
                                                  _synthetic_answer.TASK)

    def test_ac3_four_named_module_constants_are_verbatim_anchors_of_text(self):
        """Текст ответа несёт дословно не меньше четырёх якорей, и каждый
        якорь — именованная строковая константа модуля `canary`, а не
        литерал внутри текста: тест адресует утверждение константой.

        Считаются якоря-утверждения, а не их обрамления: константа, внутри
        которой лежит другой якорь, отдельным утверждением не идёт (иначе
        «четыре якоря» выродились бы в одну фразу и её обёртки).

        Ловит мутацию: четыре утверждения вписаны в текст литералами (или
        собраны в один общий литерал) без именованных констант — в
        пространстве имён модуля `canary` не находится четырёх строковых
        констант, входящих в текст, и тест краснеет; ровно этой мутацией
        тест на текст лишился бы адресуемых якорей и сверял бы свою копию
        фраз.
        """
        anchors = _synthetic_answer.anchor_constants(self.text)
        atomic = _synthetic_answer.atomic_anchors(anchors)
        self.assertGreaterEqual(
            len(atomic), ANCHOR_COUNT,
            f"констант-якорей модуля в тексте меньше {ANCHOR_COUNT}: "
            f"{sorted(atomic)} (все вхождения: {sorted(anchors)})\n"
            f"--- текст ---\n{self.text}")

    def test_ac5_text_is_one_module_constant_for_every_escalated_from(self):
        """Текст ответа один и тот же при возврате из любого состояния
        (`spec_writing`, `tests_writing`, `in_dev`, `review`) и совпадает
        со значением константы модуля — по роли и по состоянию он не
        ветвится.

        Ловит мутацию: в текст добавили ветку по `escalated_from` (или по
        роли состояния — `config.STATE_ROLE`), например отдельную фразу
        автору тестов, — перехваченные тексты четырёх состояний
        разойдутся, и тест краснеет; он же краснеет, если текст собран
        на месте и константы модуля с таким значением нет.
        """
        texts = {state: _synthetic_answer.answer_text(
            self.conn, _synthetic_answer.TASK, escalated_from=state)
            for state in _synthetic_answer.ESCALATED_FROM_STATES}
        self.assertEqual(1, len(set(texts.values())),
                         f"текст ответа ветвится по состоянию: {texts}")
        text = next(iter(texts.values()))
        self.assertTrue(text.strip(), "текст ответа пуст")
        names = _synthetic_answer.constants_equal_to(text)
        self.assertTrue(names,
                        f"ни одна строковая константа модуля canary не равна "
                        f"тексту ответа:\n{text}")

    def test_ac6_origin_spec_stays_in_docstring_and_not_in_answer_text(self):
        """Происхождение механизма (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,
        требование 6) названо в докстринге или комментарии
        `_pass_escalated_with_synthetic_answer`, а текст, который читает
        роль, этого номера не несёт.

        Комментарии и докстринг берутся без строковых литералов тела —
        иначе номер, оставшийся в самом тексте ответа, читался бы как
        «номер в докстринге» и критерий проверялся бы сам собой.

        Ловит мутацию: номер SPEC вычистили из кода вместе с текстом
        (происхождение механизма потеряно для читателя `canary.py`) —
        падает первая половина; номер оставили в тексте ответа, а в
        докстринг не перенесли — падает вторая.
        """
        docs = _synthetic_answer.docs_and_comments(
            canary._pass_escalated_with_synthetic_answer)
        self.assertIn(ORIGIN_SPEC_ID, docs,
                      "докстринг/комментарии функции не называют SPEC, "
                      "которым введён механизм")
        self.assertIn("требование 6", docs,
                      "докстринг/комментарии функции не называют требование "
                      "введшего механизм SPEC")
        self.assertNotIn(ORIGIN_SPEC_ID, self.text,
                         f"номер чужой задачи остался в тексте ответа:\n"
                         f"{self.text}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
