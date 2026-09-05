"""Юнит-тесты перехвата сетевых git-команд `tests/sandbox.py` (SPEC
01M1QHQ277PQQA894X97RVEX9Y, требования 1, 4). Постоянное покрытие модуля
песочницы — приёмочные тесты задачи (`tasks/01M1QHQ277PQQA894X97RVEX9Y/
acceptance_tests/`) проверяют то же поведение сквозным путём через
`TmpRootTest`/`gitcmd.git`; здесь — сами модульные функции, отдельно от
конкретной песочницы, которая их использует.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.sandbox import (_is_local_git_address,  # noqa: E402
                           _network_git_command_denial, network_guarded_real_run)


class IsLocalGitAddressTest(unittest.TestCase):

    def test_file_url_is_local(self):
        self.assertTrue(_is_local_git_address("file:///tmp/origin.git"))

    def test_absolute_path_is_local(self):
        self.assertTrue(_is_local_git_address("/tmp/origin.git"))

    def test_bare_remote_name_is_local(self):
        """Голое имя remote'а (`origin`, `acme`) — не URL, git резолвит
        его сам из локального конфига репозитория (T048/T053)."""
        self.assertTrue(_is_local_git_address("origin"))

    def test_loopback_http_hosts_are_local(self):
        self.assertTrue(_is_local_git_address("http://localhost:8080/x"))
        self.assertTrue(_is_local_git_address("http://127.0.0.1:9/x"))

    def test_dns_hostname_https_is_not_local(self):
        self.assertFalse(
            _is_local_git_address("https://example.invalid/repo.git"))

    def test_host_merely_prefixed_by_loopback_ip_is_not_local(self):
        """`127.0.0.1.evil.example` — DNS-имя, лишь начинающееся с
        loopback-адреса, не сам loopback (точное сравнение хоста)."""
        self.assertFalse(
            _is_local_git_address("http://127.0.0.1.evil.example/x"))


class NetworkGitCommandDenialTest(unittest.TestCase):

    def test_fetch_with_dns_address_is_denied(self):
        denial = _network_git_command_denial(
            ["git", "fetch", "-q", "https://example.invalid/sled", "main"],
            want_text=True)
        self.assertIsNotNone(denial)
        self.assertNotEqual(0, denial.returncode)
        self.assertIn("сеть в тестах запрещена: fetch", denial.stderr)
        self.assertIn("https://example.invalid/sled", denial.stderr)

    def test_dash_c_prefix_is_skipped_when_locating_the_subcommand(self):
        """`git -C <repo> fetch ...` (`gitcmd.in_repo`) — адрес ищется
        после подкоманды, а не путается с `-C`."""
        denial = _network_git_command_denial(
            ["git", "-C", "/some/repo", "fetch", "https://example.invalid/x"],
            want_text=True)
        self.assertIsNotNone(denial)
        self.assertIn("сеть в тестах запрещена: fetch", denial.stderr)

    def test_local_address_is_not_denied(self):
        self.assertIsNone(_network_git_command_denial(
            ["git", "fetch", "-q", "/tmp/bare.git", "main"], want_text=True))

    def test_non_network_subcommand_is_not_denied(self):
        self.assertIsNone(_network_git_command_denial(
            ["git", "status", "--porcelain"], want_text=True))

    def test_bytes_mode_stderr_matches_text_flag(self):
        denial = _network_git_command_denial(
            ["git", "push", "https://example.invalid/x", "main"],
            want_text=False)
        self.assertIsInstance(denial.stderr, bytes)
        self.assertIn("сеть в тестах запрещена: push".encode(), denial.stderr)


class NetworkGuardedRealRunTest(unittest.TestCase):

    def test_dns_address_is_denied_without_touching_real_subprocess(self):
        with mock.patch("tests.sandbox._REAL_RUN") as real_run:
            res = network_guarded_real_run(
                ["git", "ls-remote", "https://example.invalid/x", "main"],
                capture_output=True, text=True)

        real_run.assert_not_called()
        self.assertNotEqual(0, res.returncode)
        self.assertIn("сеть в тестах запрещена: ls-remote", res.stderr)

    def test_non_network_command_passes_through_to_real_subprocess(self):
        fake_result = subprocess.CompletedProcess(["git", "status"], 0, "", "")
        with mock.patch("tests.sandbox._REAL_RUN",
                        return_value=fake_result) as real_run:
            res = network_guarded_real_run(["git", "status"], cwd="/tmp")

        real_run.assert_called_once_with(["git", "status"], cwd="/tmp")
        self.assertEqual(0, res.returncode)


if __name__ == "__main__":
    unittest.main()
