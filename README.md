# Chamba al Toque

Convocatorias de trabajo del Estado peruano, con sueldo, requisitos y fecha
límite, en una página por oferta: https://chambearhoy.toca.pe/

Los datos salen de [Talento Perú](https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/ofertas_laborales.xhtml),
el portal oficial de SERVIR donde las entidades públicas registran sus
convocatorias. Chamba al Toque no es SERVIR ni una entidad del Estado, no
cobra y no pide datos personales.

## Cómo funciona

1. `scraper/` recorre Talento Perú con calma (una petición por segundo,
   User-Agent identificado) y escribe `ofertas.json`. El detalle de cada
   oferta (requisitos, enlace a las bases, N.° de SERVIR) solo se pide para
   las ofertas nuevas.
2. `site/build.py` genera el sitio estático: una página por oferta con datos
   estructurados `JobPosting`, listados por departamento, entidad y tema,
   sitemaps y las páginas legales. Las reglas están en
   [`docs/SEO_SPEC.md`](docs/SEO_SPEC.md).
3. GitHub Actions lo corre dos veces al día, guarda los datos en la rama
   `data` y publica en GitHub Pages.

## Desarrollo

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # en Linux/Mac: .venv/bin/python
.venv/Scripts/python -m pytest -q scraper/tests
cd site && ../.venv/Scripts/python -m pytest -q && cd ..

# Datos: unas pocas páginas para probar
.venv/Scripts/python -m scraper --output out/ofertas.json --max-paginas 3 --max-detalles 30
# Sitio local
.venv/Scripts/python site/build.py --data out/ofertas.json --out public --base-url http://127.0.0.1:8000
.venv/Scripts/python -m http.server 8000 --directory public
```

Las tildes que faltan en la fuente se corrigen con `site/textos.py` y con
`data/correcciones.csv` (una línea `ORIGINAL,Corrección`). Cada build deja
en `out/palabras-sin-diccionario.txt` las palabras frecuentes sin revisar.

## Reportar un error

Escribe a 3b3n3z3r333@gmail.com.
