"""Тесты гейта неослабления по исходам на гейте мержа: доказательство для
головы, пакет ревьювера и двусторонний прогон по имени ошибки (волна 2а-2а
сведения тестов, SPEC 01M5R0DPNHZ7N8YBXMH375SMEE; ADR-0027 п. 8, ADR-0020
п. 8).

Свод долгоживущего `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`
(SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7: строка доказательства записи пройденного
гейта, гейт исходов в окне мержа, доказательство по четвёрке, эскалация
находки и сбой подготовки без push, строки пакета ревьювера, классификатор
провала проверки в двустороннем прогоне, граница гейта). Долгоживущий файл
удалён решением Оператора (ADR-0020 п. 8), его свойства перенесены сюда.
Доказательство неослабления — таблицы `mutation-run` «до» и «после» в PLAN
задачи.

Стенд `box` — `MergeOutcomeSandbox`, стенд `two_sided_box` —
`TwoSidedSandbox` из `tests/merge_outcome_sandbox.py` поверх песочницы
гейта исходов `OutcomeGateSandbox` из `tests/outcome_gate_sandbox.py`:
настоящий git, учебный внешний проект с единственным компонентом
`junit-xml` на поддельном `pytest` (либо `pult-vitest` без Node), раннер
подменён шпионом `subprocess.Popen`; СТОРОНА прогона — по метке выписки
(`app.py`: `'base'` у базы, `'head-…'` у головы кодовой ветки), исход
теста — последовательность сценария по стороне. Гейт мержа — сквозной
`fsm.cmd_approve` задачи на `merge_gate`: подменены только внешние
проверки, которых в песочнице нет, — цвет CI ветки и main
(`ci.branch_status` — шпион, считающий вызовы; `ci.main_line_status`),
Draft MR форджа и публикация головы (`github_adapter`). Тело гейта мержа
за один `approve` входит дважды (первый вход уходит ждать CI), поэтому
«прогон был» — хоть один вызов полного набора, «прогона не было» — ни
одного.

Сбои подготовки — шпион `subprocess.run`: отказ git только в кадрах модулей
гейта (`orchestrator.advance_gates.outcome_integrity`,
`orchestrator.fsm_merge_gate`) — выписка с sha головы, `ls-tree` файлов
блокировки (ключ компонента не снят); фетч `refs/heads/main` — в любом
кадре (sha main не получен).

Ключ компонента сверяется публичным `acceptance.suite_result_key` по дереву
головы (`<голова>^{tree}`) с профилем решения `project_profile.decide` и
рабочей копией головы (`root`): это тот же ключ `_report_suite_result_key`
с `base=False`, что требует SPEC.

Имена проектов, файлов, тестов и числа — из `random`; зерно печатается и
входит в текст каждого провала. Методы подготовки с утверждениями тесты
зовут через стенд; помощник, утверждающий исход, — функция модуля
`no_gate_refusal` (первый параметр — стенд, последний — `case`). Бывшие
`subTest` — прямым кодом или прежним циклом в одной функции: ярлык
подслучая и зерно — в локальном `case` (`tag` у бывших `Ac11`, `Ac12`, где
`case` — переменная цикла), он стоит спереди в сообщении каждого
утверждения подслучая.
"""
import contextlib
import hashlib
import io

import pytest

from orchestrator import acceptance, checkpoint, config, store
from orchestrator.advance_gates import refusal_classes, two_sided
from tests.fixtures import _sandbox
from tests.merge_outcome_sandbox import (
    APPROVE_HINT, COUNTS_MARK, COVERED_BY, FLAKY_ON_BASE, FRESHNESS_DOCS,
    MANDATE_NONE, MERGE_OUTCOME_ACTION, NOT_RUN, OPERATOR_FIXES,
    PASSED_ACTION, PREPARE_ACTION, PROOF_LINE, PROVEN, PULLED,
    MergeOutcomeSandbox, TwoSidedSandbox)
from tests.outcome_gate_sandbox import GATE_ACTIONS, py_source


@pytest.fixture
def box():
    """Стенд MergeOutcomeSandbox после setUp."""
    yield from _sandbox(MergeOutcomeSandbox)


@pytest.fixture
def two_sided_box():
    """Стенд TwoSidedSandbox после setUp."""
    yield from _sandbox(TwoSidedSandbox)


def no_gate_refusal(box, rows: list, output: str, case: str = "") -> None:
    for action in GATE_ACTIONS:
        box.assertEqual(box.details(rows, action), [],
                         case + box.explain(rows, output))


# ---------------------------------------------------------------- Ac1ProofLineTest


def test_ac1_passed_record_carries_head_base_key_and_mandate(box):
    """Запись пройденного гейта на выходе из `in_dev`: сразу после строки чисел — строка головы, базы, ключа компонента и отпечатка мандата.

    Сценарий (подслучай — свежая задача): (а) все тесты зелёные — у
    записи строка `голова <sha40>; база <sha40>; ключ <ключ>; мандат
    нет`; (б) ветка удаляет два файла тестов, на оба — мандат
    Оператора, плюс элемент мандата на третий путь без находок —
    отпечаток равен sha256 строки двух покрывших путей, отсортированных
    и соединённых переводом строки. В обоих: строка идёт сразу после
    строки чисел, голова — голова кодовой ветки, база — merge-base с
    `origin/main` (`diff_base`), ключ — `suite_result_key` по дереву
    головы с её рабочей копией.

    Ловит мутацию: строка доказательства не пишется или стоит не после
    строки чисел; голова и база перепутаны; ключ по коммиту, а не по
    дереву, либо с `base=True`; отпечаток без сортировки, по всем
    элементам мандата (включая непокрывший) или через запятую; при
    отсутствии покрывших элементов — пустой отпечаток вместо «нет».
    """
    for label in ("без мандата", "мандат"):
        case = f"{label}, зерно {box.seed}: "
        keep_rel = box.py_rel()
        tests = {keep_rel: [box.py_name() for _ in range(2)]}
        covered = []
        if label == "мандат":
            covered = [box.py_rel() for _ in range(2)]
            for rel in covered:
                tests[rel] = [box.py_name()]
        project = box.junit_project(tests)
        extra = box.py_rel()
        elements = covered + [extra] if covered else None
        t = box.verifying_task(project, {rel: None for rel in covered},
                               mandate=elements)
        detail = t.passed[-1]
        index, fields = box.proof(detail)
        assert fields is not None, case + box.note(f"нет строки доказательства:\n{detail}")
        lines = detail.splitlines()
        counts = [i for i, line in enumerate(lines) if COUNTS_MARK in line]
        assert counts, case + box.note(detail)
        assert index == counts[0] + 1, case + box.note(detail)
        head, base, key, fingerprint = fields
        assert head == box.head(t), case + box.note(detail)
        assert base == box.merge_base(
            t, f"refs/remotes/origin/{config.MAIN_BRANCH}"), case + box.note(detail)
        assert key == box.expected_key(t), case + box.note(detail)
        if covered:
            wanted = hashlib.sha256(
                "\n".join(sorted(covered)).encode("utf-8")).hexdigest()
        else:
            wanted = MANDATE_NONE
        assert fingerprint == wanted, case + box.note(detail)


def test_ac1_key_none_on_in_dev_is_prepare_refusal_without_record(box):
    """Ключ компонента не снят на выходе из `in_dev` — отказ подготовки гейта исходов, записи пройденного гейта нет.

    Сценарий: проект `junit-xml`, все тесты зелёные; git отказывает
    `ls-tree` файлов блокировки в кадрах гейта (суммы блокировки не
    сняты — ключ `None`). `advance` из `in_dev`: отказ «переход
    отклонён: гейт неослабления по исходам — подготовка», записи «гейт
    неослабления по исходам пройден» нет, задача в `in_dev`.

    Ловит мутацию: ключ `None` пишется в строку записи («ключ None») и
    гейт пройден; сбой ключа проглочен — запись без строки
    доказательства, переход в `verifying`.
    """
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.task(project)
    locks = set(acceptance.LOCK_FILE_NAMES)
    box.git_fail = lambda args: "ls-tree" in args and any(
        a.rsplit("/", 1)[-1] in locks for a in args)
    rows, output = box.developer_advance(t)
    box.git_fail = None
    assert box.details(rows, PREPARE_ACTION), box.explain(rows, output)
    assert box.details(rows, PASSED_ACTION) == [], box.explain(rows, output)
    assert box.state(t) == "in_dev", box.explain(rows, output)


# ---------------------------------------------------------------- Ac2MergeFindingTest


def test_ac2_finding_without_mandate_escalates_merge(box):
    """Находка без мандата на гейте мержа — `escalated`, действие журнала «merge отклонён: гейт неослабления по исходам» с находкой, push нет.

    Сценарий (подслучай — свежая задача сразу на `merge_gate`, записи
    пройденного гейта нет): (а) тест базы на ветке красен все три
    прогона («сломан правкой»); (б) тест базы исчез из отчёта ветки
    (текст файла не менялся — гейт по тексту его не видит). После
    `approve`: задача в `escalated`, среди новых записей — действие
    «merge отклонён: гейт неослабления по исходам», идентификатор
    теста — в тексте записей, `origin/main` проекта не сдвинулся.

    Ловит мутацию: гейт исходов не включён в окно мержа — задача в
    `done`; «сломан правкой» пишется своим действием («… — сломан
    правкой») либо возвращает задачу в `in_dev`; находка исчезновения
    не эскалирует.
    """
    for label in ("сломан", "исчез"):
        case = f"{label}, зерно {box.seed}: "
        rel, name = box.py_rel(), box.py_name()
        project = box.junit_project({rel: [name, box.py_name()]})
        head = ["failed"] if label == "сломан" else ["missing"]
        box.cases[(rel, name)] = {"base": ["passed"], "head": head}
        t = box.direct_task(project, "merge_gate")
        main = box.origin_main(t)
        rows, output = box.approve(t)
        cid = box.case_id(project, rel, name)
        assert box.state(t) == "escalated", case + box.explain(rows, output)
        assert box.details(rows, MERGE_OUTCOME_ACTION), case + box.explain(rows, output)
        assert any(cid in x for x in box.texts(rows)), case + box.explain(rows, output)
        assert box.origin_main(t) == main, case + box.explain(rows, output)


def test_ac2_merge_refusal_action_is_operator_class_key(box):
    """Действие «merge отклонён: гейт неослабления по исходам» — ключ словаря `REFUSAL_CLASSES` со значением «чинит Оператор».

    Ловит мутацию: ключ не добавлен в словарь — `refusal_class`
    отдаёт «чинит Оператор» по умолчанию, но ключа в словаре нет;
    действие отнесено к «чинит роль».
    """
    assert MERGE_OUTCOME_ACTION in refusal_classes.REFUSAL_CLASSES
    assert refusal_classes.REFUSAL_CLASSES[MERGE_OUTCOME_ACTION] == OPERATOR_FIXES
    assert refusal_classes.refusal_class(MERGE_OUTCOME_ACTION) == OPERATOR_FIXES


# ---------------------------------------------------------------- Ac3MergePrepareTest


def test_ac3_prepare_failures_keep_merge_gate_without_push(box):
    """Сбой подготовки гейта исходов на мерже — задача на `merge_gate`, push нет, подсказка «повтори artel.py approve», мерж дальше не идёт.

    Сценарий (подслучай — свежая задача сразу на `merge_gate`, тест базы
    на ветке красен): (а) выписка головы отказана git в кадрах гейта;
    (б) полный набор головы не пишет отчёт («не начат»/«неизвестно»);
    (в) полный набор базы превышает предел; (г) полный набор бросает
    исключение; (д) фетч `refs/heads/main` отказан — «fresh» без sha
    main; (е) `ls-tree` файлов блокировки отказан в кадрах гейта — ключ
    компонента `None`. В каждом: задача на `merge_gate`, `origin/main`
    не сдвинулся, подсказка «повтори artel.py approve» — в выводе или
    журнале, CI ветки не опрашивался (окно до CI не дошло); в (д) и (е)
    полный набор не звался вовсе, записи «гейт исходов: доказан» нет.

    Ловит мутацию: сбой подготовки пропускает гейт — мерж идёт к CI и
    в `done`; сбой проглочен как отсутствие находок — `done`; «fresh»
    без sha main берёт базой `diff_base` — полный набор прогнан и мерж
    дошёл до CI; ключ `None` сравнивается как значение — прогон и
    проход.
    """
    locks = set(acceptance.LOCK_FILE_NAMES)

    def checkout_head(t):
        head = box.head(t)
        return lambda args: (("worktree" in args and "add" in args)
                             or "clone" in args or "archive" in args) and any(
            head in a or t.branch in a for a in args)

    def full(side):
        return lambda run: run["full"] and not run["plank"] and run["side"] == side

    cases = ("выписка", "не начат", "таймаут", "исключение", "без sha main",
             "ключ None")
    for label in cases:
        case = f"{label}, зерно {box.seed}: "
        project, _rel, _name = box.broken_case()
        t = box.direct_task(project, "merge_gate")
        main = box.origin_main(t)
        if label == "выписка":
            box.git_fail = checkout_head(t)
        elif label == "ключ None":
            box.git_fail = lambda args: "ls-tree" in args and any(
                a.rsplit("/", 1)[-1] in locks for a in args)
        box.no_report_when = full("head") if label == "не начат" else None
        box.timeout_when = full("base") if label == "таймаут" else None
        box.suite_error = label == "исключение"
        box.fetch_fail = label == "без sha main"
        rows, output = box.approve(t)
        box.git_fail = box.no_report_when = box.timeout_when = None
        box.suite_error = box.fetch_fail = False
        context = box.explain(rows, output) + f"\nCI: {box.ci_calls}"
        assert box.state(t) == "merge_gate", case + context
        assert box.origin_main(t) == main, case + context
        assert APPROVE_HINT in output or any(
            APPROVE_HINT in x for x in box.texts(rows)), case + context
        assert box.ci_calls == [], case + context
        if label in ("без sha main", "ключ None"):
            assert box.suite_calls == [], case + context
            assert not any("доказан" in x for x in box.texts(rows)), case + context


# ---------------------------------------------------------------- Ac4ProofTest


def test_ac4_same_quadruple_proves_without_run(box):
    """Запись пройденного гейта с той же головой, базой, ключом и отпечатком — на мерже прогона нет, запись «гейт исходов: доказан для головы <sha7> и базы <sha7>».

    Сценарий (подслучай — свежая задача): задача проходит настоящий
    выход из `in_dev` (гейт исходов пройден) — (а) без находок; (б) с
    находками исчезнувших тестов удалённого файла под мандатом
    Оператора. Задача на `merge_gate`, `approve`: полный набор не
    звался ни разу, раннер полного набора не запускался, среди новых
    записей — «гейт исходов: доказан для головы <sha7 головы> и базы
    <sha7 merge-base>», задача в `done`.

    Ловит мутацию: доказательство не ищется — полный набор прогнан на
    мерже; доказательство при находках под мандатом не сверяет
    отпечаток текущего мандата верно — прогон; текст записи с полным
    sha или без базы — записи нет.
    """
    for label in ("без находок", "мандат"):
        case = f"{label}, зерно {box.seed}: "
        gone = box.py_rel()
        tests = {box.py_rel(): [box.py_name()]}
        if label == "мандат":
            tests[gone] = [box.py_name()]
        project = box.junit_project(tests)
        t = box.verifying_task(
            project, {gone: None} if label == "мандат" else None,
            mandate=[gone] if label == "мандат" else None)
        head = box.head(t)
        base = box.merge_base(t, box.origin_main(t))
        box.to_merge_gate(t)
        rows, output = box.approve(t)
        context = box.explain(rows, output)
        assert box.suite_calls == [], case + context
        assert box.full_runs() == [], case + context
        wanted = PROVEN.format(head=head[:7], base=base[:7])
        assert any(wanted in x for x in box.texts(rows)), (
            case + context + f"\nожидалось: {wanted}")
        assert box.state(t) == "done", case + context


# ---------------------------------------------------------------- Ac5ProofMismatchTest


def test_ac5_other_base_key_or_mandate_runs_gate(box):
    """Запись, отличающаяся от текущей четвёрки базой, ключом компонента или отпечатком мандата, доказательством не служит — на мерже прогон.

    Сценарий (подслучай — свежая задача): настоящий выход из `in_dev`
    (для подслучая мандата — с удалённым файлом тестов под мандатом
    Оператора); в записи пройденного гейта в журнале заменено одно
    поле строки доказательства: (а) база — случайный sha; (б) ключ —
    случайный; (в) отпечаток мандата — sha256 набора, где к покрывшему
    элементу добавлен отозванный (текущий мандат его не несёт).
    `approve`: полный набор прогнан на мерже на обеих сторонах.

    Ловит мутацию: доказательство сверяет только голову — прогона нет
    во всех подслучаях; не сверяет ключ — (б) без прогона; отпечаток
    записи не сравнивается с отпечатком текущего мандата — (в) без
    прогона.
    """
    for field in ("база", "ключ", "мандат"):
        case = f"{field}, зерно {box.seed}: "
        keep, gone = box.py_rel(), box.py_rel()
        project = box.junit_project({keep: [box.py_name()],
                                     gone: [box.py_name()]})
        t = box.verifying_task(project, {gone: None}, mandate=[gone])
        revoked = box.py_rel()

        def edit(detail, field=field, gone=gone, revoked=revoked):
            out = []
            for line in detail.splitlines():
                m = PROOF_LINE.match(line.strip())
                if m:
                    head, base, key, mark = m.groups()
                    if field == "база":
                        base = box.hexword(40)
                    elif field == "ключ":
                        key = box.hexword(64)
                    else:
                        mark = hashlib.sha256("\n".join(sorted(
                            [gone, revoked])).encode("utf-8")).hexdigest()
                    line = f"голова {head}; база {base}; ключ {key}; мандат {mark}"
                out.append(line)
            return "\n".join(out)
        box.rewrite_passed(t, edit)
        box.to_merge_gate(t)
        rows, output = box.approve(t)
        assert box.sides() == ["base", "head"], case + box.explain(rows, output)


# ---------------------------------------------------------------- Ac6LegacyRecordTest


def test_ac6_record_without_proof_line_runs_gate(box):
    """Прежняя запись пройденного гейта без строки «голова …; база …» доказательством не служит — на мерже прогон.

    Сценарий: настоящий выход из `in_dev`; из записи пройденного гейта
    в журнале убрана строка доказательства (остаётся прежняя форма —
    строка чисел). `approve`: полный набор прогнан на мерже на обеих
    сторонах, записи «гейт исходов: доказан» с этой головой до прогона
    нет.

    Ловит мутацию: запись без строки доказательства принимается как
    доказательство (любая запись пройденного гейта) — прогона нет.
    """
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.verifying_task(project)
    box.rewrite_passed(t, lambda detail: "\n".join(
        line for line in detail.splitlines()
        if not PROOF_LINE.match(line.strip())))
    box.to_merge_gate(t)
    rows, output = box.approve(t)
    assert box.sides() == ["base", "head"], box.explain(rows, output)


# ---------------------------------------------------------------- Ac7MergeBaseTest


def test_ac7_base_is_merge_base_with_fetched_main_not_diff_base(box):
    """База гейта на мерже — merge-base головы с зафетченным sha main, не `diff_base`: голова, влившая main, даёт базой этот main.

    Сценарий: задача сразу на `merge_gate`; в main проекта (и его
    `origin`) — новый коммит с новым файлом тестов, кодовая ветка его
    влила. Ссылка отслеживания `refs/remotes/origin/main` клона
    возвращена на прежний main, а `remote.origin.fetch` снят — фетч
    её не обновляет, и `diff_base` ветки — прежний main (предусловие).
    `approve`: полный набор базы прогнан на дереве, где новый файл
    тестов есть; задача в `done`.

    Ловит мутацию: база на мерже — повторный `diff_base` — выписка
    базы на прежнем main, нового файла в её дереве нет.
    """
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.direct_task(project, "merge_gate")
    clone = str(project.clone)
    old_main = box.rev(t, config.MAIN_BRANCH)
    new_rel = box.py_rel()
    box.commit_project(project.clone, {new_rel: py_source([box.py_name()])})
    new_main = box.rev(t, config.MAIN_BRANCH)
    box.git("-C", str(t.wt), "merge", "-q", "--no-edit", config.MAIN_BRANCH)
    box.git("-C", clone, "update-ref",
            f"refs/remotes/origin/{config.MAIN_BRANCH}", old_main)
    box.git("-C", clone, "config", "--unset-all", "remote.origin.fetch")
    assert box.merge_base(
        t, f"refs/remotes/origin/{config.MAIN_BRANCH}") == old_main, box.note(
            "предусловие: diff_base ветки — прежний main")
    assert box.merge_base(t, new_main) == new_main, box.note(
        "предусловие: голова влила новый main")
    box.watch = (new_rel,)
    rows, output = box.approve(t)
    context = box.explain(rows, output) + f"\nвызовы: {box.suite_calls}"
    base_calls = [c for c in box.suite_calls if c["side"] == "base"]
    assert base_calls, context
    assert all(c["seen"][new_rel] for c in base_calls), context
    assert box.state(t) == "done", context


def test_ac7_doc_only_lag_runs_gate_with_merge_base(box):
    """Отставание ветки только на документные коммиты main — штатный путь: гейт исполняется, база — merge-base головы, документного коммита в её дереве нет.

    Сценарий: задача сразу на `merge_gate`; после ветвления в main
    проекта — коммит одного документного файла `docs/<слово>.md`.
    `approve`: сверка свежести записала «свежесть: … документных
    коммитов main без подтяжки» (предусловие пути); полный набор
    прогнан на обеих сторонах, в дереве базы документного файла нет;
    отказа подготовки нет, задача в `done`.

    Ловит мутацию: базой служит сам зафетченный sha main — в дереве
    базы есть документный файл; документное отставание считается
    сбоем подготовки — задача остаётся на `merge_gate`.
    """
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.direct_task(project, "merge_gate")
    doc = f"docs/{box.word()}.md"
    box.commit_project(project.clone, {doc: f"заметка {box.seed}\n"})
    box.watch = (doc,)
    rows, output = box.approve(t)
    context = box.explain(rows, output) + f"\nвызовы: {box.suite_calls}"
    assert any(r["action"].startswith(FRESHNESS_DOCS) for r in rows), context
    assert box.sides() == ["base", "head"], context
    base_calls = [c for c in box.suite_calls if c["side"] == "base"]
    assert not any(c["seen"][doc] for c in base_calls), context
    assert box.state(t) == "done", context


def test_ac7_gate_after_fresh_and_before_acceptance_locks(box):
    """Гейт исходов идёт после «fresh» и до сверки лока приёмочных тестов.

    Сценарий (подслучай — свежая задача после настоящего выхода из
    `in_dev`): (а) лок планки нарушен — файл планки в ссылке документов
    правлен после лока; `approve`: запись «гейт исходов: доказан …» для
    головы есть, мерж остановлен (задача не в `done`). (б) В main
    проекта — коммит кода (не документ): сверка свежести подтягивает
    main в ветку, пушит и уходит ждать CI; на следующем входе — «fresh».
    Записи «доказан» для прежней головы нет; каждый прогон полного
    набора на голове — на дереве с файлом из main; задача в `done`.

    Ловит мутацию: гейт после `_acceptance_locks_refuse` — в (а)
    записи «доказан» нет; гейт до `_sync_main_or_wait` — в (б)
    доказательство для прежней головы записано до подтяжки.
    """
    case = f"лок, зерно {box.seed}: "
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.verifying_task(project)
    head = box.head(t)
    base = box.merge_base(t, box.origin_main(t))
    name, body = box.last_plank
    t.plank.mkdir(parents=True, exist_ok=True)
    (t.plank / name).write_text(
        body + f"\n# правка после лока {box.seed}\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        checkpoint.commit_step_artifacts(box.conn, t.id, "developer")
    box.to_merge_gate(t)
    rows, output = box.approve(t)
    # Предусловие: мерж остановлен сверкой лока.
    assert box.state(t) != "done", case + box.explain(rows, output)
    wanted = PROVEN.format(head=head[:7], base=base[:7])
    assert any(wanted in x for x in box.texts(rows)), case + box.explain(rows, output)
    case = f"подтяжка, зерно {box.seed}: "
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.verifying_task(project)
    old_head = box.head(t)
    lib = f"lib_{box.word()}.py"
    box.commit_project(project.clone, {lib: f"LIB = {box.seed}\n"})
    box.to_merge_gate(t)
    box.watch = (lib,)
    rows, output = box.approve(t)
    context = box.explain(rows, output) + f"\nвызовы: {box.suite_calls}"
    # Предусловие: сверка свежести подтянула main в ветку.
    assert PULLED in output, case + context
    assert not any(f"доказан для головы {old_head[:7]}" in x
                   for x in box.texts(rows)), case + context
    head_calls = [c for c in box.suite_calls if c["side"] == "head"]
    assert head_calls, case + context
    assert all(c["seen"][lib] for c in head_calls), case + context
    assert box.state(t) == "done", case + context


def test_ac7_canary_from_db_and_in_dev_base_is_diff_base(box):
    """Признак канарейки на мерже — из строки задачи: у канареечной задачи гейт исходов на мерже не исполняется; на выходе из `in_dev` база записи — `diff_base`.

    Сценарий (подслучай): (а) канареечная задача проекта в границе
    сразу на `merge_gate`, тест базы на ветке красен — `approve`:
    полный набор не звался, записей гейта исходов нет, задача в
    `done`; (б) задача после настоящего выхода из `in_dev` — база
    строки доказательства равна merge-base ветки с
    `refs/remotes/origin/main` и не равна голове.

    Ловит мутацию: признак канарейки не читается на мерже — у
    канарейки полный набор прогнан и мерж эскалирован; база выхода из
    `in_dev` — голова или sha зафетченного main вместо `diff_base`.
    """
    case = f"канарейка, зерно {box.seed}: "
    project, _rel, _name = box.broken_case()
    t = box.direct_task(project, "merge_gate", canary=True)
    rows, output = box.approve(t)
    assert box.suite_calls == [], case + box.explain(rows, output)
    assert box.gate_rows(rows) == [], case + box.explain(rows, output)
    assert box.state(t) == "done", case + box.explain(rows, output)
    case = f"in_dev, зерно {box.seed}: "
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.verifying_task(project)
    _index, fields = box.proof(t.passed[-1])
    assert fields is not None, case + box.note(t.passed[-1])
    assert fields[1] == box.merge_base(
        t, f"refs/remotes/origin/{config.MAIN_BRANCH}"), case + box.note(t.passed[-1])
    assert fields[1] != box.head(t), case + box.note(t.passed[-1])


# ---------------------------------------------------------------- Ac8ReviewLinesTest


def test_ac8_review_section_carries_outcome_gate_lines_for_head(box):
    """Пакет ревьювера при записи пройденного гейта с текущей головой — в разделе «Изменённые утверждения тестов» числа базы и ветки, покрытые находки с ANSWER, «нестабилен и на базе», перепрогоны.

    Сценарий: проект `junit-xml`; на базе `nb` тестов (из `random`), из
    них `m` в файле, который ветка удаляет под мандатом Оператора;
    ветка добавляет `k` новых зелёных; один тест трижды красен на ветке
    и красен на одном перепрогоне базы. Настоящий выход из `in_dev`,
    затем `review.review_package`. Раздел есть; в нём числа `nb` и
    число тестов ветки, идентификатор каждой покрытой находки и имя
    ANSWER из записи, строка «нестабилен и на базе» с идентификатором
    нестабильного теста, слово «перепрогон».

    Ловит мутацию: раздел строится только по гейту по тексту — строк
    гейта исходов нет; запись ищется не по текущей голове — строки
    «не исполнялся» вместо чисел; покрытые находки без имени ANSWER.
    """
    nb = box.rng.randint(11, 19)
    m = box.rng.randint(2, 3)
    k = box.rng.randint(21, 29)
    covered = box.py_rel()
    gone = [box.py_name() for _ in range(m)]
    flaky_rel, flaky = box.py_rel(), box.py_name()
    rest = [box.py_name() for _ in range(nb - m - 1)]
    project = box.junit_project({covered: gone, flaky_rel: [flaky],
                                 box.py_rel(): rest})
    box.cases[(flaky_rel, flaky)] = {"base": ["passed", "failed", "passed"],
                                     "head": ["failed"]}
    added = [box.py_name() for _ in range(k)]
    t = box.verifying_task(project, {covered: None,
                                     box.py_rel(): py_source(added)},
                           mandate=[covered])
    detail = t.passed[-1]
    sources = sorted({line.rsplit(COVERED_BY, 1)[1].strip()
                      for line in detail.splitlines() if COVERED_BY in line})
    assert sources, box.note(detail)
    text = box.package(t)
    part = box.section(text)
    assert part is not None, box.note(text[-3000:])
    context = box.note(f"раздел:\n{part}\nзапись:\n{detail}")
    nh = nb - m + k
    assert {nb, nh} <= box.numbers(part), context
    for name in gone:
        assert box.case_id(project, covered, name) in part, context
    for source in sources:
        assert source in part, context
    flaky_id = box.case_id(project, flaky_rel, flaky)
    assert any(FLAKY_ON_BASE in line and flaky_id in line
               for line in part.splitlines()), context
    assert "перепрогон" in part.lower(), context


# ---------------------------------------------------------------- Ac9ReviewNotRunTest


def test_ac9_no_record_for_current_head_says_not_run(box):
    """Пакет ревьювера без записи пройденного гейта с текущей головой — строка «гейт исходов для головы <sha7> не исполнялся».

    Сценарий (подслучай): (а) задача проекта в границе заведена сразу
    в `review`, гейт исходов не исполнялся ни разу; (б) задача прошла
    выход из `in_dev`, затем в кодовую ветку закоммичена ещё правка —
    запись есть, но для прежней головы. В обоих раздел «Изменённые
    утверждения тестов» несёт строку для sha7 текущей головы.

    Ловит мутацию: запись берётся последняя по журналу без сверки
    головы — в (б) строки прежней записи вместо «не исполнялся»; при
    отсутствии записи раздела нет либо нет строки.
    """
    case = f"без записи, зерно {box.seed}: "
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.direct_task(project, "review")
    text = box.package(t)
    assert NOT_RUN.format(head=box.head(t)[:7]) in (box.section(text) or ""), (
        case + box.note(text[-3000:]))
    case = f"другая голова, зерно {box.seed}: "
    project = box.junit_project({box.py_rel(): [box.py_name()]})
    t = box.verifying_task(project)
    box.commit_code(t, {})
    text = box.package(t)
    assert NOT_RUN.format(head=box.head(t)[:7]) in (box.section(text) or ""), (
        case + box.note(text[-3000:]))


# ---------------------------------------------------------------- Ac10NoPythonSectionTest


def test_ac10_component_without_python_has_section_except_canary(box):
    """У компонента без Python (строк гейта по тексту нет) раздел «Изменённые утверждения тестов» есть у обычной задачи и, по прежнему условию, отсутствует у канареечной.

    Сценарий (подслучай): проект `pult-vitest`, задача заведена в
    `review` — (а) не канареечная: в пакете ревьювера есть заголовок
    раздела; (б) канареечная: заголовка раздела нет.

    Ловит мутацию: раздел по-прежнему появляется только при строках
    гейта по тексту — в (а) раздела нет; канареечная задача получает
    раздел — в (б) заголовок есть.
    """
    for canary in (False, True):
        case = f"{canary}, зерно {box.seed}: "
        project = box.vitest_project({box.js_rel(): [box.js_name()]})
        t = box.direct_task(project, "review", canary=canary)
        text = box.package(t)
        if canary:
            assert box.section(text) is None, case + box.note(text[-3000:])
        else:
            assert box.section(text) is not None, case + box.note(text[-3000:])


# ---------------------------------------------------------------- Ac11TwoSidedErrorNameTest


def test_ac11_only_check_failure_is_failure_on_check(two_sided_box):
    """Двусторонний прогон профиля в границе: `failed` с именем ошибки вне списка компонента, `error` и таймаут — «упал не на проверке» с видом; провал проверки — доказательство.

    Сценарий (подслучай — свежая задача, проект `junit-xml` со списком
    «провал проверки» `AssertionError`, сторона — из `random`): одна
    сторона падает проверкой (`assert`), другая — (а) `failed` с
    `ValueError`; (б) `error` `TypeError`; (в) таймаут прогона; (г)
    контроль — тоже проверкой. В (а)–(в): отказ прогона есть, исход
    этой стороны — не «утверждение»; в (а) и (б) он называет имя
    ошибки. В (г): отказов нет, обе стороны — «утверждение».

    Ловит мутацию: признак проверки — любой `outcome == failed` (как
    до задачи) — в (а) сторона «утверждение», отказа нет; классификатор
    не зовётся вовсе — в (г) отказ.
    """
    labels = {"base": two_sided.NEW_ON_BASE, "head": two_sided.OLD_ON_BRANCH}
    for case in ("failed_other", "error", "таймаут", "контроль"):
        tag = f"{case}, зерно {two_sided_box.seed}: "
        rel, name = two_sided_box.py_rel(), two_sided_box.py_name()
        project = two_sided_box.junit_project({rel: [name]})
        side = two_sided_box.rng.choice(("base", "head"))
        other = "head" if side == "base" else "base"
        kind = {"failed_other": "failed_other", "error": "error"}.get(case, "failed")
        result, address = two_sided_box.two_sided(
            project, rel, name, {side: kind, other: "failed"},
            timeout_side=side if case == "таймаут" else None)
        text = two_sided_box.side_text(result, address, labels[side])
        context = two_sided_box.note(f"{case} на «{side}»: {result}")
        if case == "контроль":
            assert result.refusals == [], tag + context
            for label in labels.values():
                assert two_sided_box.side_text(result, address, label) == \
                    two_sided.SIDE_ASSERTION, tag + context
            continue
        assert result.refusals, tag + context
        assert text != two_sided.SIDE_ASSERTION, tag + context
        if case == "failed_other":
            assert "ValueError" in text, tag + context
        if case == "error":
            assert "TypeError" in text, tag + context


# ---------------------------------------------------------------- Ac12TwoSidedRetryTest


def test_ac12_passed_with_retry_is_side_failure_retry(two_sided_box):
    """Двусторонний прогон профиля в границе: `passed` с повтором на любой стороне — сбой стороны с видом «повтор», не доказательство и не «зелёная».

    Сценарий (подслучай — сторона): проект `pult-vitest`; на одной
    стороне запись `pass` с `retry_count: 1`, на другой — провал
    проверки. Отказ прогона есть; исход стороны с повтором называет
    «повтор» и не равен «зелёная».

    Ловит мутацию: `passed` с повтором считается зелёным — исход
    стороны «зелёная», вида «повтор» нет.
    """
    labels = {"base": two_sided.NEW_ON_BASE, "head": two_sided.OLD_ON_BRANCH}
    for side in ("base", "head"):
        tag = f"{side}, зерно {two_sided_box.seed}: "
        rel, name = two_sided_box.js_rel(), two_sided_box.js_name()
        project = two_sided_box.vitest_project({rel: [name]})
        other = "head" if side == "base" else "base"
        result, address = two_sided_box.two_sided(project, rel, name,
                                                  {side: "retried", other: "failed"})
        text = two_sided_box.side_text(result, address, labels[side])
        context = two_sided_box.note(f"повтор на «{side}»: {result}")
        assert result.refusals, tag + context
        assert "повтор" in text, tag + context
        assert text != two_sided.SIDE_GREEN, tag + context


# ---------------------------------------------------------------- Ac13RetriedBaseRerunTest


def test_ac13_retried_on_base_rerun_is_red_base(box):
    """Запись `passed` с повтором на перепрогоне базы — красная база: «нестабилен и на базе», находки нет.

    Сценарий: проект `pult-vitest`; тест базы зелёный в полном
    прогоне, на ветке красен все три прогона, на первом перепрогоне
    базы — `pass` с `retry_count: 1`, на втором — `pass`. Выход из
    `in_dev`: отказа гейта исходов нет, запись пройденного гейта несёт
    «нестабилен и на базе: <идентификатор>», задача в `verifying`.

    Ловит мутацию: на перепрогоне базы зелёным считается любой
    `passed` без сверки повторов — база зелёна трижды, отказ «… —
    сломан правкой».
    """
    rel, name = box.js_rel(), box.js_name()
    project = box.vitest_project({rel: [name, box.js_name()]})
    t = box.task(project)
    box.cases[(rel, name)] = {"base": ["passed", "retried", "passed"],
                              "head": ["failed"]}
    rows, output = box.developer_advance(t)
    no_gate_refusal(box, rows, output)
    cid = box.case_id(project, rel, name)
    assert any(f"{FLAKY_ON_BASE}: {cid}" in d
               for d in box.details(rows, PASSED_ACTION)), box.explain(rows, output)
    assert box.state(t) == "verifying", box.explain(rows, output)


# ---------------------------------------------------------------- Ac14OutOfBoundsTest


def test_ac14_test_profile_and_multi_component_keep_prior_results(two_sided_box):
    """Вне границы (запись `test_profile`, запись из нескольких компонентов) — гейт мержа, пакет ревьювера и двусторонний прогон прежние.

    Сценарий (подслучай): (а) проект `test_profile` с `report:
    junit-xml`, задача сразу на `merge_gate`, тест базы на ветке красен
    — `approve`: полный набор не звался, записей гейта исходов нет,
    задача в `done`; (б) тот же вид проекта, задача в `review` без
    строк гейта по тексту — раздела «Изменённые утверждения тестов»
    нет, слов «гейт исходов» в пакете нет; (в) тот же вид проекта,
    двусторонний прогон: одна сторона `failed` с `ValueError`, другая —
    провал проверки — прежнее правило: отказов нет; (г) запись из двух
    компонентов `junit-xml`: `approve` и пакет ревьювера не несут
    записей и строк гейта исходов, полный набор на мерже не звался.

    Ловит мутацию: граница по `reported(profile)` без
    `from_components` — у `test_profile` гейт исходов на мерже прогнан и
    эскалирует, раздел пакета появился со строкой «не исполнялся»,
    двусторонний прогон отказывает по имени ошибки.
    """
    case = f"мерж test_profile, зерно {two_sided_box.seed}: "
    project, _rel, _name = two_sided_box.broken_case("test_profile")
    t = two_sided_box.direct_task(project, "merge_gate")
    rows, output = two_sided_box.approve(t)
    assert two_sided_box.suite_calls == [], case + two_sided_box.explain(rows, output)
    assert two_sided_box.gate_rows(rows) == [], case + two_sided_box.explain(rows, output)
    assert two_sided_box.state(t) == "done", case + two_sided_box.explain(rows, output)
    case = f"пакет test_profile, зерно {two_sided_box.seed}: "
    project = two_sided_box.junit_project({two_sided_box.py_rel(): [two_sided_box.py_name()]},
                                test_profile=True)
    t = two_sided_box.direct_task(project, "review")
    text = two_sided_box.package(t)
    assert two_sided_box.section(text) is None, case + two_sided_box.note(text[-3000:])
    assert "гейт исходов" not in text, case + two_sided_box.note(text[-3000:])
    case = f"двусторонний test_profile, зерно {two_sided_box.seed}: "
    rel, name = two_sided_box.py_rel(), two_sided_box.py_name()
    project = two_sided_box.junit_project({rel: [name]}, test_profile=True)
    side = two_sided_box.rng.choice(("base", "head"))
    other = "head" if side == "base" else "base"
    result, _address = two_sided_box.two_sided(project, rel, name,
                                     {side: "failed_other", other: "failed"})
    assert result.refusals == [], case + two_sided_box.note(str(result))
    case = f"несколько компонентов, зерно {two_sided_box.seed}: "
    project = two_sided_box.multi_project()
    t = two_sided_box.direct_task(project, "merge_gate")
    rows, output = two_sided_box.approve(t)
    assert two_sided_box.suite_calls == [], case + two_sided_box.explain(rows, output)
    assert two_sided_box.gate_rows(rows) == [], case + two_sided_box.explain(rows, output)
    store.set_state(two_sided_box.conn, t.id, "review", "operator",
                    expected_state=two_sided_box.state(t), detail="сценарий")
    text = two_sided_box.package(t)
    assert "гейт исходов" not in text, case + two_sided_box.note(text[-3000:])
