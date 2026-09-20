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

Уточнение ANSWER-1 (вариант B, сила правки SPEC для требования 1 и
AC-1/AC-5): ошибка — только путь, якоренный на рабочую копию (цепочка от
`Path(__file__)`, от `config.ROOT`/`config.TASKS`, литерал с началом
`tasks/`, включая имена, присвоенные от таких выражений, — `TASK_DIR`
подставной планки именно такое); пути от временного каталога песочницы
ошибкой не считаются — класс `TempDirFixturePathsPassTest`. Все пять
образцов `DISK_READ_FORMS` якорны и после уточнения.

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

# Пути от временного каталога (ANSWER-1, вариант B): вложенная песочница
# пишет и читает поддельные артефакты фиктивной задачи во временном
# каталоге — это её фикстура, не артефакт задачи. `import tempfile` —
# строкой тела метода: пролог шаблона подставной планки фиксирован.
TEMP_DIR_BODIES = {
    "имя от tempfile.mkdtemp()": [
        'import tempfile',
        'fixture_dir = Path(tempfile.mkdtemp()) / "tasks" / TASK',
        'fixture_dir.mkdir(parents=True)',
        '(fixture_dir / "SPEC.md").write_text("# SPEC", encoding="utf-8")',
        'spec = (fixture_dir / "SPEC.md").read_text(encoding="utf-8")',
    ],
    "self.tdir песочницы": [
        'import tempfile',
        'self.tdir = Path(tempfile.mkdtemp())',
        '(self.tdir / "PLAN.md").write_text("# PLAN", encoding="utf-8")',
        'exists = os.path.exists(os.path.join(self.tdir, "REVIEW.md"))',
    ],
    "сегмент tasks посреди пути от tempfile": [
        'import tempfile',
        'tmp = tempfile.mkdtemp()',
        'plan = Path(tmp) / "tasks" / TASK / "PLAN.md"',
        'handle = open(os.path.join(tmp, "tasks", TASK, "QUESTIONS.md"), "w")',
    ],
}


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


class TempDirFixturePathsPassTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac1_paths_from_a_temporary_directory_do_not_refuse_the_exit(self):
        """Три формы вложенной песочницы (ANSWER-1, вариант B): планка
        пишет и читает `SPEC.md`/`PLAN.md`/`REVIEW.md`/`QUESTIONS.md` по
        пути от временного каталога — от имени, присвоенного из
        `tempfile.mkdtemp()`, от `self.tdir` песочницы и по пути с
        сегментом `tasks` посреди цепочки от временного каталога, — и
        после контроля, доказавшего срабатывание проверки на якорном
        чтении, выход из `tests_writing` каждый раз проходит в `in_dev`.

        Ловит мутацию: якорный предикат снят — правило вернулось к «любое
        выражение доступа с именем артефакта» — либо голый сегмент `tasks`
        правым операндом `/` посчитан корнем пути: штатный приём планок
        FSM-задач получает отказ, и состояние остаётся `tests_writing`.
        """
        self.enter_tests_writing()
        self.control_refuses()
        for name, body in TEMP_DIR_BODIES.items():
            with self.subTest(form=name):
                self.write_plank(_sandbox.plank_source(body))

                out = self.advance()

                self.assertEqual(
                    self.state(), "in_dev",
                    f"путь от временного каталога ({name}) не должен "
                    f"отклонять переход; вывод advance: {out!r}")


if __name__ == "__main__":
    unittest.main()
