"""AC-9: число тестовых методов в каждом изменённом файле `tests/` не
уменьшилось по сравнению с базой сравнения ветки.

«Изменённый файл» и «тестовый метод» считаются тем же кодом, каким их
считает сам пульт: точка расхождения с главной веткой — `gitcmd.diff_base`
(`origin/<main>`, если ref заведён, иначе локальная главная ветка), разбор
методов — `scripts/guard.py::qualified_test_methods` (там же живёт ответ на
вопрос, что считается тестовым методом, — и одноимённые методы разных
классов одного файла он различает). Своего разбора планка не заводит:
расхождение двух счётчиков иначе обнаруживалось бы разными числами в
разных местах.

Зелёный с рождения: до правки разработчика ни один файл `tests/` от базы
сравнения ветки не отличается, перечень изменённых пуст, и проверять
нечего. Тест сторожит саму правку — он становится содержательным ровно в
тот момент, когда разработчик трогает `tests/`, а зона задачи — целиком
`tests/`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from scripts import guard  # noqa: E402


class TestMethodsNotLostTest(unittest.TestCase):
    """Сверка изменённых файлов `tests/` с базой сравнения ветки."""

    def test_ac9_changed_tests_files_keep_their_test_methods(self):
        """Для каждого файла `tests/`, чей текст отличается от текста в
        точке расхождения ветки задачи с главной веткой, число тестовых
        методов не меньше прежнего.

        Ловит мутацию: перевод файла на общую фикстуру песочницы сделал
        один из его сценариев «лишним» (например, сценарий, который
        задавал карту сам), и разработчик удаляет этот тестовый метод
        вместо того, чтобы переписать его на фикстуру, — покрытие тихо
        уменьшается, а SPEC («Не входит») удаление тестовых методов
        запрещает без мандата Оператора.
        """
        base = _util.main_base_ref()
        self.assertTrue(
            base, "git не ответил на запрос точки расхождения ветки задачи с "
                  "главной веткой — сверить число тестов не с чем")

        for rel in _util.changed_tests_files(base):
            with self.subTest(file=rel):
                before = guard.qualified_test_methods(_util.text_at(base, rel))
                after = guard.qualified_test_methods(_util.text_on_disk(rel))

                self.assertGreaterEqual(
                    len(after), len(before),
                    f"{rel}: было {len(before)} тестовых методов, стало "
                    f"{len(after)}; исчезли: "
                    f"{sorted(set(before) - set(after))}")


if __name__ == "__main__":
    unittest.main()
