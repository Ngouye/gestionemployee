document.addEventListener('DOMContentLoaded', function() {
    // Animation des champs au focus
    const inputs = document.querySelectorAll('.modern-form input, .modern-form select, .modern-form textarea');
    
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        input.addEventListener('blur', function() {
            if (this.value === '') {
                this.parentElement.classList.remove('focused');
            }
        });
        
        // Vérifier les champs pré-remplis
        if (input.value !== '') {
            input.parentElement.classList.add('focused');
        }
    });
    
    // Validation en temps réel
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            this.classList.remove('invalid');
            
            if (this.checkValidity()) {
                this.classList.add('valid');
            } else {
                this.classList.remove('valid');
            }
        });
    });
    
    // Confirmation avant soumission
    const form = document.querySelector('.modern-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('.btn-submit');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enregistrement...';
                submitBtn.disabled = true;
            }
        });
    }
});