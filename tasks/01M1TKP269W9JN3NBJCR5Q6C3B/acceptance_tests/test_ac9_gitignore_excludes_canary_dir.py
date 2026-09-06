"""AC-9 (SPEC.md), первая половина: `.artel/canary/` внесён в
`.gitignore` пульта — `git` игнорирует любой путь под этим каталогом.

Настоящий `git check-ignore` на РЕАЛЬНОМ `.gitignore` рабочей копии
(не песочница: правило .gitignore — свойство файла в этом самом
репозитории, а не поведение кода, которое имело бы смысл гонять в
изолированном временном git) — тот же приём, каким `.gitignore`
итак проверяется глазами на ревью, только автоматизированный.

Зелёный с рождения: сегодняшний `.gitignore` уже несёт блаженную
строку `.artel/` (без уточнения подкаталога) — она покрывает
`.artel/canary/` как любой другой подкаталог `.artel/` уже сейчас, до
единой правки этой задачи. Тест фиксирует уже верное, а не новое
поведение (доосторожно — на случай, если разработчик СУЗИТ `.artel/`
до списка конкретных подкаталогов вроде `.artel/logs/`, `.artel/
worktrees/` и по невнимательности не добавит в этот список `.artel/
canary/`).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class GitignoreExcludesCanaryDirTest(unittest.TestCase):

    def _is_ignored(self, rel_path: str) -> bool:
        res = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=REPO_ROOT, stdin=subprocess.DEVNULL, capture_output=True)
        return res.returncode == 0

    def test_ac9_canary_diagnostics_path_is_gitignored(self):
        """Правдоподобный путь диагностики (`.artel/canary/<run_stamp>/
        <task_id>/steps.txt`, формат AC-1) — `git check-ignore` считает
        его игнорируемым; путь не обязан существовать на диске, правило
        `.gitignore` — чисто текстовый паттерн.

        Ловит мутацию: разработчик СУЖАЕТ существующую строку `.artel/`
        до перечисления конкретных подкаталогов (например, `.artel/
        logs/`, `.artel/worktrees/`, `.artel/state.db`) и забывает
        включить в список `.artel/canary/` — путь диагностики перестал
        бы быть игнорируемым.
        """
        self.assertTrue(
            self._is_ignored(
                ".artel/canary/20260101T000000Z/T900/steps.txt"),
            "путь диагностики канарейки не игнорируется git")

    def test_ac9_canary_dir_itself_is_gitignored(self):
        """Сам каталог `.artel/canary/` (без содержимого) — тоже
        игнорируется, не только файлы внутри него.

        Ловит мутацию: правило .gitignore адресует только файлы
        определённого расширения внутри `.artel/canary/` (например,
        `.artel/canary/**/*.log`), не сам каталог целиком — сохранённые
        файлы без такого расширения (например, `steps.txt`, `PLAN.md`)
        просочились бы в `git status`/автокоммит.
        """
        self.assertTrue(
            self._is_ignored(".artel/canary/"),
            "каталог .artel/canary/ сам по себе не игнорируется git")


if __name__ == "__main__":
    unittest.main()
