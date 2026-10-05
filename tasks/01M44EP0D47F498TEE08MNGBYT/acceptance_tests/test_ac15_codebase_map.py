"""Карта кодовой базы описывает поле `merge_after` (AC-15).

Группа: разовый
Красен до реализации: ни один докстринг модуля orchestrator/ не называет merge_after в первой строке, а закоммиченная карта не несёт новых файлов tests/ задачи — генератор даёт другой текст.

Корень кода — корень git-дерева рабочего каталога прогона
(`scripts/codebase_map.py::repo_root` от cwd: планку гоняют из рабочей
копии кода задачи). Текст карты строится теми же публичными функциями
генератора (`build_modules` + `render`), что исполняет `python3
scripts/codebase_map.py`, без записи на диск. «Закоммиченная карта» —
`docs/codebase-map.md` головы ветки (`git show HEAD:…`); сверка — без
строки `built_at_sha`, тем же правилом, что шаг свежести карты в CI.
"""
import re
import subprocess
import unittest
from pathlib import Path

from scripts import codebase_map

MAP_REL = "docs/codebase-map.md"


def code_root() -> Path:
    return codebase_map.repo_root(Path.cwd())


def generated_map(root: Path) -> str:
    modules, resolved_imports, imported_by = codebase_map.build_modules(root)
    return codebase_map.render(modules, resolved_imports, imported_by,
                               "0" * 40)


def without_sha(text: str) -> list[str]:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def purposes(map_text: str) -> dict[str, str]:
    """{путь модуля: строка «Назначение»} по секциям `## <путь>` карты."""
    found = {}
    for section in re.split(r"^## ", map_text, flags=re.M)[1:]:
        path, _, body = section.partition("\n")
        match = re.search(r"^\*\*Назначение:\*\*(.*)$", body, re.M)
        if match:
            found[path.strip()] = match.group(1)
    return found


class CodebaseMapMergeAfterTest(unittest.TestCase):

    def test_ac15_purpose_of_an_orchestrator_module_names_merge_after(self):
        """Строка «Назначение» хотя бы одного раздела `orchestrator/` карты называет `merge_after`.

        Сценарий: карта строится генератором по текущему дереву кода; среди
        разделов модулей `orchestrator/` есть такой, чья строка
        «Назначение» (первая строка докстринга модуля) содержит
        `merge_after`.

        Ловит мутацию: описание поля добавлено в карту ручной правкой
        `docs/codebase-map.md` (или в глубину докстринга, не в первую
        строку) — генератор его не воспроизводит, строки нет.
        """
        found = {path: text for path, text in purposes(generated_map(code_root())).items()
                 if path.startswith("orchestrator/") and "merge_after" in text}

        self.assertTrue(found, "ни одна строка «Назначение» модулей "
                               "orchestrator/ не называет merge_after")

    def test_ac15_committed_map_matches_generator_output(self):
        """Закоммиченная карта совпадает с выводом генератора (без строки `built_at_sha`).

        Сценарий: `docs/codebase-map.md` головы ветки задачи сравнивается
        построчно с текстом, который генератор строит по дереву кода
        сейчас.

        Ловит мутацию: докстринг модуля поправлен без регенерации карты
        (или карта поправлена руками) — закоммиченный текст расходится с
        выводом генератора.
        """
        root = code_root()
        committed = subprocess.run(
            ["git", "show", f"HEAD:{MAP_REL}"], cwd=root,
            capture_output=True, text=True)
        self.assertEqual(committed.returncode, 0, committed.stderr)

        self.assertEqual(without_sha(committed.stdout),
                         without_sha(generated_map(root)),
                         "закоммиченная карта стухла — регенерируй "
                         "python3 scripts/codebase_map.py")


if __name__ == "__main__":
    unittest.main()
