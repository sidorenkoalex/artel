"""Приёмочный тест AC-8 (tasks/01M1SAA01YRRTWAVADT2F81RRQ/SPEC.md):
существующие тесты `orchestrator/checkpoint.py`, `scripts/guard.py` и
`scripts/codebase_map.py` остаются зелёными без ослабления существующих
проверок или лимитов.

«Остаются зелёными» — исполняется штатным CI-гейтом на каждом коммите
ветки задачи (`.github/workflows/ci.yml`, джоб python, `unittest
discover -s tests`), тем же приёмом, что `tasks/T077/acceptance_tests/
test_ac6_full_suite_regression.py` и его предшественники (T048, T053):
дублирующий здесь прогон всего набора не даёт новой гарантии сверх
штатного гейта, только удлиняет приёмочный прогон этой задачи.

Часть, которую штатный CI-гейт НЕ ловит, — тихое ОСЛАБЛЕНИЕ (удаление
существующего тестового метода вместо починки его под новое поведение):
удалённому тесту нечему падать. Эта проверка ловит именно её — сравнение
имён тестовых методов файлов зоны на ветке задачи с `main`, тем же
приёмом, что `tasks/T077/acceptance_tests/test_ac5_existing_tests_not_
deleted.py`.

Список файлов ниже — результат grep'а по репозиторию на момент написания
теста (`grep -rl` на импорт `orchestrator.checkpoint`/`scripts.guard`/
`scripts.codebase_map` под `tests/`).

Зелёный с рождения: на ветке test_authoring (эта задача, до правок
разработчика) дифф к main по коду пуст — тест проверяет ИНВАРИАНТ «не
удалять существующие тестовые методы», а не текущее состояние правки; он
обязан остаться зелёным и после правок разработчика.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

ZONE_TEST_FILES = [
    "tests/test_acceptance_tests_flow.py",
    "tests/test_analyst_role.py",
    "tests/test_answer.py",
    "tests/test_artifact_materialization.py",
    "tests/test_checkpoint_external_step_artifacts.py",
    "tests/test_codebase_map.py",
    "tests/test_fsm_autogate.py",
    "tests/test_guard_artifact_branch_mode.py",
    "tests/test_guard_schema.py",
    "tests/test_guard_split_signals.py",
    "tests/test_guard_zones.py",
    "tests/test_id_format_guard.py",
    "tests/test_invariants.py",
    "tests/test_pause_now.py",
    "tests/test_review_registry_gate.py",
    "tests/test_step_autocommit.py",
    "tests/test_timeout_checkpoint.py",
    "tests/test_version.py",
    "tests/test_yaml_parsing.py",
]


class ExistingZoneTestsNotWeakenedTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout

    def _test_method_names(self, ref: str, path: str) -> set:
        try:
            content = self._git("show", f"{ref}:{path}")
        except subprocess.CalledProcessError:
            return set()
        return set(guard.TEST_METHOD.findall(content))

    def test_ac8_no_existing_test_method_in_the_zone_is_deleted(self):
        """Ловит мутацию: разработчик «упрощает» неудобный существующий
        тест зоны (`checkpoint`/`guard`/`codebase_map`) удалением метода
        вместо починки его под новый фильтр посторонних файлов —
        например, ослабляет `tests/test_checkpoint_external_step_
        artifacts.py::test_second_step_accumulates_onto_the_first_not_
        replaces_it` или удаляет метод целиком, чтобы не разбираться,
        почему он покраснел от нового поведения."""
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch).strip()

        for path in ZONE_TEST_FILES:
            with self.subTest(файл=path):
                before = self._test_method_names(merge_base, path)
                after = self._test_method_names(branch, path)
                removed = sorted(before - after)
                self.assertEqual(
                    removed, [],
                    f"{path}: удалены существующие тестовые методы "
                    f"{removed} (SPEC 01M1SAA01YRRTWAVADT2F81RRQ, AC-8 — "
                    f"существующие проверки чинятся под новое поведение, "
                    f"не удаляются)")


if __name__ == "__main__":
    unittest.main()
