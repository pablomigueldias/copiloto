import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Shell } from "@/components/Shell";

import "./globals.css";

/**
 * Inter sobre Inter — a escala é fixa e a densidade mexe no espaçamento, não
 * no corpo. `next/font` embute a fonte no build: nada sai para a rede de
 * terceiros, que é a regra do projeto inteiro.
 */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Copiloto",
  description: "Assistente pessoal autônomo — local por padrão, externo por medida.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      {/* `suppressHydrationWarning` só no `<body>`, e só por causa de extensão:
          várias (ColorZilla, gerenciadores de senha, Grammarly) carimbam um
          atributo no body antes de o React hidratar, e o aviso resultante é
          barulho que esconde incompatibilidade de verdade. O escopo é o próprio
          elemento — nada dentro dele deixa de ser verificado. */}
      <body suppressHydrationWarning>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
