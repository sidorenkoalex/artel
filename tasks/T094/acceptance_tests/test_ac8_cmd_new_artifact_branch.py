"""Приёмочный тест T094 — AC-8 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-8: «cmd_new создаёт артефактную ветку задачи в репозитории пульта и
делает попытку её push в origin; отказ push не прерывает заведение
задачи и не превращает его в ошибку команды.»

Красен до реализации: сегодняшний `catalog.cmd_new(title, tz_path=None,
*, canary=False)` не принимает `target` вовсе — всегда заводит задачу
для `config.DEFAULT_TARGET` (self/догфуд), а требование 16 SPEC ИМЕННО
self исключает из механики артефактной ветки до A7.
Наблюдать AC-8 можно только для НЕ-self target — тест поэтому зовёт
`catalog.cmd_new(title, target=...)` по образцу уже существующего
keyword-only расширения этой же функции (`canary=True`, требование 6
SPEC T065) — тем же приёмом, той же сигнатурной семьёй: `target` —
устоявшееся имя этого понятия по всему `orchestrator/*.py` (`store.
insert_task(..., target=...)`, `fixation.fix(task_id, target)`,
`projects.project_dir(name)`). `TypeError` на отсутствующем параметре —
легитимная краснота «функциональность ещё не добавлена», не опечатка
теста.

Артефактная ветка ищется БЕЗ предположений о её имени (SPEC не называет
схему именования — это решает PLAN.md разработчика, требование 1):
любая ветка репозитория пульта, кроме `main`, несущая `tasks/<id>/` —
годится под определение критерия.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402


def _artifact_branch_hosting(task_id: str) -> list:
    branches = gitcmd.list_branches() or []
    hosting = []
    for branch in branches:
        if branch == config.MAIN_BRANCH:
            continue
        files = gitcmd.ls_tree_files(branch, f"tasks/{task_id}")
        if files:
            hosting.append(branch)
    return hosting


class Ac8CmdNewPushBestEffortTest(ExternalTargetGitSandbox):
    """Пульт (`self.root`) БЕЗ настроенного `origin` — push не может
    удаться физически, ровно сценарий «отказ сети»."""

    def test_ac8_cmd_new_still_succeeds_when_push_has_nowhere_to_go(self):
        task_id = catalog.cmd_new("Задача внешнего target",
                                  target=self.TARGET)

        row = store.get_task(store.db(), task_id)
        self.assertEqual(row["target"], self.TARGET)
        self.assertTrue(
            _artifact_branch_hosting(task_id),
            f"после cmd_new(target={self.TARGET!r}) ни одна ветка "
            f"пульта, кроме main, не несёт tasks/{task_id}/ (AC-8)")


class Ac8CmdNewPushSucceedsTest(ExternalTargetGitSandbox):
    """Пульт (`self.root`) С работающим `origin` (локальный bare-репо,
    сеть не участвует) — push обязан реально доехать."""

    def setUp(self):
        super().setUp()
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.pult_origin = Path(bare_tmp.name) / "pult-origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.pult_origin)],
            check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.pult_origin))
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def test_ac8_cmd_new_pushes_the_artifact_branch_to_origin(self):
        task_id = catalog.cmd_new("Задача внешнего target",
                                  target=self.TARGET)

        hosting = _artifact_branch_hosting(task_id)
        self.assertTrue(hosting, f"нет артефактной ветки для {task_id}")

        remote_heads = subprocess.run(
            ["git", "ls-remote", "--heads", str(self.pult_origin)],
            capture_output=True, text=True, check=True).stdout
        self.assertTrue(
            any(branch in remote_heads for branch in hosting),
            f"артефактная ветка {hosting} не доехала до origin пульта "
            f"(AC-8, push best-effort): {remote_heads!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
