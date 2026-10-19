"""`Profile.tools` у `decide` и `_task_own_profile`; ключ рабочего дерева видит `tools` и игнорируемый файл блокировки.

Группа: разовый
Красен до реализации: у `project_profile.Profile` нет поля `tools` — AC-12 не находит его у профилей `decide` и `_task_own_profile`; ключ рабочего дерева `pytest-own` не содержит `tools` и сумм файлов блокировки — после смены `tools` или игнорируемого файла блокировки `full_suite` берёт прежний итог, и подменённый прогон не вызывается.

Разовый, а не долгоживущий: критерии называют закрытые входы
`acceptance._task_own_profile` и `suite_run._profile_command` (правило
долгоживущих файлов — только публичный интерфейс), а их поведение у записи
с несколькими компонентами меняет G1б. Песочница — `_keys.KeySandbox`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _keys import KeySandbox, tools_dict  # noqa: E402

from orchestrator import acceptance, config, project_profile, store  # noqa: E402


class ProfileToolsTest(KeySandbox):

    def test_ac12_decide_and_task_own_profile_carry_tools(self):
        """`decide` и `_task_own_profile` дают `Profile` с объявленными `tools` единственного компонента; у записей с `test_profile` — пустые.

        Сценарий: учебная запись с единственным компонентом `pytest-own`,
        `tools` — два инструмента со случайными версиями. Профиль
        `decide(<проект>)` и профиль `_task_own_profile(<БД>, <задача
        проекта>)` несут поле `tools`, равное объявленному отображению.
        Запись вида sled (`test_profile`, `pytest-own`, `workdir`): у обоих
        профилей поле `tools` есть и пусто; у артели (`pult-pytest`) пусто
        `tools` профиля `decide`.

        Ловит мутацию: `tools` заполняет только `decide`, а
        `_task_own_profile` строит `Profile.from_values` без помощника — у
        его профиля `tools` пусты; помощник берёт `tools` у записи с
        `test_profile` из чужого места и даёт непустое значение.
        """
        conn = store.db()
        cases = (
            (self.project, self.tools),
            (self.sled, {}),
        )
        for target, expected in cases:
            with self.subTest(target=target, seed=self.seed):
                profiles = {
                    "decide": project_profile.decide(target).profile,
                    "_task_own_profile": acceptance._task_own_profile(
                        conn, self.tasks[target]),
                }
                for source, profile in profiles.items():
                    self.assertIsNotNone(profile, self.note(f"{source}: нет профиля"))
                    self.assertTrue(hasattr(profile, "tools"), self.note(
                        f"{source}: у Profile нет поля tools"))
                    self.assertEqual(tools_dict(profile.tools), expected,
                                     self.note(f"{source}, проект {target}"))
        artel = project_profile.decide(config.DEFAULT_TARGET).profile
        self.assertTrue(hasattr(artel, "tools"), self.note("артель: нет поля tools"))
        self.assertEqual(tools_dict(artel.tools), {}, self.note("артель"))


class WorkingTreeKeyTest(KeySandbox):

    def test_ac13_working_key_same_for_both_inputs_and_tracks_tools_and_lock(self):
        """Ключ рабочего дерева одинаков у профилей `_task_own_profile` и `decide` и меняется со сменой `tools` и игнорируемого файла блокировки.

        Сценарий: `full_suite` дерева задачи учебного проекта с профилем
        `_task_own_profile` гоняет набор (подменённый прогон вызван один
        раз); тот же вызов с профилем `decide` (вход гейта мержа) берёт
        сохранённый итог — прогон не вызван. Версия одного инструмента в
        `tools` меняется — `full_suite` с новым профилем гоняет набор заново;
        `tools` возвращены — снова прежний итог. Содержимое игнорируемого
        git файла блокировки в `workdir` меняется (дерево `suite_tree_hash`
        при этом прежнее) — набор гоняется заново; прежнее содержимое
        возвращено — прежний итог.

        Ловит мутацию: `tools` заполнены только у одного входа — ключи
        входов разные, профиль `decide` гоняет набор; `tools` не входят в
        ключ — после их смены итог берётся повторно; сумма файла блокировки
        берётся из объекта дерева (игнорируемого там нет) или не берётся
        вовсе — смена его содержимого ключ не меняет.
        """
        conn = store.db()
        task = self.tasks[self.project]

        def own():
            return acceptance._task_own_profile(conn, task)

        tree = acceptance.suite_tree_hash(self.tree)
        self.assertIsNotNone(tree, self.note("дерево прогона не снято"))
        runs, new = self.full(self.project, own())
        self.assertEqual(runs, 1, self.note("первый прогон не вызван"))
        self.assertTrue(any(n.startswith("gate-") for n in new),
                        self.note(f"итог не сохранён: {new}"))
        runs, _ = self.full(self.project,
                            project_profile.decide(self.project).profile)
        self.assertEqual(runs, 0, self.note(
            "профиль decide дал иной ключ, чем профиль _task_own_profile"))

        changed = dict(self.tools)
        name = self.rng.choice(sorted(changed))
        changed[name] = f"{changed[name]}.{self.rng.randrange(1, 9)}"
        self.write_targets(changed)
        runs, _ = self.full(self.project, own())
        self.assertEqual(runs, 1, self.note(
            f"смена tools ({name}: {self.tools[name]} → {changed[name]}) "
            f"ключ не изменила"))
        self.write_targets(self.tools)
        runs, _ = self.full(self.project, own())
        self.assertEqual(runs, 0, self.note("прежние tools — прежний ключ"))

        content_a = (self.tree / self.workdir / self.lock).read_bytes()
        content_b = content_a + self.rng.randbytes(1 + self.rng.randrange(40))
        self.set_lock(content_b)
        self.assertEqual(acceptance.suite_tree_hash(self.tree), tree,
                         self.note("игнорируемый файл изменил дерево"))
        runs, _ = self.full(self.project, own())
        self.assertEqual(runs, 1, self.note(
            "смена игнорируемого файла блокировки ключ не изменила"))
        self.set_lock(content_a)
        runs, _ = self.full(self.project, own())
        self.assertEqual(runs, 0, self.note(
            "прежнее содержимое файла блокировки — прежний ключ"))


if __name__ == "__main__":
    unittest.main()
