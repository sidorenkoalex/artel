"""Признак шага роли и отказы команд для обоих провайдеров.

Группа: долгоживущий
Красен до реализации: признак ещё не принимает env и не видит ARTEL_ROLE; смоки и note пока не проверяют этот признак.
"""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import answer, config, doctor, notes, pool_seal, providers, roles, runner, store
from tests.sandbox import SchemaTmpRootTest, TmpRootTest


class RoleEnvironmentPredicateTest(unittest.TestCase):
    def test_ac1_marker_and_legacy_environment(self):
        """Переданное окружение и окружение процесса одинаково узнают роль.

        Ловит мутацию: проверка ARTEL_ROLE пропущена или читает только os.environ —
        словарь с маркером и чужим HOME даст ложь вместо истины.
        """
        seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for _ in range(6):
            role = f"role_{rng.randrange(1 << 30):x}"
            foreign_home = f"/tmp/operator_{rng.randrange(1 << 30):x}"
            env = {"HOME": foreign_home, config.ARTEL_ROLE_ENV: role}
            self.assertTrue(runner.in_role_environment(env), f"зерно: {seed}; env={env}")
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertTrue(runner.in_role_environment(), f"зерно: {seed}; role={role}")

        legacy = {"HOME": str(config.ROLE_HOME),
                  "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)}
        self.assertTrue(runner.in_role_environment(legacy), f"зерно: {seed}; старые маркеры")
        self.assertFalse(runner.in_role_environment(
            {"HOME": "/tmp/operator", config.ARTEL_ROLE_ENV: ""}),
            f"зерно: {seed}; пустой маркер")


class RoleConsumerRefusalTest(TmpRootTest):
    def test_ac2_existing_consumers_refuse_codex_and_claude(self):
        """Команды с существующим рубежом отказывают обоим шагам роли.

        Ловит мутацию: потребитель обходит in_role_environment или проверяет
        только HOME Claude — codex с ARTEL_ROLE дойдёт до обычной ветки.
        """
        with mock.patch.object(store, "db", return_value=object()), \
                mock.patch.object(store, "resolve_task_id", side_effect=lambda conn, task: task), \
                mock.patch.object(answer.lease, "run_locked", side_effect=lambda conn, task, sid, fn: fn(sid)), \
                mock.patch.object(answer.artifact_source, "resolve",
                                  side_effect=AssertionError("прошли рубеж окружения роли")):
            for provider in ("codex", "claude"):
                env = {config.ARTEL_ROLE_ENV: "developer", "HOME": f"/tmp/{provider}-operator"}
                if provider == "claude":
                    env.update(HOME=str(config.ROLE_HOME),
                               CLAUDE_CONFIG_DIR=str(config.ROLE_CONFIG_DIR))
                with self.subTest(provider=provider), mock.patch.dict(os.environ, env, clear=True):
                    with mock.patch.object(runner, "in_role_environment",
                                           wraps=runner.in_role_environment) as predicate:
                        with self.assertRaises(SystemExit) as zones:
                            answer.cmd_zones_extend("T001", "docs/a.md")
                        predicate.assert_called()
                    self.assertIn("роли", str(zones.exception))
                    with mock.patch.object(runner, "in_role_environment",
                                           wraps=runner.in_role_environment) as predicate:
                        with self.assertRaises(SystemExit) as doc:
                            notes.cmd_doc_commit(["--flush"])
                        predicate.assert_called()
                    self.assertIn("роли", str(doc.exception))


class ProviderIsolationSmokeTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        skills = self.root / "skills"
        skills.mkdir()
        for name in roles.skills("developer"):
            (skills / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

    def test_ac3_each_offline_smoke_rejects_unrecognized_step(self):
        """Оба офлайн-смока замечают непризнанное окружение своего шага.

        Ловит мутацию: смок не зовёт in_role_environment для собранного
        окружения — подмена результата на ложь оставит зелёный Check.
        """
        with mock.patch.object(runner, "declared_tool_path", return_value="/tmp/codex"):
            for name, smoke in (("claude", doctor.isolation_smoke),
                                ("codex", doctor.codex_isolation_smoke)):
                with self.subTest(provider=name, recognized=True):
                    baseline = smoke("developer")
                    self.assertEqual(baseline.status, "ok", f"{name}: {baseline.detail}")
            with mock.patch.object(runner, "in_role_environment", return_value=False):
                for name, smoke in (("claude", doctor.isolation_smoke),
                                    ("codex", doctor.codex_isolation_smoke)):
                    with self.subTest(provider=name):
                        check = smoke("developer")
                        self.assertEqual(check.status, "fail", f"{name}: {check.detail}")
                        self.assertRegex(check.detail.lower(), r"рол[ьи]|role")


class RoleCommandRefusalTest(SchemaTmpRootTest):
    def test_ac5_provider_environments_and_operator_boundary(self):
        """Собранные окружения обеих ролей распознаются; чужой дом Оператора нет.

        Ловит мутацию: role_env теряет ARTEL_ROLE на codex или признак
        считает всякий HOME ролью — ошибётся одно из трёх распознаваний.
        """
        seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {seed}")
        with mock.patch.object(runner, "declared_tool_path", return_value="/tmp/tool"), \
                mock.patch.object(runner, "git_identity", return_value={}):
            for name in ("codex", "claude"):
                with self.subTest(provider=name), \
                        mock.patch.object(providers, "for_role", return_value=providers.get(name)):
                    env = runner.role_env("developer")
                    self.assertTrue(runner.in_role_environment(env), f"зерно: {seed}; {name}")
        rng = random.Random(seed)
        for _ in range(4):
            operator = {"HOME": f"/tmp/operator_{rng.randrange(1 << 30):x}"}
            self.assertFalse(runner.in_role_environment(operator), f"зерно: {seed}; {operator}")

    def test_ac5_codex_answer_note_and_pool_decryption_refuse(self):
        """Шаг codex получает отказы answer, note и восстановления пула.

        Ловит мутацию: note не проверяет ARTEL_ROLE — пустой flush
        завершится успешно, хотя процесс принадлежит роли codex.
        """
        with tempfile.TemporaryDirectory() as fake_home:
            env = {"HOME": fake_home, config.ARTEL_ROLE_ENV: "developer"}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(Path, "home", return_value=Path(fake_home)):
                with mock.patch.object(store, "db", return_value=object()), \
                        mock.patch.object(store, "resolve_task_id", side_effect=lambda conn, task: task), \
                        mock.patch.object(answer.lease, "run_locked", side_effect=lambda conn, task, sid, fn: fn(sid)), \
                        mock.patch.object(store, "get_task", return_value={"state": "in_dev", "branch": "task/test"}):
                    with self.assertRaises(SystemExit) as refused_answer:
                        answer.cmd_answer("T001", "/tmp/no-answer")
                    self.assertIn("роли", str(refused_answer.exception))

                with self.assertRaises(SystemExit) as refused_note:
                    notes.cmd_note(["--flush"])
                self.assertIn("роли", str(refused_note.exception))

                refusal = pool_seal.restore_pool_if_missing(None)
                self.assertIsInstance(refusal, str)
                self.assertIn("роли", refusal)


if __name__ == "__main__":
    unittest.main()
