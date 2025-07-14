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
        // Use native confirm if TennisUI is not available
        let confirmed;
        if (typeof TennisUI !== 'undefined' && TennisUI.showConfirmDialog) {
            confirmed = await TennisUI.showConfirmDialog(
                'Delete Team',
                `Are you sure you want to delete team "${teamName}"? This action cannot be undone and may affect matches involving this team.`,
                'Delete Team',
                'btn-tennis-danger'
            );
        } else {
            confirmed = confirm(`Are you sure you want to delete team "${teamName}"?\n\nThis action cannot be undone and may affect matches involving this team.`);
        }

        if (!confirmed) return;

        try {
            const response = await fetch(`/teams/${teamId}/delete`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // Show success notification
                if (typeof TennisUI !== 'undefined' && TennisUI.showNotification) {
                    TennisUI.showNotification(result.message || 'Team deleted successfully!', 'success');
                } else {
                    this.showSimpleAlert(result.message || 'Team deleted successfully!', 'success');
                }
                
                // Remove the row from the table with animation
                this.removeTeamRowFromTable(teamId);
                
            } else {
                throw new Error(result.error || 'Failed to delete team');
            }
            
        } catch (error) {
            console.error('Error deleting team:', error);
            if (typeof TennisUI !== 'undefined' && TennisUI.showNotification) {
                TennisUI.showNotification(
                    error.message || 'Failed to delete team. Please try again.',
                    'danger'
                );
            } else {
                this.showSimpleAlert(error.message || 'Failed to delete team. Please try again.', 'error');
            }
        }
    }

    removeTeamRowFromTable(teamId) {
        const button = document.querySelector(`[data-team-id="${teamId}"]`);
        if (button) {
            const row = button.closest('tr');
            if (row) {
                row.style.transition = 'all 0.3s ease-out';
                row.style.opacity = '0';
                row.style.transform = 'translateX(-100%)';
                
                setTimeout(() => {
                    row.remove();
                    this.updateTeamCount();
                    
                    // Check if no teams remain and show empty state
                    const tbody = document.querySelector('.tennis-table tbody');
                    if (tbody && tbody.children.length === 0) {
                        location.reload(); // Reload to show empty state
                    }
                }, 300);
            }
        }
    }

    updateTeamCount() {
        const badge = document.querySelector('.tennis-badge-primary');
        if (badge) {
            const currentText = badge.textContent;
            const match = currentText.match(/\d+/);
            if (match) {
                const currentCount = parseInt(match[0]);
                const newCount = currentCount - 1;
                badge.textContent = `${newCount} team${newCount !== 1 ? 's' : ''}`;
            }
        }
    }

    showSimpleAlert(message, type = 'info') {
        // Fallback alert function if TennisUI is not available
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
        
        const iconClass = type === 'success' ? 'check-circle' : 
                         type === 'error' ? 'exclamation-triangle' : 
                         'info-circle';
        
        alertDiv.innerHTML = `
            <i class="fas fa-${iconClass}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
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