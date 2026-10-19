"""Ключ базы прежний при любых `tools` и одинаков у гейта мержа и `suite-run`; при пустых `tools` ключи обоих видов байт в байт прежние.

Группа: разовый
Зелёный с рождения: свойства сохранения — ключ базы и ключи записей с пустыми `tools` до задачи такие же; AC-15 сверяет ключи `full_suite` с ключами кода `acceptance.py` ревизии базы ветки задачи (`_pult.DIFF_BASE`), а это факт задачи, после мержа сверять не с чем.

Песочница — `_keys.KeySandbox`. Ключ базы гейта мержа — имя
`base-<ключ>.json`, под которым `full_suite` сохраняет итог базы, и
`acceptance.suite_result_key(<дерево базы>, <профиль decide>, base=True)`;
ключ поиска `suite-run` — тот же вызов с командой `suite_run._profile_command`
(suite_run.py:521-524, файл задачей не меняется).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _keys import KeySandbox, acceptance_at_base, keys_of  # noqa: E402

from orchestrator import (acceptance, config, project_profile, store,  # noqa: E402
                          suite_run)


class BaseKeyTest(KeySandbox):

    def test_ac14_base_key_same_for_merge_gate_and_suite_run_ignores_tools_and_lock(self):
        """Ключ базы профиля `decide` равен ключу поиска `suite-run`; смена `tools` и игнорируемого файла блокировки его не меняет.

        Сценарий: дерево базы — `suite_tree_hash(<дерево>, base=True)`.
        `suite_result_key(…, base=True)` профиля `decide` учебного проекта и
        команды `suite_run._profile_command` равны и не пусты; `full_suite` с
        профилем `_task_own_profile` сохраняет итог базы под этим ключом, и
        `saved_suite_result("base", <ключ suite-run>)` его находит. После
        смены версии инструмента в `tools` ключ базы профиля `decide` прежний,
        и прогон гейта не заводит другого файла `base-…`; после смены
        содержимого игнорируемого файла блокировки — то же.

        Ловит мутацию: `tools` или суммы файлов блокировки добавлены и в ключ
        базы (`base=True`) — ключ профиля `decide` (с `tools`) расходится с
        ключом `suite-run` (без `tools`), итог базы, сохранённый гейтом,
        `suite-run` не находит, а после смены `tools` появляется второй
        файл `base-…`.
        """
        base_tree = acceptance.suite_tree_hash(self.tree, base=True)
        self.assertIsNotNone(base_tree, self.note("дерево базы не снято"))
        command, refusal = suite_run._profile_command(self.project)
        self.assertEqual(refusal, "", self.note(refusal))
        search = acceptance.suite_result_key(base_tree, command, base=True)
        self.assertIsNotNone(search, self.note("ключ suite-run не посчитан"))
        merge = acceptance.suite_result_key(
            base_tree, project_profile.decide(self.project).profile, base=True)
        self.assertEqual(merge, search, self.note(
            "ключ базы гейта мержа ≠ ключ поиска suite-run"))

        conn = store.db()
        task = self.tasks[self.project]
        runs, new = self.full(self.project,
                              acceptance._task_own_profile(conn, task))
        self.assertEqual(runs, 1, self.note("прогон не вызван"))
        self.assertEqual(keys_of(new, "base"), [search], self.note(
            f"итог базы сохранён не под ключом suite-run: {sorted(new)}"))
        self.assertIsNotNone(acceptance.saved_suite_result(
            "base", search, tree=base_tree), self.note("suite-run не находит итог"))

        changed = dict(self.tools)
        name = self.rng.choice(sorted(changed))
        changed[name] = f"{changed[name]}.{self.rng.randrange(1, 9)}"
        self.write_targets(changed)
        self.assertEqual(acceptance.suite_result_key(
            base_tree, project_profile.decide(self.project).profile, base=True),
            search, self.note("смена tools изменила ключ базы"))
        _, new = self.full(self.project, acceptance._task_own_profile(conn, task))
        self.assertEqual(keys_of(new, "base"), [], self.note(
            f"после смены tools — новый итог базы: {sorted(new)}"))

        self.write_targets(self.tools)
        self.set_lock(self.rng.randbytes(1 + self.rng.randrange(300)))
        self.assertEqual(acceptance.suite_tree_hash(self.tree, base=True),
                         base_tree, self.note("игнорируемый файл изменил дерево базы"))
        self.assertEqual(acceptance.suite_result_key(
            base_tree, project_profile.decide(self.project).profile, base=True),
            search, self.note("смена файла блокировки изменила ключ базы"))
        _, new = self.full(self.project, acceptance._task_own_profile(conn, task))
        self.assertEqual(keys_of(new, "base"), [], self.note(
            f"после смены файла блокировки — новый итог базы: {sorted(new)}"))


class UnchangedKeyTest(KeySandbox):

    def test_ac15_empty_tools_keys_equal_base_revision(self):
        """При пустых `tools` ключи обоих видов у артели и у записи вида sled равны ключам кода базы ветки, в том числе после смены игнорируемого файла блокировки.

        Сценарий: `full_suite` дерева задачи артели (команда пульта, как у
        автогейта и гейта мержа артели) и задачи записи вида sled (профиль
        `_task_own_profile`, `pytest-own` с `workdir`) сохраняет итоги
        `gate-<ключ>`/`base-<ключ>`. Каждый ключ равен ключу, который даёт
        `acceptance.py` ревизии базы ветки задачи на тех же входах:
        `suite_result_key(suite_tree_hash(<дерево>), <команда>)` и
        `suite_result_key(suite_tree_hash(<дерево>, base=True), <команда>,
        base=True)`. Затем меняется содержимое игнорируемого файла
        блокировки в `workdir`: повторный `full_suite` обоих берёт прежний
        итог (прогон не вызван, новых файлов нет), ключи кода базы — прежние.

        Ловит мутацию: новый элемент ключа (`tools`, суммы блокировок)
        добавляется и при пустых `tools` — пустым списком или пустым
        отображением: ключ записи sled (или артели) отличается от ключа кода
        базы; суммы файлов блокировки берутся при пустых `tools` — смена
        файла даёт новый прогон.
        """
        before = acceptance_at_base()
        conn = store.db()
        commands = {
            config.DEFAULT_TARGET: None,
            self.sled: acceptance._task_own_profile(conn, self.tasks[self.sled]),
        }
        self.assertIsNotNone(commands[self.sled], self.note("профиль sled не построен"))

        def expected(command):
            tree = before.suite_tree_hash(self.tree)
            base_tree = before.suite_tree_hash(self.tree, base=True)
            return (before.suite_result_key(tree, command),
                    before.suite_result_key(base_tree, command, base=True))

        saved = {}
        for target, command in commands.items():
            with self.subTest(target=target, seed=self.seed):
                gate, base = expected(command)
                self.assertIsNotNone(gate, self.note("ключ кода базы не посчитан"))
                runs, new = self.full(target, command)
                self.assertEqual(runs, 1, self.note(f"{target}: прогон не вызван"))
                self.assertEqual(keys_of(new, "gate"), [gate], self.note(
                    f"{target}: ключ рабочего дерева ≠ ключ кода базы: {sorted(new)}"))
                self.assertEqual(keys_of(new, "base"), [base], self.note(
                    f"{target}: ключ базы ≠ ключ кода базы: {sorted(new)}"))
                saved[target] = (gate, base)

        self.set_lock(self.rng.randbytes(1 + self.rng.randrange(300)))
        for target, command in commands.items():
            with self.subTest(target=target, after="файл блокировки", seed=self.seed):
                self.assertEqual(expected(command), saved[target], self.note(
                    f"{target}: ключ кода базы сдвинулся от игнорируемого файла"))
                runs, new = self.full(target, command)
                self.assertEqual((runs, sorted(new)), (0, []), self.note(
                    f"{target}: смена игнорируемого файла блокировки при "
                    f"пустых tools изменила ключ"))


if __name__ == "__main__":
    unittest.main()
