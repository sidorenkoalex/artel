"""AC-4 — гейт зон на `in_dev → review` отказывает переходу на новых
защищённых путях тем же именованным текстом, что и на `gates.yaml`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Гейт зон на `in_dev → review` отказывает переходу, когда дифф ветки
трогает `conftest.py`, `pyproject.toml` или `tests/sub/conftest.py`, —
тем же именованным текстом отказа «защищённый путь …», что и для
`gates.yaml`.

«Тот же текст» проверяется СРАВНЕНИЕМ с отказом на `gates.yaml`, снятым в
том же прогоне, а не литералом сегодняшней формулировки: формулировку
отказа Оператор правит отдельными задачами (она уже общая у гейта зон и
гейта мержа), и планка не вправе её замораживать.

Дифф ветки подменяется на уровне `gitcmd.diff_base`/`gitcmd.diff_names` —
тот же приём, которым сверяет этот гейт `tests/test_protected_paths_gate.
py::ZonesGateProtectedPathPriorityTest`; заявленная зона задачи-фикстуры
(`orchestrator/store.py`) нарочно НЕ покрывает проверяемые пути, чтобы
отказ шёл именно по защищённости, а не по «вне зон».

Красен до реализации: гейт зон сверяет дифф собственной префиксной формулой `_touches_zone`, записи-маски ещё нет в перечне — на `conftest.py` и `tests/sub/conftest.py` гейт отказывает обычным «вне заявленных zones», а не «защищённый путь».
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from orchestrator import gitcmd  # noqa: E402
from orchestrator.advance_gates import zones  # noqa: E402
from tests.sandbox import TaskIdSchemaConnTmpRootTest  # noqa: E402

BRANCH = "task/plank-ac4"
#: Заявленная зона фикстуры — заведомо не совпадает ни с одним из
#: проверяемых путей: иначе отказ был бы неотличим от «вне зон».
FIXTURE_ZONE = "orchestrator/store.py"


class ZonesGateNewProtectedPathsTest(TaskIdSchemaConnTmpRootTest):

    def _task_row(self) -> dict:
        return {"title": "Планка AC-4", "branch": BRANCH,
                "zones": FIXTURE_ZONE, "zones_extension": None}

    def _refusal(self, path: str):
        """`GateRefusal | None` гейта зон на диффе из одного файла `path`."""
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=[path]):
            return zones._zones_gate(self.conn, self.task_id,
                                     self._task_row(), BRANCH, "# PLAN\n")

    def _refuses(self, path: str) -> bool:
        """Тот же гейт через публичную обёртку `_zones_gate_refuses` —
        она и журналирует отказ, то есть переход действительно не идёт."""
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=[path]):
            return zones._zones_gate_refuses(self.conn, self.task_id,
                                             self._task_row(), BRANCH,
                                             "# PLAN\n")

    def test_ac4_new_protected_paths_refuse_with_the_gates_yaml_text(self):
        """Дифф ветки из одного нового защищённого пути (`conftest.py`,
        `pyproject.toml`, `tests/sub/conftest.py`) отклоняет переход, и
        действие с деталью отказа совпадают с теми, что тот же гейт даёт
        на `gates.yaml`, — с точностью до имени пути в тексте.

        Ловит мутацию: гейт зон продолжает сверять дифф собственной
        префиксной формулой вместо общего помощника. Наблюдаемое
        расхождение: на `tests/sub/conftest.py` гейт возвращает отказ с
        действием «переход отклонён: гейт зон» и деталью «дифф трогает
        файлы вне заявленных zones» вместо «переход отклонён: защищённый
        путь» — то есть роль чинит дифф расширением зон и спокойно уезжает
        на `review` с подменённым окружением pytest.
        """
        reference = self._refusal("gates.yaml")
        self.assertIsNotNone(
            reference,
            "опорный отказ на gates.yaml не получен — фикстура гейта "
            "сломана, сравнивать текст не с чем")

        for path in _protected.GATE_PATHS:
            with self.subTest(path=path):
                refusal = self._refusal(path)
                self.assertIsNotNone(
                    refusal,
                    f"гейт зон пропустил дифф с защищённым путём {path}")
                self.assertEqual(refusal.action, reference.action)
                self.assertEqual(
                    refusal.detail,
                    reference.detail.replace("gates.yaml", path),
                    f"текст отказа на {path} разошёлся с текстом отказа на "
                    f"gates.yaml")
                self.assertTrue(
                    self._refuses(path),
                    f"публичная обёртка гейта не отклонила переход на "
                    f"{path}")


if __name__ == "__main__":
    unittest.main()
