"""Команда `amend-tests`: штатная правка зафиксированной планки приёмки
(ADR-0012, tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Заменяет ручную цепочку «правка -> обновление tests_locked_sha прямой
записью в БД -> запись в журнал руками» (три случая 02.09, один — с
войной правок, один — с необнаруженной опечаткой 03.09) одной
атомарной, журналируемой командой с обязательным прогоном перед
фиксацией.

Оператор правит `tasks/<id>/acceptance_tests/` прямо в worktree задачи
(`workspace.path`) ДО вызова этой команды — сама команда только
фиксирует уже внесённую правку. Существо правки (неослабление покрытия)
не оценивает — зона ревьювера по чек-листу (ADR-0012 п.4); агентов не
запускает (SPEC требование 5).

ANSWER-3 (переработка после A7, вопрос 2): с A7 планка `tasks/<id>/`
живёт ТОЛЬКО в артефактной ветке пульта (`artifact_branch.branch_name`),
никогда в кодовой ветке задачи (`orchestrator/artifact_source.py`,
`fsm_advance.py::in_dev` — `lock_ref = branch`, всегда артефактная).
До этой правки команда коммитила правку в worktree КОДОВОЙ ветки и
сдвигала `tests_locked_sha` на её HEAD — асимметрия с гейтом `in_dev ->
review`, который сверяет лок с АРТЕФАКТНОЙ веткой: любой успешный
`amend-tests` немедленно ломал бы собственный переход (PLAN.md,
раздел «Эскалация», вопрос 2). Теперь команда читает правку Оператора
с диска worktree (как и раньше — это единственная поверхность, на
которой Оператор реально работает), но коммитит её ПЛОТНИЦКИ прямо на
артефактную ветку (`artifact_branch.commit_files`, тот же приём, что
`checkpoint._commit_external_step_artifacts`) и сдвигает `tests_locked_sha`
на HEAD именно этой ветки — ту же, с которой сверяет лок гейт.
"""
import sys
from pathlib import Path

from scripts import guard

from . import (acceptance, alerts, artifact_branch, config, fixation, gitcmd,
               lease, store, workspace, yamlmini)
from .advance_gates import acceptance as acceptance_gates

AMEND_ACTION = "правка планки"
DEVALUATION_ALERT_SOURCE = "amend_tests.window_threshold"
# Окно и порог — ADR-0012 п.3, ANSWER-1 вопрос 1 (вариант B): последние
# WINDOW_SIZE задач пульта, дошедших до фиксации лока, program-wide;
# больше WINDOW_THRESHOLD правок в этом окне поднимает алерт.
WINDOW_SIZE = 5
WINDOW_THRESHOLD = 1


def cmd_amend_tests(task_id: str, reason: str | None,
                    session_id: str | None = None,
                    from_branch: bool = False) -> None:
    """Берёт lease задачи перед работой — тем же приёмом, что и остальные
    мутирующие команды задачи (`answer.cmd_answer`/`fsm.cmd_approve`).

    Префикс -> полный id резолвится ЗДЕСЬ, до lease (тот же порядок,
    что у `answer.cmd_answer`/`workspace.cmd_workspace`).

    `from_branch` (SPEC 01M287TPG0HAVXS8CHBCY679WN, требование 3) —
    источник правки не worktree, а расхождение содержимого
    `acceptance_tests/` между `tests_locked_sha` и головой артефактной
    ветки; `False` (дефолт) — прежнее поведение без изменений (AC-9)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    if from_branch:
        lease.run_locked(
            conn, task_id, session_id,
            lambda sid: _cmd_amend_tests_from_branch(conn, task_id, reason))
        return
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_amend_tests(conn, task_id, reason))


def _worktree_changed_paths(wt_path: Path) -> list[str] | None:
    """Пути worktree с незакоммиченными изменениями (staged и unstaged,
    включая untracked), относительно корня репозитория worktree; `None`
    — git не ответил.

    `git status --porcelain`: каждая строка — `XY путь` либо, для
    переименований, `XY старый -> новый` (интересна только новая
    сторона — старого пути на диске уже нет).

    Источник AC-3 («изменения за пределами acceptance_tests/») — целиком
    worktree, не только `tasks/<id>/`: правка планки не имеет права
    тихо игнорировать любой сторонний незакоммиченный дифф worktree,
    не только соседние файлы задачи (PLAN.md и т.п.).

    `--untracked-files=all` — с A7 `tasks/<id>/` целиком НЕ отслеживается
    кодовой веткой (планка живёт только в артефактной ветке): без этого
    флага git схлопывает полностью untracked каталог в одну строку
    `?? tasks/`, и ни один путь под ним не сопоставится с префиксом
    `acceptance_tests/` — правка ошибочно читалась бы как «за пределами»
    целиком, даже валидная (найдено на AC-1: `outside` содержал буквально
    `tasks/`, не пофайловый путь)."""
    res = gitcmd.in_repo(wt_path, "status", "--porcelain",
                         "--untracked-files=all")
    if res is None or res.returncode != 0:
        return None
    paths = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest)
    return paths


def _materialize_tests_if_missing(task_id: str, tdir: Path) -> None:
    """Если `acceptance_tests/` ещё нет на диске worktree — заполняет её
    ТЕКУЩИМ содержимым артефактной ветки (ANSWER-3, вопрос 2: «если
    каталога нет — материализует его из артефактной ветки перед
    правкой»), прежде чем Оператор/эта же команда решают, есть ли
    реальная правка (AC-2). Каталог уже есть (Оператор уже положил
    правку) — не трогается вовсе, материализация поверх стёрла бы её."""
    tests_dir = tdir / "acceptance_tests"
    if tests_dir.is_dir():
        return
    prefix = f"tasks/{task_id}/acceptance_tests/"
    for rel, text in artifact_branch.read_tree(task_id).items():
        if not rel.startswith(prefix):
            continue
        dest = tdir / rel[len(f"tasks/{task_id}/"):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def _materialize_spec_if_missing(task_id: str, tdir: Path) -> Path | None:
    """SPEC.md ещё нет на диске worktree (обычный случай post-A7:
    `tasks/<id>/` живёт только в артефактной ветке) — подкладывает его
    ТЕКУЩИМ содержимым артефактной ветки, только чтобы `guard.
    acceptance_traceability_errors(tdir)` (требует SPEC.md на диске)
    вообще имел что прочитать (SPEC требование 1, AC-1). Возвращает путь
    к файлу, если он создан ИМЕННО этим вызовом — вызывающий код обязан
    убрать его после проверки: оставшись на диске, он торчал бы ВНЕ
    `acceptance_tests/` и следующий вызов `_worktree_changed_paths`
    ошибочно читал бы его как правку «за пределами» (AC-3 задачи
    01M1HNNHDMP2C1AJTH5QF1BTN2), ломая amend-tests для этого worktree
    навсегда. `None` — файл уже был на диске (трогать не надо), либо его
    нет и на артефактной ветке."""
    spec_path = tdir / "SPEC.md"
    if spec_path.is_file():
        return None
    text = artifact_branch.read_tree(task_id).get(f"tasks/{task_id}/SPEC.md")
    if text is None:
        return None
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(text, encoding="utf-8")
    return spec_path


def _refuse_traceability(conn, task_id: str, errors: list[str]) -> None:
    """Отказ по нарушенной трассируемости AC — общий для worktree- (AC-1)
    и `--from-branch`-пути (AC-3): один и тот же текст `sys.exit`, и
    журнальная запись актором `operator`, называющая сломанный критерий
    (AC-2). `AMEND_ACTION` («правка планки») здесь намеренно не
    переиспользуется — иначе отказ засчитывался бы `_amend_events_in_window`
    как состоявшуюся правку планки, хотя лок не сдвинулся."""
    reason = "; ".join(errors)
    store.journal(conn, task_id, "operator", "amend-tests отклонён",
                 f"трассируемость AC нарушена: {reason}")
    sys.exit(f"[{task_id}] amend-tests: отказ — трассируемость AC нарушена: "
             f"{reason}")


def _test_files(snapshot: dict[str, str]) -> list[tuple[str, str]]:
    return sorted((rel, text) for rel, text in snapshot.items()
                  if Path(rel).name.startswith("test_"))


def _group_line_errors(t, rel_tests_dir: str,
                       files: list[tuple[str, str]]) -> list[str]:
    """Ошибки строки группы правки (SPEC 01M3N0BWYQ9KHVN41Z4G72706R,
    требования 1-2, 7): только target `config.DEFAULT_TARGET` и только
    планка, зафиксированная после появления правила — её `test_*.py` на
    `tests_locked_sha` несут строку группы (`guard.plank_has_group_lines`;
    планка, зафиксированная раньше, строк группы не несёт и не
    проверяется). Лок не читается — сверять не с чем, правку не
    проверяем: тот же исход, что у планки до правила."""
    if t["target"] != config.DEFAULT_TARGET:
        return []
    # Задача — из `tasks/<id>/acceptance_tests`: её клон хранит лок.
    task_id = Path(rel_tests_dir).parts[1]
    locked = _branch_tests_snapshot(t["tests_locked_sha"], rel_tests_dir,
                                    task_id)
    if locked is None or not guard.plank_has_group_lines(_test_files(locked)):
        return []
    return guard.group_line_errors_from_files(files)


def _refuse_group_lines(conn, task_id: str, errors: list[str]) -> None:
    """Отказ по строке группы — тем же приёмом, что `_refuse_traceability`
    (журнал актором `operator`, не `AMEND_ACTION`)."""
    reason = "; ".join(errors)
    store.journal(conn, task_id, "operator", "amend-tests отклонён",
                 f"строка группы: {reason}")
    sys.exit(f"[{task_id}] amend-tests: отказ — строка группы: {reason}")


def _tests_snapshot(wt_path: Path, rel_tests_dir: str) -> dict[str, bytes] | None:
    """{путь относительно корня worktree: байты} НЕ игнорируемых git
    файлов под `rel_tests_dir` — источник и сверки «есть ли правка»
    (AC-2), и самого коммита в артефактную ветку: `.gitignore`-исключённые
    файлы (`__pycache__`, `*.pyc` — сгенерированные обязательным прогоном
    AC-10 — ANSWER-3) в это множество не попадают, тем же критерием, что
    обычный `git add`. `None` — git не ответил.

    `--cached --others --exclude-standard` (REVIEW.md iteration 2/3,
    R2-F1) — БЕЗ `--cached` `ls-files` возвращает только untracked-файлы:
    для задач, чей `tasks/<id>/acceptance_tests/` уже трекнут кодовой
    веткой (в т.ч. для этой самой задачи — заведена до A7, 14 файлов
    трекнуты, `git ls-files tasks/<id>/acceptance_tests/` не пуст),
    правка уже отслеживаемого файла невидима снимку: `disk` возвращал
    бы `{}` для НЕИЗМЕНЁННОГО untracked-множества, сверка AC-2 никогда
    не находила бы разницу с непустым `baseline`, а фиксация ушла бы с
    пустым `files` (побайтно тот же коммит, но новый sha) — лок
    сдвигался бы без реального содержимого правки. `--cached` добавляет
    уже трекнутые пути (сколь угодно изменённые/неизменённые) к тому же
    выводу; `--exclude-standard` по-прежнему фильтрует ТОЛЬКО untracked-
    часть (`.gitignore`-политика git не применяется к уже трекнутым
    путям — тот же принцип, что у обычного `git add .`).

    Байты, не текст (тот же довод, что `checkpoint._commit_external_
    step_artifacts`, REVIEW.md T094 итерация 2, замечание 1) — точная
    копия того, что реально лежит на диске, без риска потерять
    не-UTF8 содержимое."""
    res = gitcmd.in_repo(wt_path, "ls-files", "--cached", "--others",
                         "--exclude-standard", "--", rel_tests_dir)
    if res is None or res.returncode != 0:
        return None
    files = {}
    for rel in res.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        try:
            files[rel] = (wt_path / rel).read_bytes()
        except OSError:
            continue
    return files


def _artifact_tests_snapshot(task_id: str, rel_tests_dir: str) -> dict[str, bytes]:
    """{путь: байты} текущего содержимого `rel_tests_dir` на артефактной
    ветке — baseline для сверки AC-2 (UTF-8: `acceptance_tests/` всегда
    текстовый python-код, тот же приём, что `artifact_branch.read_tree`
    уже применяет для чтения)."""
    prefix = f"{rel_tests_dir}/"
    return {rel: text.encode("utf-8")
           for rel, text in artifact_branch.read_tree(task_id).items()
           if rel.startswith(prefix)}


def _removed_paths(disk: dict[str, bytes], baseline: dict[str, bytes],
                   manifest_rel: str) -> list[str]:
    """Пути `acceptance_tests/` артефактной ветки, которых нет на диске
    worktree, — удаление Оператора, переносимое коммитом правки (SPEC
    01M3XWR7140Q8C1XAFPZ9E854M, требование 1). Без этого коммит только
    дописывал файлы, и удалённый README оставался в ветке (случай
    101965d0). Перечень долгоживущих файлов не удаляется никогда: его
    пишет только команда (требование 2)."""
    return sorted(p for p in baseline if p not in disk and p != manifest_rel)


def _removed_note(task_id: str, removed: list[str]) -> str:
    """Хвост детали журнала «правка планки» с удалёнными путями
    относительно `tasks/<id>/` (требование 5); пусто — удалений нет."""
    if not removed:
        return ""
    prefix = f"tasks/{task_id}/"
    return "\nудалены: " + ", ".join(p[len(prefix):] if p.startswith(prefix)
                                      else p for p in removed)


def _commit_plank(task_id: str, files: dict, message: str,
                  removed: list[str]) -> tuple[str, str]:
    """Коммит правки планки в ссылку документов с удалениями `removed`:
    (sha, "") — коммит есть и меняет дерево; ("", "") — git не записал
    коммит; ("", причина) — дерево коммита равно дереву головы или не
    сверено с ним (SPEC 01M3XWR7140Q8C1XAFPZ9E854M, требование 3,
    fail-closed): такой коммит лок не принимает, и ссылка его не
    получает — сверка идёт до записи (`artifact_branch.commit_change`):
    коммит ссылки сразу уезжает в origin (ADR-0021 п.3), откатить его
    назад, как прежде откатывали ветку, уже нельзя."""
    sha, outcome = artifact_branch.commit_change(task_id, files, message,
                                                 remove=removed)
    if sha:
        return sha, ""
    if outcome == artifact_branch.TREE_UNKNOWN:
        return "", ("дерево коммита правки не сверено с деревом головы "
                    "ссылки документов — git не ответил")
    if outcome == artifact_branch.UNCHANGED:
        return "", ("коммит правки не меняет ни одного файла ссылки "
                    "документов (дерево равно дереву головы); "
                    "tests_locked_sha не сдвинут")
    return "", ""


def _run_summary(tail: str) -> str:
    """Итоговая строка прогона pytest (`N passed in Xs`/`M failed, N
    passed in Xs`) из хвоста вывода `acceptance.run` — для журнала
    (AC-11), не только «прошло/не прошло» одним словом. Регулярка не
    найдена (вывод truncated иначе, чем ожидается) — весь хвост как есть,
    без потери диагностики.

    Сама регулярка живёт в `orchestrator/acceptance.py` — там же, где
    остальной разбор вывода pytest (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
    требование 1): один узел на весь пульт. Журналу правки планки нужна
    ТОЛЬКО итоговая строка (AC-11 задачи 01M1HNNHDMP2C1AJTH5QF1BTN2), не
    выжимка с именами упавших тестов, поэтому здесь зовётся
    `run_summary_line`, а не `run_digest`."""
    return acceptance.run_summary_line(tail) or tail.strip()


def _locked_window_task_ids(conn, limit: int = WINDOW_SIZE) -> list[str]:
    """id последних `limit` задач пульта, дошедших до фиксации лока
    (`tests_locked_sha` не пуст), program-wide, по порядку заведения
    (ANSWER-1, вопрос 1, вариант B).

    `created_at`, не строковое сравнение `id` — прокси «порядка
    заведения» (PLAN, «Подход»): легаси `Tnnn` и текущие ULID-id в
    одной программе не сопоставимы лексикографически с реальной
    хронологией, тот же столбец, которым уже пользуется
    `store.latest_fixed_sha` для похожей задачи «последняя по времени».
    """
    locked = [t for t in store.all_tasks(conn) if t["tests_locked_sha"]]
    locked.sort(key=lambda t: (t["created_at"] or "", t["id"]))
    return [t["id"] for t in locked[-limit:]]


def _amend_events_in_window(conn, window_ids: list[str]) -> int:
    """Число событий «правка планки» журнала, чей `task_id` — в окне."""
    count = 0
    for task_id in window_ids:
        count += sum(1 for s in store.task_steps(conn, task_id)
                    if AMEND_ACTION in s["action"])
    return count


def _refuse(conn, task_id: str, what: str, errors: list[str]) -> None:
    """Отказ проверки до записи — приёмом `_refuse_traceability` (журнал
    актором `operator`, не `AMEND_ACTION`)."""
    reason = "; ".join(errors)
    store.journal(conn, task_id, "operator", "amend-tests отклонён",
                  f"{what}: {reason}")
    sys.exit(f"[{task_id}] amend-tests: отказ — {what}: {reason}")


def _lock_manifest(conn, task_id: str, t) -> tuple[dict[str, str] | None, str]:
    """Перечень долгоживущих файлов из дерева лока — тем же узлом, что
    сверка сумм на переходах. Пустой словарь — задача без долгоживущих
    файлов: `amend-tests` ведёт себя как до ADR-0020, задача 3 (SPEC
    01M3NSZ4YWZW9SD5Y6H62ATGRV, требование 7)."""
    return acceptance_gates.long_lived_manifest(
        task_id, t, store.task_target(conn, task_id))


def _worktree_long_lived_files(wt_path: Path, task_id: str) -> dict[str, str] | None:
    """{путь: текст} долгоживущих файлов задачи, которые лежат на диске
    worktree (отслеживаемые и новые, не игнорируемые git) — итоговое
    состояние правки; `None` — git не ответил или файл не прочитан."""
    res = gitcmd.in_repo(wt_path, "ls-files", "--cached", "--others",
                         "--exclude-standard", "--", "tests")
    if res is None or res.returncode != 0:
        return None
    files: dict[str, str] = {}
    for rel in sorted(set(res.stdout.splitlines())):
        rel = rel.strip()
        if not guard.is_long_lived_test_path(task_id, rel):
            continue
        path = wt_path / rel
        if not path.is_file():
            continue  # удалён в worktree, но ещё в индексе
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    return files


def _code_head_long_lived(code_branch: str, task_id: str
                          ) -> tuple[str, dict[str, str]] | None:
    """(голова кодовой ветки, {путь: текст} её долгоживущих файлов задачи);
    `None` — git не ответил."""
    repo = workspace.task_repo(task_id)
    head = gitcmd.branch_head_sha(code_branch, repo=repo)
    present = gitcmd.ls_tree_files(head, "tests", repo=repo) if head else None
    if present is None:
        return None
    files: dict[str, str] = {}
    for rel in present:
        if not guard.is_long_lived_test_path(task_id, rel):
            continue
        text, _reason = gitcmd.show(head, rel, repo=repo)
        if text is None:
            return None
        files[rel] = text
    return head, files


def _head_digests(head: str, task_id: str) -> dict[str, str] | None:
    """{путь: sha256 байтов} долгоживущих файлов задачи в дереве `head` —
    содержимое перечня Р2; `None` — git не ответил."""
    repo = workspace.task_repo(task_id)
    present = gitcmd.ls_tree_files(head, "tests", repo=repo) if head else None
    if present is None:
        return None
    digests: dict[str, str] = {}
    for rel in present:
        if guard.is_long_lived_test_path(task_id, rel):
            digest = acceptance_gates.blob_sha256(head, rel, repo)
            if digest is None:
                return None
            digests[rel] = digest
    return digests


def _deleted_file_text(code_head: str, rel: str, repo: Path) -> str | None:
    """Текст удаляемого файла перечня: с головы кодовой ветки, а если там
    его уже нет — с родителя коммита, который его удалил. `repo` — клон
    проекта задачи."""
    text, _reason = gitcmd.show(code_head, rel, repo=repo)
    if text is not None:
        return text
    res = gitcmd.in_repo(repo, "log", "-1", "--format=%H", "--no-renames",
                         "--diff-filter=D", code_head, "--", rel)
    sha = res.stdout.strip() if res is not None and res.returncode == 0 else ""
    if not sha:
        return None
    text, _reason = gitcmd.show(f"{sha}^", rel, repo=repo)
    return text


def _method_names(source: str) -> set[str]:
    """Имена тестовых методов без класса: перенос метода в другую группу
    меняет его класс, но не имя."""
    return {name.rsplit("::", 1)[-1]
            for name in guard.qualified_test_methods(source)}


def _long_lived_errors(task_id: str, files: dict[str, str],
                       deleted: dict[str, str | None],
                       plank_sources: list[str]) -> list[str]:
    """Проверки итогового состояния долгоживущих файлов (SPEC
    01M3NSZ4YWZW9SD5Y6H62ATGRV, требования 1, 4): в `tests/` — только
    «Группа: долгоживущий»; признаки и «Ловит мутацию» — узлом выхода из
    `tests_writing`; удаление файла перечня — только переносом, без потери
    метода (ADR-0020, пункт 8). Файл, который не разбирается, строкой
    группы не проверяется — его точнее назовёт сухой сбор."""
    errors: list[str] = []
    for rel, text in sorted(files.items()):
        group, group_error = guard.plank_file_group(text)
        if group != guard.GROUP_LONG_LIVED and (group or group_error):
            errors.append(f"{rel}: нет строки «Группа: {guard.GROUP_LONG_LIVED}» "
                          f"— в tests/ кодовой ветки только долгоживущие файлы")
    errors += guard.long_lived_errors_from_files(sorted(files.items()), task_id)
    kept: set[str] = set()
    for source in [*plank_sources, *files.values()]:
        kept |= _method_names(source)
    for rel, text in sorted(deleted.items()):
        if text is None:
            errors.append(f"{rel}: удаляемый файл перечня не прочитан — "
                          f"сверить его методы с итоговой планкой нечем")
            continue
        lost = sorted(_method_names(text) - kept)
        if lost:
            errors.append(
                f"{rel}: удаление снимает методы {', '.join(lost)} — их нет "
                f"ни в acceptance_tests/, ни в долгоживущих файлах задачи; "
                f"снятие теста — по мандату Оператора на ослабление, не "
                f"правкой планки (ADR-0020, пункт 8)")
    return errors


def _collect_and_run(conn, task_id: str, acc_tdir: Path, cwd: Path,
                     long_lived: dict[str, str],
                     plank_files: list[tuple[str, str]]) -> str:
    """Сухой сбор и прогон планки вместе с долгоживущими файлами — как
    `in_dev -> verifying`; хвост прогона для журнала. Красный прогон
    допускается прежним правилом: каждый файл планки несёт маркер
    «Красен до реализации»/«Зелёный с рождения». Долгоживущий файл обязан
    нести маркер, только если упал он сам (или имена упавших из вывода
    не прочитаны): зелёный долгоживущий файл рядом с ещё красной планкой —
    обычное состояние задачи в разработке, не повод для отказа."""
    extra = sorted(long_lived)
    collected, tail = acceptance.collect(acc_tdir, cwd, extra=extra)
    if not collected:
        _refuse(conn, task_id, "сухой сбор планки и долгоживущих файлов "
                f"({', '.join(extra)}) не прошёл", [tail])
    green, tail = acceptance.run(acc_tdir, cwd=cwd, extra=extra)
    if not green:
        failed = acceptance.failed_test_lines(tail)
        suspects = [(rel, text) for rel, text in sorted(long_lived.items())
                    if not failed or any(rel in line for line in failed)]
        marker_errors = (guard.redness_marker_errors_from_files(plank_files)
                         + guard.redness_marker_errors_from_files(suspects))
        if marker_errors:
            _refuse(conn, task_id, "прогон планки и долгоживущих файлов не "
                    "«OK», и не все падения промаркированы «Красен до "
                    "реализации»", [*marker_errors, tail])
    return tail


def _commit_long_lived(wt_path: Path, paths: list[str], message: str) -> bool:
    """Коммит в worktree кодовой ветки ровно `paths` (включая удаления) —
    запись (а) требования 1; сбой снимает их со сцены и отдаёт `False`."""
    added = gitcmd.in_repo(wt_path, "add", "-A", "--", *paths)
    commit = None
    if added is not None and added.returncode == 0:
        commit = gitcmd.in_repo(
            wt_path, "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
            "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
            "commit", "-q", "-m", message, "--", *paths)
    if commit is None or commit.returncode != 0:
        gitcmd.in_repo(wt_path, "reset", "-q", "--", *paths)
        return False
    return True


def _recovery_exit(conn, task_id: str, detail: str) -> None:
    """Сбой между записями (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требование 2):
    кодовая ветка уже несёт правку, лок — нет. Не `AMEND_ACTION`: правка
    не состоялась, счётчик ADR-0012 её не видит."""
    store.journal(conn, task_id, "operator", "amend-tests прерван", detail)
    sys.exit(f"[{task_id}] amend-tests: сбой — {detail}; tests_locked_sha не "
             f"сдвинут. Восстановление: artel.py amend-tests {task_id} "
             f"--from-branch --reason «…»")


def _cmd_amend_tests(conn, task_id: str, reason: str | None) -> None:
    fixation.stop_on_ref_drift(conn, task_id, "operator", "amend-tests")
    t = store.get_task(conn, task_id)

    # AC-5: «флага нет» и «флаг пуст» — один и тот же отказ, не только
    # `is None` (REVIEW-урок из докстринга приёмочного теста).
    if not (reason or "").strip():
        sys.exit(f"[{task_id}] amend-tests: отказ — основание (--reason) "
                 f"пустое, правка планки требует непустой причины")

    old_locked = t["tests_locked_sha"]
    if not old_locked:
        sys.exit(f"[{task_id}] amend-tests: отказ — задача ещё не проходила "
                 f"фиксацию лока приёмочных тестов (tests_locked_sha пуст) "
                 f"— сверять правку не с чем")

    wt_path, error = workspace.ensure(task_id, t["branch"])
    if error is not None:
        sys.exit(f"[{task_id}] amend-tests: отказ — worktree не готов: {error}")

    rel_tests_dir = f"tasks/{task_id}/acceptance_tests"
    prefix = f"{rel_tests_dir}/"
    tdir = wt_path / "tasks" / task_id
    _materialize_tests_if_missing(task_id, tdir)

    changed = _worktree_changed_paths(wt_path)
    if changed is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"статус worktree {wt_path}")
    # Долгоживущие пути задачи — вторая область правки, только у задачи с
    # непустым перечнем лока (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требования
    # 1, 7): без перечня правка `tests/` — прежнее «за пределами».
    manifest, manifest_reason = _lock_manifest(conn, task_id, t)
    long_changed = sorted(p for p in changed
                          if guard.is_long_lived_test_path(task_id, p))
    outside = [p for p in changed if not p.startswith(prefix)
               and not (manifest and p in long_changed)]
    if manifest is None and long_changed:
        # Без перечня лока не отличить путь перечня от нового и не
        # проверить удаление — fail-closed (ADR-0002).
        sys.exit(f"[{task_id}] amend-tests: отказ — перечень долгоживущих "
                 f"файлов лока не прочитан ({manifest_reason}), правка "
                 f"{', '.join(long_changed)} не проверяема")

    disk = _tests_snapshot(wt_path, rel_tests_dir)
    if disk is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"содержимое {rel_tests_dir}/")
    baseline = _artifact_tests_snapshot(task_id, rel_tests_dir)
    # Файл перечня в сверку «есть ли правка» не входит: его пишет только
    # команда (ручная правка — отказ сразу), а его отсутствие на диске —
    # не правка: планку в worktree материализует и выход из
    # `tests_writing`, раньше, чем пишет перечень.
    manifest_rel = acceptance_gates.long_lived_manifest_rel(task_id)
    if manifest_rel in disk and disk[manifest_rel] != baseline.get(manifest_rel):
        sys.exit(f"[{task_id}] amend-tests: отказ — {manifest_rel} изменён "
                 f"в worktree руками; перечень пишет только amend-tests "
                 f"(по байтам головы кодовой ветки) — верни файл как был")
    plank_same = ({p: v for p, v in disk.items() if p != manifest_rel}
                  == {p: v for p, v in baseline.items() if p != manifest_rel})
    if plank_same and not (manifest and long_changed):
        # AC-2: материализация (выше) сама по себе не считается правкой —
        # сверка идёт по СОДЕРЖИМОМУ против артефактной ветки, не по
        # `git status` worktree (та всегда покажет материализованные
        # файлы как untracked, даже без реальной правки Оператора).
        sys.exit(f"[{task_id}] amend-tests: отказ — нет изменений в "
                 f"{rel_tests_dir}/, нечего фиксировать")
    if outside:
        sys.exit(f"[{task_id}] amend-tests: отказ — есть изменения за "
                 f"пределами {rel_tests_dir}/: {', '.join(sorted(outside))}")
    removed = _removed_paths(disk, baseline, manifest_rel)

    if manifest:
        _amend_with_long_lived(conn, t, task_id, reason, wt_path, disk,
                               manifest, long_changed, removed)
        return

    # AC-1/AC-4: трассируемость AC — ДО прогона планки (копилка 11.09,
    # коммит 33aeb202: `amend-tests` сдвигал лок мимо этой проверки).
    created_spec = _materialize_spec_if_missing(task_id, tdir)
    try:
        trace_errors = guard.acceptance_traceability_errors(tdir)
    finally:
        if created_spec is not None:
            created_spec.unlink(missing_ok=True)
    if trace_errors:
        _refuse_traceability(conn, task_id, trace_errors)
    group_errors = _group_line_errors(t, rel_tests_dir,
                                      guard.acceptance_test_files(tdir))
    if group_errors:
        _refuse_group_lines(conn, task_id, group_errors)

    green, tail = acceptance.run(tdir)
    if not green:
        # Обязательный прогон (ТЗ п.6, инцидент опечатки 03.09) — не «OK»
        # блокирует, КРОМЕ падений, промаркированных «Красен до
        # реализации»/«Зелёный с рождения» (тем же разбором, что выход
        # из tests_writing, guard.scan_redness_markers): такой файл
        # ещё не имеет кода под собой, и это норма, не поломка правки.
        marker_errors = guard.scan_redness_markers(tdir)
        if marker_errors:
            sys.exit(
                f"[{task_id}] amend-tests: отказ — прогон "
                f"{rel_tests_dir}/ не «OK», и не все падения промаркированы "
                f"«Красен до реализации»: {'; '.join(marker_errors)}\n{tail}")

    commit_message = f"{task_id}: правка планки приёмки — {reason}"
    new_locked, refusal = _commit_plank(task_id, disk, commit_message, removed)
    if refusal:
        _refuse(conn, task_id, "пустой коммит правки", [refusal])
    if not new_locked:
        sys.exit(f"[{task_id}] amend-tests: коммит правки в артефактную "
                 f"ветку не удался")
    store.update_task(conn, task_id, tests_locked_sha=new_locked)

    detail = (f"старый sha={old_locked}, новый sha={new_locked}, "
             f"основание: {reason}{_removed_note(task_id, removed)}\n"
             f"приёмочные тесты: {_run_summary(tail)}")
    _record_amend(conn, task_id, detail,
                  f"[{task_id}] {AMEND_ACTION}: {old_locked} -> {new_locked} "
                  f"(ветка {artifact_branch.branch_name(task_id)})")


def _amend_with_long_lived(conn, t, task_id: str, reason: str, wt_path: Path,
                           disk: dict[str, bytes], manifest: dict[str, str],
                           long_changed: list[str], removed: list[str]) -> None:
    """Правка из worktree задачи с непустым перечнем лока (SPEC
    01M3NSZ4YWZW9SD5Y6H62ATGRV, требования 1, 4): проверки итогового
    состояния планки и долгоживущих файлов — до любой записи; затем строго
    (а) коммит `long_changed` в кодовую ветку, (б) коммит планки с
    перечнем, пересчитанным по новой голове кодовой ветки, в ветку
    документов, (в) сдвиг `tests_locked_sha`. Сбой после (а) — ненулевой
    код с путём восстановления `--from-branch`."""
    old_locked = t["tests_locked_sha"]
    rel_tests_dir = f"tasks/{task_id}/acceptance_tests"
    tdir = wt_path / "tasks" / task_id
    files = _worktree_long_lived_files(wt_path, task_id)
    code_head = gitcmd.branch_head_sha(t["branch"],
                                       repo=workspace.task_repo(task_id))
    if files is None or not code_head:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"долгоживущие файлы worktree {wt_path} или голову "
                 f"{t['branch']}")
    deleted = {rel: _deleted_file_text(code_head, rel,
                                         workspace.task_repo(task_id))
               for rel in manifest if rel not in files}

    created_spec = _materialize_spec_if_missing(task_id, tdir)
    try:
        trace_errors = guard.acceptance_traceability_errors(
            tdir, list(files.values()))
    finally:
        if created_spec is not None:
            created_spec.unlink(missing_ok=True)
    if trace_errors:
        _refuse_traceability(conn, task_id, trace_errors)
    plank_files = guard.acceptance_test_files(tdir)
    group_errors = (_group_line_errors(t, rel_tests_dir, plank_files)
                    + guard.long_lived_plank_errors(plank_files, task_id))
    if group_errors:
        _refuse_group_lines(conn, task_id, group_errors)
    errors = _long_lived_errors(task_id, files, deleted,
                                [text for _rel, text in plank_files])
    if errors:
        _refuse(conn, task_id, "долгоживущие файлы tests/", errors)
    tail = _collect_and_run(conn, task_id, tdir, wt_path, files, plank_files)

    if long_changed:
        if not _commit_long_lived(
                wt_path, long_changed,
                f"{task_id}: правка долгоживущих тестов — {reason}"):
            sys.exit(f"[{task_id}] amend-tests: коммит правки "
                     f"{', '.join(long_changed)} в кодовую ветку не удался — "
                     f"ничего не записано")
        code_head = gitcmd.branch_head_sha(t["branch"],
                                           repo=workspace.task_repo(task_id))
    digests = _head_digests(code_head, task_id) if code_head else None
    new_locked, refusal = "", ""
    if digests is not None:
        docs_files = dict(disk)
        docs_files[acceptance_gates.long_lived_manifest_rel(task_id)] = (
            guard.render_long_lived_manifest(digests))
        new_locked, refusal = _commit_plank(
            task_id, docs_files, f"{task_id}: правка планки приёмки — {reason}",
            removed)
    if not new_locked:
        failure = ("перечень по голове кодовой ветки не посчитан"
                   if digests is None else refusal or
                   "коммит планки и перечня в ветку документов не удался")
        if long_changed:
            _recovery_exit(conn, task_id, f"кодовая ветка несёт правку "
                           f"{', '.join(long_changed)} (голова {code_head}), "
                           f"но {failure}")
        if refusal:
            _refuse(conn, task_id, "пустой коммит правки", [refusal])
        sys.exit(f"[{task_id}] amend-tests: {failure} — ничего не записано")
    store.update_task(conn, task_id, tests_locked_sha=new_locked)

    detail = (f"старый sha={old_locked}, новый sha={new_locked}, "
              f"основание: {reason}{_removed_note(task_id, removed)}\n"
              f"долгоживущие файлы: "
              f"{', '.join(long_changed) or 'без правки'}, голова кодовой "
              f"ветки {code_head}\nприёмочные тесты: {_run_summary(tail)}")
    _record_amend(conn, task_id, detail,
                  f"[{task_id}] {AMEND_ACTION}: {old_locked} -> {new_locked} "
                  f"(ветка {artifact_branch.branch_name(task_id)}, кодовая "
                  f"ветка {t['branch']} -> {code_head})")


def _record_amend(conn, task_id: str, detail: str, line: str) -> None:
    """Ровно одно событие `AMEND_ACTION` на успешный вызов любого режима,
    сколько бы веток он ни изменил (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV,
    требование 3), и алерт окна ADR-0012.

    Правка планки — запись пульта в ссылку документов по команде
    Оператора: документы перефиксируются (`store.record_fixation`,
    ADR-0021 п.3), иначе следующая сверка фиксации увидела бы её
    расхождением."""
    store.journal(conn, task_id, "operator", AMEND_ACTION, detail)
    store.record_fixation(conn, task_id)
    print(line)

    window_ids = _locked_window_task_ids(conn)
    count = _amend_events_in_window(conn, window_ids)
    if count > WINDOW_THRESHOLD:
        message = (
            f"планка девальвируется: {count} правок планки в скользящем "
            f"окне последних {len(window_ids)} задач(и), дошедших до "
            f"фиксации лока (порог — больше {WINDOW_THRESHOLD})")
        alerts.raise_alert(conn, None, "threshold", DEVALUATION_ALERT_SOURCE,
                           message)
        print(f"[{task_id}] ВНИМАНИЕ: {message}")


def _branch_tests_snapshot(rev: str, rel_tests_dir: str,
                           task_id: str) -> dict[str, str] | None:
    """{путь: текст} `rel_tests_dir` на git-ревизии `rev` — `rev` может
    быть именем ветки ИЛИ голым sha, `gitcmd.ls_tree_files`/`gitcmd.show`
    принимают любую git-ревизию одинаково (тот же приём, каким
    `fsm_advance._zones_gate` уже сравнивает дерево на разных точках
    истории). `None` — git не ответил на любой из двух вызовов.
    Чтение — в репозитории задачи (`artifact_branch`, ADR-0021 п.3)."""
    paths = artifact_branch.ls_tree(task_id, rev, rel_tests_dir)
    if paths is None:
        return None
    files = {}
    for rel in paths:
        text, _reason = artifact_branch.show(task_id, rev, rel)
        if text is None:
            return None
        files[rel] = text
    return files


def _branch_traceability_errors(task_id: str, rev: str,
                                tests_snapshot: dict[str, str],
                                extra_sources: list[str] = ()) -> list[str] | None:
    """Ошибки трассируемости AC (SPEC требование 2, AC-3) по SPEC.md и
    `acceptance_tests/` ГОЛОВЫ артефактной ветки — тем же ядром, что
    рабочая копия использует через `guard.acceptance_traceability_errors`
    (`guard.scan_ac_content`/`guard.traceability_errors_from_content`,
    тот же приём, каким `orchestrator/fsm.py::_tests_writing_ac_state`
    уже читает трассируемость с чужой ветки, SPEC T031), но без диска:
    `tests_snapshot` — уже прочитанный `_branch_tests_snapshot` того же
    `rev` (переиспользован вызывающим кодом, второй обход дерева не
    нужен). Только `test_*.py` (SPEC T081, тот же фильтр, что `guard.
    scan_acceptance_tests` применяет для рабочей копии) — вспомогательный
    файл каталога (например `_sandbox.py`) не должен читаться как
    настоящая AC-разметка. `None` — git не ответил на SPEC.md.

    `extra_sources` — тексты долгоживущих файлов задачи с головы кодовой
    ветки: их методы `test_ac<n>_…` покрывают критерии наравне с планкой
    (тот же контракт, что у `guard.acceptance_traceability_errors`)."""
    spec_text, _reason = artifact_branch.show(task_id, rev,
                                              f"tasks/{task_id}/SPEC.md")
    if spec_text is None:
        return None
    meta = yamlmini.frontmatter(spec_text) or {}
    sources = [text for rel, text in tests_snapshot.items()
              if Path(rel).name.startswith("test_")] + list(extra_sources)
    tested, markers = guard.scan_ac_content(sources)
    return guard.traceability_errors_from_content(spec_text, meta, tested,
                                                   markers)


def _cmd_amend_tests_from_branch(conn, task_id: str, reason: str | None) -> None:
    """`amend-tests <id> --reason "<основание>" --from-branch` (SPEC
    01M287TPG0HAVXS8CHBCY679WN, требование 3): источник правки —
    расхождение содержимого `acceptance_tests/` МЕЖДУ `tests_locked_sha`
    и головой артефактной ветки, не worktree (AC-7/AC-8). Содержимое уже
    закоммичено на ветке (например автокоммитом шага роли, минуя
    `amend-tests`, — SPEC «Контекст») — новый коммит здесь не нужен,
    команда только сдвигает `tests_locked_sha` на уже существующий sha
    головы.

    Задача с непустым перечнем лока (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV,
    требование 2): правка — и расхождение долгоживущих файлов головы
    кодовой ветки с перечнем лока (путь восстановления после сбоя между
    записями worktree-режима). Перечень нового лока — всегда пересчёт по
    голове кодовой ветки: не совпадающий с ним перечень головы ветки
    документов заменяется коммитом пересчитанного.

    Голова, сдвинутая мимо пульта, лок не получает: правку планки ролью
    узаконивает не эта команда, а `approve <id> <sha>`."""
    fixation.stop_on_ref_drift(conn, task_id, "operator", "amend-tests")
    t = store.get_task(conn, task_id)

    if not (reason or "").strip():
        sys.exit(f"[{task_id}] amend-tests: отказ — основание (--reason) "
                 f"пустое, правка планки требует непустой причины")

    old_locked = t["tests_locked_sha"]
    if not old_locked:
        sys.exit(f"[{task_id}] amend-tests: отказ — задача ещё не проходила "
                 f"фиксацию лока приёмочных тестов (tests_locked_sha пуст) "
                 f"— сверять правку не с чем")

    branch = artifact_branch.branch_name(task_id)
    rel_tests_dir = f"tasks/{task_id}/acceptance_tests"

    new_sha = artifact_branch.ref_head(task_id)
    if not new_sha:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"голову артефактной ветки {branch}")

    old_snapshot = _branch_tests_snapshot(old_locked, rel_tests_dir, task_id)
    new_snapshot = _branch_tests_snapshot(new_sha, rel_tests_dir, task_id)
    if old_snapshot is None or new_snapshot is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"содержимое {rel_tests_dir}/")

    # Долгоживущие файлы (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требование 2):
    # расхождение головы кодовой ветки с перечнем лока — тоже правка, а
    # перечень на голове ветки документов в сравнение планки не входит:
    # его в новый лок всё равно пишет эта команда, пересчётом.
    manifest, manifest_reason = _lock_manifest(conn, task_id, t)
    if manifest is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — перечень долгоживущих "
                 f"файлов лока не прочитан: {manifest_reason}")
    manifest_rel = acceptance_gates.long_lived_manifest_rel(task_id)
    head_files: dict[str, str] = {}
    head_digests: dict[str, str] = {}
    code_head = ""
    if manifest:
        code = _code_head_long_lived(t["branch"], task_id)
        digests = _head_digests(code[0], task_id) if code else None
        if code is None or digests is None:
            sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                     f"долгоживущие файлы головы кодовой ветки {t['branch']}")
        (code_head, head_files), head_digests = code, digests
        old_plank = {p: v for p, v in old_snapshot.items() if p != manifest_rel}
        new_plank = {p: v for p, v in new_snapshot.items() if p != manifest_rel}
    else:
        old_plank, new_plank = old_snapshot, new_snapshot
    long_diverged = sorted(p for p in set(manifest) | set(head_digests)
                           if manifest.get(p) != head_digests.get(p))

    if old_plank == new_plank and not long_diverged:
        sys.exit(f"[{task_id}] amend-tests: отказ — нет расхождения в "
                 f"{rel_tests_dir}/ между {old_locked} и головой ветки "
                 f"{branch}" + (f" и долгоживущих файлов головы "
                                f"{t['branch']} с перечнем лока"
                                if manifest else ""))

    # AC-3: трассируемость AC по содержимому ГОЛОВЫ ветки — до сдвига
    # tests_locked_sha (копилка 11.09, тот же путь мимо проверки, что и
    # у worktree-пути AC-1).
    trace_errors = _branch_traceability_errors(task_id, new_sha, new_snapshot,
                                               list(head_files.values()))
    if trace_errors is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"tasks/{task_id}/SPEC.md")
    if trace_errors:
        _refuse_traceability(conn, task_id, trace_errors)
    plank_files = _test_files(new_snapshot)
    group_errors = _group_line_errors(t, rel_tests_dir, plank_files)
    if manifest:
        group_errors += guard.long_lived_plank_errors(plank_files, task_id)
    if group_errors:
        _refuse_group_lines(conn, task_id, group_errors)
    if long_diverged:
        _check_code_head_long_lived(conn, t, task_id, branch, code_head,
                                    head_files, manifest, plank_files)

    if manifest:
        recomputed = guard.render_long_lived_manifest(head_digests)
        if new_snapshot.get(manifest_rel) != recomputed:
            new_sha = artifact_branch.commit_files(
                task_id, {manifest_rel: recomputed},
                f"{task_id}: перечень долгоживущих тестов по голове кодовой "
                f"ветки {code_head} — {reason}")
            if not new_sha:
                sys.exit(f"[{task_id}] amend-tests: коммит перечня в ветку "
                         f"документов не удался — ничего не записано")

    changed_files = sorted(
        p for p in set(old_plank) | set(new_plank)
        if old_plank.get(p) != new_plank.get(p)) + long_diverged

    store.update_task(conn, task_id, tests_locked_sha=new_sha)

    detail = (f"старый sha={old_locked}, новый sha={new_sha}, "
             f"основание: {reason}\nотличаются файлы: "
             f"{', '.join(changed_files)}")
    _record_amend(conn, task_id, detail,
                  f"[{task_id}] {AMEND_ACTION}: {old_locked} -> {new_sha} "
                  f"(ветка {branch}, источник — голова артефактной ветки)")


def _check_code_head_long_lived(conn, t, task_id: str, docs_branch: str,
                                code_head: str, head_files: dict[str, str],
                                manifest: dict[str, str],
                                plank_files: list[tuple[str, str]]) -> None:
    """Проверки требования 1 по долгоживущим файлам головы кодовой ветки
    для `--from-branch` (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV, требование 2):
    статические — по текстам из git; сухой сбор и прогон — в worktree
    задачи, куда планка материализуется с головы ветки документов, как на
    `in_dev -> verifying`. Незакоммиченная правка долгоживущих путей в
    worktree — отказ: прогон проверил бы её, а не голову ветки."""
    deleted = {rel: _deleted_file_text(code_head, rel,
                                         workspace.task_repo(task_id))
               for rel in manifest if rel not in head_files}
    errors = _long_lived_errors(task_id, head_files, deleted,
                                [text for _rel, text in plank_files])
    if errors:
        _refuse(conn, task_id, "долгоживущие файлы tests/", errors)
    wt_path, error = workspace.ensure(task_id, t["branch"])
    if error is not None:
        sys.exit(f"[{task_id}] amend-tests: отказ — worktree не готов: {error}")
    changed = _worktree_changed_paths(wt_path)
    if changed is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"статус worktree {wt_path}")
    dirty = sorted(p for p in changed if guard.is_long_lived_test_path(task_id, p))
    if dirty:
        sys.exit(f"[{task_id}] amend-tests: отказ — в worktree незакоммиченная "
                 f"правка {', '.join(dirty)}; --from-branch проверяет голову "
                 f"кодовой ветки — закоммить правку или верни файлы как были")
    with acceptance.plank_in_code_copy(task_id, docs_branch, wt_path) as acc_tdir:
        _collect_and_run(conn, task_id, acc_tdir, wt_path, head_files,
                         plank_files)
