"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AbasComercial } from "@/components/comercial/Abas";
import { Cabecalho, Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import type { LeadLinha } from "@/lib/tipos";

// Lista simples dos leads (Fase 1, passo 3). O kanban por estágio é o passo 7;
// a tela Hoje, com o que fazer em ordem, é o passo 5.

const ESTAGIO: Record<string, string> = {
  prospect: "prospect",
  contatado: "contatado",
  respondeu: "respondeu",
  reuniao: "reunião",
  proposta: "proposta",
  ganho: "ganho",
  perdido: "perdido",
  nao_agora: "não agora",
};

export default function Leads() {
  const [leads, setLeads] = useState<LeadLinha[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api
      .leads()
      .then((l) => {
        setLeads(l);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, []);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  return (
    <div className="max-w-[1100px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Comercial · Leads</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        Quem está no CRM
      </h1>
      <p className="m-0 mb-6 max-w-[64ch] text-[15px] text-muted">
        Cada lead começa pela pesquisa: o Pesquisador lê o site da clínica e só
        libera o e-mail que ela mesma publica.
      </p>
      <AbasComercial />

      {erro && <Erro>Não consegui carregar os leads: {erro}</Erro>}
      {leads && leads.length === 0 && (
        <Vazio
          titulo="Nenhum lead ainda"
          acao={{
            href: "/comercial/empresas",
            rotulo: "Trazer clínicas da base",
          }}
        >
          Os leads nascem na tela Empresas, trazidos da base de prospecção.
        </Vazio>
      )}
      {leads && leads.length > 0 && (
        <div className="card overflow-x-auto">
          <div className="tnum mb-2 text-[12px] text-neutral-500">
            {plural(leads.length, "lead", "leads")}
          </div>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="card-kicker text-neutral-500">
                <th className="pb-2 font-normal">Lead</th>
                <th className="pb-2 font-normal">Estágio</th>
                <th className="pb-2 font-normal">E-mail</th>
                <th className="pb-2 font-normal">Próxima ação</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id} className="border-t border-divider align-top">
                  <td className="py-[10px] pr-3">
                    <Link
                      href={`/comercial/leads/${l.id}`}
                      className="text-[14px] text-text no-underline hover:text-accent"
                    >
                      {l.nome}
                    </Link>
                  </td>
                  <td className="py-[10px] pr-3 text-[13px] text-muted">
                    {ESTAGIO[l.estagio] ?? l.estagio}
                  </td>
                  <td className="py-[10px] pr-3 text-[13px]">
                    <span className="text-muted">{l.email ?? "—"}</span>
                    {l.email && (
                      <span
                        className={`ml-2 text-[11.5px] ${l.email_confirmado ? "text-accent" : "text-neutral-500"}`}
                      >
                        {l.email_confirmado ? "confirmado" : "não confirmado"}
                      </span>
                    )}
                  </td>
                  <td className="py-[10px] text-[13px] text-muted">
                    {l.proxima_acao ?? "pesquisar"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
