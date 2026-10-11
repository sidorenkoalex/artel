"""Приложения PLAN к шаблонам и скилам аналитика и аудитора: применимость к
голове кода и годность шаблона QUESTIONS после наложения (AC-8).

Группа: разовый

Красен до реализации: PLAN.md задачи ещё не написан — `artifact_text("PLAN.md")` отдаёт None, приложений к templates/QUESTIONS.md, templates/SPEC.md, skills/spec-authoring.md и skills/spec-audit.md нет.

Провалидирован стабом в памяти процесса (репозиторий не правился): PLAN
с четырьмя приложениями, снятыми `git diff` с текущих файлов (пример
QUESTIONS переписан в форму матрицы), и временная проверка матрицы в
guard — оба теста зелены; без приложения к skills/spec-audit.md красен
первый, пример без одной метки — оба, без проверки матрицы в guard —
второй.

PLAN.md читается помощником пульта `artifact_text` из ссылки документов
задачи; приложения разбирает `guard.plan_appendices` — тот же разбор, что
гейт применимости на выходе `in_dev` и применение на мерже. Применимость —
`apply_check` помощника: `git apply --check` к дереву HEAD рабочей копии
(ветка задачи защищённых путей не меняет, их содержимое там — содержимое
main на базе ветки). Шаблон после наложения собирается во временном
каталоге: исходный `templates/QUESTIONS.md` из HEAD (`git show`), поверх —
приложения к нему по порядку (`git apply --include`), подставляется id
задачи и статус; guard — командой `python3 scripts/guard.py <файл>` из
корня рабочей копии.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, TASK_ID, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from scripts import guard  # noqa: E402

QUESTIONS_TEMPLATE = "templates/QUESTIONS.md"
REQUIRED_PATHS = (QUESTIONS_TEMPLATE, "templates/SPEC.md",
                  "skills/spec-authoring.md", "skills/spec-audit.md")
LABEL_LINE = re.compile(r"^\s*(?:-\s+)?(ломается|ослабляется|цена|чьё решение):")
VARIANT_LINE = re.compile(r"^\s*-\s+[A-Z]\)")
QUESTION_LINE = re.compile(r"^\d+\.\s")


def plan_appendices() -> list:
    plan = artifact_text("PLAN.md")
    if plan is None:
        raise AssertionError("PLAN.md задачи нет в ссылке документов")
    appendices, errors = guard.plan_appendices(plan)
    if errors:
        raise AssertionError(f"приложения PLAN не разобраны: {errors}")
    return appendices


def git(*args: str, cwd, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(cwd).parent)
    return subprocess.run(["git", *args], cwd=cwd, input=stdin, env=env,
                          capture_output=True, text=True, timeout=60)


def run_guard(path: Path) -> tuple:
    res = subprocess.run([sys.executable, str(Path(CODE_ROOT) / "scripts" / "guard.py"),
                          str(path)], cwd=CODE_ROOT, capture_output=True,
                         text=True, timeout=60)
    return res.returncode, res.stdout + res.stderr


def with_status(text: str, status: str) -> str:
    return re.sub(r"^status:.*$", f"status: {status}", text, count=1, flags=re.M)


def without_first_example_label(text: str) -> tuple:
    """(текст без первой строки метки матрицы первого варианта первого
    вопроса раздела «Вопросы», удалённая строка); строки нет — ("", "")."""
    lines = text.split("\n")
    in_section = seen_question = seen_variant = False
    for index, line in enumerate(lines):
        if line.startswith("## "):
            in_section = line.strip() == "## Вопросы"
            continue
        if not in_section:
            continue
        if not seen_question:
            seen_question = bool(QUESTION_LINE.match(line))
            continue
        if not seen_variant:
            seen_variant = bool(VARIANT_LINE.match(line))
            continue
        if LABEL_LINE.match(line):
            return "\n".join(lines[:index] + lines[index + 1:]), line
    return "", ""


class PlanAppendicesTest(unittest.TestCase):

    def test_ac8_appendices_apply_to_head(self):
        """Приложения PLAN к четырём защищённым файлам есть и применяются к HEAD рабочей копии.

        Сценарий: PLAN.md из ссылки документов, разбор приложений guard.
        Для каждого из `templates/QUESTIONS.md`, `templates/SPEC.md`,
        `skills/spec-authoring.md`, `skills/spec-audit.md` есть хотя бы
        одно приложение, и каждое такое приложение проходит
        `git apply --check` к дереву HEAD.

        Ловит мутацию: приложение к одному из файлов забыто — его
        подтест падает на «приложения нет»; контекст или число строк хунка
        не совпадает с файлом HEAD (дифф снят с устаревшей копии или
        поправлен руками) — `apply_check` отдаёт ответ git вместо пустой
        строки.
        """
        appendices = plan_appendices()
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                own = [a for a in appendices if path in a.paths]
                self.assertTrue(own, f"в PLAN нет приложения к {path}")
                for appendix in own:
                    self.assertEqual(apply_check(appendix.diff), "",
                                     f"приложение к {appendix.paths} не "
                                     f"применяется к HEAD")

    def test_ac8_questions_template_passes_guard_and_refuses_without_label(self):
        """Шаблон QUESTIONS после наложения приложений проходит guard в `draft` и `ready`, без метки примера — отказ.

        Сценарий: `templates/QUESTIONS.md` из HEAD во временном каталоге,
        поверх — приложения PLAN к нему по порядку; `TASK_ID` заменён id
        задачи. Со `status: draft` и `status: ready` guard выходит с кодом
        0. Без первой строки метки матрицы у первого варианта первого
        вопроса примера (`status: ready`) — ненулевой код.

        Ловит мутацию: пример шаблона оставлен в старой форме «варианты в
        строку» — guard отказывает исходному шаблону (и строки метки
        внутри варианта для второй половины нет); пример без одной метки
        у варианта — отказ guard шаблону; guard не проверяет матрицу —
        шаблон без метки проходит с кодом 0.
        """
        own = [a for a in plan_appendices() if QUESTIONS_TEMPLATE in a.paths]
        self.assertTrue(own, f"в PLAN нет приложения к {QUESTIONS_TEMPLATE}")
        original = git("show", f"HEAD:{QUESTIONS_TEMPLATE}", cwd=CODE_ROOT)
        self.assertEqual(original.returncode, 0, original.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / QUESTIONS_TEMPLATE
            target.parent.mkdir(parents=True)
            target.write_text(original.stdout, encoding="utf-8")
            for index, appendix in enumerate(own):
                patch = Path(tmp) / f"appendix-{index}.diff"
                patch.write_text(appendix.diff, encoding="utf-8")
                res = git("apply", f"--include={QUESTIONS_TEMPLATE}", str(patch),
                          cwd=tmp)
                self.assertEqual(res.returncode, 0,
                                 f"приложение {index} не наложилось: {res.stderr}")
            template = target.read_text(encoding="utf-8").replace("TASK_ID", TASK_ID)
            check = Path(tmp) / "QUESTIONS.md"
            for status in ("draft", "ready"):
                with self.subTest(status=status):
                    check.write_text(with_status(template, status), encoding="utf-8")
                    code, out = run_guard(check)
                    self.assertEqual(code, 0, f"шаблон ({status}) не прошёл "
                                              f"guard:\n{out}\n{template}")
            broken, removed = without_first_example_label(with_status(template, "ready"))
            self.assertTrue(broken, f"в примере шаблона нет строки метки "
                                    f"матрицы внутри варианта:\n{template}")
            check.write_text(broken, encoding="utf-8")
            code, out = run_guard(check)
            self.assertNotEqual(code, 0, f"без строки {removed!r} guard не "
                                         f"отказал:\n{out}\n{broken}")


if __name__ == "__main__":
    unittest.main()
