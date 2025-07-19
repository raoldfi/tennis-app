/* Facilities Page JavaScript */

// Component info for import/export functionality
window.ComponentInfo = {
    COMPONENTS: {
        'leagues': {
            'display_name': 'Leagues',
            'icon': 'fas fa-trophy',
            'color': 'warning'
        },
        'facilities': {
            'display_name': 'Facilities',
            'icon': 'fas fa-building',
            'color': 'info'
        },
        'teams': {
            'display_name': 'Teams',
            'icon': 'fas fa-users',
            'color': 'success'
        },
        'matches': {
            'display_name': 'Matches',
            'icon': 'fas fa-calendar',
            'color': 'primary'
        }
    }
};

class FacilitiesPage {
    constructor() {
        this.init();
    }

    init() {
        this.setupFacilityTableInteractions();
        this.initializeTooltips();
        console.log('🎾 Facilities Page Initialized');
    }

    // ==================== TABLE INTERACTIONS ====================

    setupFacilityTableInteractions() {
        const table = document.getElementById('facilitiesTable');
        if (!table) return;
        
        // Add sortable headers
        const headers = table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            // Skip action column
            if (index === headers.length - 1) return;
            
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            header.setAttribute('data-sort-column', index);
            
            // Add sort icon
            const sortIcon = document.createElement('i');
            sortIcon.className = 'fas fa-sort ms-1 opacity-50';
            header.appendChild(sortIcon);
            
            header.addEventListener('click', () => this.sortFacilityTable(index));
        });
        
        // Add row click handlers for navigation
        const rows = document.querySelectorAll('.facility-row');
        rows.forEach(row => {
            row.addEventListener('click', function(e) {
                // Don't trigger if clicking on buttons or links
                if (e.target.matches('button, button *, a, a *')) return;
                
                const facilityId = this.getAttribute('data-facility-id');
                if (facilityId) {
                    // Add visual feedback
                    this.style.backgroundColor = 'var(--tennis-gray-100)';
                    setTimeout(() => {
                        this.style.backgroundColor = '';
                    }, 200);
                    
                    // Navigate to facility details
                    window.location.href = `/facilities/${facilityId}`;
                }
            });
            
            // Add hover effect
            row.addEventListener('mouseenter', function() {
                this.style.cursor = 'pointer';
            });
        });
    }

    sortFacilityTable(columnIndex) {
        const table = document.getElementById('facilitiesTable');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const header = table.querySelectorAll('thead th')[columnIndex];
        const sortIcon = header.querySelector('i');
        
        // Determine sort direction
        const currentDirection = header.getAttribute('data-sort-direction') || 'asc';
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        
        // Reset all sort icons
        table.querySelectorAll('thead th i').forEach(icon => {
            icon.className = 'fas fa-sort ms-1 opacity-50';
        });
        
        // Update current sort icon
        sortIcon.className = `fas fa-sort-${newDirection === 'asc' ? 'up' : 'down'} ms-1`;
        header.setAttribute('data-sort-direction', newDirection);
        
        // Sort rows
        rows.sort((a, b) => {
            const aValue = a.cells[columnIndex].textContent.trim();
            const bValue = b.cells[columnIndex].textContent.trim();
            
            // Handle numeric sorting for ID column
            if (columnIndex === 0) {
                return newDirection === 'asc' 
                    ? parseInt(aValue) - parseInt(bValue)
                    : parseInt(bValue) - parseInt(aValue);
            }
            
            // Handle text sorting
            const result = aValue.localeCompare(bValue);
            return newDirection === 'asc' ? result : -result;
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
        
        //TennisUI.showNotification(`Sorted by ${header.textContent.trim()} (${newDirection})`, 'info');
    }

    initializeTooltips() {
        // Initialize tooltips for action buttons if Bootstrap is available
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    window.facilitiesPage = new FacilitiesPage();
});

// Make class available globally
window.FacilitiesPage = FacilitiesPage;