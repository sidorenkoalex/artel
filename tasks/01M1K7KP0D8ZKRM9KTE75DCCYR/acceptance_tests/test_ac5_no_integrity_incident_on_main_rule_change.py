"""AC-5 (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md): смена содержимого
скила или CLAUDE.md в `main` между двумя шагами (срезами) одной и той же
задачи, уже прошедшими через WIP-чекпоинты, не порождает инцидент
целостности (`fixation.check_integrity`) на следующем шаге этой задачи —
правила системы не являются планкой задачи (`tasks.fixed_sha` фиксирует
голову ВЕТКИ ЗАДАЧИ + чистоту `tasks/<id>`, не содержимое скилов/
CLAUDE.md).

Зелёный с рождения: `fixation.check_integrity`/`fixation._fix_dogfood`
(см. `orchestrator/fixation.py`) сегодня вообще не читают `skills/*.md`
ни `CLAUDE.md` — сверяют только sha головы ветки задачи и чистоту
`tasks/<id>/` (SPEC «Не входит»: эта задача не трогает `fixation.py`).
Смена main-компонента поэтому не может повлиять на результат
`check_integrity` уже сегодня; тест — регрессионная защита от
возможной будущей ошибки (например, попытки «удобно» завязать
свежесть брифа на hash-фиксацию), а не документирование факта, что
задача что-то чинит здесь.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import TaskSandbox, claude_md_marker, skill_marker  # noqa: E402
from orchestrator import checkpoint, fixation, store, workspace  # noqa: E402


class NoIntegrityIncidentOnMainRuleChangeTest(TaskSandbox):

    def test_ac5_skill_and_claude_md_change_in_main_between_wip_checkpoints_does_not_flag_incident(self):
        """Два «среза» одной задачи, разделённых WIP-чекпоинтом
        (`checkpoint.commit_timeout_checkpoint` — тот же механизм, что
        реально коммитит недописанный шаг агента при таймауте, SPEC
        T041): между ними `main` продвигает и скил, и CLAUDE.md.
        Следующий `fixation.check_integrity` этой же задачи обязан
        остаться None.

        Ловит мутацию: если будущая реализация AC-1/AC-2/AC-4 (по ошибке
        или «для удобства») подмешивает hash скила/CLAUDE.md в
        `tasks.fixed_sha`/сверку `check_integrity`, смена main-компонента
        между срезами станет видна как «расхождение sha» и уведёт задачу
        в escalated — тест поймает это как непустую причину отказа
        вместо None.
        """
        conn = store.db()
        store.record_fixation(conn, self.TASK)
        fixed_after_first_step = store.get_task(conn, self.TASK)["fixed_sha"]
        self.assertTrue(
            fixed_after_first_step,
            "подготовка теста: первая фиксация обязана дать непустой sha")

        # WIP-чекпоинт первого («прерванного») среза — та же механика,
        # что таймаут реального шага. Артефакт WIP.md — в артефактную
        # ветку (ANSWER-2 к эскалации этой задачи: `tasks/<id>/`
        # self-таргета после A7 живёт ТОЛЬКО там, `artifact_source.
        # resolve` — `foreign=True` безусловно; прямая запись в ветку/
        # worktree кода устарела). `commit_timeout_checkpoint` чекпоинтит
        # рабочее дерево КОДОВОЙ ветки (`workspace.path`) — та после A7
        # заводится лениво первым шагом роли (`workspace.ensure`,
        # `runner.role_cwd`, T045), не самим `cmd_new` (раньше worktree
        # существовал сразу, отсюда и была возможна прямая запись без
        # заведения) — здесь заводится тем же способом, а незакоммиченный
        # след кладётся ПРЯМО В НЕЁ (не под `tasks/<id>/` — та ветка этот
        # путь больше не несёт вовсе), чтобы самому механизму чекпоинта
        # было что закоммитить.
        self.write_and_commit_in_worktree(
            "WIP.md", "недописанный след первого среза\n",
            "WIP.md от test_author (артефактная ветка)")
        branch = store.get_task(conn, self.TASK)["branch"]
        wt, err = workspace.ensure(self.TASK, branch)
        self.assertIsNone(
            err, f"подготовка теста: worktree обязан завестись: {err}")
        (wt / "WIP-code.md").write_text(
            "недописанный код первого среза\n", encoding="utf-8")
        checkpoint_detail = checkpoint.commit_timeout_checkpoint(
            conn, self.TASK, "test_author")
        self.assertTrue(
            checkpoint_detail,
            "подготовка теста: WIP-чекпоинт обязан реально закоммититься")

        reason_right_after_checkpoint = fixation.check_integrity(
            conn, self.TASK)
        self.assertIsNone(
            reason_right_after_checkpoint,
            "подготовка теста: сам WIP-чекпоинт не должен быть инцидентом "
            "— он перефиксируется тем же действием (docstring "
            "checkpoint.commit_timeout_checkpoint)")

        # Между срезами main продвигает и скил, и CLAUDE.md — ветка
        # задачи при этом не трогается вовсе.
        self.write_and_commit("skills/test-authoring.md",
                              skill_marker("test-authoring", "V2"),
                              "main: скил test-authoring -> V2")
        self.write_and_commit("CLAUDE.md", claude_md_marker("V2"),
                              "main: CLAUDE.md -> V2")

        reason_before_next_step = fixation.check_integrity(conn, self.TASK)

        self.assertIsNone(
            reason_before_next_step,
            "смена содержимого скила/CLAUDE.md в main между срезами "
            "задачи не должна порождать инцидент целостности следующего "
            "шага (SPEC AC-5) — правила системы не являются планкой "
            f"задачи; фактическая причина: {reason_before_next_step!r}")


if __name__ == "__main__":
    unittest.main()
