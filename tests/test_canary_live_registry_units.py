"""Реестр живого прогона канарейки — свойства вне долгоживущих файлов задачи
01M5C6QA6S3RY9PS4H9ZJ58WQ0: разбор `approve` с `--during-canary`, уборка
нечитаемой записи и неприкосновенность чужой метки того же `run_stamp`."""
import json
import os

from orchestrator import artel, canary, config, store
from tests.sandbox import InitializedTmpRootTest, TmpRootTest

STAMP = "20310101T000000Z"


class ApproveDuringCanaryArgsTest(TmpRootTest):
    def test_reason_is_not_taken_for_sha(self):
        """Основание `--during-canary` в любом месте строки не читается как sha.

        Ловит мутацию: флаг выпал из `_approve_reason_indices` — основание
        без sha становится позиционным sha, а с sha перед флагом sha
        остаётся прежним.
        """
        rest = ["01TASK", "--during-canary", "abc1234"]
        self.assertIsNone(artel._approve_sha_arg(rest))
        self.assertEqual(artel._approve_sha_arg(["01TASK", "--during-canary",
                                                 "abc1234", "f" * 40]), "f" * 40)
        self.assertEqual(artel._approve_during_canary_kwargs(rest),
                         {"during_canary": "abc1234"})
        self.assertEqual(artel._approve_during_canary_kwargs(["01TASK"]), {})


class LiveRunsSweepTest(InitializedTmpRootTest):
    def directory(self):
        path = canary._live_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_unreadable_record_swept_with_journal_line(self):
        """Запись реестра с битым JSON — не живая: убрана вместе со своей меткой, строка журнала без задачи.

        Ловит мутацию: нечитаемая запись пропускается молча — файл остаётся
        в каталоге, и окно тишины держится до ручной уборки, либо уборка не
        пишет журнал.
        """
        directory = self.directory()
        record = directory / f"{STAMP}-999999.json"
        record.write_text("{не json", encoding="utf-8")
        mark = directory / f"{STAMP}.lock"
        mark.write_text("999999\n", encoding="utf-8")
        self.assertEqual(canary.live_runs(), [])
        self.assertFalse(record.exists())
        self.assertFalse(mark.exists())
        rows = [r for r in store.all_steps(store.db())
                if r["action"] == canary.LIVE_RUN_SWEPT_ACTION]
        self.assertEqual(len(rows), 1, rows)
        self.assertFalse(rows[0]["task_id"])

    def test_mark_of_other_pid_kept_on_sweep(self):
        """Уборка мёртвой записи не снимает метку `run_stamp`, принадлежащую другому pid.

        Ловит мутацию: метка удаляется по одному `run_stamp`, без сверки
        владельца, — метка живого прогона того же `run_stamp` пропадает и
        повтор `run_stamp` перестаёт отказывать.
        """
        directory = self.directory()
        dead = directory / f"{STAMP}-999998.json"
        dead.write_text(json.dumps({
            "pid": 999998, "process_start": None, "run_stamp": STAMP,
            "sha": "a" * 40, "set_name": config.CANARY_DEFAULT_SET,
            "started_at": "2031-01-01T00:00:00+00:00", "tasks": 1}),
            encoding="utf-8")
        mark = directory / f"{STAMP}.lock"
        mark.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self.assertEqual(canary.live_runs(), [])
        self.assertFalse(dead.exists())
        self.assertTrue(mark.exists())
