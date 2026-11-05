# Записка test_author

## Визит после ANSWER-2 (вариант B) — сделано
- AC-9 возвращён в tests/test_01m6n7cykdamakenx60cbk7vqx_people_flow.py: до отправки — ветка в origin остаётся, запись «уборка» несёт «ветка origin <ветка>: …» и «PR не тронут…», `gh pr close` не вызван; после отправки и github+operator — как в черновике ниже. Пометка `# AC-9: escalate` снята из acceptance_tests/test_mandate_files.py.
- До кода: оба теста target-human красны (gh pr close вызван / нет «PR не тронут»), github+operator зелёный. Временный стаб в cleanup.py (не закрывать PR и дописать фразу при merged_by_project_people) — AC-9/AC-10 зелёные; стаб снят, cleanup.py не изменён.
- preflight: все проверки пройдены; plank-run: 3 failed (AC-13, ждут реализации), 7 passed.

## Выяснено (прошлый визит)
- AC-9 эскалирован (пометка `# AC-9: escalate` в acceptance_tests/test_mandate_files.py): белый список отправок (orchestrator/gitcmd.py:836-841, :866-876) у любой записи с merge_gate не operator отказывает `-c` перед push и `--delete` всего, кроме refs/artifacts/<id>; уборка kill удаляет ветку именно так (cleanup.py:253-276) → «ветка origin <ветка>: удалена» до отправки недостижимо без правки gitcmd.py (только чтение по SPEC). Стенд подтвердил: GitLab target-human сейчас пишет «ветка origin …: оставлено — отказ: … глобальная опция git -c перед push». Варианты A/B/C и дефолт B — в пометке.
- Образцы стенда: tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_gate.py (Stand: RealGitSandbox, FakeGh, make_project_repo, url https на время approve/advance).
- Красный CI на гейте людей: _approve_for_project_people → ("wait") → _wait_for_branch_ci_green → _ci_confirm_red_or_flake (fsm_merge_gate.py:297-338). До реализации trigger_rerun для GitHub людей: find_run_id (gh api actions/runs) → run rerun --failed → run watch.

## Не сработало
- ls вне рабочего каталога требует подтверждения — Read/git ls-files.
- `run` в initialized_tmp_root не доходит до spawn_agent (скил роли не читается без git в config.ROOT) — утверждение «дошёл до агента» для run снято, остаётся «нет отказа поддержки».

## Где остановился
Готово, провалидировано временным стабом (снят, код чист, git status — только новые файлы tests/):
- tests/test_01m6n7cykdamakenx60cbk7vqx_pair_open.py — AC-1, AC-2;
- ..._entry_checks.py — AC-3, AC-8, AC-11;
- ..._doctor_lines.py — AC-4, AC-5;
- ..._people_flow.py — AC-6, AC-7, AC-10 (AC-9 снят до ответа);
- acceptance_tests/test_mandate_files.py — AC-12 (неизменность + прогон сторожа и пяти файлов подпроцессом), AC-13 (ast-сверка трёх файлов мандата с базой) и пометка escalate AC-9.
plank-run: 3 failed (AC-13, ждут правки по мандату), 7 passed. preflight: все проверки пройдены.
После ответа: черновик тестов AC-9 — в приложении ниже (часть «после отправки» и github+operator от ответа не зависят; «до отправки» переписать по ответу), вернуть в people_flow вместо комментария «AC-9 эскалирован», снять пометку escalate.
Карту docs/codebase-map.md не регенерировал: правку вне tests/ пульт в этом шаге откатывает.

## Чего не хватило
- Что у target-human удаление ветки в origin режет белый список отправок — в SPEC/записках этого нет; нашёл только прогоном стенда.


## Приложение: черновик тестов AC-9 (снят из tests/…_people_flow.py до ответа на эскалацию)

```python
# ------------------------------------------------------------------- AC-9


def test_ac9_kill_before_send_deletes_branch_keeps_pr(stand):
    """`kill` задачи `github` + `target-human` до отправки: ветки в `origin` нет, `gh pr close` не вызван, одна запись «уборка» несёт «ветка origin <ветка>: удалена» и «PR не тронут: MR вливают люди проекта».

    Сценарий: задача в `in_dev`; ветка задачи заведена в голом `origin`
    git-командой стенда, записи «ветка отправлена» в журнале нет. `kill`:
    задача `killed`, ветки задачи в `origin` нет, шпион `gh` не видел `pr
    close`; среди записей журнала «уборка» есть одна, несущая обе фразы.

    Ловит мутацию: уборка до отправки закрывает PR по хостингу GitHub
    (`gh pr close`, прежнее поведение); фраза «PR не тронут» не пишется или
    пишется отдельной записью без исхода удаления ветки; ветка origin не
    удаляется.
    """
    task = stand.new_task(state="in_dev", published=False)
    stand.publish_branch(task)
    branch = stand.branch(task)
    assert stand.origin_has(branch), stand.context(task, "предусловие: ветка в origin")
    out = stand.kill(task)
    where = stand.context(task, out)
    assert stand.state(task) == "killed", where
    assert not stand.origin_has(branch), where
    assert stand.gh.seen("pr", "close") == [], where
    deleted = BRANCH_DELETED.format(branch=branch)
    assert any(deleted in r and PR_UNTOUCHED in r
               for r in stand.cleanup_records(task)), where


def test_ac9_kill_after_send_keeps_branch_notes_both(stand):
    """`kill` задачи `github` + `target-human` после отправки: ветка в `origin` цела, `gh pr close` не вызван, запись «уборка» несёт прежнее «сервер проекта не тронут: ветка <ветка> отправлена» и «PR не тронут: MR вливают люди проекта».

    Сценарий: задача в `in_dev`, ветка на сервере с записью «ветка
    отправлена». `kill`: задача `killed`, ветка в `origin` есть, шпион `gh`
    не видел `pr close`; среди записей «уборка» есть одна с обеими фразами.

    Ловит мутацию: после отправки фраза «PR не тронут» не дописана к
    прежнему тексту (или прежний текст заменён ею); уборка после отправки
    удаляет ветку либо закрывает PR.
    """
    task = stand.new_task(state="in_dev")
    branch = stand.branch(task)
    out = stand.kill(task)
    where = stand.context(task, out)
    assert stand.state(task) == "killed", where
    assert stand.origin_has(branch), where
    assert stand.gh.seen("pr", "close") == [], where
    left = SERVER_LEFT.format(branch=branch)
    assert any(left in r and PR_UNTOUCHED in r
               for r in stand.cleanup_records(task)), where


@pytest.mark.parametrize("published", [False, True], ids=["до отправки", "после отправки"])
def test_ac9_github_operator_kill_closes_pr(real_git, published):
    """`kill` задачи `github` + `operator` зовёт `gh pr close` ветки задачи, как прежде.

    Сценарий: стенд `github` + `operator`; задача в `in_dev` с веткой в
    `origin` (с записью «ветка отправлена» и без неё). `kill`: шпион `gh`
    видел `pr close` с веткой задачи.

    Ловит мутацию: запрет закрытия PR поставлен по хостингу GitHub без
    признака проекта людей — `gh pr close` у записи `operator` не вызван.
    """
    stand = Stand(real_git, gate="operator")
    task = stand.new_task(state="in_dev", published=published)
    if not published:
        stand.publish_branch(task)
    branch = stand.branch(task)
    out = stand.kill(task)
    where = stand.context(task, out)
    closes = stand.gh.seen("pr", "close")
    assert closes and branch in closes[0], where


```
