from flask import Flask, request, jsonify
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import re
import urllib.parse

app = Flask(__name__)

SPOTIFY_CLIENT_ID = 'd2f27b893fb64c3a97242d8a1e46c63c'
SPOTIFY_CLIENT_SECRET = '8d31ddeef0614731be0e6cef6aebaad3'
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/api/token'
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

def parse_track_id(input_str):
    if re.match(r'^[a-zA-Z0-9]{22}$', input_str):
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
