"""
models.py
Dieses Modul enthält die SQLAlchemy-Modelle für die MovieWeb-Anwendung.
This module contains the SQLAlchemy models for the MovieWeb application.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Globale SQLAlchemy-Instanz (wird in app.py initialisiert)
db = SQLAlchemy()

class User(db.Model):
    """
    User
    Repräsentiert einen Benutzer der Anwendung.
    Represents a user of the application.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Relationships / Beziehungen
    movies = db.relationship('UserMovie', back_populates='user', cascade="all, delete-orphan") # User's movie list / Filmliste des Benutzers
    comments = db.relationship('Comment', back_populates='user', cascade="all, delete-orphan") # Comments made by the user / Vom Benutzer erstellte Kommentare

    def __repr__(self):
        return f"<User id={self.id} name={self.name}>"

class Movie(db.Model):
    """
    Movie
    Repräsentiert einen Film in der Datenbank.
    Represents a movie in the database.
    """
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    original_title = db.Column(db.String(255), nullable=True)
    director = db.Column(db.String(255), nullable=True)
    writer = db.Column(db.Text, nullable=True)
    actors = db.Column(db.Text, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    runtime = db.Column(db.String(50), nullable=True)
    genre = db.Column(db.String(255), nullable=True)
    plot = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(255), nullable=True)
    country = db.Column(db.String(255), nullable=True)
    awards = db.Column(db.Text, nullable=True)
    poster_url = db.Column(db.String(255), nullable=True)
    community_rating = db.Column(db.Float, nullable=True) # Average community rating / Durchschnittliches Community-Rating
    community_rating_count = db.Column(db.Integer, default=0) # Number of ratings for the average / Anzahl der Bewertungen für den Durchschnitt
    imdb_rating = db.Column(db.String(10), nullable=True)
    imdb_votes = db.Column(db.String(50), nullable=True)
    imdb_id = db.Column(db.String(20), nullable=True, unique=True) # IMDb ID für eindeutige Identifizierung
    metascore = db.Column(db.String(10), nullable=True)
    rated_omdb = db.Column(db.String(20), nullable=True) # MPAA rating from OMDb / MPAA-Bewertung von OMDb
    initial_omdb_rating = db.Column(db.Float, nullable=True) # Initiales, von OMDb übernommenes 5-Sterne-Rating

    # Relationships / Beziehungen
    users = db.relationship('UserMovie', back_populates='movie', cascade="all, delete-orphan") # Users who have this movie in their list / Benutzer, die diesen Film in ihrer Liste haben
    comments = db.relationship('Comment', back_populates='movie', cascade="all, delete-orphan") # Comments associated with this movie / Mit diesem Film verbundene Kommentare

    def __repr__(self):
        return f"<Movie id={self.id} title={self.title}>"

class UserMovie(db.Model):
    """
    UserMovie
    Verbindet Benutzer und Filme (n:m-Beziehung).
    Connects users and movies (many-to-many relationship).
    """
    __tablename__ = 'user_movies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    user_rating = db.Column(db.Float, nullable=True) # Individual user rating for this movie / Individuelle Benutzerbewertung für diesen Film

    # Relationships / Beziehungen
    user = db.relationship('User', back_populates='movies') # The user who owns this entry / Der Benutzer, dem dieser Eintrag gehört
    movie = db.relationship('Movie', back_populates='users') # The movie being referenced / Der referenzierte Film

    def __repr__(self):
        return f"<UserMovie user_id={self.user_id} movie_id={self.movie_id}>"

class Comment(db.Model):
    """
    Comment
    Repräsentiert einen Kommentar zu einem Film.
    Represents a comment on a movie.
    """
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes_count = db.Column(db.Integer, default=0, nullable=False) # New field for likes (future feature) / Neues Feld für Likes (zukünftiges Feature)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    
    # Relationships / Beziehungen
    user = db.relationship('User', back_populates='comments') # The user who wrote the comment / Der Benutzer, der den Kommentar geschrieben hat
    movie = db.relationship('Movie', back_populates='comments') # The movie being commented on / Der kommentierte Film

    def __repr__(self):
        return f"<Comment id={self.id} user_id={self.user_id} movie_id={self.movie_id}>"
