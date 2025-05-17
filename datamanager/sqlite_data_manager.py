"""
sqlite_data_manager.py
Dieses Modul implementiert die DataManagerInterface mit SQLite/SQLAlchemy.
This module implements the DataManagerInterface using SQLite/SQLAlchemy.
"""

from typing import List, Optional
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc
from datamanager.data_manager_interface import DataManagerInterface
from models import db, User, Movie, UserMovie, Comment
from datetime import datetime  # For year validation

class SQLiteDataManager(DataManagerInterface):
    """
    SQLiteDataManager
    Konkrete Umsetzung des DataManagerInterface für SQLite über SQLAlchemy.
    Concrete implementation of DataManagerInterface for SQLite using SQLAlchemy.
    """

    def get_all_users(self) -> List[User]:
        """
        Returns all users.
        Liefert alle Benutzer.
        """
        try:
            return User.query.all()
        except SQLAlchemyError as e:
            # Log error when fetching all users fails.
            # Logge Fehler, wenn das Abrufen aller Benutzer fehlschlägt.
            current_app.logger.error(f"Error fetching users: {e} / Fehler beim Abrufen der Benutzer: {e}")
            return []

    def get_user_movies(self, user_id: int) -> List[Movie]:
        """
        Returns all movies for a given user.
        Liefert alle Filme eines Benutzers.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return []
            # Fetch movies via UserMovie relationship
            # Filme über UserMovie-Beziehung abrufen
            return [um.movie for um in user.movies]
        except SQLAlchemyError as e:
            # Log error when fetching movies for a specific user fails.
            # Logge Fehler, wenn das Abrufen der Filme für einen bestimmten Benutzer fehlschlägt.
            current_app.logger.error(f"Error fetching movies for user {user_id}: {e} / Fehler beim Abrufen der Filme für Benutzer {user_id}: {e}")
            return []

    def add_user(self, name: str) -> Optional[User]:
        """
        Adds a new user.
        Fügt einen neuen Benutzer hinzu.
        """
        # Defensive input: strip whitespace and normalize to lowercase
        # Defensive Eingabe: Leerzeichen entfernen und in Kleinbuchstaben normalisieren
        name = name.strip().lower()
        if not name:
            # Log warning if attempting to add a user with an empty name.
            # Logge Warnung bei Versuch, Benutzer mit leerem Namen hinzuzufügen.
            current_app.logger.warning("Attempted to add user with empty name. / Versuch, Benutzer mit leerem Namen hinzuzufügen.")
            return None
        # Duplicate check (case-insensitive)
        # Prüfung auf Duplikate (Groß-/Kleinschreibung ignorieren)
        from sqlalchemy import func
        if User.query.filter(func.lower(User.name) == name).first():
            # Log warning if attempting to add a duplicate user.
            # Logge Warnung bei Versuch, doppelten Benutzer hinzuzufügen.
            current_app.logger.warning(f"Attempted to add duplicate user '{name}'. / Versuch, doppelten Benutzer '{name}' hinzuzufügen.")
            return None
        try:
            user = User(name=name.strip()) # .strip() is actually redundant here due to above .strip().lower() / .strip() ist hier eigentlich redundant wegen obigem .strip().lower()
            db.session.add(user)
            db.session.commit()
            return user
        except SQLAlchemyError as e:
            db.session.rollback()
            # Log error when adding a new user fails.
            # Logge Fehler, wenn das Hinzufügen eines neuen Benutzers fehlschlägt.
            current_app.logger.error(f"Error adding user '{name}': {e} / Fehler beim Hinzufügen von Benutzer '{name}': {e}")
            return None

    def add_movie(self, user_id: int, title: str, director: str, year: int, rating: float, poster_url: str = None,
                  plot: str = None, runtime: str = None, awards: str = None, languages: str = None,
                  genre: str = None, actors: str = None, writer: str = None, country: str = None,
                  metascore: str = None, rated: str = None, imdb_id: str = None,
                  omdb_rating_for_community: Optional[float] = None) -> Optional[Movie]:
        """
        Fügt einen neuen Film für einen Benutzer hinzu. 
        Prüft, ob der Film (via imdb_id) bereits global existiert. Wenn ja, wird er verlinkt.
        Wenn nein, wird er global erstellt und dann verlinkt.
        Das Rating des Benutzers wird in der UserMovie-Verknüpfung gespeichert.
        Das Community-Rating des Films wird aktualisiert.

        Adds a new movie for a user. 
        Checks if the movie (via imdb_id) already exists globally. If so, it's linked.
        If not, it's created globally and then linked.
        The user's rating is stored in the UserMovie link.
        The movie's community rating is updated.
        """
        # Defensive input stripping
        # Eingabe-Strings bereinigen
        title = title.strip()
        director = director.strip() if director else None

        # Validate year (if provided) not in the future
        # Jahr validieren (falls angegeben), darf nicht in der Zukunft liegen
        current_year = datetime.now().year
        if year is not None and year > current_year:
            # Log warning for future year.
            # Logge Warnung für Zukunftsjahr.
            current_app.logger.warning(f"Attempted to add movie with future year: {year}. / Versuch, Film mit Zukunftsjahr hinzuzufügen: {year}.")
            return None

        # Validate rating (if provided) between 0 and 5
        # Bewertung validieren (falls angegeben), muss zwischen 0 und 5 liegen
        if rating is not None and not (0 <= rating <= 5):
            # Log warning for invalid rating.
            # Logge Warnung für ungültige Bewertung.
            current_app.logger.warning(f"Attempted to add movie with invalid rating: {rating}. / Versuch, Film mit ungültiger Bewertung hinzuzufügen: {rating}.")
            return None

        if not title:
            # Log warning for empty title.
            # Logge Warnung für leeren Titel.
            current_app.logger.warning("Attempted to add movie with empty title. / Versuch, Film mit leerem Titel hinzuzufügen.")
            return None
        try:
            user = User.query.get(user_id)
            if not user:
                # Log warning if user not found.
                # Logge Warnung, wenn Benutzer nicht gefunden wurde.
                current_app.logger.warning(f"User {user_id} not found. / Benutzer {user_id} nicht gefunden.")
                return None

            # Check if a movie with this imdb_id already exists
            # Prüfen, ob ein Film mit dieser imdb_id bereits existiert
            movie = None
            if imdb_id:
                movie = Movie.query.filter_by(imdb_id=imdb_id).first()

            if movie: # Movie already exists globally / Film existiert bereits global
                # Log info: Movie exists, linking to user.
                # Info-Log: Film existiert, wird mit Benutzer verknüpft.
                current_app.logger.info(f"Movie with imdb_id {imdb_id} already exists. Linking to user {user_id}. / Film mit imdb_id {imdb_id} existiert bereits. Wird mit Benutzer {user_id} verknüpft.")
                # Optional: Update existing movie data here if desired.
                # Community rating will be recalculated later by _update_community_rating.
                # Optional: Hier könnten existierende Filmdaten aktualisiert werden, falls gewünscht.
                # Das Community-Rating wird später durch _update_community_rating neu berechnet.
            else: # Movie does not exist globally, create new entry / Film existiert global noch nicht, neu erstellen
                # Log info: Movie not found, creating new entry.
                # Info-Log: Film nicht gefunden, neuer Eintrag wird erstellt.
                current_app.logger.info(f"Movie with imdb_id {imdb_id} not found. Creating new entry. / Film mit imdb_id {imdb_id} nicht gefunden. Neuer Eintrag wird erstellt.")
                
                db_initial_omdb_rating = None
                if omdb_rating_for_community is not None and 0 <= omdb_rating_for_community <= 5:
                    db_initial_omdb_rating = omdb_rating_for_community
                    current_app.logger.info(f"Using OMDb rating {omdb_rating_for_community} as initial_omdb_rating for movie {imdb_id}.")

                movie = Movie(
                    title=title,
                    director=director,
                    year=year,
                    # community_rating und community_rating_count werden durch _update_community_rating gesetzt
                    poster_url=poster_url,
                    plot=plot,
                    runtime=runtime,
                    awards=awards,
                    language=languages, 
                    genre=genre,
                    actors=actors,
                    writer=writer,
                    country=country,
                    metascore=metascore,
                    rated_omdb=rated, 
                    imdb_id=imdb_id,
                    initial_omdb_rating=db_initial_omdb_rating # HIER setzen
                )
                db.session.add(movie)
                db.session.flush() # Make movie.id available
                # Kein expliziter Commit hier, da _update_community_rating am Ende committet

            # Check if the UserMovie link already exists
            # Prüfen, ob die UserMovie-Verknüpfung bereits existiert
            user_movie_link = UserMovie.query.filter_by(user_id=user.id, movie_id=movie.id).first()
            if not user_movie_link:
                um = UserMovie(user_id=user.id, movie_id=movie.id, user_rating=rating) # Set user_rating here / user_rating hier setzen
                db.session.add(um)
                # Log info: New UserMovie link created.
                # Info-Log: Neue UserMovie-Verknüpfung erstellt.
                current_app.logger.info(f"New UserMovie link for user {user.id}, movie {movie.id} with user_rating {rating}. / Neue UserMovie-Verknüpfung für Benutzer {user.id}, Film {movie.id} mit Benutzerbewertung {rating}.")
            else:
                # Log info: Movie already linked to user.
                # Info-Log: Film ist bereits mit Benutzer verknüpft.
                current_app.logger.info(f"Movie {movie.id} already linked to user {user.id}. / Film {movie.id} ist bereits mit Benutzer {user.id} verknüpft.")
                # If already linked, set/update the passed rating as user_rating for this link
                # Wenn bereits verlinkt, die übergebene Bewertung als user_rating für diese Verknüpfung setzen/aktualisieren
                if rating is not None and user_movie_link.user_rating != rating:
                    user_movie_link.user_rating = rating
                    # Log info: Updating user_rating for existing link.
                    # Info-Log: Benutzerbewertung für existierende Verknüpfung wird aktualisiert.
                    current_app.logger.info(f"Updating user_rating for existing link user {user.id}, movie {movie.id} to {rating}. / Benutzerbewertung für existierende Verknüpfung Benutzer {user.id}, Film {movie.id} auf {rating} aktualisiert.")
                elif rating is None and user_movie_link.user_rating is not None: # Case: User explicitly wants to remove rating / Fall: Benutzer möchte Bewertung explizit entfernen
                    user_movie_link.user_rating = None
                    # Log info: Removing user_rating for existing link.
                    # Info-Log: Benutzerbewertung für existierende Verknüpfung wird entfernt.
                    current_app.logger.info(f"Removing user_rating for existing link user {user.id}, movie {movie.id}. / Benutzerbewertung für existierende Verknüpfung Benutzer {user.id}, Film {movie.id} entfernt.")

            self._update_community_rating(movie.id) # Update community rating based on all UserMovie entries / Community-Rating basierend auf allen UserMovie-Einträgen aktualisieren
            return movie
        except SQLAlchemyError as e:
            db.session.rollback()
            # Log error: Failed to add movie for user.
            # Fehler-Log: Film konnte für Benutzer nicht hinzugefügt werden.
            current_app.logger.error(f"Error adding movie '{title}' for user {user_id}: {e} / Fehler beim Hinzufügen des Films '{title}' für Benutzer {user_id}: {e}")
            return None

    def update_user_rating_for_movie(self, user_id: int, movie_id: int, new_rating: Optional[float]) -> bool:
        """
        Aktualisiert das individuelle Rating eines Benutzers für einen Film.
        Berechnet danach das Community-Rating des Films neu.
        new_rating kann None sein, um ein existierendes Rating zu entfernen.

        Updates an individual user's rating for a movie.
        Recalculates the movie's community rating afterwards.
        new_rating can be None to remove an existing rating.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                # Log warning: No link found to update rating.
                # Warnungs-Log: Keine Verknüpfung zum Aktualisieren der Bewertung gefunden.
                current_app.logger.warning(f"No link found for user {user_id} and movie {movie_id} to update rating. / Keine Verknüpfung für Benutzer {user_id} und Film {movie_id} zum Aktualisieren der Bewertung gefunden.")
                # Optional: If the movie exists globally but the user doesn't have it in their list yet,
                # one could create the link here and set the rating.
                # Vorerst: Nur Fehler, wenn keine Verknüpfung vorhanden ist.
                return False
            
            if new_rating is not None and not (0 <= new_rating <= 5):
                # Log warning: Attempted to update with invalid rating.
                # Warnungs-Log: Versuch, mit ungültiger Bewertung zu aktualisieren.
                current_app.logger.warning(f"Attempted to update with invalid rating: {new_rating}. / Versuch, mit ungültiger Bewertung zu aktualisieren: {new_rating}.")
                return False

            user_movie_link.user_rating = new_rating
            db.session.commit()
            # Log info: User rating updated.
            # Info-Log: Benutzerbewertung aktualisiert.
            current_app.logger.info(f"User rating for user {user_id}, movie {movie_id} updated to {new_rating}. / Benutzerbewertung für Benutzer {user_id}, Film {movie_id} aktualisiert auf {new_rating}.")
            
            # Update the movie's community rating
            # Community-Rating des Films aktualisieren
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback()
            # Log error: Failed to update user rating.
            # Fehler-Log: Benutzerbewertung konnte nicht aktualisiert werden.
            current_app.logger.error(f"Error updating user rating for user {user_id}, movie {movie_id}: {e} / Fehler beim Aktualisieren der Benutzerbewertung für Benutzer {user_id}, Film {movie_id}: {e}")
            return False

    def delete_movie(self, movie_id: int) -> bool:
        """
        DEPRECATED (potentially). Consider using delete_movie_from_user_list for typical user actions.
        Löscht einen Film global anhand seiner ID. Dies entfernt den Film für ALLE Benutzer und auch alle zugehörigen UserMovie-Verknüpfungen und Kommentare durch Kaskadierung in den Modellen.
        Diese Funktion sollte mit Vorsicht verwendet werden, typischerweise nur für administrative Zwecke.
        Wenn ein Benutzer einen Film nur aus seiner persönlichen Liste entfernen möchte, sollte `delete_movie_from_user_list` verwendet werden.
        
        DEPRECATED (potenziell). Erwägen Sie die Verwendung von delete_movie_from_user_list für typische Benutzeraktionen.
        Deletes a movie globally by its ID. This removes the movie for ALL users and also all associated UserMovie links and comments through cascading in the models.
        This function should be used with caution, typically only for administrative purposes.
        If a user only wants to remove a movie from their personal list, `delete_movie_from_user_list` should be used.
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                # Log warning: Movie not found for global deletion.
                # Warnungs-Log: Film für globale Löschung nicht gefunden.
                current_app.logger.warning(f"Movie {movie_id} not found for global deletion. / Film {movie_id} für globale Löschung nicht gefunden.")
                return False
            db.session.delete(movie)
            db.session.commit()
            # Log info: Movie and associations deleted globally.
            # Info-Log: Film und zugehörige Verknüpfungen global gelöscht.
            current_app.logger.info(f"Movie {movie_id} and all its associations (UserMovie, Comment) deleted globally. / Film {movie_id} und alle zugehörigen Verknüpfungen (UserMovie, Comment) global gelöscht.")
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            # Log error: Failed to delete movie globally.
            # Fehler-Log: Film konnte nicht global gelöscht werden.
            current_app.logger.error(f"Error deleting movie {movie_id} globally: {e} / Fehler beim globalen Löschen von Film {movie_id}: {e}")
            return False

    def add_existing_movie_to_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Fügt einen bereits existierenden Film zur Liste eines Benutzers hinzu (UserMovie-Verknüpfung).
        Das Rating des Films selbst wird hierbei nicht verändert, nur die Verknüpfung hergestellt. Ein initiale User-Rating wird nicht gesetzt.

        Adds an already existing movie to a user's list (UserMovie link).
        The movie's rating itself is not changed here, only the link is established. An initial user rating is not set.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.warning(f"User {user_id} not found for adding movie to list. / Benutzer {user_id} nicht gefunden, um Film zur Liste hinzuzufügen.")
                return False
            
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie {movie_id} not found for adding to user list. / Film {movie_id} nicht gefunden, um zur Benutzerliste hinzugefügt zu werden.")
                return False

            # Check if the link already exists
            # Prüfen, ob die Verknüpfung bereits existiert
            existing_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
            if existing_link:
                current_app.logger.info(f"Movie {movie_id} is already in list of user {user_id}. / Film {movie_id} ist bereits in der Liste von Benutzer {user_id}.")
                return True # Already exists, treat as success / Bereits vorhanden, als Erfolg werten

            # Create new UserMovie link
            # Neue UserMovie-Verknüpfung erstellen
            user_movie_link = UserMovie(user_id=user.id, movie_id=movie.id, user_rating=None) # user_rating initially None / user_rating initial None
            db.session.add(user_movie_link)
            db.session.commit()
            current_app.logger.info(f"Added movie {movie_id} to list of user {user_id} (no initial rating). / Film {movie_id} zur Liste von Benutzer {user_id} hinzugefügt (keine initiale Bewertung).")
            self._update_community_rating(movie_id) # Update community rating / Community-Rating aktualisieren
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding movie {movie_id} to list for user {user_id}: {e} / Fehler beim Hinzufügen von Film {movie_id} zur Liste für Benutzer {user_id}: {e}")
            return False

    def _update_community_rating(self, movie_id: int) -> bool:
        """
        Private Hilfsmethode, um das Community-Rating eines Films neu zu berechnen.
        Wird aufgerufen, nachdem ein User-Rating hinzugefügt, geändert oder entfernt wurde.

        Private helper method to recalculate a movie's community rating.
        Called after a user rating is added, changed, or removed.
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie {movie_id} not found for updating community rating. / Film {movie_id} nicht gefunden zum Aktualisieren des Community-Ratings.")
                return False

            current_total_rating = 0.0
            current_rating_count = 0

            # Berücksichtige das initial_omdb_rating als erste "Stimme", falls vorhanden
            if movie.initial_omdb_rating is not None:
                current_total_rating += movie.initial_omdb_rating
                current_rating_count += 1
                current_app.logger.debug(f"Movie {movie_id}: Initial OMDb rating {movie.initial_omdb_rating} included in community rating calculation.")

            # Get all valid user ratings for this movie
            # Alle gültigen Benutzerbewertungen für diesen Film abrufen
            user_ratings_query = db.session.query(UserMovie.user_rating).filter(
                UserMovie.movie_id == movie_id,
                UserMovie.user_rating.isnot(None)
            ).all()

            user_ratings_list = [r[0] for r in user_ratings_query]

            current_total_rating += sum(user_ratings_list)
            current_rating_count += len(user_ratings_list)
            
            if current_rating_count > 0:
                movie.community_rating = current_total_rating / current_rating_count
                movie.community_rating_count = current_rating_count
            else:
                movie.community_rating = None # Sollte nicht passieren, wenn initial_omdb_rating da ist
                movie.community_rating_count = 0
            
            db.session.commit()
            current_app.logger.info(f"Community rating for movie {movie_id} updated: {movie.community_rating} ({movie.community_rating_count} ratings). initial_omdb_rating was: {movie.initial_omdb_rating}")
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating community rating for movie {movie_id}: {e} / Fehler beim Aktualisieren des Community-Ratings für Film {movie_id}: {e}")
            return False

    def delete_movie_from_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Entfernt einen Film aus der Liste eines bestimmten Benutzers (löscht die UserMovie-Verknüpfung).
        Aktualisiert danach das Community-Rating des Films.
        Gibt True zurück bei Erfolg, sonst False.

        Removes a movie from a specific user's list (deletes the UserMovie link).
        Updates the movie's community rating afterwards.
        Returns True on success, otherwise False.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                current_app.logger.warning(f"No link found for user {user_id} and movie {movie_id} to delete. / Keine Verknüpfung für Benutzer {user_id} und Film {movie_id} zum Löschen gefunden.")
                return False # Movie was not in the user's list / Film war nicht in der Liste des Benutzers

            db.session.delete(user_movie_link)
            db.session.commit()
            current_app.logger.info(f"Movie {movie_id} removed from list of user {user_id}. / Film {movie_id} aus der Liste von Benutzer {user_id} entfernt.")
            
            # Update the movie's community rating, as a rating might have been removed
            # (even if user_rating was None, it could theoretically be the last one affecting the calculation if it was the only link)
            # Community-Rating des Films aktualisieren, da möglicherweise eine Bewertung entfernt wurde
            # (selbst wenn user_rating None war, könnte es theoretisch das letzte sein, das die Berechnung beeinflusst, wenn es die einzige Verknüpfung war)
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing movie {movie_id} from list for user {user_id}: {e} / Fehler beim Entfernen von Film {movie_id} aus der Liste für Benutzer {user_id}: {e}")
            return False

    def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[Movie]:
        """
        Sucht einen Film anhand seiner IMDb-ID.
        Returns a movie by its IMDb ID.
        """
        try:
            return Movie.query.filter_by(imdb_id=imdb_id).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movie by imdb_id {imdb_id}: {e} / Fehler beim Abrufen des Films nach imdb_id {imdb_id}: {e}")
            return None

    def add_movie_globally(self, movie_data: dict) -> Optional[Movie]:
        """
        Fügt einen Film global zur Datenbank hinzu, wenn er nicht bereits existiert (basierend auf imdbID).
        Wenn ein OMDb-Rating vorhanden ist, wird dieses als initiales Community-Rating verwendet.
        Aktualisiert keine bestehenden Filmdaten, wenn der Film bereits existiert.
        Nimmt ein Dictionary mit Filmdetails entgegen (ähnlich OMDb-Antwort).
        Gibt das Movie-Objekt zurück (entweder das neu erstellte oder das bereits existierende).

        Adds a movie globally to the database if it doesn't already exist (based on imdbID).
        If an OMDb rating is present, it is used as the initial community rating.
        Does not update existing movie data if the movie already exists.
        Accepts a dictionary with movie details (similar to OMDb response).
        Returns the Movie object (either newly created or pre-existing).
        """
        imdb_id = movie_data.get('imdbID')
        if not imdb_id:
            current_app.logger.warning("Attempted to add global movie without imdbID. / Versuch, globalen Film ohne imdbID hinzuzufügen.")
            return None

        try:
            existing_movie = Movie.query.filter_by(imdb_id=imdb_id).first()
            if existing_movie:
                current_app.logger.info(f"Movie with imdb_id {imdb_id} already exists globally. Returning existing. / Film mit imdb_id {imdb_id} existiert bereits global. Bestehender wird zurückgegeben.")
                return existing_movie
            
            # Convert year safely. OMDb 'Year' can be 'YYYY' or 'YYYY–YYYY' (TV Series).
            # Jahr sicher konvertieren. OMDb 'Year' kann 'JJJJ' oder 'JJJJ–JJJJ' (TV-Serie) sein.
            year_str = movie_data.get('Year', '').strip()
            year = None
            if year_str:
                try:
                    # Take only the first year if it's a range
                    # Nur das erste Jahr nehmen, falls es ein Bereich ist
                    year_part = year_str.split('–')[0].split('-')[0].strip() # Handles both en-dash and hyphen / Behandelt Gedankenstrich und Bindestrich
                    if year_part.isdigit(): # Ensure it's all digits before int() / Sicherstellen, dass es nur Ziffern sind vor int()
                         year = int(year_part)
                    else:
                        current_app.logger.warning(f"Invalid year format (non-digit part) for global movie {imdb_id}: {year_str}. / Ungültiges Jahresformat (nicht-numerischer Teil) für globalen Film {imdb_id}: {year_str}.")
                except ValueError:
                    current_app.logger.warning(f"Invalid year format for global movie {imdb_id}: {year_str}. / Ungültiges Jahresformat für globalen Film {imdb_id}: {year_str}.")
                    # Optional: Add movie without year or error out / Optional: Film ohne Jahr hinzufügen oder Fehler ausgeben
                    # For now, proceed without year if format is unexpected beyond simple parsing / Vorerst ohne Jahr fortfahren, wenn das Format unerwartet ist

            # Poster URL Handling
            # Behandlung der Poster-URL
            poster_url = movie_data.get('Poster')
            if poster_url == 'N/A': # Treat OMDb's N/A as None / OMDb's N/A als None behandeln
                poster_url = None

            # Process OMDb rating for initial community rating
            # OMDb-Rating für initiales Community-Rating verarbeiten
            initial_community_rating_val = None
            initial_community_rating_count_val = 0
            raw_omdb_rating = movie_data.get('imdbRating')
            if raw_omdb_rating and raw_omdb_rating != 'N/A':
                try:
                    rating10 = float(raw_omdb_rating)
                    rating5 = round(rating10 / 2 * 2) / 2 # Convert to 0-5 scale, half steps / Umrechnung auf 0-5 Skala, halbe Schritte
                    if 0 <= rating5 <= 5:
                        initial_community_rating_val = rating5
                        initial_community_rating_count_val = 1
                        current_app.logger.info(f"Using OMDb rating {rating5} ({raw_omdb_rating}/10) as initial community rating for global movie {imdb_id}. / OMDb-Rating {rating5} ({raw_omdb_rating}/10) als initiales Community-Rating für globalen Film {imdb_id} verwendet.")
                except ValueError:
                    current_app.logger.warning(f"Invalid imdbRating format for global movie {imdb_id}: {raw_omdb_rating}. / Ungültiges imdbRating-Format für globalen Film {imdb_id}: {raw_omdb_rating}.")

            new_movie = Movie(
                imdb_id=imdb_id,
                title=movie_data.get('Title', 'N/A').strip(),
                year=year,
                director=movie_data.get('Director', '').strip() or None,
                poster_url=poster_url,
                plot=movie_data.get('Plot', '').strip() or None,
                runtime=movie_data.get('Runtime', '').strip() or None,
                awards=movie_data.get('Awards', '').strip() or None,
                language=movie_data.get('Language', '').strip() or None, # 'Language' in OMDb
                genre=movie_data.get('Genre', '').strip() or None,
                actors=movie_data.get('Actors', '').strip() or None,
                writer=movie_data.get('Writer', '').strip() or None,
                country=movie_data.get('Country', '').strip() or None,
                metascore=movie_data.get('Metascore', '').strip() or None,
                rated_omdb=movie_data.get('Rated', '').strip() or None, # 'Rated' in OMDb
                community_rating=initial_community_rating_val, # Wird jetzt durch _update_community_rating initial mit dem OMDb Wert (falls vorhanden) gesetzt
                community_rating_count=initial_community_rating_count_val, # Wird jetzt durch _update_community_rating initial mit 1 (falls OMDb Wert vorhanden) gesetzt
                initial_omdb_rating=initial_community_rating_val # HIER setzen wir das neue Feld
            )
            db.session.add(new_movie)
            db.session.commit() # Commit, damit new_movie.id verfügbar ist
            current_app.logger.info(f"Movie with imdb_id {imdb_id} added globally with id {new_movie.id}, initial_omdb_rating: {initial_community_rating_val}.")
            
            # Da _update_community_rating jetzt das initial_omdb_rating berücksichtigt,
            # können wir es hier aufrufen, um das community_rating und community_rating_count korrekt zu setzen.
            self._update_community_rating(new_movie.id)
            return new_movie
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding global movie with imdb_id {imdb_id}: {e}. / Fehler beim Hinzufügen des globalen Films mit imdb_id {imdb_id}: {e}.")
            return None
        except Exception as e: # Catch other potential errors like int conversion / Andere potenzielle Fehler wie int-Konvertierung abfangen
            db.session.rollback()
            current_app.logger.error(f"Unexpected error adding global movie with imdb_id {imdb_id}: {e}. / Unerwarteter Fehler beim Hinzufügen des globalen Films mit imdb_id {imdb_id}: {e}.")
            return None

    def get_top_movies(self, limit: int = 10) -> List[tuple[Movie, int, Optional[float]]]:
        """
        Liefert die Top-Filme basierend auf Nutzerzahl und durchschnittlichem Community-Rating.
        """
        try:
            results = (
                db.session.query(
                    Movie,
                    func.count(UserMovie.id).label('user_count'),
                    func.avg(Movie.community_rating).label('avg_rating')
                )
                .join(UserMovie, UserMovie.movie_id == Movie.id)
                .group_by(Movie.id)
                .order_by(desc('user_count'), desc(Movie.community_rating)) # Corrected: order by actual column or its label
                .limit(limit)
                .all()
            )
            return results
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching top movies: {e} / Fehler beim Abrufen der Top-Filme: {e}")
            return []

    def get_user_by_name(self, name: str) -> Optional[User]:
        """
        Liefert einen Benutzer anhand seines Namens (case-insensitive).
        Der Name wird intern bereinigt und in Kleinbuchstaben umgewandelt für den Vergleich.
        """
        try:
            # Bereinige den Eingabe-Namen genauso wie beim Erstellen/Suchen
            search_name = name.strip().lower()
            if not search_name:
                return None
            return User.query.filter(func.lower(User.name) == search_name).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching user by name '{name}': {e} / Fehler beim Abrufen des Benutzers nach Name '{name}': {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Liefert einen Benutzer anhand seiner ID.
        """
        try:
            return User.query.get(user_id)
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching user by ID {user_id}: {e} / Fehler beim Abrufen des Benutzers nach ID {user_id}: {e}")
            return None

    def get_user_movie_relations(self, user_id: int) -> List[UserMovie]:
        """
        Liefert alle UserMovie-Objekte für einen bestimmten Benutzer,
        geordnet nach einem sinnvollen Kriterium (z.B. Film-ID oder Hinzufüge-Datum, falls vorhanden).
        Aktuell nicht explizit geordnet, SQLAlchemy-Standardordnung.
        """
        try:
            # Explicitly join with Movie and User to potentially optimize or allow ordering by related fields later
            # Explizit mit Movie und User verbinden, um potenziell zu optimieren oder späteres Sortieren nach verwandten Feldern zu ermöglichen
            relations = UserMovie.query.filter_by(user_id=user_id)\
                .join(Movie, UserMovie.movie_id == Movie.id)\
                .join(User, UserMovie.user_id == User.id)\
                .all() # Add .order_by(Movie.title) or UserMovie.id for explicit ordering if needed
            return relations
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching user movie relations for user {user_id}: {e} / Fehler beim Abrufen der Filmverknüpfungen für Benutzer {user_id}: {e}")
            return []

    def get_movie_by_id(self, movie_id: int) -> Optional[Movie]:
        """
        Liefert einen Film anhand seiner ID.
        """
        try:
            return Movie.query.get(movie_id)
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movie by ID {movie_id}: {e} / Fehler beim Abrufen des Films nach ID {movie_id}: {e}")
            return None

    def add_comment(self, movie_id: int, user_id: int, text: str) -> Optional[Comment]:
        """
        Fügt einen neuen Kommentar zu einem Film hinzu.
        """
        text = text.strip()
        if not text:
            current_app.logger.warning("Attempted to add empty comment. / Versuch, leeren Kommentar hinzuzufügen.")
            return None

        user = self.get_user_by_id(user_id)
        if not user:
            current_app.logger.warning(f"User with ID {user_id} not found when adding comment. / Benutzer mit ID {user_id} beim Hinzufügen eines Kommentars nicht gefunden.")
            return None
        
        movie = self.get_movie_by_id(movie_id)
        if not movie:
            current_app.logger.warning(f"Movie with ID {movie_id} not found when adding comment. / Film mit ID {movie_id} beim Hinzufügen eines Kommentars nicht gefunden.")
            return None
            
        try:
            comment = Comment(movie_id=movie.id, user_id=user.id, text=text)
            db.session.add(comment)
            db.session.commit()
            current_app.logger.info(f"Comment added by user {user_id} to movie {movie_id}. / Kommentar von Benutzer {user_id} zu Film {movie_id} hinzugefügt.")
            return comment
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding comment by user {user_id} to movie {movie_id}: {e} / Fehler beim Hinzufügen des Kommentars von Benutzer {user_id} zu Film {movie_id}: {e}")
            return None

    def get_all_movies(self) -> List[Movie]:
        """
        Liefert eine Liste aller Filme in der Datenbank.
        """
        try:
            return Movie.query.all() # Ggf. .order_by(Movie.title) hinzufügen
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching all movies: {e} / Fehler beim Abrufen aller Filme: {e}")
            return []

    def get_comments_for_movie(self, movie_id: int) -> List[Comment]:
        """
        Liefert alle Kommentare für einen bestimmten Film, geordnet nach Erstellungsdatum (neueste zuerst).
        """
        try:
            movie = self.get_movie_by_id(movie_id) # Check if movie exists
            if not movie:
                current_app.logger.warning(f"Movie with ID {movie_id} not found when fetching comments. / Film mit ID {movie_id} beim Abrufen der Kommentare nicht gefunden.")
                return []
            return Comment.query.filter_by(movie_id=movie_id).order_by(Comment.created_at.desc()).all()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching comments for movie {movie_id}: {e} / Fehler beim Abrufen der Kommentare für Film {movie_id}: {e}")
            return []

    def get_user_movie_link(self, user_id: int, movie_id: int) -> Optional[UserMovie]:
        """
        Liefert die spezifische UserMovie-Verknüpfung zwischen einem Benutzer und einem Film.
        """
        try:
            # Stelle sicher, dass User und Movie existieren, bevor die Verknüpfung gesucht wird
            user = self.get_user_by_id(user_id)
            if not user:
                current_app.logger.warning(f"User with ID {user_id} not found when fetching UserMovie link.")
                return None
            movie = self.get_movie_by_id(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie with ID {movie_id} not found when fetching UserMovie link.")
                return None

            return UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching UserMovie link for user {user_id}, movie {movie_id}: {e}")
            return None