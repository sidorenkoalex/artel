"""AC-14 — 01M300A14KRHCFB0DQXVCBJEKF: `models.yaml` в списке защищённых
путей, и сама ветка задачи этот файл не трогает.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. `config.PROTECTED_PATHS` содержит `models.yaml`, и ветка задачи
этого файла не трогает: в диффе ветки `models.yaml` нет, поэтому гейт зон
(`orchestrator/advance_gates/zones.py`, проверка защищённых путей диффа)
и джоб CI `protected-paths` (`.github/workflows/ci.yml`), читающие список
из ветки, на ветке задачи не отказывают.

Обе половины механические: состав списка читается прямо из `config`, а
дифф ветки — настоящим git этого рабочего каталога (тот же приём, что
`tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/_util.py` применяет к
дифу своей ветки: критерий говорит буквально о диффе КОДОВОЙ ветки, это
не воспроизвести песочницей с фейковым git). Формула «путь == запись или
начинается с неё» берётся у самого гейта зон, а не переписывается: джоб
CI применяет её же регуляркой.

Красен до реализации: `config.PROTECTED_PATHS`
(`orchestrator/config.py:615-618`) не содержит `models.yaml` — путь ПОКА
НЕ в списке по решению Оператора 20.09, и включить его — дело этой
задачи.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import config  # noqa: E402
from orchestrator.advance_gates import zones  # noqa: E402

CATALOG_PATH = "models.yaml"


def _merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции. Сначала
    `origin/main` (локальная `main` главной копии — пин пульта и
    отстаёт), затем `config.MAIN_BRANCH` для клона без origin."""
    for ref in ("origin/" + config.MAIN_BRANCH, config.MAIN_BRANCH):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=_tariff.REPO_ROOT, capture_output=True,
                             text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError(
        f"git merge-base не ответил ни по origin/{config.MAIN_BRANCH}, ни "
        f"по {config.MAIN_BRANCH} в {_tariff.REPO_ROOT}")


def _changed_paths() -> list:
    """Пути, изменённые веткой задачи относительно базы интеграции —
    включая незакоммиченное рабочее дерево."""
    res = subprocess.run(["git", "diff", "--name-only", _merge_base()],
                         cwd=_tariff.REPO_ROOT, capture_output=True,
                         text=True, check=True)
    return [line for line in res.stdout.splitlines() if line]


class ModelsCatalogIsProtectedAndUntouchedTest(unittest.TestCase):

    def test_ac14_catalog_is_in_protected_paths_and_not_in_the_branch_diff(self):
        """`models.yaml` объявлен защищённым путём, формула гейта зон его
        ловит, а в диффе ветки задачи этого пути нет — значит ни гейт
        зон, ни джоб CI `protected-paths` на этой ветке не отказывают.

        Ловит мутацию: путь дописан в `config.PROTECTED_PATHS` вместе с
        правкой самого `models.yaml` в этой же ветке — ровно то, из-за
        чего включение защиты и откладывали до части 2: оба читателя
        списка берут его ИЗ ВЕТКИ, и ветка красит собственный PR.
        Обратная мутация — путь в список не дописан вовсе — красит первую
        проверку.
        """
        self.assertIn(CATALOG_PATH, config.PROTECTED_PATHS)
        self.assertEqual([CATALOG_PATH],
                         zones._protected_paths_touched([CATALOG_PATH]))

        changed = _changed_paths()

        self.assertNotIn(CATALOG_PATH, changed)
        self.assertNotIn(CATALOG_PATH, zones._protected_paths_touched(changed))


if __name__ == "__main__":
    unittest.main()
