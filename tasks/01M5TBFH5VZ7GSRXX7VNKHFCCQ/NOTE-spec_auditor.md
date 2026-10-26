# Записка spec_auditor — 01M5TBFH5VZ7GSRXX7VNKHFCCQ (визит 4, SPEC sha 5a7c3572)

## Выяснено
- Ветка задачи по-прежнему без Э1 (нет orchestrator/board.py): сверка по `git -C <wt> show origin/main:<файл>`; main = 7f37c6dd7 (Э1 смержен).
- Все ссылки SPEC на строки main подтвердились: report.py:48/565/596/1378/1428/1440, board.py:34/39/123, catalog.py:694 (вызов _ensure_task_worktree)/738/786, fsm.py:1070, canary_drive.py:54, targets.py:289-294, test_report.py:208..260, board_model.py:141/202/222/266/269.
- E1 ac21 проверяет ключи карточки подмножеством (`CARD_KEYS <=`) — расширение карточки его не красит.
- watch._pin_head читает .git файлами, не subprocess — report из модели не нарушит command_report.py:417 (без git).
- canary=True в CLI не выставлен — обхода ref_required через `new` нет.

## Где остановился
- SPEC-AUDIT.md: verdict concerns (пустой ключ `--ref kaiten:` проходит ref_required; `link --remove` снимает обязательную ссылку; мелочи: порядок карточек в группе эпика, «кто записал», разбор `--ref`), status ready.

## Чего не хватило
- Ничего существенного.
