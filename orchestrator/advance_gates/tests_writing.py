"""`_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,
`_freshness_refuses` (SPEC 01M2CYQR0357VAQFZ5VACJD9TD, требование 1) —
перенесено дословно из `orchestrator/fsm_advance.py`."""
import os
import re
from pathlib import Path

from scripts import guard

from .. import (acceptance, artifact_branch, artifacts, checkpoint, config,
                cycle_hint, fixation, github_adapter, gitcmd, knowledge_cards,
                project_profile, repo_context, store, targets, workspace,
                yamlmini)
from ..reporters import outcome
from ._base import GateRefusal
from .acceptance import (blob_sha256, criterion_files, file_records,
                         in_outcome_bounds, is_repeat, long_lived_manifest_rel,
                         not_passed_kind, outcome_kind, record_criterion,
                         record_location)
from .refusal_classes import (FAIL_TO_PASS_PREPARE_REFUSAL_ACTION,
                              FAIL_TO_PASS_REFUSAL_ACTION,
                              LONG_LIVED_GIT_REFUSAL_ACTION,
                              NO_FAILURE_ERRORS_REFUSAL_ACTION,
                              SPEC_ANCHOR_REFUSAL_ACTION,
                              SPEC_CHANGED_AFTER_GATE_REFUSAL_ACTION)


def _freshness_refuses(conn, task_id: str, t, meta, status: str) -> bool:
    """Свежесть вердикта REVIEW.md — НЕ через каркас `_run_gates`
    (PLAN «Подход»): исторический формат `action` (`"переход отклонён"`,
    без суффикса) и печати (`f"[{task_id}] {detail}"`, без префикса
    «переход отклонён: ») отличается от остальных гейтов этого модуля —
    самостоятельный случай, не копия того же шаблона."""
    iteration = artifacts.fresh_verdict_iteration(meta, t["reviewed_iter"])
    if iteration is not None:
        return False
    detail = (
        f"вердикт REVIEW.md (status={status}, "
        f"iteration={meta.get('iteration', '—')}) уже учтён — "
        f"жду новый прогон ревьювера с iteration: {t['reviewed_iter'] + 1}"
    )
    store.journal(conn, task_id, "fsm", "переход отклонён", detail)
    print(f"[{task_id}] {detail}")
    print("  дальше: " + cycle_hint.launch_text(
        conn, task_id, "run", "(прогон ревьювера)"))
    return True


def _origin_push_gate(conn, task_id: str, t) -> GateRefusal | None:
    """Голова ветки задачи на origin — предусловие входа в verifying
    (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, AC-1..AC-5; ADR-0015,
    требование 2 — рубеж переехал с входа `review()` на вход `in_dev ->
    verifying` целиком, без дублирования на новом месте), вызывается
    только для не-канареечных задач, в `in_dev()` ниже.

    Канареечная задача (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование
    11/AC-11) не зовёт этот гейт вовсе (см. `in_dev()`): её `verifying`
    не ждёт CI и не читает origin (`canary._kill_at_verifying` убивает
    задачу сразу по входу) — push на origin-заглушку
    (`canary.ORIGIN_STUB_URL`) гарантированно проваливается по
    построению, не по сбою."""
    push_ok, push_detail = github_adapter.ensure_head_in_origin(
        conn, task_id, t["branch"])
    if push_ok:
        return None
    hint = f"почини доступ к origin и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: голова не в origin", push_detail, hint)


# Адрес в `tests/` чинит разработчик — класс «чинит роль». Своего действия
# в перечне `refusal_classes` у рубежа нет (модуль вне зон задачи
# 01M4JN2EDQP8Q3WVYK0TS95ZVC), поэтому — историческое действие без суффикса
# того же класса, что у `_freshness_refuses`; правило называет `detail`.
NETWORK_ADDRESS_ACTION = "переход отклонён"
# Сбой git — не вина роли: действия нет в перечне, значит «чинит Оператор».
NETWORK_ADDRESS_GIT_ACTION = ("переход отклонён: сетевые адреса tests/ — "
                              "git не ответил")


def _network_address_gate(conn, task_id: str, t) -> GateRefusal | None:
    """Адреса `http(s)://<DNS-имя>` в файлах `tests/**/*.py`, которые
    кодовая ветка добавила или изменила против своей базы, — отказ
    `in_dev -> verifying` до похода в CI (SPEC 01M4JN2EDQP8Q3WVYK0TS95ZVC,
    требование 3): инвариант 35 краснел только в CI ветки. Файлы, которых
    ветка не касалась, не читаются — их держит сам инвариант на main.

    Только артель: инвариант 35 — правило дерева `tests/` пульта, в чужом
    репозитории `tests/` значит другое. Канареечная задача — не
    проверяется, как `_mutation_claim_gate`: её `verifying` не ждёт CI.
    Сбой git — отказ, а не пропуск (ADR-0002)."""
    if t["is_canary"]:
        return None
    if not repo_context.is_artel(store.task_target(conn, task_id)):
        return None
    branch = t["branch"]
    repo = workspace.task_repo(task_id)
    git_hint = (f"разберись, почему git не отвечает, и повтори artel.py "
                f"advance {task_id}")
    base = gitcmd.diff_base(branch, repo=repo)
    entries = (None if base is None
               else gitcmd.diff_name_status(base, branch, "tests", repo=repo))
    if entries is None:
        return GateRefusal(
            NETWORK_ADDRESS_GIT_ACTION,
            f"дифф кодовой ветки {branch} против базы не прочитан — git не "
            f"ответил, проверка сетевых адресов tests/ невозможна", git_hint)
    files: list[tuple[str, str]] = []
    for status, path, new_path in entries:
        rel = new_path or path
        if status.startswith("D") or not (
                rel.startswith("tests/") and rel.endswith(".py")):
            continue
        text, reason = gitcmd.show(branch, rel, repo=repo)
        if text is None:
            return GateRefusal(
                NETWORK_ADDRESS_GIT_ACTION,
                f"{rel} не прочитан на голове {branch}: {reason} — проверка "
                f"сетевых адресов tests/ невозможна", git_hint)
        files.append((rel, text))
    errors = guard.network_address_errors_from_files(files)
    if not errors:
        return None
    hint = (f"замени адрес на localhost/127.0.0.1 и повтори artel.py "
            f"advance {task_id}")
    return GateRefusal(NETWORK_ADDRESS_ACTION, "; ".join(errors), hint)


def _registry_gate(conn, task_id: str, tdir, review_text, meta) -> GateRefusal | None:
    """Реестр замечаний (SPEC T100, требование 5): вердикт approved не
    проходит этот гейт, пока в реестре есть запись со статусом отличным
    от accepted — ни fixed, ни rejected сами по себе не закрывают
    замечание (ANSWER-1, симметрия). Вызывается только когда
    `guard.requires_registry(meta)` истинно (schema_version >= 3, см.
    `_review_approved`); guard уже подтвердил структуру этого REVIEW.md
    (`fsm.guard_refuses` в `review()`) — здесь читается тот же текст,
    отдельного чтения не заводится."""
    registry_text = review_text
    if registry_text is None:
        registry_text = (tdir / "REVIEW.md").read_text(encoding="utf-8")
    unresolved = [r["id"] for r in guard.registry_records(registry_text)
                 if r.get("status") != "accepted"]
    if not unresolved:
        return None
    detail = (f"реестр замечаний не закрыт: "
             f"{', '.join(unresolved)} — каждая запись обязана "
             f"дойти до status: accepted явным решением "
             f"ревьювера, прежде чем approved пройдёт гейт")
    hint = (f"доведи записи {', '.join(unresolved)} до "
           f"accepted и повтори artel.py advance {task_id}")
    return GateRefusal("переход отклонён: реестр замечаний", detail, hint)


STRAY_PLANK_FILES_ACTION = "переход отклонён: посторонние файлы планки"


def _tests_writing_stray_plank_files_gate(conn, task_id: str) -> GateRefusal | None:
    """Требование 3/AC-8 (SPEC 01M2ARQRDV4YY9TVPHXN2E7136): пока запись
    журнала `checkpoint.STRAY_ACCEPTANCE_FILES_ACTION` («посторонние файлы
    в каталоге планки» — checkpoint отбросил файлы этого же шага
    `test_author`, `checkpoint._commit_external_step_artifacts`) остаётся
    ПОСЛЕДНЕЙ записью с момента входа задачи в текущий визит состояния
    `tests_writing`, выход отклоняет переход, называя отброшенные файлы
    поимённо — иначе задача прошла бы трассируемость AC и сухой сбор
    планкой, ссылающейся на файл, которого нет ни на артефактной ветке,
    ни в следующем шаге developer (класс дефекта инцидента 06.09, SPEC
    «Контекст»: `_shared.py` был отброшен молча, трассируемость его не
    видела вовсе, а тесты планки падали ImportError только на приёмке).

    «Текущий визит состояния» — записи журнала ПОСЛЕ последней `state ->
    tests_writing` (обычный маркер `store.set_state`); нет такой записи
    вовсе (лёгкие песочницы, где переход состояния делается напрямую
    правкой строки БД, минуя `store.set_state`, либо самый первый вход
    задачи в состояние без единой записи журнала) — сверять от начала всего
    журнала, тот же вырожденный приём деградации, что и у
    `auto._role_step_since_state_entry` («сверять нечем» не значит
    «не сверять вовсе», здесь означает «весь имеющийся журнал — один
    визит»).

    Запись НЕ последняя (за ней есть более поздняя активность визита —
    например, повторный шаг `test_author` после починки, заметка
    Оператора) — не блокирует: устаревшая, уже замещённая запись не
    имеет права держать переход бесконечно.

    Записи `actor == "lease"` («lease взят»/«lease перехвачен»,
    `orchestrator/lease.py::acquire`) исключаются из сравнения целиком:
    это бухгалтерия ПРОЦЕССА, вызывающего `advance` сейчас (пишется
    самим `lease.run_locked` ДО того, как управление вообще дошло до
    этого гейта), не активность визита состояния — без исключения
    первый же холодный вызов `advance` для задачи без предсуществующего
    lease (обычный путь однократного `artel.py advance <id>`, не только
    тестовая песочница) журналировал бы «lease взят» ПОЗЖЕ отброшенной
    записи планки и гейт молчал бы всегда, даже когда отброшенные файлы
    реально остались последней содержательной записью визита.

    Так же исключаются записи автора `knowledge_cards.JOURNAL_ACTOR` с
    действием обращения или отказа подсказки (SPEC
    01M4S0K2MJRMVMQWKATAME3RHR, требование 8): команда роли `knowledge` и
    сборка миссии пишут их в любой момент визита, досыл очереди — и
    позже; без исключения такая запись заслонила бы маркер. Запись этого
    автора с любым другим действием сравнивается как обычно.

    Зарезервированное имя помощника пульта (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V,
    требование 5): `_pult.py` первого уровня планки в ссылке документов
    отклоняет выход своим действием; тот же файл черновика автокоммит
    отбрасывает как посторонний (`guard.is_extraneous_acceptance_test_file`),
    и отказ по записи журнала ниже называет то же основание в подсказке.

    Запись «правило планки: взято умолчание»
    (`project_profile.PLANK_RULE_DEFAULT_ACTION`) тоже пропускается (SPEC
    01M5AQH8M2DKBV30NBY86J34A7, требование 8): чекпоинт пишет её раз на
    визит, и она не активность роли, замещающая запись о посторонних."""
    reserved = _reserved_plank_helper_refusal(task_id)
    if reserved is not None:
        return reserved
    knowledge_actions = (knowledge_cards.ACCESS_ACTION,
                         knowledge_cards.HINT_REFUSAL_ACTION)
    rows = [r for r in store.task_steps(conn, task_id)
            if r["actor"] != "lease"
            and r["action"] != project_profile.PLANK_RULE_DEFAULT_ACTION
            and not (r["actor"] == knowledge_cards.JOURNAL_ACTOR
                     and r["action"] in knowledge_actions)]
    marker = "state -> tests_writing"
    since = 0
    for i, row in enumerate(rows):
        if row["action"] == marker:
            since = i + 1
    visit = rows[since:]
    if not visit:
        return None
    last = visit[-1]
    if last["action"] != checkpoint.STRAY_ACCEPTANCE_FILES_ACTION:
        return None
    detail = last["detail"] or ""
    prefix = checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX
    names = detail[len(prefix):] if detail.startswith(prefix) else detail
    refusal_detail = f"планка ссылается на отброшенные файлы: {names}"
    hint = (f"верни отброшенные файлы либо перепиши планку без них "
           f"(skills/test-authoring.md: общий код — только модули _*.py) "
           f"и повтори artel.py advance {task_id}")
    reserved_rel = f"acceptance_tests/{guard.RESERVED_PLANK_HELPER_NAME}"
    if reserved_rel in [n.strip() for n in names.split(",")]:
        hint = (f"{guard.RESERVED_PLANK_HELPER_NAME}: "
                f"{guard.RESERVED_PLANK_HELPER_HINT} — переименуй свой файл, "
                f"а остальные отброшенные верни либо перепиши планку без "
                f"них, и повтори artel.py advance {task_id}")
    return GateRefusal(STRAY_PLANK_FILES_ACTION, refusal_detail, hint)


def _reserved_plank_helper_refusal(task_id: str) -> GateRefusal | None:
    """`_pult.py` первого уровня `acceptance_tests/` в голове ссылки
    документов — отказ: пульт кладёт под этим именем свой помощник, и файл
    планки при выкладке был бы молча перетёрт. Действие — то же, что у
    отброшенных посторонних файлов: класс «чинит роль»
    (`refusal_classes.REFUSAL_CLASSES`), test_author переименует файл сам.
    Git не ответил на список — гейт молчит: сухой сбор того же выхода
    читает ту же ссылку и откажет своим диагнозом."""
    rel_dir = f"tasks/{task_id}/acceptance_tests"
    paths = artifact_branch.ls_tree(task_id, artifact_branch.branch_name(task_id),
                                    rel_dir)
    if not paths or f"{rel_dir}/{guard.RESERVED_PLANK_HELPER_NAME}" not in paths:
        return None
    detail = (f"в планке ссылки документов лежит "
              f"{rel_dir}/{guard.RESERVED_PLANK_HELPER_NAME}")
    hint = (f"{guard.RESERVED_PLANK_HELPER_NAME}: "
            f"{guard.RESERVED_PLANK_HELPER_HINT} — переименуй свой файл "
            f"(например, в _plank.py), убери {guard.RESERVED_PLANK_HELPER_NAME} "
            f"из acceptance_tests/ и повтори artel.py advance {task_id}")
    return GateRefusal(STRAY_PLANK_FILES_ACTION, detail, hint)


def _tests_writing_acceptance_dir(task_id: str, tdir, target: str,
                                  branch: str, code_branch: str):
    """(планка, cwd) материализованной планки для сухого сбора на выходе
    `tests_writing` (требование 2): рабочая копия задачи в области
    проекта (ADR-0021 п.1-2) — одна ветка логики для любого проекта,
    включая артель (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требование 6): сбор в
    главной копии пульта проверял бы код пина, а не код задачи. `tdir` и
    `target` больше не участвуют в выборе — сигнатура прежняя."""
    # Отказ `ensure` уже отклонил переход гейтом
    # `_tests_writing_code_copy_gate`; здесь — идемпотентный повтор.
    run_cwd, _err = workspace.ensure(task_id, code_branch)
    return acceptance.materialize_from_branch(task_id, branch, run_cwd), run_cwd


CODE_COPY_REFUSAL_ACTION = "переход отклонён: рабочая копия задачи не заведена"


def _tests_writing_code_copy_gate(task_id: str, target: str,
                                  code_branch: str) -> GateRefusal | None:
    """Рабочая копия задачи заведена до сухого сбора планки (ревью
    01M42PENCS26D0656X8FR7DFA7, R1-F3): иначе планка легла бы в каталог без
    кода и сухой сбор упал бы на импорте с непонятной причиной. Для любого
    проекта, включая артель (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требование
    6): отката на главную копию пульта нет."""
    _path, error = workspace.ensure(task_id, code_branch)
    if error is None and workspace.on_task_branch(
            task_id, code_branch, target) is False:
        # `ensure` отдаёт уже заведённую копию, не сверяя её ветку: сбор в
        # ней проверял бы чужой код.
        error = f"рабочая копия задачи не выписана на ветку {code_branch}"
    if error is None:
        return None
    return GateRefusal(CODE_COPY_REFUSAL_ACTION, error,
                       f"artel.py workspace {task_id} и повтори "
                       f"artel.py advance {task_id}")


ARTIFACT_DISK_READ_ACTION = "переход отклонён: планка читает артефакты с диска"


def _tests_writing_artifact_source_gate(acc_tdir, task_id: str) -> GateRefusal | None:
    """Источник артефактов задачи в планке — только артефактная ветка
    (SPEC 01M2XJKKPHM5XDAE42838AMBQH, требование 5, AC-6/AC-7):
    статическая проверка `guard.scan_artifact_disk_reads` над всеми
    `*.py` материализованной планки `acc_tdir` — тем же каталогом, что
    сухой сбор ниже. Непустой результат отклоняет переход именованным
    действием `ARTIFACT_DISK_READ_ACTION`, текст ошибок guard (файл,
    строка, рецепт) — в `detail`. Отказ идёт обычным путём `_run_gates`
    (`store.journal(..., "fsm", ...)` с префиксом «переход отклонён: »),
    поэтому история отказов брифа test_author и стоп-кран T038 видят его
    тем же классом, что отказ сухого сбора: шаг роли повторяется,
    `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` его не вычитает.

    Зовётся из `_tests_writing_dry_collect_gate` ДО `acceptance.collect`,
    а не отдельным элементом списка `_run_gates` в `fsm_advance.
    tests_writing`: зоны задачи (`scripts/guard.py`, этот модуль,
    `tests/`) не включают `orchestrator/fsm_advance.py`, а статическая
    проверка дешевле субпроцесса pytest и даёт точнее диагноз."""
    errors = guard.scan_artifact_disk_reads(acc_tdir)
    if not errors:
        return None
    hint = (f"перепиши чтение артефактов планки на помощник пульта "
            f"(from _pult import artifact_text; artifact_text(\"PLAN.md\"), "
            f"skills/test-authoring.md) и повтори artel.py advance {task_id}")
    return GateRefusal(ARTIFACT_DISK_READ_ACTION, "; ".join(errors), hint)


TEST_GROUPS_ACTION = "переход отклонён: группы приёмочных тестов"


def _project_imports(task_id: str, profile):
    """Правило импортов долгоживущих файлов по проекту задачи (SPEC
    01M5633WZ3Y3A0P4KKBZDB3KER, требование 6): признак артели — здесь,
    по проекту задачи, а не флагом вызывающего обработчика."""
    return project_profile.long_lived_imports(
        workspace.task_target(task_id), profile)


def _tests_writing_test_groups_gate(acc_tdir, task_id: str, profile, *,
                                    network_addresses: bool = True
                                    ) -> GateRefusal | None:
    """Строка группы у каждого `test_*.py` планки и проверки долгоживущих
    файлов — признаки требования 3 и «Ловит мутацию» у каждого метода
    (SPEC 01M3N0BWYQ9KHVN41Z4G72706R, требования 1-4, 6-7; ADR-0020).
    Правила — `scripts/guard.py`, здесь только область и отказ.

    Любой проект с профилем тестов (`profile` — `project_profile.Profile`;
    SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требование 5) — включая канареечные
    задачи; `None` — профиля нет, пропуск журналирует вызывающий
    обработчик. Файлы — те же, что у сухого сбора (`acc_tdir`).

    Подсказка test_author — в `detail`, не только в печати: история
    отказов брифа роли читает журнал (требование 6).

    `network_addresses` — признак адресов инварианта 35 (SPEC
    01M4JN2EDQP8Q3WVYK0TS95ZVC): только у артели, как рубеж `in_dev`
    (`_network_address_gate`); решает вызывающий обработчик."""
    if profile is None:
        return None
    # Тестовые файлы с меткой `AC-<n>: ` — по правилу планки проекта: строка
    # группы в первом комментарии (SPEC 01M5AA5TS90RDJ2AFXB882WTPD,
    # требование 5).
    rule = project_profile.plank_rule(workspace.task_target(task_id))
    files = guard.acceptance_test_files(acc_tdir, rule)
    # Долгоживущий файл в планке — отказ с подсказкой перенести его в
    # каталог долгоживущих тестов (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    # требование 4): временная оговорка задачи 1 снята; проверки задачи 1
    # для такого файла остаются.
    errors = (guard.group_line_errors_from_files(files, rule)
              + guard.long_lived_plank_errors(
                  files, task_id, profile.long_lived_dir,
                  profile.long_lived_name, rule=rule,
                  example=profile.long_lived_hint(task_id))
              + guard.long_lived_errors_from_files(
                  files, task_id, network_addresses=network_addresses,
                  project_imports=_project_imports(task_id, profile),
                  rule=rule)
              # Запреты в тексте файлов с меткой `AC-<n>: ` (SPEC
              # 01M5AQH8M2DKBV30NBY86J34A7, требование 7).
              + guard.plank_ban_errors(files, rule))
    if not errors:
        return None
    hint = f"исправь файл планки и повтори artel.py advance {task_id}"
    return GateRefusal(TEST_GROUPS_ACTION,
                       "; ".join(errors) + f"\nдальше: {hint}", hint)


LONG_LIVED_ACTION = "переход отклонён: долгоживущие файлы tests/"


def _long_lived_refusal(task_id: str, detail: str, profile) -> GateRefusal:
    hint = (f"test_author только добавляет файлы "
            f"{profile.long_lived_example(task_id)} со строкой "
            f"«Группа: {guard.GROUP_LONG_LIVED}»; верни прочее к базе ветки "
            f"и повтори artel.py advance {task_id}")
    return GateRefusal(LONG_LIVED_ACTION, f"{detail}\nдальше: {hint}", hint)


def _long_lived_git_refusal(task_id: str, detail: str) -> GateRefusal:
    """Сбой git проверки долгоживущих файлов — своё действие класса «чинит
    Оператор» (SPEC 01M446WEVJXARR5CDED8RE9CCR, требование 5.3): test_author
    его не починит, `LONG_LIVED_ACTION` остаётся за нарушением правила
    «только добавляет файлы»."""
    hint = f"разберись, почему git не отвечает, и повтори artel.py advance {task_id}"
    return GateRefusal(LONG_LIVED_GIT_REFUSAL_ACTION,
                       f"{detail}\nдальше: {hint}", hint)


def _tests_writing_code_diff(task_id: str, code_branch: str, profile):
    """(записи диффа, {путь: текст}, отказ) — дифф кодовой ветки против её
    базы (`gitcmd.diff_base`, `gitcmd.diff_name_status`) и тексты
    добавленных долгоживущих файлов задачи на голове ветки (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 2, 5) — по каталогу и шаблону
    имени профиля тестов проекта (`profile`, SPEC
    01M45FJVGQT1K0P8HDEXZX6HS7). Сбой git — отказ, а не пустой дифф: иначе
    нарушение прошло бы молча (ADR-0002)."""
    repo = workspace.task_repo(task_id)
    base = gitcmd.diff_base(code_branch, repo=repo)
    entries = (gitcmd.diff_name_status(base, code_branch, repo=repo)
              if base else None)
    if entries is None:
        return None, None, _long_lived_git_refusal(
            task_id, f"дифф кодовой ветки {code_branch} против базы не "
                     f"прочитан — git не ответил, проверка невозможна")
    files: dict[str, str] = {}
    for status, path, _new in entries:
        if status == "A" and profile.is_long_lived(task_id, path):
            text, reason = gitcmd.show(code_branch, path, repo=repo)
            if text is None:
                return None, None, _long_lived_git_refusal(
                    task_id, f"{path} не прочитан на голове {code_branch}: "
                             f"{reason}")
            files[path] = text
    return entries, files, None


def _diff_entry_error(task_id: str, status: str, path: str,
                      new_path: str | None, profile) -> str | None:
    """Нарушение правила «только добавление» одной записью диффа
    (требование 2); `None` — запись законна. Каталог и имя — профиля
    тестов проекта (у артели `tests/`, `test_<id>_<имя>.py`)."""
    directory = f"{profile.long_lived_dir}/"
    if status[:1] in ("R", "C"):
        return (f"{path} -> {new_path}: переименование/копия — test_author "
                f"не трогает существующие файлы")
    if status == "M":
        return f"{path}: правка файла базы ветки — существующие файлы не трогаются"
    if status == "D":
        return f"{path}: удаление файла базы ветки — существующие файлы не трогаются"
    if status != "A":
        return f"{path}: изменение «{status}» — допустимо только добавление"
    if not path.startswith(directory):
        return (f"{path}: путь вне {directory} — кодовая ветка несёт только "
                f"файлы {directory}")
    if not profile.is_long_lived(task_id, path):
        return (f"{path}: файл без префикса задачи — имя "
                f"{profile.long_lived_example(task_id)}")
    return None


def _tests_writing_long_lived_gate(task_id: str, code_branch: str, entries,
                                   files: dict[str, str], profile, *,
                                   network_addresses: bool = True
                                   ) -> GateRefusal | None:
    """Гейт «только добавление» на выходе из `tests_writing` (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 2-3; ADR-0020, п. 7 — второй
    рубеж за откатом чекпоинта): дифф кодовой ветки несёт только
    добавленные файлы `tests/` с префиксом задачи, путь каждого ещё не
    существует в `origin/main`, каждый — со строкой `Группа: долгоживущий`
    и проходит статические проверки задачи 1 (признаки, «Ловит мутацию»).
    Сухой сбор — тем же вызовом, что планка (`_tests_writing_dry_collect_
    gate`), он требует выписанной рабочей копии кодовой ветки.

    Каталог и шаблон имени — профиля тестов проекта (`profile`, SPEC
    01M45FJVGQT1K0P8HDEXZX6HS7, требование 5); `network_addresses` — как
    у `_tests_writing_test_groups_gate`."""
    errors = [error for status, path, new_path in entries
              if (error := _diff_entry_error(task_id, status, path, new_path,
                                             profile))]
    if files:
        repo = workspace.task_repo(task_id)
        main_ref = gitcmd.diff_base_source(code_branch, repo=repo)
        on_main = gitcmd.ls_tree_files(main_ref, profile.long_lived_dir,
                                       repo=repo)
        if on_main is None:
            return _long_lived_git_refusal(
                task_id, f"дерево {main_ref} не прочитано — git не ответил, "
                         f"проверка путей невозможна")
        # Профиль из шаблона `long_lived` — файлы с меткой по правилу
        # планки (SPEC 01M5AA5TS90RDJ2AFXB882WTPD, требования 5-6); иначе
        # `None`, прежний разбор Python.
        rule = project_profile.long_lived_rule(workspace.task_target(task_id),
                                               profile)
        for path in sorted(files):
            if path in on_main:
                errors.append(f"{path}: путь уже существует в {main_ref}")
            errors += guard.long_lived_group_errors(
                [(path, files[path])], profile.long_lived_dir, rule)
        errors += guard.long_lived_errors_from_files(
            sorted(files.items()), task_id,
            network_addresses=network_addresses,
            project_imports=_project_imports(task_id, profile), rule=rule)
        errors += guard.plank_ban_errors(sorted(files.items()), rule)
        if workspace.on_task_branch(task_id, code_branch) is not True:
            errors.append(f"рабочая копия кодовой ветки {code_branch} не "
                          f"выписана — долгоживущие файлы не собрать")
    if not errors:
        return None
    return _long_lived_refusal(task_id, "; ".join(errors), profile)


def _tests_writing_manifest_gate(conn, task_id: str, code_branch: str,
                                 paths: list[str]) -> GateRefusal | None:
    """Перечень долгоживущих файлов в ветку документов (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 6, формат Р2) — ДО записи
    `tests_locked_sha`, чтобы перечень попал в дерево коммита лока и его
    правку ловила нынешняя сверка лока. Суммы — от байтов файлов в дереве
    головы кодовой ветки. Перечень без записей — пустой файл, тоже
    записывается: отсутствие файла в дереве лока значит «лок снят до
    внедрения перечня», а не «файлов нет». Сбой git — отказ."""
    repo = workspace.task_repo(task_id)
    head = gitcmd.branch_head_sha(code_branch, repo=repo)
    digests: dict[str, str] = {}
    for path in paths:
        digest = blob_sha256(head, path, repo) if head else None
        if digest is None:
            return _long_lived_git_refusal(
                task_id, f"{path}: сумма на голове {code_branch} не "
                         f"посчитана — git не ответил, перечень не записан")
        digests[path] = digest
    rel = long_lived_manifest_rel(task_id)
    drift = fixation.ref_drift(conn, task_id)
    if drift is not None and drift.moved:
        # Перечень поверх подмены не пишется; переход ниже сам уведёт
        # задачу в эскалацию инцидентом (`store.set_state`).
        return None
    if drift is not None:
        # Голова не прочитана (git не ответил или ссылки нет): запись в
        # отсутствующую ссылку дала бы корневой коммит, а его перефиксация
        # узаконила бы удаление ссылки ролью.
        return GateRefusal(
            f"переход отклонён: {fixation.DOCS_REF_UNREAD_ACTION}",
            f"{rel} не записан в ветку документов: {drift.text()}",
            f"восстанови {artifact_branch.branch_name(task_id)} или разбери "
            f"инцидент, затем artel.py advance {task_id}")
    sha = artifact_branch.commit_files(
        task_id, {rel: guard.render_long_lived_manifest(digests)},
        f"{task_id}: перечень долгоживущих тестов (выход из tests_writing)")
    if not sha:
        return _long_lived_git_refusal(
            task_id, f"{rel} не записан в ветку документов — git не ответил")
    store.journal(conn, task_id, "fsm", "перечень долгоживущих тестов записан",
                  f"{rel}: {len(digests)} файл(ов), sha {sha}")
    # Запись пульта перефиксирует свой коммит сама: переход ниже сверяет
    # голову с фиксацией (SPEC 01M41AB597B330P2RCXCMVRZPE, требование 4).
    store.record_fixation(conn, task_id)
    return None


def _tests_writing_dry_collect_gate(acc_tdir, run_cwd, task_id: str,
                                    extra: list[str] = (),
                                    command=None) -> GateRefusal | None:
    """Требование 2/AC-4/AC-5: сухой сбор материализованной планки
    (`acceptance.collect`) ПОСЛЕ трассируемости AC и гейта AC-8, ДО
    перевода задачи в `in_dev` — отказ сбора (импорт/синтаксис планки)
    отклоняет переход тем же текстом действия («переход отклонён: планка
    не собирается»), что и остальные отказы `tests_writing`, чтобы стоп-
    кран T038 и история отказов брифа test_author (`brief.
    advance_refusal_history`) видели его как обычный отказ шага роли,
    не как повод остановиться навсегда (AC-6 — уже общий механизм,
    правки не требует).

    Первым — источник артефактов (`_tests_writing_artifact_source_gate`,
    SPEC 01M2XJKKPHM5XDAE42838AMBQH): планка, читающая `PLAN.md` с диска,
    отклоняется своим именованным действием без запуска субпроцесса
    pytest.

    `extra` — долгоживущие файлы `tests/` задачи: собираются тем же вызовом
    из рабочей копии кодовой ветки (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    требование 3).

    `command` — начало команды прогона из профиля тестов проекта (SPEC
    01M45FJVGQT1K0P8HDEXZX6HS7, требование 6) либо сам профиль
    `pytest-own` или профиль с отчётом — он идёт в сбор как есть, не
    сворачиваясь в список (SPEC 01M52EEHSRD93WMPHWB5VJYRKD,
    01M590GJAF0EDV4NBC4C99MFVH); `None` — команда пульта (проект без
    профиля)."""
    refusal = _tests_writing_artifact_source_gate(acc_tdir, task_id)
    if refusal is not None:
        return refusal
    own = acceptance.own(command) or acceptance.reported(command)
    kwargs = ({"command": own} if own is not None
              else {"command": list(command)} if command else {})
    if extra:
        collected, tail = acceptance.collect(acc_tdir, run_cwd, extra=list(extra),
                                             **kwargs)
    else:
        collected, tail = acceptance.collect(acc_tdir, run_cwd, **kwargs)
    if collected:
        return None
    hint = f"почини импорт/синтаксис планки и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: планка не собирается", tail, hint)


# ------------------------------------------------ честный `FAIL_TO_PASS`
#
# Выход из `tests_writing` у компонента записи `components:` с `report`
# (SPEC 01M5AQH8M2DKBV30NBY86J34A7, требования 2-5): тест каждого
# покрытого критерия на коде базы обязан упасть провалом проверки, а тест
# файла с маркером «Зелёный с рождения:» — пройти.

# Деталь перехода гейта SPEC (`orchestrator/fsm.py`, `cmd_approve`):
# опора перечня «Зелёный с рождения» — фиксация именно этого перехода.
SPEC_GATE_PASSED_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"
_TRANSITION_ACTION = "state -> tests_writing"
_FIXATION_ACTION = "sha зафиксирован"
_STEP_START_ACTION = "agent run started"
# Хвост детали `store.set_state` при непрочитанной голове ссылки документов.
_UNFIXED_TRANSITION = "без паспорта и фиксации"
_ARTIFACTS_SHA = re.compile(r"артефакты=(\S+)")
GREEN_SECTION = "Зелёный с рождения"
NO_TESTED_CRITERIA_NOTE = "честный FAIL_TO_PASS: критериев с тестом нет"
ANCHOR_NOT_FOUND = "опора SPEC для перечня «Зелёный с рождения» не найдена: "
NO_RECORD_FINDING = "теста нет в отчёте"
REPEAT_FINDING = "повтор имени теста в файле: "
FILE_LEVEL_FINDING = "ошибка уровня файла — тесты файла не исполнены"
PREPARE_PREFIX = "отказ подготовки: "
# Вид падения записи JUnit об ошибке сбора файла (pytest
# `--continue-on-collection-errors`).
_COLLECTION_FAILURE = outcome.COLLECTION_FAILURE
# Засчитывание ошибки уровня файла «новым модулем» (SPEC
# 01M5EDW6KD1ESCEVRSV2WPNXAP, требование 2; ADR-0026 п. 5): запись журнала
# задачи, её деталь — строка пакета ревьювера (`review._outcome_gate_lines`).
FILE_LEVEL_COUNTED_ACTION = "ошибка уровня файла засчитана красным"
FILE_LEVEL_COUNTED_DETAIL = "новый модуль {path} (файл {name})"
# Итоговая строка трассировки сбора pytest о неразрешённом импорте.
_PY_MISSING_MODULE = re.compile(
    r"(?:E   )?ModuleNotFoundError: No module named '([^']+)'")
# Две формы сообщения Vitest о неразрешённом импорте.
_VITEST_MISSING_MODULE = (
    re.compile(r'Failed to resolve import "([^"]+)" from "[^"]*"'),
    re.compile(r"Cannot find module '([^']+)'"))


def _spec_anchor(conn, task_id: str) -> tuple[str, str]:
    """(sha опоры, причина ненахода): `артефакты=` ПЕРВОЙ записи «sha
    зафиксирован» после последней записи перехода гейта SPEC, если она
    раньше первой «agent run started» после того же перехода и между ними
    нет перехода «без паспорта и фиксации» (требование 5)."""
    rows = store.task_steps(conn, task_id)
    start = None
    for i, row in enumerate(rows):
        if row["action"] == _TRANSITION_ACTION and \
                (row["detail"] or "") == SPEC_GATE_PASSED_DETAIL:
            start = i
    if start is None:
        return "", (f"в журнале нет записи «{_TRANSITION_ACTION}» с деталью "
                    f"«{SPEC_GATE_PASSED_DETAIL}»")
    for row in rows[start + 1:]:
        if _UNFIXED_TRANSITION in (row["detail"] or ""):
            return "", (f"переход гейта SPEC прошёл {_UNFIXED_TRANSITION} — "
                        f"версия SPEC.md на переходе не зафиксирована")
        if row["action"] == _STEP_START_ACTION:
            return "", (f"после перехода гейта SPEC запись «{_FIXATION_ACTION}» "
                        f"появилась только после начала шага роли — это "
                        f"фиксация чекпоинта, а не перехода")
        if row["action"] == _FIXATION_ACTION:
            match = _ARTIFACTS_SHA.search(row["detail"] or "")
            sha = match.group(1) if match else ""
            if not sha or sha == "—":
                return "", (f"в опорной записи «{_FIXATION_ACTION}» "
                            f"артефакты=— (голова ссылки документов на "
                            f"переходе не прочитана)")
            return sha, ""
    return "", f"после перехода гейта SPEC нет записи «{_FIXATION_ACTION}»"


def _spec_anchor_check(conn, task_id: str) -> tuple[GateRefusal | None, str]:
    """(отказ, текст SPEC.md опорной версии): опора не найдена или SPEC.md
    на голове ссылки документов отличается от опорной версии — отказ
    своего действия (требование 5)."""
    rel = f"tasks/{task_id}/SPEC.md"
    hint = (f"опору чинит Оператор (журнал перехода гейта SPEC, ссылка "
            f"документов), затем artel.py advance {task_id}")
    sha, reason = _spec_anchor(conn, task_id)
    anchor = None
    if sha:
        anchor, why = artifact_branch.show(task_id, sha, rel)
        if anchor is None:
            reason = f"SPEC.md в опорном коммите {sha} не прочитан: {why}"
    if anchor is None:
        return GateRefusal(SPEC_ANCHOR_REFUSAL_ACTION,
                           f"{ANCHOR_NOT_FOUND}{reason}", hint), ""
    ref = artifact_branch.branch_name(task_id)
    head, why = artifact_branch.show(task_id, ref, rel)
    if head is None:
        return GateRefusal(
            SPEC_ANCHOR_REFUSAL_ACTION,
            f"SPEC.md на голове {ref} не прочитан ({why}) — сверка с опорной "
            f"версией {sha} невозможна", hint), ""
    if head != anchor:
        return GateRefusal(
            SPEC_CHANGED_AFTER_GATE_REFUSAL_ACTION,
            f"SPEC.md изменён после одобрения на гейте SPEC — верни его к "
            f"версии {sha}",
            f"верни tasks/{task_id}/SPEC.md к версии {sha} (правку SPEC после "
            f"гейта вносит Оператор) и повтори artel.py advance {task_id}"), ""
    return None, anchor


def _green_list(spec_text: str) -> set[int]:
    """Критерии раздела SPEC «## Зелёный с рождения» (строки `AC-<n>`)."""
    body = guard.section_body(spec_text, GREEN_SECTION)
    return {int(n) for n in re.findall(r"\bAC-(\d+)\b", body)}


def _criterion_numbers(covered) -> set[int]:
    """Номера критериев `covered`: `AC-<n>` (ответ Оператора, ANSWER-1) или
    числа."""
    numbers = set()
    for item in covered:
        if isinstance(item, int):
            numbers.add(item)
            continue
        match = re.fullmatch(r"AC-(\d+)", str(item))
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def _task_long_lived_paths(conn, task_id: str, profiles
                           ) -> tuple[list[str] | None, GateRefusal | None]:
    """Пути долгоживущих файлов, которые кодовая ветка задачи добавила
    против базы, по шаблонам `profiles` — для вызова гейта без путей
    перехода. Ветки ещё нет — файлов нет; сбой git — отказ подготовки."""
    branch = store.get_task(conn, task_id)["branch"]
    repo = workspace.task_repo(task_id)
    if not gitcmd.branch_exists(branch, repo=repo):
        return [], None
    base = gitcmd.diff_base(branch, repo=repo)
    entries = (gitcmd.diff_name_status(base, branch, repo=repo)
               if base else None)
    if entries is None:
        return None, GateRefusal(
            FAIL_TO_PASS_PREPARE_REFUSAL_ACTION,
            f"{PREPARE_PREFIX}дифф кодовой ветки {branch} против базы не "
            f"прочитан — git не ответил",
            f"разберись, почему git не отвечает, и повтори artel.py advance "
            f"{task_id}")
    return sorted(path for status, path, _new in entries
                  if status == "A" and any(
                      p.long_lived_dir and p.is_long_lived(task_id, path)
                      for p in profiles)), None


def _check_failure_kind(record, profile) -> str:
    """Вид записи, не являющейся провалом проверки (требование 3); пусто —
    провал проверки: у `pult-vitest` — `failed` с именем из
    `failure_errors`, у `junit-xml` — `failed` с видом падения от
    «assert » или от имени из `failure_errors`."""
    if record.retries:
        return f"{outcome.RETRY_NOTE} внутри прогона: {record.retries}"
    if record.outcome != outcome.FAILED:
        return outcome_kind(record)
    if record.fails:
        return "fails (тест помечен it.fails)"
    failure = record.failure or ""
    names = tuple(profile.failure_errors)
    if profile.report == project_profile.REPORT_VITEST:
        check = failure in names
    else:
        check = failure.startswith("assert ") or failure.startswith(names)
    return "" if check else f"имя ошибки {failure or 'без имени'}"


def _component_runs(tdir: Path, run_cwd, components, files
                    ) -> tuple[dict, list[str], list[str]]:
    """({компонент: записи}, причины отказа подготовки, находки таймаута) —
    прогон планки и своих долгоживущих файлов каждого компонента на коде
    базы рабочей копии (`acceptance.run` с `records`)."""
    runs: dict = {}
    prepare: list[str] = []
    timeouts: list[str] = []
    for profile in components:
        name = profile.component
        extra = [f.rel for f in files
                 if not f.plank and f.profile.component == name]
        records: list = []
        acceptance.run(tdir, cwd=run_cwd, extra=extra, command=profile,
                       records=records, continue_on_collection_errors=True)
        state = next((r for r in records
                      if isinstance(r, acceptance.ReportRun)), None)
        runs[name] = [r for r in records if isinstance(r, outcome.CaseResult)]
        if state is None:
            prepare.append(f"компонент {name}: прогон не вернул исхода")
        elif state.refusal:
            prepare.append(f"компонент {name}: {state.refusal}")
        elif state.timed_out:
            timeouts.append(f"таймаут прогона компонента {name}: прогон "
                            f"превысил {config.ACCEPTANCE_TIMEOUT_SEC}с — "
                            f"тесты не исполнены до конца")
        elif state.state == outcome.UNKNOWN and not state.block:
            # Записей нет вовсе (`block` пуст только у отчёта, которого нет
            # или который не разобран): «теста нет в отчёте» было бы ложью.
            prepare.append(f"компонент {name}: {state.reason}")
    return runs, prepare, timeouts


def _is_file_level(record) -> bool:
    return record.file_level or (
        record.outcome == outcome.ERROR
        and record.failure.startswith(_COLLECTION_FAILURE))


def _record_owners(by_file: dict) -> dict:
    """{id(запись): файл задачи} — записи, сопоставленные файлу по пути."""
    return {id(record): cfile for cfile, records in by_file.items()
            for record in records}


def _file_level_findings(files, runs: dict, by_file: dict,
                         counted: set = frozenset()) -> list[str]:
    """Ошибки уровня файла (требование 4; SPEC 01M5EDW6KD1ESCEVRSV2WPNXAP,
    требование 1): незасчитанная запись `file_level` любого отчёта либо
    запись JUnit `error` с видом «collection failure» — запись с путём файла
    задачи (Vitest) по имени этого файла, иначе файл по имени записи;
    тестовый файл планки `pult-vitest` без записей в отчёте. `counted` —
    `(компонент, id)` записей, засчитанных красным."""
    plank_names = {Path(f.name).stem: f.name for f in files if f.plank}
    owners = _record_owners(by_file)
    found = []
    for component, records in runs.items():
        for record in records:
            if not _is_file_level(record) or (component, record.id) in counted:
                continue
            cfile = owners.get(id(record))
            if cfile is not None:
                found.append(f"{cfile.name}: {FILE_LEVEL_FINDING}")
                continue
            where = record_location(record)
            dotted = where[2] if where is not None else record.id
            name = plank_names.get(dotted.rsplit(".", 1)[-1], dotted)
            found.append(f"{name}: {FILE_LEVEL_FINDING}")
    for cfile in files:
        if cfile.plank and not by_file[cfile] and \
                cfile.profile.report == project_profile.REPORT_VITEST:
            found.append(f"{cfile.name}: {FILE_LEVEL_FINDING}")
    return list(dict.fromkeys(found))


def _dotted_file(rel: str, root: str) -> str | None:
    """Точечный путь файла `rel` (от корня репозитория) от каталога `root`
    — имя записи сбора pytest; `None` — файл не `.py` или вне `root`."""
    if not rel.endswith(".py"):
        return None
    inner = os.path.relpath(os.path.normpath(rel),
                            os.path.normpath(root or ".")).replace(os.sep, "/")
    if inner == ".." or inner.startswith("../"):
        return None
    return inner[:-3].replace("/", ".")


def _level_file(component: str, record, files, owners: dict):
    """Файл задачи записи `file_level`: у Vitest — по пути записи
    (`file_records`), у JUnit — по ПОЛНОМУ точечному пути файла от
    `workdir` (SPEC 01M5EDW6KD1ESCEVRSV2WPNXAP, требование 1), не по
    последнему сегменту: одноимённый долгоживущий файл не засчитывает файл
    планки."""
    cfile = owners.get(id(record))
    if cfile is not None:
        return cfile
    where = record_location(record)
    if where is None:
        return None
    return next((f for f in files if f.profile.component == component
                 and _dotted_file(f.rel, where[1]) == where[2]), None)


def _python_module_name(path: str, workdir: str) -> str | None:
    """Ожидаемое имя модуля пути `path` (от корня проекта) от `workdir`:
    без `.py` через точки, у `__init__.py` — имя пакета; `None` — путь не
    модуль Python под `workdir`."""
    root = workdir.strip("/")
    if root:
        if not path.startswith(root + "/"):
            return None
        path = path[len(root) + 1:]
    if not path.endswith(".py"):
        return None
    stem = path[:-len(".py")]
    if stem == "__init__":
        return None
    if stem.endswith("/__init__"):
        stem = stem[:-len("/__init__")]
    return stem.replace("/", ".")


def _missing_import_path(record, cfile, zones: list[str]) -> str | None:
    """Путь P из `zones`, неразрешённый импорт которого — ошибка записи
    (условие (б) требования 2 SPEC 01M5EDW6KD1ESCEVRSV2WPNXAP); `None` —
    ошибка иная.

    Python — только итоговая (последняя непустая) строка трассировки:
    вхождение того же текста выше — например, в сообщении `RuntimeError` —
    признаком не является. Vitest — две формы сообщения; спецификатор
    разрешается от каталога файла в выкладке."""
    detail = record.detail or ""
    if cfile.profile.report == project_profile.REPORT_VITEST:
        spec = next((m.group(1) for form in _VITEST_MISSING_MODULE
                     if (m := form.search(detail))), None)
        if spec is None:
            return None
        resolved = os.path.normpath(os.path.join(
            os.path.dirname(cfile.rel), spec)).replace(os.sep, "/")
        bare = not os.path.splitext(spec)[1]
        for zone in zones:
            stem, ext = os.path.splitext(zone)
            # Все три случая (б) — про модуль-файл с расширением; элемент
            # без расширения — каталог, «элементы-каталоги не считаются».
            if not ext:
                continue
            if resolved == zone or (bare and resolved == stem) \
                    or resolved + "/index" == stem:
                return zone
        return None
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    match = _PY_MISSING_MODULE.fullmatch(lines[-1]) if lines else None
    if match is None:
        return None
    workdir = getattr(cfile.profile, "workdir", "") or ""
    return next((zone for zone in zones
                 if _python_module_name(zone, workdir) == match.group(1)), None)


def _absent_in_base(conn, task_id: str, run_cwd, path: str) -> bool | None:
    """P нет в дереве `diff_base` кодовой ветки (ветки нет — в HEAD рабочей
    копии прогона); `None` — git не ответил. `ls-tree` рекурсивен: P,
    оказавшийся в базе каталогом, перечислен своими файлами `P/…` — это
    присутствие, не отсутствие."""
    branch = store.get_task(conn, task_id)["branch"]
    repo = workspace.task_repo(task_id)
    if gitcmd.branch_exists(branch, repo=repo):
        rev = gitcmd.diff_base(branch, repo=repo)
    else:
        rev, repo = "HEAD", Path(run_cwd)
    listed = gitcmd.ls_tree_files(rev, path, repo=repo) if rev else None
    if listed is None:
        return None
    return not any(rel == path or rel.startswith(path + "/") for rel in listed)


def _counted_new_modules(conn, task_id: str, run_cwd, files, runs: dict,
                         by_file: dict, anchor_text: str
                         ) -> tuple[dict, GateRefusal | None]:
    """({(компонент, id записи): (файл, P)}, отказ подготовки) — ошибки
    уровня файла, засчитанные красным как «новый модуль» (SPEC
    01M5EDW6KD1ESCEVRSV2WPNXAP, требование 2; ADR-0026 п. 5): файл планки
    без маркера «Зелёный с рождения:», импорт не разрешён именно у P —
    элемента `zones:` опорного SPEC (не `zones-extend`), которого нет в
    базе кодовой ветки. Сбой git — отказ подготовки, не засчитывание."""
    meta = yamlmini.frontmatter(anchor_text) or {}
    zones = sorted(guard.zone_items(meta.get("zones")))
    owners = _record_owners(by_file)
    counted: dict = {}
    for component, records in runs.items():
        for record in records:
            if not record.file_level:
                continue
            cfile = _level_file(component, record, files, owners)
            if cfile is None or not cfile.plank or cfile.green:
                continue
            path = _missing_import_path(record, cfile, zones)
            if path is None:
                continue
            absent = _absent_in_base(conn, task_id, run_cwd, path)
            if absent is None:
                return {}, GateRefusal(
                    FAIL_TO_PASS_PREPARE_REFUSAL_ACTION,
                    f"{PREPARE_PREFIX}отсутствие {path} в базе кодовой ветки "
                    f"не проверено — git не ответил",
                    f"разберись, почему git не отвечает, и повтори artel.py "
                    f"advance {task_id}")
            if absent:
                counted[(component, record.id)] = (cfile, path)
    return counted, None


def _criterion_findings(numbers: set[int], files, by_file: dict,
                        green: set[int], counted_files=frozenset()
                        ) -> list[str]:
    """Находки по критериям (требования 3, 5): запись каждого покрытого
    критерия — провал проверки, у файла с маркером «Зелёный с рождения:»
    (все его критерии — из перечня) — прошла; маркер у файла с критерием вне
    перечня — находка. «Теста нет в отчёте» не даёт критерий, все файлы
    которого засчитаны красным (`counted_files`; SPEC
    01M5EDW6KD1ESCEVRSV2WPNXAP, требование 2)."""
    findings: list[str] = []
    green_files = set()
    for cfile in files:
        if not (cfile.plank and cfile.green):
            continue
        outside = sorted(cfile.numbers - green)
        if outside:
            listed = ", ".join(f"AC-{n}" for n in outside)
            findings.append(
                f"{cfile.name}: маркер «Зелёный с рождения:» у файла с тестом "
                f"критерия вне раздела SPEC «## {GREEN_SECTION}»: {listed}")
        else:
            green_files.add(cfile)
    by_number: dict[int, list] = {}
    for cfile in files:
        seen = set()
        for record in by_file[cfile]:
            n = record_criterion(record, cfile)
            if n is not None:
                seen.add(n)
                by_number.setdefault(n, []).append((record, cfile))
        if cfile in green_files:
            findings += [f"AC-{n}: {NO_RECORD_FINDING} (файл {cfile.name} с "
                         f"маркером «Зелёный с рождения:»)"
                         for n in sorted(cfile.numbers - seen)]
    in_files = set().union(*(f.numbers for f in files)) if files else set()
    for n in sorted(numbers & in_files):
        pairs = by_number.get(n, [])
        if not pairs:
            if not all(f in counted_files for f in files if n in f.numbers):
                findings.append(f"AC-{n}: {NO_RECORD_FINDING}")
            continue
        for record, cfile in pairs:
            if cfile in green_files:
                kind = not_passed_kind(record)
                if kind:
                    findings.append(f"{record.id}: не прошёл на базе у файла "
                                    f"с маркером «Зелёный с рождения:» — {kind}")
            else:
                kind = _check_failure_kind(record, cfile.profile)
                if kind:
                    findings.append(f"{record.id}: не провал проверки на базе "
                                    f"— {kind}")
    return findings


def _task_plank_dir(acc_tdir) -> Path:
    """Каталог задачи с `acceptance_tests/`: переход передаёт выкладку
    `<рабочая копия>/tasks/<id>`, прямой вызов — сам каталог планки."""
    path = Path(acc_tdir)
    return path.parent if path.name == "acceptance_tests" else path


def _tests_writing_foreign_plank_gate(task_id: str, acc_tdir, target: str,
                                      profile) -> GateRefusal | None:
    """Планка чужого компонента на выходе из `tests_writing` (SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 4): у записи из нескольких
    компонентов файл планки, который правило планки относит к компоненту
    X, отличному от компонента задачи, — отказ честного FAIL_TO_PASS, если
    X в границе гейта (`in_outcome_bounds` профиля X), независимо от
    границы компонента задачи; X вне границы — файл не проверяется, как
    прежде. У прочих записей и при правиле по умолчанию — `None`."""
    if profile is None or not project_profile.is_multi(target):
        return None
    rule = project_profile.plank_rule(target)
    if rule.is_default or rule.refusal:
        return None
    try:
        owners = {p.component: p
                  for p in project_profile.component_profiles(target)}
    except targets.TargetsError as exc:
        return GateRefusal(project_profile.REFUSAL_ACTION, str(exc),
                           project_profile.refusal_hint(task_id))
    tests_dir = _task_plank_dir(acc_tdir) / "acceptance_tests"
    if not tests_dir.is_dir():
        return None
    foreign = []
    for path in sorted(tests_dir.iterdir()):
        if not path.is_file() or not rule.is_test(path.name):
            continue
        comp = rule.component_of(path.name)
        if not comp or comp == profile.component:
            continue
        if in_outcome_bounds(owners.get(comp)):
            foreign.append(f"файл планки {path.name} — компонента {comp}, "
                           f"задача — компонента {profile.component}")
    if not foreign:
        return None
    return GateRefusal(
        FAIL_TO_PASS_REFUSAL_ACTION, "; ".join(foreign),
        f"перенеси тест в файл планки компонента {profile.component} или "
        f"раздели задачу по компонентам и повтори artel.py advance {task_id}")


def _tests_writing_fail_to_pass_gate(conn, task_id: str, acc_tdir, run_cwd,
                                     covered: set[str], profiles: list, *,
                                     long_lived_paths: list[str] | None = None
                                     ) -> GateRefusal | None:
    """Честный `FAIL_TO_PASS` на выходе из `tests_writing` (SPEC
    01M5AQH8M2DKBV30NBY86J34A7, требования 2-5; подпись — ANSWER-1, п. 1).

    `acc_tdir` — каталог планки, `run_cwd` — рабочая копия кодовой ветки
    (код базы), `covered` — критерии `AC-<n>`, покрытые тестом, `profiles`
    — профили компонентов; компонент файла гейт выбирает сам.
    `long_lived_paths` — пути своих долгоживущих файлов от `run_cwd`, уже
    прочитанные переходом; не переданы — гейт читает их из диффа кодовой
    ветки.

    Порядок: граница (вне — `None`, гейта нет) → опора SPEC и «SPEC изменён
    после одобрения» → правило планки не построено → критериев с тестом нет
    (запись журнала, `None`) → пустой `failure_errors` компонента файла →
    прогон (отказ подготовки) → находки одним отказом: таймаут → повторы
    `#<n>` → по критериям → ошибки уровня файла."""
    if not any(in_outcome_bounds(p) for p in profiles):
        return None
    refusal, anchor_text = _spec_anchor_check(conn, task_id)
    if refusal is not None:
        return refusal
    # Утверждённая на гейте SPEC замена (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R,
    # требование 4): критерий, которому сопоставлен заменяемый тест, обязан
    # иметь тест планки — пометка вместо теста замену не несёт.
    from .mandate import approved_replacements
    from .refusal_classes import REPLACEMENT_REFUSAL_ACTION
    tested = set(_criterion_numbers(covered))
    unmatched = [f"заменяемый тест {test_id} сопоставлен AC-{n}, а у AC-{n} "
                 f"нет теста планки"
                 for test_id, n in approved_replacements(conn, task_id).items()
                 if n not in tested]
    if unmatched:
        return GateRefusal(
            REPLACEMENT_REFUSAL_ACTION, "\n".join(unmatched),
            f"напиши тест планки каждого такого критерия и повтори artel.py "
            f"advance {task_id}")
    target = store.task_target(conn, task_id)
    rule = project_profile.plank_rule(target)
    if rule.refusal:
        return GateRefusal(project_profile.REFUSAL_ACTION, rule.refusal,
                           project_profile.refusal_hint(task_id))
    numbers = _criterion_numbers(covered)
    if not numbers:
        store.journal(conn, task_id, "fsm", NO_TESTED_CRITERIA_NOTE,
                      "у каждого критерия пометка вместо теста — прогона "
                      "планки на базе нет")
        return None
    if long_lived_paths is None:
        long_lived_paths, refusal = _task_long_lived_paths(conn, task_id,
                                                           profiles)
        if refusal is not None:
            return refusal
    tdir = _task_plank_dir(acc_tdir)
    files = [f for f in criterion_files(task_id, tdir, Path(run_cwd), rule,
                                        list(profiles), list(long_lived_paths),
                                        target)
             if in_outcome_bounds(f.profile)]
    components = list({f.profile.component: f.profile for f in files}.values())
    empty = [p.component for p in components if not p.failure_errors]
    if empty:
        return GateRefusal(
            NO_FAILURE_ERRORS_REFUSAL_ACTION,
            "; ".join(f"список «провал проверки» не задан у компонента {name}"
                      for name in empty),
            f"задай failure_errors компонента в targets.yaml и повтори "
            f"artel.py advance {task_id}")
    runs, prepare, timeouts = _component_runs(tdir, run_cwd, components, files)
    if prepare:
        return GateRefusal(
            FAIL_TO_PASS_PREPARE_REFUSAL_ACTION,
            "; ".join(f"{PREPARE_PREFIX}{reason}" for reason in prepare),
            f"разберись с подготовкой прогона компонента и повтори artel.py "
            f"advance {task_id}")
    by_file = file_records(files, runs)
    counted, refusal = _counted_new_modules(conn, task_id, run_cwd, files, runs,
                                            by_file, anchor_text)
    if refusal is not None:
        return refusal
    for cfile, path in dict.fromkeys(counted.values()):
        store.journal(conn, task_id, "fsm", FILE_LEVEL_COUNTED_ACTION,
                      FILE_LEVEL_COUNTED_DETAIL.format(path=path, name=cfile.name))
    repeats = [f"{REPEAT_FINDING}{record.id}" for cfile in files
               for record in by_file[cfile]
               if is_repeat(record_location(record))]
    findings = (timeouts + repeats
                + _criterion_findings(numbers, files, by_file,
                                      _green_list(anchor_text),
                                      {cfile for cfile, _path in counted.values()})
                + _file_level_findings(files, runs, by_file, set(counted)))
    if not findings:
        return None
    hint = (f"перепиши тесты критериев так, чтобы на коде базы каждый падал "
            f"провалом проверки (имя ошибки из failure_errors компонента), и "
            f"повтори artel.py advance {task_id}")
    # Подсказка — в детали (её читает бриф test_author, `brief.py`); пустой
    # `hint` — печать отказа не повторяет её второй строкой (перенос 15).
    return GateRefusal(FAIL_TO_PASS_REFUSAL_ACTION,
                       "; ".join(findings) + f"\nдальше: {hint}", "")
