/**
 * Enhanced Facility Management for Team Forms
 * Handles adding, removing, and reordering preferred facilities
 */

class TeamFacilityManager {
    constructor() {
        this.selectedFacilities = [];
        this.isInitialized = false;
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        
        // Check if DOM is already loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.initializeFacilityManagement();
                this.setupFormValidation();
                this.setupEventListeners();
            });
        } else {
            // DOM is already loaded, initialize immediately
            this.initializeFacilityManagement();
            this.setupFormValidation();
            this.setupEventListeners();
        }
        
        this.isInitialized = true;
    }

    initializeFacilityManagement() {
        // Load existing facilities if in edit mode
        const existingFacilities = document.querySelectorAll('#selectedFacilities .facility-item');
        this.selectedFacilities = [];
        
        existingFacilities.forEach(item => {
            const facilityId = item.getAttribute('data-facility-id');
            if (facilityId) {
                this.selectedFacilities.push(facilityId);
            }
        });
        
        this.updateHiddenInput();
        this.updateAddDropdown();
        this.updateFacilityActions();
    }

    setupEventListeners() {
        // Captain field for auto-name generation
        const captainField = document.getElementById('captain');
        if (captainField) {
            captainField.addEventListener('blur', () => this.tryGenerateTeamName());
        }

        // Add facility button
        const addFacilityBtn = document.getElementById('addFacilityBtn');
        if (addFacilityBtn) {
            addFacilityBtn.addEventListener('click', () => this.addFacility());
        }

        // Generate team name button
        const generateNameBtn = document.getElementById('generateTeamNameBtn');
        if (generateNameBtn) {
            generateNameBtn.addEventListener('click', () => this.generateTeamName());
        }

        // Event delegation for facility action buttons
        const facilityList = document.getElementById('selectedFacilities');
        if (facilityList) {
            facilityList.addEventListener('click', (e) => {
                const button = e.target.closest('button');
                if (!button) return;

                if (button.classList.contains('move-up-btn')) {
                    this.moveFacilityUp(button);
                } else if (button.classList.contains('move-down-btn')) {
                    this.moveFacilityDown(button);
                } else if (button.classList.contains('btn-outline-danger')) {
                    this.removeFacility(button);
                }
            });
        }

        // Form submission
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmission(e));
        }
    }

    addFacility() {
        const dropdown = document.getElementById('facilityToAdd');
        const selectedOption = dropdown.options[dropdown.selectedIndex];
        
        if (!selectedOption.value) {
            return;
        }
        
        const facilityId = selectedOption.value;
        const facilityName = selectedOption.getAttribute('data-name');
        const facilityShort = selectedOption.getAttribute('data-short');
        const facilityLocation = selectedOption.getAttribute('data-location');
        
        // Check if facility is already selected
        if (this.selectedFacilities.includes(facilityId)) {
            this.showAlert('This facility is already selected.', 'warning');
            dropdown.selectedIndex = 0;
            return;
        }
        
        // Add to selected facilities array
        this.selectedFacilities.push(facilityId);
        
        // Remove "no facilities" message if present
        const noFacilitiesMessage = document.getElementById('noFacilitiesMessage');
        if (noFacilitiesMessage) {
            noFacilitiesMessage.remove();
        }
        
        // Create facility item HTML
        const facilityItem = this.createFacilityItem(facilityId, facilityName, facilityShort, facilityLocation);
        
        // Add to the list with animation
        const facilityList = document.getElementById('selectedFacilities');
        facilityItem.classList.add('facility-item-new');
        facilityList.appendChild(facilityItem);
        
        // Remove animation class after animation completes
        setTimeout(() => {
            facilityItem.classList.remove('facility-item-new');
        }, 300);
        
        // Update UI
        this.updateFacilityActions();
        this.updateHiddenInput();
        this.updateAddDropdown();
        
        // Reset dropdown
        dropdown.selectedIndex = 0;
        
        // Trigger team name generation if conditions are met
        this.tryGenerateTeamName();
        
        this.showAlert(`Added ${facilityName} to preferred facilities.`, 'success');
    }

    createFacilityItem(facilityId, facilityName, facilityShort, facilityLocation) {
        const div = document.createElement('div');
        div.className = 'facility-item d-flex align-items-center justify-content-between mb-2 p-2 bg-light rounded';
        div.setAttribute('data-facility-id', facilityId);
        
        const isPrimary = this.selectedFacilities.length === 1; // First facility is primary
        
        div.innerHTML = `
            <div class="facility-info">
                <span class="facility-name fw-bold">${this.escapeHtml(facilityName)}</span>
                ${facilityShort ? `<span class="text-muted"> (${this.escapeHtml(facilityShort)})</span>` : ''}
                ${facilityLocation ? `<br><small class="text-muted">${this.escapeHtml(facilityLocation)}</small>` : ''}
                ${isPrimary ? '<span class="badge bg-primary ms-2">Primary</span>' : ''}
            </div>
            <div class="facility-actions">
                <button type="button" class="btn btn-sm btn-outline-primary me-1 move-up-btn" title="Move up">
                    <i class="fas fa-arrow-up"></i>
                </button>
                <button type="button" class="btn btn-sm btn-outline-primary me-1 move-down-btn" title="Move down">
                    <i class="fas fa-arrow-down"></i>
                </button>
                <button type="button" class="btn btn-sm btn-outline-danger" title="Remove facility">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        
        return div;
    }

    removeFacility(button) {
        const facilityItem = button.closest('.facility-item');
        const facilityId = facilityItem.getAttribute('data-facility-id');
        const facilityName = facilityItem.querySelector('.facility-name').textContent;
        
        // Remove from array
        this.selectedFacilities = this.selectedFacilities.filter(id => id !== facilityId);
        
        // Remove from DOM with animation
        facilityItem.style.transition = 'all 0.3s ease-out';
        facilityItem.style.opacity = '0';
        facilityItem.style.transform = 'translateX(-100%)';
        
        setTimeout(() => {
            facilityItem.remove();
            
            // Show "no facilities" message if no facilities remain
            if (this.selectedFacilities.length === 0) {
                this.showNoFacilitiesMessage();
            }
            
            // Update UI
            this.updateFacilityActions();
            this.updateHiddenInput();
            this.updateAddDropdown();
        }, 300);
        
        this.showAlert(`Removed ${facilityName} from preferred facilities.`, 'info');
    }

    moveFacilityUp(button) {
        const facilityItem = button.closest('.facility-item');
        const facilityId = facilityItem.getAttribute('data-facility-id');
        const index = this.selectedFacilities.indexOf(facilityId);
        
        if (index > 0) {
            // Swap in array
            [this.selectedFacilities[index - 1], this.selectedFacilities[index]] = 
            [this.selectedFacilities[index], this.selectedFacilities[index - 1]];
            
            // Move in DOM
            const previousSibling = facilityItem.previousElementSibling;
            facilityItem.parentNode.insertBefore(facilityItem, previousSibling);
            
            // Update UI
            this.updateFacilityActions();
            this.updateHiddenInput();
            
            // Visual feedback
            facilityItem.style.transition = 'all 0.2s ease';
            facilityItem.style.transform = 'translateY(-5px)';
            setTimeout(() => {
                facilityItem.style.transform = 'translateY(0)';
            }, 200);
        }
    }

    moveFacilityDown(button) {
        const facilityItem = button.closest('.facility-item');
        const facilityId = facilityItem.getAttribute('data-facility-id');
        const index = this.selectedFacilities.indexOf(facilityId);
        
        if (index < this.selectedFacilities.length - 1) {
            // Swap in array
            [this.selectedFacilities[index], this.selectedFacilities[index + 1]] = 
            [this.selectedFacilities[index + 1], this.selectedFacilities[index]];
            
            // Move in DOM
            const nextSibling = facilityItem.nextElementSibling;
            if (nextSibling) {
                facilityItem.parentNode.insertBefore(nextSibling, facilityItem);
            }
            
            // Update UI
            this.updateFacilityActions();
            this.updateHiddenInput();
            
            // Visual feedback
            facilityItem.style.transition = 'all 0.2s ease';
            facilityItem.style.transform = 'translateY(5px)';
            setTimeout(() => {
                facilityItem.style.transform = 'translateY(0)';
            }, 200);
        }
    }

    updateFacilityActions() {
        const facilityItems = document.querySelectorAll('#selectedFacilities .facility-item');
        
        facilityItems.forEach((item, index) => {
            const moveUpBtn = item.querySelector('.move-up-btn');
            const moveDownBtn = item.querySelector('.move-down-btn');
            const primaryBadge = item.querySelector('.badge');
            
            // Show/hide move buttons
            if (moveUpBtn) {
                moveUpBtn.style.display = index === 0 ? 'none' : 'inline-block';
            }
            if (moveDownBtn) {
                moveDownBtn.style.display = index === facilityItems.length - 1 ? 'none' : 'inline-block';
            }
            
            // Update primary badge
            if (primaryBadge) {
                primaryBadge.remove();
            }
            if (index === 0) {
                const facilityInfo = item.querySelector('.facility-info');
                const badge = document.createElement('span');
                badge.className = 'badge bg-primary ms-2';
                badge.textContent = 'Primary';
                facilityInfo.appendChild(badge);
            }
        });
    }

    updateHiddenInput() {
        const hiddenInput = document.getElementById('preferred_facility_ids');
        if (hiddenInput) {
            hiddenInput.value = this.selectedFacilities.join(',');
        }
    }

    updateAddDropdown() {
        const dropdown = document.getElementById('facilityToAdd');
        if (!dropdown) return;
        
        const options = dropdown.querySelectorAll('option[value]');
        
        options.forEach(option => {
            const facilityId = option.value;
            option.style.display = this.selectedFacilities.includes(facilityId) ? 'none' : 'block';
        });
        
        // Update add button state
        const addBtn = document.getElementById('addFacilityBtn');
        if (addBtn) {
            const hasAvailableOptions = Array.from(options).some(option => 
                option.value && option.style.display !== 'none'
            );
            addBtn.disabled = !hasAvailableOptions;
        }
    }

    showNoFacilitiesMessage() {
        const facilityList = document.getElementById('selectedFacilities');
        const noFacilitiesMessage = document.createElement('div');
        noFacilitiesMessage.id = 'noFacilitiesMessage';
        noFacilitiesMessage.className = 'text-muted text-center py-3';
        noFacilitiesMessage.innerHTML = `
            <i class="fas fa-building"></i><br>
            No facilities selected. Add facilities using the dropdown below.
        `;
        facilityList.appendChild(noFacilitiesMessage);
    }

    // Team name generation (updated for new facility structure)
    generateTeamName() {
        const captain = document.getElementById('captain')?.value?.trim();
        
        if (captain && this.selectedFacilities.length > 0) {
            // Get the primary facility (first in the list)
            const primaryFacilityId = this.selectedFacilities[0];
            const dropdown = document.getElementById('facilityToAdd');
            const primaryOption = dropdown?.querySelector(`option[value="${primaryFacilityId}"]`);
            
            if (primaryOption) {
                const facilityName = primaryOption.getAttribute('data-name');
                const facilityShort = primaryOption.getAttribute('data-short');
                
                // Extract last name from captain (assume "First Last" format)
                const lastName = captain.split(' ').pop();
                
                // Use short name if available and under 15 chars, otherwise use full name
                const facilityDisplay = (facilityShort && facilityShort.length > 0 && facilityShort.length <= 15) 
                    ? facilityShort 
                    : facilityName;
                
                const suggestedName = `${lastName} - ${facilityDisplay}`;
                const nameField = document.getElementById('name');
                if (nameField) {
                    nameField.value = suggestedName;
                    
                    // Highlight the updated field briefly
                    nameField.classList.add('bg-warning', 'bg-opacity-25');
                    setTimeout(() => {
                        nameField.classList.remove('bg-warning', 'bg-opacity-25');
                    }, 1500);
                }
            }
        }
    }

    tryGenerateTeamName() {
        const captain = document.getElementById('captain')?.value?.trim();
        const nameField = document.getElementById('name')?.value?.trim();
        
        if (captain && this.selectedFacilities.length > 0 && !nameField) {
            this.generateTeamName();
        }
    }

    setupFormValidation() {
        const form = document.querySelector('form');
        if (!form) return;
        
        form.addEventListener('submit', (e) => this.handleFormSubmission(e));
    }

    handleFormSubmission(e) {
        // Check if at least one facility is selected
        if (this.selectedFacilities.length === 0) {
            e.preventDefault();
            this.showAlert('Please select at least one preferred facility.', 'error');
            return false;
        }
        
        // Check preferred days
        const checkboxes = document.querySelectorAll('input[name="preferred_days"]:checked');
        if (checkboxes.length === 0) {
            const proceed = confirm('No preferred days selected. The team will be available for scheduling on any day. Continue?');
            if (!proceed) {
                e.preventDefault();
                return false;
            }
        }
        
        // Update hidden input one final time before submission
        this.updateHiddenInput();
        return true;
    }

    showAlert(message, type = 'info') {
        // Create a simple alert (you could enhance this with a toast notification system)
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';
        
        // For now, use console.log - you can enhance this with actual UI alerts
        console.log(`${type.toUpperCase()}: ${message}`);
        
        // Could add a toast notification here in the future
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.facilityManager = new TeamFacilityManager();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TeamFacilityManager;
}