"""AC-1, AC-2: `scripts/guard.py` распознаёт пометку критерия `# AC-n:
ci — <причина>` наравне с `manual`/`skip`/`escalate`, и допускает её
только для критерия, формулировка которого — про существующие тесты.

Красен до реализации: `guard.AC_MARKER` сейчас (до этой задачи) несёт
альтернативу `(manual|skip|escalate)` без `ci` — регулярка не находит
пометку `ci` вовсе, `acceptance_traceability_errors` в
`test_ac1_ci_marker_covers_criterion_without_dedicated_test` вернёт
непустой список ошибок вместо пустого; сама эвристика по ключевым
словам требования 3/AC-2 в текущем guard.py отсутствует — второй тест
не найдёт ожидаемой ошибки о замене на `manual`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

# Индирекция символа решётки — та же причина, что в `_sandbox.py`
# (см. `_HASH` там): буквальный текст "# AC-9: ci — …" здесь сам
# попал бы под сканирование этой ЖЕ задачи (01M1SHJTT0V516BWHYXWS50F3G),
# если бы стоял литералом в исходнике этого файла — фикстуры ниже
# несут планку СИМУЛИРУЕМОЙ задачи T001 внутри временного каталога, не
# текущей.
_HASH = "#"

SPEC_HEADER = (
    "---\n"
    "task: T001\n"
    "type: spec\n"
    "author_role: analyst\n"
    "status: ready\n"
    "schema_version: 4\n"
    "---\n\n"
    "# SPEC: песочница guard ci-пометки\n\n"
)


class GuardCiMarkerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)

    def _write_task(self, criterion_text: str, marker_line: str) -> Path:
        """Каталог `<tmp>/T001/` с SPEC.md (один критерий AC-9) и
        `acceptance_tests/test_marker.py`, несущим `marker_line`."""
        tdir = self.tmp_path / "T001"
        tdir.mkdir()
        spec = (SPEC_HEADER + "## Критерии приёмки\n\n" + criterion_text
                + "\n")
        (tdir / "SPEC.md").write_text(spec, encoding="utf-8")
        tests_dir = tdir / "acceptance_tests"
        tests_dir.mkdir()
        (tests_dir / "test_marker.py").write_text(
            '"""Фикстура guard: планка симулируемой задачи T001, код не '
            'исполняется (guard разбирает текст статически)."""\n'
            + marker_line, encoding="utf-8")
        return tdir

    def test_ac1_ci_marker_covers_criterion_without_dedicated_test(self):
        """Планка несёт только пометку `# AC-9: ci — <причина>` (без
        тестового метода `test_ac9_...`) на критерий про существующие
        `tests/` — guard принимает пометку как валидное покрытие,
        трассируемость AC не отказывает.

        Ловит мутацию: `guard.AC_MARKER`, не расширенный литералом `ci`
        в альтернативе `(manual|skip|escalate)`, не увидел бы пометку
        вовсе — `acceptance_traceability_errors` вернула бы ошибку
        «AC-9: нет теста и нет пометки manual/skip/escalate».
        """
        tdir = self._write_task(
            "AC-9. Существующие тесты `tests/` остаются зелёными.\n",
            _HASH + " AC-9: ci — CI ветки уже подтверждает зелёный "
            "существующий набор.\n")

        errors = guard.acceptance_traceability_errors(tdir)

        self.assertEqual(errors, [])

    def test_ac2_ci_marker_rejected_for_unrelated_criterion_wording(self):
        """Планка ставит `ci` на критерий, формулировка которого не
        про существующие тесты (нет ни одного из ключевых слов
        «существующ», `tests/`, «зелён», «не ослаб») — guard отказывает,
        называя номер критерия и подсказывая заменить пометку на
        `manual` (требование 3 — эвристика fail-closed).

        Ловит мутацию: реализация, разрешающая `ci` наравне с `manual`
        БЕЗ ограничения по формулировке критерия (то есть требование 1
        сделано, а требование 3 — нет), пропустила бы эту планку без
        единой ошибки — тест поймает пустой список там, где ожидается
        отказ с номером критерия.

        Ошибка ОБЯЗАНА отличаться от общей «нет теста и нет пометки
        manual/skip/escalate» (ту же строку и сегодня, до распознавания
        `ci`, возвращает `acceptance_traceability_errors` для ЛЮБОЙ
        нераспознанной пометки, включая эту, — она НЕ доказывает работу
        эвристики требования 3, только то, что пометка `ci` пока не
        существует для guard'а вовсе): проверка ниже отдельно требует
        ОТСУТСТВИЯ этой общей фразы, иначе тест совпал бы и с сегодняшним
        поведением «пометка не распознана» вместо целевого «пометка
        распознана, но отклонена по формулировке».
        """
        tdir = self._write_task(
            "AC-9. Кнопка становится синей при наведении на элемент "
            "интерфейса.\n",
            _HASH + " AC-9: ci — тест не нужен, зелёный CI уже "
            "достаточен.\n")

        errors = guard.acceptance_traceability_errors(tdir)

        joined = " ".join(errors)
        self.assertIn("AC-9", joined,
                      "ошибка обязана называть номер критерия")
        self.assertIn("manual", joined,
                      "ошибка обязана подсказывать замену на manual")
        self.assertNotIn("нет теста и нет пометки", joined,
                         "ошибка обязана быть про ОТКЛОНЁННУЮ по "
                         "формулировке пометку ci, не про её отсутствие")

    def test_ac1_scan_ac_content_parses_ci_kind_and_reason(self):
        """`guard.scan_ac_content` (ядро, общее для дискового и ветко-
        корректного чтения планки) разбирает `# AC-n: ci — <причина>`
        в ту же структуру `{n: (kind, reason)}`, что и `manual`/`skip`/
        `escalate` — `kind` равен буквально `"ci"`, причина — текст
        после тире.

        Ловит мутацию: альтернатива `AC_MARKER`, расширенная НЕ строкой
        `ci`, а похожим, но другим литералом (опечатка вроде `сi` с
        кириллической «с», либо `CI` в другом регистре без `re.I`),
        нашла бы ноль пометок — `markers` остался бы пуст, тест поймает
        расхождение с ожидаемым словарём.
        """
        content = (_HASH + " AC-9: ci — существующие tests/ зелёные "
                  "по CI ветки.\n")

        _, markers = guard.scan_ac_content([content])

        self.assertEqual(markers.get(9),
                         ("ci", "существующие tests/ зелёные по CI ветки."))


if __name__ == "__main__":
    unittest.main()
