"""AC-6 (tasks/01M1GV6H5DDDCWW4G3GW1D3A1X/SPEC.md): опись компонентов
(путь/размер/sha256) и протокол чтения частей (заголовки «ЧАСТЬ N/M»,
инструкция прочитать все части по порядку) размещены ВНЕ граничных
маркеров недоверенного содержимого.

## Допущение теста

SPEC требование 3 явно относит опись и протокол частей к «служебным
частям пакета — продукту оркестратора», размещаемым вне недоверенных
границ; это же читается как ограничение НА ФОРМУЛУ описи: `sha256`/
`размер`, которые видит роль в заголовке компонента, обязаны остаться
хэшем/размером ИСХОДНОГО (небёрнутого маркерами) содержимого — иначе
заголовок относился бы уже к обёрнутому тексту, то есть фактически
переехал бы внутрь границы. Первый тест ниже проверяет именно это:
sha256 заголовка совпадает с `context_package.sha256_of` НЕОБЁРНУТОГО
текста и стоит по тексту раньше открывающего маркера.

Второй тест использует сценарий, где деление на части (`context_package.
discipline`, эта задача её не трогает — «Не входит») режет МЕЖДУ
компонентами, не сквозь один: оба компонента (SPEC и конвенции) по
отдельности меньше потолка части, но вместе — больше. В этом случае
заголовки «--- ЧАСТЬ N/M ---» обязаны попадать в промежутки между
компонентами, а не внутрь пары маркеров ни одного из них — сценарий, где
маркеры одного компонента разорваны надвое разбиением на части, отдельно
покрыт AC-7 и туда не входит.

Красен до реализации: маркеров нет — `marker_id_for` бросает
`AssertionError` в обоих тестах.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import BriefSandbox, CONVENTIONS_SMALL, SPEC_SMALL  # noqa: E402
from _sandbox import marker_id_for, marker_span  # noqa: E402

from orchestrator import config, context_package  # noqa: E402


class Ac6ManifestOutsideMarkersTest(BriefSandbox):

    def test_ac6_spec_manifest_sha256_of_raw_text_precedes_the_marker(self):
        """Ловит мутацию: заголовок описи считает sha256/размер уже
        ОБЁРНУТОГО маркерами текста (опись «переехала» внутрь границы)
        либо заголовок печатается ПОСЛЕ открывающего маркера."""
        text = self.build_developer_brief()

        expected_sha = context_package.sha256_of(SPEC_SMALL)
        self.assertIn(expected_sha, text,
                     "опись обязана нести sha256 исходного (небёрнутого) "
                     "текста SPEC.md")
        sha_idx = text.index(expected_sha)

        run_id = marker_id_for(text, SPEC_SMALL.strip())
        open_idx, _close_idx = marker_span(text, SPEC_SMALL.strip(), run_id)

        self.assertLess(
            sha_idx, open_idx,
            "заголовок описи (путь/размер/sha256) обязан стоять ДО "
            "открывающего маркера — вне недоверенной границы")


class Ac6PartsProtocolBetweenComponentsTest(BriefSandbox):
    """SPEC/конвенции — каждый под потолком части поодиночке, вместе —
    больше: `context_package._pack_components` режет строго между ними
    (внутренняя механика discipline() эта задача не меняет)."""

    def setUp(self):
        super().setUp()
        cap = config.CONTEXT_PART_MAX_BYTES
        spec_body = "\n".join(f"строка-SPEC-{i:05d}" for i in range(1, 2500))
        conv_body = "\n".join(f"строка-CLAUDE-{i:05d}" for i in range(1, 2000))
        self.assertLess(len(spec_body.encode("utf-8")), cap)
        self.assertLess(len(conv_body.encode("utf-8")), cap)
        self.assertGreater(
            len(spec_body.encode("utf-8")) + len(conv_body.encode("utf-8")), cap,
            "тело обязано превысить потолок части СУММОЙ двух компонентов")
        self.spec_body = spec_body
        self.conv_body = conv_body
        self.write_spec(f"# SPEC\n\n{spec_body}\n")
        self.write_conventions(f"# Конвенции\n\n{conv_body}\n")

    def test_ac6_part_headers_never_fall_inside_a_component_marker_pair(self):
        """Ловит мутацию: заголовок «--- ЧАСТЬ N/M ---» оказывается между
        открывающим и закрывающим маркером компонента (например если
        обёртка маркерами применяется уже К ГОТОВЫМ пронумерованным
        частям, а не к компонентам до деления)."""
        text = self.build_developer_brief()

        part_header_positions = [
            m.start() for m in re.finditer(r"--- ЧАСТЬ \d+/\d+", text)]
        self.assertGreaterEqual(
            len(part_header_positions), 2,
            "сценарий обязан реально разделиться на части — иначе тест "
            "ничего не проверяет")

        spec_id = marker_id_for(text, self.spec_body)
        conv_id = marker_id_for(text, self.conv_body)
        self.assertEqual(spec_id, conv_id)

        spans = [
            marker_span(text, self.spec_body, spec_id),
            marker_span(text, self.conv_body, conv_id),
        ]
        for pos in part_header_positions:
            for open_idx, close_idx in spans:
                self.assertFalse(
                    open_idx < pos < close_idx,
                    f"заголовок части на позиции {pos} обязан быть вне "
                    f"пары маркеров ({open_idx}, {close_idx})")


if __name__ == "__main__":
    unittest.main()
