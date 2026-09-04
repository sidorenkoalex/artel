"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-3 (сигнал «затронут
инвариантный механизм»).

AC-3 сам по себе не называл правило вычисления сигнала — test_author
эскалировал именно это (см. историю `test_ac_manual_and_escalate_
markers.py` до правки этим коммитом). ANSWER-1 даёт правило буквально:
сигнал срабатывает, если хотя бы одна строка пути вида
`orchestrator/<имя>.py`/`scripts/<имя>.py`, встречающаяся в разделе
«Зоны» SPEC, встречается как подстрока в тексте `docs/invariants.md`;
сравнение буквальное, без разбора смысла.

Наблюдаемая точка сигнала — та же, что у AC-2 (test_ac2_uncertainty_
phrase_signal.py): отказ `guard.check_content` при пустой/отсутствующей
секции «Оценка объёма и деление» — общая механика «отказ + пустая
секция» принадлежит test_ac5, здесь проверяется только само срабатывание
ЭТОГО сигнала по ЭТОМУ правилу.

Реальный `docs/invariants.md` сегодня не содержит НИ ОДНОЙ подстроки
вида `orchestrator/<имя>.py`/`scripts/<имя>.py` (проверено `grep -no
"orchestrator/[A-Za-z_]*\\.py\\|scripts/[A-Za-z_]*\\.py" docs/
invariants.md` — пусто): позитивный случай (сигнал сработал) собран
через `_sandbox.fake_invariants_doc` (подмена `pathlib.Path.read_text`
только для пути `docs/invariants.md`, см. её докстринг) — без подмены
из реального файла позитивный фикстур собрать нечем. Негативный случай
(сигнал НЕ сработал) использует настоящий файл без подмены — путь для
него заведомо отсутствует в реальном документе.

Красен до реализации: guard.py сегодня не знает ни о секции «Зоны», ни о
сравнении с `docs/invariants.md` — `check_content` возвращает пустой
список ошибок для обеих фикстур ниже (позитивной и негативной), пока
разработчик не реализует правило ANSWER-1 (требования 1, 3 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import check, fake_invariants_doc  # noqa: E402

# Путь заведомо отсутствует в реальном docs/invariants.md — фикстура для
# негативного случая не полагается на подмену файла.
ABSENT_FROM_REAL_INVARIANTS = "orchestrator/zzz_fixture_only_module.py"

# Путь для позитивного случая — совпадёт с текстом фиктивного
# docs/invariants.md, который подставляет fake_invariants_doc ниже.
PRESENT_IN_FAKE_INVARIANTS = "scripts/some_guarded_module.py"

FAKE_INVARIANTS_TEXT = (
    "# Инварианты системы\n\n"
    "| # | Инвариант | Тест(ы) | Откуда |\n"
    "|---|---|---|---|\n"
    "| 1 | Пример | `test_x.Y` | `scripts/some_guarded_module.py` "
    "несёт защищённую механику |\n"
)


class InvariantMechanismSignalFiresTest(unittest.TestCase):
    """Путь из раздела «Зоны», буквально встречающийся в тексте
    `docs/invariants.md`, вызывает отказ guard'а, когда секция «Оценка
    объёма и деление» отсутствует.

    Ловит мутацию: реализация сравнивает не с `docs/invariants.md`, а с
    каким-то другим документом (например, `docs/design.md`) — подмена
    `fake_invariants_doc` перестаёт влиять на результат, и тест
    покраснеет уже ПОСЛЕ реализации (ложноотрицательный сигнал).
    """

    def test_ac3_zone_path_found_in_invariants_doc_triggers_refusal(self):
        with fake_invariants_doc(FAKE_INVARIANTS_TEXT):
            errors = check(zone_paths=[PRESENT_IN_FAKE_INVARIANTS],
                           volume_section=None)

        self.assertTrue(
            errors,
            f"путь «{PRESENT_IN_FAKE_INVARIANTS}» в разделе «Зоны», "
            f"буквально встречающийся в docs/invariants.md, не вызвал "
            f"отказ guard'а при отсутствующей секции «Оценка объёма и "
            f"деление»")


class InvariantMechanismSignalDoesNotFireTest(unittest.TestCase):
    """Путь из раздела «Зоны», отсутствующий в тексте реального
    `docs/invariants.md`, НЕ вызывает отказ guard'а (сигнал не
    срабатывает без совпадения) — реальный файл, без подмены.

    Ловит мутацию: реализация срабатывает по любому пути формата
    `orchestrator/<имя>.py`/`scripts/<имя>.py` в разделе «Зоны»
    независимо от того, есть ли он в `docs/invariants.md` (сравнение с
    документом не реализовано вовсе, только распознавание формата пути).
    """

    def test_ac3_zone_path_absent_from_real_invariants_doc_does_not_fire(self):
        errors = check(zone_paths=[ABSENT_FROM_REAL_INVARIANTS],
                       volume_section=None)

        self.assertEqual(
            errors, [],
            f"guard отказал SPEC с путём «{ABSENT_FROM_REAL_INVARIANTS}» "
            f"в разделе «Зоны», которого нет в docs/invariants.md: "
            f"{errors}")


if __name__ == "__main__":
    unittest.main()
