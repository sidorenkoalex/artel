"""AC-6 (SPEC.md): если заведённая канареечная задача переходит в
состояние `escalated`, механика прогона отвечает синтетическим
ANSWER-ответом Оператора (заглушкой), и задача возвращается в работу
без остановки прогона и без участия живого Оператора.

Наблюдение — ТОЛЬКО через снимок эфемерного клона, снятый ДО его
удаления (`_sandbox.py::_EphemeralDirTracker(deep=True)`): по AC-2/AC-3
весь цикл задачи, включая её артефактную ветку и БД состояния, живёт
внутри клона, которого после прогона (AC-4) больше нет — снаружи (в
`self.root`/`config.DB` этой песочницы) исход эскалации не увидеть в
принципе, это не обходной приём теста, а прямое следствие остальных
критериев этой же задачи.

`SmartAgent` этой песочницы эскалирует РОВНО те задачи, чей заголовок
(= имя файла шаблона пула, `f.stem`, тем же приёмом что и v1) несёт
`_sandbox.ESCALATE_TITLE_MARKER` — коммитит `QUESTIONS.md` вместо
готового `SPEC.md` на `spec_writing`, тем же документом и тем же
эффектом, что `tests/test_answer.py::_ArtifactBranchAnswerTest.
_escalate()` (см. докстринг `_sandbox.py`).

Красен до реализации: `canary --k` падает на разборе аргументов — эфемерных клонов не заводится вовсе, `git_like_snapshots()` пуст, первая содержательная проверка (наличие снимка клона) падает `AssertionError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox, ESCALATE_TITLE_MARKER, \
    _EphemeralDirTracker  # noqa: E402

POOL_TEMPLATES = {
    f"{ESCALATE_TITLE_MARKER}-case.md":
        "Синтетическая канареечная правка, вызывающая батч вопросов.",
}


class EscalationSyntheticAnswerTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.tracker = _EphemeralDirTracker()
        self.tracker.start(self, deep=True)

    def test_ac6_escalated_task_gets_a_synthetic_answer_and_the_run_continues(self):
        """Единственная задача пула (k=1) устроена так, что на
        `spec_writing` роль-заглушка кладёт `QUESTIONS.md` вместо
        готового `SPEC.md` — обычный (не канареечный) `fsm.cmd_advance`
        по такому артефакту переводит задачу в `escalated`
        (`tests/test_answer.py::_ArtifactBranchAnswerTest._escalate()`
        — тот же самый эффект). Требование 6 обязывает механику прогона
        заметить это САМА (без участия живого Оператора) и продолжить
        задачу дальше синтетическим ANSWER.

        Проверяется по снимку клона, снятому ДО его удаления: (1)
        журнал задачи внутри клона несёт переход `state -> escalated`
        (эскалация действительно случилась — не тавтология «просто
        дошло до конца»); (2) в артефактную ветку клона закоммичен
        файл `tasks/<id>/ANSWER-1.md`; (3) итоговое состояние задачи —
        НЕ `escalated` (прогон не встал, увёл её дальше своим циклом).

        Ловит мутацию: разработчик копирует `_drive_task` v1 буквально
        (`orchestrator/canary.py`, где эскалация — терминальный выход
        из цикла, «canary дальше не ведёт», см. докстринг функции) не
        добавляя ветку авто-ответа — тогда финальное состояние задачи
        в БД клона так и останется `escalated`, а `ANSWER-1.md` в
        журнале коммитов клона не появится вовсе.
        """
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)

        clones = self.tracker.git_like_snapshots()
        self.assertGreaterEqual(
            len(clones), 1,
            f"прогон не завёл ни одного эфемерного клона: "
            f"{self.tracker.snapshots}")

        matches = [s for s in clones
                  if any(ESCALATE_TITLE_MARKER in (t.get("title") or "")
                        for t in s.get("tasks", []))]
        self.assertEqual(
            len(matches), 1,
            f"не найден ровно один клон с нашей эскалируемой задачей "
            f"среди {len(clones)} перехваченных: {clones}")
        snap = matches[0]
        task_row = next(t for t in snap["tasks"]
                        if ESCALATE_TITLE_MARKER in (t.get("title") or ""))
        task_id = task_row["id"]
        steps = snap["steps_by_task"].get(task_id, [])

        escalated_transitions = [r for r in steps
                                 if r.get("action") == "state -> escalated"]
        self.assertTrue(
            escalated_transitions,
            f"задача {task_id} ни разу не переходила в escalated — "
            f"сценарий теста не воспроизвёлся, журнал: {steps}")

        answer_files = snap.get("answer_files", [])
        self.assertTrue(
            any(f"tasks/{task_id}/ANSWER-" in f for f in answer_files),
            f"в артефактную ветку клона не закоммичен ни один "
            f"ANSWER-*.md для {task_id}: {answer_files}")

        self.assertNotEqual(
            task_row["state"], "escalated",
            f"задача {task_id} осталась в escalated до конца прогона — "
            f"механика не увела её дальше синтетическим ответом")


if __name__ == "__main__":
    unittest.main()
