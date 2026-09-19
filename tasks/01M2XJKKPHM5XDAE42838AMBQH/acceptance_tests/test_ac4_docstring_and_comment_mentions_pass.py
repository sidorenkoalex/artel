"""AC-4 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): упоминание имени
артефакта (`PLAN.md`, `SPEC.md`, `REVIEW.md`, `TZ.md`, `QUESTIONS.md`,
`TEST_REPORT.md`, `ANSWER-`) в докстринге или комментарии планки ошибкой
не считается — выход из `tests_writing` проходит.

Сценарий нарочно неудобен для проверки «по тексту строки»: имена
артефактов стоят и в докстринге модуля, и в отдельных комментариях, и —
самое существенное — в КОНЦЕВОМ комментарии строки, где рядом настоящее
обращение к файловой системе, но к файлу, артефактом задачи не
являющемуся.

Красен до реализации: контроль в начале теста требует отказа на чтении
`PLAN.md` с диска, а гейта «планка читает артефакты с диска» ещё нет —
вложенная задача уходит в `in_dev` и на нарушающей планке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

DOCSTRING_EXTRA = """

PLAN.md, SPEC.md, REVIEW.md, TZ.md, QUESTIONS.md, TEST_REPORT.md и
ANSWER-1.md эта планка читает из артефактной ветки — здесь имена
названы текстом докстринга, обращения к диску за ними нет."""

MENTIONS_BODY = [
    '# REVIEW.md и TEST_REPORT.md живут в артефактной ветке задачи,',
    '# читать их с диска (QUESTIONS.md, ANSWER-1.md — тоже) незачем.',
    'sample = (Path(__file__).resolve().parents[1] / "fixture.txt")'
    '  # рядом с SPEC.md',
    'data = open("fixture.txt", encoding="utf-8")  # не PLAN.md',
]


class MentionsInProseDoNotRefuseTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac4_docstring_and_comment_mentions_do_not_refuse_the_exit(self):
        """Планка вложенной задачи называет все семь имён артефактов в
        докстринге модуля и в комментариях (в том числе в концевом
        комментарии строки с настоящим чтением постороннего
        `fixture.txt`), но ни одного артефакта с диска не читает — после
        контроля, доказавшего срабатывание проверки, выход из
        `tests_writing` проходит в `in_dev`.

        Ловит мутацию: проверка ищет имя артефакта в сыром тексте строки
        рядом с признаком доступа к файловой системе, не спрашивая AST,
        откуда это имя (комментарий/докстринг или строковый литерал
        выражения) — строка `sample = (... / "fixture.txt")  # рядом с
        SPEC.md` тут же даст ложную ошибку, и переход останется в
        `tests_writing`.
        """
        self.enter_tests_writing()
        self.control_refuses()

        self.write_plank(_sandbox.plank_source(MENTIONS_BODY,
                                               extra=DOCSTRING_EXTRA))

        out = self.advance()

        self.assertEqual(
            self.state(), "in_dev",
            f"имена артефактов в докстринге и комментариях не должны "
            f"отклонять переход; вывод advance: {out!r}")


if __name__ == "__main__":
    unittest.main()
