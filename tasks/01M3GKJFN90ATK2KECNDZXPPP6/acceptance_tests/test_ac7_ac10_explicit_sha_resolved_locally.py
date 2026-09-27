"""AC-7, AC-10 — 01M3GKJFN90ATK2KECNDZXPPP6: явный `--sha` канарейки
приводится к полному sha локально, и пометка происхождения это видит.

Источник — раздел «Критерии приёмки»:

AC-7. `canary._resolve_target_sha` с явным коротким `--sha` возвращает
полный 40-символьный sha, разрешённый локально, и не вызывает
`gitcmd.fetch_ref_sha` ни одного раза.

AC-10. `canary._sha_label` для явного `--sha`, разрешившегося в голову
главной копии, даёт пометку «код пина», а не «код <sha>».

Локальность резолва выражена заглушкой `_util.fake_local_git`: у неё
есть только локальная база (`rev-parse` по словарю известных ревизий),
а `gitcmd.fetch_ref_sha` — отдельный мок, который обязан остаться
непозванным. Точную форму вызова `rev-parse` планка не диктует
(`--verify`, `--quiet`, суффикс `^{commit}` заглушке безразличны) —
диктует локальность и полный sha на выходе.

Красен до реализации: `_resolve_target_sha` возвращает явный `--sha` как
напечатан — короткая строка из семи символов вместо сорока, а
`_sha_label` сравнивает её с полной головой главной копии и никогда не
даёт «код пина».
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import canary  # noqa: E402


class ExplicitShaResolvedLocallyTest(unittest.TestCase):
    """Чистая маршрутизация `_resolve_target_sha`/`_sha_label`: ни БД, ни
    настоящего git — только подменённые `gitcmd.git`/`gitcmd.fetch_ref_sha`.
    """

    def test_ac7_short_explicit_sha_becomes_the_full_sha_without_origin(self):
        """Прогон с коротким явным `--sha`: на выходе полный
        40-символьный sha, разрешённый локальным git'ом по этой самой
        короткой записи, и ни одного обращения к `origin`.

        Ловит мутацию: резолв сделан через `gitcmd.fetch_ref_sha`
        («всё равно надо спросить git, а функция под рукой») — короткий
        sha разрешался бы, но ценой обращения к origin, которое требование
        7 SPEC запрещает этой ветке.
        """
        calls: list = []
        fake = _util.fake_local_git({_util.SHORT_SHA: _util.FULL_SHA},
                                    _util.OTHER_HEAD_SHA, calls)

        with mock.patch.object(canary.gitcmd, "git", fake), \
             mock.patch.object(canary.gitcmd, "fetch_ref_sha") as fetch_mock:
            target_sha, _origin_sha = canary._resolve_target_sha(
                _util.SHORT_SHA)

        fetch_mock.assert_not_called()
        self.assertEqual(_util.FULL_SHA, target_sha)
        self.assertEqual(40, len(target_sha))
        self.assertTrue(
            any(argv and argv[0] == "rev-parse"
                and any(_util.SHORT_SHA in arg for arg in argv[1:])
                for argv in calls),
            f"локальный резолв короткого sha не запрашивался: {calls}")

    def test_ac10_explicit_sha_of_the_main_copy_head_is_labelled_pin(self):
        """Явный `--sha` записан коротко, но разрешается в голову главной
        копии: пометка происхождения целевого sha — «код пина», а не
        «код <sha>».

        Ловит мутацию: `_sha_label` оставлен сравнивать `target_sha` с
        `gitcmd.head_sha()` ДО приведения к полному sha (сравнение
        переехало в ветку без `--sha`) — пометка «код пина» на явном sha
        пина не срабатывала бы никогда, ровно как до этой задачи.
        """
        fake = _util.fake_local_git({_util.SHORT_SHA: _util.FULL_SHA},
                                    _util.FULL_SHA)

        with mock.patch.object(canary.gitcmd, "git", fake):
            target_sha, origin_sha = canary._resolve_target_sha(
                _util.SHORT_SHA)
            label = canary._sha_label(target_sha, origin_sha)

        self.assertEqual("код пина", label)


if __name__ == "__main__":
    unittest.main()
