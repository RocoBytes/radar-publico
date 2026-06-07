# Estrategia de Resolución de Errores de Tests en CI

Este documento describe el diagnóstico y el plan de acción para corregir la suite de pruebas del backend en `radar-publico`.

## 1. Diagnóstico del Error Raíz

El 95% de las fallas (`FAILED` y `ERROR` en cascada) se deben a una única excepción que invalida la transacción de la base de datos durante la fase de inserción o en el `teardown` de las fixtures:

```text
sqlalchemy.exc.PendingRollbackError: This Session's transaction has been rolled back due to a previous exception during flush...
Original exception was: cannot insert a non-DEFAULT value into column "search_vector"
DETAIL: Column "search_vector" is a generated column.
```

### ¿Por qué ocurre?
En una migración reciente, la columna `search_vector` de la tabla `licitaciones` se modificó a una columna generada nativamente en PostgreSQL (`GENERATED ALWAYS AS ... STORED`).
PostgreSQL prohíbe explícitamente pasar cualquier valor (incluyendo `None`/`NULL`) a una columna generada durante un `INSERT` o `UPDATE` (solo permite omitirla o pasarle la palabra clave `DEFAULT`).

Dado que SQLAlchemy mapea `search_vector` como un atributo normal en el modelo `Licitacion`:
```python
search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
```
SQLAlchemy incluye el campo `search_vector` con valor `None` en sus consultas SQL generadas, disparando el error `GeneratedAlwaysError`.

---

## 2. Plan de Acción y Solución Técnica

### Paso 1: Configurar `search_vector` como solo lectura (server-side generated) en los Modelos ORM

Debemos indicarle a SQLAlchemy que la base de datos se encarga de calcular el valor de esta columna y que la **omita** por completo en las sentencias `INSERT` y `UPDATE`. Esto se logra importando y utilizando `FetchedValue`.

#### A. Modificar `backend/app/models/licitacion.py`
1. Importar `FetchedValue` desde `sqlalchemy`.
2. Actualizar el mapeo de `search_vector` para incluir `FetchedValue()`:

```python
from sqlalchemy import (
    # ... otras importaciones ...
    FetchedValue,
)

# ...

class Licitacion(Base):
    # ...
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, FetchedValue(), nullable=True)
```

#### B. Modificar `backend/app/models/plan_anual.py`
Aunque el plan anual use un trigger o una columna calculada, aplicar la misma configuración previene que SQLAlchemy intente insertar valores nulos:

```python
from sqlalchemy import (
    # ... otras importaciones ...
    FetchedValue,
)

# ...

class PlanAnualLinea(Base):
    # ...
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, FetchedValue(), nullable=True)
```

---

## 3. Estrategia de Validación de Tests

Una vez aplicados los cambios en los modelos, se debe ejecutar la suite de pruebas de manera incremental:

1. **Ejecutar tests unitarios específicos**:
   ```bash
   pytest app/tests/unit/api/test_licitaciones.py
   ```
2. **Ejecutar todos los tests unitarios**:
   ```bash
   pytest app/tests/unit
   ```
3. **Ejecutar la suite completa**:
   ```bash
   pytest app/tests --cov=app/services --cov-fail-under=70 -v
   ```

---

## 4. Notas sobre Tests Obsoletos / XFAIL

Los tests que fallaban legítimamente por características no implementadas en la versión actual (como el onboarding wizard completo, patrones estacionales o la vista agrupada por radar) ya están correctamente decorados con `@pytest.mark.xfail` en la base de código. 

Esto significa que no es necesario eliminarlos ni modificarlos en esta etapa, ya que pytest los procesa como fallos esperados (`XFAIL`) sin romper el resultado general del CI (exit code 0).
