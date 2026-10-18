"""`config.COMMON_ZONES` в ветке задачи не изменён.

Группа: разовый
Зелёный с рождения: задача не правит `orchestrator/config.py` (не входит в её зоны), значение `COMMON_ZONES` на базе диффа и в HEAD ветки совпадает; тест держит, что реализация расширения зон по профилю не идёт через дописывание каталога профиля в `COMMON_ZONES`.

Свойства этой задачи (AC-1..AC-7, AC-9) — в долгоживущем файле
`tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py`.

Значение `COMMON_ZONES` берётся разбором `orchestrator/config.py` (ast,
`literal_eval` присваивания) из двух ревизий рабочей копии кода: базы диффа
задачи (`_pult.DIFF_BASE` — та же база, что у гейта зон) и HEAD ветки.
Стаб-мутация потребовала бы коммита в ветку задачи — вместо неё разбор
проверен вручную: на HEAD он возвращает кортеж, содержащий `tests/`.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

CONFIG = "orchestrator/config.py"


def common_zones_at(revision: str):
    """Значение `COMMON_ZONES` в `orchestrator/config.py` ревизии."""
    res = subprocess.run(["git", "-C", CODE_ROOT, "show",
                          f"{revision}:{CONFIG}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git show {revision}:{CONFIG}: {res.stderr}")
    for node in ast.walk(ast.parse(res.stdout)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == "COMMON_ZONES"
               for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"в {revision}:{CONFIG} нет присваивания COMMON_ZONES")


class Ac8CommonZonesUnchangedTest(unittest.TestCase):

    def test_ac8_common_zones_same_at_base_and_head(self):
        """Значение `COMMON_ZONES` на базе диффа задачи и в HEAD её ветки одинаково.

        Ловит мутацию: реализация расширяет зоны чекпоинта дописыванием
        каталога профиля (`backend/tests/`) в `config.COMMON_ZONES` —
        значения на базе и в HEAD разойдутся.
        """
        self.assertTrue(DIFF_BASE, "база диффа задачи не определена пультом")
        self.assertEqual(common_zones_at("HEAD"), common_zones_at(DIFF_BASE),
                         "config.COMMON_ZONES изменён в ветке задачи")


if __name__ == "__main__":
    unittest.main()
