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
# DEEP_SEEK_API_KEY = os.getenv('DEEP_SEEK_API_KEY') # Nicht mehr verwendet
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

csrf = CSRFProtect(app) # Initialize CSRFProtect

# Datenbank an die App binden
# Bind database to the app
db.init_app(app)

# Blueprints registrieren
# Register blueprints
app.register_blueprint(api_blueprint, url_prefix='/api')

# DataManager instanziieren
# Instantiate DataManager
data_manager = SQLiteDataManager()

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
    "\n\nPlease **strictly avoid suggesting any of the following titles** as they have been recommended to this user recently: {movies_to_exclude}. "
    "Your new suggestions must be different from this list."
)
AI_RECOMMENDATION_HISTORY_SESSION_KEY = 'ai_recommendation_history'
AI_RECOMMENDATION_HISTORY_LENGTH = 20 
DEFAULT_AI_TEMPERATURE_RECOMMEND = 0.7 
DEFAULT_AI_TEMPERATURE_INTERPRET = 0.3 # Niedrigere Temperatur für präzisere Interpretation
NO_CLEAR_MOVIE_TITLE_MARKER = "NO_CLEAR_MOVIE_TITLE_FOUND_INTERNAL"

# --- Hilfsfunktion für KI-Titelinterpretation ---
def get_ai_interpreted_movie_title(user_input: str, temperature: float = DEFAULT_AI_TEMPERATURE_INTERPRET) -> Optional[str]:
    """
    Verwendet KI, um die Benutzereingabe zu interpretieren und den wahrscheinlichsten Filmtitel zu finden.
    Gibt den Titel oder NO_CLEAR_MOVIE_TITLE_MARKER zurück.
    """
    if not user_input:
        return NO_CLEAR_MOVIE_TITLE_MARKER

    prompt = AI_MOVIE_IDENTIFICATION_PROMPT_TEMPLATE.format(user_input=user_input)
    current_app.logger.debug(f"Constructed AI Title Identification Prompt:\n{prompt}")
    
    # ask_openrouter_for_movies gibt eine Liste zurück; wir erwarten hier nur einen Titel oder die spezielle Phrase
    raw_ai_response_list = ask_openrouter_for_movies(prompt_content=prompt, temperature=temperature, expected_responses=1)
    
    if raw_ai_response_list:
        # Die Bereinigung von Nummerierungen ist hier weniger relevant, da wir einen einzelnen Titel erwarten,
        # aber zur Sicherheit wenden wir sie trotzdem an.
        interpreted_title = raw_ai_response_list[0] # Nehmen das erste Element der (normalerweise) Ein-Element-Liste
        
        if interpreted_title == "NO_CLEAR_MOVIE_TITLE_FOUND":
            current_app.logger.info(f"AI indicated no clear movie title for input: '{user_input}'")
            return NO_CLEAR_MOVIE_TITLE_MARKER
        
        # Zusätzliche Prüfung: Wenn die KI trotz allem mit einer Fehlermeldung antwortet (was ask_openrouter_for_movies als Liste zurückgibt)
        if "error" in interpreted_title.lower() or "not configured" in interpreted_title.lower() or "timed out" in interpreted_title.lower():
            current_app.logger.warning(f"AI returned an error phrase instead of a title or marker: {interpreted_title}")
            return NO_CLEAR_MOVIE_TITLE_MARKER # Behandeln wie nicht gefunden
            
        current_app.logger.info(f"AI interpreted user input '{user_input}' as movie title: '{interpreted_title}'")
        return interpreted_title
    else:
        current_app.logger.warning(f"AI returned no response for title interpretation of input: '{user_input}'")
        return NO_CLEAR_MOVIE_TITLE_MARKER

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

@app.context_processor
def inject_user_status():
    is_logged_in = g.user is not None
    return dict(g_is_user_logged_in=is_logged_in, g_current_user=g.user)

@app.route('/')
def home():
    """
    Home-Route mit Top-Filmen
    Zeigt die Startseite der Anwendung mit den Top-Filmen.
    Home route: displays the application's welcome page with top movies.
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
    """Login-Route"""
    username = request.form.get('username', '').strip().lower()
    user = User.query.filter_by(name=username).first()
    
    if user:
        session['user_id'] = user.id
        return jsonify({'success': True, 'redirect': f'/users/{user.id}'})
    return jsonify({'success': False, 'message': 'Benutzer nicht gefunden'})

@app.route('/register', methods=['POST'])
def register():
    """Registrierungs-Route"""
    username = request.form.get('username', '').strip().lower()
    
    if User.query.filter_by(name=username).first():
        return jsonify({'success': False, 'message': 'Benutzername existiert bereits'})
    
    user = User(name=username)
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    return jsonify({'success': True, 'redirect': f'/users/{user.id}'})

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    g.user = None # Auch g.user zurücksetzen für den aktuellen Request
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/users')
def list_users():
    """
    Benutzerliste-Route
    Zeigt alle registrierten Benutzer an.
    Users list route: displays all registered users.
    """
    users = data_manager.get_all_users()
    return render_template('users.html', users=users)

@app.route('/users/<int:user_id>')
def list_user_movies(user_id):
    """
    Benutzer-Filmliste-Route
    Zeigt alle Lieblingsfilme eines bestimmten Benutzers an.
    User movies list route: displays a specific user's favorite movies.
    """
    try:
        # Fetch user for displaying name
        user = User.query.get(user_id)
        if not user:
            flash('Benutzer nicht gefunden. / User not found.')
            return redirect('/users')
        
        # Hole die UserMovie-Verknüpfungen, um sowohl Movie-Details als auch User-Rating zu haben
        user_movie_relations = UserMovie.query.filter_by(user_id=user_id).all()
        
    except Exception as e:
        current_app.logger.error(f"Error in list_user_movies: {e}")
        return render_template('500.html'), 500

    # IS_USER_LOGGED_IN für das Template setzen (ist hier immer der Fall, da es die eigene Liste ist)
    is_user_logged_in = True # Vereinfacht, da es die /users/<id> Route ist
    return render_template('movies.html', user_movie_relations=user_movie_relations, user=user, IS_USER_LOGGED_IN=is_user_logged_in)

# Benutzer erstellen-Route
# Create user route
@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    """
    Benutzer erstellen-Route
    Zeigt das Formular zum Hinzufügen eines neuen Benutzers und verarbeitet die Eingabe.
    Create user route: displays form for adding a new user and processes submission.
    """
    if request.method == 'POST':
        # Read, strip, normalize to lowercase / Lese, trimme und wandle in Kleinbuchstaben um
        name = request.form.get('name', '').strip().lower()
        # Prüfe auf bestehenden Benutzernamen / Check for existing username
        if any(u.name == name for u in data_manager.get_all_users()):
            flash(
                'Benutzername existiert bereits. Bitte erweitere ihn, z.B. mit deinem Geburtstag im Format TTMM. / '
                'Username already exists. Please extend it, e.g. with your birthday in DDMM format.'
            )
            return redirect('/add_user')
        if not name:
            flash('Bitte geben Sie einen Namen ein. / Please enter a name.')
            return redirect('/add_user')
        try:
            user = data_manager.add_user(name)
        except Exception as e:
            current_app.logger.error(f"Error in add_user: {e}")
            flash('Fehler beim Erstellen des Benutzers. / Error creating user.')
            return redirect('/add_user')
        if user:
            flash(f"Benutzer {user.name} erstellt. / User {user.name} created.")
            return redirect('/users')
        else:
            flash(
                'Benutzername existiert bereits. Bitte erweitere ihn, z.B. mit deinem Geburtsjahr / '
                'Username already exists. Please extend it, e.g. with your birthyear'
            )
            return redirect('/add_user')
    return render_template('add_user.html')

@app.route('/users/<int:user_id>/add_movie', methods=['GET', 'POST'])
def add_movie(user_id):
    user = User.query.get_or_404(user_id)
    
    # Initialzustände für Template-Variablen
    user_search_input_value = request.args.get('user_search_input', '') # Für das Festhalten der Eingabe
    ai_suggested_title = None # Von KI vorgeschlagener Titel
    ai_message = None # Nachrichten von/über die KI
    omdb_data_for_template = None
    omdb_details_for_template = None
    rating5_for_template = None
    show_details_form = False # Steuert, ob das finale Formular zum Hinzufügen angezeigt wird
    title_for_omdb_search_value = request.args.get('title_for_omdb_search', '').strip()
    movie_to_add_id_value = request.args.get('movie_to_add_id', type=int) # Neuer Parameter

    if request.method == 'GET':
        # Phase 2b: Film-ID wurde direkt übergeben (z.B. von KI-Empfehlungen)
        if movie_to_add_id_value:
            current_app.logger.info(f"User {user_id} will add existing movie_id: {movie_to_add_id_value}")
            movie_from_db = Movie.query.get(movie_to_add_id_value)
            if movie_from_db:
                # Stelle die Daten so bereit, wie sie vom OMDb-Abruf kommen würden
                omdb_data_for_template = { # teilweises Mockup der OMDb-Antwort
                    'Response': 'True',
                    'Title': movie_from_db.title,
                    'Year': str(movie_from_db.year) if movie_from_db.year else 'N/A',
                    'Poster': movie_from_db.poster_url,
                    'Director': movie_from_db.director,
                    'imdbRating': str(movie_from_db.community_rating * 2) if movie_from_db.community_rating is not None else 'N/A' # Annahme: community_rating ist 0-5
                    # Weitere Felder könnten hier aus movie_from_db befüllt werden, falls nötig
                }
                omdb_details_for_template = { # Details aus dem Movie-Objekt
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
                    rating5_for_template = movie_from_db.community_rating # Direkt verwenden oder leer lassen
                else: # Kein Community Rating, vielleicht das User Rating als Vorschlag, falls schon vorhanden?
                    user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_from_db.id).first()
                    if user_movie_link and user_movie_link.user_rating is not None:
                        rating5_for_template = user_movie_link.user_rating
                    # Ansonsten bleibt rating5_for_template None, Nutzer muss selbst bewerten

                show_details_form = True
                # user_search_input_value könnte hier auf den Filmtitel gesetzt werden, um Konsistenz zu wahren
                user_search_input_value = movie_from_db.title 
            else:
                flash(f'Movie with ID {movie_to_add_id_value} not found in database.', 'danger')
                return redirect(url_for('list_user_movies', user_id=user_id)) # Oder eine andere Fehlerseite

        # Phase 2a: Nutzer hat auf 'Load Movie Details' geklickt, mit dem von der KI vorgeschlagenen Titel (höhere Priorität)
        elif 'title_for_omdb_search' in request.args and title_for_omdb_search_value:
            current_app.logger.info(f"User {user_id} initiated OMDb search with AI-suggested title: '{title_for_omdb_search_value}'")
            # Die user_search_input_value muss hier ggf. aus den args neu geladen werden, falls sie für das Template Rendering benötigt wird
            # da sie im vorherigen Schritt vielleicht nicht gesetzt wurde, wenn man direkt zu Phase 2 springt (unwahrscheinlich aber sicher ist sicher)
            user_search_input_value = request.args.get('user_search_input', user_search_input_value) # Behalte alten Wert oder nimm neuen

            params = {'apikey': OMDB_API_KEY, 't': title_for_omdb_search_value}
            try:
                resp = requests.get('http://www.omdbapi.com/', params=params, timeout=10)
                resp.raise_for_status()
                omdb_data_for_template = resp.json()
            except requests.exceptions.RequestException as e:
                current_app.logger.error(f"OMDb API request failed for title '{title_for_omdb_search_value}': {e}")
                omdb_data_for_template = {'Response': 'False', 'Error': str(e)}
                # Diese Flash-Nachricht ist hier besser, da sie den Kontext des OMDb-Abrufs hat
                flash(f"Error connecting to OMDb for title '{title_for_omdb_search_value}': {str(e)[:100]}", "error")

            if omdb_data_for_template and omdb_data_for_template.get('Response') == 'True':
                show_details_form = True # Formular zum Hinzufügen anzeigen
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
                        pass # rating5_for_template bleibt None
                # Wichtig: Den Titel, der für die OMDb-Suche verwendet wurde (AI-Vorschlag), 
                # auch an das Template weitergeben, um ihn im Hinzufügen-Formular korrekt zu verwenden.
                # `omdb_data_for_template.Title` sollte dem entsprechen.
            else:
                # OMDb hat den von der KI interpretierten Titel nicht gefunden
                # Die Flash-Nachricht oben ist bereits ausreichend.
                # Zusätzlich eine ai_message für direkte Anzeige im Template setzen.
                error_msg_from_omdb = omdb_data_for_template.get('Error', 'Unknown OMDb error') if omdb_data_for_template else 'No response from OMDb.'
                ai_message = f"OMDb could not find details for the title: '{title_for_omdb_search_value}'. Error: {error_msg_from_omdb}"
                current_app.logger.warning(f"OMDb search failed for title '{title_for_omdb_search_value}': {error_msg_from_omdb}")
                show_details_form = False
        
        # Phase 1: Nutzer hat eine Suche eingegeben, um KI-Vorschlag zu erhalten (nur wenn nicht Phase 2)
        elif 'user_search_input' in request.args and user_search_input_value:
            current_app.logger.info(f"User {user_id} initiated AI movie search with input: '{user_search_input_value}'")
            ki_result = get_ai_interpreted_movie_title(user_search_input_value)

            if ki_result == NO_CLEAR_MOVIE_TITLE_MARKER or ki_result is None:
                ai_message = "AI could not identify a clear movie title. Please try a different title or description."
                current_app.logger.info(f"AI could not find title for user input: '{user_search_input_value}'")
            else:
                ai_suggested_title = ki_result
                current_app.logger.info(f"AI suggested title '{ai_suggested_title}' for input '{user_search_input_value}'")
                # OMDb-Abruf erfolgt erst im nächsten Schritt

        # Rendere das Template mit den aktuellen Daten, egal in welcher Phase
        return render_template(
            'add_movie.html',
            user=user,
            current_year=datetime.now().year, # Wird evtl. nicht mehr gebraucht, aber schadet nicht
            user_search_input_value=user_search_input_value, # Die ursprüngliche Eingabe des Users
            ai_suggested_title=ai_suggested_title, # Der Vorschlag der KI
            ai_message=ai_message, # Nachrichten von der KI oder über den Prozess
            omdb=omdb_data_for_template, # OMDb Rohdaten (nach Phase 2)
            omdb_details=omdb_details_for_template, # Aufbereitete OMDb Details (nach Phase 2)
            rating5=rating5_for_template, # OMDb Rating auf 5er Skala (nach Phase 2)
            show_details_form=show_details_form, # Ob das finale Hinzufüge-Formular gezeigt wird
            # Hilfsvariable, um zu wissen, welcher Titel für OMDb verwendet wurde, falls es Abweichungen gibt
            # oder für das erneute Rendern des Formulars nach einem POST-Fehler.
            # title_actually_used_for_omdb = title_for_omdb_search_value if 'title_for_omdb_search' in request.args else None
        )

    elif request.method == 'POST':
        # Die POST-Logik verarbeitet das finale Formular, das angezeigt wird, wenn show_details_form True ist.
        # Die Daten hier sollten aus dem Formular stammen, das mit OMDb-Daten (basierend auf dem KI-Titel) gefüllt wurde.
        
        title_from_omdb_form = request.form.get('title_from_omdb', '').strip() # Titel aus dem OMDb-bestätigten Formular
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
        # Die ursprüngliche Nutzereingabe, um ggf. dorthin zurückzukehren oder für Logging
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
                    # Umleitung zum Start des Prozesses, da das erneute Füllen des komplexen Formulars schwierig ist
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
            return redirect(url_for('list_user_movies', user_id=user_id))
        else:
            flash(f"Could not add movie '{title_from_omdb_form}'. It might already be in your list or an error occurred.", 'danger')
            return redirect(url_for('add_movie', user_id=user_id, user_search_input=original_user_search_input_for_post))

    # Fallback für unerwartete Methoden oder Zustände (sollte nicht passieren)
    return redirect(url_for('add_movie', user_id=user_id)) 

@app.route('/users/<int:user_id>/update_movie_rating/<int:movie_id>', methods=['GET', 'POST'])
def update_movie_rating(user_id, movie_id):
    """
    Film-Rating bearbeiten-Route (User-spezifisch)
    Zeigt die Filmdetails an und erlaubt die Aktualisierung des persönlichen Ratings für einen Film in der User-Liste.
    """
    # Sicherstellen, dass der bearbeitende User der eingeloggte User ist
    if not g.user or g.user.id != user_id:
        flash('You can only edit ratings for your own movie list.', 'danger')
        return redirect(url_for('home'))

    movie = Movie.query.get_or_404(movie_id)
    user_movie_link = UserMovie.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()

    if not user_movie_link:
        flash(f'Movie "{movie.title}" is not in your list. You can add it first.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie.id)) # Zur Detailseite, um es ggf. hinzuzufügen

    if request.method == 'POST':
        rating_str = request.form.get('rating', '').strip()
        new_user_rating = None

        if not rating_str: # Erlaube leere Eingabe, um Rating zu entfernen
            pass # new_user_rating bleibt None
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
            # Bleibe auf der Seite mit den aktuellen Daten
            return render_template('update_movie_rating.html', user=g.user, movie=movie, current_user_rating=user_movie_link.user_rating)
    
    # GET Request: Zeige das Formular mit dem aktuellen User-Rating
    return render_template(
        'update_movie_rating.html',
        user=g.user, 
        movie=movie, 
        current_user_rating=user_movie_link.user_rating
    )

@app.route('/users/<int:user_id>/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(user_id, movie_id):
    """
    Film löschen-Route
    Löscht einen Film aus der Favoritenliste und leitet zurück zur Filmliste.
    Delete movie route: deletes a movie from favorites and redirects to the list.
    """
    try:
        # success = data_manager.delete_movie(movie_id) # Ursprüngliche Logik
        # Angepasste Logik: Film nur aus der Benutzerliste entfernen und User-ID übergeben
        success = data_manager.delete_movie_from_user_list(user_id=user_id, movie_id=movie_id)
    except Exception as e:
        current_app.logger.error(f"Error in delete_movie for user {user_id}, movie {movie_id}: {e}") # User-ID zum Logging hinzugefügt
        flash('Fehler beim Löschen des Films. / Error deleting movie.')
        return redirect(url_for('list_user_movies', user_id=user_id)) # Zurück zur Filmliste des Benutzers
    if success:
        flash('Film aus Ihrer Liste gelöscht. / Movie deleted from your list.') # Nachricht angepasst
    else:
        flash('Film konnte nicht aus Ihrer Liste gelöscht werden. / Could not delete movie from your list.') # Nachricht angepasst
    return redirect(url_for('list_user_movies', user_id=user_id)) # Zurück zur Filmliste des Benutzers

@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    """Film-Details mit Kommentaren und ähnlichen Filmen"""
    movie = Movie.query.get_or_404(movie_id)
    comments = Comment.query.filter_by(movie_id=movie_id).order_by(Comment.created_at.desc()).all()
    
    # Ähnliche Filme von Deep Seek API - ENTFERNT
    # similar_movies = get_similar_movies(movie.title)
    
    return jsonify({
        'movie': {
            'id': movie.id,
            'title': movie.title,
            'director': movie.director,
            'year': movie.year,
            'rating': movie.rating, # Beachten Sie, dass dies das veraltete 'rating'-Feld ist, nicht 'community_rating'
            'poster_url': movie.poster_url
        },
        'comments': [{
            'id': c.id,
            'text': c.text,
            'user': c.user.name,
            'created_at': c.created_at.isoformat()
        } for c in comments] # Komma hier entfernt, da 'similar_movies' entfernt wurde
        # 'similar_movies': similar_movies # ENTFERNT
    })

@app.route('/movie/<int:movie_id>/comment', methods=['POST'])
def add_movie_comment(movie_id):
    """Kommentar zu einem Film hinzufügen"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Nicht eingeloggt'})
    
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Kommentar darf nicht leer sein'})
    
    comment = Comment(
        movie_id=movie_id,
        user_id=session['user_id'],
        text=text
    )
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({'success': True})

# def get_similar_movies(title): # KOMPLETTE FUNKTION ENTFERNT
#     """Ähnliche Filme von Deep Seek API abrufen"""
#     try:
#         response = requests.get(
#             'https://api.deepseek.com/v1/similar',
#             params={'title': title},
#             headers={'Authorization': f'Bearer {DEEP_SEEK_API_KEY}'}
#         )
#         if response.ok:
#             similar_titles = response.json().get('similar_titles', [])
#             similar_movies = []
#             
#             for title in similar_titles[:5]:  # Nur die ersten 5 ähnlichen Filme
#                 # OMDb API für Details
#                 omdb_response = requests.get(
#                     'http://www.omdbapi.com/',
#                     params={'apikey': OMDB_API_KEY, 't': title}
#                 )
#                 if omdb_response.ok:
#                     movie_data = omdb_response.json()
#                     if movie_data.get('Response') == 'True':
#                         similar_movies.append({
#                             'title': movie_data['Title'],
#                             'year': movie_data.get('Year'),
#                             'poster': movie_data.get('Poster'),
#                             'imdb_id': movie_data.get('imdbID')
#                         })
#             
#             return similar_movies
#     except Exception as e:
#         current_app.logger.error(f"Error fetching similar movies: {e}")
#     
#     return []

@app.route('/api/docs')
def api_docs():
    """API-Dokumentation"""
    return render_template('api_docs.html')

@app.route('/about')
def about():
    """
    Über uns-Seite
    Zeigt Informationen über die MovieWeb App.
    About page: displays information about the MovieWeb application.
    """
    return render_template('about.html')

# Fehler-Handler
@app.errorhandler(404)
def page_not_found(e):
    """
    404-Fehlerseite
    Rendern der 404-Seite.
    404 error page: render 404.html template.
    """
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """
    500-Fehlerseite
    Rendern der 500-Seite.
    500 error page: render 500.html template.
    """
    return render_template('500.html'), 500

# Route für die dedizierte Filmdetailseite
# Route for the dedicated movie detail page
@app.route('/movie/<int:movie_id>/page')
def movie_page(movie_id):
    """
    Rendert die dedizierte Detailseite für einen Film.
    Renders the dedicated detail page for a movie.

    Args:
        movie_id (int): Die ID des Films.
                        The ID of the movie.

    Returns:
        HTML: Die gerenderte Detailseite des Films oder 404/500 bei Fehlern.
              The rendered movie detail page or 404/500 on error.
    """
    try:
        movie = Movie.query.get_or_404(movie_id)
        current_user_specific_rating = None # Rating des eingeloggten Users für DIESEN Film
        is_movie_in_user_list = False

        if g.user: # Prüfen, ob überhaupt ein User eingeloggt ist
            user_movie_link = UserMovie.query.filter_by(user_id=g.user.id, movie_id=movie.id).first()
            if user_movie_link:
                is_movie_in_user_list = True
                current_user_specific_rating = user_movie_link.user_rating

        # Das 'user'-Objekt hier ist g.user, das den eingeloggten Benutzer repräsentiert (oder None)
        return render_template(
            'movie_detail_page.html', 
            movie=movie,  # Enthält movie.community_rating und movie.community_rating_count
            user=g.user,  # Der eingeloggte Benutzer (für Kommentare, etc.)
            is_movie_in_user_list=is_movie_in_user_list,
            current_user_rating_for_movie=current_user_specific_rating
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering movie page for movie_id {movie_id}: {e}")
        # Bei SQLAlchemy 404 (get_or_404) wird Werkzeug HTTP 404 ausgelöst, das vom @app.errorhandler(404) behandelt wird.
        # Andere Exceptions führen zur 500er Seite.
        # Hier könnten wir spezifischere Fehlerbehandlung oder Flash-Nachrichten hinzufügen, falls gewünscht.
        return render_template('500.html'), 500 # Generische Fehlerseite

# Route zum Hinzufügen eines Kommentars von der Filmdetailseite
# Route for adding a comment from the movie detail page
@app.route('/movie/<int:movie_id>/comment/page', methods=['POST'])
def add_movie_comment_page(movie_id):
    """
    Verarbeitet das Hinzufügen eines Kommentars von der Filmdetailseite.
    Handles adding a comment from the movie detail page.
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
        current_app.logger.error(f"Error adding comment from page: {e}")
        flash(f'Error adding comment: {e}', 'error')
    
    return redirect(url_for('movie_page', movie_id=movie_id))

@app.route('/user/add_movie_to_list/<int:movie_id>', methods=['POST'])
def add_movie_to_list(movie_id):
    if not g.user:
        flash('You must be logged in to add movies to your list.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id)) # Zurück zur Detailseite

    success = data_manager.add_existing_movie_to_user_list(user_id=g.user.id, movie_id=movie_id)

    if success:
        movie_title = Movie.query.get(movie_id).title # Für die Flash-Nachricht
        flash(f"'{movie_title}' has been added to your list.", 'success')
    else:
        flash('Could not add movie to your list. It might already be there or an error occurred.', 'danger')
    
    return redirect(url_for('movie_page', movie_id=movie_id)) # Zurück zur Detailseite

@app.route('/user/list/remove/<int:movie_id>', methods=['POST'], endpoint='remove_movie_from_list_explicit')
def remove_movie_from_list(movie_id):
    """
    Entfernt einen Film aus der Liste des eingeloggten Benutzers.
    """
    if not g.user:
        flash('You must be logged in to remove movies from your list.', 'warning')
        return redirect(url_for('movie_page', movie_id=movie_id))

    #movie = Movie.query.get(movie_id) 
    success = data_manager.delete_movie_from_user_list(user_id=g.user.id, movie_id=movie_id)

    if success:
        flash(f"Movie (ID: {movie_id}) has been removed from your list.", 'success') 
    else:
        flash(f"Could not remove movie (ID: {movie_id}) from your list. It might not have been in your list or an error occurred.", 'danger')
    
    return redirect(url_for('movie_page', movie_id=movie_id))

@app.route('/movie/<int:movie_id>/ai_recommendations')
def get_ai_movie_recommendations_route(movie_id):
    movie = Movie.query.get(movie_id)
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'}), 404

    user_history_before_this_call = session.get(AI_RECOMMENDATION_HISTORY_SESSION_KEY, [])
    exclusion_text = ""
    if user_history_before_this_call:
        movies_to_exclude_str = ', '.join(user_history_before_this_call)
        exclusion_text = EXCLUSION_CLAUSE_TEMPLATE.format(movies_to_exclude=movies_to_exclude_str)

    prompt = MOVIE_RECOMMENDATION_PROMPT_TEMPLATE.format(movie_title=movie.title, exclusion_clause=exclusion_text)
    current_app.logger.debug(f"Constructed AI Prompt for user {session.get('user_id', 'N/A')} (Movie: {movie.title}):\n{prompt}") # Debug Print des Prompts
    
    try:
        temperature_str = request.args.get('temp', str(DEFAULT_AI_TEMPERATURE_RECOMMEND))
        temperature = float(temperature_str)
        if not (0.0 <= temperature <= 2.0):
            temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND
            current_app.logger.warning(f"Ungültiger Temperaturwert '{temperature_str}' empfangen, Fallback auf {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")
    except ValueError:
        temperature = DEFAULT_AI_TEMPERATURE_RECOMMEND
        current_app.logger.warning(f"Konnte Temperaturwert '{request.args.get('temp')}' nicht in float umwandeln, Fallback auf {DEFAULT_AI_TEMPERATURE_RECOMMEND}.")

    try:
        # KI liefert jetzt genau 5 (oder weniger, wenn sie nicht mehr findet) bereinigte Titel
        current_ai_suggestions = ask_openrouter_for_movies(prompt_content=prompt, temperature=temperature, expected_responses=5)
        current_app.logger.info(f"KI (temp={temperature}) empfahl für '{movie.title}' (Ausschluss: {len(user_history_before_this_call)} Titel für User {session.get('user_id','N/A')}): {current_ai_suggestions}")

        is_error_response = False
        if current_ai_suggestions and len(current_ai_suggestions) == 1:
            title_lower = current_ai_suggestions[0].lower()
            if "error" in title_lower or "not configured" in title_lower or "did not return" in title_lower or "failed to connect" in title_lower or "timed out" in title_lower:
                is_error_response = True

        if is_error_response:
            # Wenn die KI eine Fehlermeldung zurückgibt, diese direkt anzeigen
            return jsonify({'success': False, 'recommendations': current_ai_suggestions, 'message': current_ai_suggestions[0]})

        # Die dem Benutzer angezeigten Filme sind die aktuellen Vorschläge der KI
        recommendations_to_display = current_ai_suggestions
        current_app.logger.info(f"Dem User (ID: {session.get('user_id','N/A')}) werden {len(recommendations_to_display)} Titel gezeigt: {recommendations_to_display}")

        # Historie aktualisieren: Nur Titel hinzufügen, die vorher noch nicht in der User-History waren.
        if recommendations_to_display: # Nur wenn auch was gezeigt wurde
            updated_user_history = list(user_history_before_this_call) # Start mit der alten Historie
            newly_added_this_round_count = 0
            for title_shown in recommendations_to_display:
                if title_shown not in updated_user_history: 
                    updated_user_history.append(title_shown)
                    newly_added_this_round_count += 1
            
            if newly_added_this_round_count > 0: # Nur wenn tatsächlich neue Titel zur Historie kamen
                while len(updated_user_history) > AI_RECOMMENDATION_HISTORY_LENGTH:
                    updated_user_history.pop(0)
                session[AI_RECOMMENDATION_HISTORY_SESSION_KEY] = updated_user_history
                current_app.logger.info(f"{newly_added_this_round_count} neue Titel zur KI-Empfehlungshistorie für User (ID: {session.get('user_id', 'N/A')}) hinzugefügt. Neue Länge: {len(updated_user_history)}. Inhalt: {updated_user_history}")
            else:
                current_app.logger.info(f"Keine *neuen* Titel zur KI-Historie für User (ID: {session.get('user_id', 'N/A')}) hinzugefügt, da alle angezeigten Titel bereits bekannt waren.")

        return jsonify({'success': True, 'recommendations': recommendations_to_display})
    
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"OpenRouter API RequestException in Route: {e}")
        if e.response is not None and e.response.status_code in [401, 403] or ("OPENROUTER_API_KEY" in str(e)):
            msg = "OpenRouter API key is missing, invalid, or quota exceeded. Please check server configuration."
        else:
            msg = f"Failed to get AI recommendations due to a network or API issue: {str(e)}"
        return jsonify({'success': False, 'message': msg}), 500
    except Exception as e:
        current_app.logger.error(f"Error getting AI recommendations in Route: {e}")
        return jsonify({'success': False, 'message': f"Failed to get AI recommendations: {str(e)}"}), 500

def ask_openrouter_for_movies(prompt_content: str, temperature: float, expected_responses: int = 5) -> list[str]:
    """
    Stellt eine Anfrage an die OpenRouter API, um Filmtitel zu erhalten.
    expected_responses: Definiert, ob primär ein einzelner Titel (für Interpretation)
                      oder eine Liste von Titeln (für Empfehlungen) erwartet wird.
                      Dies beeinflusst nicht direkt die API-Anfrage, aber die Handhabung der Antwort.
    """
    if not OPENROUTER_API_KEY:
        current_app.logger.error("OpenRouter API Key ist nicht konfiguriert.")
        return ["OpenRouter API Key not configured on server."]

    current_app.logger.debug(f"Sending prompt to AI (temp={temperature}, expecting ~{expected_responses} responses):\n{prompt_content[:500]}...") # Gekürzter Prompt für Lesbarkeit

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
                "max_tokens": 150 if expected_responses > 1 else 50 # Mehr Tokens für Listen, weniger für Einzeltitel
            }),
            timeout=20 
        )
        response.raise_for_status()
        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if content:
            # Wenn wir nur eine einzelne Antwort erwarten (Titelinterpretation), nicht nach Zeilenumbrüchen splitten,
            # es sei denn, die KI gibt die spezielle Fehlermarkierung zurück.
            if expected_responses == 1 and content != "NO_CLEAR_MOVIE_TITLE_FOUND":
                # Direkte Bereinigung des einzelnen Titels
                cleaned_title = content.strip()
                
                # Gängige Präfixe entfernen (Groß-/Kleinschreibung ignorieren)
                prefixes_to_remove = [
                    r"the most probable movie title is:?",
                    r"it is likely:?",
                    r"the movie title is:?",
                    r"title:?",
                    r"movie:?",
                    r"^\s*-\s*", # Bindestrich am Anfang (oft bei Listen)
                    r"^\s*\d+[.,\)]\s*" # Nummerierungen wie 1. oder 1)
                ]
                for prefix_pattern in prefixes_to_remove:
                    cleaned_title = re.sub(f"^{prefix_pattern}", "", cleaned_title, flags=re.IGNORECASE).strip()
                
                # Umschließende Anführungszeichen entfernen
                if (cleaned_title.startswith('"') and cleaned_title.endswith('"')) or \
                   (cleaned_title.startswith("'") and cleaned_title.endswith("'")):
                    cleaned_title = cleaned_title[1:-1].strip()
                
                current_app.logger.debug(f"Raw AI single response: '{content}', Processed: '{cleaned_title}'")
                return [cleaned_title] if cleaned_title else [] # Zurück als Liste mit einem Element oder leer
            elif content == "NO_CLEAR_MOVIE_TITLE_FOUND":
                 return ["NO_CLEAR_MOVIE_TITLE_FOUND"]
            else: # Mehrere Antworten erwartet (Empfehlungen)
                movie_titles_from_ai = [title.strip() for title in content.split('\n') if title.strip()]
                processed_titles = []
                prefix_pattern = re.compile(r"^\s*(\d+[,.)]?\s*|[-*•]+\s*)")
                for title_str in movie_titles_from_ai:
                    cleaned_title = prefix_pattern.sub("", title_str).strip()
                    if cleaned_title.startswith('"') and cleaned_title.endswith('"'):
                         cleaned_title = cleaned_title[1:-1]
                    if cleaned_title.startswith("'") and cleaned_title.endswith("'"):
                         cleaned_title = cleaned_title[1:-1]
                    if cleaned_title:
                        processed_titles.append(cleaned_title)
                current_app.logger.debug(f"Raw AI list response: {movie_titles_from_ai}, Processed: {processed_titles}")
                return processed_titles
        else:
            current_app.logger.warning("Kein Inhalt von OpenRouter API erhalten.")
            # Spezifische Behandlung für Titelinterpretation vs. Empfehlungen
            return ["AI did not return any suggestions."] if expected_responses > 1 else [NO_CLEAR_MOVIE_TITLE_MARKER] 

    except requests.exceptions.Timeout:
        current_app.logger.error(f"OpenRouter API request timed out.")
        return ["AI service request timed out. Please try again later."] 
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"OpenRouter API RequestException: {e}. Response: {e.response.text if e.response else 'No response'}")
        error_message = f"Error connecting to AI service: {str(e)}"
        if e.response is not None:
            try:
                error_detail = e.response.json()
                error_message = f"AI API Error: {error_detail.get('error', {}).get('message', str(e))}"
            except ValueError:
                error_message = f"AI API Error (non-JSON response): {e.response.status_code} - {e.response.text[:100]}"
        return [error_message] 
    except Exception as e:
        current_app.logger.error(f"Generischer Fehler in ask_openrouter_for_movies: {e}")
        return [f"An unexpected error occurred with the AI service: {str(e)}"]

if __name__ == '__main__':
    # Anwendung starten
    app.run(debug=True)