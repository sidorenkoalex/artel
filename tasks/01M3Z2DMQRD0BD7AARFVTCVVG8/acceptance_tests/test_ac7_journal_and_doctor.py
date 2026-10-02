"""AC-7: коммит закрытия в журнале; `doctor` сверяет ссылку с `origin` и с ним.

Группа: разовый
Красен до реализации: сегодня `refs/artifacts/<id>` до закрытия нет (предусловия о голове ссылки падают), `doctor` сверяет с origin ветку `artifact/<id>`, а не ссылку, и публикует отложенные снимки закрытых задач.

Файл разовый: проверка идёт через настоящий git и bare `origin`, правила
долгоживущих файлов `tests/` такое запрещают.

Строки `doctor` ищутся среди всех его проверок (`doctor.all_checks`) по
содержанию — статус warn/fail и id задачи в имени или тексте строки, — а
не по имени проверки: имени SPEC не называет.
"""
import unittest

from _sandbox import EXTERNAL_TARGET, RefSandbox, legacy_branch, ref_name
from orchestrator import store


class Ac7ClosingJournalTest(RefSandbox):
    """AC-7: запись коммита закрытия."""

    def test_ac7_closing_commit_sha_is_journaled(self):
        """После `kill` журнал задачи называет sha коммита закрытия.

        Ловит мутацию: закрытие пишет в журнал только «задача закрыта» без
        sha коммита — сверять неизменность закрытой ссылки не с чем.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)

        out = self.kill(task_id)

        head = self.local_head(task_id)
        self.assertEqual(self.row(task_id)["state"], "killed", out[-1500:])
        self.assertTrue(head, "ссылки нет после закрытия")
        self.assertTrue(any(head in t for t in self.journal_texts(task_id)),
                        f"sha коммита закрытия {head} не записан в журнал: "
                        f"{self.journal_texts(task_id)[-6:]}")


class Ac7DoctorLiveRefTest(RefSandbox):
    """AC-7 (а): расхождение ссылки живой задачи с `origin`."""

    def test_ac7_doctor_reports_live_ref_diverged_from_origin(self):
        """В `origin` коммит мимо пульта — `doctor` называет задачу.

        Ловит мутацию: сверка с origin осталась на ветке `artifact/<id>` —
        ветки нет, строка не выдаётся, расхождение ссылки не видно.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)
        self.advance_origin_ref(task_id)

        complaints = self.doctor_complaints(task_id)

        self.assertTrue(complaints,
                        f"doctor не сообщил о расхождении {ref_name(task_id)} "
                        f"с origin")

    def test_ac7_doctor_reports_live_ref_ahead_of_origin(self):
        """Локальная ссылка впереди `origin` — `doctor` называет задачу.

        `origin` отвергает запись в `refs/artifacts/*`, поэтому локальный
        коммит туда не уезжает.

        Ловит мутацию: сверка смотрит только на «origin впереди», а
        локальный неотправленный коммит считает нормой — строки нет.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)
        self.reject_ref_pushes()
        self.seed_docs(task_id, {"NOTE.md": "локальная правка\n"},
                       "локальный коммит")
        self.assertNotEqual(self.local_head(task_id), self.origin_head(task_id),
                            "предусловие: локальная ссылка впереди origin")

        complaints = self.doctor_complaints(task_id)

        self.assertTrue(complaints,
                        f"doctor не сообщил, что {ref_name(task_id)} впереди "
                        f"origin")

    def test_ac7_doctor_silent_for_live_ref_in_sync(self):
        """Ссылка живой задачи совпадает с `origin` — строки о ней нет.

        Ловит мутацию: сверка сравнивает с origin не ту ссылку (например
        прежнюю ветку, которой нет) и жалуется на каждую живую задачу.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)

        complaints = self.doctor_complaints(task_id)

        self.assertEqual(complaints, [])


class Ac7DoctorClosedRefTest(RefSandbox):
    """AC-7 (б): закрытая ссылка изменилась после коммита закрытия."""

    def close(self) -> str:
        task_id = self.new_task()
        self.sync_origin(task_id)
        out = self.kill(task_id)
        self.assertEqual(self.row(task_id)["state"], "killed", out[-1500:])
        return task_id

    def test_ac7_doctor_reports_closed_ref_changed_after_closing(self):
        """После закрытия в ссылку лёг ещё коммит — `doctor` называет задачу.

        Новый коммит отправлен и в `origin`: строка обязана появиться
        именно из-за расхождения с коммитом закрытия в журнале, а не из-за
        расхождения с `origin`.

        Ловит мутацию: закрытые задачи исключены из сверки (как сегодня —
        сверяются только живые) — изменённая после закрытия ссылка молчит.
        """
        task_id = self.close()
        self.seed_docs(task_id, {"AFTER.md": "после закрытия\n"},
                       "правка после закрытия")
        self.sync_origin(task_id)

        complaints = self.doctor_complaints(task_id)

        self.assertTrue(complaints,
                        f"doctor не сообщил об изменении закрытой "
                        f"{ref_name(task_id)}")

    def test_ac7_doctor_silent_for_closed_ref_unchanged(self):
        """Закрытая ссылка равна коммиту закрытия — строки о ней нет.

        Ловит мутацию: сверка закрытой ссылки сравнивает голову не с
        коммитом закрытия из журнала, а с прежней головой до закрытия, — и
        жалуется на каждую закрытую задачу.
        """
        task_id = self.close()

        complaints = self.doctor_complaints(task_id)

        self.assertEqual(complaints, [])


class Ac7NoLegacyChecksTest(RefSandbox):
    """AC-7: проверок ветки `artifact/*` и отложенных снимков не остаётся."""

    def test_ac7_doctor_ignores_legacy_artifact_branch(self):
        """Ветка `artifact/<id>` живой задачи, разошедшаяся с origin, — молчание.

        Ветку заводит сам тест (как наследие прежнего устройства), локальная
        и в origin — на разных коммитах. Ни одна строка `doctor` её не
        называет.

        Ловит мутацию: проверка синхронности ветки `artifact/*` оставлена в
        `doctor` рядом с новой — строка «ветка разошлась с origin» есть.
        """
        task_id = self.new_task()
        self.sync_origin(task_id)
        branch = legacy_branch(task_id)
        self.git("branch", "-f", branch, "main")
        self.git("push", "-q", "origin", f"{branch}:{branch}")
        self.git("commit", "--allow-empty", "-q", "-m", "наследие")
        self.git("branch", "-f", branch, "HEAD")

        lines = [c for c in self.doctor_checks()
                 if branch in f"{c.name} {c.detail}"]

        self.assertEqual(lines, [], f"doctor проверяет ветку {branch}")

    def test_ac7_doctor_does_not_publish_pending_snapshot(self):
        """Закрытая задача внешнего target с веткой `artifact/<id>` — без снимка.

        Сегодня такая задача считается «снимок не доставлен»: `doctor`
        публикует снимок в `refs/artifacts/<id>` origin клона target
        (клон с origin заведён) и удаляет ветку, а строка проверки называет
        её. После этой части `doctor` такого не делает: ссылка и ветка не
        меняются, строки о ветке нет.

        Ловит мутацию: проверка отложенных снимков оставлена — `doctor`
        публикует снимок, удаляет ветку `artifact/<id>` и пишет об этом
        строку.
        """
        self.declare_external_target()
        self.make_target_workspace()
        task_id = self.new_task(target=EXTERNAL_TARGET)
        branch = legacy_branch(task_id)
        self.git("branch", "-f", branch, "main")
        state = self.row(task_id)["state"]
        store.set_state(store.db(), task_id, "done", "fsm",
                        expected_state=state, detail="закрыта планкой AC-7")
        local_before = self.local_head(task_id)
        origin_before = self.origin_head(task_id)

        lines = [c for c in self.doctor_checks()
                 if branch in f"{c.name} {c.detail}"]

        self.assertEqual(lines, [], f"doctor разбирает ветку {branch}")
        self.assertTrue(self.legacy_branch_local(task_id),
                        "doctor удалил ветку artifact/<id>")
        self.assertEqual(self.local_head(task_id), local_before,
                         "doctor переписал локальную ссылку")
        self.assertEqual(self.origin_head(task_id), origin_before,
                         "doctor переписал ссылку в origin")


if __name__ == "__main__":
    unittest.main()
