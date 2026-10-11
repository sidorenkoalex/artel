"""AC-9 (tasks/T073/SPEC.md): `docs/retention.md` упоминает
premod-очередь как будущую строку политики, без её реализации в этой
задаче.

Два самостоятельных факта в одном критерии, оба автоматически
проверяемы:
1. документ называет premod (упоминание) — grep текста;
2. этой задачей не появилось никакого КОДА premod (реализации) —
   grep `orchestrator/` на слово «premod»; SPEC «Не входит»: «premod-
   очередь — она не существует до C3».

Красен до реализации: `docs/retention.md` не существует.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class RetentionDocPremodMentionTest(unittest.TestCase):

    def test_ac9_doc_mentions_premod_as_future_policy_line(self):
        text = (REPO_ROOT / "docs" / "retention.md").read_text(encoding="utf-8")
        self.assertIn(
            "premod", text.lower(),
            "docs/retention.md обязан упомянуть premod-очередь как "
            "будущую строку политики (SPEC AC-9)")

    def test_ac9_no_premod_implementation_added_under_orchestrator(self):
        offenders = []
        for path in (REPO_ROOT / "orchestrator").rglob("*.py"):
            if "premod" in path.read_text(encoding="utf-8").lower():
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(
            offenders, [],
            f"premod-очередь не существует до C3 (SPEC «Не входит») — "
            f"эта задача не вправе добавлять её реализацию: {offenders}")


if __name__ == "__main__":
    unittest.main()
