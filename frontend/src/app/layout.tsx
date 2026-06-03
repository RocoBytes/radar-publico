import type { Metadata } from "next"
import { Fira_Sans, Fira_Code } from "next/font/google"
import { Providers } from "@/components/providers"
import "./globals.css"

const firaSans = Fira_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
})

const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",
  display: "swap",
})

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
      <body className={`${firaSans.variable} ${firaCode.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
