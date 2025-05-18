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
import traceback

# Umgebungsvariablen laden (falls noch nicht global geschehen oder zur Sicherheit)
load_dotenv()
OMDB_API_KEY = os.getenv('OMDB_API_KEY') # Ensure OMDB_API_KEY is loaded here / Sicherstellen, dass OMDB_API_KEY hier geladen wird

# Blueprint für API-Routen erstellen
# Create blueprint for API routes
api = Blueprint('api', __name__)

# DataManager-Instanz
data_manager = SQLiteDataManager()

# Einfacher Cache für API-Antworten
# Simple cache for API responses
cache = {}
CACHE_TIMEOUT = 300  # 5 minutes / 5 Minuten

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
            # Log API error for server-side diagnostics.
            # Logge API-Fehler für serverseitige Diagnose.
            current_app.logger.error(f"API Error in endpoint '{f.__name__}': {str(e)} / API-Fehler im Endpunkt '{f.__name__}': {str(e)}", exc_info=True)
            # traceback.print_exc() # Alternative for more detailed local debugging / Alternative für detaillierteres lokales Debugging
            return jsonify({
                'success': False, # Standardized field / Standardisiertes Feld
                'message': 'An internal server error occurred.', # User-friendly message / Benutzerfreundliche Nachricht
                # 'error_details': str(e) # Potentially include for dev/staging, remove for production / Potenziell für Dev/Staging einfügen, für Produktion entfernen
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
    users_from_db = data_manager.get_all_users()
    users_list = []
    for user_obj in users_from_db:
        # Die Logik für 'movie_count' bleibt hier, da sie spezifisch für diese API-Antwort ist.
        # data_manager.get_all_users() liefert reine User-Objekte.
        # Um movie_count effizient zu bekommen, müsste man UserMovie-Relationen laden.
        # Alternativ könnte man die UserMovie-Relation in User vorladen (lazy='joined' oder subquery)
        # oder eine spezifischere Methode im DataManager erstellen.
        # Für jetzt belassen wir es bei len(user_obj.movies) direkt auf dem Objekt.
        users_list.append({
            'id': user_obj.id,
            'name': user_obj.name,
            'movie_count': len(user_obj.movies) # Requires user.movies to be loaded
        })
    current_app.logger.info(f"Successfully retrieved {len(users_list)} users for /api/users endpoint.")
    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'users': users_list
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

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
    user = data_manager.get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404 # Standardized error / Standardisierter Fehler
    
    # Hole die Filme des Benutzers separat, um die Datenstruktur beizubehalten
    # user.movies wird hier direkt verwendet, was okay ist, wenn User-Objekt vom DM kommt
    # und die Relation geladen ist (Standard ist lazy loading)
    user_movies_data = [{
        'id': um_relation.movie.id, # Annahme: user.movies ist eine Liste von UserMovie Objekten
        'title': um_relation.movie.title,
        'director': um_relation.movie.director,
        'year': um_relation.movie.year,
        'community_rating': um_relation.movie.community_rating,
        'community_rating_count': um_relation.movie.community_rating_count,
        'poster_url': um_relation.movie.poster_url,
        'user_rating': um_relation.user_rating # Hinzufügen der persönlichen Bewertung
    } for um_relation in user.movies] # user.movies ist die UserMovie Collection

    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'user': {
            'id': user.id,
            'name': user.name,
            'movies': user_movies_data
        }
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

@api.route('/users/<int:user_id>/movies')
@handle_api_error
@cache_response()
def get_user_movies(user_id):
    """
    Gibt alle Filme eines Benutzers zurück, inklusive persönlicher Bewertung.
    Returns all movies of a user, including their personal rating.

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
    user = data_manager.get_user_by_id(user_id) # Erst Benutzer prüfen
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404 # Standardized error / Standardisierter Fehler

    user_movie_relations = data_manager.get_user_movie_relations(user_id)
    
    movies_data = []
    for relation in user_movie_relations:
        movies_data.append({
            'id': relation.movie.id,
            'title': relation.movie.title,
            'director': relation.movie.director,
            'year': relation.movie.year,
            'community_rating': relation.movie.community_rating,
            'community_rating_count': relation.movie.community_rating_count,
            'poster_url': relation.movie.poster_url,
            'user_rating': relation.user_rating # Persönliche Bewertung des Nutzers
        })

    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'user_id': user.id, # Include user_id for context / user_id für Kontext einfügen
        'user_name': user.name, # Include user_name for context / user_name für Kontext einfügen
        'movies': movies_data
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

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
    movies_from_db = data_manager.get_all_movies()
    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'movies': [{
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'community_rating': movie.community_rating,
            'community_rating_count': movie.community_rating_count,
            'poster_url': movie.poster_url
        } for movie in movies_from_db]
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

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
    movie = data_manager.get_movie_by_id(movie_id)
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'}), 404 # Standardized error / Standardisierter Fehler

    # Kommentare separat laden, um die Struktur beizubehalten
    comments_from_db = data_manager.get_comments_for_movie(movie_id)
    comments_data = [{
        'id': c.id,
        'text': c.text,
        'user': c.user.name, # Annahme: c.user Relation ist geladen
        'created_at': c.created_at.isoformat(),
        'likes_count': c.likes_count
    } for c in comments_from_db]

    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'movie': {
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'community_rating': movie.community_rating,
            'community_rating_count': movie.community_rating_count,
            'poster_url': movie.poster_url,
            'plot': movie.plot,
            'runtime': movie.runtime,
            'awards': movie.awards,
            'language': movie.language,
            'genre': movie.genre,
            'actors': movie.actors,
            'writer': movie.writer,
            'country': movie.country,
            'metascore': movie.metascore,
            'rated_omdb': movie.rated_omdb,
            'imdb_id': movie.imdb_id,
            'comments': comments_data
        }
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

@api.route('/movies/<int:movie_id>/comments')
@handle_api_error
@cache_response()
def get_movie_comments(movie_id):
    """
    Gibt alle Kommentare für einen bestimmten Film zurück.
    Returns all comments for a specific movie.

    Args:
        movie_id (int): ID des Films.
                       ID of the movie.

    Returns:
        JSON: Liste der Kommentare.
              List of comments.

    Raises:
        404: Wenn der Film nicht gefunden wurde.
             If the movie was not found.
    """
    # Sicherstellen, dass der Film existiert, bevor Kommentare geladen werden.
    # data_manager.get_comments_for_movie prüft dies bereits intern und gibt ggf. eine leere Liste zurück.
    # Wenn hier ein 404 gewünscht ist, falls der Film nicht existiert, muss der Film zuerst geladen werden.
    movie = data_manager.get_movie_by_id(movie_id)
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'}), 404 # Standardized error / Standardisierter Fehler

    comments_from_db = data_manager.get_comments_for_movie(movie_id)
    comments_data = [{
        'id': c.id,
        'text': c.text,
        'user': c.user.name, # Annahme: c.user Relation ist geladen
        'created_at': c.created_at.isoformat(),
        'likes_count': c.likes_count
    } for c in comments_from_db]
    
    return jsonify({
        'success': True, # Added for consistency / Für Konsistenz hinzugefügt
        'movie_id': movie_id, # Include movie_id for context / movie_id für Kontext einfügen
        'comments': comments_data
    }), 200 # Explicitly set 200 OK / Explizit 200 OK setzen

@api.route('/users/<int:user_id>/movies', methods=['POST'])
@handle_api_error # Generic error handling / Generische Fehlerbehandlung
def add_movie_api(user_id):
    """
    POST /api/users/<user_id>/movies
    Fügt einen neuen Film zur Favoritenliste eines Benutzers hinzu.
    Adds a new movie to a user's favorites list.
    Erwartet JSON mit 'title', optional 'director', 'year', 'rating', 'poster_url', 'imdb_id'.
    Expects JSON with 'title', optional 'director', 'year', 'rating', 'poster_url', 'imdb_id'.
    """
    # Check if user exists first
    # Zuerst prüfen, ob der Benutzer existiert
    user = data_manager.get_user_by_id(user_id)
    if not user:
        current_app.logger.warning(f"Attempt to add movie for non-existent user_id: {user_id}")
        return jsonify({'success': False, 'message': 'Benutzer nicht gefunden.'}), 404

    data = request.get_json() or {}
    title = data.get('title')
    director = data.get('director')
    year_str = data.get('year') # Year might be a string from JSON / Jahr könnte ein String aus JSON sein
    rating_str = data.get('rating') # Rating might be a string / Rating könnte ein String sein
    poster_url = data.get('poster_url')
    imdb_id = data.get('imdb_id') # Added imdb_id to be passed to data_manager
    # Fields from OMDb for a potentially new global movie, if imdb_id is provided and movie is not yet global
    # Felder von OMDb für einen potenziell neuen globalen Film, falls imdb_id angegeben ist und der Film noch nicht global ist
    plot = data.get('plot')
    runtime = data.get('runtime')
    awards = data.get('awards')
    languages = data.get('language') # OMDb uses 'Language' / OMDb verwendet 'Language'
    genre = data.get('genre')
    actors = data.get('actors')
    writer = data.get('writer')
    country = data.get('country')
    metascore = data.get('metascore')
    rated_omdb = data.get('rated') # OMDb uses 'Rated' / OMDb verwendet 'Rated'
    omdb_rating_for_community_str = data.get('omdb_initial_rating_5_star') # e.g. from a previous OMDb lookup, scaled to 5 stars / z.B. von einer vorherigen OMDb-Abfrage, auf 5 Sterne skaliert

    if not title:
        return jsonify({'success': False, 'message': 'Titel ist erforderlich.'}), 400

    year = None
    if year_str:
        try:
            year = int(year_str)
        except ValueError:
            return jsonify({'success': False, 'message': 'Ungültiges Jahresformat. Muss eine ganze Zahl sein.'}), 400

    rating = None # User's personal rating for the movie / Persönliche Bewertung des Benutzers für den Film
    if rating_str is not None: 
        try:
            rating = float(rating_str)
            if not (0 <= rating <= 5):
                 return jsonify({'success': False, 'message': 'Bewertung muss zwischen 0 und 5 liegen.'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Ungültiges Bewertungsformat. Muss eine Zahl sein.'}), 400
    
    omdb_rating_for_community_param = None
    if omdb_rating_for_community_str:
        try:
            omdb_rating_for_community_param = float(omdb_rating_for_community_str)
            if not (0 <= omdb_rating_for_community_param <= 5):
                omdb_rating_for_community_param = None # Reset if invalid / Bei Ungültigkeit zurücksetzen
        except ValueError:
            omdb_rating_for_community_param = None # Ignore if not a valid float / Bei ungültigem Float ignorieren

    # Call data_manager.add_movie, which handles both adding the movie globally (if new and OMDb data provided)
    # and linking it to the user. It also updates/calculates community rating.
    # Rufe data_manager.add_movie auf, das sowohl das globale Hinzufügen des Films (falls neu und OMDb-Daten vorhanden)
    # als auch die Verknüpfung mit dem Benutzer übernimmt. Es aktualisiert/berechnet auch das Community-Rating.
    user_movie_link_object = data_manager.add_movie(
        user_id=user_id, 
        title=title, 
        director=director, 
        year=year, 
        user_specific_rating=rating, # Pass user's rating here / Hier die Bewertung des Benutzers übergeben
        poster_url=poster_url, 
        imdb_id=imdb_id,
        plot=plot,
        runtime=runtime,
        awards=awards,
        languages=languages,
        genre=genre,
        actors=actors,
        writer=writer,
        country=country,
        metascore=metascore,
        rated=rated_omdb,
        omdb_rating_for_community=omdb_rating_for_community_param # This is the initial 0-5 star OMDb rating for community calculation
                                                                # Dies ist das initiale 0-5 Sterne OMDb-Rating für die Community-Berechnung
    )
    
    if user_movie_link_object and user_movie_link_object.movie:
        current_app.logger.info(f"Movie {user_movie_link_object.movie.id} ('{title}') successfully added to user {user_id}'s list.")
        return jsonify({
            'success': True,
            'message': 'Film erfolgreich zur Benutzerliste hinzugefügt.',
            'movie_id': user_movie_link_object.movie.id,
            'user_movie_id': user_movie_link_object.id # ID of the UserMovie link / ID der UserMovie-Verknüpfung
        }), 201
    else:
        # Specific error should be logged by data_manager.add_movie
        # data_manager.add_movie returns None if movie not found (even after trying OMDb) or other critical errors.
        # Or if the user_movie link could not be created (e.g. already exists and not updatable by this simple add)
        # Ein spezifischer Fehler sollte von data_manager.add_movie geloggt werden.
        # data_manager.add_movie gibt None zurück, wenn der Film nicht gefunden wurde (auch nach OMDb-Versuch) oder andere kritische Fehler auftreten.
        # Oder wenn die UserMovie-Verknüpfung nicht erstellt werden konnte (z.B. existiert bereits und ist durch dieses einfache Hinzufügen nicht aktualisierbar)
        current_app.logger.warning(f"Could not add movie '{title}' for user {user_id}. data_manager.add_movie returned None.")
        return jsonify({
            'success': False, 
            'message': 'Film konnte nicht hinzugefügt werden. Möglicherweise existiert er bereits in der Liste oder ein interner Fehler ist aufgetreten.'
        }), 409 # 409 Conflict is a good general status if it might already exist, or 400/500 for other issues.
                 # 409 Conflict ist ein guter allgemeiner Status, wenn es möglicherweise bereits existiert, oder 400/500 für andere Probleme.

@api.route('/omdb_proxy')
@handle_api_error # Use error handling / Fehlerbehandlung nutzen
# No caching here, as it's just a proxy and OMDb itself might cache or data could change (rarely)
# Kein Caching hier, da es nur ein Proxy ist und OMDb selbst ggf. schon cacht oder Daten sich ändern können (selten)
def omdb_proxy():
    """
    Proxies OMDb API requests to avoid exposing the API key on the client-side.
    Expects 'title' or 'imdb_id' as query parameters.

    Leitet OMDb-API-Anfragen weiter, um den API-Schlüssel nicht clientseitig preiszugeben.
    Erwartet 'title' oder 'imdb_id' als Query-Parameter.

    Query Parameters:
        title (str, optional): Movie title to search for. / Zu suchender Filmtitel.
        imdb_id (str, optional): IMDb ID to search for. / Zu suchende IMDb-ID.
        year (str, optional): Year of release for disambiguation. / Erscheinungsjahr zur Unterscheidung.
        plot (str, optional): 'short' or 'full' for plot length. / 'short' oder 'full' für die Handlungslänge.

    Returns:
        JSON: The response from OMDb API or an error message.
              Die Antwort von der OMDb-API oder eine Fehlermeldung.
    """
    if not OMDB_API_KEY:
        # Log error if OMDb API key is not configured.
        # Logge Fehler, wenn der OMDb-API-Schlüssel nicht konfiguriert ist.
        current_app.logger.error("OMDb API key is not configured on the server for the proxy.")
        return jsonify({'success': False, 'message': 'OMDb API key not configured on server.'}), 503

    title = request.args.get('title')
    imdb_id = request.args.get('imdb_id')
    year = request.args.get('year')
    plot = request.args.get('plot', 'short') # Default to short plot / Standardmäßig kurze Handlung

    if not title and not imdb_id:
        return jsonify({'success': False, 'message': 'Missing query parameter: title or imdb_id required.'}), 400

    params = {
        'apikey': OMDB_API_KEY,
        'plot': plot
    }
    if title:
        params['t'] = title
    if imdb_id:
        params['i'] = imdb_id
    if year:
        params['y'] = year
    
    # Log OMDb proxy request.
    # Logge OMDb-Proxy-Anfrage.
    current_app.logger.info(f"OMDb Proxy Request: {params}")

    try:
        response = requests.get('http://www.omdbapi.com/', params=params, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx) / HTTPError für schlechte Antworten auslösen (4xx oder 5xx)
        omdb_data = response.json()
        
        if omdb_data.get('Response') == 'True':
            # Log OMDb proxy response success.
            # Logge erfolgreiche OMDb-Proxy-Antwort.
            current_app.logger.info(f"OMDb Proxy Response for '{title or imdb_id}': True")
            return jsonify({'success': True, 'data': omdb_data})
        else:
            # OMDb returned Response: False, but HTTP status might be 200
            # OMDb gab Response: False zurück, aber HTTP-Status könnte 200 sein
            error_message_from_omdb = omdb_data.get('Error', 'OMDb_RESPONSE_FALSE_NO_SPECIFIC_ERROR_FIELD') # More specific default
            current_app.logger.warning(f"OMDb Proxy Response for '{title or imdb_id}': False, Error: {error_message_from_omdb}, Full OMDb Response: {omdb_data}")
            return jsonify({'success': False, 'message': error_message_from_omdb, 'data': omdb_data}), 200

    except requests.exceptions.Timeout:
        # Log OMDb proxy timeout.
        # Logge OMDb-Proxy-Zeitüberschreitung.
        current_app.logger.warning(f"OMDb Proxy request timed out for '{title or imdb_id}'.")
        return jsonify({'success': False, 'message': 'OMDb API request timed out.'}), 504 # Gateway Timeout
    except requests.exceptions.HTTPError as http_err:
        # Log OMDb proxy HTTP error.
        # Logge OMDb-Proxy-HTTP-Fehler.
        current_app.logger.error(f"OMDb Proxy HTTP error for '{title or imdb_id}': {http_err}. Response text: {response.text}")
        error_message = f'OMDb API HTTP error: {http_err}'
        omdb_response_data = None
        try:
            omdb_response_data = response.json() # Try to parse error response as JSON
            if isinstance(omdb_response_data, dict) and 'Error' in omdb_response_data:
                error_message = omdb_response_data['Error'] # Use specific error from OMDb JSON
        except ValueError: # response.text was not JSON
            pass # error_message remains the generic HTTP error
        return jsonify({'success': False, 'message': error_message, 'omdb_response_text': response.text, 'omdb_error_data': omdb_response_data}), response.status_code
    except requests.exceptions.RequestException as req_err: # Other network issues
        # Log OMDb proxy request exception.
        # Logge OMDb-Proxy-Anfrageausnahme.
        current_app.logger.error(f"OMDb Proxy request failed for '{title or imdb_id}': {req_err}")
        return jsonify({'success': False, 'message': f'Failed to connect to OMDb API: {req_err}'}), 502
    except ValueError as json_err: # Includes JSONDecodeError
        # Log OMDb proxy JSON decoding error.
        # Logge OMDb-Proxy-JSON-Dekodierungsfehler.
        current_app.logger.error(f"OMDb Proxy JSON decoding error for '{title or imdb_id}': {json_err}. Response: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({'success': False, 'message': 'Failed to decode OMDb API response.', 'details': str(json_err)}), 500

@api.route('/check_or_create_movie_by_imdb', methods=['POST'])
@handle_api_error
def check_or_create_movie_by_imdb():
    """
    Prüft, ob ein Film mit der gegebenen imdb_id existiert.
    Wenn nicht, wird er global hinzugefügt, basierend auf den übergebenen OMDb-ähnlichen Daten.
    Gibt den Status ('exists' oder 'created') und die movie_id zurück.

    Checks if a movie with the given imdb_id exists.
    If not, it is added globally based on the provided OMDb-like data.
    Returns the status ('exists' or 'created') and the movie_id.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided.'}), 400

    imdb_id = data.get('imdbID') # OMDb provides 'imdbID' / OMDb liefert 'imdbID'
    if not imdb_id:
        return jsonify({'success': False, 'message': 'imdbID is required.'}), 400

    # Try to find the movie by IMDb ID
    # Versuche, den Film anhand der IMDb-ID zu finden
    movie = data_manager.get_movie_by_imdb_id(imdb_id)
    if movie:
        current_app.logger.info(f"Movie with imdbID {imdb_id} found in DB (ID: {movie.id}). Status: exists. / Film mit imdbID {imdb_id} in DB gefunden (ID: {movie.id}). Status: exists.")
        return jsonify({'success': True, 'data': {'status': 'exists', 'movie_id': movie.id}}), 200
    else:
        # Movie does not exist, so add it globally
        # The 'data' should be the complete OMDb data
        # Film existiert nicht, also global hinzufügen
        # Die 'data' sollten die vollständigen OMDb-Daten sein
        current_app.logger.info(f"Movie with imdbID {imdb_id} not found in DB. Attempting to create globally. / Film mit imdbID {imdb_id} nicht in DB gefunden. Versuch, global zu erstellen.")
        new_movie = data_manager.add_movie_globally(movie_data=data)
        if new_movie:
            current_app.logger.info(f"Movie with imdbID {imdb_id} created globally (New ID: {new_movie.id}). Status: created. / Film mit imdbID {imdb_id} global erstellt (Neue ID: {new_movie.id}). Status: created.")
            return jsonify({'success': True, 'data': {'status': 'created', 'movie_id': new_movie.id}}), 201
        else:
            # Error during addition should have been logged by data_manager
            # Fehler beim Hinzufügen sollte vom data_manager geloggt worden sein
            current_app.logger.error(f"Failed to create movie globally with imdbID {imdb_id} via API. DataManager returned None. / Fehler beim globalen Erstellen von Film mit imdbID {imdb_id} via API. DataManager gab None zurück.")
            return jsonify({'success': False, 'message': 'Failed to create new movie globally. Check server logs.'}), 500