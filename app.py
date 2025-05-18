"""
app.py
Hauptmodul für die MovieWeb-Anwendung.
Main module for the MovieWeb application.
"""

import os
import re # Import für reguläre Ausdrücke
from flask import Flask, render_template, request, redirect, current_app, flash, jsonify, session, url_for, g
from datetime import datetime  # For year validation
import requests  # For OMDb API calls
from dotenv import load_dotenv
from sqlalchemy import func, desc
import urllib
from flask_wtf.csrf import CSRFProtect # Import CSRFProtect
import json # Wird für die ask_openrouter_for_movies Funktion benötigt
from typing import Optional

# Environment variables
# Umgebungsvariablen laden
load_dotenv()
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
# DEEP_SEEK_API_KEY = os.getenv('DEEP_SEEK_API_KEY') # No longer used / Nicht mehr verwendet
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

from models import db, User, Movie, UserMovie, Comment
from datamanager.sqlite_data_manager import SQLiteDataManager
from api.routes import api as api_blueprint

# Flask-Anwendung initialisieren
# Initialize Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///moviewebapp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret')

csrf = CSRFProtect(app) # Initialize CSRFProtect / CSRFProtect initialisieren

# Datenbank an die App binden
# Bind database to the app
db.init_app(app)

# Blueprints registrieren
# Register blueprints
app.register_blueprint(api_blueprint, url_prefix='/api')

# DataManager instanziieren
# Instantiate DataManager
data_manager = SQLiteDataManager()

# --- Constants for AI functions ---
# --- Konstanten für KI-Funktionen ---
AI_MOVIE_IDENTIFICATION_PROMPT_TEMPLATE = (
    "A user is trying to find a specific movie. Their input is: '{user_input}'. "
    "This input could be a full movie title, a partial title, a misspelled title, or a short natural language description of the movie's plot, characters, or setting. "
    "Your task is to identify the single, most probable, correct, and full movie title they are looking for. "
    "If the input is a description (e.g., 'a movie about a shark that terrorizes a beach town'), try to deduce the most famous movie matching that description (e.g., 'Jaws'). "
    "If the input is a partial or misspelled title, correct it to the full, official title. "
    "Return only this single movie title. "
    "If the input is too vague, nonsensical, clearly not describing a movie, or if you cannot confidently determine a single movie title, please return the exact phrase 'NO_CLEAR_MOVIE_TITLE_FOUND' and nothing else. "
    "Do not add any other explanatory text, just the single movie title or the specific error phrase."
)
MOVIE_RECOMMENDATION_PROMPT_TEMPLATE = (
    "Based on the movie '{movie_title}', considering its plot, genre, pacing, intensity, and overall tone, "
    "please suggest exactly 5 other movie titles that are similar. "
    "Only return the titles, each on a new line. Strictly do not use any numbering (like 1., 2.), bullet points (like -, *, •), or any additional explanatory text. "
    "Just the movie titles, one per line."
    "{exclusion_clause}" 
)
EXCLUSION_CLAUSE_TEMPLATE = (
    "\n\nPlease **strictly avoid suggesting any of the following titles** as they have been recommended to this user recently. "
    "Do NOT suggest any of these specific titles:\n{movies_to_exclude_list_format}\n"
    "Your new suggestions must be different from this list."
)
AI_RECOMMENDATION_HISTORY_SESSION_KEY = 'ai_recommendation_history'
AI_RECOMMENDATION_HISTORY_LENGTH = 20 # Max number of movies to remember for exclusion. / Maximale Anzahl von Filmen, die für den Ausschluss gespeichert werden.
DEFAULT_AI_TEMPERATURE_RECOMMEND = 0.7 
DEFAULT_AI_TEMPERATURE_INTERPRET = 0.3 # Lower temperature for more precise interpretation. / Niedrigere Temperatur für präzisere Interpretation.
NO_CLEAR_MOVIE_TITLE_MARKER = "NO_CLEAR_MOVIE_TITLE_FOUND_INTERNAL" # Internal marker for when AI can't find a title. / Interner Marker, wenn die KI keinen Titel finden kann.

# --- Constants for AI response handling and error messages ---
# --- Konstanten für die Handhabung von KI-Antworten und Fehlermeldungen ---
AI_MODEL_FOR_REQUESTS = "openai/gpt-3.5-turbo"
AI_MSG_OPENROUTER_KEY_MISSING = "OpenRouter API Key not configured on server." # English only for user-facing
AI_MSG_REQUEST_TIMEOUT = "AI service request timed out. Please try again later." # English only for user-facing
AI_MSG_CONNECTION_ERROR_GENERIC = "Error connecting to AI service." # English only for user-facing
AI_MSG_API_ERROR_DETAILED_TEMPLATE = "AI API Error: {error_message}." # English only for user-facing
AI_MSG_UNEXPECTED_ERROR_TEMPLATE = "An unexpected error occurred with the AI service: {error_message}." # English only for user-facing
AI_MSG_NO_SUGGESTIONS_LIST = "AI did not return any suggestions." # English only for user-facing

# --- Helper function for AI title interpretation ---
# --- Hilfsfunktion für KI-Titelinterpretation ---
def get_ai_interpreted_movie_title(user_input: str, temperature: float = DEFAULT_AI_TEMPERATURE_INTERPRET) -> Optional[str]:
    """
    Uses AI to interpret user input and find the most likely movie title.
    Returns the title or NO_CLEAR_MOVIE_TITLE_MARKER.

    Verwendet KI, um die Benutzereingabe zu interpretieren und den wahrscheinlichsten Filmtitel zu finden.
    Gibt den Titel oder NO_CLEAR_MOVIE_TITLE_MARKER zurück.
    """
    if not user_input:
        return NO_CLEAR_MOVIE_TITLE_MARKER

    prompt = AI_MOVIE_IDENTIFICATION_PROMPT_TEMPLATE.format(user_input=user_input)
    # Log the constructed prompt for debugging.
    # Logge den erstellten Prompt für Debugging-Zwecke.
    current_app.logger.debug(f"Constructed AI Title Identification Prompt:\\n{prompt}")
    
    # ask_openrouter_for_movies returns a list; we expect only one title or the special phrase here
    # ask_openrouter_for_movies gibt eine Liste zurück; wir erwarten hier nur einen Titel oder die spezielle Phrase
    raw_ai_response_list = ask_openrouter_for_movies(prompt_content=prompt, temperature=temperature, expected_responses=1)
    
    if raw_ai_response_list:
        # Cleaning of numbering is less relevant here as we expect a single title,
        # but we apply it anyway for safety.
        # Die Bereinigung von Nummerierungen ist hier weniger relevant, da wir einen einzelnen Titel erwarten,
        # aber wir wenden sie zur Sicherheit trotzdem an.
        interpreted_title = raw_ai_response_list[0] # Take the first element of the (usually) single-element list
        
        if interpreted_title == "NO_CLEAR_MOVIE_TITLE_FOUND":
            # Log when AI indicates no clear movie title.
            # Logge, wenn die KI keinen klaren Filmtitel angibt.
            current_app.logger.info(f"AI indicated no clear movie title for input: '{user_input}'")
            return NO_CLEAR_MOVIE_TITLE_MARKER
        
        # Additional check: If AI responds with an error message despite everything
        # Zusätzliche Prüfung: Wenn die KI trotz allem eine Fehlermeldung zurückgibt
        if "error" in interpreted_title.lower() or "not configured" in interpreted_title.lower() or "timed out" in interpreted_title.lower():
            # Log warning if AI returns an error phrase.
            # Logge eine Warnung, wenn die KI eine Fehlerphrase zurückgibt.
            current_app.logger.warning(f"AI returned an error phrase instead of a title or marker: {interpreted_title}")
            return NO_CLEAR_MOVIE_TITLE_MARKER # Treat as not found / Als nicht gefunden behandeln
            
        # Log successful AI interpretation.
        # Logge erfolgreiche KI-Interpretation.
        current_app.logger.info(f"AI interpreted user input '{user_input}' as movie title: '{interpreted_title}'")
        return interpreted_title
    else:
        # Log warning if AI returns no response.
        # Logge eine Warnung, wenn die KI keine Antwort zurückgibt.
        current_app.logger.warning(f"AI returned no response for title interpretation of input: '{user_input}'")
        return NO_CLEAR_MOVIE_TITLE_MARKER

@app.before_request
def load_logged_in_user():
    """
    Loads the logged-in user from the session before each request.
    Sets `g.user` to the user object or None if not logged in.

    Lädt den eingeloggten Benutzer aus der Session vor jeder Anfrage.
    Setzt `g.user` auf das Benutzerobjekt oder None, falls nicht eingeloggt.
    """
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = data_manager.get_user_by_id(user_id)

@app.context_processor
def inject_user_status():
    """
    Injects user login status and current user object into the template context.
    This makes `g_is_user_logged_in` and `g_current_user` available in all templates.

    Stellt den Login-Status des Benutzers und das aktuelle Benutzerobjekt dem Template-Kontext zur Verfügung.
    Dadurch sind `g_is_user_logged_in` und `g_current_user` in allen Templates verfügbar.
    """
    is_logged_in = g.user is not None
    return dict(g_is_user_logged_in=is_logged_in, g_current_user=g.user)

@app.route('/')
def home():
    """
    Home route: displays the application's welcome page with top movies.
    Zeigt die Startseite der Anwendung mit den Top-Filmen.
    """
    top_movies = data_manager.get_top_movies()
    return render_template('home.html', top_movies=top_movies)

@app.route('/login', methods=['POST'])
def login():
    """
    Login route: handles user login attempts via POST request.
    Expects 'username' in form data. Returns JSON response.

    Login-Route: Verarbeitet Benutzer-Login-Versuche per POST-Request.
    Erwartet 'username' in den Formulardaten. Gibt JSON-Antwort zurück.
    """
    username = request.form.get('username', '').strip() # .lower() removed, as data_manager handles it
    user = data_manager.get_user_by_name(username)
    
    if user:
        session['user_id'] = user.id
        current_app.logger.info(f"User '{username}' (ID: {user.id}) logged in successfully.")
        return jsonify({'success': True, 'redirect': f'/users/{user.id}', 'message': 'Login successful.'}), 200
    current_app.logger.warning(f"Failed login attempt for username '{username}'. User not found.")
    return jsonify({'success': False, 'message': 'User not found. Please check your username or register.'}), 401 # 401 Unauthorized

@app.route('/register', methods=['POST'])
def register():
    """
    Registration route: handles new user registration attempts via POST request.
    Expects 'username' in form data. Returns JSON response.

    Registrierungs-Route: Verarbeitet Registrierungsversuche neuer Benutzer per POST-Request.
    Erwartet 'username' in den Formulardaten. Gibt JSON-Antwort zurück.
    """
    username = request.form.get('username', '').strip()
    
    # data_manager.add_user handles stripping, lowercasing, empty check and duplicate check
    new_user = data_manager.add_user(username)
    
    if not new_user:
        # add_user returns None if name is empty or user already exists.
        # We can rely on the logging within add_user for specific reasons.
        # Determine if it was an empty username or a duplicate for a slightly more specific log here, if possible,
        # but for the user, a generic message is okay as data_manager might have more specific internal logging.
        # Bestimme, ob es ein leerer Benutzername oder ein Duplikat war für ein etwas spezifischeres Log hier, falls möglich,
        # aber für den Benutzer ist eine generische Nachricht in Ordnung, da der data_manager möglicherweise spezifischere interne Protokollierung hat.
        if not username: # Explicit check for empty username again, for clarity
            current_app.logger.warning("Registration attempt with empty username.")
            # Message could be more specific, but current one covers it broadly.
            # Nachricht könnte spezifischer sein, aber aktuelle deckt es breit ab.
            return jsonify({'success': False, 'message': 'Username cannot be empty.'}), 400 # Bad Request
        else:
            current_app.logger.warning(f"Registration attempt failed for username '{username}'. User might already exist or name is invalid.")
            return jsonify({'success': False, 'message': 'Username invalid or already exists. Please choose a different name.'}), 409 # Conflict or 400 Bad Request
    
    session['user_id'] = new_user.id
    current_app.logger.info(f"User '{new_user.name}' (ID: {new_user.id}) registered and logged in successfully.")
    return jsonify({'success': True, 'redirect': f'/users/{new_user.id}', 'message': 'Registration successful! You are now logged in.'}), 201 # 201 Created

@app.route('/logout')
def logout():
    """
    Logout route: logs the current user out by clearing the session.
    Redirects to the home page.

    Logout-Route: Meldet den aktuellen Benutzer ab, indem die Session geleert wird.
    Leitet zur Startseite weiter.
    """
    session.pop('user_id', None)
    g.user = None # Reset g.user for the current request as well. / g.user auch für die aktuelle Anfrage zurücksetzen.
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/users')
def list_users():
    """
    Users list route: displays all registered users.
    Zeigt alle registrierten Benutzer an.
    """
    users = data_manager.get_all_users()
    return render_template('users.html', users=users)

@app.route('/users/<int:user_id>')
def list_user_movies(user_id):
    """
    User movies list route: displays a specific user's favorite movies.
    Zeigt alle Lieblingsfilme eines bestimmten Benutzers an.
    """
    try:
        user = data_manager.get_user_by_id(user_id)
        if not user:
            flash('User not found.', 'warning')
            return redirect(url_for('list_users')) # Changed from '/users' to url_for for consistency
        
        user_movie_relations = data_manager.get_user_movie_relations(user_id)
        
    except Exception as e:
        current_app.logger.error(f"Error in list_user_movies for user {user_id}: {e}")
        # A bilingual error message for the user would be good here, but since it's a 500 error, the generic 500.html is rendered.
        # Eine zweisprachige Fehlermeldung für den Benutzer wäre hier gut, aber da es ein 500er ist, wird die generische 500.html gerendert.
        return render_template('500.html'), 500

    # Set IS_USER_LOGGED_IN for the template (always true here as it's the user's own list)
    # Setze IS_USER_LOGGED_IN für das Template (hier immer wahr, da es die eigene Liste des Benutzers ist)
    is_user_logged_in = True # Simplified, as it's the /users/<id> route
    return render_template('movies.html', user_movie_relations=user_movie_relations, user=user, IS_USER_LOGGED_IN=is_user_logged_in)

# Create user route
# Route zum Erstellen eines Benutzers
@app.route('/add_user', methods=['GET', 'POST'])
def add_user(): # Hinzugefügt: Fehlende Funktion
    """
    Add user route: handles new user creation (typically for admin or testing).
    Not a standard registration flow.

    Benutzer hinzufügen Route: Verarbeitet die Erstellung neuer Benutzer (normalerweise für Admin oder Tests).
    Kein Standard-Registrierungsablauf.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name: # Check for empty name before calling data_manager
            flash('Username cannot be empty.', 'danger')
        else:
            # data_manager.add_user handles stripping, lowercasing, empty check and duplicate check
            new_user_obj = data_manager.add_user(name)
            if new_user_obj:
                flash(f'User "{new_user_obj.name}" added successfully.', 'success') # Use name from returned object
                return redirect(url_for('list_users'))
            else:
                # add_user returns None if name is empty (already checked) or user already exists.
                # We can rely on the logging within add_user for specific reasons.
                flash(f'User "{name}" already exists or is invalid.', 'warning') # Generic message
    return render_template('add_user.html') # Erstellt eine einfache Vorlage oder leitet um

# --- Helper functions for add_movie GET route ---
# --- Hilfsfunktionen für die add_movie GET-Route ---
def _prepare_movie_details_from_db_for_add_template(movie_id: int, user_id: int) -> dict:
    """
    Prepares movie details from the local database for the 'add_movie' template.
    Bereitet Filmdetails aus der lokalen Datenbank für das 'add_movie'-Template vor.

    Args:
        movie_id (int): The ID of the movie to load from the database. / Die ID des Films, der aus der DB geladen werden soll.
        user_id (int): The ID of the current user (for checking existing ratings). / Die ID des aktuellen Benutzers (zur Prüfung existierender Bewertungen).

    Returns:
        dict: A dictionary containing template variables using keys expected by the template (omdb, omdb_details, rating5).
              Ein Wörterbuch mit Template-Variablen, das vom Template erwartete Schlüssel verwendet (omdb, omdb_details, rating5).
    """
    context = {
        'omdb': None, # Changed from omdb_data_for_template
        'omdb_details': None, # Changed from omdb_details_for_template
        'rating5': None, # Changed from rating5_for_template
        'user_search_input_value_update': None, # To prefill search box
        'flash_message': None # Tuple (message, category)
    }
    movie_from_db = data_manager.get_movie_by_id(movie_id)
    if movie_from_db:
        context['omdb'] = {
            'Response': 'True',
            'Title': movie_from_db.title,
            'Year': str(movie_from_db.year) if movie_from_db.year else 'N/A',
            'Poster': movie_from_db.poster_url,
            'Director': movie_from_db.director,
            'imdbRating': str(movie_from_db.community_rating * 2) if movie_from_db.community_rating is not None else 'N/A'
        }
        context['omdb_details'] = {
            'plot': movie_from_db.plot,
            'runtime': movie_from_db.runtime,
            'awards': movie_from_db.awards,
            'languages': movie_from_db.language,
            'genre': movie_from_db.genre,
            'actors': movie_from_db.actors,
            'writer': movie_from_db.writer,
            'country': movie_from_db.country,
            'metascore': movie_from_db.metascore,
            'rated': movie_from_db.rated_omdb,
            'imdb_id': movie_from_db.imdb_id
        }
        if movie_from_db.community_rating is not None:
            context['rating5'] = movie_from_db.community_rating
        else:
            user_movie_link = data_manager.get_user_movie_link(user_id=user_id, movie_id=movie_from_db.id)
            if user_movie_link and user_movie_link.user_rating is not None:
                context['rating5'] = user_movie_link.user_rating
        context['user_search_input_value_update'] = movie_from_db.title
    else:
        context['flash_message'] = (f'Movie with ID {movie_id} not found in database.', 'danger')
    return context

def _fetch_movie_details_from_omdb_for_add_template(title_for_omdb_search: str) -> dict:
    """
    Fetches movie details from OMDb API for the 'add_movie' template.
    Ruft Filmdetails von der OMDb-API für das 'add_movie'-Template ab.

    Args:
        title_for_omdb_search (str): The movie title to search on OMDb. / Der Filmtitel für die OMDb-Suche.

    Returns:
        dict: A dictionary containing template variables using keys expected by the template (omdb, omdb_details, rating5).
              Ein Wörterbuch mit Template-Variablen, das vom Template erwartete Schlüssel verwendet (omdb, omdb_details, rating5).
    """
    context = {
        'omdb': None, # Changed from omdb_data_for_template
        'omdb_details': None, # Changed from omdb_details_for_template
        'rating5': None, # Changed from rating5_for_template
        'ai_message': None, # For OMDb errors
        'flash_message': None # Tuple (message, category)
    }
    params = {'apikey': OMDB_API_KEY, 't': title_for_omdb_search}
    omdb_api_response_data = None # To store the actual response from OMDb API
    try:
        resp = requests.get('http://www.omdbapi.com/', params=params, timeout=10)
        resp.raise_for_status()
        omdb_api_response_data = resp.json()
        context['omdb'] = omdb_api_response_data # Store full OMDb response under 'omdb' key
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"OMDb API request failed for title '{title_for_omdb_search}': {e}")
        omdb_api_response_data = {'Response': 'False', 'Error': str(e)}
        context['omdb'] = omdb_api_response_data # Store error response under 'omdb' key
        context['flash_message'] = (f"Error connecting to OMDb for title '{title_for_omdb_search}': {str(e)[:100]}.", "danger")

    if omdb_api_response_data and omdb_api_response_data.get('Response') == 'True':
        context['omdb_details'] = {
            'plot': omdb_api_response_data.get('Plot'),
            'runtime': omdb_api_response_data.get('Runtime'),
            'awards': omdb_api_response_data.get('Awards'),
            'languages': omdb_api_response_data.get('Language'),
            'genre': omdb_api_response_data.get('Genre'),
            'actors': omdb_api_response_data.get('Actors'),
            'writer': omdb_api_response_data.get('Writer'),
            'country': omdb_api_response_data.get('Country'),
            'metascore': omdb_api_response_data.get('Metascore'),
            'rated': omdb_api_response_data.get('Rated'),
            'imdb_id': omdb_api_response_data.get('imdbID')
        }
        raw_rating = omdb_api_response_data.get('imdbRating')
        if raw_rating and raw_rating != 'N/A':
            try:
                rating10 = float(raw_rating)
                context['rating5'] = round(rating10 / 2 * 2) / 2
            except ValueError:
                pass # rating5 remains None
    elif omdb_api_response_data: # Response is 'False' or other issues
        error_msg_from_omdb = omdb_api_response_data.get('Error', 'Unknown OMDb error')
        context['ai_message'] = f"OMDb could not find details for the title: '{title_for_omdb_search}'. Error: {error_msg_from_omdb}"
        current_app.logger.warning(f"OMDb search failed for title '{title_for_omdb_search}': {error_msg_from_omdb}")
    
    return context

def _get_ai_suggestion_for_add_movie_template(user_search_input: str) -> dict:
    """
    Gets AI-interpreted movie title suggestion for the 'add_movie' template.
    Holt einen KI-interpretierten Filmtitelvorschlag für das 'add_movie'-Template.

    Args:
        user_search_input (str): The user's raw search input. / Die rohe Sucheingabe des Benutzers.

    Returns:
        dict: A dictionary containing template variables ('ai_suggested_title', 'ai_message').
              Ein Wörterbuch mit Template-Variablen ('ai_suggested_title', 'ai_message').
    """
    context = {'ai_suggested_title': None, 'ai_message': None}
    current_app.logger.info(f"Initiating AI movie search with input: '{user_search_input}' for add_movie.")
    ki_result = get_ai_interpreted_movie_title(user_search_input)

    if ki_result == NO_CLEAR_MOVIE_TITLE_MARKER or ki_result is None:
        context['ai_message'] = "AI could not identify a clear movie title. Please try a different title or description."
        current_app.logger.info(f"AI could not find title for user input: '{user_search_input}' in add_movie.")
    else:
        context['ai_suggested_title'] = ki_result
        current_app.logger.info(f"AI suggested title '{ki_result}' for input '{user_search_input}' in add_movie.")
    return context

# --- Helper function for add_movie POST route ---
# --- Hilfsfunktion für die add_movie POST-Route ---
def _process_add_movie_form(form_data, user_id: int, source_movie_id: Optional[int], original_user_search_input: str) -> tuple[bool, str, Optional[str], Optional[str]]:
    """
    Processes the form data submitted to add a movie.
    Validates input and calls the DataManager to add the movie.

    Verarbeitet die Formulardaten, die zum Hinzufügen eines Films gesendet wurden.
    Validiert die Eingaben und ruft den DataManager auf, um den Film hinzuzufügen.

    Args:
        form_data (werkzeug.datastructures.ImmutableMultiDict): The form data from the request.
                                                               Die Formulardaten aus dem Request.
        user_id (int): The ID of the user adding the movie. / Die ID des Benutzers, der den Film hinzufügt.
        source_movie_id (Optional[int]): The ID of the movie from which the add action originated (e.g. recommendations page).
                                           Die ID des Films, von dem die Hinzufügeaktion ausging (z.B. Empfehlungsseite).
        original_user_search_input (str): The original search input by the user, for redirect purposes on error.
                                            Die ursprüngliche Sucheingabe des Benutzers, für Weiterleitungszwecke bei Fehlern.


    Returns:
        tuple[bool, str, Optional[str], Optional[str]]: 
            - success (bool): True if movie was added successfully, False otherwise.
                              True, wenn der Film erfolgreich hinzugefügt wurde, sonst False.
            - message (str): Flash message for the user. / Flash-Nachricht für den Benutzer.
            - message_category (Optional[str]): Category for the flash message (e.g., 'success', 'danger').
                                                Kategorie für die Flash-Nachricht (z.B. 'success', 'danger').
            - redirect_url_on_fail (Optional[str]): URL to redirect to if adding fails and a specific redirect is needed.
                                                      URL für die Weiterleitung, falls das Hinzufügen fehlschlägt und eine bestimmte Weiterleitung erforderlich ist.
    """
    title_from_omdb_form = form_data.get('title_from_omdb', '').strip()
    if not title_from_omdb_form: 
        return False, 'Error: Movie title for adding was missing. Please try the search again.', 'danger', url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input)

    director = form_data.get('director', '').strip()
    year_str = form_data.get('year', '').strip()
    rating_str = form_data.get('rating', '').strip()
    poster_url = form_data.get('poster_url', '').strip()
    plot = form_data.get('plot', '').strip()
    runtime = form_data.get('runtime', '').strip()
    awards = form_data.get('awards', '').strip()
    languages = form_data.get('languages', '').strip()
    genre = form_data.get('genre', '').strip()
    actors = form_data.get('actors', '').strip()
    writer = form_data.get('writer', '').strip()
    country = form_data.get('country', '').strip()
    metascore = form_data.get('metascore', '').strip()
    rated = form_data.get('rated', '').strip()
    imdb_id = form_data.get('imdb_id', '').strip()

    year = None
    if year_str and year_str.isdigit():
        year = int(year_str)
    
    rating = None
    if rating_str:
        try:
            rating = float(rating_str)
            if not (0 <= rating <= 5):
                return False, 'Rating must be between 0 and 5.', 'warning', url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input)
        except ValueError:
            return False, 'Rating must be a numeric value.', 'warning', url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input)

    omdb_suggested_rating_str = form_data.get('omdb_suggested_rating', '')
    omdb_rating_for_community_param = None
    if omdb_suggested_rating_str:
        try:
            omdb_rating_for_community_param = float(omdb_suggested_rating_str)
            if not (0 <= omdb_rating_for_community_param <= 5):
                omdb_rating_for_community_param = None
        except ValueError:
            pass

    movie_added_successfully = data_manager.add_movie(
        user_id,
        title_from_omdb_form, 
        director,
        year,
        rating,
        poster_url or None,
        plot=plot or None,
        runtime=runtime or None,
        awards=awards or None,
        languages=languages or None,
        genre=genre or None,
        actors=actors or None,
        writer=writer or None,
        country=country or None,
        metascore=metascore or None,
        rated=rated or None,
        imdb_id=imdb_id or None,
        omdb_rating_for_community=omdb_rating_for_community_param
    )

    if movie_added_successfully:
        return True, f"Movie '{title_from_omdb_form}' added successfully.", 'success', None
    else:
        fail_redirect_url = url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input)
        if source_movie_id: # If adding failed but we came from a specific movie page, go back there
            fail_redirect_url = url_for('movie_page', movie_id=source_movie_id)
        return False, f"Could not add movie '{title_from_omdb_form}'. It might already be in your list or an error occurred.", 'danger', fail_redirect_url

@app.route('/users/<int:user_id>/add_movie', methods=['GET', 'POST'])
def add_movie(user_id):
    """
    Add movie route for a specific user.
    Handles a multi-stage process for adding a movie:
    1. User search input -> AI interpretation -> AI suggested title.
    2. User confirms AI title -> Load OMDb details for AI title.
       Alternatively, if a movie_id is passed directly (e.g. from AI recommendations), load details from DB.
    3. User sees OMDb/DB details and a form to add the movie with a personal rating.
    4. POST request submits the form to add the movie to the user's list and the global DB if new.

    Route zum Hinzufügen eines Films für einen bestimmten Benutzer.
    Verarbeitet einen mehrstufigen Prozess zum Hinzufügen eines Films:
    1. Benutzersucheingabe -> KI-Interpretation -> KI-Titelvorschlag.
    2. Benutzer bestätigt KI-Titel -> OMDb-Details für KI-Titel laden.
       Alternativ, wenn eine movie_id direkt übergeben wird (z.B. von KI-Empfehlungen), Details aus DB laden.
    3. Benutzer sieht OMDb-/DB-Details und ein Formular zum Hinzufügen des Films mit persönlicher Bewertung.
    4. POST-Request sendet das Formular ab, um den Film zur Benutzerliste und ggf. zur globalen DB hinzuzufügen.
    """
    user = data_manager.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('list_users'))
    
    # --- Initialize context for template ---
    # --- Kontext für Template initialisieren ---
    template_context = {
        'user': user,
        'current_year': datetime.now().year,
        'user_search_input_value': request.args.get('user_search_input', ''),
        'ai_suggested_title': None,
        'ai_message': None,
        'omdb': None, # Changed from omdb_data_for_template
        'omdb_details': None, # Changed from omdb_details_for_template
        'rating5': None, # Changed from rating5_for_template
        'show_details_form': False,
        'hide_initial_search_form': False,
        'source_movie_id_for_template': request.args.get('source_movie_id', type=int) # Keep this from request.args
    }
    
    # --- GET Request Logic ---
    # --- GET-Request-Logik ---
    if request.method == 'GET':
        movie_to_add_id_value = request.args.get('movie_to_add_id', type=int)
        title_for_omdb_search_value = request.args.get('title_for_omdb_search', '').strip()
        user_search_input_original_value = request.args.get('user_search_input', '') # Keep original for prefilling

        if movie_to_add_id_value or title_for_omdb_search_value:
            template_context['hide_initial_search_form'] = True

        # Phase 2b: Movie ID was passed directly (e.g., from AI recommendations)
        # Phase 2b: Film-ID wurde direkt übergeben (z.B. von KI-Empfehlungen)
        if movie_to_add_id_value:
            current_app.logger.info(f"User {user_id} attempting to add existing movie_id: {movie_to_add_id_value}")
            db_details_context = _prepare_movie_details_from_db_for_add_template(movie_to_add_id_value, user_id)
            template_context.update(db_details_context) # Update main context
            if db_details_context.get('flash_message'):
                flash(db_details_context['flash_message'][0], db_details_context['flash_message'][1])
                if db_details_context['flash_message'][1] == 'danger': # Critical error, redirect
                    return redirect(url_for('list_user_movies', user_id=user_id))
            # Check the 'omdb' key from the helper function's returned context
            if db_details_context.get('omdb') and db_details_context['omdb'].get('Response') == 'True':
                template_context['show_details_form'] = True
            if db_details_context.get('user_search_input_value_update'): # If movie found, update search box
                 template_context['user_search_input_value'] = db_details_context['user_search_input_value_update']


        # Phase 2a: User clicked 'Load Movie Details' with AI-suggested title (higher priority)
        # Phase 2a: Benutzer klickte auf 'Filmdetails laden' mit KI-vorgeschlagenem Titel (höhere Priorität)
        elif title_for_omdb_search_value: # Note: 'elif' implies movie_to_add_id_value was not present or handled
            current_app.logger.info(f"User {user_id} initiated OMDb search with title: '{title_for_omdb_search_value}'")
            template_context['user_search_input_value'] = user_search_input_original_value # Preserve original search

            omdb_fetch_context = _fetch_movie_details_from_omdb_for_add_template(title_for_omdb_search_value)
            template_context.update(omdb_fetch_context) # Update main context
            
            if omdb_fetch_context.get('flash_message'):
                flash(omdb_fetch_context['flash_message'][0], omdb_fetch_context['flash_message'][1])
            
            # Check the 'omdb' key from the helper function's returned context
            if omdb_fetch_context.get('omdb') and omdb_fetch_context['omdb'].get('Response') == 'True':
                template_context['show_details_form'] = True
            else: # OMDb search failed or movie not found by OMDb
                template_context['show_details_form'] = False
                # ai_message is already set by _fetch_movie_details_from_omdb_for_add_template if OMDb error

        # Phase 1: User entered a search to get AI suggestion (only if not Phase 2)
        # Phase 1: Benutzer gab eine Suche ein, um einen KI-Vorschlag zu erhalten (nur wenn nicht Phase 2)
        elif template_context['user_search_input_value']: # Check the initial value from request.args
            ai_context = _get_ai_suggestion_for_add_movie_template(template_context['user_search_input_value'])
            template_context.update(ai_context) # Update main context
            # ai_suggested_title and ai_message are set by the helper

        return render_template('add_movie.html', **template_context)

    # --- POST Request Logic (largely unchanged for now, can be refactored later) ---
    # --- POST-Request-Logik (vorerst weitgehend unverändert, kann später refaktoriert werden) ---
    elif request.method == 'POST':
        # original_user_search_input is needed by _process_add_movie_form for error redirects
        # original_user_search_input wird von _process_add_movie_form für Fehlerweiterleitungen benötigt
        original_user_search_input_for_post = request.form.get('original_user_search_input', '')
        source_movie_id_from_form = request.form.get('source_movie_id', type=int) # Hidden field in form

        success, message, category, fail_redirect_url = _process_add_movie_form(
            request.form, 
            user_id, 
            source_movie_id_from_form, 
            original_user_search_input_for_post
        )

        flash(message, category)

        if success:
            if source_movie_id_from_form:
                return redirect(url_for('movie_page', movie_id=source_movie_id_from_form))
            return redirect(url_for('list_user_movies', user_id=user_id))
        else:
            # fail_redirect_url is determined by _process_add_movie_form
            # fail_redirect_url wird von _process_add_movie_form bestimmt
            return redirect(fail_redirect_url or url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input_for_post))

    # Fallback redirect for GET if no specific phase was handled (should not happen with current logic but good for safety)
    # Fallback-Weiterleitung für GET, falls keine spezifische Phase behandelt wurde (sollte mit aktueller Logik nicht passieren, aber gut zur Sicherheit)
    return redirect(url_for('add_movie', user_id=user_id, hide_initial_search_form=template_context['hide_initial_search_form'], source_movie_id_for_template=template_context['source_movie_id_for_template']))

@app.route('/users/<int:user_id>/update_movie_rating/<int:movie_id>', methods=['GET', 'POST'])
def update_movie_rating(user_id, movie_id):
    """
    Edit movie rating route (user-specific).
    Displays movie details and allows updating the personal rating for a movie in the user's list.

    Film-Rating bearbeiten-Route (User-spezifisch).
    Zeigt die Filmdetails an und erlaubt die Aktualisierung des persönlichen Ratings für einen Film in der User-Liste.
    """
    if not g.user or g.user.id != user_id:
        flash('You can only edit ratings for your own movie list.', 'danger')
        return redirect(url_for('home'))

    movie = data_manager.get_movie_by_id(movie_id)
    if not movie:
        flash(f'Movie with ID {movie_id} not found.', 'danger')
        return redirect(url_for('home'))

    user_movie_link = data_manager.get_user_movie_link(user_id=g.user.id, movie_id=movie.id)

    if not user_movie_link:
        flash(f'Movie "{movie.title}" is not in your list. You can add it first.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie.id))

    if request.method == 'POST':
        rating_str = request.form.get('rating', '').strip()
        new_user_rating = None

        if not rating_str:
            # Empty string means user wants to remove their rating
            # Leerer String bedeutet, der Benutzer möchte seine Bewertung entfernen
            pass
        else:
            try:
                new_user_rating = float(rating_str)
                if not (0 <= new_user_rating <= 5):
                    flash('Rating must be between 0 and 5.', 'warning')
                    return redirect(url_for('movie_page', movie_id=movie.id))
            except ValueError:
                flash('Rating must be a number.', 'warning')
                return redirect(url_for('movie_page', movie_id=movie.id))

        success = data_manager.update_user_rating_for_movie(user_id=g.user.id, movie_id=movie.id, new_rating=new_user_rating)

        if success:
            flash(f"Your rating for '{movie.title}' has been updated.", 'success')
            return redirect(url_for('list_user_movies', user_id=g.user.id))
        else:
            flash('Could not update your rating for this movie.', 'error')
            return redirect(url_for('movie_page', movie_id=movie.id))
    
    # For GET request, display the page with current rating
    # Für GET-Request, Seite mit aktueller Bewertung anzeigen
    return render_template(
        'update_movie_rating.html',
        user=g.user, 
        movie=movie, 
        current_user_rating=user_movie_link.user_rating
    )

@app.route('/users/<int:user_id>/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(user_id, movie_id):
    """
    Delete movie route: deletes a movie from favorites and redirects to the list.
    Löscht einen Film aus der Favoritenliste und leitet zurück zur Filmliste.
    """
    try:
        success = data_manager.delete_movie_from_user_list(user_id=user_id, movie_id=movie_id)
    except Exception as e:
        # Log error for server-side diagnostics.
        # Logge den Fehler für serverseitige Diagnose.
        current_app.logger.error(f"Error in delete_movie for user {user_id}, movie {movie_id}: {e}")
        flash('Error deleting movie.', 'danger')
        return redirect(url_for('list_user_movies', user_id=user_id))
    if success:
        flash('Movie deleted from your list.', 'success')
    else:
        flash('Could not delete movie from your list.', 'warning')
    return redirect(url_for('list_user_movies', user_id=user_id))

@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    """
    Movie details with comments (JSON endpoint).
    Provides movie details and its associated comments as a JSON response.
    Follows standardized format: {'success': True/False, 'data': ..., 'message': ...}

    Filmdetails mit Kommentaren (JSON-Endpunkt).
    Liefert Filmdetails und zugehörige Kommentare als JSON-Antwort.
    Folgt dem standardisierten Format: {'success': True/False, 'data': ..., 'message': ...}
    """
    movie = data_manager.get_movie_by_id(movie_id)
    if not movie:
        current_app.logger.warning(f"Movie with ID {movie_id} not found for JSON endpoint /movie/{movie_id}.")
        return jsonify({'success': False, 'message': 'Movie not found'}), 404

    comments = data_manager.get_comments_for_movie(movie_id)
    
    movie_data = {
        'id': movie.id,
        'title': movie.title,
        'director': movie.director,
        'year': movie.year,
        'community_rating': movie.community_rating,
        'community_rating_count': movie.community_rating_count,
        'plot': movie.plot,
        'genre': movie.genre,
        'runtime': movie.runtime,
        'poster_url': movie.poster_url,
        'imdb_id': movie.imdb_id
    }
    comments_data = [{
        'id': c.id,
        'text': c.text,
        'user': c.user.name,
        'created_at': c.created_at.isoformat()
    } for c in comments]

    current_app.logger.info(f"Successfully retrieved details for movie {movie_id} for JSON endpoint.")
    return jsonify({
        'success': True,
        'data': {
            'movie': movie_data,
            'comments': comments_data
        }
    }), 200

@app.route('/movie/<int:movie_id>/comment', methods=['POST'])
def add_movie_comment(movie_id):
    """
    Add a comment to a movie (JSON endpoint).
    Requires user to be logged in. Expects 'text' in form data.
    Follows standardized format: {'success': True/False, 'data': ..., 'message': ...}
    NOTE: This endpoint might be legacy if all commenting is handled by /page.

    Fügt einen Kommentar zu einem Film hinzu (JSON-Endpunkt).
    Erfordert, dass der Benutzer angemeldet ist. Erwartet 'text' in den Formulardaten.
    Folgt dem standardisierten Format: {'success': True/False, 'data': ..., 'message': ...}
    HINWEIS: Dieser Endpunkt könnte veraltet sein, wenn alle Kommentare über /page abgewickelt werden.
    """
    if 'user_id' not in session:
        current_app.logger.warning(f"Add comment attempt (via /comment) by unauthenticated user for movie {movie_id}.")
        return jsonify({'success': False, 'message': 'User not logged in. Authentication required.', 'data': None}), 401
    
    user_id_from_session = session['user_id']
    text = request.form.get('text', '').strip()

    if not text:
        current_app.logger.warning(f"Add comment attempt (via /comment) for movie {movie_id} by user {user_id_from_session} with empty text.")
        return jsonify({'success': False, 'message': 'Comment text cannot be empty.', 'data': None}), 400
    
    new_comment = data_manager.add_comment(movie_id=movie_id, user_id=user_id_from_session, text=text)
    
    if new_comment:
        current_app.logger.info(f"User {user_id_from_session} successfully added comment {new_comment.id} to movie {movie_id} (via /comment).")
        return jsonify({
            'success': True, 
            'message': 'Comment added successfully.',
            'data': {'comment_id': new_comment.id}
        }), 201
    else:
        # Specific error logging is done within data_manager.add_comment
        current_app.logger.error(f"Failed to add comment (via /comment) for movie {movie_id} by user {user_id_from_session}. data_manager.add_comment returned None.")
        return jsonify({'success': False, 'message': 'Error adding comment. Please try again.', 'data': None}), 500

@app.route('/api/docs')
def api_docs():
    """
    API documentation page.
    Renders the HTML page for API documentation.
    """
    return render_template('api_docs.html')

@app.route('/about')
def about():
    """
    About page: displays information about the MovieWeb application.
    Zeigt Informationen über die MovieWeb App.
    """
    return render_template('about.html')

@app.errorhandler(404)
def page_not_found(e):
    """
    404 error page: render 404.html template.
    Rendern der 404-Seite.
    """
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """
    500 error page: render 500.html template.
    Rendern der 500-Seite.
    """
    return render_template('500.html'), 500

@app.route('/movie/<int:movie_id>/page')
def movie_page(movie_id):
    """
    Renders the dedicated detail page for a movie.
    
    Args:
        movie_id (int): The ID of the movie.
                        Die ID des Films.

    Returns:
        HTML: The rendered movie detail page or 404/500 on error.
              Die gerenderte Detailseite des Films oder 404/500 bei Fehlern.
    """
    try:
        movie = data_manager.get_movie_by_id(movie_id)
        if not movie:
            current_app.logger.warning(f"Movie with ID {movie_id} not found for movie_page.")
            return render_template('404.html'), 404

        current_user_specific_rating = None
        is_movie_in_user_list = False

        if g.user:
            user_movie_link = data_manager.get_user_movie_link(user_id=g.user.id, movie_id=movie.id)
            if user_movie_link:
                is_movie_in_user_list = True
                current_user_specific_rating = user_movie_link.user_rating

        return render_template(
            'movie_detail_page.html', 
            movie=movie,
            user=g.user,
            is_movie_in_user_list=is_movie_in_user_list,
            current_user_rating_for_movie=current_user_specific_rating
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering movie page for movie_id {movie_id}: {e}")
        return render_template('500.html'), 500

@app.route('/movie/<int:movie_id>/comment/page', methods=['POST'])
def add_movie_comment_page(movie_id):
    """
    Handles adding a comment from the movie detail page. Returns JSON.
    Verarbeitet das Hinzufügen eines Kommentars von der Filmdetailseite. Gibt JSON zurück.
    """
    if 'user_id' not in session:
        # flash('You must be logged in to comment.', 'warning') # Old
        # return redirect(url_for('movie_page', movie_id=movie_id)) # Old
        current_app.logger.warning(f"Add comment attempt by unauthenticated user for movie {movie_id}.")
        return jsonify({'success': False, 'message': 'You must be logged in to comment.'}), 401

    user_id_from_session = session['user_id']

    current_app.logger.debug(f"Add comment request for movie {movie_id} by user {user_id_from_session}. Headers: {request.headers}")
    current_app.logger.debug(f"Request data raw: {request.data}")
    data = request.get_json()
    current_app.logger.debug(f"Request data JSON: {data}")

    if not data:
        # flash('Invalid request data.', 'danger') # Old
        # current_app.logger.warning("add_movie_comment_page: No JSON data received.") # Old
        # return redirect(url_for('movie_page', movie_id=movie_id)) # Old
        current_app.logger.warning(f"Add comment attempt for movie {movie_id} by user {user_id_from_session} with no JSON data.")
        return jsonify({'success': False, 'message': 'Invalid request data. Expected JSON.'}), 400

    text = data.get('comment_text', '').strip()
    current_app.logger.debug(f"Extracted comment text for movie {movie_id} by user {user_id_from_session}: '{text}'")

    if not text:
        # flash('Comment cannot be empty.', 'warning') # Old
        # current_app.logger.warning(f"add_movie_comment_page: Comment text is empty after processing. Original data: {data}") # Old
        # return redirect(url_for('movie_page', movie_id=movie_id)) # Old
        current_app.logger.warning(f"Add comment attempt for movie {movie_id} by user {user_id_from_session} with empty text.")
        return jsonify({'success': False, 'message': 'Comment cannot be empty.'}), 400

    new_comment = data_manager.add_comment(movie_id=movie_id, user_id=user_id_from_session, text=text)

    if new_comment:
        # flash('Comment added successfully!', 'success') # Old
        current_app.logger.info(f"User {user_id_from_session} successfully added comment {new_comment.id} to movie {movie_id}.")
        return jsonify({
            'success': True, 
            'message': 'Comment added successfully!', 
            'comment_id': new_comment.id,
            'comment_text': new_comment.text,
            'user_name': new_comment.user.name, # Assuming user relationship is loaded
            'created_at': new_comment.created_at.isoformat()
        }), 201
    else:
        # Specific error logging is done within data_manager.add_comment
        # flash('Error adding comment. Please try again.', 'danger') # Old
        # return redirect(url_for('movie_page', movie_id=movie_id)) # Old
        current_app.logger.error(f"Failed to add comment for movie {movie_id} by user {user_id_from_session}. data_manager.add_comment returned None.")
        return jsonify({'success': False, 'message': 'Error adding comment. Please try again.'}), 500
    
    # return redirect(url_for('movie_page', movie_id=movie_id)) # Old - Should not be reached anymore

@app.route('/user/add_movie_to_list/<int:movie_id>', methods=['POST'])
def add_movie_to_list(movie_id):
    """
    Adds an existing movie to the logged-in user's list.
    Redirects back to the movie detail page.

    Fügt einen vorhandenen Film zur Liste des angemeldeten Benutzers hinzu.
    Leitet zurück zur Filmdetailseite.
    """
    if not g.user:
        flash('You must be logged in to add movies to your list.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id))

    success = data_manager.add_existing_movie_to_user_list(user_id=g.user.id, movie_id=movie_id)

    if success:
        movie_title_query = data_manager.get_movie_by_id(movie_id)
        movie_title = movie_title_query.title if movie_title_query else f"ID {movie_id}"
        flash(f"'{movie_title}' has been added to your list.", 'success')
    else:
        flash('Could not add movie to your list. It might already be there or an error occurred.', 'danger')
    
    return redirect(url_for('movie_page', movie_id=movie_id))

@app.route('/user/list/remove/<int:movie_id>', methods=['POST'], endpoint='remove_movie_from_list_explicit')
def remove_movie_from_list(movie_id):
    """
    Removes a movie from the logged-in user's list.
    Entfernt einen Film aus der Liste des eingeloggten Benutzers.
    """
    if not g.user:
        flash('You must be logged in to remove movies from your list.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id))

    success = data_manager.delete_movie_from_user_list(user_id=g.user.id, movie_id=movie_id)

    if success:
        flash(f"Movie (ID: {movie_id}) has been removed from your list.", 'success') 
    else:
        flash(f"Could not remove movie (ID: {movie_id}) from your list. It might not have been in your list or an error occurred.", 'danger')
    
    return redirect(url_for('movie_page', movie_id=movie_id))

@app.route('/movie/<int:movie_id>/ai_recommendations')
def get_ai_movie_recommendations_route(movie_id):
    """
    AI movie recommendations route.
    Fetches AI-based movie recommendations for a given movie_id.
    Returns JSON response with recommendations or error message.

    Route für KI-Filmempfehlungen.
    Ruft KI-basierte Filmempfehlungen für eine bestimmte movie_id ab.
    Gibt eine JSON-Antwort mit Empfehlungen oder einer Fehlermeldung zurück.
    """
    movie = data_manager.get_movie_by_id(movie_id)
    if not movie:
        current_app.logger.warning(f"AI recommendations requested for non-existent movie_id: {movie_id}")
        return jsonify({'success': False, 'message': 'Movie not found.'}), 404

    user_id_for_logging = session.get('user_id', 'Guest') # Get user ID or Guest for logging
    user_history_before_this_call = session.get(AI_RECOMMENDATION_HISTORY_SESSION_KEY, [])
    exclusion_text = ""
    if user_history_before_this_call:
        movies_to_exclude_list_str = "\n".join([f"- \"{title}\"" for title in user_history_before_this_call])
        exclusion_text = EXCLUSION_CLAUSE_TEMPLATE.format(movies_to_exclude_list_format=movies_to_exclude_list_str)

    prompt = MOVIE_RECOMMENDATION_PROMPT_TEMPLATE.format(movie_title=movie.title, exclusion_clause=exclusion_text)
    current_app.logger.debug(f"Constructed AI Prompt for user {user_id_for_logging} (Movie: {movie.title}):\\n{prompt}")
    
    try:
        temperature_str = request.args.get('temp', str(DEFAULT_AI_TEMPERATURE_RECOMMEND))
        temperature = float(temperature_str)
        if not (0.0 <= temperature <= 2.0):
            current_app.logger.warning(f"Invalid temperature value '{temperature_str}' for user {user_id_for_logging}, falling back to {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")
            temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND
    except ValueError:
        current_app.logger.warning(f"Could not convert temperature value '{request.args.get('temp')}' for user {user_id_for_logging} to float, falling back to {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")
        temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND

    # The ask_openrouter_for_movies function now returns a list of strings which are either titles or error messages.
    # Die Funktion ask_openrouter_for_movies gibt nun eine Liste von Strings zurück, die entweder Titel oder Fehlermeldungen sind.
    current_ai_suggestions_or_error = ask_openrouter_for_movies(prompt_content=prompt, temperature=temperature, expected_responses=5)
    
    # Check if the first (and likely only) element indicates an error returned from ask_openrouter_for_movies
    # Prüfen, ob das erste (und wahrscheinlich einzige) Element auf einen Fehler hinweist, der von ask_openrouter_for_movies zurückgegeben wurde
    is_internal_error_response = False
    error_message_from_ai_func = ""

    if not current_ai_suggestions_or_error: # Should not happen if ask_openrouter_for_movies respects its contract to return a list
        current_app.logger.error(f"AI call for user {user_id_for_logging} (Movie: {movie.title}) returned empty list unexpectedly.")
        return jsonify({'success': False, 'message': AI_MSG_UNEXPECTED_ERROR_TEMPLATE.format(error_message='AI service returned no data.')}), 500

    # Check for known error messages from our constants used within ask_openrouter_for_movies
    # Überprüfe auf bekannte Fehlermeldungen aus unseren Konstanten, die in ask_openrouter_for_movies verwendet werden
    possible_error_markers = [
        AI_MSG_OPENROUTER_KEY_MISSING,
        AI_MSG_REQUEST_TIMEOUT,
        AI_MSG_CONNECTION_ERROR_GENERIC,
        AI_MSG_NO_SUGGESTIONS_LIST # This indicates AI ran but found nothing, not strictly an error but needs handling
    ]
    # Also check for templates by looking for their unique parts
    # Überprüfe auch Vorlagen, indem du nach ihren eindeutigen Teilen suchst
    if any(marker in current_ai_suggestions_or_error[0] for marker in possible_error_markers) or \
       AI_MSG_API_ERROR_DETAILED_TEMPLATE.split('{')[0] in current_ai_suggestions_or_error[0] or \
       AI_MSG_UNEXPECTED_ERROR_TEMPLATE.split('{')[0] in current_ai_suggestions_or_error[0]:
        is_internal_error_response = True
        error_message_from_ai_func = current_ai_suggestions_or_error[0]
        # Log AI error specifically for recommendations flow.
        # Logge KI-Fehler spezifisch für den Empfehlungsablauf.
        current_app.logger.warning(f"AI recommendations for user {user_id_for_logging} (Movie: {movie.title}) failed. AI function returned: {error_message_from_ai_func}")

    if is_internal_error_response:
        # For user-facing messages, we might want to be less specific than the internal log / Für benutzerseitige Nachrichten möchten wir möglicherweise weniger spezifisch sein als im internen Log
        user_facing_error = error_message_from_ai_func 
        if AI_MSG_OPENROUTER_KEY_MISSING in user_facing_error or "API Key" in user_facing_error: # English only for user-facing
            user_facing_error = "AI service is currently misconfigured. Please contact support." # English only
        elif AI_MSG_NO_SUGGESTIONS_LIST in user_facing_error:
             user_facing_error = "The AI could not find any specific recommendations for this movie at the moment."
        # For other generic errors from ask_openrouter_for_movies, they are already user-friendly
        # Für andere generische Fehler von ask_openrouter_for_movies sind diese bereits benutzerfreundlich
        return jsonify({'success': False, 'recommendations': [], 'message': user_facing_error }), 503 # Service Unavailable or 500

    # If we are here, current_ai_suggestions_or_error should be a list of actual movie titles
    # Wenn wir hier sind, sollte current_ai_suggestions_or_error eine Liste tatsächlicher Filmtitel sein
    
    # Explicitly filter out the original movie title from suggestions, just in case AI includes it despite the prompt.
    # Den ursprünglichen Filmtitel explizit aus den Vorschlägen herausfiltern, nur für den Fall, dass die KI ihn trotz des Prompts einbezieht.
    original_movie_title_for_filtering = movie.title
    filtered_suggestions_with_potential_duplicates = [
        sugg_title for sugg_title in current_ai_suggestions_or_error 
        if sugg_title.lower().strip() != original_movie_title_for_filtering.lower().strip()
    ]

    # De-duplicate the list while preserving order of first appearance
    # Dedupliziere die Liste unter Beibehaltung der Reihenfolge des ersten Auftretens
    seen_titles = set()
    filtered_suggestions = []
    for sugg_title in filtered_suggestions_with_potential_duplicates:
        if sugg_title.lower().strip() not in seen_titles:
            filtered_suggestions.append(sugg_title)
            seen_titles.add(sugg_title.lower().strip())
    
    current_app.logger.info(f"AI (temp={temperature}) recommended for '{original_movie_title_for_filtering}' (exclusion: {len(user_history_before_this_call)} titles for User {user_id_for_logging}), Original suggestions: {current_ai_suggestions_or_error}, After self-filtering and deduplication: {filtered_suggestions}")

    recommendations_to_display_structured = []
    # Limit to a maximum of 5 suggestions from the de-duplicated list
    for title_str in filtered_suggestions[:5]: 
        if isinstance(title_str, str) and title_str: 
            recommendations_to_display_structured.append({'title': title_str, 'year': None})
    
    current_app.logger.info(f"Showing {len(recommendations_to_display_structured)} structured titles to user (ID: {user_id_for_logging}): {recommendations_to_display_structured}")

    if recommendations_to_display_structured:
        updated_user_history = list(user_history_before_this_call)
        newly_added_this_round_count = 0
        # Add only the actually displayed unique titles to the history for future exclusion
        # Füge nur die tatsächlich angezeigten eindeutigen Titel zur Historie für zukünftigen Ausschluss hinzu
        for displayed_rec in recommendations_to_display_structured:
            title_shown_str = displayed_rec['title']
            if isinstance(title_shown_str, str) and title_shown_str and title_shown_str.lower().strip() not in [h.lower().strip() for h in updated_user_history]: 
                updated_user_history.append(title_shown_str)
                newly_added_this_round_count += 1
        
        if newly_added_this_round_count > 0:
            while len(updated_user_history) > AI_RECOMMENDATION_HISTORY_LENGTH:
                updated_user_history.pop(0)
            session[AI_RECOMMENDATION_HISTORY_SESSION_KEY] = updated_user_history
            current_app.logger.info(f"{newly_added_this_round_count} new titles added to AI recommendation history for user (ID: {user_id_for_logging}). New length: {len(updated_user_history)}.")
        else:
            current_app.logger.info(f"No *new* titles added to AI history for user (ID: {user_id_for_logging}) as all displayed titles were already known.")

        return jsonify({'success': True, 'recommendations': recommendations_to_display_structured, 'message': 'Recommendations loaded successfully.'}), 200
    else:
        # This case implies that ask_openrouter_for_movies returned a list of empty strings or non-strings after cleaning, which is unlikely but possible.
        # Dieser Fall impliziert, dass ask_openrouter_for_movies nach der Bereinigung eine Liste von leeren Strings oder Nicht-Strings zurückgegeben hat, was unwahrscheinlich, aber möglich ist.
        current_app.logger.warning(f"AI recommendations for user {user_id_for_logging} (Movie: {movie.title}) resulted in an empty list after structuring.")
        return jsonify({'success': False, 'recommendations': [], 'message': 'AI could not provide recommendations in the expected format.'}), 500

def ask_openrouter_for_movies(prompt_content: str, temperature: float, expected_responses: int = 5) -> list[str]:
    """
    Makes a request to the OpenRouter API to get movie titles.
    `expected_responses`: Defines whether primarily a single title (for interpretation)
                          or a list of titles (for recommendations) is expected.
                          This doesn't directly affect the API request, but how the response is handled.

    Stellt eine Anfrage an die OpenRouter API, um Filmtitel zu erhalten.
    `expected_responses`: Definiert, ob primär ein einzelner Titel (für Interpretation)
                          oder eine Liste von Titeln (für Empfehlungen) erwartet wird.
                          Dies beeinflusst nicht direkt die API-Anfrage, aber die Handhabung der Antwort.
    """
    if not OPENROUTER_API_KEY:
        current_app.logger.error("OpenRouter API Key is not configured. / OpenRouter API-Schlüssel ist nicht konfiguriert.")
        return [AI_MSG_OPENROUTER_KEY_MISSING]

    current_app.logger.debug(f"Sending prompt to AI (model: {AI_MODEL_FOR_REQUESTS}, temp={temperature}, expecting ~{expected_responses} responses):\\n{prompt_content[:500]}...")

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            data=json.dumps({
                "model": AI_MODEL_FOR_REQUESTS,
                "messages": [{"role": "user", "content": prompt_content}],
                "temperature": temperature,
                "max_tokens": 150 if expected_responses > 1 else 50
            }),
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        raw_content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if raw_content:
            if expected_responses == 1:
                if raw_content == "NO_CLEAR_MOVIE_TITLE_FOUND": # Check against the specific, un-cleaned marker
                    return ["NO_CLEAR_MOVIE_TITLE_FOUND"]
                cleaned_title = _clean_ai_single_movie_title_response(raw_content)
                current_app.logger.debug(f"Raw AI single response: '{raw_content}', Processed: '{cleaned_title}'")
                return [cleaned_title] if cleaned_title else [] # Return empty list if cleaning results in empty
            else: # This is for expected_responses > 1 (recommendations)
                processed_titles = _clean_ai_movie_list_response(raw_content)
                current_app.logger.debug(f"Raw AI list response content: '{raw_content}', Processed list: {processed_titles}")
                return processed_titles
        else:
            current_app.logger.warning("No content received from OpenRouter API. / Kein Inhalt von OpenRouter API erhalten.")
            return [AI_MSG_NO_SUGGESTIONS_LIST] if expected_responses > 1 else [NO_CLEAR_MOVIE_TITLE_MARKER]

    except requests.exceptions.Timeout:
        current_app.logger.error("OpenRouter API request timed out. / OpenRouter API-Anfrage Zeitüberschreitung.")
        return [AI_MSG_REQUEST_TIMEOUT]
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"OpenRouter API RequestException: {e}. Response: {e.response.text if e.response else 'No response / Keine Antwort'}")
        error_message_for_user = AI_MSG_CONNECTION_ERROR_GENERIC
        if e.response is not None:
            try:
                error_detail = e.response.json()
                api_err_msg = error_detail.get('error', {}).get('message', str(e))
                error_message_for_user = AI_MSG_API_ERROR_DETAILED_TEMPLATE.format(error_message=api_err_msg)
            except ValueError: # Handle cases where response is not JSON
                api_err_msg = f"{e.response.status_code} - {e.response.text[:100]}"
                error_message_for_user = AI_MSG_API_ERROR_DETAILED_TEMPLATE.format(error_message=api_err_msg)
        return [error_message_for_user] 
    except Exception as e:
        current_app.logger.error(f"Generic error in ask_openrouter_for_movies: {e}. / Allgemeiner Fehler in ask_openrouter_for_movies: {e}.")
        return [AI_MSG_UNEXPECTED_ERROR_TEMPLATE.format(error_message=str(e))]

def _clean_ai_single_movie_title_response(raw_content: str) -> str:
    """
    Cleans a single movie title string received from the AI.
    Removes common prefixes, quotes, and trailing periods.

    Bereinigt einen einzelnen Filmtitel-String, der von der KI empfangen wurde.
    Entfernt gängige Präfixe, Anführungszeichen und nachgestellte Punkte.
    """
    cleaned_title = raw_content.strip()
    
    # Try to extract content from quotes first
    # Versuche zuerst, den Inhalt aus Anführungszeichen zu extrahieren
    match = re.search(r'"([^"]+)"', cleaned_title)
    if match:
        cleaned_title = match.group(1).strip()
    else:
        # If no quotes, remove common textual prefixes
        # Wenn keine Anführungszeichen, dann gängige textuelle Präfixe entfernen
        prefixes_to_remove = [
            r"the most probable movie title is:?",
            r"it is likely:?",
            r"the movie title is:?",
            r"the movie is:?",
            r"movie title:?",
            r"movie:?",
            r"title:?",
            r"^\s*-\s*", 
            r"^\s*\d+[.,\\)]\s*" 
        ]
        for prefix_pattern in prefixes_to_remove:
            cleaned_title = re.sub(f"^{prefix_pattern}", "", cleaned_title, flags=re.IGNORECASE).strip()

        # Remove surrounding quotes if they still exist (e.g. '"Title"' -> 'Title')
        # Entferne umschließende Anführungszeichen, falls sie noch existieren (z.B. '"Titel"' -> 'Titel')
        if (cleaned_title.startswith('"') and cleaned_title.endswith('"')) or \
           (cleaned_title.startswith("'") and cleaned_title.endswith("'")):
            cleaned_title = cleaned_title[1:-1].strip()
    
    # Remove trailing period if any
    # Entferne nachgestellten Punkt, falls vorhanden
    if cleaned_title.endswith('.'):
        cleaned_title = cleaned_title[:-1].strip()
        
    return cleaned_title

def _clean_ai_movie_list_response(raw_content: str) -> list[str]:
    """
    Cleans a list of movie titles received from the AI (typically newline-separated).
    Handles list prefixes, comma-separated titles within a line, and individual title cleaning.

    Bereinigt eine Liste von Filmtiteln, die von der KI empfangen wurden (typischerweise durch Zeilenumbrüche getrennt).
    Behandelt Listenpräfixe, kommagetrennte Titel innerhalb einer Zeile und die Bereinigung einzelner Titel.
    """
    processed_titles = []
    
    # Regex to remove leading numbers, bullets, or hyphens used for lists
    # Regex zum Entfernen führender Zahlen, Aufzählungszeichen oder Bindestriche, die für Listen verwendet werden
    list_prefix_pattern = re.compile(r"^(\d+[,.)]?\s*|[-*•]+\s*)")
    
    # Step 1: Split by newlines
    # Schritt 1: Nach Zeilenumbrüchen teilen
    lines_from_ai = [line.strip() for line in raw_content.split('\n') if line.strip()]

    for line_str in lines_from_ai:
        # Step 2: Remove list prefixes (like '*', '1.', '-') from the whole line first
        # Schritt 2: Listenpräfixe (wie '*', '1.', '-') zuerst von der gesamten Zeile entfernen
        line_without_list_prefix = list_prefix_pattern.sub("", line_str).strip()

        # Step 3: Titles on this line might be separated by commas or exist as a single item
        # Schritt 3: Titel in dieser Zeile könnten durch Kommas getrennt sein oder als einzelnes Element existieren
        # potential_titles_on_line = [t.strip() for t in line_without_list_prefix.split(',') if t.strip()] # OLD LOGIC
        
        # NEW LOGIC: Assume each line (after prefix cleaning) is one title.
        # NEUE LOGIK: Annahme, dass jede Zeile (nach Präfix-Bereinigung) ein Titel ist.
        title_candidate = line_without_list_prefix

        # for title_candidate in potential_titles_on_line: # OLD LOGIC LOOP
        if title_candidate: # Check if candidate is not empty
            # Step 4: Apply single title cleaning to each candidate
            # Schritt 4: Die Bereinigung für einzelne Titel auf jeden Kandidaten anwenden
            # Re-using _clean_ai_single_movie_title_response for consistency
            # Wiederverwendung von _clean_ai_single_movie_title_response für Konsistenz
            cleaned_title = _clean_ai_single_movie_title_response(title_candidate)
            
            if cleaned_title: # Ensure it's not empty after all cleaning
                              # Sicherstellen, dass es nach der gesamten Bereinigung nicht leer ist
                processed_titles.append(cleaned_title)
                        
    return processed_titles

if __name__ == '__main__':
    app.run(debug=True)