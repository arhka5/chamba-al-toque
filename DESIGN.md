# DESIGN.md: Chamba al Toque

Reglas de diseño del sitio. Léelas antes de tocar `site/static/estilos.css` o
las plantillas. El objetivo: que una persona entienda en 3 segundos qué
puesto es, cuánto pagan, hasta cuándo postula y qué piden, desde un celular
barato y con pocos datos.

## Paleta (variables en `estilos.css`)

| Variable | Claro | Oscuro | Uso |
|---|---|---|---|
| `--papel` | `#f3f5f5` | `#0e1416` | Fondo. Gris frío: **nunca crema** |
| `--tinta` | `#121a1c` | `#e8eff0` | Texto |
| `--cab` / `--pri` | `#0b4a53` / `#0b5560` | `#0b3a41` / `#72cbd5` | Marca: cabecera, enlaces, bordes de tarjeta |
| `--dato` | `#0b5560` | `#86dbe3` | El sueldo (el dato que más importa) |
| `--sol` | `#f2b705` | igual | **Único acento**: botón de acción, "Cierra en N días", foco |

Prohibido: crema con terracota u óxido (la "paleta de asistente IA"),
degradados, sombras en reposo y violetas.

## Tipografía y forma
- Pila del sistema, sin fuentes web. Jerarquía con peso (800–900) y tamaño, no con color.
- Sin etiquetas en mayúsculas pequeñas con espaciado. Las etiquetas van en oración y en negrita.
- Números tabulares en sueldos, fechas y conteos. `text-wrap: balance` en títulos.
- Bordes de 1 px, esquinas de 4 a 6 px. Un solo tipo de botón: plano y lleno.

## Componentes
- **Tarjeta:** entidad (gris) → cargo (negrita) → sueldo grande → lugar y cierre → una frase de requisitos → "Ver convocatoria". Toda la tarjeta es un solo enlace (`::after` absoluto), sin botones duplicados.
- **Urgencia:** "Cierra hoy/mañana/en N días" en etiqueta amarilla con texto oscuro. Se distingue por la forma, no solo por el color.
- **Campo vacío ≠ "no pide".** Si la fuente trae "-" o ".", se muestra "No indicada en la convocatoria".

## Interacción y accesibilidad (Web Interface Guidelines de Vercel)
- Áreas táctiles de al menos 44 px, foco visible y enlace "Saltar al contenido".
- `touch-action: manipulation`, y `color-scheme` y `theme-color` coherentes con el tema.
- El estado de la búsqueda (`q`, `d`, `exp`, `sec`, `sueldo`) vive en la URL.
- Placeholders con un ejemplo y "…". Nada de pop-ups ni anuncios que tapen la oferta.
- CSS en línea de 12 KB como máximo (se minifica en el build). Sin JS obligatorio, salvo en /buscar/.

## Cómo revisar un cambio (los "ojos")

```sh
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python site/build.py --data out/ofertas.json --out public-prev --base-url http://127.0.0.1:8795
.venv/Scripts/python -m http.server 8795 --directory public-prev
.venv/Scripts/python herramientas/mirar.py http://127.0.0.1:8795 / /departamento/cusco/ "/buscar/?q=chofer"
.venv/Scripts/python herramientas/mirar.py http://127.0.0.1:8795 / --oscuro
```

`mirar.py` toma capturas en 390, 768 y 1440 px y avisa de scroll horizontal,
áreas táctiles chicas, imágenes sin medidas y errores de consola. Hay que
mirar las capturas, corregir los 3 peores problemas y repetir (máximo 3 rondas).
