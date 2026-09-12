"""Приёмочный тест AC-9 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): формат JSON удержанной записи и путь каталога
`.artel/notes-pending/` не меняются; отправка удержанных записей
(флашем в начале `cmd_note` и `note --flush`) идёт в порядке имени
файла.

Красен до реализации: первый тест (формат/путь при удержании по окну)
красен по той же причине, что и AC-1/AC-2 — окно тишины ещё не
проверяется, запись уходит в push вместо удержания, `pending_notes()`
пуст там, где тест ждёт одну запись. Второй тест (очерёдность `--flush`
по имени файла) — существующее поведение `_flush_pending`
(`_pending_paths()` уже сортирует `glob("*.json")`, до этой задачи не
трогается) и остаётся зелёным сам по себе, но собран в один файл с
первым по теме AC-9 — прогон всего файла красен из-за первого теста.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class PendingFormatUnchangedTest(NoteSandbox):

    def test_ac9_held_by_window_uses_existing_json_shape_and_directory(self):
        """Запись, удержанная ИМЕННО окном тишины (не сетевым отказом),
        лежит в том же каталоге `.artel/notes-pending/*.json` и несёт
        те же поля (`kind`/`section`/`text`), что и удержание при
        недоступном origin — общий формат `notes.pending_notes()`
        читает оба вида одинаково, без разбора причины удержания.

        Ловит мутацию: окно тишины удерживает запись собственным,
        параллельным форматом/путём вместо переиспользования
        `_hold_pending` — тест красен на несовпадении набора файлов
        `.artel/notes-pending/*.json` (пусто) с ожидаемым (один файл).
        """
        self.insert_task_in_state("in_dev")

        self.capture(
            notes.cmd_note,
            ["копилка", "--text",
             "9 | 09.09 | формат не меняется | orchestrator/fmt.py"])

        pending_dir = config.ROOT / ".artel" / "notes-pending"
        files = sorted(pending_dir.glob("*.json"))
        self.assertEqual(len(files), 1, files)
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "insert")
        self.assertEqual(payload["section"], "копилка")
        self.assertIn("формат не меняется", payload["text"])

    def test_ac9_flush_applies_held_notes_in_filename_order(self):
        """Два удержанных `append` на РАЗНЫЕ ключи, файлы имён
        `0001-...`/`0002-...` (порядок имени файла = порядок удержания,
        требование 8) — `--flush` применяет их именно в этом порядке:
        коммиты в origin несут маркеры в порядке 0001, затем 0002.

        Ловит мутацию: `_flush_pending`/`_pending_paths` перебирают
        файлы не по сортировке имени (например, порядком обхода
        каталога ОС) — тест красен на перевёрнутом порядке маркеров
        в `origin_log_subjects_since`.
        """
        pending_dir = config.ROOT / ".artel" / "notes-pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        (pending_dir / "0001-aaaa.json").write_text(
            json.dumps({"kind": "append", "key": "УНИКАЛЬНЫЙКЛЮЧ",
                       "text": "МЕТКАПЕРВАЯ"}, ensure_ascii=False),
            encoding="utf-8")
        (pending_dir / "0002-bbbb.json").write_text(
            json.dumps({"kind": "append", "key": "ДРУГОЙКЛЮЧ",
                       "text": "МЕТКАВТОРАЯ"}, ensure_ascii=False),
            encoding="utf-8")
        base = self.origin_head()

        self.capture(notes.cmd_note, ["--flush"])

        self.assertEqual(notes.pending_notes(), [])
        subjects = self.origin_log_subjects_since(base)
        self.assertEqual(len(subjects), 2, subjects)
        self.assertIn("МЕТКАПЕРВАЯ", subjects[0])
        self.assertIn("МЕТКАВТОРАЯ", subjects[1])


if __name__ == "__main__":
    unittest.main()
