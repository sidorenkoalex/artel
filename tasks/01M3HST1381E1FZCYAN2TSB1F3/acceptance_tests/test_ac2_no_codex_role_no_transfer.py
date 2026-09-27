"""AC-2 — 01M3HST1381E1FZCYAN2TSB1F3: без роли на Codex дом клона не
меняется и проверка входа не зовётся.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Прогон на наборе по умолчанию (без `--set`) и прогон на наборе, ни
одна роль которого не идёт провайдером `codex`: в доме роли клона файла
указателя нет, проверка входа не зовётся ни разу, дом клона содержит ровно
то, что кладёт холодный старт клона.

Критерий называет ДВА случая, и планка держит их раздельными: набор по
умолчанию (прогон вообще без параметра набора) и исправный набор, чьи роли
идут провайдером по умолчанию. Второй случай не сводится к первому —
именно на нём ломается реализация, ставящая перенос на «передан `--set`»
вместо «на наборе есть роль Codex».

«Ровно то, что кладёт холодный старт клона» сверяется с перечнем,
посчитанным от референсов дома роли реестра провайдеров
(`_util.cold_start_role_home_files` — вход `catalog._deploy_role_home_
reference`), а не с перечнем из другого прогона: иначе сверка
доказывала бы лишь совпадение двух прогонов друг с другом.

«Проверка входа не зовётся ни разу» наблюдается на двух уровнях сразу:
узел `doctor.check_codex_chatgpt_auth` не вызван и процесса `codex … login
status` не было — своя копия логики проверки мимо узла тоже нарушает
критерий.

Красен до реализации: `_util.auth_check_targets` и перечень файлов дома
клона сегодня дают пустые наблюдения, поэтому три метода из четырёх зелены
с рождения, а `test_ac2_codex_set_is_the_only_case_that_differs` красен —
он требует, чтобы набор С ролью на Codex отличался от набора без неё
ровно указателем, чего сегодня не происходит.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class NoCodexRoleNoTransferTest(_util.CodexClonePlankSandbox):

    def test_ac2_default_set_leaves_the_clone_role_home_at_cold_start(self):
        """Прогон без `--set`: указателя в доме роли клона нет, а сам дом —
        ровно то, что развернул холодный старт клона.

        Ловит мутацию: перенос сделан безусловно, до разбора набора (или
        условием «клон собран»), — прогон «как пульт» начал бы возить
        указатель Оператора в каждый эфемерный клон, то есть менять
        поведение, которое требование 2 объявляет прежним байт-в-байт.
        """
        files, _root = self.clone_role_home_files(_util.OMIT)

        self.assertNotIn(_util.POINTER_REL, files, sorted(files))
        self.assertEqual(_util.cold_start_role_home_files(), files)

    def test_ac2_set_without_a_codex_role_leaves_the_clone_role_home_alone(self):
        """Прогон на наборе, ни одна роль которого не идёт провайдером
        `codex`: тот же дом клона холодного старта, без указателя.

        Ловит мутацию: условие переноса записано как «передан `--set`»
        (или «набор не набор по умолчанию») вместо «на наборе есть роль
        провайдера codex» — набор на моделях провайдера по умолчанию
        тоже получал бы указатель, и требование 2 нарушалось бы на любом
        наборе.
        """
        self.assertEqual([], _util.codex_roles_of_set(_util.CLAUDE_SET_NAME),
                         "предпосылка: набор не ведёт ни одной роли Codex")

        files, _root = self.clone_role_home_files(_util.CLAUDE_SET_NAME)

        self.assertNotIn(_util.POINTER_REL, files, sorted(files))
        self.assertEqual(_util.cold_start_role_home_files(), files)

    def test_ac2_auth_check_is_not_called_once_on_either_set(self):
        """Ни на наборе по умолчанию, ни на наборе без роли Codex проверка
        входа не зовётся: ни узлом `doctor`, ни процессом `codex login
        status`.

        Ловит мутацию: проверка входа поставлена в подготовку клона
        безусловно — прогон «как пульт» на машине без Codex CLI (или без
        выполненного входа) отказывал бы там, где раньше проходил, то есть
        канарейка перестала бы работать у пульта, Codex не использующего.
        """
        for label, set_name in (("набор по умолчанию", _util.OMIT),
                                ("набор без роли Codex",
                                 _util.CLAUDE_SET_NAME)):
            with self.subTest(scenario=label):
                outcome = self.run_canary(set_name=set_name)

                self.assertEqual([], outcome.auth_calls,
                                 "узел проверки входа вызван")
                self.assertEqual([], outcome.spy.login_calls,
                                 "процесс `codex login status` запущен")

    def test_ac2_codex_set_is_the_only_case_that_differs(self):
        """Дом роли клона на наборе С ролью Codex отличается от дома клона
        без такой роли — и отличается РОВНО указателем.

        Ловит мутацию: перенос не сделан вовсе (оба прогона дают один и тот
        же дом клона) либо сделан ценой холодного старта — указатель лёг в
        дом роли клона ДО `catalog.cmd_init()`, `_deploy_role_home_
        reference` вышел на `ROLE_HOME.exists()`, и роли клона остались без
        курируемого дома: `assertEqual` назовёт исчезнувшие файлы
        референса.
        """
        without, _root = self.clone_role_home_files(_util.CLAUDE_SET_NAME)
        with_codex, _clone = self.clone_role_home_files(_util.SET_NAME)

        self.assertEqual(without | {_util.POINTER_REL}, with_codex)


if __name__ == "__main__":
    unittest.main()
