"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useRef, useState } from "react"
import {
  LayoutDashboard,
  Search,
  Kanban,
  Radar,
  BarChart2,
  BookOpen,
  Settings,
  LogOut,
  Bell,
} from "lucide-react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { getMeClient, getNotificacionesResumen, marcarNotificacionLeida } from "@/lib/api"
import type { Notificacion } from "@/types/notificacion"

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/licitaciones", icon: Search, label: "Oportunidades" },
  { href: "/pipeline", icon: Kanban, label: "Pipeline" },
  { href: "/radares", icon: Radar, label: "Radares" },
  { href: "/analisis", icon: BarChart2, label: "Análisis" },
  { href: "/directorios", icon: BookOpen, label: "Directorios" },
  { href: "/configuracion", icon: Settings, label: "Configuración" },
] as const

const TIPO_LABELS: Record<string, string> = {
  nueva_oportunidad: "Nueva",
  recordatorio_cierre: "Cierre",
  cambio_estado: "Estado",
  adjudicacion_postulacion: "Adjudicación",
  oportunidad_futura: "Futura",
  sistema: "Sistema",
}

function NotifBell() {
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()
  const containerRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ["notif-resumen"],
    queryFn: getNotificacionesResumen,
    refetchInterval: 60_000,
  })

  const unreadCount = data?.unread_count ?? 0
  const items = data?.items ?? []

  async function handleClickItem(notif: Notificacion) {
    setOpen(false)
    await marcarNotificacionLeida(notif.id)
    void queryClient.invalidateQueries({ queryKey: ["notif-resumen"] })
    if (notif.licitacion_codigo) {
      router.push(`/licitaciones/${notif.licitacion_codigo}`)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="Notificaciones"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-semibold leading-none text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-lg border bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <span className="text-sm font-semibold">Notificaciones</span>
              {unreadCount > 0 && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                  {unreadCount} sin leer
                </span>
              )}
            </div>

            {items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                No tenés notificaciones
              </p>
            ) : (
              <ul className="max-h-80 divide-y overflow-y-auto">
                {items.map((notif) => (
                  <li key={notif.id}>
                    <button
                      type="button"
                      className={`w-full cursor-pointer px-4 py-3 text-left transition-colors hover:bg-muted/50 ${
                        notif.leida_at === null ? "bg-blue-50/60" : ""
                      }`}
                      onClick={() => void handleClickItem(notif)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="line-clamp-2 text-sm font-medium leading-snug">
                          {notif.titulo}
                        </span>
                        <span className="shrink-0 rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {TIPO_LABELS[notif.tipo] ?? notif.tipo}
                        </span>
                      </div>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {format(new Date(notif.created_at), "dd/MM HH:mm", { locale: es })}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: getMeClient,
    staleTime: 5 * 60 * 1000,
  })

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" })
    } finally {
      router.push("/login")
    }
  }

  const initial = user
    ? (user.empresa?.razon_social ?? user.email).charAt(0).toUpperCase()
    : "…"

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-white shadow-sm">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
            <circle cx="5" cy="19" r="2.5" fill="currentColor" />
            <path d="M5 13a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M5 7a12 12 0 0 1 12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>
        <span className="text-base font-bold tracking-tight">Radar Público</span>
        <Badge variant="secondary" className="h-4 px-1.5 py-0 text-[10px]">
          beta
        </Badge>
      </div>

      <Separator />

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-0.5 px-3 py-3">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive = pathname === href || pathname.startsWith(`${href}/`)
          return (
            <Link
              key={href}
              href={href}
              className={
                isActive
                  ? "-ml-0.5 flex items-center gap-3 rounded-md border-l-2 border-primary bg-primary/10 py-2 pl-[11px] pr-3 text-sm font-semibold text-primary transition-colors"
                  : "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      <Separator />

      {/* User + notif + logout */}
      <div className="flex flex-col gap-2.5 px-4 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            {initial}
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            {user ? (
              <>
                {user.empresa && (
                  <span className="truncate text-sm font-medium leading-tight">
                    {user.empresa.razon_social}
                  </span>
                )}
                <span className="truncate text-xs leading-tight text-muted-foreground">
                  {user.email}
                </span>
              </>
            ) : (
              <div className="space-y-1">
                <div className="h-3 w-24 animate-pulse rounded bg-muted" />
                <div className="h-2.5 w-32 animate-pulse rounded bg-muted" />
              </div>
            )}
          </div>
          <NotifBell />
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="w-full cursor-pointer justify-start gap-2 text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-3.5 w-3.5" />
          {isLoggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
        </Button>
      </div>
    </aside>
  )
}
