"""Юнит-тесты SPEC 01M1NKTF173WV5CPDZ1C3WW69K: материализация `tasks/<id>/`
из ГОЛОВЫ артефактной ветки (`artifact_branch.materialize_task_dir`,
требование 1), конфликт-гвард автокоммита по роли, не тронувшей файл
(требование 4), лок удаления `acceptance_tests/` только для test_author
(требование 7) и статус `escalate` guard'а (требование 6).

Дополняют, не дублируют, приёмочные тесты задачи
(`tasks/01M1NKTF173WV5CPDZ1C3WW69K/acceptance_tests/`): здесь — прямые
юнит-случаи с краями, которые AC не называют буквально (вложенные
подкаталоги при материализации, чужая роль на удалении acceptance_tests/
до лока, многострочный пункт «Вопросы», статус escalate поверх текста
эскалации).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, checkpoint, config, runner, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class MaterializeTaskDirTest(RealGitSandbox):

    TASK = "01UTMATERIALIZEDIRECT"

    def commit_artifact(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, "фикстура не закоммитила артефактную ветку")
        return sha

    def test_nested_subdirectory_files_are_written_and_pruned(self):
        """Файл во вложенном подкаталоге ветки (`acceptance_tests/test_x.py`)
        материализуется на диск; вложенный файл, отсутствующий в ветке,
        убирается — та же проверка, что AC-1, но на структуре с
        подкаталогом, не только с плоскими файлами прямо в `tasks/<id>/`.

        Ловит мутацию: материализация собирает только файлы верхнего
        уровня `tasks/<id>/` (например, `ls_tree_files` без `-r`) — файл
        во вложенном подкаталоге теряется молча.
        """
        self.commit_artifact(
            {f"tasks/{self.TASK}/acceptance_tests/test_x.py": "тест x"},
            "исходная версия")
        dest = self.root / "materialized"
        dest.mkdir()
        leftover = dest / "tasks" / self.TASK / "acceptance_tests" / "test_stale.py"
        leftover.parent.mkdir(parents=True)
        leftover.write_text("осевший тест\n", encoding="utf-8")

        head = artifact_branch.materialize_task_dir(self.TASK, dest)

        self.assertTrue(head)
        self.assertEqual(
            (dest / "tasks" / self.TASK / "acceptance_tests" /
             "test_x.py").read_text(encoding="utf-8"), "тест x")
        self.assertFalse(leftover.exists(),
                         "вложенный файл, отсутствующий в ветке, обязан "
                         "быть убран материализацией")

    def test_no_branch_returns_empty_sha_and_leaves_disk_untouched(self):
        """AC-2 на уровне самой функции: ветки нет — возврат пустой строки,
        каталог назначения не создаётся вовсе."""
        dest = self.root / "materialized2"

        head = artifact_branch.materialize_task_dir(self.TASK, dest)

        self.assertEqual(head, "")
        self.assertFalse((dest / "tasks" / self.TASK).exists())


class ConflictGuardStateGuardTest(RealGitSandbox):
    """AC-13/AC-14 покрывают лок через `tests_locked_sha`; здесь —
    отдельный защитный рубеж того же правила: `state` задачи, а не
    только лок. Сигнал «последний коммит пути — автокоммит ЭТОЙ ЖЕ
    роли» (`subject == message`) сам по себе требует, чтобы роль
    вызова совпадала с ролью прошлого коммита — заведомо не отличить
    удаление test_author от удаления чужой роли одним лишь именем роли
    (сообщение автокоммита несёт роль в тексте). Состояние задачи —
    независимый второй рубеж на случай гонки, где `tests_locked_sha`
    ещё не проставлен, а задача уже сдвинулась с `tests_writing`."""

    TASK = "01UTSTATEGUARDNODEL01"
    TARGET = "ut-state-guard-target"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.TASK, "State-гвард лока тестов",
                          "tests_writing", f"task/{self.TASK.lower()}-x",
                          self.TARGET, config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / self.TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK

    def artifact_branch_files(self) -> list:
        from orchestrator import gitcmd
        branch = artifact_branch.branch_name(self.TASK)
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_deletion_after_state_left_tests_writing_is_not_carried_over(self):
        """Файл появился в ветке автокоммитом test_author (state:
        tests_writing, лок пуст) — легитимный кандидат на удаление по
        AC-13. Дальше задача сдвинулась с `tests_writing` (например,
        гонка обновления `tests_locked_sha` и `state`), но лок ВСЁ ЕЩЁ
        пуст на момент повторного удаления — новое правило не имеет
        права сработать по одному лишь пустому логу, `state` обязан
        совпасть тоже.

        Ловит мутацию: условие проверяет только `role ==
        "test_author"` и пустой `tests_locked_sha`, без `state ==
        "tests_writing"` — залоченная-по-факту (но ещё не
        колонкой) планка теряет файл в узком окне гонки.
        """
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "acceptance_tests").mkdir()
        (self.task_dir / "acceptance_tests" / "test_ac1_foo.py").write_text(
            "стаб\n", encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")
        self.assertIn(f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
                      self.artifact_branch_files())

        store.update_task(store.db(), self.TASK, state="in_dev")
        self.task_dir.mkdir(parents=True)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "test_author")

        self.assertIn(
            f"tasks/{self.TASK}/acceptance_tests/test_ac1_foo.py",
            self.artifact_branch_files(),
            "удаление вне state: tests_writing не имеет права доехать "
            "до артефактной ветки, даже с пустым tests_locked_sha")


class EscalationStatusErrorsTest(unittest.TestCase):
    """Юнит-случаи `guard.escalation_status_errors`/`_escalation_bullet_text`
    сверх сценариев приёмки (AC-11/AC-12): многострочный пункт «Вопросы»,
    тип вне {plan, review, spec}, статус escalate поверх заполненной
    секции."""

    def plan_text(self, status: str, escalation_body: str) -> str:
        return (
            "---\ntask: x\ntype: plan\nauthor_role: developer\n"
            f"status: {status}\n---\n\n"
            "## Подход\n\nТекст.\n\n## Шаги\n\n1. Шаг.\n\n"
            "## Покрытие требований\n\n| Требование | Шаг |\n|---|---|\n"
            "| 1 | 1 |\n\n## Влияние на систему\n\nТекст.\n\n"
            f"{escalation_body}")

    def test_multiline_questions_bullet_is_detected(self):
        """Пункт «Вопросы» из нескольких строк (реальный батч эскалации,
        skills/escalation-rules.md — «все вопросы разом») распознаётся
        целиком, не только первая строка.

        Ловит мутацию: `_escalation_bullet_text` без DOTALL/многострочного
        захвата — видит только первую строку пункта и не замечает
        содержательный батч, если первая строка формально пуста.
        """
        body = (
            "## Эскалация\n\n"
            "- **Вопросы** —\n"
            "  1. Первый вопрос? Дефолт — А.\n"
            "  2. Второй вопрос? Дефолт — Б.\n"
            "- **Контекст** — сделано то и это.\n"
            "- **Блокирует** — дальнейшую работу.\n")
        errors = guard.check_content("PLAN.md", self.plan_text("ready", body))

        self.assertTrue(
            any("эскалация текстом без статуса escalate" in e for e in errors),
            errors)

    def test_type_outside_plan_review_spec_is_never_flagged(self):
        """`type: tz`/`questions`/… — раздел «Эскалация» с полным текстом
        не имеет отношения к этому правилу (SPEC требование 6 называет
        только plan/review/spec).

        Ловит мутацию: проверка типа убрана или ослаблена — TZ.md с
        разделом «Эскалация» ловил бы то же нарушение, для которого
        `type: tz` не предусмотрен ни SPEC, ни RULES.
        """
        text = (
            "---\ntask: x\ntype: tz\nauthor_role: analyst\nstatus: draft\n"
            "---\n\n## Эскалация\n\n"
            "- **Вопросы** — тестовый вопрос.\n")
        errors = guard.escalation_status_errors("TZ.md", text,
                                                {"type": "tz", "status": "draft"})

        self.assertEqual(errors, [])

    def test_escalate_status_bypasses_even_with_full_escalation_section(self):
        """Позитивный кейс к AC-12 на уровне самой функции: status
        escalate — правило не срабатывает независимо от содержимого
        секции."""
        body = (
            "## Эскалация\n\n"
            "- **Вопросы** — вопрос.\n"
            "- **Блокирует** — всё.\n")
        errors = guard.escalation_status_errors(
            "PLAN.md", self.plan_text("escalate", body),
            {"type": "plan", "status": "escalate"})

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
