"""AC-3 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: мандат зон на путь, которого нет в
дереве кодовой ветки задачи, отказывает; на существующий файл и на
существующий каталог — проходит.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. `answer` с мандатом зон на путь, которого нет в дереве кодовой ветки
задачи, отказывает именованно; мандат на существующий файл и на
существующий каталог (в том числе записанный с `/` на конце) проходит и
ANSWER коммитится.

Дерево `_sandbox.CODE_BRANCH_TREE` положено ТОЛЬКО в кодовую ветку задачи
и НЕ в main: критерий говорит «в дереве кодовой ветки задачи», поэтому
проверка, подсматривающая вместо неё main (или рабочее дерево пульта),
на положительных случаях обязана краснеть.

Красен до реализации: для задачи в `escalated` `answer` содержимое файла
ответа не разбирает вовсе (`orchestrator/answer.py:124-125`) — мандат на
несуществующий путь коммитится как есть, отказа нет
(`test_ac3_zones_mandate_on_a_path_missing_from_the_branch_refuses`).
Три положительных метода на сегодняшнем коде зелёные — контроль, не
молчаливый пропуск: они фиксируют, что новая проверка не начнёт отказывать
исправному мандату (в том числе мандату на каталог, которого в дереве git
как отдельной записи нет вовсе).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class ZonesMandatePathExistsTest(_sandbox.AnswerMandateSandbox):

    def test_ac3_zones_mandate_on_a_path_missing_from_the_branch_refuses(self):
        """Мандат зон на путь, которого в дереве кодовой ветки задачи нет
        ни файлом, ни каталогом, — `answer` отказывает именованно (назвав
        строку и сам элемент), ANSWER не создаётся.

        Ловит мутацию: проверка существования снята (или сведена к
        «похоже на путь» по форме строки) — опечатка в пути мандата
        доезжала бы до гейта зон и там молча не срабатывала, ровно как
        26.09.
        """
        line = _sandbox.zones_mandate_line(_sandbox.MISSING_PATH)

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(_sandbox.MISSING_PATH, message,
                      "отказ обязан назвать элемент, которого нет в дереве")
        self.assertIn(line, message,
                      "отказ обязан назвать строку мандата")

    def test_ac3_zones_mandate_on_an_existing_file_commits_the_answer(self):
        """Мандат зон на файл, существующий в дереве кодовой ветки, проверку
        проходит: `ANSWER-1.md` появляется на артефактной ветке и несёт
        строку мандата.

        Ловит мутацию: существование проверяется не в дереве КОДОВОЙ ВЕТКИ
        задачи, а в рабочем дереве пульта либо в main — там этого файла
        нет, и исправный мандат Оператора отказывал бы на ровном месте.
        """
        line = _sandbox.zones_mandate_line(_sandbox.EXISTING_FILE)

        self.succeed_answer(_sandbox.answer_text(line))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())
        text = self.answer_text_in_branch(1)
        self.assertIsNotNone(text, "ANSWER-1.md не прочитан с ветки")
        self.assertIn(line, text)

    def test_ac3_zones_mandate_on_an_existing_directory_commits_the_answer(self):
        """Мандат зон на КАТАЛОГ дерева кодовой ветки (без `/` на конце)
        проверку проходит.

        Ловит мутацию: существование проверяется только как файл
        (`git cat-file -e <ветка>:<элемент>`) — мандат на каталог, самый
        частый вид мандата зон (`orchestrator/advance_gates/`), отказывал
        бы всегда.
        """
        self.succeed_answer(_sandbox.answer_text(
            _sandbox.zones_mandate_line(_sandbox.EXISTING_DIR)))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())

    def test_ac3_zones_mandate_on_a_directory_with_trailing_slash_commits(self):
        """Тот же каталог, записанный с `/` на конце — критерий называет эту
        запись отдельно («с учётом `/` на конце», требование 2б).

        Ловит мутацию: элемент сверяется со списком путей дерева без
        нормализации `/` на конце (`элемент in files or any(f.startswith(
        элемент + "/"))` — для «orchestrator/» это ищет префикс
        «orchestrator//»), и штатная запись зоны-каталога (COMMON_ZONES
        пульта пишутся именно так: «tests/») отказывала бы всегда.
        """
        self.succeed_answer(_sandbox.answer_text(
            _sandbox.zones_mandate_line(_sandbox.EXISTING_DIR + "/")))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())


if __name__ == "__main__":
    unittest.main()
