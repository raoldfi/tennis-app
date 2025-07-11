/* Matches Page JavaScript */

class MatchesPage {
    constructor(leagues = []) {
        this.currentMatchId = null;
        this.leagues = leagues;
        this.init();
    }

    init() {
        this.checkBootstrapAvailability();
        this.initializeDryRunCheckbox();
        this.initializeScopeRadios();
        this.initializeFilterForm();
        this.initializeTableInteractions();
        this.initializeTooltips();
        this.initializeScheduledMatchesTable();
        this.cleanupSchedulingState();
        console.log('🎾 Matches page initialized');
    }

    checkBootstrapAvailability() {
        if (typeof bootstrap === 'undefined') {
            console.error('❌ Bootstrap is not available! Modal functionality will not work.');
            return false;
        }
        if (typeof bootstrap.Modal === 'undefined') {
            console.error('❌ Bootstrap.Modal is not available! Modal functionality will not work.');
            return false;
        }
        console.log('✅ Bootstrap Modal is available');
        return true;
    }

    // ==================== INITIALIZATION METHODS ====================

    initializeDryRunCheckbox() {
        const dryRunCheckbox = document.getElementById('dry-run-checkbox');
        if (dryRunCheckbox) {
            dryRunCheckbox.addEventListener('change', function() {
                const btn = document.getElementById('auto-schedule-modal-btn');
                const text = document.getElementById('auto-schedule-modal-text');
                const description = document.getElementById('auto-schedule-description');
                
                if (this.checked) {
                    btn.className = 'btn btn-primary';
                    btn.innerHTML = '<i class="fas fa-eye"></i> <span id="auto-schedule-modal-text">Preview Auto-Schedule</span>';
                    description.textContent = 'This will show you which matches can be automatically scheduled without making any changes.';
                } else {
                    btn.className = 'btn btn-tennis-warning';
                    btn.innerHTML = '<i class="fas fa-magic"></i> <span id="auto-schedule-modal-text">Execute Auto-Schedule</span>';
                    description.textContent = 'This will actually schedule the matches to available facilities and time slots.';
                }
            });
        }
    }

    initializeScopeRadios() {
        const scopeRadios = document.querySelectorAll('input[name="scope"]');
        scopeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                const leagueSelection = document.getElementById('leagueSelection');
                if (leagueSelection) {
                    leagueSelection.style.display = this.value === 'league' ? 'block' : 'none';
                }
            });
        });
    }

    initializeFilterForm() {
        const filterForm = document.querySelector('.tennis-form');
        if (!filterForm || !filterForm.closest('.tennis-card')) return;
        
        // Auto-submit on select changes for better UX
        const selects = filterForm.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', function() {
                // Small delay to allow user to see the change
                setTimeout(() => {
                    filterForm.submit();
                }, 100);
            });
        });
        
        // Clear search on Escape key
        const searchInput = filterForm.querySelector('input[name="search_query"]');
        if (searchInput) {
            searchInput.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    this.value = '';
                    filterForm.submit();
                }
            });
        }
    }

    initializeTableInteractions() {
        const table = document.querySelector('.table-hover');
        if (!table) return;
        
        // Add enhanced hover effects for better UX
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.addEventListener('mouseenter', function() {
                this.style.transform = 'scale(1.01)';
                this.style.transition = 'transform 0.2s ease';
            });
            
            row.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1)';
            });
        });
        
        // Performance optimization for large tables
        if (rows.length > 100) {
            console.log('Large table detected, optimizing interactions');
            // Reduce animation complexity for performance
            rows.forEach(row => {
                row.addEventListener('mouseenter', function() {
                    this.style.transform = 'translateX(1px)';
                    this.style.transition = 'transform 0.1s ease';
                });
                
                row.addEventListener('mouseleave', function() {
                    this.style.transform = 'translateX(0)';
                });
            });
        }
    }

    initializeTooltips() {
        // Use TennisUI's existing tooltip initialization if available
        if (typeof TennisUI.initializeTooltips === 'function') {
            TennisUI.initializeTooltips();
        } else {
            // Fallback tooltip initialization
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    initializeScheduledMatchesTable() {
        // Initialize the enhanced scheduled matches table component with schedule button support
        TennisUI.initializeScheduledMatchesTable();
    }

    cleanupSchedulingState() {
        // Clean up any stale scheduling indicators
        TennisUI.cleanupSchedulingState();
    }

    // ==================== BULK OPERATION MODALS ====================

    showBulkAutoScheduleModal() {
        this.createCustomBulkModal(
            'bulkAutoScheduleModal',
            'bulkAutoScheduleForm',
            'Auto-Schedule Matches',
            'fas fa-magic',
            [
                { value: 'all', label: 'All unscheduled matches' },
                { value: 'league', label: 'Specific league only' },
                { value: 'selected', label: 'Currently filtered matches only' }
            ],
            'This will attempt to automatically schedule unscheduled matches to available facilities and time slots.',
            'btn-tennis-primary',
            'Preview Auto-Schedule',
            () => this.handleBulkAutoSchedule()
        );
    }

    showBulkUnscheduleModal() {
        this.createCustomBulkModal(
            'bulkUnscheduleModal',
            'bulkUnscheduleForm',
            'Unschedule Matches',
            'fas fa-calendar-times',
            [
                { value: 'all', label: 'All scheduled matches' },
                { value: 'league', label: 'Scheduled matches in specific league' },
                { value: 'selected', label: 'Currently filtered scheduled matches only' }
            ],
            '<strong>Warning:</strong> This will remove scheduling information from selected matches. This action cannot be undone.',
            'btn-tennis-danger',
            'Unschedule Matches',
            () => this.handleBulkUnschedule()
        );
    }

    showBulkDeleteModal() {
        this.createCustomBulkModal(
            'bulkDeleteModal',
            'bulkDeleteForm',
            'Delete Matches',
            'fas fa-trash',
            [
                { value: 'unscheduled', label: 'All unscheduled matches only' },
                { value: 'league', label: 'Unscheduled matches in specific league' },
                { value: 'selected', label: 'Currently filtered unscheduled matches' }
            ],
            '<strong>Warning:</strong> Only unscheduled matches can be deleted for safety. This action cannot be undone.',
            'btn-tennis-danger',
            'Delete Matches',
            () => this.handleBulkDelete()
        );
    }

    createCustomBulkModal(modalId, formId, title, icon, scopeOptions, message, buttonClass, buttonText, handler) {
        // Check if Bootstrap is available
        if (!this.checkBootstrapAvailability()) {
            alert('Bootstrap is not available. Modal functionality will not work. Please refresh the page.');
            return;
        }

        // Remove existing modal if it exists
        const existingModal = document.getElementById(modalId);
        if (existingModal) existingModal.remove();

        const needsLeagueSelection = scopeOptions.some(option => option.value === 'league');
        
        const modalHTML = `
            <div class="modal fade" id="${modalId}" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content tennis-card">
                        <div class="modal-header tennis-section-header">
                            <h5 class="modal-title tennis-section-title">
                                <i class="${icon}"></i> ${title}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body tennis-card-body">
                            <form id="${formId}">
                                <div class="tennis-form-group">
                                    <label class="tennis-form-label">Scope</label>
                                    ${scopeOptions.map((option, index) => `
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="scope" value="${option.value}" 
                                                   id="${option.value}Option" ${index === 0 ? 'checked' : ''}>
                                            <label class="form-check-label" for="${option.value}Option">
                                                ${option.label}
                                            </label>
                                        </div>
                                    `).join('')}
                                </div>
                                
                                ${needsLeagueSelection ? `
                                <div class="tennis-form-group" id="leagueSelection" style="display: none;">
                                    <label for="bulkLeagueSelect" class="tennis-form-label">Select League</label>
                                    <select class="tennis-form-control" id="bulkLeagueSelect" name="league_id">
                                        <option value="">Choose a league...</option>
                                        ${this.leagues.map(league => `<option value="${league.id}">${league.name}</option>`).join('')}
                                    </select>
                                </div>
                                ` : ''}
                                
                                ${modalId === 'bulkAutoScheduleModal' ? `
                                <div class="tennis-form-group">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="dryRunCheckbox" name="dry_run" value="true" checked>
                                        <label class="form-check-label" for="dryRunCheckbox">
                                            <strong>Preview Only (Dry Run)</strong>
                                        </label>
                                    </div>
                                    <div class="tennis-form-text">Check to preview changes without actually scheduling matches</div>
                                </div>
                                ` : ''}
                                
                                <div class="tennis-status tennis-status-scheduled">
                                    <i class="fas fa-info-circle"></i>
                                    ${message}
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn-tennis-outline" data-bs-dismiss="modal">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                            <button type="button" class="${buttonClass}" id="modalActionBtn">
                                <i class="${icon}"></i> ${buttonText}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Initialize Bootstrap modal with proper configuration
        const modalElement = document.getElementById(modalId);
        if (!modalElement) {
            console.error('Modal element not found:', modalId);
            return;
        }
        
        // Configure modal with proper options
        const modal = new bootstrap.Modal(modalElement, {
            backdrop: 'static',  // Prevent closing by clicking backdrop
            keyboard: true,      // Allow closing with Escape
            focus: true         // Focus on modal when opened
        });
        
        console.log('🎾 Modal created:', modalId, modal);
        console.log('🎾 Modal element classes:', modalElement.className);
        console.log('🎾 Modal backdrop setting:', modal._config.backdrop);
        
        // Set up event handlers after a short delay to ensure DOM is ready
        setTimeout(() => {
            // Set up scope radio handlers
            if (needsLeagueSelection) {
                modalElement.querySelectorAll('input[name="scope"]').forEach(radio => {
                    radio.addEventListener('change', function() {
                        const leagueSelection = modalElement.querySelector('#leagueSelection');
                        if (leagueSelection) {
                            leagueSelection.style.display = this.value === 'league' ? 'block' : 'none';
                        }
                    });
                });
            }
            
            // Handle dry run checkbox for auto-schedule
            if (modalId === 'bulkAutoScheduleModal') {
                const dryRunCheckbox = modalElement.querySelector('#dryRunCheckbox');
                const actionBtn = modalElement.querySelector('#modalActionBtn');
                
                if (dryRunCheckbox && actionBtn) {
                    dryRunCheckbox.addEventListener('change', function() {
                        if (this.checked) {
                            actionBtn.innerHTML = '<i class="fas fa-eye"></i> Preview Auto-Schedule';
                            actionBtn.className = 'btn-tennis-primary';
                        } else {
                            actionBtn.innerHTML = '<i class="fas fa-magic"></i> Execute Auto-Schedule';
                            actionBtn.className = 'btn-tennis-warning';
                        }
                    });
                }
            }
            
            // Handle action button click
            const actionBtn = modalElement.querySelector('#modalActionBtn');
            if (actionBtn) {
                console.log('🎾 Action button found:', actionBtn);
                actionBtn.addEventListener('click', (e) => {
                    console.log('🎾 Action button clicked!', e);
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🎾 Calling handler...');
                    handler();
                });
            } else {
                console.error('🎾 Action button not found!');
            }
            
            // Handle cancel button click
            const cancelBtn = modalElement.querySelector('[data-bs-dismiss="modal"]');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    modal.hide();
                });
            }
        }, 100);
        
        // Clean up when modal is hidden
        modalElement.addEventListener('hidden.bs.modal', () => {
            modalElement.remove();
        });
        
        // Show modal
        modal.show();
    }

    // ==================== BULK OPERATION HANDLERS ====================

    handleBulkAutoSchedule() {
        const formData = new FormData(document.getElementById('bulkAutoScheduleForm'));
        const isDryRun = formData.get('dry_run') === 'true';
        TennisUI.addCurrentFiltersToFormData(formData, 'selected');
        
        // Store form data for later use by preview modal buttons
        this.lastFormData = {};
        for (let [key, value] of formData.entries()) {
            this.lastFormData[key] = value;
        }
        
        console.log('Auto-schedule:', { isDryRun, scope: formData.get('scope') });
        console.log('🎾 Stored form data for preview buttons:', this.lastFormData);
        
        // Custom success callback to handle dry-run vs execution
        const customSuccessCallback = (result) => {
            if (result.dry_run) {
                // Show preview results
                this.displayAutoSchedulePreview(result);
            } else {
                // Show execution results
                if (result.warning && result.failed_count > 0) {
                    TennisUI.showNotification(
                        result.message || `Auto-scheduled ${result.scheduled_count} of ${result.total_count} matches. ${result.failed_count} could not be scheduled.`,
                        'warning',
                        15000,
                        {
                            showRefresh: true,
                            refreshText: 'Refresh Page',
                            onRefresh: () => this.preserveSortAndReload()
                        }
                    );
                } else {
                    TennisUI.showNotification(result.message || 'All matches scheduled successfully!', 'success');
                    setTimeout(() => this.preserveSortAndReload(), 1500);
                }
            }
        };

        // Use modified executeBulkOperation with custom callback
        this.executeBulkOperationWithRefresh(
            'Bulk Auto-Schedule',
            '/api/bulk-auto-schedule',
            formData,
            'bulkAutoScheduleModal',
            customSuccessCallback
        );
    }

    displayAutoSchedulePreview(result) {
        // Close the original modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('bulkAutoScheduleModal'));
        if (modal) modal.hide();
        
        // Store the seed for reproducible execution
        if (result.seed) {
            window.lastAutoScheduleSeed = result.seed;
            console.log('🌱 SEED DEBUG: Stored seed for future execution:', result.seed);
            console.log('🌱 SEED DEBUG: typeof stored seed:', typeof result.seed);
        } else {
            console.warn('🌱 SEED DEBUG: No seed found in result!', result);
        }
        
        // Create preview modal content
        let previewHtml = `
            <div class="modal fade" id="autoSchedulePreviewModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-eye"></i> Auto-Schedule Preview Results
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row mb-3">
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="display-6 text-primary">${result.total_matches}</div>
                                        <small class="text-muted">Total Matches</small>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="display-6 text-success">${result.scheduled}</div>
                                        <small class="text-muted">Would Schedule</small>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="display-6 text-danger">${result.failed}</div>
                                        <small class="text-muted">Cannot Schedule</small>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <div class="display-6 text-warning">${result.average_quality_score || 0}</div>
                                        <small class="text-muted">Avg Quality Score</small>
                                    </div>
                                </div>
                            </div>
        `;

        if (result.scheduled > 0) {
            previewHtml += `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Good news!</strong> ${result.scheduled} matches can be automatically scheduled.
                </div>
            `;
        }

        if (result.failed > 0) {
            previewHtml += `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>Note:</strong> ${result.failed} matches cannot be scheduled due to conflicts or lack of available facilities.
                </div>
            `;
        }

        previewHtml += `
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Close Preview
                            </button>
                            <button type="button" class="btn btn-outline-primary" onclick="window.matchesPage.tryAutoScheduleAgain()">
                                <i class="fas fa-redo"></i> Try Again
                            </button>
        `;
        
        if (result.scheduled > 0) {
            previewHtml += `
                <button type="button" class="btn btn-success" onclick="window.matchesPage.executeSchedulingFromPreview()">
                    <i class="fas fa-play"></i> Execute Scheduling
                </button>
            `;
        }
        
        previewHtml += `
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page and show it
        document.body.insertAdjacentHTML('beforeend', previewHtml);
        const previewModal = new bootstrap.Modal(document.getElementById('autoSchedulePreviewModal'));
        previewModal.show();
        
        // Clean up modal when hidden
        document.getElementById('autoSchedulePreviewModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }

    executeSchedulingFromPreview() {
        console.log('🎾 Execute Scheduling from Preview called');
        
        // Close preview modal
        const previewModal = bootstrap.Modal.getInstance(document.getElementById('autoSchedulePreviewModal'));
        if (previewModal) previewModal.hide();
        
        // Check if we have stored form data
        if (!this.lastFormData) {
            console.error('🎾 No stored form data found for execution!');
            TennisUI.showNotification('Error: Form data not available. Please try auto-schedule again.', 'danger');
            return;
        }
        
        console.log('🎾 Using stored form data:', this.lastFormData);
        
        // Recreate FormData from stored data
        const formData = new FormData();
        for (let [key, value] of Object.entries(this.lastFormData)) {
            formData.set(key, value);
        }
        
        // Override to execute (not dry-run)
        formData.set('dry_run', 'false');
        
        // Use the same seed from the preview for reproducible results
        if (window.lastAutoScheduleSeed) {
            formData.set('seed', window.lastAutoScheduleSeed);
            console.log('🌱 SEED DEBUG: Using stored seed for execution:', window.lastAutoScheduleSeed);
        } else {
            console.warn('🌱 SEED DEBUG: No stored seed found! This execution may produce different results than the preview.');
        }
        
        const customSuccessCallback = (result) => {
            TennisUI.showNotification(result.message || 'Matches scheduled successfully!', 'success');
            setTimeout(() => this.preserveSortAndReload(), 1500);
        };

        this.executeBulkOperationWithRefresh(
            'Execute Auto-Schedule',
            '/api/bulk-auto-schedule',
            formData,
            null, // No modal to close
            customSuccessCallback
        );
    }

    tryAutoScheduleAgain() {
        console.log('🎾 Try Auto-Schedule Again called');
        
        // Close preview modal
        const previewModal = bootstrap.Modal.getInstance(document.getElementById('autoSchedulePreviewModal'));
        if (previewModal) previewModal.hide();
        
        // Check if we have stored form data
        if (!this.lastFormData) {
            console.error('🎾 No stored form data found for retry!');
            TennisUI.showNotification('Error: Form data not available. Please try auto-schedule again.', 'danger');
            return;
        }
        
        console.log('🎾 Using stored form data for retry:', this.lastFormData);
        
        // Re-run the same auto-schedule operation with the same parameters
        setTimeout(() => {
            // Recreate FormData from stored data
            const formData = new FormData();
            for (let [key, value] of Object.entries(this.lastFormData)) {
                formData.set(key, value);
            }
            
            // Ensure dry_run is set to true for preview
            formData.set('dry_run', 'true');
            TennisUI.addCurrentFiltersToFormData(formData, 'selected');
            
            const customSuccessCallback = (result) => {
                // Show the preview results again
                this.displayAutoSchedulePreview(result);
            };

            this.executeBulkOperationWithRefresh(
                'Try Auto-Schedule Again',
                '/api/bulk-auto-schedule',
                formData,
                null, // No modal to close
                customSuccessCallback
            );
        }, 300); // Small delay to ensure smooth transition
    }

    // Helper function for bulk operations with refresh capability
    executeBulkOperationWithRefresh(title, endpoint, formData, modalId, successCallback) {
        // Show loading state
        TennisUI.showNotification(`${title}: Processing...`, 'info', 3000);
        
        fetch(endpoint, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Close modal if specified
            if (modalId) {
                const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
                if (modal) modal.hide();
            }
            
            // Call custom success callback
            if (successCallback) {
                successCallback(data);
            } else {
                TennisUI.showNotification(data.message || 'Operation completed successfully!', 'success');
                setTimeout(() => this.preserveSortAndReload(), 1500);
            }
        })
        .catch(error => {
            TennisUI.showNotification(error.message || 'Operation failed', 'danger');
        });
    }

    handleBulkUnschedule() {
        const formData = new FormData(document.getElementById('bulkUnscheduleForm'));
        TennisUI.addCurrentFiltersToFormData(formData, 'selected');
        
        const customSuccessCallback = (result) => {
            if (result.warning) {
                TennisUI.showNotification(
                    result.message || 'Unscheduling completed with some issues.',
                    'warning',
                    12000,
                    {
                        showRefresh: true,
                        refreshText: 'Refresh Page',
                        onRefresh: () => window.location.reload()
                    }
                );
            } else {
                TennisUI.showNotification(result.message || 'Matches unscheduled successfully!', 'success');
                setTimeout(() => this.preserveSortAndReload(), 1500);
            }
        };

        this.executeBulkOperationWithRefresh(
            'Bulk Unschedule',
            '/api/bulk-unschedule',
            formData,
            'bulkUnscheduleModal',
            customSuccessCallback
        );
    }

    handleBulkDelete() {
        const formData = new FormData(document.getElementById('bulkDeleteForm'));
        TennisUI.addCurrentFiltersToFormData(formData, 'selected');
        
        const customSuccessCallback = (result) => {
            TennisUI.showNotification(result.message || 'Matches deleted successfully!', 'success');
            setTimeout(() => this.preserveSortAndReload(), 1500);
        };

        this.executeBulkOperationWithRefresh(
            'Bulk Delete',
            '/api/bulk-delete',
            formData,
            'bulkDeleteModal',
            customSuccessCallback
        );
    }

    // ==================== INDIVIDUAL MATCH OPERATIONS ====================

    async scheduleMatch(matchId) {
        this.currentMatchId = matchId;
        
        try {
            // Use TennisUI for modal management
            TennisUI.setModalContent('scheduleMatchModal', 'scheduleMatchContent', 
                '<div class="text-center py-4"><div class="tennis-spinner"></div><p class="mt-2">Loading match details...</p></div>'
            );
            
            TennisUI.showModal('scheduleMatchModal');
            
            // Use TennisUI for API calls
            const data = await TennisUI.apiCall(`/api/matches/${matchId}/schedule-form`);
            TennisUI.setModalContent('scheduleMatchModal', 'scheduleMatchContent', data.html);
            
        } catch (error) {
            TennisUI.setModalContent('scheduleMatchModal', 'scheduleMatchContent', 
                `<div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    Error loading match details: ${error.message}
                </div>`
            );
        }
    }

    async unscheduleMatch(matchId, matchDescription) {
        // Use TennisUI for confirmation dialogs
        const confirmed = await TennisUI.showConfirmDialog(
            'Unschedule Match',
            `Are you sure you want to remove the schedule for "${matchDescription}"?`,
            'Unschedule',
            'btn-tennis-warning'
        );

        if (!confirmed) return;

        try {
            // Use TennisUI for API calls
            const result = await TennisUI.apiCall(`/matches/${matchId}/schedule`, {
                method: 'DELETE'
            });

            // Use TennisUI for notifications
            TennisUI.showNotification(result.message || 'Match unscheduled successfully!', 'success');
            setTimeout(() => this.preserveSortAndReload(), 1000);
            
        } catch (error) {
            TennisUI.showNotification(error.message || 'Failed to unschedule match.', 'danger');
        }
    }

    async deleteMatch(matchId, matchDescription) {
        // Use TennisUI for confirmation dialogs
        const confirmed = await TennisUI.showConfirmDialog(
            'Delete Match',
            `Are you sure you want to delete "${matchDescription}"? This action cannot be undone.`,
            'Delete Match',
            'btn-tennis-danger'
        );

        if (!confirmed) return;

        try {
            // Use TennisUI for API calls
            const result = await TennisUI.apiCall(`/matches/${matchId}`, {
                method: 'DELETE'
            });

            // Use TennisUI for notifications
            TennisUI.showNotification(result.message || 'Match deleted successfully!', 'success');
            setTimeout(() => this.preserveSortAndReload(), 1000);
            
        } catch (error) {
            TennisUI.showNotification(error.message || 'Failed to delete match.', 'danger');
        }
    }

    // ==================== SCHEDULE MODAL FORM HANDLERS ====================

    submitSchedule() {
        const form = document.getElementById('scheduleForm');
        if (!form || !TennisUI.validateForm('scheduleForm')) {
            return;
        }
        
        const formData = new FormData(form);
        
        // Use TennisUI for form loading states
        TennisUI.setFormLoading('scheduleForm', true);
        
        // Use TennisUI for API calls
        TennisUI.apiCall(`/matches/${this.currentMatchId}/schedule`, {
            method: 'POST',
            body: formData
        })
        .then(result => {
            TennisUI.hideModal('scheduleMatchModal');
            TennisUI.showNotification(result.message || 'Match scheduled successfully', 'success');
            setTimeout(() => this.preserveSortAndReload(), 1500);
        })
        .catch(error => {
            TennisUI.showNotification(`Failed to schedule match: ${error.message}`, 'danger');
        })
        .finally(() => {
            TennisUI.setFormLoading('scheduleForm', false);
        });
    }

    clearSchedule() {
        // Use TennisUI for confirmation dialogs
        TennisUI.showConfirmDialog(
            'Clear Schedule',
            'Are you sure you want to clear the schedule for this match?',
            'Clear Schedule',
            'btn-tennis-warning'
        ).then(confirmed => {
            if (confirmed) {
                // Use TennisUI for API calls
                TennisUI.apiCall(`/matches/${this.currentMatchId}/schedule`, {
                    method: 'DELETE'
                })
                .then(result => {
                    TennisUI.hideModal('scheduleMatchModal');
                    TennisUI.showNotification(result.message || 'Match schedule cleared successfully', 'success');
                    setTimeout(() => this.preserveSortAndReload(), 1500);
                })
                .catch(error => {
                    TennisUI.showNotification(`Failed to clear schedule: ${error.message}`, 'danger');
                });
            }
        });
    }

    // ==================== UTILITY FUNCTIONS ====================

    preserveSortAndReload() {
        // Use TennisUI's reload method if available to preserve sort state
        if (typeof TennisUI !== 'undefined' && typeof TennisUI.preserveSortAndReload === 'function') {
            TennisUI.preserveSortAndReload();
        } else {
            // Fallback to regular reload
            window.location.reload();
        }
    }

    updateBulkOperationButtons(selectedCount) {
        const bulkButton = document.getElementById('bulkOperationsDropdown');
        if (bulkButton) {
            if (selectedCount > 0) {
                bulkButton.innerHTML = `<i class="fas fa-tasks"></i> Bulk Operations (${selectedCount})`;
                bulkButton.classList.remove('btn-tennis-primary');
                bulkButton.classList.add('btn-tennis-warning');
            } else {
                bulkButton.innerHTML = '<i class="fas fa-tasks"></i> Bulk Operations';
                bulkButton.classList.remove('btn-tennis-warning');
                bulkButton.classList.add('btn-tennis-primary');
            }
        }
    }
}

// Make MatchesPage available globally
window.MatchesPage = MatchesPage;

// Global functions for onclick handlers (required by templates)
window.handleBulkAutoSchedule = function() {
    if (window.matchesPage) {
        window.matchesPage.handleBulkAutoSchedule();
    }
};

window.handleBulkUnschedule = function() {
    if (window.matchesPage) {
        window.matchesPage.handleBulkUnschedule();
    }
};

window.handleBulkDelete = function() {
    if (window.matchesPage) {
        window.matchesPage.handleBulkDelete();
    }
};

window.scheduleMatch = function(matchId) {
    if (window.matchesPage) {
        window.matchesPage.scheduleMatch(matchId);
    }
};

window.unscheduleMatch = function(matchId, matchDescription) {
    if (window.matchesPage) {
        window.matchesPage.unscheduleMatch(matchId, matchDescription);
    }
};

window.deleteMatch = function(matchId, matchDescription) {
    if (window.matchesPage) {
        window.matchesPage.deleteMatch(matchId, matchDescription);
    }
};

window.submitSchedule = function() {
    if (window.matchesPage) {
        window.matchesPage.submitSchedule();
    }
};

window.clearSchedule = function() {
    if (window.matchesPage) {
        window.matchesPage.clearSchedule();
    }
};