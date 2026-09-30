"""AC-4 — PLAN.md перечисляет тесты `tests/`, сверяющие `call_args`
подменённого `subprocess.run` на пути `environment_fingerprint` (или
пишет «не найдено»), и каждый перечисленный тест зелёный при любом
состоянии кэша `environment_fingerprint`.

Группа: разовый

Перечень читается из PLAN.md артефактной ветки задачи (`gitcmd.show`)
— единственный источник артефактов задачи в среде прогона гейта.
Тест в перечне узнаётся по идентификатору вида pytest
`tests/test_<файл>.py::<Класс>::<метод>` (или `tests/<файл>.py::<метод>`);
каждый такой идентификатор, указывающий на существующий в файле метод,
прогоняется в отдельном интерпретаторе (`_runner.py`) при пустом и при
заполненном кэше. Содержательная полнота поиска (описание, где искали)
— предмет ревью PLAN, а не этой проверки.

Красен до реализации: PLAN.md ещё не создан (его пишет роль developer) — в артефактной ветке его нет, тест падает на отсутствии перечня.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M3RHSS9S7GJXW28WMJKNC8YG"
RUN_TIMEOUT_SEC = 100

NODE_RE = re.compile(r"(tests/test_[A-Za-z0-9_]+\.py)((?:::[A-Za-z_][A-Za-z0-9_]*)+)")
NOT_FOUND_RE = re.compile(r"не\s+найден", re.IGNORECASE)


def plan_text():
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def listed_tests(text: str) -> list[tuple[str, str]]:
    """(файл, метод) каждого идентификатора, чей метод есть в файле."""
    found = []
    for file, tail in NODE_RE.findall(text):
        method = tail.rsplit("::", 1)[-1]
        path = REPO_ROOT / file
        if not method.startswith("test") or not path.is_file():
            continue
        if re.search(rf"def {re.escape(method)}\(", path.read_text(
                encoding="utf-8")) and (file, method) not in found:
            found.append((file, method))
    return found


class PlanListsCallArgsTestsTest(unittest.TestCase):

    def test_ac4_plan_lists_found_tests_and_each_is_cache_independent(self):
        """PLAN.md несёт перечень (или «не найдено»); перечисленное зелёное.

        Сценарий: из PLAN.md извлекаются идентификаторы тестов `tests/`;
        перечня нет — PLAN.md обязан сказать «не найдено». Каждый
        перечисленный тест прогоняется отдельно при пустом и при заранее
        заполненном кэше `environment_fingerprint` и обязан быть зелёным
        (код 0) в обоих случаях.

        Ловит мутацию: разработчик нашёл второй тест, сверяющий
        `run_mock.call_args` на пути fingerprint, внёс его в перечень, но
        не починил — при пустом кэше он видит `timeout=5` вызова
        `--version` и прогон падает с кодом 1; либо PLAN.md вовсе
        умалчивает о результате поиска — нет ни перечня, ни «не найдено».
        """
        text = plan_text()
        self.assertIsNotNone(text, "PLAN.md задачи нет в артефактной "
                                   "ветке")
        tests = listed_tests(text)
        if not tests:
            self.assertRegex(text, NOT_FOUND_RE,
                             "PLAN.md не перечисляет ни одного теста tests/ "
                             "и не говорит «не найдено»")
            return
        for file, method in tests:
            for cache in ("empty", "prefilled"):
                with self.subTest(test=f"{file}::{method}", cache=cache):
                    res = subprocess.run(
                        [sys.executable, str(HERE / "_runner.py"), cache,
                         "none", file, "-k", method],
                        cwd=REPO_ROOT, capture_output=True, text=True,
                        timeout=RUN_TIMEOUT_SEC)
                    self.assertEqual(
                        res.returncode, 0,
                        f"{file}::{method} красен при кэше {cache}:\n"
                        f"{(res.stdout + res.stderr)[-3000:]}")


if __name__ == "__main__":
    unittest.main()
