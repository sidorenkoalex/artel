"""AC-3 — долгоживущий файл задачи 01M3SE87R3M7HGWX8HG1ANAKR0 не тронут и зелёный.

Поведенческая часть AC-3 (прежние основания признака достаточны, пустой
маркер при чужом HOME — не роль) — в долгоживущем файле задачи
`tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py::HomePredicateTest::
test_ac3_prior_grounds_remain_sufficient`. Здесь — факт этой задачи: файл
`tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py` сохраняет хэш,
запертый перечнем сумм той задачи, и проходит без правки.

Группа: разовый
Зелёный с рождения: файл 01M3SE87 сегодня не тронут и зелёный — планка держит, что реализация признака не потребует его правки.
"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plank  # noqa: E402

PRIOR_FILE_REL = "tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py"
PRIOR_LOCK_REL = ("tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests/"
                  "long_lived.sha256.txt")


class PriorLongLivedFileTest(unittest.TestCase):
    def test_ac3_prior_file_keeps_locked_hash(self):
        """Сумма файла 01M3SE87 в дереве задачи совпадает с запертой.

        Перечень сумм читается из базы диффа задачи (git, не диск), сумма
        файла — по его байтам в чекауте планки.

        Ловит мутацию: разработчик «подстроил» `test_ac1`/`test_ac5` файла
        01M3SE87 под новое правило HOME — sha256 файла расходится с
        записью перечня, и тест краснеет с обеими суммами в тексте.
        """
        base = _plank.diff_base()
        self.assertIsNotNone(base, "git не ответил на базу диффа задачи")
        lock = _plank.show_at(base, PRIOR_LOCK_REL)
        self.assertIsNotNone(lock, f"{PRIOR_LOCK_REL} нет в базе {base}")
        locked = {line.split()[1]: line.split()[0]
                  for line in lock.splitlines() if len(line.split()) == 2}
        self.assertIn(PRIOR_FILE_REL, locked, f"перечень сумм: {lock!r}")
        actual = hashlib.sha256(
            (_plank.REPO_ROOT / PRIOR_FILE_REL).read_bytes()).hexdigest()
        self.assertEqual(locked[PRIOR_FILE_REL], actual,
                         f"{PRIOR_FILE_REL} изменён: заперто "
                         f"{locked[PRIOR_FILE_REL]}, сейчас {actual}")

    def test_ac3_prior_file_passes(self):
        """Файл 01M3SE87 целиком проходит отдельным прогоном pytest.

        Ловит мутацию: новое правило HOME вытеснило ветку маркера или
        пустой маркер при чужом HOME стал ролью — `test_ac1` файла 01M3SE87
        краснеет, код возврата прогона ненулевой.
        """
        res = _plank.run_pytest([PRIOR_FILE_REL])
        self.assertEqual(0, res.returncode,
                         f"{PRIOR_FILE_REL} красный:\n{_plank.tail(res)}")


if __name__ == "__main__":
    unittest.main()
