"""Бриф аудитора без возвратов с гейта SPEC и бриф аналитика — прежние побайтно; правило скила аудитора — приложением PLAN.

Группа: разовый
Красен до реализации: AC-5 и AC-6 зелены с рождения (бриф без раздела и бриф аналитика на main собираются ровно из этих функций компонентов — тест держит неизменность), красен до реализации только AC-7: PLAN.md с приложением `skills/spec-audit.md` ещё не написан разработчиком — `artifact_text("PLAN.md")` отдаёт None.

Разовый, потому что сверяет с УСТРОЙСТВОМ main на момент задачи: оракул
AC-5/AC-6 — закрытые функции сборки компонентов `orchestrator/brief.py`
(`_return_reason_component`, `_manifest_component`, `_journal_component`,
`_questions_component`, `_answer_component`, `_fresh_map_text_and_note`,
`_artifact_source_branch`), названные в самих критериях, и порядок
компонентов на main; AC-7 — содержимое PLAN.md этой задачи. После мержа
сверять это не на чем.

Песочница — `tests.sandbox.LightTransitionSandbox` (документы задачи с
диска песочницы, git заглушён, карта — фикстура со свежим `built_at_sha`).
Идентификатор прогона брифа фиксирован подменой `brief.new_run_id` —
бриф и оракул собираются при одном и том же id. Переходы журнала —
настоящими командами (`fsm.cmd_reject` на `spec_gate`, выход аудита по
fail `advance_gates.spec_audit.leave`) и `store.set_state` для прочих.
Метки и выбор вариантов — из `random`, зерно печатается и входит в текст
провала.
"""
import contextlib
import io
import random
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import (brief, config, context_package, fsm,  # noqa: E402
                          store)
from orchestrator.advance_gates import spec_audit as audit_gate  # noqa: E402
from scripts import codebase_map, guard  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

SECTION_TITLE = "Решения Оператора на гейте SPEC"
LABEL_STEM = "Решение Оператора на гейте SPEC"
GATE_PREFIX = "возврат из spec_gate: "
RU = "абвгдежзиклмнопрстуфхцчшэюя"
SKILL = "skills/spec-audit.md"
RULE = (
    "Решение Оператора из раздела «Решения Оператора на гейте SPEC» имеет "
    "силу ANSWER-n по содержанию SPEC: отклонение, которое оно прямо "
    "снимает, не поднимается. Мандаты (ослабление тестов, расширение зон, "
    "зависимости мержа) раздел не создаёт: без строки мандата в ANSWER-n "
    "отсутствие мандата остаётся отклонением. Расхождение между решениями "
    "Оператора — пункт вердикта concerns.")


class BriefOracleSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.run_id = "%032x" % self.rng.getrandbits(128)
        patcher = mock.patch.object(brief, "new_run_id",
                                    return_value=self.run_id)
        patcher.start()
        self.addCleanup(patcher.stop)
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "codebase-map.md").write_text(
            f"---\nbuilt_at_sha: {'a' * 40}\n---\n\n# Карта {self.word()}\n\n"
            f"## orchestrator/x.py\n\nМодуль.\n\n## tests/test_x.py\n\nТест.\n",
            encoding="utf-8")
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            f"# SPEC {self.word()}\n\nAC-1. Критерий.\n", encoding="utf-8")
        self.conn = store.db()

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def word(self, length: int = 8) -> str:
        return "".join(self.rng.choice(RU) for _ in range(length))

    def state_of(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def move(self, state: str, actor: str = "fsm", detail: str = "") -> None:
        store.set_state(store.db(), self.TASK, state, actor,
                        expected_state=self.state_of(), detail=detail)

    def quiet(self, fn, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            return fn(*args)

    def gate_reject(self, reason: str) -> None:
        self.move("spec_audit", detail="SPEC готов — аудит")
        self.move("spec_gate", detail="аудит SPEC: вердикт pass — SPEC ждёт approve")
        self.quiet(fsm.cmd_reject, self.TASK, reason)
        self.assertEqual(self.state_of(), "spec_writing", self.msg("reject"))

    def fail_return(self) -> None:
        self.move("spec_audit", detail="SPEC готов — аудит")
        audit = (f"---\ntask: {self.TASK}\ntype: spec_audit\nverdict: fail\n"
                 f"---\n\n# SPEC-AUDIT\n\n## Вердикт\n\nОтклонение: "
                 f"{GATE_PREFIX}{self.word()}.\n")
        with mock.patch.object(config, "SPEC_AUDIT_FAIL_RETURNS", 1000):
            self.quiet(audit_gate.leave, store.db(), self.TASK, "spec_audit",
                       "fail", audit)
        self.assertEqual(self.state_of(), "spec_writing", self.msg("fail"))

    def write_answers(self, count: int) -> None:
        for n in range(1, count + 1):
            (self.tdir / f"ANSWER-{n}.md").write_text(
                f"# ANSWER-{n}\n\nОтвет {self.word()}.\n", encoding="utf-8")

    def assert_no_section(self, text: str) -> None:
        self.assertNotIn(SECTION_TITLE, text, self.msg(text[:4000]))
        self.assertNotIn(LABEL_STEM, text, self.msg(text[:4000]))


# ---------------------------------------------------------------- AC-5

class AuditorBriefWithoutGateReturnsTest(BriefOracleSandbox):

    def test_ac5_auditor_brief_without_gate_returns_equals_main_components(self):
        """Бриф аудитора задачи без возвратов с гейта SPEC — побайтно сборка из функций компонентов main.

        Сценарий: задача без единого reject на spec_gate; случайно с ТЗ или
        без, с 0-3 ANSWER-n, с 0-2 fail-возвратами аудитора (их текст несёт
        «возврат из spec_gate: »), визит `spec_audit` случайно начат
        возвратом из эскалации (тогда в брифе раздел «Причина возврата»)
        или обычным входом из `spec_writing`. Бриф `spec_auditor_brief` не
        несёт ни заголовка раздела, ни метки «Решение Оператора на гейте
        SPEC», и побайтно равен `mark_unclosed_parts(text, run_id,
        num_parts)` при `text, num_parts = context_package.discipline(
        [HEADER, BOUNDARY_INSTRUCTION, *компоненты])`, где компоненты —
        причина возврата визита, TZ, SPEC, ANSWER-n по номеру, карта (её
        пометка + `MAP_PROJECTION_NOTE` + `_manifest_component` проекции),
        собранные функциями компонентов при том же run_id.

        Ловит мутацию: раздел решений вставляется и при пустом списке
        (пустой заголовок); компонент переставлен (ANSWER после карты,
        причина возврата не первой) или пропал; fail-возврат аудитора
        принят за решение Оператора.
        """
        with_tz = self.rng.random() < 0.7
        if with_tz:
            (self.tdir / "TZ.md").write_text(f"# ТЗ {self.word()}\n",
                                             encoding="utf-8")
        answers = self.rng.randint(0, 3)
        self.write_answers(answers)
        for _ in range(self.rng.randint(0, 2)):
            self.fail_return()
        escalation = self.rng.random() < 0.5
        if escalation:
            self.move("spec_audit", detail="SPEC готов — аудит")
            self.move("escalated", detail=f"эскалация аудитора {self.word()}")
            self.move("spec_audit", actor="operator",
                      detail="эскалация разрешена, продолжаем")
        else:
            self.move("spec_audit", detail="SPEC готов — аудит")

        text = self.quiet(brief.spec_auditor_brief, self.conn, self.TASK)
        expected = self.oracle()
        context = self.msg(f"ТЗ={with_tz}, ANSWER={answers}, "
                           f"эскалация={escalation}")
        self.assert_no_section(text)
        if escalation:
            self.assertIn(brief.RETURN_REASON_HEADER, expected, context)
        self.assertEqual(text, expected, context)

    def oracle(self) -> str:
        conn, task, role, run_id = self.conn, self.TASK, "spec_auditor", self.run_id
        branch, foreign = brief._artifact_source_branch(conn, task)
        parts = []
        reason = brief._return_reason_component(
            conn, task, role, "spec_audit", branch, foreign, run_id,
            render=brief._manifest_component)
        if reason:
            parts.append(reason)
        tz = self.tdir / "TZ.md"
        if tz.exists():
            parts.append(brief._manifest_component(
                conn, task, role, f"tasks/{task}/TZ.md",
                tz.read_text(encoding="utf-8"), run_id))
        parts.append(brief._manifest_component(
            conn, task, role, f"tasks/{task}/SPEC.md",
            (self.tdir / "SPEC.md").read_text(encoding="utf-8"), run_id))
        numbered = sorted(int(p.name[len("ANSWER-"):-len(".md")])
                          for p in self.tdir.glob("ANSWER-*.md"))
        for n in numbered:
            parts.append(brief._manifest_component(
                conn, task, role, f"tasks/{task}/ANSWER-{n}.md",
                (self.tdir / f"ANSWER-{n}.md").read_text(encoding="utf-8"),
                run_id))
        map_text, map_note = self.quiet(brief._fresh_map_text_and_note,
                                        conn, task)
        parts.append(map_note + brief.MAP_PROJECTION_NOTE
                     + brief._manifest_component(
                         conn, task, role, brief.MAP_PROJECTION_LABEL,
                         codebase_map.project_for_brief(map_text), run_id))
        text, num_parts = context_package.discipline(
            [brief.HEADER, brief.BOUNDARY_INSTRUCTION, *parts])
        return brief.mark_unclosed_parts(text, run_id, num_parts)


# ---------------------------------------------------------------- AC-6

class AnalystBriefUnchangedTest(BriefOracleSandbox):

    def test_ac6_analyst_brief_with_gate_return_equals_main_components(self):
        """Бриф аналитика задачи с возвратом на spec_gate — без раздела решений, побайтно сборка main.

        Сценарий: 0-1 fail-возврат аудитора, затем 1-3 настоящих reject на
        spec_gate (последний начинает визит `spec_writing`, в брифе —
        «Причина возврата»); случайно есть QUESTIONS.md и 0-2 ANSWER-n.
        `analyst_map_component` не несёт ни заголовка раздела, ни метки
        «Решение Оператора на гейте SPEC», и побайтно равен
        `f"{HEADER}\\n\\n{BOUNDARY_INSTRUCTION}\\n" + "\\n".join(компоненты)`:
        причина возврата (`_return_reason_component`), карта
        (`MAP_PROJECTION_NOTE + _journal_component(... MAP_PROJECTION_LABEL,
        project_for_brief(fresh_map_text(...)) ...)`), QUESTIONS
        (`_questions_component`), ANSWER (`_answer_component`) — при том же
        run_id, пустые пропущены.

        Ловит мутацию: раздел решений добавлен и в бриф аналитика (общий
        сборщик возвратов для обеих ролей); причина возврата аналитика
        стала сводкой всех reject; компонент переставлен или пропал.
        """
        if self.rng.random() < 0.5:
            self.fail_return()
        for _ in range(self.rng.randint(1, 3)):
            self.gate_reject(f"Причина {self.word()}: «{self.word()}».")
        if self.rng.random() < 0.5:
            (self.tdir / "QUESTIONS.md").write_text(
                f"# QUESTIONS\n\n1. Вопрос {self.word()}?\n", encoding="utf-8")
        self.write_answers(self.rng.randint(0, 2))

        text = self.quiet(brief.analyst_map_component, self.conn, self.TASK)
        expected = self.oracle()
        self.assert_no_section(text)
        self.assertIn(brief.RETURN_REASON_HEADER, expected, self.msg("оракул"))
        self.assertEqual(text, expected, self.msg("бриф аналитика"))

    def oracle(self) -> str:
        conn, task, run_id = self.conn, self.TASK, self.run_id
        branch, foreign = brief._artifact_source_branch(conn, task)
        map_text = codebase_map.project_for_brief(
            self.quiet(brief.fresh_map_text, conn, task))
        parts = []
        reason = brief._return_reason_component(
            conn, task, "analyst", "spec_writing", branch, foreign, run_id)
        if reason:
            parts.append(reason)
        parts.append(brief.MAP_PROJECTION_NOTE + brief._journal_component(
            conn, task, "analyst", brief.MAP_PROJECTION_LABEL, map_text, run_id))
        questions = brief._questions_component(conn, task, "analyst", branch,
                                               foreign, run_id)
        if questions:
            parts.append(questions)
        answer = brief._answer_component(conn, task, "analyst", branch,
                                         foreign, run_id)
        if answer:
            parts.append(answer)
        return (f"{brief.HEADER}\n\n{brief.BOUNDARY_INSTRUCTION}\n"
                + "\n".join(parts))


# ---------------------------------------------------------------- AC-7

def normalized(text: str) -> str:
    """Пробелы и переносы строк схлопнуты, markdown-выделение (`*`, `_`,
    обратные кавычки) снято: перенос абзаца по строкам и выделение слов —
    оформление, не текст правила."""
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", text)).strip()


class SkillRuleAppendixTest(unittest.TestCase):

    def test_ac7_plan_appendix_adds_rule_to_spec_audit_skill(self):
        """Приложение PLAN к `skills/spec-audit.md` применимо к HEAD и вносит правило требования 5 дословно.

        Сценарий: PLAN.md задачи из ссылки документов (`artifact_text`)
        разбирается тем же разбором приложений, что пульт
        (`guard.plan_appendices`); среди приложений есть блок с путём
        `skills/spec-audit.md`; `apply_check` блока к дереву HEAD рабочей
        копии согласен (либо обратное наложение согласно — правка уже в
        дереве); добавленные блоком строки (`+`) несут правило требования 5
        дословно — с точностью до переносов строк и markdown-выделения.

        Ловит мутацию: приложения нет или оно по другому файлу; хедер хунка
        не совпадает с файлом (git apply --check отказывает в обе
        стороны); правило пересказано своими словами или урезано (нет
        фразы про мандаты либо про concerns).
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи в ссылке документов нет")
        appendices, _errors = guard.plan_appendices(plan)
        mine = [a for a in appendices if SKILL in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения с путём {SKILL}")
        for appendix in mine:
            verdict = apply_check(appendix.diff)
            if verdict:
                self.assertEqual(
                    apply_check(appendix.diff, reverse=True), "",
                    f"приложение {SKILL} не накладывается на HEAD ни прямо, "
                    f"ни обратно: {verdict}")
        added = "\n".join(line[1:] for appendix in mine
                          for line in appendix.diff.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        self.assertIn(normalized(RULE), normalized(added),
                      f"правило требования 5 не добавлено дословно:\n{added}")


if __name__ == "__main__":
    unittest.main()
