"""A public YouTube or YouTube Music playlist by link, listed with yt-dlp (no sign-in)."""
import re
from urllib.parse import parse_qs, urlsplit

from library import Entry, ImportFailed, artist_and_title, https_url, key, text
from ytdlp import Refused, listing


# Words that mark a bracket or a tail of a video title as being about the video, not the song.
NOISE = re.compile(r"official|video|audio|lyric|visuali[sz]er|explicit|клип|премьера|\bm/?v\b|\bhd\b|\bhq\b|\b4k\b", re.I)
# How labels title a video on their own channel: BTS 'Dynamite' Official MV.
QUOTED = re.compile(r"""(.+?)\s+['"‘“]([^'"’”]+)['"’”]\s*(.*)""")
TOPIC = " - Topic"


def clean(title):
    """A video title without what uploaders append: (Official Video), [Lyrics], | Official Audio."""
    title = re.sub(r"\s*[(\[]([^)\]]*)[)\]]", lambda bracket: "" if NOISE.search(bracket[1]) else bracket[0], title)
    head, bar, tail = title.partition("|")
    return " ".join((head if bar and NOISE.search(tail) else title).split())


def song(title, channel):
    """(artist, title) of a playlist entry. YouTube Music lists a song under its bare title on the
    artist's channel; a video is usually titled "Artist - Song" by whoever uploaded it."""
    owner = channel.removesuffix(TOPIC).strip()
    # A "Topic" channel is made by YouTube for one artist, so a dash in its titles belongs to the song.
    if channel.endswith(TOPIC):
        return owner, title
    quoted = QUOTED.fullmatch(title)
    if quoted and NOISE.search(quoted[3]):
        return quoted[1], quoted[2]
    title = clean(title)
    artist, name = artist_and_title(title)
    if not artist:
        # Some channels part the two with a bar: Passenger | Let Her Go.
        artist, bar, name = map(str.strip, title.partition("|"))
        if not (artist and name):
            return owner, title
    # A channel named first among the artists is the main one: "Lady Gaga, Bruno Mars - …" on Lady Gaga's channel.
    named, own = key(artist), key(owner)
    if own and named.startswith(own) and not named[len(own):len(own) + 1].isalnum():
        return owner, name
    return artist, name


def playlist_id(link):
    link = link.strip()
    parts = urlsplit(link if "://" in link else f"https://{link}")
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    found = parse_qs(parts.query).get("list", [""])[0]
    return found if host in ("youtube.com", "music.youtube.com", "youtu.be") and re.fullmatch(r"[\w-]{10,}", found) else ""


def entries(rows):
    found = []
    for row in rows:
        title, channel, link = text(row.get("title")), text(row.get("channel")) or text(row.get("uploader")), https_url(row.get("url"))
        # A video that was removed or hidden stays in the list under a title in square brackets and without a channel.
        if row.get("ie_key") != "Youtube" or not title or not channel:
            continue
        artist, name = song(title, channel)
        if artist and name:
            found.append(Entry(name, artist, link.replace("https://music.youtube.com/", "https://www.youtube.com/")))
    return found


def tracks(link, cancelled=lambda: False):
    """The name of a public playlist and its tracks."""
    number = playlist_id(link)
    if not number:
        raise ImportFailed("Вставьте ссылку на плейлист вида https://www.youtube.com/playlist?list=…")
    try:
        rows = listing(f"https://www.youtube.com/playlist?list={number}", ("url", "title", "channel", "uploader", "ie_key", "playlist_title"),
                       cancelled, "плейлистов YouTube")
    except Refused as error:
        said = str(error).lower()
        if "does not exist" in said:
            raise ImportFailed("YouTube не нашёл такой плейлист. Проверьте ссылку.") from error
        if "unviewable" in said:
            raise ImportFailed("Миксы и личные подборки YouTube без входа не открываются. Сложите треки в обычный открытый плейлист.") from error
        if "private" in said or "sign in" in said or "cookies" in said:
            raise ImportFailed("YouTube просит войти в аккаунт: плейлист закрыт или сервис проверяет, что вы не робот. "
                               "Откройте плейлист для всех или повторите импорт позже.") from error
        raise ImportFailed("Не удалось получить плейлист YouTube. Проверьте интернет или обновите yt-dlp.") from error
    found = entries(rows)
    if not found:
        raise ImportFailed("В плейлисте не найдено открытых видео.")
    # YouTube Music calls an album "Album - Name".
    name = next((text(row.get("playlist_title")) for row in rows if text(row.get("playlist_title"))), "")
    return name.removeprefix("Album - ") or "плейлист", found
