"""Приёмочный тест AC-8 (SPEC 01M2B6K02YVJBWE1JDWP85EJH0): отчёт прогона
(заголовок `[canary] прогон <stamp>: ...` и итоговая строка задачи
«шагов=… исход=…») несёт целевой sha и пометку его происхождения:
«код пина» — целевой sha совпадает с `gitcmd.head_sha()` главной копии;
«код origin/main» — совпадает с головой `origin/<MAIN_BRANCH>` (и не
совпадает с HEAD главной копии); «код <sha>» — в остальных случаях.

Красен до реализации: `cmd_canary`/`_run_one_task` сегодня печатают
только `run_stamp`/число задач и метрики (`orchestrator/canary.py`,
строки ~1229 и ~1209-1215) — ни sha, ни одна из трёх пометок нигде в
выводе не появляются.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TargetShaCanarySandbox  # noqa: E402


def _assert_sha_present(test, line: str, sha: str) -> None:
    """Sha в отчёте может быть напечатан полностью или сокращённо
    (`sha[:7]`, обычный приём остального кода — см. `pin.py`) — критерий
    не фиксирует формат буквально, тест принимает оба."""
    test.assertTrue(sha in line or sha[:7] in line, line)


class ReportPinSourceLabelTest(TargetShaCanarySandbox):

    def test_ac8_label_is_pin_code_when_target_sha_equals_local_head(self):
        """Целевой sha передан явно и совпадает с `gitcmd.head_sha()`
        главной копии — заголовок и итоговая строка прогона несут sha и
        пометку «код пина» (приоритет над «код origin/main», даже когда
        стенд синхронен и оба совпадения истинны одновременно — AC-8
        перечисляет «код пина» первым).

        Ловит мутацию: пометка вычисляется без сравнения с локальным
        HEAD вовсе (например, всегда «код origin/main» либо всегда «код
        <sha>») — «код пина» не появился бы в выводе, хотя целевой sha
        буквально равен HEAD главной копии.
        """
        pin_sha = self.head_sha()

        out, _ = self.run_cmd_canary(sha=pin_sha)

        header = next(l for l in out.splitlines() if l.startswith("[canary] прогон"))
        summary = next(l for l in out.splitlines() if "шагов=" in l and "исход=" in l)
        for line in (header, summary):
            _assert_sha_present(self, line, pin_sha)
            self.assertIn("код пина", line, line)

    def test_ac8_label_is_origin_main_code_when_target_sha_is_origin_head_but_differs_from_pin(self):
        """`origin/<MAIN_BRANCH>` ушёл вперёд локального `main` (пина) —
        целевой sha по умолчанию (голова `origin/<MAIN_BRANCH>`, AC-1)
        несёт пометку «код origin/main», не «код пина» и не «код <sha>».

        Ловит мутацию: пометка «код пина» ставится всегда, когда прогон
        идёт БЕЗ явного `--sha` (спутано «по умолчанию» с «совпадает с
        HEAD главной копии») — вывод нёс бы «код пина» вместо «код
        origin/main», хотя целевой sha от HEAD главной копии как раз
        разошёлся.
        """
        pin_sha = self.head_sha()
        origin_sha = self.advance_origin_only()
        self.assertNotEqual(pin_sha, origin_sha)

        out, _ = self.run_cmd_canary(sha=None)

        header = next(l for l in out.splitlines() if l.startswith("[canary] прогон"))
        summary = next(l for l in out.splitlines() if "шагов=" in l and "исход=" in l)
        for line in (header, summary):
            _assert_sha_present(self, line, origin_sha)
            self.assertIn("код origin/main", line, line)
            self.assertNotIn("код пина", line, line)

    def test_ac8_label_is_bare_sha_code_when_target_sha_is_neither_pin_nor_origin_head(self):
        """Явный `--sha`, отличный и от HEAD главной копии, и от головы
        `origin/<MAIN_BRANCH>` (предок текущего main) — пометка «код
        <sha>» с самим этим sha, не «код пина»/«код origin/main».

        Ловит мутацию: третья ветка (`else`) не реализована — любой sha,
        не совпавший с двумя первыми случаями, ошибочно получил бы одну
        из их пометок вместо «код <sha>» с буквальным значением sha.
        """
        explicit_sha = self.root_sha
        self.assertNotEqual(explicit_sha, self.head_sha())
        self.assertNotEqual(explicit_sha, self.origin_head_sha())

        out, _ = self.run_cmd_canary(sha=explicit_sha)

        header = next(l for l in out.splitlines() if l.startswith("[canary] прогон"))
        summary = next(l for l in out.splitlines() if "шагов=" in l and "исход=" in l)
        for line in (header, summary):
            self.assertTrue(
                f"код {explicit_sha}" in line or f"код {explicit_sha[:7]}" in line,
                line)
            self.assertNotIn("код пина", line, line)
            self.assertNotIn("код origin/main", line, line)


if __name__ == "__main__":
    import unittest
    unittest.main()
