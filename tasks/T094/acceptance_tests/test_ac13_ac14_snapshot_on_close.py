"""Приёмочные тесты T094 — AC-13 и AC-14 (tasks/T094/SPEC.md, «Критерии
приёмки»).

AC-13: «При переходе задачи в done или killed (не канареечный прогон)
оркестратор публикует в refs/artifacts/<id> целевого снапшот,
включающий артефакты задачи и RETRO с полями operator, model,
artel_sha, до удаления кодовой и артефактной веток задачи.»

AC-14: «Снапшот при закрытии публикуется в refs/artifacts/<id> целевого
одинаково для целевых уровня full и partial — снапшот не пишется в
.artel/projects/<target>/.»

Проверяется через `cleanup.cmd_kill` (существующая стабильная команда,
`orchestrator/artel.py`) — путь `killed`; `refs/artifacts/<id>` целевого
— реальный git-ref в `self.target_origin` (bare-репо, имитирующий
форндж целевого, сеть не участвует). Формат/путь файла RETRO внутри
снапшота SPEC не называет — тест сканирует ВСЕ файлы снапшота и ищет
хотя бы один с frontmatter, несущим все три поля (operator/model/
artel_sha), тем же парсером, каким читает frontmatter остальная система
(`orchestrator.yamlmini.frontmatter`).

Красен до реализации: `refs/artifacts/<id>` целевого сегодня никто не
пишет — `cleanup.cmd_kill` убирает worktree/каталог/ветку и журналирует,
сети не касаясь вовсе.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, cleanup, config, gitcmd, store, yamlmini  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402


def _snapshot_ref_exists(origin: Path, task_id: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(origin), "show-ref", "--verify", "--quiet",
         f"refs/artifacts/{task_id}"],
        capture_output=True, text=True)
    return res.returncode == 0


def _snapshot_files(origin: Path, task_id: str) -> list:
    res = subprocess.run(
        ["git", "-C", str(origin), "ls-tree", "-r", "--name-only",
         f"refs/artifacts/{task_id}"],
        capture_output=True, text=True)
    if res.returncode != 0:
        return []
    return [p for p in res.stdout.splitlines() if p]


def _snapshot_file_text(origin: Path, task_id: str, rel: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(origin), "show", f"refs/artifacts/{task_id}:{rel}"],
        capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


class Ac13SnapshotOnKillTest(ExternalTargetGitSandbox):

    def test_ac13_kill_publishes_a_snapshot_ref_with_task_artifacts_and_retro(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)

        cleanup.cmd_kill(task_id)

        self.assertTrue(
            _snapshot_ref_exists(self.target_origin, task_id),
            f"refs/artifacts/{task_id} не появился в origin целевого "
            f"после kill (AC-13)")

        files = _snapshot_files(self.target_origin, task_id)
        self.assertTrue(
            any(f.startswith(f"tasks/{task_id}/") for f in files),
            f"снапшот {task_id} не несёт tasks/{task_id}/: {files}")

        retro_meta = None
        for rel in files:
            text = _snapshot_file_text(self.target_origin, task_id, rel)
            meta = yamlmini.frontmatter(text)
            if meta and {"operator", "model", "artel_sha"} <= meta.keys():
                retro_meta = meta
                break
        self.assertIsNotNone(
            retro_meta,
            f"ни один файл снапшота {task_id} не несёт frontmatter с "
            f"полями operator/model/artel_sha (AC-13): {files}")

    def test_ac13_canary_run_does_not_publish_a_snapshot(self):
        task_id = catalog.cmd_new("Канарейка внешнего target",
                                  target=self.TARGET, canary=True)

        cleanup.cmd_kill(task_id)

        self.assertFalse(
            _snapshot_ref_exists(self.target_origin, task_id),
            f"канареечный прогон {task_id} не должен публиковать "
            f"refs/artifacts/{task_id} (AC-13, исключение канарейки)")


class Ac14SnapshotNeverInLocalProjectsDirTest(ExternalTargetGitSandbox):

    def test_ac14_snapshot_is_not_written_under_dot_artel_projects(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)
        before = sorted((config.PROJECTS / self.TARGET).rglob("*"))

        cleanup.cmd_kill(task_id)

        after = sorted((config.PROJECTS / self.TARGET).rglob("*"))
        new_paths = [p for p in after if p not in before]
        suspicious = [p for p in new_paths if task_id in p.name
                     or "artifact" in p.name.lower()
                     or "snapshot" in p.name.lower()]
        self.assertEqual(
            suspicious, [],
            f".artel/projects/{self.TARGET}/ получил новые пути, похожие "
            f"на снапшот закрытия — AC-14 запрещает писать снапшот сюда: "
            f"{suspicious}")


if __name__ == "__main__":
    import unittest
    unittest.main()
