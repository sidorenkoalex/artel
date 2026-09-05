"""AC-1 (SPEC.md): команда прогона канарейки читает шаблоны ТЗ из
каталога `~/.artel-canary` (вне корня пульта) и принимает параметр
выборки k, отбирая k случайных шаблонов из доступных N.

Красен до реализации: `canary` пока умеет только v1-сигнатуру
(`cmd_canary(tz_dir, *, rewrite_baseline)`, `tasks/T065/SPEC.md`) —
`--k` читается как позиционный `tz_dir` (несуществующий каталог
`--k`), команда падает `SystemExit("canary: каталог не найден: --k")`
до заведения хоть одной задачи (проверено самим прогоном файла —
см. коммит этой задачи: `python3 -m unittest discover` красит
`test_ac1_five_templates_but_only_k_tasks_are_created` этой причиной,
не опечаткой песочницы).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import store  # noqa: E402
from _sandbox import CanarySandbox  # noqa: E402

POOL_TEMPLATES = {
    f"shablon-{i}.md": f"Синтетическая типовая правка №{i} для канарейки v2."
    for i in range(1, 6)  # N = 5
}


class PoolDirAndSamplingTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)

    def test_ac1_five_templates_but_only_k_tasks_are_created(self):
        """Пул вне корня пульта несёт N=5 шаблонов; прогон с k=2 заводит
        РОВНО 2 задачи (не 5) — сам факт «меньше N» и есть наблюдаемое
        свойство выборки k из N, а не «прогон всего пула», как было в
        v1 (`tasks/T065/SPEC.md`, требование 1 — там команда обрабатывала
        КАЖДЫЙ файл каталога).

        Ловит мутацию: разработчик переносит v1-цикл «завести задачу на
        каждый файл `*.md` каталога» как есть, не применяя `k` — тогда
        заведённых задач было бы 5 (=N), тест это отличает от 2 (=k).
        """
        pool_dir_before = self.pool_dir
        self.assertNotEqual(
            pool_dir_before, self.root,
            "пул этой песочницы должен жить вне self.root по построению")

        out = self.run_canary_pool(2)

        # Мандат Оператора 05.09 (ANSWER-5, вариант A): заведённые
        # канареечные задачи живут в БД эфемерного клона (SPEC требования
        # 2 и 3, test_ac3/test_ac5 требуют пустой `tasks` снаружи), поэтому
        # «заведено ровно k» читается по записям `canary_runs` в БД пульта
        # — единственному следу прогона снаружи клона (требование 5).
        runs = store.db().execute(
            "SELECT title, task_id FROM canary_runs").fetchall()
        task_ids = [r["task_id"] for r in runs]
        self.assertEqual(
            len(task_ids), 2,
            f"k=2 из N=5 шаблонов пула должно завести ровно 2 задачи, "
            f"заведено {len(task_ids)}: {task_ids}\nвывод команды:\n{out}")

        titles = {r["title"] for r in runs}
        pool_stems = {Path(name).stem for name in POOL_TEMPLATES}
        self.assertTrue(
            titles.issubset(pool_stems),
            f"заголовки заведённых задач {titles} не являются подмножеством "
            f"имён шаблонов пула {pool_stems} — задачи заведены не из "
            f"каталога пула `{self.pool_dir}`")


if __name__ == "__main__":
    unittest.main()
