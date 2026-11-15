"""Contratos dos workflows que o pytest consegue cobrar sem rodar o Actions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))


def _sem_comentarios(arquivo: Path) -> str:
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in linhas if not ln.lstrip().startswith("#"))


@pytest.mark.parametrize("arquivo", WORKFLOWS, ids=lambda p: p.name)
def test_nenhuma_expressao_usa_string_vazia_como_ramo_verdadeiro(arquivo):
    """`cond && '' || X` devolve SEMPRE X: a string vazia e falsa no Actions.

    Era assim que a simulacao decidia nao comitar -- `inputs.dry_run && '' ||
    'dados: ...'` -- e portanto ela sempre comitava. O defeito viveu escondido
    enquanto o dry-run nao escrevia arquivo ("Nada mudou -- nenhum commit"); no
    dia em que um passo passou a atualizar a PTAX antes, uma simulacao publicou
    95 linhas na main.
    """
    assert not re.search(r"&&\s*''\s*\|\|", _sem_comentarios(arquivo)), (
        f"{arquivo.name}: ramo verdadeiro vazio"
    )


@pytest.mark.parametrize("nome", ["atualiza-fundamentos.yml", "atualiza-mercado.yml"])
def test_workflow_com_simulacao_so_passa_mensagem_de_commit_fora_dela(nome):
    texto = _sem_comentarios(next(p for p in WORKFLOWS if p.name == nome))
    mensagem = next(ln for ln in texto.splitlines() if ln.strip().startswith("mensagem:"))
    assert "inputs.dry_run != true &&" in mensagem
    assert mensagem.rstrip().endswith("|| '' }}\"")
