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
        g.user = User.query.get(user_id)

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
    top_movies = (
        db.session.query(
            Movie,
            func.count(UserMovie.id).label('user_count'),
            func.avg(Movie.community_rating).label('avg_rating')
        )
        .join(UserMovie, UserMovie.movie_id == Movie.id)
        .group_by(Movie.id)
        .order_by(desc('user_count'), desc(func.avg(Movie.community_rating)))
        .limit(10)
        .all()
    )
    return render_template('home.html', top_movies=top_movies)

@app.route('/login', methods=['POST'])
def login():
    """
    Login route: handles user login attempts via POST request.
    Expects 'username' in form data. Returns JSON response.

    Login-Route: Verarbeitet Benutzer-Login-Versuche per POST-Request.
    Erwartet 'username' in den Formulardaten. Gibt JSON-Antwort zurück.
    """
    username = request.form.get('username', '').strip().lower()
    user = User.query.filter_by(name=username).first()
    
    if user:
        session['user_id'] = user.id
        return jsonify({'success': True, 'redirect': f'/users/{user.id}'})
    return jsonify({'success': False, 'message': 'User not found.'})

@app.route('/register', methods=['POST'])
def register():
    """
    Registration route: handles new user registration attempts via POST request.
    Expects 'username' in form data. Returns JSON response.

    Registrierungs-Route: Verarbeitet Registrierungsversuche neuer Benutzer per POST-Request.
    Erwartet 'username' in den Formulardaten. Gibt JSON-Antwort zurück.
    """
    username = request.form.get('username', '').strip().lower()
    
    if User.query.filter_by(name=username).first():
        return jsonify({'success': False, 'message': 'Username already exists.'})
    
    user = User(name=username)
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    return jsonify({'success': True, 'redirect': f'/users/{user.id}'})

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
        # Benutzer zum Anzeigen des Namens abrufen
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'warning')
            return redirect('/users')
        
        # Get UserMovie links to have both Movie details and User rating
        # UserMovie-Verknüpfungen abrufen, um sowohl Filmdetails als auch Benutzerbewertungen zu erhalten
        user_movie_relations = UserMovie.query.filter_by(user_id=user_id).all()
        
    except Exception as e:
        # Log error for server-side diagnostics.
        # Logge den Fehler für serverseitige Diagnose.
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
        name = request.form.get('name')
        if name:
            if User.query.filter(func.lower(User.name) == func.lower(name)).first():
                flash(f'User "{name}" already exists.', 'warning')
            else:
                new_user = User(name=name)
                db.session.add(new_user)
                db.session.commit()
                flash(f'User "{name}" added successfully.', 'success')
                return redirect(url_for('list_users'))
        else:
            flash('Username cannot be empty.', 'danger')
    return render_template('add_user.html') # Erstellt eine einfache Vorlage oder leitet um

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
    user = User.query.get_or_404(user_id)
    
    # Initial states for template variables
    # Initialzustände für Template-Variablen
    user_search_input_value = request.args.get('user_search_input', '')
    ai_suggested_title = None
    ai_message = None
    omdb_data_for_template = None
    omdb_details_for_template = None
    rating5_for_template = None
    show_details_form = False
    title_for_omdb_search_value = request.args.get('title_for_omdb_search', '').strip()
    movie_to_add_id_value = request.args.get('movie_to_add_id', type=int)
    source_movie_id_value = request.args.get('source_movie_id', type=int)

    hide_initial_search_form = False

    if request.method == 'GET':
        if movie_to_add_id_value or title_for_omdb_search_value:
            hide_initial_search_form = True

        # Phase 2b: Movie ID was passed directly (e.g., from AI recommendations)
        # Phase 2b: Film-ID wurde direkt übergeben (z.B. von KI-Empfehlungen)
        if movie_to_add_id_value:
            current_app.logger.info(f"User {user_id} will add existing movie_id: {movie_to_add_id_value}")
            movie_from_db = Movie.query.get(movie_to_add_id_value)
            if movie_from_db:
                # Provide data as if it came from OMDb fetch
                # Daten bereitstellen, als ob sie von einem OMDb-Abruf stammen
                omdb_data_for_template = {
                    'Response': 'True',
                    'Title': movie_from_db.title,
                    'Year': str(movie_from_db.year) if movie_from_db.year else 'N/A',
                    'Poster': movie_from_db.poster_url,
                    'Director': movie_from_db.director,
                    'imdbRating': str(movie_from_db.community_rating * 2) if movie_from_db.community_rating is not None else 'N/A'
                }
                omdb_details_for_template = {
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
                    rating5_for_template = movie_from_db.community_rating
                else:
                    user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_from_db.id).first()
                    if user_movie_link and user_movie_link.user_rating is not None:
                        rating5_for_template = user_movie_link.user_rating

                show_details_form = True
                user_search_input_value = movie_from_db.title 
            else:
                flash(f'Movie with ID {movie_to_add_id_value} not found in database.', 'danger')
                return redirect(url_for('list_user_movies', user_id=user_id))

        # Phase 2a: User clicked 'Load Movie Details' with AI-suggested title (higher priority)
        # Phase 2a: Benutzer klickte auf 'Filmdetails laden' mit KI-vorgeschlagenem Titel (höhere Priorität)
        elif 'title_for_omdb_search' in request.args and title_for_omdb_search_value:
            hide_initial_search_form = True
            # Log OMDb search initiation.
            # Logge die Initiierung der OMDb-Suche.
            current_app.logger.info(f"User {user_id} initiated OMDb search with AI-suggested title: '{title_for_omdb_search_value}'")
            user_search_input_value = request.args.get('user_search_input', user_search_input_value)

            params = {'apikey': OMDB_API_KEY, 't': title_for_omdb_search_value}
            try:
                resp = requests.get('http://www.omdbapi.com/', params=params, timeout=10)
                resp.raise_for_status()
                omdb_data_for_template = resp.json()
            except requests.exceptions.RequestException as e:
                # Log OMDb API request failure.
                # Logge fehlgeschlagene OMDb-API-Anfrage.
                current_app.logger.error(f"OMDb API request failed for title '{title_for_omdb_search_value}': {e}")
                omdb_data_for_template = {'Response': 'False', 'Error': str(e)}
                flash(f"Error connecting to OMDb for title '{title_for_omdb_search_value}': {str(e)[:100]}.", "danger")

            if omdb_data_for_template and omdb_data_for_template.get('Response') == 'True':
                show_details_form = True
                omdb_details_for_template = {
                    'plot': omdb_data_for_template.get('Plot'),
                    'runtime': omdb_data_for_template.get('Runtime'),
                    'awards': omdb_data_for_template.get('Awards'),
                    'languages': omdb_data_for_template.get('Language'),
                    'genre': omdb_data_for_template.get('Genre'),
                    'actors': omdb_data_for_template.get('Actors'),
                    'writer': omdb_data_for_template.get('Writer'),
                    'country': omdb_data_for_template.get('Country'),
                    'metascore': omdb_data_for_template.get('Metascore'),
                    'rated': omdb_data_for_template.get('Rated'),
                    'imdb_id': omdb_data_for_template.get('imdbID')
                }
                raw_rating = omdb_data_for_template.get('imdbRating')
                if raw_rating and raw_rating != 'N/A':
                    try:
                        rating10 = float(raw_rating)
                        rating5_for_template = round(rating10 / 2 * 2) / 2
                    except ValueError:
                        pass
            else:
                error_msg_from_omdb = omdb_data_for_template.get('Error', 'Unknown OMDb error') if omdb_data_for_template else 'No response from OMDb.'
                ai_message = f"OMDb could not find details for the title: '{title_for_omdb_search_value}'. Error: {error_msg_from_omdb}"
                # Log OMDb search failure.
                # Logge fehlgeschlagene OMDb-Suche.
                current_app.logger.warning(f"OMDb search failed for title '{title_for_omdb_search_value}': {error_msg_from_omdb}")
                show_details_form = False
        
        # Phase 1: User entered a search to get AI suggestion (only if not Phase 2)
        # Phase 1: Benutzer gab eine Suche ein, um einen KI-Vorschlag zu erhalten (nur wenn nicht Phase 2)
        elif 'user_search_input' in request.args and user_search_input_value:
            # Log AI movie search initiation.
            # Logge die Initiierung der KI-Filmsuche.
            current_app.logger.info(f"User {user_id} initiated AI movie search with input: '{user_search_input_value}'")
            ki_result = get_ai_interpreted_movie_title(user_search_input_value)

            if ki_result == NO_CLEAR_MOVIE_TITLE_MARKER or ki_result is None:
                ai_message = "AI could not identify a clear movie title. Please try a different title or description."
                # Log when AI could not find title.
                # Logge, wenn die KI keinen Titel finden konnte.
                current_app.logger.info(f"AI could not find title for user input: '{user_search_input_value}'")
            else:
                ai_suggested_title = ki_result
                # Log AI suggested title.
                # Logge den von der KI vorgeschlagenen Titel.
                current_app.logger.info(f"AI suggested title '{ai_suggested_title}' for input '{user_search_input_value}'")

        return render_template(
            'add_movie.html',
            user=user,
            current_year=datetime.now().year,
            user_search_input_value=user_search_input_value,
            ai_suggested_title=ai_suggested_title,
            ai_message=ai_message,
            omdb=omdb_data_for_template,
            omdb_details=omdb_details_for_template,
            rating5=rating5_for_template,
            show_details_form=show_details_form,
            hide_initial_search_form=hide_initial_search_form,
            source_movie_id_for_template=source_movie_id_value,
        )

    elif request.method == 'POST':
        title_from_omdb_form = request.form.get('title_from_omdb', '').strip()
        if not title_from_omdb_form: 
            flash('Error: Movie title for adding was missing. Please try the search again.', 'danger')
            return redirect(url_for('add_movie', user_id=user_id))

        director = request.form.get('director', '').strip()
        year_str = request.form.get('year', '').strip()
        rating_str = request.form.get('rating', '').strip()
        poster_url = request.form.get('poster_url', '').strip()
        plot = request.form.get('plot', '').strip()
        runtime = request.form.get('runtime', '').strip()
        awards = request.form.get('awards', '').strip()
        languages = request.form.get('languages', '').strip()
        genre = request.form.get('genre', '').strip()
        actors = request.form.get('actors', '').strip()
        writer = request.form.get('writer', '').strip()
        country = request.form.get('country', '').strip()
        metascore = request.form.get('metascore', '').strip()
        rated = request.form.get('rated', '').strip()
        imdb_id = request.form.get('imdb_id', '').strip()
        original_user_search_input_for_post = request.form.get('original_user_search_input', '')

        year = None
        if year_str and year_str.isdigit():
            year = int(year_str)
        
        rating = None
        if rating_str:
            try:
                rating = float(rating_str)
                if not (0 <= rating <= 5):
                    flash('Rating must be between 0 and 5.', 'warning')
                    return redirect(url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input_for_post))
            except ValueError:
                flash('Rating must be a numeric value.', 'warning')
                return redirect(url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input_for_post))

        omdb_suggested_rating_str = request.form.get('omdb_suggested_rating', '')
        omdb_rating_for_community_param = None
        if omdb_suggested_rating_str:
            try:
                omdb_rating_for_community_param = float(omdb_suggested_rating_str)
                if not (0 <= omdb_rating_for_community_param <= 5):
                    omdb_rating_for_community_param = None
            except ValueError:
                pass

        movie_added = data_manager.add_movie(
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
        if movie_added:
            flash(f"Movie '{title_from_omdb_form}' added successfully.", 'success')
            if source_movie_id_value:
                return redirect(url_for('movie_page', movie_id=source_movie_id_value))
            return redirect(url_for('list_user_movies', user_id=user_id))
        else:
            flash(f"Could not add movie '{title_from_omdb_form}'. It might already be in your list or an error occurred.", 'danger')
            redirect_url = url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input_for_post)
            if source_movie_id_value:
                redirect_url = url_for('movie_page', movie_id=source_movie_id_value)
            return redirect(redirect_url)

    return redirect(url_for('add_movie', user_id=user_id, hide_initial_search_form=hide_initial_search_form, source_movie_id_for_template=source_movie_id_value))

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

    movie = Movie.query.get_or_404(movie_id)
    user_movie_link = UserMovie.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()

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
                    return render_template('update_movie_rating.html', user=g.user, movie=movie, current_user_rating=user_movie_link.user_rating)
            except ValueError:
                flash('Rating must be a number.', 'warning')
                return render_template('update_movie_rating.html', user=g.user, movie=movie, current_user_rating=user_movie_link.user_rating)

        success = data_manager.update_user_rating_for_movie(user_id=g.user.id, movie_id=movie.id, new_rating=new_user_rating)

        if success:
            flash(f"Your rating for '{movie.title}' has been updated.", 'success')
            return redirect(url_for('list_user_movies', user_id=g.user.id))
        else:
            flash('Could not update your rating for this movie.', 'error')
            return render_template('update_movie_rating.html', user=g.user, movie=movie, current_user_rating=user_movie_link.user_rating)
    
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
    """
    movie = Movie.query.get_or_404(movie_id)
    comments = Comment.query.filter_by(movie_id=movie_id).order_by(Comment.created_at.desc()).all()
    
    return jsonify({
        'movie': {
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
        },
        'comments': [{
            'id': c.id,
            'text': c.text,
            'user': c.user.name,
            'created_at': c.created_at.isoformat()
        } for c in comments]
    })

@app.route('/movie/<int:movie_id>/comment', methods=['POST'])
def add_movie_comment(movie_id):
    """
    Add a comment to a movie (JSON endpoint).
    Requires user to be logged in. Expects 'text' in form data.

    Fügt einen Kommentar zu einem Film hinzu (JSON-Endpunkt).
    Erfordert, dass der Benutzer angemeldet ist. Erwartet 'text' in den Formulardaten.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in.'})
    
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Comment cannot be empty.'})
    
    comment = Comment(
        movie_id=movie_id,
        user_id=session['user_id'],
        text=text
    )
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({'success': True})

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
        movie = Movie.query.get_or_404(movie_id)
        current_user_specific_rating = None
        is_movie_in_user_list = False

        if g.user:
            user_movie_link = UserMovie.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()
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
    Handles adding a comment from the movie detail page.
    Verarbeitet das Hinzufügen eines Kommentars von der Filmdetailseite.
    """
    if 'user_id' not in session:
        flash('You must be logged in to comment.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id))

    user = User.query.get(session['user_id'])
    movie = Movie.query.get_or_404(movie_id)

    text = request.form.get('text', '').strip()
    if not text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id))

    try:
        comment = Comment(movie_id=movie.id, user_id=user.id, text=text)
        db.session.add(comment)
        db.session.commit()
        flash('Comment added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        # Log error when adding comment from page fails.
        # Logge Fehler, wenn das Hinzufügen eines Kommentars von der Seite fehlschlägt.
        current_app.logger.error(f"Error adding comment from page: {e}")
        flash('Error adding comment. Please try again.', 'danger')
    
    return redirect(url_for('movie_page', movie_id=movie_id))

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
        movie_title_query = Movie.query.get(movie_id)
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
    movie = Movie.query.get(movie_id)
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found.'}), 404

    user_history_before_this_call = session.get(AI_RECOMMENDATION_HISTORY_SESSION_KEY, [])
    exclusion_text = ""
    if user_history_before_this_call:
        movies_to_exclude_list_str = "\n".join([f"- \"{title}\"" for title in user_history_before_this_call])
        exclusion_text = EXCLUSION_CLAUSE_TEMPLATE.format(movies_to_exclude_list_format=movies_to_exclude_list_str)

    prompt = MOVIE_RECOMMENDATION_PROMPT_TEMPLATE.format(movie_title=movie.title, exclusion_clause=exclusion_text)
    # Log constructed AI prompt for recommendations.
    # Logge den erstellten KI-Prompt für Empfehlungen.
    current_app.logger.debug(f"Constructed AI Prompt for user {session.get('user_id', 'N/A')} (Movie: {movie.title}):\\n{prompt}")
    
    try:
        temperature_str = request.args.get('temp', str(DEFAULT_AI_TEMPERATURE_RECOMMEND))
        temperature = float(temperature_str)
        if not (0.0 <= temperature <= 2.0):
            temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND
            # Log invalid temperature fallback.
            # Logge Fallback bei ungültiger Temperatur.
            current_app.logger.warning(f"Invalid temperature value '{temperature_str}' received, falling back to {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")
    except ValueError:
        temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND
        # Log temperature conversion fallback.
        # Logge Fallback bei Temperaturkonvertierung.
        current_app.logger.warning(f"Could not convert temperature value '{request.args.get('temp')}' to float, falling back to {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")

    try:
        current_ai_suggestions = ask_openrouter_for_movies(prompt_content=prompt, temperature=temperature, expected_responses=5)
        # Log AI recommendations.
        # Logge KI-Empfehlungen.
        current_app.logger.info(f"AI (temp={temperature}) recommended for '{movie.title}' (exclusion: {len(user_history_before_this_call)} titles for User {session.get('user_id','N/A')}): {current_ai_suggestions}")

        is_error_response = False
        if current_ai_suggestions and len(current_ai_suggestions) == 1:
            title_lower = current_ai_suggestions[0].lower()
            if any(err_phrase in title_lower for err_phrase in ["error", "not configured", "did not return", "failed to connect", "timed out", "api key"]):
                is_error_response = True

        if is_error_response:
            error_msg_for_user = f"AI service error: {current_ai_suggestions[0]}." # English only
            return jsonify({'success': False, 'recommendations': [], 'message': error_msg_for_user })

        # Convert list of title strings to list of objects for the frontend
        # Konvertiere die Liste der Titel-Strings in eine Liste von Objekten für das Frontend
        recommendations_to_display_structured = []
        if current_ai_suggestions:
            for title_str in current_ai_suggestions:
                if isinstance(title_str, str) and title_str: # Ensure it's a non-empty string / Sicherstellen, dass es ein nicht-leerer String ist
                    recommendations_to_display_structured.append({'title': title_str, 'year': None}) # Add year as None for now / Jahr vorerst als None hinzufügen
                # Optionally, handle cases where title_str might not be a string, though ask_openrouter_for_movies should return list[str]
                # Optional können Fälle behandelt werden, in denen title_str kein String ist, obwohl ask_openrouter_for_movies list[str] zurückgeben sollte

        # Log titles shown to user.
        # Logge die dem Benutzer angezeigten Titel.
        current_app.logger.info(f"Showing {len(recommendations_to_display_structured)} structured titles to user (ID: {session.get('user_id','N/A')}): {recommendations_to_display_structured}")

        if recommendations_to_display_structured: # Check the structured list / Überprüfe die strukturierte Liste
            updated_user_history = list(user_history_before_this_call)
            newly_added_this_round_count = 0
            # Use the original title strings for history management
            # Verwende die ursprünglichen Titel-Strings für das Verlaufsmanagement
            for title_shown_str in current_ai_suggestions: 
                if isinstance(title_shown_str, str) and title_shown_str and title_shown_str not in updated_user_history: 
                    updated_user_history.append(title_shown_str)
                    newly_added_this_round_count += 1
            
            if newly_added_this_round_count > 0:
                while len(updated_user_history) > AI_RECOMMENDATION_HISTORY_LENGTH:
                    updated_user_history.pop(0)
                session[AI_RECOMMENDATION_HISTORY_SESSION_KEY] = updated_user_history
                # Log AI recommendation history update.
                # Logge die Aktualisierung des KI-Empfehlungsverlaufs.
                current_app.logger.info(f"{newly_added_this_round_count} new titles added to AI recommendation history for user (ID: {session.get('user_id', 'N/A')}). New length: {len(updated_user_history)}. Content: {updated_user_history}")
            else:
                # Log if no new titles were added to history.
                # Logge, wenn keine neuen Titel zum Verlauf hinzugefügt wurden.
                current_app.logger.info(f"No *new* titles added to AI history for user (ID: {session.get('user_id', 'N/A')}) as all displayed titles were already known.")

        return jsonify({'success': True, 'recommendations': recommendations_to_display_structured})
    
    except requests.exceptions.RequestException as e:
        # Log OpenRouter API RequestException.
        # Logge OpenRouter API RequestException.
        current_app.logger.error(f"OpenRouter API RequestException in Route: {e}")
        if e.response is not None and e.response.status_code in [401, 403] or ("OPENROUTER_API_KEY" in str(e)):
            msg = "OpenRouter API key is missing, invalid, or quota exceeded. Please check server configuration." # English only
        else:
            msg = f"Failed to get AI recommendations due to a network or API issue: {str(e)}." # English only
        return jsonify({'success': False, 'message': msg}), 500
    except Exception as e:
        # Log generic error getting AI recommendations.
        # Logge generischen Fehler beim Abrufen von KI-Empfehlungen.
        current_app.logger.error(f"Error getting AI recommendations in Route: {e}")
        return jsonify({'success': False, 'message': f"Failed to get AI recommendations: {str(e)}."}), 500 # English only for user-facing

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
        # Log error if OpenRouter API Key is not configured.
        # Logge Fehler, wenn der OpenRouter API-Schlüssel nicht konfiguriert ist.
        current_app.logger.error("OpenRouter API Key is not configured. / OpenRouter API-Schlüssel ist nicht konfiguriert.")
        return ["OpenRouter API Key not configured on server."] # English only for user-facing

    # Log prompt being sent to AI.
    # Logge den an die KI gesendeten Prompt.
    current_app.logger.debug(f"Sending prompt to AI (temp={temperature}, expecting ~{expected_responses} responses):\\n{prompt_content[:500]}...")

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            },
            data=json.dumps({
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": prompt_content}
                ],
                "temperature": temperature,
                "max_tokens": 150 if expected_responses > 1 else 50
            }),
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if content:
            if expected_responses == 1 and content != "NO_CLEAR_MOVIE_TITLE_FOUND":
                cleaned_title = content.strip()
                
                match = re.search(r'"([^"]+)"', cleaned_title)
                if match:
                    cleaned_title = match.group(1).strip()
                else:
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

                    if (cleaned_title.startswith('"') and cleaned_title.endswith('"')) or \
                       (cleaned_title.startswith("'") and cleaned_title.endswith("'")):
                        cleaned_title = cleaned_title[1:-1].strip()
                
                if cleaned_title.endswith('.'):
                    cleaned_title = cleaned_title[:-1].strip()

                # Log raw and processed AI single response.
                # Logge rohe und verarbeitete einzelne KI-Antwort.
                current_app.logger.debug(f"Raw AI single response: '{content}', Processed: '{cleaned_title}'")
                return [cleaned_title] if cleaned_title else []
            elif content == "NO_CLEAR_MOVIE_TITLE_FOUND":
                 return ["NO_CLEAR_MOVIE_TITLE_FOUND"]
            else: # This is for expected_responses > 1 (recommendations)
                processed_titles = []
                
                # Regex to remove leading numbers, bullets, or hyphens used for lists
                # Regex zum Entfernen führender Zahlen, Aufzählungszeichen oder Bindestriche, die für Listen verwendet werden
                list_prefix_pattern = re.compile(r"^(\d+[,.)]?\s*|[-*•]+\s*)")
                
                # Consistent list of textual prefixes to remove, similar to single response cleaning
                # Konsistente Liste zu entfernender textueller Präfixe, ähnlich der Einzelantwort-Bereinigung
                textual_prefixes_to_remove_patterns = [
                    r"the most probable movie title is:?",
                    r"it is likely:?",
                    r"the movie title is:?",
                    r"the movie is:?",
                    r"movie title:?",
                    r"movie:?",
                    r"title:?",
                    # Adding patterns that were in single response but might also appear here
                    # Hinzufügen von Mustern, die in der Einzelantwort waren, aber auch hier erscheinen könnten
                    r"^\s*-\s*", # Handles cases where a dash might remain if not caught by list_prefix_pattern
                                  # Behandelt Fälle, in denen ein Bindestrich verbleiben könnte, wenn er nicht vom list_prefix_pattern erfasst wird
                ]

                # Step 1: Split by newlines
                # Schritt 1: Nach Zeilenumbrüchen teilen
                lines_from_ai = [line.strip() for line in content.split('\n') if line.strip()]

                for line_str in lines_from_ai:
                    # Step 2: Remove list prefixes (like '*', '1.', '-') from the whole line first
                    # Schritt 2: Listenpräfixe (wie '*', '1.', '-') zuerst von der gesamten Zeile entfernen
                    line_without_list_prefix = list_prefix_pattern.sub("", line_str).strip()

                    # Step 3: Now, titles on this line might be separated by commas
                    # Schritt 3: Nun könnten Titel in dieser Zeile durch Kommas getrennt sein
                    potential_titles_on_line = [t.strip() for t in line_without_list_prefix.split(',') if t.strip()]

                    for title_candidate in potential_titles_on_line:
                        # Step 4: Apply remaining cleaning to each individual title candidate
                        # Schritt 4: Die verbleibende Bereinigung auf jeden einzelnen Titelkandidaten anwenden
                        cleaned_title = title_candidate # Start with this / Damit beginnen
                        
                        # Try to extract content from quotes if present
                        # Versuche, Inhalt aus Anführungszeichen zu extrahieren, falls vorhanden
                        match_quotes = re.search(r'"([^"]+)"', cleaned_title)
                        if match_quotes:
                            cleaned_title = match_quotes.group(1).strip()
                        else:
                            # If no quotes, then apply textual prefix removal
                            # Wenn keine Anführungszeichen vorhanden sind, dann textuelle Präfixentfernung anwenden
                            for text_prefix_regex_str in textual_prefixes_to_remove_patterns:
                                cleaned_title = re.sub(f"^{text_prefix_regex_str}", "", cleaned_title, flags=re.IGNORECASE).strip()
                            
                            # Remove leading/trailing quotes if they were not handled by regex and are hugging the title
                            # Entferne führende/nachfolgende Anführungszeichen, wenn sie nicht von Regex behandelt wurden und den Titel umschließen
                            if (cleaned_title.startswith('"') and cleaned_title.endswith('"')) or \
                               (cleaned_title.startswith("'") and cleaned_title.endswith("'")):
                                cleaned_title = cleaned_title[1:-1].strip()
                        
                        # Remove trailing period if any
                        # Entferne nachfolgenden Punkt, falls vorhanden
                        if cleaned_title.endswith('.'):
                            cleaned_title = cleaned_title[:-1].strip()

                        if cleaned_title: # Ensure it's not empty after all cleaning / Sicherstellen, dass es nach der gesamten Bereinigung nicht leer ist
                            processed_titles.append(cleaned_title)
                        
                # Log raw and processed AI list response.
                # Logge rohe und verarbeitete KI-Listenantwort.
                current_app.logger.debug(f"Raw AI list response: {lines_from_ai}, Processed: {processed_titles}")
                return processed_titles
        else:
            # Log warning if no content received from OpenRouter API.
            # Logge Warnung, wenn kein Inhalt von der OpenRouter API empfangen wurde.
            current_app.logger.warning("No content received from OpenRouter API. / Kein Inhalt von OpenRouter API erhalten.")
            return ["AI did not return any suggestions."] if expected_responses > 1 else [NO_CLEAR_MOVIE_TITLE_MARKER] # English only for user-facing

    except requests.exceptions.Timeout:
        # Log OpenRouter API request timeout.
        # Logge Zeitüberschreitung der OpenRouter API-Anfrage.
        current_app.logger.error(f"OpenRouter API request timed out. / OpenRouter API-Anfrage Zeitüberschreitung.")
        return ["AI service request timed out. Please try again later."] # English only for user-facing
    except requests.exceptions.RequestException as e:
        # Log OpenRouter API RequestException.
        # Logge OpenRouter API RequestException.
        current_app.logger.error(f"OpenRouter API RequestException: {e}. Response: {e.response.text if e.response else 'No response / Keine Antwort'}")
        error_message_user = "Error connecting to AI service." # English only
        if e.response is not None:
            try:
                error_detail = e.response.json()
                error_message_user = f"AI API Error: {error_detail.get('error', {}).get('message', str(e))}." # English only
            except ValueError: # Handle cases where response is not JSON / Behandle Fälle, in denen die Antwort kein JSON ist
                error_message_user = f"AI API Error (non-JSON response): {e.response.status_code} - {e.response.text[:100]}." # English only
        return [error_message_user] 
    except Exception as e:
        # Log generic error in ask_openrouter_for_movies.
        # Logge generischen Fehler in ask_openrouter_for_movies.
        current_app.logger.error(f"Generic error in ask_openrouter_for_movies: {e}. / Allgemeiner Fehler in ask_openrouter_for_movies: {e}.")
        return [f"An unexpected error occurred with the AI service: {str(e)}."] # English only for user-facing

if __name__ == '__main__':
    app.run(debug=True)