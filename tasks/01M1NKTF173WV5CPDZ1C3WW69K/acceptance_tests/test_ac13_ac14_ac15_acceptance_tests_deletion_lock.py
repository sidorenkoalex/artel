"""Приёмочные тесты AC-13/AC-14/AC-15 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/
SPEC.md): автокоммит шага переносит удаление файла из
`tasks/<id>/acceptance_tests/` в артефактную ветку тем же коммитом, если
удаление сделано ролью test_author в состоянии `tests_writing` ДО
фиксации лока приёмочных тестов (`tests_locked_sha` ещё пуст) — AC-13.
После фиксации лока то же удаление больше НЕ переносится — прежнее
правило («удаляемы только `type: questions`») остаётся в силе, файл
остаётся в ветке — AC-14. Регресс-тест сценария канарейки v2: несколько
файлов, отменённых test_author'ом одним шагом до лока, пропадают из
ветки за ЭТОТ ЖЕ вызов автокоммита, без повторных попыток — AC-15.

Красен до реализации: `checkpoint._DELETABLE_ARTIFACT_TYPES` сегодня —
`frozenset({"questions"})`, а файлы `acceptance_tests/*.py` не несут
YAML-frontmatter вовсе (`yamlmini.frontmatter` на них — `None`), поэтому
НИКОГДА не признаются кандидатом на удаление сегодняшним правилом — их
удаление ролью НЕ переносится в артефактную ветку ни до, ни после лока.
AC-13/AC-15 падают на том, что удалённый файл остаётся в ветке. AC-14
(«после лока файл остаётся») формально уже проходит сегодня, но по
СЛУЧАЙНОЙ причине (общее правило никогда не удаляет .py-файлы, не
потому что лок это специально запрещает) — см. докстринг класса ниже,
почему этот тест всё равно ценен и не является тавтологией.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "ac131415locktarget"

AC_TEST_STUB = (
    '"""Заглушка теста для стенда AC-13/AC-14/AC-15."""\n'
    "import unittest\n\n\n"
    "class StubTest(unittest.TestCase):\n"
    "    def test_stub_passes(self):\n"
    "        pass\n"
)


class AcceptanceTestsDeletionBeforeLockTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01AC13BEFORELOCKDEL01"
        store.insert_task(store.db(), self.TASK, "Удаление до лока",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_ac13_role_deletion_before_lock_lands_in_the_artifact_branch(self):
        """test_author пишет тест на первом шаге, затем на следующем шаге
        (состояние всё ещё `tests_writing`, `tests_locked_sha` пуст) его
        убирает — удаление обязано доехать до артефактной ветки тем же
        коммитом.

        Ловит мутацию: удаление `acceptance_tests/*.py` по-прежнему
        подчиняется только старому правилу `_DELETABLE_ARTIFACT_TYPES`
        (frontmatter `type: questions`) — файл без frontmatter никогда не
        считается кандидатом, остаётся в ветке вопреки AC-13.
        """
        self.task_dir.mkdir(parents=True)
        self.write("acceptance_tests/test_ac1_foo.py", AC_TEST_STUB)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
                      self.artifact_branch_files())

        # Следующий шаг test_author: файл больше не пишется — роль его
        # убрала. tests_locked_sha всё ещё пуст.
        self.task_dir.mkdir(parents=True)

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "test_author")

        self.assertNotIn(
            f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
            self.artifact_branch_files(),
            "удаление файла acceptance_tests/ до лока обязано доехать до "
            "артефактной ветки")
        self.assertIn("удалено", detail)


class AcceptanceTestsDeletionAfterLockTest(RealGitSandbox):
    """AC-14: после `tests_locked_sha` прежнее правило (только `type:
    questions`) остаётся в силе — здесь ЦЕЛЕНАПРАВЛЕННО воспроизводится
    сценарий «удаление после лока» с явно взведённым `tests_locked_sha`,
    не полагаясь на случайное совпадение с сегодняшним поведением: если
    реализация AC-13 расширит правило удаления НЕ сузив его условием
    «лок ещё пуст», этот тест поймает регресс, которого сегодняшнее
    (ещё не расширенное) поведение поймать не может."""

    def setUp(self):
        super().setUp()
        self.TASK = "01AC14AFTERLOCKKEEP01"
        store.insert_task(store.db(), self.TASK, "Удаление после лока",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_ac14_role_deletion_after_lock_does_not_reach_the_branch(self):
        """Файл `acceptance_tests/` уже зафиксирован (`tests_locked_sha`
        не пуст) — его исчезновение с диска на очередном шаге НЕ имеет
        права дойти до артефактной ветки: планка приёмки залочена.

        Ловит мутацию: расширение правила AC-13 не проверяет
        `tests_locked_sha` вовсе (удаляет `acceptance_tests/*.py` по
        одному лишь `role == test_author`) — залоченный тест исчезает из
        ветки уже ПОСЛЕ фиксации лока.
        """
        self.task_dir.mkdir(parents=True)
        self.write("acceptance_tests/test_ac1_foo.py", AC_TEST_STUB)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
                      self.artifact_branch_files())

        store.update_task(store.db(), self.TASK, tests_locked_sha="f" * 40)
        self.task_dir.mkdir(parents=True)

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        self.assertIn(
            f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
            self.artifact_branch_files(),
            "после фиксации лока удаление файла acceptance_tests/ НЕ "
            "имеет права дойти до артефактной ветки")


class AcceptanceTestsDeletionSingleStepNoRetryTest(RealGitSandbox):
    """AC-15: регресс-тест канарейки v2 — несколько файлов, отменённых
    сразу одним шагом test_author до лока, полностью пропадают из ветки
    за ЭТОТ ЖЕ вызов автокоммита (без повторных попыток)."""

    def setUp(self):
        super().setUp()
        self.TASK = "01AC15CANARYREGRESS01"
        store.insert_task(store.db(), self.TASK, "Канарейка v2 регресс",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_ac15_two_cancelled_tests_disappear_in_the_same_autocommit_call(self):
        """SPEC отменена и переписана — test_author убирает ОБА старых
        теста в ОДНОМ шаге; один вызов `commit_step_artifacts` обязан
        унести оба удаления сразу, без второго захода.

        Ловит мутацию: цикл удаления обрабатывает только ПЕРВЫЙ найденный
        кандидат на удаление за вызов (например, `break` вместо
        продолжения цикла) — второй файл переживает автокоммит и требует
        повторной попытки, ровно инцидент канарейки v2 из «Контекста» SPEC.
        """
        self.task_dir.mkdir(parents=True)
        self.write("acceptance_tests/test_ac1_foo.py", AC_TEST_STUB)
        self.write("acceptance_tests/test_ac2_bar.py", AC_TEST_STUB)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")
        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
                      files)
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac2_bar.py",
                      files)

        self.task_dir.mkdir(parents=True)

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "test_author")

        files = self.artifact_branch_files()
        self.assertNotIn(
            f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py", files)
        self.assertNotIn(
            f"tasks/{self.TASK}/acceptance_tests/test_ac2_bar.py", files)
        self.assertIn("test_ac1_foo.py", detail)
        self.assertIn("test_ac2_bar.py", detail)


if __name__ == "__main__":
    unittest.main()
