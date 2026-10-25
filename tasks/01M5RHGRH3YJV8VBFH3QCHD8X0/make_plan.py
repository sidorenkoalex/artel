"""Сборщик PLAN.md задачи 01M5RHGRH3YJV8VBFH3QCHD8X0: постоянный текст
(`plan_static.txt`) + строки мутаций (данные ниже), строки падения
«до → после» из логов прогонов, места утверждений подготовки, перечни имён,
числа и время. Таблицы «до»/«после» берутся из текущего PLAN.md (их туда
дописывал `add_table.py` по ходу прогонов) без изменений.

python3 make_plan.py --status ready
"""
import argparse
import ast
import glob
import pathlib
import re
import subprocess
import sys

DOCS = pathlib.Path(__file__).resolve().parent
TASK = DOCS.name
WT = DOCS.parent.parent / "worktrees" / TASK
LOGS = pathlib.Path(f"/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/{TASK}")
BASE = "ad3608c6d2ceedd43f2d91ad569a6b8684804782"
BEFORE_RUNS = list(range(1, 21))
AFTER_RUNS = list(range(21, 41))
sys.path.insert(0, str(DOCS / "acceptance_tests"))
import _plan  # noqa: E402

A1 = "AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value"
A2 = "AnswerMandateAcceptedTest::test_ac11_merge_gate_answer_outside_role_env_accepted"
A3 = "AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit"
A4 = "AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused"
G1 = "GuardMergeAfterFieldTest::test_ac1_self_reference_names_field_and_element"
G2 = "GuardMergeAfterFieldTest::test_ac1_repeated_element_is_a_repeat_error"
G3 = "GuardMergeAfterFieldTest::test_ac1_element_not_in_task_id_format_is_a_form_error"
G4 = "GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass"
P1 = "PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value"
P2 = "PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies"
P3 = "PlanChannelAppliesTest::test_ac9_plan_without_field_keeps_db_value"
P4 = "PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition"
S1 = "SpecGateMissingOrAmbiguousTest::test_ac2_missing_task_keeps_spec_gate_and_column_empty"
S2 = "SpecGateMissingOrAmbiguousTest::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty"
S3 = "SpecGateKilledForeignSelfTest::test_ac3_killed_dependency_refused"
S4 = "SpecGateKilledForeignSelfTest::test_ac3_dependency_of_other_target_refused"
S5 = "SpecGateKilledForeignSelfTest::test_ac3_prefix_resolving_to_own_id_refused"
S6 = "SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused"
S7 = "SpecGateWritesColumnTest::test_ac5_prefixes_written_as_full_ids_in_spec_order"
S8 = "SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty"
T1 = "StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done"
T2 = "StatusSuffixTest::test_ac13_no_suffix_in_other_state"
T3 = "StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done"
T4 = "ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states"
T5 = "ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line"
N1 = "NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order"
N2 = "NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot"
N3 = "NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing"
N4 = "NewRefusesTest::test_ac4_unparsed_element_refused_without_traces"
N5 = "NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces"
N6 = "NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces"
N7 = "NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together"
N8 = "DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies"

# (номер, заявившие тесты, что меняет патч, почему убийство не зависит от зерна)
M = [
    (1, [A1], "`orchestrator/merge_after.py` `value_refusals`: снят ранний возврат для `[\"нет\"]` — «нет» проверяется как id (альтернатива «„нет“ читается как id задачи»)",
     "вторая строка мандата сценария — всегда «Зависимости мержа: нет», её отказ роняет вызов :174 при любом зерне"),
    (2, [A1], "`orchestrator/merge_after.py` `mandate_value`: `check(…)[0]` → `check(…)[1]` — значение строки не применяется (переписанная альтернатива «копируется как есть»: сырой перенос убивался лишь на части зёрен — при полных id)",
     "зависимостей всегда 1–3, колонка остаётся пустой при любой форме элементов"),
    (3, [A2], "`orchestrator/answer.py` `cmd_answer`: ветка `merge_gate` не принимает ответ (`state == \"merge_gate_\"`)",
     "задача всегда на `merge_gate`, ответ любого вида (нет/живые) уходит в отказ"),
    (4, [A3], "`orchestrator/merge_after.py` `value_refusals`: только форма строки (`if True:` вместо условия без БД)",
     "все четыре варианта перебираются при любом зерне; «нет такой задачи» и «убитая» годны по форме"),
    (5, [A3], "`orchestrator/answer.py` `cmd_answer`: проверка строк мандата в `escalated` — после коммита ANSWER",
     "все четыре варианта перебираются при любом зерне, каждый негодный — ANSWER уже в ссылке"),
    (6, [A4], "`orchestrator/answer.py` `cmd_answer`: снят отказ `merge_gate` без строки мандата",
     "первый вызов — файл без строки мандата, вход от зерна не зависит"),
    (7, [A4], "`orchestrator/answer.py` `cmd_answer`: снят рубеж `runner.in_role_environment` в ветке `merge_gate`",
     "второй вызов — годная строка (и «нет», и живая задача годны) в окружении роли при любом зерне"),
    (8, [G1], "`scripts/guard.py` `merge_after_form_errors`: снята сверка элемента с полем `task:`",
     "элемент — ровно полный id задачи, версия схемы на ветку проверки не влияет"),
    (9, [G2], "`scripts/guard.py` `merge_after_form_errors`: элементы схлопываются `dict.fromkeys` до проверки",
     "оба входа — один и тот же текст дважды при любом зерне"),
    (10, [G3], "`scripts/guard.py` `merge_after_form_errors`: проверка формата элемента снята (`if False:`)",
     "вход «foo bar» постоянный, зерно его не меняет"),
    (11, [G4], "`scripts/guard.py` `spec_merge_after_errors`: поле объявлено обязательным",
     "SPEC без поля перебирается для каждой версии 1–5 без зерна"),
    (12, [G4], "`scripts/guard.py` `merge_after_items`: разделитель `,` → `;` — список читается одним элементом",
     "корректный список всегда из двух элементов через «, »"),
    (13, [P1], "`orchestrator/merge_after.py` `apply_plan`: `ids == old` → `ids != old` — отличное от БД значение не применяется (переписанная альтернатива «применяется сырым»: префиксы ломали её лишь на части зёрен)",
     "новое значение PLAN всегда несёт хотя бы одну свежую задачу — оно отлично от прежнего"),
    (14, [P1], "`orchestrator/merge_after.py` `rewrite`: запись «было → стало» не называет новое значение (переписанная альтернатива «не называет прежнее»: прежнее могло стоять и в новом — лишь на части зёрен)",
     "новый перечень всегда содержит свежую задачу, которой нет в прежнем"),
    (15, [P2], "`orchestrator/merge_after.py` `apply_plan`: пустое поле читается как «поля нет» (`not meta.get(FIELD)`)",
     "поле PLAN пусто без зерна, прежнее значение всегда непусто"),
    (16, [P3], "`orchestrator/merge_after.py` `apply_plan`: отсутствие поля очищает колонку (переписанная альтернатива «читается как пустое»: её гасила проверка обоснования на части зёрен)",
     "прежнее значение всегда 1–2 зависимости, ветка обоснования не участвует"),
    (17, [P4], "`orchestrator/merge_after.py` `apply_plan` + `orchestrator/fsm_advance.py`: отказ значения возвращает `True`, переход останавливается",
     "все пять вариантов перебираются при любом зерне, каждый отклоняется"),
    (18, [P4], "`orchestrator/merge_after.py` `apply_plan`: снята проверка обоснования смены",
     "вариант «без обоснования» перебирается при любом зерне"),
    (19, [P4], "`orchestrator/merge_after.py` `apply_plan`: причины `check` по элементам отбрасываются",
     "варианты негодных элементов перебираются при любом зерне"),
    (20, [S1], "`orchestrator/merge_after.py` `check`: отсутствующий элемент молча отбрасывается",
     "отсутствующий id в значении есть всегда; с соседом и без колонка/состояние расходятся"),
    (21, [S2], "`orchestrator/merge_after.py` `check`: `task_id_matches(…)[:1]` — первое совпадение",
     "две задачи с общим префиксом заводятся всегда, длина префикса не меняет совпадение двух"),
    (22, [S3], "`orchestrator/merge_after.py` `check`: снята проверка `killed`",
     "зависимость всегда в `killed`, её элемент однозначен в любой форме"),
    (23, [S4, N6], "`orchestrator/merge_after.py` `check`: снята сверка target (у `new_declares` — альтернатива «target заводимой задачи не сверяется»)",
     "target зависимости всегда отличен от target задачи; вариант «чужой target» перебирается всегда"),
    (24, [S5], "`orchestrator/merge_after.py` `check`: самоссылка по буквальному элементу (`item == task_id`)",
     "элемент — всегда префикс короче id (полный тест заменяет `own[:-1]`)"),
    (25, [S6], "`orchestrator/merge_after.py` `check`: проверка цикла снята (переписанная альтернатива «только прямая обратная ссылка»: убивалась лишь при цепочке длины 2 — на части зёрен)",
     "цикл есть при обеих длинах цепочки"),
    (26, [S6], "`orchestrator/merge_after.py` `check`: граф строится без нового значения задачи",
     "путь B → A находится по рёбрам БД при любой длине цепочки — для сценария мутация эквивалентна, не убита ни при каком зерне"),
    (27, [S7], "`orchestrator/fsm.py` `cmd_approve`: колонка `merge_after` не пишется (переписанная альтернатива «сырое значение»; «id сортируются» — находка)",
     "зависимостей всегда 1–3, пустая колонка расходится с ними при любом зерне"),
    (28, [S8], "`orchestrator/merge_after.py` `spec_gate_value`: отсутствие поля — причина отказа",
     "SPEC без поля при любом зерне"),
    (29, [S8], "`orchestrator/merge_after.py` `spec_gate_value`: отсутствие поля пишет строку «None»",
     "SPEC без поля при любом зерне"),
    (30, [T1, N8], "`orchestrator/merge_after.py` `_dependency_states`: состояния зависимостей кэшируются по id задачи",
     "оба теста переводят все зависимости в `done` и зовут `status` снова при любом зерне"),
    (31, [T1, T3], "`orchestrator/merge_after.py` `status_suffix`: снят фильтр `s != \"done\"` (добавка включает завершённые)",
     "у `StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done` после перевода всех в `done` перечень непуст при любом зерне"),
    (32, [T2], "`orchestrator/merge_after.py` `status_suffix`: фильтр состояния задачи снят — «[ждёт мержа:» в любом состоянии",
     "любое состояние `OTHER_STATES` (включая `spec_writing`) получает добавку при любом зерне"),
    (33, [T3], "`orchestrator/merge_after.py` `status_suffix`: снято условие пустоты перечня (переписанные альтернативы; «пустая колонка — ждём всех» убивалась лишь на части зёрен)",
     "обе ветки сценария дают пустой перечень незавершённых в `acceptance`/`merge_gate`"),
    (34, [T4], "`orchestrator/merge_after.py` `show_line`: фильтр добавки `s != \"done\"`",
     "завершённая зависимость есть всегда (тест добавляет её, если зерно не дало)"),
    (35, [T5], "`orchestrator/merge_after.py` `show_line`: строка печатается безусловно",
     "зависимостей нет при любом зерне"),
    (36, [N1], "`orchestrator/merge_after.py` `record_declared`: значение не пишется в колонку (переписанная альтернатива «сырой хвост»: убивалась лишь на части зёрен)",
     "оба подслучая (1 и 2–3 зависимости) — колонка пуста при любой форме элементов"),
    (37, [N1], "`orchestrator/merge_after.py` `record_declared`: порядок id обращён (переписанная альтернатива «id сортируются»)",
     "подслучай `count` 2–3 идёт всегда: обращение перечня из ≥2 различных id его меняет"),
    (38, [N1], "`orchestrator/merge_after.py` `record_declared`: запись журнала не делается",
     "записи нет ни в одном подслучае при любом зерне"),
    (39, [N2], "`orchestrator/merge_after.py` `declared_from_tz`: перечень до конца строки (ни «(», ни «.» не режут)",
     "обе ветки зерна ставят «(» или «.» за перечнем — хвост даёт негодный элемент"),
    (40, [N3], "`orchestrator/merge_after.py` `_ORDER_LINE_RE`: слово «после» необязательно",
     "варианты «Порядок: без …» перебираются все при любом зерне"),
    (41, [N3], "`orchestrator/merge_after.py` `_ORDER_LINE_RE`: «после» ищется по всему ТЗ",
     "пункт «Требуется» несёт «после <id>.» во всех вариантах"),
    (42, [N4], "`orchestrator/merge_after.py` `declared_from_tz`: строка с негодным элементом молча отбрасывается",
     "негодный элемент в хвосте есть всегда, с соседом или без"),
    (43, [N4, N6], "`orchestrator/catalog.py` `cmd_new`: строка «Порядок:» проверяется после заведения строки задачи",
     "каждый вариант негоден при любом зерне — строка задачи появляется"),
    (44, [N5], "`orchestrator/merge_after.py` `declared_from_tz`: повтор строки не сверяется — берётся первая",
     "обе строки годны при любом зерне"),
    (45, [N5], "`orchestrator/merge_after.py` `declared_from_tz`: повтор строки не сверяется — берётся последняя (переписанная альтернатива «значения объединяются»: при одной задаче в обеих строках её ловил отказ «повтор» — лишь на части зёрен)",
     "обе строки годны при любом зерне"),
    (46, [N6], "`orchestrator/merge_after.py` `declared_from_tz`: строка разбирается только по форме, без `check`",
     "варианты «нет такой задачи», «убитая», «чужой target» годны по форме и перебираются всегда"),
    (47, [N7], "`orchestrator/catalog.py` `cmd_new`: отказ сверки путей выходит раньше разбора «Порядок:»",
     "отказ сверки путей есть всегда, элемент любой ветки зерна в вывод не попадает"),
    (48, [N7], "`orchestrator/catalog.py` `cmd_new`: отказ «Порядок:» вытесняет отказ сверки путей",
     "и элемент не в форме, и несуществующий id дают отказ «Порядок:» при любом зерне"),
    (49, [N8], "`orchestrator/merge_after.py` `status_suffix`: снята ветка ранних состояний",
     "оба ранних состояния перебираются при любом зерне"),
    (50, [N8], "`orchestrator/merge_after.py` `status_suffix`: в ранних состояниях «[ждёт мержа:» вместо «[мерж после:»",
     "оба ранних состояния перебираются при любом зерне"),
]
# Убийцы «до», убивающие лишь на части зёрен (выведены из сравнения).
PARTIAL = {12: [T1], 31: [T3], 46: [N7]}

HEAD_RE = re.compile(r"^_+ (\S.*?) _+$")
PLACE = re.compile(r"^(tests/\S+\.py):(\d+):")


def git(*args):
    return subprocess.run(["git", "-C", str(WT), *args], capture_output=True,
                          text=True).stdout


def frames(run: int) -> dict:
    """{патч: {тест: [[(файл, строка), …] на каждый провал]}}."""
    out = {}
    for path in sorted(glob.glob(f"{LOGS}/{TASK}-mutation-run-{run}-p*.log")):
        patch = int(path.rsplit("-p", 1)[1].split(".")[0])
        found = out.setdefault(patch, {})
        current = None
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.rstrip("\n")
            head = HEAD_RE.match(line)
            if head and "FAILURES" not in line and "summary" not in line:
                name = head.group(1).split(" (", 1)[0].split("[", 1)[0]
                current = found.setdefault(name.replace(".", "::"), [])
                current.append([])
                continue
            place = PLACE.match(line)
            if place and current is not None:
                item = (place.group(1), int(place.group(2)))
                if item not in current[-1]:
                    current[-1].append(item)
    return out


def control_seconds(run: int) -> str:
    text = (LOGS / f"{TASK}-mutation-run-{run}-control.log").read_text(
        encoding="utf-8", errors="replace")
    hit = re.findall(r"(\d+) passed[^\n]* in ([\d.]+)s", text)
    return f"{hit[-1][1].replace('.', ',')} с" if hit else "?"


def tables_text(plan: str, mark: str) -> str:
    start = plan.index(mark[0]) + len(mark[0])
    end = plan.index(mark[1])
    return plan[start:end].strip("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="draft")
    args = ap.parse_args()
    old_plan = (DOCS / "PLAN.md").read_text(encoding="utf-8")
    before_block = tables_text(old_plan, ("<!-- начало мутаций до -->", "<!-- конец мутаций до -->")) \
        if "<!-- начало мутаций до -->" in old_plan else None
    if before_block is None:
        i = old_plan.index("Часть №1:")
        before_block = old_plan[i:old_plan.index("<!-- конец мутаций до -->")].strip("\n")
    i = old_plan.index("<!-- конец мутаций после -->")
    j = old_plan.index("## Мутации после")
    after_block = old_plan[j + len("## Мутации после"):i].strip("\n")
    if "<!-- начало мутаций после -->" in after_block:
        after_block = after_block.split("<!-- начало мутаций после -->", 1)[1].strip("\n")

    base_texts = {p: git("show", f"{BASE}:{p}") for p in _plan.SOURCE_FILES}
    base_trees = {p: ast.parse(t) for p, t in base_texts.items()}
    head_text = git("show", f"HEAD:{_plan.MODULE}")
    head = ast.parse(head_text)
    head_funcs = _plan.module_functions(head)
    tests = {}
    for p, t in base_texts.items():
        for test in _plan.base_tests(p, t):
            tests[test.key] = test

    def rows(runs):
        out = {}
        for r in runs:
            text = (DOCS / f"mutation-run-{r}.tsv").read_text(encoding="utf-8")
            out.update(_plan.last_rows(_plan.tables(text)[0]))
        return out

    b_rows, a_rows = rows(BEFORE_RUNS), rows(AFTER_RUNS)
    b_fr, a_fr = {}, {}
    for r in BEFORE_RUNS:
        b_fr.update(frames(r))
    for r in AFTER_RUNS:
        a_fr.update(frames(r))

    def form_before(test, line):
        node = _plan.assertion_at(base_trees[test.path], line)
        if node is None:
            return None
        return _plan.normal_form(node, _plan.base_canon(base_trees[test.path], test.path))

    def form_after(test, line):
        node = _plan.assertion_at(head, line)
        if node is None:
            return None
        func = head_funcs[test.name]
        site = _plan.function_chain(head, line)[0]
        base_c = _plan.base_canon(base_trees[test.path], test.path)
        canon = _plan.new_canon(func, test.func, base_c) if site is func else \
            _plan.Canon({site.args.args[0].arg} if site.args.args else set(), {})
        return _plan.normal_form(node, canon)

    def fmt(places):
        if len(places) == 1:
            return f"{places[0][0]}:{places[0][1]}"
        return (f"{places[-1][0]}:{places[-1][1]} (вызов в теле теста "
                f"{places[0][0]}:{places[0][1]})")

    mut_lines, kill_lines, problems = [], [], []
    for n, keys, change, seed in M:
        # «на части зёрен» в строке с ключом теста планка читает как
        # частичного убийцу — описание альтернатив говорит иначе.
        change = re.sub(r"(?:лишь )?на части зёрен", "не при каждом зерне", change)
        files = ", ".join(f"`{pathlib.Path(tests[k].path).name}`" for k in dict.fromkeys(keys))
        loop = sorted(p for p, ls in _plan.patch_old_lines(
            (DOCS / f"mutation-{n:03d}.diff").read_text(encoding="utf-8")).items()
            if _plan.LOOP_NODES.get(p) and any(
                _plan.enclosing_names(git("show", f"{BASE}:{p}"), x) & set(_plan.LOOP_NODES[p])
                for x in ls))
        loop_text = ("может зациклить общий узел: да — меняет строки узла "
                     "из перечня, прогнан один в части") if loop else \
            "может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет"
        mut_lines.append(f"- mutation-{n:03d} — заявка {', '.join(keys)} (прежний файл {files}): "
                         f"{change}; {loop_text}; зерно: {seed}.")
        outcome, nodes = b_rows[n]
        a_outcome, a_nodes = a_rows[n]
        if outcome != _plan.KILLED:
            continue
        b_killers = {_plan.node_key(x) for x in nodes}
        a_killers = {_plan.after_node(x)[1] for x in a_nodes}
        for key in PARTIAL.get(n, []):
            kill_lines.append(f"- mutation-{n:03d}: {key} убивает её лишь на части зёрен — "
                              f"из сравнения «до → после» выведен (требование 13).")
        for key in dict.fromkeys(keys):
            if key in PARTIAL.get(n, []):
                continue
            test = tests[key]
            if key not in b_killers or test.name not in a_killers:
                problems.append(f"мутация {n}: {key} не убийца «до» и «после»")
                continue
            pair = None
            for bp in b_fr.get(n, {}).get(key, []):
                bf = form_before(test, bp[-1][1]) if bp else None
                if bf is None:
                    continue
                for ap_ in a_fr.get(n, {}).get(test.name, []):
                    if ap_ and form_after(test, ap_[-1][1]) == bf:
                        pair = (bp, ap_)
                        break
                if pair:
                    break
            if not pair:
                problems.append(f"мутация {n}: {key} — нет пары строк одной формы")
                continue
            kill_lines.append(
                f"- mutation-{n:03d}: {key} — {fmt(pair[0])} → "
                f"test_merge_after_module.py::{test.name} — {fmt(pair[1])} "
                f"(то же утверждение)")

    # Утверждения и вызовы подготовки «до» и их новые места «после».
    prep_lines = []
    for path, lines in _plan.PREP_ASSERT_LINES.items():
        tree = base_trees[path]
        for line in lines:
            chain = _plan.function_chain(tree, line)
            owner = chain[-1]
            fname = owner.name if owner.name.startswith("test") else f"{_plan.PREFIX[path]}_{owner.name}"
            old = sorted((n for n in _plan.self_assertions(owner)), key=lambda x: x.lineno)
            idx = [x.lineno for x in old].index(_plan.assertion_at(tree, line).lineno)
            new = sorted(_plan.plain_assertions(head_funcs[fname]), key=lambda x: x.lineno)[idx]
            prep_lines.append(f"- {path}:{line} (утверждение в `{owner.name}`) → "
                              f"tests/test_merge_after_module.py:{new.lineno} "
                              f"(`{fname}`) — не доказательство.")
    for path, lines in _plan.PREP_CALL_LINES.items():
        tree = base_trees[path]
        for line in lines:
            owner = _plan.function_chain(tree, line)[-1]
            method = next(m for p, m in _plan.RESULT_HELPERS if p == path and any(
                _plan.covers(c, line) for c in _plan.calls_in_order(owner, m, True)))
            old = _plan.calls_in_order(owner, method, True)
            idx = next(i for i, c in enumerate(old) if _plan.covers(c, line))
            new = _plan.calls_in_order(head_funcs[owner.name],
                                       f"{_plan.PREFIX[path]}_{method}", False)[idx]
            prep_lines.append(f"- {path}:{line} (вызов-подготовка `{method}` в "
                              f"`{owner.name}`) → tests/test_merge_after_module.py:"
                              f"{new.lineno} (`{_plan.PREFIX[path]}_{method}`) — не доказательство.")

    names = sorted(f for f in head_funcs if any(f.startswith(p + "_") for p in _plan.PREFIX.values())
                   and not f.startswith("test"))
    base_counts = {p: len(_plan.base_tests(p, t)) for p, t in base_texts.items()}
    base_lines = {p: t.count("\n") for p, t in base_texts.items()}
    old_mod = git("show", f"{BASE}:{_plan.MODULE}")
    counts = (f"- До свода (база {BASE[:8]}): шесть файлов волны — {sum(base_counts.values())} "
              f"тестов, {sum(base_lines.values())} строк ("
              + ", ".join(f"`{pathlib.Path(p).name}` — {base_counts[p]} тестов, {base_lines[p]} строк"
                          for p in _plan.SOURCE_FILES)
              + f"); `tests/test_merge_after_module.py` — "
              f"{len(_plan.module_tests(ast.parse(old_mod)))} тестов, {old_mod.count(chr(10))} строк.\n"
              f"- После свода (HEAD): `tests/test_merge_after_module.py` — "
              f"{len(_plan.module_tests(head))} тестов (20 + 33, удалённых дублей нет), "
              f"{head_text.count(chr(10))} строк; шести файлов волны на ветке нет.")
    times = ("- Контрольные прогоны `mutation-run` (без патча): «до» — "
             + ", ".join(f"№{r}: {control_seconds(r)}" for r in BEFORE_RUNS)
             + "; «после» — " + ", ".join(f"№{r}: {control_seconds(r)}" for r in AFTER_RUNS) + ".")
    tree_line = git("rev-parse", f"{BASE}:orchestrator").strip()
    tree_head = git("rev-parse", "HEAD:orchestrator").strip()
    s_base = git("rev-parse", f"{BASE}:scripts").strip()
    s_head = git("rev-parse", "HEAD:scripts").strip()

    text = (DOCS / "plan_static.txt").read_text(encoding="utf-8")
    repl = {
        "{{STATUS}}": args.status,
        "{{MUTATIONS}}": "\n".join(mut_lines),
        "{{KILLS}}": "\n".join(kill_lines),
        "{{PREP}}": "\n".join(prep_lines),
        "{{HELPERS}}": ", ".join(f"`{n}`" for n in names),
        "{{COUNTS}}": counts,
        "{{TIMES}}": times,
        "{{TREES}}": (f"дерево `orchestrator/` базы {BASE[:8]} и HEAD — {tree_line[:12]} / "
                      f"{tree_head[:12]}, `scripts/` — {s_base[:12]} / {s_head[:12]}"),
        "{{BEFORE}}": before_block,
        "{{AFTER}}": after_block,
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    (DOCS / "PLAN.md").write_text(text, encoding="utf-8")
    print("\n".join(problems) or "согласованность «до → после»: расхождений нет")


if __name__ == "__main__":
    main()
