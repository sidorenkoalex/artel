"""AC-2: гонка двух записей в ссылку одной задачи не теряет изменений.

Группа: разовый
Красен до реализации: сегодня запись идёт в ветку `artifact/<id>`, а `refs/artifacts/<id>` после `new` нет — предусловие о голове ссылки падает раньше гонки; и сама запись `update-ref` идёт без сверки прежнего значения.

Файл разовый по той же причине, что и остальная планка: проверка идёт через
`artifact_branch` и настоящий git, а правила долгоживущих файлов `tests/`
такие имена запрещают.

Как разыграна гонка. Пишущий узел — `artifact_branch.commit_files`
(публичная запись документов задачи, ею пишут все существующие места и
тесты `tests/test_artifact_branch_push.py`, `tests/test_amend.py`). Вторая
запись вклинивается ровно в тот момент, когда первая уже собрала коммит от
прежней головы и подаёт `git update-ref` на `refs/artifacts/<id>` (SPEC,
требование 2: запись — `commit-tree` и `update-ref`): перехват видит этот
вызов git и до его исполнения проводит вторую запись целиком. Внутренние
функции пульта не подменяются — наблюдается только вызов внешней команды git.
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import RefSandbox, ref_name
from orchestrator import artifact_branch

REAL_RUN = subprocess.run


def _is_ref_update(cmd, kwargs, ref: str) -> bool:
    argv = [str(a) for a in (cmd if isinstance(cmd, (list, tuple)) else [cmd])]
    if not argv or not argv[0].endswith("git") or "update-ref" not in argv:
        return False
    if "-d" in argv:
        return False
    data = kwargs.get("input") or ""
    if isinstance(data, bytes):
        data = data.decode("utf-8", "replace")
    return ref in argv or ref in data


class Ac2RaceTest(RefSandbox):
    """AC-2."""

    def test_ac2_second_write_from_stale_head_keeps_both_changes(self):
        """Вторая запись начата от прежней головы — итог несёт обе правки.

        Первая запись кладёт `A.md`, вторая (вклинившаяся до `update-ref`
        первой) — `B.md`. Голова ссылки после обеих несёт оба файла, история
        от прежней головы линейна: ни одного коммита с двумя родителями,
        прежняя голова — предок итоговой.

        Ловит мутацию: `update-ref` без сверки прежнего значения (как
        сегодня у ветки) — первая запись перетирает ссылку своим коммитом от
        прежней головы, `B.md` пропадает из головы, коммит второй записи
        становится недостижим.
        """
        task_id = self.new_task()
        ref = ref_name(task_id)
        head0 = self.local_head(task_id)
        self.assertTrue(head0, f"предусловие: после new есть {ref}")
        a_rel = f"tasks/{task_id}/A.md"
        b_rel = f"tasks/{task_id}/B.md"
        state = {"fired": False}

        def racing_run(cmd, *args, **kwargs):
            if not state["fired"] and _is_ref_update(cmd, kwargs, ref):
                state["fired"] = True
                state["b_sha"] = artifact_branch.commit_files(
                    task_id, {b_rel: "правка B\n"}, f"{task_id}: B")
            return REAL_RUN(cmd, *args, **kwargs)

        with mock.patch.object(subprocess, "run", racing_run):
            artifact_branch.commit_files(task_id, {a_rel: "правка A\n"},
                                         f"{task_id}: A")

        self.assertTrue(state["fired"],
                        f"запись не подала git update-ref на {ref}")
        self.assertTrue(state.get("b_sha"), "вторая запись не прошла")
        head = self.local_head(task_id)
        self.assertEqual(self.file_at(head, a_rel), "правка A\n",
                         "правка первой записи потеряна")
        self.assertEqual(self.file_at(head, b_rel), "правка B\n",
                         "правка второй записи потеряна")
        self.assertTrue(self.is_ancestor(head0, head),
                        "прежняя голова не предок итоговой")
        self.assertTrue(self.is_ancestor(state["b_sha"], head),
                        "коммит второй записи недостижим из головы")
        for sha in self.chain(head):
            self.assertLessEqual(len(self.parents(sha)), 1,
                                 f"коммит {sha} ссылки — слияние, история "
                                 f"не линейна")


if __name__ == "__main__":
    unittest.main()
