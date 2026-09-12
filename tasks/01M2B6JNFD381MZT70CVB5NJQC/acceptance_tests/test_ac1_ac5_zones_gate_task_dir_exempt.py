"""AC-1, AC-5 (первая половина) (tasks/01M2B6JNFD381MZT70CVB5NJQC/SPEC.md):
гейт зон (`fsm_advance._zones_gate`) не считает путём вне зон
неотслеживаемый файл под `tasks/<task_id>/` — собственным каталогом
задачи, тем же правилом, что `checkpoint._zone_paths` уже применяет к
WIP-чекпоинтам; пропуск такого пути не создаёт отдельной записи журнала
(это штатное поведение).

Красен до реализации: `fsm_advance._zones_gate` сегодня строит зоны
довеска неотслеживаемых файлов как `declared + list(config.COMMON_ZONES)`
(orchestrator/fsm_advance.py) — `tasks/<task_id>/` в этот список не
входит, и неотслеживаемый файл под ним считается путём вне зон, как и
любой другой посторонний путь.

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия): та же, что уже несёт залоченная планка
01M290PVYG2VJK6442H5BAX9MA (`test_ac6_zones_gate_untracked_files.py`)
для симметричного сценария «файл вне зон».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm_advance, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class ZonesGateUntrackedTaskDirFileTest(_WorktreeCheckpointTest):

    ZONE = "orchestrator/allowed_module.py"

    def enter_in_dev(self):
        # `zones` объявляется ПОСЛЕ `enter_in_dev()` — см. докстринг того
        # же приёма в залоченной планке 01M290PVYG2VJK6442H5BAX9MA.
        sha = super().enter_in_dev()
        store.update_task(store.db(), self.TASK, zones=self.ZONE)
        return sha

    def _commit_code_in_zone(self) -> None:
        self.write_code_file(self.ZONE, "# код строго в заявленной зоне\n")
        self.worktree_git("add", "-A")
        self.worktree_git("commit", "-q", "-m", "код в зоне")

    def _write_untracked_plank_file(self) -> Path:
        acc_dir = self.wt / "tasks" / self.TASK / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        path = acc_dir / "test_x.py"
        path.write_text(
            "import unittest\n\n\nclass X(unittest.TestCase):\n\n"
            "    def test_x(self):\n        pass\n", encoding="utf-8")
        return path

    def test_ac1_untracked_task_dir_file_does_not_count_as_out_of_zone(self):
        """Коммиченный дифф строго в заявленной зоне, а рабочее дерево
        worktree несёт НЕОТСЛЕЖИВАЕМЫЙ файл под собственным каталогом
        задачи (`tasks/<id>/acceptance_tests/test_x.py`, оставленный
        материализацией планки) — гейт зон обязан пропустить переход, не
        отказывать так, как отказал бы на постороннем пути.

        Ловит мутацию: `tasks/<task_id>/` не добавлен в список зон
        довеска неотслеживаемых файлов (правило `checkpoint._zone_paths`
        не переиспользовано единым источником) — `refuses` вернула бы
        `True`, как и до правки, вместо `False`.
        """
        self.enter_in_dev()
        self._commit_code_in_zone()
        self._write_untracked_plank_file()

        conn = store.db()
        t = store.get_task(conn, self.TASK)
        branch = t["branch"]

        refuses = fsm_advance._zones_gate_refuses(conn, self.TASK, t, branch,
                                                   "PLAN\n")

        self.assertFalse(
            refuses,
            f"журнал: {[r['detail'] for r in store.task_steps(conn, self.TASK)]}")

    def test_ac5_task_dir_skip_leaves_no_separate_journal_entry(self):
        """Тот же сценарий, что AC-1 (неотслеживаемый файл под собственным
        каталогом задачи, коммит строго в зоне) — пропуск пути гейтом не
        добавляет отдельной записи журнала сверх того, что уже было до
        вызова: это штатное поведение, не аудиторская запись.

        Ловит мутацию: реализация правила «каталог задачи — своя зона»
        сопровождается собственной записью журнала (например, «путь
        пропущен как зона задачи») вместо тихого пропуска — счётчик
        записей журнала после вызова оказался бы больше на одну запись.
        """
        self.enter_in_dev()
        self._commit_code_in_zone()
        self._write_untracked_plank_file()

        conn = store.db()
        t = store.get_task(conn, self.TASK)
        branch = t["branch"]
        before = len(store.task_steps(conn, self.TASK))

        fsm_advance._zones_gate_refuses(conn, self.TASK, t, branch, "PLAN\n")

        after = len(store.task_steps(conn, self.TASK))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
