"""AC-1: PLAN.md несёт перечень тестов `tests/`, читающих настоящий
`roles.yaml`/`models.yaml`, и по каждому пункту — поля, от которых зависит
исход, и вердикт «предмет карты: да|нет».

Кто такой «читающий настоящую карту» — решает разбор AST
(`_util.map_reader_tests`) по трём путям, которые называет сама
формулировка критерия: `config.ROLES`/`config.MODELS`, литерал адреса
карты и помощники песочницы, производные от боевой карты
(`SANDBOX_ROLES_TEXT`, `roles_text_on_default_provider`, `_roles_yaml_text`,
`_tiers_text`, `_REAL_ROLES_TEXT`). Сверх того в перечень обязан попасть
`tests/test_analyst_role.py`: его зависимость от поля `provider:` боевой
карты называет прямым текстом AC-5, а собственного чтения карты в файле
нет — он берёт её у песочницы.

`tests/sandbox.py` пунктом перечня не считается: AC-1 говорит о ТЕСТАХ, а
песочница — их общая обвязка (её собственное чтение карты — предмет AC-6).

Форма пункта, которую разбирает планка, названа одной строкой в
`_util.PLAN_ENTRY_SHAPE` и цитируется каждым отказом: разбираются строка с
путём и её продолжения до пустой строки либо до следующего пути, поэтому и
список с переносами, и таблица годятся одинаково.

PLAN.md читается из АРТЕФАКТНОЙ ветки (`gitcmd.show`), не с диска: в среде
прогона гейта пульт материализует только `acceptance_tests/`.

Красен до реализации: PLAN.md задачи ещё не создан — его пишет роль
developer, и `_util.plan_text()` отдаёт `None`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class PlanEnumeratesMapReadersTest(unittest.TestCase):
    """Перечень PLAN.md против фактических читателей боевой карты."""

    def test_ac1_plan_lists_every_map_reader_with_fields_and_verdict(self):
        """PLAN.md называет КАЖДЫЙ файл `tests/`, читающий настоящий
        `roles.yaml`/`models.yaml`, и у каждого пункта есть и перечень
        полей, от которых зависит исход, и вердикт «предмет карты».

        Ловит мутацию: перечень собран только по файлам, которые читают
        карту ПРЯМО (`config.ROLES`, литерал адреса) — читатели ЧЕРЕЗ
        помощники песочницы (`roles_text_on_default_provider`,
        `_roles_yaml_text`) в него не попали. Ровно эта слепота оставила
        `tests/test_models_doctor.py` вне поля зрения помощников и, по
        разделу «Контекст» SPEC, сохранила ему жизнь случайно: перечень с
        такой дырой снова не покажет, какие файлы класс не закрыл.
        """
        plan = _util.plan_text()
        self.assertIsNotNone(
            plan,
            f"PLAN.md задачи не найден в артефактной ветке "
            f"{_util.artifact_branch.branch_name(_util.TASK_ID)} — перечень "
            f"читателей боевой карты пишет роль developer")

        entries = _util.plan_entries(plan)
        readers = _util.map_reader_tests()
        self.assertTrue(
            readers,
            "разбор `tests/` не нашёл ни одного читателя боевой карты — "
            "сверять перечень PLAN.md не с чем")

        missing = [rel for rel in readers if rel not in entries]
        self.assertEqual(
            missing, [],
            f"PLAN.md не называет эти файлы `tests/`, читающие настоящую "
            f"карту: {missing}\nформа пункта: {_util.PLAN_ENTRY_SHAPE}")

        for rel in readers:
            with self.subTest(file=rel):
                entry = entries[rel]
                self.assertTrue(
                    entry["fields"],
                    f"пункт PLAN.md про {rel} (строка {entry['line']}) не "
                    f"называет полей боевого файла, от которых зависит его "
                    f"исход\nформа пункта: {_util.PLAN_ENTRY_SHAPE}")
                self.assertIsNotNone(
                    entry["subject"],
                    f"пункт PLAN.md про {rel} (строка {entry['line']}) не "
                    f"отвечает, является ли боевая карта предметом теста"
                    f"\nформа пункта: {_util.PLAN_ENTRY_SHAPE}")


if __name__ == "__main__":
    unittest.main()
