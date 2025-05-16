/*
 main.js
 JS-Logik für interaktive Sternebewertung.
 JS logic for interactive star-rating.
*/

document.addEventListener('DOMContentLoaded', function() {
    const ratingInput = document.getElementById('rating');
    // Prüfe, ob bereits ein dedizierter interaktiver Sterne-Container existiert
    const dedicatedStarContainerExists = document.getElementById('star-rating-interactive') || document.getElementById('interactive-star-rating-widget');

    // Nur fortfahren, wenn das Input-Feld existiert UND
    // es NICHT die Klasse 'form-input-hidden' hat (oder ähnliche Indikatoren für manuelle Handhabung)
    // UND kein dedizierter Sterne-Container bereits auf der Seite ist.
    if (!ratingInput || ratingInput.classList.contains('form-input-hidden') || dedicatedStarContainerExists) {
        // Wenn das Input spezifisch versteckt ist oder ein dedizierter Container da ist,
        // soll dieses globale Skript die Sterne nicht automatisch hinzufügen.
        // Das lokale Skript der jeweiligen Seite (add_movie.html oder update_movie_rating.html) übernimmt das.
        if (ratingInput && (ratingInput.classList.contains('form-input-hidden') || dedicatedStarContainerExists)) {
            console.log('main.js: Skipping automatic star generation for #rating due to .form-input-hidden or existing star widget.');
        }
        return;
    }
    console.log('main.js: Proceeding with automatic star generation for #rating.');

    const maxStars = 5;
    // Erstelle Container für Sterne / Create star container
    const starContainer = document.createElement('div');
    starContainer.classList.add('star-rating');

    // Erzeuge Sterne / Generate stars
    for (let i = 1; i <= maxStars; i++) {
        const star = document.createElement('span');
        star.classList.add('star');
        star.textContent = '☆'; // leerer Stern / empty star
        star.dataset.value = i;
        starContainer.appendChild(star);
    }

    // Füge Container vor dem Input ein / Insert container before input
    ratingInput.parentNode.insertBefore(starContainer, ratingInput);
    ratingInput.style.display = 'none'; // Verstecke das numerische Input-Feld

    // Funktion zum Aktualisieren der Sternanzeige / Function to update stars display
    function updateStars(value) {
        const stars = starContainer.querySelectorAll('.star');
        stars.forEach(function(star) {
            const starValue = parseInt(star.dataset.value, 10);
            // Unicode-Sterne für Flexibilität
            if (value >= starValue) {
                star.textContent = '★'; // Gefüllter Stern
            } else if (value >= starValue - 0.5) {
                star.textContent = '🌗'; // Halber Stern (z.B. Unicode U+1F317)
            } else {
                star.textContent = '☆'; // Leerer Stern
            }
        });
    }

    // Initiale Anzeige
    updateStars(parseFloat(ratingInput.value) || 0);

    // Klick-Event zum Setzen der Bewertung / Click event to set rating
    starContainer.addEventListener('click', function(event) {
        if (event.target.classList.contains('star')) {
            const starElement = event.target;
            const selectedStarValue = parseInt(starElement.dataset.value, 10);
            const rect = starElement.getBoundingClientRect();
            const offsetX = event.clientX - rect.left;
            let actualRating = selectedStarValue;

            if (offsetX < rect.width / 2) {
                actualRating -= 0.5;
            }

            // Wenn auf denselben Wert geklickt wird, wird die Bewertung auf 0 gesetzt
            if (parseFloat(ratingInput.value) === actualRating) {
                ratingInput.value = '0'; 
                updateStars(0);
            } else {
                ratingInput.value = actualRating.toFixed(1);
                updateStars(actualRating);
            }
        }
    });

    // Hover-Effekt für Sterne (optional, aber verbessert UX)
    starContainer.addEventListener('mousemove', function(event) {
        if (event.target.classList.contains('star')) {
            const starElement = event.target;
            const hoverStarValue = parseInt(starElement.dataset.value, 10);
            const rect = starElement.getBoundingClientRect();
            const offsetX = event.clientX - rect.left;
            let hoverRating = hoverStarValue;

            if (offsetX < rect.width / 2) {
                hoverRating -= 0.5;
            }
            // Temporäre Anzeige der Sterne beim Hovern
            const tempStars = starContainer.querySelectorAll('.star');
            tempStars.forEach(function(star) {
                const starValue = parseInt(star.dataset.value, 10);
                // Hier Unicode-Sterne oder FontAwesome-Klassen verwenden, passend zu updateStars
                if (hoverRating >= starValue) {
                    star.textContent = '★'; 
                } else if (hoverRating >= starValue - 0.5) {
                    star.textContent = '🌗'; // Beispiel für halben Stern (ggf. anpassen)
                } else {
                    star.textContent = '☆';
                }
            });
        }
    });

    starContainer.addEventListener('mouseleave', function() {
        // Sterne auf den aktuell gespeicherten Wert zurücksetzen
        updateStars(parseFloat(ratingInput.value) || 0);
    });
});

// Login-Funktion
function login() {
    const username = document.getElementById('username').value.trim();
    if (!username) {
        alert('Bitte geben Sie einen Benutzernamen ein.');
        return;
    }
    const csrfTokenInput = document.querySelector('meta[name="csrf-token"]');
    if (!csrfTokenInput) {
        alert('CSRF Token nicht gefunden. Bitte laden Sie die Seite neu.');
        return;
    }
    const csrfToken = csrfTokenInput.getAttribute('content');

    fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `username=${encodeURIComponent(username)}&csrf_token=${encodeURIComponent(csrfToken)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect;
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ein Fehler ist aufgetreten.');
    });
}

// Registrierungs-Funktion
function register() {
    const username = document.getElementById('username').value.trim();
    if (!username) {
        alert('Bitte geben Sie einen Benutzernamen ein.');
        return;
    }
    const csrfTokenInput = document.querySelector('meta[name="csrf-token"]');
    if (!csrfTokenInput) {
        alert('CSRF Token nicht gefunden. Bitte laden Sie die Seite neu.');
        return;
    }
    const csrfToken = csrfTokenInput.getAttribute('content');

    fetch('/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `username=${encodeURIComponent(username)}&csrf_token=${encodeURIComponent(csrfToken)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect;
        } else {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ein Fehler ist aufgetreten.');
    });
}