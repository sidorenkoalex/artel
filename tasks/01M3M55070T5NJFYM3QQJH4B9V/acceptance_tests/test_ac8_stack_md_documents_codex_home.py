"""AC-8: раздел «Провайдер codex» в `docs/stack.md` несёт одно-два
предложения о поиске входа по пути `CODEX_HOME` и о том, как эфемерный
клон канарейки получает путь дома роли пульта.

Красен до реализации: сегодня в разделе нет ни одного абзаца, где
`CODEX_HOME` стоял бы рядом и с клоном, и с пультом — про `CODEX_HOME`
раздел говорит в абзацах про дом роли и про исключённые имена, а про
эфемерный клон — в абзаце про указатель связки ключей, где `CODEX_HOME` не
упомянут вовсе.

Абзац, а не файл целиком, — потому что одно-два предложения критерия живут
одним абзацем: россыпь тех же слов по разным абзацам раздела означала бы,
что связки «вход ищется по `CODEX_HOME`» -> «клон получает путь пульта»
читатель по-прежнему не видит.

Ни клиент Codex, ни связка ключей здесь не при чём: тест читает текст
документа.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

#: Заголовок раздела и его границы в `docs/stack.md`.
SECTION_RE = re.compile(r"^##\s+Провайдер codex\s*$(.*?)(?=^##\s|\Z)",
                        re.M | re.S)

#: Корни слов, которыми абзац обязан назвать обе стороны переноса. Корни, а
#: не словоформы: падеж выбирает автор текста, критерий — нет.
CLONE_ROOT = "клон"
PULT_ROOT = "пульт"


class StackMdCodexHomeTest(unittest.TestCase):
    """AC-8: раздел «Провайдер codex» документа стека."""

    def section(self) -> str:
        text = (config.ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
        match = SECTION_RE.search(text)
        self.assertIsNotNone(match, "в docs/stack.md нет раздела «Провайдер codex»")
        return match.group(1)

    def test_ac8_the_section_ties_codex_home_to_the_clone_and_the_pult(self):
        """В разделе «Провайдер codex» есть абзац, в котором `CODEX_HOME`
        стоит вместе со словом о клоне и словом о пульте.

        Ловит мутацию: правка документа описала подмену «клон берёт дом
        роли пульта», не назвав `CODEX_HOME` (или назвала `CODEX_HOME`, не
        сказав про клон) — Оператор, читающий раздел перед однократным
        `codex login`, не узнаёт, каким ИМЕННО путём клиент ключует запись
        входа, и повторяет вход не тем домом, а прогон канарейки снова
        отказывает предполётом.
        """
        paragraphs = [" ".join(chunk.split())
                      for chunk in re.split(r"\n\s*\n", self.section())
                      if chunk.strip()]
        matched = [p for p in paragraphs
                   if codex_provider.HOME_ENV in p
                   and CLONE_ROOT in p.lower() and PULT_ROOT in p.lower()]

        self.assertTrue(
            matched,
            "ни один абзац раздела не несёт сразу "
            f"{codex_provider.HOME_ENV}, «{CLONE_ROOT}…» и «{PULT_ROOT}…»")


if __name__ == "__main__":
    unittest.main()
