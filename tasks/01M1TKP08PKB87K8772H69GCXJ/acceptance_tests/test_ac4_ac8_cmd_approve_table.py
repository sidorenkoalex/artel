"""AC-4 / AC-8 задачи 01M1TKP08PKB87K8772H69GCXJ.

AC-4: `orchestrator.fsm._cmd_approve` использует словарь «состояние ->
обработчик» вместо цепочки `if state == ...`; обработчики для
`spec_gate`/`acceptance`/`merge_gate`/`escalated` — существующие
функции переходов. AC-8: новый юнит-тест проверяет, что каждое из этих
четырёх состояний ведёт к ожидаемому обработчику, а состояние вне
таблицы — к прежнему тексту отказа.

Красен до реализации (AC-4, структурная проверка): сегодняшний
`_cmd_approve` — цепочка `if state == ...: ... elif ...`, не словарь;
`test_ac4_*` обязан упасть на сегодняшнем коде. `test_ac8_*` — зелёные
с рождения: каждое состояние сегодня УЖЕ ведёт к правильному переходу
(цепочкой `if`/`elif`, не словарём) — задача меняет ТОЛЬКО форму
диспетчеризации (требование 3), не какое состояние куда ведёт, поэтому
поведенческая часть AC-8 не имеет права покраснеть от рефакторинга.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ApproveTableSandbox  # noqa: E402
from orchestrator import config, fsm, fsm_merge_gate  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
FSM_PY = REPO_ROOT / "orchestrator" / "fsm.py"

APPROVE_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")

SPEC_SKIP_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
skip_tests: "фикстура таблицы approve — тесты не нужны этому сценарию"
---

# SPEC: фикстура approve

## Критерии приёмки

AC-1. Фикстура.
"""


def _find_cmd_approve(tree: ast.Module) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_cmd_approve":
            return node
    raise AssertionError("_cmd_approve не найден в orchestrator/fsm.py")


class Ac4DispatchTableStructureTest(unittest.TestCase):

    def test_ac4_cmd_approve_uses_a_state_to_handler_dict_not_if_elif_chain(self):
        """`_cmd_approve` обязан нести словарь (`ast.Dict`), чьи ключи —
        строковые литералы `spec_gate`/`acceptance`/`merge_gate`/
        `escalated`, и НЕ обязан больше сравнивать `state` с этими же
        строками через `==` (старая цепочка `if state == "spec_gate":
        ... elif state == "acceptance": ...` несла ровно четыре таких
        сравнения).

        Ловит мутацию: разработчик оставляет прежнюю цепочку `if/elif`
        нетронутой (переименовав обработчики в отдельные функции без
        самой таблицы-словаря) — `assertTrue` по наличию `ast.Dict` с
        нужными ключами и `assertLess` по числу явных сравнений `state
        == "..."` это поймают.
        """
        source = FSM_PY.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(FSM_PY))
        func = _find_cmd_approve(tree)

        dict_with_states = None
        for node in ast.walk(func):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value for k in node.keys
                   if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if keys >= set(APPROVE_STATES):
                dict_with_states = node
                break
        self.assertIsNotNone(
            dict_with_states,
            "_cmd_approve не несёт словарь с ключами "
            f"{APPROVE_STATES} — таблица «состояние -> обработчик» "
            "(SPEC требование 3) не заведена")

        explicit_state_compares = 0
        for node in ast.walk(func):
            if not isinstance(node, ast.Compare):
                continue
            if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
                continue
            left, right = node.left, node.comparators[0]
            names = [n for n in (left, right) if isinstance(n, ast.Name)
                    and n.id == "state"]
            consts = [n for n in (left, right)
                     if isinstance(n, ast.Constant) and n.value in APPROVE_STATES]
            if names and consts:
                explicit_state_compares += 1
        self.assertLess(
            explicit_state_compares, len(APPROVE_STATES),
            f"_cmd_approve всё ещё сравнивает state == \"...\" "
            f"{explicit_state_compares} раз(а) — цепочка if/elif на месте "
            f"старой прежней формы, таблица её не заменила")


class Ac8DispatchBehaviorTest(ApproveTableSandbox):

    def test_ac8_spec_gate_state_routes_to_spec_gate_handler(self):
        """Approve из `spec_gate` со SPEC, помеченным `skip_tests`, обязан
        перевести задачу в `in_dev` — тот же обработчик, что и до
        введения таблицы.

        Ловит мутацию: таблица роняет/меняет местами ключ `spec_gate` —
        состояние осталось бы `spec_gate` вместо `in_dev`.
        """
        self.insert("spec_gate")
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_SKIP_TESTS.format(task=self.TASK), encoding="utf-8")
        with mock.patch.object(fsm.artifact_source, "resolve",
                               return_value=(self.BRANCH, False)):
            self.approve("f" * 40)

        self.assertEqual(self.state(), "in_dev")
        self.ensure_draft_mr.assert_called_once()

    def test_ac8_acceptance_state_routes_to_acceptance_handler(self):
        """Approve из `acceptance` (подтяжка замокана `"fresh"`) обязан
        перевести задачу в `merge_gate` — тот же обработчик, что и до
        введения таблицы.

        Ловит мутацию: таблица роняет/меняет местами ключ `acceptance` —
        состояние осталось бы `acceptance`.
        """
        self.insert("acceptance")
        with mock.patch.object(fsm, "_pull_main_or_escalate",
                               return_value="fresh"), \
             mock.patch.object(fsm, "_snapshot_split_assessment"), \
             mock.patch.object(fsm.github_adapter, "undraft_mr"), \
             mock.patch.object(fsm.fixation, "approve_sha_hint",
                               return_value=""):
            self.approve("f" * 40)

        self.assertEqual(self.state(), "merge_gate")

    def test_ac8_merge_gate_state_routes_to_merge_gate_handler(self):
        """Approve из `merge_gate` обязан вызвать РОВНО
        `fsm_merge_gate._cmd_approve_merge_gate_cycle` с этой задачей и
        этим состоянием — тот же обработчик, что и до введения таблицы.

        Ловит мутацию: таблица роняет/меняет местами ключ `merge_gate` —
        цикл `merge_gate` не будет вызван вовсе.
        """
        self.insert("merge_gate")
        with mock.patch.object(
                fsm_merge_gate, "_cmd_approve_merge_gate_cycle") as cycle:
            self.approve("f" * 40)

        cycle.assert_called_once()
        args = cycle.call_args[0]
        self.assertEqual(args[1], self.TASK)
        self.assertEqual(args[2], "sid")
        self.assertEqual(args[4], "merge_gate")

    def test_ac8_escalated_state_routes_to_escalated_handler(self):
        """Approve из `escalated` без `escalated_from`/`answer_baseline`
        обязан вернуть задачу в `in_dev` — тот же обработчик, что и до
        введения таблицы (см. `tests/test_fsm_draft_mr_reentry.py`,
        сценарий без `escalated_from`).

        Ловит мутацию: таблица роняет/меняет местами ключ `escalated` —
        состояние осталось бы `escalated`.
        """
        self.insert("escalated", escalated_from=None, answer_baseline=None)

        self.approve("f" * 40)

        self.assertEqual(self.state(), "in_dev")
        self.ensure_draft_mr.assert_called_once()

    def test_ac8_state_outside_table_keeps_the_previous_refusal_text(self):
        """Состояние вне таблицы (например, `review`) обязано печатать
        прежний текст «в состоянии X нечего подтверждать», не менять
        состояние задачи.

        Ловит мутацию: ветка «иначе» после введения таблицы теряется
        (например, `KeyError` на нехватке ключа) или меняет
        формулировку отказа.
        """
        self.insert("review")

        out = self.approve()

        self.assertEqual(out.strip(), f"[{self.TASK}] в состоянии review "
                         f"нечего подтверждать")
        self.assertEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
