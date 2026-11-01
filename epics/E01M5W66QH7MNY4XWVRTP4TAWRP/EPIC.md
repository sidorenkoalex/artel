<!-- artel-epic-row: {"id": "E01M5W66QH7MNY4XWVRTP4TAWRP", "project": "artel", "title": "Проект на GitLab с гейтом людей проекта (ADR-0029)", "goal": "Пульт ведёт задачи проекта на GitLab до открытого MR: адаптер хостинга, ветка по ключу трекера, гейт target-human с awaiting_human и mr-sync, полный набор из CI, профиль проверок; первая живая задача — после Б2", "envelope_usd": 600.0, "state": "open", "outcome": null, "created_at": "2026-10-26 13:25:40Z", "closed_at": null, "parallel": 3} -->
# Эпик E01M5W66QH7MNY4XWVRTP4TAWRP: Проект на GitLab с гейтом людей проекта (ADR-0029)

- Проект: artel
- Состояние: open
- Цель: Пульт ведёт задачи проекта на GitLab до открытого MR: адаптер хостинга, ветка по ключу трекера, гейт target-human с awaiting_human и mr-sync, полный набор из CI, профиль проверок; первая живая задача — после Б2
- Конверт: $600.00
- Итог: —
- Заведён: 2026-10-26 13:25:40Z
- Закрыт: —

## Задачи

| задача | название | состояние | closed_as |
|---|---|---|---|
| 01M5W27CY7K7NR9347NKD8F0NX | GitLab А0: неподдержанный хостинг или гейт людей проекта — именованный отказ до первой задачи | done | — |
| 01M5W670PHF08VPZWDRM5BY56W | GitLab А1: адаптер хостинга — общий интерфейс, реализация GitLab, проверочная команда только на чтение | killed | divided |
| 01M5W67E0AYGKF03SEM6E2AQX2 | GitLab Б1: ветка по ключу трекера, автор и шаблон коммита, сжатие и перебазирование, единая точка отправки | killed | divided |
| 01M5WCXBM7WCMRWCBWNCHMAR3T | GitLab А1.1: интерфейс адаптера, реализация GitLab, подключение ci | done | — |
| 01M5WCXBR9K8CN586W1AP3ZN6Q | GitLab А1.2: doctor, проверочная команда forge-probe и песочница без живого HTTP | done | — |
| 01M5WDB7F14SQ30QVWJY2XYBG2 | GitLab Б1.1: поля записи, ветка по шаблону, единая точка отправки с журналом и белым списком | done | — |
| 01M5WDB7JY0VJGHVKCABA2QC5T | GitLab Б1.2: автор, соавтор и трейлер пульта, сжатие и перебазирование на входе в verifying, перезапись своей ветки | done | — |
| 01M5XX9PW3K206Q3EKQCT649QF | GitLab В1: источник полного набора full_suite (local\|ci\|both), исходы из отчёта задания CI | killed | divided |
| 01M5XXA2HY73D3WTXDR19Z5SWW | GitLab Б2.1: гейт мержа target-human — MR вместо слияния, состояние awaiting_human | killed | divided |
| 01M5XZ9Z68V75VXF5Z66C708T4 | Б2.1а: состояние awaiting_human и его учёт в перечнях пульта | done | — |
| 01M5XZ9Z68XE2EKPDHYCAK25KF | Б2.1б: гейт мержа target-human открывает MR, черновой MR и max_in_flight через forge | done | — |
| 01M5XZSKK8GZTECA2KWAFHE029 | GitLab В1.1: источник полного набора full_suite (local\|ci\|both) на приёмке | in_dev | — |
| 01M5XZSKK8H096FD3CPN05BQNM | GitLab В1.2: гейт неослабления по исходам из отчётов задания CI | in_dev | — |
| 01M69W4J5DSBFYS8A0FG71N93K | Предпосылка теста fetch базы рабочей копии не зависит от версии git (git 2.56 на раннере CI) | done | — |
| 01M6AB4VE2R0Q2V5D4MMJGNGH7 | GitLab Б2.2: команда mr-sync — сверка MR и нахождения правки в base, закрытие done по подтверждению Оператора | merge_gate | — |
