"""AC-1/AC-7 (SPEC 01M2ARQGY51B99YNP9PY806AN1) — новый примитив
`orchestrator/gitcmd.py` получает голову удалённой ветки через
временную приватную ссылку `refs/artel/fetch/<pid>-<uuid>`, без единого
обращения к `FETCH_HEAD` (AC-1), и это свойство держится даже когда
`FETCH_HEAD` меняется параллельным процессом ПОСЛЕ `git fetch` и ДО
`git rev-parse` — ровно гонка инцидента 12.09 07:15Z (AC-7).

Вход в примитив — `gitcmd.fetch_head_sha(remote, ref)` (AC-4: одно из
трёх мест, «переведённых» на примитив, имя и сигнатура прежние) — не
имя самого примитива, которое эта SPEC не называет: наблюдаемое
поведение `fetch_head_sha` после перевода ОБЯЗАНО совпасть с поведением
примитива (требование 2), так что проверка через устойчивое, зафикси-
рованное AC-4 имя не зависит от того, как разработчик назовёт новую
внутреннюю функцию.

Красен до реализации: сегодня `fetch_head_sha` (orchestrator/gitcmd.py:
412-435) буквально делает `git("rev-parse", "--verify", "--quiet",
"FETCH_HEAD")` — `test_ac1...` поймает этот вызов как элемент списка
аргументов, а `test_ac7...` поймает то, что тамперенный `FETCH_HEAD`
просачивается в результат (текущий код читает именно его).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402
from _sandbox import PrivateFetchSandbox  # noqa: E402


class Ac1PrivateRefMechanismTest(PrivateFetchSandbox):

    def test_ac1_fetch_uses_private_ref_refspec_and_never_touches_fetch_head(self):
        """Фетч удалённой ветки, продвинутой на origin, идёт через
        `git fetch origin +refs/heads/<MAIN_BRANCH>:refs/artel/fetch/
        <pid>-<uuid>`, и НИ ОДИН git-вызов примитива не несёт литерала
        `FETCH_HEAD` среди аргументов.

        Ловит мутацию: реализация оставляет (или возвращает) прежний
        приём — отдельный `git rev-parse ... FETCH_HEAD` — вместо
        `rev-parse --verify` приватной ссылки; либо адресует fetch голым
        именем ветки/через отдельный `refs/artel/pull-<pid>` без
        неймспейса `refs/artel/fetch/`, нарушая контракт AC-1 буквально.
        """
        origin = self.add_synced_origin()
        real_sha = self.advance_origin(origin, "ac1.txt", "1\n")

        orig_git = gitcmd.git
        calls: list[tuple] = []

        def spy(*args):
            calls.append(args)
            return orig_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            sha, reason = gitcmd.fetch_head_sha("origin", config.MAIN_BRANCH)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")

        for args in calls:
            self.assertNotIn("FETCH_HEAD", args,
                             f"вызов {args} обращается к FETCH_HEAD")

        fetch_calls = [a for a in calls if a and a[0] == "fetch"]
        self.assertEqual(len(fetch_calls), 1,
                         f"ровно один git fetch, получили {fetch_calls}")
        refspec_candidates = [
            a for a in fetch_calls[0]
            if a.startswith(f"+refs/heads/{config.MAIN_BRANCH}:")]
        self.assertEqual(
            len(refspec_candidates), 1,
            f"fetch обязан адресовать ветку рефспеком "
            f"+refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid> "
            f"(вызов: {fetch_calls[0]})")
        private_ref = refspec_candidates[0].split(":", 1)[1]
        self.assertRegex(
            private_ref, r"^refs/artel/fetch/\d+-[0-9a-fA-F-]+$",
            "приватная ссылка обязана жить в неймспейсе refs/artel/fetch/ "
            "и нести <pid>-<uuid> (AC-1)")


class Ac7FetchHeadRaceImmunityTest(PrivateFetchSandbox):

    def test_ac7_concurrent_fetch_head_rewrite_does_not_affect_the_result(self):
        """Между `git fetch` и чтением результата параллельный процесс
        (симуляция другого шага пульта, инцидент 12.09) переписывает
        `.git/FETCH_HEAD` чужим, но реальным sha; итог примитива обязан
        остаться настоящей головой зафетченной ветки, не тем, что лежит
        в `FETCH_HEAD` в момент завершения.

        Ловит мутацию: примитив на самом деле читает результат через
        `git rev-parse FETCH_HEAD` (буквально текущая реализация) —
        decoy sha, подставленный между вызовами, просочился бы в
        результат вместо настоящей головы `origin/<MAIN_BRANCH>`.
        """
        origin = self.add_synced_origin()
        real_sha = self.advance_origin(origin, "ac7.txt", "1\n")
        decoy_sha = self.head()
        self.assertNotEqual(decoy_sha, real_sha,
                            "проверка бессмысленна на совпадающих sha")

        fetch_head_path = config.ROOT / ".git" / "FETCH_HEAD"
        orig_git = gitcmd.git

        def spy(*args):
            res = orig_git(*args)
            if args and args[0] == "fetch":
                # Симуляция гонки: параллельный шаг другой задачи успел
                # зафетчить/перезаписать общий FETCH_HEAD ПОСЛЕ нашего
                # fetch, но ДО того, как мы прочли результат.
                fetch_head_path.write_text(
                    f"{decoy_sha}\t\tbranch 'decoy' of ./nowhere\n",
                    encoding="utf-8")
            return res

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            sha, reason = gitcmd.fetch_head_sha("origin", config.MAIN_BRANCH)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
