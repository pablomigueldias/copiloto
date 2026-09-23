"use client";

/**
 * A redação — o backlog editorial e o estado de cada post.
 *
 * Agrupada por estado e não ordenada por data: a pergunta que eu faço ao abrir
 * esta tela é "o que está começado e parado?", e uma lista cronológica única
 * esconde justamente isso — o rascunho de anteontem afunda embaixo da pauta que
 * eu anotei hoje.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { Cabecalho, Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { EstadoPost, PostLinha } from "@/lib/tipos";

// A ordem é a do trabalho, e é ela que desenha a tela de cima para baixo.
const ORDEM: { estado: EstadoPost; rotulo: string; explica: string }[] = [
  { estado: "rascunho", rotulo: "Escrevendo", explica: "texto começado — é aqui que o post trava" },
  { estado: "pronto", rotulo: "Pronto para publicar", explica: "as cinco camadas fecharam — falta o PR" },
  { estado: "pauta", rotulo: "Pautas", explica: "ideia anotada, sem uma linha escrita" },
  { estado: "publicado", rotulo: "Publicado", explica: "entrou na main e está no ar" },
  { estado: "arquivado", rotulo: "Arquivado", explica: "saiu do caminho sem ser apagado" },
];

function haQuanto(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "agora";
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

function Cartao({ post }: { post: PostLinha }) {
  return (
    <Link
      href={`/posts/${post.id}`}
      className="card elev-sm flex flex-col gap-[6px] no-underline transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_35%,transparent)]"
    >
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="text-[15px] text-text">{post.titulo}</span>
        {post.pilar && <span className="card-kicker">{post.pilar}</span>}
        <span className="tnum ml-auto text-[11.5px] text-neutral-600">
          {haQuanto(post.updated_at)}
        </span>
      </div>

      {post.descricao && (
        <p className="m-0 max-w-[70ch] text-[13px] text-neutral-500">{post.descricao}</p>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-neutral-600">
        <span className="tnum">{plural(post.palavras, "palavra", "palavras")}</span>
        {post.tags.length > 0 && <span>{post.tags.join(" · ")}</span>}
        {/* A bolinha responde, de longe, a única pergunta que importa na lista:
            este post já serve aos quatro públicos? */}
        <span className={post.camadas_ok ? "text-accent" : "text-neutral-500"}>
          {post.camadas_ok ? "● camadas fechadas" : "○ faltam camadas"}
        </span>
        {/* O PR é a informação que a lista precisa quando o post já saiu daqui:
            "esperando o CI" e "no ar" são estados bem diferentes de espera. */}
        {post.publicado_em ? (
          <span className="text-accent">no ar · PR #{post.pr_numero}</span>
        ) : post.pr_numero ? (
          <span>PR #{post.pr_numero} aberto</span>
        ) : post.exportado_em ? (
          <span>exportado {haQuanto(post.exportado_em)}</span>
        ) : null}
      </div>
    </Link>
  );
}

export default function Posts() {
  const [itens, setItens] = useState<PostLinha[] | null>(null);
  const [porEstado, setPorEstado] = useState<Record<string, number>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [criando, setCriando] = useState(false);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(
    (): Promise<void> =>
      api
        .posts()
        .then((r) => {
          setItens(r.itens);
          setPorEstado(r.por_estado);
        })
        .catch((e: Error) => setErro(String(e.message ?? e))),
    [],
  );

  useEffect(() => {
    void carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const criar = async () => {
    const nome = titulo.trim();
    if (!nome) return;
    setCriando(true);
    try {
      await api.criarPost({ titulo: nome });
      setTitulo("");
      ok("Pauta criada");
      await carregar();
    } catch (e) {
      falhou("Não consegui criar a pauta", e);
    } finally {
      setCriando(false);
    }
  };

  const total = itens?.length ?? 0;

  return (
    <div className="max-w-[1000px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Redação</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">Os posts do blog</h1>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        O post mora aqui até estar pronto — rascunho não é commit. Cada um é
        medido em cinco camadas, uma por público que chega ao blog, e só quando
        elas fecham é que dá para publicar. Daí em diante é um botão: branch,
        commit do arquivo, PR, checks e merge. O que{" "}
        <strong>não</strong> é automático é a decisão — nada vai para a{" "}
        <code>main</code> sem você clicar, e o merge só acende com o CI verde.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <div className="mb-7 flex flex-wrap items-center gap-2">
        <input
          className="input max-w-[420px] flex-1"
          placeholder="título da pauta nova…"
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void criar();
          }}
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={criando || !titulo.trim()}
          onClick={() => void criar()}
        >
          {criando ? "…" : "anotar pauta"}
        </button>
      </div>

      {!itens && <p className="text-[13px] text-neutral-500">carregando…</p>}

      {itens && total === 0 && (
        <Vazio titulo="A redação está vazia">
          Anote a primeira pauta acima. Ela pode nascer de uma nota do vault ou
          de um doc de fase do Copiloto — o campo <em>origem</em> do editor é o
          que liga o post à fonte.
        </Vazio>
      )}

      <div className="flex flex-col gap-8">
        {ORDEM.map(({ estado, rotulo, explica }) => {
          const doGrupo = (itens ?? []).filter((p) => p.estado === estado);
          if (doGrupo.length === 0) return null;
          return (
            <section key={estado}>
              <div className="mb-3 flex items-baseline gap-3">
                <h2 className="m-0 text-[17px]">{rotulo}</h2>
                <span className="tnum text-[12px] text-neutral-600">
                  {porEstado[estado] ?? doGrupo.length}
                </span>
                <span className="text-[12.5px] text-neutral-600">{explica}</span>
              </div>
              <div className="flex flex-col gap-3">
                {doGrupo.map((p) => (
                  <Cartao key={p.id} post={p} />
                ))}
              </div>
            </section>
          );
        })}
      </div>

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}
    </div>
  );
}
