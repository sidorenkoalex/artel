"""`docs/retention.md` описывает уборку этой задачи: ссылки отслеживания
`origin` главной копии снимает `pin-update`, бесхозные каталоги
`.artel/worktrees/` убирает `prune`.

Группа: разовый
Красен до реализации: раздел «Ветки `task/*` пульта» не называет `pin-update` и `git remote prune origin`, а раздел «Worktree задачи» несёт фразу «`prune` этого вида не касается» и не говорит об уборке бесхозных каталогов.

Планка провалидирована временной правкой `docs/retention.md` (тест зелёный, правка откачена, не закоммичена).

Документ читается из рабочей копии кода (`CODE_ROOT` помощника пульта) —
это код ветки задачи, не артефакт `tasks/<id>/`. Раздел — текст от строки
заголовка `## …`, содержащей имя раздела, до следующего заголовка `## `.

AC-1..AC-7 — долгоживущие файлы `tests/test_01m5m675f6k2te7ttjn3aet4pp_pin_prune_refs.py`
(AC-1..AC-3) и `tests/test_01m5m675f6k2te7ttjn3aet4pp_worktrees_prune.py` (AC-4..AC-7).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

BRANCHES_SECTION = "Ветки `task/*` пульта"
WORKTREE_SECTION = "Worktree задачи"
REMOVED_PHRASE = "этого вида не касается"


def retention_text() -> str:
    return (Path(CODE_ROOT) / "docs" / "retention.md").read_text(encoding="utf-8")


def section(text: str, title: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.startswith("## ") and title in line), None)
    if start is None:
        raise AssertionError(f"в docs/retention.md нет раздела «{title}»")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


class RetentionDocTest(unittest.TestCase):

    def test_ac8_retention_names_pin_update_prune_and_orphan_worktrees(self):
        """Разделы документа называют новых исполнителей уборки, старой фразы нет.

        Раздел «Ветки `task/*` пульта» содержит `pin-update` и `git remote
        prune origin`; раздел «Worktree задачи» содержит `.artel/worktrees/`,
        `prune` и слово «бесхозн…»; во всём документе нет фразы
        «`prune` этого вида не касается» (ни с обратными кавычками, ни без).

        Ловит мутацию: правило о снятии ссылок записано не в раздел веток
        (например, в «Worktree задачи» или в конец документа) — в разделе
        веток нет `pin-update`; фраза «`prune` этого вида не касается»
        оставлена рядом с новым правилом — она находится в тексте.
        """
        text = retention_text()
        branches = section(text, BRANCHES_SECTION)
        for needle in ("pin-update", "git remote prune origin"):
            self.assertIn(needle, branches,
                          f"раздел «{BRANCHES_SECTION}» не называет {needle}")
        worktree = section(text, WORKTREE_SECTION)
        for needle in (".artel/worktrees/", "prune", "бесхозн"):
            self.assertIn(needle, worktree.lower(),
                          f"раздел «{WORKTREE_SECTION}» не называет {needle}")
        for phrase in (f"`prune` {REMOVED_PHRASE}", f"prune {REMOVED_PHRASE}"):
            self.assertNotIn(phrase, text, f"в документе осталась «{phrase}»")


if __name__ == "__main__":
    unittest.main()
