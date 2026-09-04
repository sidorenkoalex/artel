"""Общие фикстуры приёмочных тестов 01M1KS8K9RXWHX2PW3ZKB0P903 (SPEC:
«Оценка объёма задачи и решение о делении на этапе SPEC»).

Чёрный ящик над `scripts.guard.check_content` — SPEC.md строится текстом,
без импорта ещё не написанной реализации сигналов «подозрения на большой
объём» (тот же приём, что tasks/T072/acceptance_tests/
test_ac1_ac5_evidence_section_guard.py держит для секции «Проверено
исполнением»).

Не подпадает под маркерную/redness-проверку самой задачи: обе читают
только `test_*.py` под `acceptance_tests/` (scripts/guard.py::
scan_acceptance_tests/scan_redness_markers) — этот файл в выборку не
входит.
"""
import pathlib
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

INVARIANTS_DOC_PATH = REPO_ROOT / "docs" / "invariants.md"

FIXTURE_TASK_ID = "01M1KS8K9RXWHX2PW3ZKB0P903-FIXTURE"

# Три фразы сигнала «формулировки неопределённости» — буквально из
# требования 1 / AC-2 SPEC (одна фраза — один естественный русский пример
# её употребления, для читаемости фикстур ниже).
UNCERTAINTY_PHRASE_SENTENCES = {
    "ориентировочно": "Список затронутых файлов оценён ориентировочно.",
    "весь оркестратор": "Правка потенциально затрагивает весь оркестратор.",
    "по факту затронутых мест": "Точный перечень появится по факту "
                                 "затронутых мест.",
}

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 3
budget_usd: 15
---

# SPEC: фикстура теста сигналов объёма

## Контекст
Фикстура приёмочного теста задачи 01M1KS8K9RXWHX2PW3ZKB0P903 — короткий
безобидный текст, не связанный с реальной механикой пульта.

## Требования
1. Первое требование фикстуры.{extra}
{zones_block}
## Критерии приёмки
AC-1. Первый критерий фикстуры.
AC-2. Второй критерий фикстуры.

## Не входит
- Всё остальное.
{volume_block}"""


def spec_text(*, extra_requirement_sentence: str = "",
              volume_section: str | None = "",
              zone_paths: list | None = None) -> str:
    """Текст фиктивного `SPEC.md`.

    `extra_requirement_sentence` дописывается отдельным предложением в
    конец требования 1 — место для триггерной фразы сигнала AC-2, пусто по
    умолчанию (ни одна из трёх фраз не встречается).

    `volume_section` — тело секции `## Оценка объёма и деление`: `None` —
    секция отсутствует целиком, `""` (умолчание) — заголовок есть, тело
    пустое, любая другая строка — заданное содержимое секции.

    `zone_paths` — список путей вида `orchestrator/<имя>.py`/
    `scripts/<имя>.py` для секции `## Зоны` (AC-3, ANSWER-1): `None`
    (умолчание) — секция отсутствует целиком, пустой список — заголовок
    есть, тело пустое, непустой список — по одному пути на строку.
    """
    extra = f" {extra_requirement_sentence}" if extra_requirement_sentence else ""
    if volume_section is None:
        volume_block = ""
    else:
        volume_block = f"\n## Оценка объёма и деление\n{volume_section}\n"
    if zone_paths is None:
        zones_block = ""
    else:
        body = "\n".join(f"- `{p}`" for p in zone_paths)
        zones_block = f"\n## Зоны\n{body}\n"
    return SPEC_TEMPLATE.format(task=FIXTURE_TASK_ID, extra=extra,
                                volume_block=volume_block,
                                zones_block=zones_block)


def check(**kwargs) -> list[str]:
    """`guard.check_content` над `spec_text(**kwargs)` — экономит
    повторение `guard.check_content("SPEC.md", spec_text(...))` в каждом
    тесте."""
    return guard.check_content("SPEC.md", spec_text(**kwargs))


@contextmanager
def fake_invariants_doc(fake_text: str):
    """Подменяет содержимое `docs/invariants.md`, как его видит любой код,
    читающий файл через `pathlib.Path.read_text` (соглашение этого модуля
    — см. `scripts/guard.py::id_format_patterns`, `ID_FORMAT_PATTERNS_PATH.
    read_text(...)` — единообразный приём чтения вспомогательных файлов
    guard'а по требованию, без кеша на импорте).

    Нужен ровно одному тесту (AC-3, ANSWER-1): сегодняшний РЕАЛЬНЫЙ
    `docs/invariants.md` не содержит НИ ОДНОЙ подстроки вида
    `orchestrator/<имя>.py`/`scripts/<имя>.py` (проверено `grep`), так что
    положительный (сигнал сработал) случай нельзя собрать ни из какого
    реального пути — только подменой текста документа, который сравнение
    видит. Подменяет `pathlib.Path.read_text` ТОЛЬКО для вызовов на пути
    `docs/invariants.md`; любой другой путь (включая сам `SPEC.md`
    фикстуры, читаемый мимо диска строкой) уходит в оригинальную
    реализацию нетронутым.
    """
    original_read_text = pathlib.Path.read_text

    def _read_text(self, *args, **kwargs):
        if self == INVARIANTS_DOC_PATH:
            return fake_text
        return original_read_text(self, *args, **kwargs)

    with mock.patch.object(pathlib.Path, "read_text", _read_text):
        yield
