"use client";

import { useCallback, useEffect, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { FichaCrm } from "@/components/comercial/FichaCrm";
import { FormCrm } from "@/components/comercial/FormCrm";
import {
  BarraLista,
  Celula,
  TelaCrm,
  td,
  th,
  useAtrasado,
  useOpcoes,
} from "@/components/comercial/crm";
import { Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { EmpresaCrm } from "@/lib/tipos";

// As empresas do CRM: a clínica, com os contatos e os negócios dela. A tabela
// edita no lugar; o clique na linha abre a ficha com tudo o que está ligado.

export default function Empresas() {
  const opcoes = useOpcoes();
  const [busca, setBusca] = useState("");
  const [status, setStatus] = useState("");
  const [dados, setDados] = useState<{
    total: number;
    itens: EmpresaCrm[];
  } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ficha, setFicha] = useState<number | null>(null);
  const [nova, setNova] = useState(false);
  const [excluir, setExcluir] = useState<EmpresaCrm | null>(null);
  const termo = useAtrasado(busca);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .crmEmpresas({ busca: termo, status })
      .then((d) => {
        setDados(d);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [termo, status]);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const opStatus = Object.entries(opcoes?.status_empresa ?? {}).map(
    ([valor, rotulo]) => ({ valor, rotulo }),
  );
  const salvar =
    (id: number, campo: string) => async (v: string | boolean | null) => {
      await api.crmEditar("empresa", id, { [campo]: v });
      carregar();
    };

  return (
    <TelaCrm
      secao="Empresas"
      acoes={
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setNova(true)}
        >
          + nova empresa
        </button>
      }
    >
      <BarraLista
        busca={busca}
        onBusca={setBusca}
        filtros={
          <select
            className="input !w-auto"
            aria-label="status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">status: todos</option>
            {opStatus.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </select>
        }
      />

      {erro && <Erro>Não consegui carregar as empresas: {erro}</Erro>}
      {dados && dados.total === 0 && !termo && !status ? (
        <Vazio
          titulo="Nenhuma empresa ainda"
          acao={{ href: "/comercial/base", rotulo: "Trazer clínicas da base" }}
        >
          Traga clínicas da base de prospecção, ou cadastre uma à mão em
          &ldquo;+ nova empresa&rdquo;.
        </Vazio>
      ) : dados && dados.itens.length === 0 ? (
        <div className="card text-[14px] text-muted">
          Nenhuma empresa bate com a busca.
        </div>
      ) : dados ? (
        <div className="card overflow-x-auto !p-0">
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr className="card-kicker border-b border-divider text-neutral-500">
                <th className={`${th} pl-4`}>Empresa</th>
                <th className={th}>Status</th>
                <th className={th}>Bairro</th>
                <th className={th}>E-mail</th>
                <th className={th}>Telefone</th>
                <th className={`${th} text-right`}>Contatos</th>
                <th className={`${th} text-right`}>Negócios</th>
                <th className={`${th} pr-4 text-right`} />
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setFicha(e.id)}
                  className="cursor-pointer border-t border-divider first:border-t-0 hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                >
                  <td className={`${td} pl-4`}>
                    <div className="font-medium text-text">{e.nome}</div>
                    {e.site && (
                      <div className="truncate text-[11.5px] text-neutral-500">
                        {e.site.replace(/^https?:\/\//, "")}
                      </div>
                    )}
                  </td>
                  <td className={td}>
                    <Celula
                      valor={e.status}
                      tipo="opcao"
                      opcoes={opStatus}
                      onSalvar={salvar(e.id, "status")}
                    />
                  </td>
                  <td className={`${td} text-muted`}>
                    <Celula
                      valor={e.bairro}
                      onSalvar={salvar(e.id, "bairro")}
                    />
                  </td>
                  <td className={td}>
                    <Celula
                      valor={e.email}
                      tipo="email"
                      onSalvar={salvar(e.id, "email")}
                    />
                  </td>
                  <td className={`${td} tnum`}>
                    <Celula
                      valor={e.telefone}
                      tipo="telefone"
                      onSalvar={salvar(e.id, "telefone")}
                    />
                  </td>
                  <td className={`${td} tnum text-right text-muted`}>
                    {e.n_contatos}
                  </td>
                  <td className={`${td} tnum text-right text-muted`}>
                    {e.n_negocios}
                  </td>
                  <td className={`${td} pr-4 text-right`}>
                    <button
                      type="button"
                      className="text-[12px] text-neutral-500 hover:text-[#e07f86]"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        setExcluir(e);
                      }}
                    >
                      excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {dados && dados.itens.length > 0 && (
        <p className="tnum mt-3 text-[12px] text-neutral-500">
          {plural(dados.itens.length, "empresa", "empresas")}
          {dados.total > dados.itens.length ? ` de ${dados.total}` : ""} ·
          negócios contam só os abertos
        </p>
      )}

      {ficha !== null && (
        <FichaCrm
          tipo="empresa"
          id={ficha}
          onFechar={() => setFicha(null)}
          onMudou={carregar}
        />
      )}
      {nova && (
        <FormCrm
          tipo="empresa"
          onFechar={() => setNova(false)}
          onSalvo={(id) => {
            carregar();
            setFicha(id);
          }}
        />
      )}
      {excluir && (
        <Dialogo
          titulo="Excluir empresa"
          descricao={`Excluir "${excluir.nome}" e os contatos dela? Empresa com negócio não sai: apague ou mude os negócios antes.`}
          confirmar="excluir"
          perigo
          onConfirmar={async () => {
            const alvo = excluir;
            setExcluir(null);
            try {
              await api.crmExcluir("empresa", alvo.id);
              ok(`${alvo.nome} excluída`);
              carregar();
            } catch (e) {
              falhou("Não excluí", e);
            }
          }}
          onCancelar={() => setExcluir(null)}
        />
      )}
      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </TelaCrm>
  );
}
