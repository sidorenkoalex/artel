"""Приёмочный тест AC-1 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-1: существует единая функция/объект «репозиторный контекст target»:
для self — путь клона `config.ROOT`, remote `origin`, ветка
`config.MAIN_BRANCH`; для любого другого target — путь клона
`.artel/projects/<target>/workspace`, адрес форджа
`targets.yaml[target]["url"]`, базовая ветка `targets.yaml[target]["base"]`.

Требование 1 SPEC явно называет место: «понятие ... в одном модуле
(модуль/функция)» — реестр точек §4.3 (13 строк) переводится на этот
общий узел, а не на 13 независимых копий одной и той же развилки
self/внешний target. Разработчик волен назвать сам объект/поле как
угодно ВНУТРИ модуля, но точка входа фиксируется этим тестом как
`orchestrator.repo_context.resolve(target_name)` — единственный
разумный шов, из которого `ci.py`/`review.py`/`acceptance.py`/
`github_adapter.py`/`doctor.py`/`fsm.py`/`fsm_merge_gate.py` могут
получить контекст без цикла импортов (ни один из них не может зависеть
от `fsm.py`, который уже несёт похожую, но приватную и self-специфичную
пару `_origin_main_source`/`_origin_main_sha`).

Красен до реализации: модуля `orchestrator.repo_context` ещё нет —
импорт падает `ModuleNotFoundError` до того, как код задачи появится.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import EXTERNAL_TARGET, ExternalTargetGitSandbox  # noqa: E402


class SelfTargetContextTest(TmpRootTest):
    """Self (`config.DEFAULT_TARGET`) не обязан читать `targets.yaml`
    вовсе (тот же принцип, что уже несёт `fsm._origin_main_source` —
    песочницы self-сценариев намеренно не заводят `config.TARGETS`)."""

    def test_ac1_self_target_context_is_root_origin_main(self):
        """Self-target: путь клона — `config.ROOT`, ветка —
        `config.MAIN_BRANCH`, remote — `origin` (без обращения к
        `targets.yaml`, которого в этой песочнице нет).

        Ловит мутацию: реализация читает `targets.yaml` даже для self
        и падает/эскалирует, потому что записи 'artel' в файле нет —
        `self.assertFalse(config.TARGETS.exists())` перед вызовом
        гарантирует, что тест ловит именно это, а не совпадение.
        """
        from orchestrator import repo_context

        self.assertFalse(config.TARGETS.exists())
        ctx = repo_context.resolve(config.DEFAULT_TARGET)

        self.assertIsNotNone(ctx)
        self.assertEqual(Path(ctx.path), config.ROOT)
        self.assertEqual(ctx.base, config.MAIN_BRANCH)
        self.assertEqual(ctx.remote, "origin")


class ExternalTargetContextTest(ExternalTargetGitSandbox):

    def test_ac1_external_target_context_is_workspace_and_targets_yaml(self):
        """Внешний target: путь клона — `.artel/projects/<target>/
        workspace` (буквально `config.PROJECTS/<target>/"workspace"`),
        remote/базовая ветка — из `targets.yaml[target]`.

        Ловит мутацию: возврат `config.ROOT`/`config.MAIN_BRANCH` для
        любого target (старое поведение, которое и чинит вся SPEC) —
        `assertEqual` на путь/базу целевого это поймает.
        """
        from orchestrator import repo_context

        ctx = repo_context.resolve(EXTERNAL_TARGET)

        self.assertIsNotNone(ctx)
        self.assertEqual(Path(ctx.path),
                         config.PROJECTS / EXTERNAL_TARGET / "workspace")
        self.assertEqual(Path(ctx.path), self.target_workspace)
        self.assertEqual(ctx.remote, f"https://example.invalid/{EXTERNAL_TARGET}")
        self.assertEqual(ctx.base, "main")

    def test_ac1_unknown_target_degrades_to_none_not_a_traceback(self):
        """Запись target'а не читается (файл сломан или её нет вовсе) —
        `None`, тем же принципом деградации, что уже несёт
        `fsm._origin_main_source` («молчаливый откат на 'origin' был бы
        опаснее обычной деградации»): вызывающий код обязан получить
        сигнал «конфигурация не читается», а не тихо соскользнуть на
        чужой репозиторий.

        Ловит мутацию: неизвестный target роняет `TargetsError` наружу
        необработанным исключением вместо контролируемого `None` —
        `assertIsNone` внутри `assertRaises`-свободного вызова это
        поймает (само исключение уже завалило бы тест раньше assert'а).
        """
        from orchestrator import repo_context

        ctx = repo_context.resolve("no-such-target")

        self.assertIsNone(ctx)


if __name__ == "__main__":
    import unittest
    unittest.main()
