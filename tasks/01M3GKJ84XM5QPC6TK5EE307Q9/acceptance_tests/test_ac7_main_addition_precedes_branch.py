"""AC-7 — 01M3GKJ84XM5QPC6TK5EE307Q9: в слитом файле добавка main стоит
перед добавкой ветки задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. В слитом файле добавка main стоит перед добавкой ветки задачи.

Порядок — не косметика: SPEC требование 6 объясняет его четырьмя
доводами (main — уже общая история; растущие вниз списки; порядок задан
аргументами слияния, а не тем, какую сторону git пометил `ours`; волна
остаётся хронологической), и именно он задаётся порядком аргументов
`git merge-file -p --union <стадия main> <стадия базы> <стадия ветки>`.

Красен до реализации: аддитивного слияния ещё нет — merge эскалирует,
файл остаётся в состоянии базы, и ни одной добавки в нём нет вовсе;
`assertIn` по добавке main падает раньше сверки порядка.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class MainAdditionPrecedesBranchTest(_sandbox.AdditivePullSandbox):

    def test_ac7_main_addition_comes_before_the_branch_addition(self):
        """В слитом документе строка, добавленная main, встречается
        раньше строки, добавленной веткой задачи.

        Ловит мутацию: аргументы union-слияния переставлены местами
        (`<стадия ветки> <стадия базы> <стадия main>`) либо порядок
        отдан на откуп тому, что git считает `ours`/`theirs` — добавка
        ветки встала бы перед добавкой main, и следующая задача волны
        получила бы список в обратном хронологическом порядке.
        """
        self.seed_additive_conflict(_sandbox.DOC_A)

        self.evaluate()

        text = self.read(_sandbox.DOC_A)
        self.assertIn(_sandbox.MAIN_LINE, text,
                      f"добавки main нет в слитом файле:\n{text}")
        self.assertIn(_sandbox.BRANCH_LINE, text,
                      f"добавки ветки нет в слитом файле:\n{text}")
        self.assertLess(
            text.index(_sandbox.MAIN_LINE), text.index(_sandbox.BRANCH_LINE),
            f"добавка main обязана стоять ПЕРЕД добавкой ветки задачи "
            f"(SPEC требование 6):\n{text}")


if __name__ == "__main__":
    unittest.main()
