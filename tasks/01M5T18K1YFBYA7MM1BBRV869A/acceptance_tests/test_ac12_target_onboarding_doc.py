"""Документ порядка подключения внешнего проекта `docs/target-onboarding.md`
в рабочей копии кода задачи.

Группа: разовый

Красен до реализации: документа `docs/target-onboarding.md` в репозитории ещё нет — проверка существования файла падает.

Документ читается из рабочей копии кода (`_pult.CODE_ROOT`); пункт порядка
требования 9 ищется в его тексте регулярным выражением без учёта регистра
(основа слова — чтобы склонение не влияло).
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

DOC_REL = ("docs", "target-onboarding.md")

ONBOARDING_TERMS = [
    ("шаг разбора", r"разбор"), ("ИИ-настройки проекта", r"ИИ-настро"),
    ("как текст", r"текст"),
    ("стек", r"стек"), ("архитектура", r"архитектур"), ("слои", r"сло[иёея]"),
    ("стиль кода", r"стил[ья] кода"), ("команды тестов", r"тест"),
    ("линтеры", r"линтер"), ("миграции", r"миграци"),
    ("именование", r"именовани"), ("команды запуска обвязки", r"обвязк"),
    ("commit", r"commit"), ("push", r"push"), ("роли", r"рол[иьея]"),
    ("ревью", r"ревью"), ("хуки", r"хук"), ("MCP", r"MCP"),
    ("разрешения", r"разрешени"),
    ("путь файла пульта", re.escape(".artel/projects/<имя>/conventions.md")),
    ("команда отметки", r"conventions-stamp"), ("doctor", r"doctor"),
    ("предупреждение дрейфа", r"дрейф|изменились с последнего разбора"),
]


@pytest.mark.parametrize("what,pattern", ONBOARDING_TERMS)
def test_ac12_onboarding_document_describes_procedure(what, pattern):
    """Документ `docs/target-onboarding.md` рабочей копии кода задачи.

    Существует и называет каждый пункт порядка требования 9: шаг разбора
    ИИ-настроек проекта как текста; каждое выбираемое (стек, архитектура и
    слои, стиль кода, команды тестов и линтеров, миграции, именование) и
    каждое отбрасываемое (команды запуска обвязки, commit/push, роли,
    ревью, хуки, MCP, разрешения); путь
    `.artel/projects/<имя>/conventions.md`; команду `conventions-stamp`;
    действие при предупреждении дрейфа `doctor`.

    Ловит мутацию: документ не заведён или из него выпал пункт — перечень
    отбрасываемого без MCP и разрешений, без пути файла пульта или без
    команды отметки."""
    path = Path(CODE_ROOT).joinpath(*DOC_REL)
    assert path.is_file(), f"нет {path}"
    text = path.read_text(encoding="utf-8")
    assert re.search(pattern, text, flags=re.I), (
        f"{path}: нет пункта «{what}» (/{pattern}/)")
