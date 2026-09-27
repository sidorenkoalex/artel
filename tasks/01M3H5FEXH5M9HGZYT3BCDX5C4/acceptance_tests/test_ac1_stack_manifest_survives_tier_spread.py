"""AC-1: прогон `tests/test_stack_optional_tools.py` на карте
исполнителей, где одна agent-роль, не названная этим тестом, стоит на
ярусе перечня `orchestrator/models.py::TIERS`, отличном от яруса
остальных agent-ролей.

Карта исполнителей подаётся КОПИЕЙ дерева кода во временном каталоге
(`_util.repo_copy`), а не правкой `roles.yaml` репозитория: и
`tests/sandbox.py`, и `tests/test_runner_role_model.py::_roles_yaml_text`
читают карту путём, вычисленным от `__file__` собственного модуля, —
подменить её иначе, чем подменив само дерево, нечем. Сам прогон —
подпроцессом pytest с `cwd` в копии.

Красен до реализации: песочница `_ManifestSandbox.use_tier` пишет
локальный слой с моделью ТОЛЬКО у яруса теста, поэтому цепочка «роль ->
ярус -> модель» роли на другом ярусе не разрешается, `check_stack()`
даёт строку `model-<роль>` со статусом `fail`, и
`CheckStackLinesTest::test_missing_unused_tool_gives_no_line_at_all`
краснеет — ровно тот отказ, которым 27.09 покраснела главная ветка.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import models  # noqa: E402


class StackManifestTierSpreadTest(unittest.TestCase):
    """Прогон файла манифеста стека на карте с разведёнными ярусами."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def test_ac1_stack_optional_tools_is_green_with_a_role_on_another_tier(self):
        """Карта исполнителей: одна agent-роль, которую
        `tests/test_stack_optional_tools.py` не называет, переведена на
        второй ярус `models.TIERS`, остальные agent-роли — на первом.
        На такой карте весь файл обязан пройти без единого провала и
        единой ошибки.

        Ловит мутацию: покрытие ярусов написано в одном месте песочницы
        (например, в `tests/sandbox.py`), а собственный локальный слой
        `_ManifestSandbox.use_tier` остался однострочным `tiers:` с
        моделью у одного яруса — состав строк `check_stack()` снова
        зависит от того, на каких ярусах стоят роли, которых тест не
        называет, и `doctor` краснеет от решения Оператора в
        `roles.yaml`, а не от состояния стека.
        """
        text, role, other_tier, base_tier = _util.spread_roles_text(
            [_util.STACK_TEST])

        tiers = _util.agent_roles(text)
        self.assertNotEqual(other_tier, base_tier)
        self.assertIn(other_tier, models.TIERS)
        self.assertIn(base_tier, models.TIERS)
        self.assertEqual(tiers.get(role), other_tier, tiers)
        self.assertEqual({t for name, t in tiers.items() if name != role},
                         {base_tier}, tiers)
        self.assertNotIn(role, (_util.REPO_ROOT / _util.STACK_TEST).read_text(
            encoding="utf-8"))

        code = _util.repo_copy(self.tdir, text)
        result = _util.run_pytest(code, [_util.STACK_TEST], timeout=90)

        self.assertEqual(_util.failed_nodeids(result.stdout), [],
                         _util.run_report(result))
        self.assertEqual(result.returncode, 0, _util.run_report(result))


if __name__ == "__main__":
    unittest.main()