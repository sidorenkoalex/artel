"""Приёмочные тесты T077, AC-2 (tasks/T077/SPEC.md): сообщение об
отсутствующей обязательной секции, вызванное тем, что заголовок
присутствует на неверном уровне (не H2), называет требуемый уровень
заголовка (`## <имя секции>`, не H3 и не другой уровень).

Красен до реализации: `check_content` строит набор заголовков только по
`^##\\s+...` (ровно два `#`) — заголовок `### Критерии приёмки` в этот
набор не попадает, и секция считается «отсутствующей» тем же
сообщением, что и при полном отсутствии заголовка:
«отсутствует обязательная секция '## Критерии приёмки'» — сообщение
показывает требуемую форму (`## Критерии приёмки`), но ни словом не
называет, что дело в УРОВНЕ заголовка (не H2, не H3) — фактура T071
(SPEC T077, Контекст).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

SPEC_WITH_H3_CRITERIA_SECTION = """---
task: T999
type: spec
author_role: analyst
status: draft
schema_version: 2
---

# SPEC: test

## Контекст
x

## Требования
1. x

### Критерии приёмки
AC-1. x

## Не входит
x
"""


class SectionAtWrongHeaderLevelTest(unittest.TestCase):
    def test_ac2_h3_instead_of_h2_message_names_required_level(self):
        errors = guard.check_content("SPEC.md", SPEC_WITH_H3_CRITERIA_SECTION)
        joined = " ".join(errors)

        self.assertTrue(
            any("Критерии приёмки" in e for e in errors),
            f"секция на неверном уровне не отмечена нарушением: {errors}")
        self.assertIn(
            "## Критерии приёмки", joined,
            "сообщение не называет требуемый заголовок целиком")
        self.assertTrue(
            "уровень" in joined or "уровня" in joined
            or "H2" in joined or "H3" in joined,
            f"сообщение не называет требуемый УРОВЕНЬ заголовка "
            f"(не H3 и не другой уровень): {errors}")


if __name__ == "__main__":
    unittest.main()
