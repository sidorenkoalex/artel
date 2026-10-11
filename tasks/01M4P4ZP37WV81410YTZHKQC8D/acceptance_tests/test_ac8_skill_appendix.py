"""Приложение PLAN к `skills/test-authoring.md`: указание запускать предпроверку.

Группа: разовый

Красен до реализации: PLAN.md задачи ещё не написан — `artifact_text("PLAN.md")` отдаёт None, приложения к скилу нет.

Источник PLAN — ссылка документов задачи через помощник пульта
(`_pult.artifact_text`). Приложения разбирает тот же
`guard.plan_appendices`, что гейт приложений пульта. Каждое приложение к
скилу по порядку PLAN накладывается `git apply --include` на копию
скила из рабочей копии кода во временном каталоге; рабочая копия не
меняется. Применимость приложения к дереву ветки держит гейт приложений
пульта — здесь проверяется только текст скила после наложения.

AC-1–AC-7, AC-9, AC-10 и остальная часть AC-8 (белый список ролей,
`store.db()`, файл БД только на чтение) — в долгоживущем файле задачи
`tests/` кодовой ветки.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text  # noqa: E402

if CODE_ROOT and str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))
from scripts import guard  # noqa: E402

SKILL = "skills/test-authoring.md"
PREFLIGHT = re.compile(r"artel\.py\s+preflight\b")
BEFORE_HANDING = re.compile(r"перед\s+(сдач|заверш)|до\s+(сдач|заверш)", re.I)
GIT_LOCATING_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


def apply_to_copy(original: str, diff: str) -> tuple[str | None, str]:
    """(текст скила после наложения `diff`, ответ git при отказе).

    Рубеж перехода гоняет планку на дереве «ветка + приложения PLAN»
    (`orchestrator/appendix_tree.py::suite_tree`): там приложение к скилу
    уже наложено. Признак «уже наложено» — только `git apply --reverse
    --check` всего приложения на копии (то же правило, что
    `plan_appendix.in_base`); частично наложенное обратную проверку не
    проходит и идёт обычным наложением — отказ git (правка Оператора по
    ADR-0012 п.(а), amend-tests 11.10.2026)."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATING_ENV}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / SKILL
        path.parent.mkdir(parents=True)
        path.write_text(original, encoding="utf-8")
        applied = subprocess.run(
            ["git", "apply", "--reverse", "--check", f"--include={SKILL}", "-"],
            cwd=tmp, input=diff, capture_output=True, text=True, env=env)
        if applied.returncode == 0:
            return original, ""
        res = subprocess.run(["git", "apply", f"--include={SKILL}", "-"],
                             cwd=tmp, input=diff, capture_output=True,
                             text=True, env=env)
        if res.returncode != 0:
            return None, (res.stderr or res.stdout).strip()
        return path.read_text(encoding="utf-8"), ""


def skill_after_plan(plan: str, original: str) -> tuple[str | None, str]:
    """(скил после приложений PLAN к нему, причина неудачи)."""
    appendices, errors = guard.plan_appendices(plan)
    own = [a for a in appendices if SKILL in a.paths]
    if not own:
        return None, f"в PLAN.md нет приложения к {SKILL}; ошибки разбора: {errors}"
    text = original
    for number, appendix in enumerate(own, 1):
        text, answer = apply_to_copy(text, appendix.diff)
        if text is None:
            return None, f"приложение {number} к {SKILL} не легло: {answer}"
    return text, ""


def preflight_paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n[^\S\n]*\n", text) if PREFLIGHT.search(p)]


def added_text(plan: str) -> str:
    """Текст строк «+» приложений PLAN к скилу (без заголовков `+++`):
    абзац о предпроверке обязан прийти из приложения, а не уже стоять в
    скиле."""
    appendices, _errors = guard.plan_appendices(plan)
    lines = []
    for appendix in (a for a in appendices if SKILL in a.paths):
        lines += [line[1:] for line in appendix.diff.splitlines()
                  if line.startswith("+") and not line.startswith("+++")]
    return "\n".join(lines)


class SkillAppendixTest(unittest.TestCase):

    def test_ac8_plan_appendix_puts_preflight_into_skill(self):
        """Скил после приложения PLAN велит запускать `artel.py preflight <id>` перед сдачей шага.

        Сценарий: PLAN.md читается из ссылки документов, приложения к
        `skills/test-authoring.md` накладываются по порядку на копию скила
        рабочей копии кода. В тексте после наложения есть абзац с
        `artel.py preflight`, и этот же абзац говорит о сдаче (завершении)
        шага словами «перед сдачей/завершением» либо «до сдачи/завершения».

        Ловит мутацию: приложения к скилу нет (правка скила забыта или
        сделана в ветке задачи, а не приложением) — PLAN без приложения;
        приложение упоминает команду без связи со сдачей шага — абзаца с
        `artel.py preflight` и «перед сдачей» нет.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        original = (Path(CODE_ROOT) / SKILL).read_text(encoding="utf-8")
        text, why = skill_after_plan(plan, original)
        self.assertIsNotNone(text, why)
        paragraphs = preflight_paragraphs(text)
        self.assertTrue(paragraphs, f"после наложения в {SKILL} нет абзаца с "
                                    f"«artel.py preflight»")
        self.assertTrue(any(BEFORE_HANDING.search(p) for p in paragraphs),
                        f"абзацы с «artel.py preflight» не говорят о запуске "
                        f"перед сдачей шага: {paragraphs}")
        own = preflight_paragraphs(added_text(plan))
        self.assertTrue(any(BEFORE_HANDING.search(p) for p in own),
                        f"строки «+» приложения к {SKILL} не несут абзаца с "
                        f"«artel.py preflight» и «перед сдачей»: {own}")


if __name__ == "__main__":
    unittest.main()
