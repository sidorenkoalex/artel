"""Приёмочные тесты 01M1RFVWV6WWTXRC5F40K61632 — AC-5..AC-7: запись
журнала «карта: размер» на каждом мерже.

Источник — только tasks/01M1RFVWV6WWTXRC5F40K61632/SPEC.md, раздел
«Критерии приёмки». Песочница и приём подмены `gitcmd.git`/
`subprocess.run` — тот же, что уже использует `tests/
test_fsm_map_regen.py::RegenerateAndCommitMapTest` (не копия классов
оттуда — только совпадающий стиль моков, чтобы не завязываться на
внутренние детали существующего файла).

Схема `detail` — JSON `map_stats(текст карты)` (см. `test_map_stats.py`
и `_fixtures.py` про выбор полей `bytes_by_dir`/`top_sections`) плюс
ключ `sha` — HEAD-sha репозитория ПОСЛЕ завершения регенерации (SPEC,
AC-5). Имя ключа `sha` SPEC буквально не называет — это конкретизация
теста, единственная, что естественно ложится рядом с полями
`map_stats` в одном плоском словаре без коллизии имён.

Красен до реализации: `fsm_postmerge._regenerate_and_commit_map` ещё
не пишет запись «карта: размер» — тесты этого файла не находят такую
запись в журнале (`assertIsNotNone`/`assertEqual(len(...), N)` падают)
или падают раньше на `AttributeError`/`KeyError` внутри `map_stats`,
пока обе функции не реализованы (требования 1-2 SPEC).
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, fsm_postmerge, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

COMMITTED_MAP = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
                 "---\n\n# Карта кодовой базы\n\nСодержимое A.\n")

OLD_SHA = "0" * 40
NEW_SHA = "1" * 40

SIZE_ACTION = "карта: размер"


class _MapSizeJournalTest(TmpRootTest):
    """Песочница: `docs/codebase-map.md` на месте, git/regen —
    управляемые заглушки, отслеживающие текущий HEAD sha (меняется
    только вызовом `commit`, тем же приёмом, что `fake_git`-замыкания
    `tests/test_fsm_map_regen.py`)."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        self.map_path = self.root / "docs" / "codebase-map.md"
        self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")

        store.create_schema(store.db())
        self.conn = store.db()

        self.current_sha = [OLD_SHA]
        self.git_calls = []

    def fake_git(self, *args) -> subprocess.CompletedProcess:
        self.git_calls.append(args)
        if args[:1] == ("commit",):
            self.current_sha[0] = NEW_SHA
            return subprocess.CompletedProcess(list(args), 0, "", "")
        if args[:2] == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(
                list(args), 0, self.current_sha[0] + "\n", "")
        return subprocess.CompletedProcess(list(args), 0, "", "")

    def fake_run_writing(self, text: str):
        def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess:
            self.map_path.write_text(text, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return fake_run

    def size_steps(self, task_id: str) -> list:
        return [r for r in store.task_steps(self.conn, task_id)
                if r["action"] == SIZE_ACTION]

    def run_regen(self, task_id: str, regenerated_text: str):
        with mock.patch.object(gitcmd, "git", self.fake_git), \
                mock.patch("subprocess.run",
                          side_effect=self.fake_run_writing(regenerated_text)):
            fsm_postmerge._regenerate_and_commit_map(self.conn, task_id)


class ContentChangedWritesSizeWithNewShaTest(_MapSizeJournalTest):
    """AC-5: карта содержательно изменилась — запись несёт detail
    `map_stats` регенерированного текста плюс НОВЫЙ sha (после коммита)."""

    def test_ac5_size_entry_carries_map_stats_and_post_commit_sha(self):
        """Регенерация меняет содержимое (не только `built_at_sha`) —
        коммит происходит, запись «карта: размер» несёт `sha` РОВНО
        новый (после коммита), а не тот, что был до вызова.

        Ловит мутацию: реализация берёт sha ДО коммита (забыла, что
        коммит уже сделан к моменту записи журнала) — `detail['sha']`
        совпал бы с `OLD_SHA` вместо `NEW_SHA`.
        """
        task_id = "01M1TESTMAPSIZE0000000001"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", "artel", 25.0)
        regenerated = COMMITTED_MAP.replace("Содержимое A.", "Содержимое B.")

        self.run_regen(task_id, regenerated)

        rows = self.size_steps(task_id)
        self.assertEqual(len(rows), 1)
        detail = json.loads(rows[0]["detail"])
        self.assertEqual(detail["sha"], NEW_SHA)
        self.assertIn("bytes_total", detail)
        self.assertEqual(detail["bytes_total"],
                         len(regenerated.encode("utf-8")))
        self.assertEqual(rows[0]["actor"], "orchestrator")


class UnchangedContentStillWritesSizeTest(_MapSizeJournalTest):
    """AC-5/AC-6: карта не изменилась содержательно (правку откатывают)
    — запись всё равно пишется, sha — тот, что был ДО вызова (коммита
    не было)."""

    def test_ac6_no_content_diff_still_writes_size_entry_with_pre_call_sha(self):
        """Регенерация меняет только `built_at_sha` — `_map_content_
        without_sha` признаёт тексты равными, правка откатывается
        (`git checkout`), коммита нет; запись «карта: размер» тем не
        менее есть, и её `sha` — тот, что стоял ДО вызова (карта не
        сдвинулась).

        Ловит мутацию: запись размера пишется только на ветке «был
        коммит» (`if committed: journal(...)`) — при откате без
        содержательных отличий `size_steps` был бы пуст.
        """
        task_id = "01M1TESTMAPSIZE0000000002"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", "artel", 25.0)
        regenerated = COMMITTED_MAP.replace(
            "aaaa000011112222333344445555666677778888",
            "dddd444455556666777788889999000011112222")

        self.run_regen(task_id, regenerated)

        rows = self.size_steps(task_id)
        self.assertEqual(len(rows), 1)
        detail = json.loads(rows[0]["detail"])
        self.assertEqual(detail["sha"], OLD_SHA)
        self.assertFalse(any(c[0] == "commit" for c in self.git_calls),
                         "без содержательных отличий коммита быть не должно")


class RegenFailureWritesNoSizeEntryTest(_MapSizeJournalTest):
    """AC-6: провал регенерации (`_map_regen_incident`) — записи
    размера нет, только существующая failure-запись."""

    def test_ac6_regeneration_failure_does_not_write_a_size_entry(self):
        """Генератор карты падает (код возврата ≠ 0) — журнал несёт
        только `"регенерация карты FAILED"`, «карта: размер» отсутствует
        целиком.

        Ловит мутацию: запись размера пишется БЕЗУСЛОВНО в конце функции
        (после всех ветвей, включая провал) — на этом сценарии
        `size_steps` был бы непустым, хотя регенерация не удалась.
        """
        task_id = "01M1TESTMAPSIZE0000000003"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", "artel", 25.0)
        fail = subprocess.CompletedProcess(["python3"], 1, "", "стенд: сбой")

        with mock.patch.object(gitcmd, "git", self.fake_git), \
                mock.patch("subprocess.run", return_value=fail):
            fsm_postmerge._regenerate_and_commit_map(self.conn, task_id)

        self.assertEqual(self.size_steps(task_id), [])
        actions = [r["action"] for r in store.task_steps(self.conn, task_id)]
        self.assertIn("регенерация карты FAILED", actions)
        self.assertEqual(len(alerts.open_alerts(self.conn, "incident")), 1)


class NoGapsAcrossConsecutiveMergesTest(_MapSizeJournalTest):
    """AC-6: ряд без пропусков — N успешных регенераций подряд дают
    ровно N записей «карта: размер»."""

    def test_ac6_three_successful_merges_write_three_size_entries(self):
        """Три последовательных вызова с меняющимся содержимым карты —
        три отдельные записи «карта: размер», без пропусков.

        Ловит мутацию: запись теряется на КАКОМ-то из вызовов
        (например, из-за не сброшенного состояния между вызовами) —
        `len(rows)` разошёлся бы с 3.
        """
        task_id = "01M1TESTMAPSIZE0000000004"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", "artel", 25.0)
        current = COMMITTED_MAP
        for i in range(3):
            current = current.replace(
                "Содержимое A.", f"Содержимое {i}.") if i == 0 else \
                current.replace(f"Содержимое {i - 1}.", f"Содержимое {i}.")
            self.run_regen(task_id, current)

        self.assertEqual(len(self.size_steps(task_id)), 3)


class TargetAttributionTest(_MapSizeJournalTest):
    """AC-7: запись несёт target задачи — ряды двух target разделяются
    фильтрацией по этому полю без дополнительного кода."""

    def test_ac7_size_entries_are_filterable_by_task_target(self):
        """Две задачи с разными target — записи «карта: размер» каждой
        несут её собственный target (`store.task_target`), фильтрация
        по target разделяет ряды без пересечения.

        Ловит мутацию: ничего специфичного не нужно ломать в самой
        `_regenerate_and_commit_map` — `store.journal` уже заполняет
        `target` (СУЩЕСТВУЮЩИЙ механизм, AC-7 «без правки»); тест ловит
        регресс, если БУДУЩАЯ правка вставит запись напрямую SQL в
        обход `store.journal`, потеряв атрибуцию.
        """
        task_a = "01M1TESTMAPSIZE00000000A1"
        task_b = "01M1TESTMAPSIZE00000000B1"
        store.insert_task(self.conn, task_a, "Задача А", "in_dev",
                          f"task/{task_a.lower()}", "artel", 25.0)
        store.insert_task(self.conn, task_b, "Задача Б", "in_dev",
                          f"task/{task_b.lower()}", "sled", 25.0)

        self.run_regen(task_a, COMMITTED_MAP.replace("A.", "A-2."))
        self.map_path.write_text(COMMITTED_MAP, encoding="utf-8")
        self.current_sha = [OLD_SHA]
        self.run_regen(task_b, COMMITTED_MAP.replace("A.", "A-3."))

        rows = self.conn.execute(
            "SELECT task_id, target FROM steps WHERE action=?",
            (SIZE_ACTION,)).fetchall()
        by_target = {r["target"]: r["task_id"] for r in rows}
        self.assertEqual(len(rows), 2)
        self.assertEqual(by_target["artel"], task_a)
        self.assertEqual(by_target["sled"], task_b)


if __name__ == "__main__":
    unittest.main()
