"""AC-1 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): планка, читающая
артефакт задачи с диска — в любом из названных критерием образцов
(`Path(__file__)…/"PLAN.md"`, `open(`, `.read_text(`, `os.path.join`,
`os.path.exists` со строковым литералом имени артефакта), — даёт ошибку
новой проверки; текст ошибки называет имя файла планки, номер строки и
рецепт «читай из артефактной ветки: gitcmd.show(artifact_branch.
branch_name(TASK_ID), "tasks/<id>/PLAN.md")».

Наблюдается через настоящий `fsm.cmd_advance` вложенной песочницы —
единственный санкционированный вызов проверки (SPEC требование 4
запрещает второй, из `check()`/`main()`), а имени функции SPEC не даёт;
подробнее — докстринг `_sandbox.py`.

Красен до реализации: гейта «переход отклонён: планка читает артефакты с
диска» на выходе `tests_writing` ещё нет — advance уводит вложенную
задачу в `in_dev`, записи журнала с этим действием не появляется вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

# Пять образцов доступа к файловой системе, названных AC-1 поимённо.
# Каждый — одна строка тела тестового метода подставной планки.
DISK_READ_FORMS = {
    'Path(__file__)…/"PLAN.md"': _sandbox.DISK_READ_LINE,
    'open(':
        'handle = open("tasks/01FIXTURETASK/PLAN.md", encoding="utf-8")',
    '.read_text(':
        'text = TASK_DIR.joinpath("PLAN.md").read_text(encoding="utf-8")',
    'os.path.join':
        'path = os.path.join("tasks", "01FIXTURETASK", "PLAN.md")',
    'os.path.exists':
        'exists = os.path.exists("tasks/01FIXTURETASK/PLAN.md")',
}

PATH_FORM = DISK_READ_FORMS['Path(__file__)…/"PLAN.md"']


class DiskReadFormsRefuseTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac1_every_named_disk_read_form_refuses_the_exit(self):
        """Пять образцов доступа к файловой системе из AC-1 разыгрываются
        по одному: планка вложенной задачи читает `PLAN.md` с диска, и
        выход из `tests_writing` каждый раз отклоняется, называя в тексте
        отказа имя файла планки и номер строки нарушения.

        Ловит мутацию: список образцов доступа реализован не полностью —
        проверяется только буквальный `Path(...)` с делением, а `open(`/
        `os.path.join`/`os.path.exists` забыты (или условие собрано через
        `and` вместо `or`, и срабатывает лишь совпадение всех признаков
        сразу) — цикл покраснеет на первом же непокрытом образце:
        вложенная задача уйдёт в `in_dev` без записи отказа.
        """
        self.enter_tests_writing()
        for name, offending in DISK_READ_FORMS.items():
            with self.subTest(form=name):
                source = _sandbox.plank_source([offending])
                self.write_plank(source)

                out = self.advance()

                self.assert_disk_read_refused(out, source, offending)


class DiskReadErrorTextTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac1_error_text_carries_the_artifact_branch_recipe(self):
        """Текст отказа на чтении `PLAN.md` с диска несёт рецепт — «читай
        из артефактной ветки» и вызов `gitcmd.show(artifact_branch.
        branch_name(TASK_ID), …)`, — а не только констатацию нарушения.

        Ловит мутацию: текст ошибки сокращён до «планка читает артефакты
        с диска» с файлом и строкой, без рецепта (рецепт «и так в скиле»)
        — роль получает отказ, не получая способа его починить, и обе
        проверки рецепта покраснеют.
        """
        self.enter_tests_writing()
        source = _sandbox.plank_source([PATH_FORM])
        self.write_plank(source)

        out = self.advance()

        detail = self.assert_disk_read_refused(out, source, PATH_FORM)
        self.assertIn(_sandbox.RECIPE_HEAD, detail)
        self.assertIn(_sandbox.RECIPE_CALL, detail)


if __name__ == "__main__":
    unittest.main()
