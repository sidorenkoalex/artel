"""Факт задачи: приложения PLAN.md дают те же пять файлов, что Приложения 1–5 TZ.md.

Группа: разовый
Красен до реализации: PLAN.md с приложениями ещё не написан — `artifact_text("PLAN.md")` отдаёт None.

Тексты PLAN.md и TZ.md читаются только помощником пульта `artifact_text`
(ссылка документов), не с диска каталога задачи. Наложение идёт во
временном индексе git во временном каталоге, собранном из дерева HEAD
рабочей копии: рабочая копия, её индекс и ветка не меняются.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

from scripts import guard  # noqa: E402

PATHS = ("skills/spec-authoring.md", "templates/SPEC.md", "skills/spec-audit.md",
         "skills/test-authoring.md", "skills/review-checklist.md")
DIFF_BLOCK = re.compile(r"^```diff[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
DIFF_GIT = re.compile(r"^diff --git a/(\S+) b/", re.M)
GIT_TIMEOUT = 60


def _git(*args, index=None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    if index:
        env["GIT_INDEX_FILE"] = index
    return subprocess.run(["git", "-C", CODE_ROOT, *args], env=env,
                          capture_output=True, text=True, timeout=GIT_TIMEOUT,
                          start_new_session=True)


def _tz_blocks(text):
    """Блоки ```diff TZ.md, все заголовки `diff --git` которых — среди PATHS."""
    out = []
    for block in DIFF_BLOCK.findall(text):
        heads = DIFF_GIT.findall(block)
        if heads and all(h in PATHS for h in heads):
            out.append(block)
    return out


def _blobs_after(diffs):
    """({путь: sha блоба} после наложения `diffs` по порядку на дерево HEAD,
    "") либо (None, ответ git)."""
    with tempfile.TemporaryDirectory(prefix="ac1-") as tmp:
        index = str(Path(tmp) / "index")
        res = _git("read-tree", "HEAD", index=index)
        if res.returncode:
            return None, res.stderr
        for n, diff in enumerate(diffs):
            patch = Path(tmp) / f"{n}.diff"
            patch.write_text(diff, encoding="utf-8")
            res = _git("apply", "--cached", str(patch), index=index)
            if res.returncode:
                return None, f"блок {n}: {res.stderr}\n{diff[:200]}"
        tree = _git("write-tree", index=index).stdout.strip()
        blobs = {}
        for path in PATHS:
            res = _git("rev-parse", f"{tree}:{path}")
            blobs[path] = res.stdout.strip() if res.returncode == 0 else None
        return blobs, ""


@pytest.mark.parametrize("path", PATHS)
def test_ac1_plan_appendices_equal_tz_appendices(path):
    """Наложение приложений PLAN.md и Приложений 1–5 TZ.md на HEAD даёт одно содержимое файла.

    Во временном индексе от дерева HEAD по очереди накладываются
    приложения PLAN.md (разбор `guard.plan_appendices`, тот же, что у
    пульта) и — отдельно — пять блоков ```diff разделов «Приложение 1» …
    «Приложение 5» TZ.md; sha блоба файла `path` в двух деревьях совпадает,
    и PLAN.md несёт приложение к этому файлу.

    Ловит мутацию: в PLAN.md пропущено одно из приложений, перенесено с
    правкой строки текста или с другим хунком — файла нет среди путей
    приложений PLAN либо sha его блоба расходится с деревом по TZ.md.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md задачи нет в ссылке документов"
    appendices, errors = guard.plan_appendices(plan)
    assert errors == [], f"ошибки разбора приложений PLAN.md: {errors}"
    assert path in {p for a in appendices for p in a.paths}, \
        f"PLAN.md: нет приложения к {path}"
    tz = _tz_blocks(artifact_text("TZ.md") or "")
    assert len(tz) == 5, f"в TZ.md найдено {len(tz)} блоков приложений вместо 5"
    expected, why = _blobs_after(tz)
    assert expected is not None, f"Приложения TZ.md не накладываются на HEAD: {why}"
    actual, why = _blobs_after([a.diff for a in appendices])
    assert actual is not None, f"приложения PLAN.md не накладываются на HEAD: {why}"
    assert expected[path] is not None, f"{path}: файла нет в дереве по TZ.md"
    assert actual[path] == expected[path], path
