"""AC-12, AC-13: документация описывает вход по подписке, а не слот
ключа — `AGENTS.md` курируемого дома роли и раздел «Провайдер codex»
в `docs/stack.md`.

Красен до реализации: `docs/reference/role-home/codex/AGENTS.md` несёт
абзац «ключ приходит переменной окружения OPENAI_API_KEY из отдельного
слота keychain пульта», а раздел «Провайдер codex» в `docs/stack.md` —
подраздел «Слот ключа» с командой `security add-generic-password` и
строку `codex-api-key` в перечне зелёных строк `doctor`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import guard  # noqa: E402


class AgentsReferenceTest(unittest.TestCase):
    """Абзац об авторизации в `AGENTS.md` дома роли — требование 6."""

    def setUp(self):
        self.text = _util.codex_reference("AGENTS.md").read_text(
            encoding="utf-8")

    def test_ac12_agents_md_describes_the_chatgpt_login_and_no_key_channel(self):
        """Файл говорит про вход ChatGPT, про то, что токены хранит и
        обновляет сам CLI, и про то, что личный вход Оператора и ключи API
        роль не получает; описания `OPENAI_API_KEY` или слота keychain как
        канала секрета роли в нём нет.

        Ловит мутацию: правка сделана в коде, а `AGENTS.md` оставлен как
        есть (или в нём заменена одна фраза про вход, но абзац про слот
        ключа остался рядом) — роль на Codex читает в собственном доме,
        что её секрет приходит переменной `OPENAI_API_KEY`, которой в
        окружении шага уже нет, и ищет причину отказа не там.
        """
        lowered = _util.squashed(self.text)

        self.assertIn("chatgpt", lowered)
        self.assertIn("хранит", lowered)
        self.assertTrue(
            any(word in lowered for word in ("обновля", "продлева", "освежа")),
            "не сказано, что токены обновляет сам CLI")
        self.assertIn("не получает", lowered)
        for absent in ("OPENAI_API_KEY", _util.SLOT_RECORD_NAME,
                       _util.SLOT_CONST_NAME):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, self.text)


class StackDocSectionTest(unittest.TestCase):
    """Раздел «Провайдер codex» в `docs/stack.md` — требование 7."""

    def setUp(self):
        text = _util.STACK_DOC.read_text(encoding="utf-8")
        self.section = guard.section_body(text, _util.STACK_DOC_SECTION)
        self.assertTrue(self.section.strip(),
                        f"раздел «{_util.STACK_DOC_SECTION}» не найден")

    def test_ac13_the_section_replaces_the_key_slot_with_the_subscription_login(self):
        """Раздел несёт вход по подписке: оба однократных шага Оператора
        (указатель связки ключей для дома роли на macOS и команда входа с
        домом роли), что хранится и как обновляется, когда нужен повторный
        вход и что исключено из окружения шага; перечень зелёных строк
        `doctor` при переводе роли несёт `codex-chatgpt-auth` и не несёт
        `codex-api-key`.

        Ловит мутацию: раздел переписан наполовину — про вход ChatGPT
        сказано, а указатель связки ключей не назван. Живая проверка 22.09
        показала, что без него вход в изолированном `HOME` не сохраняется
        (`persist_failed`): Оператор прошёл бы OAuth, получил красную
        строку `doctor` и не нашёл бы в документации шага, которого не
        хватает. Вторая мутация: в перечне зелёных строк `doctor` осталась
        `codex-api-key` — Оператор ждёт строку, которой пульт больше не
        печатает, и считает перевод роли незавершённым.
        """
        lowered = _util.squashed(self.section)

        self.assertIn("chatgpt", lowered)
        self.assertIn("default-keychain", lowered)
        self.assertIn("codex login", lowered)
        self.assertIn(_util.AUTH_CHECK, lowered)
        self.assertIn("хранит", lowered)
        self.assertTrue(
            any(word in lowered for word in ("обновля", "продлева", "освежа")),
            "не сказано, как обновляется вход")
        self.assertIn("повторн", lowered)
        self.assertIn("исключ", lowered)
        self.assertNotIn(_util.OLD_CHECK, lowered)
        self.assertNotIn(_util.SLOT_RECORD_NAME, lowered)


if __name__ == "__main__":
    unittest.main()
