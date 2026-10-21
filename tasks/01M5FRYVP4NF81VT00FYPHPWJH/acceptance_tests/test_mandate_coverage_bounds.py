"""Признание ячейки «Чем покрыто после» матрицы неослабления вне и внутри границы гейта исходов (AC-9, AC-10).

Группа: разовый

Решение профиля задачи у `mandate.matrix_refusals` берётся закрытым
`mandate._task_decision`; критерии задают профиль, а не запись
`targets.yaml`, поэтому тест подменяет это закрытое имя решением с нужным
профилем — долгоживущему файлу `tests/` такая подмена недоступна (правило
ADR-0020), проверка живёт в планке. Весь остальной путь — настоящий:
`matrix_refusals` сам считает границу (`in_outcome_bounds`) и признание
ячейки. Матрица — одна строка данных: элемент мандата `src/a.test.ts`,
свойство остаётся, «Решение» — «ок»; отказ «строка данных 1» значит, что
ячейка покрытием не признана.

Красен до реализации: при профиле в границе ячейки «`src/`», «src/**», «src/a.test.ts::x» и «src/a.test.ts.» сегодня признаются покрытием (токен лишь сверяется с масками области) — AC-10 падает на них; AC-9 и положительные случаи AC-10 держат существующее поведение и зелёные.
"""
import unittest
from unittest import mock

from orchestrator import project_profile
from orchestrator.advance_gates import mandate
from orchestrator.advance_gates.acceptance import in_outcome_bounds

ELEMENT = "src/a.test.ts"
NOT_COVERED = "строка данных 1"

MATRIX = """# PLAN

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| {element} | проверка поведения | да | {cell} | ок |
"""


def profile(**extra):
    fields = dict(command=("python3", "-m", "pytest"), long_lived_dir="src",
                  long_lived_name="test_<id>_<name>.py",
                  weakening_scope=("src/**",),
                  mutation_claim_scope=("src/test_*.py",), project="p",
                  component="default")
    fields.update(extra)
    return project_profile.Profile(**fields)


IN_BOUNDS = profile(report="junit-xml", component="web", from_components=True)


class MatrixCoverageTest(unittest.TestCase):

    def refusals(self, prof, cell: str) -> list:
        decision = project_profile.Decision("p", profile=prof)
        with mock.patch.object(mandate, "_task_decision",
                               return_value=decision):
            return mandate.matrix_refusals(
                MATRIX.format(element=ELEMENT, cell=cell), [ELEMENT],
                conn=object(), task_id="T1")

    def covered(self, prof, cell: str) -> bool:
        found = self.refusals(prof, cell)
        other = [r for r in found if NOT_COVERED not in r]
        self.assertEqual(other, [], f"предпосылка: форма матрицы годна ({cell})")
        return not found

    def test_ac9_non_py_path_refused_outside_outcome_bounds(self):
        """Вне границы гейта исходов ячейка только с путём `src/a.test.ts` в области — отказ мандата.

        Сценарий: три профиля вне `in_outcome_bounds` — запись
        `test_profile`, `test_profile` с `runner: pytest-own` и `report`,
        компонент записи `components:` без `report`; область
        `src/**` включает путь. Ячейка «Чем покрыто после» — путь
        отдельным токеном и в обратных кавычках: каждый раз отказ
        «строка данных 1».

        Ловит мутацию: признание любого пути файла области применяется без
        проверки границы (по `from_components` или по `report` отдельно) —
        ячейка без `*.py` у профиля вне границы проходит мандат.
        """
        outside = (
            ("test_profile", profile()),
            ("test_profile pytest-own с report",
             profile(runner="pytest-own", report="junit-xml")),
            ("компонент без report", profile(component="web",
                                             from_components=True)),
        )
        for name, prof in outside:
            self.assertFalse(in_outcome_bounds(prof), f"предпосылка: {name}")
            self.assertTrue(prof.in_weakening_scope(ELEMENT))
            for cell in (ELEMENT, f"`{ELEMENT}`"):
                with self.subTest(name, cell=cell):
                    self.assertFalse(self.covered(prof, cell))

    def test_ac10_in_bounds_admits_only_file_paths_and_own_test_id(self):
        """При профиле в границе покрытие — путь файла отдельным токеном или в кавычках (с `:<число>`, выделение снято) и идентификатор своего компонента; каталог, маска, `::x` и точка в конце — нет.

        Сценарий: компонент с `report`, область `src/**`. Признаются:
        путь токеном, в обратных кавычках, в `**…**` и `_…_`, с `:12`,
        с запятой после, среди слов, `web:src/a.test.ts::case` в
        кавычках, путь `*.py` внутри ячейки (`src/test_a.py::test_x`). Не
        признаются: «`src/`», «src/**», «src/a.test.ts::x»,
        «src/a.test.ts.», путь вне области.

        Ловит мутацию: токен сверяется только с масками области (каталог
        `src/` и сама маска `src/**` проходят); хвост `:<число>` не
        допускается (ссылка на строку отклоняется); регулярка ищется в
        токене, а не совпадает целиком (`src/a.test.ts::x` и путь с точкой
        в конце проходят); сужение задело прежнее правило `*.py` или
        идентификатор своего компонента.
        """
        self.assertTrue(in_outcome_bounds(IN_BOUNDS), "предпосылка: граница")
        admitted = (ELEMENT, f"`{ELEMENT}`", f"**{ELEMENT}**", f"_{ELEMENT}_",
                    f"{ELEMENT}:12", f"`{ELEMENT}:12`", f"{ELEMENT},",
                    f"тест {ELEMENT} держит свойство",
                    f"`web:{ELEMENT}::case`",
                    "см. src/test_a.py::test_x")
        refused = ("`src/`", "src/**", f"{ELEMENT}::x", f"{ELEMENT}.",
                   "lib/a.test.ts")
        for cell in admitted:
            with self.subTest(admitted=cell):
                self.assertTrue(self.covered(IN_BOUNDS, cell))
        for cell in refused:
            with self.subTest(refused=cell):
                self.assertFalse(self.covered(IN_BOUNDS, cell))


if __name__ == "__main__":
    unittest.main()
