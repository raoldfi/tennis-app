/**
 * Schedule Match Page JavaScript
 * Handles match scheduling UI interactions, time slot selection, and API calls
 */

class ScheduleMatchUI {
    constructor() {
        this.selectedDate = null;
        this.selectedTimes = [];
        this.selectedFacilityId = null;  // Track which facility the selected times belong to
        this.facilityOptions = [];  // Store facility options for the selected date
        this.availableTimes = [];
        this.schedulingMode = 'same_time';
        this.matchId = null;
        this.linesNeeded = 3;
        this.facilityInfoId = null;
        this.init();
    }

    init() {
        // Get match info from template variables
        const matchElement = document.querySelector('[data-match-id]');
        if (matchElement) {
            this.matchId = parseInt(matchElement.dataset.matchId);
            this.linesNeeded = parseInt(matchElement.dataset.linesNeeded) || 3;
            this.facilityInfoId = matchElement.dataset.facilityInfoId ? parseInt(matchElement.dataset.facilityInfoId) : null;
        }

        this.initializeDateCards();
        this.initializeSchedulingMode();
        this.initializeButtons();
        this.updateModeDescription();
    }

    initializeDateCards() {
        document.querySelectorAll('.date-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Remove selection from other cards
                document.querySelectorAll('.date-card').forEach(c => c.classList.remove('selected'));
                
                // Select this card
                card.classList.add('selected');
                
                // Update selected date
                this.selectedDate = card.dataset.date;
                this.availableTimes = card.dataset.times ? 
                    card.dataset.times.split(',') : [];
                
                // Extract facility options for the selected date
                try {
                    this.facilityOptions = JSON.parse(card.dataset.facilityOptions || '[]');
                } catch (e) {
                    console.warn('Failed to parse facility options:', e);
                    this.facilityOptions = [];
                }
                
                // Extract time slot details for enhanced display
                this.timeSlotDetails = this.extractTimeSlotDetails(card);
                this.selectedTimes = [];
                this.selectedFacilityId = null;  // Reset facility selection
                
                this.updateSelectedDateDisplay();
                this.updateAvailableTimesDisplay();
                this.updateUI();
            });
        });
    }
    
    extractTimeSlotDetails(card) {
        // Extract time slot details from the selected card's HTML
        const timeSlotDetails = [];
        const slotElements = card.querySelectorAll('.tennis-badge');
        
        slotElements.forEach(badge => {
            const timeText = badge.textContent.trim();
            // Look for pattern like "09:00 (3/12)"
            const match = timeText.match(/(\d{2}:\d{2})\s*\((\d+)\/(\d+)\)/);
            if (match) {
                timeSlotDetails.push({
                    time: match[1],
                    available_courts: parseInt(match[2]),
                    total_courts: parseInt(match[3])
                });
            }
        });
        
        return timeSlotDetails;
    }

    initializeSchedulingMode() {
        const modeSelect = document.getElementById('scheduling-mode');
        if (modeSelect) {
            modeSelect.addEventListener('change', (e) => {
                this.schedulingMode = e.target.value;
                this.selectedTimes = []; // Clear selections when mode changes
                this.updateModeDescription();
                this.updateSelectedTimesDisplay();
                this.updateAvailableTimesDisplay(); // Re-render time slots
                this.updateScheduleButton();
                this.updateSplitTimesHelper();
            });
        }
    }

    initializeButtons() {
        const previewButton = document.getElementById('preview-button');
        const confirmButton = document.getElementById('confirm-schedule');
        
        if (previewButton) {
            previewButton.addEventListener('click', () => {
                this.showPreview();
            });
        }

        if (confirmButton) {
            confirmButton.addEventListener('click', () => {
                this.confirmSchedule();
            });
        }
    }

    updateSelectedDateDisplay() {
        const display = document.getElementById('selected-date-display');
        if (!display) return;
        
        const cardBody = display.querySelector('.tennis-card-body');
        if (this.selectedDate) {
            const dateObj = new Date(this.selectedDate + 'T00:00:00');
            const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'long' });
            cardBody.innerHTML = `
                <strong class="text-tennis-primary">${this.selectedDate}</strong><br>
                <small class="text-tennis-muted">${dayName}</small>
            `;
        } else {
            cardBody.innerHTML = '<em class="text-tennis-muted">Select a date from the left</em>';
        }
    }

    updateAvailableTimesDisplay() {
        const container = document.getElementById('available-times-container');
        if (!container) return;
        
        const cardBody = container.querySelector('.tennis-card-body');
        const section = document.getElementById('times-section');
        
        // Use enhanced facility options with time slot details
        if (this.facilityOptions && this.facilityOptions.length > 0) {
            // Generate time slots organized by facility
            let timeSlotsHtml = '';
            
            this.facilityOptions.forEach(facilityOption => {
                if (facilityOption.time_slots && facilityOption.time_slots.length > 0) {
                    timeSlotsHtml += `
                        <div class="facility-time-group mb-3">
                            <div class="facility-name text-tennis-secondary fw-bold mb-2">
                                <i class="fas fa-building me-1"></i>${facilityOption.facility_name}
                            </div>
                            <div class="time-slots-container">
                                ${facilityOption.time_slots.map(slot => {
                                    const utilizationPercent = slot.total_courts > 0 ? 
                                        ((slot.total_courts - slot.available_courts) / slot.total_courts * 100) : 0;
                                    
                                    let badgeClass = 'tennis-badge-light';
                                    if (slot.available_courts >= slot.total_courts * 0.7) {
                                        badgeClass = 'tennis-badge-success';
                                    } else if (slot.available_courts >= slot.total_courts * 0.3) {
                                        badgeClass = 'tennis-badge-warning';
                                    } else {
                                        badgeClass = 'tennis-badge-danger';
                                    }
                                    
                                    return `
                                        <div class="time-slot-enhanced d-flex align-items-center justify-content-between p-2 mb-2 border rounded time-slot" 
                                             data-time="${slot.time}" 
                                             data-facility-id="${facilityOption.facility_id}"
                                             data-available-courts="${slot.available_courts}"
                                             data-total-courts="${slot.total_courts}"
                                             style="cursor: pointer; transition: all 0.2s ease; min-width: 180px;">
                                            <div>
                                                <span class="tennis-badge ${badgeClass}">${slot.time}</span>
                                                <small class="text-muted ms-2">${slot.available_courts}/${slot.total_courts} courts</small>
                                            </div>
                                            <div class="capacity-indicator" style="width: 30px; height: 4px; background: #e9ecef; border-radius: 2px; overflow: hidden;">
                                                <div class="capacity-fill" style="width: ${100 - utilizationPercent}%; height: 100%; 
                                                    background: ${slot.available_courts >= slot.total_courts * 0.7 ? '#28a745' : 
                                                              slot.available_courts >= slot.total_courts * 0.3 ? '#ffc107' : '#dc3545'}; 
                                                    transition: width 0.3s ease;"></div>
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    `;
                }
            });
            
            cardBody.innerHTML = timeSlotsHtml;
            section.style.display = 'block';
        } else if (this.timeSlotDetails && this.timeSlotDetails.length > 0) {
            // Fallback: Generate enhanced time slots with court information (without facility grouping)
            cardBody.innerHTML = this.timeSlotDetails.map(slot => {
                const utilizationPercent = slot.total_courts > 0 ? 
                    ((slot.total_courts - slot.available_courts) / slot.total_courts * 100) : 0;
                
                let badgeClass = 'tennis-badge-light';
                if (slot.available_courts >= slot.total_courts * 0.7) {
                    badgeClass = 'tennis-badge-success';
                } else if (slot.available_courts >= slot.total_courts * 0.3) {
                    badgeClass = 'tennis-badge-warning';
                } else {
                    badgeClass = 'tennis-badge-danger';
                }
                
                return `
                    <div class="time-slot-enhanced d-flex align-items-center justify-content-between p-2 mb-2 border rounded time-slot" 
                         data-time="${slot.time}" 
                         data-facility-id="${this.facilityInfoId || ''}"
                         data-available-courts="${slot.available_courts}"
                         data-total-courts="${slot.total_courts}"
                         style="cursor: pointer; transition: all 0.2s ease; min-width: 180px;">
                        <div>
                            <span class="tennis-badge ${badgeClass}">${slot.time}</span>
                            <small class="text-muted ms-2">${slot.available_courts}/${slot.total_courts} courts</small>
                        </div>
                        <div class="capacity-indicator" style="width: 30px; height: 4px; background: #e9ecef; border-radius: 2px; overflow: hidden;">
                            <div class="capacity-fill" style="width: ${100 - utilizationPercent}%; height: 100%; 
                                background: ${slot.available_courts >= slot.total_courts * 0.7 ? '#28a745' : 
                                          slot.available_courts >= slot.total_courts * 0.3 ? '#ffc107' : '#dc3545'}; 
                                transition: width 0.3s ease;"></div>
                        </div>
                    </div>
                `;
            }).join('');
            
            section.style.display = 'block';
        } else if (this.availableTimes.length > 0) {
            // Fallback to basic time display
            cardBody.innerHTML = this.availableTimes.map(time => 
                `<span class="tennis-badge tennis-badge-light time-slot" data-time="${time}" data-facility-id="${this.facilityInfoId || ''}">${time}</span>`
            ).join('');
            
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
            return;
        }
        
        // Add click handlers to time slots
        cardBody.querySelectorAll('.time-slot').forEach(slot => {
            slot.addEventListener('click', (e) => {
                const timeElement = e.target.closest('.time-slot');
                const time = timeElement.dataset.time;
                const facilityId = timeElement.dataset.facilityId;
                this.toggleTimeSelection(time, timeElement, facilityId);
            });
        });
    }

    toggleTimeSelection(time, element, facilityId) {
        if (this.schedulingMode === 'same_time') {
            // For this mode, only allow one time selection
            document.querySelectorAll('.time-slot').forEach(slot => {
                slot.classList.remove('selected', 'tennis-badge-success');
                slot.classList.add('tennis-badge-light');
            });
            element.classList.remove('tennis-badge-light');
            element.classList.add('selected', 'tennis-badge-success');
            this.selectedTimes = [time];
            this.selectedFacilityId = facilityId;  // Track the facility for the selected time
        } else if (this.schedulingMode === 'split_times') {
            // For split times mode, allow exactly 2 time selections from the same facility
            if (this.selectedTimes.includes(time)) {
                this.selectedTimes = this.selectedTimes.filter(t => t !== time);
                element.classList.remove('selected', 'split-first', 'split-second', 'tennis-badge-primary', 'tennis-badge-secondary');
                element.classList.add('tennis-badge-light');
                // If no times left, clear facility selection
                if (this.selectedTimes.length === 0) {
                    this.selectedFacilityId = null;
                }
            } else if (this.selectedTimes.length < 2) {
                // Check if this is from the same facility (or if it's the first selection)
                if (this.selectedFacilityId === null || this.selectedFacilityId === facilityId) {
                    this.selectedTimes.push(time);
                    this.selectedFacilityId = facilityId;
                    element.classList.remove('tennis-badge-light');
                    element.classList.add('selected');
                    // Add styling to distinguish first and second slots
                    if (this.selectedTimes.length === 1) {
                        element.classList.add('split-first', 'tennis-badge-primary');
                    } else {
                        element.classList.add('split-second', 'tennis-badge-secondary');
                    }
                } else {
                    // Show warning that times must be from same facility
                    if (window.TennisUI) {
                        TennisUI.showNotification('For split times mode, both time slots must be from the same facility', 'warning');
                    }
                    return;
                }
            } else {
                // Already have 2 times selected, replace the first one
                const firstSelectedTime = this.selectedTimes[0];
                const firstElement = document.querySelector(`[data-time="${firstSelectedTime}"]`);
                if (firstElement) {
                    firstElement.classList.remove('selected', 'split-first', 'split-second', 'tennis-badge-primary', 'tennis-badge-secondary');
                    firstElement.classList.add('tennis-badge-light');
                }
                
                this.selectedTimes = [this.selectedTimes[1], time];
                element.classList.remove('tennis-badge-light');
                element.classList.add('selected', 'split-second', 'tennis-badge-secondary');
                
                // Update the remaining element to be first
                const remainingElement = document.querySelector(`[data-time="${this.selectedTimes[0]}"]`);
                if (remainingElement) {
                    remainingElement.classList.remove('split-second', 'tennis-badge-secondary');
                    remainingElement.classList.add('split-first', 'tennis-badge-primary');
                }
            }
        } else {
            // Custom mode allows multiple selections from the same facility
            if (this.selectedTimes.includes(time)) {
                this.selectedTimes = this.selectedTimes.filter(t => t !== time);
                element.classList.remove('selected', 'tennis-badge-success');
                element.classList.add('tennis-badge-light');
                // If no times left, clear facility selection
                if (this.selectedTimes.length === 0) {
                    this.selectedFacilityId = null;
                }
            } else {
                // Check if this is from the same facility (or if it's the first selection)
                if (this.selectedFacilityId === null || this.selectedFacilityId === facilityId) {
                    this.selectedTimes.push(time);
                    this.selectedFacilityId = facilityId;
                    element.classList.remove('tennis-badge-light');
                    element.classList.add('selected', 'tennis-badge-success');
                } else {
                    // Show warning that times must be from same facility
                    if (window.TennisUI) {
                        TennisUI.showNotification('All selected times must be from the same facility', 'warning');
                    }
                    return;
                }
            }
        }
        
        this.updateSelectedTimesDisplay();
        this.updateScheduleButton();
    }

    updateSelectedTimesDisplay() {
        const display = document.getElementById('selected-times-display');
        if (!display) return;
        
        const cardBody = display.querySelector('.tennis-card-body');
        const section = document.getElementById('selected-times-section');
        
        if (this.selectedTimes.length > 0) {
            let content = '';
            if (this.schedulingMode === 'same_time') {
                content = `<strong class="text-tennis-primary">All lines at:</strong> <span class="tennis-badge tennis-badge-success">${this.selectedTimes[0]}</span>`;
            } else if (this.schedulingMode === 'split_times') {
                if (this.selectedTimes.length === 1) {
                    content = `<strong class="text-tennis-primary">First slot:</strong> <span class="tennis-badge tennis-badge-primary">${this.selectedTimes[0]}</span> <small class="text-tennis-info">(select second slot)</small>`;
                } else if (this.selectedTimes.length === 2) {
                    const sortedTimes = [...this.selectedTimes].sort();
                    const linesInFirstSlot = Math.ceil(this.linesNeeded / 2);
                    const linesInSecondSlot = this.linesNeeded - linesInFirstSlot;
                    content = `
                        <div class="mb-2"><strong class="text-tennis-primary">Split times:</strong></div>
                        <div class="d-flex flex-wrap gap-2">
                            <span class="tennis-badge tennis-badge-primary">${linesInFirstSlot} lines at ${sortedTimes[0]}</span>
                            <span class="tennis-badge tennis-badge-secondary">${linesInSecondSlot} lines at ${sortedTimes[1]}</span>
                        </div>
                        <small class="text-tennis-muted d-block mt-2">All lines within each slot start at the same time</small>
                    `;
                }
            } else {
                content = `<strong class="text-tennis-primary">Custom times:</strong> <div class="d-flex flex-wrap gap-1 mt-1">${this.selectedTimes.map(time => `<span class="tennis-badge tennis-badge-success">${time}</span>`).join('')}</div>`;
            }
            cardBody.innerHTML = content;
            section.style.display = 'block';
        } else {
            cardBody.innerHTML = '<em class="text-tennis-muted">No times selected</em>';
            section.style.display = this.selectedDate ? 'block' : 'none';
        }
    }

    updateModeDescription() {
        const description = document.getElementById('mode-description');
        if (!description) return;
        
        const descriptions = {
            'custom': 'Specify exact times for each line',
            'same_time': 'All lines play at the same time',
            'split_times': 'Some lines at one time, remaining lines at another time (same time within each slot)'
        };
        description.textContent = descriptions[this.schedulingMode];
    }

    updateSplitTimesHelper() {
        const helper = document.getElementById('split-times-helper');
        if (!helper) return;
        
        if (this.schedulingMode === 'split_times') {
            helper.style.display = 'block';
        } else {
            helper.style.display = 'none';
        }
    }

    validateTimeSelection() {
        // Validate that the correct number of times are selected for each mode
        switch (this.schedulingMode) {
            case 'same_time':
                // This mode requires exactly 1 time
                return this.selectedTimes.length === 1;
            
            case 'split_times':
                // Split times mode requires exactly 2 times
                return this.selectedTimes.length === 2;
            
            case 'custom':
                // Custom mode requires exact number of times for lines needed
                return this.selectedTimes.length === this.linesNeeded;
            
            default:
                return false;
        }
    }

    updateUI() {
        const modeSection = document.getElementById('mode-section');
        const actionButtons = document.getElementById('action-buttons');
        
        if (modeSection) {
            modeSection.style.display = this.selectedDate ? 'block' : 'none';
        }
        if (actionButtons) {
            actionButtons.style.display = this.selectedDate ? 'block' : 'none';
        }
        
        this.updateScheduleButton();
        this.updateSplitTimesHelper();
    }

    updateScheduleButton() {
        const previewButton = document.getElementById('preview-button');
        if (!previewButton) return;
        
        const canSchedule = this.selectedDate && this.selectedTimes.length > 0 && this.validateTimeSelection();
        
        previewButton.disabled = !canSchedule;
        
        if (canSchedule) {
            previewButton.classList.remove('btn-outline-tennis-primary');
            previewButton.classList.add('btn-tennis-primary');
        } else {
            previewButton.classList.remove('btn-tennis-primary');
            previewButton.classList.add('btn-outline-tennis-primary');
        }
    }

    async showPreview() {
        if (!this.selectedDate || this.selectedTimes.length === 0) {
            if (window.TennisUI) {
                TennisUI.showNotification('Please select a date and at least one time', 'warning');
            }
            return;
        }

        if (!this.validateTimeSelection()) {
            return;
        }

        try {
            // Show loading state
            const previewButton = document.getElementById('preview-button');
            const originalText = previewButton.textContent;
            previewButton.textContent = 'Loading Preview...';
            previewButton.disabled = true;

            // Make preview API call
            const response = await fetch('/api/schedule/match/preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    match_id: this.matchId,
                    facility_id: this.selectedFacilityId || this.facilityInfoId,
                    date: this.selectedDate,
                    times: this.selectedTimes,
                    scheduling_mode: this.schedulingMode
                })
            });

            const result = await response.json();

            if (result.success && result.preview) {
                this.displayPreview(result.preview, result.can_schedule);
            } else {
                if (window.TennisUI) {
                    TennisUI.showNotification(result.error || 'Failed to generate preview', 'danger');
                }
            }

        } catch (error) {
            console.error('Error generating preview:', error);
            if (window.TennisUI) {
                TennisUI.showNotification('Error generating preview: ' + error.message, 'danger');
            }
        } finally {
            // Restore button state
            const previewButton = document.getElementById('preview-button');
            previewButton.textContent = originalText;
            previewButton.disabled = false;
        }
    }

    displayPreview(preview, canSchedule) {
        const previewContent = document.getElementById('preview-content');
        if (!previewContent) return;
        
        // Generate conflicts/warnings display
        let conflictsHtml = '';
        if (preview.conflicts && preview.conflicts.length > 0) {
            conflictsHtml = `
                <div class="alert alert-warning mt-3">
                    <h6><i class="fas fa-exclamation-triangle"></i> Potential Conflicts:</h6>
                    <ul class="mb-0">
                        ${preview.conflicts.map(conflict => {
                            if (typeof conflict === 'object' && conflict.message) {
                                return `<li>${conflict.message}</li>`;
                            }
                            return `<li>${conflict}</li>`;
                        }).join('')}
                    </ul>
                </div>
            `;
        }

        if (preview.warnings && preview.warnings.length > 0) {
            conflictsHtml += `
                <div class="alert alert-info mt-3">
                    <h6><i class="fas fa-info-circle"></i> Warnings:</h6>
                    <ul class="mb-0">
                        ${preview.warnings.map(warning => `<li>${warning}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        // Generate operations preview
        let operationsHtml = '';
        if (preview.operations && preview.operations.length > 0) {
            operationsHtml = `
                <div class="mt-3">
                    <h6>Database Operations (Preview):</h6>
                    <div class="operations-preview">
                        ${preview.operations.map(op => `
                            <div class="operation-item">
                                <span class="badge bg-secondary">${op.type}</span>
                                ${op.description}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Get match info from data attributes
        const matchElement = document.querySelector('[data-match-id]');
        const homeTeam = matchElement ? matchElement.dataset.homeTeam : 'Unknown';
        const visitorTeam = matchElement ? matchElement.dataset.visitorTeam : 'Unknown';
        const league = matchElement ? matchElement.dataset.league : 'Unknown';

        previewContent.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Match Details</h6>
                    <ul class="list-unstyled">
                        <li><strong>Home Team:</strong> ${homeTeam}</li>
                        <li><strong>Visitor Team:</strong> ${visitorTeam}</li>
                        <li><strong>League:</strong> ${league}</li>
                        <li><strong>Lines:</strong> ${preview.lines_needed || this.linesNeeded}</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6>Scheduling Details</h6>
                    <ul class="list-unstyled">
                        <li><strong>Date:</strong> ${preview.date}</li>
                        <li><strong>Facility:</strong> ${preview.facility_name}</li>
                        <li><strong>Mode:</strong> ${preview.scheduling_mode}</li>
                        <li><strong>Details:</strong> ${preview.scheduling_details}</li>
                    </ul>
                </div>
            </div>
            
            ${conflictsHtml}
            
            <div class="preview-status mt-3">
                ${preview.success 
                    ? '<div class="alert alert-success"><i class="fas fa-check"></i> Scheduling is feasible</div>'
                    : '<div class="alert alert-danger"><i class="fas fa-times"></i> Scheduling would fail</div>'
                }
            </div>
            
            ${operationsHtml}
        `;
        
        // Update confirm button state
        const confirmButton = document.getElementById('confirm-schedule');
        if (confirmButton) {
            confirmButton.disabled = !canSchedule;
            confirmButton.textContent = canSchedule ? 'Confirm Schedule' : 'Cannot Schedule';
        }
        
        // Show preview modal
        const previewModal = document.getElementById('previewModal');
        if (previewModal && window.bootstrap) {
            const modal = new bootstrap.Modal(previewModal);
            modal.show();
        }
    }

    async confirmSchedule() {
        // This performs the actual scheduling
        try {
            // Show loading state
            const confirmButton = document.getElementById('confirm-schedule');
            const originalText = confirmButton.textContent;
            confirmButton.textContent = 'Scheduling...';
            confirmButton.disabled = true;

            // Close preview modal
            const previewModal = document.getElementById('previewModal');
            if (previewModal && window.bootstrap) {
                const modal = bootstrap.Modal.getInstance(previewModal);
                if (modal) modal.hide();
            }

            // Make actual scheduling API call (existing endpoint)
            const response = await fetch('/api/schedule/match', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    match_id: this.matchId,
                    facility_id: this.selectedFacilityId || this.facilityInfoId,
                    date: this.selectedDate,
                    times: this.selectedTimes,
                    scheduling_mode: this.schedulingMode
                })
            });

            const scheduleResult = await response.json();

            if (scheduleResult.success) {
                if (window.TennisUI) {
                    TennisUI.showNotification('Match scheduled successfully!', 'success');
                }
                // Redirect to matches page or refresh
                setTimeout(() => {
                    window.location.href = '/matches';
                }, 1500);
            } else {
                if (window.TennisUI) {
                    TennisUI.showNotification(scheduleResult.error || 'Failed to schedule match', 'danger');
                }
            }

        } catch (error) {
            console.error('Error scheduling match:', error);
            if (window.TennisUI) {
                TennisUI.showNotification('Error scheduling match: ' + error.message, 'danger');
            }
        } finally {
            // Restore button state
            const confirmButton = document.getElementById('confirm-schedule');
            confirmButton.textContent = originalText;
            confirmButton.disabled = false;
        }
    }
}

// Initialize the scheduling UI when the page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.date-card')) {
        window.scheduleUI = new ScheduleMatchUI();
    }
});