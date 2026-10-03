"""AC-8: лок планки и фиксация документов — коммиты ссылки; расхождение — отказ.

Группа: разовый
Красен до реализации: сегодня лок и фиксация смотрят на ветку `artifact/<id>`, а `refs/artifacts/<id>` нет — предусловия о голове ссылки падают; `approve` без sha не сверяет голову документов с зафиксированной на переходе.

Файл разовый: проверка идёт через настоящий git, правила долгоживущих файлов
`tests/` такое запрещают.

Лок (инвариант 27) проверяется переходом `in_dev`: правка планки после
лока — тем же узлом записи документов, каким пишет автокоммит роли.
Сверка фиксации (инвариант 25, часть о документах) проверяется командой
`approve` без sha: инвариант 25 называет именно её сверку живого состояния
документов с зафиксированным на последнем переходе; отказ — запись журнала
«approve отклонён» с живым sha, как у сегодняшнего отказа сверки.
"""
import unittest

from _sandbox import (FIXTURE_PLAN_READY, FIXTURE_SPEC, RefSandbox, plank_text,
                      ref_name)
from orchestrator import store


class Ac8LockTest(RefSandbox):
    """AC-8: лок `acceptance_tests/` на коммите ссылки."""

    def setUp(self):
        super().setUp()
        self.task_id = self.new_task()
        self.prepare_tests_writing(self.task_id)
        self.lock_plank(self.task_id)
        self.locked = self.row(self.task_id)["tests_locked_sha"]
        self.assertTrue(self.local_head(self.task_id),
                        f"предусловие: есть {ref_name(self.task_id)}")

    def lock_refusals(self, journal_before: int) -> list:
        return [t for t in self.journal_texts(self.task_id)[journal_before:]
                if self.locked in t and "acceptance_tests" in t]

    def test_ac8_tests_locked_sha_is_a_ref_commit_with_plank(self):
        """`tests_locked_sha` — коммит истории ссылки, в его дереве планка.

        Ловит мутацию: лок берёт голову прежней ветки `artifact/<id>` или
        HEAD кодовой ветки — коммит не принадлежит истории ссылки.
        """
        head = self.local_head(self.task_id)
        self.assertTrue(self.locked, "tests_locked_sha не записан")
        self.assertIn(self.locked, self.chain(head),
                      f"лок вне истории {ref_name(self.task_id)}")
        self.assertIsNotNone(
            self.file_at(self.locked, f"tasks/{self.task_id}/acceptance_tests/"
                                      f"test_ac1_plank.py"),
            "в дереве лока нет планки")

    def test_ac8_lock_refuses_when_plank_diverges_from_locked_ref_commit(self):
        """Планка в ссылке изменена после лока — переход из `in_dev` отказан.

        Ловит мутацию: лок сверяет `tests_locked_sha` с прежней веткой
        (её нет — «нечего сверять») и пропускает правку планки разработчиком.
        """
        self.seed_docs(self.task_id, {
            "PLAN.md": FIXTURE_PLAN_READY.format(task=self.task_id),
            "acceptance_tests/test_ac1_plank.py": plank_text("ПРАВКА-ПОСЛЕ-ЛОКА"),
        }, "PLAN и правка планки после лока")
        journal_before = len(self.journal_texts(self.task_id))

        out = self.advance(self.task_id)

        self.assertEqual(self.row(self.task_id)["state"], "in_dev", out[-1500:])
        self.assertTrue(self.lock_refusals(journal_before),
                        f"нет отказа лока с sha {self.locked}: "
                        f"{self.journal_texts(self.task_id)[journal_before:]}")

    def test_ac8_lock_does_not_refuse_when_plank_unchanged(self):
        """Планка не менялась после лока — отказа лока нет.

        Ловит мутацию: сверка лока сравнивает с коммитом, которого нет в
        ссылке (пустой diff трактуется как сбой git) — отказ на каждом
        переходе.
        """
        self.seed_docs(self.task_id, {
            "PLAN.md": FIXTURE_PLAN_READY.format(task=self.task_id),
        }, "PLAN без правки планки")
        journal_before = len(self.journal_texts(self.task_id))

        self.advance(self.task_id)

        self.assertEqual(self.lock_refusals(journal_before), [])


class Ac8FixationTest(RefSandbox):
    """AC-8: зафиксированное состояние документов на переходе."""

    def setUp(self):
        super().setUp()
        self.task_id = self.new_task()
        self.assertTrue(self.local_head(self.task_id),
                        f"предусловие: после new есть {ref_name(self.task_id)}")
        self.seed_docs(self.task_id,
                       {"SPEC.md": FIXTURE_SPEC.format(task=self.task_id)},
                       "SPEC ready")
        state = self.row(self.task_id)["state"]
        store.set_state(store.db(), self.task_id, "spec_gate", "fsm",
                        expected_state=state, detail="переход планки AC-8")

    def refusals(self, journal_before: int) -> list:
        return [t for t in self.journal_texts(self.task_id)[journal_before:]
                if t.startswith("approve отклонён")]

    def test_ac8_approve_refuses_when_ref_moved_after_transition(self):
        """Голова ссылки сдвинулась после перехода — `approve` без sha отказан.

        Отказ называет живую голову ссылки; задача остаётся на гейте.

        Ловит мутацию: зафиксированное состояние документов по-прежнему —
        sha репозитория фиксации, куда документы не пишутся, — коммит в
        ссылку после перехода не виден, `approve` проходит.
        """
        moved = self.seed_docs(self.task_id, {"NOTE.md": "после перехода\n"},
                               "коммит после перехода")
        self.assertEqual(self.local_head(self.task_id), moved)
        journal_before = len(self.journal_texts(self.task_id))

        out = self.approve(self.task_id)

        self.assertEqual(self.row(self.task_id)["state"], "spec_gate",
                         out[-1500:])
        refusals = self.refusals(journal_before)
        self.assertTrue(refusals, f"approve не отказал:\n{out[-1500:]}")
        self.assertTrue(any(moved in t for t in refusals),
                        f"отказ не называет живую голову ссылки {moved}: "
                        f"{refusals}")

    def test_ac8_approve_does_not_refuse_when_ref_unchanged(self):
        """Ссылка не менялась после перехода — сверка фиксации не отказывает.

        Ловит мутацию: зафиксированным считается не коммит ссылки на
        переходе, а что-то иное (sha кодовой ветки, пустая строка) —
        `approve` отказывает при неизменных документах.
        """
        journal_before = len(self.journal_texts(self.task_id))

        out = self.approve(self.task_id)

        self.assertEqual(self.refusals(journal_before), [], out[-1500:])


if __name__ == "__main__":
    unittest.main()
