"""AC-15: `docs/retention.md` и справка `prune` в `orchestrator/artel.py`
называют промпты, каталоги `suite-run` и каталоги упразднённых механизмов.

Группа: разовый

Красен до реализации: раздел `.artel/logs/` в docs/retention.md не упоминает `*.prompt.txt` и `suite-run`, разделов «Каталоги упразднённых механизмов» и «Сессии ролей» нет; абзац о `prune` в модульной строке artel.py и строка `prune` перечня модулей говорят только о логах и alerts.

Планка провалидирована временным стабом правки документации (оба метода зелёные, стаб удалён, не закоммичен).

Тексты читаются из рабочей копии кода (`CODE_ROOT` помощника пульта):
это код задачи, не её артефакты. Сравнение — без различия `ё`/`е` и
регистра, по корням слов: формулировку выбирает разработчик.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402


def norm(text: str) -> str:
    return text.replace("ё", "е").replace("Ё", "Е").lower()


def sections(markdown: str) -> list:
    """(заголовок, текст раздела вместе с подразделами) для `##`-разделов."""
    out = []
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        body = []
        for nxt in lines[i + 1:]:
            if nxt.startswith("## ") or nxt.startswith("# "):
                break
            body.append(nxt)
        out.append((line, "\n".join(body)))
    return out


def section(markdown: str, *needles: str) -> tuple | None:
    for head, body in sections(markdown):
        if all(norm(n) in norm(head) for n in needles):
            return head, body
    return None


class RetentionDocsTest(unittest.TestCase):

    def test_ac15_retention_md_names_new_kinds(self):
        """docs/retention.md описывает новые виды и раздел о сессиях ролей.

        В разделе `.artel/logs/` — промпты `*.prompt.txt`, каталоги
        `.artel/logs/suite-run/<id>/` и их исключения (`lock.json`,
        `pending-journal/`, каталог задачи, держащей замок); раздел
        «Каталоги упразднённых механизмов» называет `.artel/notes-work`;
        есть раздел «Сессии ролей» с `.artel/home/.claude/projects`.

        Ловит мутацию: документация не дописана или дописана частично —
        например, в разделе логов нет исключения `pending-journal/` либо
        раздел о сессиях ролей не заведён — соответствующая проверка
        покраснеет.
        """
        text = (Path(CODE_ROOT) / "docs" / "retention.md").read_text(encoding="utf-8")

        logs = section(text, ".artel/logs/")
        self.assertIsNotNone(logs, "нет раздела `## … .artel/logs/ …`")
        body = norm(logs[0] + "\n" + logs[1])
        for needle in (".prompt.txt", "suite-run", "lock.json", "pending-journal"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        self.assertRegex(body, r"зам(ок|к)", "нет исключения каталога задачи, держащей замок")

        abolished = section(text, "Каталоги упразднённых механизмов")
        self.assertIsNotNone(abolished, "нет раздела «Каталоги упразднённых механизмов»")
        self.assertIn(".artel/notes-work", abolished[0] + abolished[1])

        sessions = section(text, "Сессии ролей")
        self.assertIsNotNone(sessions, "нет раздела «Сессии ролей»")
        self.assertIn(".artel/home/.claude/projects", sessions[0] + sessions[1])

    def test_ac15_artel_help_names_new_kinds(self):
        """Справка `prune` в artel.py называет промпты, `suite-run`, упразднённые.

        Абзац модульной строки документации, начинающийся с `prune`, и
        строка `prune` перечня модулей (с её строками-продолжениями) — оба
        содержат «промпт», «suite-run» и «упразднённ».

        Ловит мутацию: дописан только один из двух мест справки — абзац
        модульной строки или строка перечня модулей — проверка второго
        места покраснеет.
        """
        source = (Path(CODE_ROOT) / "orchestrator" / "artel.py").read_text(encoding="utf-8")
        doc = ast.get_docstring(ast.parse(source)) or ""

        paragraphs = [p for p in re.split(r"\n\s*\n", doc)
                      if p.lstrip().startswith("`prune")]
        self.assertTrue(paragraphs, "нет абзаца модульной строки о `prune`")
        lines = doc.splitlines()
        modules = next((i for i, line in enumerate(lines)
                        if line.startswith("Модули пакета")), None)
        self.assertIsNotNone(modules, "нет перечня «Модули пакета»")
        start = next((i for i, line in enumerate(lines)
                      if i > modules and re.match(r"  prune\s", line)), None)
        self.assertIsNotNone(start, "нет строки `prune` в перечне модулей")
        entry = [lines[start]]
        for line in lines[start + 1:]:
            if not re.match(r"  \s+\S", line):
                break
            entry.append(line)

        for place, text in (("абзац", "\n".join(paragraphs)),
                            ("перечень модулей", "\n".join(entry))):
            for needle in ("промпт", "suite-run", "упраздненн"):
                with self.subTest(place=place, needle=needle):
                    self.assertIn(needle, norm(text))


if __name__ == "__main__":
    unittest.main()
