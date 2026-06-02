/**
 * Utilidades para generación y descarga de archivos CSV.
 *
 * El BOM (U+FEFF) al inicio garantiza que Excel en Windows/macOS
 * detecte correctamente UTF-8 y no corrompa tildes y eñes.
 */

/** Escapa un valor para CSV: envuelve en comillas y duplica las comillas internas. */
function escaparCelda(valor: string | number | null | undefined): string {
  const str = valor === null || valor === undefined ? "" : String(valor)
  return `"${str.replace(/"/g, '""')}"`
}

/**
 * Descarga un archivo CSV en el navegador.
 *
 * @param filename - Nombre del archivo sin extensión.
 * @param headers - Encabezados de columna.
 * @param rows - Filas de datos (valores primitivos, null se convierte a cadena vacía).
 */
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number | null | undefined)[][]
): void {
  const BOM = "﻿"
  const lineas = [
    headers.map(escaparCelda).join(","),
    ...rows.map((row) => row.map(escaparCelda).join(",")),
  ]
  const contenido = BOM + lineas.join("\r\n")
  const blob = new Blob([contenido], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${filename}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
