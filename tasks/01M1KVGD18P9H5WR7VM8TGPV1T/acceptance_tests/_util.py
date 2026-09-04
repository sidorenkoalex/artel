"""Общие помощники приёмочной планки 01M1KVGD18P9H5WR7VM8TGPV1T (SPEC:
«Изоляция тестов от настоящего репозитория: артефактная ветка из
песочницы»).

`refs_snapshot`/`diff_refs` дублируют механику, которую требование 1
SPEC описывает как «снимок git for-each-ref до и после прогона»
(AC-1/AC-2): штатная реализация этого инварианта — правка защищённых
путей (`tests/sandbox.py`, `tests/test_invariants.py`,
`.github/workflows/ci.yml`), которые эта ветка не несёт (SPEC «Не
входит», ANSWER-1 — поставляются unified-diff-приложением к PLAN.md,
Оператор применяет их отдельно после `merge_gate`). Приёмочная планка
не может импортировать код, которого здесь нет — та же логика снимка
ссылок продублирована здесь напрямую и не зависит от того, применён ли
уже диф.

ANSWER-4: планка НЕ убирает за собой расхождение снимков (прежняя
`cleanup_new_refs` удаляла/форс-ресетила ссылки в настоящем репозитории
пульта — общем на все параллельные сессии — и могла задеть настоящую
ветку чужой задачи, появившуюся/сдвинувшуюся во время дорогого прогона;
REVIEW.md итерация 4, R4-F1). При расхождении тест просто падает и
перечисляет разошедшиеся ссылки в сообщении об ошибке — без побочных
эффектов на состояние репозитория.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

# refs/artifacts/* — задел механики снапшота задач (см. artifact_branch.py
# докстринг про `GIT_INDEX_FILE`/`refs/artifacts/*`, tasks/T094); AC-1
# называет оба префикса явно.
REF_PREFIXES = ("refs/heads/", "refs/artifacts/")


def refs_snapshot() -> dict:
    """{refname: sha} всех ссылок под `REF_PREFIXES` настоящего репозитория
    пульта (`config.ROOT`) прямо сейчас."""
    out = {}
    for prefix in REF_PREFIXES:
        res = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname) %(objectname)", prefix],
            cwd=config.ROOT, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            refname, sha = line.split()
            out[refname] = sha
    return out


def diff_refs(before: dict, after: dict) -> dict:
    """{refname: (sha_до, sha_после)} — расхождения снимков; пусто, если
    снимки совпадают. `sha_до`/`sha_после` — `None`, если ссылка
    появилась/пропала."""
    return {k: (before.get(k), after.get(k))
            for k in before.keys() | after.keys()
            if before.get(k) != after.get(k)}
