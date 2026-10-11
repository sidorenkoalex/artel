"""Приёмочный тест T094 — AC-12 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-12: «На каждом переходе FSM в артефактную ветку добавляется строка
паспорта живой задачи с состоянием, моментом перехода и
оператором/актором перехода.»

Имя и путь файла-паспорта SPEC не называет (решение — реестр PLAN.md,
требование 1) — тест не гадает за разработчика, а сканирует ВСЮ
артефактную ветку целиком (`git ls-tree -r`, не только `tasks/<id>/`)
и ищет СТРОКУ (одну), несущую все три поля критерия сразу: имя
состояния, метку времени (`store.now()`, формат `%Y-%m-%d %H:%M:%SZ`
— в самой строке узнаётся по `\\d{4}-\\d{2}-\\d{2}`) и актора перехода
(строка `actor`, переданная `store.set_state`). Такая тройная сборка
на одной строке — низкий риск ложного срабатывания на постороннем
тексте артефактов (SPEC/PLAN нередко упоминают имена состояний в прозе
поодиночке, без даты и актора рядом).

Красен до реализации: сегодня переходы FSM (`store.set_state`) ничего,
кроме журнала БД (`steps`), не пишут — артефактная ветка вообще не
существует как понятие (см. `test_ac8_cmd_new_artifact_branch.py`).
Второй метод проверяет ДОПИСЫВАНИЕ (не перезапись): строка первого
перехода обязана пережить второй.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, gitcmd, config, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

ACTOR = "operator"


def _hosting_branch(task_id: str) -> str | None:
    for branch in (gitcmd.list_branches() or []):
        if branch == config.MAIN_BRANCH:
            continue
        if gitcmd.ls_tree_files(branch, f"tasks/{task_id}"):
            return branch
    return None


def _branch_full_text(branch: str) -> str:
    res = gitcmd.git("ls-tree", "-r", "--name-only", branch)
    if res is None or res.returncode != 0:
        return ""
    chunks = []
    for path in res.stdout.splitlines():
        if not path:
            continue
        text, _ = gitcmd.show(branch, path)
        if text is not None:
            chunks.append(text)
    return "\n".join(chunks)


def _has_status_line(text: str, state: str, actor: str) -> bool:
    for line in text.splitlines():
        if state in line and actor in line and re.search(r"\d{4}-\d{2}-\d{2}", line):
            return True
    return False


class Ac12PassportFileTest(ExternalTargetGitSandbox):

    def test_ac12_transition_appends_a_passport_status_line(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)
        conn = store.db()
        state0 = store.get_task(conn, task_id)["state"]

        store.set_state(conn, task_id, "spec_gate", ACTOR,
                        expected_state=state0)
        branch = _hosting_branch(task_id)
        self.assertIsNotNone(branch, f"нет артефактной ветки для {task_id}")
        after_first = _branch_full_text(branch)
        self.assertTrue(
            _has_status_line(after_first, "spec_gate", ACTOR),
            f"после перехода в spec_gate артефактная ветка не несёт "
            f"строку паспорта (состояние+момент+актор) — AC-12")

        store.set_state(conn, task_id, "tests_writing", ACTOR,
                        expected_state="spec_gate")
        branch = _hosting_branch(task_id) or branch
        after_second = _branch_full_text(branch)

        self.assertTrue(
            _has_status_line(after_second, "tests_writing", ACTOR),
            f"после перехода в tests_writing артефактная ветка не несёт "
            f"новую строку паспорта — AC-12")
        self.assertTrue(
            _has_status_line(after_second, "spec_gate", ACTOR),
            "строка паспорта первого перехода (spec_gate) пропала — "
            "паспорт обязан ДОПИСЫВАТЬСЯ, не перезаписываться (AC-12)")


if __name__ == "__main__":
    import unittest
    unittest.main()
