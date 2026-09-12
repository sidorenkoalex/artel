"""Юнит-тесты `gitcmd.fetch_ref_sha` (SPEC 01M2ARQGY51B99YNP9PY806AN1) —
голова удалённой ветки через ВРЕМЕННУЮ приватную ссылку `refs/artel/
fetch/<pid>-<uuid>`, без единого обращения к общему `FETCH_HEAD`
(инцидент 12.09 07:15Z, канарейка 01M2A22CG2: merge-коммит 9a7f06c4
принёс голову ЧУЖОЙ артефактной ветки вместо `origin/main` — гонка
между `git fetch` и последующим отдельным чтением `FETCH_HEAD`).

Плюс реальный git-провод у двух других мест приёма (`fsm._origin_main_sha`,
`fsm_merge_gate._origin_main_sha`, требование 2/AC-4): существующие тесты
этих узлов (`tests/test_branch_freshness_gate.py`,
`tests/test_fsm_merge_gate_*.py`) патчат их целиком по имени
(`mock.patch.object(fsm, "_origin_main_sha", ...)`) и ни разу не исполняют
их git-тело — здесь оно исполняется впервые, настоящим fetch.

Реальный git (не заглушка): сам предмет проверки — фактический fetch в
объектную базу и заведение/уборка приватной ссылки, заглушкой этого не
изобразить (тот же приём, что `RealGitSandbox` в
`tests/test_gitcmd_branch_reads.py`).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, fsm_merge_gate, gitcmd, repo_context  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    res = subprocess.run(["git", "-C", str(cwd), *args],
                         capture_output=True, text=True)
    assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
    return res


class _PrivateRefRealGitSandbox(RealGitSandbox):
    """`self.root` (via `RealGitSandbox`) + помощники, общие для всех
    тестов этого файла."""

    def private_refs(self, repo: Path | None = None) -> list[str]:
        """Ссылки под `refs/artel/fetch/` в `repo` (по умолчанию
        `self.root`) прямо сейчас — пусто, если ни одна не осталась
        висеть после вызова примитива."""
        listing = _run("for-each-ref", "--format=%(refname)",
                       "refs/artel/fetch/", cwd=repo or self.root).stdout
        return [line for line in listing.splitlines() if line]

    def advance_origin(self, origin: Path, filename: str, content: str) -> str:
        """Коммитит и пушит новый коммит в `origin` из ОТДЕЛЬНОГО
        одноразового клона — не через `self.root`/`repo`: объект нового
        коммита обязан отсутствовать в проверяемой объектной базе ДО
        вызова примитива (иначе `object_present` прошёл бы и без
        настоящего fetch, ничего не доказав об объектах, реально
        попавших в базу)."""
        clone = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, clone, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "--branch", config.MAIN_BRANCH,
                       str(origin), str(clone)], check=True, capture_output=True)
        _run("config", "user.email", "artel@example.invalid", cwd=clone)
        _run("config", "user.name", "artel tests", cwd=clone)
        (clone / filename).write_text(content, encoding="utf-8")
        _run("add", "-A", cwd=clone)
        _run("commit", "-q", "-m", "advance", cwd=clone)
        _run("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}", cwd=clone)
        return _run("rev-parse", "HEAD", cwd=clone).stdout.strip()

    def object_present(self, sha: str, repo: Path | None = None) -> bool:
        res = subprocess.run(
            ["git", "-C", str(repo or self.root), "cat-file", "-e",
             f"{sha}^{{commit}}"], capture_output=True, text=True)
        return res.returncode == 0


class FetchRefShaTest(_PrivateRefRealGitSandbox):

    def test_returns_the_remote_head_fetches_objects_and_removes_the_private_ref(self):
        """AC-6. Ловит мутацию: примитив возвращает sha, но идёт голым
        `ls-remote` вместо настоящего `fetch` (`object_present` не
        нашёл бы коммит локально), либо путает ветку/remote и возвращает
        не ту голову (`assertEqual(sha, real_sha)`), либо не убирает
        приватную ссылку после успеха (`private_refs()` поймал бы
        висящую запись)."""
        origin = self.add_synced_origin()
        real_sha = self.advance_origin(origin, "a.txt", "1\n")
        self.assertFalse(
            self.object_present(real_sha),
            "проверка бессмысленна, если объект уже есть локально")

        sha, reason = gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")
        self.assertTrue(self.object_present(real_sha),
                        "объект нового коммита обязан попасть в локальную "
                        "объектную базу")
        self.assertEqual(self.private_refs(), [],
                         "приватная ссылка после успеха не остаётся")

    def test_concurrent_fetch_head_rewrite_does_not_leak_into_the_result(self):
        """AC-7. Между `git fetch` и чтением результата параллельный шаг
        ДРУГОЙ задачи (симуляция инцидента 12.09 07:15Z, канарейка
        01M2A22CG2) переписывает `.git/FETCH_HEAD` чужим, но реальным
        sha — итог обязан остаться настоящей головой зафетченной ветки.

        Ловит мутацию: примитив на самом деле читает результат через
        `git rev-parse FETCH_HEAD` — decoy sha, подставленный между
        вызовами, просочился бы в результат вместо настоящей головы.
        """
        origin = self.add_synced_origin()
        real_sha = self.advance_origin(origin, "b.txt", "1\n")
        decoy_sha = self.git("rev-parse", "HEAD").strip()
        self.assertNotEqual(decoy_sha, real_sha,
                            "проверка бессмысленна на совпадающих sha")

        fetch_head_path = self.root / ".git" / "FETCH_HEAD"
        orig_git = gitcmd.git

        def spy(*args):
            res = orig_git(*args)
            if args and args[0] == "fetch":
                fetch_head_path.write_text(
                    f"{decoy_sha}\t\tbranch 'decoy' of ./nowhere\n",
                    encoding="utf-8")
            return res

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            sha, reason = gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")

    def test_unreachable_remote_returns_a_reason_and_leaves_no_private_ref(self):
        """AC-8. `remote`, не настроенный в репозитории (эквивалент «сеть/
        remote недоступны» без реального похода в сеть).

        Ловит мутацию: отказ `fetch` трактуется как успех с пустым sha
        (`assertTrue(reason)` поймает пустую причину), либо приватная
        ссылка заведена до fetch и не убрана при его отказе
        (`private_refs()` поймал бы висящую ссылку).
        """
        sha, reason = gitcmd.fetch_ref_sha("no-such-remote-configured",
                                           config.MAIN_BRANCH)

        self.assertEqual(sha, "")
        self.assertTrue(reason)
        self.assertEqual(self.private_refs(), [],
                         "приватной ссылки после отказа fetch не остаётся")

    def test_repo_param_fetches_inside_the_given_clone_not_config_root(self):
        """AC-2. `repo=<клон>` — ВЕСЬ git-трафик примитива идёт там
        (`gitcmd.in_repo`), не в `config.ROOT`.

        Ловит мутацию: `repo` подставляется только в `fetch`, а
        `rev-parse`/`update-ref` по-прежнему идут в `config.ROOT` — sha
        не разрешился бы (объект есть только в клоне), либо объект/
        приватная ссылка попали бы в `config.ROOT` вместо клона.
        """
        target_repo = self.root / ".target-clone"
        target_repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH,
                       str(target_repo)], check=True, capture_output=True)
        _run("config", "user.email", "artel@example.invalid", cwd=target_repo)
        _run("config", "user.name", "artel tests", cwd=target_repo)
        (target_repo / "marker.txt").write_text("target\n", encoding="utf-8")
        _run("add", "-A", cwd=target_repo)
        _run("commit", "-q", "-m", "init", cwd=target_repo)

        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", str(origin)],
                       check=True, capture_output=True)
        _run("remote", "add", "origin", str(origin), cwd=target_repo)
        _run("push", "-q", "origin",
             f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}", cwd=target_repo)
        real_sha = self.advance_origin(origin, "c.txt", "1\n")
        self.assertFalse(self.object_present(real_sha, repo=target_repo))
        self.assertFalse(self.object_present(real_sha),
                         "sanity: объект не имеет права уже быть в config.ROOT")

        sha, reason = gitcmd.fetch_ref_sha("origin", config.MAIN_BRANCH,
                                           repo=target_repo)

        self.assertEqual(sha, real_sha)
        self.assertEqual(reason, "")
        self.assertTrue(self.object_present(real_sha, repo=target_repo),
                        "объект обязан попасть в объектную базу КЛОНА")
        self.assertFalse(self.object_present(real_sha),
                         "объект не имеет права попасть в config.ROOT")
        self.assertEqual(self.private_refs(repo=target_repo), [],
                         "приватная ссылка убирается в том же клоне")


class OriginMainShaRealGitWiringTest(_PrivateRefRealGitSandbox):
    """`fsm._origin_main_sha`/`fsm_merge_gate._origin_main_sha` (AC-4) —
    существующие тесты этих узлов патчат их целиком по имени и никогда не
    исполняют git-тело; здесь оно исполняется впервые, реальным fetch,
    подтверждая сам перевод на `gitcmd.fetch_ref_sha` (требование 2), не
    только сохранение сигнатуры."""

    def setUp(self):
        super().setUp()
        self.origin = self.add_synced_origin()

    def test_fsm_origin_main_sha_self_target_fetches_via_private_ref(self):
        """Ловит мутацию: `fsm._origin_main_sha` перестаёт реально фетчить
        (например, возвращает локальный `config.MAIN_BRANCH` вместо
        головы `origin`) — `assertEqual(sha, real_sha)` поймает
        расхождение; приватная ссылка, оставшаяся висеть, поймана
        `private_refs()`.
        """
        real_sha = self.advance_origin(self.origin, "fsm.txt", "1\n")

        sha = fsm._origin_main_sha(config.DEFAULT_TARGET)

        self.assertEqual(sha, real_sha)
        self.assertEqual(self.private_refs(), [])

    def test_fsm_merge_gate_origin_main_sha_self_ctx_fetches_via_private_ref(self):
        """Тот же узел `orchestrator/fsm_merge_gate.py`, self-контекст.

        Ловит мутацию: перевод одного из двух дублей `_origin_main_sha`
        на примитив забыт (второй файл остаётся на прежнем `FETCH_HEAD`)
        — этот тест красен именно на файле `fsm_merge_gate.py`, тест
        выше — на `fsm.py`."""
        real_sha = self.advance_origin(self.origin, "merge_gate.txt", "1\n")
        ctx = repo_context.RepoContext(
            path=config.ROOT, remote="origin", base=config.MAIN_BRANCH)

        sha = fsm_merge_gate._origin_main_sha(ctx)

        self.assertEqual(sha, real_sha)
        self.assertEqual(self.private_refs(), [])


if __name__ == "__main__":
    unittest.main()
