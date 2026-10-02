"""Юнит-тесты набора моделей задачи (SPEC 01M3YCHS4F08VTV6XX10VF92H3) —
свойства, которых не покрывает долгоживущий файл задачи
`tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`: нечитаемый
записанный состав, пара на боевой модели, частичная стоимость оборванного
шага, провайдеры наборов в манифесте стека, флаг `--set` без значения.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, catalog, config, models, spend, stack, store  # noqa: E402
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_OTHER_MODEL,  # noqa: E402
                           FIXTURE_TIER_MODEL, TaskSeededTmpRootTest,
                           TmpRootTest)


def set_task(conn, task_id: str, name: str, members: dict) -> None:
    store.update_task(conn, task_id, model_set=name,
                      model_set_members=json.dumps(members))


class TaskModelResolutionTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.use_catalog_fixture()
        self.conn = store.db()

    def test_unreadable_members_refuse_instead_of_combat(self):
        """Нечитаемый записанный состав — отказ разрешения, не боевая модель.

        Сценарий: строка задачи несёт имя набора и испорченный JSON
        состава; `resolve_task_role` роли developer.

        Ловит мутацию: `task_set_members` отдаёт `{}` на нечитаемом
        составе — задача, заведённая Оператором на наборе, молча идёт на
        боевых моделях."""
        store.update_task(self.conn, self.TASK, model_set="nabor",
                          model_set_members="{не json")
        with self.assertRaises(models.TaskSetError) as caught:
            models.resolve_task_role("developer",
                                     store.get_task(self.conn, self.TASK))
        self.assertIn("nabor", str(caught.exception))

    def test_set_member_on_combat_model_needs_no_pair(self):
        """Роль набора на боевой модели идёт без записи пары в `pairs:`.

        Сценарий: состав переводит developer на ту же модель, что даёт
        ярус; `model_sets.yaml` пары не несёт. Разрешение — модель набора
        без отката и без текста о снятой паре.

        Ловит мутацию: сверка пары на старте шага не исключает боевую
        модель (правило `set_admitted`) — шаг пишет в журнал «снята» о
        паре, которой допуск и не нужен."""
        models.model_sets_path().write_text(
            "sets:\npairs:\ncanary_templates:\n", encoding="utf-8")
        set_task(self.conn, self.TASK, "nabor",
                 {"developer": FIXTURE_TIER_MODEL})
        step = models.resolve_task_role("developer",
                                        store.get_task(self.conn, self.TASK))
        self.assertIsNone(step.withdrawn)
        self.assertTrue(step.from_set)
        self.assertEqual(step.resolution.model, FIXTURE_TIER_MODEL)

    def test_partial_cost_of_cut_step_uses_set_model_tariff(self):
        """Частичная стоимость оборванного шага — по тарифу модели набора.

        Сценарий: пара developer → `FIXTURE_OTHER_MODEL` допущена, состав
        задачи её несёт; `spend.charge_missing_result` с разбивкой
        усечённого usage. Списано — по тарифу модели набора, не боевой.

        Ловит мутацию: путь PARTIAL берёт тариф цепочки РОЛИ без задачи
        (`role_tariff(role)`) — оборванный шаг списывается по боевой
        цене."""
        models.model_sets_path().write_text(
            "sets:\npairs:\n  developer:\n"
            f"    {FIXTURE_OTHER_MODEL}:\n      date: 2026-10-01\n"
            "      basis: тест\n      state: допущена\n"
            "canary_templates:\n", encoding="utf-8")
        set_task(self.conn, self.TASK, "nabor",
                 {"developer": FIXTURE_OTHER_MODEL})
        tokens = {"input": 120_000, "output": 30_000}
        before = store.get_task(self.conn, self.TASK)["spent_usd"]
        spend.charge_missing_result(self.conn, self.TASK, "developer",
                                    "попытка 1/3", "таймаут шага", tokens,
                                    True)
        spent = store.get_task(self.conn, self.TASK)["spent_usd"] - before
        expected = spend.tariff_cost_usd(
            models.resolve_model(FIXTURE_OTHER_MODEL).tariff, tokens)
        combat = spend.tariff_cost_usd(
            models.resolve_model(FIXTURE_TIER_MODEL).tariff, tokens)
        self.assertNotAlmostEqual(expected, combat, places=6)
        self.assertAlmostEqual(spent, expected, places=6)


class LiveTaskSetProvidersTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.use_catalog_fixture()
        self.conn = store.db()

    def test_open_task_set_demands_its_provider_closed_does_not(self):
        """Провайдер модели набора незакрытой задачи — в востребованных.

        Сценарий: набор задачи переводит developer на модель раздела
        `codex`, ярусы ведут на `claude`. Пока задача в работе,
        `stack.model_providers()` несёт `codex`; задача в `done` — нет.

        Ловит мутацию: наборы задач не добавлены к востребованным CLI
        (шаг на модели набора стартует без проверки инструмента), либо
        закрытые задачи продолжают требовать CLI своего набора."""
        set_task(self.conn, self.TASK, "nabor",
                 {"developer": FIXTURE_CODEX_MODEL})
        self.assertIn("codex", stack.model_providers())
        store.update_task(self.conn, self.TASK, state="done")
        self.assertNotIn("codex", stack.model_providers())


class LiveTaskSetProvidersNoDbTest(TmpRootTest):

    def test_absent_db_is_not_created(self):
        """Манифест стека вне пульта не заводит БД.

        Ловит мутацию: чтение наборов задач открывает `store.db()` без
        сверки наличия файла — сборка манифеста (CI `stack_ci`) создаёт
        `.artel/state.db` там, где пульта нет."""
        self.assertFalse(config.DB.exists())
        self.assertEqual(models.live_task_set_providers(), set())
        self.assertFalse(config.DB.exists())


class NewSetFlagTest(unittest.TestCase):

    def test_set_flag_without_name_refused_before_new(self):
        """`new <название> --set` без имени — отказ до заведения задачи.

        Сценарий: флаг последним аргументом и флаг, за которым идёт
        другой флаг (`--set --tz`: снятие пары оставило бы корректный
        argv из одного названия). Оба — `SystemExit` с текстом о `--set`,
        `catalog.cmd_new` не вызван.

        Ловит мутацию: значением набора берётся следующий токен (`--tz`)
        либо флаг без значения молча отбрасывается — задача заводится
        без набора, который Оператор просил."""
        for rest in (["Название", "--set"], ["Название", "--set", "--tz"]):
            with mock.patch.object(catalog, "cmd_new") as cmd_new, \
                    self.assertRaises(SystemExit) as caught:
                artel._cmd_new(rest)
            self.assertIn("--set", str(caught.exception.code))
            cmd_new.assert_not_called()

    def test_set_flag_passes_name_and_keeps_tz(self):
        """`new <название> --set <набор> --tz <файл>` — имя набора и путь
        ТЗ доходят до `catalog.cmd_new`.

        Ловит мутацию: снятие пары `--set <набор>` сдвигает разбор —
        имя набора принимается лишним аргументом (отказ) либо теряется
        путь ТЗ."""
        with mock.patch.object(catalog, "cmd_new") as cmd_new:
            artel._cmd_new(["Название", "--set", "nabor", "--tz", "т.md"])
        cmd_new.assert_called_once_with("Название", tz_path="т.md",
                                        model_set="nabor")


if __name__ == "__main__":
    unittest.main()
