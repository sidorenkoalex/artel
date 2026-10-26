"""Фильтр ссылки эпика `refs/artifacts/epic-<id>` в местах перебора ссылок
документов (SPEC 01M5TBFCVFNN95BHH0E9C6KBKB, требование 15) — свойства,
которые без фильтра дают видимое расхождение: перечень ссылок origin
сверки `doctor`, ссылка документов каталога `tasks/<имя>/` в
`artifact-history-snapshots`, решение `artifact-branches-cleanup --execute`
об удалении ветки. Песочница и помощники — те же, что у долгоживущего
файла задачи `tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py`."""
from pathlib import Path

from orchestrator import config, doctor
from tests.test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans import (  # noqa: F401
    ARTIFACTS, both_in_origin, cli, note, stand)


def test_doctor_origin_refs_skip_epic_ref(stand):
    """Перечень ссылок origin, по которому `doctor` сверяет задачи, при обеих ссылках в origin несёт ссылку задачи с её головой и не несёт ссылку эпика.

    Ловит мутацию: `_origin_artifact_refs` не отсеивает
    `refs/artifacts/epic-…` — ссылка эпика в перечне сверки задач.
    """
    both_in_origin(stand)

    refs, reason = doctor._origin_artifact_refs(stand.root)

    assert refs is not None, note(stand, reason)
    assert refs.get(f"{ARTIFACTS}{stand.task}") == stand.task_sha, note(
        stand, f"{refs}")
    assert not [r for r in refs if stand.epic in r], note(
        stand, f"ссылка эпика в перечне сверки: {refs}")


def test_history_snapshots_epic_ref_is_no_docs_ref_of_dir(stand):
    """`artifact-history-snapshots --dry-run`: каталог main с именем ссылки эпика (`tasks/epic-<id>/`) не получает ссылку эпика своей ссылкой документов — он числится без ссылки, каталог задачи — со своей.

    Ловит мутацию: `_history_pass` не отсеивает `epic-…` из принесённых
    ссылок — ссылка эпика засчитана каталогу как снимок, «без ссылки 0».
    """
    for name in (stand.task, stand.epic_ref):
        rel = Path(config.TASKS.name) / name / "SPEC.md"
        (stand.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (stand.root / rel).write_text(f"SPEC {stand.seed}\n", encoding="utf-8")
        stand.git("add", str(rel))
    stand.git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
              "commit", "-qm", f"каталоги {stand.seed}")
    stand.git("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
    both_in_origin(stand)

    out, code = cli("artifact-history-snapshots", "--dry-run")

    assert code == 0, note(stand, f"dry-run ({code}):\n{out}")
    assert "со ссылкой 1, без ссылки 1" in out, note(stand, out)
    assert f"  {ARTIFACTS}{stand.epic_ref}\n" in out, note(stand, out)
    assert f"  {ARTIFACTS}{stand.task}\n" not in out, note(stand, out)


def test_cleanup_execute_keeps_branch_backed_only_by_epic_ref(stand):
    """`artifact-branches-cleanup --execute` при ветке `artifact/epic-<id>` в origin и ссылке эпика там же: отказ, называющий ключ ветки, ветка в origin цела.

    Ловит мутацию: опись засчитывает `refs/artifacts/epic-…` ссылкой
    документов задачи — ветка удаляется на основании ссылки эпика.
    """
    both_in_origin(stand)
    branch = f"artifact/{stand.epic_ref.lower()}"
    stand.git("push", "-q", str(stand.origin), f"HEAD:refs/heads/{branch}")

    out, code = cli("artifact-branches-cleanup", "--execute")

    assert code != 0 and stand.epic_ref.lower() in out, note(stand, out)
    left = stand.git("-C", str(stand.origin), "for-each-ref",
                     "--format=%(refname)", f"refs/heads/{branch}").strip()
    assert left == f"refs/heads/{branch}", note(stand, f"ветка удалена:\n{out}")
