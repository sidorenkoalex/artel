"""SPEC задачи несёт готовый текст правки раздела о долгоживущих файлах skills/test-authoring.md.

Группа: разовый
Зелёный с рождения: текст правки — факт SPEC.md этой задачи (раздел «Материалы»), написан аналитиком до планки; тест держит, что он там есть и годен Оператору для `doc-commit`.

SPEC.md читается из ссылки документов задачи помощником пульта
(`_pult.artifact_text`), файл навыка — из рабочей копии кода
(`_pult.CODE_ROOT`): защищённый путь в ветке задачи не меняется, поэтому
«Было» обязано совпадать с его текущим текстом.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

SKILL = "skills/test-authoring.md"
HEADING = "### Готовый текст правки `skills/test-authoring.md`"


def blocks_after(text: str, heading: str) -> list[str]:
    """Блоки ``` … ``` раздела, начинающегося заголовком `heading`."""
    start = text.index(heading)
    tail = text[start + len(heading):]
    nxt = re.search(r"^#{1,3} ", tail, re.M)
    section = tail[:nxt.start()] if nxt else tail
    return re.findall(r"^```\n(.*?)^```", section, re.M | re.S)


def squash(text: str) -> str:
    return " ".join(text.split())


class Ac8SkillPatchTextTest(unittest.TestCase):

    def test_ac8_spec_carries_ready_skill_patch(self):
        """В «Материалах» SPEC — пара «Было»/«Стало» для абзаца о долгоживущих файлах навыка.

        «Было» дословно (с точностью до переносов строк) входит в текущий
        `skills/test-authoring.md`; «Стало» вместо буквального `tests/`
        называет каталог долгоживущих тестов проекта из задания роли и
        сохраняет правила артели: её каталог `tests/`, шаблон
        `tests/test_<id задачи в нижнем регистре>_<имя>.py`, откат правок
        на чекпоинте, перечень сумм `long_lived.sha256.txt`.

        Ловит мутацию: правка SPEC убрала готовый текст или «Было»
        разошлось с навыком (Оператор не сможет внести правку
        `doc-commit`), либо «Стало» по-прежнему говорит только о `tests/`
        кодовой ветки — тест покраснеет.
        """
        spec = artifact_text("SPEC.md")
        self.assertIsNotNone(spec, "SPEC.md нет в ссылке документов")
        self.assertIn(HEADING, spec)
        blocks = blocks_after(spec, HEADING)
        self.assertGreaterEqual(len(blocks), 2, "нет пары блоков Было/Стало")
        before, after = blocks[0], blocks[1]
        skill = (Path(CODE_ROOT) / SKILL).read_text(encoding="utf-8")
        self.assertIn(squash(before), squash(skill),
                      "«Было» не совпадает с текущим текстом навыка")
        self.assertIn("`tests/` кодовой ветки задачи", squash(before))
        flat = squash(after)
        self.assertNotEqual(squash(before), flat)
        self.assertIn("каталог долгоживущих тестов проекта", flat)
        self.assertIn("в задании роли", flat)
        self.assertIn("у артели — `tests/`", flat)
        self.assertIn("`tests/test_<id задачи в нижнем регистре>_<имя>.py`", flat)
        self.assertIn("пульт откатывает на чекпоинте шага", flat)
        self.assertIn("long_lived.sha256.txt", flat)
        self.assertNotIn("`tests/` кодовой ветки задачи", flat)


if __name__ == "__main__":
    unittest.main()
