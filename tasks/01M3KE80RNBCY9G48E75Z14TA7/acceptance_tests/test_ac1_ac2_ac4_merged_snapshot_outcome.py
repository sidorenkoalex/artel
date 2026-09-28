"""Приёмочные тесты AC-1, AC-2, AC-4 (путь закрытия мержем) —
tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Предмет — ретроспектива `tasks/<id>/RETRO.md` ВНУТРИ снимка
`refs/artifacts/<id>` origin целевого и сообщение коммита этого снимка
после закрытия задачи мержем.

Красен до реализации: путь закрытия мержем передаёт в публикацию снимка
литерал «killed» (`orchestrator/cleanup.py:414`, единственный аргумент
исхода у `_publish_snapshot_if_pending`), поэтому ретроспектива снимка
смерженной задачи сегодня несёт «Итог: killed — причина: …», строку
«артефакты не сохранены» и сообщение коммита «снапшот закрытия (killed)».
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ClosingSnapshotSandbox  # noqa: E402

TASK = "01PLANKMERGEDOUTCOME000001"

#: sha в строке «Итог: done, sha …» — непустой hex-идентификатор коммита.
#: Именно непустой, а не равный конкретному sha: SPEC «Не входит» прямо
#: запрещает заводить под него новый носитель, источник остаётся тот же,
#: что уже доступен пути закрытия, и планка его не диктует.
DONE_LINE_RE = re.compile(r"^Итог: done, sha ([0-9a-f]{7,40})$", re.M)


class MergedSnapshotOutcomeTest(ClosingSnapshotSandbox):

    def setUp(self):
        super().setUp()
        self.seed_merge_gate_task(TASK)

    def test_ac1_merged_snapshot_retro_reports_done_with_merge_sha(self):
        """Задача закрыта мержем — ретроспектива её снимка несёт «Итог:
        done, sha <sha>» с непустым sha, и ни «Итог: killed», ни «причина:»
        в ней не остаётся.

        Ловит мутацию: исход, передаваемый в публикацию снимка на пути
        закрытия мержем, остаётся литералом «killed» (или берётся не из
        состояния задачи, а, скажем, из ветки «есть ли причина в журнале»)
        — файл `tasks/<id>/RETRO.md` опубликованной ссылки
        `refs/artifacts/<id>` соберётся `retro.build_killed`, строки
        «Итог: done, sha …» в нём не будет вовсе, а «Итог: killed —
        причина: …» будет.
        """
        self.assertEqual(self.approve_merge(TASK), ("done",))

        retro_text = self.snapshot_retro_text(TASK)
        match = DONE_LINE_RE.search(retro_text)
        self.assertIsNotNone(
            match,
            f"ретроспектива снимка смерженной задачи обязана нести «Итог: "
            f"done, sha <sha>» с непустым sha мержа (AC-1); получено:\n"
            f"{retro_text}")
        self.assertNotIn(
            "Итог: killed", retro_text,
            "ретроспектива снимка смерженной задачи не вправе нести "
            "«Итог: killed» (AC-1)")
        self.assertNotIn(
            "причина:", retro_text,
            "строка причины остаётся только у исхода killed (AC-1)")

    def test_ac2_merged_snapshot_retro_addresses_the_artifacts_ref(self):
        """Та же ретроспектива снимка адресует артефакты вечной ссылкой
        `refs/artifacts/<id>`, а не заметкой об удалённой при kill ветке.

        Ловит мутацию: строка «Адрес артефактов» собирается для смерженной
        задачи прежней killed-веткой (`retro.NO_ARTIFACTS_NOTE`) — в
        ретроспективе снимка не окажется `refs/artifacts/<id>`, зато
        окажется «артефакты не сохранены», и обе проверки ниже это видят.
        """
        self.approve_merge(TASK)

        retro_text = self.snapshot_retro_text(TASK)
        self.assertIn(
            f"Адрес артефактов: {self.snapshot_ref(TASK)}", retro_text,
            f"ретроспектива снимка смерженной задачи обязана называть "
            f"адрес {self.snapshot_ref(TASK)} (AC-2); получено:\n{retro_text}")
        self.assertNotIn(
            "артефакты не сохранены", retro_text,
            "подстроки «артефакты не сохранены» в ретроспективе снимка "
            "смерженной задачи быть не должно (AC-2)")

    def test_ac4_merged_snapshot_commit_message_names_done(self):
        """Сообщение коммита снимка смерженной задачи называет фактический
        исход — «снапшот закрытия (done)».

        Ловит мутацию: исход вычислен верно для текста ретроспективы, но в
        сообщение коммита снимка по-прежнему подставляется прежний литерал
        — заголовок коммита ссылки `refs/artifacts/<id>` останется
        «снапшот закрытия (killed)», и проверки ниже разойдутся с ним.
        """
        self.approve_merge(TASK)

        subject = self.snapshot_commit_subject(TASK)
        self.assertIn(
            "снапшот закрытия (done)", subject,
            f"сообщение коммита снимка обязано называть исход done "
            f"(AC-4); получено: {subject!r}")
        self.assertNotIn(
            "(killed)", subject,
            f"сообщение коммита снимка смерженной задачи не вправе "
            f"называть исход killed (AC-4); получено: {subject!r}")


if __name__ == "__main__":
    unittest.main()
