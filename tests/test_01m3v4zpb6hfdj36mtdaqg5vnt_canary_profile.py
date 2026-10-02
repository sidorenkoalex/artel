"""Подписочный профиль Codex канарейки на временном пульте.

Группа: долгоживущий
Красен до реализации: канарейка пока берёт CODEX_HOME из эфемерного клона либо из боевого дома, а отдельный постоянный профиль не готовит.
"""

import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, doctor, models, providers, runner
from tests.sandbox import ALL_CONFIG_ATTRS, FIXTURE_CODEX_MODEL, RealGitSandbox


class CanaryProfileTest(RealGitSandbox):
    """Публичная команда canary и наблюдаемые окружения её шага Codex."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.use_catalog_fixture()
        self.use_role_map()

        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# процесс клона заменён наблюдателем\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "вход клона")

        self.user_home = Path(tempfile.mkdtemp(prefix="canary-profile-user-"))
        self.addCleanup(shutil.rmtree, self.user_home, ignore_errors=True)
        pool = self.user_home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / "primer.md").write_text("# учебный шаблон\n", encoding="utf-8")
        self.patch(Path, "home", lambda *_: self.user_home)

        self.set_name = "codex-fixture"
        config.MODELS_LOCAL.write_text(
            models.local_template_text() +
            f"\ncanary_sets:\n  {self.set_name}:\n"
            f"    developer:\n      provider: codex\n"
            f"      model: {FIXTURE_CODEX_MODEL}\n", encoding="utf-8")

        provider = providers.get("codex")
        reference = provider.home_reference().reference
        repository_reference = (Path(__file__).resolve().parents[1] /
                                "docs" / "reference" / "role-home" / "codex")
        shutil.copytree(repository_reference, reference)
        self.pult_codex = config.ROLE_HOME / ".codex"
        shutil.copytree(reference, self.pult_codex)
        self.curated_config = (reference / "config.toml").read_bytes()
        self.pult_config = self.pult_codex / "config.toml"
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "референс дома роли")
        self.sha = self.git("rev-parse", "HEAD").strip()

        self.pointer = (config.ROLE_HOME / "Library" / "Preferences" /
                        "com.apple.security.plist")
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_bytes(b"fixture-keychain-pointer")
        self.checks = []
        self.steps = []
        self.launches = []
        self.auth_status = "ok"
        self.auth_detail = "вход ChatGPT подтверждён"
        self.raise_at_step = False
        self.on_step = None
        self.real_auth_check = doctor.check_codex_chatgpt_auth

        def check(role):
            env = provider.environment(role)
            self.checks.append(dict(env))
            return doctor.Check("codex-chatgpt-auth", self.auth_status,
                                self.auth_detail)

        self.patch(doctor, "check_codex_chatgpt_auth", check)

        real_popen = subprocess.Popen

        def launch(argv, *args, **kwargs):
            words = [os.fsdecode(part) for part in argv]
            if canary.CANARY_DRIVE_MODULE not in words:
                return real_popen(argv, *args, **kwargs)
            self.launches.append(Path(kwargs["cwd"]))
            if self.raise_at_step:
                raise RuntimeError("fixture: запуск клона оборван")
            self.fake_step(words)
            return real_popen([sys.executable, "-c", "pass"], *args, **kwargs)

        self.patch(subprocess, "Popen", launch)

    def patch(self, obj, name, value):
        patcher = mock.patch.object(obj, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_step(self, argv):
        """Наблюдает окружение шага до подменённого платного процесса."""
        env = providers.get("codex").environment("developer", "fixture")
        target = (Path(argv[argv.index("--codex-home") + 1])
                  if "--codex-home" in argv else Path(env["CODEX_HOME"]))
        config_path = target / "config.toml"
        observed = {
            "env": dict(env), "profile": target,
            "clone_home": config.ROLE_HOME,
            "before": config_path.read_bytes(),
            "history_before": (target / "history.fixture").exists(),
            "pointer": (config.ROLE_HOME / "Library" / "Preferences" /
                        "com.apple.security.plist").read_bytes(),
            "clone_auth": (config.ROLE_HOME / ".codex" / "auth.json").exists(),
        }
        self.steps.append(observed)
        if self.on_step:
            self.on_step()
        trust = (f'\n[projects."/fixture/{self.rng.randrange(1 << 30)}"]\n'
                 'trust_level = "trusted"\n').encode()
        config_path.write_bytes(observed["before"] + trust)
        (target / "history.fixture").write_text("session", encoding="utf-8")
        result = Path(argv[argv.index("--result") + 1])
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps({
            "task_id": "01TESTCANARY0000000000000001", "head": self.sha,
            "escalated": False, "metrics": {
                "steps": 1, "cost_usd": 0.0, "review_iterations": 0,
                "escalations": [], "dev_retries": 0, "outcome": "killed",
                "kill_note": "штатно", "test_author_visited": True,
                "ceiling_exhausted": False, "ceiling_raise": None,
            }, "steps": [],
        }), encoding="utf-8")

    def run_canary(self):
        output = io.StringIO()
        with redirect_stdout(output):
            canary.cmd_canary(k=1, sha=self.sha, set_name=self.set_name,
                              templates=["primer"])
        return output.getvalue()

    def test_ac1_profile_is_dedicated_and_persistent(self):
        """Два прогона получают один адрес профиля вне боевого дома и клонов.

        Ловит мутацию: CODEX_HOME снова берётся из нового клона на каждом
        запуске — адреса двух шагов различаются.
        """
        self.run_canary()
        self.run_canary()
        self.assertEqual(len(self.steps), 2, f"зерно: {self.seed}")
        first, second = self.steps
        self.assertEqual(first["profile"], second["profile"],
                         f"зерно: {self.seed}")
        for step in self.steps:
            self.assertNotEqual(step["profile"], self.pult_codex,
                                f"зерно: {self.seed}")
            self.assertNotEqual(step["profile"], step["clone_home"] / ".codex",
                                f"зерно: {self.seed}")
            self.assertTrue(step["profile"].is_dir(), f"зерно: {self.seed}")
        ordinary = providers.get("codex").environment("developer", "ordinary")
        self.assertEqual(Path(ordinary["CODEX_HOME"]), self.pult_codex,
                         f"зерно: {self.seed}")

    def test_ac3_step_uses_subscription_without_other_credentials(self):
        """Шаг Codex видит подписочный режим и не получает ключевые каналы.

        Несколько чужих имён ключей подкладываются в ambient окружение.
        Ловит мутацию: API-ключ из окружения Оператора пропущен в шаг —
        одно из имён появляется в наблюдаемом окружении.
        """
        names = ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN",
                 "AWS_WEB_IDENTITY_TOKEN_FILE")
        with mock.patch.dict(os.environ, {name: "fixture-secret" for name in names}):
            self.run_canary()
        env = self.steps[0]["env"]
        for name in names:
            self.assertNotIn(name, env, f"зерно: {self.seed}: {name}")
        with mock.patch.object(runner, "declared_tool_path",
                               lambda name: f"/fixture/bin/{name}"):
            command = providers.get("codex").command()
        self.assertTrue(any("forced_login_method=chatgpt" in part
                            for part in command), f"зерно: {self.seed}")
        self.assertFalse(any("api_key" in part.lower() or "wif" in part.lower()
                             or "enterprise" in part.lower() or "idp" in part.lower()
                             for part in command),
                         f"зерно: {self.seed}")

    def test_ac4_status_and_step_share_profile_environment(self):
        """Проверка входа и шаг видят один CODEX_HOME и остальные пути.

        Ловит мутацию: проверка входа смотрит в клоновый дом, а шаг
        переключён на постоянный профиль — адреса CODEX_HOME расходятся.
        """
        self.run_canary()
        self.assertTrue(self.checks, f"зерно: {self.seed}")
        self.assertEqual(self.checks[0], self.steps[0]["env"],
                         f"зерно: {self.seed}")

    def test_ac5_expired_login_refuses_before_paid_step(self):
        """Неподтверждённый вход останавливает подготовку с рецептом.

        Ловит мутацию: неуспешный login status лишь печатается как
        предупреждение — подменённый платный процесс всё же запускается.
        """
        self.auth_status = "fail"
        self.auth_detail = "вход истёк; выполните codex login"
        with self.assertRaises(SystemExit) as refused:
            self.run_canary()
        self.assertIn("codex login", str(refused.exception))
        self.assertEqual(self.launches, [], f"зерно: {self.seed}")

    def test_ac6_tokens_are_not_copied_or_published(self):
        """Секретный маркер в боевом доме не появляется в клоне и выводе.

        Ловит мутацию: подготовка копирует весь боевой дом Codex — файл
        auth.json с маркером оказывается в доме роли клона; либо doctor
        печатает сырой ответ CLI и маркер попадает в диагностику.
        """
        marker = f"fixture-secret-{self.seed}"
        (self.pult_codex / "auth.json").write_text(marker, encoding="utf-8")
        output = self.run_canary()
        self.assertFalse(self.steps[0]["clone_auth"], f"зерно: {self.seed}")
        self.assertNotIn(marker, output)
        self.assertNotIn(marker, self.steps[0]["before"].decode(errors="replace"))
        self.assertEqual(self.pointer.read_bytes(), b"fixture-keychain-pointer")
        self.assertEqual(self.git("status", "--porcelain"), "")
        for log in config.LOGS.rglob("*.log") if config.LOGS.exists() else ():
            self.assertNotIn(marker, log.read_text(errors="replace"))

        def fake_status(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0,
                                           f"Logged in using ChatGPT {marker}", "")

        provider = providers.get("codex")
        with mock.patch.object(doctor, "check_codex_chatgpt_auth",
                               self.real_auth_check), \
             mock.patch.object(provider, "login_status_command",
                               lambda: ["/fixture/bin/codex", "login", "status"]), \
             mock.patch.object(subprocess, "run", fake_status):
            result = doctor.check_codex_chatgpt_auth("developer")
        self.assertEqual(result.status, "ok")
        self.assertNotIn(marker, result.detail)

    def test_ac7_pult_and_operator_home_remain_untouched(self):
        """Клон не пишет в боевой дом и не получает ambient профиль.

        Ловит мутацию: CODEX_HOME шага подхватывается из окружения
        Оператора либо из дома пульта — меняется один из файлов-маркеров.
        """
        operator_home = self.user_home / "operator-codex"
        operator_home.mkdir()
        operator_config = operator_home / "config.toml"
        operator_config.write_bytes(b"operator-personal-settings")
        before = {str(path.relative_to(config.ROLE_HOME)): path.read_bytes()
                  for path in config.ROLE_HOME.rglob("*") if path.is_file()}
        logs_before = {str(path.relative_to(config.LOGS)): path.read_bytes()
                       for path in config.LOGS.rglob("*") if path.is_file()} \
            if config.LOGS.exists() else {}
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(operator_home)}):
            self.run_canary()
        after = {str(path.relative_to(config.ROLE_HOME)): path.read_bytes()
                 for path in config.ROLE_HOME.rglob("*") if path.is_file()}
        self.assertEqual(before, after,
                         f"зерно: {self.seed}")
        logs_after = {str(path.relative_to(config.LOGS)): path.read_bytes()
                      for path in config.LOGS.rglob("*") if path.is_file()} \
            if config.LOGS.exists() else {}
        self.assertEqual(logs_before, logs_after, f"зерно: {self.seed}")
        self.assertEqual(operator_config.read_bytes(), b"operator-personal-settings")
        self.assertNotEqual(self.steps[0]["profile"], operator_home)
        self.assertNotEqual(self.steps[0]["profile"], self.pult_codex)

    def test_ac8_profile_resets_between_runs_and_refuses_overlap(self):
        """Профиль восстанавливается по SHA, забывая доверие и историю.

        Во время первого шага вложенный запуск пытается занять тот же
        профиль; он должен получить именованный отказ занятости.
        Ловит мутацию: снят эксклюзивный доступ — вложенный запуск
        доходит до второго платного шага вместо отказа.
        """
        nested = []
        pult_paths = {name: getattr(config, name) for name in ALL_CONFIG_ATTRS}
        attempted = False

        def overlap():
            nonlocal attempted
            if attempted:
                return
            attempted = True
            try:
                with ExitStack() as stack:
                    for name, value in pult_paths.items():
                        stack.enter_context(mock.patch.object(config, name, value))
                    self.run_canary()
            except (SystemExit, RuntimeError) as exc:
                nested.append(str(exc))
            else:
                nested.append("вложенный запуск принят")

        self.on_step = overlap
        self.run_canary()
        self.on_step = None
        reference = providers.get("codex").home_reference().reference / "config.toml"
        next_config = self.curated_config + b"\n# second-target-revision\n"
        reference.write_bytes(next_config)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "новый проверяемый SHA")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.run_canary()
        self.assertEqual(len(self.steps), 2, f"зерно: {self.seed}")
        self.assertEqual(self.steps[0]["before"], self.curated_config,
                         f"зерно: {self.seed}")
        self.assertEqual(self.steps[1]["before"], next_config,
                         f"зерно: {self.seed}")
        self.assertFalse(self.steps[0]["history_before"], f"зерно: {self.seed}")
        self.assertFalse(self.steps[1]["history_before"], f"зерно: {self.seed}")
        self.assertEqual(len(nested), 1, f"зерно: {self.seed}")
        self.assertRegex(nested[0].lower(), r"занят|блокиров|already in use|locked")

    def test_ac9_clones_are_removed_on_success_and_exception(self):
        """Оба временных клона удаляются, а пути пульта восстановлены.

        Ловит мутацию: обработка исключения пропускает cleanup — каталог
        второго клона остаётся на диске после отказа процесса.
        """
        pult_root, pult_home = config.ROOT, config.ROLE_HOME
        self.run_canary()
        success_clone = self.launches[-1]
        self.assertFalse(success_clone.exists(), f"зерно: {self.seed}")
        self.raise_at_step = True
        with self.assertRaises(RuntimeError):
            self.run_canary()
        error_clone = self.launches[-1]
        self.assertFalse(error_clone.exists(), f"зерно: {self.seed}")
        self.assertEqual(config.ROOT, pult_root)
        self.assertEqual(config.ROLE_HOME, pult_home)

    def test_ac10_login_isolation_conflict_fails_before_step(self):
        """Доступный вход в боевом доме не разрешает запуск без входа клона.

        Это регрессия конфликтной пары: подписка доступна пульту, но
        отдельный профиль не подтверждён и боевой дом должен сохраниться.
        Ловит мутацию: проверка принимает боевой login status за вход
        канарейки — подменённый платный шаг запускается.
        """
        before = self.pult_config.read_bytes()
        pult = self.pult_codex

        def check(role):
            env = providers.get("codex").environment(role)
            self.checks.append(dict(env))
            status = "ok" if Path(env["CODEX_HOME"]) == pult else "fail"
            return doctor.Check("codex-chatgpt-auth", status,
                                "выполните codex login для канарейки")

        with mock.patch.object(doctor, "check_codex_chatgpt_auth", check):
            with self.assertRaises(SystemExit) as refused:
                self.run_canary()
        self.assertIn("codex", str(refused.exception).lower())
        self.assertEqual(self.launches, [], f"зерно: {self.seed}")
        self.assertEqual(self.pult_config.read_bytes(), before)


if __name__ == "__main__":
    import unittest
    unittest.main()
