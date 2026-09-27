"""AC-1 — 01M3HST1381E1FZCYAN2TSB1F3: указатель связки ключей в доме роли
клона, байт-в-байт равный указателю пульта.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. Прогон на наборе, где хотя бы одна роль идёт провайдером `codex`:
после подготовки клона в доме роли клона есть файл
`Library/Preferences/com.apple.security.plist`, байт-в-байт равный файлу
того же относительного пути дома роли пульта.

Наблюдение снимается ВНУТРИ клона — в момент, когда клон собран (холодный
старт клона прошёл), но задача ещё не заведена (`_util.CodexClonePlank
Sandbox.clone_probe`): «после подготовки клона» иначе не наблюдаемо, потому
что каталог клона умирает вместе с блоком.

Байты, а не текст: критерий говорит «байт-в-байт», и сверка через
`read_text` прошла бы на файле с переписанным переводом строки.

Предпосылка «хотя бы одна роль набора идёт провайдером codex» не
утверждается литералом: роли считаются той же картой «роль -> ярус ->
провайдер», которую собирает сам прогон (`_util.codex_roles_of_set`).

Красен до реализации: прогон канарейки указатель в дом роли клона не
переносит вовсе — файла по этому пути в клоне нет, и `assertTrue` падает
на его отсутствии.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config  # noqa: E402


class PointerInCloneRoleHomeTest(_util.CodexClonePlankSandbox):

    def test_ac1_clone_role_home_carries_the_pult_pointer_byte_for_byte(self):
        """Прогон на наборе с ролью на Codex: в доме роли клона лежит
        указатель связки ключей, равный указателю дома роли пульта
        байт-в-байт.

        Ловит мутацию: перенос сделан «созданием указателя заново» (пустой
        файл, файл с адресом связки, собранным по шаблону) вместо копии
        существующего — `codex login status` домом клона искал бы связку не
        там, где её нашёл вход Оператора, и шаг роли падал бы авторизацией
        ровно так, как до этой задачи.
        """
        self.assertTrue(_util.codex_roles_of_set(_util.SET_NAME),
                        "предпосылка: набор ведёт хотя бы одну роль "
                        "провайдером codex")

        probed = self.clone_probe(
            _util.SET_NAME,
            lambda: {"pointer": Path(config.ROLE_HOME) / _util.POINTER_REL,
                     "payload": self._read_pointer()}).probe

        self.assertTrue(probed, "наблюдение внутри клона не снято")
        self.assertIsNotNone(
            probed["payload"],
            f"указателя {_util.POINTER_REL} в доме роли клона нет: "
            f"{probed['pointer']}")
        self.assertEqual(self.pointer.read_bytes(), probed["payload"])

    def test_ac1_pointer_sits_at_the_same_relative_path_inside_the_clone(self):
        """Указатель в клоне лежит тем же ОТНОСИТЕЛЬНЫМ путём внутри дома
        роли, а сам дом роли клона — внутри каталога клона, не пульта.

        Ловит мутацию: копия положена по абсолютному пути дома роли ПУЛЬТА
        (переменная `config.ROLE_HOME` прочитана до входа в блок клона) —
        дом клона остался бы без указателя, а прогон при этом выглядел бы
        сделавшим перенос.
        """
        files, clone_root = self.clone_role_home_files(_util.SET_NAME)

        self.assertIn(_util.POINTER_REL, files,
                      f"файлы дома роли клона: {sorted(files)}")
        self.assertNotEqual(self.root, clone_root,
                            "прогон не заводил эфемерного клона вовсе")

    def _read_pointer(self):
        """Байты указателя дома роли клона (`None` — файла нет). Читается
        в момент наблюдения, изнутри клона: после выхода из блока каталог
        клона уже удалён."""
        path = Path(config.ROLE_HOME) / _util.POINTER_REL
        return path.read_bytes() if path.is_file() else None


if __name__ == "__main__":
    unittest.main()
