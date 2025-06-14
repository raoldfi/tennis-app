"""
Web Schedule Module - Flask routes for tennis match schedule display
Cleaned version using Match class methods consistently
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import traceback

# Import tennis-specific modules
try:
    from usta import MatchType
except ImportError:
    print("Warning: Could not import usta modules. Please ensure they are available.")
    from enum import Enum
    class MatchType(Enum):
        SCHEDULED = "scheduled"
        UNSCHEDULED = "unscheduled"


def register_routes(app: Flask):
    """Register all routes needed for the schedule page with the Flask app"""
    
    # Import get_db function locally to match other modules
    from web_database import get_db
    
    @app.route('/schedule')
    def schedule():
        """Schedule page - displays scheduled matches grouped by date"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        search_query = request.args.get('search', '').strip()
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
            
            # Get ALL scheduled matches using Match.is_scheduled()
            all_matches = db.list_matches(league=selected_league, match_type=MatchType.SCHEDULED)
            scheduled_matches = [m for m in all_matches if m.is_scheduled()]
            print(f"Found {len(scheduled_matches)} scheduled matches")
            
            # Apply date range filters
            if start_date:
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    scheduled_matches = [m for m in scheduled_matches 
                                       if m.date and convert_to_date(m.date) >= start_date_obj]
                except ValueError:
                    print(f"Invalid start_date format: {start_date}")
            
            if end_date:
                try:
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    scheduled_matches = [m for m in scheduled_matches 
                                       if m.date and convert_to_date(m.date) <= end_date_obj]
                except ValueError:
                    print(f"Invalid end_date format: {end_date}")
            
            # Apply search filter
            if search_query:
                scheduled_matches = search_matches(scheduled_matches, search_query)
            
            # Group matches by date
            schedule_data = build_schedule_data(scheduled_matches)
            
            # Calculate total matches and lines using Match class methods
            total_matches = len(scheduled_matches)
            total_lines = sum(m.get_num_scheduled_lines() for m in scheduled_matches)
            
            # Convert schedule_data to list format expected by template
            schedule_data_list = []
            for date_str, day_data in schedule_data.items():
                day_data_formatted = {
                    'date': day_data['date'],
                    'date_str': date_str,
                    'day_name': day_data['date'].strftime('%A'),
                    'formatted_date': day_data['date'].strftime('%A, %B %d, %Y'),
                    'matches': day_data['matches']
                }
                schedule_data_list.append(day_data_formatted)
            
            # Get leagues for filter dropdown
            leagues_list = db.list_leagues()
            
            return render_template('schedule.html',
                                 schedule_data=schedule_data_list,
                                 total_matches=total_matches,
                                 total_lines=total_lines,
                                 leagues=leagues_list,
                                 selected_league=selected_league,
                                 search_query=search_query,
                                 start_date=start_date,
                                 end_date=end_date)
                                 
        except Exception as e:
            print(f"Error in schedule route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading schedule: {str(e)}', 'error')
            return redirect(url_for('matches'))


def build_schedule_data(matches):
    """Group matches by date for schedule display"""
    schedule_data = {}
    
    for match in matches:
        try:
            date_obj = convert_to_date(match.date)
            if date_obj:
                date_str = date_obj.strftime('%Y-%m-%d')
                if date_str not in schedule_data:
                    schedule_data[date_str] = {
                        'date': date_obj,
                        'matches': []
                    }
                
                # Enhance match for template using Match class methods
                enhanced_match = enhance_match_for_template(match)
                schedule_data[date_str]['matches'].append(enhanced_match)
        except Exception as e:
            print(f"Error processing match {match.id} for schedule: {str(e)}")
    
    # Sort by date
    return dict(sorted(schedule_data.items()))


def enhance_match_for_template(match):
    """Enhance match object with additional data for template display using Match class methods"""
    try:
        enhanced_match = {
            'id': match.id,
            'home_team_name': match.home_team.name if match.home_team else 'TBD',
            'visitor_team_name': match.visitor_team.name if match.visitor_team else 'TBD',
            'facility_name': match.facility.name if match.facility else 'Unscheduled',
            'league_name': match.league.name if match.league else 'Unknown',
            'date': match.date,
            'date_formatted': convert_to_date(match.date).strftime('%Y-%m-%d') if convert_to_date(match.date) else 'TBD',
            'scheduled_times': match.scheduled_times,
            
            # Use Match class methods for all status and line information
            'num_scheduled_lines': match.get_num_scheduled_lines(),
            'expected_lines': match.get_expected_lines(),
            'is_scheduled': match.is_scheduled(),
            'is_fully_scheduled': match.is_fully_scheduled(),
            'is_partially_scheduled': match.is_partially_scheduled(),
            'status': match.get_status(),
            
            # Keep original objects for template access
            'home_team': match.home_team,
            'visitor_team': match.visitor_team,
            'facility': match.facility,
            'league': match.league
        }
        
        # Add formatted times display
        if enhanced_match['scheduled_times']:
            enhanced_match['times_display'] = ', '.join(enhanced_match['scheduled_times'])
        else:
            enhanced_match['times_display'] = 'No times set'
        
        return enhanced_match
        
    except Exception as e:
        print(f"Error enhancing match {match.id}: {str(e)}")
        # Return basic match info as fallback
        return {
            'id': match.id,
            'home_team_name': str(match.home_team) if match.home_team else 'TBD',
            'visitor_team_name': str(match.visitor_team) if match.visitor_team else 'TBD',
            'facility_name': str(match.facility) if match.facility else 'Unscheduled',
            'league_name': str(match.league) if match.league else 'Unknown',
            'date': match.date,
            'scheduled_times': [],
            'num_scheduled_lines': 0,
            'expected_lines': 0,
            'is_scheduled': False,
            'is_fully_scheduled': False,
            'is_partially_scheduled': False,
            'status': 'error',
            'times_display': 'Error loading times'
        }


def convert_to_date(date_input):
    """Convert various date formats to date object"""
    if not date_input:
        return None
    
    if isinstance(date_input, str):
        try:
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(date_input, '%m/%d/%Y').date()
            except ValueError:
                return None
    elif hasattr(date_input, 'date'):
        return date_input.date()
    else:
        return date_input


def search_matches(matches_list, search_query):
    """Simple search functionality for schedule page using Match class methods"""
    if not search_query:
        return matches_list
    
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    filtered_matches = []
    
    for match in matches_list:
        # Create searchable text from match attributes
        searchable_text = []
        
        # Team names
        if match.home_team:
            searchable_text.append(match.home_team.name.lower())
        if match.visitor_team:
            searchable_text.append(match.visitor_team.name.lower())
        
        # Facility name
        if match.facility:
            searchable_text.append(match.facility.name.lower())
        
        # League name
        if match.league:
            searchable_text.append(match.league.name.lower())
        
        # Date
        if match.date:
            searchable_text.append(str(match.date))
        
        # Times
        if match.scheduled_times:
            searchable_text.extend([time.lower() for time in match.scheduled_times])
        
        # Match ID and status using Match class methods
        searchable_text.append(str(match.id))
        searchable_text.append(match.get_status().lower())
        
        # Add scheduling status terms for better search
        if match.is_scheduled():
            searchable_text.append('scheduled')
        if match.is_fully_scheduled():
            searchable_text.append('fully scheduled')
            searchable_text.append('complete')
        if match.is_partially_scheduled():
            searchable_text.append('partially scheduled')
            searchable_text.append('partial')
        
        # Join all searchable text and check if all terms are found
        full_text = ' '.join(searchable_text)
        matches_all_terms = all(term in full_text for term in search_terms)
        
        if matches_all_terms:
            filtered_matches.append(match)
    
    return filtered_matches


# Export the register function for use in main app
__all__ = ['register_routes']