"""Бриф analyst, developer, spec_auditor, добавка test_author и пакет
ревьювера задачи артели побайтно равны эталону, снятому с кода базы ветки
задачи (main) при том же `run_id`.

Группа: разовый

Зелёный с рождения: до правки задачи код ветки и код базы совпадают, эталон снимается с базы тем же сценарием — тексты равны; краснеет, если правка задачи меняет бриф или пакет задачи артели.

Сценарий исполняется дважды в отдельных процессах — на коде базы диффа
задачи (`_pult.DIFF_BASE`, дерево выгружено `git archive` во временный
каталог, без `tasks/`) и на коде рабочей копии (`_pult.CODE_ROOT`):
песочница `tests.sandbox.RealGitSandbox` своего дерева, на `main` пульта —
шаблоны своего дерева, `CLAUDE.md` пульта и свежая карта, ветка задачи
артели с правкой кода, документы задачи (SPEC, TZ, PLAN, ANSWER-1) в
ссылке `refs/artifacts/<id>`; `brief.new_run_id` отдаёт постоянный
идентификатор, автор, дата и конфиг git постоянны — sha коммитов от
прогона к прогону не меняются. Путь временного корня песочницы в текстах
заменён меткой. Сборка — публичные `brief.analyst_map_component`,
`brief.developer_brief`, `brief.spec_auditor_brief`,
`brief.test_author_answer_component`, `review.review_package`.
"""
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

FIXED_ENV = {
    "GIT_AUTHOR_NAME": "artel etalon", "GIT_AUTHOR_EMAIL": "etalon@example.invalid",
    "GIT_COMMITTER_NAME": "artel etalon",
    "GIT_COMMITTER_EMAIL": "etalon@example.invalid",
    "GIT_AUTHOR_DATE": "2026-10-25T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-10-25T00:00:00+0000",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

SCENARIO = r'''
import json
import os
import shutil
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.getcwd())
from tests.sandbox import RealGitSandbox  # noqa: E402
from orchestrator import brief, config, review, store  # noqa: E402

RUN_ID = "0123456789abcdef0123456789abcdef"
TASK = "01HX5Q3V9E7T2K8M4N6P0R1S2W"
BRANCH = "task/01hx5q3v9e7t2k8m4n6p0r1s2w-etalon"
DOCS = {
    "SPEC.md": "# SPEC\n\nЭталонная SPEC задачи артели.\n",
    "TZ.md": "# ТЗ\n\nЭталонное ТЗ задачи артели.\n",
    "PLAN.md": "# PLAN\n\nЭталонный PLAN задачи артели.\n",
    "ANSWER-1.md": "---\ntask: " + TASK + "\ntype: answer\nauthor_role: operator\n"
                   "status: ready\nschema_version: 2\n---\n\n# ANSWER-1\n\n"
                   "Эталонный ответ Оператора.\n",
}


def main(out):
    sb = RealGitSandbox()
    sb.setUp()
    try:
        root = sb.root
        conn = store.db()
        shutil.copytree(Path.cwd() / "templates", root / "templates")
        (root / "CLAUDE.md").write_text("# Конвенции пульта эталона\n",
                                        encoding="utf-8")
        sb.git("add", "templates", "CLAUDE.md")
        sb.git("commit", "-q", "-m", "пульт")
        sha = sb.git("rev-parse", "HEAD").strip()
        (root / "docs").mkdir(exist_ok=True)
        (root / brief.MAP_REL).write_text(
            "---\nbuilt_at_sha: " + sha + "\n---\n\n# Карта эталона\n",
            encoding="utf-8")
        sb.git("add", "docs")
        sb.git("commit", "-q", "-m", "карта")
        sb.git("checkout", "-q", "-b", BRANCH)
        (root / "kod.py").write_text("ZNACHENIE = 2\n", encoding="utf-8")
        sb.git("add", "kod.py")
        sb.git("commit", "-q", "-m", "правка задачи")
        sb.git("checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(conn, TASK, "Эталон задачи артели", "in_dev", BRANCH,
                          config.DEFAULT_TARGET, 25.0)
        src = root / ".artel" / "docs-src"
        for name, body in DOCS.items():
            path = src / config.TASKS.name / TASK / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        with mock.patch.dict(os.environ,
                             {"GIT_INDEX_FILE": str(root / ".artel" / "docs.index")}):
            sb.git("--work-tree", str(src), "add", "-A")
            tree = sb.git("write-tree").strip()
        commit = sb.git("commit-tree", tree, "-m", "документы").strip()
        sb.git("update-ref", "refs/artifacts/" + TASK, commit)

        results = {}
        with mock.patch.object(brief, "new_run_id", return_value=RUN_ID):
            for role, build in (
                    ("analyst", lambda: brief.analyst_map_component(conn, TASK)),
                    ("developer", lambda: brief.developer_brief(conn, TASK)),
                    ("spec_auditor", lambda: brief.spec_auditor_brief(conn, TASK)),
                    ("test_author",
                     lambda: brief.test_author_answer_component(conn, TASK)),
                    ("reviewer", lambda: review.review_package(
                        conn, TASK, "Эталон задачи артели", BRANCH)["text"])):
                try:
                    text = build()
                except SystemExit as exc:
                    text = "SystemExit: " + str(exc.code)
                if isinstance(text, str):
                    for form in {str(root), os.path.realpath(root)}:
                        text = text.replace(form, "@ROOT@")
                results[role] = text
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False)
    finally:
        sb.doCleanups()


main(sys.argv[1])
'''


def run_scenario(tree: Path, work: Path, tag: str) -> dict:
    """Тексты пяти точек сценария на коде дерева `tree`."""
    script = work / f"scenario-{tag}.py"
    script.write_text(SCENARIO, encoding="utf-8")
    out = work / f"out-{tag}.json"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k != "PYTHONPATH"}
    env.update(FIXED_ENV)
    env["PYTHONPATH"] = str(tree)
    res = subprocess.run([sys.executable, str(script), str(out)], cwd=tree,
                         env=env, capture_output=True, text=True, timeout=100)
    assert res.returncode == 0, (
        f"сценарий на {tag} упал ({res.returncode}):\n{res.stdout}\n{res.stderr}")
    return json.loads(out.read_text(encoding="utf-8"))


def export_base(work: Path) -> Path:
    """Дерево кода базы диффа задачи без `tasks/` — во временный каталог."""
    tree = work / "base"
    tree.mkdir()
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "archive", "--format=tar",
                          DIFF_BASE, "--", ".", ":(exclude)tasks"],
                         capture_output=True, timeout=100)
    assert res.returncode == 0, f"git archive {DIFF_BASE}: {res.stderr!r}"
    with tarfile.open(fileobj=io.BytesIO(res.stdout)) as tar:
        tar.extractall(tree, filter="data")
    return tree


def test_ac6_artel_briefs_equal_base_etalon():
    """Задача артели на фиксированном входе (SPEC, TZ, PLAN, ANSWER-1,
    ветка с правкой кода, свежая карта, тот же `run_id`).

    Бриф analyst, developer, spec_auditor, добавка test_author и пакет
    ревьювера, собранные кодом рабочей копии, побайтно равны собранным
    кодом базы ветки задачи; эталон не пуст и у developer несёт SPEC
    задачи.

    Зелёный с рождения: держит неизменность брифа и пакета ролей артели —
    правка задачи, задевшая их (компонент `conventions.md`, пометка «не
    разобраны», строка фильтра обвязки или сдвиг частей у артели),
    красит сравнение."""
    assert DIFF_BASE, "база диффа задачи не определена"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        etalon = run_scenario(export_base(work), work, "base")
        actual = run_scenario(Path(CODE_ROOT), work, "head")
    assert "Эталонная SPEC задачи артели." in (etalon["developer"] or ""), \
        "эталон developer без SPEC задачи — сценарий собрал не тот бриф"
    for role, text in etalon.items():
        assert isinstance(text, str) and not text.startswith("SystemExit:"), \
            f"эталон {role} не собран: {text!r}"
    for role in ("analyst", "developer", "spec_auditor", "test_author",
                 "reviewer"):
        assert actual[role] == etalon[role], f"{role}: бриф артели изменился"
