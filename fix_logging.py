import re

with open("spotify_dl.py") as f:
    content = f.read()

content = content.replace(
    '''def search_and_download(track: dict, out_path: Path) -> bool:
    query = f"ytsearch5:{track['artist']} - {track['title']} audio"
    target_sec = track["duration_ms"] / 1000

    probe = subprocess.run(
        ["yt-dlp", query, "--dump-json", "--no-warnings", "--flat-playlist"],
        capture_output=True, text=True
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        return False''',
    '''def log_fail(track, reason):
    with open("fails.log", "a") as f:
        f.write(f"{track['artist']} - {track['title']} | {reason}\\n")

def search_and_download(track: dict, out_path: Path) -> bool:
    query = f"ytsearch5:{track['artist']} - {track['title']} audio"
    target_sec = track["duration_ms"] / 1000

    probe = subprocess.run(
        ["yt-dlp", query, "--dump-json", "--no-warnings", "--flat-playlist"],
        capture_output=True, text=True
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        log_fail(track, f"SEARCH_FAIL rc={probe.returncode} stderr={probe.stderr[-200:]}")
        return False'''
)

content = content.replace(
    '''    return dl.returncode == 0 and out_path.exists()''',
    '''    if dl.returncode != 0 or not out_path.exists():
        log_fail(track, f"DOWNLOAD_FAIL rc={dl.returncode} stderr={dl.stderr[-200:]}")
        return False
    return True'''
)

with open("spotify_dl.py", "w") as f:
    f.write(content)

print("Parcheado OK")
