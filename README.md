# MovieWeb App

MovieWeb is a Flask-based web application that allows users to manage their movie lists, discover new movies, get AI-powered recommendations, and interact with a community of movie enthusiasts.

*MovieWeb ist eine Flask-basierte Webanwendung, die es Benutzern ermöglicht, ihre Filmlisten zu verwalten, neue Filme zu entdecken, KI-gestützte Empfehlungen zu erhalten und mit einer Community von Filmbegeisterten zu interagieren.*

## Features / Funktionen

*   **User Authentication:** Simple username-based registration and login.
    *   *Benutzerauthentifizierung: Einfache benutzernamebasierte Registrierung und Anmeldung.*
*   **Movie Management:** Add movies to personal lists, rate them, and remove them.
    *   *Filmverwaltung: Filme zu persönlichen Listen hinzufügen, bewerten und entfernen.*
*   **AI-Powered Movie Search:** Find movies by title (even partial/misspelled) or by describing the plot.
    *   *KI-gestützte Filmsuche: Filme nach Titel (auch unvollständig/falsch geschrieben) oder durch Beschreibung der Handlung finden.*
*   **AI Recommendations:** Get personalized movie recommendations based on a selected movie. The AI remembers recent recommendations to avoid duplicates.
    *   *KI-Empfehlungen: Personalisierte Filmempfehlungen basierend auf einem ausgewählten Film erhalten. Die KI merkt sich kürzliche Empfehlungen, um Duplikate zu vermeiden.*
*   **Community Interaction:** View community ratings and add comments to movies.
    *   *Community-Interaktion: Community-Bewertungen einsehen und Kommentare zu Filmen hinzufügen.*
*   **Movie Details:** Access comprehensive movie information via OMDb API integration (plot, director, year, cast, poster, etc.).
    *   *Filmdetails: Zugriff auf umfassende Filminformationen über OMDb-API-Integration (Handlung, Regisseur, Jahr, Besetzung, Poster usw.).*
*   **REST API:** Programmatic access to user and movie data.
    *   *REST-API: Programmatischer Zugriff auf Benutzer- und Filmdaten.*
*   **Bilingual Interface:** User interface and messages are available in English and German.
    *   *Zweisprachige Benutzeroberfläche: Benutzeroberfläche und Nachrichten sind auf Englisch und Deutsch verfügbar.*

## Technology Stack / Technologie-Stack

*   **Backend:** Python, Flask
*   **Database:** SQLite (with SQLAlchemy ORM)
*   **Frontend:** HTML, CSS, JavaScript (vanilla)
*   **APIs:**
    *   OMDb API (for movie data)
    *   OpenRouter API (for AI-powered title interpretation and recommendations, using models like GPT-3.5-Turbo)
*   **Libraries:**
    *   `requests` (for HTTP requests to external APIs)
    *   `python-dotenv` (for managing environment variables)
    *   `Flask-SQLAlchemy` (ORM)
    *   `Flask-WTF` (for CSRF protection)

## Project Structure / Projektstruktur

```
/movieweb_app
│
├── app.py                      # Main Flask application: routing, core logic, AI integration.
│                               # *Haupt-Flask-Anwendung: Routing, Kernlogik, KI-Integration.*
│
├── models.py                   # SQLAlchemy database models (User, Movie, UserMovie, Comment).
│                               # *SQLAlchemy-Datenbankmodelle (User, Movie, UserMovie, Comment).*
│
├── init_db.py                  # Script to initialize the database schema.
│                               # *Skript zur Initialisierung des Datenbank-Schemas.*
│
├── datamanager/
│   └── sqlite_data_manager.py  # Data access layer; handles all database interactions.
│                               # *Datenzugriffsschicht; behandelt alle Datenbankinteraktionen.*
│
├── api/
│   └── routes.py               # Defines API endpoints for programmatic access.
│                               # *Definiert API-Endpunkte für programmatischen Zugriff.*
│
├── templates/                  # HTML templates for the user interface.
│   │                           # *HTML-Vorlagen für die Benutzeroberfläche.*
│   ├── base.html               # Base layout template. / *Basis-Layout-Vorlage.*
│   ├── home.html               # Homepage with login/register and top movies. / *Startseite mit Login/     Registrierung und Top-Filmen.*
│   ├── movies.html             # User's movie list page. / *Filmliste eines Benutzers.*
│   ├── add_movie.html          # Page for adding a new movie (multi-stage AI search and OMDb fetch).
│   │                           # *Seite zum Hinzufügen eines neuen Films (mehrstufige KI-Suche und OMDb-Abruf).*
│   ├── movie_detail_page.html  # Detailed view of a single movie with comments and actions.
│   │                           # *Detailansicht eines einzelnen Films mit Kommentaren und Aktionen.*
│   ├── update_movie_rating.html # Page for a user to update their rating for a movie.
│   │                           # *Seite für einen Benutzer, um seine Bewertung für einen Film zu aktualisieren.*
│   ├── _macros.html            # Reusable template macros (e.g., movie card). / *Wiederverwendbare Template-Makros (z.B. Filmkarte).*
│   ├── users.html              # List of all users (admin/overview). / *Liste aller Benutzer (Admin/Übersicht).*
│   ├── add_user.html           # Page to add a new user (admin/testing). / *Seite zum Hinzufügen eines neuen Benutzers (Admin/Test).*
│   ├── api_docs.html           # API documentation page. / *API-Dokumentationsseite.*
│   ├── about.html              # About page with application information. / *Info-Seite mit Anwendungsinformationen.*
│   ├── recommendations.html    # (Currently simple) Page to display AI recommendations. / *(Derzeit einfach) Seite zur Anzeige von KI-Empfehlungen.*
│   ├── 404.html                # Custom 404 error page. / *Benutzerdefinierte 404-Fehlerseite.*
│   └── 500.html                # Custom 500 error page. / *Benutzerdefinierte 500-Fehlerseite.*
│
├── static/                     # Static files (CSS, JavaScript, images).
│   │                           # *Statische Dateien (CSS, JavaScript, Bilder).*
│   ├── css/style.css           # Main stylesheet. / *Haupt-Stylesheet.*
│   ├── js/main.js              # Main JavaScript file (includes CSRF setup for AJAX).
│   │                           # *Haupt-JavaScript-Datei (beinhaltet CSRF-Setup für AJAX).*
│   └── img/no_poster.png       # Placeholder image for movies without a poster.
│                               # *Platzhalterbild für Filme ohne Poster.*
│
├── .env                        # Environment variables (API keys, database URI, secret key). **Not in Git.**
│                               # *Umgebungsvariablen (API-Schlüssel, Datenbank-URI, Secret Key). **Nicht in Git.**
│
├── requirements.txt            # Python package dependencies. / *Python-Paketabhängigkeiten.*
│
└── README.md                   # This file. / *Diese Datei.*
```

## Database Models / Datenbankmodelle

The application uses SQLAlchemy to define and interact with the database. The models are defined in `models.py`.

*Die Anwendung verwendet SQLAlchemy zur Definition und Interaktion mit der Datenbank. Die Modelle sind in `models.py` definiert.*

### 1. `User`

Represents a user of the application.
*Repräsentiert einen Benutzer der Anwendung.*

*   **Attributes / Attribute:**
    *   `id` (Integer, Primary Key): Unique identifier for the user. / *Eindeutiger Identifikator für den Benutzer.*
    *   `name` (String, Not Nullable, Unique): The username. / *Der Benutzername.*
*   **Relationships / Beziehungen:**
    *   `movies` (One-to-Many with `UserMovie`): The movies associated with the user, including their ratings. / *Die mit dem Benutzer verbundenen Filme, einschließlich ihrer Bewertungen.*
    *   `comments` (One-to-Many with `Comment`): Comments made by the user. / *Vom Benutzer erstellte Kommentare.*

### 2. `Movie`

Represents a movie in the database.
*Repräsentiert einen Film in der Datenbank.*

*   **Attributes / Attribute:**
    *   `id` (Integer, Primary Key): Unique identifier for the movie. / *Eindeutiger Identifikator für den Film.*
    *   `title` (String, Not Nullable): The main title of the movie. / *Der Haupttitel des Films.*
    *   `original_title` (String, Nullable): The original title, if different. / *Der Originaltitel, falls abweichend.*
    *   `director` (String, Nullable): Director(s) of the movie. / *Regisseur(e) des Films.*
    *   `writer` (Text, Nullable): Writer(s) of the movie. / *Drehbuchautor(en) des Films.*
    *   `actors` (Text, Nullable): Main actors. / *Hauptdarsteller.*
    *   `year` (Integer, Nullable): Release year. / *Erscheinungsjahr.*
    *   `runtime` (String, Nullable): Movie runtime (e.g., "120 min"). / *Filmlaufzeit (z.B. "120 min").*
    *   `genre` (String, Nullable): Genre(s) of the movie. / *Genre(s) des Films.*
    *   `plot` (Text, Nullable): A brief plot summary. / *Kurze Handlungszusammenfassung.*
    *   `language` (String, Nullable): Language(s) of the movie. / *Sprache(n) des Films.*
    *   `country` (String, Nullable): Country/Countries of origin. / *Herkunftsland/-länder.*
    *   `awards` (Text, Nullable): Awards won by the movie. / *Vom Film gewonnene Auszeichnungen.*
    *   `poster_url` (String, Nullable): URL to the movie poster image. / *URL zum Filmposterbild.*
    *   `community_rating` (Float, Nullable): Average community rating (0-5). / *Durchschnittliche Community-Bewertung (0-5).*
    *   `community_rating_count` (Integer, Default: 0): Number of community ratings. / *Anzahl der Community-Bewertungen.*
    *   `imdb_rating` (String, Nullable): IMDb rating score (e.g., "7.5/10"). / *IMDb-Bewertung (z.B. "7.5/10").*
    *   `imdb_votes` (String, Nullable): Number of IMDb votes. / *Anzahl der IMDb-Stimmen.*
    *   `imdb_id` (String, Nullable, Unique): IMDb unique identifier (e.g., "tt0111161"). / *Eindeutiger IMDb-Identifikator (z.B. "tt0111161").*
    *   `metascore` (String, Nullable): Metacritic score. / *Metacritic-Bewertung.*
    *   `rated_omdb` (String, Nullable): MPAA-style age rating from OMDb. / *MPAA-Stil Altersfreigabe von OMDb.*
*   **Relationships / Beziehungen:**
    *   `users` (One-to-Many with `UserMovie`): Users who have this movie in their list. / *Benutzer, die diesen Film in ihrer Liste haben.*
    *   `comments` (One-to-Many with `Comment`): Comments associated with this movie. / *Mit diesem Film verbundene Kommentare.*

### 3. `UserMovie`

Association table connecting users and movies, representing a movie in a user's personal list and their specific rating for it.
*Verbindungstabelle, die Benutzer und Filme verbindet und einen Film in der persönlichen Liste eines Benutzers sowie dessen spezifische Bewertung dafür darstellt.*

*   **Attributes / Attribute:**
    *   `id` (Integer, Primary Key): Unique identifier for the association. / *Eindeutiger Identifikator für die Verknüpfung.*
    *   `user_id` (Integer, Foreign Key to `users.id`, Not Nullable): ID of the user. / *ID des Benutzers.*
    *   `movie_id` (Integer, Foreign Key to `movies.id`, Not Nullable): ID of the movie. / *ID des Films.*
    *   `user_rating` (Float, Nullable): The user's personal rating for this movie (0-5). / *Die persönliche Bewertung des Benutzers für diesen Film (0-5).*
*   **Relationships / Beziehungen:**
    *   `user` (Many-to-One with `User`): The user who owns this movie entry. / *Der Benutzer, dem dieser Filmeintrag gehört.*
    *   `movie` (Many-to-One with `Movie`): The movie being referenced. / *Der referenzierte Film.*

### 4. `Comment`

Represents a comment made by a user on a movie.
*Repräsentiert einen Kommentar, den ein Benutzer zu einem Film abgegeben hat.*

*   **Attributes / Attribute:**
    *   `id` (Integer, Primary Key): Unique identifier for the comment. / *Eindeutiger Identifikator für den Kommentar.*
    *   `text` (Text, Not Nullable): The content of the comment. / *Der Inhalt des Kommentars.*
    *   `created_at` (DateTime, Default: current UTC time): Timestamp of when the comment was created. / *Zeitstempel, wann der Kommentar erstellt wurde.*
    *   `likes_count` (Integer, Default: 0, Not Nullable): Number of likes for the comment (future feature). / *Anzahl der Likes für den Kommentar (zukünftiges Feature).*
    *   `user_id` (Integer, Foreign Key to `users.id`, Not Nullable): ID of the user who wrote the comment. / *ID des Benutzers, der den Kommentar geschrieben hat.*
    *   `movie_id` (Integer, Foreign Key to `movies.id`, Not Nullable): ID of the movie the comment is for. / *ID des Films, für den der Kommentar ist.*
*   **Relationships / Beziehungen:**
    *   `user` (Many-to-One with `User`): The author of the comment. / *Der Autor des Kommentars.*
    *   `movie` (Many-to-One with `Movie`): The movie being commented on. / *Der kommentierte Film.*

## Setup and Installation / Einrichtung und Installation

1.  **Clone the Repository / Klonen des Repositories:**
    ```bash
    git clone <repository_url>
    cd movieweb_app
    ```

2.  **Create and Activate a Virtual Environment / Virtuelle Umgebung erstellen und aktivieren:**
    ```bash
    python -m venv venv
    # On Windows / Unter Windows:
    # venv\Scripts\activate
    # On macOS/Linux / Unter macOS/Linux:
    # source venv/bin/activate
    ```

3.  **Install Dependencies / Abhängigkeiten installieren:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables / Umgebungsvariablen konfigurieren:**
    Create a `.env` file in the root directory (`/movieweb_app`) and add the following variables. Obtain API keys from their respective services.
    *Erstellen Sie eine `.env`-Datei im Stammverzeichnis (`/movieweb_app`) und fügen Sie die folgenden Variablen hinzu. Beziehen Sie API-Schlüssel von den entsprechenden Diensten.*

    ```env
    OMDB_API_KEY='YOUR_OMDB_API_KEY'
    OPENROUTER_API_KEY='YOUR_OPENROUTER_API_KEY' # For AI features / Für KI-Funktionen
    DATABASE_URI='sqlite:///moviewebapp.db'     # Or your preferred database URI / Oder Ihre bevorzugte Datenbank-URI
    SECRET_KEY='a_very_strong_and_random_secret_key' # For Flask session management & CSRF / Für Flask Session-Management & CSRF
    ```

5.  **Initialize the Database / Datenbank initialisieren:**
    Run the `init_db.py` script to create the database tables.
    *Führen Sie das Skript `init_db.py` aus, um die Datenbanktabellen zu erstellen.*
    ```bash
    python init_db.py
    ```

6.  **Run the Application / Anwendung starten:**
    ```bash
    flask run
    # Or / Oder:
    # python app.py
    ```
    The application should now be running on `http://127.0.0.1:5000/`.
    *Die Anwendung sollte nun unter `http://127.0.0.1:5000/` laufen.*

## API Endpoints / API-Endpunkte

The application provides a RESTful API for programmatic access to its data. For detailed documentation on the available endpoints, request/response formats, and usage examples, please visit the `/api/docs` page when the application is running.

*Die Anwendung bietet eine RESTful-API für den programmatischen Zugriff auf ihre Daten. Detaillierte Dokumentationen zu den verfügbaren Endpunkten, Anfrage-/Antwortformaten und Anwendungsbeispielen finden Sie auf der Seite `/api/docs`, wenn die Anwendung läuft.*

**Key API Blueprints / Wichtige API-Blueprints:** `/api`

*   `/api/users`: Get all users, add a new user.
*   `/api/users/<user_id>`: Get details for a specific user.
*   `/api/users/<user_id>/movies`: Get movies for a specific user, add a movie to a user's list.
*   `/api/movies`: Get all movies.
*   `/api/movies/<movie_id>`: Get details for a specific movie.
*   `/api/movies/<movie_id>/comments`: Get comments for a specific movie.
*   `/api/omdb_proxy`: Proxy for OMDb API searches.
*   `/api/check_or_create_movie_by_imdb`: Check if a movie exists by IMDb ID, or create it if not.

## Future Enhancements / Zukünftige Erweiterungen

(As outlined in the About section / Wie im Abschnitt "Über uns" beschrieben)

*   **Enhanced User Accounts:** Optional password protection.
    *   *Erweiterte Benutzerkonten: Optionaler Passwortschutz.*
*   **Advanced AI Search:** Search by actors, genre, mood, combined criteria.
    *   *Fortschrittliche KI-Suche: Suche nach Schauspielern, Genre, Stimmung, kombinierten Kriterien.*
*   **Streaming Service Links:** Direct links to services like Netflix, Amazon Prime.
    *   *Streaming-Dienst-Links: Direkte Links zu Diensten wie Netflix, Amazon Prime.*
*   **MovieWeb Fun - The Game:** Interactive movie quiz.
    *   *MovieWeb Fun - Das Spiel: Interaktives Filmquiz.*
*   **Improved Social Features:** Friendships, sharing lists/recommendations.
    *   *Verbesserte soziale Funktionen: Freundschaften, Teilen von Listen/Empfehlungen.*
*   **Personalized Dashboards:** Tailored homepage experience.
    *   *Personalisierte Dashboards: Zugeschnittenes Startseitenerlebnis.*
*   **Watchlist & Notifications:** Dedicated watchlist and notifications for new releases/availability.
    *   *Watchlist & Benachrichtigungen: Dedizierte Watchlist und Benachrichtigungen für Neuerscheinungen/Verfügbarkeit.*

## License / Lizenz

[MIT License] (./LICENSE) (Assuming MIT, placeholder)
*([MIT-Lizenz] (./LICENSE) (Angenommen MIT, Platzhalter))*

## Screenshots

**Login & Top 10 Filme**

![Login und Top 10](static/img/login%20mit%20top%2010.png)

**Eigene Filmliste eines Nutzers**

![Eigene Movielist](static/img/eigene%20Movielist.png)

**Ausschnitt Top 10 Ansicht**

![Top 10 Ansicht](static/img/Auszug%20top%2010%20ansicht.png)

**KI-Suchfunktion & Kommentarfunktion**

![KI-Suche und Kommentar](static/img/ai%20suchfunktion%20und%20kommentar%20funktion.png)

**Detailkarte mit KI-Suchvorschlägen**

![Detailkarte mit KI-Suchvorschlägen](static/img/detailkarte%20mit%20ai%20such%20vorschl%C3%A4gen.png)

**Detailkarte mit KI-Suchergebnissen und Auswahlvorschau**

![Detailkarte mit KI-Suchergebnissen und Auswahlvorschau](static/img/detailkarte%20mit%20ai%20suchergebnissen%20und%20auswahlvorschau.png)

**Auswahlvorschau Detail zum Hinzufügen**

![Auswahlvorschau Detail zum Hinzufügen](static/img/auswahl%20vorschau%20detail%20zum%20hinzuf%C3%BCgen%20.png)

**Detailkarte mit KI-Suche und Kommentarfunktion**

![Detailkarte mit KI-Suche und Kommentarfunktion](static/img/detailkarte%20mit%20ai%20suche%20und%20commentarfunktion.png) 