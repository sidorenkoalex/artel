"""AC-4/AC-9 (SPEC 01M2ARQGY51B99YNP9PY806AN1) — контракт трёх мест,
переводимых на новый примитив, обязан остаться прежним снаружи:

- AC-4: `fsm._origin_main_sha`, `fsm_merge_gate._origin_main_sha` и
  `gitcmd.fetch_head_sha` сохраняют имена и сигнатуры (включая параметр
  `repo` у `fsm._origin_main_sha`);
- AC-9: `tests/test_pull.py` и `tests/test_fsm_merge_gate_*.py` остаются
  зелёными без ослабления — приём патчить `fsm._origin_main_sha` по
  имени (`mock.patch.object(fsm, "_origin_main_sha", ...)`) по-прежнему
  долетает до `pull.evaluate` через `fsm._pull_main_or_escalate`
  (orchestrator/fsm.py:203: `origin_main_sha=lambda name:
  _origin_main_sha(name, repo=repo_path)` — свободная переменная
  `_origin_main_sha`, разрешаемая из пространства имён модуля `fsm` в
  момент вызова лямбды, поэтому патч имени в этом пространстве меняет
  то, что увидит `pull.evaluate`).

Зелёный с рождения: оба свойства уже верны СЕГОДНЯ, до перевода на
приватную ссылку — сигнатуры этих трёх функций не меняются самим фактом
задачи (требование 2 SPEC), а инъекция параметром в `pull.evaluate`
(orchestrator/pull.py docstring, orchestrator/fsm.py:203) — механизм,
существующий уже сейчас, независимо от того, ЧЕМ именно
`_origin_main_sha` фетчит голову (`FETCH_HEAD` или приватная ссылка).
Смысл — не сегодняшняя проверка, а сторожевой тест: без него замена
механизма легко могла бы попутно тронуть сигнатуру или подменить
`_pull_main_or_escalate` на вызов нового примитива НАПРЯМУЮ (в обход
имени `_origin_main_sha`), и оба класса регрессии остались бы незамечены
именно этой задачей — своим тестом на трассируемость, не переприбегая
к существующим `tests/test_pull.py`/`tests/test_fsm_merge_gate_*.py`
(их эта задача не трогает и не обязана дублировать целиком).
"""
import inspect
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance, fsm, fsm_merge_gate, gitcmd  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402


class Ac4SignaturesPreservedTest(unittest.TestCase):

    def test_ac4_wrapper_names_and_signatures_are_unchanged(self):
        """Имена параметров, их порядок и вид (позиционный/keyword-only) у
        всех трёх мест — прежние; у `fsm._origin_main_sha` параметр
        `repo` остаётся keyword-only с дефолтом `None`.

        Ловит мутацию: перевод на примитив попутно меняет сигнатуру —
        например, `repo` у `fsm._origin_main_sha` становится позиционным
        (ломает вызывающий код, передающий его именованно) или пропадает
        вовсе; либо `gitcmd.fetch_head_sha` обрастает параметром `repo`,
        которого не просят её вызывающие (`workspace.ensure`,
        `artifact_branch.py:145` — AC-4 явно требует их не трогать).
        """
        fsm_params = inspect.signature(fsm._origin_main_sha).parameters
        self.assertEqual(list(fsm_params), ["target_name", "repo"])
        self.assertIs(fsm_params["repo"].kind,
                      inspect.Parameter.KEYWORD_ONLY)
        self.assertIsNone(fsm_params["repo"].default)

        merge_gate_params = inspect.signature(
            fsm_merge_gate._origin_main_sha).parameters
        self.assertEqual(list(merge_gate_params), ["ctx"])

        fetch_head_params = inspect.signature(gitcmd.fetch_head_sha).parameters
        self.assertEqual(list(fetch_head_params), ["remote", "ref"])


class Ac9PatchByNameReachesPullEvaluateTest(LightTransitionSandbox):

    def _record_merge(self, repo, *args) -> subprocess.CompletedProcess | None:
        if args[:1] == ("merge",) and "--abort" not in args:
            self.merge_calls.append((repo, args))
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")
        return None

    def test_ac9_patch_by_name_on_origin_main_sha_still_drives_the_merge_base(self):
        """`mock.patch.object(fsm, "_origin_main_sha", return_value=marker)`
        обязан определить sha, которым идёт `git merge` внутри подтяжки
        `in_dev -> verifying` — тот же узел, что и существующий приём
        `tests/test_branch_freshness_gate.py`/`tests/sandbox.py`, здесь
        воспроизведён отдельным, собственным тестом этой задачи.

        Ловит мутацию: `_pull_main_or_escalate` перестаёт передавать
        `pull.evaluate` значение ИМЕННО через вызов `_origin_main_sha` по
        имени (например, зовёт новый примитив `gitcmd` напрямую в обход
        этого узла) — тогда патч не повлияет на исход, и marker_sha не
        попадёт в аргументы `git merge`.
        """
        marker_sha = "cafef00dfeedfacecafef00dfeedfacecafef00d"
        self.merge_calls: list = []
        self.in_repo_handlers.append(self._record_merge)
        self.write_acceptance_plank()

        with mock.patch.object(fsm, "_origin_main_sha",
                               return_value=marker_sha), \
             mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(len(self.merge_calls), 1,
                         f"ровно один git merge, получили {self.merge_calls}")
        _, args = self.merge_calls[0]
        self.assertIn(marker_sha, args)


if __name__ == "__main__":
    unittest.main()
