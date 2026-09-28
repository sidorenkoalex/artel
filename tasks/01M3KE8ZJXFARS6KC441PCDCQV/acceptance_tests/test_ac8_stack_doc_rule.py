"""AC-8 — 01M3KE8ZJXFARS6KC441PCDCQV: раздел `docs/stack.md` о каталоге
моделей называет правило правки состава и не пересказывает сам состав.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Раздел `docs/stack.md` о каталоге моделей не перечисляет состав
каталога и называет правило: правка состава каталога идёт вместе с
правкой литерала `tests/test_models.py` и потому задачей, а не командой
`doc-commit`.

Раздел адресуется заголовком «Модели: каталог, ярусы, тариф»
(SPEC, «Материалы»), тело — до следующего заголовка того же уровня.

Красен до реализации: раздел сегодня говорит только «правит его Оператор
командой `doc-commit`» и про связь с литералом состава в
`tests/test_models.py` не знает — `assertIn` на имени файла падает.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

DOC_REL = "docs/stack.md"

#: Заголовок раздела о каталоге моделей (SPEC, «Материалы»).
SECTION_HEADING = re.compile(r"^##\s+Модели:.*$", re.MULTILINE)

#: Имя файла, где живёт литерал состава каталога (требование 3).
COMPOSITION_TEST = "tests/test_models.py"

#: Команда, которой правку состава вести НЕЛЬЗЯ (SPEC, «Контекст»).
DOC_COMMIT = "doc-commit"


def _section() -> str:
    """Тело раздела о каталоге моделей: от конца его заголовка до
    следующего заголовка уровня `## ` или конца файла. Подразделы
    (`### `) остаются внутри — они часть того же раздела."""
    text = (_catalog.REPO_ROOT / DOC_REL).read_text(encoding="utf-8")
    match = SECTION_HEADING.search(text)
    if match is None:
        return ""
    tail = text[match.end():]
    nxt = re.search(r"^##\s", tail, re.MULTILINE)
    return tail[:nxt.start()] if nxt else tail


def _paragraphs(body: str) -> list:
    return [block for block in re.split(r"\n\s*\n", body) if block.strip()]


class StackDocRuleTest(unittest.TestCase):

    def setUp(self):
        self.body = _section()
        self.assertTrue(
            self.body.strip(),
            f"{DOC_REL}: раздел «Модели: каталог, ярусы, тариф» не найден")

    def test_ac8_section_states_the_rule_about_the_composition_literal(self):
        """Раздел называет правило одним куском текста: правка состава
        каталога идёт вместе с литералом `tests/test_models.py` и потому
        задачей, а не командой `doc-commit`.

        Ловит мутацию: правило дописано наполовину — «состав каталога
        правится задачей», без имени файла с литералом: читатель, которому
        нужно понять, ПОЧЕМУ `doc-commit` не годится, снова пойдёт им и
        получит красный полный набор на отправке (ровно тот путь, из-за
        которого эта правка и идёт задачей).
        """
        near = [block for block in _paragraphs(self.body)
                if COMPOSITION_TEST in block]
        # Не `assertIn` по всему телу раздела: его текст на два экрана, и
        # стандартное сообщение о ненайденной подстроке вывалило бы его
        # целиком в отчёт гейта вместо диагноза.
        self.assertTrue(near,
                        f"{DOC_REL}: раздел не называет {COMPOSITION_TEST}")
        self.assertTrue(
            any(DOC_COMMIT in block and "задач" in block for block in near),
            f"{DOC_REL}: {COMPOSITION_TEST} назван, но рядом с ним нет "
            f"правила «задачей, а не командой {DOC_COMMIT}»")

    def test_ac8_section_does_not_list_the_catalog_composition(self):
        """Раздел не перечисляет состав каталога: имена моделей в нём —
        не весь новый состав.

        Ловит мутацию: правило дописали, а заодно «для наглядности»
        перенесли в документацию таблицу моделей из каталога — состав
        стал бы жить в двух местах, и следующая правка каталога тихо
        разошлась бы с документацией (ровно от этого критерий и
        страхует).
        """
        ids = sorted(_catalog.catalog().catalog.models)
        # Граница слова обязательна: `claude-opus-5` — подстрока
        # `claude-opus-5-5`, и без неё одно упоминание считалось бы двумя.
        named = [model_id for model_id in ids
                 if re.search(rf"(?<![\w.\-]){re.escape(model_id)}"
                              rf"(?![\w.\-])", self.body)]

        self.assertLess(
            len(named), len(ids),
            f"{DOC_REL}: раздел называет весь состав каталога "
            f"({', '.join(named)}) — состав живёт в самом каталоге")


if __name__ == "__main__":
    unittest.main()
