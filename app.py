from flask import Flask, request, jsonify, render_template
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import base64
import re
import urllib.parse

app = Flask(__name__)
CLIENT_ID = 'd2f27b893fb64c3a97242d8a1e46c63c'
CLIENT_SECRET = '8d31ddeef0614731be0e6cef6aebaad3'
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))

def is_spotify_url(input_string):
    return bool(re.match(r'^https://open\.spotify\.com/track/[a-zA-Z0-9]+', input_string))

def get_spotify_access_token():
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_b64}"
    }
    data = {"grant_type": "client_credentials"}
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    response.raise_for_status()
    result = response.json()
    return result["access_token"]

def get_track_metadata(track_id):
    track = sp.track(track_id)
    cover_art = track['album']['images'][0]['url'] if track['album']['images'] else None
    return {
        'title': track['name'],
        'artists': ", ".join(artist['name'] for artist in track['artists']),
        'album': track['album']['name'],
        'cover_art': cover_art,
        'track_id': track['id'],
        'track_url': f"https://open.spotify.com/track/{track['id']}",
        'release_date': track['album']['release_date'],
        'duration': f"{track['duration_ms'] // 60000}:{(track['duration_ms'] % 60000) // 1000:02d}",
        'isrc': track['external_ids'].get('isrc', 'N/A')
    }

def search_youtube(track_name, artists):
    query = urllib.parse.quote(f"{track_name} {artists}")
    response = requests.get(f"https://smartytdl.vercel.app/search?q={query}")
    response.raise_for_status()
    result = response.json()
    if result.get("result") and len(result["result"]) > 0:
        return result["result"][0]["link"]
    raise Exception("No YouTube video found")

def get_youtube_download_urls(youtube_url):
    response = requests.get(f"https://smartytdl.vercel.app/dl?url={youtube_url}")
    response.raise_for_status()
    result = response.json()
    if not result.get("success"):
        raise Exception("Failed to fetch download links")
    audio_formats = [
        {
            "format_id": media["formatId"],
            "label": media["label"],
            "url": media["url"],
            "bitrate": media["bitrate"],
            "extension": media["extension"]
        }
        for media in result["medias"]
        if media["type"] == "audio"
    ]
    return audio_formats

@app.route('/')
def home():
    return render_template('status.html')

@app.route('/sp/dl', methods=['GET'])
def download_track():
    spotify_url = request.args.get('url')
    if not spotify_url or not is_spotify_url(spotify_url):
        return jsonify({
            'status': 'error',
            'message': 'Valid Spotify track URL required',
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        }), 400
    try:
        track_id = spotify_url.split('/track/')[1].split('?')[0]
        metadata = get_track_metadata(track_id)
        if not metadata:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch metadata',
                'api_owner': '@ISmartCoder',
                'api_updates': '@TheSmartDevs'
            }), 500
        youtube_url = search_youtube(metadata['title'], metadata['artists'])
        audio_formats = get_youtube_download_urls(youtube_url)
        return jsonify({
            'status': 'success',
            'name': metadata['title'],
            'album': metadata['album'],
            'artist': metadata['artists'],
            'cover_url': metadata['cover_art'],
            'track_id': metadata['track_id'],
            'track_url': metadata['track_url'],
            'release_date': metadata['release_date'],
            'duration': metadata['duration'],
            'isrc': metadata['isrc'],
            'download_urls': audio_formats,
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        }), 500

@app.route('/sp/search', methods=['GET'])
def search_tracks():
    query = request.args.get('q')
    if not query:
        return jsonify({
            'status': 'error',
            'message': 'Search query required',
            'example': '/sp/search?q=Tomake+Chai',
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        }), 400
    try:
        results = sp.search(q=query, type='track', limit=5)
        tracks = [(track['name'], ", ".join(artist['name'] for artist in track['artists']), track['id']) for track in results['tracks']['items']]
        if not tracks:
            return jsonify({
                'status': 'error',
                'message': 'No tracks found',
                'api_owner': '@ISmartCoder',
                'api_updates': '@TheSmartDevs'
            }), 404
        results_list = []
        for name, artist, track_id in tracks:
            metadata = get_track_metadata(track_id)
            if not metadata:
                continue
            results_list.append({
                'title': name,
                'artist': artist,
                'track_id': track_id,
                'track_url': f"https://open.spotify.com/track/{track_id}",
                'album': metadata['album'],
                'release_date': metadata['release_date'],
                'duration': metadata['duration'],
                'isrc': metadata['isrc'],
                'cover_art': metadata['cover_art']
            })
        return jsonify({
            'status': 'success',
            'results': results_list,
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'api_owner': '@ISmartCoder',
            'api_updates': '@TheSmartDevs'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
