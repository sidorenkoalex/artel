"""AC-6: гейт мержа и закрытие отказывают, пока ссылка не совпадает с `origin`.

Группа: разовый
Красен до реализации: сегодня ни `kill`, ни `approve` на гейте мержа не сверяют `refs/artifacts/<id>` с `origin` (ссылки до закрытия нет вовсе) — предусловие о голове ссылки падает, а закрытие проходит при любом расхождении.

Файл разовый: проверка идёт через настоящий git и bare `origin`, правила
долгоживущих файлов `tests/` такое запрещают.

Расхождение строится так, чтобы попутная отправка пульта его не лечила:
либо в `origin` лежит коммит мимо пульта (обычный push отвергнут как
non-fast-forward), либо ссылки в `origin` нет и `origin` отвергает запись
в `refs/artifacts/*` хуком `pre-receive`. «Именованный отказ» — запись
журнала или вывод команды со словом отказа и упоминанием `origin`.
"""
import unittest

from _sandbox import EXTERNAL_TARGET, RefSandbox, ref_name

REFUSAL_WORDS = ("отказ", "отклон")


class _RefusalMixin:

    def assert_named_refusal(self, task_id: str, journal_before: int,
                             out: str) -> None:
        rows = self.journal_texts(task_id)[journal_before:]
        texts = [out] + rows
        named = [t for t in texts
                 if any(w in t.lower() for w in REFUSAL_WORDS)
                 and "origin" in t]
        self.assertTrue(named, f"нет именованного отказа с упоминанием "
                               f"origin:\nвывод: {out[-1500:]}\nжурнал: {rows}")

    def diverge_origin(self, task_id: str) -> str:
        self.sync_origin(task_id)
        return self.advance_origin_ref(task_id)

    def drop_from_origin(self, task_id: str) -> None:
        self.sync_origin(task_id)
        self.drop_origin_ref(task_id)
        self.reject_ref_pushes()
        self.assertEqual(self.origin_head(task_id), "",
                         "предусловие: ссылки в origin нет")


class Ac6KillTest(_RefusalMixin, RefSandbox):
    """AC-6: закрытие `kill`."""

    def test_ac6_kill_refuses_when_origin_diverged(self):
        """В `origin` коммит мимо пульта — `kill` отказывает, задача не закрыта.

        Ловит мутацию: закрытие не сверяет локальную ссылку с `origin` —
        задача уходит в `killed`, коммит закрытия ложится поверх ссылки,
        расходящейся с `origin`.
        """
        task_id = self.new_task()
        self.diverge_origin(task_id)
        before = self.local_head(task_id)
        state = self.row(task_id)["state"]
        journal_before = len(self.journal_texts(task_id))

        out = self.kill(task_id)

        self.assertEqual(self.row(task_id)["state"], state,
                         f"kill закрыл задачу при расхождении:\n{out[-1500:]}")
        self.assertEqual(self.local_head(task_id), before,
                         "коммит закрытия записан при расхождении")
        self.assert_named_refusal(task_id, journal_before, out)

    def test_ac6_kill_refuses_when_ref_missing_in_origin(self):
        """Ссылки в `origin` нет — `kill` отказывает, задача не закрыта.

        Ловит мутацию: сверка считает «в origin нет ссылки» совпадением
        (пустой sha origin пропускается как «нечего сверять») — задача
        уходит в `killed`, история документов есть только локально.
        """
        task_id = self.new_task()
        self.drop_from_origin(task_id)
        state = self.row(task_id)["state"]
        journal_before = len(self.journal_texts(task_id))

        out = self.kill(task_id)

        self.assertEqual(self.row(task_id)["state"], state,
                         f"kill закрыл задачу без ссылки в origin:\n{out[-1500:]}")
        self.assert_named_refusal(task_id, journal_before, out)

    def test_ac6_kill_passes_when_in_sync(self):
        """Ссылка совпадает с `origin` — `kill` закрывает задачу.

        Ловит мутацию: сверка с `origin` сравнивает не те значения (например
        локальную голову с пустой строкой) и отказывает всегда — задача не
        закрывается даже при совпадении.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)

        out = self.kill(task_id)

        self.assertEqual(self.row(task_id)["state"], "killed", out[-1500:])


class Ac6MergeGateTest(_RefusalMixin, RefSandbox):
    """AC-6: гейт мержа."""

    def setUp(self):
        super().setUp()
        self.declare_external_target()
        self.task_id = self.new_task(target=EXTERNAL_TARGET)
        self.prepare_external_merge_gate(self.task_id)

    def test_ac6_merge_gate_refuses_when_origin_diverged(self):
        """В `origin` коммит мимо пульта — `approve` на гейте мержа отказывает.

        Ловит мутацию: гейт мержа не сверяет ссылку документов с `origin` —
        задача уходит в `done`, закрытие ложится на разошедшуюся ссылку.
        """
        self.diverge_origin(self.task_id)
        journal_before = len(self.journal_texts(self.task_id))

        out = self.approve(self.task_id)

        self.assertEqual(self.row(self.task_id)["state"], "merge_gate",
                         f"мерж прошёл при расхождении:\n{out[-1500:]}")
        self.assert_named_refusal(self.task_id, journal_before, out)

    def test_ac6_merge_gate_refuses_when_ref_missing_in_origin(self):
        """Ссылки в `origin` нет — `approve` на гейте мержа отказывает.

        Ловит мутацию: отсутствие ссылки в `origin` гейт трактует как
        «сверять не с чем» и пропускает мерж.
        """
        self.drop_from_origin(self.task_id)
        journal_before = len(self.journal_texts(self.task_id))

        out = self.approve(self.task_id)

        self.assertEqual(self.row(self.task_id)["state"], "merge_gate",
                         f"мерж прошёл без ссылки в origin:\n{out[-1500:]}")
        self.assert_named_refusal(self.task_id, journal_before, out)

    def test_ac6_merge_gate_passes_when_in_sync(self):
        """Ссылка совпадает с `origin` — `approve` доводит задачу до `done`.

        Ловит мутацию: сверка отказывает всегда (перепутано условие
        совпадения) — синхронная задача остаётся на гейте мержа.
        """
        self.sync_origin(self.task_id)

        out = self.approve(self.task_id)

        self.assertEqual(self.row(self.task_id)["state"], "done", out[-1500:])
        self.assertTrue(self.local_head(self.task_id),
                        f"ссылка {ref_name(self.task_id)} пропала после мержа")


if __name__ == "__main__":
    unittest.main()
