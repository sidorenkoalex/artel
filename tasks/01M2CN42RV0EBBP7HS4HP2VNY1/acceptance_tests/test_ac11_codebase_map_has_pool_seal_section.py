"""AC-11 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: `docs/codebase-map.md`
регенерирован (`python3 scripts/codebase_map.py`) и несёт секцию для
нового модуля `orchestrator/pool_seal.py` (требование 9).

Красен до реализации: секция `## orchestrator/pool_seal.py` отсутствует
— модуль ещё не существует, карта не может знать о нём.
"""
import sys
import unittest
from pathlib import Path

# AC-12: manual — PLAN.md разработчика (таблица переносов, подтверждение
# отката одним ревертом merge-коммита, сравнение вывода artel.py doctor/
# status до и после переноса) — содержательная оценка текста артефакта
# роли, не кода; тест на наличие ключевых слов был бы тавтологией (не
# доказывает, что таблица переносов верна или что сравнение вывода
# реально проведено) — решение принимает Оператор/ревьювер чтением
# PLAN.md.

REPO_ROOT = Path(__file__).resolve().parents[3]
MAP_PATH = REPO_ROOT / "docs" / "codebase-map.md"


class CodebaseMapHasPoolSealSectionTest(unittest.TestCase):

    def test_ac11_codebase_map_has_pool_seal_module_section(self):
        """Сценарий: ищем заголовок секции модуля в формате, которым
        карта озаглавливает существующие модули (`## orchestrator/
        canary.py` и т.п.) — для `orchestrator/pool_seal.py`.

        Ловит мутацию: разработчик перенёс код, но не выполнил
        требование 9 (`python3 scripts/codebase_map.py`) — карта не
        регенерирована, секции нового модуля в ней нет вовсе.
        """
        text = MAP_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "## orchestrator/pool_seal.py", text,
            "docs/codebase-map.md не несёт секцию нового модуля "
            "orchestrator/pool_seal.py — карта не регенерирована "
            "(python3 scripts/codebase_map.py)")


if __name__ == "__main__":
    unittest.main()
