"""Абзац политики об удалении ветки задачи в `origin` после мержа в `docs/retention.md`.

Группа: разовый

Красен до реализации: раздел «Ветки `task/*` пульта» говорит только об удалении локальной ветки — слов об `origin`, голове ветки, записи «уборка», подсказке и PR в нём нет.

Документ читается из рабочей копии кода (`CODE_ROOT` помощника пульта) —
это файл кода задачи, не её артефакт. Разовый: проверяет текст, внесённый
этой задачей.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

DOC = "docs/retention.md"
HEADING = "## Ветки `task/*` пульта"

# Утверждения абзаца AC-9 и признаки каждого (подстроки в нижнем регистре;
# достаточно одной из перечисленных форм).
CLAIMS = {
    "ветка удаляется и в origin проекта": ("origin",),
    "условие — голова входит в смерженный main": ("голов",),
    "смерженный main": ("смержен", "влит"),
    "сбой пишется в журнал записью «уборка»": ("«уборка»", "уборка"),
    "запись журнала": ("журнал",),
    "причина сбоя": ("причин",),
    "подсказка ручной команды": ("подсказк",),
    "удаление head-ветки закрывает PR": ("закрывает", "закрыва"),
    "PR": ("pr",),
    "push в базу помечает PR смерженным": ("помечает", "помеча"),
    "сверка на первом мерже после внедрения": ("внедрени",),
}


def _section(text: str) -> str | None:
    lines = text.splitlines()
    try:
        start = lines.index(HEADING)
    except ValueError:
        return None
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        body.append(line)
    return "\n".join(body)


class RetentionDocTest(unittest.TestCase):

    def test_ac9_section_describes_origin_branch_removal(self):
        """Раздел «Ветки `task/*` пульта» несёт каждое утверждение абзаца AC-9.

        Сценарий: читается `docs/retention.md` рабочей копии, выделяется
        текст раздела до следующего заголовка; для каждого утверждения
        абзаца (удаление в `origin`, условие по голове и смерженному
        main, запись «уборка» с причиной, подсказка ручной команды,
        закрытие PR удалением head-ветки, пометка PR смерженным, сверка на
        первом мерже после внедрения) в тексте раздела есть его признак.

        Ловит мутацию: абзац не добавлен или добавлен в другой раздел —
        признаков `origin`/`подсказк`/`внедрени` в разделе нет; из абзаца
        выпала фраза о PR — нет признаков «закрывает»/«помечает».
        """
        path = Path(CODE_ROOT) / DOC
        self.assertTrue(path.is_file(), f"нет {DOC}")
        section = _section(path.read_text(encoding="utf-8"))
        self.assertIsNotNone(section, f"в {DOC} нет раздела «{HEADING}»")
        low = section.lower()
        missing = [claim for claim, marks in CLAIMS.items()
                   if not any(mark in low for mark in marks)]
        self.assertEqual(missing, [],
                         f"раздел «{HEADING}» не несёт утверждений: {missing}"
                         f"\n---\n{section}")


if __name__ == "__main__":
    unittest.main()
