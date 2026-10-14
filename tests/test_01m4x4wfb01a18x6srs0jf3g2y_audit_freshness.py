"""Свежесть аудита на связке автокоммит — журнал — очередь — advance.

Группа: долгоживущий
Красен до реализации: AC-1–3 допускают spec_gate по посторонней записи со старым SHA; положительные и прежние отказы AC-4–5 уже работают.

Песочница RealGitSandbox держит настоящий git и БД; документы фикстуры
коммитит публичный checkpoint, переход исполняет fsm.cmd_advance.
Случайные SHA получаются из содержимого документов с печатаемым зерном.
Временный стаб строгого свидетельства в памяти: все методы зелёные,
включая обычный и WIP-формат; производственный код не менялся.
"""
import contextlib
import io
import os
import random
import re
from unittest import mock

from orchestrator import acceptance, checkpoint, config, fsm, store, suite_lock
from orchestrator.advance_gates import spec_audit
from tests.sandbox import RealGitSandbox


class AuditFreshnessTest(RealGitSandbox):
    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2**32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.use_role_map()
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.addCleanup(self.conn.close)
        self.counter = 0

    def msg(self, value):
        return f"зерно: {self.seed}; {value}"

    def state(self, task):
        return store.get_task(self.conn, task)["state"]

    def docs(self, task):
        return self.root / ".artel" / "projects" / config.DEFAULT_TARGET / "tasks" / task

    def commit(self, task, files, role="spec_auditor", timeout=False):
        folder = self.docs(task)
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
        before = {row["id"] for row in store.task_steps(self.conn, task)}
        if timeout:
            checkpoint.commit_timeout_checkpoint(self.conn, task, role)
            rows = [row for row in store.task_steps(self.conn, task)
                    if row["id"] not in before and row["action"] ==
                    "автокоммит артефактов шага (артефактная ветка)"]
            self.assertEqual(len(rows), 1, self.msg("нет WIP-автокоммита"))
            detail = rows[0]["detail"]
        else:
            detail = checkpoint.commit_step_artifacts(self.conn, task, role)
        self.assertTrue(detail, self.msg("автокоммит не состоялся"))
        return detail

    def new_task(self):
        self.counter += 1
        task = f"T{500 + self.counter}"
        branch = f"task/{task.lower()}-audit"
        self.git("branch", branch)
        store.insert_task(self.conn, task, "Аудит фикстуры", "spec_writing",
                          branch, config.DEFAULT_TARGET, 25.0)
        spec = (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
                "status: ready\nschema_version: 5\nzones: app.py\nbudget_usd: 25\n"
                f"---\n# SPEC\n## Контекст\n{self.rng.getrandbits(64)}\n"
                "## Требования\n1. Фикстура.\n## Критерии приёмки\n"
                "AC-1. Фикстура.\n## Не входит\nНичего.\n")
        self.commit(task, {"SPEC.md": spec}, "analyst")
        store.set_state(self.conn, task, "spec_audit", "fsm",
                        expected_state="spec_writing")
        spec_audit.record_entry(self.conn, task)
        return task

    def audit(self, task, verdict="pass", spec_sha=None, role="spec_auditor", timeout=False):
        sha = spec_sha or spec_audit.entry(self.conn, task)["sha"]
        sections = ("ТЗ и SPEC", "Факты против кода", "Проверяемость критериев",
                    "Зоны", "Матрица неослабления", "Пути обхода гейтов", "Вердикт")
        text = (f"---\ntask: {task}\ntype: spec_audit\nauthor_role: spec_auditor\n"
                f"status: ready\nverdict: {verdict}\nsignals: нет\nspec_sha: {sha}\n"
                f"---\n# SPEC-AUDIT\nВерсия {self.rng.getrandbits(64)}\n")
        for section in sections:
            text += f"\n## {section}\n"
            if section == "Матрица неослабления":
                text += ("| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |\n"
                         "|---|---|---|---|---|\n| Фикстура | Фикстура | Да | Фикстура | Сохранено |\n")
            else:
                text += "Отклонений нет.\n"
        detail = self.commit(task, {"SPEC-AUDIT.md": text}, role, timeout=timeout)
        match = re.search(r"sha ([0-9a-f]{40})", detail)
        self.assertIsNotNone(match, self.msg(detail))
        return match[1], detail

    def advance(self, task):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            fsm.cmd_advance(task)
        return output.getvalue()

    def old_audit(self):
        task = self.new_task()
        sha, detail = self.audit(task)
        output = self.advance(task)
        self.assertEqual(self.state(task), "spec_gate", self.msg(output))
        store.set_state(self.conn, task, "spec_audit", "operator",
                        expected_state="spec_gate")
        spec_audit.record_entry(self.conn, task)
        return task, sha, detail

    def assert_refused(self, task):
        output = self.advance(task)
        self.assertEqual(self.state(task), "spec_audit",
                         self.msg(f"старый/неподтверждённый аудит прошёл: {output}"))

    def test_ac1_deferred_old_sha_cannot_advance(self):
        """Старый pass доставлен из файла очереди после повторного входа.

        Запись действительно дошла, но пройти можно только после нового
        автокоммита аудитора. Проверяются два разных текста очереди.
        Ловит мутацию: любой досланный detail с SHA признаётся свежестью —
        advance переводит задачу в spec_gate до нового шага.
        """
        for form in ("точный", "в тексте"):
            with self.subTest(form=form, seed=self.seed):
                task, sha, _ = self.old_audit()
                detail = sha if form == "точный" else f"отчёт прогона: {sha}; завершён"
                self.assertTrue(suite_lock.defer_journal({
                    "task_id": task, "action": acceptance.SUITE_NEAR_LIMIT_ACTION,
                    "detail": detail, "at": store.now(), "session_id": "fixture"}), self.msg(form))
                self.assertTrue(list(suite_lock.directory().rglob("*.json")), self.msg("нет файла очереди"))
                self.assertEqual(suite_lock.deliver_journal(), 1, self.msg(form))
                rows = [r for r in store.task_steps(self.conn, task)
                        if r["action"] == acceptance.SUITE_NEAR_LIMIT_ACTION]
                self.assertEqual(len(rows), 1, self.msg(rows))
                self.assertIn(sha, rows[0]["detail"], self.msg(rows))
                self.assert_refused(task)
                self.audit(task, "concerns")
                output = self.advance(task)
                self.assertEqual(self.state(task), "spec_gate", self.msg(output))

    def test_ac2_ordinary_orchestrator_record_cannot_advance(self):
        """Обычные действия с точным SHA не заменяют автокоммит аудитора.

        Ловит мутацию: проверка доверяет только actor и SHA, игнорируя
        действие журнала; после такой записи задача уходит в spec_gate.
        """
        for action in ("диагностика", "прогон завершён"):
            with self.subTest(action=action, seed=self.seed):
                task, sha, detail = self.old_audit()
                store.journal(self.conn, task, "orchestrator", action, detail)
                self.assertIn(sha, detail, self.msg(detail))
                self.assert_refused(task)

    def test_ac3_similar_sha_and_foreign_text_cannot_advance(self):
        """Подлинное действие с неверным свидетельством не даёт свежесть.

        Перебираются короткий, длинный, соседний SHA, точный SHA в
        постороннем тексте и свидетельства другой роли/задачи.
        Ловит мутацию: поиск SHA подстрокой принимает удлинённый SHA либо
        упоминание вне соответствующего автокоммита — spec_gate открыт.
        """
        for variant in ("short", "long", "similar", "text", "role", "task", "suffix"):
            with self.subTest(variant=variant, seed=self.seed):
                task, sha, detail = self.old_audit()
                values = {
                    "short": detail.replace(sha, sha[:-1]),
                    "long": detail.replace(sha, sha + "a"),
                    "similar": detail.replace(sha, ("0" if sha[0] != "0" else "1") + sha[1:]),
                    "text": f"посторонний текст {sha} конец",
                    "role": detail.replace("spec_auditor", "analyst"),
                    "task": detail.replace(task + ":", "T999:"),
                    "suffix": detail.replace(sha, "a" * 40) + f"; справочно: {sha}",
                }
                store.journal(self.conn, task, "orchestrator",
                              "автокоммит артефактов шага (артефактная ветка)", values[variant])
                self.assert_refused(task)

    def test_ac4_current_autocommit_passes(self):
        """Обычный и WIP checkpoint текущего визита допускают pass и concerns.

        Ловит мутацию: уточнённый разбор не принимает штатный формат
        свидетельства — задача с новым аудитом остаётся в spec_audit.
        """
        for verdict, timeout in (("pass", False), ("concerns", False),
                                 ("pass", True), ("concerns", True)):
            with self.subTest(verdict=verdict, timeout=timeout, seed=self.seed):
                task = self.new_task()
                self.audit(task, verdict, timeout=timeout)
                output = self.advance(task)
                self.assertEqual(self.state(task), "spec_gate", self.msg(output))

    def test_ac5_previous_visit_wrong_role_binding_and_unreadable_history(self):
        """Прежние причины отказа проверяются на настоящих документах.

        Нечитаемая история проверяется публичным freshness_refusal с
        отсутствующей ссылкой: настоящий git log возвращает ошибку.
        Ловит мутацию: снят отказ свежести, роли или привязки — соответствующий
        сценарий открывает spec_gate; ошибка истории принимается за успех.
        """
        for defect in ("old", "role", "changed", "binding", "history"):
            with self.subTest(defect=defect, seed=self.seed):
                if defect == "old":
                    task, _, _ = self.old_audit()
                    self.assert_refused(task)
                    continue
                task = self.new_task()
                if defect == "role":
                    self.audit(task, role="analyst")
                elif defect == "binding":
                    self.audit(task, spec_sha="f" * 40)
                else:
                    sha, _ = self.audit(task)
                    if defect == "changed":
                        self.commit(task, {"SPEC.md": "SPEC изменён после входа\n"}, "analyst")
                if defect == "history":
                    # Существующая публичная функция получает заведомо
                    # несуществующую ссылку: git log возвращает ошибку.
                    refusal = spec_audit.freshness_refusal(self.conn, task, "refs/missing/audit")
                    self.assertIsNotNone(refusal, self.msg("нечитаемая история принята"))
                else:
                    self.assert_refused(task)
