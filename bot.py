import os
import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import json
from dotenv import load_dotenv
from playlist_manager import (
    get_user_playlists, 
    get_user_playlists_full, 
    add_track_to_playlist, 
    load_playlists, 
    save_playlists, 
    get_available_playlists,
    get_playlist_tracks
)
import yt_dlp as youtube_dl 
import re
import asyncio

# Carica le variabili d'ambiente dal file .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")

if DISCORD_TOKEN is None:
    raise ValueError("Il token del bot non è stato trovato nel file .env")

# Impostazione degli intents per il bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='/', intents=intents)
tree = bot.tree

# Regex per identificare link YouTube
YOUTUBE_URL_REGEX = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/")

##############################################
# FUNZIONI PER LA GESTIONE DEI BRANI
##############################################
async def get_track(query: str) -> wavelink.YouTubeTrack | None:
 
    match = YOUTUBE_URL_REGEX.match(query)
    if match:
        video_id = match.group(1)
        results = await wavelink.YouTubeTrack.search(f"https://www.youtube.com/watch?v={video_id}")
        return results[0] if results else None

    return await wavelink.YouTubeTrack.search(query, return_first=True)


async def ensure_player_connected(interaction: discord.Interaction) -> wavelink.Player:

    node = wavelink.NodePool.get_node()
    player: wavelink.Player = node.get_player(interaction.guild)

    if not player:
        player = await interaction.user.voice.channel.connect(cls=CustomPlayer)
    elif not player.is_connected():
        await player.connect(channel=interaction.user.voice.channel)

    return player

##############################################
# EVENTI DEL BOT
##############################################
@bot.event
async def on_ready():
    print(f'{bot.user} pronto!')
    await tree.sync()

    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="🎶 la musica degli utenti"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    try:
        wavelink.NodePool.get_node()
    except wavelink.ZeroConnectedNodes:
        try:
            await wavelink.NodePool.create_node(
                bot=bot,
                host=LAVALINK_HOST,
                port=LAVALINK_PORT,
                password=LAVALINK_PASSWORD
            )
        except Exception as e:
            print(f"❌ Errore nel connettere Lavalink: {e}")
        else:
            print("✅ Nodo Lavalink connesso!")
    else:
        print("ℹ️ Nodo Lavalink già connesso.")

##############################################
# COMANDO /playplaylist - Riproduzione Playlist
##############################################
@tree.command(name="playplaylist", description="Scegli una delle playlist visibili da ascoltare")
async def playplaylist(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    playlists = get_available_playlists(interaction.user.id)
    if not playlists:
        return await interaction.followup.send("❌ Non ci sono playlist disponibili!", ephemeral=True)

    embed = discord.Embed(
        title="🎷 Le Playlist Disponibili",
        description="Clicca su una playlist per iniziare l'ascolto",
        color=discord.Color.purple()
    )
    for pl in playlists:
        stato = "🌐 Pubblica" if pl.get("is_public", False) else "🔒 Privata"
        embed.add_field(name=f"📁 {pl['name']}", value=f"{stato} - {len(pl['tracks'])} brani", inline=False)

    view = PlaylistSelectView(playlists, interaction.user.id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

##############################################
# VIEW PER LA SELEZIONE DELLA PLAYLIST
##############################################
class PlaylistSelectView(discord.ui.View):
    def __init__(self, playlists, user_id):
        super().__init__(timeout=60)
        for pl in playlists:
            self.add_item(PlayButton(pl, user_id))


class PlayButton(discord.ui.Button):
    def __init__(self, playlist, user_id):
        super().__init__(label=playlist["name"], style=discord.ButtonStyle.green)
        self.playlist = playlist
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("🔇 Devi essere in un canale vocale!", ephemeral=True)

        player = await ensure_player_connected(interaction)

        tracks_to_add = []
        for song in self.playlist.get("tracks", []):
            track = await wavelink.YouTubeTrack.search(song["url"], return_first=True)
            if track:
                tracks_to_add.append(track)

        if not tracks_to_add:
            return await interaction.response.send_message("❌ Playlist vuota!", ephemeral=True)

        if (not player.is_playing() or player.stopped) and not player.control_message:
            first = tracks_to_add[0]
            first.requester = interaction.user
            await player.play(first)
            player.current = first

            for t in tracks_to_add[1:]:
                t.requester = interaction.user
            player.queue.extend(tracks_to_add[1:])

            secs = int(first.length)
            m, s = divmod(secs, 60)
            vol = player.volume

            embed = discord.Embed(
                title=f"▶️ Playlist: {self.playlist['name']}",
                description=f"[{first.title}]({first.uri})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=first.thumbnail or "https://via.placeholder.com/150")
            embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
            embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
            embed.add_field(name="🎧 Brani in coda", value=str(len(player.queue)), inline=True)
            embed.set_footer(text=f"Richiesto da {first.requester}",
                             icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

            msg = await interaction.response.send_message(embed=embed, view=MusicControls(first, interaction.guild, loop_active=player.loop))
            player.control_message = await interaction.original_response()

        else:
            for t in tracks_to_add:
                t.requester = interaction.user
                player.queue.append(t)
            await interaction.response.send_message(
                f"✅ Playlist **{self.playlist['name']}** aggiunta in coda con {len(tracks_to_add)} brani.",
                ephemeral=True
            )

##############################################
# COMANDO /gestisciplaylist - Gestione Playlist
##############################################
@tree.command(name="gestisciplaylist", description="Gestisci le tue playlist e quelle pubbliche")
async def gestisci_playlist(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    playlists = get_available_playlists(interaction.user.id)
    if not playlists:
        return await interaction.followup.send("❌ Non ci sono playlist disponibili!", ephemeral=True)
    embed = discord.Embed(
        title="🎛️ Gestione Playlist",
        description="Clicca su una playlist per gestirla:",
        color=discord.Color.blurple()
    )
    for pl in playlists:
        stato = "🌐 Pubblica" if pl.get("is_public", False) else "🔒 Privata"
        embed.add_field(name=f"📁 {pl['name']}", value=f"{stato} - {len(pl['tracks'])} brani", inline=False)
    view = GestisciPlaylistView(playlists, interaction.user.id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class GestisciPlaylistView(discord.ui.View):
    def __init__(self, playlists, user_id):
        super().__init__(timeout=60)
        for pl in playlists:
            self.add_item(GestisciPlaylistButton(pl, user_id))

class GestisciPlaylistButton(discord.ui.Button):
    def __init__(self, playlist, user_id):
        super().__init__(label=playlist["name"], style=discord.ButtonStyle.green)
        self.playlist = playlist
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        owner_id = int(self.playlist.get("owner_id", self.user_id))
        is_public = self.playlist.get("is_public", False)
        if (not is_public) and (interaction.user.id != owner_id):
            return await interaction.response.send_message("❌ Non sei il proprietario e la playlist è privata.", ephemeral=True)
        manage_view = ManagePlaylistView(self.playlist, interaction.user)
        await interaction.response.send_message(
            f"⚙️ Gestisci la playlist **{self.playlist['name']}**",
            view=manage_view,
            ephemeral=True
        )

##############################################
# VIEW DI GESTIONE DELLA PLAYLIST (opzioni)
##############################################
class ManagePlaylistView(discord.ui.View):
    def __init__(self, playlist, user):
        super().__init__(timeout=60)
        self.playlist = playlist
        self.user = user
        self.add_item(ClearPlaylistButton(playlist, user))
        self.add_item(RenamePlaylistButton(playlist, user))
        self.add_item(DeletePlaylistButton(playlist, user))
        self.add_item(RemoveTrackMenuButton(playlist, user))

class ClearPlaylistButton(discord.ui.Button):
    def __init__(self, playlist, user):
        super().__init__(label="🗑️ Svuota", style=discord.ButtonStyle.danger)
        self.playlist = playlist
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if (not self.playlist.get("is_public", False)) and (interaction.user.id != int(self.playlist.get("owner_id", self.user.id))):
            return await interaction.response.send_message("❌ Non sei il proprietario di questa playlist.", ephemeral=True)
        self.playlist["tracks"] = []
        data = load_playlists()
        owner_key = str(self.playlist.get("owner_id", self.user.id))
        user_playlists = data.get(owner_key, [])
        for pl in user_playlists:
            if pl["name"].lower() == self.playlist["name"].lower():
                pl.update(self.playlist)
                break
        save_playlists(data)
        await interaction.response.send_message("🗑️ Playlist svuotata!", ephemeral=True)

class RenamePlaylistButton(discord.ui.Button):
    def __init__(self, playlist, user):
        super().__init__(label="✏️ Rinomina", style=discord.ButtonStyle.gray)
        self.playlist = playlist
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if (not self.playlist.get("is_public", False)) and (interaction.user.id != int(self.playlist.get("owner_id", self.user.id))):
            return await interaction.response.send_message("❌ Non sei il proprietario di questa playlist.", ephemeral=True)
        await interaction.response.send_modal(RenamePlaylistModal(self.playlist))

class DeletePlaylistButton(discord.ui.Button):
    def __init__(self, playlist, user):
        super().__init__(label="🚫 Elimina", style=discord.ButtonStyle.red)
        self.playlist = playlist
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if (not self.playlist.get("is_public", False)) and (interaction.user.id != int(self.playlist.get("owner_id", self.user.id))):
            return await interaction.response.send_message("❌ Non sei il proprietario di questa playlist.", ephemeral=True)
        data = load_playlists()
        owner_key = str(self.playlist.get("owner_id", self.user.id))
        user_playlists = data.get(owner_key, [])
        data[owner_key] = [pl for pl in user_playlists if pl["name"].lower() != self.playlist["name"].lower()]
        save_playlists(data)
        await interaction.response.send_message("🚫 Playlist eliminata con successo!", ephemeral=True)

class RemoveTrackMenuButton(discord.ui.Button):
    def __init__(self, playlist, user):
        super().__init__(label="➖ Rimuovi Brano", style=discord.ButtonStyle.secondary)
        self.playlist = playlist
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if not self.playlist.get("tracks"):
            return await interaction.response.send_message("❌ La playlist è vuota.", ephemeral=True)
        if (not self.playlist.get("is_public", False)) and (interaction.user.id != int(self.playlist.get("owner_id", self.user.id))):
            return await interaction.response.send_message("❌ Non sei il proprietario di questa playlist.", ephemeral=True)
        view = RemoveTrackView(self.playlist, self.user)
        await interaction.response.send_message("Seleziona il brano da rimuovere:", view=view, ephemeral=True)

class RemoveTrackView(discord.ui.View):
    def __init__(self, playlist, user):
        super().__init__(timeout=60)
        self.playlist = playlist
        self.user = user
        for index, track in enumerate(self.playlist.get("tracks", [])):
            title = track.get("title", "Sconosciuto")
            title = (title[:25] + "...") if len(title) > 28 else title
            self.add_item(RemoveTrackButton(title, index, playlist, user))

class RemoveTrackButton(discord.ui.Button):
    def __init__(self, title, index, playlist, user):
        super().__init__(label=title, style=discord.ButtonStyle.red)
        self.index = index
        self.playlist = playlist
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if (not self.playlist.get("is_public", False)) and (interaction.user.id != int(self.playlist.get("owner_id", self.user.id))):
            return await interaction.response.send_message("❌ Non sei il proprietario di questa playlist.", ephemeral=True)
        try:
            removed = self.playlist["tracks"].pop(self.index)
        except IndexError:
            return await interaction.response.send_message("Errore: brano non trovato.", ephemeral=True)
        data = load_playlists()
        owner_key = str(self.playlist.get("owner_id", self.user.id))
        user_playlists = data.get(owner_key, [])
        for pl in user_playlists:
            if pl["name"].lower() == self.playlist["name"].lower():
                pl.update(self.playlist)
                break
        save_playlists(data)
        await interaction.response.send_message(f"✅ Rimosso il brano '{removed.get('title', 'Sconosciuto')}' dalla playlist.", ephemeral=True)

class RenamePlaylistModal(discord.ui.Modal, title="✏️ Rinomina Playlist"):
    def __init__(self, playlist):
        super().__init__()
        self.playlist = playlist
        self.new_name = discord.ui.TextInput(
            label="Nuovo nome",
            placeholder="Inserisci il nuovo nome della playlist",
            max_length=100
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        old_name = self.playlist["name"]
        self.playlist["name"] = self.new_name.value
        data = load_playlists()
        owner_key = str(self.playlist.get("owner_id", interaction.user.id))
        user_playlists = data.get(owner_key, [])
        for pl in user_playlists:
            if pl["name"] == old_name:
                pl["name"] = self.new_name.value
                break
        save_playlists(data)
        await interaction.response.send_message(f"✅ Playlist rinominata in **{self.new_name.value}**", ephemeral=True)

##############################################
# COMANDO /play - Riproduce una canzone o una playlist da YouTube
##############################################
@tree.command(name="play", description="Riproduci una canzone o playlist YouTube")
@app_commands.describe(query="Link o titolo")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.followup.send("❌ Devi essere in un canale vocale!", ephemeral=True)

    player = await ensure_player_connected(interaction)

    if "list=" in query:
        tracks = await get_playlist_tracks(query)
        if not tracks:
            return await interaction.followup.send("❌ Nessuna playlist trovata.", ephemeral=True)

        first = tracks.pop(0)
        first.requester = interaction.user
        await player.play(first)
        player.current = first

        for t in tracks:
            t.requester = interaction.user
        player.queue.extend(tracks)

        secs = int(first.length)
        m, s = divmod(secs, 60)
        vol = player.volume

        embed = discord.Embed(
            title="🎶 Ora in riproduzione (Playlist)",
            description=f"[{first.title}]({first.uri})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=first.thumbnail or "https://via.placeholder.com/150")
        embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
        embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
        embed.add_field(name="📑 Brani in coda", value=str(len(player.queue)), inline=True)
        embed.set_footer(text=f"Richiesto da {first.requester}",
                         icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        msg = await interaction.followup.send(embed=embed, view=MusicControls(first, interaction.guild, loop_active=player.loop))
        player.control_message = msg

    else:
        track = await get_track(query)
        if not track:
            return await interaction.followup.send("❌ Nessun risultato trovato!", ephemeral=True)

        track.requester = interaction.user

        if (not player.is_playing() or player.stopped) and not player.control_message:
            await player.play(track)
            player.current = track

            secs = int(track.length)
            m, s = divmod(secs, 60)
            vol = player.volume

            embed = discord.Embed(
                title="🎶 Ora in riproduzione",
                description=f"[{track.title}]({track.uri})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=track.thumbnail or "https://via.placeholder.com/150")
            embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
            embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
            embed.set_footer(text=f"Richiesto da {track.requester}",
                             icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

            msg = await interaction.followup.send(embed=embed, view=MusicControls(track, interaction.guild, loop_active=player.loop))
            player.control_message = msg
        else:
            player.queue.append(track)
            return await interaction.followup.send(f"✅ **{track.title}** aggiunto alla coda.", ephemeral=True)

##############################################
# CLASSE CUSTOMPLAYER (Estensione di wavelink.Player)
##############################################
class CustomPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = []
        self.current = None
        self.stopped = False
        self._custom_paused = False
        self.control_message = None 
        self.loop = False

    async def connect(self, *, timeout=60.0, reconnect=True, self_deaf=False, self_mute=False):
        self.stopped = False
        self._custom_paused = False
        return await super().connect(timeout=timeout, reconnect=reconnect)

    async def stop(self):
        await super().stop()
        self.stopped = True
        self._custom_paused = False

    async def set_equalizer(self, equalizer_settings: list):
        payload = {
            "op": "filters",
            "guildId": str(self.guild.id),
            "equalizer": [{"band": band, "gain": gain} for band, gain in equalizer_settings]
        }
        ws = (
            getattr(self.node, '_ws', None)
            or getattr(self.node, '_websocket', None)
            or getattr(self.node, 'ws', None)
        )
        if ws is None:
            return payload
        try:
            if hasattr(ws, 'send_json'):
                await ws.send_json(payload)
                return payload
        except Exception as e:
            print("Errore invio con send_json:", e)
        try:
            if hasattr(ws, 'send_str'):
                await ws.send_str(json.dumps(payload))
                return payload
        except Exception as e:
            print("Errore invio con send_str:", e)
        try:
            if hasattr(ws, 'websocket') and hasattr(ws.websocket, 'send'):
                await ws.websocket.send(json.dumps(payload))
                return payload
        except Exception as e:
            print("Errore invio con ws.websocket.send:", e)
        return payload

##############################################
# VIEW DEI CONTROLLI MUSICALI
##############################################
class MusicControls(discord.ui.View):
    def __init__(self, track, guild, loop_active: bool = False):
        super().__init__(timeout=None)
        self.track = track
        self.guild = guild
        self.loop_active = loop_active
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "toggle_loop":
                if self.loop_active:
                    child.label = "🔁 Loop Attivato"
                    child.style = discord.ButtonStyle.primary
                else:
                    child.label = "🔁 Loop"
                    child.style = discord.ButtonStyle.secondary
                break

    @discord.ui.button(label="⏸️ Pausa", style=discord.ButtonStyle.grey, custom_id="toggle_pause")
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

        if player._custom_paused:
            try:
                await player.set_pause(False)
                player._custom_paused = False
                button.label = "⏸️ Pausa"
                msg = "La canzone è stata ripresa!"
            except Exception as e:
                return await interaction.response.send_message(f"Errore nel riprendere la canzone: {e}", ephemeral=True)
        else:
            try:
                await player.set_pause(True)
                player._custom_paused = True
                button.label = "▶️ Riprendi"
                msg = "La canzone è stata messa in pausa!"
            except Exception as e:
                return await interaction.response.send_message(f"Errore nel mettere in pausa: {e}", ephemeral=True)
        await interaction.message.edit(view=self)
        return await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.secondary, custom_id="toggle_loop")
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

        player.loop = not player.loop
        self.loop_active = player.loop
        if player.loop:
            button.label = "🔁 Loop Attivato"
            button.style = discord.ButtonStyle.primary
            status = "attivato"
        else:
            button.label = "🔁 Loop"
            button.style = discord.ButtonStyle.secondary
            status = "disattivato"

        await interaction.response.send_message(f"🔁 Loop {status}.", ephemeral=True)
        await interaction.message.edit(view=self)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger, custom_id="stop_track")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            msg = "Il player non è attivo."
        elif player.stopped:
            msg = "La canzone è già stata fermata."
        else:
            if player._custom_paused:
                await player.set_pause(False)
                player._custom_paused = False
            await player.stop()
            await player.disconnect(force=True)
            try:
                await interaction.message.delete()
            except Exception as e:
                print(f"Errore nella cancellazione del messaggio: {e}")
            msg = "Canzone fermata e bot disconnesso dal canale vocale."
        if not interaction.response.is_done():
            return await interaction.response.send_message(msg, ephemeral=True)
        else:
            return await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, custom_id="skip_track")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)
        if player.stopped:
            return await interaction.response.send_message("Il player è stato fermato.", ephemeral=True)
        if not player.queue:
            return await interaction.response.send_message("Non ci sono altri brani in coda da saltare.", ephemeral=True)
        try:
            player.skip_manual = True
            next_track = player.queue.pop(0)
            await player.play(next_track)
            player.current = next_track

            secs = int(next_track.length)
            m, s = divmod(secs, 60)
            vol = player.volume

            new_embed = discord.Embed(
                title="🎶 Ora in riproduzione",
                description=f"[{next_track.title}]({next_track.uri})",
                color=discord.Color.green()
            )
            new_embed.set_thumbnail(url=next_track.thumbnail or "https://via.placeholder.com/150")
            new_embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
            new_embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
            new_embed.set_footer(
                text=f"Richiesto da {interaction.user}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )

            await interaction.response.edit_message(embed=new_embed, view=MusicControls(next_track, interaction.guild, loop_active=player.loop))
        except Exception as e:
            await interaction.response.send_message(f"Errore nel saltare il brano: {e}", ephemeral=True)

    @discord.ui.button(label="🔊 Volume +", style=discord.ButtonStyle.grey, custom_id="volume_up")
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

        new_vol = min(100, player.volume + 10)
        await player.set_volume(new_vol)

        track = player.current
        secs = int(track.length)
        m, s = divmod(secs, 60)
        embed = discord.Embed(
            title="🎶 Ora in riproduzione",
            description=f"[{track.title}]({track.uri})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=get_thumbnail(track))
        embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
        embed.add_field(name="🔊 Volume", value=f"{new_vol}%", inline=True)
        embed.set_footer(text=f"Richiesto da {track.requester}",
                         icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        if player.control_message:
            await player.control_message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"Volume aumentato a {new_vol}%", ephemeral=True)


    @discord.ui.button(label="🔉 Volume -", style=discord.ButtonStyle.grey, custom_id="volume_down")
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

        new_vol = max(1, player.volume - 10)
        await player.set_volume(new_vol)

        track = player.current
        secs = int(track.length)
        m, s = divmod(secs, 60)
        embed = discord.Embed(
            title="🎶 Ora in riproduzione",
            description=f"[{track.title}]({track.uri})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=get_thumbnail(track))
        embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
        embed.add_field(name="🔊 Volume", value=f"{new_vol}%", inline=True)
        embed.set_footer(text=f"Richiesto da {track.requester}",
                         icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        if player.control_message:
            await player.control_message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"Volume diminuito a {new_vol}%", ephemeral=True)
    
    @discord.ui.button(label="🔧 Volume Manuale", style=discord.ButtonStyle.blurple, custom_id="volume_manual")
    async def volume_manual(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VolumeModal())

    @discord.ui.button(label="➕ Aggiungi alla Playlist", style=discord.ButtonStyle.green, custom_id="add_to_playlist")
    async def add_to_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PlaylistChoiceView(self.track)
        if not interaction.response.is_done():
            return await interaction.response.send_message("📂 Scegli cosa fare con questa canzone:", view=view, ephemeral=True)
        else:
            return await interaction.followup.send("📂 Scegli cosa fare con questa canzone:", view=view, ephemeral=True)

class VolumeModal(discord.ui.Modal, title="Imposta Volume Manuale"):
    volume = discord.ui.TextInput(
        label="Inserisci il volume (1-100)",
        placeholder="Es: 50",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vol = int(self.volume.value)
        except ValueError:
            return await interaction.response.send_message("Il volume deve essere un numero.", ephemeral=True)
        if not 1 <= vol <= 100:
            return await interaction.response.send_message("Inserisci un numero tra 1 e 100.", ephemeral=True)

        node = wavelink.NodePool.get_node()
        player = node.get_player(interaction.guild)
        if not player:
            return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

        await player.set_volume(vol)

        track = player.current
        secs = int(track.length)
        m, s = divmod(secs, 60)
        embed = discord.Embed(
            title="🎶 Ora in riproduzione",
            description=f"[{track.title}]({track.uri})",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=get_thumbnail(track))
        embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
        embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)
        embed.set_footer(text=f"Richiesto da {track.requester}",
                         icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

        if player.control_message:
            await player.control_message.edit(embed=embed, view=MusicControls(track, interaction.guild, loop_active=player.loop))

        await interaction.response.send_message(f"Volume impostato a {vol}", ephemeral=True)

##############################################
# GESTIONE DELLE PLAYLIST PER L'AGGIUNTA DI CANZONI
##############################################
class PlaylistChoiceView(discord.ui.View):
    def __init__(self, track):
        super().__init__(timeout=60)
        self.track = track

    @discord.ui.button(label="📁 Nuova Playlist", style=discord.ButtonStyle.blurple, custom_id="create_new_playlist")
    async def create_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NewPlaylistModal(self.track))

    @discord.ui.button(label="📂 Esistente", style=discord.ButtonStyle.green, custom_id="add_existing_playlist")
    async def add_existing(self, interaction: discord.Interaction, button: discord.ui.Button):
        playlists = get_user_playlists(interaction.user.id)
        if not playlists:
            return await interaction.response.send_message("❌ Non hai playlist, creane una prima!", ephemeral=True)
        view = ExistingPlaylistsView(self.track, playlists)
        await interaction.response.send_message("📚 Seleziona una playlist:", view=view, ephemeral=True)

class NewPlaylistModal(discord.ui.Modal, title="🎵 Nuova Playlist"):
    nome = discord.ui.TextInput(label="Nome Playlist", placeholder="Es: Chill Vibes", required=True)
    visibile = discord.ui.TextInput(label="Pubblica? (sì/no)", placeholder="sì o no", required=True)
    def __init__(self, track):
        super().__init__()
        self.track = track
    async def on_submit(self, interaction: discord.Interaction):
        is_public = self.visibile.value.strip().casefold() in ["sì", "si", "Si", "Sì"]
        add_track_to_playlist(
            interaction.user.id,
            self.nome.value,
            {"title": self.track.title, "url": self.track.uri},
            is_public=is_public,
            create_if_missing=True
        )
        return await interaction.response.send_message(f"✅ Canzone aggiunta alla nuova playlist **{self.nome.value}**!", ephemeral=True)

class ExistingPlaylistsView(discord.ui.View):
    def __init__(self, track, playlists):
        super().__init__(timeout=60)
        self.track = track
        for pl in playlists:
            self.add_item(PlaylistButton(pl, self.track))

class PlaylistButton(discord.ui.Button):
    def __init__(self, playlist, track):
        super().__init__(label=playlist["name"], style=discord.ButtonStyle.grey)
        self.playlist = playlist
        self.track = track
    async def callback(self, interaction: discord.Interaction):
        for song in self.playlist.get("tracks", []):
            if song.get("url") == self.track.uri:
                return await interaction.response.send_message("❌ Questa canzone è già presente nella playlist.", ephemeral=True)
        add_track_to_playlist(
            interaction.user.id,
            self.playlist["name"],
            {"title": self.track.title, "url": self.track.uri}
        )
        return await interaction.response.send_message(f"✅ Aggiunto a **{self.playlist['name']}**!", ephemeral=True)

##############################################
# COMANDO SEGRETO PER VOLUME MASSIMO CON BASS BOOST
##############################################
@tree.command(name="secretvolume", description="Funzione segreta per impostare il volume a 500 con bass boost (richiede una chiave segreta)")
@app_commands.describe(secret_key="Chiave segreta per abilitare il volume massimo")
async def secret_volume(interaction: discord.Interaction, secret_key: str):
    CHIAVE_SEGRETA = "duro"
    if secret_key != CHIAVE_SEGRETA:
        return await interaction.response.send_message("❌ Chiave segreta errata. Accesso negato.", ephemeral=True)

    node = wavelink.NodePool.get_node()
    player = node.get_player(interaction.guild)
    if not player:
        return await interaction.response.send_message("Il player non è attivo.", ephemeral=True)

    await player.set_volume(500)

    equalizer_settings = [
        (0, 0.5),
        (1, 0.45),
        (2, 0.40),
        (3, 0.30),
        (4, 0.20),
        (5, 0.00),
        (6, -0.10),
        (7, -0.20),
        (8, -0.30),
        (9, -0.20),
        (10, -0.10),
        (11, 0.00),
        (12, 0.00),
        (13, 0.00),
        (14, 0.00)
    ]

    try:
        await player.set_equalizer(equalizer_settings)
        equalizer_message = "con bass boost potenziato"
    except Exception as e:
        print("Errore nell'applicazione dell'equalizer:", e)
        equalizer_message = "ma il bass boost non è stato applicato"

    return await interaction.response.send_message(
        f"🔊 Volume impostato a 500 {equalizer_message}! Funzione segreta attivata.",
        ephemeral=True
    )

##############################################
# EVENTO DI FINE TRACCIA
##############################################
def get_thumbnail(track: wavelink.Track) -> str:
    thumbnail = getattr(track, "thumbnail", None)
    if thumbnail:
        return thumbnail
    video_id = None
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", track.uri)
    if match:
        video_id = match.group(1)
        return f"https://img.youtube.com/vi/{video_id}/0.jpg"
    return "https://via.placeholder.com/150"

@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    if not isinstance(player, CustomPlayer):
        return

    if getattr(player, "skip_manual", False):
        player.skip_manual = False
        return

    if player.loop:
        if not getattr(player, "cached_thumbnail", None):
            player.cached_thumbnail = get_thumbnail(track)
        await player.play(track)

        if player.control_message:
            secs = int(track.length)
            m, s = divmod(secs, 60)
            vol = player.volume

            embed = discord.Embed(
                title="🎶 Ora in riproduzione",
                description=f"[{track.title}]({track.uri})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=player.cached_thumbnail)
            embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
            embed.add_field(name="🔊 Volume", value=f"{vol}%", inline=True)

            await player.control_message.edit(
                embed=embed,
                view=MusicControls(track, player.guild, loop_active=True)
            )
        return

    player.cached_thumbnail = None

    if player.queue:
        next_track = player.queue.pop(0)
        try:
            current_volume = player.volume
            await player.play(next_track)
            player.current = next_track
            await player.set_volume(current_volume)

            duration_secs = int(next_track.length)
            m, s = divmod(duration_secs, 60)
            embed = discord.Embed(
                title="🎶 Ora in riproduzione",
                description=f"[{next_track.title}]({next_track.uri})",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=next_track.thumbnail or "https://via.placeholder.com/150")
            embed.add_field(name="⏱ Durata", value=f"{m}:{s:02d}", inline=True)
            embed.add_field(name="🔊 Volume", value=f"{current_volume}%", inline=True)
            embed.set_footer(
                text=f"Richiesto da {player.current.requester}",
                icon_url=getattr(player.current.requester, 'avatar_url', None)
            )

            if player.control_message:
                await player.control_message.edit(
                    embed=embed,
                    view=MusicControls(next_track, player.guild, loop_active=player.loop)
                )
        except Exception as e:
            print(f"Errore nel riprodurre il brano successivo: {e}")
    else:
        await asyncio.sleep(5)
        if player.control_message:
            try:
                await player.control_message.delete()
            except Exception as e:
                print(f"Errore nella cancellazione del messaggio di controllo: {e}")
            finally:
                player.control_message = None
        await player.disconnect(force=True)
        print("La coda è vuota: bot disconnesso automaticamente dalla vocale.")

# Avvio del bot
bot.run(DISCORD_TOKEN)
