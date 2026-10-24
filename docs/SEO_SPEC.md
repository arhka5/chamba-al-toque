# Chamba al Toque: especificación SEO

Versión 1.0 (23-oct-2026). Alcance: sitio estático generado a diario (Python + Jinja2) y publicado en GitHub Pages. Este documento no contiene código del sitio; define reglas que el generador debe cumplir.

Leyenda de prioridad:
- **[P0]** imprescindible para el lanzamiento.
- **[P1]** primer mes después de lanzar.
- **[P2]** más adelante, cuando haya tracción.

Los datos de ejemplo (id 821548, cargo, entidad, ubicación, N.º de convocatoria, formación) son los reales que se tienen. Los sueldos y fechas de los ejemplos son inventados solo para ilustrar el formato.

---

## 0. Decisiones previas que condicionan todo

### 0.1 Dominio propio: comprarlo antes de lanzar [P0, recomendado fuerte]
Estar en `https://arhka5.github.io/chamba-al-toque/` trae tres problemas reales:

1. **`robots.txt` no funciona.** Google solo lee `robots.txt` en la raíz del host (`https://arhka5.github.io/robots.txt`). Un proyecto en subdirectorio no controla ese archivo. Consecuencia: todo el control de indexación tiene que hacerse con `<meta name="robots">`, no con `robots.txt`. (Alternativa débil: poner el archivo en el repo de usuario `arhka5.github.io`, si existe.)
2. **No hay redirecciones 301 ni código 410.** GitHub Pages solo sirve 200 y 404. Cualquier cambio de URL futuro se pierde.
3. **Autoridad compartida y prefijo en todas las URLs.** Un dominio propio (`chambaaltoque.pe` o `.com`) cuesta unos S/ 40 a 100 al año y evita migrar después con el sitio ya indexado.

Si se configura dominio propio en GitHub Pages, GitHub redirige las URLs antiguas de `github.io` al dominio nuevo (verificar en la documentación vigente de GitHub Pages al hacerlo). Aun así, es mejor empezar ya en el dominio final.

**Regla de implementación (sirve con o sin dominio):** una sola variable `BASE_URL` (por ejemplo `https://arhka5.github.io/chamba-al-toque`, sin barra final). Todas las URLs absolutas (canonical, sitemap, JSON-LD, Open Graph) se construyen con ella. Los enlaces internos son relativos a la raíz del sitio vía una variable `BASE_PATH` (`/chamba-al-toque` o vacío). Nunca escribir la URL a mano en una plantilla.

### 0.2 Hora de construcción [P0]
Construir y publicar **a las 00:30 hora de Lima** (05:30 UTC) con GitHub Actions. Razón: `validThrough` vence a las 23:59:59 del día de cierre; a esa hora las ofertas del día anterior ya salen del sitio. Otras notas de Actions:
- Los `schedule` de Actions pueden retrasarse decenas de minutos y se **desactivan solos tras 60 días sin actividad en el repo**. El script diario debe hacer un commit (por ejemplo del archivo de estado) o hay que reactivarlo a mano.
- Publicar con `actions/deploy-pages` (artefacto), no commiteando miles de HTML al repo: evita inflar el historial git.
- Segundo disparo opcional a las 13:00 Lima si SERVIR publica durante el día.

### 0.3 Archivo de estado persistente [P0]
El generador mantiene `state.json` (commiteado en una rama `data` o en el repo, no en `gh-pages`) con, por `id`: `slug` congelado, `first_seen`, `last_seen`, `content_hash`, `lastmod`, `closed_at`. Sirve para:
- **Congelar el slug** la primera vez que se ve la oferta. Si SERVIR corrige el cargo, la URL no cambia (no hay 301 en GitHub Pages).
- Calcular `lastmod` reales (ver 5.1).
- Saber hace cuántos días cerró una oferta (ver 1.4).

### 0.4 Año dinámico [P0]
Variable `ANIO` = año calendario de la fecha de construcción en zona `America/Lima`. Se usa en títulos y H1 de listados, nunca escrito a mano. Se renueva solo el 1 de enero. (Si a mediados de diciembre se prefiere adelantar al año siguiente, es un cambio de una línea; no hace falta al inicio.)

### 0.5 Idioma [P0]
`<html lang="es-PE">`. Solo hay una versión de idioma y país. **`hreflang` no aplica**: no hay versiones alternativas. No poner `hreflang` ni `x-default`. Confirmado.

---

## 1. Arquitectura de URLs y tipos de página

Todas las URLs terminan en `/` (carpeta con `index.html`; GitHub Pages redirige la versión sin barra con 301). Todo en minúsculas, sin tildes, sin `ñ`, sin parámetros de consulta.

### 1.1 Mapa de URLs

| Tipo | URL (tras `BASE_URL`) | Prioridad | ¿Se indexa? |
|---|---|---|---|
| Portada | `/` | P0 | Sí |
| Oferta | `/oferta/{slug}-{id}/` | P0 | Sí mientras esté vigente |
| Departamento | `/departamento/{slug}/` | P0 | Sí |
| Departamento, páginas 2+ | `/departamento/{slug}/pagina/{n}/` | P0 | Sí (ver 4.4) |
| Entidad | `/entidad/{slug}/` | P0 | Solo si cumple umbral (1.3) |
| Tema: CAS | `/convocatorias-cas/` | P0 | Sí |
| Tema: sin experiencia | `/sin-experiencia/` | P0 | Sí |
| Tema: solo secundaria | `/secundaria-completa/` | P0 | Sí |
| Tipo de entidad: municipalidades | `/municipalidades/` | P1 | Sí |
| Tipo de entidad: gobiernos regionales | `/gobiernos-regionales/` | P1 | Sí |
| Tema: técnico | `/tecnico/` | P1 | Sí |
| Tema: universitario | `/universitario/` | P1 | Sí |
| Departamento + tema | `/departamento/{slug}/sin-experiencia/` | P1 | Solo si cumple umbral |
| Prácticas | `/practicas/` | P2 (cuando haya fuente) | Sí |
| Nuevas de hoy | `/nuevas/` | P1 | No (`noindex,follow`): cambia a diario |
| Por vencer | `/por-vencer/` | P1 | No (`noindex,follow`) |
| Guías: qué es CAS, cómo postular, convocatorias falsas | `/guia/{slug}/` | P1 | Sí |
| Acerca de, Aviso legal, Privacidad, Contacto | `/acerca/`, `/aviso-legal/`, `/privacidad/`, `/contacto/` | P0 | Sí (Privacidad: `noindex` opcional) |
| 404 | `/404.html` | P0 | `noindex` |

Notas:
- Se descarta una página por provincia o distrito al lanzar: con ~3,800 ofertas repartidas en cientos de lugares, casi todas serían finas. El dato `"LIMA - PACHACAMAC"` se usa para `addressRegion` y `addressLocality` y para el texto, no para URLs. **[P2]** `/departamento/lima/provincia/{slug}/` solo para provincias con 15 o más ofertas vigentes.
- Para búsquedas tipo "trabajo en Arequipa" la página de departamento es la que compite; su texto menciona la capital cuando coincide (Arequipa, Cusco, Piura, Huancayo en Junín, etc.).
- Hay que **verificar el formato real de la columna ubicación**: el ejemplo `LIMA - PACHACAMAC` parece "DEPARTAMENTO - lugar" donde Pachacámac es un distrito. Si el segundo término es a veces provincia y a veces distrito, tratarlo como "localidad" sin etiquetarlo.
- Callao se trata como departamento propio. Si aparece "EXTRANJERO" o similar, URL `/departamento/extranjero/` con `noindex` si tiene menos de 10 ofertas.

### 1.2 Slugs [P0]
Función `slugify(texto)`:
1. Normalizar NFKD y quitar marcas diacríticas (`á`→`a`, `ñ`→`n`).
2. Minúsculas.
3. Todo carácter fuera de `[a-z0-9]` pasa a `-`; colapsar guiones repetidos; recortar guiones en los extremos.
4. Quitar palabras vacías solo al medio de slugs largos (`de`, `del`, `la`, `el`, `los`, `las`, `y`, `en`) **únicamente** si hace falta para entrar en el límite. Preferir truncar en límite de palabra.

Reglas por tipo:
- **Oferta:** `{cargo-slug}-{entidad-corta-slug}-{id}`. Cargo: máximo 6 palabras. Entidad corta: abreviar prefijos (`municipalidad-distrital-de` → `muni-distrital`; `municipalidad-provincial-de` → `muni-provincial`; `gobierno-regional-de` → `gore`; `unidad-de-gestion-educativa-local` → `ugel`). Largo total del slug sin el id: 70 caracteres máximo. El **id va siempre al final** y es lo único que identifica la oferta. Ejemplo: `/oferta/operario-de-limpieza-interna-muni-distrital-pachacamac-821548/`.
- **Departamento:** `lima`, `la-libertad`, `san-martin`, `ancash`, `apurimac`, `huanuco`, `junin`, `madre-de-dios`.
- **Entidad:** slug completo del nombre normalizado, sin abreviar (`municipalidad-distrital-de-pachacamac`). Si dos entidades distintas colisionan, sufijo `-2` (revisar manualmente la primera vez). Slug congelado en `state.json`.
- **Estabilidad:** el slug se calcula una sola vez y se guarda. Si el cargo cambia después, la URL no cambia y el contenido sí.

### 1.3 Criterios contra páginas finas [P0]
Umbrales (variables de configuración, no constantes en el código):

| Página | Condición para `index,follow` | Si no la cumple |
|---|---|---|
| Entidad | 3 o más ofertas vigentes | Se genera igual, con `noindex,follow`, y fuera del sitemap |
| Departamento | Siempre (son 25 y siempre tendrán contenido) | n/a; si un departamento tuviera 0 vigentes, `noindex` |
| Departamento + tema | 10 o más ofertas | No se genera la página (ni se enlaza) |
| Tema nacional | 20 o más ofertas | `noindex` |
| Página 2+ de listado | Tiene al menos 1 oferta | No se genera |

Razonamiento sobre entidades con 1 o 2 ofertas: la búsqueda "convocatorias municipalidad distrital de X 2026" también la atiende la **página de la oferta**, porque su título y H1 llevan el nombre de la entidad. Una página de entidad con 1 oferta sería un duplicado de esa oferta. Por eso: se genera para navegación (el enlace de la oferta a "otras convocatorias de la entidad" sigue funcionando), pero no se indexa. Si una entidad sube a 3 o más, pasa a indexable al día siguiente. Para evitar que entre y salga del índice cada semana, se aplica histéresis: pasa a indexable con 3 o más y vuelve a `noindex` solo si baja a 0 durante 30 días seguidos.

Con ~1,000+ entidades se esperan unas 150 a 300 indexables. Es un número manejable.

Texto único mínimo para páginas de listado indexables: un bloque de 2 a 3 frases **generado desde datos** (conteo, rango de sueldos, entidades con más plazas, cuántas piden secundaria o menos). No repetir el mismo párrafo en 25 regiones cambiando solo el nombre.

### 1.4 Ofertas vencidas o retiradas [P0]
Google exige que no queden accesibles ofertas vencidas con marcado `JobPosting` vigente, y avisa que la demora puede acabar en acción manual. GitHub Pages no sirve 410 ni 301. Política:

1. **Una oferta cuenta como cerrada** cuando `ahora_Lima > fecha_fin 23:59:59` **o** cuando ya no aparece en la descarga diaria de SERVIR (retirada).
2. **Mismo día del cierre (siguiente build):** la página se regenera como "cerrada":
   - se **quita todo el JSON-LD `JobPosting`**,
   - `<meta name="robots" content="noindex,follow">`,
   - se saca de todos los listados y del sitemap,
   - el cuerpo muestra un aviso: "Esta convocatoria cerró el 30 de octubre de 2026" y debajo 6 ofertas parecidas vigentes, más enlace al departamento y a la entidad.
3. **A los 30 días del cierre:** la página se elimina del build (pasa a 404 con `404.html` útil).
4. Si una oferta retirada reaparece, vuelve a renderse como vigente.
5. **Indexing API [P1/P2]** acelera la salida del índice (ver 5.5).

Por qué no un 404 inmediato: se conserva el enlace para quien llega desde un buscador o WhatsApp con un enlace guardado, y para dar tiempo a que Google reprocese. Por qué no mantenerla más de 30 días: acumula miles de páginas muertas.

Salvaguarda de build: si la descarga de SERVIR falla o trae menos del 50% de las ofertas del día anterior, **no publicar** (el workflow termina en error y se conserva el sitio anterior). Si no, un fallo de scraping cerraría miles de ofertas de golpe.

### 1.5 Ofertas duplicadas o casi duplicadas [P0]
Es común que una entidad publique 10 plazas del mismo cargo con distinto N.º de convocatoria. Cada `id` conserva su página. Para distinguirlas:
- Si dentro de la misma entidad hay más de una oferta vigente con el mismo cargo, el título y H1 agregan el número corto de la convocatoria: "Operario de Limpieza Interna en Municipalidad Distrital de Pachacámac (CAS 033)". Extraer el último grupo de dígitos de `D.LEG 1057 - INDETERMINADO-033`.
- Cada una enlaza a las otras ("Otras 3 plazas de Operario de Limpieza Interna en esta entidad").
- Canonical siempre autorreferenciado; no se consolidan.

---

## 2. Plantillas de `<title>`, meta description y H1

Reglas generales:
- Título: objetivo de 60 caracteres, máximo 70. Google reescribe títulos con frecuencia; lo importante es que la palabra clave y la entidad estén al inicio.
- Marca `| Chamba al Toque` solo si el total no pasa de 65 caracteres; si pasa, se omite. En la portada la marca va siempre.
- Meta description: 120 a 155 caracteres. Texto único por página, construido con datos.
- Un solo H1 por página, distinto del title pero con las mismas palabras clave.
- `{ANIO}` = variable de la sección 0.4.
- Formato de números: `S/ 1,500` (coma de millares como en Perú); sin decimales si son `.00`.
- Fechas en texto: `30 de octubre de 2026`. En atributos `datetime`: ISO.
- Nada de guiones largos, ni signos de exclamación, ni emojis en title/description.

### 2.1 Portada
- **Title:** `Convocatorias CAS y trabajos en el Estado {ANIO} | Chamba al Toque`
  - Ejemplo: `Convocatorias CAS y trabajos en el Estado 2026 | Chamba al Toque`
- **Description:** `{N} convocatorias de trabajo vigentes en entidades públicas del Perú, con sueldo, requisitos y fecha límite. Datos de Talento Perú (SERVIR), actualizados {fecha_corta}.`
  - Ejemplo: `3,812 convocatorias de trabajo vigentes en entidades públicas del Perú, con sueldo, requisitos y fecha límite. Datos de Talento Perú (SERVIR), actualizados el 23 de octubre.`
- **H1:** `Convocatorias de trabajo en el Estado peruano`

### 2.2 Oferta
- **Title:** `{Cargo} en {Entidad}` + (` ({CAS nnn})` si hay duplicados) + (` {ANIO}` si cabe) + (` | Chamba al Toque` si cabe)
  - Ejemplo: `Operario de Limpieza Interna en Municipalidad Distrital de Pachacámac` (69 caracteres: sin año ni marca)
  - Ejemplo corto: `Auxiliar Administrativo en UGEL Ica 2026 | Chamba al Toque`
  - Orden de recorte: primero marca, luego año, luego abreviar el prefijo de la entidad (`Municipalidad Distrital de` → `Muni. Distrital de`), y si aún no cabe se deja el título largo sin recortar (un título largo no penaliza; uno cortado a mitad de palabra se ve mal).
  - **No** poner sueldo, N.º de convocatoria ni id en el title (además Google pide que el `title` del JobPosting sea solo el cargo).
- **Description:** `{Régimen} para {Cargo} en {EntidadConArticulo} ({Localidad}, {Departamento}). {Vacantes} vacante(s), S/ {sueldo} al mes. Postula hasta el {fecha_fin}. Requisitos: {formacion}, {experiencia_resumen}.`
  - Ejemplo: `Convocatoria CAS para Operario de Limpieza Interna en la Municipalidad Distrital de Pachacámac (Lima). 1 vacante, S/ 1,500 al mes. Postula hasta el 30 de octubre de 2026. Requisitos: secundaria completa, sin experiencia.`
  - Truncar a 155 caracteres cortando en palabra, sin puntos suspensivos si el corte cae en límite de oración. Prioridad de contenido si hay que cortar: sueldo y fecha se conservan, requisitos se recortan primero.
  - Régimen: `D.LEG 1057` → "Convocatoria CAS"; otros regímenes según tabla (ver 6.4).
  - Si no hay sueldo (0 o vacío): omitir la frase de sueldo, no escribir "S/ 0".
- **H1:** `{Cargo} en {Entidad}` (+ ` (CAS 033)` si hay duplicados). Mismo texto que el title sin marca ni año.

### 2.3 Departamento
- **Title:** `Trabajos en {Departamento} {ANIO}: convocatorias del Estado | Chamba al Toque` → si no cabe, `Trabajos en {Departamento} {ANIO}: convocatorias CAS y del Estado`
  - Ejemplo: `Trabajos en Arequipa 2026: convocatorias CAS y del Estado`
  - Páginas 2+: agregar ` (página {n})` al final del title.
- **Description:** `{N} convocatorias vigentes en {Departamento}: sueldos desde S/ {min} hasta S/ {max} al mes, {M} sin experiencia. Municipalidades, hospitales, UGEL y más. Actualizado el {fecha}.`
- **H1:** `Trabajos en el Estado en {Departamento} {ANIO}` (páginas 2+: se mantiene igual y se agrega `<span>(página 2)</span>`).

### 2.4 Entidad (indexable)
- **Title:** `Convocatorias {Entidad} {ANIO}: {N} plazas vigentes`
  - Ejemplo: `Convocatorias Municipalidad Distrital de Pachacámac 2026: 5 plazas`
  - Si se pasa de 70, usar `Convocatorias {EntidadAbreviada} {ANIO}`.
- **Description:** `{N} convocatorias vigentes en {Entidad} ({Departamento}): {cargos_ejemplo_3}. Sueldos desde S/ {min}. Cierran desde el {primera_fecha_cierre}.`
- **H1:** `Convocatorias de {Entidad} {ANIO}`

### 2.5 Temáticas
| Página | Title | H1 |
|---|---|---|
| `/convocatorias-cas/` | `Convocatorias CAS {ANIO}: ofertas vigentes en el Estado` | `Convocatorias CAS {ANIO}` |
| `/sin-experiencia/` | `Trabajos en el Estado sin experiencia {ANIO}` | `Trabajos sin experiencia en entidades públicas {ANIO}` |
| `/secundaria-completa/` | `Trabajos en el Estado con secundaria completa {ANIO}` | `Convocatorias que piden solo secundaria completa {ANIO}` |
| `/departamento/{d}/sin-experiencia/` | `Trabajo en {Departamento} sin experiencia {ANIO}: Estado` | `Trabajos sin experiencia en {Departamento} {ANIO}` |
| `/municipalidades/` | `Convocatorias de municipalidades {ANIO}: CAS y más` | `Convocatorias de municipalidades {ANIO}` |

Description de temáticas: misma estructura que departamento (conteo, rango de sueldos, entidades principales).

Cuidado con "CAS": en `/convocatorias-cas/` entran solo ofertas con régimen D.LEG 1057. Si el 99% de la base es CAS, esta página y la portada serán casi idénticas. En ese caso: **la portada compite por "trabajos en el Estado"/"chamba en el estado" y `/convocatorias-cas/` por "convocatorias CAS"**, con H1, orden y texto introductorio distintos, y la portada limitada a "lo más reciente" (24 ofertas) en lugar de listar todo. Revisar al ver los datos reales.

---

## 3. JSON-LD

Un único bloque `<script type="application/ld+json">` por tipo, en el `<head>` o al final del `<body>`. Generar con `json.dumps(..., ensure_ascii=False)` y escapar `</` como `<\/` para que el HTML no se rompa. Validar en build contra reglas propias (3.5).

### 3.1 `JobPosting` (solo páginas de oferta vigente) [P0]

**Mapeo campo a campo**

| Propiedad | Estado Google | Fuente / valor | Notas |
|---|---|---|---|
| `@type` | n/a | `"JobPosting"` | |
| `title` | **Obligatorio** | Cargo en formato legible (6.5) | Solo el cargo: sin código, fecha, sueldo ni entidad |
| `description` | **Obligatorio** | HTML construido (3.2) | No puede ser igual al title |
| `datePosted` | **Obligatorio** | `fecha_inicio` en ISO 8601: `"2026-10-20"` | Si `fecha_inicio` es futura al build, igual se publica con esa fecha |
| `validThrough` | Recomendado (tratarlo como obligatorio) | `fecha_fin` → `"2026-10-30T23:59:59-05:00"` | Perú no tiene horario de verano; offset siempre `-05:00` |
| `hiringOrganization` | **Obligatorio** | `{"@type":"Organization","name":"Municipalidad Distrital de Pachacámac"}` | Nombre real de la entidad, no "SERVIR". Sin `logo` (no se tiene). Sin `sameAs` salvo que se conozca el sitio oficial |
| `jobLocation` | **Obligatorio** (no es remoto) | `{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Pachacámac","addressRegion":"Lima","addressCountry":"PE"}}` | `addressCountry` es obligatorio dentro de la dirección. Si la localidad no se puede separar, omitir `addressLocality` y dejar region + país |
| `baseSalary` | Recomendado | `{"@type":"MonetaryAmount","currency":"PEN","value":{"@type":"QuantitativeValue","value":1500,"unitText":"MONTH"}}` | `value` numérico, no texto. `unitText` en mayúsculas. Solo si el sueldo es mayor que 0 y es el que publica la entidad. Si hay rango, `minValue` y `maxValue` en vez de `value` |
| `employmentType` | Recomendado | `["FULL_TIME"]` por defecto para CAS | Tabla de régimen en 6.4. No inventar `PART_TIME` sin dato. No usar `CONTRACTOR` para CAS (es relación laboral dependiente) |
| `identifier` | Recomendado | `{"@type":"PropertyValue","name":"Talento Perú (SERVIR)","value":"821548"}` | Id oficial de SERVIR. Es el id del portal oficial, el más cercano al "id del empleador" que tenemos |
| `directApply` | Recomendado | `false` | Correcto: la postulación se hace en la web de la entidad, no en nuestra página |
| `totalJobOpenings` | Opcional (schema.org, Google no lo usa hoy) | `vacantes` como entero | Inofensivo; incluir |
| `educationRequirements` | Beta | `{"@type":"EducationalOccupationalCredential","credentialCategory":"high school"}` | **[P1]** Solo si el texto mapea sin ambigüedad (secundaria completa → `high school`; técnica → `associate degree`; universitaria/bachiller → `bachelor degree`). Si no mapea, omitir |
| `experienceRequirements` | Beta | `{"@type":"OccupationalExperienceRequirements","monthsOfExperience":0}` | **[P1]** Solo cuando `NO APLICA` (0). Si el texto dice "6 meses" o "1 año" y se puede parsear con seguridad, usar el número; si no, omitir |
| `url` | Opcional | URL canónica de la oferta | |
| `jobLocationType`, `applicantLocationRequirements` | No aplica | **No incluir**: no hay ofertas remotas en los campos que tenemos | Si algún día una oferta dice "remoto", hay que revisarla caso a caso |

**Ejemplo ilustrativo (sueldo y fechas inventados)**

```json
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Operario de Limpieza Interna",
  "description": "<p>La Municipalidad Distrital de Pachacámac convoca 1 plaza de <strong>Operario de Limpieza Interna</strong> bajo el régimen CAS (D.Leg. 1057).</p><ul><li>Lugar de trabajo: Pachacámac, Lima, Perú.</li><li>Remuneración mensual: S/ 1,500.</li><li>Formación académica: secundaria completa.</li><li>Experiencia: no aplica.</li></ul><p>Las funciones, el cronograma y el formulario de postulación están en las bases de la convocatoria que publica la entidad. Convocatoria registrada en Talento Perú (SERVIR) con el N.° 821548.</p>",
  "datePosted": "2026-10-20",
  "validThrough": "2026-10-30T23:59:59-05:00",
  "employmentType": ["FULL_TIME"],
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Municipalidad Distrital de Pachacámac"
  },
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Pachacámac",
      "addressRegion": "Lima",
      "addressCountry": "PE"
    }
  },
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "PEN",
    "value": { "@type": "QuantitativeValue", "value": 1500, "unitText": "MONTH" }
  },
  "identifier": {
    "@type": "PropertyValue",
    "name": "Talento Perú (SERVIR)",
    "value": "821548"
  },
  "directApply": false,
  "totalJobOpenings": 1
}
```

### 3.2 Construcción de `description` (HTML honesto) [P0]
No tenemos descripción de funciones. Reglas:
- Armar HTML solo con campos reales: entidad, cargo, régimen, vacantes, lugar, remuneración, formación, experiencia, especialización, conocimientos, competencias. Omitir cualquier línea cuyo campo esté vacío.
- Etiquetas HTML permitidas por Google: `<p>`, `<br>`, `<ul>`, `<li>`, `<strong>`, `<em>`, `<h1>` a `<h5>`. Usar solo `<p>`, `<ul>`, `<li>`, `<strong>`.
- **Nunca inventar funciones.** Frase fija al final: "Las funciones, el cronograma y el formulario de postulación están en las bases publicadas por la entidad." No decir "se encargará de..." ni rellenar con tareas genéricas del puesto.
- El contenido de `description` debe coincidir con lo visible en la página (Google lo exige). Por eso la página muestra exactamente esos datos, además de contenido extra (similares, entidad, etc.).
- Longitud típica 400 a 900 caracteres. Es una descripción corta; es la limitación honesta de la fuente. Riesgo: Google puede considerar poco rico el marcado y mostrar menos la oferta en el panel de empleos. Mitigación futura [P2]: si la web de la entidad tiene un PDF de bases con funciones, extraerlas (con enlace) en vez de inventarlas.

### 3.3 Riesgos con la política de Google (leer antes de lanzar)
1. **El marcado va solo en la página de cada oferta**, nunca en listados, entidad, departamento ni portada.
2. **Todo lo del JSON-LD debe verse en la página** (sueldo, fecha límite, ubicación). Un sueldo solo en el marcado es violación.
3. **Debe haber forma de postular.** Sin un enlace claro a la convocatoria oficial, Google puede rechazar la oferta. Botón "Ver convocatoria y postular" visible arriba, sin requerir login ni registro en nuestro sitio.
4. **Ofertas vencidas con marcado** = causa de acción manual. Aplicar 1.4 sin excepciones.
5. **Somos agregador, no el empleador.** Google permite agregadores, pero exige que la oferta sea real y que la página sea la oferta, no un anuncio ni una página que "pide datos". Evitar cualquier pago, formulario de captación, publicidad que simule ser una oferta, o textos como "garantizamos tu ingreso".
6. **Sueldo:** `baseSalary` debe ser el que publica el empleador. No estimar, no promediar. Si el dato viene en 0 o con texto "A TRATAR", omitir.
7. **Título:** sin "URGENTE", "SE BUSCA", códigos ni sueldo.
8. **Ofertas duplicadas entre sitios** no son problema para Google for Jobs, pero sí lo es publicar la misma oferta con ids distintos varias veces en nuestro sitio. Deduplicar por `id`.
9. **Datos incorrectos en el origen:** si la fecha fin viene antes que la fecha inicio o está vacía, no emitir `validThrough` (Google permite omitirlo si se desconoce) y no emitir la oferta si `datePosted` es inválida. Mejor sin marcado que con marcado falso.

### 3.4 `BreadcrumbList` [P0]
En ofertas, entidades, departamentos y temas. Jerarquía:
- Oferta: `Inicio > {Departamento} > {Entidad (si indexable) o saltar} > {Cargo}`. Si la entidad no es indexable, se omite ese nivel del marcado **y** del breadcrumb visible, para que el marcado coincida con lo visible.
- Departamento: `Inicio > {Departamento}`.
- Entidad: `Inicio > {Departamento principal de la entidad} > {Entidad}`.
- Temas: `Inicio > {Tema}`.
- El último ítem lleva `name` y puede omitir `item`.

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type":"ListItem","position":1,"name":"Inicio","item":"{BASE_URL}/"},
    {"@type":"ListItem","position":2,"name":"Lima","item":"{BASE_URL}/departamento/lima/"},
    {"@type":"ListItem","position":3,"name":"Operario de Limpieza Interna"}
  ]
}
```

### 3.5 `WebSite` y `Organization` (solo portada) [P0]
```json
[
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Chamba al Toque",
    "url": "{BASE_URL}/",
    "inLanguage": "es-PE"
  },
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Chamba al Toque",
    "url": "{BASE_URL}/",
    "logo": "{BASE_URL}/img/logo-512.png",
    "email": "contacto@..."
  }
]
```
- **`SearchAction`: no incluir.** Google retiró el cuadro de búsqueda de sitelinks en noviembre de 2024, así que el marcado ya no produce nada, y un sitio estático no tiene endpoint de búsqueda con parámetro.
- `Organization`: `logo` debe ser un PNG o SVG rasterizable de al menos 112x112 px. `sameAs` con perfiles sociales cuando existan.
- Búsqueda interna: **[P1]** agregar Pagefind u otro índice estático como mejora progresiva (sin JS, el usuario navega por departamentos y temas).

### 3.6 Validaciones automáticas en build [P0]
El generador debe abortar (o al menos excluir la oferta del marcado y registrar el error) si:
- `title` vacío o igual a `description`;
- `validThrough` anterior al instante del build;
- `datePosted` posterior a `validThrough`;
- `baseSalary.value` no numérico o menor o igual a 0;
- falta `hiringOrganization.name` o `addressCountry`;
- aparece JSON-LD `JobPosting` en cualquier página que no sea de oferta vigente (test sobre todo el `_site`).

Además, antes de lanzar y tras cada cambio de plantilla: probar 5 URLs distintas en la Prueba de resultados enriquecidos de Google y revisar el informe "Ofertas de empleo" de Search Console.

---

## 4. Enlazado interno

### 4.1 Estructura general [P0]
- Todo HTML con enlaces `<a href>` reales (sin enlaces generados por JS).
- Ninguna página indexable a más de 3 clics de la portada, excepto páginas profundas de paginación (que además están en el sitemap indirectamente por las ofertas).
- Encabezado: logo, "Departamentos", "Temas" (menú `<details>` o enlaces simples, sin JS obligatorio). Pie: Acerca, Aviso legal, Privacidad, Contacto, guías, fuente (Talento Perú).
- Bloque "Trabajos por departamento" (los 25) en el pie de la portada y de cada oferta: enlaces sitewide que distribuyen autoridad.

### 4.2 Portada
- Últimas 24 ofertas publicadas (con enlace a `/nuevas/`).
- Cuadrícula de 25 departamentos con conteo `Lima (812)`.
- Accesos a temas: CAS, sin experiencia, secundaria completa, municipalidades.
- Top 12 entidades con más plazas vigentes (solo entidades indexables).

### 4.3 Página de oferta
Orden en pantalla (móvil primero):
1. Breadcrumb.
2. H1, entidad, ubicación, sueldo, vacantes, **fecha límite** destacada (texto, no solo color).
3. Botón "Ver convocatoria y postular" (enlaza al `detalle` de la entidad; `rel="noopener"`; abrir en la misma pestaña o nueva según preferencia, con aviso "Sale a la web de la entidad").
4. "Requisitos en palabras simples": formación, experiencia, especialización, conocimientos, competencias.
5. "Cómo postular": 3 pasos cortos y genéricos, con enlace a la guía.
6. Aviso de confianza breve (ver sección 8).
7. "Más trabajos": 
   - `Más trabajos en {Departamento} {ANIO}` → departamento (obligatorio, texto de enlace descriptivo).
   - `Otras convocatorias de {Entidad}` → entidad (si es indexable) y lista de hasta 5 de la misma entidad.
   - Hasta 6 ofertas **similares**: misma entidad primero, luego mismo cargo (primeros 2 tokens normalizados) en el mismo departamento, luego mismo cargo en otros departamentos. Orden determinista para que el HTML no cambie sin motivo.
   - Enlaces a temas aplicables ("Trabajos sin experiencia").

Reglas: no enlazar más de 20 ofertas por página; texto de enlace descriptivo ("Auxiliar Administrativo en UGEL Ica"), nunca "clic aquí".

### 4.4 Listados y paginación [P0]
- **25 ofertas por página** en departamentos, entidades y temas (cabe en poco peso y se lee bien en móvil).
- URL de página 2+: `/{ruta}/pagina/{n}/`. La página 1 es la ruta sin `/pagina/1/` (esa URL no existe, no redirigir).
- **Canonical autorreferenciado** en cada página (la 2 canoniza a la 2, no a la 1). `rel="prev"/"next"` ya no los usa Google; se pueden omitir. Enlaces visibles "Anterior / Siguiente" y numeración compacta `1 … 4 5 6 … 32` con `aria-label` y `aria-current="page"`.
- Páginas 2+: `index,follow`, title con ` (página n)`, mismo H1. Sin bloque de texto introductorio repetido (solo en la página 1).
- Orden: más recientes primero (por `datePosted` y desempate por `id` descendente). El contenido de cada página rota a medida que hay ofertas nuevas; es aceptable porque las ofertas individuales están en el sitemap y tienen otras rutas.
- Páginas de entidad no indexables pueden mostrar todas sus ofertas en una sola página si son pocas (menos de 25, siempre).

### 4.5 Breadcrumbs visibles [P0]
`<nav aria-label="Migas de pan"><ol>...</ol></nav>` con los mismos niveles que el JSON-LD (3.4).

---

## 5. Aspectos técnicos

### 5.1 Sitemaps [P0]
Estructura:
```
{BASE_URL}/sitemap.xml                 (índice)
{BASE_URL}/sitemap-ofertas-1.xml       (hasta 2,000 URLs por archivo; se parte en -2, -3...)
{BASE_URL}/sitemap-listados.xml        (portada, departamentos, temas, entidades indexables)
{BASE_URL}/sitemap-info.xml            (guías y páginas legales)
```
- Todas las URLs absolutas con `BASE_URL`. Un sitemap dentro de `/chamba-al-toque/` solo puede listar URLs bajo ese prefijo, lo que se cumple.
- **Solo URLs `200`, canónicas e indexables.** Nunca ofertas cerradas, `noindex` ni páginas 2+ (llegan por enlaces).
- **`<lastmod>` solo cuando el contenido cambió de verdad**, tomado de `state.json` (cambia cuando cambia el `content_hash` de la oferta o, en listados, cuando cambia el conjunto de ofertas). Poner la fecha del build en todo es el error clásico: Google deja de confiar en `lastmod`. Formato `YYYY-MM-DD` o con hora y zona. Ignorar `priority` y `changefreq` (Google los ignora).
- Listados como departamentos cambian a diario por definición; su `lastmod` es la fecha del último cambio de contenido (alta/baja de ofertas).
- **Referencia en `robots.txt`:** inútil en subdirectorio de `github.io` (ver 0.1). Por eso **hay que enviar el sitemap manualmente en Search Console y Bing**. Con dominio propio, `robots.txt` en la raíz con `Sitemap: https://.../sitemap.xml`.

### 5.2 `robots.txt` [P0 si hay dominio propio]
Con dominio propio:
```
User-agent: *
Allow: /

Sitemap: https://DOMINIO/sitemap.xml
```
No bloquear CSS ni JS. No usar `Disallow` para controlar indexación (Google no puede ver el `noindex` de una página bloqueada). Sin dominio propio, no se publica este archivo en el proyecto (no tendría efecto).

### 5.3 Canonical, robots meta y cabecera [P0]
Cada página:
```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>…</title>
<meta name="description" content="…">
<link rel="canonical" href="{BASE_URL}/ruta/">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">  (o noindex,follow)
```
- Canonical absoluto, mismo protocolo y host, con barra final, sin parámetros.
- `noindex,follow` en: entidades bajo umbral, ofertas cerradas, `/nuevas/`, `/por-vencer/`, 404.
- Si algún día se agregan parámetros (`?utm_...` en difusión), el canonical limpio ya los neutraliza.

### 5.4 Open Graph y Twitter [P0 básico, P1 imágenes por tipo]
Todas las páginas indexables:
```html
<meta property="og:locale" content="es_PE">
<meta property="og:site_name" content="Chamba al Toque">
<meta property="og:type" content="website">          <!-- article no aplica -->
<meta property="og:title" content="…">               <!-- igual al H1 -->
<meta property="og:description" content="…">         <!-- igual a la meta description -->
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{BASE_URL}/img/og/{tipo}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
```
- **[P0]** Una imagen OG genérica de marca para todo.
- **[P1]** Una imagen por departamento (25 PNG) y una para ofertas con plantilla (se puede generar con Pillow en el build: cargo, entidad, sueldo, fecha límite sobre un fondo). Esto mejora el clic cuando se comparte por WhatsApp y Facebook, que es el canal principal de este público. Pesos máximos 150 KB por imagen. Cachear: solo regenerar si cambian los datos.

### 5.5 Avisar a Google de los cambios diarios
1. **Sitemap + `lastmod` honesto** [P0]. Es la base. Google lo rastrea con frecuencia en sitios con cambios diarios, pero no garantiza velocidad.
2. **Indexing API** [P1, evaluar tras 2 a 3 semanas]. Es el mecanismo previsto por Google para sitios de empleo (se permite solo para páginas `JobPosting` y transmisiones en vivo). Permite avisar `URL_UPDATED` al publicar y `URL_DELETED` al cerrar.
   - **Requisitos:** proyecto en Google Cloud con la Indexing API habilitada; una cuenta de servicio con su clave JSON (guardada como secreto de GitHub Actions); esa cuenta agregada como **propietario** de la propiedad en Search Console; la propiedad debe estar verificada (de prefijo de URL funciona); marcado `JobPosting` válido.
   - **Cuota:** 200 notificaciones de publicación por día por defecto (se puede pedir más). Con ~3,800 ofertas vivas y rotación de entre 150 y 300 ofertas nuevas por día, la cuota por defecto alcanza justo; priorizar `URL_UPDATED` de ofertas nuevas y `URL_DELETED` de las cerradas con marcado indexado, y pedir ampliación si hace falta.
   - **Cuándo conviene:** si pasadas 2 a 3 semanas las ofertas nuevas tardan más de 2 a 3 días en aparecer o las cerradas siguen visibles en Google for Jobs. Sin eso, el esfuerzo extra no se justifica.
   - **No usar la API para páginas que no sean ofertas** (política de Google).
   - Paso de build separado, tolerante a fallos: si falla, no impide la publicación del sitio.
3. **IndexNow (Bing/Yandex)** [P2]. Muy barato, envío por lote de URLs. Google no lo usa.
4. **Search Console:** "Inspeccionar URL → Solicitar indexación" a mano solo para 2 a 3 URLs de prueba al lanzar, no como flujo.

### 5.6 Rendimiento y Core Web Vitals en celulares baratos [P0]
Objetivo: LCP menor de 2.5 s en 4G lento y Android de gama baja; CLS menor de 0.1; INP bajo sin JS pesado.

Presupuestos (peso transferido con gzip/brotli):
| Tipo | HTML | Total página |
|---|---|---|
| Oferta | 12 KB | 25 KB |
| Listado (25 tarjetas) | 35 KB | 50 KB |
| Portada | 40 KB | 60 KB |

Reglas:
- **Sin JavaScript obligatorio.** Toda oferta, listado y enlace funciona con JS desactivado. (Esto además es una ventaja frente a El Paisano, cuya lista carga con JS y muestra "Cargando convocatorias...", lo que obliga al buscador a renderizar para ver el contenido.)
- CSS **en línea** (máximo 12 KB minificado) en `<style>`; cero solicitudes de CSS bloqueantes. Una sola hoja compartida.
- Sin fuentes web: pila del sistema (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`).
- Sin imágenes en el cuerpo, salvo el logo SVG en línea. Si luego se agregan imágenes: `width`/`height` explícitos y `loading="lazy"` salvo la primera.
- Analítica (cuando se agregue): script ligero con `defer`, de menos de 5 KB (GoatCounter, Plausible o Cloudflare Web Analytics). Evitar Google Tag Manager y sus cadenas de scripts.
- Anuncios (futuro): reservar espacio fijo con `min-height` para no romper CLS; no agregar al lanzamiento.
- GitHub Pages sirve con `Cache-Control: max-age=600` y gzip; no se pueden cambiar cabeceras. Un dominio propio detrás de Cloudflare (plan gratuito) permitiría controlar caché y brotli [P2].
- Presupuesto de build: se calculan ~6,000 archivos diarios (3,800 ofertas, ~1,000 entidades, listados, paginación), muy por debajo del límite de 1 GB del sitio de GitHub Pages. Revisar el peso total del artefacto (meta: menos de 150 MB).
- Test de aceptación: PageSpeed Insights en móvil sobre portada, un departamento y una oferta; todos en verde (90 o más en Rendimiento) antes del lanzamiento.

### 5.7 Accesibilidad mínima [P0]
- `lang="es-PE"`, un `<h1>` por página, jerarquía de encabezados sin saltos.
- Landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`; enlace "Saltar al contenido" al inicio.
- Contraste AA (4.5:1 texto normal); no depender solo del color para "por vencer" (texto "Cierra mañana" / "Cierra en 2 días").
- Áreas táctiles de al menos 44x44 px para botones y paginación.
- Foco visible; enlaces con texto descriptivo; `aria-current` en la paginación y migas.
- Fechas con `<time datetime="2026-10-30">30 de octubre de 2026</time>`.
- Tamaño base de texto 16 px o más; interlineado de 1.5.

### 5.8 Otras reglas técnicas [P0]
- Una sola versión del host y de la barra final.
- `404.html` útil: buscador de departamentos, enlaces a portada y a temas, `noindex`.
- Enlace externo a la entidad: `rel="noopener"`; sin `nofollow` por defecto (las fuentes son oficiales y la señal es de confianza). Revisar tasa de enlaces rotos mensualmente [P1].
- Favicon, `manifest` mínimo y `theme-color` [P1].
- Fecha de actualización visible en portada y listados (`Actualizado el 23 de octubre de 2026, 00:30`).

---

## 6. Contenido y tono

### 6.1 Principios
- Español peruano de uso corriente. Se puede usar "chamba", "postular", "plaza", "sueldo" y "convocatoria"; sin jerga que excluya (evitar "currar").
- Frases cortas, datos concretos, segunda persona informal-neutra ("Postula hasta…", "Revisa las bases").
- **Prohibido:** "descubre", "sumérgete", "en un solo lugar", "experiencia única", "no te pierdas", "el mejor portal", signos de exclamación decorativos, emojis decorativos, guiones largos (—), "revolucionario", "potencia tu carrera". Tampoco superlativos que no se puedan sostener.
- Cada afirmación debe poder sostenerse con los datos ("3,812 convocatorias" sí; "las mejores ofertas" no).
- Mensaje de honestidad cuando falte un dato: "No indicado en la convocatoria" en vez de dejar en blanco o inventar.

### 6.2 Texto de portada (bajo el H1, 3 frases)
> Aquí encuentras las convocatorias de trabajo de municipalidades, gobiernos regionales, ministerios, hospitales y otras entidades públicas del Perú. Los datos vienen de Talento Perú, el portal oficial de SERVIR, y se actualizan todos los días. Cada convocatoria enlaza a la web de la entidad, donde se postula; Chamba al Toque no cobra ni pide datos personales.

Debajo: contador dinámico `3,812 convocatorias vigentes · 1,046 entidades · actualizado el 23 de octubre de 2026`.

### 6.3 Texto de páginas de departamento (2 a 3 frases, generado con datos)
> Hay {N} convocatorias vigentes de entidades públicas en {Departamento}, con sueldos desde S/ {min} hasta S/ {max} al mes. {M} no piden experiencia y {K} piden solo secundaria completa. Las entidades con más plazas son {entidad1}, {entidad2} y {entidad3}.

Ejemplo: "Hay 214 convocatorias vigentes de entidades públicas en Arequipa, con sueldos desde S/ 1,025 hasta S/ 9,800 al mes. 61 no piden experiencia y 47 piden solo secundaria completa. Las entidades con más plazas son la Municipalidad Provincial de Arequipa, el Gobierno Regional de Arequipa y la UGEL Sur." (cifras ilustrativas).

Bloques extra obligatorios por página (todo derivado de datos, para evitar texto de relleno): tabla "Cierran esta semana", "Entidades con más plazas" (con enlaces), y enlace al tema "sin experiencia en {Departamento}" si existe.

Entidad: "{Entidad} tiene {N} convocatorias vigentes. Las plazas más cercanas a cerrar vencen el {fecha}. Los sueldos van de S/ {min} a S/ {max}. Esta información proviene de Talento Perú (SERVIR); las bases completas están en la web de la entidad."

### 6.4 Régimen y tipo de empleo
Mapeo de la columna "número de convocatoria" a texto y `employmentType`:

| Contiene | Texto visible | `employmentType` |
|---|---|---|
| `D.LEG 1057` | "CAS (D.Leg. 1057)" | `FULL_TIME` |
| `D.LEG 728` | "Régimen laboral privado (D.Leg. 728)" | `FULL_TIME` |
| `D.LEG 276` | "Carrera administrativa (D.Leg. 276)" | `FULL_TIME` |
| `PRACTICAS` o `D.LEG 1401` | "Prácticas" | `INTERN` |
| Otro | Mostrar el texto tal cual, sin mapear | omitir `employmentType` |

Verificar con los datos reales qué valores de la columna existen antes de cerrar esta tabla. `INDETERMINADO` en el texto se muestra como "plazo indeterminado" cuando aparezca; no deducir plazo si no figura.

### 6.5 Normalización de texto de MAYÚSCULAS a legible [P0]
Se aplica a cargo, entidad y especialización. Hacer funciones puras con pruebas unitarias.

Algoritmo:
1. Quitar espacios duplicados y extremos. Pasar todo a minúsculas.
2. Dividir en palabras (también tras `/`, `-`, `(`).
3. Primera palabra y palabras tras `(` o `-`: capitalizar.
4. **Palabras pequeñas en minúscula** (salvo primera): `de, del, la, las, el, los, y, e, o, u, en, a, al, con, para, por, sin, un, una`.
5. **Siglas siempre en mayúsculas** (lista cerrada, ampliable): `CAS, SERVIR, UGEL, DRE, DIRESA, GERESA, INEI, SUNAT, SUNARP, RENIEC, ONPE, JNE, PNP, FAP, INPE, MINSA, MINEDU, MIDIS, MTC, MEF, MIMP, MINAM, MIDAGRI, MINCETUR, PRODUCE, ESSALUD (EsSalud), SIS, SIAF, SEACE, OSCE, DNI, TI, PCM, IGV, GL, ONG, UNI, UNMSM, SENASA, SEDAPAL, PNUD, CEPLAN, EPS, COFOPRI, FONCODES, QALI WARMA (Qali Warma), CUNA MAS (Cuna Más)`.
6. **Numerales romanos** (I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII): se mantienen en mayúsculas solo cuando la palabra está al final del cargo o entre espacios y aparece en lista cerrada. Cuidado con "V" y "I" ambiguos: considerar romano solo si el cargo tiene al menos otra palabra y está al final.
7. **Palabras con mayúscula interna** por diccionario: `EsSalud`, `PRONIED → Pronied`, `ProInversión`.
8. **Tildes:** la fuente puede venir sin tildes. Dos capas:
   - Diccionario exacto de **departamentos** (25) y topónimos frecuentes: Áncash, Apurímac, Huánuco, Junín, San Martín, Pachacámac, Chimbote, Huancayo, Cañete, Ayacucho, Huaraz, Cajamarca, Lambayeque, etc. (construir desde el padrón de ubigeos del INEI para cubrir distritos).
   - Diccionario de **palabras de cargo frecuentes** (los 300 términos más repetidos): `TECNICO → Técnico`, `ADMINISTRACION → Administración`, `SECRETARIA → Secretaría` (ambigua: cuidar), `AUXILIAR`, `CONTABILIDAD`, `INGENIERIA → Ingeniería`, `ABOGADO`, `PSICOLOGO → Psicólogo`, `ENFERMERIA → Enfermería`, `PROMOTOR`, `SEGURIDAD`, `SERENAZGO`, `CHOFER`, `VIGILANTE`, `MECANICO → Mecánico`, `ELECTRICISTA`, `DIGITACION → Digitación`.
   - Regla de sufijo: `-CION → -ción`, `-SION → -sión`, `-IA → -ía` solo en lista cerrada (cuidado con falsos positivos).
   - Si la fuente ya trae tildes, **no tocar**.
   - Mantener un archivo `data/correcciones.csv` donde el dueño agrega pares `ORIGINAL → Corrección`; el build lista las 50 palabras sin diccionario más frecuentes del día para ir completándolo.
9. Los textos de requisitos (conocimientos, competencias) se pasan a "oración": primera letra mayúscula, el resto minúscula, con las mismas excepciones de siglas.
10. `NO APLICA` en experiencia se muestra como "No se exige experiencia" y en el resumen "sin experiencia".

Ejemplos:
- `OPERARIO DE LIMPIEZA INTERNA` → `Operario de Limpieza Interna`
- `MUNICIPALIDAD DISTRITAL DE PACHACAMAC` → `Municipalidad Distrital de Pachacámac`
- `ESPECIALISTA EN CONTRATACIONES II` → `Especialista en Contrataciones II`
- `ASISTENTE ADMINISTRATIVO - CAS` → `Asistente Administrativo - CAS`
- `SECUNDARIA COMPLETA` → `Secundaria completa`

### 6.6 Resumen de requisitos en lenguaje simple
Frase única generada con plantillas por formación y experiencia:
- `SECUNDARIA COMPLETA` + `NO APLICA` → "Pide secundaria completa y no exige experiencia."
- `TITULADO UNIVERSITARIO` + `1 AÑO` → "Pide título universitario y 1 año de experiencia."
- Si el valor no encaja en ninguna plantilla: mostrar el texto normalizado sin parafrasear (no arriesgar un resumen incorrecto).

Tema "sin experiencia" = experiencia igual a `NO APLICA` o vacía **y** no una experiencia mínima declarada en otro campo. Tema "secundaria completa" = formación igual a `SECUNDARIA COMPLETA` o inferior (primaria, sin requisito). Revisar con los datos reales los valores de formación para cerrar la lista.

---

## 7. Off-page y medición

### 7.1 Pasos para el dueño, en orden [P0]
1. **Dominio propio** (0.1) y apuntarlo a GitHub Pages (CNAME + HTTPS).
2. **Google Search Console:** crear propiedad. Con dominio propio, tipo "Dominio" (verificación por DNS). Sin dominio: tipo "Prefijo de URL" con `https://arhka5.github.io/chamba-al-toque/`, verificar con archivo HTML subido al sitio (el archivo va en la raíz del proyecto, es decir bajo `/chamba-al-toque/`).
3. **Enviar** `sitemap.xml` (índice) en Sitemaps. Revisar que los sub-sitemaps queden en "Correcto".
4. **Bing Webmaster Tools:** importar el sitio desde Search Console y enviar el sitemap. Bing alimenta también DuckDuckGo, Yahoo y buscadores de IA que lo usan.
5. **Inspección de URL** de 3 páginas (portada, un departamento, una oferta) y revisar "Información sobre la página" y "Ofertas de empleo" en Mejoras.
6. **Prueba de resultados enriquecidos** sobre 5 ofertas antes del lanzamiento público.
7. **Analítica ligera** (GoatCounter o similar) con aviso en Privacidad. Evitar cookies si es posible.
8. Perfil de Facebook/Page, TikTok y canal de Telegram con el mismo nombre y logo.
9. Revisión semanal (15 minutos): informe Rendimiento (consultas, CTR), Cobertura/Indexación (páginas "Excluidas" y "Rastreada: actualmente sin indexar"), Ofertas de empleo (errores), Core Web Vitals.

### 7.2 Difusión realista [P1]
- **Grupos de Facebook** de convocatorias CAS, trabajos en el Estado y por región (hay muchos, de decenas de miles de miembros). Respetar las reglas del grupo; compartir en cada grupo la página de **su** departamento con una frase útil ("Hoy hay 214 convocatorias en Arequipa, 61 sin experiencia"), no spam diario. Pedir a administradores permiso para publicar semanalmente.
- **TikTok y Reels:** videos de 20 a 30 s: "5 chambas del Estado sin experiencia esta semana", "Cómo saber si una convocatoria es falsa", "Qué es un CAS". Contenido educativo atrae más que listas. Los datos del script alimentan guiones semanales.
- **Telegram y canal de WhatsApp** [P2]: un bot/canal por departamento que publica automáticamente las ofertas nuevas del día (el mismo script puede generar el mensaje con enlace). Es el canal que más retiene a este público. Alertas por correo después, si se agrega captura de correos y política de privacidad.
- **Prensa y enlaces:** una nota de datos mensual ("Los sueldos más altos en convocatorias CAS de [mes]", "Qué regiones tienen más plazas sin experiencia") con tabla propia es el tipo de contenido que citan medios locales y creadores. Enviarlo a periodistas que ya publican sobre CAS.
- **Guías evergreen** (P1): `/guia/que-es-cas/`, `/guia/como-postular-convocatoria-cas/`, `/guia/convocatorias-falsas-como-reconocerlas/`. Atraen búsquedas informativas, suman enlaces y refuerzan confianza.
- No copiar texto de competidores ni usar sus marcas; no comprar enlaces.

### 7.3 Plazos esperables (honestos)
- **Días 1 a 7:** Google descubre y rastrea la portada y parte de las ofertas. Es normal ver "Descubierta: actualmente sin indexar" para muchas URLs de un sitio nuevo en un subdominio de `github.io`.
- **Semanas 2 a 4:** primeras ofertas indexadas y, si el marcado es válido, aparición en el panel de empleos de Google. Impresiones bajas.
- **Meses 2 a 3:** búsquedas de cola larga con entidad y cargo ("convocatoria municipalidad distrital de X 2026") empiezan a traer clics; las ofertas nuevas se indexan más rápido.
- **Meses 4 a 8:** posibilidad real de entrar a la primera página por "trabajo en el Estado en {región}" y "convocatorias CAS {región}" en regiones menos competidas. Competir por "convocatorias CAS" a nivel nacional contra medios grandes puede tomar más de un año y depende de enlaces.
- Un sitio nuevo sin dominio propio ni enlaces es más lento. La difusión directa (Facebook, TikTok, Telegram) genera tráfico mucho antes que el SEO; usarla como puente.
- Métricas objetivo (no promesas): mes 1, 1,000+ páginas indexadas; mes 3, 300+ clics diarios; mes 6, 1,500+.

---

## 8. Aviso legal y confianza (E-E-A-T)

Importa para posicionamiento (temas YMYL laborales/económicos) y para que la gente no caiga en convocatorias falsas, que son un problema real en Perú.

### 8.1 Contenido obligatorio [P0]
**Página `/acerca/`:**
- Qué es Chamba al Toque, quién la hace (nombre o seudónimo identificable y un correo real), por qué existe, cómo se obtienen los datos (Talento Perú, SERVIR), con qué frecuencia se actualiza (diario) y la hora.
- Declaración clara: "No somos SERVIR ni una entidad del Estado. No intervenimos en los procesos de selección."

**Página `/aviso-legal/`:**
- Información tomada de Talento Perú (portal oficial del Estado). Puede tener errores o retrasos; **siempre confirmar en las bases de la entidad**.
- No cobramos por publicar ni por ver convocatorias, no ofrecemos puestos, no garantizamos resultados ni intermediamos pagos.
- No se pide DNI, correo, teléfono ni ningún dato personal a quienes consultan convocatorias. La postulación se hace solo en el sitio de la entidad.
- Marcas e instituciones citadas pertenecen a sus titulares.
- Canal para corregir o retirar datos (correo y tiempo de respuesta, por ejemplo 48 horas).

**Página `/privacidad/`:** qué datos se recogen (solo métricas anónimas de visita, si aplica), sin cookies de publicidad al inicio, referencia a la Ley N.° 29733 de Protección de Datos Personales.

**Página `/contacto/`:** correo, y formulario solo si no se piden datos innecesarios.

### 8.2 Aviso en cada oferta [P0]
Recuadro breve, bajo el botón:
> Postular a una convocatoria pública no cuesta nada. Si alguien te pide un pago, un depósito o tu clave para "asegurar" la plaza, es una estafa. Revisa las bases en la web oficial de la entidad y confirma la fecha en Talento Perú. Chamba al Toque no es SERVIR ni la entidad convocante, y no te pedirá datos personales.

Con enlace a `/guia/convocatorias-falsas-como-reconocerlas/` [P1] y al portal oficial `https://talentoperu.servir.gob.pe/` (verificar la URL vigente antes de publicar).

### 8.3 Señales de confianza en la interfaz [P0]
- Fuente y fecha de actualización visibles en portada, listados y oferta ("Fuente: Talento Perú, SERVIR. Registrada el 20 de octubre de 2026").
- En la oferta: el id de SERVIR visible (`N.° 821548`) para que cualquiera la busque en el portal oficial.
- Enlace "Reportar un error o una convocatoria sospechosa" por oferta (correo con asunto prellenado; sin formularios).
- Sin publicidad engañosa ni "Postula aquí" que no vaya a la entidad. Si se agrega publicidad [P2], etiquetada y separada del contenido.
- Sin pop-ups ni solicitudes de notificaciones al entrar.

---

## 9. Plan de entrega por prioridad

**P0 (lanzamiento):**
- Variable `BASE_URL`/`BASE_PATH`; dominio propio recomendado.
- Páginas: portada, oferta, 25 departamentos (+ paginación), entidad (con umbral), 3 temas (CAS, sin experiencia, secundaria), Acerca, Aviso legal, Privacidad, Contacto, 404.
- Títulos, descripciones y H1 según sección 2; normalización de texto (6.5) con pruebas.
- JSON-LD `JobPosting`, `BreadcrumbList`, `WebSite`, `Organization`; validaciones de build (3.6).
- Gestión de ofertas cerradas (1.4) y salvaguarda contra scraping incompleto.
- Sitemaps con `lastmod` real; canonical; `meta robots`; Open Graph genérico.
- Presupuestos de rendimiento, sin JS obligatorio, accesibilidad mínima.
- Search Console, Bing, envío de sitemap, prueba de resultados enriquecidos.

**P1 (primer mes):**
- Temas adicionales (técnico, universitario, municipalidades, gobiernos regionales), combinación departamento + sin experiencia, `/nuevas/`, `/por-vencer/`.
- Guías evergreen y página de convocatorias falsas.
- Imágenes OG por departamento y por oferta.
- Evaluar Indexing API; `educationRequirements` y `experienceRequirements`.
- Búsqueda interna estática (Pagefind), analítica ligera, revisión de enlaces rotos.
- Difusión en Facebook y TikTok.

**P2 (cuando haya tracción):**
- Indexing API y IndexNow en producción, páginas de provincia, `/practicas/`, canal de Telegram/WhatsApp, alertas por correo, notas de datos mensuales, Cloudflare delante del dominio, publicidad etiquetada.

---

## 10. Lista de verificación previa al lanzamiento

- [ ] Ninguna URL, canonical ni JSON-LD tiene la URL escrita a mano; todo sale de `BASE_URL`.
- [ ] Prueba de resultados enriquecidos sin errores en 5 ofertas variadas (con y sin sueldo, con duplicados, con localidad compuesta).
- [ ] No existe `JobPosting` en ninguna página que no sea oferta vigente (test sobre `_site`).
- [ ] Ninguna oferta vencida con marcado; `validThrough` correcto con `-05:00`.
- [ ] Títulos únicos en todo el sitio (reporte de duplicados) y descriptions sin truncar mal.
- [ ] Sitemaps solo con URLs 200 e indexables; `lastmod` no es la fecha del build en todas las URLs.
- [ ] Páginas de entidad bajo umbral con `noindex,follow` y fuera del sitemap.
- [ ] PageSpeed móvil 90 o más en tres tipos de página; HTML de oferta bajo el presupuesto.
- [ ] Sitio navegable con JS desactivado.
- [ ] Textos legales, aviso en oferta y fuente visibles; sin frases prohibidas (búsqueda automática de "descubre", "sumérgete", "en un solo lugar", "experiencia única", "—" en `_site`).
- [ ] Workflow diario probado, con salvaguarda de scraping incompleto y sin desactivarse a los 60 días.
- [ ] Search Console y Bing configurados, sitemap enviado.
