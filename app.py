#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev 
from flask import Flask, request, jsonify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import re
import urllib.parse
import hashlib
import hmac
import math
import time

app = Flask(__name__)

SPOTIFY_CLIENT_ID = 'd2f27b893fb64c3a97242d8a1e46c63c'
SPOTIFY_CLIENT_SECRET = '8d31ddeef0614731be0e6cef6aebaad3'
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_LYRICS_SEO_URL = 'https://spclient.wg.spotify.com/color-lyrics/v2/seo/track/'
SPOTIFY_LYRICS_AUTH_URL = 'https://spclient.wg.spotify.com/color-lyrics/v2/track/'
SPOTIFY_SERVER_TIME = 'https://open.spotify.com/api/server-time'
SPOTIFY_TOKEN_URL = 'https://open.spotify.com/api/token'
SPOTIFY_DC = 'AQAO1j7bPbFcbVh5TbQmwmTd_XFckJhbOipaA0t2BZpViASzI6Qrk1Ty0WviN1K1mmJv_hV7xGVbMPHm4-HAZbs3OXOHSu38Xq7hZ9wqWwvdZwjiWTQmKWLoKxJP1j3kI7-8eWgVZ8TcPxRnXrjP3uDJ9SnzOla_EpxePC74dHa5D4nBWWfFLdiV9bMQuzUex6izb12gCh0tvTt3Xlg'
YTDL_SEARCH = 'https://smartytdl.vercel.app/search'
YTDL_DOWNLOAD = 'https://smartytdl.vercel.app/dl'
HEADERS = {
    'accept': 'application/json',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'origin': 'https://open.spotify.com',
    'referer': 'https://open.spotify.com/',
    'app-platform': 'WebPlayer'
}

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

def generate_totp():
    req = requests.get('https://raw.githubusercontent.com/Thereallo1026/spotify-secrets/refs/heads/main/secrets/secrets.json')
    data = req.json()[-1]
    secret = ''.join(str(ord(c) ^ ((i % 33) + 9)) for i, c in enumerate(data['secret'])).encode('utf-8')
    version = data['version']
    counter = math.floor(time.time() / 30)
    counter_bytes = counter.to_bytes(8, byteorder='big')
    h = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    binary = ((h[offset] & 0x7F) << 24 | (h[offset + 1] & 0xFF) << 16 | (h[offset + 2] & 0xFF) << 8 | (h[offset + 3] & 0xFF))
    return str(binary % 1000000).zfill(6), version

def get_spotify_token(sp_dc):
    session = requests.Session()
    session.cookies.set('sp_dc', sp_dc)
    session.headers.update(HEADERS)
    server_time = session.get(SPOTIFY_SERVER_TIME).json()['serverTime'] * 1000
    totp, version = generate_totp()
    params = {'reason': 'init', 'productType': 'web-player', 'totp': totp, 'totpVer': str(version), 'ts': str(server_time)}
    response = session.get(SPOTIFY_TOKEN_URL, params=params)
    if response.status_code == 200:
        return response.json()['accessToken']
    raise Exception('Failed to authenticate with Spotify')

def parse_track_id(input_str):
    if re.match(r'^[a-zAZ0-9]{22}$', input_str):
        return input_str
    match = re.search(r'spotify\.com/track/([a-zA-Z0-9]{22})', input_str)
    if match:
        return match.group(1)
    raise ValueError('Invalid Spotify track ID or URL')

def fetch_track_info(track_id):
    track = sp.track(track_id)
    return {
        'id': track['id'],
        'title': track['name'],
        'artists': [{'name': a['name'], 'id': a['id']} for a in track['artists']],
        'album': {
            'name': track['album']['name'],
            'id': track['album']['id'],
            'release_date': track['album']['release_date']
        },
        'duration': f"{track['duration_ms'] // 60000}:{(track['duration_ms'] % 60000) // 1000:02d}",
        'cover': track['album']['images'][0]['url'] if track['album']['images'] else None,
        'url': track['external_urls']['spotify'],
        'isrc': track['external_ids'].get('isrc', 'N/A')
    }

def fetch_lyrics(track_id, sp_dc, market='BD'):
    session = requests.Session()
    session.headers.update(HEADERS)
    params = {'format': 'json', 'market': market}
    response = session.get(f"{SPOTIFY_LYRICS_SEO_URL}{track_id}", params=params)
    if response.status_code == 200:
        return response.json()
    session.headers['authorization'] = f"Bearer {get_spotify_token(sp_dc)}"
    response = session.get(f"{SPOTIFY_LYRICS_AUTH_URL}{track_id}", params=params)
    return response.json() if response.status_code == 200 else {'error': f'Lyrics not available (status: {response.status_code})'}

def format_lyrics(lyrics_data, format_type):
    if not lyrics_data or 'lyrics' not in lyrics_data or not lyrics_data['lyrics'].get('lines'):
        return ['No lyrics available'] if 'error' not in lyrics_data else [lyrics_data['error']]
    lines = lyrics_data['lyrics']['lines']
    if format_type == 'synchronized':
        return [f"[{line['startTimeMs']}] {line['words']}" for line in lines if line['words']]
    return [line['words'] for line in lines if line['words']]

def youtube_search(title, artists):
    query = urllib.parse.quote(f"{title} {', '.join(a['name'] for a in artists)}")
    response = requests.get(f"{YTDL_SEARCH}?q={query}").json()
    return response['result'][0]['link'] if response.get('result') else None

def youtube_downloads(youtube_url):
    response = requests.get(f"{YTDL_DOWNLOAD}?url={youtube_url}").json()
    if not response.get('success'):
        return [], None
    audio = [{
        'id': str(m['formatId']),
        'label': m['label'],
        'url': m['url'],
        'bitrate': m['bitrate'],
        'ext': m['extension']
    } for m in response['medias'] if m['type'] == 'audio']
    video = [{
        'id': str(m['formatId']),
        'label': m['label'],
        'url': m['url'],
        'resolution': f"{m['width']}x{m['height']}" if m.get('width') and m.get('height') else 'N/A',
        'ext': m['extension']
    } for m in response['medias'] if m['type'] == 'video' and m['extension'] == 'mp4']
    best_video = None
    for res in [(1920, 1080), (1280, 720), (640, 360)]:
        for v in video:
            if v['resolution'] == f"{res[0]}x{res[1]}":
                best_video = v
                break
        if best_video:
            break
    return audio, best_video

@app.route('/')
def index():
    return jsonify({'status': 'running', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'})

@app.route('/sp/lyrics', methods=['GET'])
def lyrics():
    track_id = request.args.get('id')
    track_url = request.args.get('url')
    format_type = request.args.get('format', 'plain')
    sp_dc = request.args.get('sp_dc', SPOTIFY_DC)
    market = request.args.get('market', 'BD')
    if not track_id and not track_url:
        return jsonify({'status': 'error', 'message': 'Track ID or URL required', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 400
    try:
        track_id = parse_track_id(track_id or track_url)
        track_info = fetch_track_info(track_id)
        lyrics_data = fetch_lyrics(track_id, sp_dc, market)
        lyrics_text = format_lyrics(lyrics_data, format_type)
        return jsonify({
            'status': 'success',
            'track': track_info,
            'lyrics': lyrics_text,
            'format': format_type,
            'owner': '@ISmartCoder',
            'updates': '@TheSmartDevs'
        })
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e), 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 500

@app.route('/sp/dl', methods=['GET'])
def download():
    track_url = request.args.get('url')
    if not track_url or not re.match(r'^https://open\.spotify\.com/track/[a-zA-Z0-9]+', track_url):
        return jsonify({'status': 'error', 'message': 'Valid Spotify URL required', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 400
    try:
        track_id = parse_track_id(track_url)
        track_info = fetch_track_info(track_id)
        youtube_url = youtube_search(track_info['title'], track_info['artists'])
        if not youtube_url:
            return jsonify({'status': 'error', 'message': 'No YouTube video found', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 404
        audio_formats, best_video = youtube_downloads(youtube_url)
        return jsonify({
            'status': 'success',
            'track': track_info,
            'audio_formats': audio_formats,
            'video_format': best_video,
            'owner': '@ISmartCoder',
            'updates': '@TheSmartDevs'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 500

@app.route('/sp/search', methods=['GET'])
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({'status': 'error', 'message': 'Query required', 'example': '/sp/search?q=Song+Name', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 400
    try:
        results = sp.search(q=query, type='track', limit=5)
        tracks = results['tracks']['items']
        if not tracks:
            return jsonify({'status': 'error', 'message': 'No tracks found', 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 404
        response = [{
            'title': t['name'],
            'artist': ', '.join(a['name'] for a in t['artists']),
            'id': t['id'],
            'url': t['external_urls']['spotify'],
            'album': t['album']['name'],
            'release_date': t['album']['release_date'],
            'duration': f"{t['duration_ms'] // 60000}:{(t['duration_ms'] % 60000) // 1000:02d}",
            'cover': t['album']['images'][0]['url'] if t['album']['images'] else None
        } for t in tracks]
        return jsonify({'status': 'success', 'results': response, 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'owner': '@ISmartCoder', 'updates': '@TheSmartDevs'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
