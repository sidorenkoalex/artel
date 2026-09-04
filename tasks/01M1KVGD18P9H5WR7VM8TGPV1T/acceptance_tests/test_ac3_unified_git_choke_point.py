"""AC-3 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md): «Все прямые вызовы
subprocess.run с cwd=config.ROOT в artifact_branch.write_commit,
commit_files, snapshot и пине идут через единый модуль, который tests/
sandbox.py подменяет одним патчем по умолчанию для всех наследников
базовых классов.»

Структурная (по исходному тексту) проверка — тот же способ, которым
требование 3 SPEC само предлагает проверять соседний пункт («grep по
tests/ и tasks/*/acceptance_tests/»): критерий описывает свойство КОДА
(какой модуль зовёт `subprocess.run`), не поведение, наблюдаемое только
на рантайме. Рантайм-поведение `artifact_branch.commit_files` под
`tests.sandbox.TmpRootTest` УЖЕ безопасно сегодня — не потому, что
критерий выполнен, а потому что `subprocess` — общий модуль-синглтон, и
патч `gitcmd.subprocess.run` (SpyRun) неявно перехватывает и вызовы
`artifact_branch.py`, использующие тот же `import subprocess` (см.
`test_ac3_sandbox_default_covers_carpentry.py`, отдельный «зелёный с
рождения» файл: то же наблюдение, но не различает «работает по
случайности синглтона» от «спроектировано как единая точка подмены» —
только исходный текст различает эти два случая, отсюда структурная, а
не поведенческая проверка здесь).

Красен до реализации: сегодня `orchestrator/artifact_branch.py` зовёт
`subprocess.run` напрямую пять раз (`write_commit`: read-tree,
hash-object, update-index, write-tree, commit-tree; `commit_files`:
update-ref) — ни разу через `gitcmd`. Эмпирически подтверждено grep'ом
при подготовке этой планки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config  # noqa: E402

# Требование 2/3 называет эти три модуля явно.
CARPENTRY_FILES = ("artifact_branch.py", "snapshot.py", "pin.py")
RAW_CALL_MARKERS = ("subprocess.run(", "subprocess.Popen(")


class Ac3NoRawSubprocessInCarpentryModulesTest(unittest.TestCase):

    def test_ac3_carpentry_modules_have_no_raw_subprocess_calls(self):
        """`orchestrator/artifact_branch.py`, `snapshot.py`, `pin.py` не
        содержат буквальных вызовов `subprocess.run(`/`subprocess.Popen(`
        — вся плотницкая git-работа этих модулей идёт через единый
        модуль (`gitcmd` либо новый тонкий слой), не напрямую.

        Ловит мутацию: `write_commit`/`commit_files` (или любой из
        плотницких вызовов внутри них) оставлен звать `subprocess.run`
        напрямую вместо делегирования единому модулю — grep находит
        литеральный вызов, тест падает.
        """
        offenders = {}
        for name in CARPENTRY_FILES:
            src = (config.ROOT / "orchestrator" / name).read_text(encoding="utf-8")
            hits = [ln.strip() for ln in src.splitlines()
                    if any(marker in ln for marker in RAW_CALL_MARKERS)]
            if hits:
                offenders[name] = hits
        self.assertEqual(
            {}, offenders,
            f"прямые вызовы subprocess.run/Popen вне единого модуля: {offenders}")


if __name__ == "__main__":
    unittest.main()
