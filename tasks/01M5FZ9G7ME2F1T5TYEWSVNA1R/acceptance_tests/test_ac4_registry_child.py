"""AC-4: реестр держит прогон по записи дочернего процесса; уборка мёртвой записи дочернего не трогает метку живого родителя.

Группа: разовый
Красен до реализации: подкоманды `run-task` нет — снять копию записи дочернего во время подменённой задачи нечем (вызов отказывает «нужен параметр --k», подменённое ведение не вызывается).

Почему разовый: запись дочернего по критерию — копия файла, снятая во
время подменённой задачи подкоманды (закрытые `_run_one_task` и `_set_plan`
подменены); правила долгоживущего файла `tests/` такие подмены запрещают.

Песочница — `tests.sandbox.InitializedTmpRootTest`. Живая запись
дочернего — копия, снятая подкомандой в процессе теста (её pid — сам
процесс теста). Мёртвая — копия, снятая подкомандой в отдельном
интерпретаторе (`sys.executable -c`, конфиг песочницы через файл
настроек), который завершился и дождан `Popen.wait()`; его родитель —
процесс теста, метка для него несёт pid процесса теста. Гибель родителя —
запись и метка с pid завершённого процесса, без настоящего SIGKILL.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _runtask import RunTaskMixin  # noqa: E402

from orchestrator import canary  # noqa: E402
from tests.sandbox import InitializedTmpRootTest  # noqa: E402


class RegistryChildTest(RunTaskMixin, InitializedTmpRootTest):
    """Каталог реестра песочницы; записи дочерних — копии, снятые подкомандой."""

    def setUp(self):
        super().setUp()
        self.setup_runtask()

    def test_ac4_live_child_keeps_run_after_parent_death(self):
        """(1) Мёртвая запись родителя, метка с его pid и живая запись дочернего (копия из подкоманды в процессе теста).

        Наблюдение: `live_runs()` возвращает запись дочернего (pid процесса
        теста, `parent_pid`, `template`), `live_run_note()` не пуст, запись
        родителя и его метка убраны.

        Ловит мутацию: запись дочернего не пишется (или пишется под маской,
        которую `live_runs` не читает, либо с `tasks`/`started_at`, делающими
        её нечитаемой) — после уборки мёртвого родителя прогон не держится,
        `live_run_note()` пуст.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(5)
        copy = self.capture_record(stamp, set_name, summary)
        self.assertEqual(self.listing(), [], self.msg("реестр не пуст после подкоманды"))
        dead = self.dead_pid()
        parent = self.put_record(stamp, dead, self.sha, set_name, start_known=False)
        mark = self.put_mark(stamp, dead)
        child = self.registry() / self.own_record_name(stamp)
        child.write_bytes(copy)

        runs = canary.live_runs()
        ctx = self.msg(f"{runs}; {self.listing()}")
        self.assertEqual([e.get("pid") for e in runs], [os.getpid()], ctx)
        self.assertEqual(runs[0].get("parent_pid"), self.ppid, ctx)
        self.assertEqual(runs[0].get("template"), self.template_name, ctx)
        self.assertFalse(parent.exists(), ctx)
        self.assertFalse(mark.exists(), ctx)
        child.write_bytes(copy)
        self.assertIsNotNone(canary.live_run_note(), ctx)
        self.assertTrue(child.exists(), ctx)

    def test_ac4_dead_child_swept_parent_mark_kept(self):
        """(2) Живая запись родителя, метка с его pid и мёртвая запись дочернего (копия из завершившегося отдельного процесса подкоманды).

        Наблюдение: после `live_runs()` запись дочернего убрана, метка и
        запись родителя на месте с тем же содержимым; живая запись в выдаче
        — родителя.

        Ловит мутацию: в записи дочернего нет `parent_pid`, а pid — родителя
        (запись пишется с `os.getppid()` вместо своего pid) — мёртвая запись
        не распознаётся и остаётся; либо метка пишется с pid дочернего и
        уходит вместе с его мёртвой записью.
        """
        stamp, set_name = self.stamp(), "nabor-" + self.token(5)
        summary = "сводка " + self.token(5)
        mark = self.put_mark(stamp, os.getpid())
        child_pid, copy, log = self.run_child(stamp, set_name, summary)
        ctx = self.msg(log)
        self.assertEqual(json.loads(copy).get("pid"), child_pid, ctx)
        self.assertEqual(json.loads(copy).get("parent_pid"), os.getpid(), ctx)
        self.assertEqual(self.listing(), [mark.name], self.msg(f"реестр после ребёнка: {self.listing()}"))

        parent = self.put_record(stamp, os.getpid(), self.sha, set_name)
        child = self.registry() / self.own_record_name(stamp, child_pid)
        child.write_bytes(copy)
        shot = {p: p.read_bytes() for p in (parent, mark)}

        runs = canary.live_runs()
        ctx = self.msg(f"{runs}; {self.listing()}")
        self.assertFalse(child.exists(), ctx)
        self.assertEqual({p: p.read_bytes() for p in (parent, mark) if p.exists()}, shot, ctx)
        self.assertEqual([e.get("pid") for e in runs], [os.getpid()], ctx)


if __name__ == "__main__":
    unittest.main()
