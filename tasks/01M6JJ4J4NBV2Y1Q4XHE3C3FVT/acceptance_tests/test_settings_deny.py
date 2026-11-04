"""AC-18: запрет `Bash(git clean:*)` в курируемом `settings.json` HOME роли.

Группа: разовый
Предмет — содержимое живого файла репозитория
`docs/reference/role-home/claude/settings.json` кодовой ветки, а правило
долгоживущих файлов `tests/` запрещает читать живые файлы репозитория;
поэтому файл — в планке. Корень кода — `CODE_ROOT` помощника пульта
`_pult.py`.

Красен до реализации: в `permissions.deny` курируемого `settings.json` строки `Bash(git clean:*)` ещё нет.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402


def test_ac18_curated_settings_deny_git_clean():
    """Курируемый `settings.json` — валидный JSON с `Bash(git clean:*)` в `permissions.deny`.

    Ловит мутацию: строка запрета добавлена в `allow` вместо `deny` или с
    другой формой (`Bash(git clean *)`) — её нет среди `permissions.deny`;
    правка ломает JSON — `json.loads` падает.
    """
    settings = Path(CODE_ROOT) / "docs" / "reference" / "role-home" / "claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))

    assert "Bash(git clean:*)" in data["permissions"]["deny"]
