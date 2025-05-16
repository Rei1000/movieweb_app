"""
data_manager_interface.py
Definiert das Interface für DataManager-Implementierungen.
Defines the interface for DataManager implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from models import User, Movie

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