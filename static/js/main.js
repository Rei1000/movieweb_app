/*
 main.js
 JS logic for interactive star-rating.
 JS-Logik für interaktive Sternebewertung.
*/

document.addEventListener('DOMContentLoaded', function() {
    const ratingInput = document.getElementById('rating');
    // Check if a dedicated interactive star container already exists
    // Prüfe, ob bereits ein dedizierter interaktiver Sterne-Container existiert
    const dedicatedStarContainerExists = document.getElementById('star-rating-interactive') || document.getElementById('interactive-star-rating-widget');

    // Only proceed if the input field exists AND
    // it does NOT have the class 'form-input-hidden' (or similar indicators for manual handling)
    // AND no dedicated star container is already on the page.
    // Nur fortfahren, wenn das Input-Feld existiert UND
    // es NICHT die Klasse 'form-input-hidden' hat (oder ähnliche Indikatoren für manuelle Handhabung)
    // UND kein dedizierter Sterne-Container bereits auf der Seite ist.
    if (!ratingInput || ratingInput.classList.contains('form-input-hidden') || dedicatedStarContainerExists) {
        // If the input is specifically hidden or a dedicated container exists,
        // this global script should not automatically add stars.
        // The local script of the respective page (add_movie.html or update_movie_rating.html) will handle it.
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
    // Create star container
    // Erstelle Container für Sterne
    const starContainer = document.createElement('div');
    starContainer.classList.add('star-rating');

    // Generate stars
    // Erzeuge Sterne
    for (let i = 1; i <= maxStars; i++) {
        const star = document.createElement('span');
        star.classList.add('star');
        star.textContent = '☆'; // empty star / leerer Stern
        star.dataset.value = i;
        starContainer.appendChild(star);
    }

    // Insert container before input
    // Füge Container vor dem Input ein
    ratingInput.parentNode.insertBefore(starContainer, ratingInput);
    ratingInput.style.display = 'none'; // Hide the numerical input field / Verstecke das numerische Input-Feld

    // Function to update stars display
    // Funktion zum Aktualisieren der Sternanzeige
    function updateStars(value) {
        const stars = starContainer.querySelectorAll('.star');
        stars.forEach(function(star) {
            const starValue = parseInt(star.dataset.value, 10);
            // Unicode stars for flexibility
            // Unicode-Sterne für Flexibilität
            if (value >= starValue) {
                star.textContent = '★'; // Filled star / Gefüllter Stern
            } else if (value >= starValue - 0.5) {
                star.textContent = '🌗'; // Half star (e.g., Unicode U+1F317) / Halber Stern (z.B. Unicode U+1F317)
            } else {
                star.textContent = '☆'; // Empty star / Leerer Stern
            }
        });
    }

    // Initial display
    // Initiale Anzeige
    updateStars(parseFloat(ratingInput.value) || 0);

    // Click event to set rating
    // Klick-Event zum Setzen der Bewertung
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

            // If the same value is clicked, the rating is set to 0
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

    // Hover effect for stars (optional, but improves UX)
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
            // Temporary display of stars on hover
            // Temporäre Anzeige der Sterne beim Hovern
            const tempStars = starContainer.querySelectorAll('.star');
            tempStars.forEach(function(star) {
                const starValue = parseInt(star.dataset.value, 10);
                // Use Unicode stars or FontAwesome classes here, matching updateStars
                // Hier Unicode-Sterne oder FontAwesome-Klassen verwenden, passend zu updateStars
                if (hoverRating >= starValue) {
                    star.textContent = '★'; 
                } else if (hoverRating >= starValue - 0.5) {
                    star.textContent = '🌗'; // Example for half star (adjust if needed) / Beispiel für halben Stern (ggf. anpassen)
                } else {
                    star.textContent = '☆';
                }
            });
        }
    });

    starContainer.addEventListener('mouseleave', function() {
        // Reset stars to the currently saved value
        // Sterne auf den aktuell gespeicherten Wert zurücksetzen
        updateStars(parseFloat(ratingInput.value) || 0);
    });
});

// Login function
// Login-Funktion
function login() {
    const username = document.getElementById('username').value.trim();
    if (!username) {
        alert('Please enter a username.');
        return;
    }
    const csrfTokenInput = document.querySelector('meta[name="csrf-token"]');
    if (!csrfTokenInput) {
        alert('CSRF Token not found. Please reload the page.');
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
            alert(data.message); // This message comes from app.py and is already English-only / Diese Nachricht kommt von app.py und ist bereits nur auf Englisch
        }
    })
    .catch(error => {
        console.error('Login Error:', error);
        alert('An error occurred during login.');
    });
}

// Registration function
// Registrierungs-Funktion
function register() {
    const username = document.getElementById('username').value.trim();
    if (!username) {
        alert('Please enter a username.');
        return;
    }
    const csrfTokenInput = document.querySelector('meta[name="csrf-token"]');
    if (!csrfTokenInput) {
        alert('CSRF Token not found. Please reload the page.');
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
            alert(data.message); // This message comes from app.py and is already English-only / Diese Nachricht kommt von app.py und ist bereits nur auf Englisch
        }
    })
    .catch(error => {
        console.error('Registration Error:', error);
        alert('An error occurred during registration.');
    });
}