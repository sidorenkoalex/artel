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
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

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

## Критерии приёмки
AC-1. Первый критерий фикстуры.
AC-2. Второй критерий фикстуры.

## Не входит
- Всё остальное.
{volume_block}"""


def spec_text(*, extra_requirement_sentence: str = "",
              volume_section: str | None = "") -> str:
    """Текст фиктивного `SPEC.md`.

    `extra_requirement_sentence` дописывается отдельным предложением в
    конец требования 1 — место для триггерной фразы сигнала AC-2, пусто по
    умолчанию (ни одна из трёх фраз не встречается).

    `volume_section` — тело секции `## Оценка объёма и деление`: `None` —
    секция отсутствует целиком, `""` (умолчание) — заголовок есть, тело
    пустое, любая другая строка — заданное содержимое секции.
    """
    extra = f" {extra_requirement_sentence}" if extra_requirement_sentence else ""
    if volume_section is None:
        volume_block = ""
    else:
        volume_block = f"\n## Оценка объёма и деление\n{volume_section}\n"
    return SPEC_TEMPLATE.format(task=FIXTURE_TASK_ID, extra=extra,
                                volume_block=volume_block)


def check(**kwargs) -> list[str]:
    """`guard.check_content` над `spec_text(**kwargs)` — экономит
    повторение `guard.check_content("SPEC.md", spec_text(...))` в каждом
    тесте."""
    return guard.check_content("SPEC.md", spec_text(**kwargs))
