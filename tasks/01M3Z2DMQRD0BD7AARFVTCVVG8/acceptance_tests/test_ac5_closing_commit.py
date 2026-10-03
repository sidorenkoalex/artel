"""AC-5: закрытие (`killed`, `done`) — коммит RETRO в ту же ссылку, без снимка.

Группа: разовый
Красен до реализации: сегодня закрытие публикует снимок без родителя и удаляет ветку `artifact/<id>`, а `refs/artifacts/<id>` до закрытия нет вовсе — предусловие о голове ссылки падает раньше закрытия.

Файл разовый: проверка идёт через настоящий git и bare `origin`, правила
долгоживущих файлов `tests/` такое запрещают.

Перед закрытием ссылка совпадает с `origin` — это обеспечивает сам тест
обычным push (`RefSandbox.sync_origin`): отказ закрытия при расхождении —
предмет AC-6, здесь он не должен вмешиваться.
"""
import unittest

from _sandbox import EXTERNAL_TARGET, RefSandbox, ref_name


class _ClosingMixin:

    def assert_closing_commit(self, task_id: str, before: str,
                              chain_before: list, out: str,
                              exact_parent: bool = True) -> str:
        retro = f"tasks/{task_id}/RETRO.md"
        head = self.local_head(task_id)
        self.assertTrue(head, f"ссылка {ref_name(task_id)} удалена при "
                              f"закрытии:\n{out[-1500:]}")
        self.assertNotEqual(head, before, f"коммита закрытия нет:\n{out[-1500:]}")
        parents = self.parents(head)
        if exact_parent:
            self.assertEqual(parents, [before], "родитель коммита закрытия — "
                                                "не прежняя голова ссылки")
        else:
            self.assertEqual(len(parents), 1,
                             f"у коммита закрытия не один родитель: {parents}")
            self.assertTrue(self.is_ancestor(before, parents[0]),
                            "родитель коммита закрытия не потомок прежней "
                            "головы ссылки")
            self.assertIsNone(self.file_at(parents[0], retro),
                              "RETRO.md появился раньше коммита закрытия")
        self.assertIsNotNone(self.file_at(head, retro),
                             "в коммите закрытия нет RETRO.md")
        self.assertEqual(self.first_commit(head), self.first_commit(before),
                         "при закрытии появился новый коммит без родителя")
        chain_after = set(self.chain(head))
        lost = [sha for sha in chain_before if sha not in chain_after]
        self.assertEqual(lost, [], "прежние коммиты ссылки недостижимы")
        return head


class Ac5KillTest(_ClosingMixin, RefSandbox):
    """AC-5: `killed`."""

    def test_ac5_kill_appends_retro_commit_and_keeps_history(self):
        """`kill` после лока планки — коммит RETRO поверх прежней головы.

        Задача прошла выход из `tests_writing` (`tests_locked_sha` записан).
        После `kill`: ссылка на месте, голова — коммит с
        `tasks/<id>/RETRO.md`, его единственный родитель — прежняя голова;
        корень истории прежний (новых коммитов без родителя нет); все
        прежние коммиты, включая `tests_locked_sha`, достижимы из головы.

        Ловит мутацию: закрытие по-прежнему пишет снимок коммитом без
        родителя в `refs/artifacts/<id>` — у головы нет родителя, история
        и коммит лока становятся недостижимы.
        """
        task_id = self.new_task()
        self.prepare_tests_writing(task_id)
        self.lock_plank(task_id)
        locked = self.row(task_id)["tests_locked_sha"]
        before = self.sync_origin(task_id)
        chain_before = self.chain(before)
        self.assertIn(locked, chain_before,
                      "предусловие: лок — коммит истории ссылки")

        out = self.kill(task_id)

        self.assertEqual(self.row(task_id)["state"], "killed", out[-1500:])
        head = self.assert_closing_commit(task_id, before, chain_before, out)
        self.assertIn(locked, self.chain(head),
                      "коммит tests_locked_sha недостижим после закрытия")


class Ac5DoneTest(_ClosingMixin, RefSandbox):
    """AC-5: `done`."""

    def test_ac5_merge_appends_retro_commit_and_keeps_history(self):
        """Мерж задачи (`approve` на гейте мержа) — коммит RETRO поверх головы.

        Задача внешнего target на гейте мержа, CI ветки зелёный. После
        `approve`: задача `done`, ссылка на месте, голова — коммит с
        `RETRO.md`, корень истории прежний, прежние коммиты достижимы. У
        внешнего target переход в `done` сам дописывает строку паспорта
        (AC-4) — поэтому родитель коммита закрытия здесь сверяется как
        единственный потомок прежней головы без `RETRO.md`, а не как сама
        прежняя голова.

        Ловит мутацию: мерж зовёт прежний снимок закрытия — в ссылке
        оказывается коммит без родителя, а прежняя история пропадает.
        """
        self.declare_external_target()
        task_id = self.new_task(target=EXTERNAL_TARGET)
        self.prepare_external_merge_gate(task_id)
        before = self.sync_origin(task_id)
        chain_before = self.chain(before)

        out = self.approve(task_id)

        self.assertEqual(self.row(task_id)["state"], "done", out[-1500:])
        self.assert_closing_commit(task_id, before, chain_before, out,
                                   exact_parent=False)


if __name__ == "__main__":
    unittest.main()
