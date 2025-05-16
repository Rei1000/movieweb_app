"""
sqlite_data_manager.py
Dieses Modul implementiert die DataManagerInterface mit SQLite/SQLAlchemy.
This module implements the DataManagerInterface using SQLite/SQLAlchemy.
"""

from typing import List, Optional
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from datamanager.data_manager_interface import DataManagerInterface
from models import db, User, Movie, UserMovie
from datetime import datetime  # For year validation

class SQLiteDataManager(DataManagerInterface):
    """
    SQLiteDataManager
    Konkrete Umsetzung des DataManagerInterface für SQLite über SQLAlchemy.
    Concrete implementation of DataManagerInterface for SQLite using SQLAlchemy.
    """

    def get_all_users(self) -> List[User]:
        """
        Liefert alle Benutzer.
        Returns all users.
        """
        try:
            return User.query.all()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching users: {e}")
            return []

    def get_user_movies(self, user_id: int) -> List[Movie]:
        """
        Liefert alle Filme eines Benutzers.
        Returns all movies for a given user.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return []
            # über UserMovie-Beziehung die Filme holen
            return [um.movie for um in user.movies]
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movies for user {user_id}: {e}")
            return []

    def add_user(self, name: str) -> Optional[User]:
        """
        Fügt einen neuen Benutzer hinzu.
        Adds a new user.
        """
        # Defensive input: strip whitespace and normalize to lowercase / Eingabe trimmen und in Kleinschreibung
        name = name.strip().lower()
        if not name:
            current_app.logger.warning("Attempted to add user with empty name.")
            return None
        # Duplicate check (case-insensitive) / Prüfe auf bestehenden Benutzernamen
        from sqlalchemy import func
        if User.query.filter(func.lower(User.name) == name).first():
            current_app.logger.warning(f"Attempted to add duplicate user '{name}'.")
            return None
        try:
            user = User(name=name.strip())
            db.session.add(user)
            db.session.commit()
            return user
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding user '{name}': {e}")
            return None

    def add_movie(self, user_id: int, title: str, director: str, year: int, rating: float, poster_url: str = None,
                  plot: str = None, runtime: str = None, awards: str = None, languages: str = None,
                  genre: str = None, actors: str = None, writer: str = None, country: str = None,
                  metascore: str = None, rated: str = None, imdb_id: str = None,
                  omdb_rating_for_community: Optional[float] = None) -> Optional[Movie]:
        """
        Fügt einen neuen Film für einen Benutzer hinzu.
        Adds a new movie for a user.
        """
        # Defensive input stripping
        title = title.strip()
        director = director.strip() if director else None

        # Validate year (if provided) not in the future
        current_year = datetime.now().year
        if year is not None and year > current_year:
            current_app.logger.warning(f"Attempted to add movie with future year: {year}")
            return None

        # Validate rating (if provided) between 0 and 5
        if rating is not None and not (0 <= rating <= 5):
            current_app.logger.warning(f"Attempted to add movie with invalid rating: {rating}")
            return None

        if not title:
            current_app.logger.warning("Attempted to add movie with empty title.")
            return None
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.warning(f"User {user_id} not found.")
                return None

            # Prüfen, ob ein Film mit dieser imdb_id bereits existiert
            movie = None
            if imdb_id:
                movie = Movie.query.filter_by(imdb_id=imdb_id).first()

            if movie: # Film existiert bereits global
                current_app.logger.info(f"Movie with imdb_id {imdb_id} already exists. Linking to user {user_id}.")
                # Optional: Hier könnte man das existierende Movie-Objekt mit den neuen Daten aktualisieren, falls gewünscht.
                # Das community_rating wird später durch _update_community_rating neu berechnet.
            else: # Film existiert global noch nicht, neu erstellen
                current_app.logger.info(f"Movie with imdb_id {imdb_id} not found. Creating new entry.")
                
                initial_community_rating = None
                initial_community_rating_count = 0
                if omdb_rating_for_community is not None and 0 <= omdb_rating_for_community <= 5:
                    initial_community_rating = omdb_rating_for_community
                    initial_community_rating_count = 1 # Zählt als eine initiale "Bewertung"
                    current_app.logger.info(f"Using OMDb rating {omdb_rating_for_community} as initial community rating for movie {imdb_id}.")

                movie = Movie(
                    title=title,
                    director=director,
                    year=year,
                    community_rating=initial_community_rating, # Initiales Community-Rating setzen
                    community_rating_count=initial_community_rating_count,
                    poster_url=poster_url,
                    plot=plot,
                    runtime=runtime,
                    awards=awards,
                    language=languages, # Wurde in models.py zu language geändert
                    genre=genre,
                    actors=actors,
                    writer=writer,
                    country=country,
                    metascore=metascore,
                    rated_omdb=rated, # Wurde in models.py zu rated_omdb geändert
                    imdb_id=imdb_id
                )
                db.session.add(movie)
                db.session.flush() # movie.id verfügbar machen für UserMovie

            # Prüfen, ob die UserMovie-Verknüpfung bereits existiert
            user_movie_link = UserMovie.query.filter_by(user_id=user.id, movie_id=movie.id).first()
            if not user_movie_link:
                um = UserMovie(user_id=user.id, movie_id=movie.id, user_rating=rating) # user_rating hier setzen
                db.session.add(um)
                current_app.logger.info(f"New UserMovie link for user {user.id}, movie {movie.id} with user_rating {rating}")
            else:
                current_app.logger.info(f"Movie {movie.id} already linked to user {user.id}.")
                # Wenn bereits verlinkt, das übergebene Rating als user_rating für diese Verknüpfung setzen/aktualisieren
                if rating is not None and user_movie_link.user_rating != rating:
                    user_movie_link.user_rating = rating
                    current_app.logger.info(f"Updating user_rating for existing link user {user.id}, movie {movie.id} to {rating}")
                elif rating is None and user_movie_link.user_rating is not None: # Fall: User will Rating explizit löschen
                    user_movie_link.user_rating = None
                    current_app.logger.info(f"Removing user_rating for existing link user {user.id}, movie {movie.id}")

            db.session.commit() # Änderungen an UserMovie und ggf. neuem Movie speichern
            self._update_community_rating(movie.id) # Community-Rating basierend auf allen UserMovie-Einträgen aktualisieren
            return movie
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding movie '{title}' for user {user_id}: {e}")
            return None

    def update_user_rating_for_movie(self, user_id: int, movie_id: int, new_rating: Optional[float]) -> bool:
        """
        Aktualisiert das individuelle Rating eines Benutzers für einen Film.
        Berechnet danach das Community-Rating des Films neu.
        new_rating kann None sein, um ein existierendes Rating zu entfernen.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                current_app.logger.warning(f"No link found for user {user_id} and movie {movie_id} to update rating.")
                # Optional: Wenn der Film global existiert, aber der User ihn noch nicht in der Liste hat,
                # könnte man hier die Verknüpfung erstellen und das Rating setzen.
                # Fürs Erste: Nur Fehler, wenn keine Verknüpfung da ist.
                return False
            
            if new_rating is not None and not (0 <= new_rating <= 5):
                current_app.logger.warning(f"Attempted to update with invalid rating: {new_rating}")
                return False

            user_movie_link.user_rating = new_rating
            db.session.commit()
            current_app.logger.info(f"User rating for user {user_id}, movie {movie_id} updated to {new_rating}.")
            
            # Community-Rating des Films aktualisieren
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating user rating for user {user_id}, movie {movie_id}: {e}")
            return False

    def delete_movie(self, movie_id: int) -> bool:
        """
        Löscht einen Film anhand seiner ID.
        WICHTIG: Muss auch das Community-Rating aktualisieren, falls der gelöschte Film User-Ratings hatte.
        Dies ist komplexer, da UserMovie-Einträge kaskadierend gelöscht werden.
        Eine einfachere Lösung ist, dass delete_movie nur die Movie-Verknüpfung eines Users löscht,
        nicht den globalen Movie-Eintrag, es sei denn, kein User hat ihn mehr.
        Fürs Erste belassen wir die alte delete_movie Logik (löscht global) und akzeptieren, dass
        Community Ratings nicht neu berechnet werden, wenn ein Film global gelöscht wird.
        BESSER: delete_movie_from_user_list(user_id, movie_id)
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie {movie_id} not found.")
                return False
            db.session.delete(movie)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting movie {movie_id}: {e}")
            return False

    def add_existing_movie_to_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Fügt einen bereits existierenden Film zur Liste eines Benutzers hinzu (UserMovie-Verknüpfung).
        Das Rating des Films selbst wird hierbei nicht verändert, nur die Verknüpfung hergestellt.
        """
        try:
            user = User.query.get(user_id)
            if not user:
                current_app.logger.warning(f"User {user_id} not found for adding movie to list.")
                return False
            
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie {movie_id} not found for adding to user list.")
                return False

            # Prüfen, ob die Verknüpfung bereits existiert
            existing_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()
            if existing_link:
                current_app.logger.info(f"Movie {movie_id} is already in list of user {user_id}.")
                return True # Bereits vorhanden, als Erfolg werten

            # Neue UserMovie-Verknüpfung erstellen
            user_movie_link = UserMovie(user_id=user.id, movie_id=movie.id, user_rating=None) # user_rating initial None
            db.session.add(user_movie_link)
            db.session.commit()
            current_app.logger.info(f"Added movie {movie_id} to list of user {user_id} (no initial rating).")
            self._update_community_rating(movie_id) # Community-Rating aktualisieren
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding movie {movie_id} to list for user {user_id}: {e}")
            return False

    def _update_community_rating(self, movie_id: int) -> bool:
        """
        Private Hilfsmethode, um das Community-Rating eines Films neu zu berechnen.
        Wird aufgerufen, nachdem ein User-Rating hinzugefügt oder geändert wurde.
        """
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                current_app.logger.warning(f"Movie {movie_id} not found for updating community rating.")
                return False

            # Alle gültigen User-Ratings für diesen Film holen
            user_ratings = db.session.query(UserMovie.user_rating).filter(
                UserMovie.movie_id == movie_id,
                UserMovie.user_rating.isnot(None)
            ).all()

            ratings_list = [r[0] for r in user_ratings]

            if ratings_list:
                movie.community_rating = sum(ratings_list) / len(ratings_list)
                movie.community_rating_count = len(ratings_list)
            else:
                movie.community_rating = None
                movie.community_rating_count = 0
            
            db.session.commit()
            current_app.logger.info(f"Community rating for movie {movie_id} updated: {movie.community_rating} ({movie.community_rating_count} ratings)")
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating community rating for movie {movie_id}: {e}")
            return False

    def delete_movie_from_user_list(self, user_id: int, movie_id: int) -> bool:
        """
        Entfernt einen Film aus der Liste eines bestimmten Benutzers (löscht die UserMovie-Verknüpfung).
        Aktualisiert danach das Community-Rating des Films.
        Gibt True zurück bei Erfolg, sonst False.
        """
        try:
            user_movie_link = UserMovie.query.filter_by(user_id=user_id, movie_id=movie_id).first()

            if not user_movie_link:
                current_app.logger.warning(f"No link found for user {user_id} and movie {movie_id} to delete.")
                return False # Film war nicht in der Liste des Users

            db.session.delete(user_movie_link)
            db.session.commit()
            current_app.logger.info(f"Movie {movie_id} removed from list of user {user_id}.")
            
            # Community-Rating des Films aktualisieren, da ein Rating entfernt wurde
            # (auch wenn das user_rating None war, könnte es theoretisch das letzte sein, was die Berechnung beeinflusst)
            return self._update_community_rating(movie_id)
            
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing movie {movie_id} from list for user {user_id}: {e}")
            return False

    def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[Movie]:
        """
        Sucht einen Film anhand seiner IMDb-ID.
        Returns a movie by its IMDb ID.
        """
        try:
            return Movie.query.filter_by(imdb_id=imdb_id).first()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Error fetching movie by imdb_id {imdb_id}: {e}")
            return None

    def add_movie_globally(self, movie_data: dict) -> Optional[Movie]:
        """
        Fügt einen Film global zur Datenbank hinzu, wenn er nicht bereits existiert.
        Wenn ein OMDb-Rating vorhanden ist, wird dieses als initiales Community-Rating verwendet.
        Aktualisiert keine bestehenden Filmdaten, wenn der Film bereits existiert.
        Nimmt ein Dictionary mit Filmdetails entgegen (ähnlich OMDb-Antwort).
        Gibt das Movie-Objekt zurück (entweder das neu erstellte oder das bereits existierende).
        """
        imdb_id = movie_data.get('imdbID')
        if not imdb_id:
            current_app.logger.warning("Attempted to add global movie without imdbID.")
            return None

        try:
            existing_movie = Movie.query.filter_by(imdb_id=imdb_id).first()
            if existing_movie:
                current_app.logger.info(f"Movie with imdb_id {imdb_id} already exists globally. Returning existing.")
                return existing_movie
            
            # Konvertiere das Jahr sicher. OMDb 'Year' kann 'YYYY' oder 'YYYY–YYYY' (TV Series) sein.
            year_str = movie_data.get('Year', '').strip()
            year = None
            if year_str:
                try:
                    # Nimm nur das erste Jahr, falls es ein Bereich ist
                    year = int(year_str.split('–')[0].split('-')[0].strip())
                except ValueError:
                    current_app.logger.warning(f"Invalid year format for global movie {imdb_id}: {year_str}")
                    # Optional: Film trotzdem ohne Jahr hinzufügen oder Fehler
                    # For now, proceed without year if format is unexpected beyond simple parsing

            # Poster URL Handling
            poster_url = movie_data.get('Poster')
            if poster_url == 'N/A':
                poster_url = None

            # OMDb-Rating für initiales Community-Rating verarbeiten
            initial_community_rating_val = None
            initial_community_rating_count_val = 0
            raw_omdb_rating = movie_data.get('imdbRating')
            if raw_omdb_rating and raw_omdb_rating != 'N/A':
                try:
                    rating10 = float(raw_omdb_rating)
                    rating5 = round(rating10 / 2 * 2) / 2 # Umrechnung auf 0-5 Skala, halbe Schritte
                    if 0 <= rating5 <= 5:
                        initial_community_rating_val = rating5
                        initial_community_rating_count_val = 1
                        current_app.logger.info(f"Using OMDb rating {rating5} ({raw_omdb_rating}/10) as initial community rating for global movie {imdb_id}.")
                except ValueError:
                    current_app.logger.warning(f"Invalid imdbRating format for global movie {imdb_id}: {raw_omdb_rating}")

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
                community_rating=initial_community_rating_val, # Hier setzen
                community_rating_count=initial_community_rating_count_val # Hier setzen
            )
            db.session.add(new_movie)
            db.session.commit()
            current_app.logger.info(f"Movie with imdb_id {imdb_id} added globally with id {new_movie.id}.")
            return new_movie
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding global movie with imdb_id {imdb_id}: {e}")
            return None
        except Exception as e: # Catch other potential errors like int conversion
            db.session.rollback()
            current_app.logger.error(f"Unexpected error adding global movie with imdb_id {imdb_id}: {e}")
            return None