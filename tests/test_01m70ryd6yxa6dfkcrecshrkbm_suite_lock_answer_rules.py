"""Правило пустого основания `suite-lock` по ANSWER-1 (п. 4): основание,
пустое после `strip()`, — отказ разбора до взятия замка, как `--reason ""`.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/suite_hold.py` на базе ещё нет — импорт в теле теста падает.

Поверхность решения `suite_hold.refusal` проверяется малым тестом: случаи —
литералами `parametrize`, команда и прочие значения — от `random`, зерно
печатается и входит в текст провала.
"""
import random
import string

import pytest

pytestmark = pytest.mark.size("small")

LETTERS = string.ascii_letters + string.digits + "абвгдеёжзийклмнопрстуфхцчшщэюя"


def seeded() -> tuple[int, random.Random]:
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def word(rng: random.Random) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(rng.randint(1, 8)))


@pytest.mark.parametrize("reason, refused", [
    ("   ", True),
    ("\n\r", True),
    (" \t\n ", True),
    (" r ", False),
])
def test_blank_reason_refused_before_lock(reason, refused):
    """Основание из одних пробелов или переводов строк — отказ `refusal`, основание с непробельным символом — не отказ.

    Сценарий: `--reason <reason> -- <случайная команда>`; `--reason "   "`,
    `--reason "\\n\\r"` и смесь пробельных — отказ (непустая строка);
    основание « r » с пробелами по краям — `None`.

    Ловит мутацию: пустым считается только `""` — основание из пробелов
    или переводов строк проходит разбор и пишется в замок пустым после
    `reason_text`; `strip()` применён к проверке и отказывает основанию с
    непробельным символом внутри.
    """
    from orchestrator import suite_hold

    seed, rng = seeded()
    argv = ["--reason", reason, "--", word(rng), word(rng)]

    text = suite_hold.refusal(argv)

    where = f"зерно {seed}: {argv!r} → {text!r}"
    if refused:
        assert isinstance(text, str) and text, where
    else:
        assert text is None, where
