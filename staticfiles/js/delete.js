document.addEventListener('DOMContentLoaded', function() {
    console.log('Delete confirmation page loaded');
    
    const confirmCheckbox = document.getElementById('confirmDelete');
    const deleteButton = document.getElementById('deleteButton');
    const deleteForm = document.querySelector('.delete-form');
    
    // Activer/désactiver le bouton de suppression
    if (confirmCheckbox && deleteButton) {
        confirmCheckbox.addEventListener('change', function() {
            deleteButton.disabled = !this.checked;
        });
    }
    
    // Confirmation supplémentaire
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            if (!confirm('⚠️ DERNIÈRE CONFIRMATION : Êtes-vous ABSOLUMENT certain de vouloir supprimer cet employé ?')) {
                e.preventDefault();
                return;
            }
            
            // Animation de suppression
            const submitBtn = this.querySelector('.btn-danger');
            if (submitBtn) {
                const originalHTML = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Suppression en cours...';
                submitBtn.disabled = true;
                
                // Réactiver après 10 secondes maximum
                setTimeout(() => {
                    submitBtn.innerHTML = originalHTML;
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    }
    
    // Effet de pulsation sur le bouton de suppression
    if (deleteButton) {
        setInterval(() => {
            if (!deleteButton.disabled) {
                deleteButton.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    deleteButton.style.transform = 'scale(1)';
                }, 500);
            }
        }, 2000);
    }
});document.addEventListener('DOMContentLoaded', function() {
    console.log('Delete confirmation page loaded');
    
    const confirmCheckbox = document.getElementById('confirmDelete');
    const deleteButton = document.getElementById('deleteButton');
    const deleteForm = document.querySelector('.delete-form');
    
    // Activer/désactiver le bouton de suppression
    if (confirmCheckbox && deleteButton) {
        confirmCheckbox.addEventListener('change', function() {
            deleteButton.disabled = !this.checked;
        });
    }
    
    // Confirmation supplémentaire
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            if (!confirm('⚠️ DERNIÈRE CONFIRMATION : Êtes-vous ABSOLUMENT certain de vouloir supprimer cet employé ?')) {
                e.preventDefault();
                return;
            }
            
            // Animation de suppression
            const submitBtn = this.querySelector('.btn-danger');
            if (submitBtn) {
                const originalHTML = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Suppression en cours...';
                submitBtn.disabled = true;
                
                // Réactiver après 10 secondes maximum
                setTimeout(() => {
                    submitBtn.innerHTML = originalHTML;
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    }
    
    // Effet de pulsation sur le bouton de suppression
    if (deleteButton) {
        setInterval(() => {
            if (!deleteButton.disabled) {
                deleteButton.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    deleteButton.style.transform = 'scale(1)';
                }, 500);
            }
        }, 2000);
    }
});document.addEventListener('DOMContentLoaded', function() {
    console.log('Delete confirmation page loaded');
    
    const confirmCheckbox = document.getElementById('confirmDelete');
    const deleteButton = document.getElementById('deleteButton');
    const deleteForm = document.querySelector('.delete-form');
    
    // Activer/désactiver le bouton de suppression
    if (confirmCheckbox && deleteButton) {
        confirmCheckbox.addEventListener('change', function() {
            deleteButton.disabled = !this.checked;
        });
    }
    
    // Confirmation supplémentaire
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            if (!confirm('⚠️ DERNIÈRE CONFIRMATION : Êtes-vous ABSOLUMENT certain de vouloir supprimer cet employé ?')) {
                e.preventDefault();
                return;
            }
            
            // Animation de suppression
            const submitBtn = this.querySelector('.btn-danger');
            if (submitBtn) {
                const originalHTML = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Suppression en cours...';
                submitBtn.disabled = true;
                
                // Réactiver après 10 secondes maximum
                setTimeout(() => {
                    submitBtn.innerHTML = originalHTML;
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    }
    
    // Effet de pulsation sur le bouton de suppression
    if (deleteButton) {
        setInterval(() => {
            if (!deleteButton.disabled) {
                deleteButton.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    deleteButton.style.transform = 'scale(1)';
                }, 500);
            }
        }, 2000);
    }
});document.addEventListener('DOMContentLoaded', function() {
    console.log('Delete confirmation page loaded');
    
    const confirmCheckbox = document.getElementById('confirmDelete');
    const deleteButton = document.getElementById('deleteButton');
    const deleteForm = document.querySelector('.delete-form');
    
    // Activer/désactiver le bouton de suppression
    if (confirmCheckbox && deleteButton) {
        confirmCheckbox.addEventListener('change', function() {
            deleteButton.disabled = !this.checked;
        });
    }
    
    // Confirmation supplémentaire
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            if (!confirm('⚠️ DERNIÈRE CONFIRMATION : Êtes-vous ABSOLUMENT certain de vouloir supprimer cet employé ?')) {
                e.preventDefault();
                return;
            }
            
            // Animation de suppression
            const submitBtn = this.querySelector('.btn-danger');
            if (submitBtn) {
                const originalHTML = submitBtn.innerHTML;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Suppression en cours...';
                submitBtn.disabled = true;
                
                // Réactiver après 10 secondes maximum
                setTimeout(() => {
                    submitBtn.innerHTML = originalHTML;
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    }
    
    // Effet de pulsation sur le bouton de suppression
    if (deleteButton) {
        setInterval(() => {
            if (!deleteButton.disabled) {
                deleteButton.style.transform = 'scale(1.02)';
                setTimeout(() => {
                    deleteButton.style.transform = 'scale(1)';
                }, 500);
            }
        }, 2000);
    }
});