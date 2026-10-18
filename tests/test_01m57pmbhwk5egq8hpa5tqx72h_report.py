"""Проект задачи и алерта в HTML `report`; разбивка «Экономики» и доли
acceptance по проекту.

Группа: долгоживущий
Красен до реализации: `report` не ставит метку `[<проект>]` за id задачи внешнего проекта ни в одной строке задачи и ни у алерта проекта, а «Экономика» и доля acceptance считаются одной суммой по всем проектам; проверки строк артели, алертов без метки, однопроектных блоков (AC-4) и доставки алерта задачи дозором зелены и до правки — они держат прежнее поведение.

Связка: строки задач, журнала и алертов в БД песочницы —
`report.cmd_report` (файл `.artel/report.html`), для доставки алерта —
`artel.main` (`observe register`, `watch --observation`). Имя внешнего
проекта и маркеры алертов выбираются случайно при каждом запуске; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import json
import os
import random
import re
import sys
from html.parser import HTMLParser
from unittest import mock

from orchestrator import artel, config, report, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture, patch_sleep

PROJECT_NAMES = ("sled", "zubr", "kedr", "luna", "brod", "volna", "sosna")


class ElementParser(HTMLParser):
    """Каждый элемент разметки: заголовок h2 секции, тег, классы, полный
    текст элемента с потомками, собственный текст без потомков и номер
    плитки `div.tile`, внутри которой элемент лежит (`None` — вне плиток)."""

    def __init__(self):
        super().__init__()
        self.elements = []
        self.stack = []
        self.section = ""
        self.tiles = 0

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        inside = next((item["tile_no"] for item in reversed(self.stack)
                       if item["tile_no"] is not None), None)
        tile_no = None
        if "tile" in classes:
            self.tiles += 1
            tile_no = self.tiles
        self.stack.append({"tag": tag, "classes": classes, "text": "",
                           "own": "", "section": self.section,
                           "tile_no": tile_no, "in_tile": inside})

    def handle_data(self, data):
        if not self.stack:
            return
        self.stack[-1]["own"] += data
        for item in self.stack:
            item["text"] += data

    def handle_endtag(self, tag):
        if not self.stack:
            return
        item = self.stack.pop()
        if item["tag"] == "h2":
            self.section = item["text"].strip()
            item["section"] = self.section
        self.elements.append(item)


def parse(html: str) -> list:
    parser = ElementParser()
    parser.feed(html)
    return parser.elements


def block_rows(html: str, h3_title: str) -> list:
    """Тексты строк `metric-row` между заголовком h3 `h3_title` и
    следующим h3."""
    start = html.index(f"<h3>{h3_title}")
    end = html.find("<h3>", start + 4)
    chunk = html[start:end if end != -1 else len(html)]
    return [e["text"].strip() for e in parse(chunk)
            if "metric-row" in e["classes"]]


def block_text(html: str, h3_title: str) -> str:
    start = html.index(f"<h3>{h3_title}")
    end = html.find("<h3>", start + 4)
    chunk = html[start:end if end != -1 else len(html)]
    return re.sub(r"<[^>]+>", " ", chunk)


class _ReportBase(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.project = self.rng.choice(PROJECT_NAMES)
        self.mark = f"m{self.rng.randrange(1 << 30)}"
        self.conn = store.db()

    def msg(self, *parts) -> str:
        return f"зерно {self.seed}: " + " ".join(str(p) for p in parts)

    def add_task(self, task_id: str, target, state: str) -> None:
        store.insert_task(self.conn, task_id, "Плитка", state,
                          f"task/{task_id.lower()}", target or config.DEFAULT_TARGET,
                          25.0)
        if target is None:
            store.update_task(self.conn, task_id, target=None)

    def render(self) -> str:
        capture(report.cmd_report)
        return (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")


class ReportTaskLabelTest(_ReportBase):
    """T001 — артели (acceptance), T002 — внешнего проекта (acceptance),
    T003 — артели с `target` NULL (done), T004 — внешнего проекта (done)."""

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, self.TASK, state="acceptance")
        self.add_task("T002", self.project, "acceptance")
        self.add_task("T003", None, "done")
        self.add_task("T004", self.project, "done")
        for task_id in ("T001", "T002", "T003", "T004"):
            store.journal(self.conn, task_id, report.TEST_AUTHOR_ROLE,
                          report.STEP_STARTED_ACTION, "старт шага")

    def rows_of(self, elements: list, block: str) -> list:
        if block == "tile":
            return [e["text"] for e in elements if "tile" in e["classes"]]
        if block == "gate":
            return [e["text"] for e in elements if "gate-row" in e["classes"]]
        if block == "closed":
            return [e["text"] for e in elements if "closed-row" in e["classes"]]
        section = {"tokens": "Токены и стоимость", "friction": "Метрика «трение»",
                   "test_author": "Шаги test_author"}[block]
        return [e["text"] for e in elements
                if "metric-row" in e["classes"] and e["section"].startswith(section)]

    def row_for(self, rows: list, task_id: str, block: str) -> str:
        found = [r.strip() for r in rows
                 if re.search(rf"(?<!\d){task_id}(?!\d)", r)]
        self.assertEqual(len(found), 1, self.msg(block, task_id, rows))
        return found[0]

    def test_ac1_task_rows_label_external_project(self):
        """Строки задачи внешнего проекта во всех шести блоках несут
        `[<проект>]` сразу за id, строки задач артели — без метки.

        Сценарий: по задаче каждого проекта в гейте acceptance и в done, у
        каждой — запуск test_author в окне; плитки, очередь гейтов,
        закрытые задачи, разрез задач, трение и шаги test_author ищутся
        разбором разметки, текст строки — без тегов.
        Ловит мутацию: метка добавлена не во все места (например, забыт
        разрез задач или шаги test_author) или стоит не сразу за id; либо
        метка ставится каждой задаче — `[artel]` у артели, `[None]` у
        задачи с `target` NULL.
        """
        elements = parse(self.render())
        cases = (("tile", ("T001", "T002", "T003", "T004")),
                 ("gate", ("T001", "T002")), ("closed", ("T003", "T004")),
                 ("tokens", ("T001", "T002", "T003", "T004")),
                 ("friction", ("T001", "T002", "T003", "T004")),
                 ("test_author", ("T001", "T002", "T003", "T004")))
        external = {"T002", "T004"}
        for block, task_ids in cases:
            rows = self.rows_of(elements, block)
            for task_id in task_ids:
                with self.subTest(block=block, task=task_id, seed=self.seed):
                    row = self.row_for(rows, task_id, block)
                    labelled = re.search(
                        rf"{task_id}\s*\[{re.escape(self.project)}\]", row)
                    if task_id in external:
                        self.assertIsNotNone(labelled, self.msg(block, row))
                    else:
                        self.assertIsNone(re.search(rf"{task_id}\s*\[", row),
                                          self.msg(block, row))
                        for label in (f"[{config.DEFAULT_TARGET}]", "[None]",
                                      f"[{self.project}]"):
                            self.assertNotIn(label, row, self.msg(block, row))

    def test_ac1_tile_nested_project_element(self):
        """Плитка задачи внешнего проекта: элемент с собственным текстом
        ровно `<проект>`, элемент id — ровно id задачи.

        Ловит мутацию: метка вписана в элемент id (`T002 [sled]`) или
        одним текстом `[sled]` в элемент проекта — собственный текст
        элемента перестаёт быть ровно именем проекта либо id.
        """
        elements = parse(self.render())
        tiles = [e for e in elements if "tile" in e["classes"]]
        for task_id in ("T002", "T004"):
            with self.subTest(task=task_id, seed=self.seed):
                tile = [t for t in tiles
                        if re.search(rf"(?<!\d){task_id}(?!\d)", t["text"])]
                self.assertEqual(len(tile), 1, self.msg(task_id, tiles))
                inner = [e for e in elements if e["in_tile"] == tile[0]["tile_no"]]
                own = [e["own"].strip() for e in inner]
                self.assertIn(self.project, own, self.msg(task_id, own))
                ids = [e["own"].strip() for e in inner if "tile-id" in e["classes"]]
                self.assertEqual(ids, [task_id], self.msg(task_id, own))


class ReportAlertLabelTest(_ReportBase):
    """Панель незакрытых алертов и доставка алерта задачи внешнего
    проекта дозором."""

    EXT = "T002"

    def setUp(self):
        super().setUp()
        self.add_task(self.EXT, self.project, "in_dev")
        self.alerts = {}
        for name, target in (("project", self.project),
                             ("artel", config.DEFAULT_TARGET),
                             ("null", None), ("task", self.EXT)):
            message = f"{self.mark}-{name}"
            store.insert_alert(self.conn, target, "attention" if name == "task"
                               else "incident", f"src-{name}", message)
            self.alerts[name] = message

    def alert_rows(self) -> dict:
        rows = [e["text"].strip() for e in parse(self.render())
                if "alert-item" in e["classes"]]
        found = {}
        for name, message in self.alerts.items():
            matched = [r for r in rows if message in r]
            self.assertEqual(len(matched), 1, self.msg(name, rows))
            found[name] = matched[0]
        return found

    def test_ac2_alert_panel_labels_only_project_alert(self):
        """Алерт с `target` внешнего проекта несёт `[<проект>]`; алерты
        артели, NULL и id задачи внешнего проекта — прежний вид строки.

        Прежний вид — текст строки ровно «вид, сообщение, `source: …`»
        подряд, без метки.
        Ловит мутацию: метка ставится любому `target` вне {NULL, артель} —
        алерт с id задачи получает `[T002]`; либо метка ставится каждому
        алерту — `[artel]`/`[None]`; либо алерт проекта метки не получает.
        """
        rows = self.alert_rows()
        self.assertIn(f"[{self.project}]", rows["project"], self.msg(rows))
        for name, kind in (("artel", "incident"), ("null", "incident"),
                           ("task", "attention")):
            with self.subTest(alert=name, seed=self.seed):
                self.assertEqual(
                    rows[name], f"{kind}{self.alerts[name]}source: src-{name}",
                    self.msg(rows[name]))

    def test_ac2_task_alert_delivered_to_observation_of_task(self):
        """Алерт с `target` = id задачи внешнего проекта выводится дозором
        наблюдения, в набор которого входит эта задача.

        Сценарий: наблюдение на T002 и T001 (артель первой) — одна
        итерация `watch --observation`.
        Ловит мутацию: правка доставки алертов (NULL каждому наблюдению)
        переписала фильтр так, что ветка «id задачи набора» выпала —
        алерт задачи пропадает из вывода дозора.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register",
                                             "--tasks", f"{self.TASK},{self.EXT}"]):
            observation_id = json.loads(capture(artel.main))["id"]
        # Позиция наблюдения — максимум журнала на регистрации: алерт
        # заводится после неё.
        message = f"{self.mark}-task-after"
        store.insert_alert(self.conn, self.EXT, "attention", "src-task", message)
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation",
                                             observation_id]), \
                patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))), \
                contextlib.redirect_stdout(out):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                artel.main()
        self.assertIn(message, out.getvalue(), self.msg(out.getvalue()))


def ratio_text(autogate: int, operator: int) -> str:
    total = autogate + operator
    return (f"autogate {autogate} ({round(autogate * 100 / total)}%) / "
            f"operator {operator} ({round(operator * 100 / total)}%) из {total}")


class ReportPerProjectMetricsTest(_ReportBase):
    """Блоки «Экономика» и «Доля acceptance» при задачах двух проектов."""

    GATE_H3 = "Доля acceptance: автогейт vs Оператор"
    ECONOMY_H3 = "Экономика"

    def gate_entries(self, task_id: str, actors: list) -> None:
        for actor in actors:
            store.journal(self.conn, task_id, actor, report.GATE_TRANSITION_ACTION)

    def test_ac3_metrics_split_by_project(self):
        """«Экономика» и доля acceptance — значения каждого проекта по его
        задачам и записям; окно проекта — его последние записи.

        Сценарий: у обоих проектов записей перехода больше окна; записи
        внешнего проекта старше записей артели, так что последние
        `GATE_RATIO_WINDOW` записей пульта — только артели. Деньги задач
        подобраны так, что значение каждого проекта отличается от общего.
        Ловит мутацию: окно проекта берётся как его доля среди последних
        записей всех проектов — у внешнего проекта «записей нет» вместо
        своего окна; или итог проекта считается по всем задачам — в блоке
        общие суммы вместо значений проекта; или блок не разбит вовсе.
        """
        window = report.GATE_RATIO_WINDOW
        extra_ext = self.rng.randrange(2, 6)
        extra_artel = self.rng.randrange(1, 4)
        self.add_task("T002", self.project, "done")
        self.add_task("T003", config.DEFAULT_TARGET, "done")
        self.add_task("T004", self.project, "in_dev")
        store.update_task(self.conn, self.TASK, state="done", spent_usd=1.25,
                          spent_estimate_usd=0.4)
        store.update_task(self.conn, "T003", spent_usd=3.75)
        store.update_task(self.conn, "T002", spent_usd=9.0)
        store.update_task(self.conn, "T004", spent_usd=4.5, spent_estimate_usd=2.2)
        # Внешний проект: сначала operator, затем окно autogate.
        self.gate_entries("T002", ["operator"] * extra_ext + ["autogate"] * window)
        # Артель позже: сначала autogate, затем окно operator.
        self.gate_entries(self.TASK, ["autogate"] * extra_artel + ["operator"] * window)
        html = self.render()

        gate = block_text(html, self.GATE_H3)
        economy = block_text(html, self.ECONOMY_H3)
        for name in (config.DEFAULT_TARGET, self.project):
            self.assertIn(name, gate, self.msg(gate))
            self.assertIn(name, economy, self.msg(economy))
        expected_gate = {
            "ext history": ratio_text(window, extra_ext),
            "ext window": ratio_text(window, 0),
            "artel history": ratio_text(extra_artel, window),
            "artel window": ratio_text(0, window),
        }
        for label, text in expected_gate.items():
            with self.subTest(value=label, seed=self.seed):
                self.assertIn(text, gate, self.msg(label, gate))
        # artel: done 1.25 и 3.75 → $2.50, расход $5.00, оценка $0.40;
        # внешний: done 9.00 → $9.00, расход $13.50, оценка $2.20.
        for value in ("$2.50", "$5.00", "$0.40", "$9.00", "$13.50", "$2.20"):
            with self.subTest(value=value, seed=self.seed):
                self.assertIn(value, economy, self.msg(economy))


class ReportSingleProjectMetricsTest(_ReportBase):
    """Однопроектная выборка: блоки без разбивки, прежние строки."""

    def seed_tasks(self, targets: list) -> None:
        store.update_task(self.conn, self.TASK, target=targets[0], state="done",
                          spent_usd=2.0, spent_estimate_usd=0.5)
        self.add_task("T002", targets[1], "in_dev")
        store.update_task(self.conn, "T002", spent_usd=3.0)
        for actor in ("autogate", "operator", "autogate"):
            store.journal(self.conn, self.TASK, actor, report.GATE_TRANSITION_ACTION)

    def test_ac4_single_project_blocks_unchanged(self):
        """Только артель (с задачей `target` NULL рядом с артелью) и
        только внешний проект — блоки «Экономика» и доли acceptance
        совпадают построчно с прежним видом и не называют проекта.

        Ловит мутацию: разбивка включается при одном проекте (в том числе
        когда NULL считается отдельным проектом рядом с `artel`, или
        единственный внешний проект получает свою строку) — в блоке
        появляются строки с именем проекта.
        """
        expected_gate = [f"за всю историю: {ratio_text(2, 1)}",
                         f"за последние 10 задач: {ratio_text(2, 1)}"]
        expected_economy = [
            "$/задачу (done): $2.00",
            "Суммарный расход программы: $5.00",
            "Суммарная верхняя оценка (тариф модели не разрешён): $0.50"]
        for targets in ((None, config.DEFAULT_TARGET),
                        (self.project, self.project)):
            with self.subTest(targets=targets, seed=self.seed):
                self.seed_tasks(list(targets))
                html = self.render()
                gate = block_rows(html, "Доля acceptance: автогейт vs Оператор")
                economy = block_rows(html, "Экономика")
                self.assertEqual(gate, expected_gate, self.msg(gate))
                self.assertEqual(economy, expected_economy, self.msg(economy))
                for text in gate + economy:
                    for name in (config.DEFAULT_TARGET, self.project, "None"):
                        self.assertNotIn(name, text, self.msg(text))
                # Следующий вариант — с чистого журнала и без T002.
                self.conn.execute("DELETE FROM steps")
                self.conn.execute("DELETE FROM tasks WHERE id='T002'")
                self.conn.commit()
