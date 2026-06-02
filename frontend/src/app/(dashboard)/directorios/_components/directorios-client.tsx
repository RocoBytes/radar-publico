"use client"

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Building2, Search, Users } from "lucide-react"
import { getOrganismos, getProveedores } from "@/lib/api"
import type { OrganismoListItem, ProveedorListItem } from "@/types/directorios"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

function formatMonto(monto: number | null): string {
  if (monto === null) return "—"
  if (monto >= 1_000_000_000) {
    return `$${(monto / 1_000_000_000).toFixed(1)}B`
  }
  if (monto >= 1_000_000) {
    return `$${(monto / 1_000_000).toFixed(1)}M`
  }
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(monto)
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: cols }).map((__, j) => (
            <TableCell key={j}>
              <Skeleton className="h-4 w-full" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  )
}

function Paginacion({
  page,
  totalPages,
  total,
  onPrev,
  onNext,
}: {
  page: number
  totalPages: number
  total: number
  onPrev: () => void
  onNext: () => void
}) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between">
      <p className="text-sm text-muted-foreground">
        Página {page} de {totalPages} ({total.toLocaleString("es-CL")} resultados)
      </p>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={onPrev} disabled={page <= 1}>
          Anterior
        </Button>
        <Button variant="outline" size="sm" onClick={onNext} disabled={page >= totalPages}>
          Siguiente
        </Button>
      </div>
    </div>
  )
}

// ── Tab: Organismos ──────────────────────────────────────────────────────────

function TabOrganismos() {
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [page, setPage] = useState(1)

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  const { data, isLoading } = useQuery({
    queryKey: ["directorios-organismos", debouncedQ, page],
    queryFn: () => getOrganismos({ q: debouncedQ || undefined, page, page_size: 25 }),
  })

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar organismo..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Organismo</TableHead>
              <TableHead className="w-40">Ministerio</TableHead>
              <TableHead className="w-36">Región</TableHead>
              <TableHead className="w-28 text-right">Licitaciones</TableHead>
              <TableHead className="w-36 text-right">Monto adjudicado</TableHead>
              <TableHead className="w-28 text-right">Proveedores</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <SkeletonRows cols={6} />
            ) : !data?.items.length ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  No se encontraron organismos
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((org: OrganismoListItem) => (
                <TableRow key={org.codigo_organismo}>
                  <TableCell>
                    <p className="font-medium leading-snug line-clamp-2 max-w-xs text-sm">
                      {org.nombre}
                    </p>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {org.ministerio
                      ? <span className="line-clamp-1">{org.ministerio}</span>
                      : "—"}
                  </TableCell>
                  <TableCell className="text-sm">{org.region ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="secondary" className="font-mono">
                      {org.total_licitaciones.toLocaleString("es-CL")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-sm font-medium">
                    {formatMonto(org.monto_total_adjudicado)}
                  </TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">
                    {org.proveedores_distintos > 0
                      ? org.proveedores_distintos.toLocaleString("es-CL")
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Paginacion
        page={page}
        totalPages={data?.total_pages ?? 1}
        total={data?.total ?? 0}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  )
}

// ── Tab: Proveedores ─────────────────────────────────────────────────────────

function TabProveedores() {
  const [q, setQ] = useState("")
  const [debouncedQ, setDebouncedQ] = useState("")
  const [page, setPage] = useState(1)

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  const { data, isLoading } = useQuery({
    queryKey: ["directorios-proveedores", debouncedQ, page],
    queryFn: () => getProveedores({ q: debouncedQ || undefined, page, page_size: 25 }),
  })

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar proveedor..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Razón social</TableHead>
              <TableHead className="w-32 font-mono">RUT</TableHead>
              <TableHead className="w-36 text-right">Licitaciones ganadas</TableHead>
              <TableHead className="w-40 text-right">Monto total adjudicado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <SkeletonRows cols={4} />
            ) : !data?.items.length ? (
              <TableRow>
                <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                  No se encontraron proveedores
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((prov: ProveedorListItem) => (
                <TableRow key={prov.rut}>
                  <TableCell>
                    <p className="font-medium text-sm leading-snug line-clamp-1 max-w-xs">
                      {prov.razon_social}
                    </p>
                    {prov.nombre_fantasia && (
                      <p className="text-xs text-muted-foreground truncate max-w-xs">
                        {prov.nombre_fantasia}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {prov.rut}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="secondary" className="font-mono">
                      {prov.licitaciones_ganadas.toLocaleString("es-CL")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-sm font-medium">
                    {formatMonto(prov.monto_total)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Paginacion
        page={page}
        totalPages={data?.total_pages ?? 1}
        total={data?.total ?? 0}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────

export function DirectoriosClient() {
  return (
    <Tabs defaultValue="organismos">
      <TabsList>
        <TabsTrigger value="organismos" className="gap-2">
          <Building2 className="h-4 w-4" />
          Organismos
        </TabsTrigger>
        <TabsTrigger value="proveedores" className="gap-2">
          <Users className="h-4 w-4" />
          Proveedores
        </TabsTrigger>
      </TabsList>

      <TabsContent value="organismos" className="mt-4">
        <TabOrganismos />
      </TabsContent>

      <TabsContent value="proveedores" className="mt-4">
        <TabProveedores />
      </TabsContent>
    </Tabs>
  )
}
