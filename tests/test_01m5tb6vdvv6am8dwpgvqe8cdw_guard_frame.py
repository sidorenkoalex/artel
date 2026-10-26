"""Проверка поля «Рамка:» частей деления в `scripts/guard.py`.

Группа: долгоживущий
Красен до реализации: guard разбирает «Рамка:», но значение не проверяет — $150, «тридцать», $0 и рамка выше `ROLE_BUDGET_CAP` ошибки не дают.

Модульный тест без песочницы: предмет — чистая проверка текста SPEC
(`guard.check_content`). Ошибка рамки выделяется сравнением с тем же
SPEC без рамки вовсе, поэтому прочие правила guard на результат не
влияют. Число частей и позиция части с рамкой порождаются модулем
`random` при каждом запуске; зерно печатается и входит в текст провала.
"""
import random
import re

import pytest

from orchestrator import config
from scripts import guard

ZONE = "orchestrator/t_frame_zone.py"
FIRST = "первая, без зависимостей"
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб")


def spec_text(parts: list) -> str:
    """SPEC родителя; `parts` — (название, «Рамка:» или None)."""
    sections = "".join(
        f"### {title}\n\nЗоны: {ZONE}\n"
        f"Порядок: {FIRST if n == 1 else f'после части {n - 1}'}\n"
        + (f"Рамка: {frame}\n" if frame is not None else "")
        + f"\nТекст ТЗ части «{title}».\n\n"
        for n, (title, frame) in enumerate(parts, 1))
    return f"""---
task: T9001
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 15
zones: {ZONE}
---

# SPEC: Родитель деления

## Контекст
Фикстура деления.

## Требования
1. Фикстура.

## Критерии приёмки
AC-1. Фикстура.

## Оценка объёма и деление
Фикстура.

## Деление

{sections}## Не входит
- Всё остальное.
"""


def frame_value(kind: str) -> str:
    cap = config.ROLE_BUDGET_CAP
    if kind == "$150":
        return "$150" if cap < 150 else f"${cap + 50:.2f}"
    if kind == "cap+0.01":
        return f"${cap + 0.01:.2f}"
    if kind == "cap":
        return f"${cap:.2f}"
    if kind == "cap без $":
        return f"{cap:.2f}"
    return kind


def scenario(kind: str):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    names = [f"Узел {w}" for w in rng.sample(WORDS, rng.randint(2, 4))]
    position = rng.randrange(len(names))
    plain = guard.check_content("SPEC.md", spec_text(
        [(t, None) for t in names]))
    framed = [(t, frame_value(kind) if n == position else None)
              for n, t in enumerate(names)]
    errors = guard.check_content("SPEC.md", spec_text(framed))
    extra = [e for e in errors if e not in plain]
    return seed, names[position], position + 1, extra, (names, plain)


def names_part(text: str, number: int, title: str) -> bool:
    return bool(title in text or re.search(
        rf"част\w*\s*№?\s*{number}(?!\d)", text, re.IGNORECASE))


@pytest.mark.parametrize("kind", ["$150", "тридцать", "$0", "cap+0.01"])
def test_ac13_bad_frame_is_guard_error_naming_part(kind):
    """Рамка части $150, «тридцать», $0 или на $0.01 выше `ROLE_BUDGET_CAP`: guard даёт ошибку сверх ошибок того же SPEC без рамки, и она называет эту часть.

    Ловит мутацию: значение рамки не проверяется вовсе; проверяется
    только нечисловое значение, без границ ≤ 0 и выше потолка ролей;
    граница выше потолка сравнивается с `DEFAULT_BUDGET_USD` или через
    округление до целого — $cap+0.01 проходит; ошибка не называет часть.
    """
    seed, title, number, extra, _ = scenario(kind)
    assert extra, f"зерно: {seed}; рамка {frame_value(kind)!r} части " \
                  f"«{title}» ошибки не дала"
    assert any(names_part(e, number, title) for e in extra), (
        f"зерно: {seed}; ошибка не называет часть «{title}»: {extra}")


@pytest.mark.parametrize("kind", ["cap", "cap без $", None])
def test_ac13_frame_at_cap_or_absent_is_not_error(kind):
    """Рамка, равная `ROLE_BUDGET_CAP` (с `$` и без), и часть без «Рамка:» ошибок сверх SPEC без рамки не дают.

    Ловит мутацию: граница сравнивается `>=` — рамка, равная потолку
    ролей, становится ошибкой; `$` не снимается до разбора числа —
    «$N» считается нечисловым; отсутствие поля «Рамка:» объявлено
    ошибкой (поле стало обязательным).
    """
    if kind is None:
        # SPEC, где ни у одной части нет «Рамка:», — база сравнения
        # сценария: ни одна её ошибка не называет часть и не говорит о
        # рамке.
        seed, _, _, _, (names, plain) = scenario("$1")
        about_parts = [e for e in plain
                       if "Рамка" in e or any(t in e for t in names)]
        assert about_parts == [], (f"зерно: {seed}; части без рамки дали "
                                   f"ошибки: {about_parts}")
        return
    seed, title, _, extra, _ = scenario(kind)
    assert extra == [], (f"зерно: {seed}; рамка {frame_value(kind)!r} части "
                         f"«{title}» дала ошибки: {extra}")
