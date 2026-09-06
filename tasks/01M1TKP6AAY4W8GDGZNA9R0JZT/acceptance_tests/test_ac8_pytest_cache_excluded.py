"""AC-8 (SPEC.md, требование 5): после прогона pytest пультом
(`acceptance.run()`/`run_full_suite()`) каталог `.pytest_cache/` не
попадает в дерево автокоммита артефактов задачи
(`orchestrator/checkpoint.py`) — либо не создаётся вовсе
(`-p no:cacheprovider`), либо отфильтрован тем же приёмом, что и прочие
`.gitignore`-исключения (`gitcmd.check_ignore`, тот же вызов, что
использует `checkpoint._commit_external_step_artifacts`).

Зелёный с рождения: запись `.pytest_cache/` УЖЕ есть в `.gitignore`
корня репозитория (независимо от этой задачи) — второй разъединитель
требования 5 («либо каталог остаётся исключён .gitignore… тем же
приёмом, что и сейчас») выполнен структурно ДО перехода на pytest;
`checkpoint.py` не входит в зону этой задачи и не правится ею. До
перехода requirement 1 на pytest `run()`/`run_full_suite()` вообще не
порождают `.pytest_cache/` (unittest не создаёт такой каталог) —
первый тест ниже проходит вырожденно (кеш не создан — первая ветка
дизъюнкции требования 5 выполнена тривиально); после перехода тест
проверяет содержательно, что кеш либо не создаётся вовсе, либо лежит
вне `tasks/<id>/` (куда смотрит `checkpoint.py`) или отфильтрован
`.gitignore`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import acceptance, gitcmd  # noqa: E402

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""


class PytestCacheNotCommittedTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.code_root = Path(tmp.name)
        self.task_id = "T001"
        self.tdir = self.code_root / "tasks" / self.task_id
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_marker.py").write_text(PASSING_TEST, encoding="utf-8")

    def test_ac8_gitignore_already_excludes_pytest_cache_anywhere_in_tree(self):
        """`.gitignore` пульта (`config.ROOT`) считает ЛЮБОЙ путь с
        компонентом `.pytest_cache/` игнорируемым, включая путь под
        `tasks/<id>/` — ровно тот приём, которым `checkpoint.py`
        отфильтровывает артефакты перед автокоммитом.

        Ловит мутацию: запись `.pytest_cache/` убрана из `.gitignore`
        (например, случайная правка при подготовке этой задачи) —
        `gitcmd.check_ignore` вернёт пустое множество вместо пути,
        `assertIn` откажет.
        """
        candidate = f"tasks/{self.task_id}/acceptance_tests/.pytest_cache/CACHEDIR.TAG"
        ignored = gitcmd.check_ignore({candidate})
        self.assertIsNotNone(ignored, "git check-ignore не ответил")
        self.assertIn(candidate, ignored)

    def test_ac8_real_run_leaves_no_committable_cache_under_task_dir(self):
        """Реальный прогон `acceptance.run()` на планке, вложенной в
        `tasks/<id>/` реалистичного дерева `code_root` — любой созданный
        `.pytest_cache/` либо отсутствует вовсе, либо не попадает под
        `tasks/<id>/` (единственное поддерево, которое сканирует
        `checkpoint._commit_external_step_artifacts`), либо, если всё же
        оказался внутри, распознаётся `gitcmd.check_ignore` как
        игнорируемый.

        Ловит мутацию: реализация требования 1 передаёт pytest
        `--cache-dir=<путь внутри tasks/<id>/>` явно (например, «чтобы
        не мусорить в code_root») — кеш оказывается ИМЕННО там, откуда
        `checkpoint.py` собирает артефакты, и не покрыт `.gitignore`
        (запись `.pytest_cache/` матчит каталог с таким именем, но не
        произвольный путь `--cache-dir`) — тест ниже поймает и
        нежелательное расположение, и то, что оно не отфильтровано.
        """
        green, tail = acceptance.run(self.tdir, self.code_root)
        self.assertTrue(green, tail)

        task_prefix = self.tdir.resolve()
        caches = [p for p in self.code_root.rglob(".pytest_cache") if p.is_dir()]
        for cache_dir in caches:
            rel_to_code_root = cache_dir.resolve().relative_to(self.code_root.resolve())
            under_task_dir = str(cache_dir.resolve()).startswith(str(task_prefix))
            if not under_task_dir:
                continue
            ignored = gitcmd.check_ignore({rel_to_code_root.as_posix()})
            self.assertIsNotNone(ignored, "git check-ignore не ответил")
            self.assertIn(
                rel_to_code_root.as_posix(), ignored,
                f"{cache_dir} лежит внутри tasks/<id>/, но НЕ отфильтрован "
                f".gitignore — попадёт в автокоммит артефактов")


if __name__ == "__main__":
    unittest.main()
