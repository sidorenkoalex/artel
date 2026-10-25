"""Дописывает копию таблицы `mutation-run-<n>.tsv` в раздел PLAN.md
«Мутации до» (`--before`) или «Мутации после» (`--after`) — перед меткой
конца раздела. Порядок требования 2 SPEC: вывод части в PLAN до старта
следующей.

python3 add_table.py --before 1
python3 add_table.py --after 22 --status "<вывод git status>"
"""
import argparse
import pathlib

DOCS = pathlib.Path(__file__).resolve().parent
MARK = {"before": "<!-- конец мутаций до -->", "after": "<!-- конец мутаций после -->"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=int)
    ap.add_argument("--after", type=int)
    ap.add_argument("--status", default="")
    args = ap.parse_args()
    kind = "before" if args.before else "after"
    run = args.before or args.after
    table = (DOCS / f"mutation-run-{run}.tsv").read_text(encoding="utf-8").rstrip("\n")
    plan = DOCS / "PLAN.md"
    text = plan.read_text(encoding="utf-8")
    head = f"Часть №{run}:\n\n"
    if kind == "after":
        head = (f"Перед частью №{run}: `git status --porcelain -- orchestrator/ "
                f"scripts/` — вывод пуст{args.status}\n\n")
    block = f"{head}```\n{table}\n```\n\n"
    assert f"# mutation-run №{run} " not in text, f"таблица №{run} уже в PLAN"
    text = text.replace(MARK[kind], block + MARK[kind])
    plan.write_text(text, encoding="utf-8")
    print(f"таблица №{run} дописана в раздел «Мутации {'до' if kind == 'before' else 'после'}»")


if __name__ == "__main__":
    main()
