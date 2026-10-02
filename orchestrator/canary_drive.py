"""Вход ведения учебной задачи канарейки кодом проверяемого коммита (SPEC
01M3PKSWPETC49WFTFZ69GH3F2; ADR-0021, этап 0; ADR-0019 п.2).

Исполняется ОТДЕЛЬНЫМ процессом интерпретатора из эфемерного клона пульта
(`python -m orchestrator.canary_drive …`, рабочий каталог — клон), который
заводит `orchestrator/canary.py::_run_task_in_ephemeral_clone`. Поэтому
весь код ведения — `catalog.cmd_new`, `workspace.ensure`,
`canary._drive_task` с помощниками гейтов, подъёмом потолка, потолком
повторов developer и синтетическим ответом на эскалацию — здесь код
КЛОНА, то есть проверяемого коммита, а не код пина процесса пульта: до
этой задачи пульт вёл учебную задачу сам, и изменения переходов, гейтов и
запуска ролей канарейка до `pin-update` не проверяла (прецедент 29.09,
задача 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ).

Пути `config` здесь переадресовывать не нужно: `config.ROOT` вычисляется
от расположения самого модуля, то есть в этом процессе это и есть клон.
Всё, что эфемерный клон пульт готовит сам (`catalog.cmd_init`, локальный
слой моделей набора, указатель связки ключей Codex), к старту процесса уже
лежит в клоне. Из состояния процесса пульта передаются venv
(`--venv-dir`) и, для набора с Codex, адрес постоянного профиля
(`--codex-home`). Клон собственного venv не заводит.

Обмен с пультом — ОДИН JSON-объект в файле `--result`, путь которого
передал пульт (`build_result`); поток вывода процесса — только
диагностика, пульт его не разбирает. Файл пишется целиком через
временный соседний файл и `replace`: оборванная запись не должна
выглядеть результатом.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import canary, catalog, config, gitcmd, store, workspace
from .providers import codex as codex_provider

#: Поля строки журнала, которые пульт читает из шагов результата —
#: выдержка журнала (`canary._journal_excerpt_lines`) и файл диагностики
#: (`canary._save_diagnostics`).
STEP_FIELDS = ("ts", "actor", "action", "detail")


def drive(template_path: Path) -> dict:
    """Заводит учебную задачу из шаблона и ведёт её до конца тем же
    порядком, что `canary._drive_task`; возвращает объект результата.

    HEAD клона снимается ДО заведения задачи: результат обязан называть
    коммит, чей код загружен в этот процесс, а не то, что стало с веткой
    по ходу ведения.
    """
    head = gitcmd.head_sha()
    conn = store.db()
    task_id = catalog.cmd_new(template_path.stem, tz_path=str(template_path),
                              canary=True)
    # `cmd_new` (A7) не заводит worktree/кодовую ветку задачи — это делает
    # `runner.role_cwd` на первом РЕАЛЬНОМ шаге агента. Заводим заранее и
    # идемпотентно тем же вызовом, как и до переноса ведения в клон.
    t = store.get_task(conn, task_id)
    _wt_path, wt_error = workspace.ensure(task_id, t["branch"])
    if wt_error is not None:
        raise RuntimeError(f"canary: worktree для {task_id} не создан: {wt_error}")
    canary._drive_task(conn, task_id)
    return build_result(conn, task_id, head)


def build_result(conn, task_id: str, head: str) -> dict:
    """Объект результата (SPEC, требование 2): id задачи, HEAD клона, шаги
    журнала, метрики задачи, исход и фактическая эскалация.

    Метрики считает код клона (`canary._task_metrics`) — пульт их не
    пересчитывает: журнал задачи живёт в БД клона и умирает вместе с ним.
    `escalated` — отдельное булево поле, а не вывод из `metrics`: пульт
    сверяет его с маркером шаблона и не обязан знать форму списка эскалаций.
    """
    steps = [{field: row[field] for field in STEP_FIELDS}
             for row in store.task_steps(conn, task_id)]
    metrics = canary._task_metrics(conn, task_id)
    return {
        "task_id": task_id,
        "head": head,
        "outcome": metrics["outcome"],
        "escalated": bool(metrics["escalations"]),
        "metrics": metrics,
        "steps": steps,
    }


def write_result(path: Path, result: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m orchestrator.canary_drive",
        description="Ведение учебной задачи канарейки кодом этого клона.")
    parser.add_argument("--template", required=True,
                        help="шаблон ТЗ учебной задачи (файл пула)")
    parser.add_argument("--result", required=True,
                        help="файл, куда записать JSON-объект результата")
    parser.add_argument("--venv-dir", default=None,
                        help="venv пульта, которым исполняется клон")
    parser.add_argument("--codex-home", default=None,
                        help="отдельный постоянный профиль Codex канарейки")
    args = parser.parse_args(argv)

    if args.venv_dir is not None:
        config.VENV_DIR = Path(args.venv_dir)
    if args.codex_home is not None:
        codex_provider.set_codex_home_override(Path(args.codex_home))
    # Вывод ведения (`store.set_state`, `cleanup.cmd_kill`, …) — в поток
    # диагностики; пульт сохраняет его в каталог диагностики прогона.
    result = drive(Path(args.template))
    write_result(Path(args.result), result)
    print(f"[canary-drive] {result['task_id']}: исход={result['outcome']}, "
          f"код {result['head']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
