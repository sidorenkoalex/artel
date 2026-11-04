"""Указание на гейте SPEC не задевает ANSWER, мандаты, причины возврата с гейта и прежние решения `reject --decision` (AC-13).

Группа: разовый
Красен до реализации: ключа `--note` пульт не знает — `approve <id> --note <файл>` отказывает «sha '--note' короче минимальной длины», задача остаётся на `spec_gate`, и сравнение с задачей-близнецом без указания не начинается.

Почему файл в планке, а не в `tests/`: критерий называет закрытые функции
пульта (`fsm._answer_file_count`, `fsm._latest_answer_number`,
`brief._spec_gate_reasons`) и исход проверок мандатов, который читают
закрытые узлы гейтов (`test_integrity._answer_mandate`,
`zones._answer_zones_mandate`, `outcome_integrity._answer_mandates`);
долгоживущий файл обращаться к закрытым именам не вправе. Сверка этих
функций с указанием — проверка этой задачи; поведение команды и брифа
держит долгоживущий `tests/test_01m6kwkz8gkzzfabdg8qc9rdjf_spec_gate_note.py`,
его стенд и помощники эта планка берёт оттуда (импорт модуля, не имён
`test_*`, чтобы не собрать его тесты второй раз).

Стенд: две задачи артели с одинаковой историей — `reject` с гейта SPEC с
одной причиной, возврат на гейт, `approve` (первая — с `--note`, вторая —
без), эскалация test_author, `answer`, возврат в `tests_writing`. Draft MR —
пустышка `github_adapter.ensure_draft_mr` фикстуры `stand`.
"""
from orchestrator import artifact_source, brief, config, fsm, spec_gate_decision, store
from orchestrator.advance_gates import mandate, outcome_integrity, test_integrity, zones
import tests.test_01m6kwkz8gkzzfabdg8qc9rdjf_spec_gate_note as base

stand = base.stand


def facts(stand, t) -> dict:
    """Наблюдаемое критерием AC-13 для задачи `t`."""
    conn = stand.conn
    branch, _foreign = artifact_source.resolve(conn, t.id)
    reasons = brief._spec_gate_reasons(conn, t.id)
    return {
        "answer_count": fsm._answer_file_count(conn, t.id, config.TASKS / t.id),
        "latest_answer": fsm._latest_answer_number(conn, t.id),
        "gate_reasons": reasons,
        "decisions": [spec_gate_decision.numbered(r) for r in reasons],
        "test_mandate": test_integrity._answer_mandate(branch, t.id),
        "zones_mandate": zones._answer_zones_mandate(branch, t.id),
        "outcome_mandates": outcome_integrity._answer_mandates(branch, t.id),
        "replacements": mandate.approved_replacements(conn, t.id),
    }


def test_ac13_note_keeps_answers_mandates_and_gate_reasons(stand):
    """Задача с указанием и близнец без него: одинаковые число и номер ANSWER, последний ANSWER в брифе test_author, мандаты, причины возврата с гейта и разбор прежних решений.

    Сценарий: у обеих задач — `reject` с одной и той же причиной, возврат
    на гейт, `approve` (первая с `--note`), эскалация и ответ `answer`.
    Число ANSWER — 1, номер последнего — 1, причины возврата —
    `[причина]` у обеих; исходы проверок мандатов и `approved_replacements`
    совпадают; бриф test_author первой задачи несёт текст и путь `ANSWER-1.md`
    её ответа, как у близнеца.

    Ловит мутацию: указание кладётся в ссылку документов файлом
    `ANSWER-n.md` — число и номер ANSWER первой задачи 2, в брифе последний
    ANSWER — указание; запись указания пишется действием `state ->
    spec_writing` от `operator` либо её текст читается узлами мандатов —
    причины возврата или мандаты расходятся с близнецом.
    """
    reason = f"Причина возврата {base.word(stand, 10)}"
    tasks = [base.new_task(stand), base.new_task(stand)]
    for t in tasks:
        ok, out = base.cli("reject", t.id, reason)
        assert base.state(stand, t) == "spec_writing", base.note(stand, f"предпосылка reject:\n{out}")
        base.put_doc(stand, t, "SPEC.md", base.spec_text(stand, t.id))
        store.set_state(stand.conn, t.id, "spec_gate", "analyst",
                        expected_state="spec_writing", detail="SPEC переписан")
        store.record_fixation(stand.conn, t.id)
    noted, twin = tasks
    _ok, out = base.approve_note(stand, noted, base.note_text(stand))
    assert base.state(stand, noted) == "tests_writing", base.note(stand, f"approve --note:\n{out}")
    _ok, out = base.approve_plain(stand, twin)
    assert base.state(stand, twin) == "tests_writing", base.note(stand, f"approve:\n{out}")
    replies = [base.escalate_and_answer(stand, t)[1] for t in tasks]

    got, plain = facts(stand, noted), facts(stand, twin)
    briefs = [base.role_brief(stand, t) for t in tasks]

    why = base.note(stand, f"с указанием: {got}\nбез: {plain}")
    assert got["answer_count"] == 1 and got["latest_answer"] == 1, why
    assert got["gate_reasons"] == [reason], why
    assert got == plain, why
    for t, reply, text in zip(tasks, replies, briefs):
        assert reply in text, base.note(stand, f"бриф {t.id}:\n{text}")
        assert f"{t.id}/ANSWER-1.md" in text, base.note(stand, f"бриф {t.id}:\n{text}")
