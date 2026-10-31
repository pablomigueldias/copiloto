"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CampoForm,
  PainelLateral,
  useOpcoes,
} from "@/components/comercial/crm";
import { api } from "@/lib/api";
import type {
  CamposCrm,
  ContatoCrm,
  EmpresaCrm,
  NegocioCrm,
  TipoRegistro,
} from "@/lib/tipos";

type Def = {
  campo: string;
  rotulo: string;
  tipo:
    | "texto"
    | "longo"
    | "numero"
    | "data"
    | "sim_nao"
    | "opcao"
    | "empresa"
    | "contato"
    | "negocio";
  opcoes?: "status_empresa" | "origem" | "tipo_tarefa";
  largo?: boolean;
  obrigatorio?: boolean;
  dica?: string;
};

// O espelho de `CAMPOS` em `app/comercial/crm/cadastro.py`: o servidor valida,
// aqui só se escolhe o controle certo para cada campo.
const DEFS: Record<TipoRegistro, Def[]> = {
  empresa: [
    {
      campo: "nome",
      rotulo: "Nome",
      tipo: "texto",
      largo: true,
      obrigatorio: true,
    },
    {
      campo: "status",
      rotulo: "Status",
      tipo: "opcao",
      opcoes: "status_empresa",
    },
    { campo: "segmento", rotulo: "Segmento", tipo: "texto" },
    { campo: "razao_social", rotulo: "Razão social", tipo: "texto" },
    { campo: "cnpj", rotulo: "CNPJ", tipo: "texto" },
    { campo: "site", rotulo: "Site", tipo: "texto" },
    { campo: "email", rotulo: "E-mail", tipo: "texto" },
    { campo: "telefone", rotulo: "Telefone", tipo: "texto" },
    { campo: "instagram", rotulo: "Instagram", tipo: "texto" },
    { campo: "bairro", rotulo: "Bairro", tipo: "texto" },
    { campo: "cidade", rotulo: "Cidade", tipo: "texto" },
    { campo: "uf", rotulo: "UF", tipo: "texto" },
    { campo: "notas", rotulo: "Notas", tipo: "longo", largo: true },
  ],
  contato: [
    {
      campo: "nome",
      rotulo: "Nome",
      tipo: "texto",
      largo: true,
      obrigatorio: true,
    },
    { campo: "empresa_id", rotulo: "Empresa", tipo: "empresa", largo: true },
    { campo: "cargo", rotulo: "Cargo", tipo: "texto" },
    { campo: "decisor", rotulo: "Decide a compra", tipo: "sim_nao" },
    { campo: "email", rotulo: "E-mail", tipo: "texto" },
    { campo: "telefone", rotulo: "Telefone / WhatsApp", tipo: "texto" },
    { campo: "linkedin", rotulo: "LinkedIn", tipo: "texto", largo: true },
    { campo: "notas", rotulo: "Notas", tipo: "longo", largo: true },
  ],
  negocio: [
    {
      campo: "nome",
      rotulo: "Nome",
      tipo: "texto",
      largo: true,
      dica: "vazio: o nome da empresa",
    },
    { campo: "empresa_id", rotulo: "Empresa", tipo: "empresa" },
    { campo: "contato_id", rotulo: "Contato", tipo: "contato" },
    { campo: "origem", rotulo: "Origem", tipo: "opcao", opcoes: "origem" },
    { campo: "valor_estimado", rotulo: "Valor estimado (R$)", tipo: "numero" },
    { campo: "proxima_acao", rotulo: "Próxima ação", tipo: "texto" },
    { campo: "proxima_em", rotulo: "Quando", tipo: "data" },
    { campo: "notas", rotulo: "Notas", tipo: "longo", largo: true },
  ],
  atividade: [
    {
      campo: "lead_id",
      rotulo: "Negócio",
      tipo: "negocio",
      largo: true,
      obrigatorio: true,
    },
    { campo: "tipo", rotulo: "Tipo", tipo: "opcao", opcoes: "tipo_tarefa" },
    { campo: "vence_em", rotulo: "Vence em", tipo: "data", obrigatorio: true },
    { campo: "descricao", rotulo: "Descrição", tipo: "texto", largo: true },
    { campo: "feita", rotulo: "Feita", tipo: "sim_nao" },
  ],
};

const TITULO: Record<TipoRegistro, [string, string]> = {
  empresa: ["Nova empresa", "Editar empresa"],
  contato: ["Novo contato", "Editar contato"],
  negocio: ["Novo negócio", "Editar negócio"],
  atividade: ["Nova atividade", "Editar atividade"],
};

const hojeIso = () => new Date().toLocaleDateString("sv-SE");

const PADRAO: Record<TipoRegistro, CamposCrm> = {
  empresa: { status: "prospect" },
  contato: { decisor: false },
  negocio: { origem: "indicacao" },
  atividade: { tipo: "ligar", feita: false },
};

/**
 * Criar ou editar um registro do CRM, no painel lateral. `inicial` já vem com a
 * ligação quando o formulário abre de dentro de outra ficha ("+ contato" na
 * empresa traz a empresa marcada).
 */
export function FormCrm({
  tipo,
  id,
  inicial,
  onFechar,
  onSalvo,
}: {
  tipo: TipoRegistro;
  id?: number;
  inicial?: CamposCrm;
  onFechar: () => void;
  onSalvo: (id: number) => void;
}) {
  const opcoes = useOpcoes();
  const [form, setForm] = useState<CamposCrm>(() => ({
    ...PADRAO[tipo],
    ...(tipo === "atividade" ? { vence_em: hojeIso() } : {}),
    ...inicial,
  }));
  const [carregado, setCarregado] = useState(!id);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [empresas, setEmpresas] = useState<EmpresaCrm[]>([]);
  const [contatos, setContatos] = useState<ContatoCrm[]>([]);
  const [negocios, setNegocios] = useState<NegocioCrm[]>([]);
  const defs = DEFS[tipo];

  useEffect(() => {
    if (!id) return;
    api
      .crmRegistro(tipo, id)
      .then((r) => {
        setForm(r.valores);
        setCarregado(true);
      })
      .catch((e) => setErro((e as Error).message));
  }, [tipo, id]);

  useEffect(() => {
    if (defs.some((d) => d.tipo === "empresa"))
      api
        .crmEmpresas()
        .then((p) => setEmpresas(p.itens))
        .catch(() => undefined);
    if (defs.some((d) => d.tipo === "contato"))
      api
        .crmContatos()
        .then((p) => setContatos(p.itens))
        .catch(() => undefined);
    if (defs.some((d) => d.tipo === "negocio"))
      api
        .crmNegocios()
        .then(setNegocios)
        .catch(() => undefined);
  }, [defs]);

  // O contato do negócio é da empresa escolhida (ou sem empresa).
  const contatosDaEmpresa = useMemo(
    () =>
      form.empresa_id
        ? contatos.filter(
            (c) =>
              c.empresa_id === Number(form.empresa_id) || c.empresa_id === null,
          )
        : contatos,
    [contatos, form.empresa_id],
  );

  const set = (campo: string, v: string | number | boolean | null) =>
    setForm((f) => ({ ...f, [campo]: v }));

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    const falta = defs.find(
      (d) => d.obrigatorio && (form[d.campo] ?? "") === "",
    );
    if (falta) {
      setErro(`preencha: ${falta.rotulo.toLowerCase()}`);
      return;
    }
    setSalvando(true);
    setErro(null);
    try {
      const campos = Object.fromEntries(
        defs.map((d) => [d.campo, form[d.campo] ?? null]),
      );
      if (id) {
        await api.crmEditar(tipo, id, campos);
        onSalvo(id);
      } else {
        const r = await api.crmCriar(tipo, campos);
        onSalvo(r.id);
      }
      onFechar();
    } catch (err) {
      setErro((err as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  function controle(d: Def) {
    const v = form[d.campo];
    const texto = v == null ? "" : String(v);
    const ref = (
      lista: { id: number; nome: string; sub?: string | null }[],
      vazio: string,
    ) => (
      <select
        className="input"
        value={texto}
        onChange={(e) => {
          const novo = e.target.value ? Number(e.target.value) : null;
          set(d.campo, novo);
          if (d.campo === "empresa_id" && tipo === "negocio") {
            const c = contatos.find((x) => x.id === Number(form.contato_id));
            if (c?.empresa_id && c.empresa_id !== novo) set("contato_id", null);
          }
        }}
      >
        <option value="">{vazio}</option>
        {lista.map((x) => (
          <option key={x.id} value={x.id}>
            {x.nome}
            {x.sub ? ` · ${x.sub}` : ""}
          </option>
        ))}
      </select>
    );
    switch (d.tipo) {
      case "longo":
        return (
          <textarea
            className="input"
            value={texto}
            onChange={(e) => set(d.campo, e.target.value)}
          />
        );
      case "sim_nao":
        return (
          <label className="flex min-h-[36px] items-center gap-2 text-[14px]">
            <input
              type="checkbox"
              checked={Boolean(v)}
              onChange={(e) => set(d.campo, e.target.checked)}
            />
            {v ? "sim" : "não"}
          </label>
        );
      case "opcao":
        return (
          <select
            className="input"
            value={texto}
            onChange={(e) => set(d.campo, e.target.value)}
          >
            {Object.entries(opcoes?.[d.opcoes!] ?? {}).map(
              ([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ),
            )}
          </select>
        );
      case "empresa":
        return ref(empresas, "sem empresa");
      case "contato":
        return ref(
          contatosDaEmpresa.map((c) => ({
            id: c.id,
            nome: c.nome,
            sub: c.empresa_nome ?? c.cargo,
          })),
          "sem contato",
        );
      case "negocio":
        return ref(
          negocios.map((n) => ({
            id: n.id,
            nome: n.nome,
            sub: opcoes?.estagio[n.estagio] ?? n.estagio,
          })),
          "escolha o negócio",
        );
      default:
        return (
          <input
            className="input"
            type={d.tipo === "data" ? "date" : "text"}
            inputMode={d.tipo === "numero" ? "decimal" : undefined}
            placeholder={d.dica}
            value={texto}
            onChange={(e) => set(d.campo, e.target.value)}
          />
        );
    }
  }

  return (
    <PainelLateral
      titulo={TITULO[tipo][id ? 1 : 0]}
      onFechar={onFechar}
      largura="max-w-[560px]"
      camada={55}
    >
      {!carregado ? (
        <div className="h-40 animate-pulse rounded-[10px] bg-surface" />
      ) : (
        <form onSubmit={salvar} className="flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-2">
            {defs.map((d) => (
              <CampoForm
                key={d.campo}
                rotulo={d.obrigatorio ? `${d.rotulo} *` : d.rotulo}
                largo={d.largo}
              >
                {controle(d)}
              </CampoForm>
            ))}
          </div>
          {erro && <p className="m-0 text-[13px] text-[#e07f86]">{erro}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn btn-ghost" onClick={onFechar}>
              cancelar
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={salvando}
            >
              {salvando ? "salvando…" : id ? "salvar" : "criar"}
            </button>
          </div>
        </form>
      )}
    </PainelLateral>
  );
}
