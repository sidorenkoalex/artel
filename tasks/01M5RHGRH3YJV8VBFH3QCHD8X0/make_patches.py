"""Генератор патчей мутаций задачи 01M5RHGRH3YJV8VBFH3QCHD8X0: замены текста
в файлах orchestrator/ и scripts/guard.py рабочей копии (база ветки) ->
mutation-<nnn>.diff в каталоге документов задачи; каждый патч проверяется
`git apply --check`. Правки одного патча применяются по очереди.

Запуск из рабочей копии задачи: python3 <путь>/make_patches.py
"""
import difflib
import pathlib
import subprocess

DOCS = pathlib.Path(__file__).resolve().parent
A = "orchestrator/merge_after.py"
ANS = "orchestrator/answer.py"
G = "scripts/guard.py"
F = "orchestrator/fsm.py"
FA = "orchestrator/fsm_advance.py"
C = "orchestrator/catalog.py"
P = []


def p(*edits):
    P.append(list(edits))


# ---------------------------------------------------------------- answer
# 001 ac11_escalated: «нет» читается как id задачи
p((A, """    if elements == [NONE_WORD]:
        return []
    if NONE_WORD in elements:""", """    if NONE_WORD in elements:"""))
# 002 ac11_escalated: значение строки мандата не применяется (mandate_value
# берёт перечень причин check вместо полных id)
p((A, "    return check(conn, task_id, elements)[0]",
   "    return check(conn, task_id, elements)[1]"))
# 003 ac11_merge_gate: merge_gate не среди принимающих состояний
p((ANS, """    elif state == "merge_gate":
        if runner.in_role_environment():""", """    elif state == "merge_gate_":
        if runner.in_role_environment():"""))
# 004 ac12_invalid: в узле мандата только форма строки
p((A, """    if conn is None or task_id is None:
        return guard.merge_after_form_errors(elements, task_id)""",
   """    if True:
        return guard.merge_after_form_errors(elements, task_id)"""))
# 005 ac12_invalid: проверка строк мандата после коммита ANSWER
p((ANS, """    if state == "escalated":
        raw = _read_checked_answer_file(conn, task_id, file_path, t["branch"])
        merge_deps = merge_after.mandate_value(conn, task_id, raw)""",
   """    if state == "escalated":
        raw = _read_answer_file(task_id, file_path)
        merge_deps = merge_after.mandate_value(conn, task_id, raw)"""),
  (ANS, """    rel_answer, branch = _commit_answer(conn, task_id, raw)

    if merge_deps is not None:
""", """    rel_answer, branch = _commit_answer(conn, task_id, raw)
    if state == "escalated":
        _read_checked_answer_file(conn, task_id, file_path, t["branch"])

    if merge_deps is not None:
"""))
# 006 ac12_merge_gate: в merge_gate принимается любой ANSWER
p((ANS, """        if merge_deps is None:
            sys.exit(f"[{task_id}] answer в состоянии merge_gate принимает "
                     f"только строку «{mandate.MERGE_AFTER_MANDATE_MARKER} "
                     f"…» — ANSWER не создан")
""", ""))
# 007 ac12_merge_gate: рубеж окружения роли в merge_gate снят
p((ANS, """    elif state == "merge_gate":
        if runner.in_role_environment():
            sys.exit(f"[{task_id}] {_ROLE_ENV_REFUSAL}")
        raw = _read_checked_answer_file""", """    elif state == "merge_gate":
        raw = _read_checked_answer_file"""))
# ----------------------------------------------------------------- guard
# 008 самоссылка не сверяется с полем task:
p((G, """        elif own_task_id and item == str(own_task_id):
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» — id самой "
                          f"задачи, задача не может зависеть от себя")
""", ""))
# 009 элементы схлопываются до проверки
p((G, """    for item in items:
        if not idgen.is_task_id_form(item):""",
   """    for item in dict.fromkeys(items):
        if not idgen.is_task_id_form(item):"""))
# 010 формат элемента не проверяется
p((G, """        if not idgen.is_task_id_form(item):
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» не в формате \"""",
   """        if False:
            errors.append(f"{MERGE_AFTER_FIELD}: элемент «{item}» не в формате \""""))
# 011 поле объявлено обязательным
p((G, """    if (meta.get("type") or "") != "spec" or MERGE_AFTER_FIELD not in meta:
        return []""", """    if (meta.get("type") or "") != "spec":
        return []
    if MERGE_AFTER_FIELD not in meta:
        return [f"{path}: {MERGE_AFTER_FIELD}: поле обязательно, а его нет"]"""))
# 012 разделитель-запятая не распознаётся (узел merge_after_items)
p((G, """    return [item.strip() for item in str(raw).split(",") if item.strip()]""",
   """    return [item.strip() for item in str(raw).split(";") if item.strip()]"""))
# ------------------------------------------------------------------ plan
# 013 ac9_justified: отличное от БД значение PLAN не применяется
p((A, "    if not reasons and ids == old:", "    if not reasons and ids != old:"))
# 014 ac9_justified: запись «было → стало» не называет новое значение
p((A, """    detail = f"{_text(old)} → {_text(new_ids)} (канал: {channel})\"""",
   """    detail = f"{_text(old)} → (канал: {channel})\""""))
# 015 ac9_empty: пустое поле читается как «поля нет»
p((A, """    if FIELD not in meta:
        return
    old = stored(t["merge_after"])""", """    if not meta.get(FIELD):
        return
    old = stored(t["merge_after"])"""))
# 016 ac9_without_field: отсутствие поля в PLAN снимает зависимости
p((A, """    if FIELD not in meta:
        return
    old = stored(t["merge_after"])""", """    if FIELD not in meta:
        store.update_task(conn, task_id, merge_after=None)
        return
    old = stored(t["merge_after"])"""))
# 017 ac10: отказ значения PLAN останавливает переход
p((A, """        print(f"[{task_id}] ВНИМАНИЕ: {PLAN_REJECTED_ACTION}: {detail}")
        return
""", """        print(f"[{task_id}] ВНИМАНИЕ: {PLAN_REJECTED_ACTION}: {detail}")
        return True
"""), (FA, """    merge_after.apply_plan(conn, task_id, t, plan_meta, plan_text)
""", """    if merge_after.apply_plan(conn, task_id, t, plan_meta, plan_text):
        return False
"""))
# 018 ac10: проверка обоснования смены снята
p((A, """    if not reasons and FIELD not in guard.section_body(plan_text,
                                                       IMPACT_SECTION):""",
   """    if False:"""))
# 019 ac10: причины check по элементам отбрасываются
p((A, """    old = stored(t["merge_after"])
    ids, reasons = check(conn, task_id, guard.merge_after_items(meta[FIELD]))""",
   """    old = stored(t["merge_after"])
    ids, reasons = check(conn, task_id, guard.merge_after_items(meta[FIELD]))[0], []"""))
# ------------------------------------------------------------- spec_gate
# 020 ac2_missing: отсутствующий элемент молча отбрасывается (узел check)
p((A, """        if not matches:
            reasons.append(_reason(item, "нет такой задачи"))
            continue""", """        if not matches:
            continue"""))
# 021 ac2_ambiguous: префикс разрешается первым совпадением (узел check)
p((A, "        matches = store.task_id_matches(conn, item)",
   "        matches = store.task_id_matches(conn, item)[:1]"))
# 022 ac3_killed: состояние зависимости не сверяется (узел check)
p((A, """        if store.task_state(conn, dep) == "killed":
            reasons.append(_reason(item, f"задача {dep} убита (killed)"))
            continue
""", ""))
# 023 ac3_other_target + new_declares ac6: target не сверяется (узел check)
p((A, """        dep_target = store.task_target(conn, dep)
        if dep_target != own_target:
            reasons.append(_reason(
                item, f"задача {dep} другого target ({dep_target}), у задачи "
                      f"— {own_target}"))
            continue
""", ""))
# 024 ac3_own_prefix: самоссылка по буквальному элементу (узел check)
p((A, "        if dep == task_id:", "        if item == task_id:"),
  (A, "        path = _cycle_path(graph, dep, task_id)",
   "        path = None if dep == task_id else _cycle_path(graph, dep, task_id)"))
# 025 ac4_cycle: проверка цикла снята (узел check)
p((A, """    for item, dep in resolved:
        path = _cycle_path(graph, dep, task_id)
        if path is not None:
            reasons.append(_reason(
                item, f"цикл: {' → '.join([task_id] + path)}"))
""", ""))
# 026 ac4_cycle: граф строится без нового значения задачи (узел check)
p((A, """    graph[task_id] = [dep for _, dep in resolved]
""", ""))
# 027 ac5_prefixes: approve гейта SPEC не пишет колонку
p((F, """    store.update_task(conn, task_id, zones=meta.get("zones"),
                      merge_after=merge_deps)""",
   """    store.update_task(conn, task_id, zones=meta.get("zones"),
                      merge_after=None)"""))
# 028 ac5_without_field: отсутствие поля — ошибка проверки
p((A, """    if FIELD not in meta:
        return None, None""", """    if FIELD not in meta:
        return None, f"{FIELD}: поля нет в SPEC\""""))
# 029 ac5_without_field: в колонку попадает строка «None»
p((A, """    if FIELD not in meta:
        return None, None""", """    if FIELD not in meta:
        return "None", None"""))
# ----------------------------------------------------------- status_show
# 030 ac13_status_suffix + new_declares ac8: состояния зависимостей кэшируются
p((A, """def _dependency_states(conn, t) -> list[tuple[str, str]]:""",
   """_STATES_CACHE: dict = {}


def _dependency_states(conn, t) -> list[tuple[str, str]]:"""),
  (A, """    return [(dep, store.task_state(conn, dep) or MISSING_STATE)
            for dep in stored(t["merge_after"])]""",
   """    if t["id"] not in _STATES_CACHE:
        _STATES_CACHE[t["id"]] = [
            (dep, store.task_state(conn, dep) or MISSING_STATE)
            for dep in stored(t["merge_after"])]
    return _STATES_CACHE[t["id"]]"""))
# 031 ac13_status_suffix (+ ac13_no_suffix на части зёрен): добавка
# включает завершённые
p((A, """    pending = [(d, s) for d, s in _dependency_states(conn, t) if s != "done"]""",
   """    pending = _dependency_states(conn, t)"""))
# 032 ac13_other_state: фильтр состояния задачи снят
p((A, """    if t["state"] in STATUS_WAIT_STATES:
        label = "ждёт мержа"
    elif t["state"] in STATUS_DECLARED_STATES:
        label = "мерж после"
    else:
        return ""
""", """    label = "ждёт мержа"
"""))
# 033 ac13_no_suffix: условие пустоты снято — добавка с пустым перечнем
p((A, """    if not pending:
        return ""
""", ""))
# 034 ac14_lists_all: show переиспользует фильтр добавки
p((A, """    states = _dependency_states(conn, t)
    if not states:
        return None""", """    states = [(d, s) for d, s in _dependency_states(conn, t) if s != "done"]
    if not states:
        return None"""))
# 035 ac14_without: строка show безусловно
p((A, """    if not states:
        return None
""", ""))
# ---------------------------------------------------------- new_declares
# 036 ac1: заявленное значение не пишется в колонку
p((A, """    store.update_task(conn, task_id, merge_after=column(ids))
""", ""))
# 037 ac1: порядок заявленных id обращён
p((A, "    store.update_task(conn, task_id, merge_after=column(ids))",
   "    store.update_task(conn, task_id, merge_after=column(ids[::-1]))"))
# 038 ac1: запись журнала не делается
p((A, """    store.journal(conn, task_id, "operator", DECLARED_ACTION, _text(ids))
""", ""))
# 039 ac2: ни «(», ни «.» не режут перечень (узел declared_from_tz)
p((A, "    tail = _ORDER_LIST_END.split(tails[0], maxsplit=1)[0]",
   "    tail = tails[0]"))
# 040 ac3: хвост «Порядок:» разбирается и без слова «после» (узел _ORDER_LINE_RE)
p((A, r'''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \t]+после(?!\w)(.*)$", re.M)''',
   r'''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \t]+(?:после(?!\w))?(.*)$", re.M)'''))
# 041 ac3: «после <id>» ищется по всему ТЗ (узел _ORDER_LINE_RE)
p((A, r'''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \t]+после(?!\w)(.*)$", re.M)''',
   r'''_ORDER_LINE_RE = re.compile(r"после(?!\w)(.*)$", re.M)'''))
# 042 ac4: строка с негодным элементом молча отбрасывается (узел declared_from_tz)
p((A, """    items = guard.merge_after_items(tail)
    if not items:""", """    items = guard.merge_after_items(tail)
    if guard.merge_after_form_errors(items, None):
        return [], []
    if not items:"""))
# 043 ac4 + ac6: проверка строки «Порядок:» после заведения строки задачи
p((C, """            declared, order_reasons = merge_after.declared_from_tz(
                conn, tz_raw, target)""", """            declared, order_reasons = [], []"""),
  (C, """                 model_set=model_set,
                 set_members=set_members)
    if tz_check_detail is not None:""", """                 model_set=model_set,
                 set_members=set_members)
    if tz_raw is not None and not canary:
        declared, late_reasons = merge_after.declared_from_tz(conn, tz_raw, target)
        if late_reasons:
            sys.exit("\\n".join(late_reasons) + "\\nnew: зависимости мержа ТЗ "
                     "не годны — задача не заведена")
    if tz_check_detail is not None:"""))
# 044 ac5: повтор строки не сверяется — берётся первая (узел declared_from_tz)
p((A, """    if len(tails) > 1:
        return [], [f"строка «{ORDER_LINE}» повторена — значение задаёт "
                    f"одна строка"]
""", ""))
# 045 ac5: повтор строки не сверяется — берётся последняя (узел declared_from_tz)
p((A, """    if len(tails) > 1:
        return [], [f"строка «{ORDER_LINE}» повторена — значение задаёт "
                    f"одна строка"]
    tail = _ORDER_LIST_END.split(tails[0], maxsplit=1)[0]""",
   """    tail = _ORDER_LIST_END.split(tails[-1], maxsplit=1)[0]"""))
# 046 ac6: строка разбирается только по форме, без check по БД (узел declared_from_tz)
p((A, "    return check(conn, None, items, target=target)",
   "    return items, guard.merge_after_form_errors(items, None)"))
# 047 ac7: отказ сверки путей выходит раньше разбора «Порядок:»
p((C, """        refusal = _tz_path_refusal(tz_path, tz_raw, target)
""", """        refusal = _tz_path_refusal(tz_path, tz_raw, target)
        if refusal is not None:
            sys.exit(refusal)
"""))
# 048 ac7: отказ «Порядок:» вытесняет отказ сверки путей
p((C, """                ([refusal] if refusal else [])
                + [f"ТЗ {tz_path}: «{merge_after.ORDER_LINE}»: {r}\"""",
   """                [f"ТЗ {tz_path}: «{merge_after.ORDER_LINE}»: {r}\""""))
# 049 ac8: добавки в ранних состояниях нет
p((A, """    elif t["state"] in STATUS_DECLARED_STATES:
        label = "мерж после"
""", ""))
# 050 ac8: в ранних состояниях — «[ждёт мержа:» вместо «[мерж после:»
p((A, """        label = "мерж после\"""", """        label = "ждёт мержа\""""))


def main():
    for n, edits in enumerate(P, 1):
        texts, muts = {}, {}
        for path, old, new in edits:
            if path not in texts:
                texts[path] = pathlib.Path(path).read_text(encoding="utf-8")
                muts[path] = texts[path]
            assert muts[path].count(old) == 1, (n, path, muts[path].count(old))
            muts[path] = muts[path].replace(old, new)
        out = []
        for path in texts:
            diff = difflib.unified_diff(texts[path].splitlines(True),
                                        muts[path].splitlines(True),
                                        f"a/{path}", f"b/{path}", n=3)
            out.append(f"diff --git a/{path} b/{path}\n" + "".join(diff))
        name = DOCS / f"mutation-{n:03d}.diff"
        name.write_text("".join(out), encoding="utf-8")
        res = subprocess.run(["git", "apply", "--check", str(name)],
                             capture_output=True, text=True)
        if res.returncode:
            print(n, res.stderr)
    print("патчей:", len(P))


if __name__ == "__main__":
    main()
