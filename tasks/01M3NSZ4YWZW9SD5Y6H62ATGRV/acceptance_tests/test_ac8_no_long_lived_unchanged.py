"""AC-8: задача без перечня в дереве лока, с пустым перечнем или без лока
— `review.snapshot_exclude` отдаёт прежний кортеж, текст пакета ревью
байт в байт прежний, существующие тесты amend/пакета/гейта ёмкости не
тронуты и зелёные.

«Прежний текст пакета» — текст, который собирает `orchestrator/review.py`
с базы ветки задачи (`gitcmd.diff_base`), загруженный отдельным модулем,
на той же песочнице и с тем же идентификатором границ.

Группа: разовый
Зелёный с рождения: до реализации поведение задачи без долгоживущих файлов и есть прежнее — критерий сторожит, чтобы реализация его не сдвинула.

Почему разовый: «прежнее» — это база ветки задачи и дифф против неё,
после мержа сравнивать не с чем.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (REPO_ROOT, _TransitionSandbox,  # noqa: E402
                      fixed_run_id, review_module_before_task, task_diff_base)
from orchestrator import artifact_branch, gitcmd, review, store  # noqa: E402

EXISTING_TESTS = ("tests/test_amend.py", "tests/test_review_package.py",
                  "tests/test_review_package_map.py")


def existing_test_files() -> list[str]:
    capacity = sorted(p.relative_to(REPO_ROOT).as_posix()
                      for p in (REPO_ROOT / "tests").glob("test_capacity_gate*.py"))
    return [*EXISTING_TESTS, *capacity]


class NoLongLivedUnchangedTest(_TransitionSandbox):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.before, cls.before_reason = review_module_before_task()

    def setUp(self):
        super().setUp()
        self.assertIsNotNone(self.before, self.before_reason)
        self.feature_committed = False

    def commit_feature(self) -> None:
        """Код фичи в кодовой ветке — после выхода из `tests_writing`
        (гейт «только добавление» не пустил бы его раньше)."""
        if not self.feature_committed:
            self.wt_commit({"feature.py": "print('код фичи')\n"})
            self.feature_committed = True

    def packages(self) -> tuple[str, str]:
        with fixed_run_id():
            now = review.review_package(store.db(), self.TASK, "песочница",
                                        self.branch)["text"]
            then = self.before.review_package(store.db(), self.TASK, "песочница",
                                              self.branch)["text"]
        return now, then

    def scenarios(self):
        def no_lock():
            self.set_row(tests_locked_sha=None)

        def lock_without_manifest():
            docs_head = gitcmd.branch_head_sha(
                artifact_branch.branch_name(self.TASK))
            self.assertTrue(docs_head)
            self.set_row(tests_locked_sha=docs_head)

        def empty_manifest():
            out = self.exit_tests_writing()
            self.assertEqual(self.state(), "in_dev", out)

        # Пустой перечень первым: выход из `tests_writing` — до кода фичи.
        return (("пустой перечень", empty_manifest),
                ("без лока", no_lock),
                ("лок без перечня в дереве", lock_without_manifest))

    def test_ac8_exclude_and_package_text_unchanged(self):
        """Три вида задачи без долгоживущих файлов: без лока, лок без
        перечня в дереве, пустой перечень. У каждой
        `snapshot_exclude(<id>)` — `(".", ":!tasks/<id>/",
        ":!docs/codebase-map.md")`, а текст пакета ревью совпадает с
        текстом сборщика с базы ветки задачи.

        Ловит мутацию: компонент долгоживущих файлов (или заметка о них)
        добавляется в пакет безусловно, в том числе при пустом перечне —
        текст пакета расходится с прежним.
        """
        for label, arrange in self.scenarios():
            with self.subTest(scenario=label):
                arrange()
                self.commit_feature()
                self.assertEqual(
                    review.snapshot_exclude(self.TASK),
                    (".", f":!tasks/{self.TASK}/", ":!docs/codebase-map.md"))
                now, then = self.packages()
                self.assertEqual(now, then, f"{label}: текст пакета изменился")


class ExistingTestsUntouchedTest(unittest.TestCase):

    def test_ac8_existing_tests_unchanged_and_green(self):
        """`tests/test_amend.py`, `tests/test_review_package.py`,
        `tests/test_review_package_map.py`, `tests/test_capacity_gate*.py`
        не отличаются от базы ветки задачи (ни в коммитах, ни в рабочей
        копии) и проходят прогоном pytest.

        Ловит мутацию: существующий тест подогнан под новое поведение
        (правка ожидания `snapshot_exclude` в `test_review_package_map.py`)
        — файл отличается от базы.
        """
        base, reason = task_diff_base()
        self.assertIsNotNone(base, reason)
        files = existing_test_files()
        self.assertTrue(any("test_capacity_gate" in f for f in files))
        diff = gitcmd.in_repo(REPO_ROOT, "diff", "--name-only", base, "--", *files)
        self.assertIsNotNone(diff)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertEqual(diff.stdout.strip(), "",
                         "существующие тесты правлены относительно базы")
        for rel in files:
            self.assertTrue((REPO_ROOT / rel).is_file(), rel)
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             *files], cwd=REPO_ROOT, capture_output=True, text=True, timeout=110)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
