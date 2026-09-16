"use client";

import { useState } from "react";

import { api } from "@/lib/api";

/**
 * A figura de uma questão de prova.
 *
 * Duas decisões que não são estéticas.
 *
 * **Fundo branco fixo, não o fundo do tema.** As figuras vêm recortadas de PDF
 * de prova: diagrama UML em traço preto, árvore binária em cinza claro, DER em
 * linha fina. Quase todas têm fundo claro ou transparente, e sobre o tema
 * escuro do app uma linha preta sobre transparente simplesmente some. A moldura
 * clara é o que garante que o desenho seja legível nos dois temas — e é também
 * como a figura aparecia na prova impressa, que é a condição que estou
 * treinando.
 *
 * **O `alt` vira texto visível quando o arquivo falha.** Numa questão comum, a
 * imagem que não carrega é um incômodo; aqui ela pode tornar a questão
 * impossível — "que tipo de topologia é o da imagem?" não se responde sem a
 * imagem. Então o `onError` troca a figura pela descrição, que é o suficiente
 * para responder quase todas, e diz qual arquivo faltou.
 *
 * **Sem `arquivo`, só a descrição — e é assim de propósito.** Hoje toda questão
 * do acervo tem a figura da prova em disco; duas passaram um tempo sem, porque
 * a transcrição do caderno não trouxe a imagem, e foram recortadas do PDF
 * depois. O modo sem arquivo fica para a próxima que chegar assim. A tentação,
 * quando ela chega, é colar a descrição no enunciado; seria mentir sobre o que
 * a banca escreveu, que foi "analise a imagem a seguir". A descrição aparece
 * aqui, no lugar da figura e marcada como minha, pelo mesmo motivo que a
 * explicação nunca é apresentada como sendo da banca.
 */
export function ImagemQuestao({
  arquivo,
  alt,
  className,
}: {
  /** Ausente quando a figura da prova não foi recuperada — só resta a descrição. */
  arquivo?: string | null;
  alt: string | null;
  className?: string;
}) {
  const [falhou, setFalhou] = useState(false);

  if (!arquivo || falhou) {
    return (
      <figure
        className={`m-0 rounded-[10px] border border-dashed border-divider p-4 ${className ?? ""}`}
      >
        <div className="card-kicker mb-[6px] text-neutral-500">
          {arquivo ? "Figura não carregou" : "Figura da prova não recuperada"}
        </div>
        <p className="m-0 text-[14px] leading-[1.6] text-muted">
          {alt ?? "Sem descrição — o arquivo é a única fonte."}
        </p>
        <p className="m-0 mt-2 text-[11.5px] leading-[1.5] text-neutral-600">
          {arquivo ? (
            <span className="font-mono">data/estudo/imagens/{arquivo}</span>
          ) : (
            "Descrição minha, não da banca — o enunciado original manda analisar a imagem."
          )}
        </p>
      </figure>
    );
  }

  return (
    <figure className={`m-0 ${className ?? ""}`}>
      {/* `<img>` e não `next/image`: o arquivo é servido pelo FastAPI através
          do rewrite `/api/*`, sem as dimensões que o Image exige em build, e
          são figuras de 3 a 20 KB — não há o que otimizar. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={api.urlImagem(arquivo)}
        alt={alt ?? "Figura da questão"}
        onError={() => setFalhou(true)}
        className="block max-w-full rounded-[10px] border border-divider bg-white p-3"
      />
    </figure>
  );
}
