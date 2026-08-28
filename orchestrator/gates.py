"""Политика гейтов из `gates.yaml` (ADR-0007, SPEC T066).

Читается ТОЛЬКО из главной копии пульта (`config.ROOT`), никогда с ветки
или из worktree задачи: `gates.yaml` — конфиг системы (`PROTECTED_PATHS`),
и задача не имеет права подсунуть себе выгодную политику собственной
веткой. Меняет файл только Оператор отдельным MR (skills/conventions-core.md).

Дефолт — `manual` (fail-closed, требование 1): неизвестное значение
политики, отсутствие секции `gates:`, отсутствующий или нечитаемый
`gates.yaml` — всё сводится к «гейт ручной», не к отказу чтения. Только
буквальное значение `auto` даёт автогейту ход.
"""
from . import config, yamlmini

GATES_FILE_REL = "gates.yaml"
AUTO = "auto"
MANUAL = "manual"


def _policy_map() -> dict:
    """Секция `gates:` файла или `{}` — любой недочёт (файла нет, не
    прочитан, не разобран, секции нет) вырождается в пустое отображение:
    `policy()` ниже уже трактует отсутствие ключа как `manual`."""
    path = config.ROOT / GATES_FILE_REL
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        parsed = yamlmini.mapping(text)
    except yamlmini.YamlError:
        return {}
    gates = parsed.get("gates")
    return gates if isinstance(gates, dict) else {}


def policy(gate: str) -> str:
    """Политика гейта `gate`: буквально `auto`, иначе `manual`."""
    return AUTO if _policy_map().get(gate) == AUTO else MANUAL
