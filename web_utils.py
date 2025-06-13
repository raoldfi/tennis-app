from typing import Optional, Type, Dict, Any

from datetime import datetime
from usta_league import League
from usta_team import Team
from usta_facility import Facility
from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS


def create_facility_dict_fallback(facility):
    """Fallback function to create facility dictionary if to_yaml_dict method is missing"""
    try:
        # Build schedule dictionary
        schedule_dict = {}
        if hasattr(facility, 'schedule') and facility.schedule:
            for day_name, day_schedule in facility.schedule.get_all_days().items():
                if hasattr(day_schedule, 'start_times') and day_schedule.start_times:
                    # Convert start_times list to dictionary format
                    time_slots = {}
                    for time_str in day_schedule.start_times:
                        # Get courts available for this time slot
                        if hasattr(day_schedule, 'courts_by_time') and day_schedule.courts_by_time:
                            courts = day_schedule.courts_by_time.get(time_str, facility.total_courts)
                        else:
                            courts = facility.total_courts
                        time_slots[time_str] = courts
                    schedule_dict[day_name] = time_slots
        
        # Build the facility dictionary
        facility_dict = {
            'id': facility.id,
            'name': facility.name,
            'location': getattr(facility, 'location', ''),
            'total_courts': getattr(facility, 'total_courts', 0),
            'schedule': schedule_dict,
            'unavailable_dates': getattr(facility, 'unavailable_dates', []) or []
        }
        
        # Add short_name if it exists and is different from name
        if hasattr(facility, 'short_name') and facility.short_name and facility.short_name != facility.name:
            facility_dict['short_name'] = facility.short_name
        
        return facility_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert facility to dictionary: {str(e)}")



# ==================== LEAGUE ROUTES ====================




def create_league_dict_fallback(league):
    """Fallback method to convert League object to dictionary"""
    try:
        league_dict = {
            'id': league.id,
            'name': league.name,
            'year': league.year,
            'section': league.section,
            'region': league.region,
            'age_group': league.age_group,
            'division': league.division,
            'num_matches': league.num_matches,
            'num_lines_per_match': league.num_lines_per_match,
            'allow_split_lines': league.allow_split_lines
        }
        
        # Add optional fields if they exist
        if hasattr(league, 'start_date') and league.start_date:
            league_dict['start_date'] = league.start_date
        if hasattr(league, 'end_date') and league.end_date:
            league_dict['end_date'] = league.end_date
        if hasattr(league, 'preferred_days') and league.preferred_days:
            league_dict['preferred_days'] = league.preferred_days
        
        return league_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert league to dictionary: {str(e)}")


def create_league_from_dict_fallback(league_data):
    """Fallback method to create League object from dictionary"""
    try:
        # Create League with required fields
        league = League(
            id=league_data.get('id'),
            name=league_data['name'],
            year=league_data['year'],
            section=league_data['section'],
            region=league_data['region'],
            age_group=league_data['age_group'],
            division=league_data['division'],
            num_matches=league_data.get('num_matches', 6),
            num_lines_per_match=league_data.get('num_lines_per_match', 4),
            allow_split_lines=league_data.get('allow_split_lines', False)
        )
        
        # Add optional fields if they exist
        if 'start_date' in league_data:
            league.start_date = league_data['start_date']
        if 'end_date' in league_data:
            league.end_date = league_data['end_date']
        if 'preferred_days' in league_data:
            league.preferred_days = league_data['preferred_days']
        
        return league
        
    except Exception as e:
        print(f"Fallback creation error: {str(e)}")
        raise Exception(f"Could not create league from dictionary: {str(e)}")



# ==================== TEAM ROUTES ====================

# Fix for the teams() route in tennis_web_app.py

def enhance_teams_with_facility_info(teams_list, db):
    """
    Enhance teams with facility information for the template
    This function was missing but is required by the teams.html template
    """
    enhanced_teams = []
    
    for team in teams_list:
        # Get facility information
        facility_name = "No facility assigned"
        facility_exists = False
        facility_id = None
        facility_location = None
        
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'name'):
                # Team has a Facility object
                facility_name = team.home_facility.name
                facility_exists = True
                facility_id = getattr(team.home_facility, 'id', None)
                facility_location = getattr(team.home_facility, 'location', None)
            else:
                # Team has a facility name string
                facility_name = str(team.home_facility)
                # Check if this facility exists in the database
                facilities = db.list_facilities()
                for facility in facilities:
                    if facility.name == facility_name:
                        facility_exists = True
                        facility_id = facility.id
                        facility_location = facility.location
                        break
        
        # Check if team has preferred days
        has_preferred_days = (hasattr(team, 'preferred_days') and 
                            team.preferred_days and 
                            len(team.preferred_days) > 0)
        
        # Create enhanced team object
        enhanced_team = {
            'team': team,  # This is what the template expects!
            'facility_name': facility_name,
            'facility_exists': facility_exists,
            'facility_id': facility_id,
            'facility_location': facility_location,
            'has_preferred_days': has_preferred_days
        }
        
        enhanced_teams.append(enhanced_team)
    
    return enhanced_teams





def filter_teams_by_search(teams_list, search_query):
    """
    Filter teams based on search query
    Searches across: team name, captain, facility name, contact email, league name
    """
    if not search_query:
        return teams_list
    
    # Split search query into individual terms for more flexible matching
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    filtered_teams = []
    
    for team in teams_list:
        # Create searchable text from team attributes
        searchable_text = []
        
        # Team name
        if hasattr(team, 'name') and team.name:
            searchable_text.append(team.name.lower())
        
        # Captain name
        if hasattr(team, 'captain') and team.captain:
            searchable_text.append(team.captain.lower())
        
        # Contact email
        if hasattr(team, 'contact_email') and team.contact_email:
            searchable_text.append(team.contact_email.lower())
        
        # League name
        if hasattr(team, 'league') and team.league and hasattr(team.league, 'name'):
            searchable_text.append(team.league.name.lower())
        
        # Facility name
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'name'):
                searchable_text.append(team.home_facility.name.lower())
            else:
                searchable_text.append(str(team.home_facility).lower())
        
        # Join all searchable text
        full_text = ' '.join(searchable_text)
        
        # Check if all search terms are found
        matches_all_terms = all(term in full_text for term in search_terms)
        
        if matches_all_terms:
            filtered_teams.append(team)
    
    return filtered_teams

def search_teams_advanced(teams_list, search_query):
    """
    Advanced search with field-specific matching
    Supports queries like: captain:john facility:club league:3.0
    """
    if not search_query:
        return teams_list
    
    # Parse field-specific search terms
    field_searches = {}
    general_terms = []
    
    # Split by spaces and look for field:value patterns
    terms = search_query.split()
    for term in terms:
        if ':' in term and len(term.split(':', 1)) == 2:
            field, value = term.split(':', 1)
            field = field.lower().strip()
            value = value.lower().strip()
            if field and value:
                if field not in field_searches:
                    field_searches[field] = []
                field_searches[field].append(value)
        else:
            general_terms.append(term.lower().strip())
    
    filtered_teams = []
    
    for team in teams_list:
        matches = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            
            for value in values:
                if field in ['name', 'team']:
                    if hasattr(team, 'name') and team.name and value in team.name.lower():
                        field_match = True
                        break
                elif field in ['captain', 'cap']:
                    if hasattr(team, 'captain') and team.captain and value in team.captain.lower():
                        field_match = True
                        break
                elif field in ['facility', 'fac']:
                    if hasattr(team, 'home_facility') and team.home_facility:
                        facility_name = ""
                        if hasattr(team.home_facility, 'name'):
                            facility_name = team.home_facility.name.lower()
                        elif isinstance(team.home_facility, str):
                            facility_name = team.home_facility.lower()
                        if value in facility_name:
                            field_match = True
                            break
                elif field in ['league', 'lg']:
                    if hasattr(team, 'league') and team.league:
                        if hasattr(team.league, 'name') and team.league.name and value in team.league.name.lower():
                            field_match = True
                            break
                        if hasattr(team.league, 'division') and team.league.division and value in team.league.division.lower():
                            field_match = True
                            break
                elif field in ['email', 'contact']:
                    if hasattr(team, 'contact_email') and team.contact_email and value in team.contact_email.lower():
                        field_match = True
                        break
                elif field in ['day', 'days']:
                    if hasattr(team, 'preferred_days') and team.preferred_days:
                        for day in team.preferred_days:
                            if value in day.lower():
                                field_match = True
                                break
                        if field_match:
                            break
            
            if not field_match:
                matches = False
                break
        
        # Check general search terms (search across all fields)
        if matches and general_terms:
            # Use the existing general search logic
            searchable_text = []
            
            if hasattr(team, 'name') and team.name:
                searchable_text.append(team.name.lower())
            if hasattr(team, 'captain') and team.captain:
                searchable_text.append(team.captain.lower())
            if hasattr(team, 'contact_email') and team.contact_email:
                searchable_text.append(team.contact_email.lower())
            if hasattr(team, 'home_facility') and team.home_facility:
                if hasattr(team.home_facility, 'name') and team.home_facility.name:
                    searchable_text.append(team.home_facility.name.lower())
                elif isinstance(team.home_facility, str):
                    searchable_text.append(team.home_facility.lower())
            if hasattr(team, 'league') and team.league:
                if hasattr(team.league, 'name') and team.league.name:
                    searchable_text.append(team.league.name.lower())
                if hasattr(team.league, 'division') and team.league.division:
                    searchable_text.append(team.league.division.lower())
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches = False
                    break
        
        if matches:
            filtered_teams.append(team)
    
    return filtered_teams






def create_team_dict_fallback(team):
    """Fallback method to convert Team object to dictionary"""
    try:
        team_dict = {
            'id': team.id,
            'name': team.name,
            'league_id': team.league.id if hasattr(team, 'league') and team.league else None,
            'captain': team.captain
        }
        
        # Handle home facility - export the facility ID if available
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'id') and team.home_facility.id:
                team_dict['home_facility_id'] = team.home_facility.id
            # Also include the facility name for reference
            if hasattr(team.home_facility, 'name'):
                team_dict['home_facility_name'] = team.home_facility.name
        elif hasattr(team, 'home_facility_id') and team.home_facility_id:
            # Fallback if only ID is available
            team_dict['home_facility_id'] = team.home_facility_id
        
        # Add optional fields if they exist
        if hasattr(team, 'preferred_days') and team.preferred_days:
            team_dict['preferred_days'] = team.preferred_days
        if hasattr(team, 'contact_email') and team.contact_email:
            team_dict['contact_email'] = team.contact_email
        if hasattr(team, 'notes') and team.notes:
            team_dict['notes'] = team.notes
        
        return team_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert team to dictionary: {str(e)}")


def create_team_from_dict_fallback(team_data, db):
    """Fallback method to create Team object from dictionary"""
    try:
        # Get league object if league_id is provided
        league = None
        if 'league_id' in team_data and team_data['league_id']:
            try:
                league = db.get_league(team_data['league_id'])
                if not league:
                    raise Exception(f"League with ID {team_data['league_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid league_id {team_data['league_id']}: {str(e)}")
        
        # Handle home facility - get the actual Facility object
        home_facility = None
        
        if 'home_facility_id' in team_data and team_data['home_facility_id']:
            # Primary method: use facility ID to get Facility object
            try:
                home_facility = db.get_facility(team_data['home_facility_id'])
                if not home_facility:
                    raise Exception(f"Facility with ID {team_data['home_facility_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid home_facility_id {team_data['home_facility_id']}: {str(e)}")
                
        elif 'home_facility' in team_data and team_data['home_facility']:
            # Legacy support: try to find facility by name
            facility_name = team_data['home_facility']
            try:
                facilities = db.list_facilities()
                for facility in facilities:
                    if facility.name == facility_name:
                        home_facility = facility
                        break
                
                if not home_facility:
                    # Create a minimal facility object for custom names
                    # This depends on your Facility class constructor
                    print(f"Warning: Facility '{facility_name}' not found in database, creating custom facility reference")
                    # You may need to adjust this based on your Facility class constructor
                    from usta import Facility
                    home_facility = Facility(
                        id=None,
                        name=facility_name,
                        location='Unknown',
                        schedule=None  # or create a default schedule
                    )
            except Exception as e:
                print(f"Error looking up facility by name: {str(e)}")
                # Create minimal facility object as fallback
                from usta import Facility
                home_facility = Facility(
                    id=None,
                    name=facility_name,
                    location='Unknown',
                    schedule=None
                )
        
        # Create Team with required fields
        team = Team(
            id=team_data.get('id'),
            name=team_data['name'],
            league=league,
            captain=team_data.get('captain', ''),
            home_facility=home_facility  # Pass the Facility object
        )
        
        # Add optional fields if they exist
        if 'preferred_days' in team_data:
            team.preferred_days = team_data['preferred_days']
        if 'contact_email' in team_data:
            team.contact_email = team_data['contact_email']
        if 'notes' in team_data:
            team.notes = team_data['notes']
        
        return team
        
    except Exception as e:
        print(f"Fallback creation error: {str(e)}")
        raise Exception(f"Could not create team from dictionary: {str(e)}")



# ==================== MATCH ROUTES ====================

# Fix for tennis_web_app.py - Matches route parameter mismatch



def enhance_match_for_template(match):
    """
    Enhanced match object creation for template display
    """
    # Get scheduled times - handle different ways they might be stored
    scheduled_times = []
    if hasattr(match, 'scheduled_times') and match.scheduled_times:
        if isinstance(match.scheduled_times, list):
            scheduled_times = match.scheduled_times
        elif isinstance(match.scheduled_times, str):
            # Handle comma-separated times
            scheduled_times = [time.strip() for time in match.scheduled_times.split(',') if time.strip()]
    
    # Calculate expected lines
    expected_lines = 0
    if hasattr(match, 'league') and match.league and hasattr(match.league, 'num_lines_per_match'):
        expected_lines = match.league.num_lines_per_match
    
    # Determine scheduling status
    has_facility = hasattr(match, 'facility') and match.facility is not None
    has_date = hasattr(match, 'date') and match.date is not None
    num_scheduled_lines = len(scheduled_times)
    
    is_fully_scheduled = (has_facility and has_date and 
                         num_scheduled_lines >= expected_lines and expected_lines > 0)
    is_partially_scheduled = (has_facility and has_date and 
                            num_scheduled_lines > 0 and num_scheduled_lines < expected_lines)
    
    # Determine status text
    if is_fully_scheduled:
        status = "Fully Scheduled"
    elif is_partially_scheduled:
        status = f"Partially Scheduled ({num_scheduled_lines}/{expected_lines})"
    elif has_facility and has_date:
        status = "Location/Date Set"
    else:
        status = "Unscheduled"
    
    # Determine missing fields
    missing_fields = []
    if not has_facility:
        missing_fields.append('Facility')
    if not has_date:
        missing_fields.append('Date')
    if num_scheduled_lines < expected_lines:
        if expected_lines > 0:
            missing_fields.append(f'Times ({num_scheduled_lines}/{expected_lines})')
        elif num_scheduled_lines == 0:
            missing_fields.append('Times')
    
    # Create enhanced match object
    enhanced_match = {
        'id': match.id,
        'home_team_name': match.home_team.name if hasattr(match, 'home_team') and match.home_team else 'Unknown',
        'visitor_team_name': match.visitor_team.name if hasattr(match, 'visitor_team') and match.visitor_team else 'Unknown',
        'facility_name': match.facility.name if has_facility else 'No Facility Assigned',
        'facility_id': match.facility.id if has_facility else None,
        'league_name': match.league.name if hasattr(match, 'league') and match.league else 'Unknown',
        'date': match.date,
        'time': ', '.join(scheduled_times) if scheduled_times else 'Not Scheduled',
        'scheduled_times': scheduled_times,
        'status': status,
        'num_scheduled_lines': num_scheduled_lines,
        'expected_lines': expected_lines,
        'is_fully_scheduled': is_fully_scheduled,
        'is_partially_scheduled': is_partially_scheduled,
        'missing_fields': missing_fields,
        'has_facility': has_facility,
        'has_date': has_date
    }
    
    return enhanced_match


def filter_matches(matches_list, start_date, end_date, search_query):
    """
    Filter matches based on date range and search query
    """
    filtered_matches = matches_list
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and m.date >= start_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and m.date <= end_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    # Apply search filter
    if search_query:
        filtered_matches = filter_matches_by_search(filtered_matches, search_query)
    
    return filtered_matches


def filter_matches_by_search(matches_list, search_query):
    """
    Search functionality that works with match objects
    """
    if not search_query:
        return matches_list
    
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    filtered_matches = []
    
    for match in matches_list:
        # Create searchable text from match attributes
        searchable_text = []
        
        # Team names
        if hasattr(match, 'home_team') and match.home_team and hasattr(match.home_team, 'name'):
            searchable_text.append(match.home_team.name.lower())
        if hasattr(match, 'visitor_team') and match.visitor_team and hasattr(match.visitor_team, 'name'):
            searchable_text.append(match.visitor_team.name.lower())
        
        # Facility name
        if hasattr(match, 'facility') and match.facility and hasattr(match.facility, 'name'):
            searchable_text.append(match.facility.name.lower())
        
        # League name
        if hasattr(match, 'league') and match.league and hasattr(match.league, 'name'):
            searchable_text.append(match.league.name.lower())
        
        # Date
        if hasattr(match, 'date') and match.date:
            searchable_text.append(str(match.date))
        
        # Times
        if hasattr(match, 'scheduled_times') and match.scheduled_times:
            if isinstance(match.scheduled_times, list):
                searchable_text.extend([time.lower() for time in match.scheduled_times])
            else:
                searchable_text.append(str(match.scheduled_times).lower())
        
        # Match ID
        searchable_text.append(str(match.id))
        
        # Join all searchable text
        full_text = ' '.join(searchable_text)
        
        # Check if all search terms are found
        matches_all_terms = all(term in full_text for term in search_terms)
        
        if matches_all_terms:
            filtered_matches.append(match)
    
    return filtered_matches



def _calculate_status(match, scheduled_times):
    """Calculate status when Match class doesn't have get_status method"""
    if not match.facility or not match.date:
        return "Unscheduled"
    
    if not scheduled_times:
        return "Location/Date Set"
    
    expected_lines = match.league.num_lines_per_match if match.league else 0
    scheduled_lines = len(scheduled_times)
    
    if scheduled_lines >= expected_lines:
        return "Fully Scheduled"
    elif scheduled_lines > 0:
        return f"Partially Scheduled ({scheduled_lines}/{expected_lines})"
    else:
        return "Location/Date Set"


def _is_scheduled(match, scheduled_times):
    """Calculate if scheduled when Match class doesn't have is_scheduled method"""
    expected_lines = match.league.num_lines_per_match if match.league else 0
    return (match.facility is not None and 
            match.date is not None and 
            len(scheduled_times) >= expected_lines)






# Alternative function to get match status for cleaner code
def get_match_status(match):
    """Helper function to determine match status"""
    if not match.facility:
        return 'Unscheduled'
    elif not match.date or not match.time:
        return 'Partially Scheduled'
    else:
        return 'Scheduled'







def search_matches_advanced(matches_list, search_query):
    """
    Advanced search with field-specific matching
    Supports queries like: home:lightning facility:club date:2025-01 status:scheduled
    """
    if not search_query:
        return matches_list
    
    # Parse field-specific search terms
    field_searches = {}
    general_terms = []
    
    # Split by spaces and look for field:value patterns
    terms = search_query.split()
    for term in terms:
        if ':' in term and len(term.split(':', 1)) == 2:
            field, value = term.split(':', 1)
            field = field.lower().strip()
            value = value.lower().strip()
            if field and value:
                if field not in field_searches:
                    field_searches[field] = []
                field_searches[field].append(value)
        else:
            general_terms.append(term.lower().strip())
    
    filtered_matches = []
    
    for match in matches_list:
        matches = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            
            for value in values:
                if field in ['home', 'home_team']:
                    if match.get('home_team_name') and value in match['home_team_name'].lower():
                        field_match = True
                        break
                elif field in ['visitor', 'visitor_team', 'away']:
                    if match.get('visitor_team_name') and value in match['visitor_team_name'].lower():
                        field_match = True
                        break
                elif field in ['team', 'teams']:
                    home_match = match.get('home_team_name') and value in match['home_team_name'].lower()
                    visitor_match = match.get('visitor_team_name') and value in match['visitor_team_name'].lower()
                    if home_match or visitor_match:
                        field_match = True
                        break
                elif field in ['facility', 'venue']:
                    if match.get('facility_name') and value in match['facility_name'].lower():
                        field_match = True
                        break
                elif field in ['league', 'lg']:
                    if match.get('league_name') and value in match['league_name'].lower():
                        field_match = True
                        break
                elif field in ['date', 'day']:
                    if match.get('date') and value in str(match['date']).lower():
                        field_match = True
                        break
                elif field in ['time']:
                    if match.get('time') and value in str(match['time']).lower():
                        field_match = True
                        break
                elif field in ['status']:
                    if match.get('status') and value in match['status'].lower():
                        field_match = True
                        break
                elif field in ['id', 'match_id']:
                    if value in str(match['id']):
                        field_match = True
                        break
                elif field in ['captain']:
                    home_captain_match = match.get('home_team_captain') and value in match['home_team_captain'].lower()
                    visitor_captain_match = match.get('visitor_team_captain') and value in match['visitor_team_captain'].lower()
                    if home_captain_match or visitor_captain_match:
                        field_match = True
                        break
                elif field in ['division', 'div']:
                    if match.get('league_division') and value in match['league_division'].lower():
                        field_match = True
                        break
                elif field in ['year']:
                    if match.get('league_year') and value in str(match['league_year']):
                        field_match = True
                        break
            
            if not field_match:
                matches = False
                break
        
        # Check general search terms (search across all fields)
        if matches and general_terms:
            # Use the existing general search logic
            searchable_text = []
            
            if match.get('home_team_name'):
                searchable_text.append(match['home_team_name'].lower())
            if match.get('visitor_team_name'):
                searchable_text.append(match['visitor_team_name'].lower())
            if match.get('facility_name') and match['facility_name'] != 'Unknown':
                searchable_text.append(match['facility_name'].lower())
            if match.get('league_name') and match['league_name'] != 'Unassigned':
                searchable_text.append(match['league_name'].lower())
            if match.get('date'):
                searchable_text.append(str(match['date']).lower())
            if match.get('status'):
                searchable_text.append(match['status'].lower())
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches = False
                    break
        
        if matches:
            filtered_matches.append(match)
    
    return filtered_matches


# Enhanced match status tracking for better search results
def get_match_status_details(match):
    """
    Get detailed status information for a match to help with search
    """
    status_info = {
        'is_fully_scheduled': match.is_scheduled(),
        'status': match.get_status(),
        'missing_fields': match.get_missing_fields(),
        'has_facility': bool(match.facility_id),
        'has_date': bool(match.date),
        'has_time': bool(match.time),
        'scheduling_completeness': 0
    }
    
    # Calculate scheduling completeness percentage
    required_fields = ['facility_id', 'date', 'time']
    completed_fields = sum(1 for field in required_fields if getattr(match, field, None))
    status_info['scheduling_completeness'] = (completed_fields / len(required_fields)) * 100
    
    return status_info





# ==================== API ROUTES ====================





# ==================== HELPER FUNCTIONS ====================

def get_usta_constants() -> Dict[str, list]:
    """Get USTA constants from the usta module"""
    from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
    return {
        'sections': USTA_SECTIONS,
        'regions': USTA_REGIONS,
        'age_groups': USTA_AGE_GROUPS,
        'divisions': USTA_DIVISIONS
    }

# ==================== OTHER ROUTES ====================





# Add this route to tennis_web_app.py after the existing matches route
# ==================== SCHEDULE OUTPUT  ====================

# Updated schedule() route in tennis_web_app.py




def filter_schedule_by_search(matches_by_date, search_query):
    """Filter schedule matches by search query"""
    if not search_query:
        return matches_by_date
    
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    if not search_terms:
        return matches_by_date
    
    filtered_by_date = {}
    
    for date, matches in matches_by_date.items():
        filtered_matches = []
        
        for match_data in matches:
            match = match_data['match']
            
            # Build searchable content from match objects
            searchable_text = ' '.join([
                match.home_team.name,
                match.visitor_team.name,
                match.league.name,
                match.facility.name if match.facility else '',
                getattr(match.facility, 'location', '') if match.facility else '',
                ' '.join(match.scheduled_times)
            ]).lower()
            
            if all(term in searchable_text for term in search_terms):
                filtered_matches.append(match_data)
        
        if filtered_matches:
            filtered_by_date[date] = filtered_matches
    
    return filtered_by_date
    




def search_schedule_matches_advanced(matches_list, search_query):
    """
    Advanced search for schedule matches with field-specific matching
    Supports queries like: home:lightning facility:club date:2025-01 time:morning
    """
    if not search_query:
        return matches_list
    
    # Parse field-specific search terms
    field_searches = {}
    general_terms = []
    
    # Split by spaces and look for field:value patterns
    terms = search_query.split()
    for term in terms:
        if ':' in term and len(term.split(':', 1)) == 2:
            field, value = term.split(':', 1)
            field = field.lower().strip()
            value = value.lower().strip()
            if field and value:
                if field not in field_searches:
                    field_searches[field] = []
                field_searches[field].append(value)
        else:
            general_terms.append(term.lower().strip())
    
    filtered_matches = []
    
    for match in matches_list:
        matches = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            
            for value in values:
                if field in ['home', 'home_team']:
                    if match.get('home_team_name') and value in match['home_team_name'].lower():
                        field_match = True
                        break
                elif field in ['visitor', 'visitor_team', 'away']:
                    if match.get('visitor_team_name') and value in match['visitor_team_name'].lower():
                        field_match = True
                        break
                elif field in ['team', 'teams']:
                    home_match = match.get('home_team_name') and value in match['home_team_name'].lower()
                    visitor_match = match.get('visitor_team_name') and value in match['visitor_team_name'].lower()
                    if home_match or visitor_match:
                        field_match = True
                        break
                elif field in ['facility', 'venue']:
                    if match.get('facility_name') and value in match['facility_name'].lower():
                        field_match = True
                        break
                elif field in ['league', 'lg']:
                    if match.get('league_name') and value in match['league_name'].lower():
                        field_match = True
                        break
                elif field in ['date', 'day']:
                    if match.get('date'):
                        date_str = str(match['date']).lower()
                        if value in date_str:
                            field_match = True
                            break
                        # Check day names and month names
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(str(match['date']), '%Y-%m-%d')
                            if (value in date_obj.strftime('%A').lower() or  # Full day name
                                value in date_obj.strftime('%a').lower() or  # Short day name
                                value in date_obj.strftime('%B').lower() or  # Full month name
                                value in date_obj.strftime('%b').lower()):   # Short month name
                                field_match = True
                                break
                        except ValueError:
                            pass
                elif field in ['time']:
                    if match.get('time') and value in str(match['time']).lower():
                        field_match = True
                        break
                    # Support time range searches
                    elif match.get('time'):
                        try:
                            time_str = str(match['time'])
                            hour = int(time_str.split(':')[0])
                            if value == 'morning' and 6 <= hour < 12:
                                field_match = True
                                break
                            elif value == 'afternoon' and 12 <= hour < 18:
                                field_match = True
                                break
                            elif value == 'evening' and 18 <= hour < 24:
                                field_match = True
                                break
                        except (ValueError, IndexError):
                            pass
                elif field in ['status']:
                    if match.get('status') and value in match['status'].lower():
                        field_match = True
                        break
                elif field in ['id', 'match_id']:
                    if value in str(match['id']):
                        field_match = True
                        break
                elif field in ['captain']:
                    home_captain_match = match.get('home_team_captain') and value in match['home_team_captain'].lower()
                    visitor_captain_match = match.get('visitor_team_captain') and value in match['visitor_team_captain'].lower()
                    if home_captain_match or visitor_captain_match:
                        field_match = True
                        break
                elif field in ['division', 'div']:
                    if match.get('league_division') and value in match['league_division'].lower():
                        field_match = True
                        break
                elif field in ['year']:
                    if match.get('league_year') and value in str(match['league_year']):
                        field_match = True
                        break
            
            if not field_match:
                matches = False
                break
        
        # Check general search terms (search across all fields)
        if matches and general_terms:
            searchable_text = []
            
            if match.get('home_team_name') and match['home_team_name'] != 'Unknown':
                searchable_text.append(match['home_team_name'].lower())
            if match.get('visitor_team_name') and match['visitor_team_name'] != 'Unknown':
                searchable_text.append(match['visitor_team_name'].lower())
            if match.get('facility_name') and match['facility_name'] not in ['Unknown', 'No Facility Assigned']:
                searchable_text.append(match['facility_name'].lower())
            if match.get('league_name') and match['league_name'] != 'Unknown':
                searchable_text.append(match['league_name'].lower())
            if match.get('date'):
                searchable_text.append(str(match['date']).lower())
            if match.get('time'):
                searchable_text.append(str(match['time']).lower())
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches = False
                    break
        
        if matches:
            filtered_matches.append(match)
    
    return filtered_matches
        


