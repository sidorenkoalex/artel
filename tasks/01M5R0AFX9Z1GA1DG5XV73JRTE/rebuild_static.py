"""Восстанавливает plan_static.txt (шаблон make_plan.py) из PLAN.md:
генерируемые разделы заменяются метками {{…}}."""
import pathlib
import re

DOCS = pathlib.Path(__file__).resolve().parent
text = (DOCS / "PLAN.md").read_text(encoding="utf-8")

text = re.sub(r"^status: \w+$", "status: {{STATUS}}", text, count=1, flags=re.M)


def block(text, head, body_re, mark):
    """Заменяет подряд идущие строки списка после заголовка/вступления."""
    new, n = re.subn(body_re, lambda m: m.group(1) + mark + "\n", text, count=1, flags=re.S | re.M)
    assert n == 1, head
    return new


text = block(text, "patches",
             r"(## Мутации: патчи и заявки\n.*?\n\n)(?:- mutation-\d{3} .*?\n)+", "{{PATCHES}}")
text = block(text, "kills",
             r"(## Строки падения и соответствие «до → после»\n.*?\n\n)(?:- mutation-\d{3}: .*?\n)+",
             "{{KILLS}}")
text = block(text, "seeds", r"(## Зерно\n\n)(?:- mutation-\d{3}: .*?\n)+", "{{SEEDS}}")
text = block(text, "before",
             r"(## Мутации до\n.*?вывод частей дословно\.\n\n).*?(?=\n## Мутации после)", "{{BEFORE}}")
text = block(text, "after",
             r"(## Мутации после\n.*?вывод частей дословно\.\n\n).*?(?=\n## Замеры)", "{{AFTER}}")
text = re.sub(r"^- После свода \(HEAD\):.*$", "{{COUNTS}}", text, count=1, flags=re.M)
text = re.sub(r"(контрольных прогонов `mutation-run` \(без патча\): ).*$", r"\1{{TIMES}}.",
              text, count=1, flags=re.M)
for mark in ("{{STATUS}}", "{{PATCHES}}", "{{KILLS}}", "{{SEEDS}}", "{{BEFORE}}",
             "{{AFTER}}", "{{COUNTS}}", "{{TIMES}}"):
    assert text.count(mark) == 1, mark
(DOCS / "plan_static.txt").write_text(text, encoding="utf-8")
print("ok")
