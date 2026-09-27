"""AC-6 — дифф задачи в планке считается от точки расхождения с
`origin/<основная ветка>`; локальная ветка — только когда origin
недоступен.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. После применения приложения `skills/test-authoring.md` требует
считать дифф задачи в планке от точки расхождения с
`origin/<основная ветка>` и разрешает локальную ветку только при
недоступном `origin`.

Проверяется абзац скила после применения приложений PLAN к базе сравнения
(см. `_appendix`): критерий не называет раздела, поэтому ищется абзац,
который говорит о диффе задачи, точке расхождения и origin.

Красен до реализации: приложения на `skills/test-authoring.md` ещё нет — в
базе сравнения слово «расхождение» не встречается вовсе, правила базы
диффа для планки в скиле нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402


class DiffBaseFromOriginTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()
        self.text = _appendix.applied_text(_appendix.TEST_AUTHORING)
        self.candidates = [
            p for p in _appendix.paragraphs_with(self.text, "расхожден")
            if _appendix.has(p, "origin") and _appendix.has(p, "диф")]

    def test_ac6_requires_divergence_point_with_origin(self):
        """Скил требует считать дифф задачи в планке от точки расхождения с
        `origin/<основная ветка>`: есть абзац, где рядом стоят дифф, точка
        расхождения и origin.

        Ловит мутацию: правка говорит «считай дифф от main», не называя
        origin (та же ошибка, из-за которой планка
        01M3H3JW9XE1THF0HK8RESZ0CV считала дифф от локальной ветки-пина и
        эскалировала исправную задачу на мерже) — абзаца с origin рядом с
        точкой расхождения не появится, и проверка покраснеет.
        """
        self.assertTrue(
            self.text,
            f"текст `{_appendix.TEST_AUTHORING}` после применения приложений "
            f"пуст ({self.state.diagnosis()})")
        self.assertTrue(
            self.candidates,
            f"в `{_appendix.TEST_AUTHORING}` нет абзаца о базе диффа задачи: "
            f"ищется абзац со словами «расхожден», «origin» и «диф» "
            f"({self.state.diagnosis()})")

    def test_ac6_allows_local_branch_only_when_origin_unavailable(self):
        """Тот же абзац разрешает локальную ветку ТОЛЬКО когда origin
        недоступен: рядом с локальной веткой стоит условие недоступности.

        Ловит мутацию: правка называет origin предпочтительной базой, но
        оставляет локальную ветку равноправной альтернативой («или от
        локальной main») — условия недоступности origin в абзаце не будет, и
        проверка покраснеет.
        """
        self.assertTrue(
            self.candidates,
            f"абзаца о базе диффа задачи нет вовсе — условие про локальную "
            f"ветку проверять не на чем ({self.state.diagnosis()})")
        conditioned = [p for p in self.candidates
                       if _appendix.has(p, "локальн")
                       and (_appendix.has(p, "недоступ")
                            or _appendix.has(p, "отсутств")
                            or _appendix.has(p, "нет"))]
        self.assertTrue(
            conditioned,
            f"абзац о базе диффа не оговаривает, что локальная ветка годится "
            f"только при недоступном origin (ищутся «локальн» и "
            f"«недоступ»/«отсутств»/«нет» в том же абзаце) "
            f"({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
