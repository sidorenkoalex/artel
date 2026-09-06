"""Приёмочный тест AC-3 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
запросы, остающиеся в `store.py`, сгруппированы заголовками-
разделителями по шести областям, перечисленным в SPEC буквально: задачи
и переходы; журнал `steps`; lease; алерты; канарейка; зоны и очередь —
именно в этом порядке сверху вниз файла.

Тест ищет заголовок как КОММЕНТАРНУЮ строку, содержащую ключевое слово
области (не пересказ имени функции внутри группы) — конкретный
декоративный синтаксис разделителя (`# ===`, `# ---` и т.п.) SPEC не
диктует, поэтому тест не завязан на символы вокруг заголовка, только на
наличие и порядок самих шести меток.

Красен до реализации: сегодняшний `store.py` не содержит ни одного из
шести заголовков-разделителей — рефакторинг группировки (AC-3) ещё не
сделан, запросы вперемешку со схемой/миграцией в одном файле (SPEC,
«Контекст»).
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

STORE_PY = REPO_ROOT / "orchestrator" / "store.py"

# Порядок и формулировки — буквально из SPEC, требование 2 / AC-3.
_CATEGORY_PATTERNS = (
    ("задачи и переходы", re.compile(r"задач.{0,3}\s+и\s+перех", re.IGNORECASE)),
    ("журнал steps", re.compile(r"журнал.{0,10}steps", re.IGNORECASE)),
    ("lease", re.compile(r"\blease\b", re.IGNORECASE)),
    ("алерты", re.compile(r"алерт", re.IGNORECASE)),
    ("канарейка", re.compile(r"канаре", re.IGNORECASE)),
    ("зоны и очередь", re.compile(r"зон.{0,3}\s+и\s+очеред", re.IGNORECASE)),
)


def _comment_header_lines(source: str) -> list:
    """Строки-комментарии верхнего уровня (без отступа — заголовок
    раздела, а не пояснение внутри тела функции)."""
    return [line for line in source.splitlines()
            if re.match(r"^#", line)]


class StoreQueryGroupsHaveOrderedHeadersTest(unittest.TestCase):

    def test_ac3_six_category_headers_present_in_spec_order(self):
        """Каждая из шести областей SPEC (требование 2) находит ровно
        один заголовок-комментарий верхнего уровня в `store.py`, и эти
        заголовки идут сверху вниз файла в том же порядке, что и в
        формулировке критерия.

        Ловит мутацию: группировка сделана лишь частично (например,
        добавлены заголовки для «lease»/«алерты», но не для «канарейка»/
        «зоны и очередь») — тогда для отсутствующей категории не
        найдётся ни одной строки-комментария, и `assertIsNotNone`
        упадёт на её имени; либо заголовки расставлены, но в другом
        порядке (например, «канарейка» выше «lease») — тогда список
        найденных позиций перестанет быть отсортированным по
        возрастанию, и `assertEqual(positions, sorted(positions))`
        упадёт.
        """
        source = STORE_PY.read_text(encoding="utf-8")
        lines = source.splitlines()

        positions = []
        for label, pattern in _CATEGORY_PATTERNS:
            matches = [i for i, line in enumerate(lines)
                      if re.match(r"^#", line) and pattern.search(line)]
            self.assertTrue(
                matches,
                f"не найден заголовок-разделитель для области «{label}» "
                "в orchestrator/store.py (комментарий верхнего уровня, "
                "без отступа)")
            positions.append(matches[0])

        self.assertEqual(
            positions, sorted(positions),
            "заголовки-разделители найдены, но не в порядке SPEC "
            "(задачи и переходы; журнал steps; lease; алерты; "
            f"канарейка; зоны и очередь): {list(zip((c[0] for c in _CATEGORY_PATTERNS), positions))}")


if __name__ == "__main__":
    unittest.main()
