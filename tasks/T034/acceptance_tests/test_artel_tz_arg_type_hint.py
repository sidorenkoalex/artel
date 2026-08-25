"""Приёмочные тесты T034: AC-10 — type-hint возврата `artel.py: _tz_arg`.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 7
(ревью T025): `_tz_arg` объявлена `-> str`, но фактически возвращает
`None`, когда флага `--tz` нет (см. `if "--tz" not in rest: return None`).
Аннотация должна допускать `None`.
"""
import sys
import typing
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import artel  # noqa: E402


class Ac10TzArgReturnTypeAllowsNoneTest(unittest.TestCase):
    """AC-10: аннотация возврата `_tz_arg` допускает `None`."""

    def test_ac10_return_annotation_includes_none(self):
        hints = typing.get_type_hints(artel._tz_arg)
        ret = hints["return"]

        args = typing.get_args(ret)
        self.assertIn(
            type(None), args,
            f"аннотация возврата _tz_arg ({ret!r}) не допускает None, а "
            f"функция возвращает None при отсутствии флага --tz")

    def test_ac10_actual_behaviour_without_the_flag_is_still_none(self):
        """Смежная гарантия: правка типа не меняет фактическое поведение."""
        self.assertIsNone(artel._tz_arg([]))


if __name__ == "__main__":
    unittest.main()
