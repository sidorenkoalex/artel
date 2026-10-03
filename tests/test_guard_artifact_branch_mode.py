"""Юнит-тесты `guard.check_content` на черновике — наследие режима
артефактной ветки guard (01M1R66X5SMD3ZEDCVAJ0DR7K2).

Режим `--artifact-branch` снят (ADR-0021 п.4, SPEC
01M41VTQJ9DSX64NFMFAF9W53B): CI на пуше документов отменён, документы
проверяют гейты пульта на переходах полной проверкой. Отсутствие режима
(ключа, параметра `artifact_branch_mode`, сводки «сдано / черновиков»)
сторожит долгоживущий файл
`tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py`. Здесь
остаётся проверка, верная и без режима: черновик с разбитым содержимым
отказывает так же, как «сданный».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402


class CheckContentDefaultIsUnaffectedTest(unittest.TestCase):
    """`check_content` на черновике не отличим от проверки «сданного»
    артефакта — draft-документ с разбитым содержимым отказывает."""

    DRAFT_SPEC_NO_SECTIONS = """---
task: T1
type: spec
author_role: analyst
status: draft
schema_version: 1
---

# SPEC: фикстура
"""

    def test_default_call_reports_full_content_errors_for_a_draft(self):
        """Ловит мутацию: `check_content` ошибочно включает льготный режим
        для черновика (например, возвращает только нарушения frontmatter
        при `status: draft`) — тогда черновик без единой обязательной
        секции прошёл бы проверку молча."""
        errors = guard.check_content("label", self.DRAFT_SPEC_NO_SECTIONS)
        self.assertTrue(
            any("отсутствует обязательная секция" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
