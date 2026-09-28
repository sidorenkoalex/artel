"""AC-1..AC-4 — чекпоинт шага test_author коммитит в кодовую ветку только
файлы `tests/test_<полный id задачи в нижнем регистре>_<имя>.py`, которых
нет в базе ветки, и их последующую правку/удаление, пока задача в
`tests_writing`; любое другое изменение вне `tasks/<id>/` откатывается с
записью в журнал и в кодовую ветку не попадает.

Чекпоинт наблюдается на обоих путях шага: исход «шаг завершён» (тот узел
`runner`, которым шаг реально завершается) и WIP-чекпоинт таймаута. Какую
функцию `orchestrator/checkpoint.py` реализация для этого расширит, SPEC
не фиксирует — наблюдается итог: дерево головы кодовой ветки, диск
worktree, журнал задачи.

Группа: разовый
Красен до реализации: чекпоинт test_author сегодня не коммитит в кодовую ветку ничего — на пути «шаг завершён» правка остаётся в worktree незакоммиченной, а WIP-чекпоинт таймаута откатывает и файл с префиксом задачи; файла `tests/test_<префикс>_…py` в голове ветки нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

KINDS = ("success", "timeout")


class TestAuthorCheckpointTest(_sandbox.LongLivedSandbox):

    def test_ac1_new_prefixed_file_is_committed_to_code_branch(self):
        """test_author добавил `tests/test_<префикс>_alpha.py`, которого нет
        в базе; после чекпоинта шага (каждого из двух путей) файл лежит в
        голове кодовой ветки байт-в-байт, в worktree не осталось
        незакоммиченного изменения по нему.

        Ловит мутацию: чекпоинт test_author по-прежнему откатывает всё вне
        `tasks/<id>/` (или не коммитит вовсе на пути «шаг завершён») —
        файла нет в `git show <ветка>:<путь>`.
        """
        rel = self.ll_path("alpha")
        for kind in KINDS:
            with self.subTest(checkpoint=kind):
                self.reset_branch()
                text = _sandbox.long_lived_source(tag=kind)
                self.wt_write(rel, text)
                self.checkpoint(kind)
                self.assertEqual(self.branch_text(rel), text,
                                 f"{kind}: файл с префиксом задачи не "
                                 f"закоммичен в кодовую ветку")
                status = self.wt_git("status", "--porcelain", "--", rel)
                self.assertEqual(status.strip(), "",
                                 f"{kind}: файл остался незакоммиченным")

    def test_ac2_foreign_changes_are_rolled_back_with_journal(self):
        """Три сценария — правка файла `tests/` из базы, новый файл
        `tests/` без префикса задачи, правка пути вне `tests/` и вне
        `tasks/<id>/` (`CLAUDE.md`) — на каждом из двух путей чекпоинта:
        голова кодовой ветки не несёт изменения, диск worktree вернулся к
        базе, а запись журнала, появившаяся за чекпоинт, называет путь.

        Ловит мутацию: разрешение коммита для test_author сделано по
        одному признаку «путь под `tests/`» без проверки префикса и
        отсутствия в базе — правка `tests/test_existing.py` или
        `tests/test_noprefix.py` уезжает в кодовую ветку.
        """
        existing = "tests/test_existing.py"
        noprefix = "tests/test_noprefix.py"
        outside = "CLAUDE.md"
        for kind in KINDS:
            for label, rel in (("правка файла базы", existing),
                               ("файл без префикса", noprefix),
                               ("путь вне tests/", outside)):
                with self.subTest(checkpoint=kind, scenario=label):
                    self.reset_branch()
                    base_text = self.branch_text(rel)
                    changed = (base_text or "") + "# правка test_author\n"
                    self.wt_write(rel, changed)
                    entries = self.checkpoint(kind)
                    self.assertEqual(self.branch_text(rel), base_text,
                                     f"{kind}/{label}: изменение попало в "
                                     f"кодовую ветку")
                    path = self.wt / rel
                    if base_text is None:
                        self.assertFalse(path.exists(),
                                         f"{kind}/{label}: новый файл не "
                                         f"убран с диска")
                    else:
                        self.assertEqual(path.read_text(encoding="utf-8"),
                                         base_text,
                                         f"{kind}/{label}: правка не откачена")
                    self.assertTrue(
                        any(rel in e for e in entries),
                        f"{kind}/{label}: журнал чекпоинта не называет {rel}: "
                        f"{entries!r}")

    def test_ac3_own_file_edit_and_delete_are_committed(self):
        """Свой файл с префиксом уже закоммичен прошлым чекпоинтом; задача
        всё ещё в `tests_writing`. Правка файла — после чекпоинта голова
        ветки несёт новый текст; удаление — пути в голове ветки нет.
        Отката нет: диск worktree совпадает с головой.

        Ловит мутацию: разрешён только статус «новый нетрекенный файл»
        (`?`/`A` в `git status`), а правка трекенного файла с префиксом
        (`M`) и его удаление (`D`) идут в откат как изменения «вне
        мандата» — голова ветки держит старый текст.
        """
        rel = self.ll_path("own")
        for kind in KINDS:
            with self.subTest(checkpoint=kind):
                self.reset_branch()
                self.wt_write(rel, _sandbox.long_lived_source())
                self.checkpoint(kind)
                self.assertIsNotNone(self.branch_text(rel),
                                     f"{kind}: исходный файл не закоммичен")

                edited = _sandbox.long_lived_source(tag="правка своего файла")
                self.wt_write(rel, edited)
                self.checkpoint(kind)
                self.assertEqual(self.branch_text(rel), edited,
                                 f"{kind}: правка своего файла не закоммичена")
                self.assertEqual((self.wt / rel).read_text(encoding="utf-8"),
                                 edited, f"{kind}: правка откачена")

                (self.wt / rel).unlink()
                self.checkpoint(kind)
                self.assertIsNone(self.branch_text(rel),
                                  f"{kind}: удаление своего файла не "
                                  f"закоммичено")
                self.assertFalse((self.wt / rel).exists(),
                                 f"{kind}: удалённый файл восстановлен")

    def test_ac4_prefix_is_full_lowercase_task_id(self):
        """Три файла одним шагом: с полным id задачи в нижнем регистре, с
        id соседней задачи (совпадают первые 10, значит и 8 знаков) и с
        префиксом из первых 8 знаков id. Чекпоинт коммитит только первый;
        два других в голову ветки не попадают.

        Ловит мутацию: префикс задачи укорочен до метки времени ULID
        (`task_id[:10].lower()`) или до восьми знаков — файл соседней
        задачи / короткого префикса признаётся своим и коммитится.
        """
        own = f"tests/test_{self.TASK.lower()}_own.py"
        sibling = _sandbox.sibling_task_id(self.TASK, 10).lower()
        self.assertEqual(sibling[:10], self.TASK.lower()[:10])
        self.assertNotEqual(sibling, self.TASK.lower())
        neighbour = f"tests/test_{sibling}_own.py"
        short = f"tests/test_{self.TASK.lower()[:8]}_own.py"
        for kind in KINDS:
            with self.subTest(checkpoint=kind):
                self.reset_branch()
                for rel in (own, neighbour, short):
                    self.wt_write(rel, _sandbox.long_lived_source())
                self.checkpoint(kind)
                self.assertIsNotNone(self.branch_text(own),
                                     f"{kind}: файл с полным id не закоммичен")
                self.assertIsNone(self.branch_text(neighbour),
                                  f"{kind}: файл соседней задачи (первые 10 "
                                  f"знаков id совпадают) закоммичен")
                self.assertIsNone(self.branch_text(short),
                                  f"{kind}: файл с префиксом из 8 знаков "
                                  f"закоммичен")


if __name__ == "__main__":
    unittest.main()
