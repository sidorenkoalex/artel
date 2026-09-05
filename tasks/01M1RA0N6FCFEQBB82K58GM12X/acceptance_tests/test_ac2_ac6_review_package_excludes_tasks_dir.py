"""AC-2, AC-6 (tasks/01M1RA0N6FCFEQBB82K58GM12X/SPEC.md): diff и стат-
список ревью-пакета (`review.review_package`/`review.git_diff_part`) не
несут содержимого `tasks/<task_id>/` — ни в `--stat`, ни в самом diff —
тем же правилом, что и гейт ёмкости (AC-1). Артефакты уже идут в пакет
своими компонентами (SPEC/PLAN/REVIEW/ANSWER, T011/SPEC T075) — их дубль
внутри diff/стат-списка только раздувает контекст ревьювера (регрессия
№10, T029).

AC-2 явно называет ОБА расчёта — полный и инкрементальный: этот файл
разносит их по разным классам — `Ac6FullDiffExcludesTasksDirTest`
(итерация 1, полный diff от `config.MAIN_BRANCH`) закрывает AC-6
буквально, `Ac2IncrementalDiffExcludesTasksDirTest` (итерация 2+, diff
от `prev_sha`) закрывает вторую половину AC-2, не покрытую AC-6.

Настоящий git-репозиторий (`tests.sandbox.RealGitSandbox` через
`_sandbox.GitFeatureBranchSandbox`), не подмена `gitcmd.git`: пакет
собирается `review.review_package` по-настоящему, тест смотрит только на
готовый текст — способ исключения внутри `git_diff_part` тестами не
навязывается.

Красен до реализации: `review.git_diff_part`/`review.review_package`
сегодня передают diff и `--stat` без какого-либо pathspec, исключающего
`tasks/<task_id>/` — обе строки ниже видят путь артефакта прямо в
diff/стат-секции пакета.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import gitcmd, review  # noqa: E402
from _sandbox import GitFeatureBranchSandbox  # noqa: E402


def _stat_and_diff_sections(text: str) -> tuple[str, str]:
    """(секция стат-списка, секция diff) пакета — по заголовкам, которые
    `review.review_package` несёт дословно и стабильно по порядку
    (`test_all_parts_are_present_in_a_stable_order`, tests/
    test_review_package.py) — секция diff идёт от своего заголовка и до
    конца пакета (последний компонент по порядку сборки)."""
    stat_marker = "### Изменённые файлы"
    diff_marker = "### Diff"
    stat_at = text.index(stat_marker)
    diff_at = text.index(diff_marker)
    return text[stat_at:diff_at], text[diff_at:]


class Ac6FullDiffExcludesTasksDirTest(GitFeatureBranchSandbox):
    """Первая (полная, `iteration == 1`) итерация ревью-пакета: diff и
    стат-список считаются от `config.MAIN_BRANCH`, как и до этой задачи
    (T029) — критерий, буквально сформулированный как «Тест» в SPEC
    (AC-6).

    Ловит мутацию: `review_package` продолжает звать `git_diff_part` без
    исключающего pathspec — путь `tasks/<id>/acceptance_tests/...`
    появляется и в стат-строке, и в теле diff."""

    TASK = "T901"
    BRANCH = "task/t901-x"

    def test_ac6_full_diff_and_stat_carry_no_tasks_dir_lines(self):
        self.write(self.CODE_FILE, "базовый код\nправка кода\n")
        self.commit("код")
        self.write(f"tasks/{self.TASK}/acceptance_tests/test_x.py",
                  "содержимое планки\n")
        self.commit("артефакты: планка")

        package = review.review_package(self.conn, self.TASK,
                                        "Ревью-пакет", self.BRANCH)

        stat_section, diff_section = _stat_and_diff_sections(package["text"])
        needle = f"tasks/{self.TASK}/"
        self.assertNotIn(
            needle, stat_section,
            f"стат-список ревью-пакета не имеет права нести строку "
            f"{needle!r} (AC-6): {stat_section!r}")
        self.assertNotIn(
            needle, diff_section,
            f"diff ревью-пакета не имеет права нести строку {needle!r} "
            f"(AC-6): {diff_section!r}")
        self.assertIn(
            self.CODE_FILE, diff_section,
            "сценарий сконструирован неверно: правка кода обязана "
            "остаться в diff'е — исключение не должно задевать код")


class Ac2IncrementalDiffExcludesTasksDirTest(GitFeatureBranchSandbox):
    """Вторая половина AC-2: инкрементальный diff (T029, `iteration > 1`,
    diff от `prev_sha`, не от `config.MAIN_BRANCH`) — то же правило
    исключения `tasks/<id>/` действует и здесь, отдельно от полного diff
    (AC-6), потому что инкремент считается другим вызовом `git_diff_part`
    с другой базой сравнения.

    Ловит мутацию: исключение реализовано только для ветки полного diff
    (`iteration == 1`) в `review_package`, инкрементальный вызов
    `git_diff_part` в ветке `iteration > 1` его не наследует — путь
    `tasks/<id>/` возвращается в инкрементальном diff/стат-списке."""

    TASK = "T902"
    BRANCH = "task/t902-x"

    def test_ac2_incremental_diff_and_stat_carry_no_tasks_dir_lines(self):
        self.write(self.CODE_FILE, "базовый код\nправка кода v1\n")
        self.commit("код v1 (граница прошлого вердикта)")
        prev_sha = gitcmd.head_sha()
        self.assertTrue(prev_sha, "sha прошлого вердикта обязан быть получен")

        self.write(self.CODE_FILE, "базовый код\nправка кода v1\nправка кода v2\n")
        self.commit("код v2 (после прошлого вердикта)")
        self.write(f"tasks/{self.TASK}/acceptance_tests/test_y.py",
                  "содержимое планки после вердикта\n")
        self.commit("артефакты: планка после вердикта")

        package = review.review_package(self.conn, self.TASK, "Ревью-пакет",
                                        self.BRANCH, iteration=2,
                                        prev_sha=prev_sha)

        self.assertIn(
            "инкрементальный", package["text"],
            "сценарий сконструирован неверно: пакет обязан признать себя "
            "инкрементальным (иначе он деградировал на полный diff, и "
            "тест ничего не проверяет про AC-2)")
        stat_section, diff_section = _stat_and_diff_sections(package["text"])
        needle = f"tasks/{self.TASK}/"
        self.assertNotIn(
            needle, stat_section,
            f"инкрементальный стат-список не имеет права нести строку "
            f"{needle!r} (AC-2): {stat_section!r}")
        self.assertNotIn(
            needle, diff_section,
            f"инкрементальный diff не имеет права нести строку {needle!r} "
            f"(AC-2): {diff_section!r}")
        self.assertIn(
            "правка кода v2", diff_section,
            "сценарий сконструирован неверно: инкрементальная правка кода "
            "обязана остаться в diff'е — исключение не должно задевать код")


if __name__ == "__main__":
    unittest.main()
