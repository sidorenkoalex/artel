"""Приёмочный тест AC-4 задачи 01M2XMCG167615YS9EZD9TYJWV: сверка базы
с пином. Содержимое пути в `origin/<MAIN_BRANCH>` разошлось с
содержимым того же пути в HEAD главной копии — именованный отказ без
коммита; пути, которого нет ни там, ни там, команда не боится и
коммитит.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — первый сценарий красен на маркере «Неизвестная команда» вместо
отказа сверки, второй — на несдвинувшемся origin.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config  # noqa: E402
from _sandbox import DOC_REL, DocCommitSandbox  # noqa: E402

REFUSAL = "файл изменился в origin после пина — сначала pin-update"

FOREIGN_TEXT = "# Роадмап\n\nРаздел, приехавший в origin от другой сессии.\n"
MY_TEXT = "# Роадмап\n\nМоя правка поверх устаревшей версии.\n"
NEW_REL = "docs/research/doc-commit-note.md"
NEW_TEXT = "# Заметка\n\nПуть, которого ещё нет ни в origin, ни в пине.\n"


class PinBaseCheckTest(DocCommitSandbox):

    def _push_foreign_change_past_the_pin(self) -> None:
        """origin уезжает вперёд по тому же пути, пин главной копии
        остаётся на старом содержимом — ровно расклад AC-4."""
        (self.root / DOC_REL).write_text(FOREIGN_TEXT, encoding="utf-8")
        self.git("commit", "-a", "-q", "-m", "чужая правка роадмапа")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")

    def test_ac4_origin_diverged_from_pin_refuses_naming_pin_update(self):
        """origin несёт чужую версию `docs/roadmap.md`, HEAD главной
        копии — старую: правка поверх устаревшей базы отказывается
        названной формулировкой, origin не сдвигается и чужой текст в
        нём цел.

        Ловит мутацию: сверка базы сравнивает `origin/<MAIN_BRANCH>` не с
        HEAD главной копии, а с содержимым файла `--from` (или вовсе
        отсутствует) — тогда вызов проходит и затирает чужую правку:
        тест красен и на отсутствии отказа, и на подменённом
        `origin_show`.
        """
        self._push_foreign_change_past_the_pin()
        source = self.source_file(MY_TEXT)
        before = self.origin_head()

        self.assert_refused(["doc-commit", DOC_REL, "--from", str(source),
                             "--message", "моя правка"], REFUSAL)

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(DOC_REL), FOREIGN_TEXT)

    def test_ac4_path_absent_in_origin_and_pin_is_committed(self):
        """Пути нет ни в `origin/<MAIN_BRANCH>`, ни в HEAD главной копии
        — сверка базы его пропускает, файл заводится коммитом в origin с
        содержимым `--from`.

        Ловит мутацию: сверка трактует «файла нет в origin» как
        расхождение с пином (сравнение пустой строки с отсутствием) —
        тогда ни один новый документ завести нельзя, и тест красен на
        отказе вместо коммита.
        """
        source = self.source_file(NEW_TEXT, name="new-note.md")

        self.run_artel("doc-commit", NEW_REL, "--from", str(source),
                       "--message", "новая заметка исследования")

        self.assertEqual(self.origin_show(NEW_REL), NEW_TEXT)


if __name__ == "__main__":
    unittest.main()
