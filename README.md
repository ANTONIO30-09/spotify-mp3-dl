# spotify-mp3-dl

Herramienta CLI para descargar playlists completas de Spotify a MP3, sin necesitar cuenta Premium ni credenciales de la API oficial. Uso estrictamente personal (backup de tu propia biblioteca).

## Por qué existe

Desde febrero de 2026, Spotify exige cuenta **Premium** para crear una app en el [Developer Dashboard](https://developer.spotify.com/dashboard) y así obtener `Client ID`/`Client Secret`. Sin eso, la Web API oficial (usada por `spotipy` y derivados) queda cerrada.

Este proyecto evita ese requisito por completo: lee la metadata de la playlist desde la página pública de Spotify (la misma que usan los widgets embebidos), y descarga el audio real desde YouTube.

## Arquitectura

```
Spotify (metadata pública, sin login)
        │  spotifyscraper
        ▼
lista de tracks [título, artista, álbum, duración, portada]
        │
        ▼
yt-dlp busca "artista - título" en YouTube (5 candidatos)
        │  elige el de duración más cercana (±6s) a la de Spotify
        ▼
descarga el audio y lo convierte a MP3 192kbps (ffmpeg vía yt-dlp)
        │
        ▼
mutagen inyecta tags ID3 (título, artista, álbum, portada) desde la metadata real de Spotify
        │
        ▼
./descargas/{Nombre de playlist}/{Artista} - {Título}.mp3
```

## Stack

- [`spotifyscraper`](https://pypi.org/project/spotifyscraper/) — metadata de Spotify sin login ni API key
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — búsqueda y descarga de audio en YouTube
- `ffmpeg` — conversión a MP3 (invocado por yt-dlp)
- [`mutagen`](https://mutagen.readthedocs.io/) — tageo ID3 + portada
- [`deno`](https://deno.land) — runtime JS requerido por yt-dlp para resolver los desafíos de firma de YouTube

## Instalación

```bash
git clone https://github.com/TU_USUARIO/spotify-mp3-dl.git
cd spotify-mp3-dl

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

sudo apt install ffmpeg -y   # Debian/Ubuntu/Mint

curl -fsSL https://deno.land/install.sh | sh
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Si vas a usar `--cookies-from-browser` (recomendado, evita el bot-check de YouTube), instalá `secretstorage` en Linux:

```bash
pip install secretstorage
```

## Uso

```bash
python spotify_dl.py "https://open.spotify.com/playlist/TU_PLAYLIST_ID"
```

Opciones:

```bash
python spotify_dl.py "URL" --browser chrome --workers 6
python spotify_dl.py "URL" --browser ""        # sin cookies (más fallos de bot-check probables)
```

Si se interrumpe (`Ctrl+C`), simplemente volvé a correr el mismo comando: los tracks ya descargados se saltan (`SKIP`) automáticamente.

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Sign in to confirm you're not a bot` | YouTube pide verificación | Usar `--cookies-from-browser <navegador>` con sesión logueada |
| `Requested format is not available` | Falta resolver el desafío de firma JS de YouTube | Instalar `deno` (el script ya usa `--remote-components ejs:github` automáticamente) |
| `secretstorage not available` | Linux necesita esta lib para leer cookies del navegador | `pip install secretstorage` |
| Playlist se corta en 100 tracks | Límite del embed público antiguo | Ya resuelto: usa `spotifyscraper` con paginación completa |
| Muchos `FAIL` en playlists grandes | Rate-limit temporal de YouTube | Volver a correr el mismo comando 1-2 veces más |

## Disclaimer

Proyecto de uso personal para backup de tu propia biblioteca musical. Descargar contenido con copyright de YouTube puede violar sus Términos de Servicio dependiendo de tu jurisdicción — usalo bajo tu propio criterio y responsabilidad.

## Licencia

MIT
