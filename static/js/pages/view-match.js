/* View Match Page JavaScript */

class ViewMatchPage {
    constructor(matchId) {
        this.matchId = matchId;
        this.init();
    }

    init() {
        // Initialize tooltips for action buttons
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        console.log('🎾 View Match Page Initialized for match:', this.matchId);
    }

    // Schedule match function
    scheduleMatch(matchId = null) {
        const targetMatchId = matchId || this.matchId;
        
        // Show loading in modal content
        TennisUI.setModalContent('scheduleMatchModal', 'scheduleModalContent', 
            '<div class="text-center py-4"><div class="tennis-spinner"></div><p class="mt-2">Loading scheduling options...</p></div>'
        );
        
        // Show the modal
        TennisUI.showModal('scheduleMatchModal');
        
        // Load scheduling form
        TennisUI.apiCall(`/api/matches/${targetMatchId}/schedule`)
            .then(data => {
                TennisUI.setModalContent('scheduleMatchModal', 'scheduleModalContent', data.html);
            })
            .catch(error => {
                TennisUI.setModalContent('scheduleMatchModal', 'scheduleModalContent', 
                    `<div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i>
                        Error loading scheduling options: ${error.message}
                    </div>`
                );
            });
    }

    // Clear schedule function
    async clearSchedule(matchId = null) {
        const targetMatchId = matchId || this.matchId;
        
        const confirmed = await TennisUI.showConfirmDialog(
            'Clear Schedule',
            'Are you sure you want to clear the schedule for this match? This action cannot be undone.',
            'Clear Schedule',
            'btn-tennis-warning'
        );

        if (!confirmed) return;
        
        try {
            const result = await TennisUI.apiCall(`/api/matches/${targetMatchId}/schedule`, {
                method: 'DELETE'
            });

            TennisUI.showNotification(result.message || 'Match schedule cleared successfully', 'success');
            setTimeout(() => location.reload(), 1500);
            
        } catch (error) {
            TennisUI.showNotification(`Failed to clear schedule: ${error.message}`, 'danger');
        }
    }

    // Submit schedule form (called from dynamically loaded content)
    submitSchedule() {
        const form = document.getElementById('scheduleForm');
        if (!form) {
            TennisUI.showNotification('Schedule form not found', 'danger');
            return;
        }
        
        if (!TennisUI.validateForm('scheduleForm')) {
            return;
        }
        
        const formData = new FormData(form);
        
        TennisUI.setFormLoading('scheduleForm', true);
        
        TennisUI.apiCall(`/api/matches/${this.matchId}/schedule`, {
            method: 'POST',
            body: formData
        })
        .then(result => {
            TennisUI.hideModal('scheduleMatchModal');
            TennisUI.showNotification(result.message || 'Match scheduled successfully', 'success');
            setTimeout(() => location.reload(), 1500);
        })
        .catch(error => {
            TennisUI.showNotification(`Failed to schedule match: ${error.message}`, 'danger');
        })
        .finally(() => {
            TennisUI.setFormLoading('scheduleForm', false);
        });
    }
}

// Make ViewMatchPage available globally
window.ViewMatchPage = ViewMatchPage;

// Global functions for onclick handlers (required by templates)
window.scheduleMatch = function(matchId) {
    if (window.viewMatchPage) {
        window.viewMatchPage.scheduleMatch(matchId);
    }
};

window.clearSchedule = function(matchId) {
    if (window.viewMatchPage) {
        window.viewMatchPage.clearSchedule(matchId);
    }
};

window.submitSchedule = function() {
    if (window.viewMatchPage) {
        window.viewMatchPage.submitSchedule();
    }
};