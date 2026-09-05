"""AC-5 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): задача в `in_dev` с PLAN.md
`status: ready` (сценарий «планка сдана до возврата из эскалации по
бюджету») — предварительный `advance` переводит её в `review`, не
запуская шаг developer.

Инцидент, который называет «Контекст» SPEC (регрессия 05.09): именно
этот сценарий терял шаги ($1-6 за штуку) у зон части 3, тестов без
сети, стоимости по видам, канарейки — PLAN.md уже был `ready`, но `auto`
всё равно запускала разработчика, прежде чем заметить это `advance`'ом.

Красен до реализации: нынешний `orchestrator/auto.py::_cmd_auto` зовёт
`runner.cmd_run` (роль `developer`) ДО `fsm.cmd_advance` — даже если
PLAN.md уже `ready` с самого начала вызова, первый шаг цикла всё равно
запускает разработчика вхолостую, и только СЛЕДУЮЩИЙ (уже после
холостого запуска) `advance` замечает готовый PLAN.md и переводит
задачу в `review`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import RoleRecordingRun  # noqa: E402

from orchestrator import auto, config, runner  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402


class Ac5PlanReadyBeforeStepSkipsDeveloperTest(AutoCycleTest):

    def test_ac5_ready_plan_moves_to_review_without_running_developer(self):
        """Задача входит в `in_dev`, а PLAN.md уже `status: ready` с
        самого начала вызова `auto` (планка сдана до возврата из
        эскалации по бюджету, SPEC «Контекст») — предварительный
        `advance` переводит её в `review`, не запуская `developer`.

        Ловит мутацию: реализация, оставившая старый порядок «run,
        затем advance» — `recorder.roles` содержал бы `"developer"`,
        хотя PLAN.md был готов ещё до первого шага цикла.
        """
        self.write_plan("ready")
        self.set_state("in_dev")
        recorder = RoleRecordingRun()
        self.patch_object(runner, "cmd_run", recorder)
        # REVIEW.md никогда не появляется в этом сценарии — без порога
        # холостых шагов ниже дефолтного `AUTO_MAX_STEPS` цикл крутил бы
        # ревьювера все 30 раз, прежде чем встать; предмет теста — только
        # первый шаг (`in_dev`), а не то, сколько раз крутится `review`.
        self.patch_object(config, "AUTO_STALL_STEPS_LIMIT", 2)

        self.capture(auto.cmd_auto, self.TASK)

        self.assertNotIn(
            "developer", recorder.roles,
            "auto запустила шаг developer, хотя PLAN.md уже было ready")
        self.assertEqual(self.state(), "review",
                         "предварительный advance не перевёл задачу в review")


if __name__ == "__main__":
    unittest.main()
