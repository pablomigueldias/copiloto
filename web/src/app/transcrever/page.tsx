"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { Cabecalho, Erro } from "@/components/ui";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import type { EstadoTranscricao } from "@/lib/tipos";

const relogio = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** O formulário da nota, montado a partir do que o modelo sugeriu. */
function FormularioNota({
  estado,
  pastas,
  tags,
  onSalvar,
  salvando,
}: {
  estado: EstadoTranscricao;
  pastas: string[];
  tags: string[];
  onSalvar: (c: { titulo: string; pasta: string; tags: string[] }) => void;
  salvando: boolean;
}) {
  const s = estado.sugestao!;
  const [titulo, setTitulo] = useState(s.titulo);
  const [pasta, setPasta] = useState(s.pasta);
  const [escolhidas, setEscolhidas] = useState<string[]>(s.tags);
  const [nova, setNova] = useState("");

  // A união do que o vault já tem com o que o modelo propôs: reaproveitar tag
  // existente é o que impede `Estudos/Python` nascer ao lado de `Pessoal/Python`.
  const cardapio = Array.from(new Set([...s.tags, ...tags]));

  return (
    <section className="card elev-sm mb-6">
      <div className="card-kicker mb-3">Nota sugerida</div>

      <label className="card-kicker mb-[6px] block text-neutral-400" htmlFor="titulo">
        Título
      </label>
      <input
        id="titulo"
        className="input mb-3"
        value={titulo}
        onChange={(e) => setTitulo(e.target.value)}
      />

      <label className="card-kicker mb-[6px] block text-neutral-400" htmlFor="pasta">
        Pasta no vault
      </label>
      <input
        id="pasta"
        list="pastas-do-vault"
        className="input mb-1"
        value={pasta}
        onChange={(e) => setPasta(e.target.value)}
        placeholder="_inbox"
      />
      <datalist id="pastas-do-vault">
        {pastas.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>
      <p className="m-0 mb-3 text-[12px] text-neutral-600">
        {s.pasta
          ? "Veio das notas vizinhas — o modelo viu como as irmãs se chamam antes de nomear esta."
          : "Sem vizinho próximo no vault: assunto novo, vai para _inbox."}
      </p>

      <span className="card-kicker mb-[6px] block text-neutral-400">Tags</span>
      <div className="mb-2 flex flex-wrap gap-[6px]">
        {cardapio.map((t) => {
          const on = escolhidas.includes(t);
          return (
            <button
              key={t}
              type="button"
              onClick={() =>
                setEscolhidas((v) =>
                  on ? v.filter((x) => x !== t) : [...v, t],
                )
              }
              className={`tag ${on ? "tag-accent" : "tag-neutral"}`}
            >
              {t}
            </button>
          );
        })}
      </div>
      <div className="mb-3 flex gap-2">
        <input
          className="input max-w-[220px]"
          value={nova}
          placeholder="nova tag"
          onChange={(e) => setNova(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || !nova.trim()) return;
            e.preventDefault();
            setEscolhidas((v) => Array.from(new Set([...v, nova.trim()])));
            setNova("");
          }}
        />
      </div>

      {s.resumo && (
        <p className="m-0 mb-2 text-[14px] leading-[1.6] text-muted">{s.resumo}</p>
      )}
      {s.destaques.length > 0 && (
        <ul className="m-0 mb-3 flex list-disc flex-col gap-1 pl-5 text-[13.5px] text-muted">
          {s.destaques.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
        </ul>
      )}
      {s.corrigidos.length > 0 && (
        <p className="m-0 mb-3 text-[12.5px] text-neutral-500">
          O glossário corrigiu: {s.corrigidos.join(", ")} — vale acrescentar o
          que faltou nele.
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={salvando || !titulo.trim()}
          onClick={() => onSalvar({ titulo, pasta, tags: escolhidas })}
          className="btn btn-primary px-4 py-[9px]"
        >
          {salvando ? "salvando…" : "Salvar no vault"}
        </button>
        <span className="tnum text-[12px] text-neutral-600">
          {s.palavras} palavras · indexa a nota na hora
        </span>
      </div>
    </section>
  );
}

export default function Transcrever() {
  const [estado, setEstado] = useState<EstadoTranscricao | null>(null);
  const [destinos, setDestinos] = useState<{
    pastas: string[];
    tags: string[];
    vault: string;
  } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const { aviso, ok, falhou, fechar } = useAvisos();
  const fim = useRef<HTMLDivElement>(null);

  const puxar = useCallback(
    (): Promise<void> =>
      api
        .estadoTranscricao()
        .then(setEstado)
        .catch((e: Error) => setErro(String(e.message ?? e))),
    [],
  );

  useEffect(() => {
    void puxar();
    api.destinosTranscricao().then(setDestinos).catch(() => {});
    // Os blocos são reescritos a cada 20 s; olhar a cada 3 é folgado o
    // bastante para a tela parecer viva sem martelar o servidor.
    const t = setInterval(() => void puxar(), 3000);
    return () => clearInterval(t);
  }, [puxar]);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [estado?.trechos.length]);

  const acao = async (
    fn: () => Promise<unknown>,
    sucesso: string,
    falha: string,
  ) => {
    setOcupado(true);
    try {
      await fn();
      ok(sucesso);
      await puxar();
    } catch (e) {
      falhou(falha, e);
    } finally {
      setOcupado(false);
    }
  };

  const gravando = estado?.estado === "gravando";
  const processando = estado?.estado === "processando";
  const revisando = estado?.estado === "revisar";
  const ocioso = estado?.estado === "ocioso";

  return (
    <div className="max-w-[900px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Transcrever</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        Aula, reunião, vídeo
      </h1>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        Os blocos são reescritos durante a gravação, na GPU que ficaria ociosa.
        O resultado não é a transcrição bem formatada — é uma nota de estudo,
        com título e pasta vindos das notas vizinhas do vault.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <div className="card elev-sm mb-6 flex flex-row flex-wrap items-center gap-4">
        <span
          className={`h-[9px] w-[9px] flex-none rounded-full ${
            gravando
              ? "animate-pulse bg-accent"
              : processando
                ? "bg-accent-700"
                : revisando
                  ? "bg-accent-400"
                  : "bg-neutral-700"
          }`}
        />
        <span className="text-[14px]">
          {estado?.estado ?? "…"}
          {estado?.etapa ? (
            <span className="text-neutral-500"> · {estado.etapa}</span>
          ) : null}
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="tnum text-[13px] text-neutral-500">
            {estado ? relogio(estado.segundos) : "00:00"} ·{" "}
            {estado?.palavras ?? 0} palavras
            {estado && estado.blocos > 0
              ? ` · bloco ${estado.bloco} de ${estado.blocos}`
              : ""}
          </span>

          {ocioso && (
            <>
              <button
                type="button"
                disabled={ocupado}
                onClick={() =>
                  acao(
                    () => api.iniciarTranscricao("sistema"),
                    "Gravando o áudio do sistema",
                    "Não consegui começar",
                  )
                }
                className="btn btn-primary"
              >
                ● gravar o sistema
              </button>
              <button
                type="button"
                disabled={ocupado}
                onClick={() =>
                  acao(
                    () => api.iniciarTranscricao("mic"),
                    "Gravando o microfone",
                    "Não consegui começar",
                  )
                }
                className="btn btn-secondary"
              >
                microfone
              </button>
            </>
          )}

          {gravando && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() =>
                acao(
                  () => api.pararTranscricao(),
                  "Encerrando — o fichamento é a última etapa",
                  "Não consegui parar",
                )
              }
              className="btn btn-primary"
            >
              ■ parar e organizar
            </button>
          )}

          {(gravando || revisando || processando) && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setConfirmando(true)}
              className="btn btn-ghost"
            >
              descartar
            </button>
          )}
        </div>
      </div>

      {estado?.erro && <Erro>{estado.erro}</Erro>}

      {revisando && estado?.sugestao && destinos && (
        <FormularioNota
          estado={estado}
          pastas={destinos.pastas}
          tags={destinos.tags}
          salvando={ocupado}
          onSalvar={(c) =>
            acao(
              async () => {
                const r = await api.salvarNota({ ...c, nome_arquivo: null });
                ok(`Salva em ${r.caminho} · ${r.chunks} chunks indexados`);
              },
              "Nota salva no vault",
              "Não consegui salvar a nota",
            )
          }
        />
      )}

      <div className="flex flex-col gap-2">
        {estado?.trechos.map((t) => (
          <div
            key={t.indice}
            className={`group flex gap-3 text-[14px] leading-[1.6] ${
              t.anuncio ? "opacity-45" : ""
            }`}
          >
            <span className="tnum w-[46px] flex-none pt-px text-[12px] text-neutral-600">
              {t.relogio}
            </span>
            <span className={`min-w-0 flex-1 ${t.processado ? "text-muted" : ""}`}>
              {t.texto}
              {t.anuncio && (
                <span className="ml-2 text-[11px] text-accent-300">
                  parece anúncio
                </span>
              )}
            </span>
            {/* Cortar ao vivo é mais barato que qualquer filtro automático, e
                não corre o risco de apagar conteúdo real. Depois de o trecho
                entrar num bloco reescrito, cortar exigiria refazer o bloco. */}
            <button
              type="button"
              disabled={t.processado || ocupado}
              title={
                t.processado
                  ? "já entrou num bloco reescrito"
                  : "cortar este trecho"
              }
              onClick={() =>
                acao(
                  () => api.cortarTrecho(t.indice),
                  "Trecho cortado",
                  "Não consegui cortar",
                )
              }
              className="flex-none text-[13px] text-neutral-700 opacity-0 transition-opacity hover:text-accent-300 group-hover:opacity-100 disabled:cursor-not-allowed disabled:hover:text-neutral-700"
            >
              ✕
            </button>
          </div>
        ))}
        <div ref={fim} />
      </div>

      {ocioso && estado?.trechos.length === 0 && (
        <p className="m-0 text-[13.5px] text-neutral-500">
          Nada gravando. <strong>gravar o sistema</strong> captura o que está
          tocando — vídeo, reunião; <strong>microfone</strong> captura a sua voz.
          {destinos ? ` Vault: ${destinos.vault}` : ""}
        </p>
      )}

      {confirmando && (
        <Dialogo
          titulo="Descartar esta sessão?"
          descricao="A transcrição e o fichamento vão embora. Nada é salvo no vault."
          confirmar="descartar"
          perigo
          onCancelar={() => setConfirmando(false)}
          onConfirmar={() => {
            setConfirmando(false);
            void acao(
              () => api.descartarTranscricao(),
              "Sessão descartada",
              "Não consegui descartar",
            );
          }}
        />
      )}

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}
    </div>
  );
}
