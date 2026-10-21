"""Абзац `docs/retention.md` об удалении ветки задачи в `origin` после мержа.

Группа: разовый

Красен до реализации: в разделе «Ветки `task/*` пульта» пока нет ни слова об `origin` проекта и о PR — проверки содержания раздела падают.

Документ читается из рабочей копии кода (`CODE_ROOT` помощника пульта) —
это файл кодовой ветки, не артефакт задачи. Проверяются смысловые опоры
абзаца, а не его дословный текст.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

SECTION = "## Ветки `task/*` пульта"


def _section_text() -> str:
    text = (Path(CODE_ROOT) / "docs" / "retention.md").read_text(encoding="utf-8")
    start = text.find(SECTION)
    if start < 0:
        return ""
    body = text[start + len(SECTION):]
    nxt = re.search(r"^## ", body, re.M)
    return body[:nxt.start()] if nxt else body


def _paragraphs(section: str) -> list:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", section)
            if p.strip()]


class RetentionDocTest(unittest.TestCase):

    def test_ac9_retention_paragraph_on_origin_branch_and_pr(self):
        """Раздел «Ветки `task/*` пульта» несёт абзац об удалении ветки в `origin` после мержа и фразу о PR.

        Сценарий: в разделе находится абзац, где сказано про `origin`
        проекта, условие «голова входит в смерженный main», сбой удаления
        оставляет ветку и пишется в журнал записью «уборка» с причиной,
        печатается подсказка ручной команды; в том же абзаце — что удаление
        head-ветки на GitHub закрывает открытый PR, push в базу обычно уже
        помечает PR смерженным, конечный статус PR сверяется на первом
        мерже после внедрения.

        Ловит мутацию: абзац не добавлен или добавлен в другой раздел — в
        разделе нет абзаца с `origin`; из абзаца выпала оговорка о PR или
        об условии головы — нет соответствующей опоры.
        """
        section = _section_text()
        self.assertTrue(section, f"нет раздела {SECTION!r}")
        hits = [p for p in _paragraphs(section) if "origin" in p and "PR" in p]
        self.assertTrue(hits, f"нет абзаца об origin и PR в разделе:\n{section}")
        para = hits[0]
        low = para.lower()
        checks = {
            "после мержа": "мерж" in low,
            "голова входит в смерженный main": "голов" in low
            and "смерж" in low and "main" in low,
            "сбой оставляет ветку": "сбой" in low and "оставл" in low,
            "запись «уборка» в журнале": "журнал" in low and "уборк" in low,
            "причина": "причин" in low,
            "подсказка ручной команды": "подсказк" in low,
            "GitHub закрывает открытый PR": "github" in low
            and "закрыва" in low and "открыт" in low,
            "push в базу помечает PR смерженным": "push" in low
            and "смерженн" in low,
            "сверка на первом мерже после внедрения": "перв" in low
            and "внедрен" in low,
        }
        missing = [k for k, ok in checks.items() if not ok]
        self.assertEqual(missing, [], f"в абзаце нет опор {missing}:\n{para}")


if __name__ == "__main__":
    unittest.main()
