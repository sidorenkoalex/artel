"""Факты задачи: перечень команд роли, докстринг и карта `retro_corpus`,
покрытие девяти сценариев постоянными тестами `tests/`.

Поведенческие критерии (AC-1…AC-14) проверяют долгоживущие файлы задачи в
`tests/` кодовой ветки (`tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py`,
`tests/test_01m41vtse5n15p5p2wzf4gf2bq_branches_cleanup.py`); здесь — то,
что держится на тексте и составе файлов этой задачи.

Группа: разовый
Красен до реализации: докстринг orchestrator/retro_corpus.py и его секция в docs/codebase-map.md ещё не называют docs --fetch-all — метод AC-11 красный; методы AC-9 (перечня без новых команд) и AC-15 (долгоживущие файлы задачи уже в tests/) зелёные с рождения.
"""
import ast
import unittest
from pathlib import Path

from orchestrator import artel, config, retro_corpus

TASK_PREFIX = "test_01m41vtse5n15p5p2wzf4gf2bq_"
FETCH_ALL = "docs --fetch-all"
MAP_SECTION = "## orchestrator/retro_corpus.py"

#: Девять сценариев требования 7 SPEC -> номер критерия, чьё имя метода
#: `test_ac<n>_…` в постоянном тесте закрывает сценарий.
SCENARIOS = {
    "docs подтягивает версию origin новее локальной": 1,
    "docs без локальной ссылки": 2,
    "--fetch-all приносит ссылку, которой нет локально": 8,
    "чтение исторического снимка": 4,
    "docs для внешнего проекта читает его origin": 5,
    "show без локальной ссылки называет docs": 10,
    "предпросмотр уборки ничего не удаляет": 12,
    "уборка отказывает при задаче без ссылки в origin": 13,
    "уборка удаляет ветки origin и локальные": 14,
}


def repo_root() -> Path:
    return Path(config.ROOT)


class RoleWhitelistTest(unittest.TestCase):

    def test_ac9_whitelist_lacks_new_commands(self):
        """Белый список команд роли не несёт ни `docs`, ни уборку веток.

        Зелёный с рождения: держит, что команды не внесены в
        `_ROLE_ALLOWED_COMMANDS` при их регистрации в диспетчере.
        Ловит мутацию: разработчик добавил `docs` (как «читающую») или
        `artifact-branches-cleanup` в `_ROLE_ALLOWED_COMMANDS` — элемент
        появляется в множестве.
        """
        for cmd in ("docs", "artifact-branches-cleanup"):
            self.assertNotIn(cmd, artel._ROLE_ALLOWED_COMMANDS,
                             f"{cmd} в белом списке команд роли")


class RetroCorpusDocTest(unittest.TestCase):

    def test_ac11_docstring_and_map_name_fetch_all(self):
        """Докстринг `retro_corpus` и его секция карты называют `docs --fetch-all`.

        Модульный докстринг `orchestrator/retro_corpus.py` содержит
        `docs --fetch-all`; секция `## orchestrator/retro_corpus.py` в
        `docs/codebase-map.md` (до следующего заголовка `## `) — тоже: карта
        берёт первую строку докстринга и регенерирована генератором.

        Ловит мутацию: способ наполнения корпуса дописан в хвост докстринга, а
        не в первую строку, или карта не регенерирована — в секции карты нет
        `docs --fetch-all`.
        """
        self.assertIn(FETCH_ALL, retro_corpus.__doc__ or "",
                      "докстринг retro_corpus не называет docs --fetch-all")
        text = (repo_root() / "docs" / "codebase-map.md").read_text(
            encoding="utf-8")
        start = text.find(MAP_SECTION + "\n")
        self.assertNotEqual(start, -1, "в карте нет секции retro_corpus")
        end = text.find("\n## ", start + len(MAP_SECTION))
        section = text[start:end if end != -1 else len(text)]
        self.assertIn(FETCH_ALL, section,
                      f"секция карты не называет docs --fetch-all:\n{section}")


class PermanentTestsCoverageTest(unittest.TestCase):

    def test_ac15_nine_scenarios_have_permanent_tests(self):
        """Каждый из девяти сценариев закрыт методом постоянного теста с заявкой мутации.

        Зелёный с рождения: долгоживущие файлы задачи `tests/test_<id>_*.py`
        пишет test_author, пульт кладёт их в кодовую ветку. Для каждого
        сценария требования 7 в этих файлах есть метод `test_ac<n>_…`,
        докстринг которого несёт строку «Ловит мутацию:».
        Ловит мутацию: долгоживущий файл задачи не попал в `tests/` кодовой
        ветки (потерян чекпоинтом или удалён) — метода сценария нет.
        """
        files = sorted((repo_root() / "tests").glob(f"{TASK_PREFIX}*.py"))
        self.assertTrue(files, "в tests/ нет долгоживущих файлов задачи")
        claimed: dict = {}
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.FunctionDef)
                        and node.name.startswith("test_ac")):
                    doc = ast.get_docstring(node) or ""
                    if "Ловит мутацию:" in doc:
                        claimed.setdefault(node.name, path.name)
        for scenario, n in SCENARIOS.items():
            hits = [m for m in claimed if m.startswith(f"test_ac{n}_")]
            self.assertTrue(hits, f"сценарий «{scenario}» (AC-{n}) без "
                                  f"постоянного теста с «Ловит мутацию:»")


if __name__ == "__main__":
    unittest.main()
