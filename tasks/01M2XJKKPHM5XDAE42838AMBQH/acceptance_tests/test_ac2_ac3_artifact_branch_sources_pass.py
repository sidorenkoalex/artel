"""AC-2, AC-3 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): чтение того же
артефакта из артефактной ветки ошибкой не считается — ни через
`gitcmd.show(…)`/`artifact_branch` (AC-2), ни через `subprocess` с
`git show`/`git cat-file` (AC-3): выход из `tests_writing` проходит.

Оба теста начинаются с КОНТРОЛЯ механизма (планка с чтением `PLAN.md` с
диска обязана отказать) — без него «ошибок нет» доказывало бы лишь то,
что проверки не существует вовсе, и файл остался бы зелёным навсегда
независимо от реализации.

Красен до реализации: контроль внутри каждого теста требует отказа,
которого сегодня нет — гейт «планка читает артефакты с диска» ещё не
написан, вложенная задача уходит в `in_dev` и на нарушающей планке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

# Разрешённые источники критерия AC-2 — артефактная ветка через
# примитивы пульта.
ARTIFACT_BRANCH_BODIES = {
    "gitcmd.show": [
        'text, _reason = gitcmd.show(',
        '    artifact_branch.branch_name(TASK),',
        '    "tasks/01FIXTURETASK/PLAN.md")',
    ],
    "artifact_branch": [
        'rev = artifact_branch.branch_name(TASK) + (',
        '    ":tasks/01FIXTURETASK/REVIEW.md")',
    ],
}

# Разрешённые источники критерия AC-3 — та же артефактная ветка, но
# своим вызовом git.
SUBPROCESS_BODIES = {
    "git show": [
        'res = subprocess.run(',
        '    ["git", "show",',
        '     "artifacts/01FIXTURETASK:tasks/01FIXTURETASK/PLAN.md"],',
        '    capture_output=True, text=True)',
    ],
    "git cat-file": [
        'res = subprocess.run(',
        '    ["git", "cat-file", "-p",',
        '     "artifacts/01FIXTURETASK:tasks/01FIXTURETASK/SPEC.md"],',
        '    capture_output=True, text=True)',
    ],
}


class ArtifactBranchSourcesPassTest(_sandbox.ArtifactSourcePlankSandbox):

    def assert_passes(self, body: list[str]) -> None:
        out = self.advance()
        self.assertEqual(
            self.state(), "in_dev",
            f"чтение артефакта из артефактной ветки ({body[0]}) не должно "
            f"отклонять переход; вывод advance: {out!r}")
        self.assertNotIn(_sandbox.REFUSAL_ACTION.split(": ")[1], out)

    def test_ac2_gitcmd_show_and_artifact_branch_do_not_raise_errors(self):
        """Планка читает `PLAN.md`/`REVIEW.md` через
        `gitcmd.show(artifact_branch.branch_name(...), ...)` и через
        составленный `artifact_branch` ревизион-адрес — после контроля,
        доказавшего срабатывание проверки на дисковом чтении, выход из
        `tests_writing` этих планок проходит в `in_dev`.

        Ловит мутацию: проверка написана по тексту без разбора выражения
        — «строка содержит PLAN.md» достаточно для ошибки — и тогда
        законное чтение из артефактной ветки, где имя артефакта тоже
        стоит строковым литералом, отклоняет переход: `self.state()`
        останется `tests_writing` вместо `in_dev`.
        """
        self.enter_tests_writing()
        self.control_refuses()
        for name, body in ARTIFACT_BRANCH_BODIES.items():
            with self.subTest(source=name):
                self.write_plank(_sandbox.plank_source(body))
                self.assert_passes(body)

    def test_ac3_subprocess_git_show_and_cat_file_do_not_raise_errors(self):
        """Планка читает артефакт своим вызовом git — `subprocess.run`
        с `git show` и с `git cat-file -p` по адресу артефактной ветки;
        после того же контроля выход из `tests_writing` проходит.

        Ловит мутацию: список разрешённых источников сведён к
        `gitcmd.show`/`artifact_branch` (забыта ветка про `subprocess`
        требования 2) — планка, читающая артефакт через `git show`
        собственным вызовом, получает отказ, и переход не доходит до
        `in_dev`.
        """
        self.enter_tests_writing()
        self.control_refuses()
        for name, body in SUBPROCESS_BODIES.items():
            with self.subTest(source=name):
                self.write_plank(_sandbox.plank_source(body))
                self.assert_passes(body)


if __name__ == "__main__":
    unittest.main()
