"""
api/routes.py
API-Routen für die MovieWeb-Anwendung.
API routes for the MovieWeb application.
"""

from flask import Blueprint, jsonify, request, current_app
import requests # Hinzugefügt für OMDb-Anfrage
import os # Hinzugefügt für os.getenv
from dotenv import load_dotenv # Hinzugefügt für load_dotenv
from datamanager.sqlite_data_manager import SQLiteDataManager
from functools import wraps
import time
from models import User, Movie, Comment

# Umgebungsvariablen laden (falls noch nicht global geschehen oder zur Sicherheit)
load_dotenv()

# Blueprint für API-Routen erstellen
# Create blueprint for API routes
api = Blueprint('api', __name__)

# DataManager-Instanz
data_manager = SQLiteDataManager()

# Einfacher Cache für API-Antworten
# Simple cache for API responses
cache = {}
CACHE_TIMEOUT = 300  # 5 Minuten / 5 minutes

def cache_response(timeout=CACHE_TIMEOUT):
    """
    Decorator für das Caching von API-Antworten.
    Decorator for caching API responses.

    Args:
        timeout (int): Cache-Timeout in Sekunden.
                      Cache timeout in seconds.

    Returns:
        function: Decorierte Funktion.
                 Decorated function.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Cache-Key aus Funktionsname und Argumenten erstellen
            # Create cache key from function name and arguments
            cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            # Prüfen ob Antwort im Cache ist und noch gültig
            # Check if response is in cache and still valid
            if cache_key in cache:
                timestamp, response = cache[cache_key]
                if time.time() - timestamp < timeout:
                    return response
            
            # Funktion ausführen und Ergebnis cachen
            # Execute function and cache result
            response = f(*args, **kwargs)
            cache[cache_key] = (time.time(), response)
            return response
        return decorated_function
    return decorator

def handle_api_error(f):
    """
    Decorator für die Fehlerbehandlung von API-Routen.
    Decorator for error handling of API routes.

    Args:
        f (function): Zu dekorierende Funktion.
                     Function to decorate.

    Returns:
        function: Decorierte Funktion.
                 Decorated function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"API Error: {str(e)}")
            return jsonify({
                'error': 'Internal Server Error',
                'message': str(e)
            }), 500
    return decorated_function

@api.route('/users')
@handle_api_error
@cache_response()
def get_users():
    """
    Gibt eine Liste aller Benutzer zurück.
    Returns a list of all users.

    Returns:
        JSON: Liste der Benutzer mit ID, Name und Anzahl der Filme.
              List of users with ID, name and movie count.
    """
    users = User.query.all()
    return jsonify({
        'users': [{
            'id': user.id,
            'name': user.name,
            'movie_count': len(user.movies)
        } for user in users]
    })

@api.route('/users/<int:user_id>')
@handle_api_error
@cache_response()
def get_user(user_id):
    """
    Gibt Details eines bestimmten Benutzers zurück.
    Returns details of a specific user.

    Args:
        user_id (int): ID des Benutzers.
                      ID of the user.

    Returns:
        JSON: Benutzerdetails mit Filmen.
              User details with movies.

    Raises:
        404: Wenn der Benutzer nicht gefunden wurde.
             If the user was not found.
    """
    user = User.query.get_or_404(user_id)
    return jsonify({
        'user': {
            'id': user.id,
            'name': user.name,
            'movies': [{
                'id': movie.id,
                'title': movie.title,
                'director': movie.director,
                'year': movie.year,
                'rating': movie.rating,
                'poster_url': movie.poster_url
            } for movie in user.movies]
        }
    })

@api.route('/users/<int:user_id>/movies')
@handle_api_error
@cache_response()
def get_user_movies(user_id):
    """
    Gibt alle Filme eines Benutzers zurück.
    Returns all movies of a user.

    Args:
        user_id (int): ID des Benutzers.
                      ID of the user.

    Returns:
        JSON: Liste der Filme des Benutzers.
              List of user's movies.

    Raises:
        404: Wenn der Benutzer nicht gefunden wurde.
             If the user was not found.
    """
    user = User.query.get_or_404(user_id)
    return jsonify({
        'movies': [{
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'rating': movie.rating,
            'poster_url': movie.poster_url
        } for movie in user.movies]
    })

@api.route('/movies')
@handle_api_error
@cache_response()
def get_movies():
    """
    Gibt eine Liste aller Filme zurück.
    Returns a list of all movies.

    Returns:
        JSON: Liste aller Filme.
              List of all movies.
    """
    movies = Movie.query.all()
    return jsonify({
        'movies': [{
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'rating': movie.rating,
            'poster_url': movie.poster_url
        } for movie in movies]
    })

@api.route('/movies/<int:movie_id>')
@handle_api_error
@cache_response()
def get_movie(movie_id):
    """
    Gibt Details eines bestimmten Films zurück.
    Returns details of a specific movie.

    Args:
        movie_id (int): ID des Films.
                       ID of the movie.

    Returns:
        JSON: Filmdetails mit Kommentaren.
              Movie details with comments.

    Raises:
        404: Wenn der Film nicht gefunden wurde.
             If the movie was not found.
    """
    movie = Movie.query.get_or_404(movie_id)
    return jsonify({
        'movie': {
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'rating': movie.rating,
            'poster_url': movie.poster_url,
            'plot': movie.plot,
            'runtime': movie.runtime,
            'awards': movie.awards,
            'languages': movie.languages,
            'genre': movie.genre,
            'actors': movie.actors,
            'writer': movie.writer,
            'country': movie.country,
            'metascore': movie.metascore,
            'rated': movie.rated,
            'imdb_id': movie.imdb_id,
            'comments': [{
                'id': comment.id,
                'text': comment.text,
                'user': comment.user.name,
                'created_at': comment.created_at.isoformat()
            } for comment in movie.comments]
        }
    })

@api.route('/movies/<int:movie_id>/comments')
@handle_api_error
@cache_response()
def get_movie_comments(movie_id):
    """
    Gibt alle Kommentare zu einem Film zurück.
    Returns all comments for a movie.

    Args:
        movie_id (int): ID des Films.
                       ID of the movie.

    Returns:
        JSON: Liste der Kommentare zum Film.
              List of comments for the movie.

    Raises:
        404: Wenn der Film nicht gefunden wurde.
             If the movie was not found.
    """
    movie = Movie.query.get_or_404(movie_id)
    return jsonify({
        'comments': [{
            'id': comment.id,
            'text': comment.text,
            'user': comment.user.name,
            'created_at': comment.created_at.isoformat()
        } for comment in movie.comments]
    })

@api.route('/users/<int:user_id>/movies', methods=['POST'])
def add_movie_api(user_id):
    """
    POST /api/users/<user_id>/movies
    Fügt einen neuen Film zur Favoritenliste eines Benutzers hinzu.
    Adds a new movie to a user's favorites.
    Erwartet JSON mit 'title', 'director', 'year', 'rating', optional 'poster_url'.
    Expects JSON with 'title', 'director', 'year', 'rating', optional 'poster_url'.
    """
    data = request.get_json() or {}
    title = data.get('title')
    director = data.get('director')
    year = data.get('year')
    rating = data.get('rating')
    poster_url = data.get('poster_url')
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    try:
        movie = data_manager.add_movie(user_id, title, director, year, rating, poster_url)
        if movie:
            return jsonify({'message': 'Movie added', 'id': movie.id}), 201
        else:
            return jsonify({'error': 'Could not add movie'}), 400
    except Exception as e:
        current_app.logger.error(f"Error in API add_movie: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@api.route('/omdb_proxy')
@handle_api_error # Fehlerbehandlung nutzen
# Kein Caching hier, da es nur ein Proxy ist und OMDb selbst ggf. schon cacht oder Daten sich ändern können (selten)
def omdb_proxy():
    """
    Leitet eine Suchanfrage an die OMDb-API weiter und gibt deren JSON-Antwort zurück.
    Erwartet 'title' als Query-Parameter.
    Optional: 'year' als Query-Parameter.
    """
    title = request.args.get('title')
    year = request.args.get('year') # Optionales Jahr

    if not title:
        return jsonify({'error': 'Parameter "title" is required'}), 400

    omdb_api_key = os.getenv('OMDB_API_KEY')
    if not omdb_api_key:
        current_app.logger.error("OMDB_API_KEY nicht in Umgebungsvariablen gefunden.")
        return jsonify({'error': 'OMDb API key not configured on server'}), 500

    params = {
        'apikey': omdb_api_key,
        't': title
    }
    if year:
        params['y'] = year

    try:
        response = requests.get('http://www.omdbapi.com/', params=params, timeout=10)
        response.raise_for_status() # HTTP-Fehler auslösen
        # OMDb gibt manchmal HTML zurück bei Fehlern, sicherstellen, dass es JSON ist
        if 'application/json' not in response.headers.get('Content-Type', ''):
             current_app.logger.error(f"OMDb hat kein JSON zurückgegeben. Status: {response.status_code}, Inhalt: {response.text[:200]}")
             return jsonify({'Error': 'OMDb did not return JSON.', 'Response': 'False'}), response.status_code
        
        return jsonify(response.json()) # Direkte JSON-Antwort von OMDb weiterleiten
    except requests.exceptions.Timeout:
        current_app.logger.error(f"OMDb API request timed out for title: {title}")
        return jsonify({'Error': 'OMDb request timed out', 'Response': 'False'}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"OMDb API request failed for title: {title}, Error: {e}")
        # Versuche, den Statuscode der OMDb-Antwort zu verwenden, falls verfügbar
        status_code = response.status_code if 'response' in locals() and hasattr(response, 'status_code') else 500
        return jsonify({'Error': str(e), 'Response': 'False'}), status_code

@api.route('/check_or_create_movie_by_imdb', methods=['POST'])
@handle_api_error
def check_or_create_movie_by_imdb():
    """
    Prüft, ob ein Film mit der gegebenen imdb_id existiert.
    Wenn nicht, wird er global hinzugefügt, basierend auf den übergebenen OMDb-Daten.
    Gibt den Status ('exists' oder 'created') und die movie_id zurück.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    imdb_id = data.get('imdbID') # OMDb liefert 'imdbID'
    if not imdb_id:
        return jsonify({'success': False, 'message': 'imdbID is required'}), 400

    # Versuche, den Film anhand der IMDb-ID zu finden
    movie = data_manager.get_movie_by_imdb_id(imdb_id)
    if movie:
        return jsonify({'success': True, 'status': 'exists', 'movie_id': movie.id}), 200
    else:
        # Film existiert nicht, also global hinzufügen
        # Die 'data' sollten die vollständigen OMDb-Daten sein
        new_movie = data_manager.add_movie_globally(movie_data=data)
        if new_movie:
            return jsonify({'success': True, 'status': 'created', 'movie_id': new_movie.id}), 201
        else:
            # Fehler beim Hinzufügen wurde bereits im DataManager geloggt
            return jsonify({'success': False, 'message': 'Failed to create new movie globally.'}), 500