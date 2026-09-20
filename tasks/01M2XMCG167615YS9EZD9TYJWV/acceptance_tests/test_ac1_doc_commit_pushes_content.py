"""Приёмочный тест AC-1 задачи 01M2XMCG167615YS9EZD9TYJWV: `doc-commit`
с допустимым docs-путём, существующим `--from <файл>` и `--message`
кладёт содержимое файла в origin, не трогая главную копию, и называет
sha созданного коммита.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — вызов отказывает «Неизвестная команда», origin остаётся на
фикстурном коммите, `origin_show` отдаёт старый текст роадмапа.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DOC_REL, ROADMAP_TEXT, DocCommitSandbox  # noqa: E402

NEW_TEXT = "# Роадмап\n\nНовый раздел роадмапа от doc-commit.\n"
MESSAGE = "перенос раздела из каталога сессии"


class DocCommitPushesContentTest(DocCommitSandbox):

    def test_ac1_origin_commit_carries_source_file_content_and_output_names_sha(self):
        """Содержимое `--from <файл>` становится содержимым
        `docs/roadmap.md` в origin, а вывод команды называет sha именно
        того коммита, на который сдвинулся origin.

        Ловит мутацию: реализация коммитит путь, но печатает только имя
        файла (sha не выводится) либо печатает sha локального коммита
        рабочего репозитория, не совпавший с origin после повтора
        non-fast-forward — тест красен на отсутствии среди hex-токенов
        вывода префикса `origin_head()`.
        """
        source = self.source_file(NEW_TEXT)
        before = self.origin_head()

        output = self.run_artel("doc-commit", DOC_REL,
                                "--from", str(source), "--message", MESSAGE)

        self.assertEqual(self.origin_show(DOC_REL), NEW_TEXT)
        head = self.origin_head()
        self.assertNotEqual(before, head, "origin не сдвинулся")
        tokens = re.findall(r"[0-9a-f]{7,40}", output)
        self.assertTrue(any(head.startswith(t) for t in tokens),
                        f"вывод не называет sha {head}: {output!r}")

    def test_ac1_main_copy_head_branch_and_worktree_untouched(self):
        """Тот же успешный вызов не сдвигает ни HEAD, ни ветку, ни
        рабочее дерево главной копии `config.ROOT`: файл на диске
        главной копии остаётся прежним, `git status` — прежним.

        Ловит мутацию: реализация правит файл прямо в `config.ROOT` и
        коммитит там (самый короткий путь мимо отдельного рабочего
        репозитория) — тест красен на изменившемся снимке главной копии
        и на новом содержимом файла на диске.
        """
        source = self.source_file(NEW_TEXT)
        before = self.main_copy_snapshot()

        self.run_artel("doc-commit", DOC_REL,
                       "--from", str(source), "--message", MESSAGE)

        self.assertEqual(before, self.main_copy_snapshot())
        self.assertEqual((self.root / DOC_REL).read_text(encoding="utf-8"),
                         ROADMAP_TEXT)


if __name__ == "__main__":
    unittest.main()
