"""AC-7 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: инкремент несёт правку разработчика
и не несёт изменений main, пришедших подтяжкой.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. С базы вердикта в ветку задачи пришли и правка разработчика (файл
A), и подтяжка main merge-коммитом (файл B, разработчиком не тронут) —
инкрементальный diff пакета несёт изменения A и не несёт изменений B;
заметка под diff'ом называет базу (sha вердикта) и голову ветки.

Красен до реализации: инкрементальный diff собирается как `git diff
<база>...<ветка>` по всему дереву за вычетом `tasks/<id>/`
(`orchestrator/review.py::review_package`) — изменения, пришедшие
подтяжкой main, попадают в него наравне с правкой разработчика; плюс
сама база сегодня берётся предпоследней записью журнала, а не по якорю
вердикта, поэтому диапазон в пакете тоже другой.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

DEV_EDIT = f"{_sandbox.DEV_MARK}-итерация-2"
MAIN_EDIT = f"{_sandbox.MAIN_MARK}-чужая-правка"


class IncrementCarriesOnlyOwnCommitsTest(_sandbox.ReviewPackagePlankSandbox):

    def setUp(self):
        super().setUp()
        # Итерация 2 задачи: вердикт итерации 1 вынесен на `verdict_sha`,
        # дальше правка разработчика (файл A) и подтяжка main
        # merge-коммитом (файл B) — каждая со своей записью фиксации в
        # журнале, как их пишет настоящий переход/автокоммит.
        self.verdict_sha = self.developer_commit(
            f"{_sandbox.DEV_MARK}-база\n")
        self.journal_verdict_anchor(self.verdict_sha, iteration=1)
        self.dev_sha = self.developer_commit(f"{DEV_EDIT}\n")
        self.journal_transition("review")
        self.journal_fixation(self.dev_sha)
        self.merge_sha = self.main_pull_merge(f"{MAIN_EDIT}\n")
        self.journal_fixation(self.merge_sha)

    def test_ac7_increment_shows_the_developer_edit(self):
        """С базы вердикта разработчик правил файл A, а подтяжка main
        принесла файл B — правка A обязана быть в инкрементальном diff
        пакета.

        Ловит мутацию: ограничение путей собрано не по СОБСТВЕННЫМ
        коммитам ветки, а по коммитам подтяжки (перепутаны стороны
        обхода) — из diff исчезнет именно правка разработчика, ради
        которой ревьювер и читает пакет.
        """
        text = self.build_prompt(reviewed_iter=1)

        self.assertIn(DEV_EDIT, text, "правка разработчика обязана быть в diff")
        self.assertIn(_sandbox.DEV_FILE, text,
                      "путь правки разработчика обязан быть в стат-списке")

    def test_ac7_increment_hides_what_the_main_pull_brought(self):
        """Файл B разработчик не трогал — он пришёл merge-коммитом
        подтяжки main: ни его содержимого, ни его пути в пакете быть не
        должно (ни в diff, ни в стат-списке — правило у них одно).

        Ловит мутацию: обход собственных коммитов идёт без ограничения
        первым родителем (или merge-коммиты не исключены) — пути,
        пришедшие из main через merge, снова попадут в пакет, и
        assertNotIn покраснеет.
        """
        text = self.build_prompt(reviewed_iter=1)

        self.assertNotIn(MAIN_EDIT, text,
                         "изменения main, пришедшие подтяжкой, в инкремент "
                         "не входят")
        self.assertNotIn(_sandbox.MAIN_FILE, text,
                         "стат-список собирается по тому же правилу, что и "
                         "показанный diff")

    def test_ac7_note_names_the_verdict_base_and_the_branch_head(self):
        """Заметка под diff'ом называет базу (sha вердикта) и голову
        ветки задачи.

        Ловит мутацию: заметка оставлена на прежнем `prev_sha`, который
        разошёлся с реально использованной базой (правка сделана только
        в месте сборки diff) — ревьювер получит диапазон, по которому
        diff не воспроизводится, а assertIn покраснеет.
        """
        text = self.build_prompt(reviewed_iter=1)

        tail = _sandbox.after_diff(text)
        self.assertTrue(tail, "в пакете нет части diff")
        self.assertIn(self.verdict_sha, tail, "заметка не называет базу")
        self.assertIn(self.BRANCH, tail, "заметка не называет голову ветки")


if __name__ == "__main__":
    unittest.main()
