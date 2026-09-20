"""AC-2, AC-3, AC-4: `pre-commit` во временном репозитории с включёнными
хуками — отказ коммиту в main без маркера, проход с маркером, проход на
ветке `task/*`.

Красен до реализации: файла `scripts/git-hooks/pre-commit` ещё нет — песочница падает на его копировании.
"""
import unittest

from _hooks import REFUSAL_CORE, HookedRepoTest, output, squeeze


class PreCommitHookTest(HookedRepoTest):

    def test_ac2_commit_to_main_without_marker_is_refused_by_name(self):
        """Коммит на main без `ARTEL_PULT_GIT` в окружении: git возвращает
        ненулевой код, HEAD остаётся на прежнем коммите, а в выводе стоит
        именованный текст отказа требования 2 SPEC.

        Ловит мутацию: автор хука печатает текст отказа, но завершает его
        `exit 0` (предупреждение вместо запрета) — код возврата стал бы
        нулевым, а коммит реально создался бы, и обе проверки ниже (код и
        неподвижность HEAD) покраснели бы.
        """
        before = self.head()
        self.stage("docs/backlog.md", "строка беклога\n")

        res = self.commit("ручной коммит в main", marker=False)

        self.assertNotEqual(res.returncode, 0,
                            "коммит в main без маркера прошёл")
        self.assertEqual(self.head(), before, "коммит всё-таки создан")
        self.assertIn(squeeze(REFUSAL_CORE), output(res))

    def test_ac3_commit_to_main_with_the_pult_marker_passes(self):
        """Тот же коммит на main, но с `ARTEL_PULT_GIT=1` в окружении,
        проходит: команды пульта (note, doc-commit, pin-update, push мержа)
        обязаны оставаться работоспособными.

        Ловит мутацию: условие хука сводится к одной проверке имени ветки,
        а чтение маркера окружения пропущено — тогда хук отказал бы и
        командам пульта, то есть мерж задачи ломался бы на первом же
        `approve` на merge_gate.
        """
        before = self.head()
        self.stage("docs/backlog.md", "строка беклога\n")

        res = self.commit("коммит команды пульта", marker=True)

        self.assertEqual(res.returncode, 0, output(res))
        self.assertNotEqual(self.head(), before, "коммит не создан")

    def test_ac4_commit_on_a_task_branch_without_marker_passes(self):
        """Коммит на ветке `task/x` без маркера проходит: хук сторожит
        только main главной копии, работа роли на ветке задачи его не
        касается.

        Ловит мутацию: в хуке перепутано условие — отказ выдаётся, когда
        ветка НЕ main (или сравнение ветки потеряно вовсе и отказ
        безусловный) — тогда любой коммит разработчика на ветке задачи
        перестал бы проходить.
        """
        self.git_ok("checkout", "-q", "-b", "task/x")
        before = self.head()
        self.stage("orchestrator/probe.py", "# правка роли\n")

        res = self.commit("правка на ветке задачи", marker=False)

        self.assertEqual(res.returncode, 0, output(res))
        self.assertNotEqual(self.head(), before, "коммит не создан")


if __name__ == "__main__":
    unittest.main()
