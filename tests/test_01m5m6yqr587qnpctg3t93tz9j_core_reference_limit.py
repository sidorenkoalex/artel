"""Справочник ядра при пределе по умолчанию 16 384 байта: включение ровно
предела, пропуск сверх него и между новым и прежним пределом, предупреждение
90 %, состав промпта по ролям, размер куска справочника в брифе и сводка
`reference`.

Группа: долгоживущий

Красен до реализации: `config.CORE_REFERENCE_MAX_BYTES` ещё 32 768 — справочники 16 385 и 20 000 байт включаются, 15 000 байт не поднимает предупреждения, сводка печатает «предел 32768 байт» и «в пределе»; методы AC-3 и AC-4 зелены и сегодня — держат состав по ролям и размер куска, которые задача менять не должна.

Песочница — `tests.sandbox.LightTransitionSandbox` (тот же приём, что
`ReferenceBriefSandbox` задачи 01M4S24EBVB72B8WYJ3JY96Y0E): задача
артели заведена `catalog.cmd_new`, карта и `CLAUDE.md` —
`seed_developer_brief_fixtures`, SPEC задачи — файл на диске, git подменён
целиком. Справочник отдаёт подмена публичного
`reference_cache.get_reference`; настоящие `targets.yaml` и
`.artel/projects` пульта не читаются. AC-5 — чистая функция
`projects.reference_summary`, без песочницы.

Тексты справочника (латиница или кириллица) и метки выбираются случайно;
зерно печатается и входит в текст провала.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import alerts, brief, config, projects, reference_cache, role_prompt, store
from tests.sandbox import LightTransitionSandbox, seed_developer_brief_fixtures

GET_REFERENCE = "orchestrator.reference_cache.get_reference"
OVERSIZED_SOURCE = "brief.core_reference_oversized"
NEAR_LIMIT_SOURCE = "brief.core_reference_near_limit"
BOUNDARY_OPEN = "=== ГРАНИЦА НЕДОВЕРЕННЫХ ДАННЫХ"
BOUNDARY_CLOSE = "=== КОНЕЦ ГРАНИЦЫ НЕДОВЕРЕННЫХ ДАННЫХ"
NOT_INCLUDED = "не включён"
NEW_LIMIT = 16_384
ROLES = ("developer", "test_author")
ALL_ROLES = ("analyst", "spec_auditor", "test_author", "developer", "reviewer")
WITHOUT_REFERENCE = ("analyst", "spec_auditor", "reviewer")


class CoreReferenceSandbox(LightTransitionSandbox):
    """Задача артели с SPEC на диске, подмена `get_reference` по запросу."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        seed_developer_brief_fixtures(self.root)
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            "# SPEC\n\nМаркер-текста-SPEC.\n", encoding="utf-8")
        self.conn = store.db()
        self.target = store.task_target(self.conn, self.TASK)
        self.label = brief.CORE_REFERENCE_LABEL.format(target=self.target)
        self.answer = reference_cache.Reference("", "", "off")

    def fake_get_reference(self, conn, task_id, *, reason, sha=None):
        return self.answer

    def use(self, text: str) -> None:
        self.answer = reference_cache.Reference(text, "", "fresh")

    def build(self, role: str, text: str):
        """Бриф роли: developer — весь бриф, test_author — добавка."""
        self.use(text)
        with mock.patch(GET_REFERENCE, new=self.fake_get_reference):
            if role == "developer":
                return brief.developer_brief(self.conn, self.TASK)
            return brief.test_author_answer_component(self.conn, self.TASK)

    def reference_text(self, size: int, cyrillic: bool | None = None) -> str:
        """Текст ровно `size` байт UTF-8 с уникальной первой строкой."""
        if cyrillic is None:
            cyrillic = self.rng.random() < 0.5
        head = f"# core-reference метка-{self.rng.randrange(10 ** 12)}\n"
        fill = size - len(head.encode("utf-8"))
        body = ("ж" * (fill // 2) + "x" * (fill % 2)) if cyrillic else "x" * fill
        text = head + body
        self.assertEqual(len(text.encode("utf-8")), size, self.msg("фикстура"))
        return text

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def head(self, reference: str) -> str:
        return reference.split("\n", 1)[0]

    def open_alerts_of(self, kind: str, source: str) -> list:
        return [r for r in alerts.open_alerts(self.conn, kind)
                if r["source"] == source and r["target"] == self.target]

    def header_index(self, text: str) -> int:
        match = re.search(rf"^### {re.escape(self.label)}", text, re.M)
        return match.start() if match else -1

    def assert_included(self, text, reference: str, case: str) -> None:
        self.assertIsNotNone(text, self.msg(f"{case}: добавки нет"))
        self.assertIn(reference, text, self.msg(f"{case}: справочник не включён"))
        self.assertGreaterEqual(self.header_index(text), 0,
                                self.msg(f"{case}: нет заголовка компонента"))

    def assert_excluded(self, text, reference: str, case: str) -> None:
        self.assertIsNotNone(text, self.msg(f"{case}: добавки нет"))
        self.assertNotIn(self.head(reference), text,
                         self.msg(f"{case}: справочник включён"))
        self.assertEqual(self.header_index(text), -1,
                         self.msg(f"{case}: заголовок компонента есть"))


class DefaultLimitTest(CoreReferenceSandbox):

    def test_ac1_default_limit_includes_16384_and_skips_16385_and_20000(self):
        """Предел не подменён; developer и test_author, справочник латиницей
        или кириллицей.

        16 384 байта — справочник в тексте и заголовок компонента есть; 16 385
        и 20 000 байт — ни текста, ни заголовка, есть строка «не включён» и
        открыт `incident` источника `brief.core_reference_oversized` по проекту
        задачи; после возврата к 16 384 байт он снят перед следующим случаем.

        Ловит мутацию: предел оставлен 32 768 (16 385 и 20 000 байт попадут в
        бриф, алерта не будет), задан литералом 16 383 или сравнение `>=`
        (16 384 байт выпадет), либо предел у test_author взят литералом мимо
        `config` — у этой роли граница разойдётся.
        """
        self.assertEqual(config.CORE_REFERENCE_MAX_BYTES, NEW_LIMIT,
                         self.msg("предел по умолчанию"))
        for role in ROLES:
            for case, size, included in (("ровно 16384", NEW_LIMIT, True),
                                         ("16385", NEW_LIMIT + 1, False),
                                         ("20000", 20_000, False)):
                with self.subTest(роль=role, случай=case, зерно=self.seed):
                    reference = self.reference_text(size)

                    text = self.build(role, reference)

                    over = self.open_alerts_of("incident", OVERSIZED_SOURCE)
                    if included:
                        self.assert_included(text, reference, case)
                        self.assertEqual(over, [], self.msg(f"{case}: алерт {over}"))
                    else:
                        self.assert_excluded(text, reference, case)
                        self.assertIn(NOT_INCLUDED, text,
                                      self.msg(f"{case}: нет строки «не включён»"))
                        self.assertTrue(over, self.msg(f"{case}: алерта предела нет"))
                        self.build(role, self.reference_text(NEW_LIMIT))
                        self.assertEqual(
                            self.open_alerts_of("incident", OVERSIZED_SOURCE), [],
                            self.msg(f"{case}: алерт не снят в пределе"))

    def test_ac2_near_limit_warning_at_15000_not_at_14000(self):
        """Предел не подменён; developer и test_author.

        15 000 байт — справочник включён, открыт `warning` источника
        `brief.core_reference_near_limit` по проекту задачи; 14 000 байт —
        справочник включён, предупреждение снято и не открыто.

        Ловит мутацию: предел оставлен 32 768 (15 000 байт ниже 90 % — нет
        предупреждения), порог 90 % заменён на 95 % или на `size > limit * 0.8`
        (15 000 без предупреждения либо 14 000 с ним), либо предупреждение не
        снимается при возврате ниже порога.
        """
        for role in ROLES:
            for case, size, warned in (("15000", 15_000, True),
                                       ("14000", 14_000, False)):
                with self.subTest(роль=role, случай=case, зерно=self.seed):
                    reference = self.reference_text(size)

                    text = self.build(role, reference)

                    self.assert_included(text, reference, case)
                    near = self.open_alerts_of("warning", NEAR_LIMIT_SOURCE)
                    self.assertEqual(bool(near), warned,
                                     self.msg(f"{case}: предупреждение {near}"))


class RoleCompositionTest(CoreReferenceSandbox):

    def test_ac3_only_developer_and_test_author_prompts_carry_reference(self):
        """`role_prompt.mission_brief_package` всех пяти ролей при
        справочнике 10 000 байт с уникальной меткой.

        В брифе developer и test_author метка встречается ровно один раз; в
        миссии, брифе и пакете analyst, spec_auditor и reviewer метки нет.

        Ловит мутацию: справочник добавлен в бриф ещё одной роли (общий
        помощник, который зовёт `spec_auditor_brief`/`analyst_map_component`,
        или ревью-пакет), либо вставлен в бриф developer/test_author дважды
        (и в общий помощник, и в бриф роли) — счёт метки разойдётся.
        """
        reference = self.reference_text(10_000)
        mark = self.head(reference)
        self.use(reference)
        t = store.get_task(self.conn, self.TASK)
        for role in ALL_ROLES:
            with self.subTest(роль=role, зерно=self.seed):
                with mock.patch(GET_REFERENCE, new=self.fake_get_reference):
                    mission, brief_text, package = role_prompt.mission_brief_package(
                        self.conn, self.TASK, t, role, self.root)
                if role in ROLES:
                    self.assertEqual((brief_text or "").count(mark), 1,
                                     self.msg(f"{role}: метка в брифе"))
                else:
                    package_text = (package.get("text", "")
                                    if isinstance(package, dict) else package or "")
                    for part, value in (("миссия", mission), ("бриф", brief_text),
                                        ("пакет", package_text)):
                        self.assertNotIn(mark, str(value or ""),
                                         self.msg(f"{role}: метка в «{part}»"))


class ChunkSizeTest(CoreReferenceSandbox):

    def chunk(self, text: str) -> str:
        """От заголовка компонента до конца строки закрывающей границы."""
        start = self.header_index(text)
        self.assertGreaterEqual(start, 0, self.msg("нет заголовка компонента"))
        close = text.find(BOUNDARY_CLOSE, start)
        self.assertGreaterEqual(close, 0, self.msg("нет закрывающей границы"))
        end = text.find("\n", close)
        return text[start:] if end < 0 else text[start:end]

    def test_ac4_reference_chunk_is_reference_plus_component_framing(self):
        """Справочники случайного размера до предела `config` включительно, у
        developer и test_author.

        Кусок от метки `brief.CORE_REFERENCE_LABEL` до конца компонента несёт
        текст справочника ровно один раз, его байты не больше предела, а всё
        прочее в куске — обрамление компонента: строка заголовка, строки
        открывающей и закрывающей границ и пустые строки; итого кусок не
        больше предела плюс это обрамление.

        Ловит мутацию: в компонент вместе со справочником попадает ещё
        текст (повтор справочника, файл кэша целиком с хвостом, соседний
        компонент), либо предел не применён и компонент собран из
        справочника крупнее предела — в куске окажутся строки сверх
        обрамления или байт больше предела.
        """
        limit = config.CORE_REFERENCE_MAX_BYTES
        sizes = [limit, self.rng.randrange(200, limit)]
        for role in ROLES:
            for size in sizes:
                with self.subTest(роль=role, размер=size, зерно=self.seed):
                    reference = self.reference_text(size)

                    text = self.build(role, reference)

                    chunk = self.chunk(text)
                    self.assertEqual(chunk.count(self.head(reference)), 1,
                                     self.msg("справочник в куске не один раз"))
                    framing = chunk.replace(reference, "", 1)
                    for line in framing.split("\n"):
                        self.assertTrue(
                            not line.strip() or line.startswith(f"### {self.label}")
                            or line.startswith(BOUNDARY_OPEN)
                            or line.startswith(BOUNDARY_CLOSE),
                            self.msg(f"в куске не обрамление: {line[:120]!r}"))
                    self.assertLessEqual(
                        len(chunk.encode("utf-8")),
                        limit + len(framing.encode("utf-8")),
                        self.msg("кусок больше предела плюс обрамление"))


class SummaryTest(unittest.TestCase):

    def test_ac5_summary_of_20000_bytes_names_new_limit_and_exclusion(self):
        """Сводка `projects.reference_summary` справочника 20 000 байт
        (`fresh` и `cached`, латиница и кириллица).

        Строки сводки содержат «предел 16384 байт» и «больше предела — в бриф
        не попадёт».

        Ловит мутацию: предел оставлен 32 768 («предел 32768 байт», «в
        пределе»), либо сводка считает размер в символах — у кириллического
        текста 20 000 байт окажется в пределе.
        """
        seed = random.randrange(1 << 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for state in ("fresh", "cached"):
            for cyrillic in (False, True):
                with self.subTest(state=state, кириллица=cyrillic, зерно=seed):
                    head = f"# core-reference {rng.randrange(10 ** 12)}\n"
                    fill = 20_000 - len(head.encode("utf-8"))
                    body = ("ж" * (fill // 2) + "x" * (fill % 2)) if cyrillic else "x" * fill
                    result = reference_cache.Reference(head + body, "", state)

                    text = "\n".join(projects.reference_summary(
                        config.DEFAULT_TARGET, None, "0" * 40, result))

                    for needle in ("предел 16384 байт",
                                   "больше предела — в бриф не попадёт"):
                        self.assertIn(needle, text,
                                      f"зерно: {seed}; нет «{needle}»: {text}")


if __name__ == "__main__":
    unittest.main()
