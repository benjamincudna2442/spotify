from flask import Flask, request, jsonify, render_template
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import base64
import re
from datetime import datetime

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
    try:
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            headers=headers,
            data=data
        )
        response.raise_for_status()
        result = response.json()
        return result["access_token"]
    except Exception as e:
        raise Exception("Error fetching Spotify access token: " + str(e))

def get_spotify_track_details(url: str):
    try:
        response = requests.get(f"https://api.fabdl.com/spotify/get?url={url}")
        response.raise_for_status()
        result = response.json()
        return result["result"]
    except Exception as e:
        raise Exception("Error fetching Spotify track details: " + str(e))

def get_download_link(gid: str, track_id: str):
    try:
        response = requests.get(f"https://api.fabdl.com/spotify/mp3-convert-task/{gid}/{track_id}")
        response.raise_for_status()
        result = response.json()
        
        if result["result"]["status"] == 3 and result["result"]["download_url"]:
            return f"https://api.fabdl.com{result['result']['download_url']}"
        else:
            raise Exception("Download not ready or failed")
    except Exception as e:
        raise Exception("Error fetching download link: " + str(e))

def get_track_metadata(track_id):
    try:
        track = sp.track(track_id)
        cover_art = track['album']['images'][0]['url'] if track['album']['images'] else None
        duration_ms = track['duration_ms']
        return {
            'id': track['id'],
            'title': track['name'],
            'artists': ", ".join(artist['name'] for artist in track['artists']),
            'album': track['album']['name'],
            'release_date': track['album']['release_date'],
            'duration': f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}",
            'isrc': track['external_ids'].get('isrc', 'N/A'),
            'cover_art': cover_art
        }
    except Exception:
        return None

def search_spotify(query, limit=5):
    try:
        results = sp.search(q=query, type='track', limit=limit)
        return [(track['name'], ", ".join(artist['name'] for artist in track['artists']), track['id']) for track in results['tracks']['items']]
    except Exception:
        return []

@app.route('/')
def home():
    return render_template('status.html')

@app.route('/sp/dl', methods=['GET'])
def download_track():
    spotify_url = request.args.get('url')
    if not spotify_url or not is_spotify_url(spotify_url):
        return jsonify({
            'status': False,
            'message': 'Valid Spotify track URL required ❌',
            'example': '/sp/dl?url=https://open.spotify.com/track/TRACK_ID'
        }), 400
    
    try:
        track_id = spotify_url.split('/track/')[1].split('?')[0]
        metadata = get_track_metadata(track_id)
        if not metadata:
            return jsonify({
                'status': False,
                'message': 'Failed to fetch metadata ❌'
            }), 500

        track_details = get_spotify_track_details(spotify_url)
        gid = str(track_details["gid"])
        track_id = track_details["id"]
        name = track_details["name"]
        image = track_details["image"]
        artists = track_details["artists"]
        duration_ms = track_details["duration_ms"]

        download_url = get_download_link(gid, track_id)
        
        return jsonify({
            'status': True,
            'title': metadata['title'],
            'artist': metadata['artists'],
            'track_id': track_id,
            'track_url': f"https://open.spotify.com/track/{track_id}",
            'download_url': download_url,
            'album': metadata['album'],
            'release_date': metadata['release_date'],
            'duration': metadata['duration'],
            'isrc': metadata['isrc'],
            'cover_art': metadata['cover_art'],
            'credit': 'Downloaded By @TheSmartDev And API Developer @TheSmartDev Organization github Oceans-11/TheSmartDevs'
        })

    except Exception as e:
        return jsonify({
            'status': False,
            'message': f'Error: {str(e)} ❌'
        }), 500

@app.route('/sp/search', methods=['GET'])
def search_tracks():
    query = request.args.get('q')
    if not query:
        return jsonify({
            'status': False,
            'message': 'Search query required ❌',
            'example': '/sp/search?q=Tomake+Chai'
        }), 400
    
    try:
        tracks = search_spotify(query)
        if not tracks:
            return jsonify({
                'status': False,
                'message': 'No tracks found ❌'
            }), 404

        results = []
        for name, artist, track_id in tracks:
            track_url = f"https://open.spotify.com/track/{track_id}"
            metadata = get_track_metadata(track_id)
            if not metadata:
                continue
                
            results.append({
                'title': name,
                'artist': artist,
                'track_id': track_id,
                'track_url': track_url,
                'album': metadata['album'],
                'release_date': metadata['release_date'],
                'duration': metadata['duration'],
                'isrc': metadata['isrc'],
                'cover_art': metadata['cover_art'],
            })

        return jsonify({
            'status': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'status': False,
            'message': f'Error: {str(e)} ❌'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
