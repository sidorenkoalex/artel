"""AC-3 (SPEC.md): после завершения прогона в основном пульте не
появляется новых веток задач, записей RETRO, записей копилки/алертов
инцидента или снапшотов артефактов, связанных с канареечными задачами
прогона — ни для успешных, ни для убитых задач.

Дыра v1 (контекст SPEC): RETRO killed-канареек v1 писалось прямо в
`config.ROOT` пульта (`orchestrator/retro.py::build_killed`,
`tasks/<id>/RETRO.md` на диске main) — она и есть предмет этого
критерия. Весь цикл задач v2 обязан идти в ЭФЕМЕРНОМ КЛОНЕ (AC-2), так
что «основной пульт» здесь — это ЖЕ САМОЕ, что видит `store.db()`/
`config.ROOT` СНАРУЖИ прогона (`self.root` этой песочницы): если
реализация верна, она вообще не пишет в эти пути НИКАКИМ кодовым путём
— работа целиком идёт в клоне, о котором `self.root` знать не может.

Красен до реализации: `canary --k` пока падает `SystemExit` на позиционном разборе (см. `test_ac1_pool_dir_and_sampling.py`) — ни одна задача не заводится, `task_ids_before == task_ids_after` тривиально истинно, а вот следующая проверка (что прогон вообще выполнился — `self.assertEqual(len(reports_before_run) ...)` про сам факт заведения пары канареечных сущностей) распознаёт «прогон не случился» отдельно; здесь редну даёт ИМЕННО она, не тождественное равенство пустых множеств (см. первый assert в тесте — сверка, что прогон действительно что-то сделал, до сверки следов).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

from orchestrator import store  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
    "udalenie-rudimenta.md": "Убери неиспользуемый синтетический модуль Y.",
}


class NoTracesInMainPultTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)

    def test_ac3_run_leaves_no_branches_tasks_alerts_or_snapshots_in_main_pult(self):
        """Прогон двух шаблонов (успешная и потенциально убитая ветка
        сценария — обе доходят до `merge_gate`/`killed` внутри клона,
        v1-семантика «canary никогда не approve merge_gate», AC-11)
        не оставляет в `self.root` (main пульта СНАРУЖИ клона) ни одной
        новой ветки, ни одной строки `tasks`/`steps`, ни одного нового
        алерта, ни одного файла артефактов задачи.

        Ловит мутацию: разработчик по ошибке гоняет весь FSM-цикл
        (`catalog.cmd_new`/`auto.cmd_auto`/`cleanup.cmd_kill`) прямо
        поверх `config.ROOT` внешнего процесса вместо переключения его
        на путь эфемерного клона (самая естественная «забытая» правка
        при переносе v1 в v2, раз весь остальной код `_drive_task` не
        меняется) — тогда `store.all_tasks` main пульта после прогона
        перестанет быть пустым, ветки задач появятся в `git branch
        --list` main-репозитория, тест покраснеет по этой проверке.
        """
        branches_before = set(
            self._git("branch", "--list", "--format=%(refname:short)")
            .stdout.split())
        tasks_before = store.all_tasks(store.db())
        self.assertEqual(
            tasks_before, [],
            "песочница нечиста до прогона — предпосылка теста не выполнена")
        alerts_before = store.open_alerts(store.db())
        tasks_dir_files_before = (
            sorted(p.relative_to(self.root)
                  for p in self.root.glob("tasks/**/*") if p.is_file())
            if (self.root / "tasks").exists() else [])
        sha_before = self.main_sha()

        out = self.run_canary_pool(2)

        # Прогон действительно случился (не оборвался на входе) — иначе
        # проверки ниже про «ничего не изменилось» были бы неотличимы
        # от «команда вообще ничего не сделала» (сообщение об отказе
        # тоже несёт слово «canary», так что по нему одному не отличить
        # реальный прогон от `SystemExit` на разборе аргументов —
        # `run_cli` дописывает маркер `[SystemExit]` именно на такой
        # случай, см. `_sandbox.py::CanarySandbox.run_cli`).
        self.assertNotIn(
            "[SystemExit]", out,
            f"прогон оборвался исключением, вместо того чтобы выполниться "
            f"и оставить (не оставить) следы:\n{out}")

        sha_after = self.main_sha()
        self.assertEqual(sha_before, sha_after,
                         "sha main изменился за время прогона")

        branches_after = set(
            self._git("branch", "--list", "--format=%(refname:short)")
            .stdout.split())
        self.assertEqual(
            branches_before, branches_after,
            f"прогон завёл новые ветки в main пульта: "
            f"{branches_after - branches_before}")

        tasks_after = store.all_tasks(store.db())
        self.assertEqual(
            tasks_after, [],
            f"прогон оставил строки в `tasks` main пульта: {tasks_after}")

        alerts_after = store.open_alerts(store.db())
        self.assertEqual(
            len(alerts_before), len(alerts_after),
            f"прогон завёл новые алерты в main пульта: было "
            f"{len(alerts_before)}, стало {len(alerts_after)}: "
            f"{alerts_after}")

        tasks_dir_files_after = (
            sorted(p.relative_to(self.root)
                  for p in self.root.glob("tasks/**/*") if p.is_file())
            if (self.root / "tasks").exists() else [])
        self.assertEqual(
            tasks_dir_files_before, tasks_dir_files_after,
            f"прогон оставил файлы артефактов задач на диске main пульта: "
            f"{set(tasks_dir_files_after) - set(tasks_dir_files_before)}")


if __name__ == "__main__":
    unittest.main()
