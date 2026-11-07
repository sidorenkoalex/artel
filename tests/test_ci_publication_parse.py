"""Строка публикации сценария CI для приёмки и её разбор в `ci` (SPEC
01M6TRKY1A41QSZMCXY9TKYXG7, требование 2; ANSWER-4 п. 1).

Свойства вне долгоживущих файлов задачи: строгость разбора, круг
«сценарий печатает — `ci` разбирает», равенство литералов сценария и пульта
(сценарий пакет пульта не импортирует), единственность проверки
`FULL_SUITE_JOB`. Граница `ci.gh` подменена; сети нет.
"""
import hashlib
import json
import random
import subprocess
from unittest import mock

import pytest

from orchestrator import ci
from scripts import guard, plan_appendix_ci


def rng_pair():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def hexes(rng, bits: int, count: int) -> list:
    return [f"{rng.getrandbits(bits):0{bits // 4}x}" for _ in range(count)]


def test_script_line_round_trips_through_ci_parser():
    """Строка `publication_line` сценария на каждом исходе разбирается `ci.parse_publication` в те же sha, исход и список по порядку.

    Ловит мутацию: сценарий печатает поля в другом порядке, другим
    разделителем или другим заголовком — разбор `ci` возвращает None или
    иные поля; `ci` теряет порядок списка (множество) — список не тот.
    """
    seed, rng = rng_pair()
    for outcome in ci.PUBLICATION_OUTCOMES:
        ref = "" if outcome == "no-ref" else hexes(rng, 160, 1)[0]
        diffs = (hexes(rng, 256, rng.randint(1, 4))
                 if outcome == ci.PUBLICATION_APPLIED else [])
        line = plan_appendix_ci.publication_line(ref, outcome, diffs)
        prefix = f"::notice title={ci.PUBLICATION_TITLE}::"
        assert line.startswith(prefix), f"{line!r}; зерно {seed}"
        parsed = ci.parse_publication(line[len(prefix):])
        assert parsed == ci.CiPublication(ref, outcome, tuple(diffs)), \
            f"{line!r} → {parsed!r}; зерно {seed}"


def test_script_and_pult_share_literals_and_digest_form():
    """Заголовок и исходы публикации у сценария и `ci` совпадают; дайджесты сценария и приёмки по одному PLAN равны.

    Ловит мутацию: литерал заголовка или исхода изменён только с одной
    стороны — приёмка перестаёт узнавать публикацию; форма хеша
    изменена у одной из сторон — списки расходятся.
    """
    assert plan_appendix_ci.PUBLICATION_TITLE == ci.PUBLICATION_TITLE
    assert (plan_appendix_ci.OUTCOME_APPLIED, plan_appendix_ci.OUTCOME_NO_PLAN,
            plan_appendix_ci.OUTCOME_NO_APPENDICES,
            plan_appendix_ci.OUTCOME_NO_REF) == ci.PUBLICATION_OUTCOMES
    from orchestrator import acceptance
    diff = ("--- a/CLAUDE.md\n+++ b/CLAUDE.md\n@@ -1 +1 @@\n-старое\n"
            "+новое ё\n")
    appendices = [guard.PlanAppendix(("CLAUDE.md",), diff)]
    expected = [hashlib.sha256(diff.encode("utf-8")).hexdigest()]
    assert plan_appendix_ci.appendix_digests(appendices) == expected
    assert acceptance.appendix_digests(appendices) == expected


@pytest.mark.parametrize("broken", [
    "upper_hex", "short_ref", "unknown_outcome", "short_digest",
    "trailing_text", "missing_diffs", "empty_item"])
def test_parser_rejects_off_form_text(broken):
    """Текст не в форме ANSWER-4 — `parse_publication` отдаёт None, а не частичную публикацию.

    Ловит мутацию: разбор по `search` вместо полного совпадения, допуск
    заглавных букв, неизвестного исхода или пустого элемента списка —
    поддельная или повреждённая строка принимается за публикацию.
    """
    seed, rng = rng_pair()
    ref, = hexes(rng, 160, 1)
    digests = hexes(rng, 256, 2)
    text = {
        "upper_hex": f"ref={ref.upper()}; outcome=applied; diffs={digests[0]}",
        "short_ref": f"ref={ref[:39]}; outcome=applied; diffs={digests[0]}",
        "unknown_outcome": f"ref={ref}; outcome=done; diffs={digests[0]}",
        "short_digest": f"ref={ref}; outcome=applied; diffs={digests[0][:63]}",
        "trailing_text": (f"ref={ref}; outcome=applied; "
                          f"diffs={','.join(digests)}; ещё"),
        "missing_diffs": f"ref={ref}; outcome=applied",
        "empty_item": f"ref={ref}; outcome=applied; diffs={digests[0]},,",
    }[broken]
    assert ci.parse_publication(text) is None, f"{text!r}; зерно {seed}"


def test_two_full_suite_checks_refuse_publication():
    """Две проверки `FULL_SUITE_JOB` у коммита — публикация не читается, причина одной строкой; аннотации не запрашиваются.

    Ловит мутацию: берётся первая из проверок `FULL_SUITE_JOB` — при двух
    попытках публикация одной из них принимается без однозначности.
    """
    seed, rng = rng_pair()
    sha, = hexes(rng, 160, 1)
    ids = rng.sample(range(10**6, 10**7), 2)
    calls = []

    def fake_gh(*args, **kwargs):
        text = " ".join(args)
        calls.append(text)
        if "/annotations" in text:
            line = plan_appendix_ci.publication_line(
                sha, ci.PUBLICATION_APPLIED, hexes(rng, 256, 1))
            message = line.split("::", 2)[2]
            body = [{"title": ci.PUBLICATION_TITLE, "message": message}]
        else:
            runs = [{"id": i, "name": ci.FULL_SUITE_JOB, "status": "completed",
                     "conclusion": "success"} for i in ids]
            body = {"total_count": len(runs), "check_runs": runs}
        return subprocess.CompletedProcess(args, 0, json.dumps(body), "")

    with mock.patch.object(ci, "gh", side_effect=fake_gh):
        published, why = ci.full_suite_publication(sha)
    assert published is None, f"{published!r}; зерно {seed}"
    assert why.strip() and "\n" not in why, f"{why!r}; зерно {seed}"
    assert not [c for c in calls if "/annotations" in c], f"{calls}; зерно {seed}"


def test_off_form_annotation_message_refuses_publication():
    """Единственная аннотация `plan-appendix-docs` с текстом не в форме — публикация не читается, причина одной строкой.

    Ловит мутацию: разбор сбоем отдаёт пустую публикацию вместо отказа —
    приёмка видит исход и список там, где их нет.
    """
    seed, rng = rng_pair()
    sha, = hexes(rng, 160, 1)
    check_id = rng.randrange(10**6, 10**7)

    def fake_gh(*args, **kwargs):
        text = " ".join(args)
        if f"check-runs/{check_id}/annotations" in text:
            body = [{"title": ci.PUBLICATION_TITLE,
                     "message": "ref=; outcome=applied\nлишняя строка"}]
        else:
            runs = [{"id": check_id, "name": ci.FULL_SUITE_JOB,
                     "status": "completed", "conclusion": "success"}]
            body = {"total_count": 1, "check_runs": runs}
        return subprocess.CompletedProcess(args, 0, json.dumps(body), "")

    with mock.patch.object(ci, "gh", side_effect=fake_gh):
        published, why = ci.full_suite_publication(sha)
    assert published is None, f"{published!r}; зерно {seed}"
    assert why.strip() and "\n" not in why, f"{why!r}; зерно {seed}"
