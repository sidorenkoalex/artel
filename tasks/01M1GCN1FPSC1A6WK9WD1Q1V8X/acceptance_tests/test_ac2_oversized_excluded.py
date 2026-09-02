"""AC-2 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): компонент, чей размер
превышает потолок одного файла (131072 байт = 128 КиБ), не включается в
текст пакета целиком — опись несёт по нему путь, размер и причину
пропуска («превышен лимит файла») вместо содержимого.

131072 — не значение, которое Оператор может тихо покрутить мимо этой
задачи (config.* ещё не существует): это САМ критерий приёмки AC-2/AC-3,
дословно зафиксированный в SPEC числом байт — здесь он используется
литералом намеренно, не в обход скила test-authoring.

Красен до реализации: сейчас компонент включается в пакет ЦЕЛИКОМ
независимо от размера (`truncate_package`/`truncate_diff` режут пакет
байтовым/строчным хвостом, а не исключают отдельный компонент по
описи) — большой CLAUDE.md/PLAN.md сегодня оказался бы в тексте целиком
(или обрублен без разбора компонентов), а не пропущен со ссылкой и
причиной.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BriefSandbox, FakeGitDiff, SPEC_MD, TASK,  # noqa: E402
                      build_review_package, standard_files)

FILE_CAP_BYTES = 131072  # AC-2/AC-3


class Ac2BriefOversizedConventionsTest(BriefSandbox):
    """CLAUDE.md (конвенции) — компонент брифа, не артефакт конкретной
    задачи и не «всегда включаемый» docs/codebase-map.md (AC-21) — его
    пропуск по потолку размера не задевает алерт AC-21/AC-22, только
    описи AC-2 касается этот тест."""

    def test_ac2_oversized_conventions_excluded_with_reason(self):
        marker = "МАРКЕР-КОНВЕНЦИЙ-ЦЕЛИКОМ"
        big = marker + "\n" + ("я" * (FILE_CAP_BYTES + 1000))
        (self.root / "CLAUDE.md").write_text(big, encoding="utf-8")

        text = self.build_brief()

        self.assertIn("CLAUDE.md", text, "путь пропущенного файла назван")
        self.assertNotIn(marker, text,
                         "содержимое компонента крупнее потолка не должно "
                         "попасть в пакет целиком")
        self.assertIn(str(len(big.encode("utf-8"))), text,
                      "размер пропущенного файла назван в описи")
        self.assertIn("превышен лимит файла", text,
                      "причина пропуска — дословно из AC-2")


class Ac2ReviewPackagePlanTest(unittest.TestCase):

    def test_ac2_oversized_plan_excluded_with_reason(self):
        marker = "МАРКЕР-PLAN-ЦЕЛИКОМ"
        big_plan = marker + "\n" + ("я" * (FILE_CAP_BYTES + 1000))
        files = standard_files()
        files[f"tasks/{TASK}/PLAN.md"] = big_plan
        git = FakeGitDiff(files=files)

        package = build_review_package(git)
        text = package["text"]

        self.assertIn(f"tasks/{TASK}/PLAN.md", text,
                      "путь пропущенного PLAN.md назван")
        self.assertNotIn(marker, text,
                         "тело PLAN.md крупнее потолка не должно попасть "
                         "в пакет целиком")
        self.assertIn(str(len(big_plan.encode("utf-8"))), text,
                      "размер пропущенного PLAN.md назван в описи")
        self.assertIn("превышен лимит файла", text)
        # SPEC.md — под потолком, остаётся целиком рядом с пропуском PLAN.
        self.assertIn(SPEC_MD.format(task=TASK).strip().splitlines()[-1], text)


if __name__ == "__main__":
    unittest.main()
