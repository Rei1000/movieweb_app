"""
data_manager_interface.py
Definiert das Interface für DataManager-Implementierungen.
Defines the interface for DataManager implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from models import User, Movie, Comment, UserMovie

class DataManagerInterface(ABC):
    """
    DataManagerInterface
    Abstraktes Interface für Datenzugriffsoperationen.
    Abstract interface for data access operations.
    """

    @abstractmethod
    def get_all_users(self) -> List[User]:
        """
        Liefert alle Benutzer.
        Returns all users.
        """
        pass

    @abstractmethod
    def get_user_movies(self, user_id: int) -> List[Movie]:
        """
        Liefert alle Filme eines bestimmten Benutzers.
        Returns all movies for a given user.
        """
        pass

    @abstractmethod
    def add_user(self, name: str) -> Optional[User]:
        """
        Fügt einen neuen Benutzer hinzu.
        Adds a new user.
        """
        pass

    @abstractmethod
    def add_movie(self, user_id: int, title: str, director: str, year: int, rating: float, poster_url: str = None) -> Optional[Movie]:
        """
        Fügt einen neuen Film für einen Benutzer hinzu.
        Adds a new movie for a user.
        """
        pass

    @abstractmethod
    def update_user_rating_for_movie(self, user_id: int, movie_id: int, new_rating: Optional[float]) -> bool:
        """
        Aktualisiert das individuelle Rating eines Benutzers für einen Film.
        Updates a user's individual rating for a movie.
        new_rating kann None sein, um ein existierendes Rating zu entfernen.
        """
        pass

    @abstractmethod
    def delete_movie(self, movie_id: int) -> bool:
        """
        Löscht einen Film anhand seiner ID.
        Deletes a movie by its ID.
        """
        pass

    @abstractmethod
    def get_top_movies(self, limit: int = 10) -> List[tuple[Movie, int, Optional[float]]]:
        """
        Liefert die Top-Filme basierend auf Nutzerzahl und durchschnittlichem Community-Rating.
        Gibt eine Liste von Tupeln zurück: (Movie-Objekt, Anzahl der Nutzer, Durchschnitts-Rating).

        Returns the top movies based on user count and average community rating.
        Returns a list of tuples: (Movie object, user count, average rating).
        """
        pass

    @abstractmethod
    def get_user_by_name(self, name: str) -> Optional[User]:
        """
        Liefert einen Benutzer anhand seines Namens (case-insensitive).
        Returns a user by their name (case-insensitive).
        """
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Liefert einen Benutzer anhand seiner ID.
        Returns a user by their ID.
        """
        pass

    @abstractmethod
    def get_user_movie_relations(self, user_id: int) -> List[UserMovie]:
        """
        Liefert alle UserMovie-Objekte (Verknüpfungen) für einen bestimmten Benutzer.
        Returns all UserMovie objects (relations) for a given user.
        """
        pass

    @abstractmethod
    def get_movie_by_id(self, movie_id: int) -> Optional[Movie]:
        """
        Liefert einen Film anhand seiner ID.
        Returns a movie by its ID.
        """
        pass

    @abstractmethod
    def add_comment(self, movie_id: int, user_id: int, text: str) -> Optional[Comment]:
        """
        Fügt einen neuen Kommentar zu einem Film hinzu.
        Adds a new comment to a movie.
        """
        pass

    @abstractmethod
    def get_all_movies(self) -> List[Movie]:
        """
        Liefert eine Liste aller Filme in der Datenbank.
        Returns a list of all movies in the database.
        """
        pass

    @abstractmethod
    def get_comments_for_movie(self, movie_id: int) -> List[Comment]:
        """
        Liefert alle Kommentare für einen bestimmten Film, geordnet nach Erstellungsdatum (neueste zuerst).
        Returns all comments for a specific movie, ordered by creation date (newest first).
        """
        pass