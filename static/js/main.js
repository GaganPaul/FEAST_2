/**
 * FEAST - Community Kitchen Network
 * Main JavaScript file
 */

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize flash message dismissal
    initFlashMessages();
    
    // Initialize location services if available
    initLocationServices();
    
    // Initialize form validations
    initFormValidations();
});

/**
 * Initialize flash message dismissal functionality
 */
function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    
    flashMessages.forEach(message => {
        // Add close button to each message
        const closeBtn = document.createElement('span');
        closeBtn.innerHTML = '&times;';
        closeBtn.className = 'flash-close';
        message.appendChild(closeBtn);
        
        // Add click event to close button
        closeBtn.addEventListener('click', function() {
            message.style.opacity = '0';
            setTimeout(() => {
                message.style.display = 'none';
            }, 300);
        });
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.style.display = 'none';
            }, 300);
        }, 5000);
    });
}

/**
 * Initialize location services
 */
function initLocationServices() {
    // Check if geolocation is available in the browser
    if (navigator.geolocation) {
        // Get location permission button if it exists
        const locationBtn = document.getElementById('getLocationBtn');
        
        if (locationBtn) {
            locationBtn.addEventListener('click', function() {
                navigator.geolocation.getCurrentPosition(
                    // Success callback
                    function(position) {
                        const latitude = position.coords.latitude;
                        const longitude = position.coords.longitude;
                        
                        // Update hidden form fields if they exist
                        const latField = document.getElementById('latitude');
                        const lngField = document.getElementById('longitude');
                        
                        if (latField && lngField) {
                            latField.value = latitude;
                            lngField.value = longitude;
                            
                            // Show success message
                            const locationStatus = document.getElementById('locationStatus');
                            if (locationStatus) {
                                locationStatus.textContent = 'Location captured successfully!';
                                locationStatus.className = 'success-text';
                            }
                        }
                        
                        // Update server with location if user is logged in
                        updateLocationOnServer(latitude, longitude);
                    },
                    // Error callback
                    function(error) {
                        console.error("Error getting location:", error);
                        
                        // Show error message
                        const locationStatus = document.getElementById('locationStatus');
                        if (locationStatus) {
                            locationStatus.textContent = 'Failed to get location. Please try again.';
                            locationStatus.className = 'error-text';
                        }
                    }
                );
            });
        }
    }
}

/**
 * Update user location on the server
 */
function updateLocationOnServer(latitude, longitude) {
    // Check if user is logged in (this would be set in a real app)
    const isLoggedIn = document.body.hasAttribute('data-logged-in');
    
    if (isLoggedIn) {
        fetch('/api/update-location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                latitude: latitude,
                longitude: longitude
            }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('Location updated:', data);
        })
        .catch((error) => {
            console.error('Error updating location:', error);
        });
    }
}

/**
 * Initialize form validations
 */
function initFormValidations() {
    // Password confirmation validation
    const passwordForms = document.querySelectorAll('form[data-validate-password]');
    
    passwordForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const password = form.querySelector('input[name="password"]');
            const confirmPassword = form.querySelector('input[name="confirm_password"]');
            
            if (password && confirmPassword && password.value !== confirmPassword.value) {
                e.preventDefault();
                alert('Passwords do not match!');
            }
        });
    });
    
    // Date validation for expiry dates
    const expiryDateInputs = document.querySelectorAll('input[data-validate-future-date]');
    
    expiryDateInputs.forEach(input => {
        input.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const today = new Date();
            
            if (selectedDate < today) {
                this.setCustomValidity('Please select a future date');
            } else {
                this.setCustomValidity('');
            }
        });
    });
}

/**
 * Toggle mobile navigation menu
 */
function toggleMobileNav() {
    const navLinks = document.querySelector('.nav-links');
    navLinks.classList.toggle('active');
}

/**
 * Calculate distance between two points using Haversine formula
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Radius of the earth in km
    const dLat = deg2rad(lat2 - lat1);
    const dLon = deg2rad(lon2 - lon1);
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * 
        Math.sin(dLon/2) * Math.sin(dLon/2); 
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    const distance = R * c; // Distance in km
    return distance;
}

function deg2rad(deg) {
    return deg * (Math.PI/180);
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

/**
 * Format time for display
 */
function formatTime(timeString) {
    const date = new Date(`2000-01-01T${timeString}`);
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Show loading spinner
 */
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="loading-spinner"></div>';
    }
}

/**
 * Hide loading spinner
 */
function hideLoading(elementId, content) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = content || '';
    }
}
