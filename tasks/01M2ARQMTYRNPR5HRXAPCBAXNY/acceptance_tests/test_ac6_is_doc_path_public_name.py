"""AC-6 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md): `scripts/
ci_push_class.py` несёт публичное имя `is_doc_path`; регулярное выражение
`_DOC_PATTERN` не изменено.

Красен до реализации: `scripts/ci_push_class.py` несёт сегодня только
приватное `_is_doc_path` — публичного `is_doc_path` не существует
(`hasattr` вернёт `False`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import ci_push_class  # noqa: E402

# Регулярное выражение требования 4 ТЗ/SPEC — байт-в-байт то же, что уже
# несёт `scripts/ci_push_class.py` ДО этой задачи (ADR-0016): `docs/**`,
# `tasks/**` или `*.md` в корне.
_EXPECTED_DOC_PATTERN = r"^(docs/|tasks/|[^/]+\.md$)"


class IsDocPathPublicNameTest(unittest.TestCase):

    def test_ac6_is_doc_path_is_public_and_pattern_unchanged(self):
        """Публичное имя `is_doc_path` обязано существовать и вести себя
        как классификатор документного пути (ADR-0016), а
        `_DOC_PATTERN` — остаться байт-в-байт тем же регулярным
        выражением.

        Ловит мутацию: `is_doc_path` не заведено (осталось только
        приватное `_is_doc_path`, вызывающий код `pull.py` не может его
        публично импортировать) — `hasattr` красит тест `AttributeError`
        до первого `assert`; кто-то расширил/сузил `_DOC_PATTERN` при
        переименовании — `assertEqual` по `.pattern` поймает любое
        текстовое отличие от зафиксированного значения."""
        self.assertTrue(hasattr(ci_push_class, "is_doc_path"),
                        "публичное имя is_doc_path обязано существовать")
        self.assertTrue(ci_push_class.is_doc_path("docs/x.md"))
        self.assertFalse(ci_push_class.is_doc_path("orchestrator/pull.py"))
        self.assertEqual(ci_push_class._DOC_PATTERN.pattern,
                         _EXPECTED_DOC_PATTERN)


if __name__ == "__main__":
    unittest.main()
