"""AC-14 — приложение PLAN к `targets.yaml`: применяется к дереву ветки и
приводит запись `artel` к действительности.

PLAN.md читается из ссылки документов задачи помощником пульта
(`_pult.artifact_text`); приложения разбирает тот же `guard.plan_appendices`,
что гейт применимости и мерж. Применимость — `_pult.apply_check` к дереву
HEAD рабочей копии (`targets.yaml` в кодовой ветке задачи не меняется, SPEC
«Не входит», — его текст в HEAD равен тексту `main`). «После наложения» —
приложение накладывается `git apply` на копию `targets.yaml` HEAD во
временном репозитории; итог читается штатным `orchestrator.targets.load`
при подменённом `config.TARGETS`.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`, приложения к `targets.yaml` нет.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import config, targets  # noqa: E402
from scripts import guard  # noqa: E402

TARGETS_REL = "targets.yaml"


def head_targets_text() -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"HEAD:{TARGETS_REL}"], capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"{TARGETS_REL} в HEAD не прочитан: {res.stderr}")
    return res.stdout


def record_comments(text: str, name: str) -> list[str]:
    """Строки-комментарии внутри записи `name` раздела `targets:` — от её
    заголовка до первой непустой строки с отступом меньше полей записи."""
    lines = text.splitlines()
    header = f"  {name}:"
    if header not in lines:
        raise AssertionError(f"записи {name} нет в тексте:\n{text}")
    comments = []
    for line in lines[lines.index(header) + 1:]:
        if line.strip() and len(line) - len(line.lstrip(" ")) < 4:
            break
        if line.lstrip().startswith("#"):
            comments.append(line.strip())
    return comments


class TargetsAppendixTest(unittest.TestCase):

    def appendix(self):
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], f"приложения PLAN не разобраны: {errors}")
        found = [a for a in appendices if TARGETS_REL in a.paths]
        self.assertEqual(len(found), 1,
                         f"приложений к {TARGETS_REL} не одно: "
                         f"{[a.paths for a in appendices]}")
        return found[0]

    def applied(self, appendix) -> tuple[str, Path]:
        """(текст `targets.yaml` после наложения, его путь во временном
        репозитории)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        (repo / TARGETS_REL).write_text(head_targets_text(), encoding="utf-8")
        patch = repo / "appendix.diff"
        patch.write_text(appendix.diff, encoding="utf-8")
        res = subprocess.run(["git", "-C", str(repo), "apply", str(patch)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git apply: {res.stderr}")
        path = repo / TARGETS_REL
        return path.read_text(encoding="utf-8"), path

    def test_ac14_targets_appendix_applies_and_mirrors_protected_paths(self):
        """Приложение к `targets.yaml` применяется и делает `no_paths` записи `artel` зеркалом `config.PROTECTED_PATHS`.

        Сценарий: из PLAN.md ссылки документов берётся единственное
        приложение к `targets.yaml`; `git apply --check` к HEAD проходит.
        После наложения на копию `targets.yaml` HEAD: `targets.load`
        проходит без ошибок (проверка `targets.check` всех записей);
        `no_paths` записи `artel` по множеству равно `config.PROTECTED_PATHS`
        (без повторов); ни один комментарий записи `artel` не называет поле
        декларацией; остальные поля записи `artel` и все прочие записи
        файла равны прежним.

        Ловит мутацию: приложение переписано вручную с хедером хунка, не
        совпадающим с файлом, — `git apply --check` отказывает; в `no_paths`
        потеряна запись пульта (маска `**/conftest.py`) или добавлена
        лишняя — множества расходятся; комментарий «Пока это декларация…»
        оставлен; приложение заодно поменяло `merge_gate`/профиль записи —
        прочие поля разошлись.
        """
        appendix = self.appendix()
        answer = apply_check(appendix.diff)
        self.assertEqual(answer, "", f"приложение к {TARGETS_REL} не "
                                     f"применяется к HEAD: {answer}")

        before_dir = tempfile.TemporaryDirectory()
        self.addCleanup(before_dir.cleanup)
        before_path = Path(before_dir.name) / TARGETS_REL
        before_path.write_text(head_targets_text(), encoding="utf-8")
        with mock.patch.object(config, "TARGETS", before_path):
            before = targets.load()

        text, path = self.applied(appendix)
        with mock.patch.object(config, "TARGETS", path):
            try:
                after = targets.load()
            except targets.TargetsError as exc:
                self.fail(f"targets.yaml после приложения не проходит check: {exc}")

        artel = after[config.DEFAULT_TARGET]
        no_paths = artel["no_paths"]
        self.assertEqual(len(no_paths), len(set(no_paths)),
                         f"повторы в no_paths: {no_paths}")
        self.assertEqual(set(no_paths), set(config.PROTECTED_PATHS),
                         f"no_paths: {sorted(no_paths)}; PROTECTED_PATHS: "
                         f"{sorted(config.PROTECTED_PATHS)}")

        comments = record_comments(text, config.DEFAULT_TARGET)
        self.assertFalse([c for c in comments if "декларац" in c.lower()],
                         f"комментарий записи artel называет поле декларацией: "
                         f"{comments}")

        old_artel = dict(before[config.DEFAULT_TARGET])
        new_artel = dict(artel)
        old_artel.pop("no_paths")
        new_artel.pop("no_paths")
        self.assertEqual(new_artel, old_artel, "прочие поля записи artel изменены")
        self.assertEqual({k: v for k, v in after.items()
                          if k != config.DEFAULT_TARGET},
                         {k: v for k, v in before.items()
                          if k != config.DEFAULT_TARGET},
                         "прочие записи targets.yaml изменены")


if __name__ == "__main__":
    unittest.main()
