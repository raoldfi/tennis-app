/* View Team Page JavaScript */

class ViewTeamPage {
    constructor() {
        this.init();
    }

    init() {
        this.convertStringDatesToDayNames();
        this.initializeTableSorting();
        this.initializeTooltips();
        console.log('🎾 View Team Page Initialized');
    }

    // ==================== DATE CONVERSION ====================

    convertStringDatesToDayNames() {
        const dayElements = document.querySelectorAll('.day-name[data-date]');
        const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        
        dayElements.forEach(element => {
            const dateString = element.getAttribute('data-date');
            if (dateString && dateString !== '—') {
                try {
                    // Parse the date string (expected format: YYYY-MM-DD)
                    const date = new Date(dateString + 'T00:00:00'); // Add time to avoid timezone issues
                    if (!isNaN(date.getTime())) {
                        const dayIndex = date.getDay();
                        const dayName = dayNames[dayIndex];
                        element.textContent = dayName;
                    } else {
                        console.warn('Invalid date string:', dateString);
                    }
                } catch (error) {
                    console.warn('Error parsing date string:', dateString, error);
                }
            }
        });
    }

    // ==================== TABLE SORTING ====================

    initializeTableSorting() {
        const headers = document.querySelectorAll('.sortable-header');
        
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.getAttribute('data-sort-column');
                const type = header.getAttribute('data-sort-type');
                this.sortTable(column, type, header);
            });
        });
    }

    sortTable(column, type, headerElement) {
        const table = headerElement.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        // Determine sort direction
        const currentSort = headerElement.classList.contains('sort-asc') ? 'asc' : 
                           headerElement.classList.contains('sort-desc') ? 'desc' : 'none';
        
        let newSort;
        if (currentSort === 'none' || currentSort === 'desc') {
            newSort = 'asc';
        } else {
            newSort = 'desc';
        }
        
        // Clear all sort indicators
        table.querySelectorAll('.sortable-header').forEach(h => {
            h.classList.remove('sort-asc', 'sort-desc');
        });
        
        // Set new sort indicator
        headerElement.classList.add(`sort-${newSort}`);
        
        // Sort rows
        rows.sort((a, b) => {
            let aValue = this.getSortValue(a, column, type);
            let bValue = this.getSortValue(b, column, type);
            
            if (type === 'numeric') {
                aValue = parseFloat(aValue) || 0;
                bValue = parseFloat(bValue) || 0;
            } else if (type === 'date') {
                aValue = this.parseDate(aValue);
                bValue = this.parseDate(bValue);
            } else {
                aValue = aValue.toLowerCase();
                bValue = bValue.toLowerCase();
            }
            
            if (aValue < bValue) return newSort === 'asc' ? -1 : 1;
            if (aValue > bValue) return newSort === 'asc' ? 1 : -1;
            return 0;
        });
        
        // Reorder rows in DOM
        rows.forEach(row => tbody.appendChild(row));
    }

    getSortValue(row, column, type) {
        const cells = row.querySelectorAll('td');
        
        switch(column) {
            case 'id':
                const idText = cells[0]?.querySelector('strong')?.textContent || '';
                return idText.replace('#', '');
                
            case 'day':
                const dayElement = cells[1]?.querySelector('.day-name');
                return dayElement?.textContent?.trim() || 'zzz'; // Put TBD/— at end
                
            case 'date':
                const dateElement = cells[2]?.querySelector('.match-date');
                return dateElement?.textContent?.trim() || '9999-12-31'; // Put TBD at end
                
            case 'home':
                const homeElement = cells[3]?.querySelector('.team-display');
                return homeElement?.textContent?.replace(/[^\w\s]/g, '').trim() || 'zzz';
                
            case 'visitor':
                const visitorElement = cells[4]?.querySelector('.team-display');
                return visitorElement?.textContent?.replace(/[^\w\s]/g, '').trim() || 'zzz';
                
            case 'times':
                const timeElement = cells[5]?.querySelector('.time-badge, .time-badge-small');
                return timeElement?.textContent?.trim() || 'zzz';
                
            case 'facility':
                const facilityElement = cells[6]?.querySelector('.facility-link-compact');
                return facilityElement?.textContent?.trim() || 'zzz';
                
            default:
                return '';
        }
    }

    parseDate(dateStr) {
        if (!dateStr || dateStr === '—' || dateStr === 'TBD') {
            return new Date('9999-12-31'); // Sort TBD dates to end
        }
        
        // Try to parse various date formats
        if (dateStr.includes('/')) {
            // MM/DD/YYYY format
            const parts = dateStr.split('/');
            if (parts.length === 3) {
                return new Date(parseInt(parts[2]), parseInt(parts[0]) - 1, parseInt(parts[1]));
            }
        } else if (dateStr.includes('-')) {
            // YYYY-MM-DD format
            return new Date(dateStr + 'T00:00:00');
        }
        
        return new Date(dateStr);
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

    // ==================== MATCH OPERATIONS ====================

    async scheduleMatch(matchId) {
        if (!matchId) {
            console.error('No match ID provided to scheduleMatch');
            return;
        }
        
        // Navigate directly to the schedule match form page
        // This uses the route from web_schedule_match.py: /matches/<int:match_id>/schedule
        window.location.href = `/matches/${matchId}/schedule`;
    }

    async unscheduleMatch(matchId, description) {
        if (!matchId) {
            console.error('No match ID provided to unscheduleMatch');
            return;
        }
        
        try {
            // Create and submit a form to trigger the DELETE request and redirect
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/matches/${matchId}/schedule`;
            form.style.display = 'none';
            
            // Add hidden input for method override (common pattern for DELETE in forms)
            const methodInput = document.createElement('input');
            methodInput.type = 'hidden';
            methodInput.name = '_method';
            methodInput.value = 'DELETE';
            form.appendChild(methodInput);
            
            document.body.appendChild(form);
            form.submit();
            
        } catch (error) {
            console.error('Error unscheduling match:', error);
            // On error, reload the page to show any flash messages
            window.location.reload();
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    window.viewTeamPage = new ViewTeamPage();
});

// Make ViewTeamPage available globally
window.ViewTeamPage = ViewTeamPage;

// Global functions for onclick handlers (required by templates)
window.scheduleMatch = function(matchId) {
    if (window.viewTeamPage) {
        window.viewTeamPage.scheduleMatch(matchId);
    }
};

window.unscheduleMatch = function(matchId, description) {
    if (window.viewTeamPage) {
        window.viewTeamPage.unscheduleMatch(matchId, description);
    }
};