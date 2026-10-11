"""Приёмочный тест T094 — AC-17 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-17: «docs/adr/0005-data-preservation-and-memory.md несёт правки пп.
1, 2, 4 и 5, отражающие топологию Б₃ (артефактная ветка пульта при
жизни задачи, снапшот в refs/artifacts/<id> целевого при закрытии
вместо merge-адресации, сужение «чужое не публикуем» до видимой
поверхности, судьбу счётчика номеров); пп. 6 и 7 не изменены.»

Базовая версия ADR — содержимое `docs/adr/0005-...md` на `main`
(`git show main:...`), не литерал, вшитый в тест: транскрипция
многострочного маркдауна в исходник теста — источник ложной красноты
(текст неизбежно разойдётся посимвольно с оригиналом при переносах
строк/пробелах), а не сравнение по существу. Пп. 6/7 сверяются
БАЙТ-В-БАЙТ с базовой версией (требование «не трогаются»); пп. 1/2/4/5
— что текст РАЗОШЁЛСЯ с базовым (правка была) и несёт ключевые слова
формулировки требования 15.

Красен до реализации: сегодня файл на ветке задачи совпадает с `main`
целиком — пп. 1/2/4/5 ещё не разошлись с базовой версией.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_REL = "docs/adr/0005-data-preservation-and-memory.md"
ADR_PATH = REPO_ROOT / ADR_REL

SECTION_RE = re.compile(r"\n### (\d+)\. ")


def _sections(text: str) -> dict:
    """{номер раздела: тело до следующего `### `/`## `}."""
    matches = list(SECTION_RE.finditer(text))
    out = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        body = re.split(r"\n## ", body)[0]
        out[m.group(1)] = body
    return out


def _main_baseline() -> str:
    res = subprocess.run(
        ["git", "show", f"main:{ADR_REL}"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        raise unittest.SkipTest(
            f"`git show main:{ADR_REL}` не удался — базовая версия "
            f"недоступна в этой песочнице: {res.stderr.strip()[:200]}")
    return res.stdout


KEYWORDS = {
    "1": ("видим",),
    "2": ("артефактн", "снапшот", "refs"),
    "4": ("refs/artifacts",),
    "5": ("legacy", "заморож", "не движется", "ulid", "ULID"),
}


class Ac17Adr0005EditsTest(unittest.TestCase):

    def setUp(self):
        self.baseline = _sections(_main_baseline())
        self.current = _sections(ADR_PATH.read_text(encoding="utf-8"))

    def test_ac17_sections_1_2_4_5_changed_and_carry_expected_keywords(self):
        problems = []
        for n, keywords in KEYWORDS.items():
            base = self.baseline.get(n, "")
            cur = self.current.get(n, "")
            if cur.strip() == base.strip():
                problems.append(f"п.{n}: текст не изменился относительно main")
                continue
            if not any(kw.lower() in cur.lower() for kw in keywords):
                problems.append(
                    f"п.{n}: не несёт ни одного ключевого слова {keywords}")
        self.assertEqual(problems, [], f"AC-17: {problems}")

    def test_ac17_sections_6_and_7_are_byte_identical_to_main(self):
        for n in ("6", "7"):
            self.assertEqual(
                self.current.get(n), self.baseline.get(n),
                f"п.{n} ADR-0005 изменён — требование 15 прямо запрещает "
                f"трогать пп. 6 и 7")


if __name__ == "__main__":
    unittest.main()
