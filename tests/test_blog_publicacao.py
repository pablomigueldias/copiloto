"""O caminho de "pronto" até a `main`.

**Nenhum teste aqui roda `git` ou `gh` de verdade.** O executor é substituído e
os comandos ficam registrados, porque o que precisa ser verdade não é "o push
funcionou" — é *quais comandos este módulo decide emitir*. Um `git add -A` que
entrasse aqui por descuido varreria a working tree do blog para dentro de um
commit, e isso não falha em teste nenhum que só olhe o resultado final.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blog import fluxo, publicacao, servico
from tests.test_blog import CORPO_BOM, DESCRICAO


@pytest.fixture
async def pronto():
    novo = await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")
    post = await servico.salvar(
        novo.id,
        {
            "slug": "rag-que-diz-nao-sei",
            "titulo": "Um RAG que sabe dizer: não está nas minhas notas",
            "descricao": DESCRICAO,
            "corpo": CORPO_BOM,
            "tags": ["rag", "pgvector"],
            "origem": [{"copiloto": "docs/fase03.md"}],
            "data_publicacao": "2026-09-22",
        },
    )
    return await servico.mudar_estado(post.id, "pronto")


class Executor:
    """Substitui `_rodar`. Registra a chamada e devolve o que o teste mandar."""

    def __init__(self, respostas: dict[str, str] | None = None):
        self.chamadas: list[list[str]] = []
        self.respostas = respostas or {}
        self.erro_em: str | None = None

    async def __call__(self, *args: str, cwd: Path) -> str:
        self.chamadas.append(list(args))
        if self.erro_em and self.erro_em in " ".join(args):
            raise publicacao.PublicacaoErro(f"falhou: {self.erro_em}")
        for prefixo, resposta in self.respostas.items():
            if " ".join(args).startswith(prefixo):
                return resposta
        # `git status --porcelain` precisa devolver algo, senão o módulo conclui
        # "nada mudou" e para antes de commitar.
        if "status" in args:
            return " M content/blog/rag-que-diz-nao-sei.mdx"
        return ""

    def comandos(self, *inicio: str) -> list[list[str]]:
        return [c for c in self.chamadas if c[: len(inicio)] == list(inicio)]


@pytest.fixture
def git(monkeypatch, tmp_path):
    """Executor falso + repo falso, com o worktree escrevendo em disco de verdade."""
    (tmp_path / ".git").mkdir()
    exe = Executor(
        {
            "gh pr list": "[]",
            "gh pr create": "https://github.com/pablomigueldias/pabloortiz.dev/pull/42",
        }
    )

    async def rodar(*args, cwd):
        # O `worktree add` de verdade criaria a pasta; aqui ela é criada à mão,
        # porque o módulo escreve o .mdx dentro dela logo depois.
        if args[:3] == ("git", "worktree", "add"):
            Path(args[5]).mkdir(parents=True, exist_ok=True)
            (Path(args[5]) / "content" / "blog").mkdir(parents=True, exist_ok=True)
        return await exe(*args, cwd=cwd)

    monkeypatch.setattr(publicacao, "_rodar", rodar)
    monkeypatch.setattr(publicacao, "_repo", lambda: tmp_path)
    return exe


# ── abrir o PR ────────────────────────────────────────────────────────


async def test_abre_pr_e_guarda_o_numero(pronto, git):
    dados = await fluxo.abrir_pr(pronto.id)

    assert dados["pr_numero"] == 42
    assert dados["branch"] == "post/rag-que-diz-nao-sei"

    post = await servico.obter(pronto.id)
    assert post.pr_numero == 42
    assert post.pr_url.endswith("/pull/42")
    assert post.exportado_em is not None
    # Abrir PR não publica: isso é o merge.
    assert post.estado == "pronto"
    assert post.publicado_em is None


async def test_a_branch_nasce_da_origin_main(pronto, git):
    """A `main` é `strict`: branch atrás dela não mergeia. Nascer da
    `origin/main` faz o rebase nunca ser necessário."""
    await fluxo.abrir_pr(pronto.id)

    assert git.comandos("git", "fetch", "origin", "main")
    add = git.comandos("git", "worktree", "add")[0]
    assert add[3] == "-B" and add[4] == "post/rag-que-diz-nao-sei"
    assert add[-1] == "origin/main"


async def test_nunca_faz_git_add_de_tudo(pronto, git):
    """O teste que mais importa: só o arquivo deste post entra no commit."""
    await fluxo.abrir_pr(pronto.id)

    adds = git.comandos("git", "add")
    assert len(adds) == 1
    assert adds[0] == ["git", "add", "--", "content/blog/rag-que-diz-nao-sei.mdx"]
    for chamada in git.chamadas:
        assert "-A" not in chamada and "--all" not in chamada
        assert "." not in chamada[1:]


async def test_nao_commita_na_main(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    for chamada in git.chamadas:
        assert chamada[:2] != ["git", "checkout"]
        assert chamada[:2] != ["git", "switch"]


async def test_commit_sem_trailer_de_co_autoria(pronto, git):
    """Decisão do Pablo: nada de `Co-Authored-By` no histórico deste projeto."""
    await fluxo.abrir_pr(pronto.id)
    commit = git.comandos("git", "commit")[0]
    assert "Co-Authored-By" not in " ".join(commit)


async def test_o_worktree_e_removido_mesmo_quando_falha(pronto, git, monkeypatch):
    git.erro_em = "git push"
    with pytest.raises(publicacao.PublicacaoErro):
        await fluxo.abrir_pr(pronto.id)
    assert git.comandos("git", "worktree", "remove")


async def test_post_que_nao_esta_pronto_nao_abre_pr(git):
    rascunho = await servico.criar(titulo="Meio escrito", corpo="uma linha")
    with pytest.raises(servico.NaoEstaPronto):
        await fluxo.abrir_pr(rascunho.id)
    assert git.chamadas == []


async def test_reaproveita_o_pr_aberto_da_mesma_branch(pronto, git):
    """Publicar de novo com o PR aberto atualiza a branch, não abre um segundo."""
    git.respostas["gh pr list"] = json.dumps(
        [{"number": 7, "url": "https://github.com/x/y/pull/7"}]
    )
    dados = await fluxo.abrir_pr(pronto.id)

    assert dados["pr_numero"] == 7
    assert git.comandos("gh", "pr", "create") == []
    assert git.comandos("git", "push")


async def test_sem_mudanca_em_relacao_a_main_avisa_em_vez_de_commitar(pronto, git):
    git.respostas["git status"] = ""
    with pytest.raises(publicacao.PublicacaoErro) as e:
        await fluxo.abrir_pr(pronto.id)
    assert "já está publicado" in str(e.value)


# ── situação e merge ──────────────────────────────────────────────────


def _pr_json(estado="OPEN", checks=(("ci", "SUCCESS"),), merge="CLEAN"):
    return json.dumps(
        {
            "state": estado,
            "url": "https://github.com/x/y/pull/42",
            "mergeable": "MERGEABLE",
            "mergeStateStatus": merge,
            "statusCheckRollup": [
                {"name": n, "conclusion": c, "detailsUrl": "http://x"} for n, c in checks
            ],
        }
    )


async def test_post_sem_pr_nao_consulta_o_github(pronto, git):
    situacao = await fluxo.situacao(pronto.id)
    assert situacao == {"existe": False, "estado": None, "checks": [], "mergeavel": False}
    assert git.chamadas == []


async def test_situacao_lista_os_checks(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json(
        checks=(("ci", "SUCCESS"), ("Workers Builds: pabloortiz-dev", "SUCCESS"))
    )

    s = await fluxo.situacao(pronto.id)
    assert s["existe"] and s["checks_verdes"] and s["mergeavel"]
    assert [c["nome"] for c in s["checks"]] == ["ci", "Workers Builds: pabloortiz-dev"]


async def test_check_pendente_nao_e_mergeavel(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json(
        checks=(("ci", "SUCCESS"), ("Workers Builds", None)), merge="BLOCKED"
    )
    s = await fluxo.situacao(pronto.id)
    assert not s["checks_verdes"] and not s["mergeavel"]


async def test_nao_mergeia_com_check_vermelho(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json(checks=(("ci", "FAILURE"),), merge="BLOCKED")

    with pytest.raises(publicacao.PublicacaoErro) as e:
        await fluxo.concluir(pronto.id)
    assert "ci" in str(e.value)
    assert git.comandos("gh", "pr", "merge") == []
    assert (await servico.obter(pronto.id)).estado == "pronto"


async def test_merge_e_squash_com_assunto_e_corpo_explicitos(pronto, git):
    """Sem `--subject`/`--body`, o GitHub monta a mensagem do squash juntando os
    commits da branch — trailers inclusive."""
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json()

    await fluxo.concluir(pronto.id)

    merge = git.comandos("gh", "pr", "merge")[0]
    assert "--squash" in merge and "--delete-branch" in merge
    assert "--subject" in merge and "--body" in merge
    assert "Co-Authored-By" not in " ".join(merge)


async def test_depois_do_merge_o_post_fica_publicado(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json()

    dados = await fluxo.concluir(pronto.id)
    assert dados["url"].endswith("/blog/rag-que-diz-nao-sei")

    post = await servico.obter(pronto.id)
    assert post.estado == "publicado"
    assert post.publicado_em is not None
    # A branch morreu no merge; guardar o nome seria apontar para o que não existe.
    assert post.branch is None


async def test_pr_ja_fechado_nao_mergeia_de_novo(pronto, git):
    await fluxo.abrir_pr(pronto.id)
    git.respostas["gh pr view"] = _pr_json(estado="MERGED")

    with pytest.raises(publicacao.PublicacaoErro) as e:
        await fluxo.concluir(pronto.id)
    assert "MERGED" in str(e.value)
