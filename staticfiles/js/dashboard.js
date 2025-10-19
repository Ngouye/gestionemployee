class EmployeeDashboard {
    constructor() {
        this.initializeEventListeners();
        this.currentSort = {
            column: null,
            direction: 'asc'
        };
    }

    initializeEventListeners() {
        // Recherche en temps réel
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearch(e));
        }

        // Tri des colonnes
        const sortableHeaders = document.querySelectorAll('th[data-sort]');
        sortableHeaders.forEach(header => {
            header.addEventListener('click', () => this.handleSort(header));
        });

        // Confirmation de suppression
        this.initializeDeleteConfirmations();
    }

    handleSearch(event) {
        const searchTerm = event.target.value.toLowerCase().trim();
        const employeeRows = document.querySelectorAll('.employee-row');
        
        employeeRows.forEach(row => {
            const rowText = row.textContent.toLowerCase();
            const shouldShow = rowText.includes(searchTerm);
            row.style.display = shouldShow ? '' : 'none';
            
            // Animation de recherche
            if (searchTerm) {
                this.highlightSearchTerm(row, searchTerm);
            } else {
                this.removeHighlights(row);
            }
        });
    }

    highlightSearchTerm(row, searchTerm) {
        this.removeHighlights(row);
        
        const textNodes = this.getTextNodes(row);
        textNodes.forEach(node => {
            const text = node.textContent;
            const regex = new RegExp(`(${this.escapeRegex(searchTerm)})`, 'gi');
            const newText = text.replace(regex, '<mark class="search-highlight">$1</mark>');
            
            if (newText !== text) {
                const newSpan = document.createElement('span');
                newSpan.innerHTML = newText;
                node.parentNode.replaceChild(newSpan, node);
            }
        });
    }

    removeHighlights(row) {
        const marks = row.querySelectorAll('mark.search-highlight');
        marks.forEach(mark => {
            const parent = mark.parentNode;
            parent.replaceChild(document.createTextNode(mark.textContent), mark);
            parent.normalize();
        });
    }

    getTextNodes(element) {
        const textNodes = [];
        const walk = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let node;
        while (node = walk.nextNode()) {
            textNodes.push(node);
        }
        
        return textNodes;
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    handleSort(header) {
        const sortBy = header.dataset.sort;
        const isCurrentlyAsc = header.classList.contains('asc');
        const newDirection = isCurrentlyAsc ? 'desc' : 'asc';
        
        // Reset les en-têtes
        document.querySelectorAll('th[data-sort]').forEach(h => {
            h.classList.remove('asc', 'desc');
        });
        
        // Mettre à jour l'en-tête actuel
        header.classList.add(newDirection);
        
        // Trier le tableau
        this.sortTable(sortBy, newDirection);
        
        // Mettre à jour le tri courant
        this.currentSort = { column: sortBy, direction: newDirection };
    }

    sortTable(sortBy, direction) {
        const table = document.getElementById('employeeTable');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('.employee-row:not([style*="display: none"])'));
        
        if (rows.length === 0) return;
        
        const sortedRows = rows.sort((a, b) => {
            let aValue, bValue;
            
            switch (sortBy) {
                case 'name':
                    aValue = a.querySelector('.name').textContent.trim();
                    bValue = b.querySelector('.name').textContent.trim();
                    break;
                case 'email':
                    aValue = a.querySelector('.email-cell').textContent.trim();
                    bValue = b.querySelector('.email-cell').textContent.trim();
                    break;
                case 'position':
                    aValue = a.querySelector('.position-badge').textContent.trim();
                    bValue = b.querySelector('.position-badge').textContent.trim();
                    break;
                case 'salary':
                    aValue = this.parseSalary(a.querySelector('.salary-cell').textContent);
                    bValue = this.parseSalary(b.querySelector('.salary-cell').textContent);
                    break;
                case 'hire_date':
                    aValue = new Date(a.querySelector('.date-cell').textContent.replace(' ', ''));
                    bValue = new Date(b.querySelector('.date-cell').textContent.replace(' ', ''));
                    break;
                default:
                    return 0;
            }
            
            return this.compareValues(aValue, bValue, direction);
        });
        
        // Réorganiser les lignes dans le DOM
        sortedRows.forEach(row => tbody.appendChild(row));
        
        // Animation de tri
        this.animateSort(sortedRows);
    }

    parseSalary(salaryText) {
        const number = salaryText.replace(/[^\d]/g, '');
        return parseInt(number, 10) || 0;
    }

    compareValues(a, b, direction) {
        if (a < b) return direction === 'asc' ? -1 : 1;
        if (a > b) return direction === 'asc' ? 1 : -1;
        return 0;
    }

    animateSort(rows) {
        rows.forEach((row, index) => {
            row.style.transition = 'all 0.3s ease';
            row.style.transform = 'translateX(20px)';
            row.style.opacity = '0';
            
            setTimeout(() => {
                row.style.transform = 'translateX(0)';
                row.style.opacity = '1';
            }, index * 50);
        });
    }

    initializeDeleteConfirmations() {
        const deleteButtons = document.querySelectorAll('.action-btn.delete');
        deleteButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                if (!confirm('Êtes-vous sûr de vouloir supprimer cet employé ? Cette action est irréversible.')) {
                    e.preventDefault();
                }
            });
        });
    }
}

// Initialisation du dashboard quand le DOM est chargé
document.addEventListener('DOMContentLoaded', function() {
    new EmployeeDashboard();
    
    // Ajout des styles pour la surbrillance de recherche
    const style = document.createElement('style');
    style.textContent = `
        .search-highlight {
            background-color: #ffeb3b;
            padding: 0.1rem 0.2rem;
            border-radius: 2px;
            font-weight: 600;
        }
        
        th.asc .fa-sort::before {
            content: "\\f0de";
        }
        
        th.desc .fa-sort::before {
            content: "\\f0dd";
        }
    `;
    document.head.appendChild(style);
});