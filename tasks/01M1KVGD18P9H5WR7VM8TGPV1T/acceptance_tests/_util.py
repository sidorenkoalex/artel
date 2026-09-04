"""Общие помощники приёмочной планки 01M1KVGD18P9H5WR7VM8TGPV1T (SPEC:
«Изоляция тестов от настоящего репозитория: артефактная ветка из
песочницы»).

`refs_snapshot`/`cleanup_new_refs` дублируют механику, которую
требование 1 SPEC описывает как «снимок git for-each-ref до и после
прогона» (AC-1/AC-2): штатная реализация этого инварианта — правка
защищённых путей (`tests/sandbox.py`, `tests/test_invariants.py`,
`.github/workflows/ci.yml`), которые эта ветка не несёт (SPEC «Не
входит», ANSWER-1 — поставляются unified-diff-приложением к PLAN.md,
Оператор применяет их отдельно после `merge_gate`). Приёмочная планка
не может импортировать код, которого здесь нет — та же логика снимка
ссылок продублирована здесь напрямую и не зависит от того, применён ли
уже диф.
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


def cleanup_new_refs(before: dict, after: dict) -> None:
    """Убирает ссылки, появившиеся между `before` и `after`, и восстанавливает
    ссылки, которые СУЩЕСТВОВАЛИ раньше, но сдвинули sha, на снимок `before`
    (ADR-0012, ANSWER-2 п.1, R1-F5).

    Настоящий репозиторий пульта общий на все параллельные сессии —
    приёмочный тест, диагностирующий утечку записи, не имеет права сам
    оставлять после себя новый мусор сверх уже накопленного, который он
    же и обнаружил (репозиторий на момент подготовки этой планки уже
    нёс тысячи веток `artifact/*` от прошлых утечек — тот самый дефект,
    который описывает SPEC «Контекст»), ни оставлять СУЩЕСТВОВАВШУЮ раньше
    ссылку сдвинутой на чужой sha."""
    for refname in sorted(after.keys() - before.keys()):
        if refname.startswith("refs/heads/"):
            subprocess.run(["git", "branch", "-D", refname[len("refs/heads/"):]],
                           cwd=config.ROOT, capture_output=True, text=True)
        elif refname.startswith("refs/artifacts/"):
            subprocess.run(["git", "update-ref", "-d", refname],
                           cwd=config.ROOT, capture_output=True, text=True)
    shifted = before.keys() & after.keys()
    for refname in sorted(refname for refname in shifted
                          if before[refname] != after[refname]):
        subprocess.run(["git", "update-ref", refname, before[refname]],
                       cwd=config.ROOT, capture_output=True, text=True)
