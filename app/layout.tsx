import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Santri Export — SOL e Horus",
  description:
    "Painel demonstrativo de gestão das exportações do Santri para SOL Atacadista e Horus Distribuidora.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
