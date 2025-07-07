/* Stats Page JavaScript */

class StatsPage {
    constructor(statsData) {
        this.statsData = statsData;
        this.init();
    }

    init() {
        this.createDistributionChart();
        this.makeTablesSortable();
        this.updateLastUpdatedTime();
        this.initializeTooltips();
        console.log('🎾 Stats Page Initialized');
    }

    // ==================== CHART CREATION ====================

    createDistributionChart() {
        const ctx = document.getElementById('distributionChart');
        if (!ctx) return;

        const chartCtx = ctx.getContext('2d');
        
        new Chart(chartCtx, {
            type: 'doughnut',
            data: {
                labels: ['Facilities', 'Leagues', 'Teams', 'Matches'],
                datasets: [{
                    data: [
                        this.statsData.facilities_count,
                        this.statsData.leagues_count,
                        this.statsData.teams_count,
                        this.statsData.matches_count
                    ],
                    backgroundColor: [
                        '#0d6efd',  // Blue
                        '#198754',  // Green
                        '#0dcaf0',  // Cyan
                        '#ffc107'   // Yellow
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12,
                            font: {
                                size: 11
                            }
                        }
                    }
                }
            }
        });
    }

    // ==================== TABLE SORTING ====================

    makeTablesSortable() {
        document.querySelectorAll('th').forEach(header => {
            if (header.textContent.trim() && !header.textContent.includes('League')) {
                header.style.cursor = 'pointer';
                header.style.userSelect = 'none';
                header.addEventListener('click', () => this.sortTable(header));
                
                // Add visual indicator
                header.title = 'Click to sort';
                header.classList.add('sortable-header');
            }
        });
    }

    sortTable(header) {
        const table = header.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.rows);
        const index = Array.from(header.parentNode.children).indexOf(header);
        
        // Determine sort direction
        const currentDirection = header.getAttribute('data-sort-direction') || 'asc';
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        
        // Clear all sort indicators
        table.querySelectorAll('th').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
            th.removeAttribute('data-sort-direction');
        });
        
        // Set new sort indicator
        header.classList.add(`sort-${newDirection}`);
        header.setAttribute('data-sort-direction', newDirection);
        
        // Sort rows
        rows.sort((a, b) => {
            const aText = a.cells[index].textContent.trim();
            const bText = b.cells[index].textContent.trim();
            
            // Check if values are numeric
            const aNum = parseFloat(aText);
            const bNum = parseFloat(bText);
            
            let comparison;
            if (!isNaN(aNum) && !isNaN(bNum)) {
                // Numeric comparison
                comparison = aNum - bNum;
            } else {
                // Text comparison
                comparison = aText.localeCompare(bText, undefined, {numeric: true});
            }
            
            return newDirection === 'asc' ? comparison : -comparison;
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
        
        // Show feedback if TennisUI is available
        if (typeof TennisUI !== 'undefined' && TennisUI.showNotification) {
            TennisUI.showNotification(
                `Sorted by ${header.textContent.trim()} (${newDirection === 'asc' ? 'ascending' : 'descending'})`, 
                'info', 
                2000
            );
        }
    }

    // ==================== UTILITY FUNCTIONS ====================

    updateLastUpdatedTime() {
        const lastUpdatedElement = document.getElementById('lastUpdated');
        if (lastUpdatedElement) {
            lastUpdatedElement.textContent = new Date().toLocaleString();
        }
    }

    initializeTooltips() {
        // Initialize tooltips if Bootstrap is available
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }

    // ==================== AUTO-REFRESH FUNCTIONALITY ====================

    enableAutoRefresh(intervalMinutes = 5) {
        // Auto-refresh option (can be enabled if needed)
        const refreshInterval = intervalMinutes * 60 * 1000; // Convert to milliseconds
        
        setInterval(() => {
            if (!document.hidden) {
                console.log('Auto-refreshing stats page...');
                window.location.reload();
            }
        }, refreshInterval);
        
        console.log(`Auto-refresh enabled: ${intervalMinutes} minutes`);
    }

    refreshStats() {
        // Manual refresh function
        this.updateLastUpdatedTime();
        window.location.reload();
    }
}

// Make StatsPage available globally
window.StatsPage = StatsPage;