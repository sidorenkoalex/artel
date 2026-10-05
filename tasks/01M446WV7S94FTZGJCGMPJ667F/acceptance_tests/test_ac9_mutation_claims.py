"""Тесты `tests/`, добавленные и изменённые веткой задачи, несут заявки
«Ловит мутацию».

Группа: разовый

Зелёный с рождения: ветка уже несёт долгоживущий файл планки `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py` (AC-1…AC-5), у каждого метода которого есть «Ловит мутацию»; тест сторожит, что тесты разработчика на требования 1–4 (в том числе AC-6…AC-8) не придут без заявки.

Группа «разовый»: предмет — дифф `tests/` этой ветки против базы; после
мержа его не на чем проверять.

Дифф — от точки расхождения HEAD рабочей копии кода с `origin/<основная>`
(`gitcmd.diff_base`), с рабочим деревом и неотслеживаемыми файлами `tests/`.
Заявка проверяется тем же узлом, что гейт выхода из `in_dev`
(`guard.test_functions_without_mutation_claim`): новая или изменённая
функция `test_*` без «Ловит мутацию: <текст>» в докстринге.
"""
import re
import unittest

from _plank import CODE_ROOT, git

from orchestrator import gitcmd
from scripts import guard

TEST_FILE = re.compile(r"^tests/(.+/)?test_[^/]*\.py$")


def changed_test_files(base: str) -> tuple[list, list]:
    """(добавленные, изменённые) пути `tests/test_*.py` ветки от `base`:
    коммиты, рабочее дерево и неотслеживаемые файлы."""
    res = git("diff", "--name-status", "--no-renames", base, "--", "tests")
    assert res.returncode == 0, res.stderr
    added, modified = set(), set()
    for line in res.stdout.splitlines():
        status, _, path = line.partition("\t")
        if not TEST_FILE.match(path) or status.startswith("D"):
            continue
        (added if status.startswith("A") else modified).add(path)
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "tests")
    assert untracked.returncode == 0, untracked.stderr
    added |= {p for p in untracked.stdout.split() if TEST_FILE.match(p)}
    return sorted(added), sorted(modified)


def show_base(base: str, path: str) -> str | None:
    res = git("show", f"{base}:{path}")
    return res.stdout if res.returncode == 0 else None


class MutationClaimsTest(unittest.TestCase):

    def test_ac9_branch_tests_carry_mutation_claims(self):
        """Каждая новая или изменённая веткой функция `test_*` в `tests/` несёт «Ловит мутацию».

        Сценарий: база — `gitcmd.diff_base("HEAD")` рабочей копии кода;
        собираются добавленные и изменённые веткой `tests/test_*.py`
        (среди добавленных есть хотя бы один — тесты задачи в `tests/`
        есть); для каждого `guard.test_functions_without_mutation_claim`
        (база файла, HEAD файла) пуст.

        Ловит мутацию: разработчик добавляет в `tests/` тест на досылку
        закрытой ссылки из главной копии или на порядок `doctor --fix`
        без строки «Ловит мутацию: …» в докстринге — узел гейта называет
        этот метод.
        """
        base = gitcmd.diff_base("HEAD", repo=CODE_ROOT)
        self.assertTrue(base, "база диффа ветки задачи не вычислена")
        added, modified = changed_test_files(base)
        self.assertTrue(added, "ветка не добавила ни одного tests/test_*.py")
        unclaimed = []
        for path in added + modified:
            head_src = (CODE_ROOT / path).read_text(encoding="utf-8")
            base_src = None if path in added else show_base(base, path)
            unclaimed += [f"{path}::{name}" for name in
                          guard.test_functions_without_mutation_claim(
                              base_src, head_src)]
        self.assertEqual(unclaimed, [], "методы без «Ловит мутацию»")


if __name__ == "__main__":
    unittest.main()
