"""Юнит-тесты наблюдаемого мира холодного старта (orchestrator/coldstart.py,
SPEC T049, требование 1).

Сквозной путь (посев счётчика через `store.seed_task_counters`, incident
`doctor.check_task_counters`) уже покрыт приёмочными тестами
`tasks/T049/acceptance_tests/test_ac1_*`/`test_ac2_*` — здесь только сама
функция сканирования наблюдаемого мира, источник за источником.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import coldstart, config  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class NoGitObservedWorldTest(TmpRootTest):
    """`config.ROOT` не git-репозиторий (`.git` вовсе нет) — сканируются
    только каталоги задач на диске, git-источники молча пропускаются
    (требование 1: «при доступности»), а не падают."""

    def test_empty_project_has_zero_observed_max(self):
        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 0)

    def test_task_dirs_are_scanned_without_git(self):
        (config.TASKS / "T003").mkdir(parents=True)
        (config.TASKS / "T010").mkdir(parents=True)

        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 10)

    def test_non_default_target_reads_its_own_projects_tasks_dir(self):
        (config.PROJECTS / "sled" / "tasks" / "T007").mkdir(parents=True)

        self.assertEqual(coldstart.observed_max_task_number("sled"), 7)

    def test_non_default_target_never_reads_default_targets_tasks(self):
        (config.TASKS / "T099").mkdir(parents=True)

        self.assertEqual(coldstart.observed_max_task_number("sled"), 0)


class GitObservedWorldTest(TmpRootTest):
    """`config.ROOT` — настоящий временный git-репозиторий: ветки `task/t*`,
    файлы `docs/retro/T*.md` и история `main` — источники требования 1,
    проверяемые только для `config.DEFAULT_TARGET`."""

    def setUp(self):
        super().setUp()
        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "README.md").write_text("холодный старт\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args: str) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
        return res

    def test_branch_is_a_source_of_the_observed_max(self):
        self.git("branch", "task/t015-vetka-bez-stroki-bd")

        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 15)

    def test_retro_file_is_a_source_of_the_observed_max(self):
        retro_dir = self.root / "docs" / "retro"
        retro_dir.mkdir(parents=True)
        (retro_dir / "T020.md").write_text("# RETRO: T020\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "retro T020")

        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 20)

    def test_main_history_subject_is_a_source_of_the_observed_max(self):
        (self.root / "note.txt").write_text("x", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "T025: коммит без каталога/ветки/retro")

        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 25)

    def test_max_across_all_sources_wins(self):
        self.git("branch", "task/t005-malaya-vetka")
        retro_dir = self.root / "docs" / "retro"
        retro_dir.mkdir(parents=True)
        (retro_dir / "T030.md").write_text("# RETRO: T030\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "retro T030")
        (config.TASKS / "T012").mkdir(parents=True)

        self.assertEqual(coldstart.observed_max_task_number(config.DEFAULT_TARGET), 30)

    def test_non_default_target_ignores_git_sources_entirely(self):
        self.git("branch", "task/t040-chuzhaya-vetka")

        self.assertEqual(coldstart.observed_max_task_number("sled"), 0)


if __name__ == "__main__":
    unittest.main()
