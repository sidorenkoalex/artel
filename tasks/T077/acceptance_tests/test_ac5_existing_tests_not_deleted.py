"""Приёмочные тесты T077, AC-5 (tasks/T077/SPEC.md): существующие тесты
текста сообщений guard.py обновлены синхронно с переписанными
сообщениями и не удалены (SPEC, требование 4 — `tests/test_guard_
schema.py` и другие).

Зелёный с рождения: на ветке задачи (test_authoring, до правок
разработчика) дифф к main пуст — тест проверяет ИНВАРИАНТ «не удалять
существующие тестовые методы», а не текущее состояние правки; он же
обязан остаться зелёным и после правок разработчика (тот же приём, что
AC-8 в tasks/T052/acceptance_tests/test_ac8_only_permitted_existing_
test_modified.py).

«Обновлены синхронно с переписанными сообщениями» эта проверка
буквально не перепрогоняет — если разработчик забудет обновить
проверяемую подстроку под новый текст сообщения, соответствующий
существующий тест покраснеет сам, и это ловит штатный CI-гейт
(`unittest discover -s tests`, требуется зелёным для merge_gate) — тот
же довод, что AC-6 этой же задачи (test_ac6_full_suite_regression.py).
Здесь проверяется то, что CI не ловит: тихое УДАЛЕНИЕ теста (удалённого
теста нечему падать).

Список файлов ниже — не догадка, а результат grep'а по репозиторию на
момент написания этого теста: файлы, где сегодня есть ассерты на
конкретные подстроки сообщений об ошибках guard.py (`assertIn`/`any(...
in e for e in errors)` с текстом вроде «отсутствует обязательная
секция», «недопустимый status», «нет маркера», «frontmatter без
полей», «Проверено исполнением» и т.п.).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

FILES_TESTING_GUARD_MESSAGE_TEXT = [
    "tests/test_guard_schema.py",
    "tests/test_acceptance_tests_flow.py",
    "tests/test_analyst_role.py",
    "tests/test_invariants.py",
    "tests/test_yaml_parsing.py",
]


class ExistingGuardMessageTestsNotDeletedTest(unittest.TestCase):

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

    def test_ac5_no_existing_guard_message_test_method_is_deleted(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch).strip()

        for path in FILES_TESTING_GUARD_MESSAGE_TEXT:
            with self.subTest(файл=path):
                before = self._test_method_names(merge_base, path)
                after = self._test_method_names(branch, path)
                removed = sorted(before - after)
                self.assertEqual(
                    removed, [],
                    f"{path}: удалены существующие тестовые методы "
                    f"{removed} (SPEC T077, AC-5 — тесты текста сообщений "
                    f"guard.py обновляются синхронно, не удаляются)")


if __name__ == "__main__":
    unittest.main()
