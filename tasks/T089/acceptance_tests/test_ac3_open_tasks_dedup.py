"""AC-3 (tasks/T089/SPEC.md): в `tasks/*/acceptance_tests/` задач, НЕ
закрытых на момент правки, те же дубли сведены к импорту из
`tests/sandbox.py` тем же приёмом.

«Не закрыта» проверяется по локальной git-ветке `task/t<id>-...`:
закрытие задачи (`merge_gate -> done`) удаляет именно её,
`orchestrator/cleanup.py::drop_merged_task_branch` (`git branch -d`) — та
же локальная ветка, что видна в этом же git-дереве вне зависимости от
того, из чьего рабочего каталога гонится тест (все воркт-деревья задачи
делят один `.git`).

Зелёный с рождения: на момент написания этого теста ни у одной ОТКРЫТОЙ
задачи (ветка жива — T085–T090 на момент написания, включая саму T089)
`acceptance_tests/` не содержит копий перечисленных хелперов — все
найденные копии (grep) лежат в `tasks/*/acceptance_tests/` ЗАКРЫТЫХ задач
(T028 и далее — известный остаток, AC-4) и потому этим тестом не
затрагиваются; правка T089 не обязана трогать открытые задачи, которых
дубль не касается, и красноты здесь по этой причине нет — критерий уже
выполняется тем, что копий в открытых задачах никогда не было.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _repo_scan import (acceptance_test_dirs, open_task_ids, repo_root,  # noqa: E402
                        scan_definitions, task_id_of)


class OpenTaskAcceptanceTestsDedupTest(unittest.TestCase):

    def test_ac3_open_task_acceptance_tests_have_no_duplicate_definitions(self):
        root = repo_root()
        open_ids = open_task_ids(root)

        stray = []
        for d in acceptance_test_dirs(root):
            tid = task_id_of(d)
            if tid not in open_ids:
                continue
            for path, name in scan_definitions(sorted(d.glob("*.py"))):
                stray.append((str(path.relative_to(root)), name))

        self.assertEqual(
            stray, [],
            "дубли хелперов остались в acceptance_tests/ ЕЩЁ НЕ закрытых "
            f"задач: {stray}")


if __name__ == "__main__":
    unittest.main()
