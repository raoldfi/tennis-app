/* Teams Page JavaScript */

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

class TeamsPage {
    constructor() {
        this.init();
    }

    init() {
        console.log('🎾 Teams Page Starting Initialization...');
        console.log('TennisUI available:', typeof TennisUI !== 'undefined');
        console.log('TennisTeams available:', typeof TennisTeams !== 'undefined');
        this.setupTableInteractions();
        this.initializeTooltips();
        console.log('🎾 Teams Page Initialized');
    }

    // ==================== TABLE INTERACTIONS ====================

    setupTableInteractions() {
        // Setup event delegation for export and delete buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.team-export-btn')) {
                const btn = e.target.closest('.team-export-btn');
                const teamId = btn.dataset.teamId;
                const teamName = btn.dataset.teamName;
                this.exportSingleTeam(teamId, teamName);
            }
            
            if (e.target.closest('.team-delete-btn')) {
                const btn = e.target.closest('.team-delete-btn');
                const teamId = btn.dataset.teamId;
                const teamName = btn.dataset.teamName;
                this.deleteTeam(teamId, teamName);
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

    // ==================== TEAM OPERATIONS ====================

    async deleteTeam(teamId, teamName) {
        const confirmed = await TennisUI.showConfirmDialog(
            'Delete Team',
            `Are you sure you want to delete team "${teamName}"? This action cannot be undone and may affect matches involving this team.`,
            'Delete Team',
            'btn-tennis-danger'
        );

        if (!confirmed) return;

        try {
            const result = await TennisUI.apiCall(`/api/teams/${teamId}`, {
                method: 'DELETE'
            });

            TennisUI.showNotification(result.message || 'Team deleted successfully!', 'success');
            
            // Reload page to reflect changes
            setTimeout(() => window.location.reload(), 1000);
            
        } catch (error) {
            TennisUI.showNotification(
                error.message || 'Failed to delete team. Please try again.',
                'danger'
            );
        }
    }

    exportSingleTeam(teamId, teamName) {
        // Export single team functionality
        console.log(`Exporting team ${teamId}: ${teamName}`);
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
    window.teamsPage = new TeamsPage();
});

// Make TeamsPage available globally
window.TeamsPage = TeamsPage;

// Note: TennisTeams is now defined in main.js as a global class