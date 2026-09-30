"""Изоляция дома Codex канарейки и сохранение дома обычной задачи.

Группа: долгоживущий
Красен до реализации: прогон канарейки передаёт в шаг Codex дом пульта, поэтому подменённый запуск меняет его config.toml.
"""

import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, doctor, models, providers
from tests.sandbox import FIXTURE_CODEX_MODEL, RealGitSandbox


class CanaryCodexHomeTest(RealGitSandbox):
    """Полный путь команды канарейки на временном пульте."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.use_catalog_fixture()
        self.use_role_map()

        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# вход процесса клона в песочнице\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "вход процесса клона")
        self.sha = self.git("rev-parse", "HEAD").strip()

        self.pool_home = Path(tempfile.mkdtemp(prefix="test-canary-pool-"))
        self.addCleanup(shutil.rmtree, self.pool_home, ignore_errors=True)
        pool = self.pool_home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / "primer.md").write_text("# учебный шаблон\n", encoding="utf-8")
        patcher = mock.patch.object(Path, "home", lambda *_: self.pool_home)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.set_name = "kodex-fikstura"
        layer = models.local_template_text() + (
            f"\ncanary_sets:\n  {self.set_name}:\n"
            f"    developer:\n      provider: codex\n"
            f"      model: {FIXTURE_CODEX_MODEL}\n")
        config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        config.MODELS_LOCAL.write_text(layer, encoding="utf-8")

        self.pult_codex = config.ROLE_HOME / ".codex"
        reference = providers.get("codex").home_reference().reference
        repository_reference = (Path(__file__).resolve().parent.parent /
                                "docs" / "reference" / "role-home" / "codex")
        shutil.copytree(repository_reference, reference)
        shutil.copytree(reference, self.pult_codex)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "референс дома роли")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.pult_config = self.pult_codex / "config.toml"
        self.pointer = (config.ROLE_HOME / "Library" / "Preferences" /
                        "com.apple.security.plist")
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_bytes(b"fixture-keychain-pointer")
        self.observed = []
        self.login_checks = []

        def login(role):
            self.login_checks.append(role)
            return doctor.Check("codex-chatgpt-auth", "ok", "вход подтверждён")

        patcher = mock.patch.object(doctor, "check_codex_chatgpt_auth", login)
        patcher.start()
        self.addCleanup(patcher.stop)

        real_popen = subprocess.Popen

        def launch(argv, *args, **kwargs):
            words = [os.fsdecode(part) for part in argv]
            if canary.CANARY_DRIVE_MODULE in words:
                self.fake_codex_run(words)
                return real_popen([sys.executable, "-c", "pass"], *args, **kwargs)
            return real_popen(argv, *args, **kwargs)

        patcher = mock.patch.object(subprocess, "Popen", launch)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_codex_run(self, argv):
        """Имитирует запись доверия CLI через окружение шага роли."""
        env = providers.get("codex").environment("developer", "fixture")
        target = (Path(argv[argv.index("--codex-home") + 1])
                  if "--codex-home" in argv else Path(env["CODEX_HOME"]))
        trust = f'\n[projects."/clone/{self.rng.randrange(1 << 30)}"]\ntrust_level = "trusted"\n'
        config_path = target / "config.toml"
        config_path.write_bytes(config_path.read_bytes() + trust.encode())
        clone_home = config.ROLE_HOME
        self.observed.append({
            "codex_home": target,
            "clone_home": clone_home,
            "config": config_path.read_bytes(),
            "auth_file": (clone_home / ".codex" / "auth.json").exists(),
            "pointer": (clone_home / "Library" / "Preferences" /
                        "com.apple.security.plist").read_bytes(),
        })
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
        self.output = output.getvalue()

    def test_ac1_canary_writes_trust_only_in_clone_home(self):
        """Подменённый шаг Codex дописывает доверие в свой config.toml.

        Пультовский файл остаётся байт в байт прежним, а запись видна в
        клоновском файле до удаления эфемерного клона.
        Ловит мутацию: канарейка передаёт пультовский CODEX_HOME в процесс
        клона — запись доверия появляется в файле пульта.
        """
        before = self.pult_config.read_bytes()
        self.run_canary()
        self.assertEqual(before, self.pult_config.read_bytes(), f"зерно: {self.seed}")
        self.assertEqual(len(self.observed), 1,
                         f"зерно: {self.seed}\n{self.output}")
        self.assertNotEqual(self.observed[0]["codex_home"], self.pult_codex)
        self.assertEqual(self.observed[0]["codex_home"],
                         self.observed[0]["clone_home"] / ".codex")
        self.assertIn(b'trust_level = "trusted"', self.observed[0]["config"])

    def test_ac2_clone_checks_login_and_copies_pointer_without_credentials(self):
        """Без указателя прогон отказывает до шага; с ним проверяет вход.

        В развёрнутый дом клона приезжает указатель, но не файл учётных
        данных, лежащий рядом с конфигом пульта.
        Ловит мутацию: проверка указателя снята или весь дом Codex пульта
        копируется в клон — отказ пропадает либо auth.json появляется там.
        """
        (self.pult_codex / "auth.json").write_bytes(b"fixture-secret")
        pointer = self.pointer.read_bytes()
        self.pointer.unlink()
        with self.assertRaises(SystemExit) as refused:
            self.run_canary()
        self.assertIn("указатель связки ключей", str(refused.exception))
        self.assertEqual(self.observed, [], f"зерно: {self.seed}")
        self.pointer.write_bytes(pointer)
        self.run_canary()
        self.assertIn("developer", self.login_checks)
        self.assertTrue(self.observed, f"зерно: {self.seed}\n{self.output}")
        self.assertEqual(self.observed[0]["pointer"], pointer)
        self.assertFalse(self.observed[0]["auth_file"], f"зерно: {self.seed}")

    def test_ac3_real_task_keeps_a_writable_own_codex_home(self):
        """Вне канарейки провайдер отдаёт обычной задаче развёрнутый дом.

        Та же запись доверия через CODEX_HOME меняет файл дома задачи.
        Ловит мутацию: переопределение после канарейки остаётся активным —
        настоящая задача пишет в удалённый либо чужой каталог.
        """
        self.run_canary()
        for suffix in ("a", "b"):
            env = providers.get("codex").environment("developer", suffix)
            path = Path(env["CODEX_HOME"]) / "config.toml"
            self.assertEqual(path, self.pult_config, f"зерно: {self.seed}")
            path.write_bytes(path.read_bytes() + suffix.encode())
            self.assertTrue(self.pult_config.read_bytes().endswith(suffix.encode()))

    def test_ac4_doctor_still_reports_difference_and_leaves_old_trust(self):
        """Накопленная запись доверия переживает прогон канарейки.

        Проверка doctor продолжает сообщать о расхождении дома Codex
        с референсом и сама не удаляет старую запись.
        Ловит мутацию: канарейка чистит боевой config.toml или doctor
        перестаёт сравнивать его с референсом — запись исчезает либо
        проверка перестаёт выдавать предупреждение.
        """
        old = b'\n[projects."/old-clone"]\ntrust_level = "trusted"\n'
        self.pult_config.write_bytes(self.pult_config.read_bytes() + old)
        before = self.pult_config.read_bytes()
        self.run_canary()
        check = doctor.check_codex_role_home()
        self.assertEqual(self.pult_config.read_bytes(), before, f"зерно: {self.seed}")
        self.assertEqual(check.status, "warn", f"зерно: {self.seed}: {check}")
        self.assertIn("config.toml", check.detail)


if __name__ == "__main__":
    unittest.main()
