"""AC-10: исторический снимок `refs/artifacts/<id>` читается как раньше, `doctor` молчит.

Группа: разовый
Зелёный с рождения: сегодня `gitcmd.show` читает снимок по полному имени ссылки, а `doctor` закрытые задачи без ветки `artifact/<id>` не разбирает — файл держит это поведение после перевода `doctor` на ссылку.

Файл разовый: исторические снимки — граница переходного периода этой
части (ADR-0021 п.13), проверка идёт через настоящий git.

Снимок строится так, как его писал прежний пульт: коммит без родителя с
`tasks/<id>/` и `RETRO.md`, отправленный в `refs/artifacts/<id>` origin;
задача в БД закрыта, записи о коммите закрытия в журнале нет. Прежний
пульт отправлял снимок по sha, без локальной ссылки — этот случай
проверяется отдельно.
"""
import os
import subprocess
import unittest

from _sandbox import RefSandbox, ref_name
from orchestrator import config, gitcmd, store

TASK = "01M3HSTRCSNAPSHT0000000001"
RETRO_TEXT = ("---\noperator: Оператор\nmodel: unknown\nartel_sha: abc\n---\n\n"
              "# RETRO\nИтог: done, sha abc. ИСТОРИЧЕСКИЙ-RETRO.\n")
SPEC_TEXT = "# SPEC исторической задачи\nИСТОРИЧЕСКИЙ-SPEC\n"


class Ac10HistoricalSnapshotTest(RefSandbox):
    """AC-10."""

    def write_snapshot(self) -> str:
        index = self.root / ".artel" / "plank-snapshot-index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        for rel, text in ((f"tasks/{TASK}/SPEC.md", SPEC_TEXT),
                          (f"tasks/{TASK}/RETRO.md", RETRO_TEXT)):
            blob = self.git_rc("hash-object", "-w", "--stdin",
                               input_text=text).stdout.strip()
            subprocess.run(["git", "update-index", "--add", "--cacheinfo",
                            f"100644,{blob},{rel}"], cwd=self.root, env=env,
                           check=True, capture_output=True)
        tree = subprocess.run(["git", "write-tree"], cwd=self.root, env=env,
                              check=True, capture_output=True,
                              text=True).stdout.strip()
        index.unlink(missing_ok=True)
        commit = self.git("commit-tree", tree, "-m",
                          f"{TASK}: снапшот закрытия (done)").strip()
        self.git("push", "-q", "origin", f"{commit}:{ref_name(TASK)}")
        store.insert_task(store.db(), TASK, "Историческая задача", "done",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET, 25.0)
        return commit

    def test_ac10_snapshot_reads_by_ref_name(self):
        """`gitcmd.show` по `refs/artifacts/<id>` читает RETRO и SPEC снимка.

        Ловит мутацию: чтение документов по полному имени ссылки
        переписано так, что требует истории (родителя первого коммита) или
        префикса `refs/heads/` — снимок без родителя не читается.
        """
        commit = self.write_snapshot()
        self.git("update-ref", ref_name(TASK), commit)

        retro, reason = gitcmd.show(ref_name(TASK), f"tasks/{TASK}/RETRO.md")
        spec, _ = gitcmd.show(ref_name(TASK), f"tasks/{TASK}/SPEC.md")

        self.assertIsNotNone(retro, f"RETRO снимка не прочитан: {reason}")
        self.assertIn("ИСТОРИЧЕСКИЙ-RETRO", retro)
        self.assertIn("ИСТОРИЧЕСКИЙ-SPEC", spec or "")

    def test_ac10_doctor_silent_for_snapshot_present_locally(self):
        """Снимок есть локально и в `origin` — `doctor` о задаче молчит.

        Ловит мутацию: сверка закрытых ссылок требует записи о коммите
        закрытия в журнале и жалуется, когда её нет (у исторических задач
        её нет никогда).
        """
        commit = self.write_snapshot()
        self.git("update-ref", ref_name(TASK), commit)

        self.assertEqual(self.doctor_complaints(TASK), [])
        self.assertEqual(self.local_head(TASK), commit)
        self.assertEqual(self.origin_head(TASK), commit)

    def test_ac10_doctor_silent_for_snapshot_only_in_origin(self):
        """Снимок только в `origin` (прежний пульт слал его по sha) — молчание.

        Ловит мутацию: сверка с origin распространена на закрытые задачи —
        «локальной ссылки нет, в origin есть» выдаётся расхождением.
        """
        commit = self.write_snapshot()

        self.assertEqual(self.doctor_complaints(TASK), [])
        self.assertEqual(self.origin_head(TASK), commit)


if __name__ == "__main__":
    unittest.main()
