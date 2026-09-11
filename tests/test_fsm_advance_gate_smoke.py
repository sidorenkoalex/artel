"""Смоук трёх сценариев рефакторинга R2 (SPEC 01M1TKNXX5YN5KT4WHG4T44JWV,
требование 6, AC-9): отказ гейта ёмкости, отказ гейта зон, отказ рубежа
«замечания не отработаны» (регрессии №13/№15) — журнал (`store.journal`)
и stdout после рефакторинга совпадают байт-в-байт со значениями,
зафиксированными прогоном ДО правки кода (тем же способом, что уже
проверяют `tests/test_capacity_gate.py`/`tests/test_zones_gate.py`/
`tests/test_fsm_review_rework_gate.py` для каждого гейта по отдельности
— этот файл фиксирует буквальные строки как эталон снимка, не переносит
их логику).

Фикстуры гейтов ёмкости/зон обновлены при подтяжке main (ANSWER-1.md):
`01M1SG9T962WJJ31S282GWM0EN` сменила базу сравнения обоих гейтов на
`gitcmd.diff_base`/`diff_base_source` и добавила «база сравнения ... от
...» в тексты отказов — снимок «до правки» этой задачи предшествовал
той подтяжке, поэтому байт-в-байт сверяется уже с объединённым
поведением (структура каркаса этой задачи + база сравнения main),
`diff_base`/`diff_base_source` замокан явно на детерминированное
значение, тем же приёмом, что `tests/test_zones_gate.py::
GitFailureTest.test_git_not_answering_diff_names_refuses`.
"""
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _capture(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args)
    return result, buf.getvalue()


class CapacityGateSmokeTest(TmpRootTest):

    def test_matches_the_pre_refactor_fixture_byte_for_byte(self):
        task_id = "T001"
        conn = store.db()
        store.create_schema(conn)
        t = {"title": "Тест смоука", "branch": "task/t001-x"}
        store.insert_task(conn, task_id, "Тест смоука", "in_dev",
                          "task/t001-x", "artel", 25.0)

        code_body = "x" * (config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 100)

        def git_diff(*args):
            if args and args[0] == "diff":
                if f":!tasks/{task_id}/" in args:
                    return subprocess.CompletedProcess(list(args), 0, code_body, "")
                if f"tasks/{task_id}/" in args:
                    return subprocess.CompletedProcess(list(args), 0, "", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", git_diff), \
             mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_base_source",
                               return_value="origin/main"):
            refused, out = _capture(
                fsm_advance._capacity_gate_refuses, conn, task_id, t, "in_dev")

        self.assertTrue(refused)
        self.assertEqual(
            out,
            "[T001] переход отклонён: снимок не помещается в один "
            "контекст ревью — разделить задачу (T001 «Тест смоука», "
            f"база сравнения deadbeef от origin/main): diff кода "
            f"{config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 100} "
            f"байт > потолка {config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт (исключённые артефакты "
            "tasks/T001/: 0 байт (изменений нет))\n"
            "  дальше: решение Оператора — разделить задачу или "
            "поднять потолок (ADR-0002)\n")
        rows = conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (task_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["actor"], "fsm")
        self.assertEqual(rows[0]["action"], "переход отклонён: гейт ёмкости diff")
        self.assertEqual(
            rows[0]["detail"],
            "снимок не помещается в один контекст ревью — разделить "
            "задачу (T001 «Тест смоука», база сравнения deadbeef от "
            f"origin/main): diff кода {config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 100} байт "
            f"> потолка {config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт "
            "(исключённые артефакты tasks/T001/: 0 байт (изменений нет))")


class ZonesGateSmokeTest(TmpRootTest):

    def test_matches_the_pre_refactor_fixture_byte_for_byte(self):
        task_id = "T002"
        conn = store.db()
        store.create_schema(conn)
        t = {"title": "Тест зон", "branch": "task/t002-x",
             "zones": "orchestrator/foo.py", "zones_extension": None}
        store.insert_task(conn, task_id, "Тест зон", "in_dev",
                          "task/t002-x", "artel", 25.0)

        def git_diff_names(*args):
            if args and args[0] == "diff" and "--name-only" in args:
                return subprocess.CompletedProcess(
                    list(args), 0, "orchestrator/bar.py\n", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", git_diff_names), \
             mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_base_source",
                               return_value="origin/main"):
            refused, out = _capture(
                fsm_advance._zones_gate_refuses, conn, task_id, t,
                "artifact/t002", "# PLAN\n")

        self.assertTrue(refused)
        self.assertEqual(
            out,
            "[T002] переход отклонён: дифф трогает файлы вне заявленных "
            "zones и COMMON_ZONES (база сравнения deadbeef от "
            "origin/main): orchestrator/bar.py\n"
            "  дальше: сократи дифф до заявленных zones либо оформи "
            "раздел «## Расширение зон» в PLAN.md с обоснованием и "
            "мандатом Оператора («Расширение зон разрешено: <пути>» "
            "в ANSWER-n.md), и повтори artel.py advance T002\n")
        rows = conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (task_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["actor"], "fsm")
        self.assertEqual(rows[0]["action"], "переход отклонён: гейт зон")
        self.assertEqual(
            rows[0]["detail"],
            "дифф трогает файлы вне заявленных zones и COMMON_ZONES "
            "(база сравнения deadbeef от origin/main): "
            "orchestrator/bar.py")


class ReviewReworkGateSmokeTest(TmpRootTest):

    def test_matches_the_pre_refactor_fixture_byte_for_byte(self):
        task_id = "T001"
        conn = store.db()
        store.create_schema(conn)
        code_branch = "task/t001-x"
        artifact_branch = "artifact/t001"
        t = {"branch": code_branch}
        store.insert_task(conn, task_id, "Тест rework", "in_dev",
                          code_branch, "artel", 25.0)

        review_md = (
            "---\ntask: T001\ntype: review\nauthor_role: reviewer\n"
            "status: changes_requested\niteration: 1\nschema_version: 1\n"
            "---\n\n# REVIEW\n")

        def log_reply(subject, when):
            return f"{when}\x1f{subject}\n"

        def fake_git(*args):
            if args[0] == "log" and "-1" in args:
                return subprocess.CompletedProcess(
                    list(args), 0, "2026-08-01T10:00:00+00:00\n", "")
            if args[0] == "log" and "--" in args:
                return subprocess.CompletedProcess(
                    list(args), 0,
                    log_reply("T001: правка REVIEW.md вручную",
                             "2026-08-03T10:00:00+00:00"), "")
            if args[0] == "log":
                return subprocess.CompletedProcess(
                    list(args), 0,
                    log_reply("код фикса", "2026-07-31T10:00:00+00:00"), "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "show", lambda *a: (review_md, "")), \
             mock.patch.object(gitcmd, "git", fake_git):
            refused, out = _capture(
                fsm_advance._review_rework_gate_refuses, conn, task_id, t,
                artifact_branch)

        self.assertTrue(refused)
        self.assertEqual(
            out,
            "[T001] переход отклонён: замечания ревью не отработаны: "
            "нет шага developer после итерации 1 (опорное время "
            "2026-08-01T10:00:00+00:00 — последний коммит REVIEW.md; "
            "последний коммит developer 2026-07-31T10:00:00+00:00)\n"
            "  дальше: почини код (не спорь с ревью втихую) и повтори "
            "artel.py advance T001\n")
        rows = conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (task_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["actor"], "fsm")
        self.assertEqual(
            rows[0]["action"], "переход отклонён: замечания ревью не отработаны")
        self.assertEqual(
            rows[0]["detail"],
            "замечания ревью не отработаны: нет шага developer после "
            "итерации 1 (опорное время 2026-08-01T10:00:00+00:00 — "
            "последний коммит REVIEW.md; последний коммит developer "
            "2026-07-31T10:00:00+00:00)")


if __name__ == "__main__":
    unittest.main()
