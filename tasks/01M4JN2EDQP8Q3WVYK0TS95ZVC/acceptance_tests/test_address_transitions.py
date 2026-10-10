"""Адреса `http(s)://<DNS-имя>` на рубежах пульта: выход из `tests_writing` и `in_dev -> verifying`.

Группа: разовый

Красен до реализации: ни выход из `tests_writing`, ни рубеж `in_dev -> verifying` адресов ещё не проверяют — файлы с DNS-адресом проходят переход (AC-1, AC-3 красны); сценарии пропуска (AC-2, AC-4, AC-5) зелены с рождения — до реализации отказа нет вовсе.

Почему разовый: переходы гоняются через публичный `fsm.cmd_advance` на
настоящем git песочницей `tests/test_long_lived_transitions.py::
_TransitionSandbox` (пульт с артефактной веткой, bare `origin`, worktree
кодовой ветки), которая подменяет проходом соседние гейты перехода по
закрытым именам (`_zones_gate_refuses`, `_mutation_claim_gate`, …).
Долгоживущему файлу и закрытые имена, и помощник вне `tests/sandbox.py`
запрещены; само правило адресов (что ловится, что пропускается, сверка с
инвариантом 35) держит долгоживущий файл задачи в `tests/`.

Адреса собраны по частям (`SEP`), чтобы исходник планки не нёс их одной
строкой.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import config  # noqa: E402
from orchestrator.advance_gates.tests_writing import LONG_LIVED_ACTION  # noqa: E402
from tests.test_long_lived_transitions import (  # noqa: E402
    _TransitionSandbox, long_lived_source)

SEP = ":" + "//"
DNS_URL = "https" + SEP + "example.test/x"
EXCEPTION_FILES = {
    "tests/test_github_adapter.py": ["https" + SEP + "github.com/o/r/pull/1"],
    "tests/test_ci_status.py": ["https" + SEP + "api.github.com/repos/o/r"],
    "tests/test_sandbox.py": ["http" + SEP + "example.invalid/repo.git",
                              "http" + SEP + "127.0.0.1.evil.example/repo.git"],
}


def with_address(text: str, address: str, after: str) -> tuple[str, int]:
    """(текст с `ADDRESS = '<address>'` сразу после строки `after`, её номер)."""
    lines = text.split("\n")
    at = lines.index(after) + 1
    lines.insert(at, f"ADDRESS = {address!r}")
    return "\n".join(lines), at + 1


def plain_module(addresses: list[str], pad: int = 0) -> tuple[str, list[int]]:
    """(текст модуля `tests/` со строковыми константами адресов, их строки)."""
    lines = ['"""Фикстура файла tests/ песочницы."""', ""]
    lines += [f"# заполнитель {i}" for i in range(pad)]
    numbers = []
    for n, address in enumerate(addresses):
        lines.append(f"ADDRESS_{n} = {address!r}")
        numbers.append(len(lines))
    return "\n".join(lines) + "\n", numbers


class _AddressAsserts:

    def assert_names_line(self, text: str, path: str, lineno: int) -> None:
        self.assertTrue(
            any(path in line and re.search(rf"\b{lineno}\b", line)
                for line in text.splitlines()),
            f"отказ не называет {path} и строку {lineno}: {text}")


class TestsWritingExitAddressTest(_AddressAsserts, _TransitionSandbox):

    def test_ac1_dns_address_refuses_tests_writing_exit(self):
        """Свой долгоживущий файл с `https://<example.test>/x` — выход отклонён.

        Сценарий: кодовая ветка добавляет свой файл `tests/test_<id>_alpha.py`
        с адресом строковой константой; выход из `tests_writing` оставляет
        задачу в `tests_writing` отказом `LONG_LIVED_ACTION`, называющим
        файл и номер строки адреса. Контроль: тот же файл без адреса —
        выход проходит в `in_dev`.

        Ловит мутацию: признак адреса не включён в `long_lived_sign_hits`
        (или гейт выхода зовёт проверку адреса мимо
        `long_lived_errors_from_files`) — задача уходит в `in_dev` с
        DNS-адресом в долгоживущем файле.
        """
        text, lineno = with_address(long_lived_source(), DNS_URL,
                                    "import unittest")
        self.wt_commit({self.own: text})
        out = self.exit_tests_writing()
        self.assertEqual(self.state(), "tests_writing", out)
        self.assertIn(LONG_LIVED_ACTION, out)
        self.assert_names_line(out, self.own, lineno)
        self.reset_branch()
        self.wt_commit({self.own: long_lived_source()})
        out = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev", f"контроль: {out}")

    def test_ac2_loopback_address_passes_tests_writing_exit(self):
        """Свой долгоживущий файл с адресом на `127.0.0.1:8080` или `localhost` — выход проходит.

        Сценарий: для каждого loopback-адреса ветка сбрасывается к базе,
        свой файл несёт адрес строковой константой, выход из
        `tests_writing` переводит задачу в `in_dev`.

        Ловит мутацию: исключённые хосты сравниваются вместе с портом или
        не вычитаются вовсе — loopback-адрес отклоняет выход.
        """
        for address in ("http" + SEP + "127.0.0.1:8080",
                        "http" + SEP + "localhost/x",
                        "https" + SEP + "localhost:8443"):
            with self.subTest(address=address):
                self.reset_branch()
                text, _ = with_address(long_lived_source(), address,
                                       "import unittest")
                self.wt_commit({self.own: text})
                out = self.exit_tests_writing()
                self.assertEqual(self.state(), "in_dev", f"{address}: {out}")


class InDevAddressTest(_AddressAsserts, _TransitionSandbox):

    ADDED = "tests/test_netaddr_fixture.py"

    def setUp(self):
        super().setUp()
        self.lock_with_own()
        self.locked_head = self.wt_git("rev-parse", "HEAD").strip()

    def back_to_lock(self) -> None:
        self.wt_git("reset", "-q", "--hard", self.locked_head)
        self.set_row(state="in_dev")

    def test_ac3_branch_tests_file_with_dns_address_refuses_in_dev(self):
        """Файл `tests/`, добавленный или изменённый веткой, с DNS-адресом — рубеж отклонён.

        Сценарий: (а) ветка добавляет `tests/test_netaddr_fixture.py` с
        адресом на строке N; (б) ветка дописывает адрес в конец файла базы
        `tests/test_existing.py`. В обоих случаях `in_dev -> verifying`
        оставляет задачу в `in_dev`, отказ называет файл и номер строки.
        Контроль: без адреса тот же переход уходит в `verifying`.

        Ловит мутацию: новый рубеж не вставлен в `fsm_advance.in_dev`, или
        читает только добавленные файлы (статус `A`), пропуская изменённые
        (`M`) — задача уходит в `verifying` с адресом в `tests/`.
        """
        added, (added_line,) = plain_module([DNS_URL], pad=5)
        existing = (self.root / self.EXISTING).read_text(encoding="utf-8")
        modified = existing + f"ADDRESS = {DNS_URL!r}\n"
        modified_line = len(existing.split("\n"))
        scenarios = (("добавлен", self.ADDED, added, added_line),
                     ("изменён", self.EXISTING, modified, modified_line))
        for label, path, text, lineno in scenarios:
            with self.subTest(scenario=label):
                self.back_to_lock()
                self.wt_commit({path: text})
                out = self.advance_in_dev()
                self.assertEqual(self.state(), "in_dev", f"{label}: {out}")
                self.assert_names_line(out, path, lineno)
        self.back_to_lock()
        self.wt_commit({self.ADDED: plain_module([])[0]})
        out = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", f"контроль: {out}")

    def test_ac5_named_exceptions_pass_in_dev(self):
        """Четыре пары именованных исключений, добавленные веткой, — рубеж проходит.

        Сценарий: ветка добавляет `tests/test_github_adapter.py` (хост
        `github.com`), `tests/test_ci_status.py` (`api.github.com`),
        `tests/test_sandbox.py` (`example.invalid` и
        `127.0.0.1.evil.example`); `in_dev -> verifying` переводит задачу
        в `verifying`.

        Ловит мутацию: рубеж `in_dev` проверяет адреса своим правилом без
        именованных исключений (копия шаблона вместо функции guard) — файлы
        исключений отклоняют переход.
        """
        files = {path: plain_module(addresses)[0]
                 for path, addresses in EXCEPTION_FILES.items()}
        self.wt_commit(files)
        out = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", out)


class InDevUntouchedAddressTest(_TransitionSandbox):

    UNTOUCHED = "tests/test_untouched_netaddr.py"

    def setUp(self):
        super().setUp()
        text, _ = plain_module(["https" + SEP + "mirror.example.test/repo.git"])
        (self.root / self.UNTOUCHED).write_text(text, encoding="utf-8")
        self.git("add", self.UNTOUCHED)
        self.git("commit", "-q", "-m", "main: файл tests/ с адресом")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.wt_git("merge", "-q", "--ff-only", config.MAIN_BRANCH)
        self.base_sha = self.wt_git("rev-parse", "HEAD").strip()
        self.lock_with_own()

    def test_ac4_untouched_tests_file_does_not_affect_in_dev(self):
        """Файл `tests/` с DNS-адресом из базы, не тронутый веткой, — рубеж проходит.

        Сценарий: адрес лежит в `tests/test_untouched_netaddr.py` базы
        ветки (`origin/main`), ветка его не меняла; `in_dev -> verifying`
        переводит задачу в `verifying`.

        Ловит мутацию: рубеж сканирует всё дерево `tests/` головы ветки, а
        не файлы её диффа против базы — чужой файл с адресом отклоняет
        переход.
        """
        self.assertTrue((self.wt / self.UNTOUCHED).is_file(),
                        "контроль: файл базы есть в рабочей копии ветки")
        out = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", out)


if __name__ == "__main__":
    unittest.main()
