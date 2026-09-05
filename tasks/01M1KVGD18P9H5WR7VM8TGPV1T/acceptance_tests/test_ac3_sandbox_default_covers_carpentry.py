"""AC-3 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md), вторая половина:
«…который tests/sandbox.py подменяет одним патчем по умолчанию для
всех наследников базовых классов.»

Структурная половина критерия (нет буквальных `subprocess.run` в
`artifact_branch.py`/`snapshot.py`/`pin.py`) — отдельный файл
`test_ac3_unified_git_choke_point.py` (красен до реализации).

Зелёный с рождения: `artifact_branch.commit_files` в `self.root` —
обычном временном каталоге БЕЗ `git init` — сегодня УЖЕ успешно
коммитит артефакт под одними лишь патчами, которые `tests.sandbox.
TmpRootTest.setUp` ставит по умолчанию (ничего сверх них тест здесь не
патчит). Так вышло не потому, что критерий уже выполнен архитектурно
(структурная половина в соседнем файле красная), а потому что
`subprocess` — общий модуль-синглтон: патч `gitcmd.subprocess.run`
(`SpyRun`, `tests/sandbox.py`) меняет атрибут `run` НА САМОМ модуле
`subprocess`, и `artifact_branch.py` (`import subprocess; subprocess.
run(...)`) видит тот же патч. Этот тест фиксирует ИМЕННО наблюдаемое
поведение («по умолчанию, без лишних патчей — работает»), не механизм —
он обязан остаться зелёным и после того, как структурная половина
критерия будет закрыта явным делегированием единому модулю (если
единый модуль — сам `gitcmd`, синглтон-эффект просто станет побочным
следствием прямого вызова; если новый модуль, `TmpRootTest.setUp`
обязан патчить именно его, и это наблюдение — единственный
рантайм-свидетель того, что патч не потерялся при переносе).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import artifact_branch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tests.sandbox import TmpRootTest  # noqa: E402


class Ac3SandboxDefaultCoversCarpentryTest(TmpRootTest):

    def test_ac3_commit_files_succeeds_under_default_sandbox_patch(self):
        """`artifact_branch.commit_files` в чистой песочнице `TmpRootTest`
        (без собственного `git init`, без дополнительных патчей сверх
        того, что ставит `setUp` по умолчанию) успешно коммитит артефакт
        и возвращает непустой sha.

        Ловит мутацию: код задачи переносит плотницкие вызовы на НОВЫЙ
        модуль, но `tests/sandbox.py::TmpRootTest.setUp` продолжает
        патчить только старую точку (`gitcmd.subprocess.run`), не
        переиспользуемую новым модулем, — `commit_files` попытается
        исполнить настоящий git в `self.root`, который не является
        git-репозиторием, упадёт на первой же плотницкой команде и
        вернёт пустую строку вместо sha.
        """
        sha = artifact_branch.commit_files(
            "T999", {"tasks/T999/marker.txt": "x\n"}, "тест AC-3: карпентерский коммит")
        self.assertNotEqual("", sha)
