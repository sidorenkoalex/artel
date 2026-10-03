"""AC-1: после `new` документы задачи лежат в `refs/artifacts/<id>`.

Группа: разовый
Красен до реализации: сегодня `new` пишет ветку `artifact/<id>`, а `refs/artifacts/<id>` не создаёт — голова ссылки пуста и `branch_name` возвращает имя ветки.

Файл разовый: он проверяет устройство этой части этапа 1 через имена
`artifact_branch`/`gitcmd` и настоящий git, а правила долгоживущих файлов
`tests/` такие имена и вызов git запрещают. Долгоживущие тесты того же
поведения — обязанность разработчика по требованию 8 SPEC. Часть (б)
этапа 1 меняет место документов, и этот факт после неё проверять не на чем.
"""
import unittest

from _sandbox import TZ_MARKER, RefSandbox, ref_name
from orchestrator import artifact_branch, gitcmd


class Ac1NewCreatesRefTest(RefSandbox):
    """AC-1."""

    def test_ac1_new_creates_parentless_ref_with_task_tree_only(self):
        """`new` с ТЗ заводит `refs/artifacts/<id>` вместо ветки.

        Первый коммит истории ссылки один и без родителя; дерево головы
        содержит только пути `tasks/<id>/…`. Ветки `artifact/<id>` нет ни
        локально, ни в `origin`.

        Ловит мутацию: первый коммит ссылки по-прежнему строится потомком
        `origin/main` (как у сегодняшней ветки) — в истории ссылки
        появляется коммит main с родителем, а в дереве — `marker.txt` и
        `.gitignore` main рядом с `tasks/<id>/`.
        """
        task_id = self.new_task()

        head = self.local_head(task_id)
        self.assertTrue(head, f"после new нет {ref_name(task_id)}")
        roots = self.first_commit(head)
        self.assertEqual(len(roots), 1, f"корней истории ссылки: {roots}")
        self.assertEqual(self.parents(roots[0]), [],
                         "первый коммит ссылки обязан быть без родителя")
        for sha in self.chain(head):
            stray = [p for p in self.tree_paths(sha)
                     if not p.startswith(f"tasks/{task_id}/")]
            self.assertEqual(stray, [],
                             f"в дереве коммита {sha} ссылки пути вне "
                             f"tasks/{task_id}/: {stray}")
        self.assertFalse(self.legacy_branch_local(task_id),
                         "ветка artifact/<id> заведена локально")
        self.assertFalse(self.legacy_branch_origin(task_id),
                         "ветка artifact/<id> отправлена в origin")

    def test_ac1_branch_name_and_show_read_the_ref(self):
        """`branch_name(<id>)` — полное имя ссылки; `show` по нему читает ТЗ.

        Ловит мутацию: `branch_name` оставлен прежним (`artifact/<id>`)
        при записи уже в ссылку — имя не совпадает с `refs/artifacts/<id>`,
        а чтение ТЗ по полному имени ссылки возвращает `None`.
        """
        task_id = self.new_task()

        self.assertEqual(artifact_branch.branch_name(task_id),
                         ref_name(task_id))
        text, reason = gitcmd.show(ref_name(task_id),
                                   f"tasks/{task_id}/TZ.md")
        self.assertIsNotNone(text, f"ТЗ не прочитано из ссылки: {reason}")
        self.assertIn(TZ_MARKER, text)


if __name__ == "__main__":
    unittest.main()
