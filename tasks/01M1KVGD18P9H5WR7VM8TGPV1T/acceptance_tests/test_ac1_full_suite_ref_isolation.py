"""AC-1 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md): «Прогон полного
набора тестов не меняет набор ссылок (refs/heads/*, refs/artifacts/*)
настоящего репозитория пульта: снимок git for-each-ref до и после
прогона совпадает.»

«Полный набор тестов» — тот же прогон, что штатно гоняет CI (джоб
`python`, `.github/workflows/ci.yml`): `python3 -m unittest discover -s
tests -q` из корня репозитория. Снимок ссылок вокруг него — та же
механика, которую требование 1 SPEC поручает `tests/sandbox.py`
(базовый класс) и отдельному сторожу CI — оба защищённых пути не в
этой ветке (см. `_util.py`), поэтому сравнение продублировано здесь
напрямую (`_util.refs_snapshot`/`diff_refs`).

Дорогой тест: реальный прогон занимает несколько минут — то же
свойство, что и у самого критерия («весь прогон не трогает ссылки» не
доказать, не запустив весь прогон). ANSWER-4 (REVIEW.md итерация 4,
R4-F1): тест НЕ убирает за собой расхождение снимков — настоящий
репозиторий пульта общий на все параллельные сессии, и уборка,
удалявшая/форс-ресетившая ссылки по признаку «появилась/сдвинулась за
время прогона», не умела отличить утечку кода этой задачи от настоящей
чужой ветки, появившейся/сдвинувшейся за те же минуты — риск тихо
задеть параллельную сессию. При расхождении тест просто падает и
перечисляет разошедшиеся ссылки в сообщении об ошибке.

Красен до реализации: на сегодняшнем коде `tests/test_review_package.
py::PreviousVerdictShaTest` заводит задачу через `catalog.cmd_new` без
подмены `config.ROOT`; `cmd_new` коммитит артефакты в артефактную ветку
пульта через `artifact_branch.commit_files` → `write_commit`, который
зовёт `subprocess.run` напрямую в НАСТОЯЩЕМ `config.ROOT` (SPEC
«Контекст»). Прогон полного набора заводит как минимум одну новую
ветку `artifact/<id>` в этом самом репозитории — снимок «до» и «после»
расходится, тест падает. Эмпирически подтверждено при подготовке этой
планки: разовый прогон `python3 -m unittest discover -s tests -q` в
этом рабочем дереве действительно добавил новые ветки `artifact/*`,
которых не было в снимке «до».

Стаб корректной реализации для валидации этого теста не готовился:
«корректная реализация» AC-1 — это правка защищённых путей
(`tests/sandbox.py`, `tests/test_invariants.py`) и/или
`orchestrator/artifact_branch.py`/`tests/test_review_package.py`,
которые test_author не имеет права трогать (SPEC «Не входит»,
conventions-core). Валидация того, что само сравнение снимков не
тавтологично и действительно ловит прямую запись, — отдельно, дёшево
по времени, в `test_ac2_invariant_check_sensitivity.py`
(`Ac2InvariantCheckSensitivityTest`), канареечной мутацией той же
формы, что описывает AC-2.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import diff_refs, refs_snapshot  # noqa: E402

FULL_SUITE_TIMEOUT_SECONDS = 1200


class Ac1FullSuiteDoesNotMutateRealRepoTest(unittest.TestCase):
    """Прогон `tests/` целиком не меняет ссылки настоящего репозитория пульта."""

    def test_ac1_full_suite_run_leaves_refs_unchanged(self):
        """Снимок `git for-each-ref` (refs/heads/*, refs/artifacts/*) до и
        после `python3 -m unittest discover -s tests -q` совпадает.

        Ловит мутацию: любой тест внутри `tests/`, заводящий задачу через
        `catalog.cmd_new` (или иначе пишущий в git) без подмены
        `config.ROOT`/общей точки подмены требования 2 — после прогона в
        снимке появляется новая ветка `artifact/<id>` (или сдвигается
        голова существующей), которой не было «до»; сравнение расходится
        и тест падает.
        """
        before = refs_snapshot()
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=config.ROOT, capture_output=True, text=True,
            timeout=FULL_SUITE_TIMEOUT_SECONDS)
        self.assertIn(
            result.returncode, (0, 1),
            f"прогон tests/ не завершился штатно (код {result.returncode}): "
            f"{result.stderr[-2000:]}")
        after = refs_snapshot()
        changed = diff_refs(before, after)
        self.assertEqual(
            {}, changed,
            f"прогон tests/ изменил набор ссылок настоящего репозитория "
            f"пульта: {changed}")


if __name__ == "__main__":
    unittest.main()
