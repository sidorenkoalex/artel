"""Форма критерия ADR-0032 совместима с проверками guard.

Строки «Поверхность решения: …» и «Размер проверки: …» (в том числе
«большой — <обоснование>») внутри критериев SPEC не меняют ни исход
`scripts.guard.check_content`, ни число распознанных критериев, ни сверку
покрытия тестами `scripts.guard.traceability_errors_from_content`; пункт
`1. Размер проверки: …` по-прежнему отказ как пункт без AC-разметки.

Тексты SPEC собираются строками в памяти при каждом запуске из случайных
слов (зерно печатается и входит в текст провала); файлов, git и процессов
тесты не трогают.

Группа: долгоживущий
Зелёный с рождения: код guard задача не меняет — тесты закрепляют, что его правила разбора уже принимают новую форму критерия и не ослаблены под неё.
"""
import random
import re

import pytest

from scripts import guard

META = {"schema_version": 5}
WORDS = ("команда", "отказ", "журнал", "ветка", "задача", "критерий", "вход",
         "выход", "строка", "текст", "сообщение", "состояние", "переход")
MODULES = ("scripts.guard", "orchestrator.fsm", "orchestrator.advance_gates.mandate",
           "orchestrator.catalog")
NAMES = ("check_content", "matrix_refusals", "decide", "parse_mark", "verdict")
ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ROUNDS = 20
# Мутация AC-5: пункт «без AC-разметки» срабатывает на строке со слова.
MUTATED_PLAIN_ITEM = re.compile(r"^\w+\.?\s+\S", re.M)


def _rng():
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def _phrase(rng, n=4):
    return " ".join(rng.choice(WORDS) for _ in range(n))


def _criteria(rng):
    """Три критерия: у каждого строка размера (малый, средний, большой с
    обоснованием), у первого — строка поверхности решения."""
    module, name = rng.choice(MODULES), rng.choice(NAMES)
    surface = (f"Поверхность решения: {module}.{name}({rng.choice(WORDS)}, "
               f"{rng.choice(WORDS)}) -> {rng.choice(('list', 'str', 'dict', 'tuple'))}")
    sizes = ("Размер проверки: малый", "Размер проверки: средний",
             f"Размер проверки: большой — {_phrase(rng, 5)}")
    blocks = []
    for n, size in enumerate(sizes, start=1):
        lines = [f"AC-{n}. Given {_phrase(rng)}, When {_phrase(rng)}, "
                 f"Then {_phrase(rng)}."]
        if n == 1:
            lines.append(surface)
        lines.append(size)
        blocks.append("\n".join(lines))
    return blocks


def _strip_form(blocks):
    return [re.sub(r"^(Поверхность решения|Размер проверки):.*\n?", "", b,
                   flags=re.M).rstrip("\n") for b in blocks]


def _spec(rng, blocks):
    task = "".join(rng.choice(ULID) for _ in range(26))
    return (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: 5\nzones: tests/\n"
            f"budget_usd: 25\n---\n\n# SPEC: {_phrase(rng)}\n\n"
            f"## Контекст\n{_phrase(rng)}.\n\n## Требования\n1. {_phrase(rng)}.\n\n"
            f"## Критерии приёмки\n\n" + "\n\n".join(blocks) + "\n\n"
            f"## Оценка объёма и деление\nСработавшие сигналы: нет.\n\n"
            f"## Не входит\n- {_phrase(rng)}.\n")


def _ac2_problems(text):
    """Расхождения текста SPEC с исходом AC-2 (пустой список — исход тот)."""
    problems = []
    content = guard.check_content("SPEC.md", text)
    if content != []:
        problems.append(f"check_content: {content}")
    trace = guard.traceability_errors_from_content(text, META, {1, 2}, {})
    if len(trace) != 1 or not trace[0].startswith("AC-3:"):
        problems.append(f"сверка покрытия: {trace}")
    return problems


@pytest.mark.parametrize("with_form", [True, False])
def test_ac2_size_and_surface_lines_keep_guard_outcome(with_form):
    """SPEC из трёх критериев со строками размера и поверхности и без них проходит guard одинаково.

    На случайных текстах критериев `check_content` возвращает пустой
    список, а сверка покрытия при тестах только на AC-1 и AC-2 — ровно
    одну ошибку, называющую AC-3: третий критерий распознан, всего их
    три. Вариант без строк размера и поверхности — тот же исход.

    Ловит мутацию: разбор критериев начинает считать строку «Размер
    проверки: …» или «Поверхность решения: …» пунктом без AC-разметки
    (или концом раздела критериев) — `check_content` отдаёт отказ либо
    AC-3 не распознан и сверка покрытия возвращает пустой список.
    """
    seed, rng = _rng()
    for _ in range(ROUNDS):
        blocks = _criteria(rng)
        text = _spec(rng, blocks if with_form else _strip_form(blocks))
        assert _ac2_problems(text) == [], f"зерно: {seed}\n{text}"


def test_ac3_numbered_size_line_refused_like_plain_item():
    """Строка `1. Размер проверки: малый` в критерии отказывает так же, как пункт без AC-разметки.

    В ту же SPEC вместо строки размера первого критерия ставится
    `1. Размер проверки: малый`; `check_content` отказывает, и его ответ
    совпадает с ответом на ту же SPEC с отдельным пунктом `1. <текст>`
    без разметки в разделе критериев — правило разбора не ослаблено.

    Ловит мутацию: `PLAIN_NUMBERED_ITEM` ослаблен, чтобы пропускать
    строки «N. Размер проверки:» (исключение под новую форму) — на такой
    SPEC `check_content` возвращает пустой список.
    """
    seed, rng = _rng()
    for _ in range(ROUNDS):
        blocks = _criteria(rng)
        numbered = [blocks[0].replace("Размер проверки: малый",
                                      "1. Размер проверки: малый")] + blocks[1:]
        plain = blocks[:1] + [f"1. {_phrase(rng)}."] + blocks[1:]
        errors = guard.check_content("SPEC.md", _spec(rng, numbered))
        reference = guard.check_content("SPEC.md", _spec(rng, plain))
        assert errors, f"зерно: {seed}: отказа нет\n{numbered}"
        assert any("без AC-разметки" in e for e in errors), f"зерно: {seed}: {errors}"
        assert errors == reference, f"зерно: {seed}"


@pytest.mark.parametrize("tested, expected_prefix", [
    ({1, 2, 3}, None),
    ({1, 3}, "AC-2: нет теста"),
    ({1, 2, 3, 4}, "AC-4: тест на критерий, которого нет в SPEC"),
])
def test_ac4_traceability_on_criteria_with_form_lines(tested, expected_prefix):
    """Сверка покрытия SPEC со строками размера и поверхности: полное покрытие, пропуск и лишний тест.

    На случайной SPEC из трёх критериев с новыми строками
    `traceability_errors_from_content` при тестах на AC-1–AC-3 возвращает
    пустой список, при тестах только на AC-1 и AC-3 — ровно одну ошибку
    «AC-2: нет теста…», с добавочным тестом на AC-4 — ровно одну ошибку
    «AC-4: тест на критерий, которого нет в SPEC».

    Ловит мутацию: строка «Размер проверки: …» или «Поверхность решения:
    …» обрывает разбор раздела или критерий распознаётся по строке
    размера дважды — AC-2/AC-3 не находятся (лишние ошибки при полном
    покрытии, нет ошибки «AC-2») или находится лишний критерий.
    """
    seed, rng = _rng()
    for _ in range(ROUNDS):
        text = _spec(rng, _criteria(rng))
        errors = guard.traceability_errors_from_content(text, META, set(tested), {})
        if expected_prefix is None:
            assert errors == [], f"зерно: {seed}: {errors}"
        else:
            assert len(errors) == 1, f"зерно: {seed}: {errors}"
            assert errors[0].startswith(expected_prefix), f"зерно: {seed}: {errors}"


def test_ac5_word_start_mutation_turns_ac2_red(monkeypatch):
    """Мутация `PLAIN_NUMBERED_ITEM` на строку со слова делает тест AC-2 красным на SPEC с новыми строками.

    В процессе теста `guard.PLAIN_NUMBERED_ITEM` подменяется формой
    `^\\w+\\.?\\s+\\S`; тест AC-2 в варианте со строками «Поверхность
    решения» и «Размер проверки» падает. Без подмены тот же вызов зелёный —
    краснота вызвана именно мутацией.

    Ловит мутацию: тест AC-2 перестаёт звать `check_content` (сверяет
    только покрытие) или собирает SPEC без строк размера и поверхности —
    под подменой регулярки он остаётся зелёным, и этот тест краснеет.
    """
    test_ac2_size_and_surface_lines_keep_guard_outcome(True)
    monkeypatch.setattr(guard, "PLAIN_NUMBERED_ITEM", MUTATED_PLAIN_ITEM)
    with pytest.raises(AssertionError):
        test_ac2_size_and_surface_lines_keep_guard_outcome(True)
