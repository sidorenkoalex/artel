"""AC-9 — 01M3GKJ84XM5QPC6TK5EE307Q9: изменённая или удалённая базовая
строка оставляет прежнюю эскалацию.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Конфликт документа, в котором одна из сторон изменила или удалила
базовую строку, оставляет прежнее поведение: `git merge --abort`,
эскалация с прежним текстом `pull._merge_conflict_note` и метка
`pull.PULL_CONFLICT_ROLE_STEP_MARKER` в помечаемых состояниях.

Задача сидит в `in_dev` — состояние из
`pull.PULL_CONFLICT_MARKED_STATES`, где метка положена сегодня.

Зелёный с рождения: сегодня ЛЮБОЙ конфликт, кроме одиночной
`docs/codebase-map.md`, эскалирует именно так — этот файл фиксирует
поведение, которое задача обязана СОХРАНИТЬ. Он краснеет тогда, когда
новое авторазрешение начнёт хватать конфликты с изменёнными и
удалёнными базовыми строками, то есть ровно на той ошибке, которой
боится SPEC требование 8.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class ModifiedBaseLineEscalatesTest(_sandbox.AdditivePullSandbox):

    def test_ac9_modified_base_line_escalates_as_before(self):
        """Ветка ПЕРЕПИСАЛА вторую базовую строку и дописала свою, main
        дописала свою — конфликт не аддитивен и эскалирует прежним
        путём.

        Ловит мутацию: аддитивность считается по числу ДОБАВЛЕННЫХ строк
        (`git diff --numstat`, первая колонка), а удалённые не
        проверяются — переписанная строка (удаление + добавление)
        прошла бы за аддитивную, и union-слияние оставило бы в документе
        обе редакции строки вместо честной эскалации.
        """
        base = list(_sandbox.BASE_LINES)
        self.seed_base({_sandbox.DOC_A: base})
        self.seed_branch_side({_sandbox.DOC_A: [
            base[0], "- базовый пункт 2 (переписан веткой)", base[2],
            _sandbox.BRANCH_LINE]})
        self.seed_main_side({_sandbox.DOC_A: base + [_sandbox.MAIN_LINE]})

        outcome = self.evaluate()

        self.assert_escalated_as_before(outcome, [_sandbox.DOC_A])

    def test_ac9_deleted_base_line_escalates_as_before(self):
        """Ветка УДАЛИЛА вторую базовую строку и дописала свою — тот же
        исход.

        Ловит мутацию: аддитивность доказывается только по стороне
        main, а сторона ветки принимается на веру — удаление базовой
        строки веткой прошло бы незамеченным, и слияние молча вернуло бы
        удалённую строку обратно (либо потеряло бы её у второй стороны).
        """
        base = list(_sandbox.BASE_LINES)
        self.seed_base({_sandbox.DOC_A: base})
        self.seed_branch_side({_sandbox.DOC_A: [
            base[0], base[2], _sandbox.BRANCH_LINE]})
        self.seed_main_side({_sandbox.DOC_A: base + [_sandbox.MAIN_LINE]})

        outcome = self.evaluate()

        self.assert_escalated_as_before(outcome, [_sandbox.DOC_A])


if __name__ == "__main__":
    unittest.main()
