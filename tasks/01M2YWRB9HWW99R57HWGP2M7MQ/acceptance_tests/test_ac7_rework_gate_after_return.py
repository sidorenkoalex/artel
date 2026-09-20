"""AC-7 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): после возврата AC-1 при
SPEC со `status: ready` в ветке задачи цикл `auto` запускает шаг analyst, а
не переводит задачу на `spec_gate`; после записи о завершённом шаге analyst
переход на `spec_gate` снова проходит.

Наблюдается через настоящий `auto.cmd_auto` — критерий говорит именно о
цикле, и различие видно только на нём: сам `advance` рубежом переделки не
держится (`_rework_gate_blocks` зовёт только `_cmd_auto`). Обе половины
критерия проверяются одним прогоном: цикл обязан сначала отработать шаг
analyst и лишь ПОТОМ увести задачу на `spec_gate` — порядок записей журнала
и есть наблюдаемое свойство.

Агент подменён (`runner.cmd_run` -> `_FakeAnalystStep`): настоящего шага
роли в песочнице нет и быть не может, а рубеж читает ровно одну его
запись — `agent run finished` под именем роли, тем же action/actor, каким
её пишет `runner._cmd_run` на успешном шаге. Подмена — надстройка сценария
поверх эталонной песочницы, а не своя копия её патчей.

Красен до реализации: reject на `spec_gate` ещё отказывает целиком
(`_cmd_reject`) — задача остаётся на `spec_gate`, цикл `auto` из ручного
гейта не делает ни шага, и шага analyst в журнале не появляется вовсе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import auto, config, runner, store  # noqa: E402

AGENT_FINISHED = "agent run finished"
SPEC_GATE_ACTION = _sandbox.STATE_ACTION_TMPL.format(state="spec_gate")
SPEC_WRITING_ACTION = _sandbox.STATE_ACTION_TMPL.format(state="spec_writing")


class _FakeAnalystStep:
    """Подмена `runner.cmd_run`: шага агента нет, есть его след в журнале.

    Собственный потолок вызовов — не дубль `config.AUTO_MAX_STEPS`, а
    способ его пришпилить: холостой шаг состояние не двигает, и цикл без
    рабочего лимита крутился бы не падая, а вися."""

    def __init__(self, limit: int):
        self.limit = limit
        self.states: list[str] = []

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        if len(self.states) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов больше {self.limit}")
        conn = store.db()
        t = store.get_task(conn, task_id)
        role = runner.step_role(t)
        self.states.append(t["state"])
        store.journal(conn, task_id, role, AGENT_FINISHED,
                      "rc=0, заглушка шага роли")


class ReworkGateAfterTheSpecGateReturnTest(_sandbox.SpecGateRejectSandbox):

    def setUp(self):
        super().setUp()
        # SPEC остался ready с прошлого захода — ровно та фактура, ради
        # которой рубеж и нужен: без него пред-advance увёл бы задачу
        # обратно на spec_gate по тому же самому тексту.
        self.write_spec(budget=self.spec_budget_value())
        self.write_tz()
        self.agent = _FakeAnalystStep(config.AUTO_MAX_STEPS)

    def run_auto(self) -> str:
        with mock.patch.object(runner, "cmd_run", self.agent):
            return self.capture(auto.cmd_auto, self.TASK)

    def actions(self) -> list[str]:
        return [action for _, action, _ in self.journal_rows()]

    def index_of_return(self) -> int:
        """Позиция записи возврата в журнале — ПОСЛЕДНЕЙ `state ->
        spec_writing`. Всё, что проверяет критерий, случается ПОСЛЕ неё;
        записи входа на гейт и шаги прошлой жизни задачи стоят раньше и
        в сравнение попадать не должны."""
        actions = self.actions()
        positions = [i for i, action in enumerate(actions)
                     if action == SPEC_WRITING_ACTION]
        self.assertTrue(
            positions,
            f"в журнале нет записи возврата; журнал: {self.journal_rows()!r}")
        return positions[-1]

    def first_after(self, start: int, action: str, actor: str | None = None):
        """Позиция первой записи `action` (и, если задан, `actor`) после
        `start`; `None` — такой записи нет."""
        for i, row in enumerate(self.journal_rows()):
            if i > start and row[1] == action and (actor is None
                                                   or row[0] == actor):
                return i
        return None

    def test_ac7_auto_runs_the_analyst_step_before_returning_to_the_gate(self):
        """Оператор отклонил SPEC на гейте и запустил `auto`. SPEC в ветке
        всё ещё `status: ready` — тот самый текст, который только что
        отклонили. Цикл обязан сначала отдать задачу analyst (шаг роли), и
        только записью о завершённом шаге открыть себе путь на `spec_gate`:
        в журнале `agent run finished` роли analyst стоит МЕЖДУ записью
        возврата и записью `state -> spec_gate`.

        Ловит мутацию: detail записи возврата вписан в
        `auto._ESCALATED_RETURN_DETAILS` (или иначе пропускается при
        поиске анкера) — запись перестаёт быть рубежом,
        `_role_step_since_state_entry` отдаёт `(True, ...)`, и первый же
        пред-advance уводит задачу на `spec_gate` по отклонённому SPEC, не
        запустив analyst ни разу.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)
        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-7 не проверена; "
            f"вывод команды: {out!r}")

        auto_out = self.run_auto()

        self.assertIn(
            "spec_writing", self.agent.states,
            f"цикл не запустил ни одного шага роли в spec_writing; "
            f"вывод auto: {auto_out!r}")
        returned = self.index_of_return()
        step = self.first_after(returned, AGENT_FINISHED, actor="analyst")
        gate = self.first_after(returned, SPEC_GATE_ACTION)
        self.assertIsNotNone(
            step,
            f"после возврата нет ни одной записи завершённого шага "
            f"analyst; журнал: {self.journal_rows()!r}")
        self.assertIsNotNone(
            gate,
            f"задача так и не дошла до spec_gate; вывод auto: {auto_out!r}")
        self.assertLess(
            step, gate,
            f"цикл увёл задачу на spec_gate раньше шага analyst — возврат "
            f"не состоялся по существу; журнал: {self.journal_rows()!r}")

    def test_ac7_after_the_analyst_step_the_gate_transition_passes(self):
        """Вторая половина критерия: рубеж держит ровно один шаг роли, не
        дольше — тем же прогоном задача доходит до `spec_gate`, и цикл
        встаёт на ручном гейте, как и положено.

        Ловит мутацию: взяв запись возврата анкером, рубеж ищет шаг
        analyst ДО неё, а не после (перепутан срез `rows[last_entry + 1:]`
        в `_role_step_since_state_entry`) — «шага после возврата не было»
        остаётся истиной навсегда, и цикл топчется в `spec_writing`,
        никогда не выпуская задачу на гейт.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)
        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-7 не проверена; "
            f"вывод команды: {out!r}")

        auto_out = self.run_auto()

        # Шаг роли обязан быть отработан — иначе «задача на spec_gate»
        # означало бы, что она туда и не уходила, и тест был бы зелен на
        # несостоявшемся возврате.
        self.assertTrue(
            self.agent.states,
            f"цикл не запустил ни одного шага роли; вывод auto: {auto_out!r}")
        self.assertEqual(self.state(), "spec_gate",
                         f"после отработанного шага analyst переход на "
                         f"spec_gate не прошёл; вывод auto: {auto_out!r}")


if __name__ == "__main__":
    unittest.main()
