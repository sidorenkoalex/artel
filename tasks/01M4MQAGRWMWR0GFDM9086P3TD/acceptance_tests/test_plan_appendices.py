"""AC-1 (запись роли в roles.yaml) и AC-10 (шаблон templates/SPEC-AUDIT.md) — приложения PLAN к защищённым путям.

Обе правки едут приложением PLAN (SPEC, требования 5 и 8: защищённые пути
меняет Оператор), поэтому планка проверяет файл таким, каким он станет
после наложения приложения: PLAN.md читается из ссылки документов
помощником пульта (`_pult.artifact_text`), приложения разбирает тот же
`guard.plan_appendices`, что гейт применимости на выходе `in_dev` и мерж.
Приложение применяется к HEAD (`apply_check`) — текст «после» получается
наложением во временном репозитории на текст HEAD (или на пустоту, если
файла в HEAD нет); уже наложено в HEAD (Оператор внёс правку в main, ветка
его подтянула) — «после» и есть HEAD.

Запись роли читается тем же разбором, что у пульта (`roles.load`/
`roles.skills`/`roles.model_tier` над `config.ROLES`, подменённым на файл
после наложения); шаблон «заполняется» как его заполнил бы аудитор —
подставляются id задачи вместо `TASK_ID`, значения существующих строк
`status`/`verdict`/`signals`/`spec_sha` frontmatter — и проверяется
публичным `guard.check_content`.

Провалидирован на синтетическом PLAN (подмена `_pult.artifact_text`,
приложения сняты `git diff` с настоящего `roles.yaml` и нового шаблона) при
стабе типа `spec_audit` в guard: оба метода зелёные; мутант — ярус
`balanced` и шаблон без раздела «Пути обхода гейтов» — красил оба; стаб и
синтетика удалены, код не тронут.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`, приложений к roles.yaml и templates/SPEC-AUDIT.md нет; кроме того guard пока не знает тип spec_audit.
"""
import random
import re
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

from orchestrator import config, roles  # noqa: E402
from scripts import guard  # noqa: E402

ROLES_REL = "roles.yaml"
TEMPLATE_REL = "templates/SPEC-AUDIT.md"
AUDITOR = "spec_auditor"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def head_text(rel: str) -> str | None:
    res = git("-C", str(CODE_ROOT), "show", f"HEAD:{rel}")
    return res.stdout if res.returncode == 0 else None


def apply_to_text(diff: str, rel: str, text: str | None) -> str | None:
    """Текст `rel` после `git apply` приложения к `text` (`None` — файла
    нет) во временном репозитории; `None` — git отказал или файла нет."""
    with tempfile.TemporaryDirectory(prefix="spec-audit-plank-") as tmp:
        repo = Path(tmp)
        git("init", "-q", str(repo))
        path = repo / rel
        if text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        patch = repo / "appendix.diff"
        patch.write_text(diff, encoding="utf-8")
        res = git("-C", str(repo), "apply", "--include", rel, str(patch))
        if res.returncode != 0 or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")


def text_after_appendix(case: unittest.TestCase, rel: str) -> str:
    plan = artifact_text("PLAN.md")
    case.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов — "
                               f"приложение к {rel} вносит developer")
    appendices, errors = guard.plan_appendices(plan)
    case.assertEqual(errors, [], f"приложения PLAN не разобраны: {errors}")
    found = [a for a in appendices if rel in a.paths]
    case.assertEqual(len(found), 1, f"приложений к {rel} не одно: "
                                    f"{[a.paths for a in appendices]}")
    diff = found[0].diff
    head = head_text(rel)
    answer = apply_check(diff)
    if answer == "":
        after = apply_to_text(diff, rel, head)
        case.assertIsNotNone(after, f"git apply приложения к {rel} отказал")
        return after
    reverse = apply_check(diff, reverse=True)
    case.assertEqual(reverse, "", f"приложение к {rel} не применяется к HEAD "
                                  f"({answer}) и не наложено в нём ({reverse})")
    case.assertIsNotNone(head, f"{rel} нет в HEAD")
    return head


class RolesAppendixTest(unittest.TestCase):

    def test_ac1_roles_yaml_appendix_declares_spec_auditor(self):
        """roles.yaml после приложения PLAN несёт роль spec_auditor: executor agent, model_tier strong, скил spec-audit.

        Сценарий: текст `roles.yaml` после наложения приложения PLAN
        кладётся во временный файл, `config.ROLES` подменяется на него;
        `roles.load()["spec_auditor"]["executor"]` — `agent`,
        `roles.model_tier("spec_auditor")` — `strong`, среди
        `roles.skills("spec_auditor")` есть `spec-audit`.

        Ловит мутацию: приложение к `roles.yaml` не приложено или правит
        другую роль — записи `spec_auditor` нет; ярус задан иначе
        (`fast`/`balanced`) — модель аудитора не Opus; скил назван иначе
        (`spec-auditor`) — бриф аудитора без своего скила.
        """
        after = text_after_appendix(self, ROLES_REL)
        with tempfile.TemporaryDirectory(prefix="spec-audit-roles-") as tmp:
            path = Path(tmp) / "roles.yaml"
            path.write_text(after, encoding="utf-8")
            with mock.patch.object(config, "ROLES", path):
                entry = roles.load().get(AUDITOR)
                self.assertIsInstance(entry, dict, f"роли {AUDITOR} нет:\n{after}")
                self.assertEqual(entry.get("executor"), "agent", entry)
                self.assertEqual(roles.model_tier(AUDITOR), "strong", entry)
                self.assertIn("spec-audit", roles.skills(AUDITOR), entry)


class TemplateAppendixTest(unittest.TestCase):

    def fill(self, template: str, rng: random.Random) -> tuple:
        task = "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))
        text = template.replace("TASK_ID", task)
        match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
        self.assertIsNotNone(match, f"у шаблона нет frontmatter:\n{template}")
        values = {"task": task, "status": "ready",
                  "verdict": rng.choice(["pass", "concerns", "fail"]),
                  "signals": "нет",
                  "spec_sha": "".join(rng.choice("0123456789abcdef")
                                      for _ in range(40))}
        lines = match.group(1).splitlines()
        present = {line.split(":", 1)[0].strip() for line in lines if ":" in line}
        for key in ("verdict", "signals", "spec_sha"):
            self.assertIn(key, present, f"шаблон не несёт поля {key}:\n{template}")
        filled = []
        for line in lines:
            key = line.split(":", 1)[0].strip() if ":" in line else ""
            filled.append(f"{key}: {values[key]}" if key in values else line)
        body = text[match.end():]
        return task, "---\n" + "\n".join(filled) + "\n---\n" + body

    def test_ac10_template_passes_guard_after_filling(self):
        """templates/SPEC-AUDIT.md после приложения PLAN и заполнения полей проходит guard.

        Сценарий: шаблон после наложения приложения; `TASK_ID` заменён
        случайным id, строки `status`/`verdict`/`signals`/`spec_sha`
        frontmatter получают значения (вердикт — случайно из перечня);
        `guard.check_content` над результатом — без ошибок, тип —
        `spec_audit`.

        Ловит мутацию: в шаблоне нет одного из обязательных разделов или
        полей (guard отказывает либо поле не найдено); тип шаблона назван
        иначе, чем знает guard; шаблон не приложен вовсе.
        """
        seed = random.randrange(1 << 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        template = text_after_appendix(self, TEMPLATE_REL)
        task, text = self.fill(template, rng)
        self.assertRegex(text, r"(?m)^type:\s*spec_audit\s*$",
                         f"зерно {seed}: тип шаблона:\n{text}")
        label = "/".join(("tasks", task, "SPEC-AUDIT.md"))
        self.assertEqual(guard.check_content(label, text), [],
                         f"зерно {seed}:\n{text}")


if __name__ == "__main__":
    unittest.main()
