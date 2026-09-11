"""Юнит-тесты `orchestrator.catalog.spawn_subtask`
(01M1SHJZCE0Y4DXAAWQ2W585A7, требования 1-2) — заведение одной подзадачи
деления в изоляции от `fsm._approve_spec_gate`.

Сквозной путь (approve с секцией «## Деление» находит подраздел, заводит
подзадачу, журналирует родителя) уже закрывают приёмочные тесты
`tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/acceptance_tests/test_ac5_*`/
`test_ac11_*` — не дублируется здесь. Этот файл проверяет саму функцию:
`SPEC.md` подзадачи — байт-в-байт шаблон `templates/SPEC.md` с
подставленными `task`/названием (тот же шаблон, что и `cmd_new`), а
`TZ.md` несёт ссылку на родителя первой строкой и сохраняет поля
`Зоны:`/`Порядок:` подраздела текстом (требование 2 — «эта задача не
учит cmd_new новым параметрам зон/бюджета»).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, catalog, config, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

PARENT_ID = "01SPAWNUNITPARENTTASK001"
PARENT_TITLE = "Родитель юнит-теста spawn_subtask"
TZ_BODY = ("Зоны: orchestrator/foo.py\nПорядок: первая, без "
          "зависимостей\n\nТекст ТЗ подзадачи юнит-теста.")


class SpawnSubtaskTest(RealGitSandbox):

    def test_spec_is_the_unmodified_template_with_title_and_task_id(self):
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача spawn", TZ_BODY)

        spec = artifact_branch.read_tree(sub_id)[f"tasks/{sub_id}/SPEC.md"]
        template = (config.TEMPLATES / "SPEC.md").read_text(encoding="utf-8")
        expected = template.replace("TASK_ID", sub_id).replace(
            "<название задачи>", "Подзадача spawn")
        self.assertEqual(spec, expected)

    def test_tz_starts_with_the_parent_link_and_keeps_field_text(self):
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача с полями", TZ_BODY)

        tz = artifact_branch.read_tree(sub_id)[f"tasks/{sub_id}/TZ.md"]
        link_line = f"Родительская задача: {PARENT_ID} — {PARENT_TITLE}"

        self.assertLess(
            tz.index(link_line), tz.index(TZ_BODY),
            f"ссылка на родителя не предшествует телу подраздела: {tz!r}")
        # Требование 2: поля Зоны:/Порядок: остаются literal-текстом,
        # cmd_new их не парсит и не превращает во frontmatter подзадачи.
        self.assertIn("Зоны: orchestrator/foo.py", tz)
        self.assertIn("Порядок: первая, без зависимостей", tz)

    def test_new_task_row_starts_in_spec_writing_like_cmd_new(self):
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача состояния", TZ_BODY)

        row = store.get_task(store.db(), sub_id)

        self.assertEqual(row["state"], "spec_writing")
        self.assertEqual(row["title"], "Подзадача состояния")

    def test_target_defaults_to_config_default_target(self):
        sub_id = catalog.spawn_subtask(PARENT_ID, PARENT_TITLE,
                                       "Подзадача таргета", TZ_BODY)

        row = store.get_task(store.db(), sub_id)

        self.assertEqual(row["target"], config.DEFAULT_TARGET)


if __name__ == "__main__":
    import unittest
    unittest.main()
