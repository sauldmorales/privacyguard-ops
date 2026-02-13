# Estructura de Carpetas - PrivacyGuard Ops

Esta guía explica la función y propósito de cada carpeta en el proyecto PrivacyGuard Ops (PGO).

---

## Carpetas en el directorio raíz

### `/src`
**Propósito**: Contiene todo el código fuente de la aplicación PGO.

Este directorio sigue el patrón "src-layout" estándar de Python, donde todo el código de la aplicación se encuentra dentro de un subdirectorio `src/`. Esto separa claramente el código fuente de las pruebas, configuraciones y otros archivos del proyecto.

**Estructura interna**:
```
src/pgo/
├── cli.py              # Interfaz de línea de comandos
├── manifest.py         # Manejo de manifiestos de brokers
├── core/               # Módulos centrales del sistema
│   ├── audit.py        # Sistema de auditoría con cadena de hash
│   ├── db.py           # Gestión de base de datos SQLite
│   ├── errors.py       # Excepciones personalizadas
│   ├── logging.py      # Configuración de logging
│   ├── models.py       # Modelos de datos Pydantic
│   ├── paths.py        # Gestión de rutas del sistema
│   ├── repository.py   # Capa de acceso a datos
│   ├── settings.py     # Configuración de la aplicación
│   └── state.py        # Máquina de estados de hallazgos
└── modules/            # Módulos especializados
    ├── pii_guard.py    # Protección y redacción de PII
    └── vault.py        # Bóveda de evidencia encriptada
```

---

### `/tests`
**Propósito**: Contiene todas las pruebas unitarias e integración del proyecto.

Esta carpeta asegura la calidad y corrección del código a través de pruebas automatizadas. Las pruebas verifican:
- Transiciones de estado válidas e inválidas
- Integridad de la cadena de auditoría
- Detección de fugas de PII
- Encriptación/desencriptación correcta del vault
- Funcionalidad general del sistema

**Estructura**:
```
tests/
└── unit/              # Pruebas unitarias por módulo
    ├── test_audit.py
    ├── test_pii_guard.py
    ├── test_state.py
    └── test_vault.py
```

**Cómo ejecutar**: `pytest tests/ -v`

---

### `/data`
**Propósito**: Almacena datos de runtime locales y la base de datos SQLite.

Esta carpeta contiene:
- `pgo.db`: Base de datos SQLite con hallazgos, eventos y metadatos
- Otros archivos de datos temporales generados durante la operación

**⚠️ Importante**: Esta carpeta está excluida de Git (`.gitignore`) para evitar exponer información sensible.

---

### `/vault`
**Propósito**: Almacena evidencia encriptada (capturas de pantalla, PDFs, etc.).

El vault es el sistema de almacenamiento seguro para evidencia de opt-out. Cada archivo pasa por:
1. **Redacción**: Elimina PII visible (usando `pii_guard`)
2. **Hash**: Calcula SHA-256 para verificar integridad
3. **Encriptación**: Usa Fernet (AES-128-CBC + HMAC) con clave local
4. **Almacenamiento**: Guarda con timestamp y hash de integridad

**Características de seguridad**:
- Clave de encriptación solo en variable de entorno (`PGO_VAULT_KEY`)
- Permisos restrictivos (0o600) en archivos
- Nunca almacena credenciales o PII sin encriptar

**⚠️ Importante**: Esta carpeta está excluida de Git para proteger evidencia sensible.

---

### `/exports`
**Propósito**: Almacena exportaciones de auditoría en formatos JSON/CSV.

Cuando ejecutas `pgo export --audit`, el sistema genera:
- **Log de eventos**: Cadena completa de eventos append-only
- **Verificación de integridad**: Hash chain completo
- **Firma opcional**: HMAC con clave local
- **Formatos**: JSON (estructurado) o CSV (tabular)

Las exportaciones contienen **solo hashes y timestamps**, nunca PII en claro.

**⚠️ Importante**: Esta carpeta está excluida de Git.

---

### `/reports`
**Propósito**: Almacena reportes generados y resúmenes de estado.

Esta carpeta contendrá reportes sobre:
- Estado actual de opt-outs por broker
- Detección de resurfacing (reaparición de datos)
- Estadísticas de verificación
- Resúmenes de auditoría

**⚠️ Importante**: Esta carpeta está excluida de Git.

---

### `/manifests`
**Propósito**: Contiene manifiestos YAML que definen workflows por data broker.

Cada manifest describe:
- ID único del broker
- Nombre y dominio
- Estado del workflow (draft/active/deprecated)
- Pasos BYOS (Bring Your Own Session) guiados:
  1. `locate_profile`: Encontrar perfil público
  2. `confirm_identity`: Confirmar identidad
  3. `opt_out_submit`: Enviar solicitud de opt-out
  4. `verify_absence`: Verificar ausencia y resurfacing

**Archivo principal**: `brokers_manifest.yaml`

Estos manifiestos son la base del sistema guiado de PGO, asegurando un proceso consistente por cada broker.

---

### `/sample_data`
**Propósito**: Datos de ejemplo para testing y desarrollo.

Esta carpeta puede contener:
- Datos sintéticos para pruebas
- Ejemplos de manifiestos
- Datos de prueba que no contienen información real

---

### `/.github`
**Propósito**: Configuración de GitHub Actions y workflows de CI/CD.

Contiene:
- Workflows automatizados
- Configuración de issues y PRs
- Scripts de automatización de GitHub

---

## Estructura de código fuente: `/src/pgo`

### `/src/pgo/core`
**Propósito**: Módulos centrales que implementan la lógica core del sistema.

#### `state.py`
Implementa la máquina de estados de hallazgos con transiciones válidas:
```
discovered → confirmed → submitted → pending → verified / resurfaced
```

Valida que no haya transiciones inválidas que comprometan la integridad del proceso de auditoría.

#### `models.py`
Define modelos de datos usando Pydantic:
- `FindingStatus`: Enum de estados posibles
- Validación de tipos en tiempo de ejecución
- Serialización consistente

#### `audit.py`
Sistema de auditoría append-only con cadena de hash:
- Cada evento tiene `entry_hash` y `prev_hash`
- Detección de manipulación del log
- Exportación con verificación de integridad
- Firma HMAC opcional

**Garantía principal**: Si alguien edita un evento en SQLite, la cadena se rompe y es detectable.

#### `db.py`
Gestión de conexión SQLite:
- Conexiones configuradas para integridad
- Foreign keys habilitadas
- Manejo de transacciones

#### `repository.py`
Capa de acceso a datos (patrón Repository):
- Abstrae queries SQL del resto del código
- Operaciones CRUD para hallazgos y eventos
- Mantiene separación de responsabilidades

#### `settings.py`
Configuración de la aplicación:
- Variables de entorno
- Rutas del sistema
- Parámetros configurables

#### `paths.py`
Gestión centralizada de rutas:
- Rutas a carpetas de datos
- Rutas al vault
- Rutas a exports
- Asegura consistencia en toda la app

#### `errors.py`
Excepciones personalizadas del dominio:
- `StateTransitionInvalid`: Transición de estado no permitida
- `AuditChainBroken`: Cadena de hash comprometida
- Otras excepciones específicas de PGO

#### `logging.py`
Configuración de logging:
- Niveles de log apropiados
- Formatos consistentes
- Protección contra fugas de PII en logs

---

### `/src/pgo/modules`
**Propósito**: Módulos especializados con responsabilidades específicas.

#### `vault.py`
**Bóveda de evidencia encriptada**

Maneja el ciclo de vida de evidencia:
1. Redacción de PII
2. Hash de integridad (SHA-256)
3. Encriptación (Fernet)
4. Almacenamiento con metadata

**Modelo de seguridad**:
- Clave solo en variable de entorno (nunca en disco)
- Encriptación at-rest con AES-128-CBC + HMAC
- Permisos restrictivos en archivos (0o600)

**No-objetivo**: El vault NO captura capturas de pantalla automáticamente. Los usuarios proveen evidencia (BYOS), y el vault la protege.

#### `pii_guard.py`
**Protección de PII - Boundary de Zero Trust**

Asegura que no haya fugas de PII en:
- Logs del sistema
- Exports de auditoría
- Entradas de eventos

**Estrategias**:
- Redacción basada en regex (emails, teléfonos, SSNs)
- Tokenización SHA-256 de identificadores
- Validación de exports para detectar PII sin proteger

**Boundary de confianza**: Todo texto libre pasa por aquí antes de tocar SQLite o exports.

---

### `/src/pgo/cli.py`
**Propósito**: Interfaz de línea de comandos (CLI) principal.

Implementa todos los comandos de PGO:
```bash
pgo scan         # Descubrir candidatos
pgo add-url      # Agregar URL manualmente
pgo confirm      # Confirmar hallazgo + capturar evidencia
pgo optout       # Workflow guiado de opt-out
pgo verify       # Re-chequeos programados
pgo status       # Estado por broker
pgo export       # Exportar log de auditoría
pgo wipe         # Limpiar datos locales
```

---

### `/src/pgo/manifest.py`
**Propósito**: Lectura y validación de manifiestos de brokers.

Funciones:
- Cargar `brokers_manifest.yaml`
- Validar estructura de manifiestos
- Proveer acceso a workflows de brokers
- Asegurar que los pasos estén bien definidos

---

## Archivos de configuración raíz

### `pyproject.toml`
**Propósito**: Configuración del proyecto Python moderna.

Contiene:
- Metadata del paquete (nombre, versión, descripción)
- Dependencias del proyecto
- Dependencias de desarrollo
- Configuración de herramientas (pytest, mypy, etc.)
- Punto de entrada CLI (`pgo`)

### `pytest.ini`
**Propósito**: Configuración de pytest.

Define:
- Paths de pruebas
- Opciones por defecto
- Marcadores de pruebas

### `.gitignore`
**Propósito**: Archivos y carpetas excluidos de Git.

Excluye:
- `/data/` - Base de datos local
- `/vault/` - Evidencia encriptada
- `/exports/` - Exportaciones de auditoría
- `/reports/` - Reportes generados
- `/sample_data/` - Datos de muestra (excepto .gitkeep)
- `.venv/` - Entorno virtual Python
- `__pycache__/` - Cache de Python
- `*.pyc` - Bytecode compilado

---

## Filosofía de diseño

### Local-first
Todos los datos sensibles permanecen en tu máquina. No hay backend en la nube (en v0.1).

### Zero Trust
- **PII Guard**: Nada de PII en claro en logs/exports
- **Vault**: Evidencia encriptada at-rest
- **Audit Chain**: Detección de manipulación

### BYOS (Bring Your Own Session)
PGO no hace scraping automático ni bypass de CAPTCHA. Tú realizas las acciones en los portales, y PGO estructura y audita tu trabajo.

### Append-only audit
La integridad del log es la garantía fundamental:
- Eventos inmutables
- Hash chain para detectar edits
- Exportación verificable

---

## Resumen de carpetas por función

| Carpeta | Propósito | En Git? |
|---------|-----------|---------|
| `/src` | Código fuente de PGO | ✅ Sí |
| `/tests` | Pruebas automatizadas | ✅ Sí |
| `/manifests` | Workflows de brokers (YAML) | ✅ Sí |
| `/data` | Base de datos SQLite local | ❌ No (.gitignore) |
| `/vault` | Evidencia encriptada | ❌ No (.gitignore) |
| `/exports` | Exportaciones de auditoría | ❌ No (.gitignore) |
| `/reports` | Reportes generados | ❌ No (.gitignore) |
| `/sample_data` | Datos de ejemplo/testing | ❌ No (.gitignore) |
| `/.github` | CI/CD workflows | ✅ Sí |

---

## Próximos pasos

Para trabajar con el proyecto:

1. **Instalar**: `pip install -e ".[dev]"`
2. **Probar**: `pytest tests/ -v`
3. **Explorar**: `pgo --help`
4. **Leer código**: Empieza por `src/pgo/core/models.py` y `src/pgo/core/state.py`

Para más información, consulta el [README.md](../README.md) principal.
