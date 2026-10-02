"""Исход в ретроспективе коммита закрытия (SPEC
01M3KE80RNBCY9G48E75Z14TA7, требования 1-4, 9; AC-1..AC-5, AC-9, AC-10;
с ADR-0021 п.3 — коммит RETRO в ссылку документов вместо снимка, SPEC
01M3Z2DMQRD0BD7AARFVTCVVG8, требование 3, AC-5).

До этой задачи `cleanup._publish_snapshot_if_pending` передавал в
публикацию литерал «killed» на ОБОИХ путях закрытия, и снимок смерженной
задачи утверждал «Итог: killed — причина: причина не найдена в журнале»
(01M3HP7WAXKFK3GYZ3T6HX08M0, смержена 27.09). Здесь проверяется, что
исход приходит из состояния задачи в БД: `done` у смерженной, `killed` у
ликвидированной — и в тексте ретроспективы, и в сообщении коммита снимка.

Настоящий git и настоящий bare-`origin` (`sandbox.SyncedOriginConnSandbox`):
предмет проверки — содержимое ссылки `refs/artifacts/<id>` в origin
целевого, то есть результат push, а не аргументы вызова. Target — self
(`config.DEFAULT_TARGET`): для него репозиторий целевого и есть
`config.ROOT` песочницы (`snapshot._target_workspace`), отдельный клон
заводить не нужно. Сквозной путь МЕРЖА (тело гейта целиком) проверяет
`tests/test_fsm_merge_gate_done_snapshot.py`.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, cleanup, config,  # noqa: E402
                          gitcmd, store)
from tests.sandbox import SyncedOriginConnSandbox, capture  # noqa: E402

TASK = "01M3SNAPSHOTOUTCOME001"

SPEC_TEXT = """---
task: 01M3SNAPSHOTOUTCOME001
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: задача для снимка

## Контекст

Снимок закрытия несёт верный исход. Второе предложение в «Суть» не идёт.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

#: Планка ветки: три метода, одна пометка `manual` — числа отличимы и от
#: нулей деградации, и друг от друга. `@ac` склеивается при сборке строки,
#: чтобы литерал не читался сканерами пульта как тест ЭТОГО файла.
ACCEPTANCE = ('''"""Планка приёмки задачи."""
# @AC-4: manual — проверяется руками.
import unittest


class T(unittest.TestCase):
    def test_@ac1_one(self):
        pass

    def test_@ac2_two(self):
        pass

    def test_@ac3_three(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")

COUNTS_LINE = "Приёмочные тесты: 3 тест(ов), 1 manual, 0 skip"
GIST_LINE = "Суть: Задача для снимка — Снимок закрытия несёт верный исход."
RETRO_REL = f"tasks/{TASK}/RETRO.md"


class ClosingSnapshotOutcomeTest(SyncedOriginConnSandbox):
    """Задача с живой артефактной веткой, без каталога в главной копии."""

    def setUp(self):
        super().setUp()
        # Адрес origin песочницы (`add_synced_origin` его не возвращает
        # наружу) — тем же вопросом к git, каким его задаёт сам пульт.
        self.origin = Path(self.git("remote", "get-url", "origin").strip())
        store.insert_task(self.conn, TASK, "Задача для снимка", "merge_gate",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          50.0)
        artifact_branch.commit_files(
            TASK,
            {f"tasks/{TASK}/SPEC.md": SPEC_TEXT,
             f"tasks/{TASK}/PLAN.md": "план\n",
             f"tasks/{TASK}/acceptance_tests/test_planka.py": ACCEPTANCE},
            f"{TASK}: артефакты задачи")

    def ref(self) -> str:
        return f"refs/artifacts/{TASK}"

    def origin_show(self, rel: str) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "show", f"{self.ref()}:{rel}"],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"{self.ref()}:{rel} не читается: {res.stderr}")
        return res.stdout

    def origin_ref_exists(self) -> bool:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "show-ref", "--verify", "--quiet",
             self.ref()], capture_output=True, text=True)
        return res.returncode == 0

    def origin_commit_subject(self) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "log", "-1", "--format=%s",
             self.ref()], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def publish(self, state: str, *, is_canary: bool = False) -> str:
        """Закрывает задачу переходом в `state` и пишет коммит закрытия
        тем же узлом, которым это делают оба пути закрытия. Канарейка с
        ADR-0021 (п.13) идёт тем же потоком — признак в строке БД."""
        if is_canary:
            store.update_task(self.conn, TASK, is_canary=1)
        store.set_state(self.conn, TASK, state, "orchestrator",
                        expected_state="merge_gate", detail="смержено: ветка"
                        if state == "done" else "kill switch")
        return capture(cleanup._commit_closing, self.conn, TASK)

    def test_merged_task_snapshot_says_done_with_a_non_empty_sha(self):
        """AC-1: снимок задачи, закрытой мержем, несёт «Итог: done, sha
        <непустой sha>» — и ни «Итог: killed», ни строки причины.

        Ловит мутацию: исход снова литерал «killed» (или читается не из
        состояния задачи) — в ретроспективе снимка появится «Итог: killed»
        со строкой «причина:», и `assertNotIn` ниже покраснеет.
        """
        self.publish("done")

        retro_text = self.origin_show(RETRO_REL)

        self.assertRegex(retro_text, r"Итог: done, sha [0-9a-f]{40}\n")
        self.assertNotIn("Итог: killed", retro_text)
        self.assertNotIn("причина:", retro_text)

    def test_merged_task_snapshot_addresses_the_artifact_ref(self):
        """AC-2: строка адреса ретроспективы снимка смерженной задачи —
        `refs/artifacts/<id>`, а не «артефакты не сохранены».

        Ловит мутацию: адрес снимка снова собирается прежним путём
        (контент-адресный `<sha>:tasks/<id>/` из `docs/retro/<id>.md` или
        killed-строка `NO_ARTIFACTS_NOTE`) — `assertIn` строки по ссылке
        покраснеет.
        """
        self.publish("done")

        retro_text = self.origin_show(RETRO_REL)

        self.assertIn(f"Адрес артефактов: refs/artifacts/{TASK}\n", retro_text)
        self.assertNotIn("артефакты не сохранены", retro_text)

    def test_merged_task_snapshot_commit_message_names_done(self):
        """AC-4: сообщение коммита закрытия называет фактический исход —
        «закрытие (done) — RETRO» (ADR-0021 п.3: коммит закрытия вместо
        снимка).

        Ловит мутацию: в сообщение коммита снова уходит «killed» —
        `assertEqual` ниже покраснеет на подстроке исхода.
        """
        self.publish("done")

        self.assertEqual(self.origin_commit_subject(),
                         f"{TASK}: закрытие (done) — RETRO")

    def test_killed_task_snapshot_keeps_reason_and_old_address(self):
        """AC-3: путь `kill` не изменился — «Итог: killed — причина:
        <последняя причина из журнала>» и прежняя строка адреса; сообщение
        коммита называет `killed`.

        Ловит мутацию: исход стал вычисляться «всё, что не kill, — done»
        (или строка причины/адреса поехала вместе с правкой done-пути) —
        покраснеет один из `assertIn` ниже.
        """
        note = self.publish("killed")

        retro_text = self.origin_show(RETRO_REL)

        self.assertIn("Итог: killed — причина: kill switch", retro_text)
        self.assertIn("Адрес артефактов: артефакты не сохранены", retro_text)
        self.assertEqual(self.origin_commit_subject(),
                         f"{TASK}: закрытие (killed) — RETRO")
        self.assertIn("коммит закрытия", note)
        self.assertNotIn("не записан", note)

    def test_snapshot_retro_counts_and_gist_come_from_the_branch(self):
        """AC-5/AC-10: каталога задачи в главной копии нет, а ветка несёт
        планку и SPEC — ретроспектива СНИМКА несёт числа планки и «Суть» с
        первым предложением «Контекста».

        Ловит мутацию: ретроспектива снимка снова считает по
        `config.TASKS/<id>` — в опубликованном файле окажется «0 тест(ов),
        0 manual, 0 skip» и «Суть» из одного названия задачи, и оба
        `assertIn` ниже покраснеют.
        """
        self.assertFalse((config.TASKS / TASK).exists())

        self.publish("done")

        retro_text = self.origin_show(RETRO_REL)

        self.assertIn(COUNTS_LINE, retro_text)
        self.assertIn(GIST_LINE, retro_text)

    def test_canary_run_publishes_no_snapshot(self):
        """ADR-0021 п.13 (вместо AC-9 SPEC 01M3KE80RNBCY9G48E75Z14TA7):
        канареечная задача закрывается тем же потоком — коммит RETRO
        ложится в её ссылку документов и доходит до origin.

        Ловит мутацию: прежнее исключение канарейки оставлено в узле
        закрытия — RETRO в ссылке не появится, и `origin_show` ниже
        покраснеет.
        """
        self.publish("done", is_canary=True)

        self.assertTrue(self.origin_ref_exists())
        self.assertIn("Итог: done", self.origin_show(RETRO_REL))

    def test_published_snapshot_removes_the_artifact_branch(self):
        """ADR-0021 п.3 (вместо требования 8/AC-8 SPEC T094): закрытие —
        коммит поверх прежней головы ссылки, ссылка не удаляется и в
        origin совпадает с локальной; прежний коммит документов достижим
        из головы.

        Ловит мутацию: закрытие снова пишет коммит без родителя (снимок)
        или удаляет ссылку — `is_ancestor` прежней головы либо наличие
        ссылки ниже покраснеют.
        """
        before = artifact_branch.ref_head(TASK)

        self.publish("done")

        head = artifact_branch.ref_head(TASK)
        self.assertTrue(self.origin_ref_exists())
        self.assertNotEqual(head, before)
        self.assertTrue(gitcmd.is_ancestor(before, head))
        self.assertEqual(gitcmd.remote_ref_state(self.ref()), (head, ""))


if __name__ == "__main__":
    unittest.main()
