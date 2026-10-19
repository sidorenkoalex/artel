"""Метрика «круги до кода»: блок «Круги до кода» HTML `report` и оповещение
`rounds` цикла `auto` по порогу аудитов SPEC и эскалаций.

Группа: долгоживущий
Красен до реализации: модуля `orchestrator/rounds.py`, блока «Круги до кода» в `report` и сверки порога в цикле `auto` ещё нет — блок не находится в HTML отчёта, оповещения `rounds` и записи журнала «круги до кода: оповещение» нет.

Публичная поверхность. Подсчёт по журналу задачи читается из блока отчёта
(`report.cmd_report` -> `.artel/report.html`, связка «БД песочницы —
команда `report` — файл отчёта»): блок — от заголовка «Круги до кода» до
следующего заголовка того же или старшего уровня; строка задачи — `<tr>`,
в тексте которого есть её id; столбец ищется по слову заголовка
(«задач», «проект», «аудит», «возврат», «эскалац», «ревью», «расход»), а не
по номеру; составные столбцы — «X / Y»; итог — текст блока после
последней строки задачи (блок «завершается строкой итога»); выделение строки
— разметка её тегов (без id задачи и цифр) отличается от разметки строки
задачи ниже обоих порогов.

Цикл — `auto.cmd_auto(<id>)` на лёгкой песочнице переходов (связка «цикл
`auto` — журнал `steps` — таблица `alerts`»): подменённый `fsm.cmd_advance`
переводит задачу по карте состояний сценария, только когда с последнего
входа в состояние журнал несёт завершённый шаг роли; подменённый
`runner.cmd_run` журналирует `agent run finished` под ролью шага и, если так
задано сценарием, сам уводит задачу в `escalated` (эскалация изнутри шага).

Случайные входы (числа событий, суммы, порядок записей) — от зерна, которое
печатается и входит в текст провала.
"""
import os
import random
import re
import signal
from datetime import datetime, timedelta, timezone
from importlib import util as importlib_util
from unittest import mock

from orchestrator import alerts, auto, config, fsm, report, runner, store
from tests.sandbox import InitializedTmpRootTest, LightTransitionSandbox, capture

BLOCK_TITLE = "Круги до кода"
AUDIT = "state -> spec_audit"
ESCALATED = "state -> escalated"
WRITING = "state -> spec_writing"
AUDIT_RETURN = "аудит SPEC: возврат аналитику по fail"
GATE_RETURN_PREFIX = "возврат из spec_gate: "
ESCALATION_RESOLVED = "эскалация разрешена, продолжаем"
AUDIT_FAIL_DETAIL = "аудит SPEC: вердикт fail, возврат 1 из 3"
KNOWN = "agent cost KNOWN"
PARTIAL = "agent cost PARTIAL"
MARK = "круги до кода: оповещение"
ROUNDS_SOURCE = "rounds"
FINISHED = "agent run finished"
EXTERNAL = "sled"

#: Слово заголовка -> ключ столбца; «возврат» проверяется раньше «аудит»:
#: заголовок столбца возвратов вправе назвать «возвраты аудита».
COLUMNS = (("returns", "возврат"), ("audits", "аудит"),
           ("escalations", "эскалац"), ("review", "ревью"),
           ("cost", "расход"), ("project", "проект"), ("task", "задач"))


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def numbers(text: str) -> list:
    return [float(x.replace(",", "."))
            for x in re.findall(r"\d+(?:[.,]\d+)?", text.replace("$", ""))]


def rounds_block(html: str) -> str | None:
    """HTML блока «Круги до кода»: от его заголовка до следующего заголовка
    того же или старшего уровня (либо конца `<main>`/документа)."""
    head = re.search(r"<h([1-6])\b[^>]*>[^<]*" + BLOCK_TITLE, html)
    if head is None:
        return None
    level = int(head.group(1))
    rest = html[head.end():]
    stop = re.search(rf"<h[1-{level}]\b|</main>", rest)
    return html[head.start():head.end() + (stop.start() if stop else len(rest))]


def cells(row: str) -> list:
    return [strip(c) for _, c in re.findall(r"<t([hd])\b[^>]*>(.*?)</t\1>",
                                            row, re.S)]


def column_map(header: list) -> dict:
    mapping = {}
    for index, text in enumerate(header):
        low = text.lower()
        for key, word in COLUMNS:
            if word in low and key not in mapping:
                mapping[key] = index
                break
    return mapping


def has_id(text: str, task_id: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(task_id)}(?!\w)", text) is not None


def task_rows(block: str, task_ids) -> dict:
    """id -> {html, start, end, cells, map} по строкам `<tr>` блока; карта
    столбцов — от ближайшей предшествующей строки заголовка."""
    rows, mapping = {}, None
    for m in re.finditer(r"<tr\b[^>]*>.*?</tr>", block, re.S):
        row = m.group(0)
        text = strip(row)
        hit = [t for t in task_ids if has_id(text, t)]
        if not hit:
            low = text.lower()
            if "эскалац" in low and "медиан" not in low:
                mapping = column_map(cells(row))
            continue
        rows[hit[0]] = {"html": row, "start": m.start(), "end": m.end(),
                        "cells": cells(row), "map": mapping or {}}
    return rows


def cell(info: dict, key: str) -> str:
    index = info["map"].get(key)
    if index is None or index >= len(info["cells"]):
        raise AssertionError(f"столбец {key!r} не найден: карта {info['map']}, "
                             f"ячейки {info['cells']}")
    return info["cells"][index]


def cell_int(info: dict, key: str) -> int:
    found = re.search(r"\d+", cell(info, key))
    if found is None:
        raise AssertionError(f"в столбце {key!r} нет числа: {info['cells']}")
    return int(found.group(0))


def cell_pair(info: dict, key: str) -> tuple:
    text = cell(info, key).replace("$", "")
    found = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", text)
    if found is None:
        raise AssertionError(f"столбец {key!r} не в форме «X / Y»: {text!r}")
    return tuple(float(g.replace(",", ".")) for g in found.groups())


def skeleton(row: str, task_id: str) -> list:
    tags = re.findall(r"<[^>]+>", row.replace(task_id, "ID"))
    return [re.sub(r"\d", "#", tag) for tag in tags]


def known_detail(usd: float) -> str:
    """Деталь «agent cost KNOWN» в формате `spend.charge_step`."""
    return (f"попытка 1/1, model=alfa-model-x, provider=alfa-cli: "
            f"стоимость ${usd:.4f}, токенов 60, источник=факт CLI, "
            f"разбивка по видам: input=11, output=13, cache_write=17, "
            f"cache_read=19 | actual_usd={usd!r}")


def old_created_at(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)
            ).strftime("%Y-%m-%d %H:%M:%SZ")


def report_html() -> str:
    capture(report.cmd_report)
    return (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")


class _RoleEnvClean:
    """Отчёт строится вне окружения роли (как в `tests/test_report_project_label.py`)."""

    def clean_role_env(self):
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)


class RoundsReportSandbox(_RoleEnvClean, InitializedTmpRootTest):
    """Проинициализированная БД без задач: каждая задача сценария заводится
    тестом, её журнал — записями `store.journal` в случайном порядке."""

    def setUp(self):
        super().setUp()
        self.clean_role_env()
        self.conn = store.db()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)

    def note(self, extra: str) -> str:
        return f"зерно: {self.seed}; {extra}"

    def add_task(self, task_id: str, target: str = config.DEFAULT_TARGET,
                 review_iters: int = 0) -> None:
        store.insert_task(self.conn, task_id, "Круги до кода", "in_dev",
                          f"task/{task_id.lower()}-krugi", target, 25.0)
        if review_iters:
            store.update_task(self.conn, task_id, review_iters=review_iters)

    def journal(self, task_id: str, events: list) -> None:
        events = list(events)
        self.rng.shuffle(events)
        for actor, action, detail in events:
            store.journal(self.conn, task_id, actor, action, detail)

    def counted(self, task_id: str, audits=0, audit_returns=0, gate_returns=0,
                escalations=0, before=(), after=()) -> None:
        """Журнал задачи: заданные числа событий каждого вида плюс шум, не
        входящий ни в один столбец; `before` — суммы шагов analyst/
        spec_auditor, `after` — суммы шагов developer."""
        events = []
        events += [("fsm", AUDIT, "аудит SPEC: вход")] * audits
        events += [("fsm", AUDIT_RETURN, "вердикт fail; возврат по fail 1 из 3")] * audit_returns
        events += [("operator", WRITING, f"{GATE_RETURN_PREFIX}уточни AC-{i}")
                   for i in range(gate_returns)]
        events += [("fsm", ESCALATED, "вопросы аналитика")] * escalations
        actors = ("analyst", "spec_auditor")
        events += [(actors[i % 2], KNOWN, known_detail(usd))
                   for i, usd in enumerate(before)]
        events += [("developer", KNOWN, known_detail(usd)) for usd in after]
        events += [("fsm", "state -> spec_gate", ""), ("fsm", "state -> in_dev", ""),
                   ("fsm", "аудит SPEC: вход", "sha=abc"),
                   ("fsm", "аудит SPEC: вердикт", "pass")]
        self.journal(task_id, events)

    def block(self) -> str:
        html = report_html()
        block = rounds_block(html)
        self.assertIsNotNone(block, self.note(f"в отчёте нет блока «{BLOCK_TITLE}»"))
        return block

    def rows(self, block: str, task_ids) -> dict:
        rows = task_rows(block, task_ids)
        missing = [t for t in task_ids if t not in rows]
        self.assertFalse(missing, self.note(
            f"нет строк задач {missing} в блоке:\n{strip(block)}"))
        return rows


class RoundsCountTest(RoundsReportSandbox):

    def test_ac1_counts_audits_audit_returns_escalations_review_iters(self):
        """Столбцы подсчёта по случайному журналу двух задач.

        Сценарий: модуль `orchestrator.rounds` находится; у двух задач
        случайное число записей `state -> spec_audit`, `аудит SPEC: возврат
        аналитику по fail`, `state -> escalated` и случайный
        `tasks.review_iters`, вперемешку с шумом (`аудит SPEC: вход`,
        вердикт аудита, `state -> spec_gate`/`in_dev`). В строке каждой
        задачи блока — её собственные числа аудитов SPEC, возвратов аудита
        (первое число «возвратов»), эскалаций и итераций ревью.

        Ловит мутацию: аудиты считаются по записи «аудит SPEC: вход» вместо
        `state -> spec_audit` — у задачи на одну запись больше; подсчёт не
        фильтрует журнал по задаче — числа двух задач складываются; итерации
        ревью берутся константой/из другого поля — расходятся с
        `review_iters`.
        """
        self.assertIsNotNone(importlib_util.find_spec("orchestrator.rounds"),
                             "модуля orchestrator/rounds.py нет")
        expected = {}
        for task_id in ("R0001", "R0002"):
            want = {"audits": self.rng.randint(0, 5),
                    "audit_returns": self.rng.randint(0, 4),
                    "escalations": self.rng.randint(0, 4),
                    "review": self.rng.randint(0, 6)}
            expected[task_id] = want
            self.add_task(task_id, review_iters=want["review"])
            self.counted(task_id, audits=want["audits"],
                         audit_returns=want["audit_returns"],
                         escalations=want["escalations"])
        block = self.block()
        rows = self.rows(block, expected)
        for task_id, want in expected.items():
            info = rows[task_id]
            got = {"audits": cell_int(info, "audits"),
                   "audit_returns": int(cell_pair(info, "returns")[0]),
                   "escalations": cell_int(info, "escalations"),
                   "review": cell_int(info, "review")}
            with self.subTest(task=task_id):
                self.assertEqual(got, want, self.note(f"строка {info['cells']}"))

    def test_ac2_gate_return_counts_only_spec_gate_return_detail(self):
        """Возврат с гейта SPEC — только `state -> spec_writing` с detail «возврат из spec_gate:».

        Сценарий: в журнале задачи случайное число `state -> spec_writing`
        с detail «возврат из spec_gate: …», с detail «аудит SPEC: вердикт
        fail…» и с detail «эскалация разрешена, продолжаем», запись `state
        -> spec_audit` с detail «возврат из spec_gate: …» и случайное
        (другое) число возвратов аудита; у соседней задачи свои возвраты с
        гейта. «Возвраты» строки задачи — «возвраты аудита / возвраты с
        гейта SPEC» ровно этих чисел.

        Ловит мутацию: возвратом с гейта считается любой `state ->
        spec_writing` — второе число вырастает на возвраты по fail и снятия
        эскалации; отбор только по detail без действия — засчитан `state ->
        spec_audit`; возвраты аудита и с гейта слиты в одно число — оба
        числа «X / Y» равны.
        """
        gate = self.rng.randint(1, 3)
        audit_returns = self.rng.choice([n for n in range(0, 5) if n != gate])
        self.add_task("R0001")
        self.counted("R0001", audit_returns=audit_returns, gate_returns=gate)
        self.journal("R0001",
                     [("fsm", WRITING, AUDIT_FAIL_DETAIL)] * self.rng.randint(1, 3)
                     + [("operator", WRITING, ESCALATION_RESOLVED)] * self.rng.randint(1, 3)
                     + [("operator", AUDIT, f"{GATE_RETURN_PREFIX}не туда")])
        self.add_task("R0002")
        self.counted("R0002", gate_returns=self.rng.randint(1, 4))
        info = self.rows(self.block(), ["R0001", "R0002"])["R0001"]
        self.assertEqual(cell_pair(info, "returns"),
                         (float(audit_returns), float(gate)),
                         self.note(f"строка {info['cells']}"))

    def test_ac3_cost_before_plank_and_total_of_this_task(self):
        """Расход «до планки / всего» — `actual_usd` записей `agent cost KNOWN` этой задачи.

        Сценарий: у задачи случайные суммы шагов analyst и spec_auditor
        (до планки) и developer/reviewer (только во «всего»), запись
        `agent cost PARTIAL` analyst с `actual_usd`, запись `agent cost
        KNOWN` analyst без `actual_usd` (разбор даёт `None`); у соседней
        задачи свои `agent cost KNOWN` analyst и developer. Столбец расхода
        строки задачи — её сумма analyst+spec_auditor / сумма всех её KNOWN.

        Ловит мутацию: до планки входит любая роль — первое число равно
        второму; сумма не фильтрует по задаче — в неё попадают суммы
        соседней; засчитана PARTIAL-запись или стоимость читается по
        «стоимость $…» без разбора — сумма больше.
        """
        cents = lambda: self.rng.randint(1, 999) / 100  # noqa: E731
        before = [cents() for _ in range(self.rng.randint(2, 4))]
        after = [cents() for _ in range(self.rng.randint(1, 3))]
        self.add_task("R0001")
        self.counted("R0001", before=before, after=after)
        self.journal("R0001", [
            ("reviewer", KNOWN, known_detail(1.11)),
            ("analyst", PARTIAL, known_detail(7.77)),
            ("analyst", KNOWN, "попытка 1/1: стоимость не разобрана")])
        self.add_task("R0002")
        self.counted("R0002", before=[cents()], after=[cents()])
        info = self.rows(self.block(), ["R0001", "R0002"])["R0001"]
        got = tuple(round(v, 2) for v in cell_pair(info, "cost"))
        want = (round(sum(before), 2), round(sum(before) + sum(after) + 1.11, 2))
        self.assertEqual(got, want, self.note(f"суммы {before} + {after}; "
                                              f"строка {info['cells']}"))


class RoundsBlockTest(RoundsReportSandbox):

    def test_ac4_block_table_columns_window_and_returns_pair(self):
        """Таблица блока: столбцы, задачи окна `OPERATOR_WINDOW_DAYS`, пара возвратов.

        Сценарий: задача окна с разными числами возвратов аудита и с гейта
        SPEC и задача, созданная раньше окна на случайное число дней
        (`created_at`). Заголовок таблицы называет задачу, проект, аудиты
        SPEC, возвраты, эскалации, итерации ревью и расход; строка задачи
        окна показывает «возвраты аудита / возвраты с гейта» её числами;
        id задачи старше окна в блоке нет.

        Ловит мутацию: окно не применяется (или считается по `updated_at`,
        которое у старой задачи свежее) — старая задача попадает в таблицу;
        столбец «возвраты» показывает одно число или пару в обратном
        порядке — пара не совпадает.
        """
        audit_returns = self.rng.randint(2, 4)
        gate = self.rng.randint(0, audit_returns - 1)
        self.add_task("R0001")
        self.counted("R0001", audits=1, audit_returns=audit_returns,
                     gate_returns=gate)
        self.add_task("R0009")
        self.counted("R0009", audits=4, escalations=3)
        store.update_task(self.conn, "R0009", created_at=old_created_at(
            report.OPERATOR_WINDOW_DAYS + self.rng.randint(1, 30)))
        block = self.block()
        self.assertFalse(has_id(strip(block), "R0009"),
                         self.note(f"задача старше окна в блоке:\n{strip(block)}"))
        info = self.rows(block, ["R0001"])["R0001"]
        for key in ("task", "project", "audits", "returns", "escalations",
                    "review", "cost"):
            with self.subTest(column=key):
                self.assertIn(key, info["map"], self.note(
                    f"заголовок таблицы без столбца {key}: {info['map']}"))
        self.assertEqual(cell_pair(info, "returns"),
                         (float(audit_returns), float(gate)),
                         self.note(f"строка {info['cells']}"))

    def test_ac5_rows_over_threshold_are_highlighted(self):
        """Выделены строки с аудитами SPEC ≥ 3 и с эскалациями ≥ 2, строка ниже порогов — нет.

        Сценарий: задачи ровно на пороге аудитов (3 аудита, 0 эскалаций),
        ровно на пороге эскалаций (0 аудитов, 2 эскалации), случайно выше
        порога, ниже обоих порогов (2 и 1) и без событий. Разметка тегов
        строк на пороге и выше отличается от разметки строки без событий;
        строка ниже порогов размечена так же, как строка без событий.

        Ловит мутацию: сравнение `>` вместо `≥` — строки ровно на пороге не
        выделены; пороги перепутаны местами (аудиты ≥ 2, эскалации ≥ 3) —
        выделена строка 2/1 и не выделена 0/2; выделение только по одной
        ветви — строка другой ветви размечена как обычная.
        """
        cases = {"R0001": (3, 0), "R0002": (0, 2),
                 "R0003": (self.rng.randint(3, 6), self.rng.randint(0, 1)),
                 "R0004": (self.rng.randint(0, 2), self.rng.randint(2, 4)),
                 "R0005": (2, 1), "R0006": (0, 0)}
        for task_id, (audits, escalations) in cases.items():
            self.add_task(task_id)
            self.counted(task_id, audits=audits, escalations=escalations)
        rows = self.rows(self.block(), cases)
        plain = skeleton(rows["R0006"]["html"], "R0006")
        for task_id, (audits, escalations) in cases.items():
            if task_id == "R0006":
                continue
            hot = audits >= 3 or escalations >= 2
            got = skeleton(rows[task_id]["html"], task_id)
            with self.subTest(task=task_id, audits=audits, escalations=escalations):
                if hot:
                    self.assertNotEqual(got, plain, self.note(
                        f"строка не выделена: {rows[task_id]['html']}"))
                else:
                    self.assertEqual(got, plain, self.note(
                        f"строка ниже порогов выделена: {rows[task_id]['html']}"))

    def test_ac6_totals_row_median_and_mean_of_every_number(self):
        """Итог блока — медиана и среднее каждого числа таблицы.

        Сценарий: четыре задачи (порядок заведения случайный) с наборами
        чисел, у которых медиана (среднее двух средних значений) и среднее
        различаются по каждому столбцу и все четырнадцать значений итога
        различны: аудиты 0,1,2,5; возвраты аудита 0,2,3,11; возвраты с
        гейта 0,3,4,11; эскалации 0,5,6,9; итерации ревью 0,6,7,15; расход
        до планки $1,$7,$8,$24; расход всего $2,$8,$9,$29. Текст блока после
        последней строки задачи называет медиану и среднее и несёт каждое
        из ожидаемых значений.

        Ловит мутацию: медиана при чётном числе задач берётся верхним или
        нижним средним элементом (2 вместо 1.5 у аудитов) либо подменена
        средним; итог не считает один из столбцов (возвраты с гейта, расход
        до планки) — его медианы 3.5/7.5 нет в итоге.
        """
        columns = {"audits": (0, 1, 2, 5), "audit_returns": (0, 2, 3, 11),
                   "gate_returns": (0, 3, 4, 11), "escalations": (0, 5, 6, 9),
                   "review": (0, 6, 7, 15), "before": (1, 7, 8, 24),
                   "total": (2, 8, 9, 29)}
        expected = []
        for values in columns.values():
            a, b, c, d = values
            expected += [(b + c) / 2, (a + b + c + d) / 4]
        order = list(range(4))
        self.rng.shuffle(order)
        ids = []
        for n, i in enumerate(order):
            task_id = f"R000{n + 1}"
            ids.append(task_id)
            self.add_task(task_id, review_iters=columns["review"][i])
            before = columns["before"][i]
            self.counted(task_id, audits=columns["audits"][i],
                         audit_returns=columns["audit_returns"][i],
                         gate_returns=columns["gate_returns"][i],
                         escalations=columns["escalations"][i],
                         before=[float(before)],
                         after=[float(columns["total"][i] - before)])
        block = self.block()
        rows = self.rows(block, ids)
        tail = strip(block[max(r["end"] for r in rows.values()):])
        self.assertIn("медиан", tail.lower(), self.note(f"итог: {tail!r}"))
        self.assertIn("средн", tail.lower(), self.note(f"итог: {tail!r}"))
        got = [round(v, 2) for v in numbers(tail)]
        for value in expected:
            with self.subTest(value=value):
                self.assertIn(round(value, 2), got, self.note(f"итог: {tail!r}"))

    def test_ac7_block_is_split_by_project(self):
        """При задачах двух проектов у каждого проекта свои строки и свой итог.

        Сценарий: две задачи артели (1 и 3 аудита SPEC) и одна задача
        внешнего проекта (5 аудитов), прочих событий нет. Строки артели
        идут раньше строк внешнего проекта (артель первой, как в
        разбивке по проекту прочих блоков); между последней строкой
        артели и первой строкой внешнего проекта — итог артели (2 — медиана
        и среднее её аудитов), после строки внешнего проекта — его итог (5);
        общего итога по трём задачам (3) ни там, ни там нет.

        Ловит мутацию: блок не разбит — один общий итог после всех строк с
        медианой 3, итога артели между группами нет; группы в обратном
        порядке — строка внешнего проекта раньше строк артели.
        """
        for task_id, target, audits in (("R0001", config.DEFAULT_TARGET, 1),
                                        ("R0002", config.DEFAULT_TARGET, 3),
                                        ("R0003", EXTERNAL, 5)):
            self.add_task(task_id, target=target)
            self.counted(task_id, audits=audits)
        block = self.block()
        rows = self.rows(block, ["R0001", "R0002", "R0003"])
        artel_end = max(rows["R0001"]["end"], rows["R0002"]["end"])
        external = rows["R0003"]
        self.assertLess(artel_end, external["start"], self.note(
            f"строки внешнего проекта раньше строк артели:\n{strip(block)}"))
        artel_tail = numbers(strip(block[artel_end:external["start"]]))
        external_tail = numbers(strip(block[external["end"]:]))
        self.assertIn(2.0, artel_tail, self.note(
            f"нет итога артели между группами: {artel_tail}\n{strip(block)}"))
        self.assertNotIn(3.0, artel_tail, self.note(f"итог артели: {artel_tail}"))
        self.assertIn(5.0, external_tail, self.note(
            f"нет итога внешнего проекта: {external_tail}"))
        self.assertNotIn(3.0, external_tail, self.note(
            f"итог внешнего проекта: {external_tail}"))


# ----------------------------------------------------------------- цикл auto

class MapAdvance:
    """Подмена `fsm.cmd_advance`: переход по карте `next[id][состояние]`,
    только когда после последнего входа в состояние журнал несёт
    завершённый шаг роли (как настоящий advance по готовому артефакту)."""

    def __init__(self, conn):
        self.conn = conn
        self.next: dict = {}

    def __call__(self, task_id, *args, **kwargs) -> bool:
        task_id = store.resolve_task_id(self.conn, task_id)
        state = store.get_task(self.conn, task_id)["state"]
        target = self.next.get(task_id, {}).get(state)
        if target is None or not role_finished_since_entry(self.conn, task_id):
            return False
        store.set_state(self.conn, task_id, target, "fsm",
                        expected_state=state, detail="сценарий теста")
        return False


def role_finished_since_entry(conn, task_id: str) -> bool:
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] == FINISHED:
            return True
        if row["action"].startswith("state -> "):
            return False
    return False


class ScriptedStep:
    """Подмена `runner.cmd_run`: журналирует `agent run finished` под ролью
    шага; в состоянии `escalate_in[id]` шаг сам уводит задачу в
    `escalated` (эскалация изнутри шага роли)."""

    def __init__(self, conn, cap: int):
        self.conn = conn
        self.cap = cap
        self.calls = 0
        self.escalate_in: dict = {}

    def __call__(self, task_id, *args, **kwargs) -> None:
        task_id = store.resolve_task_id(self.conn, task_id)
        self.calls += 1
        if self.calls > self.cap:
            raise AssertionError(f"цикл не остановился: шагов роли больше {self.cap}")
        t = store.get_task(self.conn, task_id)
        store.journal(self.conn, task_id, runner.step_role(t), FINISHED,
                      "rc=0, тестовая заглушка шага роли")
        if self.escalate_in.get(task_id) == t["state"]:
            store.set_state(self.conn, task_id, "escalated", "fsm",
                            expected_state=t["state"], detail="шаг роли упал")


class RoundsAutoSandbox(_RoleEnvClean, LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        self.clean_role_env()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.advance = MapAdvance(self.conn)
        self.step = ScriptedStep(self.conn, 2 * config.AUTO_MAX_STEPS)
        for target, attr, value in ((fsm, "cmd_advance", self.advance),
                                    (runner, "cmd_run", self.step)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.counter = 0

    def note(self, extra: str) -> str:
        return f"зерно: {self.seed}; {extra}"

    def task_with_history(self, audits: int, escalations: int) -> str:
        """Задача в `spec_writing` с заведённым ТЗ (роль analyst) и прошлым
        журналом: `audits` входов в аудит SPEC, `escalations` эскалаций,
        случайные возвраты аудита и снятия эскалаций; последний переход —
        возврат в `spec_writing`."""
        self.counter += 1
        task_id = f"{self.TASK[:-6]}{self.counter:06d}"
        store.insert_task(self.conn, task_id, "Круги до кода", "spec_writing",
                          f"task/{task_id.lower()}-krugi",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "TZ.md").write_text("# ТЗ сценария\n", encoding="utf-8")
        history = ([("fsm", AUDIT, "аудит SPEC: вход")] * audits
                   + [("fsm", ESCALATED, "вопросы аналитика")] * escalations
                   + [("operator", WRITING, ESCALATION_RESOLVED)] * escalations
                   + [("fsm", AUDIT_RETURN, "возврат")] * self.rng.randint(0, audits))
        self.rng.shuffle(history)
        history.append(("fsm", WRITING, AUDIT_FAIL_DETAIL))
        for actor, action, detail in history:
            store.journal(self.conn, task_id, actor, action, detail)
        self.assertEqual(runner.step_role(store.get_task(self.conn, task_id)),
                         "analyst", self.note("роль задачи сценария"))
        return task_id

    def run_auto(self, task_id: str, path: dict, escalate_in: str | None = None) -> str:
        self.advance.next[task_id] = dict(path)
        if escalate_in is not None:
            self.step.escalate_in[task_id] = escalate_in
        return capture(auto.cmd_auto, task_id)

    def rounds_alerts(self, task_id: str | None = None) -> list:
        rows = self.conn.execute(
            "SELECT * FROM alerts WHERE source = ? ORDER BY id",
            (ROUNDS_SOURCE,)).fetchall()
        if task_id is None:
            return rows
        return [r for r in rows if has_id(r["message"] or "", task_id)]

    def marks(self, task_id: str) -> list:
        return [r for r in store.task_steps(self.conn, task_id) if r["action"] == MARK]

    def assert_one_alert(self, task_id: str, audits: int, escalations: int,
                         out: str) -> None:
        found = self.rounds_alerts(task_id)
        self.assertEqual(len(found), 1, self.note(
            f"оповещений rounds {len(found)}: {[dict(r) for r in found]}\n{out}"))
        row = found[0]
        self.assertEqual(row["kind"], "warning", self.note("kind"))
        self.assertEqual(row["target"], config.DEFAULT_TARGET,
                         self.note("target — проект задачи"))
        self.assertEqual(row["message"],
                         f"задача {task_id}: {audits} аудитов SPEC, "
                         f"{escalations} эскалаций до кода — ТЗ недоопределено?",
                         self.note("текст оповещения"))
        self.assertEqual(len(self.marks(task_id)), 1, self.note(
            f"записей «{MARK}» не одна\n{out}"))


class RoundsAlertTest(RoundsAutoSandbox):

    def test_ac8_third_spec_audit_entry_raises_one_rounds_alert(self):
        """Третий вход в аудит SPEC при одной эскалации поднимает одно оповещение `rounds`.

        Сценарий: у задачи в прошлом журнале два входа в аудит SPEC и одна
        эскалация; `auto` из `spec_writing` проводит её через шаг analyst
        в `spec_audit` (третий вход) и через шаг spec_auditor в
        `spec_gate`. После вызова — ровно одно оповещение `rounds` `warning`
        с target проекта задачи и текстом «задача <id>: 3 аудитов SPEC, 1
        эскалаций до кода — ТЗ недоопределено?» и одна запись «круги до
        кода: оповещение» в журнале задачи.

        Ловит мутацию: порог аудитов сравнивается `>` — на третьем входе
        оповещения нет; target — id задачи, как у оповещения внимания;
        сверка выполняется на каждом шаге без признака однократности — в
        `spec_gate` поднимается второе оповещение или вторая запись.
        """
        task_id = self.task_with_history(audits=2, escalations=1)
        out = self.run_auto(task_id, {"spec_writing": "spec_audit",
                                      "spec_audit": "spec_gate"})
        self.assertEqual(store.get_task(self.conn, task_id)["state"], "spec_gate",
                         self.note(out))
        self.assert_one_alert(task_id, 3, 1, out)

    def test_ac9_second_escalation_raises_one_rounds_alert_in_the_same_call(self):
        """Вторая эскалация при аудитах < 3 поднимает оповещение в вызове `auto`, остановленном на `escalated`.

        Сценарий (две ветви, свежая задача на каждую): в прошлом журнале
        одна эскалация и 0 или 1 вход в аудит SPEC (случайно); `auto` ведёт
        задачу в `spec_audit`, затем в `escalated` — либо переходом
        `advance` после шага spec_auditor, либо эскалацией изнутри самого
        шага. После возврата этого же вызова `auto` задача в `escalated`,
        есть ровно одно оповещение `rounds` с текстом «… N аудитов SPEC, 2
        эскалаций до кода …» и одна запись «круги до кода: оповещение».

        Ловит мутацию: сверка стоит только в продолжении цикла (после
        перехода в состояние с ролью) — переход в `escalated` выходит из
        цикла без оповещения; сверка только после `advance` — эскалация
        изнутри шага роли проходит мимо; порог эскалаций `> 2` — оповещения
        нет.
        """
        for via in ("advance", "role_step"):
            with self.subTest(via=via):
                before = self.rng.randint(0, 1)
                task_id = self.task_with_history(audits=before, escalations=1)
                if via == "advance":
                    out = self.run_auto(task_id, {"spec_writing": "spec_audit",
                                                  "spec_audit": "escalated"})
                else:
                    out = self.run_auto(task_id, {"spec_writing": "spec_audit"},
                                        escalate_in="spec_audit")
                self.assertEqual(store.get_task(self.conn, task_id)["state"],
                                 "escalated", self.note(out))
                self.assert_one_alert(task_id, before + 1, 2, out)

    def test_ac10_later_entries_do_not_raise_a_second_rounds_alert(self):
        """Четвёртый вход в аудит и следующая эскалация не поднимают нового оповещения `rounds`.

        Сценарий: первый вызов `auto` доводит задачу до третьего аудита
        SPEC (оповещение поднято, задача в `spec_gate`); Оператор
        подтверждает (`ack`) оповещение `rounds`, у задачи открыто
        оповещение внимания; возврат с гейта SPEC в `spec_writing` (переход
        закрывает оповещения внимания); второй вызов `auto` проводит задачу
        в `spec_audit` (четвёртый вход) и в `escalated` (вторая эскалация —
        порог эскалаций тоже достигнут). Оповещений `rounds` задачи —
        по-прежнему одно (с подтверждённым), запись «круги до кода:
        оповещение» — одна.

        Ловит мутацию: однократность держится дедупом открытых оповещений
        (`raise_alert`) вместо записи журнала — после `ack` и с новым
        текстом («4 аудитов…») поднимается второе; признак — открытое
        оповещение внимания, закрытое переходом, — второе тоже поднимается.
        """
        task_id = self.task_with_history(audits=2, escalations=0)
        out = self.run_auto(task_id, {"spec_writing": "spec_audit",
                                      "spec_audit": "spec_gate"})
        first = self.rounds_alerts(task_id)
        self.assertEqual(len(first), 1, self.note(f"первое оповещение не поднято\n{out}"))
        self.assertIsNone(alerts.ack(self.conn, first[0]["id"], "operator", "видел"))
        alerts.raise_attention_alert(self.conn, task_id, f"[{task_id}] внимание")
        store.set_state(self.conn, task_id, "spec_writing", "operator",
                        expected_state="spec_gate",
                        detail=f"{GATE_RETURN_PREFIX}уточни порог")
        out += self.run_auto(task_id, {"spec_writing": "spec_audit",
                                       "spec_audit": "escalated"})
        self.assertEqual(store.get_task(self.conn, task_id)["state"], "escalated",
                         self.note(out))
        found = self.rounds_alerts(task_id)
        self.assertEqual(len(found), 1, self.note(
            f"оповещений rounds {len(found)}: {[dict(r) for r in found]}\n{out}"))
        self.assertEqual(len(self.marks(task_id)), 1, self.note(
            f"записей «{MARK}» не одна\n{out}"))

    def test_ac11_two_audits_one_escalation_neither_alert_nor_highlight(self):
        """Два аудита SPEC и одна эскалация — ни оповещения `rounds`, ни выделения строки.

        Сценарий: у задачи в прошлом журнале один вход в аудит SPEC и одна
        эскалация; `auto` проводит её в `spec_audit` (второй вход) и в
        `spec_gate`. Оповещений `rounds` и записи «круги до кода:
        оповещение» нет; в блоке отчёта строка задачи размечена так же, как
        строка задачи без аудитов и эскалаций.

        Ловит мутацию: порог аудитов 2 (или `> 1`) — оповещение поднято и
        строка выделена; пороги блока и оповещения разошлись — строка
        выделена при молчащем оповещении либо наоборот.
        """
        task_id = self.task_with_history(audits=1, escalations=1)
        out = self.run_auto(task_id, {"spec_writing": "spec_audit",
                                      "spec_audit": "spec_gate"})
        self.assertEqual(store.get_task(self.conn, task_id)["state"], "spec_gate",
                         self.note(out))
        self.assertEqual(self.rounds_alerts(), [], self.note(out))
        self.assertEqual(self.marks(task_id), [], self.note(out))
        plain = f"{self.TASK[:-6]}{999999:06d}"
        store.insert_task(self.conn, plain, "Без кругов", "in_dev",
                          f"task/{plain.lower()}-plain", config.DEFAULT_TARGET, 25.0)
        block = rounds_block(report_html())
        self.assertIsNotNone(block, self.note(f"в отчёте нет блока «{BLOCK_TITLE}»"))
        rows = task_rows(block, [task_id, plain])
        self.assertEqual(sorted(rows), sorted([task_id, plain]),
                         self.note(strip(block)))
        self.assertEqual(skeleton(rows[task_id]["html"], task_id),
                         skeleton(rows[plain]["html"], plain),
                         self.note(f"строка 2/1 выделена: {rows[task_id]['html']}"))
