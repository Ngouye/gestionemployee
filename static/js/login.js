// static/js/login.js

document.addEventListener('DOMContentLoaded', function() {
    initializeLoginPage();
});

function initializeLoginPage() {
    console.log('Login page initialized');
    
    // Password toggle functionality
    initializePasswordToggle();
    
    // Form submission handling
    initializeFormSubmission();
    
    // Auto-focus and input animations
    initializeInputAnimations();
}

function initializePasswordToggle() {
    const passwordToggle = document.getElementById('passwordToggle');
    const passwordInput = document.getElementById('id_password');
    
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Update icon
            const icon = this.querySelector('i');
            if (icon) {
                icon.className = type === 'password' ? 'fas fa-eye' : 'fas fa-eye-slash';
            }
        });
    }
}

function initializeFormSubmission() {
    const loginForm = document.querySelector('.login-form');
    const loginBtn = document.querySelector('.login-btn');
    
    if (loginForm && loginBtn) {
        loginForm.addEventListener('submit', function(e) {
            // Show loading state
            loginBtn.classList.add('loading');
            loginBtn.disabled = true;
            
            // Validate form before submission
            if (!validateForm()) {
                e.preventDefault();
                resetButtonState(loginBtn);
                return;
            }
            
            // Form is valid, allow submission
            // Loading state will be reset on page reload/redirect
            
            // Safety timeout to re-enable button (in case of error)
            setTimeout(() => {
                resetButtonState(loginBtn);
            }, 5000);
        });
    }
}

function validateForm() {
    const username = document.getElementById('id_username');
    const password = document.getElementById('id_password');
    
    let isValid = true;
    
    // Reset previous errors
    clearFieldErrors();
    
    // Validate username
    if (!username || !username.value.trim()) {
        showFieldError(username, 'Le nom d\'utilisateur est requis');
        isValid = false;
    }
    
    // Validate password
    if (!password || !password.value.trim()) {
        showFieldError(password, 'Le mot de passe est requis');
        isValid = false;
    } else if (password.value.length < 1) {
        showFieldError(password, 'Le mot de passe est trop court');
        isValid = false;
    }
    
    return isValid;
}

function showFieldError(field, message) {
    if (!field) return;
    
    // Add error class to input container
    const container = field.closest('.input-container');
    if (container) {
        container.classList.add('error');
    }
    
    // Create or update error message
    let errorElement = container.querySelector('.field-error');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'field-error';
        container.appendChild(errorElement);
    }
    
    errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    errorElement.style.display = 'block';
}

function clearFieldErrors() {
    const errorContainers = document.querySelectorAll('.input-container');
    errorContainers.forEach(container => {
        container.classList.remove('error');
        
        const errorElement = container.querySelector('.field-error');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    });
}

function resetButtonState(button) {
    if (button) {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

function initializeInputAnimations() {
    // Auto-focus on username field with delay
    setTimeout(() => {
        const usernameInput = document.getElementById('id_username');
        if (usernameInput) {
            usernameInput.focus();
        }
    }, 600);
    
    // Input focus animations
    const inputs = document.querySelectorAll('.form-input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        input.addEventListener('blur', function() {
            if (this.value === '') {
                this.parentElement.classList.remove('focused');
            }
        });
        
        // Real-time validation
        input.addEventListener('input', function() {
            clearFieldErrors();
            this.parentElement.classList.remove('error');
        });
    });
}

// Utility function to check if element is in viewport
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Add CSS for field errors (injected via JavaScript)
function injectErrorStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .input-container.error .form-input {
            border-color: var(--error-color);
            background: #fef2f2;
        }
        
        .input-container.error .input-icon {
            color: var(--error-color);
        }
        
        .field-error {
            display: none;
            color: var(--error-color);
            font-size: 0.875rem;
            margin-top: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            animation: slideIn 0.3s ease-out;
        }
        
        .input-container.focused .floating-label {
            color: #667eea;
        }
    `;
    document.head.appendChild(style);
}

// Initialize error styles when DOM is loaded
document.addEventListener('DOMContentLoaded', injectErrorStyles);