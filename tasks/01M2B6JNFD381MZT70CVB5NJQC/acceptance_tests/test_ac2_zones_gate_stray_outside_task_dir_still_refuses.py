"""AC-2 (tasks/01M2B6JNFD381MZT70CVB5NJQC/SPEC.md): неотслеживаемый файл
worktree ВНЕ `tasks/<task_id>/` по-прежнему считается путём вне зон и
вызывает отказ гейта зон — правило «каталог задачи — своя зона» (AC-1
этой же задачи) не расширяется на пути, которые задаче не принадлежат;
сегодняшнее поведение (01M290PVYG2VJK6442H5BAX9MA, AC-6) сохраняется
байт-в-байт.

Зелёный с рождения: регрессионная страховка уже существующего
поведения — до и после правки этой задачи гейт зон обязан одинаково
отказывать на постороннем неотслеживаемом файле (см. залоченную
планку 01M290PVYG2VJK6442H5BAX9MA/acceptance_tests/
test_ac6_zones_gate_untracked_files.py и tests/test_zones_gate.py::
UntrackedWorktreePathsTest). Назначение этого теста — поймать
регрессию правила AC-1 (например, случайное расширение исключения на
все неотслеживаемые пути вместо только `tasks/<task_id>/`), не
подтвердить новое поведение.

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия), тот же сценарий, что и залоченная планка
01M290PVYG2VJK6442H5BAX9MA.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class ZonesGateStrayFileOutsideTaskDirTest(_WorktreeCheckpointTest):

    ZONE = "orchestrator/allowed_module.py"

    def enter_in_dev(self):
        sha = super().enter_in_dev()
        store.update_task(store.db(), self.TASK, zones=self.ZONE)
        return sha

    def test_ac2_untracked_file_outside_task_dir_still_refuses_the_gate(self):
        """Коммиченный дифф строго в заявленной зоне, рабочее дерево несёт
        неотслеживаемый файл ВНЕ `tasks/<task_id>/` и вне заявленных зон
        (`orchestrator/stray.py`) — гейт зон обязан отказать переходу тем
        же текстом «дифф трогает файлы вне заявленных zones…», что и
        раньше: правило AC-1 этой задачи не касается путей вне
        собственного каталога задачи.

        Ловит мутацию: правило «каталог задачи — своя зона» (AC-1)
        реализовано ШИРЕ заявленного — например, исключение из довеска
        неотслеживаемых файлов применено ко ВСЕМ путям worktree, не
        только к `tasks/<task_id>/` — `refuses` вернула бы `False`
        вместо `True`, и отказ на постороннем файле пропал бы вместе с
        легитимным исключением для `tasks/<id>/`.
        """
        self.enter_in_dev()
        self.write_code_file(self.ZONE, "# код строго в заявленной зоне\n")
        self.worktree_git("add", "-A")
        self.worktree_git("commit", "-q", "-m", "код в зоне")

        self.write_code_file("orchestrator/stray.py",
                             "# посторонний файл вне зон\n")

        conn = store.db()
        t = store.get_task(conn, self.TASK)
        branch = t["branch"]

        refuses = fsm_advance._zones_gate_refuses(conn, self.TASK, t, branch,
                                                   "PLAN\n")

        self.assertTrue(refuses)
        details = [r["detail"] for r in store.task_steps(conn, self.TASK)]
        self.assertTrue(any(
            "дифф трогает файлы вне заявленных zones" in d
            and "stray.py" in d for d in details))


if __name__ == "__main__":
    unittest.main()
