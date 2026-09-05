"""Приёмочные тесты AC-1/AC-2 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md):
материализация `tasks/<id>/` рабочего каталога роли (`runner.role_cwd`)
из ГОЛОВЫ артефактной ветки на старте агентного шага (AC-1); отсутствие
артефактной ветки — тихая деградация, шаг не падает и не рвётся (AC-2).

Красен до реализации: `runner.role_cwd` сегодня только заводит/выдаёт
git worktree задачи (self) либо каталог workspace (внешний target) и
НЕ сверяет `tasks/<id>/` с артефактной веткой вовсе — ни перезаписи
устаревшего файла, ни уборки лишнего с диска не происходит; оба теста
`RoleCwdMaterializationTest` падают на этом отсутствии, а не на
постороннем дефекте стенда.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, runner, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class RoleCwdMaterializationTest(RealGitSandbox):

    TASK = "01AC1MATERIALIZE0001TT"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK.lower()}-x"
        store.insert_task(store.db(), self.TASK, "Материализация из ветки",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def commit_artifact(self, files: dict, message: str) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, "тестовая фикстура не закоммитила артефактную ветку")

    def test_ac1_overwrites_stale_disk_content_with_branch_head(self):
        """Диск роли, уже несущий устаревшую версию SPEC.md, перезаписывается
        версией с ГОЛОВЫ артефактной ветки при повторном вызове `role_cwd`
        (правка Оператора между двумя вызовами старта шага).

        Ловит мутацию: `role_cwd` продолжает возвращать worktree без
        сверки с артефактной веткой (сегодняшнее поведение) — устаревший
        текст SPEC.md остаётся на диске нетронутым вместо свежей версии.
        """
        self.commit_artifact({f"tasks/{self.TASK}/SPEC.md": "SPEC v1"},
                             "исходная версия")
        cwd = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)
        self.assertEqual(
            (cwd / "tasks" / self.TASK / "SPEC.md").read_text(encoding="utf-8"),
            "SPEC v1")

        self.commit_artifact(
            {f"tasks/{self.TASK}/SPEC.md": "SPEC v2 (правка Оператора)"},
            "правка Оператора")
        cwd2 = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)

        self.assertEqual(cwd2, cwd)
        self.assertEqual(
            (cwd2 / "tasks" / self.TASK / "SPEC.md").read_text(encoding="utf-8"),
            "SPEC v2 (правка Оператора)")

    def test_ac1_removes_a_leftover_file_absent_from_the_branch(self):
        """Файл, осевший на диске рабочего каталога роли (например, от
        прерванного предыдущего шага) и отсутствующий на ГОЛОВЕ артефактной
        ветки, убирается материализацией при следующем вызове `role_cwd`;
        легитимный файл ветки при этом не страдает.

        Ловит мутацию: материализация реализована только как «допиши
        отсутствующее» (add/overwrite) без сверки состава файлов — лишний
        файл остаётся на диске бессрочно.
        """
        self.commit_artifact({f"tasks/{self.TASK}/SPEC.md": "SPEC v1"},
                             "исходная версия")
        cwd = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)
        leftover = cwd / "tasks" / self.TASK / "STALE_LEFTOVER.md"
        leftover.write_text("осевший файл прерванного шага\n", encoding="utf-8")

        cwd2 = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)

        self.assertFalse(
            (cwd2 / "tasks" / self.TASK / "STALE_LEFTOVER.md").exists(),
            "файл, отсутствующий в артефактной ветке, обязан быть убран "
            "с диска материализацией")
        self.assertEqual(
            (cwd2 / "tasks" / self.TASK / "SPEC.md").read_text(encoding="utf-8"),
            "SPEC v1", "легитимный файл ветки не должен пострадать вместе "
                      "с лишним")


class RoleCwdNoArtifactBranchTest(RealGitSandbox):

    TASK = "01AC2NOBRANCHDEGRADE01"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK.lower()}-x"
        store.insert_task(store.db(), self.TASK, "Без артефактной ветки",
                          "in_dev", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac2_missing_artifact_branch_does_not_raise_or_wipe_disk(self):
        """У задачи нет артефактной ветки (`artifact/<id>` не заведена) —
        `role_cwd` не падает исключением и не устраивает деградацию
        рабочего каталога: существующее содержимое диска остаётся как есть.

        Ловит мутацию: чтение головы отсутствующей ветки трактуется как
        «ветка пуста» и материализация тихо вычищает диск начисто вместо
        того, чтобы вовсе не выполняться при отсутствии ветки.
        """
        cwd = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)
        task_dir = cwd / "tasks" / self.TASK
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "LOCAL_ONLY.md").write_text("локальный черновик\n",
                                                 encoding="utf-8")

        cwd2 = runner.role_cwd(store.db(), self.TASK, config.DEFAULT_TARGET)

        self.assertEqual(cwd2, cwd)
        self.assertTrue(
            (cwd2 / "tasks" / self.TASK / "LOCAL_ONLY.md").exists(),
            "материализация без артефактной ветки не имеет права трогать "
            "диск")


if __name__ == "__main__":
    unittest.main()
