#!/usr/bin/env python3
"""
spotify-mp3-dl
Descarga playlists de Spotify a MP3 usando metadata pública (sin login/API key)
+ búsqueda y descarga del audio equivalente en YouTube vía yt-dlp.

Uso: python spotify_dl.py <playlist_url> [--browser brave] [--workers 4]
"""
import argparse, os, re, sys, json, shutil, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from spotify_scraper import SpotifyClient
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError

OUT_DIR = Path.cwd() / "descargas"
DURATION_TOLERANCE = 6  # segundos de margen para matchear video de YouTube
MAX_TRACKS = 5000

def find_deno() -> str | None:
    path = shutil.which("deno")
    if path:
        return path
    fallback = Path.home() / ".deno" / "bin" / "deno"
    return str(fallback) if fallback.exists() else None

DENO_PATH = find_deno()

def sanitize(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_playlist_tracks(playlist_url: str):
    with SpotifyClient() as client:
        playlist = client.get_playlist(playlist_url, max_tracks=MAX_TRACKS)
        data = playlist.to_dict()

    playlist_name = sanitize(data.get("name", "playlist"))
    playlist_cover = None
    try:
        playlist_cover = data["images"][0]["url"]
    except Exception:
        pass

    tracks = []
    for item in data.get("tracks", []):
        t = item.get("track") if item else None
        if not t:
            continue

        artists_list = t.get("artists", [])
        artist = ", ".join(a["name"] for a in artists_list) if artists_list else "Unknown"

        cover = playlist_cover
        try:
            cover = t["album"]["images"][0]["url"]
        except Exception:
            pass

        tracks.append({
            "title": t.get("name", "Unknown"),
            "artist": artist,
            "album": t.get("album", {}).get("name", data.get("name", "")),
            "duration_ms": t.get("duration_ms", 0),
            "cover_url": cover,
        })
    return playlist_name, tracks

def log_fail(track, reason, log_path: Path):
    with open(log_path, "a") as f:
        f.write(f"{track['artist']} - {track['title']} | {reason}\n")

def search_and_download(track: dict, out_path: Path, browser: str, log_path: Path) -> bool:
    query = f"ytsearch5:{track['artist']} - {track['title']} audio"
    target_sec = track["duration_ms"] / 1000

    search_cmd = ["yt-dlp", query, "--dump-json", "--no-warnings", "--flat-playlist"]
    if browser:
        search_cmd += ["--cookies-from-browser", browser]

    probe = subprocess.run(search_cmd, capture_output=True, text=True)
    if probe.returncode != 0 or not probe.stdout.strip():
        log_fail(track, f"SEARCH_FAIL rc={probe.returncode} stderr={probe.stderr[-200:]}", log_path)
        return False

    candidates = [json.loads(l) for l in probe.stdout.strip().split("\n")]

    best, best_diff = None, float("inf")
    for c in candidates:
        dur = c.get("duration")
        if dur is None:
            continue
        diff = abs(dur - target_sec)
        if diff < best_diff:
            best_diff, best = diff, c

    video_url = best["url"] if best and best_diff <= DURATION_TOLERANCE else candidates[0]["url"]
    if not video_url.startswith("http"):
        video_url = f"https://www.youtube.com/watch?v={video_url}"

    tmp_template = str(out_path.with_suffix("")) + ".%(ext)s"
    dl_cmd = ["yt-dlp", "--remote-components", "ejs:github", video_url,
              "-f", "bestaudio/best"]
    if DENO_PATH:
        dl_cmd += ["--js-runtimes", f"deno:{DENO_PATH}"]
    dl_cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "192K",
               "-o", tmp_template, "--no-playlist", "--no-warnings", "--quiet"]
    if browser:
        dl_cmd += ["--cookies-from-browser", browser]

    dl = subprocess.run(dl_cmd, capture_output=True, text=True)
    if dl.returncode != 0 or not out_path.exists():
        log_fail(track, f"DOWNLOAD_FAIL rc={dl.returncode} stderr={dl.stderr[-200:]}", log_path)
        return False
    return True

def tag_mp3(path: Path, track: dict):
    try:
        audio = ID3(path)
    except ID3NoHeaderError:
        audio = ID3()

    audio["TIT2"] = TIT2(encoding=3, text=track["title"])
    audio["TPE1"] = TPE1(encoding=3, text=track["artist"])
    audio["TALB"] = TALB(encoding=3, text=track["album"])

    if track["cover_url"]:
        try:
            img = requests.get(track["cover_url"], timeout=10).content
            audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img)
        except Exception:
            pass

    audio.save(path, v2_version=3)

def process_track(track: dict, playlist_dir: Path, browser: str, log_path: Path):
    filename = sanitize(f"{track['artist']} - {track['title']}") + ".mp3"
    out_path = playlist_dir / filename
    if out_path.exists():
        return f"SKIP  {filename}"

    if not search_and_download(track, out_path, browser, log_path):
        return f"FAIL  {filename}"

    tag_mp3(out_path, track)
    return f"OK    {filename}"

def main():
    parser = argparse.ArgumentParser(description="Descarga una playlist de Spotify a MP3 vía YouTube.")
    parser.add_argument("playlist_url", help="URL de la playlist de Spotify")
    parser.add_argument("--browser", default="brave",
                         help="Navegador para leer cookies de YouTube y evitar bot-check (brave, chrome, firefox, etc). Usa '' para desactivar.")
    parser.add_argument("--workers", type=int, default=4, help="Descargas en paralelo (default: 4)")
    args = parser.parse_args()

    playlist_name, tracks = get_playlist_tracks(args.playlist_url)
    playlist_dir = OUT_DIR / playlist_name
    playlist_dir.mkdir(parents=True, exist_ok=True)
    log_path = playlist_dir / "fails.log"

    print(f"Playlist: {playlist_name} | {len(tracks)} tracks -> {playlist_dir}")
    if not DENO_PATH:
        print("AVISO: 'deno' no encontrado. Instalalo (https://deno.land) para evitar fallos de firma de YouTube.")

    browser = args.browser or None
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_track, t, playlist_dir, browser, log_path): t for t in tracks}
        for fut in as_completed(futures):
            print(fut.result())

if __name__ == "__main__":
    main()
