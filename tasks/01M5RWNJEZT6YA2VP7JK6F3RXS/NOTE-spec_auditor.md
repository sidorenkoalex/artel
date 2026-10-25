# NOTE spec_auditor

## Выяснено
- Строки ТЗ/SPEC сверены: artifact_branch._write:343, _send:459, origin_sync_refusal:486; lease.run_locked:334/371-375; github_adapter :160/:234; fsm_merge_gate :332/:642/:708/:739/:756/:1053; runner spawn_agent :1674; snapshot.commit_closing :138 — совпадают.
- fsm_merge_gate._ci_ready_or_wait (:756) CI не опрашивает и не ждёт (возвращает ("wait",…)/"ok") — «долгий этап» и «момент первого опроса CI» в AC-11 к нему неприложимы.
- Мандат на правку test_review_package живёт только в ТЗ; гейт неослабления читает маркер «Ослабление тестов разрешено:» только из ANSWER-n.md (advance_gates/test_integrity.py:1061).
- Без AC: досылка в fetch_all_from_origin, ensure_draft_mr, _sync_main_or_wait; исключение досылки при нормальном выходе тела (треб. 4, п.3).

## Не сработало
- bash с `cd …;` и несколькими командами требует подтверждения — звать по одной команде, пути относительные.

- tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py нет — Ac5ProofMismatchTest в tests/test_merge_outcome_module.py.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (8 пунктов), guard ок.

## Чего не хватило
- Где гейт берёт мандат на правку теста (ANSWER-n против ТЗ) — искал в advance_gates/mandate.py и test_integrity.py:1061.
