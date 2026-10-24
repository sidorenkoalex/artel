"""Заменяет маркер `<!-- table:<имя> -->` в PLAN.md дословным текстом таблицы
mutation-run (файл `<имя>` каталога документов) в ограждении кода.

Запуск: python3 fill_plan_tables.py <имя.tsv> [<текст git status>]
"""
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
plan = DOCS / "PLAN.md"
name = sys.argv[1]
marker = f"<!-- table:{name} -->"
table = (DOCS / name).read_text(encoding="utf-8").rstrip("\n")
text = plan.read_text(encoding="utf-8")
if marker not in text:
    sys.exit(f"нет маркера {marker}")
text = text.replace(marker, "```\n" + table + "\n```")
plan.write_text(text, encoding="utf-8")
print(f"вставлено {len(table.splitlines())} строк из {name}")
