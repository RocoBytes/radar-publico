export type Region = { codigo: string; nombre: string }
export type UnspscFamilia = { codigo: string; nombre: string }
export type UnspscSegmento = { codigo: string; nombre: string; familias: UnspscFamilia[] }
export type CatalogosRegionesResponse = { items: Region[] }
export type CatalogosUnspscResponse = { items: UnspscSegmento[] }
