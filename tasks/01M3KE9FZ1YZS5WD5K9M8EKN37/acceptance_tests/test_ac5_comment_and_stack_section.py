"""AC-5: комментарий у константы и раздел «Провайдер codex» стека.

Красен до реализации: константы со значением `high` в
`orchestrator/providers/codex.py` ещё нет (комментарий искать не у
чего), а раздел «Провайдер codex» файла `docs/stack.md` о глубине
рассуждения не говорит ни слова.
"""
import re
import unittest

import _util

# Место проверки поддержки ступени при добавлении модели — команда
# встроенного каталога клиента, названная критерием дословно.
BUNDLED_CATALOG_COMMAND = "codex debug models --bundled"
CATALOG_DATE = "28.09.2026"

# Приметы абзаца стека про глубину рассуждения: либо сам ключ, либо
# слово «глубин(а|ы) рассуждения» — формулировку прозы критерий не
# диктует, диктует содержание.
DEPTH_MARKERS = (_util.REASONING_KEY, "глубин")
# «Где задана» — обе половины настройки; альтернативы, чтобы не
# диктовать автору прозы единственную формулировку.
WHERE_MARKERS = ("config.toml", "образц", "образец", "дом роли")
# «Как доводится развёрнутый дом роли после правки образца» — порядок
# доведения раздел уже описывает жёлтой строкой `doctor`.
DELIVERY_MARKERS = ("codex-role-home", "doctor", "довод")


def _comment_block_above(source: str, name: str) -> str:
    """Комментарий над объявлением константы `name`.

    Соседние объявления констант ВЕРХНЕГО регистра (вторая половина
    пары «ключ/значение») блок не обрывают: комментарий пары стоит над
    первым из них, как у соседних пар модуля.
    """
    lines = source.splitlines()
    declaration = re.compile(rf"^{re.escape(name)}\s*=")
    index = next((i for i, line in enumerate(lines)
                  if declaration.match(line)), None)
    if index is None:
        return ""
    comments, cursor = [], index - 1
    while cursor >= 0:
        line = lines[cursor]
        stripped = line.strip()
        if stripped.startswith("#"):
            comments.append(stripped.lstrip("#").strip())
        elif not re.match(r"^[A-Z][A-Z0-9_]*\s*=", line):
            break
        cursor -= 1
    return "\n".join(reversed(comments))


class Ac5CommentAndDocTest(unittest.TestCase):
    """Комментарий у константы и проза раздела «Провайдер codex»."""

    def test_ac5_the_comment_names_the_catalog_check_and_the_stack_tells_the_depth(self):
        """Комментарий у константы называет, что ступень поддерживают
        все модели раздела `codex` каталога на дату решения, и где это
        проверять при добавлении модели; раздел «Провайдер codex» стека
        рассказывает о глубине рассуждения — где задана, какое значение
        и как доводится развёрнутый дом роли.

        Ловит мутацию: константа заведена с комментарием «глубина
        рассуждения роли» и без адреса проверки — тот, кто заводит
        седьмую модель раздела, не знает, где смотреть поддержку
        ступени, и ставит модель с дефолтом вендора. Наблюдаемо: в
        блоке комментария над константой нет строки
        `codex debug models --bundled`.
        """
        names = _util.named_string_constants(_util.codex_provider,
                                             _util.REASONING_VALUE)
        self.assertTrue(
            names,
            "в orchestrator/providers/codex.py нет именованной константы "
            f"со значением {_util.REASONING_VALUE!r}")

        source = _util.codex_source()
        blocks = [_comment_block_above(source, name) for name in names]
        annotated = [text for text in blocks
                     if BUNDLED_CATALOG_COMMAND in text]
        self.assertTrue(
            annotated,
            f"ни у одной из констант {names} комментарий не называет "
            f"{BUNDLED_CATALOG_COMMAND!r}")
        comment = annotated[0]
        self.assertIn(CATALOG_DATE, comment, comment)
        self.assertIn("модел", comment.lower(), comment)

        section = _util.markdown_section(_util.stack_doc_text(),
                                         _util.CODEX_STACK_SECTION)
        self.assertTrue(
            section.strip(),
            f"в docs/stack.md нет раздела «{_util.CODEX_STACK_SECTION}»")
        about_depth = [block for block in _util.paragraphs(section)
                       if any(marker in block.lower()
                              for marker in DEPTH_MARKERS)]
        self.assertTrue(
            about_depth,
            "раздел «Провайдер codex» ничего не говорит о глубине "
            "рассуждения")
        text = "\n".join(about_depth).lower()
        for label, markers in (("значение", (_util.REASONING_VALUE,)),
                               ("где задана", WHERE_MARKERS),
                               ("как доводится", DELIVERY_MARKERS)):
            with self.subTest(part=label):
                self.assertTrue(any(marker in text for marker in markers),
                                text)


if __name__ == "__main__":
    unittest.main()
