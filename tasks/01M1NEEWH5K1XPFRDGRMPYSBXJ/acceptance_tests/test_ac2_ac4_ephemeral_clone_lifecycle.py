"""AC-2 + AC-4 (SPEC.md), общая песочница (обе смотрят на один и тот же
эфемерный клон, естественно делят перехват `tempfile.mkdtemp`/
`shutil.rmtree`, см. `_sandbox.py::_EphemeralDirTracker`):

AC-2. Полный цикл каждой выбранной задачи проходит в отдельном
эфемерном клоне пульта: собственный рабочий каталог, собственная БД
состояния, собственный origin-заглушка (не настоящий git-remote).

AC-4. Каталог эфемерного клона удаляется по завершении прогона
(независимо от исхода прогона).

Перехват не полагается на конкретное имя функции/модуля, которым
реализация заведёт и уберёт эфемерный клон (см. докстринг модуля
`_sandbox.py`, п.3) — только на то, что временный каталог заведён и
убран стандартными средствами CPython, единственными для этого
пригодными.

Красен до реализации: `canary --k` падает на разборе аргументов раньше любого клона (см. `test_ac1_pool_dir_and_sampling.py`) — трекер не перехватывает НИ ОДНОГО каталога с `.git` внутри, `git_like_snapshots()` пуст, первая же содержательная проверка (`assertGreaterEqual(len(...), 1)`) падает `AssertionError` по факту отсутствия эфемерного клона, не по случайной причине песочницы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, _EphemeralDirTracker  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
    "udalenie-rudimenta.md": "Убери неиспользуемый синтетический модуль Y.",
}


class EphemeralCloneLifecycleTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.tracker = _EphemeralDirTracker()
        self.tracker.start(self)

    def test_ac2_each_task_runs_in_its_own_clone_with_own_db_and_stub_origin(self):
        """k=2 задачи прогона — минимум два разных эфемерных каталога с
        `.git` внутри (по клону на задачу, требование 2: «Полный цикл
        КАЖДОЙ выбранной задачи»), у каждого — собственный файл БД
        (`*.db`, не общий `config.DB` внешнего пульта) и `origin`, не
        указывающий на реальный внешний http(s)-хост (заглушка, не
        настоящий remote).

        Ловит мутацию: разработчик заводит ОДИН общий эфемерный клон на
        весь прогон пула вместо клона НА ЗАДАЧУ (`< 2` каталогов с
        `.git` при k=2), либо использует общий `config.DB` пульта вместо
        собственного файла БД клона (`db_files` пусто в снимке).
        """
        out = self.run_canary_pool(2)
        self.assertNotIn("[SystemExit]", out, out)

        clones = self.tracker.git_like_snapshots()
        self.assertGreaterEqual(
            len(clones), 2,
            f"ожидались минимум 2 эфемерных клона (по одному на k=2 "
            f"задачи), пойман{'о' if len(clones) != 1 else ''} "
            f"{len(clones)}: {self.tracker.snapshots}")

        for snap in clones:
            with self.subTest(clone=snap.get("entries")):
                self.assertTrue(
                    snap["db_files"],
                    f"у эфемерного клона нет собственного файла БД: {snap}")
                origin = snap.get("origin_url") or ""
                self.assertFalse(
                    origin.startswith("http://") or origin.startswith("https://"),
                    f"origin эфемерного клона указывает на настоящий "
                    f"внешний remote, не на заглушку: {origin!r}")

    def test_ac4_ephemeral_clone_directories_are_gone_after_the_run(self):
        """После завершения прогона ни один из перехваченных
        `.git`-каталогов больше не существует на диске — заявленное
        `shutil.rmtree` действительно убрало их, а не просто было
        вызвано с ошибкой/на пустом месте.

        Ловит мутацию: разработчик забывает подчистить клон в ветке
        ИСКЛЮЧЕНИЯ/убитой задачи (например, оборачивает уборку только в
        happy-path, не в `finally`) — при k=2, где обе задачи доходят
        до `killed` (v1-семантика merge_gate, AC-11), недостающий
        `finally` оставил бы каталог(и) физически на диске.
        """
        self.run_canary_pool(2)

        clones = self.tracker.git_like_snapshots()
        self.assertGreaterEqual(len(clones), 1,
                                "прогон не завёл ни одного эфемерного клона")
        for path_str in self.tracker.snapshots:
            with self.subTest(path=path_str):
                self.assertFalse(
                    Path(path_str).exists(),
                    f"эфемерный клон не удалён по завершении прогона: "
                    f"{path_str}")


if __name__ == "__main__":
    unittest.main()
