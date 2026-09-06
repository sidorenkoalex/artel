"""Приёмочные тесты AC-5: `tests/test_fsm_map_conflict_autoresolve.py` и
`tests/test_branch_freshness_gate.py` переведены на эталон `tests/
sandbox.py` (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J, требование 2).

Красен до реализации: оба файла сегодня определяют собственные
`write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev`
локально, а их основные тестовые классы наследуют голый
`unittest.TestCase`, не эталон — регэксп-проверка «нет локальной копии»
и проверка наследования падают.
"""
import hashlib
import importlib
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox as plank  # noqa: E402

TARGET_MODULES = {
    "tests.test_fsm_map_conflict_autoresolve": "MapConflictAutoResolveTest",
    "tests.test_branch_freshness_gate": "BranchFreshnessGateTest",
}

OWN_COPY_PATTERN = re.compile(
    r"^\s*def\s+(write_plan_ready|write_acceptance_plank|"
    r"advance_from_in_dev)\s*\(", re.M)

MUTATION_DOCSTRING_BLOCK = re.compile(r"Ловит мутацию.*?(?=\n\n|\"\"\")", re.S)

# Хеши точного текста докстрингов «Ловит мутацию» ДО перевода на эталон
# (требование 2 SPEC: «докстринги ... сохраняются дословно») — сняты тем
# же регэкспом выше с исходных файлов на момент написания этой планки
# (06.09, коммит ea0bba68).
EXPECTED_MUTATION_DOCSTRING_HASHES = {
    "tests/test_fsm_map_conflict_autoresolve.py":
        "9b15ee2a28d250d9203c460b1bfa21f68fb9dbcd10839cb40ce39feedda0ff62",
    "tests/test_branch_freshness_gate.py":
        "e712ef9f84bfc6b59a47e54b234f011afb374ab5dc64b21a5fb3f4a314522768",
}


class Ac5NoLocalCopiesTest(unittest.TestCase):

    def test_ac5_no_local_copies_of_sandbox_helpers(self):
        """Ни один из двух файлов не определяет собственные
        `write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev`.

        Ловит мутацию: файл сохраняет локальный `def write_plan_ready`
        рядом с наследованием от эталона (частичный перевод, дублирующий
        оба источника) — regex найдёт совпадение, `assertIsNone` ниже
        поймает регресс.
        """
        for rel in TARGET_MODULES:
            path = REPO_ROOT / rel.replace(".", "/")
            path = path.with_suffix(".py")
            text = path.read_text(encoding="utf-8")
            match = OWN_COPY_PATTERN.search(text)
            self.assertIsNone(
                match, f"{rel}: собственная копия помощника эталона "
                f"осталась: {match.group(0) if match else ''!r}")


class Ac5InheritsLightTransitionSandboxTest(unittest.TestCase):

    def test_ac5_test_classes_inherit_light_transition_sandbox(self):
        """Основные тестовые классы обоих файлов наследуют найденный
        эталонный класс лёгкой песочницы переходов `tests/sandbox.py`
        (AC-1), не голый `unittest.TestCase`.

        Ловит мутацию: класс продолжает наследовать голый
        `unittest.TestCase` вместо эталона (переезд ограничился только
        удалением локальных `def`, без реального наследования) —
        `assertTrue(issubclass(...))` ниже поймает несоответствие.
        """
        candidates = plank.find_light_transition_sandbox_classes()
        self.assertEqual(len(candidates), 1,
                         f"эталонный класс не найден однозначно (см. "
                         f"AC-1): {candidates}")
        base_cls = candidates[0]
        for mod_name, cls_name in TARGET_MODULES.items():
            module = importlib.import_module(mod_name)
            cls = getattr(module, cls_name)
            self.assertTrue(
                issubclass(cls, base_cls),
                f"{mod_name}.{cls_name} обязан наследовать эталон "
                f"{base_cls} из tests.sandbox")


class Ac5MutationDocstringsPreservedTest(unittest.TestCase):

    def test_ac5_mutation_catching_docstrings_are_preserved_verbatim(self):
        """Текст докстрингов-утверждений «Ловит мутацию: …» в обоих
        файлах не изменился ни на символ при переезде на эталон.

        Ловит мутацию: «попутная» правка формулировки одного из
        докстрингов «Ловит мутацию» при переносе `setUp` на эталон —
        хеш объединённого текста блоков перестанет совпадать с
        эталонным.
        """
        for rel, expected_hash in EXPECTED_MUTATION_DOCSTRING_HASHES.items():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            blocks = MUTATION_DOCSTRING_BLOCK.findall(text)
            digest = hashlib.sha256(
                "\x00".join(blocks).encode("utf-8")).hexdigest()
            self.assertEqual(
                digest, expected_hash,
                f"{rel}: текст докстрингов «Ловит мутацию» изменился "
                f"относительно версии до перевода на эталон")


class Ac5ExistingTestsStillPassTest(unittest.TestCase):

    def test_ac5_existing_tests_in_both_files_still_pass(self):
        """Полный набор тестов обоих файлов зелёный после перевода на
        эталон — те же сценарии, тот же исход, что и до рефакторинга.

        Ловит мутацию: перевод на эталон путает порядок/состав патчей
        `setUp` (например теряет патч `gitcmd.show` или `workspace.
        ensure`) — соответствующий сценарий покраснеет, и `returncode`
        ниже это поймает.
        """
        res = subprocess.run(
            [sys.executable, "-m", "unittest",
            "tests.test_fsm_map_conflict_autoresolve",
            "tests.test_branch_freshness_gate"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
