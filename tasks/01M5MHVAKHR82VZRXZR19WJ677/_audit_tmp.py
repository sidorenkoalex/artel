import ast
pairs = [("orchestrator/advance_gates/spec_audit.py", ["answer_names"]),
         ("orchestrator/advance_gates/test_integrity.py", ["assertion_observation"]),
         ("orchestrator/fixation.py", ["external_code_sha"]),
         ("orchestrator/gitcmd.py", ["is_clean"]),
         ("orchestrator/merge_after.py", ["has_mandate_line"]),
         ("orchestrator/pool_seal.py", ["guids_path"]),
         ("orchestrator/retro.py", ["retro_path", "retro_rel_path"]),
         ("orchestrator/retro_corpus.py", ["read_cache"]),
         ("orchestrator/rounds.py", ["task_rounds"]),
         ("orchestrator/models.py", ["VERDICT_APPROVED"]),
         ("scripts/core_reference.py", ["SETTING_KEYS", "SHA_HEX"])]
for path, names in pairs:
    tree = ast.parse(open(path).read())
    removed = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            removed.append(n)
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets):
            removed.append(n)
    rem_ids = {id(x) for r in removed for x in ast.walk(r)}
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                imported.add((a.asname or a.name).split('.')[0])
    privs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    privs |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    uses_out, uses_in = set(), set()
    for x in ast.walk(tree):
        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
            (uses_in if id(x) in rem_ids else uses_out).add(x.id)
    unused_main = sorted(imported - uses_out - uses_in - {"annotations"})
    print(path, len(removed), "orphan-imports:", sorted((uses_in - uses_out) & imported),
          "orphan-names:", sorted(((uses_in - uses_out) & privs) - set(names)),
          "unused-on-main-imports:", unused_main)
