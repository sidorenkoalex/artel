"""Приёмочный тест AC-1 (tasks/01M2CN3VV99BTAJF2JBTNADQPH/SPEC.md):
`commit_timeout_checkpoint`, `commit_abnormal_checkpoint` и
`commit_pause_now_checkpoint` сохраняют прежние сигнатуры и делегируют
общему приватному помощнику `_wip_checkpoint(conn, task_id, role,
message, action, discard_action, discard_detail, timeout)` (SPEC,
требование 1).

Красен до реализации: `orchestrator.checkpoint._wip_checkpoint` пока не
существует — рефакторинг R7 ещё не сделан, три публичные функции несут
построчно одинаковые тела напрямую, без общего помощника. `hasattr`
ниже упадёт первым.
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Сигнатуры трёх публичных функций и общего помощника — байт-в-байт то,
# что называет SPEC, требование 1 (порядок и имена параметров).
_PUBLIC_SIGNATURES = {
    "commit_timeout_checkpoint": ("conn", "task_id", "role"),
    "commit_abnormal_checkpoint": ("conn", "task_id", "role", "cause"),
    "commit_pause_now_checkpoint": ("conn", "task_id", "role"),
}
_HELPER_NAME = "_wip_checkpoint"
_HELPER_SIGNATURE = (
    "conn", "task_id", "role", "message", "action", "discard_action",
    "discard_detail", "timeout",
)


class WipCheckpointSharedHelperTest(unittest.TestCase):

    def test_ac1_public_signatures_unchanged(self):
        """Три публичные функции сохраняют прежний порядок и имена
        параметров, названные SPEC ещё до появления общего помощника.

        Ловит мутацию: при вынесении общего кода в `_wip_checkpoint`
        случайно меняется сигнатура одной из публичных функций
        (например, добавляется/переставляется параметр) — `inspect.
        signature` расходится с зафиксированным здесь порядком.
        """
        from orchestrator import checkpoint

        for name, expected_params in _PUBLIC_SIGNATURES.items():
            fn = getattr(checkpoint, name)
            actual_params = tuple(inspect.signature(fn).parameters.keys())
            self.assertEqual(
                actual_params, expected_params,
                f"сигнатура {name} изменилась: было {expected_params}, "
                f"стало {actual_params}")

    def test_ac1_shared_helper_exists_with_the_signature_named_by_spec(self):
        """Общий приватный помощник `_wip_checkpoint` существует и несёт
        ровно параметры `(conn, task_id, role, message, action,
        discard_action, discard_detail, timeout)` в этом порядке.

        Ловит мутацию: разработчик заводит помощник под другим именем
        или с другим набором/порядком параметров, не совпадающим с
        буквальной сигнатурой из требования 1 SPEC.
        """
        from orchestrator import checkpoint

        self.assertTrue(
            hasattr(checkpoint, _HELPER_NAME),
            f"orchestrator.checkpoint.{_HELPER_NAME} отсутствует")
        helper = getattr(checkpoint, _HELPER_NAME)
        actual_params = tuple(inspect.signature(helper).parameters.keys())
        self.assertEqual(actual_params, _HELPER_SIGNATURE)

    def test_ac1_all_three_public_functions_delegate_to_the_shared_helper(self):
        """Каждая из трёх публичных функций реально ВЫЗЫВАЕТ
        `_wip_checkpoint` в своём теле (а не заводит помощник рядом,
        оставляя старое тройное дублирование как было).

        Ловит мутацию: `_wip_checkpoint` заведён, но одна из трёх
        публичных функций (например, `commit_pause_now_checkpoint`)
        по-прежнему несёт прежнее самостоятельное тело построчного
        дублирования, не делегируя общему помощнику — `inspect.
        getsource` для неё не содержит вызова `_wip_checkpoint(`.
        """
        from orchestrator import checkpoint

        missing_delegation = []
        for name in _PUBLIC_SIGNATURES:
            fn = getattr(checkpoint, name)
            source = inspect.getsource(fn)
            if f"{_HELPER_NAME}(" not in source:
                missing_delegation.append(name)

        self.assertEqual(
            missing_delegation, [],
            "не делегируют общему помощнику: " + ", ".join(missing_delegation))


if __name__ == "__main__":
    unittest.main()
