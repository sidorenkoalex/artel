"""Справка пульта (докстринг `orchestrator/artel.py`) ↔ реестр команд `table`.

Группа: долгоживущий

Ключи реестра берутся разбором исходника `artel.main` (`inspect.getsource`
+ `ast`), а не списком в тесте: новая команда без строки справки красит
тест сама. Блок «Команды:» — от строки `Команды:` докстринга до первой
пустой строки.

Красен до реализации: в блоке «Команды:» нет семи ключей реестра (workspace, report, acceptance-dry-run, plank-run, suite-run, preflight, guard — AC-3), шапка говорит «Фаза 0» и не называет гейтов (AC-5); методы AC-4 и AC-7 зелены и до реализации — они держат отсутствие команд справки без реестра и форму `pin-update`, введённую раньше.
"""

import ast
import contextlib
import inspect
import io
import os
import random
import re
import sys
import textwrap
import unittest
from unittest import mock

from orchestrator import artel, config, pin
from tests.sandbox import SyncedOriginConnSandbox

KEY_WORD = re.compile(r"[a-z][a-z0-9-]*")


def registry_keys() -> list[str]:
    """Строковые ключи словаря, присвоенного имени `table` в `artel.main`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(artel.main)))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                and any(isinstance(t, ast.Name) and t.id == "table"
                        for t in node.targets)):
            return [k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    raise AssertionError("в artel.main нет присваивания `table = {...}`")


def commands_block(doc: str) -> list[str]:
    """Строки блока «Команды:» докстринга до первой пустой строки."""
    lines = doc.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip() == "Команды:"), None)
    if start is None:
        raise AssertionError("в докстринге artel.py нет строки «Команды:»")
    block = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        block.append(line)
    return block


def mentioned_as_command(key: str, block: list[str]) -> bool:
    """`key` встречается отдельным словом команды: слева начало строки,
    пробел или `|`, справа пробел, `|` или конец строки."""
    pattern = re.compile(r"(?:^|(?<=[ |]))" + re.escape(key) + r"(?=[ |]|$)")
    return any(pattern.search(line) for line in block)


def header(doc: str) -> str:
    """Текст докстринга до строки `Состояния:`."""
    idx = doc.find("Состояния:")
    if idx == -1:
        raise AssertionError("в докстринге artel.py нет строки «Состояния:»")
    return doc[:idx]


class HelpRegistryTest(unittest.TestCase):
    """Сверка справки с реестром — чистый разбор текста, без песочницы."""

    def test_ac3_every_registry_key_is_named_in_commands_block(self):
        """Каждый ключ реестра `table` назван в блоке «Команды:» словом команды.

        Ключи — из разбора исходника `artel.main`; вхождение `pin` внутри
        `pin-update` ключом `pin` не засчитывается. Отказ перечисляет все
        недостающие ключи.
        Ловит мутацию: в `table` добавили команду (или в справке удалили
        строку, например `guard <id> [<файл>]`), а справку не дописали —
        тест краснеет и называет ключ."""
        keys = registry_keys()
        self.assertIn("pin-update", keys, "разбор реестра не нашёл ключей")
        block = commands_block(artel.__doc__)
        missing = [k for k in keys if not mentioned_as_command(k, block)]
        self.assertEqual(missing, [],
                         "в блоке «Команды:» справки нет команд реестра: "
                         + ", ".join(missing))

    def test_ac4_every_command_word_of_help_is_a_registry_key(self):
        """Обратное направление: каждое слово команды блока «Команды:» — ключ `table`.

        Слово команды — первое слово строки с отступом ровно в два пробела
        и слово сразу после ` | `, если оно подходит под `[a-z][a-z0-9-]*`.
        Ловит мутацию: в справку дописали команду, которой нет в реестре
        (опечатка `plank-runs`, удалённая из `table` команда осталась в
        справке) — тест краснеет и называет слово."""
        keys = set(registry_keys())
        words = []
        for line in commands_block(artel.__doc__):
            if line.startswith("  ") and not line.startswith("   "):
                words.append(line.split()[0])
            for tail in line.split(" | ")[1:]:
                parts = tail.split()
                if parts:
                    words.append(parts[0])
        named = [w for w in words if KEY_WORD.fullmatch(w)]
        self.assertTrue(named, "в блоке «Команды:» не найдено ни одной команды")
        unknown = sorted({w for w in named if w not in keys})
        self.assertEqual(unknown, [],
                         "справка называет команды, которых нет в реестре: "
                         + ", ".join(unknown))

    def test_ac5_header_names_gates_without_phase_zero(self):
        """Шапка докстринга до `Состояния:` называет гейты и не говорит «Фаза 0».

        Нужны `spec_gate`, `acceptance`, `merge_gate`, «ручн», «автогейт»,
        `gates.yaml`; политика гейтов из `gates.yaml` не читается.
        Ловит мутацию: шапку оставили «Артель, Фаза 0 … Все гейты Фазы 0 —
        ручные» либо переписали без упоминания автогейта `acceptance`."""
        text = header(artel.__doc__)
        for needle in ("spec_gate", "acceptance", "merge_gate", "ручн",
                       "автогейт", "gates.yaml"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text, f"шапка справки без {needle!r}")
        for banned in ("Фаза 0", "Фазы 0"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text, f"шапка справки несёт {banned!r}")


class PinUpdateSecondShaTest(SyncedOriginConnSandbox):
    """Связка «диспетчер `main` — `pin-update` — git»: главная копия на
    старом sha, в `origin` — коммит поверх него, remote-tracking ref — на
    старом sha (любой `fetch` сдвинул бы его)."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        (self.root / "pin_target.txt").write_text(f"{self.seed}\n",
                                                  encoding="utf-8")
        self.git("add", "pin_target.txt")
        self.git("commit", "-q", "-m", "целевой коммит main")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.old = self.git("rev-parse", "HEAD").strip()
        self.tracking = f"refs/remotes/origin/{config.MAIN_BRANCH}"
        self.git("update-ref", self.tracking, self.old)

    def random_sha(self) -> str:
        return "".join(self.rng.choice("0123456789abcdef") for _ in range(40))

    def run_main(self, *args):
        """`artel.py <args>` из окружения Оператора со шпионом
        `pin.cmd_pin_update`; (текст выхода, исключение выхода, шпион)."""
        env = {k: v for k, v in os.environ.items()
               if k not in (config.ARTEL_ROLE_ENV, "HOME")}
        spy = mock.Mock()
        exc = None
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *args]), \
                mock.patch.object(pin, "cmd_pin_update", spy), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as e:
                exc = e
        return out.getvalue(), exc, spy

    def test_ac7_second_sha_refused_without_fetch(self):
        """`pin-update <sha1> <sha2>` с двумя полными sha — отказ, называющий `<sha2>`.

        Пары sha случайные (одна — с настоящим целевым sha первым);
        текст отказа «pin-update: неизвестный аргумент <sha2>» и строка
        использования `artel.py pin-update <sha> [--wait-ci]`; шпион
        `pin.cmd_pin_update` не вызван, remote-tracking ref не сдвинут.
        Ловит мутацию: диспетчер берёт первый позиционный аргумент как sha
        и молча отбрасывает лишние — команда уходит в `cmd_pin_update` и
        `fetch`; либо отказ называет не тот аргумент."""
        pairs = [(self.target, self.random_sha()),
                 (self.random_sha(), self.random_sha()),
                 (self.random_sha(), self.target)]
        for sha1, sha2 in pairs:
            with self.subTest(sha1=sha1, sha2=sha2):
                ctx = f"зерно: {self.seed}; pin-update {sha1} {sha2}"
                text, exc, spy = self.run_main("pin-update", sha1, sha2)
                self.assertIsNotNone(exc, f"{ctx}: ожидался отказ; {text}")
                self.assertIsInstance(exc.code, str, f"{ctx}: {exc.code!r}")
                self.assertTrue(
                    exc.code.startswith(
                        f"pin-update: неизвестный аргумент {sha2}"),
                    f"{ctx}: {exc.code}")
                self.assertIn("artel.py pin-update <sha> [--wait-ci]",
                              exc.code, f"{ctx}: нет строки использования")
                spy.assert_not_called()
                self.assertEqual(
                    self.git("rev-parse", self.tracking).strip(), self.old,
                    f"{ctx}: был git fetch")


if __name__ == "__main__":
    unittest.main()
