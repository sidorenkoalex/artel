"""Приёмочный тест AC-7: `skills/test-authoring.md` фиксирует правило —
лёгкую песочницу не переписывать заново, импортировать из `tests/
sandbox.py`; локальный `_sandbox.py` планки — только тонкая надстройка
сценария (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J, требование 3).

Красен до реализации: скил сегодня не несёт этого правила вовсе —
искомые подстроки в его тексте отсутствуют.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = REPO_ROOT / "skills" / "test-authoring.md"


class SkillTestAuthoringSandboxRuleTest(unittest.TestCase):

    def test_ac7_skill_names_sandbox_module_and_thin_overlay_rule(self):
        """Текст скила называет `tests/sandbox.py` источником эталона,
        запрещает переписывание лёгкой песочницы заново и описывает
        локальный `_sandbox.py` планки как тонкую надстройку сценария.

        Ловит мутацию: правило убрано из скила (или никогда не
        добавлено) при последующей правке — одна из проверок ниже не
        найдёт нужной подстроки.
        """
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("tests/sandbox.py", text,
                      "скил обязан называть tests/sandbox.py источником "
                      "эталона")
        self.assertIn("_sandbox.py", text,
                      "скил обязан упоминать локальный _sandbox.py "
                      "планки")
        self.assertIn("не переписывать", text,
                      "правило обязано явно запрещать переписывание "
                      "лёгкой песочницы заново")
        self.assertIn("надстройк", text,
                      "правило обязано называть локальный _sandbox.py "
                      "планки тонкой надстройкой сценария")


if __name__ == "__main__":
    unittest.main()
