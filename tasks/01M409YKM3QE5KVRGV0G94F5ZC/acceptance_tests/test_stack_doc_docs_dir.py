"""`docs/stack.md` описывает каталог документов задачи, открытый роли на
запись, у обоих провайдеров.

Группа: разовый

Красен до реализации: в `docs/stack.md` нет ни одного упоминания `--add-dir` — ни в таблице паритета безопасности роли, ни в описании провайдеров.

Группа «разовый»: предмет — текст документа на ветке задачи (документ
отражает устройство, которое заводит эта задача); после мержа этот текст
сторожит ревью документа, а не исполнение кода.

Документ читается из рабочей копии кода, в которую выложена планка
(`Path(__file__).parents[3]`). Разделы находятся по началу заголовка
второго уровня: «## Паритет безопасности роли», «## Провайдер исполнителя
роли» (описание провайдера по умолчанию — Claude Code, `providers/
claude.py`), «## Провайдер codex»; тело раздела — до следующего заголовка
второго уровня. «Каталог документов» узнаётся по корню «документ» в той же
строке таблицы или в том же разделе — точную формулировку тест не
навязывает.
"""
import re
import unittest
from pathlib import Path

STACK_DOC = Path(__file__).resolve().parents[3] / "docs" / "stack.md"

PARITY = "## Паритет безопасности роли"
CLAUDE_SECTION = "## Провайдер исполнителя роли"
CODEX_SECTION = "## Провайдер codex"
ADD_DIR = "--add-dir"
DOCS_STEM = "документ"


def section(text: str, heading: str) -> str:
    """Тело раздела, заголовок которого начинается с `heading`; пусто —
    раздела нет."""
    match = re.search(rf"^{re.escape(heading)}[^\n]*\n", text, re.M)
    if match is None:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def table_rows(body: str) -> list:
    """Строки таблиц раздела списком ячеек (без строки-разделителя)."""
    rows = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: "):
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


class StackDocNamesDocsDirTest(unittest.TestCase):

    def setUp(self):
        self.text = STACK_DOC.read_text(encoding="utf-8")

    def test_ac11_parity_table_and_both_providers_name_writable_docs_dir(self):
        """Таблица паритета и описания провайдеров называют `--add-dir` каталога документов.

        Сценарий: разбор `docs/stack.md` ветки задачи. (1) В таблице
        раздела «Паритет безопасности роли» есть строка, у которой ячейка
        «чем закрыт у Claude» (вторая) и ячейка «чем закрыт у роли на
        Codex» (третья) обе несут `--add-dir`, а сама строка говорит о
        каталоге документов. (2) Раздел провайдера исполнителя роли
        (Claude) и раздел «Провайдер codex» каждый несут `--add-dir` и
        говорят о каталоге документов; в разделе codex флаг назван при
        `codex exec` (слово `exec` в разделе).

        Ловит мутацию: документ дописан только для одного провайдера
        (строка таблицы несёт `--add-dir` в одной из двух ячеек, или
        раздел второго провайдера о флаге молчит); флаг назван в таблице,
        а описание провайдеров не обновлено; строка таблицы о флаге не
        говорит, какой каталог открыт."""
        parity = section(self.text, PARITY)
        self.assertTrue(parity, f"нет раздела «{PARITY}» в {STACK_DOC}")
        rows = [row for row in table_rows(parity) if len(row) >= 3]
        matching = [row for row in rows
                    if ADD_DIR in row[1] and ADD_DIR in row[2]
                    and DOCS_STEM in " ".join(row).lower()]
        self.assertTrue(matching, (
            f"в таблице паритета нет строки с {ADD_DIR} у Claude и у Codex "
            f"и каталогом документов; строки с {ADD_DIR}: "
            f"{[row for row in rows if ADD_DIR in ' '.join(row)]}"))

        for heading in (CLAUDE_SECTION, CODEX_SECTION):
            body = section(self.text, heading)
            with self.subTest(section=heading):
                self.assertTrue(body, f"нет раздела «{heading}»")
                self.assertIn(ADD_DIR, body,
                              f"раздел «{heading}» не называет {ADD_DIR}")
                self.assertIn(DOCS_STEM, body.lower(),
                              f"раздел «{heading}» не говорит о каталоге "
                              f"документов")
        self.assertIn("exec", section(self.text, CODEX_SECTION),
                      "раздел codex не называет подкоманду exec")


if __name__ == "__main__":
    unittest.main()
