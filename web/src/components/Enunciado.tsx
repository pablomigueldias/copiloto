"use client";

import type { ReactNode } from "react";

/**
 * O enunciado e a explicação, com as tabelas desenhadas como tabela.
 *
 * As questões de prova vêm com tabela-verdade dentro do enunciado, e o acervo
 * as guarda no formato de tabela do Markdown — que é como elas saíram do PDF e
 * como eu consigo conferir contra ele. Renderizado como texto puro, aquilo vira
 * uma pilha de canos e traços: legível para quem escreveu, ilegível para quem
 * está respondendo com o cronômetro correndo.
 *
 * Não entra biblioteca de Markdown por causa disso. O que o acervo usa de
 * Markdown são três marcas, e só: **tabela**, **negrito** e `código`. Um parser
 * disso cabe em quarenta linhas, enquanto um renderizador completo traria link,
 * imagem, título e lista — quatro coisas que eu teria de decidir como estilizar
 * sem nenhuma questão precisando delas.
 *
 * O negrito e a crase entraram quando as explicações do caderno do Avança SP
 * foram reescritas: elas marcam a palavra que decide o item ("o erro está em
 * **apenas**") e o identificador que não é prosa (`fork()`, `chmod 755`). Sem
 * o parser, o que aparecia na tela eram os próprios asteriscos — pior do que
 * não ter destaque nenhum, porque vira sujeira no meio da frase.
 */

/** `código`, que é a marca mais interna — dentro dela nada mais é marcação. */
function comCodigo(texto: string): ReactNode[] {
  return texto.split(/(`[^`\n]+`)/g).map((parte, i) =>
    parte.startsWith("`") && parte.endsWith("`") && parte.length > 2 ? (
      <code
        key={i}
        className="rounded-[4px] bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] px-[5px] py-[1px] font-mono text-[0.9em]"
      >
        {parte.slice(1, -1)}
      </code>
    ) : (
      parte
    ),
  );
}

/**
 * As marcas de dentro da linha: `**negrito**` e `` `código` ``.
 *
 * Devolve um array de nós porque é isso que o JSX aceita no lugar de uma
 * string. As partes que não casam saem como texto puro — inclusive as quebras
 * de linha, que o `whitespace-pre-line` do parágrafo continua honrando.
 *
 * O negrito é quebrado primeiro e o conteúdo dele volta para o parser de
 * código, senão `**`fork()`**` — negrito com código dentro, que o acervo usa —
 * sairia com as crases à mostra.
 */
function comMarcas(texto: string): ReactNode[] {
  return texto.split(/(\*\*[^*\n]+\*\*)/g).flatMap((parte, i) =>
    parte.startsWith("**") && parte.endsWith("**") && parte.length > 4 ? (
      <strong key={i} className="font-semibold text-text">
        {comCodigo(parte.slice(2, -2))}
      </strong>
    ) : (
      comCodigo(parte)
    ),
  );
}

type Bloco =
  | { tipo: "texto"; linhas: string[] }
  | { tipo: "tabela"; cabecalho: string[] | null; linhas: string[][] };

/** `| a | b |` — linha de tabela. */
function eLinhaDeTabela(linha: string): boolean {
  const t = linha.trim();
  return t.startsWith("|") && t.endsWith("|") && t.length > 2;
}

/** `|---|---|` — a régua que separa cabeçalho do corpo, e não é dado. */
function eRegua(celulas: string[]): boolean {
  return celulas.every((c) => /^:?-{2,}:?$/.test(c.trim()));
}

function celulas(linha: string): string[] {
  return linha
    .trim()
    .slice(1, -1)
    .split("|")
    .map((c) => c.trim());
}

function emBlocos(texto: string): Bloco[] {
  const blocos: Bloco[] = [];
  let texto_atual: string[] = [];

  const fecharTexto = () => {
    // Sem o `trim` nas pontas, a linha em branco que separa o parágrafo da
    // tabela no Markdown viraria um vão dentro do bloco de texto.
    while (texto_atual.length && !texto_atual[0].trim()) texto_atual.shift();
    while (texto_atual.length && !texto_atual[texto_atual.length - 1].trim()) texto_atual.pop();
    if (texto_atual.length) blocos.push({ tipo: "texto", linhas: texto_atual });
    texto_atual = [];
  };

  const linhas = texto.split("\n");
  for (let i = 0; i < linhas.length; i++) {
    if (!eLinhaDeTabela(linhas[i])) {
      texto_atual.push(linhas[i]);
      continue;
    }
    const corpo: string[][] = [];
    while (i < linhas.length && eLinhaDeTabela(linhas[i])) corpo.push(celulas(linhas[i++]));
    i--;

    // Uma linha só entre canos é mais provável ser texto do que tabela.
    if (corpo.length < 2) {
      texto_atual.push(linhas[i]);
      continue;
    }
    fecharTexto();
    // Matriz de prova não tem cabeçalho: as quatro linhas são dado, e desenhar a
    // primeira como título diria que ela rotula as outras — o oposto do que a
    // questão pede para enxergar. Abrir a tabela pela régua declara isso.
    const semCabecalho = eRegua(corpo[0]);
    const [primeira, ...resto] = corpo;
    blocos.push({
      tipo: "tabela",
      cabecalho: semCabecalho ? null : primeira,
      linhas: resto.filter((l) => !eRegua(l)),
    });
  }
  fecharTexto();
  return blocos;
}

/**
 * O enunciado sem as tabelas, para a prévia de uma linha na listagem do acervo.
 *
 * Lá o enunciado é texto puro dentro de um `line-clamp-2`, e uma matriz vira
 * uma fileira de canos que ocupa as duas linhas sem identificar nada. O que
 * identifica a questão é a frase; a tabela se lê na gaveta.
 */
export function semTabelas(texto: string): string {
  return texto
    .split("\n")
    .filter((l) => !eLinhaDeTabela(l))
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

export function Enunciado({ texto, className }: { texto: string; className?: string }) {
  const blocos = emBlocos(texto);

  return (
    <div className={className}>
      {blocos.map((bloco, n) =>
        bloco.tipo === "texto" ? (
          <p
            key={n}
            className="m-0 whitespace-pre-line [&+*]:mt-5"
          >
            {comMarcas(bloco.linhas.join("\n"))}
          </p>
        ) : (
          // A tabela rola sozinha: numa tela estreita ela é a única coisa aqui
          // que não quebra de linha, e sem isto empurraria a página inteira.
          <div key={n} className="overflow-x-auto [&+*]:mt-5">
            <table className="border-collapse text-[0.85em] leading-[1.4]">
              {bloco.cabecalho && (
                <thead>
                  <tr>
                    {bloco.cabecalho.map((c, i) => (
                      <th
                        key={i}
                        className="border border-divider bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)] px-[14px] py-[7px] text-center font-medium text-muted"
                      >
                        {comMarcas(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                {bloco.linhas.map((linha, i) => (
                  <tr key={i}>
                    {linha.map((c, j) => (
                      <td
                        key={j}
                        className="tnum border border-divider px-[14px] py-[7px] text-center"
                      >
                        {comMarcas(c)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ),
      )}
    </div>
  );
}
