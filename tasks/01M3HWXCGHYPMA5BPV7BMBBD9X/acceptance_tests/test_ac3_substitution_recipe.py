"""AC-3 — для свойства, наблюдаемого только подменой, скил называет приём:
подмена зависимости и проверка её вызова.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Там же назван приём для свойства, наблюдаемого только подменой:
подмена зависимости и проверка её вызова.

«Там же» — тот же раздел `skills/test-authoring.md` о заявке мутации
(раздел, называющий маркер `Ловит мутацию`), текст берётся после
применения приложений PLAN к базе сравнения (см. `_appendix`).

Красен до реализации: приложения на `skills/test-authoring.md` ещё нет —
в разделе о заявке мутации базы сравнения нет ни слова о подмене
зависимости, ни о проверке её вызова.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402


class SubstitutionRecipeTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()
        self.section = _appendix.mutation_claim_text(
            _appendix.applied_text(_appendix.TEST_AUTHORING))

    def test_ac3_names_dependency_substitution_and_call_check(self):
        """Раздел о заявке мутации называет приём для свойства, которое
        иначе не наблюдается: в одной фразе стоят подмена и вызов, а сам
        раздел говорит о зависимости, которую подменяют.

        Ловит мутацию: правка называет подмену, но не говорит, что
        наблюдением служит ПРОВЕРКА ВЫЗОВА подменённой зависимости
        (обрывается на «подмени зависимость») — фразы, где подмена и вызов
        стоят рядом, не появится, и проверка покраснеет.
        """
        self.assertTrue(
            self.section,
            f"в `{_appendix.TEST_AUTHORING}` после применения приложений нет "
            f"ни одного раздела о заявке мутации ({self.state.diagnosis()})")
        absent = _appendix.missing(self.section, ("подмен", "завис"))
        self.assertEqual(
            [], absent,
            f"раздел о заявке мутации не называет приём подмены зависимости "
            f"(нет слов: {absent}) ({self.state.diagnosis()})")
        together = [s for s in _appendix.sentences_with(self.section, "подмен")
                    if _appendix.has(s, "вызов")]
        self.assertTrue(
            together,
            f"в разделе о заявке мутации нет фразы, где подмена и проверка "
            f"её ВЫЗОВА стоят вместе — приём для свойства, наблюдаемого "
            f"только подменой, не назван ({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
