"use client";

/**
 * O editor de um post — texto à esquerda, a régua dos quatro públicos à direita.
 *
 * Duas decisões de comportamento que valem mais que a aparência:
 *
 * 1. **Autosave com diff.** O que vai no PATCH é só o campo que mudou. Mandar o
 *    objeto inteiro a cada tecla faria duas abas abertas sobrescreverem uma à
 *    outra, e faria o backend versionar o corpo a cada salvamento de descrição.
 * 2. **O diagnóstico vem do servidor.** Nenhuma camada é medida aqui: a régua
 *    mora em `app/blog/camadas.py`, que é a mesma que o portão do `pronto` usa.
 *    Medir de novo no front seria manter duas réguas — e a hora em que elas
 *    discordarem é a hora em que eu deixo de confiar nas duas.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { Cabecalho, Erro } from "@/components/ui";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import type {
  Camada,
  PostDetalhe,
  SituacaoPr,
  VersaoPost,
  VocabularioBlog,
} from "@/lib/tipos";

const MS_AUTOSAVE = 1500;
// De quanto em quanto tempo a tela pergunta ao GitHub como vão os checks.
// 15 s porque o CI do blog leva ~2 min: mais rápido que isso é gastar chamada
// de API para ver a mesma bolinha amarela.
const MS_CHECKS = 15000;

const PUBLICO: Record<string, string> = {
  entusiasta: "entusiasta",
  cliente: "cliente",
  tecnico: "técnico",
  recrutador: "recrutador",
  todos: "todos",
};

type Form = {
  titulo: string;
  slug: string;
  descricao: string;
  pilar: string;
  tags: string[];
  corpo: string;
  notas: string;
  origem: Record<string, string>[];
  data_publicacao: string;
};

function doPost(p: PostDetalhe): Form {
  return {
    titulo: p.titulo,
    slug: p.slug ?? "",
    descricao: p.descricao ?? "",
    pilar: p.pilar ?? "",
    tags: p.tags,
    corpo: p.corpo,
    notas: p.notas ?? "",
    origem: p.origem,
    data_publicacao: p.data_publicacao ?? "",
  };
}

/** O que mudou em relação ao que o servidor tem. Vazio = nada para salvar. */
function diferenca(form: Form, post: PostDetalhe): Record<string, unknown> {
  const base = doPost(post);
  const saida: Record<string, unknown> = {};
  for (const chave of Object.keys(form) as (keyof Form)[]) {
    const atual = form[chave];
    const antigo = base[chave];
    const mudou =
      typeof atual === "string"
        ? atual !== antigo
        : JSON.stringify(atual) !== JSON.stringify(antigo);
    if (mudou) {
      // String vazia em campo opcional é `null`, não "": o schema do blog
      // recusaria uma data vazia, e "" numa descrição mentiria sobre estar
      // preenchida.
      saida[chave] =
        typeof atual === "string" && atual.trim() === "" && chave !== "titulo"
          ? null
          : atual;
    }
  }
  return saida;
}

function Contador({ n, min, max }: { n: number; min: number; max: number }) {
  const ok = n >= min && n <= max;
  return (
    <span className={`tnum text-[11px] ${ok ? "text-neutral-600" : "text-accent-300"}`}>
      {n}/{max}
      {n < min ? ` (mín. ${min})` : ""}
    </span>
  );
}

function CamadaCartao({ camada }: { camada: Camada }) {
  return (
    <div className="card flex flex-col gap-[7px] p-[14px]">
      <div className="flex items-baseline gap-2">
        <span className={camada.ok ? "text-accent" : "text-accent-300"}>
          {camada.ok ? "●" : "○"}
        </span>
        <span className="text-[13.5px]">{camada.rotulo}</span>
        <span className="card-kicker ml-auto">{PUBLICO[camada.publico]}</span>
      </div>
      <p className="m-0 text-[12px] italic text-neutral-600">{camada.pergunta}</p>
      <ul className="m-0 flex list-none flex-col gap-[5px] p-0">
        {camada.sinais.map((s, i) => (
          <li key={i} className="text-[12px]">
            <span className={s.ok ? "text-neutral-500" : "text-accent-300"}>
              {s.ok ? "✓" : "✗"} {s.texto}
            </span>
            {!s.ok && s.dica && (
              <div className="mt-[3px] pl-[14px] text-[11.5px] leading-[1.5] text-neutral-600">
                {s.dica}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const [post, setPost] = useState<PostDetalhe | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [vocab, setVocab] = useState<VocabularioBlog | null>(null);
  const [versoes, setVersoes] = useState<VersaoPost[]>([]);
  const [previa, setPrevia] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [montandoPrevia, setMontandoPrevia] = useState(false);
  const [pr, setPr] = useState<SituacaoPr | null>(null);
  const [publicando, setPublicando] = useState(false);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(
    (): Promise<void> =>
      api
        .post(id)
        .then((p) => {
          setPost(p);
          // O form só é semeado uma vez: recarregar em cima do que eu estou
          // digitando é o defeito que a tela da fila já pagou para aprender.
          setForm((f) => f ?? doPost(p));
        })
        .catch((e: Error) => setErro(String(e.message ?? e))),
    [id],
  );

  useEffect(() => {
    void carregar();
    api.vocabularioBlog().then(setVocab).catch(() => {});
    api.versoesPost(id).then(setVersoes).catch(() => {});
  }, [carregar, id]);

  const verPr = useCallback(
    (): Promise<void> =>
      api
        .situacaoPrPost(id)
        .then(setPr)
        .catch(() => {}),
    [id],
  );

  // Enquanto houver PR aberto, a tela acompanha os checks sozinha. Sem PR, não
  // há o que perguntar — e o `post.pr_numero` evita a chamada inútil.
  useEffect(() => {
    if (!post?.pr_numero) return;
    void verPr();
    if (post.estado === "publicado") return;
    const t = setInterval(() => void verPr(), MS_CHECKS);
    return () => clearInterval(t);
  }, [post?.pr_numero, post?.estado, verPr]);

  /**
   * Salva o diff. Recebe `form` e `post` por parâmetro, e não de um ref: o
   * React 19 proíbe escrever ref no render, e passar o valor deixa explícito
   * que o que se salva é o estado daquele instante.
   */
  const salvar = useCallback(
    async (f: Form, p: PostDetalhe): Promise<PostDetalhe | null> => {
      const campos = diferenca(f, p);
      if (Object.keys(campos).length === 0) return p;
      setSalvando(true);
      try {
        const novo = await api.salvarPost(id, campos);
        setPost(novo);
        if ("corpo" in campos) api.versoesPost(id).then(setVersoes).catch(() => {});
        return novo;
      } catch (e) {
        falhou("Não consegui salvar", e);
        return null;
      } finally {
        setSalvando(false);
      }
    },
    [id, falhou],
  );

  // Autosave: um timer por edição, reiniciado a cada tecla.
  useEffect(() => {
    if (!form || !post) return;
    if (Object.keys(diferenca(form, post)).length === 0) return;
    const t = setTimeout(() => void salvar(form, post), MS_AUTOSAVE);
    return () => clearTimeout(t);
  }, [form, post, salvar]);

  const sujo = useMemo(
    () => (form && post ? Object.keys(diferenca(form, post)).length > 0 : false),
    [form, post],
  );

  // Ctrl+S salva agora. O autosave já cobre, mas dedo treinado aperta de
  // qualquer jeito — e o browser abrindo "salvar página" no meio de um post é
  // interrupção gratuita.
  useEffect(() => {
    const atalho = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (form && post) void salvar(form, post);
      }
    };
    window.addEventListener("keydown", atalho);
    return () => window.removeEventListener("keydown", atalho);
  }, [form, post, salvar]);

  const marcarPronto = async (f: Form, p: PostDetalhe) => {
    await salvar(f, p);
    try {
      setPost(await api.estadoPost(id, "pronto"));
      ok("Pronto para exportar");
    } catch (e) {
      // O 409 traz a lista do que falta — é a mensagem mais útil da tela.
      falhou("Ainda não está pronto", e);
    }
  };

  const mudarEstado = async (estado: string) => {
    try {
      setPost(await api.estadoPost(id, estado));
      ok(`Agora é ${estado}`);
    } catch (e) {
      falhou("Não consegui mudar o estado", e);
    }
  };

  /**
   * Abre a aba **antes** do await.
   *
   * `window.open` depois de uma requisição perde o gesto do usuário e cai no
   * bloqueador de pop-up do Chrome. Abrir primeiro e só então apontar a aba
   * para a URL mantém a abertura dentro do clique.
   */
  const verComoFica = async (f: Form, p: PostDetalhe) => {
    await salvar(f, p);
    const aba = window.open("", "_blank");
    setMontandoPrevia(true);
    try {
      const r = await api.previaNoSitePost(id);
      if (aba) aba.location.href = r.url;
      if (r.aviso) falhou(r.aviso);
      else ok("Prévia montada no blog — o arquivo entrou como rascunho");
      await carregar();
    } catch (e) {
      aba?.close();
      // O gerador do blog reprova por frontmatter ou pelo linter de
      // privacidade, e a mensagem dele é a parte útil.
      falhou("A prévia não passou no gerador do blog", e);
    } finally {
      setMontandoPrevia(false);
    }
  };

  const abrirPr = async (f: Form, p: PostDetalhe) => {
    await salvar(f, p);
    setPublicando(true);
    try {
      const r = await api.abrirPrPost(id);
      ok(`PR #${r.pr_numero} aberto — o CI leva uns minutos`);
      await carregar();
      await verPr();
    } catch (e) {
      falhou("Não consegui abrir o PR", e);
    } finally {
      setPublicando(false);
    }
  };

  const publicar = async () => {
    setPublicando(true);
    try {
      const r = await api.publicarPost(id);
      // O deploy é do Workers Builds, que escuta a main: leva alguns minutos
      // e não passa por aqui. Por isso a mensagem fala em "a caminho".
      ok(`Mergeado. O post vai ao ar em ${r.url} assim que a Cloudflare buildar`);
      await carregar();
      await verPr();
    } catch (e) {
      falhou("Não consegui concluir", e);
    } finally {
      setPublicando(false);
    }
  };

  const exportar = async (f: Form, p: PostDetalhe) => {
    await salvar(f, p);
    try {
      const r = await api.exportarPost(id);
      ok(`Escrito em ${r.caminho} — falta o commit no repo do blog`);
      await carregar();
    } catch (e) {
      falhou("Não consegui exportar", e);
    }
  };

  if (erro) return <div className="p-8"><Erro>{erro}</Erro></div>;
  if (!post || !form) return <p className="p-8 text-[13px] text-neutral-500">carregando…</p>;

  const d = post.diagnostico;
  const mudar = <K extends keyof Form>(campo: K, valor: Form[K]) =>
    setForm({ ...form, [campo]: valor });

  return (
    <div className="px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>
        <Link href="/posts" className="text-accent no-underline">
          Redação
        </Link>{" "}
        · {post.estado}
      </Cabecalho>

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* ── o texto ──────────────────────────────────────────── */}
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <input
            className="input font-heading text-[26px] leading-[1.2]"
            value={form.titulo}
            onChange={(e) => mudar("titulo", e.target.value)}
            placeholder="título do post"
          />

          <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-neutral-600">
            <span className="tnum">{d.palavras} palavras</span>
            <span className="tnum">{d.minutos} min de leitura</span>
            <span>
              {salvando ? "salvando…" : sujo ? "com alterações não salvas" : "salvo"}
            </span>
            {versoes.length > 0 && (
              <span className="tnum">
                {versoes.length} versão(ões) guardada(s) · última v{versoes[0].numero}
              </span>
            )}
          </div>

          <textarea
            className="input min-h-[62vh] resize-y font-mono text-[13.5px] leading-[1.7]"
            value={form.corpo}
            onChange={(e) => mudar("corpo", e.target.value)}
            placeholder={
              "Abra com uma cena concreta, não com \"neste post vou falar\".\n\n## O problema\n\n…"
            }
          />

          <details className="card">
            <summary className="cursor-pointer text-[13px] text-muted">
              Notas privadas — nunca vão para o MDX
            </summary>
            <textarea
              className="input mt-3 min-h-[120px] resize-y text-[13px]"
              value={form.notas}
              onChange={(e) => mudar("notas", e.target.value)}
              placeholder="link solto, nome de cliente, raciocínio de bastidor…"
            />
          </details>

          {previa !== null && (
            <div className="card">
              <div className="mb-2 flex items-center gap-3">
                <span className="card-kicker">o .mdx que sairia</span>
                <button
                  type="button"
                  className="btn btn-ghost ml-auto text-[12px]"
                  onClick={() => setPrevia(null)}
                >
                  fechar
                </button>
              </div>
              <pre className="m-0 max-h-[50vh] overflow-auto whitespace-pre-wrap rounded-[8px] border border-divider bg-[color-mix(in_srgb,black_20%,transparent)] p-3 font-mono text-[12px] leading-[1.6] text-muted">
                {previa}
              </pre>
            </div>
          )}
        </div>

        {/* ── a régua e o frontmatter ──────────────────────────── */}
        <aside className="flex w-full flex-none flex-col gap-4 lg:w-[360px]">
          <div>
            <div className="mb-2 flex items-baseline gap-2">
              <h2 className="m-0 text-[15px]">As cinco camadas</h2>
              <span className={`text-[11.5px] ${d.camadas_ok ? "text-accent" : "text-accent-300"}`}>
                {d.camadas_ok ? "fechadas" : `${d.falta.length} pendente(s)`}
              </span>
            </div>
            <p className="m-0 mb-3 text-[12px] leading-[1.5] text-neutral-600">
              Uma por público que chega ao blog. Todo sinal é medido no texto —
              nenhum depende de eu me julgar honestamente às 23h.
            </p>
            <div className="flex flex-col gap-2">
              {d.camadas.map((c) => (
                <CamadaCartao key={c.id} camada={c} />
              ))}
            </div>
          </div>

          <div className="card flex flex-col gap-3">
            <span className="card-kicker">frontmatter</span>

            <label className="flex flex-col gap-1 text-[12px] text-neutral-500">
              slug (nome do arquivo e URL)
              <input
                className="input font-mono text-[12.5px]"
                value={form.slug}
                onChange={(e) => mudar("slug", e.target.value)}
                placeholder="rag-que-diz-nao-sei"
              />
            </label>

            <label className="flex flex-col gap-1 text-[12px] text-neutral-500">
              <span className="flex items-baseline gap-2">
                descrição
                {vocab && (
                  <Contador
                    n={form.descricao.trim().length}
                    min={vocab.descricao[0]}
                    max={vocab.descricao[1]}
                  />
                )}
              </span>
              <textarea
                className="input min-h-[74px] resize-y text-[12.5px]"
                value={form.descricao}
                onChange={(e) => mudar("descricao", e.target.value)}
                placeholder="o resultado, não o tema — é o texto do card e do compartilhamento"
              />
            </label>

            <label className="flex flex-col gap-1 text-[12px] text-neutral-500">
              pilar
              <select
                className="input text-[12.5px]"
                value={form.pilar}
                onChange={(e) => mudar("pilar", e.target.value)}
              >
                <option value="">—</option>
                {(vocab?.pilares ?? []).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-[12px] text-neutral-500">
              data de publicação
              <input
                type="date"
                className="input text-[12.5px]"
                value={form.data_publicacao}
                onChange={(e) => mudar("data_publicacao", e.target.value)}
              />
            </label>

            <div className="flex flex-col gap-[6px] text-[12px] text-neutral-500">
              <span>
                tags{" "}
                <span className="tnum text-[11px] text-neutral-600">
                  {form.tags.length}/{vocab?.tags_max ?? 5}
                </span>
              </span>
              {/* Lista curada, não campo livre: tag nova entra no schema do blog
                  antes de ser usada num post. */}
              <div className="flex flex-wrap gap-[5px]">
                {(vocab?.tags ?? []).map((t) => {
                  const marcada = form.tags.includes(t);
                  const cheio = form.tags.length >= (vocab?.tags_max ?? 5);
                  return (
                    <button
                      key={t}
                      type="button"
                      disabled={!marcada && cheio}
                      onClick={() =>
                        mudar(
                          "tags",
                          marcada ? form.tags.filter((x) => x !== t) : [...form.tags, t],
                        )
                      }
                      className={`rounded-[6px] border px-[8px] py-[3px] text-[11.5px] transition-colors ${
                        marcada
                          ? "border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200"
                          : "border-divider text-neutral-500 hover:text-text disabled:opacity-40"
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col gap-[6px] text-[12px] text-neutral-500">
              <span>origem (caminho relativo, sem /home nem /mnt)</span>
              {form.origem.map((item, i) => {
                const chave = Object.keys(item)[0] ?? "vault";
                return (
                  <div key={i} className="flex gap-1">
                    <select
                      className="input w-[92px] text-[12px]"
                      value={chave}
                      onChange={(e) => {
                        const nova = [...form.origem];
                        nova[i] = { [e.target.value]: item[chave] ?? "" };
                        mudar("origem", nova);
                      }}
                    >
                      <option value="vault">vault</option>
                      <option value="copiloto">copiloto</option>
                    </select>
                    <input
                      className="input flex-1 font-mono text-[12px]"
                      value={item[chave] ?? ""}
                      onChange={(e) => {
                        const nova = [...form.origem];
                        nova[i] = { [chave]: e.target.value };
                        mudar("origem", nova);
                      }}
                      placeholder="docs/fase03.md"
                    />
                    <button
                      type="button"
                      className="btn btn-ghost px-2 text-[12px]"
                      onClick={() =>
                        mudar(
                          "origem",
                          form.origem.filter((_, j) => j !== i),
                        )
                      }
                    >
                      ×
                    </button>
                  </div>
                );
              })}
              <button
                type="button"
                className="btn btn-secondary w-fit py-[4px] text-[12px]"
                onClick={() => mudar("origem", [...form.origem, { vault: "" }])}
              >
                + origem
              </button>
            </div>

            {d.frontmatter_erros.length > 0 && (
              <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[11.5px] text-accent-300">
                {d.frontmatter_erros.map((e, i) => (
                  <li key={i}>✗ {e}</li>
                ))}
              </ul>
            )}
          </div>

          {/* A esteira: PR, checks e o merge. Aparece a partir do `pronto`,
              porque antes disso não há o que publicar. */}
          {(post.estado === "pronto" || post.pr_numero) && (
            <div className="card flex flex-col gap-3">
              <div className="flex items-baseline gap-2">
                <span className="card-kicker">publicação</span>
                {post.publicado_em && (
                  <a
                    href={`https://pabloortiz.dev/blog/${post.slug}`}
                    target="_blank"
                    rel="noopener"
                    className="ml-auto text-[12px] text-accent"
                  >
                    ver no ar ↗
                  </a>
                )}
              </div>

              {!post.pr_numero ? (
                <>
                  <p className="m-0 text-[12px] leading-[1.55] text-neutral-500">
                    Abre uma branch a partir da <code>main</code>, commita{" "}
                    <strong>só o arquivo deste post</strong> e abre o PR. O resto
                    do repo do blog fica onde está, e nada é mergeado sem você.
                  </p>
                  <button
                    type="button"
                    className="btn btn-primary w-fit"
                    disabled={publicando}
                    onClick={() => void abrirPr(form, post)}
                  >
                    {publicando ? "abrindo…" : "abrir PR"}
                  </button>
                </>
              ) : (
                <>
                  <a
                    href={post.pr_url ?? "#"}
                    target="_blank"
                    rel="noopener"
                    className="text-[13px] text-accent"
                  >
                    PR #{post.pr_numero} ↗
                  </a>

                  {pr?.checks?.length ? (
                    <ul className="m-0 flex list-none flex-col gap-1 p-0">
                      {pr.checks.map((c) => (
                        <li key={c.nome} className="text-[12px]">
                          <span
                            className={
                              c.resultado === "SUCCESS"
                                ? "text-accent"
                                : c.resultado === "FAILURE"
                                  ? "text-accent-300"
                                  : "text-neutral-500"
                            }
                          >
                            {c.resultado === "SUCCESS"
                              ? "✓"
                              : c.resultado === "FAILURE"
                                ? "✗"
                                : "◌"}{" "}
                            {c.nome}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="m-0 text-[12px] text-neutral-600">
                      {pr ? "o CI ainda não começou" : "consultando…"}
                    </p>
                  )}

                  {post.estado !== "publicado" && (
                    <button
                      type="button"
                      className="btn btn-primary w-fit"
                      disabled={publicando || !pr?.mergeavel}
                      title={
                        pr?.mergeavel ? "" : "esperando os checks fecharem em verde"
                      }
                      onClick={() => void publicar()}
                    >
                      {publicando ? "publicando…" : "publicar (merge na main)"}
                    </button>
                  )}

                  {post.estado === "publicado" && (
                    <p className="m-0 text-[12px] leading-[1.5] text-neutral-500">
                      Mergeado. O deploy de produção é da Cloudflare (Workers
                      Builds, disparado pela <code>main</code>) e leva alguns
                      minutos.
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void salvar(form, post)}
              disabled={!sujo || salvando}
            >
              salvar
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() =>
                api
                  .previaPost(id)
                  .then((r) => setPrevia(r.mdx))
                  .catch((e) => falhou("Não consegui montar a prévia", e))
              }
            >
              ver o MDX
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={montandoPrevia || !post.slug}
              title={post.slug ? "" : "precisa de slug: é o nome do arquivo e a URL"}
              onClick={() => void verComoFica(form, post)}
            >
              {montandoPrevia ? "montando…" : "ver como fica"}
            </button>
            {post.estado === "publicado" ? null : post.estado !== "pronto" ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void marcarPronto(form, post)}
                disabled={!d.exportavel}
                title={d.exportavel ? "" : "faltam camadas ou frontmatter"}
              >
                marcar pronto
              </button>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => void exportar(form, post)}>
                exportar .mdx
              </button>
            )}
            {post.estado !== "arquivado" && (
              <button
                type="button"
                className="btn btn-ghost text-[12px]"
                onClick={() => void mudarEstado("arquivado")}
              >
                arquivar
              </button>
            )}
          </div>

          {post.exportado_em && !post.pr_numero && (
            <p className="m-0 text-[11.5px] leading-[1.5] text-neutral-600">
              Exportado à mão: o arquivo está no working tree do repo do blog, e
              o commit é seu. Pelo botão de publicar, nada disso é necessário —
              ele commita numa branch própria sem tocar na sua árvore.
            </p>
          )}
        </aside>
      </div>

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}
    </div>
  );
}
