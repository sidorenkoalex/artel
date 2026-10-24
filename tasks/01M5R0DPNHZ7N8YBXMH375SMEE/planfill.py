"""Раздел PLAN.md с таблицами `mutation-run` дословно из копий `--copy-table`.

python3 planfill.py "<заголовок раздела>" <номера прогонов через запятую> [<файл вступления>]

Тело раздела `## <заголовок>` (до следующего `## `) заменяется: вступление
(текст файла, если задан) и для каждого прогона — блок ```text с копией
`mutation-run-<n>.tsv` как есть. Для раздела «Мутации после» перед каждым
блоком — строка о пустом выводе `git status --porcelain -- orchestrator/`,
который роль сверила перед стартом части."""
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent


def main() -> None:
    title, runs = sys.argv[1], [int(x) for x in sys.argv[2].split(",")]
    intro = (DOCS / sys.argv[3]).read_text(encoding="utf-8").rstrip("\n") + "\n\n" \
        if len(sys.argv) > 3 else ""
    plan = (DOCS / "PLAN.md").read_text(encoding="utf-8")
    head = f"## {title}\n"
    start = plan.index(head) + len(head)
    end = plan.find("\n## ", start)
    end = len(plan) if end < 0 else end + 1
    body = ["", intro.rstrip("\n")] if intro else [""]
    for run in runs:
        if "после" in title:
            body += [f"Перед прогоном №{run}: `git status --porcelain -- orchestrator/` "
                     f"— вывод пуст.", ""]
        copy = (DOCS / f"mutation-run-{run}.tsv").read_text(encoding="utf-8")
        body += ["```text", copy.rstrip("\n"), "```", ""]
    plan = plan[:start] + "\n".join(body).rstrip("\n") + "\n\n" + plan[end:]
    (DOCS / "PLAN.md").write_text(plan, encoding="utf-8")


if __name__ == "__main__":
    main()
