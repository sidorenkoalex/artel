"""AC-3 — 01M3KE8ZJXFARS6KC441PCDCQV: снимаемая модель ушла и из каталога,
и из всех ссылающихся путей.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Записи `gpt-5.5` в `models.yaml` нет, и строку `gpt-5.5` не несёт
ни один файл `orchestrator/`, `roles.yaml`, `docs/reference/models-local.example.yaml`
и `tests/`.

Обе половины критерия читаются в дереве ветки: запись — из каталога
ВЕТКИ (`models.yaml` рабочей копии), ссылки — из исходников. Редакция 2
планки по ANSWER-1, вопрос 1, вариант (а): прежняя редакция брала
каталог результатом применения приложения PLAN к базе сравнения и
дополнительно требовала, чтобы снимаемая запись в БАЗЕ была, — коммит
`ae3370c5` сделал оба утверждения неисполнимыми (докстринг
`_catalog.py`). Проверяемое свойство то же: записи `gpt-5.5` нет ни в
каталоге, ни в путях критерия.

Красен до реализации: половина про каталог падает, пока запись `gpt-5.5`
в `models.yaml` стоит; половина про ссылки падает на
`tests/test_models.py`, где литерал состава каталога (строки 141, 145)
по-прежнему называет снимаемую модель.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

#: Пути, которые критерий обязывает очистить от ссылок. Каталоги
#: обходятся целиком: критерий говорит «ни один файл `orchestrator/`».
SCANNED_DIRS = ("orchestrator", "tests")
SCANNED_FILES = ("roles.yaml", "docs/reference/models-local.example.yaml")


def _scanned_sources() -> list:
    """[(путь относительно корня, текст)] по путям критерия. `__pycache__`
    пропускается: это не файл репозитория, а след прогона."""
    out = []
    for name in SCANNED_DIRS:
        for path in sorted((_catalog.REPO_ROOT / name).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            out.append((path.relative_to(_catalog.REPO_ROOT).as_posix(),
                        path.read_text(encoding="utf-8", errors="ignore")))
    for rel in SCANNED_FILES:
        path = _catalog.REPO_ROOT / rel
        if path.is_file():
            out.append((rel, path.read_text(encoding="utf-8")))
    return out


class WithdrawnModelTest(unittest.TestCase):

    def test_ac3_branch_catalog_has_no_withdrawn_record(self):
        """Каталог ветки не несёт записи `gpt-5.5` — ни в разделе
        `codex`, ни в общем индексе моделей.

        Ловит мутацию: правка добавила три записи, но снять четвёртую
        забыла — модель, которую клиент Codex убирает 14.10.2026,
        осталась бы разрешимой целью яруса, и шаг на ней стартовал бы
        ровно до дня снятия.
        """
        catalog = _catalog.catalog().catalog

        self.assertIn(_catalog.WITHDRAWN_MODEL, _catalog.PREVIOUS_PRICES,
                      "снимаемая запись обязана стоять в снимке каталога "
                      "ДО правки — иначе проверка снятия ничего не "
                      "проверяет")
        self.assertNotIn(_catalog.WITHDRAWN_MODEL, catalog.models)
        self.assertNotIn(_catalog.WITHDRAWN_MODEL,
                         catalog.providers["codex"].models)

    def test_ac3_no_scanned_file_mentions_the_withdrawn_model(self):
        """Ни один файл `orchestrator/`, `tests/`, `roles.yaml` и образца
        локального слоя не несёт строки `gpt-5.5`.

        Ловит мутацию: литерал состава каталога в `tests/test_models.py`
        приведён к новому составу в разделе `codex`, а в ОБЩЕМ перечне
        (там же, ниже) снимаемая модель осталась — перечни разошлись бы
        между собой, и набор покраснел бы уже на мерже, когда приложение
        каталога ляжет в main.
        """
        hits = [f"{rel}:{number}"
                for rel, text in _scanned_sources()
                for number, line in enumerate(text.splitlines(), 1)
                if _catalog.WITHDRAWN_MODEL in line]

        self.assertEqual(
            [], hits,
            f"строка {_catalog.WITHDRAWN_MODEL} осталась в: "
            f"{', '.join(hits)}")


if __name__ == "__main__":
    unittest.main()
