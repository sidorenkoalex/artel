"""AC-3/AC-6/AC-8 (SPEC 01M2ARQGY51B99YNP9PY806AN1) — контракт возврата
и оба магистральных исхода примитива, проверенные через
`gitcmd.fetch_head_sha(remote, ref)` (AC-4: имя/сигнатура сохраняются,
её поведение после перевода обязано совпасть с примитивом дословно —
требование 2):

- AC-3: `(sha, "")` на успехе, `("", причина)` на отказе — форма
  возврата, не конкретное значение sha/причины;
- AC-6: голова удалённой ветки возвращена верно, объекты реально
  попали в локальную объектную базу (`git cat-file -e`), приватная
  ссылка после вызова не осталась;
- AC-8: недоступный remote даёт `("", причина)`, приватной ссылки не
  остаётся и в отказавшем сценарии.

Зелёный с рождения: КАЖДОЕ из трёх свойств уже верно у сегодняшнего
`fetch_head_sha` (orchestrator/gitcmd.py:412-435) само по себе —
`(sha, "")`/`("", причина)` оно возвращает уже сейчас (AC-3); реальный
успешный fetch уже сегодня возвращает верный sha и реально кладёт
объекты в базу (AC-6, первая половина); а «приватной ссылки не
осталось» вырождено в истину и до, и после задачи — сегодняшний код
вообще не заводит `refs/artel/fetch/*`, так что убирать после него
нечего (AC-6/AC-8, вторая половина; та часть этих же критериев,
которая ЛОВИТ гонку/перевод на приватную ссылку, — не здесь, а в
`test_ac1_ac7_no_fetch_head.py`, где красно уже сейчас). Смысл этих
тестов — не сегодняшняя краснота, а то, что оба свойства обязаны
остаться верными и ПОСЛЕ перевода на приватную ссылку (сохранение
контракта при смене механизма).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402
from _sandbox import PrivateFetchSandbox  # noqa: E402


class Ac3ReturnShapeContractTest(unittest.TestCase):
    """Форма возврата — по образцу `gitcmd.fetch_head_sha` (AC-3), проверена
    полностью на подменённом `gitcmd.git` — предмет здесь не конкретное
    значение sha, а именно ФОРМА (2-элементный кортеж, типы, взаимная
    исключительность частей)."""

    def test_ac3_success_and_failure_both_return_a_two_element_tuple(self):
        """Успех даёт `(str, "")`; отказ — `("", str)` (непустая причина).

        Ловит мутацию: примитив возвращает голый sha без обёртки в
        кортеж на успехе, либо `None`/строку вместо `("", причина)` на
        отказе — `assertIsInstance(..., tuple)`/`len(...) == 2` ниже
        поймают любой из этих вариантов.
        """
        def fake_ok(*args):
            if args[0] == "fetch":
                return subprocess.CompletedProcess(("git", *args), 0, "", "")
            if args[0] == "rev-parse":
                return subprocess.CompletedProcess(
                    ("git", *args), 0, "d" * 40 + "\n", "")
            if args[0] == "update-ref":
                return subprocess.CompletedProcess(("git", *args), 0, "", "")
            raise AssertionError(f"неожиданный вызов: {args}")

        with mock.patch.object(gitcmd, "git", side_effect=fake_ok):
            success = gitcmd.fetch_head_sha("origin", "main")

        self.assertIsInstance(success, tuple)
        self.assertEqual(len(success), 2)
        sha, reason = success
        self.assertIsInstance(sha, str)
        self.assertTrue(sha)
        self.assertEqual(reason, "")

        def fake_fail(*args):
            if args[0] == "fetch":
                return subprocess.CompletedProcess(
                    ("git", *args), 1, "", "remote недоступен")
            raise AssertionError(f"неожиданный вызов: {args}")

        with mock.patch.object(gitcmd, "git", side_effect=fake_fail):
            failure = gitcmd.fetch_head_sha("origin", "main")

        self.assertIsInstance(failure, tuple)
        self.assertEqual(len(failure), 2)
        sha, reason = failure
        self.assertEqual(sha, "")
        self.assertIsInstance(reason, str)
        self.assertTrue(reason)


class Ac6HappyPathTest(PrivateFetchSandbox):

    def test_ac6_returns_head_fetches_objects_and_leaves_no_private_ref(self):
        """Ветка продвинута на origin ПОСЛЕ того, как локальная объектная
        база уже сформирована (объект нового коммита туда ещё не попал);
        вызов обязан вернуть именно этот sha, положить его объект в
        локальную базу и не оставить ни одной ссылки под
        `refs/artel/fetch/`.

        Ловит мутацию: примитив возвращает sha, но не настоящий fetch
        (например, голый `ls-remote`) — `object_present` не найдёт
        коммит локально; либо примитив путает ветку/remote и возвращает
        не ту голову — `assertEqual(sha, real_sha)` поймает расхождение.
        """
        origin = self.add_synced_origin()
        real_sha = self.advance_origin(origin, "ac6.txt", "содержимое\n")
        self.assertFalse(
            self.object_present(real_sha),
            "проверка бессмысленна, если объект уже есть локально")

        sha, reason = gitcmd.fetch_head_sha("origin", config.MAIN_BRANCH)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")
        self.assertTrue(self.object_present(real_sha),
                        "AC-6: объект нового коммита обязан попасть в "
                        "локальную объектную базу")
        self.assertEqual(self.private_refs(), [],
                         "AC-6: приватная ссылка после вызова не остаётся")


class Ac8FetchFailureTest(PrivateFetchSandbox):

    def test_ac8_unreachable_remote_gives_a_reason_and_no_stray_ref(self):
        """`remote`, не настроенный в репозитории (эквивалент «сеть/remote
        недоступны» без реального похода в сеть), даёт именованный отказ
        и не оставляет приватной ссылки.

        Ловит мутацию: отказ fetch трактуется как успех с пустым sha
        (`assertTrue(reason)` поймает пустую причину); либо приватная
        ссылка заведена ДО fetch и не убрана при его отказе
        (`private_refs()` поймал бы висящую ссылку).
        """
        sha, reason = gitcmd.fetch_head_sha(
            "no-such-remote-configured", config.MAIN_BRANCH)

        self.assertEqual(sha, "")
        self.assertTrue(reason)
        self.assertEqual(self.private_refs(), [],
                         "AC-8: приватной ссылки после отказа fetch не остаётся")


if __name__ == "__main__":
    unittest.main()
