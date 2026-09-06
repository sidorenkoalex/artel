"""AC-1/AC-2 (tasks/01M1TKNXX5YN5KT4WHG4T44JWV/SPEC.md): единый
неизменяемый тип исхода гейта и функции-предикаты, возвращающие его без
побочных эффектов.

Ни AC-1, ни AC-2 не называют символ по имени (пример «GateRefusal» есть
только в разделе «Требования» SPEC, не в самих критериях) — тесты ищут
тип/предикаты СТРУКТУРНО через `_sandbox.py` (frozen-dataclass/
NamedTuple, аннотация возврата `<тип> | None`), не по зашитому имени.
Метод обнаружения провалидирован временным стабом (`GateRefusal`-подобный
класс + предикат-функция, синтетический AST) перед тем, как эти тесты
были зафиксированы — стаб не коммитился.

Красен до реализации: `orchestrator/fsm_advance.py` сегодня не содержит
ни одного frozen-dataclass/`NamedTuple` — гейты возвращают голый `bool`
(`_capacity_gate_refuses`/`_zones_gate_refuses`/`_review_rework_gate_
refuses`), единого типа исхода нет вовсе.
"""
import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox as gate_ast  # noqa: E402


class Ac1ImmutableOutcomeTypeExistsTest(unittest.TestCase):

    def test_ac1_a_single_frozen_outcome_type_exists_with_enough_fields(self):
        """Существует ровно предсказуемый класс-исход гейта: frozen-
        dataclass либо `NamedTuple`, объявленный прямо в `fsm_advance.py`
        (SPEC не даёт разработчику заводить его в новом файле — зона
        задачи ограничена `orchestrator/fsm_advance.py`, `tests/`), несущий
        не менее двух полей — по формулировке AC-1, достаточно данных,
        чтобы воспроизвести и запись `store.journal`, и печать подсказки.

        Ловит мутацию: тип исхода сделан обычным mutable-классом (голый
        `@dataclass` без `frozen=True`, либо `class X: def __init__...`
        без иммутабельности) — ни одна из двух распознаваемых форм не
        совпадёт, список окажется пустым.
        """
        names = gate_ast.find_immutable_outcome_type_names()

        self.assertEqual(
            len(names), 1,
            f"ожидался ровно один неизменяемый тип исхода гейта в "
            f"fsm_advance.py, найдено: {names!r}")

    def test_ac1_the_outcome_type_instance_is_immutable_after_construction(self):
        """Экземпляр найденного типа исхода — неизменяем: попытка
        присвоить значение существующему полю после конструирования
        обязана провалиться, как и требует AC-1 («неизменяемый тип»).

        Ловит мутацию: `frozen=True` снят с декоратора (или NamedTuple
        заменён на обычный класс с изменяемыми атрибутами) — присваивание
        полю после создания молча проходит вместо исключения.
        """
        names = gate_ast.find_immutable_outcome_type_names()
        self.assertTrue(names, "тип исхода не найден — см. предыдущий тест")
        from orchestrator import fsm_advance
        cls = getattr(fsm_advance, names[0])
        if dataclasses.is_dataclass(cls):
            field_names = [f.name for f in dataclasses.fields(cls)]
        else:
            field_names = list(getattr(cls, "_fields"))
        self.assertGreaterEqual(
            len(field_names), 2,
            f"тип исхода {names[0]} обязан нести хотя бы 2 поля (текст "
            f"для store.journal и текст подсказки), нашлось: {field_names!r}")
        instance = cls(**{name: f"x-{name}" for name in field_names})

        with self.assertRaises(
                (dataclasses.FrozenInstanceError, AttributeError),
                msg="присваивание полю уже созданного исхода обязано "
                    "падать — тип объявлен неизменяемым"):
            setattr(instance, field_names[0], "мутация")


class Ac2GatePredicatesHaveNoSideEffectsTest(unittest.TestCase):

    def test_ac2_at_least_one_predicate_returns_the_outcome_type_or_none(self):
        """Существует хотя бы одна функция-гейт в `fsm_advance.py` с
        аннотацией возврата ровно `<тип исхода> | None` — буквальная форма
        сигнатуры из AC-2.

        Ловит мутацию: гейт-предикаты не получили аннотацию возврата (или
        аннотированы иначе, например просто `bool`) — поиск по AST не
        находит ни одной функции с такой сигнатурой.
        """
        type_names = gate_ast.find_immutable_outcome_type_names()
        self.assertTrue(type_names, "тип исхода не найден — см. AC-1")

        predicates = gate_ast.find_predicate_function_names(type_names[0])

        self.assertTrue(
            predicates,
            f"ни одна функция fsm_advance.py не аннотирована как "
            f"-> {type_names[0]} | None")

    def test_ac2_predicate_bodies_never_call_store_journal_or_print(self):
        """Ни одна функция с сигнатурой предиката (`-> <тип исхода> |
        None`) не вызывает `store.journal(...)`/`print(...)` в своём
        собственном теле — побочные эффекты (запись в журнал, печать
        подсказки) принадлежат только каркасу-применителю, не отдельному
        гейту (AC-2).

        Ловит мутацию: предикат сам журналирует отказ и/или печатает
        подсказку (старый стиль `_capacity_gate_refuses`, перенесённый в
        новую функцию без вычищения побочных эффектов) — счётчик вызовов
        `store.journal`/`print` в его теле окажется не нулевым.
        """
        type_names = gate_ast.find_immutable_outcome_type_names()
        self.assertTrue(type_names, "тип исхода не найден — см. AC-1")
        predicates = gate_ast.find_predicate_function_names(type_names[0])
        self.assertTrue(predicates, "предикатов не найдено — см. предыдущий тест")

        offenders = []
        for name in predicates:
            journal_calls, print_calls = gate_ast.function_side_effect_calls(name)
            if journal_calls or print_calls:
                offenders.append((name, journal_calls, print_calls))

        self.assertEqual(
            offenders, [],
            f"эти предикаты несут побочные эффекты в своём теле: {offenders!r}")


if __name__ == "__main__":
    unittest.main()
