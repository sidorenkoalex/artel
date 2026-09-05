"""SPEC «Критерии приёмки» AC-10 (дословно тест, названный в самом
критерии): `approve` из `acceptance` с пустым/отсутствующим
`tasks/<id>/acceptance_tests` в worktree кодовой ветки и планкой,
присутствующей в артефактной ветке, — переход зелёный.

Красен до реализации: `acceptance.run(<пустой каталог>)` реально
запускает `python3 -m unittest discover -s <пустой каталог>`, и на
пустом (существующем, но без единого файла) каталоге discover
возвращает ненулевой код возврата — «Ran 0 tests ... NO TESTS RAN» либо
`ImportError: Start directory is not importable`, в зависимости от
окружения (проверено прогоном при подготовке файла: ненулевой код,
текст «NO TESTS RAN») — сегодняшний код трактует ЛЮБОЙ ненулевой код
возврата как КРАСНУЮ планку, эскалируя «приёмочные тесты красные после
подтяжки main», хотя тестов там попросту никогда не было (инцидент SPEC
«Контекст», задача 01M1QHQ277PQQA894X97RVEX9Y). Это ИМЕННО «пустой», не
«отсутствующий» случай AC-10 — «отсутствующий» (каталога нет вовсе) уже
проходил зелёным и до этой задачи (`acceptance.run` трактует `not
tests_dir.is_dir()` как «тесты не заведены»); ловушка — каталог, который
ЕСТЬ, но пуст.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AcceptancePullSandbox, GREEN_TEST  # noqa: E402


class Ac10EmptyWorktreePlankFallsBackTest(AcceptancePullSandbox):

    def test_ac10_empty_worktree_plank_with_green_artifact_plank_passes(self):
        """Worktree кодовой ветки несёт ПУСТОЙ каталог
        `tasks/<id>/acceptance_tests/` (типичный остаток предыдущего шага
        роли, который сегодня не подчищен) — источник истины обязан
        оставаться артефактной веткой, где лежит настоящая (зелёная)
        планка; переход уходит в `merge_gate`.

        Ловит мутацию: планка по-прежнему читается из worktree — пустой
        каталог там ломает `unittest discover` (`ImportError`), переход
        эскалирует вместо ухода в `merge_gate`, и `assertEqual` здесь
        покраснеет.
        """
        wt = self.worktree_dir()
        empty_tests_dir = wt / "tasks" / self.TASK / "acceptance_tests"
        empty_tests_dir.mkdir(parents=True, exist_ok=True)

        files = dict(self.spec_requires_tests())
        files[f"tasks/{self.TASK}/acceptance_tests/test_x.py"] = GREEN_TEST
        self.commit_artifact(files)

        out = self.approve()

        self.assertEqual(
            self.state(), "merge_gate",
            f"пустой каталог планки в worktree не имеет права влиять на "
            f"исход — источник истины артефактная ветка; вывод:\n{out}\n"
            f"журнал: {self.journal_details()}")


if __name__ == "__main__":
    unittest.main()
