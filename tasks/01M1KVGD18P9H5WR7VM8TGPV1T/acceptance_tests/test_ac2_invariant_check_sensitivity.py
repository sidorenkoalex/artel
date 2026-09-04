"""AC-2 (tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md), первая клауза:
«Инвариант-тест из AC-1 красный на тесте, который пишет в настоящий
репозиторий пульта напрямую (мутация: прямой subprocess.run(["git",
"update-ref", …], cwd=config.ROOT))…»

Вторая клауза («…и зелёный после перевода PreviousVerdictShaTest…») —
отдельный файл `test_ac2_previous_verdict_sha_test_migration.py`: разная
краснота (эта проверка не зависит от кода задачи вовсе, тот файл красен
до реализации требования 3) не укладывается в один файл под одним
маркером «Красен/Зелёный», см. test-authoring, «Краснота — объяснённая,
не по умолчанию».

Зелёный с рождения: предмет проверки — код этой же приёмочной планки
(`_util.refs_snapshot`/`diff_refs`), не код задачи. Снимок-сравнение
обязан ловить прямую запись в НАСТОЯЩИЙ репозиторий пульта независимо
от того, реализована ли миграция `PreviousVerdictShaTest` — иначе
`test_ac1_full_suite_ref_isolation.py` и
`test_ac2_previous_verdict_sha_test_migration.py` молчаливо доверяли бы
непроверенному инструменту.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import diff_refs, refs_snapshot  # noqa: E402


class Ac2InvariantCheckSensitivityTest(unittest.TestCase):

    def test_ac2_direct_update_ref_bypass_is_detected(self):
        """Канареечная прямая запись `subprocess.run(["git","update-ref",
        …], cwd=config.ROOT)` — ровно та мутация, что называет AC-2, —
        меняет снимок ссылок настоящего репозитория пульта, и сравнение
        снимков её замечает.

        Ловит мутацию: `_util.refs_snapshot`/`diff_refs` написаны неверно
        (например, снимают только `refs/heads/*` без `refs/artifacts/*`,
        сравнивают по неверному ключу, или сравнение тавтологично всегда
        пусто) — тогда канареечная ветка осталась бы незамеченной, и
        соседние файлы этой планки ложно зеленели бы вне зависимости от
        реальной утечки.
        """
        before = refs_snapshot()
        canary = f"refs/heads/ac2-canary-{abs(id(self))}"
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
        try:
            subprocess.run(["git", "update-ref", canary, head], cwd=config.ROOT,
                           capture_output=True, text=True, check=True)
            after = refs_snapshot()
            changed = diff_refs(before, after)
            self.assertNotEqual({}, changed)
            self.assertIn(canary, changed)
            self.assertEqual((None, head), changed[canary])
        finally:
            subprocess.run(["git", "update-ref", "-d", canary], cwd=config.ROOT,
                           capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
