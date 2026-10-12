"""AC-1 (текстовая часть): комментарий над белым списком команд роли и
справка модуля `orchestrator/artel.py`.

Поведенческая часть AC-1 (белый список под окружением роли, сверка `<id>`
с `ARTEL_TASK`, отказ по дому роли и неизвестной задаче) — в долгоживущем
файле `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py`
(`RoleWhitelistTest`). Здесь — факт формулировки комментария и справки,
которые эта задача меняет: текст исходника кода ветки, не артефакт задачи.

Группа: разовый
Красен до реализации: комментарий над _ROLE_ALLOWED_COMMANDS говорит «только чтение» и что suite-run «журнала не трогает», а справка artel.py не называет команду knowledge.
"""
import re
import unittest
from pathlib import Path

from orchestrator import artel

ASSIGNMENT = "_ROLE_ALLOWED_COMMANDS = "
EXPECTED = ("только чтение, кроме досыла очереди журнала у suite-run и одной "
            "записи журнала команды knowledge")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def comment_above_whitelist() -> str:
    lines = Path(artel.__file__).read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines)
                 if line.startswith(ASSIGNMENT))
    block = []
    for line in reversed(lines[:index]):
        stripped = line.strip()
        if not stripped.startswith("#"):
            break
        block.append(stripped.lstrip("#:").strip())
    return normalized(" ".join(reversed(block)))


class WhitelistCommentTest(unittest.TestCase):

    def test_ac1_comment_allows_both_journal_writes(self):
        """Комментарий над присваиванием `_ROLE_ALLOWED_COMMANDS` в исходнике
        `orchestrator/artel.py`, без обратных кавычек и переносов.

        Наблюдение: несёт фразу «только чтение, кроме досыла очереди журнала
        у `suite-run` и одной записи журнала команды `knowledge`» и не несёт
        утверждения, что журнал не трогается.

        Ловит мутацию: комментарий поправлен только словом о `knowledge`, а
        фраза о `suite-run` «состояния задачи, lease и журнала не трогает»
        осталась — находится «журнала не трогает».
        """
        comment = comment_above_whitelist()
        self.assertIn(EXPECTED, comment, comment)
        self.assertNotRegex(comment, r"журнал\w*\s+не\s+трогает")

    def test_ac1_module_help_names_knowledge_command(self):
        """Справка модуля — докстринг `artel.py`, который печатает `artel.py
        --help`.

        Наблюдение: в справке есть строка о команде `knowledge` (форма
        вызова `knowledge <…>` или имя команды в обратных кавычках), а не
        только прежнее слово «knowledge» в перечне каталогов области
        проекта.

        Ловит мутацию: команда заведена в диспетчер, но справку не
        дописали — строки о команде нет.
        """
        doc = artel.__doc__ or ""
        # `\b` — не «observe acknowledge <observation-id>» прежней справки.
        self.assertRegex(doc, r"\bknowledge\s*<|`knowledge[` ]")


if __name__ == "__main__":
    unittest.main()
