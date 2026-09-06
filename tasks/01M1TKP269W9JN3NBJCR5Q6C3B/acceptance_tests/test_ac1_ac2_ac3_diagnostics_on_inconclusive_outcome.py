"""AC-1/AC-2/AC-3 (SPEC.md): диагностика незелёного исхода канареечной
задачи сохраняется в `.artel/canary/<run_stamp>/<task_id>/` пульта ДО
удаления эфемерного клона:

AC-1. Журнал задачи (`steps`) текстом.
AC-2. Логи ролей клона (`.artel/logs/<task_id>-*.log`).
AC-3. Последние PLAN.md/REVIEW.md из артефактной ветки клона, если они
там есть; их отсутствие в клоне не приводит к отказу команды `canary`.

Сценарий «не сошлась» (`InconclusiveReviewLoopTest`): ревью один раз
просит доработку (`changes_requested`) — задача возвращается в `in_dev`
С РЕАЛЬНЫМ артефактом (PLAN.md/REVIEW.md уже существуют в артефактной
ветке клона, AC-3), но КАЖДЫЙ следующий вход в `in_dev`
(`_sandbox._EscalatesOnReworkAgent`) эскалирует по-настоящему (`PLAN.md
status: escalate`, `orchestrator/fsm_advance.py`) — синтетический
ANSWER canary возвращает в `in_dev`, разработчик эскалирует снова:
ГЕНУИННЫЙ бесконечный цикл эскалаций, оборванный настоящим исчерпанием
`config.CANARY_MAX_ESCALATION_CYCLES` (`canary._drive_task`), а не
имитацией стагнации через отсутствующее журналирование. Исход `killed`,
заведомо НЕ «штатно» (`canary._kill_outcome_note` вернёт «не сошлась: …»,
never «штатно») при любом прочтении границы «done»/«штатный исход» из
ANSWER-1.md — тесты этого файла не зависят от той трактовки.

(Историческая заметка: до фиксации `_sandbox.py` — расширение 2
докстринга модуля — этот же сценарий имитировал «не сошлась» побочным
эффектом отсутствующего у `SmartAgent` журналирования `agent run
finished`: pre-advance rework-гейт («регрессия №13»,
`orchestrator/auto.py::_role_step_since_state_entry`) держал бы
предварительный `advance` НАВСЕГДА уже на первом входе в `in_dev`, а не
только на возврате после доработки, и задача убивалась бы `_kill_
inconclusive` («3 прохода без прогресса», `config.CANARY_MAX_STALL_
ITERS`) до единого визита в `review` — `REVIEW.md` в артефактной ветке
клона не появлялся бы вовсе, что молча ломало бы AC-3 этого же файла.
После починки сандбокса «штатный» исход (`merge_gate`) стал достижим
(нужен `test_ac4_ac7_normal_outcome_baseline_and_diagnostics.py`), и
старый сценарий пришлось заменить на генуинный цикл эскалаций выше.)

Красен до реализации: `.artel/canary/<run_stamp>/<task_id>/` после
прогона не существует вовсе (код диагностики ещё не написан) —
`assertTrue(diag_dir.is_dir())` падает первым.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (CanarySandbox, _EscalatesOnReworkAgent,  # noqa: E402
                      _NeverSpecsAgent, ROLE_LOG_MARKER, extract_run_stamp,
                      extract_task_ids)

TITLE_NEVER_APPROVED = "nikogda-ne-odobrennaya-pravka"
TITLE_NEVER_SPECCED = "nikogda-ne-specennaya-pravka"


class InconclusiveReviewLoopTest(CanarySandbox):
    """Общий сценарий для AC-1/AC-2/AC-3 (presence-половина): один
    канареечный прогон, ревью которого запрашивает доработку один раз,
    после чего разработчик эскалирует на каждом следующем входе в
    `in_dev` (см. докстринг модуля) — задача убивается «не сошлась»
    генуинным исчерпанием лимита эскалаций, пройдя через `in_dev`
    (PLAN.md) и `review` (REVIEW.md) хотя бы по разу до убийства."""

    AGENT_CLASS = _EscalatesOnReworkAgent

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NEVER_APPROVED}.md":
                "Синтетическая правка, ревью которой никогда не "
                "одобряется.",
        })
        # Одного запроса доработки достаточно — `_EscalatesOnReworkAgent`
        # эскалирует на КАЖДОМ следующем входе в in_dev независимо от
        # того, сколько ещё раундов «нужно было бы» пройти по замыслу
        # шаблона (см. докстринг модуля); нуль означал бы мгновенное
        # «approved» без единого changes_requested вовсе — REVIEW.md
        # никогда не появился бы (AC-3 нечего было бы проверять).
        self.agent.extra_review_rounds_default = 1

    def _run_and_get_diag_dir(self):
        out = self.run_canary_pool(1)
        self.assertNotIn("[SystemExit]", out, out)
        run_stamp = extract_run_stamp(out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        task_id = task_ids[0]
        diag_dir = self.root / ".artel" / "canary" / run_stamp / task_id
        return out, task_id, diag_dir

    def _diag_texts(self, diag_dir: Path) -> str:
        return "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(diag_dir.rglob("*")) if p.is_file())

    def test_ac1_task_journal_saved_as_text(self):
        """Диагностика несёт журнал задачи (`steps`) целиком, не только
        последнюю строку — узнаваемая причина «не сошлась»
        (`_kill_inconclusive`'s жалоба на повторные эскалации подряд) и
        несколько разных переходов состояний присутствуют текстом в
        сохранённых файлах.

        Ловит мутацию: разработчик сохраняет только последнюю строку
        журнала (например, финальный `state -> killed`) вместо полного
        `store.task_steps` — узнаваемая причина «повторных эскалаций
        подряд» (журналируется ДО финального перехода в killed, см.
        `canary._kill_inconclusive`) в сохранённом файле не найдётся.
        """
        out, task_id, diag_dir = self._run_and_get_diag_dir()
        self.assertTrue(
            diag_dir.is_dir(),
            f"диагностика не сохранена: {diag_dir} не существует\n{out}")

        combined = self._diag_texts(diag_dir)
        self.assertIn(
            "повторных эскалаций подряд", combined,
            f"журнал задачи в диагностике не несёт причину «не сошлась»: "
            f"{combined!r}")
        self.assertGreaterEqual(
            combined.count("state ->"), 2,
            f"сохранённый журнал похож на одну строку, а не на полный "
            f"журнал переходов задачи: {combined!r}")

    def test_ac2_role_logs_of_the_clone_are_copied(self):
        """Диагностика несёт файл(ы) `<task_id>-*.log`, скопированные из
        `.artel/logs/` клона до его удаления — с реальным содержимым
        (узнаваемый маркер, который писала бы роль), не пустышку.

        Ловит мутацию: разработчик копирует журнал БД (AC-1), но
        забывает скопировать `.artel/logs/` клона — под `diag_dir` не
        найдётся ни одного файла `*.log`, либо найдётся, но без
        маркерного содержимого (пустой файл вместо реальной копии).
        """
        out, task_id, diag_dir = self._run_and_get_diag_dir()
        self.assertTrue(diag_dir.is_dir(), out)

        log_files = [p for p in diag_dir.rglob(f"{task_id}-*.log")]
        self.assertTrue(
            log_files,
            f"под {diag_dir} нет ни одного файла логов роли "
            f"{task_id}-*.log")
        combined = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                            for p in log_files)
        self.assertIn(
            ROLE_LOG_MARKER, combined,
            f"скопированные файлы логов не несут реального содержимого "
            f"лога роли: {combined!r}")

    def test_ac3_last_plan_and_review_are_copied_when_present(self):
        """Диагностика несёт последние PLAN.md/REVIEW.md из артефактной
        ветки клона — задача этого сценария проходит через `in_dev`
        (PLAN.md коммитится) и `review` (REVIEW.md коммитится с
        вердиктом `changes_requested`) хотя бы по разу до убийства.

        Ловит мутацию: разработчик сохраняет журнал/логи (AC-1/AC-2), но
        не читает артефактную ветку клона вовсе — ни PLAN.md, ни
        REVIEW.md под `diag_dir` не найдётся, хотя оба реально
        существуют в клоне на момент убийства задачи.
        """
        out, task_id, diag_dir = self._run_and_get_diag_dir()
        self.assertTrue(diag_dir.is_dir(), out)

        combined = self._diag_texts(diag_dir)
        self.assertIn(
            "# PLAN: канареечная задача", combined,
            f"диагностика не несёт содержимое PLAN.md артефактной ветки "
            f"клона: {combined!r}")
        self.assertIn(
            "# REVIEW: канареечная задача", combined,
            f"диагностика не несёт содержимое REVIEW.md артефактной "
            f"ветки клона: {combined!r}")


class InconclusiveWithoutSpecTest(CanarySandbox):
    """AC-3, вторая половина: PLAN.md/REVIEW.md никогда не появляются в
    артефактной ветке клона (задача убита «не сошлась» ещё на
    `spec_writing`, раньше готового SPEC.md) — команда `canary` не
    отказывает и не падает из-за их отсутствия."""

    AGENT_CLASS = _NeverSpecsAgent

    def setUp(self):
        super().setUp()
        self.write_pool_templates({
            f"{TITLE_NEVER_SPECCED}.md":
                "Синтетическая правка, SPEC которой никогда не готов.",
        })

    def test_ac3_missing_plan_and_review_do_not_fail_the_command(self):
        """`_NeverSpecsAgent` всегда отвечает батчем вопросов на
        `spec_writing` — задача эскалируется, возвращается синтетическим
        ANSWER обратно в `spec_writing`, и тот же rework-гейт (см.
        докстринг модуля), что держит повторный вход в `in_dev`, здесь
        держит повторный вход в `spec_writing` — три холостых прохода
        без прогресса убивают задачу «не сошлась», НИ РАЗУ не дойдя до
        `in_dev`/`review`: в клоне нет ни PLAN.md, ни REVIEW.md ни на
        одной из веток. Диагностика всё равно сохраняется (журнал/логи
        есть всегда), команда не падает `SystemExit`/трейсбеком.

        Ловит мутацию: разработчик читает PLAN.md/REVIEW.md артефактной
        ветки клона безусловно (например, `.read_text()` без обработки
        отсутствия файла) — здесь оба гарантированно отсутствуют, и
        такая реализация уронила бы весь прогон исключением вместо
        штатного «нечего копировать».
        """
        out = self.run_canary_pool(1)

        self.assertNotIn("[SystemExit]", out, out)
        self.assertNotIn("Traceback", out, out)

        run_stamp = extract_run_stamp(out)
        task_ids = extract_task_ids(out)
        self.assertEqual(len(task_ids), 1, out)
        diag_dir = self.root / ".artel" / "canary" / run_stamp / task_ids[0]
        self.assertTrue(
            diag_dir.is_dir(),
            f"диагностика не сохранена несмотря на отсутствие PLAN/"
            f"REVIEW: {diag_dir} не существует\n{out}")


if __name__ == "__main__":
    unittest.main()
