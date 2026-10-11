"""AC-5, AC-6, AC-9, AC-10 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md):
пакет/diff крупнее потолка части (65536 байт) делится на нумерованные
части по границам строк (AC-5); конкатенация частей побайтово равна
целому (AC-6); diff крупнее потолка делится той же разбивкой со sha256
(AC-9), не усекается с потерей хвоста (AC-10).

## Допущение теста

SPEC не фиксирует формат разметки частей (заголовки, нумерация,
конкретные ключи возвращаемого значения) — решение исполнителя (PLAN).
Тест поэтому не завязан на конкретный формат: он проверяет НАБЛЮДАЕМЫЙ
инвариант, который любая корректная реализация обязана сохранить
независимо от формата —

- каждая ИСХОДНАЯ строка diff встречается в итоговом тексте пакета как
  ЦЕЛЫЙ, НЕРАЗОРВАННЫЙ элемент `text.splitlines()` (если бы строка была
  разрезана посередине куском, обе половинки не совпали бы с исходной
  строкой ни при каком сравнении) — это одновременно доказывает и
  «ни одна строка не разрывается внутри части» (AC-5), и «хвост не
  потерян молча» (AC-9/AC-10);
- относительный ПОРЯДОК исходных строк в итоговом тексте сохраняется
  (AC-6: конкатенация частей по номеру равна целому — тождественна
  «порядок и полнота строк сохранены», раз ни одна строка не разорвана
  и не потеряна);
- при делении на части опись обязана нести sha256 КАЖДОЙ части (AC-6) —
  число встречающихся в тексте sha256-подобных 64-символьных hex-строк
  у пакета с разбитым на части diff обязано быть БОЛЬШЕ, чем у пакета с
  маленьким diff (тем же составом остальных компонентов) — лишние хеши
  и есть свидетельство появившихся частей.

Красен до реализации: `review.review_package` сегодня отвечает на
превышение диффом потолка `REVIEW_DIFF_MAX_LINES` усечением с явной
потерей хвоста (`truncate_diff`), а на превышение пакетом байтового
потолка — усечением всего текста (`truncate_package`, маркер «пакет
усечён») — обе замены теряют хвост молча, ни то ни другое не делит на
пронумерованные части с sha256.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FakeGitDiff, TASK, build_review_package,  # noqa: E402
                      standard_files)

FILE_CAP_BYTES = 131072  # AC-2/AC-3
PART_CAP_BYTES = 65536  # AC-3

LINE_COUNT = 10_000  # ~120 КБ diff — комфортно больше потолка части


def _big_diff() -> str:
    return "\n".join(f"+line-{i:05d}" for i in range(LINE_COUNT))


def _big_plan_under_the_file_cap() -> str:
    """PLAN.md между потолком части (65536) и потолком файла (131072) —
    ПОД потолком файла (AC-2 его не исключает целиком), но настолько
    большой, что итоговый пакет переваливает за потолок части (AC-5
    делит «текст пакета», а не отдельно взятый diff)."""
    lines = "\n".join(f"строка-плана-{i:05d}" for i in range(3000))  # ~88 КБ
    assert PART_CAP_BYTES < len(lines.encode("utf-8")) < FILE_CAP_BYTES
    return lines


HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


class PartsNoLossTest(unittest.TestCase):

    def build(self, diff: str = "diff --git a b\n+одна строка",
             files: dict | None = None) -> dict:
        git = FakeGitDiff(files=files or standard_files(), diff=diff)
        return build_review_package(git)

    def test_ac5_oversized_package_text_gets_its_own_numbered_parts(self):
        """AC-5 говорит про «текст пакета» в целом, не только про diff —
        здесь его раздувает крупный (но под потолком файла) PLAN.md.

        Ни один из сегодняшних потолков (`REVIEW_DIFF_MAX_LINES` —
        строки diff, `REVIEW_PACKAGE_MAX_BYTES` = 400000 — весь пакет)
        не задевает PLAN.md такого размера сам по себе — сегодня деления
        на части не происходит вовсе, поэтому проверяется не «строки не
        потерялись» (это и сегодня тривиально верно — резать нечему), а
        появление НОВЫХ sha256-записей описи частей, которых до этой
        задачи в принципе не существует ни при каком размере PLAN.md."""
        small_files = standard_files()
        small_package = self.build(files=small_files)

        big_files = standard_files()
        big_files[f"tasks/{TASK}/PLAN.md"] = _big_plan_under_the_file_cap()
        big_package = self.build(files=big_files)

        small_hashes = len(HEX64.findall(small_package["text"]))
        big_hashes = len(HEX64.findall(big_package["text"]))

        self.assertGreater(
            big_hashes, small_hashes,
            "PLAN.md крупнее потолка части обязан разбить текст пакета "
            "на пронумерованные части с собственным sha256 каждая "
            "(AC-5/AC-6) — число хешей в тексте обязано вырасти "
            "относительно маленького PLAN.md")

    def test_ac9_no_line_of_the_oversized_diff_is_broken_or_dropped(self):
        diff = _big_diff()
        package = self.build(diff)

        output_lines = set(package["text"].splitlines())
        original_lines = diff.splitlines()

        missing = [ln for ln in original_lines if ln not in output_lines]
        self.assertEqual(
            missing[:5], [],
            f"{len(missing)} строк diff отсутствуют в тексте пакета "
            f"целыми (пропущены или разорваны частью) — первые: "
            f"{missing[:5]}")

    def test_ac6_the_order_of_diff_lines_is_preserved(self):
        diff = _big_diff()
        package = self.build(diff)

        original_lines = diff.splitlines()
        original_set = set(original_lines)
        seen_in_output = [ln for ln in package["text"].splitlines()
                          if ln in original_set]

        self.assertEqual(
            seen_in_output, original_lines,
            "строки diff обязаны появиться в тексте пакета в том же "
            "порядке и ровно по одному разу — конкатенация частей по "
            "номеру равна целому (AC-6)")

    def test_ac6_splitting_the_diff_adds_more_sha256_entries_to_the_manifest(self):
        small = self.build("diff --git a b\n+одна строка")
        big = self.build(_big_diff())

        small_hashes = len(HEX64.findall(small["text"]))
        big_hashes = len(HEX64.findall(big["text"]))

        self.assertGreater(
            big_hashes, small_hashes,
            "разбитый на части diff обязан добавить в описи sha256 "
            "каждой новой части (AC-6) — число хешей в тексте пакета "
            "должно вырасти относительно маленького diff")

    def test_ac10_oversized_diff_does_not_carry_the_old_silent_truncation_mark(self):
        package = self.build(_big_diff())

        self.assertNotIn(
            "diff усечён", package["text"],
            "старое молчаливое усечение (truncate_diff) заменено "
            "дисциплиной частей (AC-10) — маркер прежнего поведения не "
            "должен остаться")
        self.assertNotIn(
            "пакет усечён", package["text"],
            "то же для truncate_package — байтовое усечение всего "
            "пакета тоже заменено (AC-10)")

    def test_ac10_bookkeeping_fields_no_longer_report_a_truncation(self):
        package = self.build(_big_diff())

        self.assertFalse(
            package.get("truncated"),
            "поле truncated описывает старую семантику усечения — "
            "дисциплина частей не имеет права её взводить (AC-10)")
        self.assertFalse(
            package.get("over_bytes"),
            "то же для over_bytes — байтовое усечение всего пакета "
            "заменено делением на части, не флагом потери хвоста (AC-10)")


if __name__ == "__main__":
    unittest.main()
