"""AC-5: переход `in_dev -> review` не отказывает ветке, которая ВПЕРВЫЕ
создаёт `models.yaml`, — гейт защищённых путей читает список главной
копии на момент проверки.

Список главной копии на момент проверки изображается подменой
`config.PROTECTED_PATHS`: гейт исполняется кодом главной копии пульта, где
`models.yaml` ещё не в списке (в списке он появится тем же мержем, что
принесёт и сам файл). Обратный сценарий — тот же гейт с тем же диффом, но
со списком, УЖЕ несущим `models.yaml`, — обязан отказать: вместе они и
означают «читает список на момент проверки», а не зашитое исключение для
имени файла.

Зелёный с рождения: `_protected_paths_touched` уже читает
`config.PROTECTED_PATHS` в момент вызова, а сегодняшний список
`models.yaml` не несёт — оба теста фиксируют существующее поведение,
которое задача обязана не сломать, добавляя путь в список.
"""
import subprocess
import unittest
from unittest import mock

import _models
from orchestrator import config, fsm_advance, gitcmd
from tests.sandbox import TaskIdSchemaConnTmpRootTest

BRANCH = "task/t001-katalog-modeley"
# Дифф ветки задачи: сам каталог и модуль его разбора.
DIFF_FILES = [_models.CATALOG_NAME, "orchestrator/models.py"]
ZONES = f"{_models.CATALOG_NAME}, orchestrator/models.py"


def _git_log_not_a_repo(*args):
    """`gitcmd.git("log", ...)` внутри `_answer_commit_is_role_step_
    autocommit` — детерминированный отказ вместо обращения к диску."""
    return subprocess.CompletedProcess(list(args), 128, "",
                                       "fatal: not a git repository")


class ProtectedPathListIsReadAtCheckTimeTest(TaskIdSchemaConnTmpRootTest):

    def refuses(self, protected: tuple) -> bool:
        t = {"title": "Каталог моделей", "branch": BRANCH,
             "zones": ZONES, "zones_extension": None}
        with mock.patch.object(config, "PROTECTED_PATHS", protected), \
                mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
                mock.patch.object(gitcmd, "diff_names", return_value=DIFF_FILES), \
                mock.patch.object(gitcmd, "git", _git_log_not_a_repo):
            return fsm_advance._zones_gate_refuses(
                self.conn, self.task_id, t, BRANCH, "PLAN\n")

    def test_ac5_branch_creating_models_yaml_passes_the_gate(self):
        """Дифф создаёт `models.yaml`, а список защищённых путей главной
        копии его ещё не несёт — переход не отказывает.

        Ловит мутацию: список защищённых путей снят в константу на импорте
        модуля гейта (или гейт сверяется со списком ВЕТКИ, а не главной
        копии) — ветка, добавляющая путь в список вместе с самим файлом,
        отказывает сама себе и не может дойти до ревью.
        """
        without_catalog = tuple(p for p in config.PROTECTED_PATHS
                                if p != _models.CATALOG_NAME)

        self.assertFalse(self.refuses(without_catalog))

    def test_ac5_gate_refuses_once_the_main_copy_list_carries_models_yaml(self):
        """Тот же дифф при списке, УЖЕ несущем `models.yaml`, отказывает —
        значит список читается на момент проверки, а не обходится.

        Ловит мутацию: путь `models.yaml` внесён в исключения самого
        гейта (жёстко прошит «кроме каталога моделей») ради прохода этой
        задачи — защита каталога от правок ролью не заработала бы никогда.
        """
        with_catalog = tuple(config.PROTECTED_PATHS) + (_models.CATALOG_NAME,)

        self.assertTrue(self.refuses(with_catalog))


if __name__ == "__main__":
    unittest.main()
