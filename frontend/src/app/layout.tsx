import type { Metadata } from "next"
import { Providers } from "@/components/providers"
import "./globals.css"

export const metadata: Metadata = {
  title: "Radar Público — Inteligencia comercial para el Mercado Público",
  description:
    "Detectá, analizá y postulá a licitaciones del Mercado Público de Chile con inteligencia artificial.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es">
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
