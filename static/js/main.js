/* Common JavaScript utilities for Tennis UI System v2.1 */




class TennisUI {
    // ==================== INITIALIZATION ====================
    
    static init() {
        console.log('🎾 Tennis UI System v2.1 Initialized');
        console.log('Bootstrap available:', typeof bootstrap !== 'undefined');
        console.log('Document ready state:', document.readyState);
        this.initializeFlashMessages();
        this.initializeTooltips();
        this.initializeSearchTables();
        this.initializeScheduledMatchesTable(); 
        this.initializeSortableTables();
        this.loadStyles();
    }

    static initializeFlashMessages() {
        // Auto-hide flash messages after 5 seconds
        document.querySelectorAll('.alert').forEach(alert => {
            if (!alert.querySelector('.btn-close')) return;
            
            setTimeout(() => {
                if (alert.parentNode && !alert.classList.contains('fade')) {
                    alert.classList.add('fade');
                    setTimeout(() => {
                        if (alert.parentNode) alert.remove();
                    }, 150);
                }
            }, 5000);
        });
    }

    static initializeTooltips() {
        // Initialize Bootstrap tooltips if available
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    static initializeSearchTables() {
        // Add search functionality to tables with search inputs
        document.querySelectorAll('input[data-table-search]').forEach(input => {
            const tableId = input.getAttribute('data-table-search');
            const table = document.getElementById(tableId);
            if (!table) return;

            input.addEventListener('input', (e) => {
                this.filterTable(table, e.target.value);
            });
        });
    }

    static initializeSortableTables() {
        // Add sortable functionality to tennis tables
        document.querySelectorAll('.tennis-table').forEach(table => {
            this.makeSortable(table);
        });
    }

    static makeSortable(table) {
        const headers = table.querySelectorAll('thead th:not(.no-sort)');
        
        headers.forEach((header, index) => {
            // Don't make actions columns sortable by default
            if (header.textContent.toLowerCase().includes('action')) {
                return;
            }
            
            header.classList.add('sortable');
            header.style.cursor = 'pointer';
            header.title = `Click to sort by ${header.textContent.trim()}`;
            
            header.addEventListener('click', () => {
                this.sortTable(table, index, header);
            });
        });
    }

    static sortTable(table, columnIndex, header) {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length <= 1) return;

        // Determine sort direction
        const isAscending = !header.classList.contains('sort-asc');
        
        // Clear all other sort indicators
        table.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc', 'sort-active');
        });
        
        // Set current sort indicator
        header.classList.add('sort-active');
        header.classList.add(isAscending ? 'sort-asc' : 'sort-desc');

        // Sort rows
        const sortedRows = rows.sort((a, b) => {
            const aCell = a.cells[columnIndex];
            const bCell = b.cells[columnIndex];
            
            if (!aCell || !bCell) return 0;
            
            let aValue = this.extractSortValue(aCell);
            let bValue = this.extractSortValue(bCell);
            
            // Handle different data types
            const comparison = this.compareValues(aValue, bValue);
            return isAscending ? comparison : -comparison;
        });

        // Clear tbody and append sorted rows
        tbody.innerHTML = '';
        sortedRows.forEach(row => tbody.appendChild(row));

        // Update row styling (maintain alternating colors)
        this.updateRowStyling(tbody);
    }

    static extractSortValue(cell) {
        // Priority order for extracting sort values:
        // 1. data-sort attribute
        // 2. first link text
        // 3. first badge text
        // 4. visible text content
        
        const dataSortValue = cell.getAttribute('data-sort');
        if (dataSortValue !== null) {
            return dataSortValue;
        }
        
        // Check for links (team names, facility names, etc.)
        const link = cell.querySelector('a');
        if (link) {
            return link.textContent.trim();
        }
        
        // Check for badges (IDs, statuses, etc.)
        const badge = cell.querySelector('.badge, .tennis-badge');
        if (badge) {
            return badge.textContent.trim();
        }
        
        // Check for specific patterns
        const textContent = cell.textContent.trim();
        
        // Check for dates (MM/DD/YYYY format)
        const dateMatch = textContent.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
        if (dateMatch) {
            // Convert to sortable format: YYYY-MM-DD
            const [, month, day, year] = dateMatch;
            return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
        }
        
        // Check for times (like "10:00 AM")
        const timeMatch = textContent.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (timeMatch) {
            const [, hour, minute, period] = timeMatch;
            let hour24 = parseInt(hour);
            if (period.toUpperCase() === 'PM' && hour24 !== 12) hour24 += 12;
            if (period.toUpperCase() === 'AM' && hour24 === 12) hour24 = 0;
            return `${hour24.toString().padStart(2, '0')}:${minute}`;
        }
        
        return textContent;
    }

    static compareValues(a, b) {
        // Handle empty values
        if (!a && !b) return 0;
        if (!a) return 1;
        if (!b) return -1;
        
        // Try numeric comparison first
        const numA = parseFloat(a);
        const numB = parseFloat(b);
        
        if (!isNaN(numA) && !isNaN(numB)) {
            return numA - numB;
        }
        
        // Fall back to string comparison
        return a.toString().toLowerCase().localeCompare(b.toString().toLowerCase());
    }

    static updateRowStyling(tbody) {
        // Ensure alternating row colors are maintained after sorting
        const rows = tbody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            row.classList.remove('odd', 'even');
            if (index % 2 === 0) {
                row.classList.add('even');
            } else {
                row.classList.add('odd');
            }
        });
    }
    
    /**
     * Validate form by ID (convenience method)
     * @param {string} formId - The ID of the form to validate
     * @returns {boolean} - True if form is valid
     */
    static validateForm(formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.error(`Form with ID '${formId}' not found`);
            return false;
        }
        
        return TennisForms.validateForm(form);
    }

    /**
     * Show a modal by ID
     * @param {string} modalId - The ID of the modal to show
     */
    static showModal(modalId) {
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        } else {
            console.error(`Modal with ID '${modalId}' not found`);
        }
    }
    
    /**
     * Hide a modal by ID
     * @param {string} modalId - The ID of the modal to hide
     */
    static hideModal(modalId) {
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
            }
        } else {
            console.error(`Modal with ID '${modalId}' not found`);
        }
    }
    
    /**
     * Set modal content
     * @param {string} modalId - The ID of the modal
     * @param {string} contentId - The ID of the content element within the modal
     * @param {string} content - The HTML content to set
     */
    static setModalContent(modalId, contentId, content) {
        const contentElement = document.getElementById(contentId);
        if (contentElement) {
            contentElement.innerHTML = content;
        } else {
            console.error(`Content element with ID '${contentId}' not found in modal '${modalId}'`);
        }
    }
    
    static filterTable(table, searchTerm) {
        const rows = table.querySelectorAll('tbody tr');
        const term = searchTerm.toLowerCase();
        let visibleCount = 0;

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const isVisible = text.includes(term);
            row.style.display = isVisible ? '' : 'none';
            if (isVisible) visibleCount++;
        });

        // Show/hide "no results" message
        const noResults = document.getElementById('noResults');
        if (noResults) {
            noResults.style.display = visibleCount === 0 && searchTerm ? 'block' : 'none';
        }
    }

    static loadStyles() {
        // Ensure required styles are loaded
        if (!document.getElementById('tennis-ui-styles')) {
            const styles = document.createElement('style');
            styles.id = 'tennis-ui-styles';
            styles.textContent = `
                .tennis-notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    min-width: 350px;
                    max-width: 500px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
                    animation: slideInRight 0.4s ease;
                    border-radius: 8px;
                    border: none;
                }
                
                .tennis-notification-enhanced {
                    background: rgba(255, 255, 255, 0.98) !important;
                    backdrop-filter: blur(10px);
                    border-left: 5px solid;
                    font-weight: 500;
                    padding: 1rem 1.25rem;
                }
                
                .tennis-notification-enhanced.alert-success {
                    border-left-color: #28a745;
                    background: rgba(40, 167, 69, 0.95) !important;
                    color: white;
                }
                
                .tennis-notification-enhanced.alert-danger {
                    border-left-color: #dc3545;
                    background: rgba(220, 53, 69, 0.95) !important;
                    color: white;
                }
                
                .tennis-notification-enhanced.alert-warning {
                    border-left-color: #ffc107;
                    background: rgba(255, 193, 7, 0.95) !important;
                    color: #212529;
                }
                
                .tennis-notification-enhanced.alert-info {
                    border-left-color: #007bff;
                    background: rgba(0, 123, 255, 0.95) !important;
                    color: white;
                }
                
                .tennis-notification-icon {
                    flex-shrink: 0;
                    margin-top: 2px;
                }
                
                .tennis-notification-content {
                    line-height: 1.4;
                }
                
                .tennis-notification-message {
                    font-size: 0.95rem;
                    font-weight: 500;
                }
                
                .tennis-notification:hover {
                    transform: translateX(-5px);
                    box-shadow: 0 12px 35px rgba(0,0,0,0.4);
                    transition: all 0.2s ease;
                }
                
                .fade-out {
                    animation: slideOutRight 0.3s ease forwards;
                }
                
                @keyframes slideInRight {
                    from { 
                        transform: translateX(100%); 
                        opacity: 0; 
                    }
                    to { 
                        transform: translateX(0); 
                        opacity: 1; 
                    }
                }
                
                @keyframes slideOutRight {
                    from { 
                        transform: translateX(0); 
                        opacity: 1; 
                    }
                    to { 
                        transform: translateX(100%); 
                        opacity: 0; 
                    }
                }
                
                /* Stack multiple notifications */
                .tennis-notification:nth-child(n+2) {
                    margin-top: 10px;
                }
                
                /* Enhanced close button for dark backgrounds */
                .tennis-notification .btn-close-white {
                    filter: brightness(0) invert(1);
                    opacity: 0.8;
                }
                
                .tennis-notification .btn-close-white:hover {
                    opacity: 1;
                    transform: scale(1.1);
                }
            `;
            document.head.appendChild(styles);
        }
    }


    // Add these methods to the TennisUI class in shared_scripts.html
    
    /**
     * Enhanced scheduled matches table functions with schedule button support
     */
    static initializeScheduledMatchesTable(tableSelector = '.tennis-matches-table') {
        const tables = document.querySelectorAll(tableSelector);
        tables.forEach(table => {
            // Add click handlers for action buttons
            table.addEventListener('click', (e) => {
                const target = e.target.closest('.action-btn');
                if (!target) return;
    
                const matchId = target.getAttribute('data-match-id');
                const action = target.getAttribute('data-action');
    
                switch (action) {
                    case 'view':
                        this.viewMatchDetails(matchId);
                        break;
                    case 'unschedule':
                        const description = target.getAttribute('data-description');
                        this.unscheduleMatch(matchId, description);
                        break;
                    case 'edit':
                        this.editMatchSchedule(matchId);
                        break;
                    case 'schedule':
                        this.scheduleMatch(matchId);
                        break;
                }
            });
        });
    
        // Also handle mobile card actions
        const mobileCards = document.querySelectorAll('.mobile-day-group-content');
        mobileCards.forEach(container => {
            container.addEventListener('click', (e) => {
                const target = e.target.closest('[data-action]');
                if (!target) return;
    
                const matchId = target.getAttribute('data-match-id');
                const action = target.getAttribute('data-action');
    
                switch (action) {
                    case 'unschedule':
                        e.preventDefault();
                        const description = target.getAttribute('data-description');
                        this.unscheduleMatch(matchId, description);
                        break;
                    case 'schedule':
                        e.preventDefault();
                        this.scheduleMatch(matchId);
                        break;
                }
            });
        });
    
        // Initialize schedule button helpers
        this.initializeScheduleButtonHelpers();
    }
    
    /**
     * Navigate to scheduling form for a match
     */
    static scheduleMatch(matchId) {
        // Track scheduling state for better UX
        this.trackSchedulingState(matchId, true);
        
        // Navigate to the scheduling form
        window.location.href = `/matches/${matchId}/schedule`;
    }
    
    /**
     * Enhanced unscheduleMatch method with better error handling
     */
    static async unscheduleMatch(matchId, description) {
        const confirmed = await this.showConfirmDialog(
            'Unschedule Match',
            `Are you sure you want to unschedule "${description}"?<br><small class="text-muted">This will remove all scheduling information for this match.</small>`,
            'Unschedule',
            'btn-tennis-warning'
        );
    
        if (!confirmed) return;
    
        try {
            // Show loading state
            const buttons = document.querySelectorAll(`[data-match-id="${matchId}"][data-action="unschedule"]`);
            buttons.forEach(btn => {
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                btn.dataset.originalText = originalText;
            });
    
            const result = await this.apiCall(`/matches/${matchId}/schedule`, {
                method: 'DELETE'
            });
    
            this.showNotification(result.message || 'Match unscheduled successfully!', 'success');
            
            // Reload page after short delay
            setTimeout(() => window.location.reload(), 1000);
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to unschedule match.', 'danger');
            
            // Restore button state
            const buttons = document.querySelectorAll(`[data-match-id="${matchId}"][data-action="unschedule"]`);
            buttons.forEach(btn => {
                btn.disabled = false;
                if (btn.dataset.originalText) {
                    btn.innerHTML = btn.dataset.originalText;
                    delete btn.dataset.originalText;
                }
            });
        }
    }
    
    /**
     * Navigate to reschedule form (same as schedule form, but will show current data)
     */
    static editMatchSchedule(matchId) {
        this.scheduleMatch(matchId); // Same form handles both cases
    }
    
    /**
     * Helper method for better user feedback on schedule buttons
     */
    static initializeScheduleButtonHelpers() {
        // Add tooltips to schedule buttons
        const scheduleButtons = document.querySelectorAll('.action-btn-schedule');
        scheduleButtons.forEach(button => {
            if (!button.title) {
                button.title = 'Schedule this match at optimal dates and times';
            }
            
            // Add subtle animation on hover
            button.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-1px) scale(1.02)';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0) scale(1)';
            });
        });
    
        // Add progress indicators for matches that are being scheduled
        const schedulingMatches = JSON.parse(sessionStorage.getItem('schedulingMatches') || '[]');
        schedulingMatches.forEach(matchId => {
            const scheduleBtn = document.querySelector(`[data-match-id="${matchId}"].action-btn-schedule`);
            if (scheduleBtn) {
                scheduleBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                scheduleBtn.disabled = true;
                scheduleBtn.title = 'Scheduling in progress...';
            }
        });
    }
    
    /**
     * Track scheduling state across page navigation
     */
    static trackSchedulingState(matchId, isScheduling = true) {
        const schedulingMatches = JSON.parse(sessionStorage.getItem('schedulingMatches') || '[]');
        
        if (isScheduling && !schedulingMatches.includes(matchId)) {
            schedulingMatches.push(matchId);
            sessionStorage.setItem('schedulingMatches', JSON.stringify(schedulingMatches));
        } else if (!isScheduling) {
            const filtered = schedulingMatches.filter(id => id !== matchId);
            sessionStorage.setItem('schedulingMatches', JSON.stringify(filtered));
        }
    }
    
    /**
     * Clean up scheduling state indicators
     */
    static cleanupSchedulingState() {
        // Clean up any stale scheduling indicators
        const schedulingMatches = JSON.parse(sessionStorage.getItem('schedulingMatches') || '[]');
        if (schedulingMatches.length > 0) {
            // Clear after 30 seconds (in case user navigated away during scheduling)
            setTimeout(() => {
                sessionStorage.removeItem('schedulingMatches');
            }, 30000);
        }
    }
    
    /**
     * Format day name from date string
     */
    static formatDayName(dateStr) {
        if (!dateStr || dateStr === 'TBD') return 'TBD';
        
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', { weekday: 'short' });
        } catch {
            return 'TBD';
        }
    }
    
    /**
     * Get status class for match
     */
    static getMatchStatusClass(match) {
        if (!match.scheduled_times || match.scheduled_times.length === 0) {
            return 'status-unscheduled';
        }
        
        const expectedLines = match.expected_lines || 3;
        const scheduledLines = match.scheduled_times.length;
        
        if (scheduledLines >= expectedLines) {
            return 'status-scheduled';
        } else {
            return 'status-partial';
        }
    }

    // ==================== API UTILITIES ====================

    /**
     * Make API calls with standardized error handling
     * @param {string} url - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise} - Response data
     */
    static async apiCall(url, options = {}) {
        try {
            const defaultHeaders = {};
            
            // Only add Content-Type for JSON data
            if (options.body && typeof options.body === 'string') {
                defaultHeaders['Content-Type'] = 'application/json';
            }
            
            const response = await fetch(url, {
                headers: {
                    ...defaultHeaders,
                    ...options.headers
                },
                ...options
            });
    
            // Always try to parse JSON response (for both success and error)
            let data;
            try {
                data = await response.json();
            } catch (parseError) {
                // If JSON parsing fails, create a generic error object
                data = { 
                    error: `Server returned non-JSON response: ${response.status} ${response.statusText}` 
                };
            }
    
            // For error responses, throw an error with the server's error message
            if (!response.ok) {
                const errorMessage = data.error || data.message || `HTTP ${response.status}: ${response.statusText}`;
                console.error('API Error Response:', {
                    status: response.status,
                    statusText: response.statusText,
                    url: url,
                    errorData: data
                });
                
                // Create an error object that includes all the response data
                const error = new Error(errorMessage);
                error.status = response.status;
                error.responseData = data;
                throw error;
            }
    
            return data;
            
        } catch (error) {
            // If it's a network error or other fetch error, wrap it
            if (!error.status) {
                console.error('Network/Fetch error:', error);
                error.message = `Network error: ${error.message}`;
            }
            throw error;
        }
    }

    // ==================== BULK OPERATIONS ====================

    /**
     * Execute a bulk operation with standardized UI updates
     * @param {string} operation - Operation name (for logging)
     * @param {string} url - API endpoint
     * @param {FormData|Object} data - Data to send
     * @param {string} modalId - Modal to close on success
     * @param {Function} successCallback - Optional success callback
     */
    static async executeBulkOperation(operation, url, data, modalId, successCallback = null) {
        const submitBtn = document.querySelector(`#${modalId} .btn-tennis-warning, #${modalId} .btn-tennis-danger, #${modalId} .btn-tennis-success, #${modalId} .btn-primary`);
        
        // Set button loading state
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('btn-loading');
            const originalText = submitBtn.innerHTML;
            submitBtn.setAttribute('data-original-text', originalText);
        }

        try {
            const options = {
                method: 'POST',
            };

            if (data instanceof FormData) {
                options.body = data;
            } else {
                options.body = JSON.stringify(data);
                options.headers = {
                    'Content-Type': 'application/json'
                };
            }

            const result = await this.apiCall(url, options);

            // Handle success
            this.showNotification(result.message || `${operation} completed successfully`, 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
            if (modal) modal.hide();
            
            // Execute success callback
            if (successCallback) {
                successCallback(result);
            } else {
                // Default: reload page after short delay
                setTimeout(() => window.location.reload(), 500);
            }

        } catch (error) {
            this.showNotification(error.message || `${operation} failed`, 'danger');
            console.error(`${operation} error:`, error);
        } finally {
            // Reset button state
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('btn-loading');
                const originalText = submitBtn.getAttribute('data-original-text');
                if (originalText) {
                    submitBtn.innerHTML = originalText;
                }
            }
        }
    }

    /**
     * Create a standardized bulk operation modal
     */
    static createBulkOperationModal(operation, title, scopeOptions, alertType, alertMessage, handler, leagues = []) {
        const iconMap = {
            'auto-schedule': 'magic',
            'unschedule': 'calendar-times',
            'delete': 'trash'
        };
    
        const buttonClassMap = {
            'auto-schedule': 'btn-tennis-warning',
            'unschedule': 'btn-tennis-warning', 
            'delete': 'btn-tennis-danger'
        };
    
        const formId = `bulk${operation.charAt(0).toUpperCase() + operation.slice(1).replace('-', '')}Form`;
        const modalId = `bulk${operation.charAt(0).toUpperCase() + operation.slice(1).replace('-', '')}Modal`;
    
        const needsLeagueSelection = scopeOptions.some(option => option.value === 'league');
        
        const modalContent = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-${iconMap[operation]}"></i> ${title}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="${formId}" class="tennis-form">
                            <div class="mb-3">
                                <label class="form-label">
                                    <i class="fas fa-crosshairs"></i> Scope <span class="required">*</span>
                                </label>
                                <div class="form-check-container">
                                    ${scopeOptions.map((option, index) => `
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="scope" value="${option.value}" 
                                                   id="${operation}${option.value}" ${index === 0 ? 'checked' : ''}>
                                            <label class="form-check-label" for="${operation}${option.value}">
                                                ${option.label}
                                            </label>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                            
                            ${needsLeagueSelection ? `
                            <div class="mb-3" id="leagueSelection" style="display: none;">
                                <label for="bulkLeagueSelect" class="form-label">
                                    <i class="fas fa-trophy"></i> Select League
                                </label>
                                <select class="form-select" id="bulkLeagueSelect" name="league_id">
                                    <option value="">Choose a league...</option>
                                    ${leagues.map(league => `<option value="${league.id}">${league.name}</option>`).join('')}
                                </select>
                            </div>
                            ` : ''}
                            
                            <div class="alert alert-${alertType}">
                                <i class="fas fa-${alertType === 'danger' ? 'exclamation-triangle' : 'info-circle'}"></i>
                                ${alertMessage}
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                        <button type="button" class="btn ${buttonClassMap[operation]}" onclick="${handler.name}()">
                            <i class="fas fa-${iconMap[operation]}"></i> ${title}
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        const existingModal = document.getElementById(modalId);
        if (existingModal) existingModal.remove();
        
        const modalElement = document.createElement('div');
        modalElement.className = 'modal fade tennis-modal';
        modalElement.id = modalId;
        modalElement.innerHTML = modalContent;
        document.body.appendChild(modalElement);
        
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    
        if (needsLeagueSelection) {
            setTimeout(() => {
                const scopeRadios = document.querySelectorAll(`#${modalId} input[name="scope"]`);
                const leagueSelection = document.getElementById('leagueSelection');
                
                scopeRadios.forEach(radio => {
                    radio.addEventListener('change', function() {
                        if (leagueSelection) {
                            leagueSelection.style.display = this.value === 'league' ? 'block' : 'none';
                        }
                    });
                });
            }, 100);
        }
    
        modal._element.addEventListener('hidden.bs.modal', () => {
            document.getElementById(modalId).remove();
        });
    }
    
    /**
     * Add current URL filters to FormData for "selected" scope operations
     */
    static addCurrentFiltersToFormData(formData, targetScope = 'selected') {
        if (formData.get('scope') === targetScope) {
            const urlParams = new URLSearchParams(window.location.search);
            for (const [key, value] of urlParams) {
                if (!formData.has(key)) {
                    formData.append(key, value);
                }
            }
        }
    }
    


    // ==================== FORM UTILITIES ====================

    /**
     * Set form loading state
     * @param {string} formId - The ID of the form
     * @param {boolean} loading - Whether form is loading
     * @param {string} buttonSelector - CSS selector for the submit button
     */
    static setFormLoading(formId, loading, buttonSelector = 'button[type="submit"], .btn-tennis-success, .btn-tennis-primary') {
        const form = document.getElementById(formId);
        if (!form) {
            console.error(`Form with ID '${formId}' not found`);
            return;
        }

        const button = form.querySelector(buttonSelector);
        
        if (loading) {
            form.classList.add('tennis-loading');
            
            // Create loading overlay if it doesn't exist
            let overlay = form.querySelector('.tennis-loading-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.className = 'tennis-loading-overlay';
                overlay.style.cssText = `
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(255, 255, 255, 0.8);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                    border-radius: var(--tennis-border-radius);
                `;
                overlay.innerHTML = '<div class="tennis-spinner"></div>';
                form.style.position = 'relative';
                form.appendChild(overlay);
            }
            
            // Disable and update submit button
            if (button) {
                button.disabled = true;
                if (!button.dataset.originalText) {
                    button.dataset.originalText = button.innerHTML;
                }
                button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
                button.classList.add('btn-loading');
            }

            // Disable all form inputs
            const inputs = form.querySelectorAll('input, select, textarea, button');
            inputs.forEach(input => {
                if (!input.hasAttribute('data-loading-disabled')) {
                    input.disabled = true;
                    input.setAttribute('data-loading-disabled', 'true');
                }
            });

        } else {
            form.classList.remove('tennis-loading');
            
            // Remove loading overlay
            const overlay = form.querySelector('.tennis-loading-overlay');
            if (overlay) {
                overlay.remove();
            }
            
            // Re-enable submit button
            if (button) {
                button.disabled = false;
                button.classList.remove('btn-loading');
                if (button.dataset.originalText) {
                    button.innerHTML = button.dataset.originalText;
                    delete button.dataset.originalText;
                }
            }

            // Re-enable form inputs
            const inputs = form.querySelectorAll('[data-loading-disabled]');
            inputs.forEach(input => {
                input.disabled = false;
                input.removeAttribute('data-loading-disabled');
            });
        }
    }

    /**
     * Serialize form data to object
     * @param {string} formId - The ID of the form
     * @returns {Object} - Form data as object
     */
    static serializeForm(formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.error(`Form with ID '${formId}' not found`);
            return {};
        }

        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            if (data[key]) {
                // Handle multiple values (like checkboxes)
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        return data;
    }

    // ==================== LOADING SPINNER UTILITIES ====================

    /**
     * Show a notification message
     * @param {string} message - Message to display
     * @param {string} type - Alert type (success, danger, warning, info)
     * @param {number} duration - Auto-hide duration in milliseconds (default: 8000)
     * @param {Object} options - Additional options
     * @param {boolean} options.showRefresh - Show refresh button (default: false)
     * @param {string} options.refreshText - Text for refresh button (default: 'Refresh')
     * @param {Function} options.onRefresh - Custom refresh callback (default: page reload)
     */
    static showNotification(message, type = 'info', duration = 8000, options = {}) {
        const { 
            showRefresh = false, 
            refreshText = 'Refresh', 
            onRefresh = () => window.location.reload() 
        } = options;
    
        // Create notification element with enhanced styling
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show tennis-notification tennis-notification-enhanced`;
        
        // Add refresh button if requested
        const refreshButton = showRefresh ? `
            <button type="button" class="btn btn-sm btn-outline-light ms-2 tennis-refresh-btn" onclick="handleNotificationRefresh(this)">
                <i class="fas fa-sync-alt"></i> ${refreshText}
            </button>
        ` : '';
        
        notification.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="tennis-notification-icon me-3">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-triangle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} fa-lg"></i>
                </div>
                <div class="tennis-notification-content flex-grow-1">
                    <div class="tennis-notification-message">${message}</div>
                </div>
                <div class="tennis-notification-actions">
                    ${refreshButton}
                    <button type="button" class="btn-close btn-close-white ms-2" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            </div>
        `;
    
        // Store refresh callback on the notification element
        if (showRefresh) {
            notification._refreshCallback = onRefresh;
        }
    
        // Add to page
        document.body.appendChild(notification);
    
        // Add click-to-dismiss functionality
        notification.addEventListener('click', function(e) {
            if (!e.target.closest('.btn-close') && !e.target.closest('.tennis-refresh-btn')) {
                // Don't dismiss when clicking buttons
                return;
            }
        });
    
        // Auto-remove after duration (if no refresh button or user preference)
        const timeoutId = setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.remove('show');
                notification.classList.add('fade-out');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, duration);
    
        // Allow manual dismissal to cancel auto-removal
        notification.addEventListener('closed.bs.alert', () => {
            clearTimeout(timeoutId);
        });
    
        // Add hover to pause auto-dismissal
        let isPaused = false;
        notification.addEventListener('mouseenter', () => {
            isPaused = true;
            clearTimeout(timeoutId);
        });
    
        notification.addEventListener('mouseleave', () => {
            if (isPaused && !showRefresh) { // Don't auto-hide if refresh button is shown
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.classList.remove('show');
                        notification.classList.add('fade-out');
                        setTimeout(() => {
                            if (notification.parentNode) {
                                notification.remove();
                            }
                        }, 300);
                    }
                }, 2000); // 2 second delay after mouse leave
            }
        });
    }

    /**
     * Show a confirmation dialog
     * @param {string} title - Dialog title
     * @param {string} message - Dialog message
     * @param {string} confirmText - Text for confirm button
     * @param {string} confirmClass - CSS class for confirm button
     * @returns {Promise<boolean>} - True if confirmed, false if cancelled
     */
    static async showConfirmDialog(title, message, confirmText = 'Confirm', confirmClass = 'btn-primary') {
        return new Promise((resolve) => {
            // Create modal HTML
            const modalId = 'tennis-confirm-dialog';
            const existingModal = document.getElementById(modalId);
            if (existingModal) {
                existingModal.remove();
            }
    
            const modalHTML = `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">${title}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <p>${message}</p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn ${confirmClass}" id="confirm-action">${confirmText}</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
    
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            const modal = new bootstrap.Modal(document.getElementById(modalId));
            
            // Handle button clicks
            document.getElementById('confirm-action').addEventListener('click', () => {
                modal.hide();
                resolve(true);
            });
    
            modal._element.addEventListener('hidden.bs.modal', () => {
                document.getElementById(modalId).remove();
                resolve(false);
            });
    
            modal.show();
        });
    }

    /**
     * Set button loading state with text
     */
    static setButtonLoading(selector, loading, loadingText = 'Loading...') {
        const buttons = typeof selector === 'string' ? document.querySelectorAll(selector) : [selector];
        
        buttons.forEach(button => {
            if (loading) {
                if (!button.dataset.originalText) {
                    button.dataset.originalText = button.innerHTML;
                }
                button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${loadingText}`;
                button.disabled = true;
            } else {
                button.disabled = false;
                if (button.dataset.originalText) {
                    button.innerHTML = button.dataset.originalText;
                    delete button.dataset.originalText;
                }
            }
        });
    }
    
    /**
     * Download file blob
     */
    static downloadFile(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
        
}

class TennisForms {
    /**
     * Initialize form validation and enhancement
     */
    static initializeFormValidation() {
        document.querySelectorAll('.tennis-form').forEach(form => {
            form.addEventListener('submit', this.handleFormSubmit.bind(this));
            
            // Add real-time validation
            form.querySelectorAll('input, select, textarea').forEach(field => {
                field.addEventListener('blur', () => this.validateField(field));
                field.addEventListener('input', () => this.clearFieldError(field));
            });
        });
    }

    static handleFormSubmit(event) {
        const form = event.target;
        const isValid = this.validateForm(form);
        
        if (!isValid) {
            event.preventDefault();
            TennisUI.showNotification('Please correct the errors in the form', 'warning');
        }
    }

    static validateForm(form) {
        let isValid = true;
        
        form.querySelectorAll('[required]').forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
      
        return isValid;
    }

    static validateField(field) {
        const value = field.value.trim();
        const isRequired = field.hasAttribute('required');
        const fieldType = field.type;
        
        // Clear previous errors
        this.clearFieldError(field);
        
        // Check required fields
        if (isRequired && !value) {
            this.showFieldError(field, 'This field is required');
            return false;
        }
        
        // Type-specific validation
        if (value) {
            switch (fieldType) {
                case 'email':
                    if (!this.isValidEmail(value)) {
                        this.showFieldError(field, 'Please enter a valid email address');
                        return false;
                    }
                    break;
                case 'number':
                    const min = field.getAttribute('min');
                    const max = field.getAttribute('max');
                    const numValue = parseFloat(value);
                    
                    if (isNaN(numValue)) {
                        this.showFieldError(field, 'Please enter a valid number');
                        return false;
                    }
                    
                    if (min !== null && numValue < parseFloat(min)) {
                        this.showFieldError(field, `Value must be at least ${min}`);
                        return false;
                    }
                    
                    if (max !== null && numValue > parseFloat(max)) {
                        this.showFieldError(field, `Value must be no more than ${max}`);
                        return false;
                    }
                    break;
            }
        }
        
        return true;
    }

    static showFieldError(field, message) {
        field.classList.add('is-invalid');
        
        let feedback = field.parentNode.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.appendChild(feedback);
        }
        
        feedback.textContent = message;
    }

    static clearFieldError(field) {
        field.classList.remove('is-invalid');
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    static isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
}

// ==================== IMPORT/EXPORT MANAGEMENT ====================

class TennisImportExport {
    static currentData = null;
    static currentAnalysis = null;

    /**
     * Show comprehensive import/export modal
     */
    static showModal(title = 'Smart Import/Export') {
        this.createImportExportModal(title);
    }

    /**
     * Create the main import/export modal
     */
    static createImportExportModal(title) {
        const modalId = 'tennis-import-export-modal';
        const existingModal = document.getElementById(modalId);
        if (existingModal) existingModal.remove();

        const modalHTML = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-exchange-alt"></i> ${title}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <!-- Tab Navigation -->
                            <ul class="nav nav-tabs mb-4" id="importExportTabs" role="tablist">
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link active" id="import-tab" data-bs-toggle="tab" data-bs-target="#import-panel" type="button">
                                        <i class="fas fa-upload"></i> Import Data
                                    </button>
                                </li>
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link" id="export-tab" data-bs-toggle="tab" data-bs-target="#export-panel" type="button">
                                        <i class="fas fa-download"></i> Export Data
                                    </button>
                                </li>
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link" id="examples-tab" data-bs-toggle="tab" data-bs-target="#examples-panel" type="button">
                                        <i class="fas fa-file-code"></i> Examples
                                    </button>
                                </li>
                            </ul>

                            <!-- Tab Content -->
                            <div class="tab-content" id="importExportTabContent">
                                ${this.createImportPanel()}
                                ${this.createExportPanel()}
                                ${this.createExamplesPanel()}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = new bootstrap.Modal(document.getElementById(modalId));

        // Initialize event listeners
        this.initializeEventListeners(modalId);
        
        modal.show();

        // Clean up on hide
        modal._element.addEventListener('hidden.bs.modal', () => {
            document.getElementById(modalId).remove();
        });

        // Load component info
        this.loadComponentInfo();
    }

    /**
     * Create import panel HTML
     */
    static createImportPanel() {
        return `
            <div class="tab-pane fade show active" id="import-panel" role="tabpanel">
                <div class="row">
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-upload"></i> Upload File</h6>
                            </div>
                            <div class="tennis-card-body">
                                <form id="import-form" enctype="multipart/form-data">
                                    <div class="mb-3">
                                        <label for="import-file" class="form-label">
                                            Choose YAML File <span class="required">*</span>
                                        </label>
                                        <input type="file" class="form-control" id="import-file" name="file" accept=".yaml,.yml" required>
                                        <div class="form-text">
                                            <i class="fas fa-info-circle"></i> 
                                            Upload any YAML file - the system automatically detects components
                                        </div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="skip-existing" name="skip_existing" checked>
                                            <label class="form-check-label" for="skip-existing">
                                                Skip existing items (recommended)
                                            </label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="validate-only" name="validate_only">
                                            <label class="form-check-label" for="validate-only">
                                                Validate only (preview without importing)
                                            </label>
                                        </div>
                                    </div>
                                    
                                    <div class="d-grid gap-2">
                                        <button type="button" class="btn btn-tennis-info" id="analyze-file-btn" disabled>
                                            <i class="fas fa-search"></i> Analyze File
                                        </button>
                                        <button type="button" class="btn btn-tennis-success" id="import-data-btn" disabled>
                                            <i class="fas fa-upload"></i> Import Data
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-info-circle"></i> File Analysis</h6>
                            </div>
                            <div class="tennis-card-body">
                                <div id="file-analysis" class="text-center text-muted">
                                    <i class="fas fa-file-upload fa-3x mb-3"></i>
                                    <p>Upload a file to see its contents analysis</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="import-results" class="mt-4" style="display: none;">
                    <div class="tennis-card">
                        <div class="tennis-card-header">
                            <h6 class="m-0"><i class="fas fa-chart-bar"></i> Import Results</h6>
                        </div>
                        <div class="tennis-card-body" id="import-results-content">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create export panel HTML
     */
    static createExportPanel() {
        return `
            <div class="tab-pane fade" id="export-panel" role="tabpanel">
                <div class="row">
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-database"></i> Complete Database Export</h6>
                            </div>
                            <div class="tennis-card-body">
                                <p class="tennis-form-text mb-3">Export your entire tennis database</p>
                                <div class="d-grid gap-2">
                                    <button type="button" class="btn btn-tennis-secondary" onclick="TennisImportExport.exportComplete('yaml')">
                                        <i class="fas fa-file-code"></i> Export as YAML
                                    </button>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.exportComplete('json')">
                                        <i class="fas fa-file-export"></i> Export as JSON
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-filter"></i> Selective Export</h6>
                            </div>
                            <div class="tennis-card-body">
                                <form id="export-form">
                                    <div class="mb-3">
                                        <label class="form-label">Select Components:</label>
                                        <div id="component-checkboxes">
                                            <!-- Populated by loadComponentInfo -->
                                        </div>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label class="form-label">Format:</label>
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="export_format" value="yaml" id="export-yaml" checked>
                                            <label class="form-check-label" for="export-yaml">YAML</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" name="export_format" value="json" id="export-json">
                                            <label class="form-check-label" for="export-json">JSON</label>
                                        </div>
                                    </div>
                                    
                                    <button type="button" class="btn btn-tennis-primary w-100" onclick="TennisImportExport.exportSelected()">
                                        <i class="fas fa-download"></i> Export Selected
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-chart-pie"></i> Current Database Contents</h6>
                            </div>
                            <div class="tennis-card-body">
                                <div id="component-info-display" class="row">
                                    <!-- Populated by loadComponentInfo -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create examples panel HTML
     */
    static createExamplesPanel() {
        return `
            <div class="tab-pane fade" id="examples-panel" role="tabpanel">
                <div class="row">
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-download"></i> Example Files</h6>
                            </div>
                            <div class="tennis-card-body">
                                <div class="d-grid gap-2">
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('complete')">
                                        <i class="fas fa-database"></i> Complete Database Example
                                    </button>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('mixed')">
                                        <i class="fas fa-puzzle-piece"></i> Mixed Components Example
                                    </button>
                                    <hr>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('leagues')">
                                        <i class="fas fa-trophy"></i> Leagues Only
                                    </button>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('facilities')">
                                        <i class="fas fa-building"></i> Facilities Only
                                    </button>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('teams')">
                                        <i class="fas fa-users"></i> Teams Only
                                    </button>
                                    <button type="button" class="btn btn-tennis-outline" onclick="TennisImportExport.downloadExample('matches')">
                                        <i class="fas fa-calendar"></i> Matches Only
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="tennis-card">
                            <div class="tennis-card-header">
                                <h6 class="m-0"><i class="fas fa-info-circle"></i> Import Tips</h6>
                            </div>
                            <div class="tennis-card-body">
                                <ul class="list-unstyled">
                                    <li class="mb-2">
                                        <i class="fas fa-check text-success"></i>
                                        Files can contain any combination of components
                                    </li>
                                    <li class="mb-2">
                                        <i class="fas fa-check text-success"></i>
                                        System automatically detects what's in your file
                                    </li>
                                    <li class="mb-2">
                                        <i class="fas fa-check text-success"></i>
                                        Use "Skip existing" to avoid duplicates
                                    </li>
                                    <li class="mb-2">
                                        <i class="fas fa-check text-success"></i>
                                        Use "Validate only" to preview before importing
                                    </li>
                                    <li class="mb-2">
                                        <i class="fas fa-check text-success"></i>
                                        Download examples to see proper format
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize event listeners
     */
    static initializeEventListeners(modalId) {
        const modal = document.getElementById(modalId);
        
        // File upload change
        const fileInput = modal.querySelector('#import-file');
        const analyzeBtn = modal.querySelector('#analyze-file-btn');
        const importBtn = modal.querySelector('#import-data-btn');
        
        fileInput.addEventListener('change', () => {
            const hasFile = fileInput.files.length > 0;
            analyzeBtn.disabled = !hasFile;
            importBtn.disabled = true;
            
            if (hasFile) {
                document.getElementById('file-analysis').innerHTML = `
                    <div class="text-center">
                        <i class="fas fa-file-alt fa-2x text-primary mb-2"></i>
                        <p class="mb-1"><strong>${fileInput.files[0].name}</strong></p>
                        <p class="text-muted">Ready to analyze</p>
                    </div>
                `;
            }
        });
        
        // Analyze button
        analyzeBtn.addEventListener('click', () => this.analyzeFile());
        
        // Import button
        importBtn.addEventListener('click', () => this.importData());
    }

    /**
     * Analyze uploaded file
     */
    static async analyzeFile() {
        const fileInput = document.getElementById('import-file');
        const file = fileInput.files[0];
        if (!file) return;

        const analyzeBtn = document.getElementById('analyze-file-btn');
        const importBtn = document.getElementById('import-data-btn');
        
        TennisUI.setButtonLoading(analyzeBtn, true, 'Analyzing...');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const result = await TennisUI.apiCall('/api/import-export/analyze', {
                method: 'POST',
                body: formData
            });

            this.currentAnalysis = result.analysis;
            this.displayAnalysis(result);
            importBtn.disabled = !result.analysis.is_valid;

        } catch (error) {
            TennisUI.showNotification(error.message || 'Failed to analyze file', 'danger');
            this.displayAnalysisError(error.message);
        } finally {
            TennisUI.setButtonLoading(analyzeBtn, false);
        }
    }

    /**
     * Display file analysis results
     */
    static displayAnalysis(result) {
        const { analysis, filename, file_size } = result;
        
        let html = `
            <div class="text-start">
                <h6 class="text-primary mb-3">
                    <i class="fas fa-file-alt"></i> ${filename}
                    <small class="text-muted">(${Math.round(file_size / 1024)} KB)</small>
                </h6>
        `;
        
        if (analysis.is_valid) {
            html += `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i> Valid YAML file with ${analysis.total_items} items
                </div>
                
                <h6>Components Found:</h6>
                <div class="mb-3">
            `;
            
            for (const [component, count] of Object.entries(analysis.component_counts)) {
                if (count > 0) {
                    const info = window.ComponentInfo?.COMPONENTS[component] || { icon: 'fas fa-circle', display_name: component };
                    html += `
                        <span class="badge bg-${info.color || 'primary'} me-2 mb-1">
                            <i class="${info.icon}"></i> ${info.display_name}: ${count}
                        </span>
                    `;
                }
            }
            
            html += '</div>';
            
            if (analysis.has_metadata) {
                html += `
                    <h6>Metadata:</h6>
                    <ul class="list-unstyled small">
                `;
                for (const [key, value] of Object.entries(analysis.metadata)) {
                    html += `<li><strong>${key}:</strong> ${value}</li>`;
                }
                html += '</ul>';
            }
        } else {
            html += `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i> ${analysis.error || 'Invalid file format'}
                </div>
            `;
        }
        
        html += '</div>';
        document.getElementById('file-analysis').innerHTML = html;
    }

    /**
     * Display analysis error
     */
    static displayAnalysisError(error) {
        document.getElementById('file-analysis').innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle"></i> 
                <strong>Analysis Failed:</strong> ${error}
            </div>
        `;
    }

    /**
     * Import data from analyzed file
     */
    static async importData() {
        const fileInput = document.getElementById('import-file');
        const file = fileInput.files[0];
        if (!file) return;

        const importBtn = document.getElementById('import-data-btn');
        const skipExisting = document.getElementById('skip-existing').checked;
        const validateOnly = document.getElementById('validate-only').checked;
        
        TennisUI.setButtonLoading(importBtn, true, validateOnly ? 'Validating...' : 'Importing...');

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('skip_existing', skipExisting);
            formData.append('validate_only', validateOnly);

            const result = await TennisUI.apiCall('/api/import-export/import', {
                method: 'POST',
                body: formData
            });

            this.displayImportResults(result);
            
            if (!validateOnly && result.success) {
                TennisUI.showNotification(
                    `Successfully imported ${result.total_imported} items!`, 
                    'success',
                    5000,
                    { showRefresh: true }
                );
            }

        } catch (error) {
            TennisUI.showNotification(error.message || 'Import failed', 'danger');
        } finally {
            TennisUI.setButtonLoading(importBtn, false);
        }
    }

    /**
     * Display import results
     */
    static displayImportResults(result) {
        const { stats, summary, validate_only } = result;
        
        let html = `
            <div class="row mb-3">
                <div class="col-md-3">
                    <div class="text-center">
                        <h5 class="text-primary">${stats.summary?.total_processed || 0}</h5>
                        <small>Processed</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h5 class="text-success">${stats.summary?.total_imported || 0}</h5>
                        <small>${validate_only ? 'Would Import' : 'Imported'}</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h5 class="text-warning">${stats.summary?.total_skipped || 0}</h5>
                        <small>Skipped</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="text-center">
                        <h5 class="text-danger">${stats.summary?.total_errors || 0}</h5>
                        <small>Errors</small>
                    </div>
                </div>
            </div>
        `;
        
        if (validate_only) {
            html += '<div class="alert alert-info"><i class="fas fa-info-circle"></i> Validation complete - no data was imported</div>';
        }
        
        // Component details
        html += '<h6>Component Details:</h6><div class="row">';
        
        for (const [component, componentStats] of Object.entries(stats)) {
            if (component === 'summary') continue;
            
            const info = window.ComponentInfo?.COMPONENTS[component];
            if (!info || !componentStats.had_data) continue;
            
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h6><i class="${info.icon}"></i> ${info.display_name}</h6>
                            <div class="d-flex justify-content-between">
                                <span>Processed: ${componentStats.processed}</span>
                                <span class="text-success">Success: ${componentStats.success_rate.toFixed(1)}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        
        document.getElementById('import-results-content').innerHTML = html;
        document.getElementById('import-results').style.display = 'block';
    }

    /**
     * Export complete database
     */
    static async exportComplete(format = 'yaml') {
        const button = event?.target;
        if (button) TennisUI.setButtonLoading(button, true, 'Exporting...');

        try {
            const response = await fetch(`/api/import-export/export?format=${format}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Export failed');
            }
            
            const blob = await response.blob();
            const filename = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || `tennis_database.${format}`;
            
            TennisUI.downloadFile(blob, filename);
            TennisUI.showNotification(`Database exported successfully as ${filename}`, 'success');
            
        } catch (error) {
            TennisUI.showNotification(error.message || 'Export failed', 'danger');
        } finally {
            if (button) TennisUI.setButtonLoading(button, false);
        }
    }

    /**
     * Export selected components
     */
    static async exportSelected() {
        const form = document.getElementById('export-form');
        const formData = new FormData(form);
        const format = formData.get('export_format') || 'yaml';
        
        const selectedComponents = [];
        document.querySelectorAll('#component-checkboxes input:checked').forEach(checkbox => {
            selectedComponents.push(checkbox.value);
        });
        
        if (selectedComponents.length === 0) {
            TennisUI.showNotification('Please select at least one component to export', 'warning');
            return;
        }

        try {
            const url = `/api/import-export/export?format=${format}&${selectedComponents.map(c => `components=${c}`).join('&')}`;
            const response = await fetch(url);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Export failed');
            }
            
            const blob = await response.blob();
            const filename = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || `tennis_export.${format}`;
            
            TennisUI.downloadFile(blob, filename);
            TennisUI.showNotification(`Selected components exported as ${filename}`, 'success');
            
        } catch (error) {
            TennisUI.showNotification(error.message || 'Export failed', 'danger');
        }
    }

    /**
     * Download example file
     */
    static async downloadExample(type) {
        try {
            const response = await fetch(`/api/import-export/examples/${type}`);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate example');
            }
            
            const blob = await response.blob();
            const filename = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || `example_${type}.yaml`;
            
            TennisUI.downloadFile(blob, filename);
            TennisUI.showNotification(`Example file ${filename} downloaded`, 'success');
            
        } catch (error) {
            TennisUI.showNotification(error.message || 'Failed to download example', 'danger');
        }
    }

    /**
     * Load component information
     */
    static async loadComponentInfo() {
        try {
            const result = await TennisUI.apiCall('/api/import-export/components');
            this.displayComponentInfo(result.components);
        } catch (error) {
            console.error('Failed to load component info:', error);
        }
    }

    /**
     * Display component information
     */
    static displayComponentInfo(components) {
        // Update checkboxes
        let checkboxHtml = '';
        for (const [component, info] of Object.entries(components)) {
            checkboxHtml += `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${component}" id="export-${component}">
                    <label class="form-check-label" for="export-${component}">
                        <i class="${info.icon}"></i> ${info.display_name} (${info.current_count})
                    </label>
                </div>
            `;
        }
        const checkboxContainer = document.getElementById('component-checkboxes');
        if (checkboxContainer) checkboxContainer.innerHTML = checkboxHtml;
        
        // Update info display
        let infoHtml = '';
        for (const [component, info] of Object.entries(components)) {
            infoHtml += `
                <div class="col-md-3 mb-3">
                    <div class="text-center">
                        <div class="stat-icon mb-2">
                            <i class="${info.icon} text-${info.color}"></i>
                        </div>
                        <h5>${info.current_count}</h5>
                        <small>${info.display_name}</small>
                    </div>
                </div>
            `;
        }
        const infoContainer = document.getElementById('component-info-display');
        if (infoContainer) infoContainer.innerHTML = infoHtml;
    }
}

// ==================== TEAMS MANAGEMENT ====================

class TennisTeams {
    /**
     * Delete a team
     */
    static async deleteTeam(teamId, teamName) {
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

    /**
     * Export single team
     */
    static exportSingleTeam(teamId, teamName) {
        console.log(`Exporting team ${teamId}: ${teamName}`);
        TennisUI.showNotification('Export functionality not yet implemented', 'info');
    }

    /**
     * Show help modal
     */
    static showHelp() {
        TennisUI.showNotification('Help functionality not yet implemented', 'info');
    }

    /**
     * Download example YAML
     */
    static downloadExample() {
        console.log('Downloading example YAML');
        TennisUI.showNotification('Download example functionality not yet implemented', 'info');
    }
}

// ==================== FACILITY MANAGEMENT ====================

class TennisFacilities {
    /**
     * Delete a facility
     */
    static async deleteFacility(facilityId, facilityName) {
        const confirmed = await TennisUI.showConfirmDialog(
            'Delete Facility',
            `Are you sure you want to delete facility "${facilityName}"? This action cannot be undone and may affect teams and matches using this facility.`,
            'Delete Facility',
            'btn-tennis-danger'
        );

        if (!confirmed) return;

        try {
            const result = await TennisUI.apiCall(`/api/facilities/${facilityId}`, {
                method: 'DELETE'
            });

            TennisUI.showNotification(result.message || 'Facility deleted successfully!', 'success');
            
            // Reload page to reflect changes
            setTimeout(() => window.location.reload(), 1000);
            
        } catch (error) {
            TennisUI.showNotification(
                error.message || 'Failed to delete facility. Please try again.',
                'danger'
            );
        }
    }
}

// ==================== GLOBAL INITIALIZATION ====================

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize TennisUI system
    TennisUI.init();
    
    // Initialize form validation
    TennisForms.initializeFormValidation();
    
    console.log('🎾 Tennis App Main.js Loaded');
});

// ==================== GLOBAL FUNCTIONS ====================

/**
 * Handle refresh button click in notifications
 */
function handleNotificationRefresh(button) {
    const notification = button.closest('.tennis-notification');
    if (notification && notification._refreshCallback) {
        // Show loading state on button
        const originalContent = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
        button.disabled = true;
        
        // Execute refresh callback
        try {
            notification._refreshCallback();
        } catch (error) {
            console.error('Refresh callback error:', error);
            // Restore button state on error
            button.innerHTML = originalContent;
            button.disabled = false;
        }
    }
}

/**
 * A function to inject the quality score description into a web page.
 * This function is used to display the quality score description in a user-friendly format.
 */
function injectQualityLegend(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const style = document.createElement('style');
  style.textContent = `
    .legend {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-width: 600px;
      font-family: "Segoe UI", sans-serif;
      font-size: 14px;
    }
    .score-line {
      display: flex;
      align-items: center;
      padding: 6px 10px;
      border-left: 6px solid;
      border-radius: 4px;
      background: #fff;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .score-line span {
      font-weight: 600;
      margin-right: 10px;
      min-width: 80px;
      white-space: nowrap;
    }
    .score-100 { border-color: #5cb85c; }
    .score-80  { border-color: #5bc0de; }
    .score-60  { border-color: #f7e300; }
    .score-40  { border-color: #f0ad4e; }
    .score-20  { border-color: #d9534f; }
  `;
  document.head.appendChild(style);

  container.innerHTML = `
    <div class="legend">
      <div class="score-line score-100"><span>100 – Optimal</span> Teams' preferred + within round</div>
      <div class="score-line score-80"><span>80 – Good</span> Teams' backup + within round</div>
      <div class="score-line score-60"><span>60 – Fair</span> League preferred + outside round</div>
      <div class="score-line score-40"><span>40 – Acceptable</span> League backup + outside round</div>
      <div class="score-line score-20"><span>20 – Poor</span> Not preferred by any team</div>
    </div>
  `;
}

// Make classes and functions available globally
window.TennisUI = TennisUI;
window.TennisForms = TennisForms;
window.TennisTeams = TennisTeams;
window.TennisImportExport = TennisImportExport;
window.TennisFacilities = TennisFacilities;
window.handleNotificationRefresh = handleNotificationRefresh;
window.injectQualityLegend = injectQualityLegend;