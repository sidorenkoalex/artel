"""AC-1…AC-5: приложение PLAN.md к `skills/spec-authoring.md` — два пункта раздела «## Границы».

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет в артефактной ветке — его пишет разработчик вместе с приложением; каждый тест падает на чтении PLAN.md.

Источник PLAN.md — артефактная ветка (`gitcmd.show`), разбор приложений —
тем же `guard.plan_appendices`, которым пульт применяет их на мерже. Сам
скил защищён и в ветке не меняется, поэтому его содержимое проверяется по
копии: файл из головы ветки задачи выкладывается во временный каталог, на
него накладывается приложение (`git apply`); если приложение уже лежит в
дереве (прогон после мержа) — сверяется обратное наложение, и копией
служит дерево как есть. Смысл пунктов — опорами (основы слов, номера
прецедентов), не точной формулировкой: формулировка — на усмотрение роли
(требование 3 SPEC).
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd
from scripts import guard

TASK_ID = "01M41VH0Z3CQ0WY039SV1ERGMB"
SKILL = "skills/spec-authoring.md"
BOUNDS = "## Границы"
FORBIDDEN = "## Запрещено"

# Опоры пункта AC-1: тест в tests/ — по свойству, не по месту; свойство,
# которое держит долгоживущий приёмочный тест, SPEC повторно не требует;
# основания — ADR-0020 и пересчёт 03.10.2026.
AC1_STEMS = ("tests/", "свойств", "мест", "долгоживущ", "повтор",
             "adr-0020", "03.10.2026")
# Опоры пункта AC-2: правка приложением к защищённому пути, сторож внутри
# приложения, не отдельным файлом tests/ ветки; основание — ликвидация.
AC2_STEMS = ("приложени", "защищ", "сторож", "tests/",
             "01m41jyghtp8zvxvpef8k8w381")
# Опоры AC-3: замер «после» по CI ветки не заказывается; «до» — по CI
# main, «после» — первый CI main после мержа.
AC3_PATTERNS = (r"замер", r"\bci\b", r"ветк", r"\bmain\b", r"мерж",
                r"\bдо\b", r"после")


def _git_apply(cwd: str, diff: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "apply", *flags, "-"], cwd=cwd, input=diff,
                          capture_output=True, text=True)


def plan_text() -> str:
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    if text is None:
        raise AssertionError(f"PLAN.md нет в артефактной ветке задачи: {reason}")
    return text


def skill_appendices(text: str) -> list:
    appendices, errors = guard.plan_appendices(text)
    if errors:
        raise AssertionError(f"приложения PLAN не разобраны: {errors}")
    mine = [a for a in appendices if SKILL in a.paths]
    if not mine:
        raise AssertionError(f"в PLAN.md нет приложения к {SKILL}")
    return appendices


def branch_skill() -> str:
    text, reason = gitcmd.show("HEAD", SKILL)
    if text is None:
        raise AssertionError(f"{SKILL} не прочитан из головы ветки: {reason}")
    return text


def apply_to_copy(original: str, diff: str) -> tuple[str, str]:
    """(файл до приложения, файл с приложением) по копии `original`.

    Прямое наложение не прошло, а обратное прошло — приложение уже в
    дереве: «до» восстанавливается обратным наложением, «с приложением» —
    сам `original`. Не прошло ни одно — AssertionError с выводом git."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / SKILL
        target.parent.mkdir(parents=True)
        target.write_text(original, encoding="utf-8")
        forward = _git_apply(tmp, diff, "--check")
        if forward.returncode == 0:
            done = _git_apply(tmp, diff)
            if done.returncode != 0:
                raise AssertionError(done.stderr)
            return original, target.read_text(encoding="utf-8")
        reverse = _git_apply(tmp, diff, "--check", "--reverse")
        if reverse.returncode != 0:
            raise AssertionError(
                f"приложение к {SKILL} не накладывается на дерево ветки ни "
                f"прямо, ни обратно:\n{forward.stderr}\n{reverse.stderr}")
        undone = _git_apply(tmp, diff, "--reverse")
        if undone.returncode != 0:
            raise AssertionError(undone.stderr)
        return target.read_text(encoding="utf-8"), original


def skill_diff(appendices: list) -> str:
    return "".join(a.diff for a in appendices if SKILL in a.paths)


def patched_skill() -> str:
    return apply_to_copy(branch_skill(), skill_diff(skill_appendices(plan_text())))[1]


def split_bounds(text: str) -> tuple[str, str, str]:
    """(текст до тела «## Границы», тело раздела, текст от следующего `## `)."""
    match = re.search(rf"^{re.escape(BOUNDS)}[ \t]*\n", text, re.M)
    if match is None:
        raise AssertionError(f"в {SKILL} нет раздела «{BOUNDS}»")
    nxt = re.search(r"^## ", text[match.end():], re.M)
    end = match.end() + nxt.start() if nxt else len(text)
    return text[:match.end()], text[match.end():end], text[end:]


def bullets(body: str) -> list[str]:
    """Пункты раздела (строка «- …» с продолжением) — сплошным текстом в нижнем регистре."""
    items, current = [], None
    for line in body.splitlines():
        if line.startswith("- "):
            current = [line[2:]]
            items.append(current)
        elif current is not None and line.strip():
            current.append(line.strip())
        elif not line.strip():
            current = None
    return [re.sub(r"\s+", " ", " ".join(item)).lower() for item in items]


def bound_bullets() -> list[str]:
    text = patched_skill()
    _head, body, tail = split_bounds(text)
    if not tail.startswith(FORBIDDEN):
        raise AssertionError(f"за «{BOUNDS}» идёт не «{FORBIDDEN}»: "
                             f"{tail.splitlines()[:1]}")
    return bullets(body)


def missing(item: str, stems) -> list[str]:
    return [s for s in stems if s not in item]


class SpecAuthoringAppendixTest(unittest.TestCase):

    def test_ac1_bounds_item_orders_tests_by_property(self):
        """В «## Границы» скила с приложением есть пункт «тест в tests/ — по свойству, не по месту».

        Сценарий: PLAN.md читается из артефактной ветки, его приложение к
        `skills/spec-authoring.md` накладывается на копию файла из ветки;
        в теле раздела «## Границы» (за ним — «## Запрещено») ищется один
        пункт, несущий все опоры: `tests/`, свойство, место, долгоживущий,
        повтор, ADR-0020 и дату пересчёта 03.10.2026.

        Ловит мутацию: пункт вписан в «## Запрещено» или «## Перед
        завершением» вместо «## Границы» — в теле «Границ» его нет; пункт
        без основания (не названы ADR-0020 или пересчёт 03.10.2026) — у
        пункта не хватает опоры; приложения к скилу в PLAN нет вовсе.
        """
        items = bound_bullets()
        best = min(items, key=lambda i: len(missing(i, AC1_STEMS)))
        self.assertEqual([], missing(best, AC1_STEMS),
                         f"нет пункта «## Границы» со всеми опорами AC-1; "
                         f"ближайший:\n{best}")

    def test_ac2_bounds_item_keeps_guard_inside_appendix(self):
        """В «## Границы» есть пункт: сторож правки приложением — внутри того же приложения.

        Сценарий: тот же скил с наложенным приложением; в «## Границы»
        ищется пункт с опорами: приложение, защищённый путь, сторож,
        `tests/` (не отдельным файлом `tests/` ветки) и основание —
        ликвидация 01M41JYGHTP8ZVXVPEF8K8W381.

        Ловит мутацию: пункт о стороже не назвал основание-прецедент
        01M41JYGHTP8ZVXVPEF8K8W381 — опоры нет; пункт добавлен в другой
        раздел файла — в «Границах» его нет.
        """
        items = bound_bullets()
        best = min(items, key=lambda i: len(missing(i, AC2_STEMS)))
        self.assertEqual([], missing(best, AC2_STEMS),
                         f"нет пункта «## Границы» со всеми опорами AC-2; "
                         f"ближайший:\n{best}")

    def test_ac3_after_measure_not_ordered_from_branch_ci(self):
        """Рядом с пунктом AC-2 сказано: замер «после» по CI ветки не заказывается.

        Сценарий: в «## Границы» скила с приложением находится пункт AC-2
        (сторож внутри приложения); в нём самом или в соседнем пункте
        (непосредственно до или после) есть опоры: замер, CI, ветка,
        `main`, мерж, «до» и «после».

        Ловит мутацию: правило о стороже добавлено, а правило о замере
        пропущено или оторвано от него в другой раздел — ни в пункте AC-2,
        ни рядом нет опор «замер»/«CI»/«после мержа».
        """
        items = bound_bullets()
        anchors = [n for n, i in enumerate(items) if not missing(i, AC2_STEMS)]
        self.assertTrue(anchors, "в «## Границы» нет пункта AC-2 — не к чему "
                                 "искать соседний пункт о замере")
        near = [items[k] for n in anchors for k in (n - 1, n, n + 1)
                if 0 <= k < len(items)]
        lacking = {}
        for item in near:
            lack = [p for p in AC3_PATTERNS if not re.search(p, item)]
            if not lack:
                return
            lacking[item[:80]] = lack
        self.fail(f"ни в пункте AC-2, ни рядом нет всех опор AC-3: {lacking}")

    def test_ac4_appendix_applies_and_plan_confirms_check(self):
        """Приложение к скилу накладывается на чистое дерево ветки, и PLAN подтверждает `git apply --check`.

        Сценарий: PLAN.md из артефактной ветки; приложение к
        `skills/spec-authoring.md` проверяется `git apply --check` на
        временном каталоге с файлом из головы ветки задачи (после мержа —
        обратное наложение); текст PLAN вне блоков ```diff называет
        проверку `git apply --check`.

        Ловит мутацию: хедер хунка не совпадает с реальным диапазоном
        файла — `git apply --check` отказывает в обе стороны; PLAN не
        упоминает выполненную проверку — в тексте вне диффа нет
        `git apply --check`.
        """
        text = plan_text()
        apply_to_copy(branch_skill(), skill_diff(skill_appendices(text)))
        prose = re.sub(r"(?ms)^```diff\b.*?^```[ \t]*$", "", text)
        self.assertIn("git apply --check", prose,
                      "PLAN.md вне блоков ```diff не подтверждает проверку "
                      "`git apply --check`")

    def test_ac5_appendix_only_adds_to_bounds_of_skill(self):
        """Приложения PLAN затрагивают только скил аналитика и только добавляют строки в «## Границы».

        Сценарий: все приложения PLAN.md разбираются `guard.plan_appendices`;
        каждое называет ровно `skills/spec-authoring.md`; в диффе нет
        удалённых строк; у файла до и после наложения совпадают всё до тела
        «## Границы» и всё от следующего раздела, а прежние строки тела
        «Границ» сохранены по порядку.

        Ловит мутацию: в приложение попал второй файл правил (например,
        `skills/test-authoring.md`) — путь вне разрешённого; правка заодно
        переписала строку «## Запрещено» или старый пункт «Границ» — в
        диффе есть строка «-», хвост файла после наложения иной.
        """
        appendices = skill_appendices(plan_text())
        for appendix in appendices:
            self.assertEqual((SKILL,), appendix.paths,
                             f"приложение PLAN трогает не только {SKILL}: "
                             f"{appendix.paths}")
        diff = skill_diff(appendices)
        removed = [line for line in diff.splitlines()
                   if line.startswith("-") and not line.startswith("---")]
        self.assertEqual([], removed, "приложение удаляет строки скила")
        before, after = apply_to_copy(branch_skill(), diff)
        head_b, body_b, tail_b = split_bounds(before)
        head_a, body_a, tail_a = split_bounds(after)
        self.assertEqual(head_b, head_a, "изменён текст до раздела «## Границы»")
        self.assertEqual(tail_b, tail_a, "изменён текст после раздела «## Границы»")
        rest = iter(body_a.splitlines())
        for line in body_b.splitlines():
            self.assertIn(line, rest, f"прежняя строка «Границ» потеряна: {line!r}")
        self.assertNotEqual(body_b, body_a, "приложение не добавило строк в «## Границы»")


if __name__ == "__main__":
    unittest.main()
