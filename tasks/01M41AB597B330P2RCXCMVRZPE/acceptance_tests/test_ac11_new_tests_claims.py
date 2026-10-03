"""Каждый новый тест задачи в `tests/` несёт заявку «Ловит мутацию».

Группа: разовый

Зелёный с рождения: до реализации ветка уже несёт долгоживущий файл планки `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`, у каждого метода которого есть «Ловит мутацию»; тест сторожит, что тесты, добавленные разработчиком, не придут без заявки.

Группа «разовый»: предмет — дифф `tests/` этой ветки против базы; после
мержа его не на чем проверять.

Дифф — от точки расхождения HEAD рабочей копии кода с `origin/<основная>`
(`gitcmd.diff_base`), с рабочим деревом и неотслеживаемыми файлами
`tests/`. Новый тест — функция `test_*` добавленного файла `tests/test_*.py`
либо новая/изменённая функция `test_*` изменённого файла; заявка — тем же
узлом, что гейт выхода из `in_dev` (`guard.test_functions_without_mutation_claim`).

Здесь же — пометка критерия AC-6 (комментарий ниже): свойство «один узел
сравнения» — устройство кода, его сверяет ревьюер по диффу.
"""
# AC-6: manual — «одна точка сравнения головы ссылки с tasks.fixed_sha, без копий в местах вызова» — устройство кода, а не поведение: SPEC не называет узел, и один узел неотличим от N одинаковых копий ни по выводу, ни по журналу, ни по состоянию; тест по тексту исходников навязал бы имя узла или форму сравнения (тест-навязывает-устройство). Ревьюер сверяет по диффу: все места требования 1 (set_state, answer и zones-extend, amend-tests, snapshot, doctor/ignored_artifacts, оба чекпоинта, прежние места _docs_ref_moved_past_pult, kill) зовут один узел, отдельного сравнения fixed_sha с головой ссылки в них нет.
import re
import unittest

from _plank import CODE_ROOT, diff_base, git

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


class NewTestsMutationClaimTest(unittest.TestCase):

    def test_ac11_new_tests_carry_mutation_claim(self):
        """Ни у одного нового или изменённого веткой теста `tests/` нет пропуска заявки «Ловит мутацию».

        Сценарий: от базы диффа ветки собираются добавленные и изменённые
        `tests/test_*.py`; для каждого узел гейта выхода из `in_dev`
        называет функции `test_*` без «Ловит мутацию: …» (новые и
        изменённые относительно базы). Список пуст; хотя бы один файл
        тестов задачей добавлен (требование 9 — сторожа в `tests/`).

        Ловит мутацию: разработчик добавляет постоянный тест (например,
        на узел сверки или на `kill`) без строки «Ловит мутацию» — узел
        гейта его называет.
        """
        base = diff_base()
        self.assertTrue(base, "база диффа ветки задачи не вычислена")
        added, modified = changed_test_files(base)
        self.assertTrue(added, "ветка не добавила ни одного файла tests/test_*.py")
        unclaimed = []
        for path in added + modified:
            head_src = (CODE_ROOT / path).read_text(encoding="utf-8")
            base_res = git("show", f"{base}:{path}")
            base_src = base_res.stdout if (path in modified
                                           and base_res.returncode == 0) else None
            unclaimed += [f"{path}::{name}" for name in
                          guard.test_functions_without_mutation_claim(
                              base_src, head_src)]
        self.assertEqual(unclaimed, [], "тесты без «Ловит мутацию»")


if __name__ == "__main__":
    unittest.main()
