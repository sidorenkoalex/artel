"""AC-6 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: якоря вердикта в журнале нет (или
`код=` не распознан) — прежняя деградация на полный diff от главной
ветки, без исключения.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Журнал задачи не несёт ни одного перехода `state -> in_dev` с
detail «замечания ревью, итерация …» либо `код=` следующей за ним записи
не распознан, а итерация > 1 — пакет остаётся на полном diff от главной
ветки и называет причину текстом; исключения не возникает.

Красен до реализации: `orchestrator/review.py::previous_verdict_sha` переход `state -> in_dev` не ищет вовсе — при двух и более записях «sha зафиксирован» она отдаёт `код=` предпоследней, то есть непустую базу там, где по критерию базы нет, и пакет уходит в инкрементальный diff вместо деградации на полный.

Два других теста файла (нераспознанный `код=` и `diff_type` полного
diff без базы) зелены и до правки намеренно: критерий требует СОХРАНИТЬ
прежнюю деградацию — они сторожат её от потери при переводе базы на
якорь вердикта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import config, review  # noqa: E402


class NoVerdictAnchorTest(_sandbox.ReviewPackagePlankSandbox):

    def test_ac6_journal_without_the_verdict_transition_has_no_base(self):
        """В журнале есть записи фиксации (переходы задачи были), но ни
        одного перехода `state -> in_dev` с detail «замечания ревью,
        итерация …» — базы нет.

        Ловит мутацию: якорь ищется только по записям «sha зафиксирован»,
        без требования предшествующего перехода по вердикту — вернётся
        непустой sha, и assertEqual с пустой строкой покраснеет.
        """
        first = self.developer_commit(f"{_sandbox.DEV_MARK}-1\n")
        second = self.developer_commit(f"{_sandbox.DEV_MARK}-2\n")
        self.journal_transition("in_dev", "план принят")
        self.journal_fixation(first)
        self.journal_transition("review")
        self.journal_fixation(second)

        base = review.previous_verdict_sha(self.conn, self.TASK)

        self.assertEqual(base, "", "якоря вердикта в журнале нет — базы нет")

    def test_ac6_unrecognised_code_sha_after_the_anchor_has_no_base(self):
        """Якорь в журнале есть, но у следующей за ним записи фиксации
        `код=` не распознан (git не ответил в момент той фиксации —
        `код=—`) — базы нет.

        Ловит мутацию: `код=` разбирается «до конца строки» вместо
        шестнадцатеричного sha — прочерк уедет в базу diff как имя
        ревизии, git на неё ответит отказом, и пакет покажет «не собран»
        вместо честной деградации.
        """
        self.journal_transition(
            "in_dev", _sandbox.VERDICT_DETAIL_TMPL.format(n=1))
        self.journal_fixation("—")
        self.journal_fixation(self.developer_commit(f"{_sandbox.DEV_MARK}\n"))

        base = review.previous_verdict_sha(self.conn, self.TASK)

        self.assertEqual(base, "", "`код=` следующей записи не распознан — "
                                   "базы нет")

    def test_ac6_iteration_two_without_a_base_stays_on_the_full_diff(self):
        """Шаг ревью итерации 2 при журнале без якоря: пакет собирается
        без исключения, diff остаётся полным от главной ветки, а текст
        пакета называет причину.

        Ловит мутацию: ветка деградации снята (база `None`/пустая строка
        уходит в `git diff` как есть) — диапазон diff перестанет
        начинаться с главной ветки, а причина исчезнет из текста.
        """
        self.developer_commit(f"{_sandbox.DEV_MARK}\n")
        self.journal_transition("in_dev", "план принят")
        self.journal_fixation(self.head(self.BRANCH))
        self.journal_transition("review")
        self.journal_fixation(self.head(self.BRANCH))

        text = self.build_prompt(reviewed_iter=1)

        self.assertIn(f"### Diff (git diff {config.MAIN_BRANCH}..."
                      f"{self.BRANCH})", text,
                      "без базы diff остаётся полным от главной ветки")
        self.assertIn("Diff выше — полный", text,
                      "прежняя деградация называет причину текстом пакета")

    def test_ac6_package_reports_the_full_diff_type_without_a_base(self):
        """Тот же вырожденный случай в структурном виде: `diff_type`
        пакета итерации 2 без базы — «полный».

        Ловит мутацию: признак типа diff выставляется по одному лишь
        номеру итерации (`iteration > 1` — значит инкрементальный), без
        учёта того, нашлась ли база — журнал и заметка пакета начнут
        называть инкрементальным полный diff.
        """
        package = self.package(iteration=2, prev_sha="")

        self.assertEqual(package["diff_type"], "полный")


if __name__ == "__main__":
    unittest.main()
