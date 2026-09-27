"""AC-15 — 01M3HST4SGX0SPKAGNHVY7DWHM: `doc-commit` документного пути
набор `tests/` не гоняет.

Источник — SPEC.md, «Критерии приёмки»:

AC-15. `doc-commit` пути `docs/**` набор `tests/` не гоняет: команда
доходит до коммита, не запуская прогон.

Наблюдаемость: в дерево прогона посеян набор, красный при ЛЮБОМ
содержимом дерева (`_sandbox.FAILING_SUITE`). Успешный коммит документа
поверх такого набора возможен только если прогона не было — отдельного
шпиона за вызовом конкретной функции пульта планка не ставит (какой
функцией разработчик гоняет набор, критерий не оговаривает).

Зелёный с рождения: сегодня `doc-commit` (:656) не гоняет набор ни для
одного пути, поэтому документный путь коммитит и сейчас — критерий
охраняет существующее поведение от расширения гейта требований 13-14 на
`docs/**`, и такой тест обязан быть зелёным до реализации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

NEW_ROADMAP = "# Роадмап\n\nНовый раздел.\n"


class DocsPathSkipsSuiteTest(_sandbox.NoteSandbox):

    def test_ac15_docs_path_commits_over_red_suite(self):
        """В дереве прогона лежит всегда-красный набор `tests/`;
        `doc-commit docs/roadmap.md --from … --message …` всё равно доводит
        новое содержимое до `origin/main`.

        Ловит мутацию: прогон набора поставлен на ВСЕ пути `doc-commit`
        (проверка `path in DOC_COMMIT_CONFIG_PATHS` забыта либо
        инвертирована) — документный путь отказывает по красному набору, и
        тест красен на `SystemExit` вместо коммита.
        """
        self.seed_suite(_sandbox.FAILING_SUITE)
        source = self.source_file(NEW_ROADMAP, "roadmap-draft.md")

        self.doc_commit(_sandbox.DOC_REL, "--from", str(source),
                        "--message", "перенос раздела")

        self.assertEqual(self.origin_show(_sandbox.DOC_REL), NEW_ROADMAP)


if __name__ == "__main__":
    unittest.main()
