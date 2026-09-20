"""AC-6 (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF): отказ гейта применимости
относится к классу «роль ещё не закончила» — `auto._pre_advance_step` не
останавливает цикл для Оператора, а запускает шаг developer заново; отказ
доезжает до истории отказов брифа; тот же отказ ПОСЛЕ шага developer
останавливает `auto` (один гарантированный шаг).

Красен до реализации: `orchestrator/auto.py::_pre_advance_step` про новое действие ничего не знает — сегодня оно попадает в `other_class_refusal` (класс «нужны руки Оператора»), поэтому первый вызов возвращает `Refused`, а второй — `Stop`, и шага developer не будет ни одного (класс инцидента 13.09); тем же остаётся красным и тест «повтор ПОСЛЕ шага developer останавливает auto» — `Stop` приходит раньше, уже на первом вызове. Тест про историю отказов брифа зелёный с рождения: `orchestrator/brief.py` собирает блок по префиксу действия и правки не требует (SPEC, «Не входит»), а красным он станет, если новое действие внесут в его перечень вычитаемых.

Действие отказа здесь — литерал из формулировки AC-5: `fsm.cmd_advance`
подменён журналирующей заглушкой (тот же приём, что `tests/
test_auto_cycle.py::FakeAdvance`), потому что предмет AC-6 — РАЗБОР
исхода в `auto.py`, а не сам гейт; гейт целиком проверяет
`test_ac5_ac7_in_dev_applicability_gate.py` на настоящем git.

Провалидировано стабом (решение Оператора 03.09): подмена литерала, по
которому `_pre_advance_step` узнаёт мягкий класс отказа гейта зон (тот
самый «образец» требования 2), на новое действие зеленит все три теста
файла; стаб удалён, репозиторий не тронут.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _parse  # noqa: E402
import _sandbox  # noqa: E402

from orchestrator import auto, brief, catalog, config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

# Detail отказа — то же, что журналирует гейт: путь приложения и ответ
# git (AC-5), их роль и читает в брифе.
REFUSAL_DETAIL = (f"приложение PLAN {_parse.PROTECTED_FILE} не применяется "
                  f"к базе сравнения deadbeef: error: patch failed: "
                  f"{_parse.PROTECTED_FILE}:1")


class JournalingAdvance:
    """Подмена `fsm.cmd_advance`: журналирует отказ гейта применимости под
    actor `fsm` и возвращает `False` — состояние не двигает, ровно как
    настоящий отказ гейта на выходе `in_dev`."""

    def __init__(self, action: str, detail: str):
        self.action = action
        self.detail = detail
        self.calls = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        store.journal(store.db(), task_id, "fsm", self.action, self.detail)
        return False


class PreAdvanceAppendixRefusalTest(TmpRootTest):

    TASK = "01APPENDIXREFUSALCLASS0001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Приложения PLAN",
                          "in_dev", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        # Граница визита состояния: по ней `store.refusal_history` и
        # `auto._role_step_between_repeated_refusals` отсчитывают «этот
        # заход роли в in_dev».
        store.journal(self.conn, self.TASK, "fsm", "state -> in_dev",
                      "гейт SPEC пройден — приёмочные тесты до кода")
        self.advance = JournalingAdvance(
            _sandbox.INAPPLICABLE_REFUSAL_ACTION, REFUSAL_DETAIL)
        patcher = mock.patch.object(fsm, "cmd_advance", self.advance)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cycle = auto._CycleState()

    def pre_advance(self):
        return auto._pre_advance_step(self.conn, self.TASK, "sid",
                                      "developer", "in_dev", "in_dev",
                                      self.cycle)

    def journal_developer_step(self) -> None:
        """Запись завершённого шага роли — тем же actor/action, что
        настоящий `orchestrator/runner.py::_cmd_run` при `rc=0`."""
        store.journal(self.conn, self.TASK, "developer", "agent run finished",
                      "rc=0, тестовая заглушка шага")

    def test_ac6_refusal_does_not_stop_auto_and_lets_developer_run(self):
        """Два подряд вызова `_pre_advance_step` с одним и тем же отказом
        гейта применимости, без завершённого шага роли между ними, оба
        возвращают `None` — цикл на обеих итерациях запускает шаг
        developer, а не останавливается решением Оператора.

        Ловит мутацию: новое действие не отнесено к классу «роль ещё не
        закончила» (не исключено из `other_class_refusal`) — первый
        вызов вернул бы `Refused`, второй `Stop`, и роль не получила бы
        ни одного шага на починку приложения: ровно тот тупик, из
        которого задача 01M2XJKKPH не вышла 20.09.
        """
        self.cycle.prev_refusal = _sandbox.INAPPLICABLE_REFUSAL_ACTION

        first = self.pre_advance()
        second = self.pre_advance()

        self.assertEqual(self.advance.calls, 2)
        self.assertIsNone(
            first, f"первый отказ увёл цикл мимо шага developer: {first!r}")
        self.assertIsNone(
            second, f"повтор отказа без шага роли между ними остановил "
                    f"цикл: {second!r}")

    def test_ac6_refusal_reaches_the_brief_refusal_history(self):
        """Блок «история отказов advance», который `orchestrator/brief.py`
        кладёт в бриф шага developer, несёт новое действие и detail с
        путём приложения.

        Ловит мутацию: новое действие внесено заодно и в перечень
        `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` (копия перечня
        `auto.py`) — блок отфильтруется в пустую строку, и роль
        запустится вслепую, не узнав, какое приложение неприменимо.
        """
        self.pre_advance()

        text = brief.advance_refusal_history(self.conn, self.TASK,
                                             "developer", "in_dev")

        self.assertTrue(text, "история отказов advance пуста — бриф шага "
                              "developer не получит причину отказа")
        self.assertIn(_sandbox.INAPPLICABLE_REFUSAL_ACTION, text)
        self.assertIn(_parse.PROTECTED_FILE, text,
                      f"путь приложения не доехал до брифа: {text!r}")

    def test_ac6_repeat_after_a_developer_step_stops_auto(self):
        """Тот же отказ, повторившийся ПОСЛЕ завершённого шага developer,
        останавливает цикл: роль свой гарантированный шаг уже получила.

        Ловит мутацию: новое действие отнесено к классу «роль ещё не
        закончила» безусловно, без журнальной защиты от кружения — цикл
        жёг бы шаги developer до `AUTO_MAX_STEPS` на приложении, которое
        роль починить не может.
        """
        first = self.pre_advance()
        self.journal_developer_step()

        second = self.pre_advance()

        self.assertIsNone(first, f"первый отказ обязан дать роли шаг: {first!r}")
        self.assertIsInstance(second, auto.Stop)
        self.assertIn(_sandbox.INAPPLICABLE_REFUSAL_ACTION, second.reason)
        self.assertEqual(second.state, "in_dev")


if __name__ == "__main__":
    unittest.main()
