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
    Concrete implementation of the DataManagerInterface using SQLite with SQLAlchemy.
    It handles all database interactions for the MovieWeb application, including managing users,
    movies, user-movie relationships (ratings), and comments.

    Konkrete Umsetzung des DataManagerInterface für SQLite mit SQLAlchemy.
    Diese Klasse handhabt alle Datenbankinteraktionen für die MovieWeb-Anwendung,
    einschließlich der Verwaltung von Benutzern, Filmen, Benutzer-Film-Beziehungen (Bewertungen) und Kommentaren.
    """

    def get_all_users(self) -> List[User]:
        """
        Retrieves all users from the database.
        Liefert alle Benutzer aus der Datenbank.
        """
        try:
            return User.query.all()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching all users: {e}.")
            # Error fetching all users: {e}. / Fehler beim Abrufen aller Benutzer: {e}.
            return []

    def get_user_movies(self, user_id: int) -> List[Movie]:
        """
        Retrieves all movies linked to a specific user.
        Liefert alle Filme, die mit einem bestimmten Benutzer verknüpft sind.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.warning(f"User with ID {user_id} not found when trying to fetch their movies.")
                # User with ID {user_id} not found. / Benutzer mit ID {user_id} nicht gefunden.
                return []
            # Fetch movies via UserMovie relationship
            # Filme über UserMovie-Beziehung abrufen
            return [um.movie for um in user.movies]
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movies for user {user_id}: {e}.")
            # Error fetching movies for user {user_id}: {e}. / Fehler beim Abrufen der Filme für Benutzer {user_id}: {e}.
            return []

    def add_user(self, name: str) -> Optional[User]:
        """
        Adds a new user. Handles input validation (stripping, lowercasing, empty check)
        and checks for duplicates before attempting to add the user to the database.

        Fügt einen neuen Benutzer hinzu. Behandelt die Eingabevalidierung (Entfernen von Leerzeichen, 
        Umwandlung in Kleinbuchstaben, Prüfung auf leere Eingabe) und prüft auf Duplikate, 
        bevor versucht wird, den Benutzer zur Datenbank hinzuzufügen.
        """
        name_processed = name.strip().lower()
        if not name_processed:
            current_app.logger.warning("Attempted to add user with empty name.")
            # Attempted to add user with empty name. / Versuch, Benutzer mit leerem Namen hinzuzufügen.
            return None
        
        try:
            if User.query.filter(func.lower(User.name) == name_processed).first():
                current_app.logger.warning(f"Attempted to add duplicate user: '{name_processed}'.")
                # Attempted to add duplicate user '{name_processed}'. / Versuch, doppelten Benutzer '{name_processed}' hinzuzufügen.
                return None

            user = User(name=name_processed) 
            db.session.add(user)
            db.session.commit()
            current_app.logger.info(f"User '{user.name}' (ID: {user.id}) added successfully.")
            # User '{user.name}' (ID: {user.id}) added successfully. / Benutzer '{user.name}' (ID: {user.id}) erfolgreich hinzugefügt.
            return user
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding user '{name_processed}': {e}.")
            # Error adding user '{name_processed}': {e}. / Fehler beim Hinzufügen von Benutzer '{name_processed}': {e}.
            return None

    def _validate_movie_input(self, title: str, year: Optional[int], rating: Optional[float]) -> bool:
        """
        Validates basic movie input fields like title, year, and rating.
        Does not produce flash messages, only logs warnings for internal use by the DataManager.

        Validiert grundlegende Filmeingabefelder wie Titel, Jahr und Bewertung.
        Erzeugt keine Flash-Meldungen, sondern loggt nur Warnungen für den internen Gebrauch durch den DataManager.
        """
        if not title:
            current_app.logger.warning("Validation failed: Movie title cannot be empty.")
            # Validation failed: Movie title cannot be empty. / Validierung fehlgeschlagen: Filmtitel darf nicht leer sein.
            return False

        current_datetime_year = datetime.now().year
        if year is not None and year > current_datetime_year:
            current_app.logger.warning(f"Validation failed: Movie year {year} is in the future (current year: {current_datetime_year}).")
            # Validation failed: Movie year {year} is in the future. / Validierung fehlgeschlagen: Filmjahr {year} liegt in der Zukunft.
            return False

        if rating is not None and not (0 <= rating <= 5):
            current_app.logger.warning(f"Validation failed: Movie rating {rating} is outside the allowed range (0-5).")
            # Validation failed: Movie rating {rating} is outside the allowed range (0-5). / Validierung fehlgeschlagen: Filmbewertung {rating} liegt außerhalb des erlaubten Bereichs (0-5).
            return False
        return True

    def _get_or_create_movie_internal(
        self, title: str, director: Optional[str], year: Optional[int], poster_url: Optional[str],
        plot: Optional[str], runtime: Optional[str], awards: Optional[str], languages: Optional[str],
        genre: Optional[str], actors: Optional[str], writer: Optional[str], country: Optional[str],
        metascore: Optional[str], rated: Optional[str], imdb_id: Optional[str],
        omdb_data: Optional[dict] # Expects OMDb-like raw data if a new movie is to be created from it.
                                  # Erwartet OMDb-ähnliche Rohdaten, falls ein neuer Film daraus erstellt werden soll.
    ) -> Optional[tuple[Movie, bool]]: # Returns (Movie object, was_created_boolean) or None
                                       # Gibt (Movie-Objekt, wurde_erstellt_boolean) oder None zurück
        """
        Internal helper: Finds a movie by IMDb ID, or by title and year, or creates a new one using omdb_data.
        If found by title/year and imdb_id is provided, it updates the existing movie's imdb_id if it was missing.
        Commits changes only if an existing movie's imdb_id is updated.
        If a new movie is created via add_movie_globally, that method handles its own transactions.

        Interne Hilfsmethode: Findet einen Film anhand der IMDb-ID oder anhand von Titel und Jahr,
        oder erstellt einen neuen Film unter Verwendung von omdb_data.
        Wenn der Film anhand von Titel/Jahr gefunden wird und eine imdb_id angegeben ist,
        wird die imdb_id des existierenden Films aktualisiert, falls sie fehlte.
        Committet Änderungen nur, wenn die imdb_id eines existierenden Films aktualisiert wird.
        Wenn ein neuer Film über add_movie_globally erstellt wird, handhabt diese Methode ihre eigenen Transaktionen.
        """
        movie = None # Initialize movie variable / Initialisiere Filmvariable
        try:
            if imdb_id:
                movie = Movie.query.filter_by(imdb_id=imdb_id).first()
                if movie:
                    current_app.logger.info(f"Movie found by imdb_id '{imdb_id}' (ID: {movie.id}) in _get_or_create_movie_internal.")
                    return movie, False # False, as the movie already existed

            if not movie and title and year is not None:
                movie = Movie.query.filter(func.lower(Movie.title) == func.lower(title), Movie.year == year).first()
                if movie:
                    current_app.logger.info(f"Movie found by title '{title}' and year {year} (ID: {movie.id}) in _get_or_create_movie_internal.")
                    if imdb_id and not movie.imdb_id: # If found by title/year, but an imdb_id was passed and it's not yet in the DB movie
                        current_app.logger.info(f"Updating existing movie {movie.id} (Title: '{movie.title}') with new imdb_id '{imdb_id}'.")
                        movie.imdb_id = imdb_id
                        db.session.commit() # Commit only this specific update / Nur dieses spezifische Update committen
                    return movie, False # False, as the movie already existed or was just updated (not newly created)

            if not movie and omdb_data: # Movie not found, needs to be created, and we have OMDb data
                current_app.logger.info(f"Movie '{omdb_data.get('Title', title)}' (imdb_id: {omdb_data.get('imdbID', imdb_id or 'N/A')}) not found. Attempting to create it globally.")
                new_global_movie = self.add_movie_globally(omdb_data) # This method handles its own commit/rollback
                if new_global_movie:
                    current_app.logger.info(f"Successfully created new global movie '{new_global_movie.title}' (ID: {new_global_movie.id}) via add_movie_globally.")
                    return new_global_movie, True # True, as the movie was newly created
                else:
                    current_app.logger.error(f"Failed to create new global movie for title '{omdb_data.get('Title', title)}' using add_movie_globally.")
                    return None, False # Creation failed
            
            if not movie: # Movie still not found and no OMDb data to create it from
                 current_app.logger.warning(f"Movie '{title}' (imdb_id: {imdb_id or 'N/A'}) not found and no OMDb data provided for creation in _get_or_create_movie_internal.")
                 return None, False


        except SQLAlchemyError as e:
            db.session.rollback() 
            current_app.logger.error(f"SQLAlchemyError in _get_or_create_movie_internal for title '{title}', imdb_id {imdb_id or 'N/A'}: {e}.")
            return None, False
        except Exception as e: # Catch any other unexpected error
            db.session.rollback()
            current_app.logger.error(f"Unexpected error in _get_or_create_movie_internal for title '{title}', imdb_id {imdb_id or 'N/A'}: {e}.")
            return None, False
        
        return movie, False # Should be unreachable if logic is correct, but as a fallback.

    def _create_or_update_user_movie_link(self, user_id: int, movie_id: int, rating: Optional[float]) -> Optional[UserMovie]:
        """
        Internal helper: Creates or updates the UserMovie link between a user and a movie.
        Adds the UserMovie object to the session but does not commit here; calling function handles commit.

        Interne Hilfsmethode: Erstellt oder aktualisiert die UserMovie-Verknüpfung zwischen einem Benutzer und einem Film.
        Fügt das UserMovie-Objekt zur Session hinzu, committet hier aber nicht; die aufrufende Funktion handhabt den Commit.
        """
        user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

        if not user_movie_link:
            current_app.logger.info(f"No existing UserMovie link for user {user_id}, movie {movie_id}. Creating new link with rating: {rating}.")
            user_movie_link = UserMovie(user_id=user_id, movie_id=movie_id, user_rating=rating)
            try:
                db.session.add(user_movie_link)
                # No flush or commit here, let the calling function manage the transaction.
            except SQLAlchemyError as e: # Should be rare if objects are fine
                current_app.logger.error(f"Error adding new UserMovie link for user {user_id}, movie {movie_id} to session: {e}.")
                return None 
        else: # Link exists, update rating if different
            if user_movie_link.user_rating != rating: # Handles None comparison correctly
                current_app.logger.info(f"Existing UserMovie link for user {user_id}, movie {movie_id}. Updating rating from {user_movie_link.user_rating} to {rating}.")
                user_movie_link.user_rating = rating
                try:
                    db.session.add(user_movie_link) # Add to session to mark as dirty if changed
                    # No flush or commit here
                except SQLAlchemyError as e: # Should be rare
                     current_app.logger.error(f"Error adding updated UserMovie link for user {user_id}, movie {movie_id} to session: {e}.")
                     return None
            else:
                current_app.logger.info(f"UserMovie link for user {user_id}, movie {movie_id} exists and rating ({rating}) is unchanged.")
        return user_movie_link

    def add_movie(self, user_id: int, title: str, director: Optional[str], year: Optional[int], rating: Optional[float], poster_url: Optional[str] = None,
                  plot: Optional[str] = None, runtime: Optional[str] = None, awards: Optional[str] = None, languages: Optional[str] = None,
                  genre: Optional[str] = None, actors: Optional[str] = None, writer: Optional[str] = None, country: Optional[str] = None,
                  metascore: Optional[str] = None, rated: Optional[str] = None, imdb_id: Optional[str] = None,
                  omdb_rating_for_community: Optional[float] = None) -> Optional[Movie]:
        """
        Adds a movie to a user's list. If the movie doesn't exist globally, it's created.
        This involves validating input, getting/creating the movie, creating/updating the user-movie link,
        and then updating the movie's community rating. Commits or rolls back the overall transaction.

        Fügt einen Film zur Liste eines Benutzers hinzu. Wenn der Film nicht global existiert, wird er erstellt.
        Dies beinhaltet die Validierung der Eingabe, das Holen/Erstellen des Films, das Erstellen/Aktualisieren 
        der Benutzer-Film-Verknüpfung und die anschließende Aktualisierung des Community-Ratings des Films. 
        Führt ein Commit oder Rollback der gesamten Transaktion durch.
        """
        title_cleaned = title.strip() if title else ""
        # director_cleaned = director.strip() if director else None 
        # imdb_id_cleaned = imdb_id.strip() if imdb_id else None

        if not self._validate_movie_input(title_cleaned, year, rating): # Use cleaned title
            return None # Validation messages logged in _validate_movie_input

        try:
            user = self.get_user_by_id(user_id)
            if not user:
                current_app.logger.warning(f"Add movie failed: User {user_id} not found.")
                # User {user_id} not found. / Benutzer {user_id} nicht gefunden.
                return None

            # Prepare OMDb data dict for _get_or_create_movie_internal if new movie creation is expected
            # Bereite OMDb-Daten-Dictionary für _get_or_create_movie_internal vor, wenn Filmerstellung erwartet wird
            omdb_data_payload = None
            if imdb_id: # If imdb_id is present, we assume this might be OMDb-sourced data
                omdb_data_payload = {
                    'Title': title_cleaned, 'Director': director, 'Year': str(year) if year else None, 
                    'Poster': poster_url, 'Plot': plot, 'Runtime': runtime, 'Awards': awards, 
                    'Language': languages, 'Genre': genre, 'Actors': actors, 'Writer': writer, 
                    'Country': country, 'Metascore': metascore, 'Rated': rated, 'imdbID': imdb_id,
                    # Pass the user's personal rating as 'imdbRating' only if it's for the initial OMDb import context
                    # This is a bit tricky; omdb_rating_for_community is a better source for initial global rating
                    'imdbRating': str(omdb_rating_for_community * 2) if omdb_rating_for_community is not None else None
                }
            
            movie_obj_tuple = self._get_or_create_movie_internal(
                title_cleaned, director, year, poster_url, plot, runtime, awards, languages,
                genre, actors, writer, country, metascore, rated, imdb_id,
                omdb_data=omdb_data_payload 
            )
            
            if not movie_obj_tuple or not movie_obj_tuple[0]:
                # Error logged in _get_or_create_movie_internal
                raise SQLAlchemyError("Failed to get or create movie internally.")
            
            movie_obj = movie_obj_tuple[0]
            # is_new_movie = movie_obj_tuple[1] # Can be used if specific logic for new vs existing is needed here

            user_movie_link = self._create_or_update_user_movie_link(user.id, movie_obj.id, rating)
            if not user_movie_link:
                raise SQLAlchemyError(f"Failed to create/update UserMovie link for user {user.id}, movie {movie_obj.id}.")

            # Commit changes to Movie (if new/updated imdb_id) and UserMovie link
            # This commit is crucial before _update_community_rating, which itself commits.
            db.session.commit() 
            current_app.logger.info(f"Committed changes for movie {movie_obj.id} and UserMovie link for user {user_id} before updating community rating.")

            if self._update_community_rating(movie_obj.id): # This method also commits on its success
                current_app.logger.info(f"Movie '{movie_obj.title}' (ID: {movie_obj.id}) successfully processed for user {user_id} and community rating updated.")
                return movie_obj
            else:
                # _update_community_rating handles its own rollback on failure.
                # The previous commit for UserMovie link might persist if _update_community_rating fails.
                # This is generally acceptable as the user's rating is saved, even if global update fails.
                # For stricter atomicity, _update_community_rating should not commit but pass status back.
                # However, current design is that _update_community_rating is a self-contained unit of work.
                current_app.logger.error(f"Failed to update community rating for movie {movie_obj.id} after processing for user {user_id}. User-specific changes might be saved.")
                # We return the movie object as the primary operation (adding to user list) might have succeeded with its commit.
                return movie_obj # Or raise an error if partial success is not desired.
                
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"SQLAlchemyError in add_movie for title '{title_cleaned}', user {user_id}: {e}. Operation rolled back.")
            return None
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error in add_movie for title '{title_cleaned}', user {user_id}: {e}. Operation rolled back.")
            return None

    def update_user_rating_for_movie(self, user_id: int, movie_id: int, new_rating: Optional[float]) -> bool:
        """
        Updates an individual user's rating for a specific movie.
        It first validates the rating, then updates the UserMovie link. 
        If successful, it commits this change and then triggers an update of the movie's community rating.

        Aktualisiert das individuelle Rating eines Benutzers für einen bestimmten Film.
        Validiert zuerst die Bewertung, aktualisiert dann die UserMovie-Verknüpfung.
        Bei Erfolg wird diese Änderung committet und anschließend eine Aktualisierung 
        des Community-Ratings des Films ausgelöst.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                current_app.logger.warning(f"Update rating failed: No UserMovie link found for user {user_id} and movie {movie_id}.")
                # No UserMovie link found for user {user_id} and movie {movie_id}. / Keine UserMovie-Verknüpfung für Benutzer {user_id} und Film {movie_id} gefunden.
                return False
            
            if new_rating is not None and not (0 <= new_rating <= 5):
                current_app.logger.warning(f"Update rating failed: Invalid rating value {new_rating} for user {user_id}, movie {movie_id}. Must be between 0 and 5.")
                # Invalid rating value {new_rating}. Must be between 0 and 5. / Ungültiger Bewertungswert {new_rating}. Muss zwischen 0 und 5 liegen.
                return False

            user_movie_link.user_rating = new_rating
            db.session.commit() 
            current_app.logger.info(f"User rating for user {user_id}, movie {movie_id} updated to {new_rating} and committed.")
            # User rating updated and committed. / Benutzerbewertung aktualisiert und committet.
            
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback() 
            current_app.logger.error(f"Error updating user rating for user {user_id}, movie {movie_id}: {e}.")
            # Error updating user rating. / Fehler beim Aktualisieren der Benutzerbewertung.
            return False

    def delete_movie(self, movie_id: int) -> bool:
        """
        DEPRECATED (potentially). Consider using delete_movie_from_user_list for typical user actions.
        Globally deletes a movie by its ID. This removes the movie for ALL users and also all associated 
        UserMovie links and Comments due to cascading rules defined in the models.
        This function should be used with extreme caution, typically only for administrative purposes.

        VERALTET (potenziell). Erwägen Sie die Verwendung von delete_movie_from_user_list für typische Benutzeraktionen.
        Löscht einen Film global anhand seiner ID. Dies entfernt den Film für ALLE Benutzer sowie alle zugehörigen 
        UserMovie-Verknüpfungen und Kommentare aufgrund von Kaskadierungsregeln, die in den Modellen definiert sind.
        Diese Funktion sollte mit äußerster Vorsicht verwendet werden, typischerweise nur für administrative Zwecke.
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Global movie deletion failed: Movie with ID {movie_id} not found.")
                # Movie with ID {movie_id} not found. / Film mit ID {movie_id} nicht gefunden.
                return False
            
            current_app.logger.info(f"Attempting global deletion of movie '{movie.title}' (ID: {movie_id}). This will remove all associated user links and comments.")
            db.session.delete(movie)
            db.session.commit()
            current_app.logger.info(f"Movie '{movie.title}' (ID: {movie_id}) and all its associations deleted globally.")
            # Movie and associations deleted globally. / Film und zugehörige Verknüpfungen global gelöscht.
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error during global deletion of movie {movie_id}: {e}.")
            # Error during global deletion of movie. / Fehler beim globalen Löschen des Films.
            return False

    def add_existing_movie_to_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Adds an already globally existing movie to a specific user's list.
        This creates a UserMovie link without an initial user-specific rating (rating will be None).
        The movie's community rating is updated afterwards.

        Fügt einen bereits global existierenden Film zur Liste eines bestimmten Benutzers hinzu.
        Dies erstellt eine UserMovie-Verknüpfung ohne eine anfängliche benutzerspezifische Bewertung (Bewertung ist None).
        Das Community-Rating des Films wird danach aktualisiert.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.warning(f"Add to list failed: User {user_id} not found.")
                # User {user_id} not found. / Benutzer {user_id} nicht gefunden.
                return False
            
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Add to list failed: Movie {movie_id} not found globally.")
                # Movie {movie_id} not found globally. / Film {movie_id} global nicht gefunden.
                return False

            existing_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
            if existing_link:
                current_app.logger.info(f"Movie {movie_id} is already in list of user {user_id}. No action needed.")
                # Movie {movie_id} is already in list of user {user_id}. / Film {movie_id} ist bereits in der Liste von Benutzer {user_id}.
                return True 

            user_movie_link = UserMovie(user_id=user.id, movie_id=movie.id, user_rating=None)
            db.session.add(user_movie_link)
            db.session.commit() 
            current_app.logger.info(f"Added movie {movie_id} to list of user {user_id} (no initial rating) and committed link.")
            # Added movie to user list (no initial rating) and committed link. / Film zur Benutzerliste hinzugefügt (keine initiale Bewertung) und Verknüpfung committet.
            
            return self._update_community_rating(movie_id) 

        except SQLAlchemyError as e:
            db.session.rollback() 
            current_app.logger.error(f"Error adding movie {movie_id} to list for user {user_id}: {e}.")
            # Error adding movie to user list. / Fehler beim Hinzufügen des Films zur Benutzerliste.
            return False

    def _update_community_rating(self, movie_id: int) -> bool:
        """
        Private helper: Recalculates and updates a movie's community rating and rating count.
        This is based on its initial OMDb rating (if any) and all individual user ratings.
        Commits the changes to the movie if successful.

        Private Hilfsmethode: Berechnet das Community-Rating und die Anzahl der Bewertungen eines Films neu und aktualisiert diese.
        Dies basiert auf seiner initialen OMDb-Bewertung (falls vorhanden) und allen individuellen Benutzerbewertungen.
        Committet die Änderungen am Film bei Erfolg.
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Community rating update failed: Movie {movie_id} not found.")
                # Movie {movie_id} not found. / Film {movie_id} nicht gefunden.
                return False

            current_total_rating = 0.0
            current_rating_count = 0

            if movie.initial_omdb_rating is not None:
                current_total_rating += movie.initial_omdb_rating
                current_rating_count += 1
                current_app.logger.debug(f"Movie {movie_id}: Initial OMDb rating {movie.initial_omdb_rating} included in community rating calculation.")

            user_ratings_query = db.session.query(UserMovie.user_rating).filter(
                UserMovie.movie_id == movie_id,
                UserMovie.user_rating.isnot(None) # Only consider non-null ratings
            ).all()

            user_ratings_list = [r[0] for r in user_ratings_query]

            current_total_rating += sum(user_ratings_list)
            current_rating_count += len(user_ratings_list)
            
            if current_rating_count > 0:
                movie.community_rating = round(current_total_rating / current_rating_count, 2) # Round to 2 decimal places
                movie.community_rating_count = current_rating_count
            else: # Should only happen if initial_omdb_rating is also None and no user ratings
                movie.community_rating = None 
                movie.community_rating_count = 0
            
            db.session.commit() # Commit the updated movie rating and count
            current_app.logger.info(f"Community rating for movie {movie_id} ('{movie.title}') updated to: {movie.community_rating} ({movie.community_rating_count} ratings). Initial OMDb: {movie.initial_omdb_rating}.")
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating community rating for movie {movie_id}: {e}.")
            # Error updating community rating. / Fehler beim Aktualisieren des Community-Ratings.
            return False

    def delete_movie_from_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Removes a movie from a specific user's list by deleting the UserMovie link.
        After successfully deleting the link and committing, it updates the movie's community rating.

        Entfernt einen Film aus der Liste eines bestimmten Benutzers durch Löschen der UserMovie-Verknüpfung.
        Nach erfolgreichem Löschen der Verknüpfung und Commit wird das Community-Rating des Films aktualisiert.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                current_app.logger.warning(f"Delete from list failed: No UserMovie link found for user {user_id} and movie {movie_id} to delete.")
                # No UserMovie link found for user {user_id} and movie {movie_id} to delete. / Keine UserMovie-Verknüpfung für Benutzer {user_id} und Film {movie_id} zum Löschen gefunden.
                return False 

            db.session.delete(user_movie_link)
            db.session.commit() 
            current_app.logger.info(f"UserMovie link for user {user_id}, movie {movie_id} deleted and committed.")
            # UserMovie link deleted and committed. / UserMovie-Verknüpfung gelöscht und committet.
            
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback() 
            current_app.logger.error(f"Error removing movie {movie_id} from list for user {user_id}: {e}.")
            # Error removing movie from list. / Fehler beim Entfernen des Films von der Liste.
            return False

    def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[Movie]:
        """
        Retrieves a movie from the database by its IMDb ID.
        Sucht einen Film anhand seiner IMDb-ID in der Datenbank.
        """
        if not imdb_id: # Prevent empty imdb_id queries
            current_app.logger.debug("Attempted to fetch movie with empty imdb_id.")
            return None
        try:
            return Movie.query.filter_by(imdb_id=imdb_id).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movie by imdb_id '{imdb_id}': {e}.")
            # Error fetching movie by imdb_id. / Fehler beim Abrufen des Films nach imdb_id.
            return None

    def _parse_omdb_data_for_movie_fields(self, movie_data: dict) -> dict:
        """
        Parses raw OMDb-like data and converts it into a clean dictionary suitable for Movie model fields.
        Handles type conversions (e.g., year to int, rating to float) and default values for missing fields.

        Parst Rohdaten (OMDb-ähnlich) und konvertiert sie in ein sauberes Dictionary, das für Movie-Modellfelder geeignet ist.
        Behandelt Typkonvertierungen (z.B. Jahr zu int, Bewertung zu float) und Standardwerte für fehlende Felder.
        """
        parsed_data = {}
        imdb_id_for_log = movie_data.get('imdbID', 'N/A') # For logging context

        parsed_data['title'] = movie_data.get('Title', 'N/A').strip()
        parsed_data['director'] = movie_data.get('Director', '').strip() or None
        parsed_data['plot'] = movie_data.get('Plot', '').strip() or None
        parsed_data['runtime'] = movie_data.get('Runtime', '').strip() or None
        parsed_data['awards'] = movie_data.get('Awards', '').strip() or None
        parsed_data['language'] = movie_data.get('Language', '').strip() or None
        parsed_data['genre'] = movie_data.get('Genre', '').strip() or None
        parsed_data['actors'] = movie_data.get('Actors', '').strip() or None
        parsed_data['writer'] = movie_data.get('Writer', '').strip() or None
        parsed_data['country'] = movie_data.get('Country', '').strip() or None
        parsed_data['metascore'] = movie_data.get('Metascore', '').strip() or None
        parsed_data['rated_omdb'] = movie_data.get('Rated', '').strip() or None
        parsed_data['imdb_id'] = movie_data.get('imdbID') 

        year_str = movie_data.get('Year', '').strip()
        year = None
        if year_str:
            try: # Handle cases like "2000-2005" or "2000"
                year_part = year_str.split('–')[0].split('-')[0].strip() # en-dash or hyphen
                if year_part.isdigit():
                    year = int(year_part)
                else:
                    current_app.logger.warning(f"Invalid year format (non-digit part '{year_part}') from OMDb for imdbID {imdb_id_for_log}: '{year_str}'.")
            except ValueError: # Should not happen if isdigit() is true
                current_app.logger.warning(f"ValueError converting year from OMDb for imdbID {imdb_id_for_log}: '{year_str}'.")
        parsed_data['year'] = year

        poster_url = movie_data.get('Poster')
        parsed_data['poster_url'] = poster_url if poster_url and poster_url != 'N/A' else None

        initial_omdb_rating_val = None
        raw_omdb_rating = movie_data.get('imdbRating')
        if raw_omdb_rating and raw_omdb_rating != 'N/A':
            try:
                rating10 = float(raw_omdb_rating)
                rating5 = round(rating10 / 2, 1) # Convert to 0-5 scale, round to 1 decimal place for 0.5 steps
                if 0 <= rating5 <= 5:
                    initial_omdb_rating_val = rating5
                else:
                    current_app.logger.warning(f"OMDb rating '{raw_omdb_rating}' for imdbID {imdb_id_for_log} is out of 0-10 range after conversion to 0-5 scale ({rating5}).")
            except ValueError:
                current_app.logger.warning(f"Invalid imdbRating format '{raw_omdb_rating}' from OMDb for imdbID {imdb_id_for_log}. Cannot convert to float.")
        parsed_data['initial_omdb_rating'] = initial_omdb_rating_val
        
        return parsed_data

    def add_movie_globally(self, movie_data: dict) -> Optional[Movie]:
        """
        Adds a movie globally to the database if it doesn't already exist (based on imdbID).
        Uses _parse_omdb_data_for_movie_fields for data preparation.
        Does not update existing movie data if the movie already exists.
        Returns the Movie object (either newly created or pre-existing).
        This method handles its own database transaction (commit or rollback).

        Fügt einen Film global zur Datenbank hinzu, wenn er nicht bereits existiert (basierend auf imdbID).
        Verwendet _parse_omdb_data_for_movie_fields zur Datenaufbereitung.
        Aktualisiert keine bestehenden Filmdaten, wenn der Film bereits existiert.
        Gibt das Movie-Objekt zurück (entweder das neu erstellte oder das bereits existierende).
        Diese Methode handhabt ihre eigene Datenbanktransaktion (Commit oder Rollback).
        """
        raw_imdb_id = movie_data.get('imdbID')
        if not raw_imdb_id:
            current_app.logger.warning("Attempted to add global movie without imdbID from raw data.")
            return None

        try:
            existing_movie = Movie.query.filter_by(imdb_id=raw_imdb_id).first()
            if existing_movie:
                current_app.logger.info(f"Movie with imdb_id {raw_imdb_id} already exists globally. Returning existing id: {existing_movie.id}.")
                return existing_movie
            
            parsed_movie_fields = self._parse_omdb_data_for_movie_fields(movie_data)
            
            if not parsed_movie_fields.get('imdb_id'): # Should be redundant due to raw_imdb_id check
                 current_app.logger.error(f"Critical: imdbID missing after parsing OMDb data for supposed imdbID {raw_imdb_id}. Aborting global add.")
                 return None 

            current_app.logger.info(f"Creating new global movie entry for '{parsed_movie_fields.get('title', 'N/A')}' (imdbID: {parsed_movie_fields['imdb_id']}).")
            
            new_movie = Movie(**parsed_movie_fields)
            
            db.session.add(new_movie)
            db.session.flush() # Flush to get new_movie.id for _update_community_rating
            current_app.logger.info(f"Movie '{new_movie.title}' (imdb_id: {new_movie.imdb_id}) added to session with ID {new_movie.id} before community rating update.")
            
            if self._update_community_rating(new_movie.id): # This method commits on its own success
                current_app.logger.info(f"Movie '{new_movie.title}' (imdb_id: {new_movie.imdb_id}) successfully added globally and community rating updated.")
                return new_movie # Success
            else: # _update_community_rating failed and should have rolled back its own changes.
                  # We need to ensure the new_movie addition is also rolled back.
                current_app.logger.error(f"Failed to update community rating for new global movie '{new_movie.title}' (ID: {new_movie.id}). Rolling back global add.")
                db.session.rollback() # Explicit rollback for the new_movie addition
                return None

        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"SQLAlchemyError in add_movie_globally for imdbID {raw_imdb_id}: {e}. Operation rolled back.")
            return None
        except Exception as e: # Catch any other unexpected errors
            db.session.rollback()
            current_app.logger.error(f"Unexpected error in add_movie_globally for imdbID {raw_imdb_id}: {e}. Operation rolled back.")
            return None

    def get_top_movies(self, limit: int = 10) -> List[tuple[Movie, int, Optional[float]]]:
        """
        Retrieves the top movies based on the number of users who have it in their list and then by community rating.
        Returns a list of tuples: (Movie object, user_count, avg_community_rating).

        Liefert die Top-Filme basierend auf der Anzahl der Benutzer, die ihn in ihrer Liste haben, 
        und dann nach dem Community-Rating.
        Gibt eine Liste von Tupeln zurück: (Movie-Objekt, user_count, avg_community_rating).
        """
        try:
            results = (
                db.session.query(
                    Movie,
                    func.count(UserMovie.user_id).label('user_count'), # Count distinct users for a movie
                    Movie.community_rating # Directly use the pre-calculated community_rating
                )
                .join(UserMovie, UserMovie.movie_id == Movie.id)
                .group_by(Movie.id, Movie.community_rating) # Group by all non-aggregated columns in select
                .order_by(desc('user_count'), desc(Movie.community_rating)) 
                .limit(limit)
                .all()
            )
            # Format results to match expected output structure if different (current matches interface)
            # For the interface: List[tuple[Movie, int, Optional[float]]]
            # The query above returns List[Row[Movie, int, Optional[float]]]
            # Which is compatible enough for iteration. If strict tuple list needed:
            # return [(movie, count, rating) for movie, count, rating in results]
            return results

        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching top movies: {e}.")
            # Error fetching top movies: {e}. / Fehler beim Abrufen der Top-Filme: {e}.
            return []

    def get_user_by_name(self, name: str) -> Optional[User]:
        """
        Retrieves a user by their name (case-insensitive).
        The input name is stripped and lowercased for comparison.

        Liefert einen Benutzer anhand seines Namens (Groß-/Kleinschreibung-unabhängig).
        Der eingegebene Name wird für den Vergleich bereinigt und in Kleinbuchstaben umgewandelt.
        """
        search_name = name.strip().lower()
        if not search_name:
            current_app.logger.debug("Attempted to fetch user with empty name.")
            return None
        try:
            return User.query.filter(func.lower(User.name) == search_name).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching user by name '{search_name}': {e}.")
            # Error fetching user by name '{search_name}': {e}. / Fehler beim Abrufen des Benutzers nach Name '{search_name}': {e}.
            return None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieves a user by their unique ID.
        Liefert einen Benutzer anhand seiner eindeutigen ID.
        """
        if not isinstance(user_id, int): # Basic type check
            current_app.logger.warning(f"Attempted to fetch user with non-integer ID: {user_id}.")
            return None
        try:
            return User.query.get(user_id)
        except SQLAlchemyError as e: # Should be rare for a simple get by PK
            current_app.logger.error(f"Error fetching user by ID {user_id}: {e}.")
            # Error fetching user by ID {user_id}: {e}. / Fehler beim Abrufen des Benutzers nach ID {user_id}: {e}.
            return None

    def get_user_movie_relations(self, user_id: int) -> List[UserMovie]:
        """
        Retrieves all UserMovie link objects for a specific user.
        These objects contain user-specific ratings. Default ordering by Movie ID.

        Liefert alle UserMovie-Verknüpfungsobjekte für einen bestimmten Benutzer.
        Diese Objekte enthalten benutzerspezifische Bewertungen. Standard-Sortierung nach Film-ID.
        """
        try:
            user = self.get_user_by_id(user_id) # Ensure user exists
            if not user:
                current_app.logger.warning(f"Cannot get UserMovie relations: User {user_id} not found.")
                return []

            relations = UserMovie.query.filter_by(user_id=user_id).join(Movie).order_by(Movie.id).all()
            return relations
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching UserMovie relations for user {user_id}: {e}.")
            # Error fetching UserMovie relations for user {user_id}: {e}. / Fehler beim Abrufen der Filmverknüpfungen für Benutzer {user_id}: {e}.
            return []

    def get_movie_by_id(self, movie_id: int) -> Optional[Movie]:
        """
        Retrieves a movie by its unique ID.
        Liefert einen Film anhand seiner eindeutigen ID.
        """
        if not isinstance(movie_id, int): # Basic type check
            current_app.logger.warning(f"Attempted to fetch movie with non-integer ID: {movie_id}.")
            return None
        try:
            return Movie.query.get(movie_id)
        except SQLAlchemyError as e: # Should be rare for a simple get by PK
            current_app.logger.error(f"Error fetching movie by ID {movie_id}: {e}.")
            # Error fetching movie by ID {movie_id}: {e}. / Fehler beim Abrufen des Films nach ID {movie_id}: {e}.
            return None

    def add_comment(self, movie_id: int, user_id: int, text: str) -> Optional[Comment]:
        """
        Adds a new comment to a movie by a specific user.
        Validates that the comment text is not empty and that the user and movie exist.

        Fügt einen neuen Kommentar zu einem Film von einem bestimmten Benutzer hinzu.
        Validiert, dass der Kommentartext nicht leer ist und dass Benutzer und Film existieren.
        """
        comment_text = text.strip()
        if not comment_text:
            current_app.logger.warning("Attempted to add an empty comment.")
            # Attempted to add an empty comment. / Versuch, einen leeren Kommentar hinzuzufügen.
            return None

        user = self.get_user_by_id(user_id)
        if not user:
            current_app.logger.warning(f"Add comment failed: User with ID {user_id} not found.")
            # User with ID {user_id} not found. / Benutzer mit ID {user_id} nicht gefunden.
            return None
        
        movie = self.get_movie_by_id(movie_id)
        if not movie:
            current_app.logger.warning(f"Add comment failed: Movie with ID {movie_id} not found.")
            # Movie with ID {movie_id} not found. / Film mit ID {movie_id} nicht gefunden.
            return None
            
        try:
            comment = Comment(movie_id=movie.id, user_id=user.id, text=comment_text)
            db.session.add(comment)
            db.session.commit()
            current_app.logger.info(f"Comment (ID: {comment.id}) added by user {user_id} to movie {movie_id} ('{movie.title}').")
            # Comment added by user {user_id} to movie {movie_id}. / Kommentar von Benutzer {user_id} zu Film {movie_id} hinzugefügt.
            return comment
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding comment by user {user_id} to movie {movie_id}: {e}.")
            # Error adding comment. / Fehler beim Hinzufügen des Kommentars.
            return None

    def get_all_movies(self) -> List[Movie]:
        """
        Retrieves a list of all movies from the database, ordered by title.
        Liefert eine Liste aller Filme aus der Datenbank, sortiert nach Titel.
        """
        try:
            return Movie.query.order_by(Movie.title).all()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching all movies: {e}.")
            # Error fetching all movies: {e}. / Fehler beim Abrufen aller Filme: {e}.
            return []

    def get_comments_for_movie(self, movie_id: int) -> List[Comment]:
        """
        Retrieves all comments for a specific movie, ordered by creation date (newest first).
        Ensures the movie exists before fetching comments.

        Liefert alle Kommentare für einen bestimmten Film, geordnet nach Erstellungsdatum (neueste zuerst).
        Stellt sicher, dass der Film existiert, bevor Kommentare abgerufen werden.
        """
        movie = self.get_movie_by_id(movie_id) 
        if not movie:
            current_app.logger.warning(f"Cannot get comments: Movie with ID {movie_id} not found.")
            # Movie with ID {movie_id} not found. / Film mit ID {movie_id} nicht gefunden.
            return []
        try:
            return Comment.query.filter_by(movie_id=movie_id).order_by(Comment.created_at.desc()).all()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching comments for movie {movie_id}: {e}.")
            # Error fetching comments for movie {movie_id}: {e}. / Fehler beim Abrufen der Kommentare für Film {movie_id}: {e}.
            return []

    def get_user_movie_link(self, user_id: int, movie_id: int) -> Optional[UserMovie]:
        """
        Retrieves the specific UserMovie link object between a user and a movie, if one exists.
        Verifies existence of both user and movie before querying the link.

        Liefert die spezifische UserMovie-Verknüpfung zwischen einem Benutzer und einem Film, falls eine existiert.
        Überprüft die Existenz von Benutzer und Film vor der Abfrage der Verknüpfung.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            current_app.logger.warning(f"Cannot get UserMovie link: User {user_id} not found.")
            return None
        movie = self.get_movie_by_id(movie_id)
        if not movie:
            current_app.logger.warning(f"Cannot get UserMovie link: Movie {movie_id} not found.")
            return None
        try:
            return UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching UserMovie link for user {user_id}, movie {movie_id}: {e}.")
            # Error fetching UserMovie link. / Fehler beim Abrufen der UserMovie-Verknüpfung.
            return None