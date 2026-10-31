"use client";

import { useEffect, useRef, useState } from "react";

import { AbasComercial } from "@/components/comercial/Abas";
import { Cabecalho } from "@/components/ui";
import { api } from "@/lib/api";
import type { OpcoesCrm } from "@/lib/tipos";

/**
 * As peças do CRM, no desenho do CRM do prospector: tabela editável no lugar,
 * pílula colorida por opção, painel lateral para a ficha e o formulário. As
 * cores e os controles são os do Nocturne; o jeito de usar é o de lá.
 */

export function TelaCrm({
  secao,
  acoes,
  children,
}: {
  secao: string;
  acoes?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="max-w-[1280px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Comercial · {secao}</Cabecalho>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h1 className="m-0 text-[clamp(32px,3.6vw,42px)]">CRM</h1>
        {acoes && (
          <div className="flex flex-wrap items-center gap-2">{acoes}</div>
        )}
      </div>
      <AbasComercial />
      {children}
    </div>
  );
}

// ── opções e cores ──

let opcoesCache: Promise<OpcoesCrm> | null = null;

/** Os rótulos do CRM. Uma busca por aba: não mudam sem deploy. */
export function useOpcoes(): OpcoesCrm | null {
  const [opcoes, setOpcoes] = useState<OpcoesCrm | null>(null);
  useEffect(() => {
    opcoesCache ??= api.crmOpcoes().catch((e) => {
      opcoesCache = null;
      throw e;
    });
    opcoesCache.then(setOpcoes).catch(() => undefined);
  }, []);
  return opcoes;
}

// Um tom por valor, com a mesma luminosidade: a pílula diz a categoria sem
// gritar mais que o texto em volta.
const TONS: Record<string, string> = {
  // estágio
  prospect: "#9397ab",
  contatado: "#7fa7e0",
  respondeu: "#5fc0b5",
  reuniao: "#b5abfc",
  proposta: "#e0b36a",
  ganho: "#79c98a",
  nao_agora: "#75798c",
  perdido: "#e07f86",
  // status da empresa
  cliente: "#79c98a",
  parceiro: "#b5abfc",
  inativa: "#75798c",
  // tarefa
  atrasada: "#e07f86",
  feita: "#79c98a",
};

export function Pilula({
  valor,
  children,
  className = "",
}: {
  valor: string;
  children: React.ReactNode;
  className?: string;
}) {
  const cor = TONS[valor] ?? "#9397ab";
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-[9px] py-[1px] text-[12px] ${className}`}
      style={{
        color: cor,
        background: `color-mix(in srgb, ${cor} 16%, transparent)`,
        border: `1px solid color-mix(in srgb, ${cor} 30%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

export function brl(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.length === 10 ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

// ── painel lateral ──

const pilha: symbol[] = [];

/**
 * A gaveta da direita, onde abrem a ficha e o formulário. Ocupa a altura toda
 * e rola o conteúdo; fecha no Esc e no clique fora.
 */
export function PainelLateral({
  titulo,
  acoes,
  onFechar,
  largura = "max-w-[640px]",
  camada = 50,
  children,
}: {
  titulo: React.ReactNode;
  acoes?: React.ReactNode;
  onFechar: () => void;
  largura?: string;
  camada?: number;
  children: React.ReactNode;
}) {
  const fechar = useRef(onFechar);
  useEffect(() => {
    fechar.current = onFechar;
  });
  useEffect(() => {
    // Ficha e formulário empilham: o Esc fecha só o de cima, e nada quando um
    // diálogo (confirmar, motivo da perda) está aberto por cima de todos.
    const eu = Symbol();
    pilha.push(eu);
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || pilha.at(-1) !== eu) return;
      if (document.querySelector("[data-dialogo]")) return;
      fechar.current();
    };
    addEventListener("keydown", onKey);
    return () => {
      pilha.splice(pilha.indexOf(eu), 1);
      removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <div
      className="fixed inset-0 flex justify-end bg-[rgb(0_0_0/50%)]"
      style={{ zIndex: camada }}
      onClick={onFechar}
      role="presentation"
    >
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={typeof titulo === "string" ? titulo : undefined}
        className={`elev-lg flex h-full w-full ${largura} flex-col border-l border-divider bg-bg`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-divider px-6 pb-4 pt-5">
          <h2 className="m-0 text-[20px] leading-snug">{titulo}</h2>
          <div className="flex flex-none items-center gap-2">
            {acoes}
            <button
              type="button"
              onClick={onFechar}
              aria-label="fechar"
              className="btn btn-icon text-[20px] text-neutral-400 hover:text-text"
            >
              ×
            </button>
          </div>
        </header>
        <div className="grow overflow-y-auto px-6 py-5">{children}</div>
      </aside>
    </div>
  );
}

// ── célula editável no lugar ──

export type TipoCelula =
  | "texto"
  | "obrigatorio"
  | "longo"
  | "email"
  | "telefone"
  | "numero"
  | "data"
  | "sim_nao"
  | "opcao"
  | "uf";

/**
 * Clica, edita, confirma (Enter, sair do campo ou escolher a opção). Esc
 * cancela. Opção vira pílula colorida; sim/não alterna num clique.
 */
export function Celula({
  valor,
  exibicao,
  tipo = "texto",
  opcoes,
  vazio = "—",
  className = "",
  onSalvar,
}: {
  valor: string | number | boolean | null | undefined;
  exibicao?: string;
  tipo?: TipoCelula | string;
  opcoes?: { valor: string; rotulo: string }[];
  vazio?: string;
  className?: string;
  onSalvar: (novo: string | boolean | null) => Promise<unknown>;
}) {
  const [editando, setEditando] = useState(false);
  const [rascunho, setRascunho] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const original = valor == null ? "" : String(valor);

  async function salvar(novo: string | boolean | null) {
    setEditando(false);
    if (typeof novo !== "boolean" && (novo ?? "") === original) return;
    setSalvando(true);
    setErro(null);
    try {
      await onSalvar(
        typeof novo === "string" && novo.trim() === "" ? null : novo,
      );
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  const parar = (e: React.SyntheticEvent) => e.stopPropagation();

  if (tipo === "sim_nao") {
    return (
      <button
        type="button"
        disabled={salvando}
        title={erro ?? "clique para alternar"}
        onClick={(e) => {
          parar(e);
          void salvar(!valor);
        }}
        className={`rounded-full border px-[9px] py-[1px] text-[12px] ${
          valor
            ? "border-[color-mix(in_srgb,var(--color-accent)_40%,transparent)] text-accent"
            : "border-divider text-neutral-500"
        } ${erro ? "!text-[#e07f86]" : ""} ${className}`}
      >
        {valor ? "sim" : "não"}
      </button>
    );
  }

  if (editando) {
    if (tipo === "opcao") {
      return (
        <select
          autoFocus
          className="input !min-h-[30px] max-w-[200px] !py-[3px] !text-[13px]"
          defaultValue={original}
          onClick={parar}
          onChange={(e) => void salvar(e.target.value)}
          onBlur={() => setEditando(false)}
          onKeyDown={(e) => e.key === "Escape" && setEditando(false)}
        >
          {!opcoes?.some((o) => o.valor === original) && (
            <option value="">{vazio}</option>
          )}
          {(opcoes ?? []).map((o) => (
            <option key={o.valor} value={o.valor}>
              {o.rotulo}
            </option>
          ))}
        </select>
      );
    }
    const props = {
      autoFocus: true,
      value: rascunho,
      onClick: parar,
      onChange: (
        e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
      ) => setRascunho(e.target.value),
      onBlur: () => void salvar(rascunho),
    };
    if (tipo === "longo") {
      return (
        <textarea
          {...props}
          className="input min-h-[110px] !text-[13.5px]"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setRascunho(original);
              setEditando(false);
            } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
              void salvar(rascunho);
          }}
        />
      );
    }
    return (
      <input
        {...props}
        type={tipo === "data" ? "date" : "text"}
        inputMode={tipo === "numero" ? "decimal" : undefined}
        className="input !min-h-[30px] max-w-[260px] !py-[3px] !text-[13px]"
        onKeyDown={(e) => {
          if (e.key === "Enter") void salvar(rascunho);
          else if (e.key === "Escape") {
            setRascunho(original);
            setEditando(false);
          }
        }}
      />
    );
  }

  const abrir = (e: React.MouseEvent) => {
    parar(e);
    setRascunho(original);
    setEditando(true);
  };

  if (tipo === "opcao" && original && !salvando) {
    return (
      <button
        type="button"
        onClick={abrir}
        title={erro ?? "clique para mudar"}
        className={`rounded-full ${className}`}
      >
        <Pilula valor={original} className={erro ? "!text-[#e07f86]" : ""}>
          {exibicao ||
            opcoes?.find((o) => o.valor === original)?.rotulo ||
            original}
        </Pilula>
      </button>
    );
  }

  return (
    <button
      type="button"
      disabled={salvando}
      onClick={abrir}
      title={erro ?? "clique para editar"}
      className={`-mx-[4px] max-w-full rounded-[5px] px-[4px] text-left transition-colors hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] ${
        erro ? "text-[#e07f86]" : original ? "text-text" : "text-neutral-500"
      } ${tipo === "longo" ? "whitespace-pre-wrap" : ""} ${salvando ? "opacity-50" : ""} ${className}`}
    >
      {salvando ? "…" : exibicao || original || vazio}
    </button>
  );
}

// ── formulário ──

export function CampoForm({
  rotulo,
  largo,
  children,
}: {
  rotulo: string;
  largo?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label
      className={`flex flex-col gap-[6px] ${largo ? "md:col-span-2" : ""}`}
    >
      <span className="card-kicker text-neutral-400">{rotulo}</span>
      {children}
    </label>
  );
}

/** A barra de cima das listas: busca, filtros à esquerda, ações à direita. */
export function BarraLista({
  busca,
  onBusca,
  filtros,
  acoes,
}: {
  busca: string;
  onBusca: (v: string) => void;
  filtros?: React.ReactNode;
  acoes?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <input
        className="input max-w-[260px]"
        placeholder="buscar…"
        aria-label="buscar"
        value={busca}
        onChange={(e) => onBusca(e.target.value)}
      />
      {filtros}
      <div className="ml-auto flex items-center gap-2">{acoes}</div>
    </div>
  );
}

/** A busca só vai ao servidor quando a pessoa para de digitar. */
export function useAtrasado<T>(valor: T, ms = 250): T {
  const [v, setV] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return v;
}

/** Controle segmentado: Kanban/Lista, abertas/feitas. */
export function Segmentos<T extends string>({
  valor,
  opcoes,
  onMudar,
  rotulo,
}: {
  valor: T;
  opcoes: { valor: T; rotulo: string }[];
  onMudar: (v: T) => void;
  rotulo: string;
}) {
  return (
    <div className="seg" role="group" aria-label={rotulo}>
      {opcoes.map((o) => (
        <button
          key={o.valor}
          type="button"
          className="seg-opt"
          aria-pressed={valor === o.valor}
          onClick={() => onMudar(o.valor)}
        >
          {o.rotulo}
        </button>
      ))}
    </div>
  );
}

export const th = "px-3 pb-2 pt-1 text-left font-normal";
export const td = "px-3 py-[9px] align-middle";
