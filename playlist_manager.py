import json
import os
import asyncio
import yt_dlp as youtube_dl
import wavelink

FILE = "playlists.json"

def load_playlists():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r") as f:
        return json.load(f)

def save_playlists(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user_playlists(user_id):
    data = load_playlists()
    return data.get(str(user_id), [])

def add_track_to_playlist(user_id, playlist_name, track, is_public=False, create_if_missing=False):
    data = load_playlists()
    user_key = str(user_id)

    if user_key not in data:
        data[user_key] = []

    for pl in data[user_key]:
        if pl["name"].lower() == playlist_name.lower():
            for song in pl.get("tracks", []):
                if song.get("url") == track.get("url"):
                    return "duplicate"
            pl["tracks"].append(track)
            pl["is_public"] = is_public
            save_playlists(data)
            return "added"

    if create_if_missing:
        new_playlist = {
            "name": playlist_name,
            "owner_id": user_id,
            "is_public": is_public,
            "tracks": [track],
            "loop": False  
        }
        data[user_key].append(new_playlist)
        save_playlists(data)
        return "created"

    return "not_found"

def get_available_playlists(user_id):
    data = load_playlists()
    available = []
    for owner_id, playlists in data.items():
        for pl in playlists:
            if pl.get("is_public", False) or int(pl.get("owner_id", 0)) == user_id:
                available.append(pl)
    return available

def get_user_playlists_full(user_id):

    data = load_playlists()
    return data.get(str(user_id), [])

async def get_playlist_tracks(query: str):

    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
    }
    loop = asyncio.get_event_loop()
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
    except Exception as e:
        print(f"Errore nell'estrazione della playlist: {e}")
        return None

    if info.get('_type') == 'playlist':
        entries = info.get('entries', [])
        tracks = []
        for entry in entries:
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            track = await wavelink.YouTubeTrack.search(video_url, return_first=True)
            if track:
                tracks.append(track)
        return tracks
    else:
        return None
