"""
Backend calendar functionality for tennis matches scheduling.
Provides calendar data structures and utilities for the web interface.
"""

from datetime import datetime, timedelta, date
from calendar import monthrange
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class CalendarEvent:
    """Represents a calendar event (match, facility event, etc.)"""
    title: str
    event_type: str  # 'match', 'facility', 'team', 'other'
    time: Optional[str] = None
    match_id: Optional[int] = None
    facility_id: Optional[int] = None
    team_id: Optional[int] = None


@dataclass
class CalendarDay:
    """Represents a single day in the calendar"""
    date: date
    day: int  # Changed from day_number to match template expectations
    is_today: bool
    is_other_month: bool
    events: List[CalendarEvent]
    matches: List[Any] = None  # Add matches attribute for template compatibility
    
    def __post_init__(self):
        # Ensure matches is initialized as empty list if not provided
        if self.matches is None:
            self.matches = []


@dataclass
class CalendarWeek:
    """Represents a week in the calendar"""
    days: List[CalendarDay]


class MatchesCalendar:
    """Calendar generator for tennis matches and related events"""
    
    def __init__(self, db_interface=None):
        """Initialize calendar with optional database interface"""
        self.db = db_interface
    
    def get_calendar_data(self, year: int, month: int) -> Dict[str, Any]:
        """
        Generate complete calendar data for a given month/year.
        
        Args:
            year: Year to generate calendar for
            month: Month (1-12) to generate calendar for
            
        Returns:
            Dictionary containing calendar weeks, month info, and navigation data
        """
        # Get first day of month and number of days
        first_day = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        
        # Get first day of week (Sunday = 0)
        first_weekday = first_day.weekday()
        # Convert to Sunday-based (0=Sunday, 6=Saturday)
        first_weekday = (first_weekday + 1) % 7
        
        # Calculate start date (may be in previous month)
        start_date = first_day - timedelta(days=first_weekday)
        
        # Generate 6 weeks of calendar data
        weeks = []
        current_date = start_date
        
        for week_num in range(6):
            week_days = []
            for day_num in range(7):
                # Determine if this day is in current month
                is_current_month = current_date.month == month and current_date.year == year
                is_today = current_date == date.today()
                
                # Get events and matches for this day
                events = self._get_events_for_date(current_date)
                matches = self._get_matches_for_date(current_date)
                
                calendar_day = CalendarDay(
                    date=current_date,
                    day=current_date.day,
                    is_today=is_today,
                    is_other_month=not is_current_month,
                    events=events,
                    matches=matches  # Populate with actual match objects
                )
                
                week_days.append(calendar_day)
                current_date += timedelta(days=1)
            
            weeks.append(CalendarWeek(days=week_days))
        
        # Calculate navigation months
        prev_month, prev_year = self._get_prev_month(month, year)
        next_month, next_year = self._get_next_month(month, year)
        
        return {
            'calendar_weeks': weeks,
            'current_month': month,
            'current_year': year,
            'month_name': first_day.strftime('%B'),
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'today': date.today()
        }
    
    def _get_events_for_date(self, target_date: date) -> List[CalendarEvent]:
        """
        Get all events for a specific date.
        
        Args:
            target_date: Date to get events for
            
        Returns:
            List of CalendarEvent objects for the date
        """
        events = []
        
        if self.db:
            # Get matches for this date
            try:
                matches = self._get_matches_for_date(target_date)
                for match in matches:
                    match_id = match.id if hasattr(match, 'id') else match.get('id')
                    event = CalendarEvent(
                        title=self._format_match_title(match),
                        event_type='match',
                        time=self._format_match_time(match),
                        match_id=match_id
                    )
                    events.append(event)
                
                # Get facility events for this date
                facility_events = self._get_facility_events_for_date(target_date)
                for facility_event in facility_events:
                    event = CalendarEvent(
                        title=facility_event.get('title', 'Facility Event'),
                        event_type='facility',
                        facility_id=facility_event.get('facility_id')
                    )
                    events.append(event)
                    
            except Exception as e:
                # Log error but don't break calendar display
                print(f"Error fetching events for {target_date}: {e}")
        
        return events
    
    def _get_matches_for_date(self, target_date: date) -> List[Any]:
        """Get scheduled matches for a specific date"""
        if not self.db:
            return []
        
        try:
            # Use the standard list_matches method from the database interface
            from usta import MatchType
            all_matches = self.db.list_matches(match_type=MatchType.SCHEDULED)
            filtered_matches = []
            
            for match in all_matches:
                if self._match_is_on_date(match, target_date):
                    filtered_matches.append(match)
            
            return filtered_matches
        except Exception as e:
            print(f"Error getting matches for date {target_date}: {e}")
            return []
    
    def _get_facility_events_for_date(self, target_date: date) -> List[Dict[str, Any]]:
        """Get facility events for a specific date (maintenance, closures, etc.)"""
        # This would be extended to query facility availability/events
        # For now, return empty list
        return []
    
    def _match_is_on_date(self, match: Any, target_date: date) -> bool:
        """Check if a match is scheduled on a specific date"""
        try:
            # Handle Match objects (which have .date attribute)
            if hasattr(match, 'date'):
                match_date = match.date
            else:
                # Handle dictionaries
                match_date = match.get('scheduled_date') or match.get('date') or match.get('match_date')
            
            if not match_date:
                return False
            
            # Convert to date object if it's a string
            if isinstance(match_date, str):
                try:
                    # Try different date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                        try:
                            parsed_date = datetime.strptime(match_date, fmt).date()
                            return parsed_date == target_date
                        except ValueError:
                            continue
                except ValueError:
                    return False
            elif isinstance(match_date, datetime):
                return match_date.date() == target_date
            elif isinstance(match_date, date):
                return match_date == target_date
            
            return False
        except Exception:
            return False
    
    def _format_match_title(self, match: Any) -> str:
        """Format match title for calendar display"""
        # Handle Match objects
        if hasattr(match, 'home_team') and hasattr(match, 'visitor_team'):
            home_team = match.home_team.name if match.home_team else 'TBD'
            away_team = match.visitor_team.name if match.visitor_team else 'TBD'
        else:
            # Handle dictionaries
            home_team = match.get('home_team', 'Home')
            away_team = match.get('away_team', 'Away')
            
            # Handle case where team names might be IDs
            if isinstance(home_team, int):
                home_team = f"Team {home_team}"
            if isinstance(away_team, int):
                away_team = f"Team {away_team}"
        
        return f"{home_team} vs {away_team}"
    
    def _format_match_time(self, match: Any) -> Optional[str]:
        """Format match time for display"""
        # Handle Match objects
        if hasattr(match, 'scheduled_times') and match.scheduled_times:
            # Take first scheduled time if multiple times exist
            return match.scheduled_times[0] if match.scheduled_times else None
        elif hasattr(match, 'get'):
            # Handle dictionaries
            scheduled_time = match.get('scheduled_time') or match.get('time')
        else:
            return None
        
        if not scheduled_time:
            return None
        
        try:
            if isinstance(scheduled_time, str):
                # Try to parse time string
                for fmt in ['%H:%M:%S', '%H:%M', '%I:%M %p']:
                    try:
                        time_obj = datetime.strptime(scheduled_time, fmt).time()
                        return time_obj.strftime('%I:%M %p')
                    except ValueError:
                        continue
                return scheduled_time
            elif hasattr(scheduled_time, 'strftime'):
                return scheduled_time.strftime('%I:%M %p')
        except Exception:
            pass
        
        return None
    
    def _get_prev_month(self, month: int, year: int) -> tuple[int, int]:
        """Get previous month and year"""
        if month == 1:
            return 12, year - 1
        return month - 1, year
    
    def _get_next_month(self, month: int, year: int) -> tuple[int, int]:
        """Get next month and year"""
        if month == 12:
            return 1, year + 1
        return month + 1, year


def create_calendar_context(db_interface=None, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Create calendar context for template rendering.
    
    Args:
        db_interface: Database interface for fetching match data
        month: Month to display (defaults to current month)
        year: Year to display (defaults to current year)
        
    Returns:
        Dictionary with calendar data for template context
    """
    today = date.today()
    if month is None:
        month = today.month
    if year is None:
        year = today.year
    
    calendar = MatchesCalendar(db_interface)
    calendar_data = calendar.get_calendar_data(year, month)
    
    return {
        'calendar_weeks': calendar_data['calendar_weeks'],
        'current_month': calendar_data['current_month'],
        'current_year': calendar_data['current_year'],
        'month_name': calendar_data['month_name'],
        'prev_month': calendar_data['prev_month'],
        'prev_year': calendar_data['prev_year'],
        'next_month': calendar_data['next_month'],
        'next_year': calendar_data['next_year'],
        'today': calendar_data['today']
    }


def get_calendar_events_json(db_interface=None, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """
    Get calendar events in JSON format for AJAX requests.
    
    Args:
        db_interface: Database interface for fetching data
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of event dictionaries suitable for JSON serialization
    """
    events = []
    
    if not start_date or not end_date:
        return events
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        calendar = MatchesCalendar(db_interface)
        current_date = start
        
        while current_date <= end:
            day_events = calendar._get_events_for_date(current_date)
            for event in day_events:
                events.append({
                    'date': current_date.isoformat(),
                    'title': event.title,
                    'type': event.event_type,
                    'time': event.time,
                    'match_id': event.match_id,
                    'facility_id': event.facility_id,
                    'team_id': event.team_id
                })
            current_date += timedelta(days=1)
            
    except ValueError as e:
        print(f"Error parsing dates: {e}")
    
    return events