"""AC-2/AC-3 (tasks/01M27JPEGCGMDDRX5A98QWJW0Z/SPEC.md): гейт зон
`in_dev -> verifying` (`fsm_advance._zones_gate`) отказывает переход,
если дифф ветки задачи трогает путь из `config.PROTECTED_PATHS`, — даже
когда этот путь заявлен в `zones`/`zones_extension` (AC-2) или покрыт
разделом «## Расширение зон» PLAN.md вместе с мандатом Оператора
«Расширение зон разрешено:» на тот же путь в ANSWER-n.md (AC-3,
обычное исключение AC-3 `zones`-гейта, tasks/01M1P9QCHPHSCEA6TK13PV85SP).

Песочница — `TmpRootTest` (без настоящего git), тем же приёмом, что
`tests/test_zones_gate.py::ZonesGateGitFailureTest`: `gitcmd.diff_base`/
`gitcmd.diff_names`/`gitcmd.ls_tree_files`/`gitcmd.show` подменены
напрямую, `_zones_gate_refuses` зовётся как публичная обёртка гейта.

Красен до реализации: `fsm_advance._zones_gate` сегодня не знает про
`config.PROTECTED_PATHS` вовсе — путь, заявленный в `zones` (AC-2) или
покрытый исключением «Расширение зон» (AC-3), проходит гейт молча
(`return None`), и оба теста здесь красны на `assertTrue(refuses)`,
получая `False`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _fake_git_log_not_a_repo(*args):
    """`gitcmd.git("log", ...)` внутри `_answer_commit_is_role_step_
    autocommit` — детерминированный отказ (не настоящий subprocess),
    чтобы функция вернула `False` («не автокоммит роли») без обращения
    к диску."""
    return subprocess.CompletedProcess(list(args), 128, "",
                                       "fatal: not a git repository")


class ZonesGateProtectedPathTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"

    def test_ac2_protected_path_refuses_even_when_declared_in_zones(self):
        """Дифф трогает `gates.yaml` (защищённый путь), который прямо
        ЗАЯВЛЕН в `zones` задачи, — переход всё равно обязан отказать.

        Ловит мутацию: проверка защищённых путей применена только к
        файлам ВНЕ `zones` (`out_of_zone`) — `gates.yaml`, заявленный в
        zones, молча проходит гейт, хотя ровно это и есть сценарий
        факта 11.09 из «Контекста» SPEC (защищённый путь, попавший в
        зоны задачи).
        """
        t = {"title": "Тест", "branch": "task/t001-x",
             "zones": "gates.yaml", "zones_extension": None}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["gates.yaml"]):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, "task/t001-x", "PLAN\n")
        self.assertTrue(refuses)

    def test_ac3_protected_path_refuses_despite_zones_extension_and_operator_mandate(self):
        """Дифф трогает `gates.yaml`; `zones` задачи его не покрывает,
        но PLAN.md несёт раздел «## Расширение зон» со строкой «Пути:
        gates.yaml», а ANSWER-1.md ветки — мандат Оператора «Расширение
        зон разрешено: gates.yaml» на тот же путь. Обычное исключение
        AC-3 `zones`-гейта здесь НЕ применяется: мандат на расширение
        зон защищённые пути не покрывает.

        Ловит мутацию: защищённый путь не исключён из действия
        исключения «Расширение зон» — при наличии и раздела PLAN.md, и
        подтверждающего мандата ANSWER-n.md переход по-прежнему
        проходит (`return None` из ветки исключения), хотя SPEC требует
        отказа именно в этом случае — ровно инцидент 11.09
        (`docs/invariants.md`), ради которого заведена задача.
        """
        t = {"title": "Тест", "branch": "task/t001-x",
             "zones": "orchestrator/store.py", "zones_extension": None}
        plan_text = ("## Расширение зон\n\nПути: gates.yaml\n\n"
                    "Обоснование расширения зон.\n")
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["gates.yaml"]), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=[f"tasks/{self.task_id}/ANSWER-1.md"]), \
             mock.patch.object(gitcmd, "show",
                               return_value=("Расширение зон разрешено: gates.yaml\n", "")), \
             mock.patch.object(gitcmd, "git", _fake_git_log_not_a_repo):
            refuses = fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, "task/t001-x", plan_text)
        self.assertTrue(refuses)


if __name__ == "__main__":
    unittest.main()
