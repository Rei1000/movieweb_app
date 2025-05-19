# Zusammenfassung: MovieWeb-Anwendung

Dieses Dokument dient als detaillierte Zusammenfassung der MovieWeb-Flask-Anwendung, basierend auf der Analyse aller relevanten Projektdateien. Es soll als Referenz für zukünftige Entwicklungen und Diskussionen dienen.

## 1. Projektübersicht

*   **Name**: MovieWeb-Anwendung
*   **Zweck**: Eine Webanwendung zur Verwaltung von Filmlisten für Benutzer, zum Abrufen von Filminformationen (über OMDb), zum Kommentieren von Filmen und zur Nutzung von KI-basierten Diensten für Filmidentifikation und -empfehlungen (über OpenRouter). Die Anwendung ist zweisprachig (Deutsch/Englisch) ausgelegt, wobei UI-Texte primär Englisch sind und Dokumentation/Kommentare bilingual.
*   **Haupttechnologien**:
    *   Backend: Python, Flask
    *   Datenbank: SQLite (mit SQLAlchemy ORM)
    *   Frontend: HTML, CSS, JavaScript (vanilla)
    *   APIs:
        *   OMDb API (für Filmdaten)
        *   OpenRouter API (für KI-Funktionen, z.B. GPT-3.5-Turbo)
    *   Wichtige Python-Bibliotheken: `requests`, `python-dotenv`, `Flask-SQLAlchemy`, `Flask-WTF`. (Details siehe `requirements.txt`)

## 2. Dateistruktur

*   **`/movieweb_app`** (Stammverzeichnis)
    *   **`app.py`**: Hauptmodul der Flask-Anwendung. Enthält App-Initialisierung, UI-bezogene Routendefinitionen, Kernlogik der Benutzeroberfläche (nicht API), KI-Integrationslogik für die UI, Hilfsfunktionen und globale Fehlerbehandler (404, 500).
    *   **`models.py`**: Definiert die SQLAlchemy-Datenbankmodelle (`User`, `Movie`, `UserMovie`, `Comment`).
    *   **`init_db.py`**: Skript zur einmaligen Initialisierung des Datenbankschemas (`db.create_all()`).
    *   **`requirements.txt`**: Listet alle Python-Paketabhängigkeiten mit fixierten Versionen.
    *   **`README.md`**: Ausführliche Dokumentation des Projekts, inklusive Setup-Anleitung.
    *   **`.env`** (erwartet, nicht versioniert): Speichert sensible Umgebungsvariablen (`OMDB_API_KEY`, `OPENROUTER_API_KEY`, `DATABASE_URI`, `SECRET_KEY`).
    *   **`datamanager/`**: Modul für die Datenzugriffsschicht.
        *   **`__init__.py`**: Macht die Klassen des Moduls importierbar.
        *   **`data_manager_interface.py`**: Definiert die abstrakte Basisklasse `DataManagerInterface` für Datenoperationen.
        *   **`sqlite_data_manager.py`**: Konkrete Implementierung der `DataManagerInterface` für SQLite unter Verwendung von SQLAlchemy. Enthält die gesamte Logik für Datenbank-CRUD-Operationen.
    *   **`api/`**: Modul für die JSON-basierte REST-API.
        *   **`__init__.py`**: Macht das API-Blueprint importierbar.
        *   **`routes.py`**: Definiert die API-Routen als Flask-Blueprint. Enthält Logik für Caching und Fehlerbehandlung der API-Endpunkte.
    *   **`templates/`**: Verzeichnis für Jinja2 HTML-Templates.
        *   `base.html`: Basis-Layout.
        *   `_macros.html`: Wiederverwendbare Template-Makros.
        *   Weitere Templates für spezifische Seiten (z.B. `home.html`, `movies.html`, `movie_detail_page.html`, `add_movie.html`, `api_docs.html`, `404.html`, `500.html` etc.).
    *   **`static/`**: Verzeichnis für statische Dateien.
        *   `css/`: Stylesheets (z.B. `style.css`).
        *   `js/`: JavaScript-Dateien (z.B. `main.js`, das CSRF für AJAX handhabt).
        *   `img/`: Bilder (z.B. `no_poster.png`).
    *   **`.gitignore`**: Spezifiziert absichtlich nicht versionierte Dateien und Verzeichnisse.
    *   **`instance/`**: (Standard-Flask-Ordner) Kann z.B. die SQLite-Datenbankdatei enthalten.
    *   **`venv/`**: (Typisch) Verzeichnis für die virtuelle Python-Umgebung.

## 3. Konfiguration (`app.py` und Umgebung)

*   **`SQLALCHEMY_DATABASE_URI`**: Aus `.env` (`DATABASE_URI`), Standard `sqlite:///moviewebapp.db`.
*   **`SQLALCHEMY_TRACK_MODIFICATIONS`**: `False`.
*   **`SECRET_KEY`**: Aus `.env` (`SECRET_KEY`), Standard `dev_secret`.
*   **`OMDB_API_KEY`**: Aus `.env`.
*   **`OPENROUTER_API_KEY`**: Aus `.env`.
*   **CSRF-Schutz**: Global in `app.py` via `Flask-WTF` initialisiert. JavaScript in `static/js/main.js` scheint CSRF-Header für AJAX-Anfragen zu setzen.

## 4. Datenbankmodelle (`models.py`)

*   **`User`**: `id` (PK), `name`. Beziehungen: `movies` (zu `UserMovie`), `comments`.
*   **`Movie`**: `id` (PK), `title`, `original_title`, `director`, `writer`, `actors`, `year`, `runtime`, `genre`, `plot`, `language`, `country`, `awards`, `poster_url`, `community_rating`, `community_rating_count`, `imdb_rating`, `imdb_votes`, `imdb_id` (Unique), `metascore`, `rated_omdb`. Beziehungen: `users` (zu `UserMovie`), `comments`.
*   **`UserMovie`**: `id` (PK), `user_id` (FK), `movie_id` (FK), `user_rating`. Dient als Assoziationstabelle für die n:m-Beziehung zwischen Usern und Filmen und speichert die individuelle Bewertung.
*   **`Comment`**: `id` (PK), `text`, `created_at`, `likes_count` (für zukünftige Nutzung), `user_id` (FK), `movie_id` (FK). Beziehungen: `user`, `movie`.
*   Alle Modelle haben `__repr__`-Methoden. Relationen sind mit `back_populates` und `cascade="all, delete-orphan"` konfiguriert.

## 5. Datenzugriffsschicht (`datamanager/`)

*   **`DataManagerInterface`**: Definiert eine klare Schnittstelle für Datenoperationen (z.B. `get_all_users`, `add_movie`, `update_user_rating_for_movie`). Dies ist eine Best Practice für Entkopplung und Testbarkeit.
*   **`SQLiteDataManager`**:
    *   Implementiert die `DataManagerInterface` für SQLite.
    *   Umfasst detaillierte Logik für das Hinzufügen, Aktualisieren und Löschen von Benutzern und Filmen, inklusive der Behandlung von Verknüpfungen (`UserMovie`).
    *   **`add_movie()`**: Komplexe Methode, die prüft, ob ein Film global existiert (via `imdb_id`), ihn ggf. neu anlegt, die `UserMovie`-Verknüpfung erstellt/aktualisiert und das `community_rating` des Films über `_update_community_rating()` aktualisiert.
    *   **`_update_community_rating()`**: Private Methode zur Neuberechnung des durchschnittlichen Community-Ratings eines Films basierend auf allen individuellen `UserMovie.user_rating`-Einträgen.
    *   **Weitere Methoden**: `delete_movie()` (löscht Film global), `delete_movie_from_user_list()` (löst nur Verknüpfung), `add_existing_movie_to_user_list()`, `get_movie_by_imdb_id()`, `add_movie_globally()`.
    *   Umfangreiches, bilinguales Logging und robuste Fehlerbehandlung (SQLAlchemyError, Rollbacks).
    *   Gute Validierung von Eingabedaten (z.B. Rating-Werte, Jahreszahlen, leere Strings).

## 6. Kernlogik und Routen (`app.py`)

`app.py` ist das zentrale Modul für die UI-bezogenen Aspekte der Anwendung.

*   **Benutzerauthentifizierung und -verwaltung (UI)**:
    *   Session-basiert (`session['user_id']`).
    *   `POST /login`, `POST /register`: Liefern jetzt standardisierte JSON-Antworten (`success`, `data`, `message`) mit HTTP-Statuscodes (200/401 bzw. 201/400/409) für AJAX-basierte Logins/Registrierungen.
    *   `GET /logout` (weiterhin traditioneller Redirect).
    *   `@app.before_request (load_logged_in_user)` und `@app.context_processor (inject_user_status)` stellen Benutzerinformationen global und für Templates bereit.
    *   `GET /users`: Listet alle Benutzer (nutzt `data_manager`).
    *   `GET /add_user`, `POST /add_user`: Formular/Logik zum Hinzufügen neuer Benutzer (nutzt `data_manager`).
*   **Filmverwaltung (UI)**:
    *   `GET /users/<int:user_id>`: Zeigt Filmliste eines Benutzers (nutzt `data_manager`).
    *   `GET, POST /users/<int:user_id>/add_movie`: Sehr umfangreiche Route für den mehrstufigen Prozess des Filmhinzufügens (Benutzereingabe -> KI-Titelinterpretation -> OMDb-Abruf -> Speichern via `data_manager.add_movie`). Wurde refaktoriert mit Hilfsfunktionen.
    *   `POST /user/add_movie_to_list/<int:movie_id>`: Fügt existierenden Film zur Nutzerliste hinzu (via `data_manager`).
    *   `GET, POST /users/<int:user_id>/update_movie_rating/<int:movie_id>`: Aktualisiert Nutzer-Rating (via `data_manager`).
    *   `POST /users/<int:user_id>/delete_movie/<int:movie_id>`: Löscht Film aus Nutzerliste (via `data_manager`).
    *   `POST /user/list/remove/<int:movie_id>` (Endpoint: `remove_movie_from_list_explicit`): Alternative Route zum Löschen eines Films aus der Liste des eingeloggten Nutzers (via `data_manager`).
    *   `GET /movie/<int:movie_id>`: Liefert Filmdetails und Kommentare als JSON-Antwort im Standardformat (für UI-Nutzung, z.B. dynamisches Nachladen).
*   **KI-Integration (UI-bezogen)**:
    *   Konstanten für Prompts, Session-Keys, Temperaturen, Fehlermeldungen und Antwort-Marker.
    *   `get_ai_interpreted_movie_title()`: Ruft `ask_openrouter_for_movies()` zur Titelinterpretation auf.
    *   `ask_openrouter_for_movies()`: Zentrale Funktion für Anfragen an OpenRouter (GPT-3.5-Turbo). Enthält Logik zur Bereinigung der KI-Antworten (`_clean_ai_single_movie_title_response`, `_clean_ai_movie_list_response`).
    *   `GET /movie/<int:movie_id>/ai_recommendations`: Ruft `ask_openrouter_for_movies()` für Filmempfehlungen auf, verwaltet Empfehlungsverlauf in Session. Liefert standardisierte JSON-Antworten (200 OK, 404 Not Found, 503 Service Unavailable).
*   **Kommentare (UI)**:
    *   `POST /movie/<int:movie_id>/comment/page`: Fügt Kommentar von Filmdetailseite hinzu (nutzt `data_manager`). Liefert standardisierte JSON-Antworten (201 Created, 400 Bad Request, 401 Unauthorized, 500 Internal Server Error).
    *   `POST /movie/<int:movie_id>/comment`: (Legacy-JSON-Endpunkt, prüft auf `request.form`) Liefert ebenfalls standardisierte JSON-Antworten.
*   **Sonstige UI-Routen**:
    *   `GET /`: Startseite mit Top-Filmen (nutzt `data_manager`).
    *   `GET /movie/<int:movie_id>/page`: Filmdetailseite.
    *   `GET /about`, `GET /api/docs`.
*   **Fehlerbehandlung**: Globaler `@handle_api_error` Decorator für API-Routen, der standardisierte JSON-Fehlerantworten generiert (`success: False`, `message`).

## 7. API-Modul (`api/routes.py`)

Definiert ein Flask-Blueprint für JSON-basierte API-Endpunkte.

*   **Caching**: Einfacher In-Memory-Cache (`@cache_response`) für GET-Anfragen.
*   **Fehlerbehandlung**: Globaler `@handle_api_error` Decorator für API-Routen.
*   **Endpunkte** (alle geben jetzt standardisierte JSON-Antworten zurück: `success`, `data`, `message`):
    *   `GET /api/users`, `GET /api/users/{user_id}`, `GET /api/users/{user_id}/movies` (200 OK, 404 Not Found)
    *   `GET /api/movies`, `GET /api/movies/{movie_id}`, `GET /api/movies/{movie_id}/comments` (200 OK, 404 Not Found)
    *   `POST /api/users/{user_id}/movies`: Fügt Film zu Nutzerliste hinzu (via `data_manager.add_movie`). (201 Created, 400, 404, 409)
    *   `PUT /api/users/{user_id}/movies/{movie_id}`: Aktualisiert das persönliche Rating eines Nutzers für einen Film. (200 OK, 400, 401, 403, 404)
    *   `DELETE /api/users/{user_id}/movies/{movie_id}`: Entfernt Film aus Nutzerliste. (200 OK, 404)
    *   `GET /api/omdb_proxy`: Proxy für OMDb-Anfragen (schützt API-Key). (200 OK, 400, 404, 500/503)
    *   `POST /api/check_or_create_movie_by_imdb`: Prüft/erstellt Film global via IMDb ID (nutzt `data_manager`). (200 OK, 201 Created, 400, 500)
*   **Datenzugriff**: Alle Routen in `api/routes.py` verwenden jetzt konsistent den `data_manager` für Datenbankinteraktionen.

## 8. Analyse und Beobachtungen

### 8.1. Aktive und genutzte Routen
*   **`app.py` Routen**: Alle definierten Routen scheinen aktiv und für die Kernfunktionalität der Web-UI notwendig zu sein.
    *   Die zwei Entfern-Routen `POST /users/<int:user_id>/delete_movie/<int:movie_id>` und `POST /user/list/remove/<int:movie_id>` haben sehr ähnliche Funktionalität, sind aber beide im Code referenziert (die erste implizit durch typische CRUD-Muster, die zweite explizit als Endpoint `remove_movie_from_list_explicit` und wird von `movie_detail_page.html` per Formular-Action aufgerufen, wenn ein Film aus der Liste entfernt werden soll). Ihre Existenz ist nachvollziehbar, da sie leicht unterschiedliche Kontexte bedienen (allgemein vs. eingeloggter User).
*   **`api/routes.py` Routen**: Alle definierten API-Routen scheinen sinnvolle Endpunkte für programmatischen Zugriff oder Frontend-Interaktionen (via JavaScript) darzustellen.

### 8.2. Doppelter, inkonsistenter oder überflüssiger Code
*   **Datenzugriffskonsistenz (Wichtigster Punkt)**:
    *   **Problem**: Früher gab es eine deutliche Inkonsistenz beim Datenbankzugriff. Der `SQLiteDataManager` war vorhanden, aber viele Routen griffen direkt auf die `db.session` oder `Query`-Objekte zu.
    *   **Status**: **Weitgehend behoben.** Nahezu alle Datenbankinteraktionen in `app.py` und `api/routes.py` erfolgen jetzt konsequent über den `SQLiteDataManager` (bzw. die `DataManagerInterface`). Dies hat die Wartbarkeit, Testbarkeit und Entkopplung erheblich verbessert.
*   **KI-Prompt-Bereinigung in `ask_openrouter_for_movies`**: Die Logik zur Bereinigung von KI-Antworten (Entfernen von Präfixen, Nummerierungen etc.) wurde verfeinert. Eine robustere Parsing-Strategie oder klarere Anweisungen an die KI (im Prompt) könnten weiterhin helfen, aber die aktuelle Implementierung ist nachvollziehbar und wurde bereits optimiert (z.B. Entfernung des Komma-Splits für Filmtitel, Deduplizierung).
*   **Redundante OMDB_API_KEY-Ladung**: `OMDB_API_KEY` wird sowohl global in `app.py` als auch in `api/routes.py` geladen. Einmaliges Laden bei App-Start in `app.py` und ggf. Übergabe an das API-Modul oder Zugriff via `current_app.config` wäre sauberer. (Dieser Punkt ist noch offen).
*   **`add_movie` Route in `app.py`**: Diese Route wurde durch Auslagerung von Logik in Hilfsfunktionen (`_prepare_movie_details_from_db_for_add_template`, `_fetch_movie_details_from_omdb_for_add_template`, `_get_ai_suggestion_for_add_movie_template`, `_process_add_movie_form`) deutlich refaktoriert und die Lesbarkeit verbessert.

### 8.3. Einhaltung von Best Practices
*   **Gut umgesetzt**:
    *   **Modulare Struktur**: Trennung in `app.py`, `models.py`, `datamanager/`, `api/`, `templates/`, `static/`.
    *   **Datenzugriffsabstraktion und -konsistenz**: Die `DataManagerInterface` und ihre konsequente Nutzung in `SQLiteDataManager` sind ein Kernstück der Anwendung.
    *   **Standardisierte JSON-Antworten**: Die meisten JSON-liefernden Endpunkte (sowohl in `app.py` für UI-Interaktionen als auch in `api/routes.py`) folgen nun einem einheitlichen Format (`success`, `data`, `message`) und verwenden passende HTTP-Statuscodes. Dies verbessert die Vorhersagbarkeit und Handhabung im Frontend.
    *   **CSRF-Schutz**: Aktiv und scheint auch für AJAX-Anfragen bedacht worden zu sein.
    *   **Fehlerbehandlung**: Gute `try-except`-Blöcke im `DataManager` und in den API-Routen. Globale 404/500 Handler. Der API-Fehlerdecorator wurde verbessert.
    *   **Logging**: Sehr detailliertes und hilfreiches Logging in `SQLiteDataManager` und `app.py` (KI-Funktionen, Routen).
    *   **Umgebungsvariablen**: Korrekte Nutzung von `.env` für sensible Daten.
    *   **`requirements.txt`**: Versionen sind gepinnt.
    *   **`init_db.py`**: Sauberes Skript zur DB-Initialisierung.
    *   **README.md**: Ausführlich und informativ.
    *   **Zweisprachigkeit**: In Kommentaren und Log-Meldungen teilweise vorhanden, im README konsequent.
    *   **Passwortsicherheit**: Aktuell nur benutzernamebasierter Login. Für eine produktive Anwendung wäre Passwort-Hashing (z.B. mit Werkzeug-Sicherheitshelfern) unerlässlich, falls nicht ein anderes Authentifizierungsschema (z.B. OAuth) geplant ist. Das README erwähnt dies als zukünftige Erweiterung.
    *   **API-Caching**: Der In-Memory-Cache in `api/routes.py` ist für Single-Instanz-Deployments okay, aber nicht für Multi-Instanz. Ein externer Cache (Redis etc.) wäre skalierbarer.
    *   **Sprachkonsistenz in UI-Nachrichten**: `flash`-Nachrichten existieren weiterhin für traditionelle Formular-Redirects. Viele dynamische UI-Meldungen basieren jetzt auf (englischen) JSON-Antworten. Eine durchgehende Internationalisierung (i18n) für alle User-facing Strings (inkl. JavaScript-generierter Meldungen) mit z.B. Flask-Babel wäre für eine vollständig zweisprachige App ideal.
    *   **KI-Konstanten**: Werte wie `AI_RECOMMENDATION_HISTORY_LENGTH` etc. könnten in `app.config` ausgelagert werden für leichtere Konfiguration.
    *   **OMDB_API_KEY-Ladung**: (Siehe 8.2)

### 8.4. Sonstige Beobachtungen
*   **`Comment.likes_count`**: Ist als zukünftiges Feature markiert. Die dazugehörige Logik fehlt noch.
*   Die API (`api/routes.py`) ist für den programmatischen Zugriff und möglicherweise für ein JavaScript-gesteuertes Frontend gedacht. Die `app.py` Routen rendern hauptsächlich serverseitige HTML-Templates.
*   Das Projekt ist insgesamt gut strukturiert und die komplexeren Teile (KI-Interaktion, Datenmanagement) sind sorgfältig implementiert worden, besonders im Hinblick auf Logging und Fehlerbehandlung im `SQLiteDataManager`.

## 9. Anweisungen für zukünftige Aktualisierungen dieser Zusammenfassung

*   Diese Datei (`Zusammenfassung.md`) soll nach jeder signifikanten Code-Änderung im Projekt aktualisiert werden.
*   Änderungen sollen die betroffenen Abschnitte (z.B. Routen, Funktionen, Datenmodelle, Logik) widerspiegeln.
*   Es kann hilfreich sein, ein kurzes Änderungsprotokoll am Ende dieses Dokuments oder in Commit-Nachrichten zu führen, die sich auf Aktualisierungen dieser Zusammenfassung beziehen.
*   Ziel ist es, dass diese Zusammenfassung stets den aktuellen Stand des Projekts reflektiert und als verlässliche Informationsquelle dient.

---
Stand: Erstellt nach Analyse aller relevanten Projektdateien am 2024-07-27.
Letzte wesentliche Aktualisierung: 2024-07-29 (Refactoring der API- und UI-Endpunkte auf standardisierte JSON-Antworten, Datenzugriffskonsistenz weitgehend hergestellt). 