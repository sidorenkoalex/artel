"""AC-7 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): для брифа/пакета,
разделённого дисциплиной частей (`context_package.discipline`, эта
задача её не трогает) на несколько пронумерованных частей: часть, в
которой обёрнутый маркерами блок остаётся незакрытым (закрывающий маркер
попал в другую часть), несёт явный, отличимый от «блок закрыт целиком»
признак незавершённости.

## Допущение теста

SPEC не даёт формулировку признака в кавычках. Формулировка самой AC-7
— «признак незавершённости» — предполагает близкое воспроизведение этих
же слов (та же практика уже применена в tasks/
01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/test_ac7_read_parts_in_order.py
к соседней AC-7 той же природы: подстрока «по порядку» дословно из
SPEC). Тест ищет подстроку «незаверш» (покрывает «незавершённости»,
«не завершён», «незавершён» и т.п.) — если реализация выберет
существенно другую формулировку, это разногласие правильно ловить на
ревью, а не тихо подгонять тест задним числом под непредсказанный текст.

Сценарий: один компонент (SPEC.md) намеренно больше потолка ЧАСТИ
(`config.CONTEXT_PART_MAX_BYTES`), но меньше потолка ФАЙЛА
(`config.CONTEXT_FILE_MAX_BYTES`) — попадает в бриф целиком (не
пропускается описью), но физически режется на несколько пронумерованных
частей самим же телом (`context_package.split_into_parts`, построчно,
без понятия о маркерах) — то есть открывающий маркер неизбежно попадает
в одну часть, закрывающий — в другую.

Красен до реализации: маркеров нет вовсе — открывающий/закрывающий id
не найти, часть с «незавершённостью» не отличить, ассерт на «незаверш»
падает."""
import bisect
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import BriefSandbox, MAP_FRESH, marker_id_for  # noqa: E402

from orchestrator import config  # noqa: E402

FIRST_LINE = "SPEC-LINE-START-UNIQUE-MARKER"
LAST_LINE = "SPEC-LINE-END-UNIQUE-MARKER"


def _oversized_spec_body() -> str:
    cap_part = config.CONTEXT_PART_MAX_BYTES
    cap_file = config.CONTEXT_FILE_MAX_BYTES
    filler_line = "x" * 40
    lines = [FIRST_LINE]
    size = len((FIRST_LINE + "\n").encode("utf-8"))
    target = int(cap_part * 1.5)
    while size < target:
        lines.append(filler_line)
        size += len(filler_line.encode("utf-8")) + 1
    lines.append(LAST_LINE)
    body = "\n".join(lines) + "\n"
    assert cap_part < len(body.encode("utf-8")) < cap_file, (
        "тело обязано быть между потолком части и потолком файла")
    return body


def _part_boundaries(text: str) -> list:
    return sorted(m.start() for m in re.finditer(r"--- ЧАСТЬ \d+/\d+", text))


def _part_index_at(boundaries: list, pos: int) -> int:
    """Индекс части (0-based по порядку следования), в которую попадает
    позиция `pos` — часть, чей заголовок стоит последним не позже `pos`."""
    return bisect.bisect_right(boundaries, pos) - 1


class Ac7UnclosedPartMarkerTest(BriefSandbox):

    def test_ac7_the_part_without_the_closing_marker_carries_an_unfinished_marker(self):
        """Ловит мутацию: часть, где закрывающий маркер физически не
        поместился (попал в следующую часть), выглядит как обычный,
        полностью закрытый текст — роль, прочитавшая только эту часть,
        приняла бы обрезанное содержимое за целое."""
        self.write_spec("# SPEC\n\n" + _oversized_spec_body())

        text = self.build_developer_brief()

        boundaries = _part_boundaries(text)
        self.assertGreaterEqual(
            len(boundaries), 2,
            "сценарий обязан реально разделиться на несколько частей")

        run_id = marker_id_for(text, MAP_FRESH.strip())

        idx_first = text.find(FIRST_LINE)
        self.assertGreater(idx_first, -1)
        self.assertIn(
            run_id, text[max(0, idx_first - 500):idx_first],
            "открывающий маркер (с общим id запуска) обязан стоять "
            "вплотную перед первой строкой SPEC")

        idx_last = text.rfind(LAST_LINE)
        self.assertGreater(idx_last, -1)
        end_last = idx_last + len(LAST_LINE)
        self.assertIn(
            run_id, text[end_last:end_last + 500],
            "закрывающий маркер (с тем же id) обязан стоять вплотную "
            "после последней строки SPEC")

        part_first = _part_index_at(boundaries, idx_first)
        part_last = _part_index_at(boundaries, idx_last)
        self.assertNotEqual(
            part_first, part_last,
            "открывающий и закрывающий маркер обязаны оказаться в РАЗНЫХ "
            "пронумерованных частях — иначе сценарий не воспроизводит "
            "AC-7 (незакрытый блок)")

        seg_start = boundaries[part_first]
        seg_end = (boundaries[part_first + 1]
                  if part_first + 1 < len(boundaries) else len(text))
        segment = text[seg_start:seg_end]

        self.assertIn(
            "незаверш", segment.lower(),
            "часть, где обёрнутый блок остаётся незакрытым (закрывающий "
            "маркер — в другой части), обязана нести явный признак "
            "незавершённости")

    def test_ac7_a_fully_contained_block_carries_no_unfinished_marker(self):
        """Контраст: маленький бриф (ничего не делится) не содержит
        признака незавершённости вообще — иначе признак был бы
        бессмысленным «всегда включённым» текстом, не связанным с
        реальным состоянием части (симметрично AC-7-тесту в
        tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X: «маленький diff не порождает
        бессмысленную инструкцию»).

        Ловит мутацию: признак незавершённости печатается БЕЗУСЛОВНО
        (статический текст в преамбуле независимо от реального деления),
        а не только тогда, когда часть действительно осталась
        незакрытой."""
        text = self.build_developer_brief()

        self.assertNotIn("незаверш", text.lower())


if __name__ == "__main__":
    unittest.main()
