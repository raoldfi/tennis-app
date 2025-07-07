/* Leagues Page JavaScript */

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

class LeaguesPage {
    constructor() {
        this.init();
    }

    init() {
        this.initializeFilters();
        this.initializeTableInteractions();
        this.initializeTooltips();
        console.log('🎾 Leagues Page Initialized');
    }

    // ==================== FILTER FUNCTIONALITY ====================

    initializeFilters() {
        const yearFilter = document.getElementById('yearFilter');
        const divisionFilter = document.getElementById('divisionFilter');
        const searchInput = document.getElementById('searchInput');
        const rows = document.querySelectorAll('#leaguesTableBody tr');
        
        if (!rows.length) return;
        
        const years = new Set();
        const divisions = new Set();
        
        rows.forEach(row => {
            const year = row.dataset.leagueYear;
            const division = row.dataset.leagueDivision;
            
            if (year) years.add(year);
            if (division) divisions.add(division);
        });
        
        // Populate year filter
        if (yearFilter && years.size > 0) {
            const sortedYears = Array.from(years).sort((a, b) => b - a);
            sortedYears.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year;
                yearFilter.appendChild(option);
            });
        }
        
        // Populate division filter
        if (divisionFilter && divisions.size > 0) {
            const sortedDivisions = Array.from(divisions).sort();
            sortedDivisions.forEach(division => {
                const option = document.createElement('option');
                option.value = division;
                option.textContent = division;
                divisionFilter.appendChild(option);
            });
        }
        
        // Add event listeners for filters
        if (yearFilter) {
            yearFilter.addEventListener('change', () => this.applyFilters());
        }
        if (divisionFilter) {
            divisionFilter.addEventListener('change', () => this.applyFilters());
        }
        if (searchInput) {
            searchInput.addEventListener('input', () => this.applyFilters());
        }
    }

    applyFilters() {
        const searchTerm = document.getElementById('searchInput')?.value.toLowerCase() || '';
        const selectedYear = document.getElementById('yearFilter')?.value || '';
        const selectedDivision = document.getElementById('divisionFilter')?.value || '';
        
        const rows = document.querySelectorAll('#leaguesTableBody tr');
        let visibleCount = 0;
        
        rows.forEach(row => {
            const leagueName = row.querySelector('.league-name')?.textContent.toLowerCase() || '';
            const leagueYear = row.dataset.leagueYear || '';
            const leagueDivision = row.dataset.leagueDivision || '';
            
            const matchesSearch = searchTerm === '' || leagueName.includes(searchTerm);
            const matchesYear = selectedYear === '' || leagueYear === selectedYear;
            const matchesDivision = selectedDivision === '' || leagueDivision === selectedDivision;
            
            const isVisible = matchesSearch && matchesYear && matchesDivision;
            row.style.display = isVisible ? '' : 'none';
            
            if (isVisible) visibleCount++;
        });
        
        // Update result counts
        const resultCount = document.getElementById('resultCount');
        const tableResultCount = document.getElementById('tableResultCount');
        if (resultCount) resultCount.textContent = `${visibleCount} leagues`;
        if (tableResultCount) tableResultCount.textContent = visibleCount;
        
        // Show/hide no results message
        const noResults = document.getElementById('noResults');
        if (noResults) {
            noResults.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }

    // ==================== TABLE INTERACTIONS ====================

    initializeTableInteractions() {
        // Add click handlers for league name cells
        document.querySelectorAll('.league-name-cell').forEach(cell => {
            cell.style.cursor = 'pointer';
        });

        // Setup event delegation for league operations
        document.addEventListener('click', (e) => {
            if (e.target.closest('.league-delete-btn')) {
                const btn = e.target.closest('.league-delete-btn');
                const leagueId = btn.dataset.leagueId;
                const leagueName = btn.dataset.leagueName;
                this.deleteLeague(leagueId, leagueName);
            }
            
            if (e.target.closest('.league-export-btn')) {
                const btn = e.target.closest('.league-export-btn');
                const leagueId = btn.dataset.leagueId;
                const leagueName = btn.dataset.leagueName;
                this.exportSingleLeague(leagueId, leagueName);
            }
        });
        
        console.log('Table interactions setup complete');
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

    // ==================== LEAGUE OPERATIONS ====================

    async deleteLeague(leagueId, leagueName) {
        const confirmed = await TennisUI.showConfirmDialog(
            'Delete League',
            `Are you sure you want to delete league "${leagueName}"? This action cannot be undone and will also remove all teams and matches associated with this league.`,
            'Delete League',
            'btn-tennis-danger'
        );

        if (!confirmed) return;

        try {
            const result = await TennisUI.apiCall(`/api/leagues/${leagueId}`, {
                method: 'DELETE'
            });

            TennisUI.showNotification(result.message || 'League deleted successfully!', 'success');
            
            // Reload page to reflect changes
            setTimeout(() => window.location.reload(), 1000);
            
        } catch (error) {
            TennisUI.showNotification(
                error.message || 'Failed to delete league. Please try again.',
                'danger'
            );
        }
    }

    exportSingleLeague(leagueId, leagueName) {
        // Export single league functionality
        console.log(`Exporting league ${leagueId}: ${leagueName}`);
        TennisUI.showNotification('Export functionality not yet implemented', 'info');
    }

    showHelp() {
        // Show help modal or information
        TennisUI.showNotification('Help functionality not yet implemented', 'info');
    }

    downloadExample() {
        // Download example YAML functionality
        console.log('Downloading example YAML');
        TennisUI.showNotification('Download example functionality not yet implemented', 'info');
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    window.leaguesPage = new LeaguesPage();
});

// Make LeaguesPage available globally
window.LeaguesPage = LeaguesPage;