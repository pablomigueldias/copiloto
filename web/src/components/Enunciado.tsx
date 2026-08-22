"use client";

/**
 * O enunciado, com as tabelas desenhadas como tabela.
 *
 * As questões de prova vêm com tabela-verdade dentro do enunciado, e o acervo
 * as guarda no formato de tabela do Markdown — que é como elas saíram do PDF e
 * como eu consigo conferir contra ele. Renderizado como texto puro, aquilo vira
 * uma pilha de canos e traços: legível para quem escreveu, ilegível para quem
 * está respondendo com o cronômetro correndo.
 *
 * Não entra biblioteca de Markdown por causa disso. O que o enunciado tem de
 * Markdown é tabela, e só; um parser de tabela cabe em vinte linhas, enquanto
 * um renderizador completo traria negrito, link e imagem — três coisas que eu
 * teria de decidir como estilizar sem nenhuma questão precisando delas.
 */

type Bloco =
  | { tipo: "texto"; linhas: string[] }
  | { tipo: "tabela"; cabecalho: string[]; linhas: string[][] };

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
    const [cabecalho, ...resto] = corpo;
    blocos.push({ tipo: "tabela", cabecalho, linhas: resto.filter((l) => !eRegua(l)) });
  }
  fecharTexto();
  return blocos;
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
            {bloco.linhas.join("\n")}
          </p>
        ) : (
          // A tabela rola sozinha: numa tela estreita ela é a única coisa aqui
          // que não quebra de linha, e sem isto empurraria a página inteira.
          <div key={n} className="overflow-x-auto [&+*]:mt-5">
            <table className="border-collapse text-[0.85em] leading-[1.4]">
              <thead>
                <tr>
                  {bloco.cabecalho.map((c, i) => (
                    <th
                      key={i}
                      className="border border-divider bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)] px-[14px] py-[7px] text-center font-medium text-muted"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bloco.linhas.map((linha, i) => (
                  <tr key={i}>
                    {linha.map((c, j) => (
                      <td
                        key={j}
                        className="tnum border border-divider px-[14px] py-[7px] text-center"
                      >
                        {c}
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
