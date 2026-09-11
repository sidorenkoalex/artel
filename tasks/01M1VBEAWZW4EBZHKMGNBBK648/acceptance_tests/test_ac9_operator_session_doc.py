"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-9 (SPEC.md).

Документ вне защищённых путей — правит разработчик тем же коммитом, что
и код (SPEC, «Материалы»/«Оценка объёма и деление» соседних задач по
аналогии; `docs/` не входит в `skills/`/`templates/`/`gates.yaml`/
`roles.yaml`/`.github/`). Тест — как `tasks/T073/acceptance_tests/
test_ac9_retention_doc_premod_mentioned_not_implemented.py`: чтение
текста раздела с диска, без импорта кода.

Красен до реализации: `test_ac9_section_describes_wait_zone_mode_
instead_of_external_watcher` — раздел «Запуски и рабочие копии» `docs/
operator-session.md` сегодня не упоминает `--wait-zone` вовсе (внешний
`zone_wait_auto.sh` не документирован в этом файле буквально ни разу —
`grep -r zone_wait_auto docs/` не находит совпадений уже сейчас, так что
предмет теста — не «убрать упоминание», а «добавить описание нового
режима» требования 7).

Зелёный с рождения: `test_ac9_section_exists` — раздел «Запуски и рабочие
копии» уже существует в документе сегодня; тест фиксирует предпосылку
остальных проверок файла, не предмет AC-9 самого по себе.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DOC = REPO_ROOT / "docs" / "operator-session.md"
SECTION_HEADING = "## Запуски и рабочие копии"


def _section_text() -> str:
    text = DOC.read_text(encoding="utf-8")
    start = text.index(SECTION_HEADING)
    rest = text[start + len(SECTION_HEADING):]
    match = re.search(r"\n## ", rest)
    end = match.start() if match else len(rest)
    return rest[:end]


class Ac9OperatorSessionDocDescribesWaitZoneTest(unittest.TestCase):

    def test_ac9_section_exists(self):
        """`docs/operator-session.md` несёт раздел «Запуски и рабочие
        копии» — предпосылка остальных проверок этого файла; падение
        здесь означает, что раздел переименован/удалён, а не то, что
        требование 7 не выполнено.

        Ловит мутацию: заголовок раздела случайно переименован при
        правке этим же коммитом (например «Запуски и worktree») — не
        предмет AC-9, но остальные assert'ы файла давали бы ложный
        `ValueError` из `_section_text` вместо внятного диагноза.
        """
        self.assertIn(SECTION_HEADING, DOC.read_text(encoding="utf-8"))

    def test_ac9_section_describes_wait_zone_mode_instead_of_external_watcher(self):
        """Раздел «Запуски и рабочие копии» описывает режим `--wait-zone`
        — внешний ожидатель зоны (`zone_wait_auto.sh`-подобный сценарий)
        Оператору больше не нужен (SPEC, требование 7, буквально).

        Ловит мутацию: раздел правится ЧЕМ-ТО ДРУГИМ этим же коммитом
        (правка соседней строки того же раздела), но упоминание
        `--wait-zone` не добавляется вовсе — Оператор, читающий этот
        документ, продолжил бы искать/заводить внешний скрипт-ожидатель,
        хотя штатная поддержка уже смержена (SPEC «Контекст»: 9 обходов
        за 05–06.09 — ровно то, что должно перестать повторяться).
        """
        section = _section_text().lower()
        self.assertIn(
            "wait-zone", section,
            "раздел «Запуски и рабочие копии» не упоминает режим "
            "--wait-zone (SPEC требование 7)")


if __name__ == "__main__":
    unittest.main()
