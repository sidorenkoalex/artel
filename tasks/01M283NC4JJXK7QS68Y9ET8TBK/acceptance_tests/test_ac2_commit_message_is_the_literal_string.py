"""Приёмочный тест AC-2 — 01M283NC4JJXK7QS68Y9ET8TBK.

Источник — tasks/01M283NC4JJXK7QS68Y9ET8TBK/SPEC.md, «Критерии приёмки»:

AC-2. Сообщение созданного коммита — буквально `<id>: код закоммичен
пультом за роль developer — шаг завершён с незакоммиченным кодом`.

Критерий называет ТОЧНУЮ строку — тест сверяет её посимвольно
(`assertEqual`, не `assertIn`), иначе «сообщение похоже на нужное» и
«сообщение буквально такое» — два разных критерия, а не один.

Красен до реализации: до этой задачи такого коммита не существует вовсе
(см. AC-1) — `subject` ниже читает `git log -1 --format=%s` рабочего
дерева кодовой ветки, HEAD которой не сдвинулся, и получает subject
исходного коммита ветки (не пустую строку — до сравнения с ожидаемым
литералом дело дойдёт, но `assertEqual` покраснеет на несовпадении).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DeveloperWipCommitSandbox  # noqa: E402


class CommitMessageIsTheLiteralStringTest(DeveloperWipCommitSandbox):

    def test_ac2_commit_subject_is_the_literal_required_string(self):
        """Шаг `developer` завершается `rc=0` с незакоммиченной правкой вне
        `tasks/<id>/` — subject коммита, который пульт создаёт за роль,
        совпадает БУКВАЛЬНО с `<id>: код закоммичен пультом за роль
        developer — шаг завершён с незакоммиченным кодом`.

        Ловит мутацию: сообщение коммита переиспользует текст соседнего
        WIP-чекпоинта (например `f"{task_id}: WIP-чекпоинт после
        таймаута шага developer"` — реальный текст `commit_timeout_
        checkpoint`) вместо литерала, названного этим AC — `assertEqual`
        отличит любое, даже близкое по смыслу, расхождение текста.
        """
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика без коммита\n")

        self.run_faked()

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        expected = (f"{self.TASK}: код закоммичен пультом за роль "
                   "developer — шаг завершён с незакоммиченным кодом")
        self.assertEqual(
            subject, expected,
            f"AC-2: сообщение коммита обязано быть буквально {expected!r}, "
            f"фактически: {subject!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
