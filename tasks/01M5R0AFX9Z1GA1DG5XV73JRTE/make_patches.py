"""Генератор патчей мутаций задачи 01M5R0AFX9Z1GA1DG5XV73JRTE: замены текста
в файлах orchestrator/ рабочей копии (база ветки) -> mutation-<nnn>.diff в
каталоге документов задачи; каждый патч проверяется `git apply --check`.

Запуск из рабочей копии задачи: python3 <путь>/make_patches.py
"""
import difflib
import pathlib
import subprocess

DOCS = pathlib.Path(__file__).resolve().parent
L = "orchestrator/merge_lock.py"
Q = "orchestrator/merge_queue.py"
S = "orchestrator/store.py"
A = "orchestrator/merge_after.py"
I = "orchestrator/idgen.py"
SC = "orchestrator/schema.py"
F = "orchestrator/fsm.py"
P = []


def p(path, old, new):
    P.append([(path, old, new)])


# 001 acquire: строка мьютекса всего пульта
p(L, """        row = store.project_merge_lock_row(conn,
                                           store.task_target(conn, task_id))""",
  """        row = store.merge_lock_row(conn)""")
# 002 acquire: проект держателя не совпадает со своим никогда
p(L, """        row = store.project_merge_lock_row(conn,
                                           store.task_target(conn, task_id))""",
  """        row = store.project_merge_lock_row(conn, task_id)""")
# 003 текст отказа
p(L, '''f"дождись освобождения и повтори approve")''',
  '''f"жди освобождения и повтори approve")''')
# 004 перехват без журнала
p(L, """        store.journal(conn, task_id, "merge-lock",
                     "мьютекс merge перехвачен", detail)
""", "")
# 005 set_merge_lock стирает всю таблицу
p(S, """    for row in merge_lock_rows(conn):
        if row["target"] == target:
            conn.execute("DELETE FROM merge_locks WHERE rowid=?",
                         (row["rowid"],))""",
  """    conn.execute("DELETE FROM merge_locks")""")
# 006 set_merge_lock не сносит прежнюю строку проекта
p(S, """    for row in merge_lock_rows(conn):
        if row["target"] == target:
            conn.execute("DELETE FROM merge_locks WHERE rowid=?",
                         (row["rowid"],))
""", "")
# 007 task_target — сырая колонка
p(S, """    if row is None:
        return config.DEFAULT_TARGET
    return row["target"] or config.DEFAULT_TARGET""",
  """    if row is None:
        return None
    return row["target"]""")
# 008 голова — первая запись всего пульта
p(Q, "            if _head_task_id(conn, target) == task_id:",
  "            if _head_task_id(conn) == task_id:")
# 009 FIFO внутри проекта снят
p(Q, "            if _head_task_id(conn, target) == task_id:",
  "            if True:")
# 010 пруна не идёт
p(Q, """            _prune_dead_entries(conn)
            if _head""", """            if _head""")
# 011 проект строки мьютекса — сырая колонка (пустой target не нормализуется)
p(S, """_ROW_TARGET_SQL = "COALESCE(NULLIF(t.target, ''), ?) AS target\"""",
  """_ROW_TARGET_SQL = "COALESCE(t.target, ?) AS target\"""")
# 012 release по одному session_id
p(S, """    conn.execute("DELETE FROM merge_locks WHERE session_id=? AND pid=?",
                 (session_id, pid))""",
  """    conn.execute("DELETE FROM merge_locks WHERE session_id=?",
                 (session_id,))""")
# 013 release — вся таблица
p(S, """    conn.execute("DELETE FROM merge_locks WHERE session_id=? AND pid=?",
                 (session_id, pid))""",
  """    conn.execute("DELETE FROM merge_locks")""")
# 014 продление — все строки
p(L, """    return [row for row in rows
            if row["target"] == target and row["task_id"] == task_id
            and row["session_id"] == sid]""", """    return rows""")
# 015 продление — только проект
p(L, """    return [row for row in rows
            if row["target"] == target and row["task_id"] == task_id
            and row["session_id"] == sid]""", """    return [row for row in rows
            if row["target"] == target]""")
# 016 продление — проект и задача без сессии
p(L, """    return [row for row in rows
            if row["target"] == target and row["task_id"] == task_id
            and row["session_id"] == sid]""", """    return [row for row in rows
            if row["target"] == target and row["task_id"] == task_id]""")
# 017 прежняя форма — сверка своей строки по None
p(L, """        if len(rows) <= 1:
            return rows""", """        if len(rows) <= 1:
            return [row for row in rows if row["task_id"] == task_id]""")
# 018 тексты ожидания по первой строке таблицы
p(Q, """    if target is None:
        return store.merge_lock_row(conn)
    return store.project_merge_lock_row(conn, target)""",
  """    return store.merge_lock_row(conn)""")
# 019 метка проекта в тексте держателя
p(Q, '''    return f"{row['task_id']} (pid {row['pid']})"''',
  '''    return f"{row['task_id']} (pid {row['pid']}, проект {target})"''')
# 020 длина не сверяется
p(I, """    return (len(text) <= _TIME_CHARS + _RANDOM_CHARS
            and all(ch in _ENCODING for ch in text))""",
  """    return all(ch in _ENCODING for ch in text)""")
# 021 алфавит не сверяется
p(I, """    return (len(text) <= _TIME_CHARS + _RANDOM_CHARS
            and all(ch in _ENCODING for ch in text))""",
  """    return len(text) <= _TIME_CHARS + _RANDOM_CHARS""")
# 022 точное совпадение не первым
p(S, """    if conn.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
        return [task_id]
""", "")
# 023 повтор по буквальному тексту
p(A, "        if dep in [d for _, d in resolved]:",
  "        if item in [i for i, _ in resolved]:")
# 024 done спутан с killed
p(A, """        if store.task_state(conn, dep) == "killed":""",
  """        if store.task_state(conn, dep) in ("killed", "done"):""")
# 025 пропавшая зависимость — как незавершённая
p(A, """    dead = [(d, s) for d, s in states if s in ("killed", MISSING_STATE)]""",
  """    dead = [(d, s) for d, s in states if s == "killed"]""")
# 026 «нет» отбрасывается до проверки
p(A, """    if NONE_WORD in elements:
        return [f"слово «{NONE_WORD}» снимает все зависимости и стоит в "
                f"строке одно, без id"]""",
  """    elements = [e for e in elements if e != NONE_WORD]""")
# 027 вторая строка мандата теряется
p(A, "    if len(_mandate_items(raw)) > 1:",
  "    if len(_mandate_items(raw)[:1]) > 1:")
# 028 сравнение по сырому тексту PLAN
p(A, "    if not reasons and ids == old:",
  "    if not reasons and guard.merge_after_items(meta[FIELD]) == old:")
# 029 фильтр «родитель в значении» снят
p(A, """        if parent_id not in old:
            continue
""", "")
# 030 миграция без колонки merge_after
p(SC, """    add_column(conn, "tasks", "merge_after", "TEXT")
""", "")
# 031 метка не с первой позиции
p(A, '''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \\t]+после(?!\\w)(.*)$", re.M)''',
  '''_ORDER_LINE_RE = re.compile(r"Порядок:[ \\t]+после(?!\\w)(.*)$", re.M)''')
# 032 «после» префиксом
p(A, '''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \\t]+после(?!\\w)(.*)$", re.M)''',
  '''_ORDER_LINE_RE = re.compile(r"^Порядок:[ \\t]+после(.*)$", re.M)''')
# 033 пустой перечень — молча
p(A, """        return [], [f"в строке «{ORDER_LINE}» нет ни одного id задачи"]""",
  """        return [], []""")
# 034 target из строки БД несуществующей задачи
p(A, "    own_target = target if target is not None else store.task_target(conn, task_id)",
  "    own_target = store.task_target(conn, task_id)")
# 035 признак «гейт SPEC пройден» снят
p(A, "    if not declared or not _declared_in_force(conn, task_id):",
  "    if not declared:")
# 036 обоснование подстрокой
p(A, """    words = set(re.findall(r"[0-9A-Za-z]+", section))
    return dep in words or item in words""",
  """    return dep in section or item in section""")
# 037 первая подзадача вместо последней
p(F, "        merge_after.replace_divided(conn, task_id, new_ids[-1])",
  "        merge_after.replace_divided(conn, task_id, new_ids[0])")
# 038 родитель удалён вместо замены
p(A, "        new_ids = [successor_id if dep == parent_id else dep for dep in old]",
  "        new_ids = [dep for dep in old if dep != parent_id]")
# 039 переписана только первая зависящая
p(A, """        rewrite(conn, row["id"], new_ids, "деление на гейте SPEC", "operator")""",
  """        rewrite(conn, row["id"], new_ids, "деление на гейте SPEC", "operator")
        return""")
# 040 соседи отброшены
p(A, "        new_ids = [successor_id if dep == parent_id else dep for dep in old]",
  "        new_ids = [successor_id]")
# 041 мимо rewrite прямым update_task
p(A, """        rewrite(conn, row["id"], new_ids, "деление на гейте SPEC", "operator")""",
  """        store.update_task(conn, row["id"], merge_after=column(new_ids))""")
# 042 запись в журнал родителя
p(A, """        rewrite(conn, row["id"], new_ids, "деление на гейте SPEC", "operator")""",
  """        store.update_task(conn, row["id"], merge_after=column(new_ids))
        store.journal(conn, parent_id, "operator", CHANGED_ACTION,
                      f"{_text(old)} → {_text(new_ids)} (канал: деление)")""")
# 043 деление не переписывает зависящих
p(F, """    if new_ids:
        merge_after.replace_divided(conn, task_id, new_ids[-1])
""", "")
# 044 переписывается только колонка родителя
p(A, "        if parent_id not in old:",
  """        if row["id"] != parent_id or parent_id not in old:""")
_LOSS_TAIL = '''{_text(lost)} — верни SPEC "
                    f"аналитику: artel.py reject {task_id} \\"аналитик, "
                    f"эскалируй вопрос о зависимости {_text(lost)}\\"; после "
                    f"эскалации аналитика ответ в escalated — artel.py "
                    f"answer {task_id} <файл> со строкой "
                    f"«{MERGE_AFTER_MANDATE_MARKER} …», затем artel.py "
                    f"approve {task_id}")'''
# 045 прежний хвост отказа о потере
p(A, _LOSS_TAIL, '''{_text(lost)} — снять "
                    f"заявленную может только Оператор: мандат "
                    f"«{MERGE_AFTER_MANDATE_MARKER} …» в ANSWER (artel.py "
                    f"answer {task_id} <файл>)")''')
# 046 answer раньше reject
p(A, _LOSS_TAIL, '''{_text(lost)} — ответ в "
                    f"escalated — artel.py answer {task_id} <файл> со строкой "
                    f"«{MERGE_AFTER_MANDATE_MARKER} …» после эскалации "
                    f"аналитика; верни SPEC аналитику: artel.py reject "
                    f"{task_id} \\"аналитик, эскалируй вопрос о зависимости "
                    f"{_text(lost)}\\", затем artel.py approve {task_id}")''')
# 047 начало отказа задето
p(A, '''        return [], (f"{FIELD} SPEC теряет зависимости, заявленные Оператором "''',
  '''        return [], (f"{FIELD} в SPEC теряет зависимости, заявленные Оператором "''')
# 048 текст отказа о добавке
p(A, '''                    f"Оператором без обоснования: {_text(unjustified)} — "''',
  '''                    f"Оператором без причины: {_text(unjustified)} — "''')
# 049 текст отказа гейта мержа (убитая зависимость)
p(A, '''{_listing(dead)} — сними "
                  f"или замени её ответом''', '''{_listing(dead)} — замени "
                  f"её ответом''')
# 050 мандат в escalated не применяется
p(A, """    found = _mandate_items(raw)
    if not found:
        return None
    elements = found[0]""", """    found = []
    if not found:
        return None
    elements = found[0]""")
# 051 продление — первая строка таблицы
p(L, """    return [row for row in rows
            if row["target"] == target and row["task_id"] == task_id
            and row["session_id"] == sid]""", """    return rows[:1]""")
# 052 пруна убирает только записи других проектов
p(Q, """            _prune_dead_entries(conn)
            if _head""", """            own = [r["rowid"] for r in
                   store.project_merge_queue_rows(conn, target)]
            for row in store.merge_queue_rows(conn):
                if row["rowid"] not in own and merge_lock._holder_is_dead(row):
                    store.delete_merge_queue_row(conn, row["rowid"])
            if _head""")


def main():
    for n, edits in enumerate(P, 1):
        out = []
        for path, old, new in edits:
            text = pathlib.Path(path).read_text(encoding="utf-8")
            assert text.count(old) == 1, (n, path, text.count(old))
            mut = text.replace(old, new)
            diff = difflib.unified_diff(text.splitlines(True),
                                        mut.splitlines(True),
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
