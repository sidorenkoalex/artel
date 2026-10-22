"""Планка чужого компонента на выходе из `tests_writing` у записи из нескольких компонентов: отказ FAIL_TO_PASS для файла компонента в границе, прежнее поведение — вне границы.

Группа: долгоживущий
Красен до реализации: у записи из двух компонентов выход из `tests_writing` отклоняется отказом профиля (`decide` без зон) раньше гейта FAIL_TO_PASS — нет ни отказа «файл планки <имя> — компонента <X>, задача — компонента <Y>», ни перехода в `in_dev` при чужом файле вне границы; а у профиля задачи из `for_task` файл чужого компонента `criterion_files` молча пропускает.

Стенд — учебный проект из двух компонентов песочницы гейта исходов
(`tests.test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.
ComponentsOutcomeSandbox`): `backend` — `junit-xml` на поддельном
`pytest` (планка — `test_*.py`), `frontend` — `pult-vitest` (планка —
`*.test.jsx` с меткой `AC-<n>: `); варианты — без поля `report` у одного
из компонентов. Задача на компонент Y проходит настоящий выход из
`tests_writing` (`fsm.cmd_advance`) с планкой из файла своего компонента
и файла чужого компонента X; исход — состояние задачи и записи журнала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`for_task` по зонам задачи и проверка файла планки чужого компонента в
границе гейта FAIL_TO_PASS (и при задаче вне границы) — все методы файла
зелёные.
"""
from types import SimpleNamespace

from tests.test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components import (
    ComponentsOutcomeSandbox)

FAIL_TO_PASS_ACTION = "переход отклонён: честный FAIL_TO_PASS"
FOREIGN = "файл планки {name} — компонента {x}, задача — компонента {y}"


class ForeignPlankSandbox(ComponentsOutcomeSandbox):

    def plank(self, comp: str) -> tuple:
        """(имя, текст) файла планки компонента `comp` по правилу планки;
        `<n>` — номер критерия SPEC задачи."""
        kind = SimpleNamespace(kind="vitest" if comp == "frontend" else "junit")
        name, body = self.plank_text(kind, 0)
        return name, body.replace("AC-0:", "AC-<n>:").replace("test_ac0_",
                                                            "test_ac<n>_")

    def exit_with_foreign(self, project, task_comp: str, foreign_comp: str):
        own_name, own_body = self.plank(task_comp)
        name, body = self.plank(foreign_comp)
        t, rows, output = self.writing_task(project, task_comp,
                                            {own_name: own_body, name: body})
        return t, rows, output, name

    def foreign_refusals(self, rows) -> list:
        return [d for d in self.details(rows, FAIL_TO_PASS_ACTION)]


class Ac19ForeignPlankTest(ForeignPlankSandbox):

    def test_ac19_foreign_file_in_bounds_refused(self):
        """Задача на `frontend`, в планке файл `backend` (в границе): отказ FAIL_TO_PASS «файл планки <имя> — компонента backend, задача — компонента frontend», задача остаётся в `tests_writing`.

        Ловит мутацию: `criterion_files` молча пропускает файл, чьего
        компонента нет среди профилей гейта (профиль задачи один) —
        переход проходит в `in_dev`.
        """
        project = self.training()
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        found = self.foreign_refusals(rows)
        self.assertTrue(any(FOREIGN.format(name=name, x="backend", y="frontend") in d
                            for d in found), self.explain(rows, output))

    def test_ac19_task_out_of_bounds_still_refused(self):
        """Задача на `backend` без `report` (вне границы), в планке файл `frontend` (в границе): тот же отказ — «… компонента frontend, задача — компонента backend».

        Ловит мутацию: гейт FAIL_TO_PASS добавляется только по профилю
        задачи в границе (`fsm_advance.py:609–613`) — у задачи вне границы
        файл чужого компонента в границе не проверяется.
        """
        project = self.training(backend_report=False)
        t, rows, output, name = self.exit_with_foreign(project, "backend",
                                                       "frontend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        found = self.foreign_refusals(rows)
        self.assertTrue(any(FOREIGN.format(name=name, x="frontend", y="backend") in d
                            for d in found), self.explain(rows, output))


class Ac25TrainingProjectTest(ForeignPlankSandbox):

    def test_ac25_backend_file_on_frontend_task(self):
        """Учебный проект: файл планки `backend` у задачи на `frontend` получает отказ AC-19 с именем файла и обоими компонентами.

        Ловит мутацию: компоненты в тексте отказа перепутаны местами
        (X — компонент задачи); отказ без имени файла.
        """
        project = self.training()
        _t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                        "backend")
        found = self.foreign_refusals(rows)
        self.assertTrue(found, self.explain(rows, output))
        self.assertIn(FOREIGN.format(name=name, x="backend", y="frontend"),
                      "\n".join(found), self.explain(rows, output))
        self.assertNotIn(FOREIGN.format(name=name, x="frontend", y="backend"),
                         "\n".join(found), self.explain(rows, output))


class Ac27OutOfBoundsForeignTest(ForeignPlankSandbox):

    def test_ac27_foreign_out_of_bounds_not_checked(self):
        """Чужой компонент `backend` без `report` (вне границы): его файл у задачи на `frontend` не проверяется — отказа AC-19 и иного отказа по файлу нет, задача уходит в `in_dev`; тот же файл при `backend` в границе — отказ AC-19.

        Ловит мутацию: отказ AC-19 дан любому файлу чужого компонента без
        условия границы — у `backend` вне границы переход отклонён.
        """
        project = self.training(backend_report=False)
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.assertEqual(self.foreign_refusals(rows), [], self.explain(rows, output))
        project = self.training()
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        self.assertTrue(any(FOREIGN.format(name=name, x="backend", y="frontend") in d
                            for d in self.foreign_refusals(rows)),
                        self.explain(rows, output))
