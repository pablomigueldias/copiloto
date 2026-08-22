"use client";

import { useEffect, useState } from "react";

import { Erro } from "@/components/ui";
import { api } from "@/lib/api";
import type { ModuloResumo } from "@/lib/tipos";

import { NovaQuestao } from "./NovaQuestao";

type Ficha = {
  chave: string;
  numero: string;
  nome: string;
  onde: string;
  descricao: string;
  campos: string[];
  exemplo: React.ReactNode;
};

function Alt({ letra, texto, certa }: { letra: string; texto: string; certa?: boolean }) {
  return (
    <div className={`flex gap-2 text-[13.5px] ${certa ? "text-accent-200" : "text-muted"}`}>
      <span className="tnum flex-none text-neutral-500">({letra})</span>
      <span>{texto}</span>
    </div>
  );
}

const FICHAS: Ficha[] = [
  {
    chave: "certo_errado",
    numero: "01",
    nome: "Julgue o item — certo ou errado",
    onde: "todas as provas do acervo",
    descricao:
      "O formato que a Quadrix aplica nas provas que eu guardei. Um comando vale para um bloco de itens, e cada item é uma afirmação a julgar. Na revisão o comando é repetido em cada questão, porque cada uma tem que funcionar sozinha quando voltar meses depois.",
    campos: ["tipo: certo_errado", "comando", "enunciado (o item)", "gabarito C|E", "explicacao"],
    exemplo: (
      <>
        <div className="card-kicker">Matemática · Lógica proposicional</div>
        <p className="m-0 mt-2 text-[12.5px] leading-[1.5] text-neutral-500">
          Acerca da proposição “Se a borboleta saiu do casulo, então a águia
          pousou no ninho”, julgue o item a seguir.
        </p>
        <p className="m-0 mt-2 text-[14px] leading-[1.5]">
          A negação dessa proposição é “A borboleta não saiu do casulo e a
          águia pousou no ninho”.
        </p>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="C" texto="Certo" />
          <Alt letra="E" texto="Errado" certa />
        </div>
        <div className="tnum mt-3 text-[11.5px] text-neutral-600">
          gabarito E · dificuldade 1
        </div>
      </>
    ),
  },
  {
    chave: "multipla_escolha",
    numero: "02",
    nome: "Múltipla escolha",
    onde: "todos os módulos",
    descricao:
      "Cinco alternativas, uma correta, ordem fixa. A ordem não muda entre revisões de propósito: quem revisa reconhece a posição antes do conteúdo, e o que precisa variar é a questão, não o lugar da resposta.",
    campos: ["tipo: multipla_escolha", "enunciado", "alternativas[5]", "gabarito", "explicacao"],
    exemplo: (
      <>
        <div className="card-kicker">Matemática · Lógica proposicional</div>
        <p className="m-0 mt-2 text-[14px] leading-[1.5]">
          A proposição “Se Marcos faz dieta, então emagrece” é verdadeira. Com
          base nessa informação, assinale a alternativa correta.
        </p>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="“Marcos faz dieta e não emagrece” é necessariamente falsa." certa />
          <Alt letra="B" texto="A negação é “Se Marcos não emagrece, então não faz dieta”." />
          <Alt letra="C" texto="Equivale a “Marcos emagrece e não faz dieta”." />
          <Alt letra="D" texto="A negação é “Marcos não faz dieta ou emagrece”." />
          <Alt letra="E" texto="“Se Marcos emagrece, então faz dieta” é verdadeira." />
        </div>
        <div className="tnum mt-3 text-[11.5px] text-neutral-600">
          gabarito A · dificuldade 2
        </div>
      </>
    ),
  },
  {
    chave: "afirmacoes",
    numero: "03",
    nome: "Afirmações I, II, III",
    onde: "banco de dados · estatística",
    descricao:
      "Três afirmações e uma pergunta sobre quais valem. É o que melhor separa quem sabe de quem reconhece — você precisa julgar as três, não achar a familiar. Alternativas sempre nesta ordem: uma só, outra só, dois pares, todas.",
    campos: ["tipo: afirmacoes", "enunciado", "afirmacoes[3]", "alternativas[5]", "gabarito"],
    exemplo: (
      <>
        <div className="card-kicker">Banco de dados · Normalização</div>
        <p className="m-0 mt-2 text-[14px]">
          Leia as afirmações a seguir sobre a terceira forma normal:
        </p>
        <ol className="m-0 mt-2 flex list-[upper-roman] flex-col gap-1 pl-6 text-[13.5px] text-muted">
          <li>Está na 3FN quem está na 2FN e não tem dependência transitiva.</li>
          <li>Dependência transitiva é atributo não-chave determinando outro.</li>
          <li>Toda relação na 3FN está, por consequência, na FNBC.</li>
        </ol>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="I, apenas." />
          <Alt letra="B" texto="III, apenas." />
          <Alt letra="C" texto="I e II, apenas." certa />
          <Alt letra="D" texto="II e III, apenas." />
          <Alt letra="E" texto="I, II e III." />
        </div>
      </>
    ),
  },
  {
    chave: "negativa",
    numero: "04",
    nome: "Enunciado negativo",
    onde: "banco de dados · python",
    descricao:
      "Quatro alternativas certas e uma fora do conjunto. Serve para fixar lista fechada. O NÃO vai em maiúsculas, como na prova — senão você lê por cima e erra por leitura, não por conteúdo.",
    campos: ["tipo: negativa", "enunciado (com NÃO)", "alternativas[5]", "gabarito"],
    exemplo: (
      <>
        <div className="card-kicker">Banco de dados · Transações</div>
        <p className="m-0 mt-2 text-[14px]">
          <strong className="text-accent-200">NÃO</strong> se trata de um comando
          de controle de transação:
        </p>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="TRUNCATE." certa />
          <Alt letra="B" texto="COMMIT." />
          <Alt letra="C" texto="ROLLBACK." />
          <Alt letra="D" texto="SAVEPOINT." />
          <Alt letra="E" texto="SET TRANSACTION." />
        </div>
      </>
    ),
  },
  {
    chave: "texto_base",
    numero: "05",
    nome: "Com texto-base",
    onde: "português",
    descricao:
      "Um trecho e uma pergunta sobre ele. É o formato de português inteiro. Um mesmo texto-base pode servir a várias questões — repita o campo em cada uma, para que ela funcione sozinha na revisão.",
    campos: ["tipo: texto_base", "texto_base", "texto_base_fonte", "enunciado", "alternativas[5]"],
    exemplo: (
      <>
        <div className="card-kicker">Português · Regência verbal</div>
        <div className="mt-2 border-l-2 border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] pl-3">
          <p className="m-0 text-[13.5px] leading-[1.55] text-muted">
            A modelagem de dados implica decisões que o código não desfaz
            sozinho.
          </p>
        </div>
        <p className="m-0 mt-2 text-[14px]">
          A frase que mantém a regência correta é:
        </p>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="implicou em perda de dados." />
          <Alt letra="B" texto="implicou na perda de dados." />
          <Alt letra="C" texto="implicou perda de dados." certa />
        </div>
      </>
    ),
  },
  {
    chave: "codigo",
    numero: "06",
    nome: "Com código ou SQL",
    onde: "sql · python · spark",
    descricao:
      "Um trecho de código e uma pergunta sobre o que ele devolve. O melhor formato para SQL: a alternativa correta é um resultado, não uma definição, e não dá para acertar por vocabulário.",
    campos: ["tipo: codigo", "codigo", "linguagem", "enunciado", "alternativas[5]"],
    exemplo: (
      <>
        <div className="card-kicker">SQL · JOINs e nulos</div>
        <pre className="m-0 mt-2 overflow-x-auto rounded-[6px] border border-divider bg-[color-mix(in_srgb,black_25%,transparent)] p-3 font-mono text-[12px] leading-[1.55]">{`SELECT c.nome, COUNT(p.id)
  FROM cliente c
  LEFT JOIN pedido p ON p.cliente_id = c.id
 WHERE p.valor > 100
 GROUP BY c.nome;`}</pre>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="lista todos os clientes, com zero quando não houver pedido." />
          <Alt letra="B" texto="o WHERE anula o LEFT JOIN e ela vira INNER JOIN." certa />
        </div>
      </>
    ),
  },
  {
    chave: "calculo",
    numero: "07",
    nome: "Cálculo",
    onde: "matemática · estatística",
    descricao:
      "Números no enunciado, número na resposta. As alternativas erradas devem ser os erros prováveis — a conta invertida, o ponto percentual trocado pela variação relativa — e não valores aleatórios: é o distrator que ensina.",
    campos: ["tipo: calculo", "enunciado", "alternativas[5]", "explicacao (com a conta)"],
    exemplo: (
      <>
        <div className="card-kicker">Matemática · Tabela-verdade</div>
        <p className="m-0 mt-2 text-[14px]">
          Na disjunção exclusiva a ⊻ b, quais são os valores de V V, V F, F V e
          F F?
        </p>
        <div className="mt-3 flex flex-col gap-1">
          <Alt letra="A" texto="F, F, F, F" />
          <Alt letra="B" texto="F, V, V, F" certa />
          <Alt letra="C" texto="V, F, V, V" />
        </div>
      </>
    ),
  },
  {
    chave: "flashcard",
    numero: "08",
    nome: "Flashcard aberto",
    onde: "sem alternativas",
    descricao:
      "A exceção. Você responde de cabeça, vira a carta e diz se acertou. Só para definição e fórmula, onde escrever cinco alternativas custa mais do que vale — e onde reconhecer não é o mesmo que lembrar. O agendamento é idêntico.",
    campos: ["tipo: flashcard", "enunciado (frente)", "explicacao (verso)", "fonte"],
    exemplo: (
      <>
        <div className="card-kicker">Estatística · Bayes</div>
        <p className="m-0 mt-2 text-[14px]">
          Escreva o teorema de Bayes e diga o que é o denominador.
        </p>
        <hr className="hr my-3" />
        <p className="m-0 text-[13.5px] leading-[1.55] text-muted">
          P(A|B) = P(B|A)·P(A) / P(B). O denominador é a probabilidade total de
          B — o que normaliza a conta.
        </p>
      </>
    ),
  },
];

const COMUNS: [string, string, string][] = [
  ["modulo", "sim", "Matemática e raciocínio lógico, Banco de dados — o mesmo nome que está em Módulos."],
  ["topico", "sim", "Lógica proposicional, Normalização. É o par módulo+tópico que a revisão mostra no topo."],
  ["formato", "sim", "Um dos oito abaixo. Define como a questão é montada na tela."],
  ["enunciado", "sim", "A pergunta, no imperativo da prova: “assinale”, “julgue o item”, “é correto afirmar que”."],
  ["alternativas", "5, salvo certo_errado e flashcard", "A a E. Ordem fixa: quem revisa reconhece a posição antes do conteúdo."],
  ["gabarito", "sim", "Uma letra — A a E, ou C/E no julgue o item. É o único campo que decide certo ou errado."],
  ["explicacao", "não", "Por que a correta está correta. Só aparece depois da segunda tentativa. Vem vazia no acervo importado — a banca publica gabarito, não razão."],
  ["comando", "não", "O enunciado que vale para um bloco de itens. Repetido em cada questão do bloco, para ela funcionar sozinha."],
  ["origem", "não", "“Quadrix · COFFITO 2023 · item 29”. É o que torna o import idempotente e o que me deixa conferir o gabarito no PDF."],
  ["dificuldade", "não", "1 a 3. Só ordena a fila do dia — o agendamento não usa."],
];

export default function Formatos() {
  const [modulos, setModulos] = useState<ModuloResumo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [abrindo, setAbrindo] = useState<string | null>(null);

  useEffect(() => {
    api
      .modulos()
      .then(setModulos)
      .catch((e) => setErro(String(e.message ?? e)));
  }, []);

  return (
    <div className="max-w-[1180px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        Formatos de questão
      </h1>
      <p className="m-0 mb-8 max-w-[68ch] text-[15px] text-muted">
        Oito formas. As duas primeiras são as que as provas do acervo de fato
        usam — a Quadrix aplica julgue-o-item e múltipla escolha de cinco
        alternativas. Cada uma existe para um tipo de conteúdo diferente:
        português pede texto-base, SQL pede código, matemática pede cálculo.
        Cadastre no formato mais próximo e o resto da tela se resolve.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <section className="mb-10">
        <h2 className="m-0 mb-4 text-[19px]">Campos de toda questão</h2>
        <div className="overflow-x-auto">
          <table className="table min-w-[680px]">
            <thead>
              <tr>
                <th className="w-[140px]">Campo</th>
                <th className="w-[180px]">Obrigatório</th>
                <th>O que vai nele</th>
              </tr>
            </thead>
            <tbody>
              {COMUNS.map(([campo, obr, oque]) => (
                <tr key={campo}>
                  <td className="font-mono text-[13px] text-accent-300">
                    {campo}
                  </td>
                  <td className="text-[13px] text-neutral-400">{obr}</td>
                  <td className="text-[13.5px] text-muted">{oque}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {FICHAS.map((f) => (
        <section key={f.chave} className="mb-10 scroll-mt-6" id={f.chave}>
          <div className="mb-4 flex items-baseline gap-3">
            <span className="tnum text-[13px] text-neutral-600">{f.numero}</span>
            <h2 className="m-0 text-[19px]">{f.nome}</h2>
            <span className="tag tag-neutral flex-none">{f.onde}</span>
            <span className="h-px flex-1 bg-divider" />
            <button
              type="button"
              onClick={() => setAbrindo(f.chave)}
              className="btn btn-secondary flex-none py-[5px] text-[12.5px]"
            >
              Cadastrar neste formato
            </button>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="m-0 mb-3 max-w-[58ch] text-[14px] leading-[1.6] text-muted">
                {f.descricao}
              </p>
              <div className="font-mono text-[12.5px] leading-[1.75] text-neutral-500">
                {f.campos.map((c) => (
                  <div key={c}>{c}</div>
                ))}
              </div>
            </div>
            <article className="card elev-sm">{f.exemplo}</article>
          </div>
        </section>
      ))}

      {abrindo && modulos && (
        <NovaQuestao
          formato={abrindo}
          modulos={modulos}
          onFechar={() => setAbrindo(null)}
          onCriada={() => {
            setAbrindo(null);
            api.modulos().then(setModulos).catch(() => {});
          }}
        />
      )}
    </div>
  );
}
