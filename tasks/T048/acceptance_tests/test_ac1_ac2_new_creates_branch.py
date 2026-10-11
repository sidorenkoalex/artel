"""AC-1, AC-2 (tasks/T048/SPEC.md): `new` рождает ТЗ/SPEC сразу в ветке
задачи, не в рабочей копии main.

AC-1. `new "<название>" --tz <файл>` оставляет рабочую копию main
нетронутой (`git status` пуст, ветка `main` без новых коммитов), а в
ветке задачи `task/<id>-<slug>` появляется коммит
`<id>: ТЗ Оператора (<название>)` с `TZ.md` и шаблонным `SPEC.md`.

AC-2. `new "<название>"` без `--tz` даёт тот же результат (ветка задачи
+ один коммит с тем же сообщением), но без `TZ.md` — в коммите только
шаблонный `SPEC.md`.

Прогоняется через `artel.main()` с подменённым argv — команда `new`
названа в критерии буквально как команда CLI (см.
tasks/T045/acceptance_tests/test_ac1_ac2_workspace_command.py — тот же
приём).
"""
import unittest

from _sandbox import TmpGitTaskTest  # noqa: E402

TITLE = "Ветка рождения ТЗ"
TZ_TEXT = "Проверка, что ТЗ рождается сразу в ветке задачи.\n"


class NewCreatesBranchAndCommitTest(TmpGitTaskTest):

    def test_ac1_tz_flow_leaves_main_untouched_and_commits_to_task_branch(self):
        before_sha = self.main_head_sha()
        tz_path = self.write_tz_file(TZ_TEXT)

        self.cli_new(TITLE, tz_path)

        row = self.last_task_row()
        task_id, branch = row["id"], row["branch"]

        self.assertEqual(
            self.git("status", "--porcelain").stdout, "",
            "рабочая копия main обязана остаться нетронутой")
        self.assertEqual(self.main_head_sha(), before_sha,
                         "ветка main не должна получить новых коммитов")
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
            "main", "текущая ветка главной копии не должна переключаться")

        self.assertTrue(self.branch_exists(branch),
                        f"ветка {branch} обязана быть заведена")
        self.assertEqual(self.commit_message(branch),
                         f"{task_id}: ТЗ Оператора ({TITLE})")
        self.assertEqual(self.commits_ahead_of_main(branch), 1,
                         "ТЗ и шаблонный SPEC обязаны прийти одним коммитом")

        files = self.tree_files(branch, f"tasks/{task_id}")
        self.assertIn(f"tasks/{task_id}/TZ.md", files)
        self.assertIn(f"tasks/{task_id}/SPEC.md", files)

    def test_ac2_without_tz_gives_same_branch_and_commit_but_no_tz_file(self):
        before_sha = self.main_head_sha()

        self.cli_new(TITLE)

        row = self.last_task_row()
        task_id, branch = row["id"], row["branch"]

        self.assertEqual(self.git("status", "--porcelain").stdout, "",
                         "результат обязан быть тем же — main нетронут")
        self.assertEqual(self.main_head_sha(), before_sha)

        self.assertTrue(self.branch_exists(branch))
        self.assertEqual(self.commit_message(branch),
                         f"{task_id}: ТЗ Оператора ({TITLE})")
        self.assertEqual(self.commits_ahead_of_main(branch), 1)

        files = self.tree_files(branch, f"tasks/{task_id}")
        self.assertIn(f"tasks/{task_id}/SPEC.md", files)
        self.assertNotIn(f"tasks/{task_id}/TZ.md", files,
                         "без --tz коммит не должен нести TZ.md")


if __name__ == "__main__":
    unittest.main()
