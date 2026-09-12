"""AC-7, AC-9 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md): посторонние файлы
`acceptance_tests/` (`orchestrator/checkpoint.py`) по-прежнему исключаются
из автокоммита и журналируются одной записью «посторонние файлы в каталоге
планки», для ЛЮБОЙ роли — эта механика САМА не меняется этой задачей (SPEC
требование 3 меняет только то, КАК эту же запись читает выход
`tests_writing`, orchestrator/fsm_advance.py — предмет
test_ac8_stray_files_last_journal_entry.py рядом).

Зелёный с рождения: `checkpoint._commit_external_step_artifacts` уже сегодня
исключает посторонние файлы планки и журналирует их одной записью
независимо от роли (SPEC 01M1SAA01YRRTWAVADT2F81RRQ) — SPEC этой задачи
прямо требует, чтобы для test_author (AC-7) это исключение осталось, а для
остальных ролей (AC-9) не изменилось вовсе. Оба теста здесь защищают этот
факт от случайной регрессии при добавлении гейта AC-8 (например, попытки
"упростить" её, начав коммитить посторонние файлы test_author, раз выше по
цепочке их всё равно отклонит fsm_advance.tests_writing).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "drycollectstraytarget"


class _StrayRoleSandbox(RealGitSandbox):

    TASK = "01DRYCOLLECTSTRAYBASE"

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача — роль и посторонние файлы",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, content: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]


class Ac7TestAuthorStrayFilesStillExcludedTest(_StrayRoleSandbox):

    TASK = "01DRYCOLLECTAC7BASE01"

    def test_ac7_stray_files_from_test_author_are_still_not_committed(self):
        """Шаг `test_author` с легитимным тестом и посторонним файлом первого
        уровня — легитимный файл коммитится, посторонний исключён и
        журналирован одной записью.

        Ловит мутацию: правка гейта AC-8 (fsm_advance.tests_writing) заодно
        трогает `checkpoint` — например, начинает коммитить посторонние
        файлы test_author, раз «отказ теперь и так случится выше по
        цепочке» — тест ловит именно этот регресс: посторонний файл обязан
        остаться исключённым здесь, независимо от того, что решит гейт."""
        self.write("acceptance_tests/test_ac1_something.py", "# тест\n")
        self.write("acceptance_tests/fixtures.json", '{"x": 1}')

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        files = self.artifact_branch_files()
        prefix = f"tasks/{self.TASK}/"
        self.assertIn(prefix + "acceptance_tests/test_ac1_something.py", files)
        self.assertNotIn(prefix + "acceptance_tests/fixtures.json", files)
        stray_entries = [d for d in self.journal_details()
                         if "посторонние файлы" in d]
        self.assertEqual(len(stray_entries), 1, stray_entries)
        self.assertIn("fixtures.json", stray_entries[0])


class Ac9OtherRolesUnaffectedTest(_StrayRoleSandbox):

    TASK = "01DRYCOLLECTAC9BASE01"

    def test_ac9_non_test_author_role_keeps_warning_only_behaviour(self):
        """Та же фикстура (легитимный файл + посторонний файл), но роль
        шага — НЕ `test_author` (например, `developer`, чей мандат тоже
        может задеть `acceptance_tests/`, скажем, правкой соседнего файла
        зоны): шаг коммитится как раньше, посторонний файл исключён,
        журнал несёт ту же предупреждающую запись — без отличий от
        поведения до этой задачи.

        Ловит мутацию: правило AC-7/AC-8 обобщается на ЛЮБУЮ роль вместо
        `test_author` — тогда шаг `developer` с посторонним файлом планки
        начинает трактоваться иначе, чем «раньше», хотя SPEC требует
        прежнего поведения для всех ролей, кроме `test_author`."""
        self.write("acceptance_tests/test_ac1_something.py", "# тест\n")
        self.write("acceptance_tests/fixtures.json", '{"x": 1}')

        result = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertTrue(
            result, "шаг не должен отказывать — легитимный файл обязан "
            "закоммититься для роли, отличной от test_author")
        files = self.artifact_branch_files()
        prefix = f"tasks/{self.TASK}/"
        self.assertIn(prefix + "acceptance_tests/test_ac1_something.py", files)
        self.assertNotIn(prefix + "acceptance_tests/fixtures.json", files)
        stray_entries = [d for d in self.journal_details()
                         if "посторонние файлы" in d]
        self.assertEqual(len(stray_entries), 1, stray_entries)


if __name__ == "__main__":
    unittest.main()
