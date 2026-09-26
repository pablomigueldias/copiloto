"use client";

/**
 * A redação — o que fazer agora, como vai o blog, e os posts.
 *
 * A manchete é o próximo passo, não um título: a pergunta que eu fazia no
 * terminal ("o que eu faço agora?") é a primeira coisa que a tela responde, com
 * o botão que resolve. A ordem dos passos é do backend (`app/blog/painel.py`):
 * primeiro o que está quase no ar, por último o que ainda é ideia.
 *
 * Abaixo, os posts continuam agrupados por estado e não por data: "o que está
 * começado e parado?" é a pergunta que uma lista cronológica esconde.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { Icone } from "@/components/icones";
import { Cabecalho, Erro, Numero, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type {
  CandidataVault,
  EstadoPost,
  PainelBlog,
  Passo,
  PostLinha,
} from "@/lib/tipos";

// A ordem é a do trabalho, e é ela que desenha a lista de cima para baixo.
const ORDEM: { estado: EstadoPost; rotulo: string; explica: string }[] = [
  { estado: "rascunho", rotulo: "Escrevendo", explica: "texto começado — é aqui que o post trava" },
  { estado: "pronto", rotulo: "Pronto para publicar", explica: "as cinco camadas fecharam — falta o PR" },
  { estado: "pauta", rotulo: "Pautas", explica: "ideia anotada, sem uma linha escrita" },
  { estado: "publicado", rotulo: "Publicado", explica: "entrou na main e está no ar" },
  { estado: "arquivado", rotulo: "Arquivado", explica: "saiu do caminho sem ser apagado" },
];

const ROTULO_ESTADO: Record<EstadoPost, string> = {
  pauta: "pauta",
  rascunho: "escrevendo",
  pronto: "pronto",
  publicado: "no ar",
  arquivado: "arquivado",
};

const ROTULO_PILAR: Record<string, string> = {
  "ia-llms": "IA aplicada & LLMs",
  "dados-ml": "Dados, Análise & ML",
};

function haQuanto(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "agora";
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

function diaMes(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

/** Para onde o botão do passo leva. Passo sem post aponta para a seção da tela. */
function destino(p: Passo): string {
  if (p.post_id) return `/posts/${p.post_id}`;
  if (p.tipo === "pauta") return "#vault";
  return "#calendario";
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
          {post.data_publicacao ? `sai ${diaMes(post.data_publicacao)} · ` : ""}
          {haQuanto(post.updated_at)}
        </span>
      </div>

      {post.descricao && (
        <p className="m-0 max-w-[70ch] text-[13px] text-neutral-500">{post.descricao}</p>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-neutral-600">
        <span className="tnum">{plural(post.palavras, "palavra", "palavras")}</span>
        {post.tags.length > 0 && <span>{post.tags.join(" · ")}</span>}
        <span className={post.camadas_ok ? "text-accent" : "text-neutral-500"}>
          {post.camadas_ok ? "● camadas fechadas" : "○ faltam camadas"}
        </span>
        {post.publicado_em ? (
          <span className="text-accent">no ar · PR #{post.pr_numero}</span>
        ) : post.pr_numero ? (
          <span>PR #{post.pr_numero} aberto</span>
        ) : post.exportado_em ? (
          <span>exportado {haQuanto(post.exportado_em)}</span>
        ) : null}
        {post.estado === "publicado" &&
          (post.linkedin_postado_em ? (
            <span>LinkedIn postado</span>
          ) : post.linkedin_em ? (
            <span className="text-accent-300">LinkedIn {diaMes(post.linkedin_em)}</span>
          ) : null)}
      </div>
    </Link>
  );
}

/** A barra do M4: a marca é o mínimo (a divulgação começa ali), o fim é a série. */
function MetaM4({ m4 }: { m4: PainelBlog["m4"] }) {
  const pct = (n: number) => `${Math.min(100, (n / m4.completo) * 100)}%`;
  return (
    <div className="max-w-[520px]">
      <div className="relative h-[6px] overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
        <span className="absolute inset-y-0 left-0 bg-accent" style={{ width: pct(m4.publicados) }} />
        <span
          className="absolute inset-y-0 w-px bg-[var(--color-text)] opacity-60"
          style={{ left: pct(m4.minimo) }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11.5px] text-neutral-500">
        <span className="tnum">
          {m4.publicados} de {m4.completo} no ar
        </span>
        <span>
          {m4.publicados >= m4.minimo
            ? "divulgação ativa liberada"
            : `divulgação começa no ${m4.minimo}º post`}
        </span>
      </div>
    </div>
  );
}

function Calendario({ semanas }: { semanas: PainelBlog["calendario"] }) {
  return (
    <ol className="m-0 flex list-none flex-col p-0">
      {semanas.map((s, i) => (
        <li
          key={s.terca}
          className="flex items-baseline gap-4 border-b border-divider py-[9px] last:border-b-0"
        >
          <span
            className={`tnum w-[46px] flex-none text-[13px] ${i === 0 ? "text-accent" : "text-neutral-500"}`}
          >
            {diaMes(s.terca)}
          </span>
          {s.posts.length === 0 ? (
            <span className="text-[13px] text-neutral-600">
              {i === 0 ? "nada marcado para esta terça" : "—"}
            </span>
          ) : (
            <span className="flex min-w-0 flex-col gap-1">
              {s.posts.map((p) => (
                <Link key={p.id} href={`/posts/${p.id}`} className="truncate text-[13.5px] no-underline">
                  <span className="text-text">{p.titulo}</span>{" "}
                  <span className="text-[11.5px] text-neutral-500">· {ROTULO_ESTADO[p.estado]}</span>
                </Link>
              ))}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

function Vault({
  notas,
  importando,
  onImportar,
}: {
  notas: CandidataVault[] | null;
  importando: string | null;
  onImportar: (c: CandidataVault) => void;
}) {
  const novas = (notas ?? []).filter((n) => !n.post_id);
  return (
    <section id="vault" className="card flex flex-col gap-3">
      <div className="flex items-baseline gap-2">
        <span className="card-kicker">do vault</span>
        <span className="tnum ml-auto text-[11.5px] text-neutral-600">{novas.length}</span>
      </div>
      {notas === null ? (
        <p className="m-0 text-[12.5px] text-neutral-500">lendo o vault…</p>
      ) : novas.length === 0 ? (
        <p className="m-0 text-[12.5px] leading-[1.55] text-neutral-500">
          Nenhuma nota marcada. No Obsidian, adicione a propriedade <code>blog: ideia</code>{" "}
          (e, se quiser, <code>pilar: dados-ml</code>) numa nota de estudo. Só as pastas de
          estudo são lidas — Currículos, Concurso e Planos nunca aparecem aqui.
        </p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {novas.map((n) => (
            <li key={n.caminho} className="flex flex-col gap-1">
              <span className="text-[13.5px] text-text">{n.titulo}</span>
              <span className="truncate text-[11px] text-neutral-600" title={n.caminho}>
                {n.caminho.replace(/^Pessoal\//, "")} · {n.palavras} palavras
              </span>
              <button
                type="button"
                className="btn btn-secondary w-fit py-[3px] text-[12px]"
                disabled={importando !== null}
                onClick={() => onImportar(n)}
              >
                {importando === n.caminho ? "…" : "virar pauta"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Posts() {
  const router = useRouter();
  const [itens, setItens] = useState<PostLinha[] | null>(null);
  const [porEstado, setPorEstado] = useState<Record<string, number>>({});
  const [painel, setPainel] = useState<PainelBlog | null>(null);
  const [notas, setNotas] = useState<CandidataVault[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [criando, setCriando] = useState(false);
  const [importando, setImportando] = useState<string | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(
    (): Promise<void> =>
      Promise.all([api.posts(), api.painelBlog()])
        .then(([r, p]) => {
          setItens(r.itens);
          setPorEstado(r.por_estado);
          setPainel(p);
        })
        .catch((e: Error) => setErro(String(e.message ?? e))),
    [],
  );

  useEffect(() => {
    void carregar();
    // O vault varre disco: fica fora do `carregar` para não atrasar a manchete.
    api.vaultBlog().then(setNotas).catch(() => setNotas([]));
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

  const importar = async (c: CandidataVault) => {
    setImportando(c.caminho);
    try {
      const post = await api.importarNota(c.caminho);
      router.push(`/posts/${post.id}`);
    } catch (e) {
      falhou("Não consegui importar a nota", e);
      setImportando(null);
    }
  };

  const primeiro = painel?.proximos[0];
  const resto = painel?.proximos.slice(1) ?? [];
  const total = itens?.length ?? 0;

  return (
    <div className="max-w-[1180px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Redação</Cabecalho>

      {erro && <Erro>{erro}</Erro>}

      {/* ── a manchete: o próximo passo ─────────────────────────── */}
      <section className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0 max-w-[720px]">
          <div className="card-kicker mb-3">o que fazer agora</div>
          <h1 className="m-0 mb-3 text-[clamp(30px,3.6vw,44px)] leading-[1.08] tracking-[-0.015em]">
            {primeiro ? primeiro.titulo : painel ? "Tudo em dia" : "…"}
          </h1>
          <p className="m-0 max-w-[58ch] text-[15px] text-muted">
            {primeiro?.detalhe ??
              "Nada esperando você. Anote a próxima pauta ou marque uma nota do vault."}
          </p>
        </div>
        {primeiro?.acao && (
          <Link
            href={destino(primeiro)}
            className="btn btn-primary flex-none px-[18px] py-[10px] text-[15px]"
          >
            {primeiro.acao}
            <Icone nome="seta" />
          </Link>
        )}
      </section>

      {painel && (
        <>
          <div className="my-[30px] flex flex-wrap gap-[38px]">
            <Numero valor={painel.m4.publicados} rotulo="Posts no ar" />
            <Numero valor={painel.cadencia.ultimos_30_dias} rotulo="Nos últimos 30 dias" />
            <Numero
              valor={painel.cadencia.dias_desde_ultimo ?? "—"}
              rotulo="Dias desde o último"
              cor={(painel.cadencia.dias_desde_ultimo ?? 0) > 7 ? "text-accent-300" : undefined}
            />
            <Numero
              valor={painel.funil.pauta + painel.funil.rascunho + painel.funil.pronto}
              rotulo="Na fila"
            />
            <Numero
              valor={`US$ ${painel.gerar.gasto_usd.toFixed(2)}`}
              rotulo={`Gemini do mês · teto ${painel.gerar.teto_usd.toFixed(2)}`}
              cor={painel.gerar.disponivel ? "text-neutral-400" : "text-accent-300"}
            />
          </div>

          <MetaM4 m4={painel.m4} />
        </>
      )}

      <hr className="hr my-[30px]" />

      <div className="grid items-start gap-[clamp(28px,4vw,56px)] lg:grid-cols-[minmax(0,7fr)_minmax(270px,3fr)]">
        {/* ── coluna principal ─────────────────────────────────── */}
        <div className="flex min-w-0 flex-col gap-9">
          {resto.length > 0 && (
            <section>
              <h2 className="m-0 mb-3 text-[18px]">Depois disso</h2>
              <ol className="m-0 flex list-none flex-col gap-2 p-0">
                {resto.map((p, i) => (
                  <li key={`${p.tipo}-${p.post_id ?? i}`}>
                    <Link
                      href={destino(p)}
                      className="card flex items-baseline gap-3 py-[11px] no-underline transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_35%,transparent)]"
                    >
                      <span className="tnum w-[18px] flex-none text-[12px] text-neutral-600">
                        {i + 2}
                      </span>
                      <span className="flex min-w-0 flex-col gap-[3px]">
                        <span className="text-[14px] text-text">{p.titulo}</span>
                        <span className="text-[12.5px] text-neutral-500">{p.detalhe}</span>
                      </span>
                      {p.acao && (
                        <span className="ml-auto flex-none text-[12px] text-accent">{p.acao} →</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ol>
            </section>
          )}

          <section>
            <div className="mb-3 flex items-baseline gap-3">
              <h2 className="m-0 text-[18px]">Os posts</h2>
              <span className="text-[12.5px] text-neutral-600">
                agrupados pelo que falta, não pela data
              </span>
            </div>

            <div className="mb-6 flex flex-wrap items-center gap-2">
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
                className="btn btn-secondary"
                disabled={criando || !titulo.trim()}
                onClick={() => void criar()}
              >
                {criando ? "…" : "anotar pauta"}
              </button>
            </div>

            {!itens && <p className="text-[13px] text-neutral-500">carregando…</p>}

            {itens && total === 0 && (
              <Vazio titulo="A redação está vazia">
                Anote a primeira pauta acima ou traga uma nota do vault (coluna ao lado). O
                campo <em>origem</em> é o que liga o post à fonte — e o que permite gerar o
                rascunho.
              </Vazio>
            )}

            <div className="flex flex-col gap-8">
              {ORDEM.map(({ estado, rotulo, explica }) => {
                const doGrupo = (itens ?? []).filter((p) => p.estado === estado);
                if (doGrupo.length === 0) return null;
                return (
                  <section key={estado}>
                    <div className="mb-3 flex items-baseline gap-3">
                      <h3 className="m-0 text-[15px]">{rotulo}</h3>
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
          </section>
        </div>

        {/* ── coluna do lado: calendário, pilares, vault ───────── */}
        <aside className="flex flex-col gap-5">
          {painel && (
            <section id="calendario" className="card">
              <div className="mb-1 flex items-baseline gap-2">
                <span className="card-kicker">próximas terças</span>
                <span className="ml-auto text-[11px] text-neutral-600">1 post por semana</span>
              </div>
              <Calendario semanas={painel.calendario} />
            </section>
          )}

          {painel && (
            <section className="card flex flex-col gap-3">
              <span className="card-kicker">pilares</span>
              {painel.pilares.map((p) => (
                <div key={p.pilar} className="flex flex-col gap-[3px]">
                  <div className="flex items-baseline gap-2">
                    <span className="text-[13.5px]">{ROTULO_PILAR[p.pilar] ?? p.pilar}</span>
                    <span className="tnum ml-auto text-[12px] text-neutral-500">
                      {p.publicados} no ar · {p.na_fila} na fila
                    </span>
                  </div>
                  <span
                    className={`text-[11.5px] ${
                      p.dias_sem_post === null || p.dias_sem_post > 30
                        ? "text-accent-300"
                        : "text-neutral-600"
                    }`}
                  >
                    {p.dias_sem_post === null
                      ? "nenhum post ainda"
                      : p.dias_sem_post === 0
                        ? "post hoje"
                        : `último há ${p.dias_sem_post} d`}
                  </span>
                </div>
              ))}
            </section>
          )}

          <Vault notas={notas} importando={importando} onImportar={(c) => void importar(c)} />

          {painel && painel.parados.length > 0 && (
            <section className="card flex flex-col gap-2">
              <span className="card-kicker text-accent-300">parados</span>
              {painel.parados.map((p) => (
                <Link key={p.id} href={`/posts/${p.id}`} className="text-[13px] no-underline">
                  <span className="text-text">{p.titulo}</span>{" "}
                  <span className="tnum text-[11.5px] text-neutral-500">· {p.dias} d sem mexer</span>
                </Link>
              ))}
            </section>
          )}

          {painel && !painel.gerar.disponivel && (
            <section className="card flex flex-col gap-2">
              <span className="card-kicker">rascunho no Gemini</span>
              <p className="m-0 text-[12.5px] leading-[1.55] text-neutral-500">
                Desligado: {painel.gerar.motivo}.{" "}
                {painel.gerar.motivo?.includes("GEMINI_API_KEY_BLOG") && (
                  <>
                    Crie uma chave só para o blog no Google AI Studio, ponha em{" "}
                    <code>GEMINI_API_KEY_BLOG=</code> no <code>.env</code> e reinicie a API.
                  </>
                )}
              </p>
            </section>
          )}
        </aside>
      </div>

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}
    </div>
  );
}
