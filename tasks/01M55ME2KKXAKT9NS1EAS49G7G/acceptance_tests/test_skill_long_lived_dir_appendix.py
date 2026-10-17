"""AC-1…AC-3: приложение PLAN.md к `skills/test-authoring.md` — абзац о каталоге долгоживущих тестов.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет в ссылке документов — его пишет разработчик вместе с приложением; тесты AC-1…AC-3 падают на чтении PLAN.md (кроме проверки пустого диффа ветки внутри AC-3).

PLAN.md читается помощником пульта (`artifact_text`), приложения
разбираются `scripts/guard.py::plan_appendices` — тем же разбором, которым
пульт применяет их на мерже. Сам скил защищён и в ветке не меняется
(критерии SPEC), поэтому его содержимое проверяется по копии: файл из
HEAD рабочей копии кладётся во временный каталог и на него накладывается
приложение (`git apply`). Если приложение уже в дереве (прогон после
мержа) — копией служит дерево как есть, а «до» восстанавливается
обратным наложением.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text, changed_paths  # noqa: E402

if CODE_ROOT and CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)
from scripts import guard  # noqa: E402

SKILL = "skills/test-authoring.md"
FIRST_LINE = ("Долгоживущий файл пишется не в `tasks/<id>/acceptance_tests/`, "
              "а в")
LAST_LINE_END = "своей задачи покрывает критерий."

# Текст «Стало» из SPEC 01M551W0TFCT2XRQ71XFXJDKB9 («Материалы», «Готовый
# текст правки `skills/test-authoring.md`»), приведённый в «Материалах»
# SPEC этой задачи.
EXPECTED = """\
Долгоживущий файл пишется не в `tasks/<id>/acceptance_tests/`, а в
каталог долгоживущих тестов проекта в кодовой ветке задачи (назван в
задании роли; у артели — `tests/`), с префиксом задачи в имени по
шаблону проекта: у артели
`tests/test_<id задачи в нижнем регистре>_<имя>.py`, `<имя>` — из
`[a-z0-9_]` (конкретный каталог и префикс называет задание роли).
Долгоживущий файл в `acceptance_tests/` выход из `tests_writing`
отклоняет. В кодовой ветке test_author только ДОБАВЛЯЕТ такие файлы:
правку, переименование и удаление существующих файлов каталога
долгоживущих тестов, файл без префикса и любую правку вне этого каталога
пульт откатывает на чекпоинте шага, а выход из `tests_writing`
отклоняет. Свои файлы коммитит пульт; пока задача в `tests_writing`, их
можно править и удалять. На выходе пульт фиксирует их перечнем сумм
`acceptance_tests/long_lived.sha256.txt` под тем же локом, что планку, и
гоняет в одном прогоне с ней; метод `test_ac<n>_…` долгоживущего файла
своей задачи покрывает критерий."""


def _git_apply(cwd: str, diff: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "apply", *flags, "-"], cwd=cwd, input=diff,
                          capture_output=True, text=True)


def plan_text() -> str:
    text = artifact_text("PLAN.md")
    if text is None:
        raise AssertionError("PLAN.md нет в ссылке документов задачи")
    return text


def appendices_of(text: str) -> list:
    appendices, errors = guard.plan_appendices(text)
    if errors:
        raise AssertionError(f"приложения PLAN не разобраны: {errors}")
    return appendices


def skill_diff(text: str) -> str:
    mine = [a for a in appendices_of(text) if SKILL in a.paths]
    if not mine:
        raise AssertionError(f"в PLAN.md нет приложения к {SKILL}")
    return "".join(a.diff for a in mine)


def head_skill() -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"HEAD:{SKILL}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"{SKILL} не прочитан из HEAD: {res.stderr}")
    return res.stdout


def apply_to_copy(original: str, diff: str) -> tuple[str, str]:
    """(файл до приложения, файл с приложением) по копии `original`.

    Прямое наложение не прошло, а обратное прошло — приложение уже в
    дереве. Не прошло ни одно — AssertionError с выводом git."""
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
                f"приложение к {SKILL} не накладывается на дерево ни прямо, "
                f"ни обратно:\n{forward.stderr}\n{reverse.stderr}")
        undone = _git_apply(tmp, diff, "--reverse")
        if undone.returncode != 0:
            raise AssertionError(undone.stderr)
        return target.read_text(encoding="utf-8"), original


def split_paragraph(text: str) -> tuple[str, str, str]:
    """(текст до абзаца, абзац, текст после) — абзац от строки FIRST_LINE
    до первой строки, оканчивающейся LAST_LINE_END."""
    lines = text.splitlines(keepends=True)
    starts = [n for n, line in enumerate(lines) if line.rstrip("\n") == FIRST_LINE]
    if len(starts) != 1:
        raise AssertionError(f"строка начала абзаца встречается {len(starts)} "
                             f"раз(а) вместо одного: {FIRST_LINE!r}")
    start = starts[0]
    for end in range(start, len(lines)):
        if lines[end].rstrip("\n").endswith(LAST_LINE_END):
            return ("".join(lines[:start]), "".join(lines[start:end + 1]),
                    "".join(lines[end + 1:]))
    raise AssertionError(f"после начала абзаца нет строки, оканчивающейся "
                         f"{LAST_LINE_END!r}")


class SkillLongLivedDirAppendixTest(unittest.TestCase):

    def test_ac1_single_appendix_applies_and_plan_confirms_check(self):
        """PLAN несёт ровно одно приложение к скилу, оно применимо, и PLAN подтверждает проверку.

        Сценарий: PLAN.md из ссылки документов разбирается
        `guard.plan_appendices` — ошибок нет, приложение одно, его пути —
        ровно `("skills/test-authoring.md",)`; его диф проходит
        `git apply --check` на дереве HEAD (ветка скил не меняет — это
        дерево main; после мержа — обратная проверка); текст PLAN вне
        блоков ```diff называет `git apply --check`.

        Ловит мутацию: блок ```diff без строки `diff --git …` — guard
        возвращает ошибку `APPENDIX_NO_HEADER_ERROR` и пустой список; хедер
        хунка не совпадает с реальным диапазоном файла — `git apply
        --check` отказывает; диф разбит на два приложения или в него
        попал второй файл — приложений/путей больше одного; PLAN не
        упоминает выполненную проверку — в прозе нет `git apply --check`.
        """
        text = plan_text()
        appendices, errors = guard.plan_appendices(text)
        self.assertEqual([], errors, "ошибки разбора приложений PLAN")
        self.assertEqual(1, len(appendices),
                         f"приложений {len(appendices)} вместо одного: "
                         f"{[a.paths for a in appendices]}")
        self.assertEqual((SKILL,), tuple(appendices[0].paths))
        diff = appendices[0].diff
        forward = apply_check(diff)
        if forward:
            reverse = apply_check(diff, reverse=True)
            self.assertEqual("", reverse,
                             f"приложение не проходит git apply --check:\n"
                             f"{forward}\n{reverse}")
        prose = re.sub(r"(?ms)^```diff\b.*?^```[ \t]*$", "", text)
        self.assertIn("git apply --check", prose,
                      "PLAN.md вне блоков ```diff не подтверждает проверку "
                      "`git apply --check`")

    def test_ac2_patched_paragraph_equals_target_text(self):
        """После наложения абзац о месте долгоживущих файлов равен тексту «Стало» байт в байт.

        Сценарий: приложение PLAN накладывается на копию скила из HEAD;
        в результате находится абзац от строки «Долгоживущий файл пишется
        не в `tasks/<id>/acceptance_tests/`, а в» до строки, оканчивающейся
        «своей задачи покрывает критерий.»; он сравнивается с текстом
        «Стало» SPEC 01M551W0TFCT2XRQ71XFXJDKB9.

        Ловит мутацию: приложение оставило буквальное «существующих файлов
        `tests/`»/«вне `tests/`» вместо «каталога долгоживущих тестов»,
        потеряло уточнение «у артели — `tests/`» или переломало строки
        иначе, чем в «Стало», — абзац отличается от ожидаемого.
        """
        _before, after = apply_to_copy(head_skill(), skill_diff(plan_text()))
        _head, paragraph, _tail = split_paragraph(after)
        self.assertEqual(EXPECTED, paragraph.rstrip("\n"))

    def test_ac3_only_paragraph_changes_and_branch_is_empty(self):
        """Приложение меняет только абзац AC-2 скила, а кодовая ветка не меняет ни одного файла.

        Сценарий: каждое приложение PLAN называет ровно
        `skills/test-authoring.md`; у копии скила до и после наложения
        совпадают весь текст до абзаца AC-2 (в том числе правила
        статической проверки долгоживущего файла) и весь текст после
        него; `changed_paths()` помощника (закоммиченный дифф от базы
        плюс неотслеживаемые файлы вне `tasks/<id>/`) пуст.

        Ловит мутацию: приложение заодно переписало пункт правил
        статической проверки (строки 93-112) или раздел о помощнике
        `_pult.py` — текст до/после абзаца иной; разработчик правит скил
        прямо в ветке или регенерирует карту `docs/codebase-map.md` — путь
        появляется в `changed_paths()`; в приложение попал второй файл —
        путь вне скила.
        """
        paths = changed_paths()
        self.assertEqual([], paths,
                         f"кодовая ветка задачи меняет файлы: {paths}")
        text = plan_text()
        for appendix in appendices_of(text):
            self.assertEqual((SKILL,), tuple(appendix.paths),
                             f"приложение PLAN трогает не только {SKILL}: "
                             f"{appendix.paths}")
        before, after = apply_to_copy(head_skill(), skill_diff(text))
        head_b, _par_b, tail_b = split_paragraph(before)
        head_a, _par_a, tail_a = split_paragraph(after)
        self.assertEqual(head_b, head_a, "изменён текст скила до абзаца AC-2")
        self.assertEqual(tail_b, tail_a, "изменён текст скила после абзаца AC-2")


if __name__ == "__main__":
    unittest.main()
