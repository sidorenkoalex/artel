"""AC-11 — 01M3GKJFN90ATK2KECNDZXPPP6: `pin --to` без аргумента читает
короткий `main_sha` зелёного прогона как «уже на пине».

Источник — раздел «Критерии приёмки»:

AC-11. `pin --to` без аргумента, когда `main_sha` последнего зелёного
прогона — короткая строка, являющаяся префиксом текущего HEAD, отказывает
сообщением «пин уже на sha последнего зелёного прогона» и `git reset
--hard` не выполняет.

Короткая строка в `canary_runs.main_sha` — не выдумка планки, а состояние
живой БД пульта («Контекст» SPEC: две коротких строки прогонов 26.09),
которое требование 9 SPEC оставляет как записано: миграция их не
дописывает, а единственное строковое сравнение обязано читать их по
префиксу. Отсутствие `git reset --hard` планка наблюдает по аргументам
подменённого `gitcmd.git`: та же заглушка отвечает и на `rev-parse HEAD`
(текущий пин), так что полный HEAD сценария задан ровно одним значением.

Красен до реализации: `cmd_pin_to` сравнивает `main_sha` с HEAD строгим
равенством — короткая строка ему не равна, отказа нет, и команда доходит
до `git reset --hard`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import pin, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

ALREADY_PINNED_REFUSAL = "пин уже на sha последнего зелёного прогона"


class PinToShortGreenShaTest(SchemaConnTmpRootTest):

    def test_ac11_short_green_sha_prefixing_head_is_read_as_already_pinned(self):
        """Последний зелёный прогон канарейки записан коротким `main_sha`,
        являющимся префиксом текущего HEAD: `pin --to` без аргумента
        отказывает «пин уже на sha последнего зелёного прогона» и HEAD не
        двигает.

        Ловит мутацию: префиксное сравнение написано в другую сторону
        (`old_sha.startswith(target)` заменено на `target.startswith(
        old_sha)`) — короткий `main_sha` перестал бы узнаваться, и команда
        снова выполнила бы `git reset --hard` на семисимвольную строку.
        """
        store.insert_canary_run(
            self.conn, "20260926T101500Z", _util.POOL_TEMPLATE_TITLE,
            "01M3GKPLANKAKANAREJKA000002", 5, 1.25, 1, 0, "killed",
            "no", False, False, main_sha=_util.SHORT_SHA, verdict="green")

        calls: list = []
        fake = _util.fake_local_git({}, _util.FULL_SHA, calls)
        with mock.patch.object(pin.gitcmd, "git", fake):
            with self.assertRaises(SystemExit) as ctx:
                pin.cmd_pin_to(None)

        self.assertIn(ALREADY_PINNED_REFUSAL, str(ctx.exception))
        self.assertEqual(
            [], [argv for argv in calls if argv[:2] == ["reset", "--hard"]],
            f"git reset --hard выполнен после отказа: {calls}")


if __name__ == "__main__":
    unittest.main()
