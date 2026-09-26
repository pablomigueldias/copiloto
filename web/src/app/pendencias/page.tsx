"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { Cabecalho, Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type {
  ColunaPendencia,
  Pendencia,
  PendenciaCampos,
  QuadroPendencias,
} from "@/lib/tipos";

const COLUNAS: { chave: ColunaPendencia; titulo: string }[] = [
  { chave: "a_fazer", titulo: "A fazer" },
  { chave: "fazendo", titulo: "Fazendo" },
  { chave: "feito", titulo: "Feito" },
];

const rotulo = "card-kicker mb-[6px] block text-neutral-400";

/** Dias até o prazo; negativo é atraso. Meia-noite local, para "hoje" ser 0. */
function diasAte(prazo: string): number {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  return Math.round(
    (new Date(`${prazo}T00:00:00`).getTime() - hoje.getTime()) / 86_400_000,
  );
}

function Prazo({ prazo, feito }: { prazo: string; feito: boolean }) {
  const d = diasAte(prazo);
  const data = new Date(`${prazo}T00:00:00`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
  const texto =
    d < 0 ? `venceu há ${-d} d` : d === 0 ? "vence hoje" : `em ${d} d`;
  const cor = feito
    ? "text-neutral-500"
    : d < 0
      ? "text-accent-300"
      : d <= 7
        ? "text-accent"
        : "text-neutral-400";
  return (
    <span className={`tnum text-[11.5px] ${cor}`}>
      {data} · {texto}
    </span>
  );
}

function Cartao({
  p,
  onMover,
  onEditar,
  onApagar,
  onArrastar,
}: {
  p: Pendencia;
  onMover: (coluna: ColunaPendencia) => void;
  onEditar: () => void;
  onApagar: () => void;
  onArrastar: (id: string | null) => void;
}) {
  const i = COLUNAS.findIndex((c) => c.chave === p.coluna);
  const antes = COLUNAS[i - 1];
  const depois = COLUNAS[i + 1];
  const feito = p.coluna === "feito";

  return (
    <article
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", p.id);
        e.dataTransfer.effectAllowed = "move";
        onArrastar(p.id);
      }}
      onDragEnd={() => onArrastar(null)}
      data-id={p.id}
      className={`card elev-sm flex cursor-grab flex-col gap-[6px] active:cursor-grabbing ${
        feito ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-baseline gap-2">
        <span className="card-kicker truncate">{p.topico}</span>
        {p.prazo && (
          <span className="ml-auto flex-none">
            <Prazo prazo={p.prazo} feito={feito} />
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onEditar}
        className={`m-0 cursor-pointer border-0 bg-transparent p-0 text-left text-[14.5px] leading-[1.4] text-text hover:text-accent ${
          feito ? "line-through decoration-neutral-500" : ""
        }`}
      >
        {p.titulo}
      </button>
      {p.descricao && (
        <p className="m-0 text-[13px] leading-[1.5] text-muted">
          {p.descricao}
        </p>
      )}
      {(p.quando || p.onde) && (
        <div className="flex flex-col gap-[2px] text-[11.5px] text-neutral-500">
          {p.quando && <span>quando: {p.quando}</span>}
          {p.onde && (
            <span className="break-all font-mono">
              {p.onde.replaceAll("`", "")}
            </span>
          )}
        </div>
      )}
      <div className="mt-1 flex items-center gap-1">
        {antes && (
          <button
            type="button"
            className="btn btn-ghost px-2 py-[2px] text-[12px]"
            onClick={() => onMover(antes.chave)}
            aria-label={`mover para ${antes.titulo}`}
          >
            ← {antes.titulo.toLowerCase()}
          </button>
        )}
        {depois && (
          <button
            type="button"
            className="btn btn-ghost px-2 py-[2px] text-[12px]"
            onClick={() => onMover(depois.chave)}
            aria-label={`mover para ${depois.titulo}`}
          >
            {depois.titulo.toLowerCase()} →
          </button>
        )}
        <button
          type="button"
          className="btn btn-ghost ml-auto px-2 py-[2px] text-[12px] text-neutral-500"
          onClick={onApagar}
        >
          apagar
        </button>
      </div>
    </article>
  );
}

type Form = {
  titulo: string;
  topico: string;
  descricao: string;
  quando: string;
  prazo: string;
  onde: string;
};

const VAZIO: Form = {
  titulo: "",
  topico: "",
  descricao: "",
  quando: "",
  prazo: "",
  onde: "",
};

function FormPendencia({
  inicial,
  topicos,
  editando,
  onSalvar,
  onCancelar,
}: {
  inicial: Form;
  topicos: string[];
  editando: boolean;
  onSalvar: (f: Form) => Promise<void>;
  onCancelar: () => void;
}) {
  const [f, setF] = useState(inicial);
  const [enviando, setEnviando] = useState(false);
  const muda = (campo: keyof Form) => (e: { target: { value: string } }) =>
    setF((atual) => ({ ...atual, [campo]: e.target.value }));

  return (
    <Dialogo
      titulo={editando ? "Editar pendência" : "Nova pendência"}
      confirmar={enviando ? "salvando…" : "salvar"}
      desabilitado={enviando || !f.titulo.trim() || !f.topico.trim()}
      onCancelar={onCancelar}
      onConfirmar={async () => {
        setEnviando(true);
        try {
          await onSalvar(f);
        } finally {
          setEnviando(false);
        }
      }}
    >
      <label className={rotulo} htmlFor="pend-titulo">
        Título
      </label>
      <input
        id="pend-titulo"
        className="input mb-3"
        value={f.titulo}
        autoFocus
        onChange={muda("titulo")}
        placeholder="Ligar o 2FA do Bitwarden"
      />
      <label className={rotulo} htmlFor="pend-topico">
        Tópico
      </label>
      <input
        id="pend-topico"
        className="input mb-3"
        list="pend-topicos"
        value={f.topico}
        onChange={muda("topico")}
        placeholder="Contas e ferramentas"
      />
      <datalist id="pend-topicos">
        {topicos.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <label className={rotulo} htmlFor="pend-descricao">
        O que fazer
      </label>
      <textarea
        id="pend-descricao"
        className="input mb-3 min-h-[72px] resize-y"
        value={f.descricao}
        onChange={muda("descricao")}
      />
      <div className="mb-3 grid grid-cols-2 gap-3">
        <div>
          <label className={rotulo} htmlFor="pend-quando">
            Quando
          </label>
          <input
            id="pend-quando"
            className="input"
            value={f.quando}
            onChange={muda("quando")}
            placeholder="antes do 1º contrato"
          />
        </div>
        <div>
          <label className={rotulo} htmlFor="pend-prazo">
            Prazo (se houver)
          </label>
          <input
            id="pend-prazo"
            type="date"
            className="input"
            value={f.prazo}
            onChange={muda("prazo")}
          />
        </div>
      </div>
      <label className={rotulo} htmlFor="pend-onde">
        Onde está o detalhe
      </label>
      <input
        id="pend-onde"
        className="input mb-3"
        value={f.onde}
        onChange={muda("onde")}
        placeholder="docs/motor-comercial/fase-0/operacao.md"
      />
    </Dialogo>
  );
}

function paraCampos(
  f: Form,
): PendenciaCampos & { titulo: string; topico: string } {
  return {
    titulo: f.titulo.trim(),
    topico: f.topico.trim(),
    descricao: f.descricao.trim() || null,
    quando: f.quando.trim() || null,
    prazo: f.prazo || null,
    onde: f.onde.trim() || null,
  };
}

export default function Pendencias() {
  const [quadro, setQuadro] = useState<QuadroPendencias | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [topico, setTopico] = useState<string | null>(null);
  const [form, setForm] = useState<{ id: string | null; inicial: Form } | null>(
    null,
  );
  const [apagando, setApagando] = useState<Pendencia | null>(null);
  const [arrastando, setArrastando] = useState<string | null>(null);
  const [alvo, setAlvo] = useState<ColunaPendencia | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .pendencias()
      .then((q) => {
        setQuadro(q);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const visiveis = useMemo(
    () => (quadro?.itens ?? []).filter((p) => !topico || p.topico === topico),
    [quadro, topico],
  );

  const abertasPorTopico = useMemo(() => {
    const conta: Record<string, number> = {};
    for (const p of quadro?.itens ?? [])
      if (p.coluna !== "feito") conta[p.topico] = (conta[p.topico] ?? 0) + 1;
    return conta;
  }, [quadro]);

  /**
   * Põe o cartão na coluna, antes de `antesDe` (ou no fim), e grava só as
   * posições que mudaram. A ordem é global da coluna, não do filtro: arrastar
   * com um tópico filtrado não pode embaralhar os cartões escondidos.
   */
  const soltar = async (
    id: string,
    coluna: ColunaPendencia,
    antesDe: string | null,
  ) => {
    if (!quadro || id === antesDe) return;
    const cartao = quadro.itens.find((p) => p.id === id);
    if (!cartao) return;
    const daColuna = quadro.itens
      .filter((p) => p.coluna === coluna && p.id !== id)
      .sort((a, b) => a.ordem - b.ordem);
    const pos = antesDe ? daColuna.findIndex((p) => p.id === antesDe) : -1;
    daColuna.splice(pos < 0 ? daColuna.length : pos, 0, cartao);

    const mudancas = daColuna
      .map((p, ordem) => ({ p, ordem }))
      .filter(({ p, ordem }) => p.ordem !== ordem || p.coluna !== coluna);
    if (!mudancas.length) return;

    // Otimista: a tela muda na hora e o servidor confirma depois.
    setQuadro({
      ...quadro,
      itens: quadro.itens.map((p) => {
        const m = mudancas.find((x) => x.p.id === p.id);
        return m ? { ...p, coluna, ordem: m.ordem } : p;
      }),
    });
    try {
      for (const { p, ordem } of mudancas)
        await api.editarPendencia(p.id, { coluna, ordem });
      if (cartao.coluna !== coluna && coluna === "feito")
        ok(`"${cartao.titulo}" feito`);
    } catch (e) {
      falhou("Não consegui mover", e);
      carregar();
    }
  };

  const salvar = async (f: Form) => {
    try {
      if (form?.id) {
        await api.editarPendencia(form.id, paraCampos(f));
        ok("Pendência salva");
      } else {
        await api.criarPendencia(paraCampos(f));
        ok("Pendência criada");
      }
      setForm(null);
    } catch (e) {
      falhou("Não consegui salvar", e);
    }
  };

  const abertas = (quadro?.itens ?? []).filter(
    (p) => p.coluna !== "feito",
  ).length;
  const topicos = quadro?.topicos ?? [];

  return (
    <div className="max-w-[1320px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Pendências</Cabecalho>
      <div className="mb-3 flex flex-wrap items-baseline gap-4">
        <h1 className="m-0 text-[clamp(32px,3.6vw,42px)]">O que é meu fazer</h1>
        <button
          type="button"
          className="btn btn-primary ml-auto"
          onClick={() =>
            setForm({ id: null, inicial: { ...VAZIO, topico: topico ?? "" } })
          }
        >
          + nova
        </button>
      </div>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        {quadro ? `${plural(abertas, "aberta", "abertas")}. ` : ""}
        Cada uma fica aqui até a hora de precisar dela. O prazo só aparece
        quando há um dia de verdade; o resto tem gatilho (&ldquo;antes do 1º
        contrato&rdquo;). Arraste entre as colunas, ou use as setas do cartão.
      </p>

      {erro && (
        <Erro>
          Não consegui carregar o quadro: {erro}. A tabela existe? (`alembic
          upgrade head`)
        </Erro>
      )}
      {!quadro && !erro && (
        <div className="text-[13px] text-muted">carregando…</div>
      )}

      {quadro && topicos.length > 0 && (
        <div
          className="mb-5 flex flex-wrap gap-2"
          role="toolbar"
          aria-label="Filtrar por tópico"
        >
          {[null, ...topicos].map((t) => (
            <button
              key={t ?? "todos"}
              type="button"
              aria-pressed={topico === t}
              onClick={() => setTopico(t)}
              className={`btn px-3 py-[4px] text-[12.5px] ${
                topico === t ? "btn-primary" : "btn-secondary"
              }`}
            >
              {t ?? "Todos"}
              {t && abertasPorTopico[t] ? (
                <span className="tnum ml-2 text-neutral-500">
                  {abertasPorTopico[t]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      )}

      {quadro && quadro.itens.length === 0 ? (
        <Vazio titulo="Nenhuma pendência">
          Crie a primeira com &ldquo;+ nova&rdquo;, ou importe as do
          <code> docs/PENDENCIAS.md</code> com
          <code> python scripts/importar_pendencias.py</code>.
        </Vazio>
      ) : quadro ? (
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
          {COLUNAS.map((c) => {
            const itens = visiveis
              .filter((p) => p.coluna === c.chave)
              .sort((a, b) => a.ordem - b.ordem);
            return (
              <section
                key={c.chave}
                aria-label={c.titulo}
                onDragOver={(e) => {
                  e.preventDefault();
                  setAlvo(c.chave);
                }}
                onDragLeave={() => setAlvo((a) => (a === c.chave ? null : a))}
                onDrop={(e) => {
                  e.preventDefault();
                  setAlvo(null);
                  const id = e.dataTransfer.getData("text/plain");
                  // Solto em cima de um cartão: entra antes dele.
                  const sobre = (e.target as HTMLElement)
                    .closest("[data-id]")
                    ?.getAttribute("data-id");
                  if (id) soltar(id, c.chave, sobre ?? null);
                }}
                className={`flex min-h-[120px] flex-col gap-3 rounded-[12px] p-2 transition-colors ${
                  alvo === c.chave && arrastando
                    ? "bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)]"
                    : ""
                }`}
              >
                <Cabecalho>
                  {c.titulo} · {itens.length}
                </Cabecalho>
                {itens.map((p) => (
                  <Cartao
                    key={p.id}
                    p={p}
                    onArrastar={setArrastando}
                    onMover={(coluna) => soltar(p.id, coluna, null)}
                    onApagar={() => setApagando(p)}
                    onEditar={() =>
                      setForm({
                        id: p.id,
                        inicial: {
                          titulo: p.titulo,
                          topico: p.topico,
                          descricao: p.descricao ?? "",
                          quando: p.quando ?? "",
                          prazo: p.prazo ?? "",
                          onde: p.onde ?? "",
                        },
                      })
                    }
                  />
                ))}
              </section>
            );
          })}
        </div>
      ) : null}

      {form && (
        <FormPendencia
          inicial={form.inicial}
          topicos={topicos}
          editando={form.id !== null}
          onSalvar={salvar}
          onCancelar={() => setForm(null)}
        />
      )}

      {apagando && (
        <Dialogo
          titulo="Apagar a pendência?"
          descricao={`"${apagando.titulo}" sai do quadro de vez. Se ela foi feita, arraste para "Feito" em vez de apagar.`}
          confirmar="apagar"
          perigo
          onCancelar={() => setApagando(null)}
          onConfirmar={async () => {
            try {
              await api.apagarPendencia(apagando.id);
              ok("Pendência apagada");
            } catch (e) {
              falhou("Não consegui apagar", e);
            } finally {
              setApagando(null);
            }
          }}
        />
      )}

      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </div>
  );
}
