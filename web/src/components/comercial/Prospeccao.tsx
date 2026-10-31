"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { quando } from "@/components/ui";
import { api } from "@/lib/api";
import type {
  FatoFicha,
  FichaDados,
  LeadDetalhe,
  RascunhoCrm,
} from "@/lib/tipos";

// O Pesquisador e o Redator de um negócio: a ficha com fonte, e o e-mail 1 e
// o lembrete pela fila de aprovação. Moram aqui porque aparecem em dois
// lugares: na página completa do lead e na ficha lateral do CRM.

/** "27/09, 14:05": a linha do tempo é passado, e com hora. */
export function dataHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function Fonte({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-2 text-[11.5px] text-neutral-500 hover:text-accent"
    >
      fonte ↗
    </a>
  );
}

function Fato({
  rotulo,
  fato,
  formato,
}: {
  rotulo: string;
  fato: FatoFicha | null;
  formato?: (v: FatoFicha["valor"]) => string;
}) {
  return (
    <div className="flex flex-col gap-[2px] border-t border-divider py-[9px] first:border-t-0">
      <span className="card-kicker text-neutral-500">{rotulo}</span>
      {fato ? (
        <span className="text-[14px] text-text">
          {formato ? formato(fato.valor) : String(fato.valor)}
          <Fonte url={fato.fonte} />
        </span>
      ) : (
        <span className="text-[13.5px] text-neutral-500">
          não achei no site
        </span>
      )}
    </div>
  );
}

const PAROU: Record<string, string> = {
  completo: "parou porque achou tudo",
  teto: "parou no teto de páginas sem achar tudo",
  "acabaram as páginas": "leu o site inteiro",
};

export function Ficha({ d }: { d: FichaDados }) {
  const js = d.com_javascript?.length ?? 0;
  return (
    <div className="card">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="m-0 text-[17px]">Ficha</h2>
        <span className="text-[12px] text-neutral-500">
          {d.paginas.length} página(s) lida(s) de {d.site}
          {d.parou_porque && PAROU[d.parou_porque]
            ? ` · ${PAROU[d.parou_porque]}`
            : ""}
          {js ? ` · ${js} com JavaScript` : ""}
        </span>
      </div>
      <Fato rotulo="O que a clínica faz" fato={d.o_que_faz} />
      <Fato rotulo="Gancho para o e-mail" fato={d.gancho} />
      <Fato rotulo="Psicólogos com CRP no site" fato={d.psicologos_crp} />
      <Fato
        rotulo="Agendamento online"
        fato={d.agendamento_online}
        formato={(v) => `sim (“${v}”)`}
      />
      <Fato
        rotulo="WhatsApp publicado"
        fato={d.whatsapp}
        formato={(v) => `sim: ${v}`}
      />
      <div className="flex flex-col gap-[2px] border-t border-divider py-[9px]">
        <span className="card-kicker text-neutral-500">E-mails publicados</span>
        {d.emails.length ? (
          d.emails.map((e) => (
            <span key={String(e.valor)} className="text-[14px] text-text">
              {String(e.valor)}
              <Fonte url={e.fonte} />
            </span>
          ))
        ) : (
          <span className="text-[13.5px] text-neutral-500">nenhum</span>
        )}
      </div>
    </div>
  );
}

type Tipo = RascunhoCrm["tipo"];
const NOME: Record<Tipo, string> = {
  email_frio: "o e-mail 1",
  lembrete_frio: "o lembrete",
};

/** O texto do Redator que vale agora para este tipo: o último não rejeitado. */
function atual(rascunhos: RascunhoCrm[], tipo: Tipo) {
  const doTipo = rascunhos.filter((r) => r.tipo === tipo);
  return {
    enviado: doTipo.find((r) => r.enviado_em) ?? null,
    vivo:
      doTipo.filter((r) => r.status !== "rejeitada" && !r.enviado_em).at(-1) ??
      null,
    rejeitado: doTipo.at(-1)?.status === "rejeitada" ? doTipo.at(-1)! : null,
  };
}

function Aprovado({
  r,
  para,
  enviando,
  onEnviei,
  onCopiado,
}: {
  r: RascunhoCrm;
  para: string | null;
  enviando: boolean;
  onEnviei: () => void;
  onCopiado: (o_que: string) => void;
}) {
  const copiar = (texto: string, o_que: string) =>
    navigator.clipboard.writeText(texto).then(() => onCopiado(o_que));
  return (
    <div className="flex flex-col gap-2">
      <div className="text-[12.5px] text-neutral-500">
        Aprovado. Copie para o webmail do comercial@, envie e marque aqui.
      </div>
      <div className="text-[13px]">
        <span className="card-kicker text-neutral-500">para </span>
        {para}
      </div>
      <div className="text-[13px]">
        <span className="card-kicker text-neutral-500">assunto </span>
        {r.assunto}
      </div>
      <pre className="m-0 whitespace-pre-wrap rounded-[8px] border border-divider p-3 font-sans text-[13px] leading-[1.6] text-muted">
        {r.corpo}
      </pre>
      {r.problemas.map((p) => (
        <div key={p} className="text-[12.5px] text-accent-300">
          ⚠ depois da sua edição: {p}
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {para && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => copiar(para, "Endereço copiado")}
          >
            copiar endereço
          </button>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => copiar(r.assunto, "Assunto copiado")}
        >
          copiar assunto
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => copiar(r.corpo, "Texto copiado")}
        >
          copiar texto
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={enviando}
          onClick={onEnviei}
        >
          {enviando ? "…" : "Enviei"}
        </button>
      </div>
    </div>
  );
}

export function CartaoEmail({
  lead,
  onLead,
  ok,
  falhou,
}: {
  lead: LeadDetalhe;
  onLead: (l: LeadDetalhe) => void;
  ok: (t: string) => void;
  falhou: (t: string, e?: unknown) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const email = atual(lead.rascunhos, "email_frio");
  const lembrete = atual(lead.rascunhos, "lembrete_frio");
  const prazoLembrete = lead.tarefas.find(
    (t) => t.tipo === "lembrete" && !t.feita_em,
  )?.vence_em;

  const escrever = async (tipo: Tipo) => {
    setOcupado(true);
    try {
      const r = await api.escreverLead(lead.id, tipo);
      onLead(r.lead);
      ok(
        r.avisos.length
          ? `Na fila, com aviso: ${r.avisos.join("; ")}`
          : `${NOME[tipo]} está na fila de aprovação`,
      );
    } catch (e) {
      falhou(`Não escrevi ${NOME[tipo]}`, e);
    } finally {
      setOcupado(false);
    }
  };
  const enviei = async (r: RascunhoCrm) => {
    setOcupado(true);
    try {
      onLead(await api.envieiLead(lead.id, r.acao_id));
      ok(`${NOME[r.tipo]} marcado como enviado`);
    } catch (e) {
      falhou("Não consegui marcar o envio", e);
    } finally {
      setOcupado(false);
    }
  };

  // Uma etapa por vez: o e-mail 1 até sair, depois o lembrete, depois nada.
  const etapa: Tipo = email.enviado ? "lembrete_frio" : "email_frio";
  const agora = etapa === "email_frio" ? email : lembrete;

  let corpo: React.ReactNode;
  if (lembrete.enviado) {
    corpo = (
      <p className="m-0 text-[13.5px] text-muted">
        Lembrete enviado em {dataHora(lembrete.enviado.enviado_em!)}. Depois
        dele, nada: se não responderem, o lead encerra.
      </p>
    );
  } else if (agora.vivo?.status === "pendente") {
    corpo = (
      <p className="m-0 text-[13.5px] text-muted">
        {NOME[etapa][0].toUpperCase() + NOME[etapa].slice(1)} está na{" "}
        <Link href="/fila" className="text-accent">
          fila de aprovação →
        </Link>
        {agora.vivo.avisos.map((a) => (
          <span key={a} className="mt-1 block text-[12.5px] text-accent-300">
            ⚠ {a}
          </span>
        ))}
      </p>
    );
  } else if (agora.vivo) {
    corpo = (
      <Aprovado
        r={agora.vivo}
        para={lead.email}
        enviando={ocupado}
        onEnviei={() => enviei(agora.vivo!)}
        onCopiado={ok}
      />
    );
  } else {
    corpo = (
      <div className="flex flex-col gap-2">
        {email.enviado && (
          <p className="m-0 text-[13.5px] text-muted">
            E-mail 1 enviado em {dataHora(email.enviado.enviado_em!)}.
            {prazoLembrete &&
              ` Sem resposta, o lembrete pode sair a partir de ${quando(prazoLembrete)}.`}
          </p>
        )}
        {agora.rejeitado && (
          <p className="m-0 text-[12.5px] text-neutral-500">
            O último texto foi rejeitado
            {agora.rejeitado.motivo ? `: ${agora.rejeitado.motivo}` : ""}.
          </p>
        )}
        <div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={ocupado || !lead.email_confirmado}
            onClick={() => escrever(etapa)}
          >
            {ocupado
              ? "escrevendo…"
              : agora.rejeitado
                ? `Escrever ${NOME[etapa]} de novo`
                : `Escrever ${NOME[etapa]}`}
          </button>
        </div>
        {!lead.email_confirmado && (
          <span className="text-[12.5px] text-neutral-500">
            Só depois que o Pesquisador confirmar o e-mail no site da clínica.
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="m-0 mb-3 text-[17px]">E-mail</h2>
      {corpo}
    </div>
  );
}

/** Ler o site da clínica e montar a ficha. Sem endereço, usa o do lead. */
export function Pesquisar({
  lead,
  onLead,
  ok,
  falhou,
  compacto = false,
}: {
  lead: LeadDetalhe;
  onLead: (l: LeadDetalhe) => void;
  ok: (t: string) => void;
  falhou: (t: string, e?: unknown) => void;
  compacto?: boolean;
}) {
  const [site, setSite] = useState("");
  const [pesquisando, setPesquisando] = useState(false);
  const jaTem = lead.interacoes.some((i) => i.tipo === "ficha");

  const pesquisar = async () => {
    setPesquisando(true);
    try {
      const r = await api.pesquisarLead(lead.id, site.trim() || undefined);
      onLead(r.lead);
      if (r.status === "ok")
        ok(
          r.email_confirmado
            ? "Ficha pronta: e-mail confirmado no site"
            : "Ficha pronta, mas nenhum e-mail confirmado no site",
        );
      else falhou(r.mensagem);
    } catch (e) {
      falhou("A pesquisa falhou", e);
    } finally {
      setPesquisando(false);
    }
  };

  return (
    <div className={compacto ? "" : "card"}>
      {!compacto && (
        <>
          <h2 className="m-0 mb-3 text-[17px]">Pesquisar</h2>
          <p className="m-0 mb-3 text-[13.5px] text-muted">
            Lê o site público da clínica página por página (contato, equipe e
            agendamento primeiro) e para assim que acha e-mail, WhatsApp,
            agendamento e equipe, ou em 15 páginas. Página montada por
            JavaScript é aberta num navegador. Respeita o robots.txt. Sem
            endereço, usa o domínio do e-mail, se não for de provedor gratuito.
          </p>
        </>
      )}
      <div className="flex flex-wrap gap-2">
        <input
          className="input min-w-[200px] flex-1"
          placeholder={
            lead.site ?? "site da clínica (ex.: clinicaaurora.com.br)"
          }
          value={site}
          onChange={(e) => setSite(e.target.value)}
          aria-label="site da clínica"
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={pesquisando}
          onClick={pesquisar}
        >
          {pesquisando
            ? "lendo o site…"
            : jaTem
              ? "Pesquisar de novo"
              : "Pesquisar"}
        </button>
      </div>
      {pesquisando && (
        <p className="m-0 mt-2 text-[12.5px] text-neutral-500">
          Pode levar até um minuto: o Pesquisador abre página por página.
        </p>
      )}
    </div>
  );
}

/**
 * O Pesquisador e o Redator dentro da ficha lateral do negócio: pesquisar,
 * escrever, marcar "enviei" e ver a ficha, sem sair do kanban.
 */
export function ProspeccaoNegocio({
  id,
  onMudou,
  ok,
  falhou,
}: {
  id: number;
  onMudou: () => void;
  ok: (t: string) => void;
  falhou: (t: string, e?: unknown) => void;
}) {
  const [lead, setLead] = useState<LeadDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api
      .lead(id)
      .then(setLead)
      .catch((e) => setErro((e as Error).message));
  }, [id]);

  const mudou = (l: LeadDetalhe) => {
    setLead(l);
    onMudou();
  };

  if (erro) return <p className="m-0 text-[13px] text-[#e07f86]">{erro}</p>;
  if (!lead)
    return <div className="h-24 animate-pulse rounded-[10px] bg-surface" />;
  const ficha = lead.interacoes.find((i) => i.tipo === "ficha")?.dados ?? null;

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[13.5px]">
        <span className="text-neutral-500">envio para </span>
        {lead.email ?? <span className="text-neutral-500">sem e-mail</span>}
        {lead.email && (
          <span
            className={`ml-2 text-[12px] ${lead.email_confirmado ? "text-accent" : "text-accent-300"}`}
          >
            {lead.email_confirmado
              ? "confirmado no site"
              : "não confirmado: não enviar"}
          </span>
        )}
        {lead.email_fonte && <Fonte url={lead.email_fonte} />}
        {lead.pesquisado_em && (
          <span className="ml-2 text-[12px] text-neutral-500">
            · pesquisado em {dataHora(lead.pesquisado_em)}
          </span>
        )}
      </div>
      <Pesquisar lead={lead} onLead={mudou} ok={ok} falhou={falhou} compacto />
      <CartaoEmail lead={lead} onLead={mudou} ok={ok} falhou={falhou} />
      {ficha && (
        <details open className="group">
          <summary className="cursor-pointer text-[12.5px] text-neutral-400 hover:text-text">
            ficha do Pesquisador
          </summary>
          <div className="mt-2">
            <Ficha d={ficha} />
          </div>
        </details>
      )}
    </div>
  );
}
