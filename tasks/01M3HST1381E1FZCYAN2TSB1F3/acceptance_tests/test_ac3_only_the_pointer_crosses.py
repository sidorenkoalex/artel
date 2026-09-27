"""AC-3 — 01M3HST1381E1FZCYAN2TSB1F3: кроме указателя, из дома роли пульта
в дом клона не попадает ни один файл.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Кроме указателя, из дома роли пульта в дом клона не попадает ни один
файл: перечень файлов, лежащих в доме клона под `Library/`, — ровно один
этот путь; файлы дома роли пульта, добавленные помимо указателя, в доме
клона не появляются.

Дом роли ПУЛЬТА в песочнице засеян не одним указателем: рядом с ним лежит
второй plist того же каталога `Preferences/`, файл соседнего каталога
`Keychains/`, посторонний файл внутри `.claude/` и файл в корне дома
(`_util.PULT_ONLY_FILES`). Без такого посева «скопировали ровно указатель»,
«скопировали весь `Preferences/`», «скопировали весь `Library/`» и
«скопировали дом целиком» давали бы одно и то же наблюдение.

Наблюдение снимается ВНУТРИ клона, после его подготовки: каталог клона
умирает вместе с блоком.

Красен до реализации: указателя в доме клона сегодня нет вовсе, поэтому
перечень файлов под `Library/` пуст, а не равен одному пути — `assertEqual`
падает на пустом перечне.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

#: Первый сегмент пути указателя — каталог, весь перечень которого критерий
#: и фиксирует. Берётся из самого пути, не отдельным литералом.
LIBRARY_DIR = _util.POINTER_REL.split("/")[0]


class OnlyThePointerCrossesTest(_util.CodexClonePlankSandbox):

    def test_ac3_library_of_the_clone_role_home_holds_exactly_the_pointer(self):
        """Перечень файлов дома роли клона под `Library/` — ровно один путь
        указателя.

        Ловит мутацию: перенос сделан копией каталога (`copytree` на
        `Library/` или на `Library/Preferences/`) вместо копии одного файла
        — в дом клона уехали бы и соседний plist, и содержимое каталога
        связок, то есть требование изоляции (требование 5) нарушилось бы
        ровно тем действием, которым задача его и должна была сохранить.
        """
        files, _root = self.clone_role_home_files(_util.SET_NAME)

        under_library = sorted(rel for rel in files
                               if rel.split("/")[0] == LIBRARY_DIR)

        self.assertEqual([_util.POINTER_REL], under_library)

    def test_ac3_no_other_file_of_the_pult_role_home_appears_in_the_clone(self):
        """Ни один посторонний файл дома роли пульта в доме клона не
        появляется, а сам дом клона остаётся холодным старт плюс указатель.

        Ловит мутацию: дом роли клона собран копией дома роли ПУЛЬТА
        целиком (вместо холодного старта плюс один файл) — в клон уехали бы
        правки Оператора в `.claude/`, его личные файлы и содержимое связки
        ключей, а расхождение дома клона с референсом перестало бы быть
        наблюдаемым.
        """
        files, _root = self.clone_role_home_files(_util.SET_NAME)

        leaked = sorted(rel for rel in _util.PULT_ONLY_FILES if rel in files)

        self.assertEqual([], leaked, f"файлы дома роли пульта в клоне: "
                                     f"{leaked}; весь дом клона: "
                                     f"{sorted(files)}")
        self.assertEqual(
            _util.cold_start_role_home_files() | {_util.POINTER_REL}, files)

    def test_ac3_pult_only_files_really_exist_before_the_run(self):
        """Предпосылка сценария: посторонние файлы в доме роли пульта
        действительно лежат — и лежат в тех же двух каталогах, где критерий
        различает копию файла и копию каталога.

        Ловит мутацию: посев песочницы перестал класть посторонние файлы
        (переименован каталог, изменён состав `PULT_ONLY_FILES`) — оба
        метода выше зеленели бы на пустом доме роли пульта, не проверяя
        ничего. Самопроверка фикстуры, без которой планка становится
        имитацией.
        """
        present = _util.files_under(self.pult_home)

        self.assertEqual(set(), set(_util.PULT_ONLY_FILES) - present,
                         sorted(present))
        self.assertIn(_util.POINTER_REL, present)
        neighbours = [rel for rel in _util.PULT_ONLY_FILES
                      if rel.startswith(LIBRARY_DIR + "/")]
        self.assertTrue(
            len(neighbours) >= 2,
            f"под {LIBRARY_DIR}/ нужен минимум один сосед указателя и один "
            f"файл соседнего каталога: {neighbours}")


if __name__ == "__main__":
    unittest.main()
