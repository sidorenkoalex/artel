"""AC-3 (tasks/01M1SD5RHTJ0H0SR0615SVCJM5/SPEC.md): сигнатура точки входа
`_cmd_approve_merge_gate_cycle(conn, task_id, sid, t, state)`, которую
вызывает `orchestrator/fsm.py:861` (вне зон задачи, не редактируется), не
меняется.

Зелёный с рождения: тест воспроизводит уже существующую сигнатуру —
рефакторинг обязан её СОХРАНИТЬ (AC-3, AC-4 требований), не создать
заново, поэтому тест зелёный уже сегодня и обязан остаться зелёным после
разбора тела на шаги.
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm_merge_gate  # noqa: E402


class CycleEntrypointSignatureTest(unittest.TestCase):

    def test_ac3_positional_parameter_names_and_order_unchanged(self):
        """Параметры `_cmd_approve_merge_gate_cycle` — ровно `(conn,
        task_id, sid, t, state)` в этом порядке, все обязательные.

        Ловит мутацию: декомпозиция на шаги попутно переставляет или
        переименовывает параметр (например `state` -> `expected_state`,
        или добавляет новый обязательный параметр вроде выделенного
        объекта-мьютекса) — вызов `orchestrator/fsm.py:861`, который эта
        задача не имеет права редактировать, перестал бы совпадать по
        сигнатуре; `assertEqual` на списке имён здесь это поймает раньше,
        чем сломался бы реальный вызов из fsm.py.
        """
        sig = inspect.signature(fsm_merge_gate._cmd_approve_merge_gate_cycle)
        names = [p.name for p in sig.parameters.values()]

        self.assertEqual(names, ["conn", "task_id", "sid", "t", "state"])

    def test_ac3_no_parameter_gained_a_default(self):
        """Ни один из пяти параметров не получил значение по умолчанию —
        точка входа остаётся вызываемой ровно так же позиционно, как
        сегодня зовёт её `fsm.py`.

        Ловит мутацию: разработчик добавляет новый шаговый параметр со
        значением по умолчанию «для гибкости» (например
        `confirmed_ci_note=None` на уровне цикла, а не только тела) —
        `assertEqual(p.default, inspect.Parameter.empty)` покраснеет на
        нём.
        """
        sig = inspect.signature(fsm_merge_gate._cmd_approve_merge_gate_cycle)

        for p in sig.parameters.values():
            self.assertEqual(
                p.default, inspect.Parameter.empty,
                f"параметр {p.name} обзавёлся значением по умолчанию")


if __name__ == "__main__":
    unittest.main()
