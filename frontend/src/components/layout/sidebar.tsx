"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useRef, useState } from "react"
import { LayoutDashboard, Search, Kanban, Radar, BarChart2, Settings, LogOut, Bell } from "lucide-react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { getNotificacionesResumen, marcarNotificacionLeida } from "@/lib/api"
import type { Notificacion } from "@/types/notificacion"

type SidebarUser = {
  email: string
  empresa: { razon_social: string } | null
}

const NAV_ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/licitaciones", icon: Search, label: "Oportunidades" },
  { href: "/pipeline", icon: Kanban, label: "Pipeline" },
  { href: "/radares", icon: Radar, label: "Radares" },
  { href: "/analisis", icon: BarChart2, label: "Análisis" },
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
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        aria-label="Notificaciones"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-semibold text-white leading-none">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Overlay para cerrar al hacer click afuera */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-full top-0 z-50 ml-2 w-72 rounded-md border bg-white shadow-lg">
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <span className="text-sm font-semibold">Notificaciones</span>
              {unreadCount > 0 && (
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                  {unreadCount} sin leer
                </span>
              )}
            </div>

            {items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">
                No tenés notificaciones
              </p>
            ) : (
              <ul className="max-h-80 overflow-y-auto divide-y">
                {items.map((notif) => (
                  <li key={notif.id}>
                    <button
                      type="button"
                      className={`w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors ${
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
                        {format(new Date(notif.created_at), "dd/MM HH:mm", {
                          locale: es,
                        })}
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

export function Sidebar({ user }: { user: SidebarUser }) {
  const pathname = usePathname()
  const router = useRouter()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      })
    } finally {
      router.push("/login")
    }
  }

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <span className="text-lg font-bold tracking-tight">Radar Público</span>
        <Badge variant="secondary" className="text-xs">
          beta
        </Badge>
      </div>

      <Separator />

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive =
            pathname === href || pathname.startsWith(`${href}/`)
          return (
            <Link
              key={href}
              href={href}
              className={
                isActive
                  ? "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium bg-primary/10 text-primary"
                  : "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          )
        })}

        {/* Campana de notificaciones */}
        <div className="mt-1 flex items-center gap-3 px-3 py-1">
          <NotifBell />
          <span className="text-sm text-muted-foreground">Notificaciones</span>
        </div>
      </nav>

      <Separator />

      {/* User + logout */}
      <div className="flex flex-col gap-2 px-4 py-4">
        <div className="flex flex-col gap-0.5">
          {user.empresa && (
            <span className="text-sm font-medium truncate">
              {user.empresa.razon_social}
            </span>
          )}
          <span className="text-xs text-muted-foreground truncate">
            {user.email}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="w-full justify-start gap-2"
        >
          <LogOut className="h-3.5 w-3.5" />
          {isLoggingOut ? "Cerrando sesión…" : "Cerrar sesión"}
        </Button>
      </div>
    </aside>
  )
}
