# Записка spec_auditor

## Выяснено
- Визит 4 (spec_sha 372571c4…): 9 решений третьего возврата в SPEC отражены (AC-3, AC-5, AC-16, AC-26 снят/перенумерован, AC-29, review.py в зонах, canary.py:1384, удаление refs/artifacts/<id>, строка матрицы «ок при условии»).
- Номера строк подтверждены: fsm_advance.py:771/776/816/821/831/833/478, pull.py:462/535/543/575/589/762, fsm.py:236/1067/1070-1073/1577, fsm_merge_gate.py:701/727, github_adapter.py:166/211/226/241, gitcmd.py:37/86/164/341/413/441/469, checkpoint.py:962-966/1882, amend.py:799/826, snapshot.py:272, review.py:245/864-866, catalog.py:582/912/1030-1033.
- Все отправки идут через gitcmd (artifact_branch._git :158, cleanup._bounded :253 → in_repo); прямой subprocess git вне gitcmd — только plank_helper.py:71 (не отправка).
- Рубеж переделки ревью отличает подтяжку по теме коммита `<id>: подтяжка ` (advance_gates/review.py:84,120), не по автору — смена автора merge-коммита его не ломает.
- forge.py / token_user в коде нет; ADR-0029 п.8 перечень интерфейса адаптера token_user не называет.
- ADR-0029 п.1: на approve merge_gate target-human подтяжка «тем же методом»; SPEC AC-31 фиксирует merge на гейте мержа (решение гейта №1 п.6).
- fsm.py:1067 эпик (`--as-epic`) заводится до частей — атомарность деления AC-11/12 эпик не покрывает.

## Не сработало
- Составные команды с cd+git/grep песочница не пропускает — git grep из рабочего каталога и python3 -c.

## Где остановился
SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
Нет — факты сходятся с кодом.
