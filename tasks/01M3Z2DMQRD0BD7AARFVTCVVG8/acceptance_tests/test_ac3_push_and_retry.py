"""AC-3: ссылка отправляется в `origin` после каждого коммита; отказ — журнал и повтор.

Группа: разовый
Красен до реализации: сегодня `new` и `zones-extend` пишут и отправляют ветку `artifact/<id>`, а `refs/artifacts/<id>` нет ни локально, ни в `origin` — сверка голов падает на пустой ссылке.

Файл разовый: проверка идёт через настоящий git и bare `origin`, а правила
долгоживущих файлов `tests/` вызов git запрещают.

Коммиты в ссылку делают публичные команды (`new`, `zones-extend`), а не
прямой вызов узла записи: критерий говорит «после каждого коммита», и
планка не диктует, внутри какой функции стоит отправка.
«Следующий переход» — `store.set_state`, единственная точка любого
перехода FSM. Задача — артели, поэтому сама смена состояния нового коммита
(строки паспорта) не пишет: совпадение с `origin` после неё — именно
повторная отправка, а не попутный push нового коммита.
"""
import unittest

from _sandbox import RefSandbox, ref_name
from orchestrator import store

FAILURE_WORDS = ("fail", "отказ", "не удал", "не отправ", "ошибк", "сеть",
                 "недоступ", "не прош")


class Ac3PushTest(RefSandbox):
    """AC-3."""

    def test_ac3_each_commit_is_pushed_to_origin(self):
        """После `new` и после следующего коммита голова в `origin` равна локальной.

        Ловит мутацию: отправка остаётся только в `new` (как сегодня у
        ветки — push зовут лишь отдельные места), а `zones-extend` коммитит
        без push — голова в `origin` отстаёт от локальной на коммит с
        `ANSWER-1.md`.
        """
        task_id = self.new_task()
        head_new = self.local_head(task_id)
        self.assertTrue(head_new, f"после new нет {ref_name(task_id)}")
        self.assertEqual(self.origin_head(task_id), head_new,
                         "после new ссылка не отправлена в origin")

        self.run_cli("zones-extend", task_id, "docs/extra.md")

        head = self.local_head(task_id)
        self.assertNotEqual(head, head_new, "zones-extend не дал коммита")
        self.assertEqual(self.origin_head(task_id), head,
                         "после zones-extend ссылка не отправлена в origin")

    def test_ac3_push_refusal_is_journaled_and_retried_on_next_transition(self):
        """Отказ push: запись в журнале, коммит цел; следующий переход досылает.

        `origin` недоступен во время `zones-extend`: локальная голова несёт
        `ANSWER-1.md`, в журнале задачи появилась запись об отказе push, в
        `origin` осталась прежняя голова. `origin` вернули, задача сменила
        состояние — голова в `origin` равна локальной.

        Ловит мутацию: отказ push проглатывается без повтора (как сегодня —
        best-effort, следующий push только при следующем коммите) — после
        перехода без нового коммита `origin` так и остаётся на голове `new`.
        """
        task_id = self.new_task()
        head_new = self.local_head(task_id)
        self.assertEqual(self.origin_head(task_id), head_new,
                         "предусловие: после new ссылка в origin")
        journal_before = len(self.journal_texts(task_id))

        url = self.break_origin()
        self.run_cli("zones-extend", task_id, "docs/extra.md")
        self.restore_origin(url)

        head = self.local_head(task_id)
        self.assertNotEqual(head, head_new, "коммит zones-extend потерян")
        self.assertIsNotNone(
            self.file_at(head, f"tasks/{task_id}/ANSWER-1.md"),
            "правка zones-extend не в локальной ссылке")
        self.assertEqual(self.origin_head(task_id), head_new,
                         "предусловие сценария: origin не получил коммит")
        new_rows = self.journal_texts(task_id)[journal_before:]
        refusal = [r for r in new_rows
                   if ("push" in r.lower() or "отправ" in r.lower())
                   and any(w in r.lower() for w in FAILURE_WORDS)]
        self.assertTrue(refusal,
                        f"нет записи журнала об отказе push: {new_rows}")

        state = store.get_task(store.db(), task_id)["state"]
        store.set_state(store.db(), task_id, "spec_gate", "fsm",
                        expected_state=state, detail="переход планки AC-3")

        self.assertEqual(self.origin_head(task_id), self.local_head(task_id),
                         "после перехода ссылка не дослана в origin")
        self.assertTrue(self.is_ancestor(head, self.origin_head(task_id)),
                        "коммит zones-extend не дошёл до origin")


if __name__ == "__main__":
    unittest.main()
