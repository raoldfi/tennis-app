"""
Updated web_matches.py - Includes bulk operations for auto-schedule, unschedule, and delete
Fixed to pass Match objects to template instead of dictionaries
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date, timedelta
import traceback
import json

from usta import Match, MatchType, League


def register_routes(app, get_db):
    """Register match-related routes with Flask app"""
    
    @app.route('/matches')
    def matches():
        """Display matches with filtering and search"""
        db = get_db()
        if not db:
            return redirect(url_for('connect'))
        
        try:
            # Get filter parameters
            league_id = request.args.get('league_id', type=int)
            match_type_str = request.args.get('match_type', 'all')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            search_query = request.args.get('search', '').strip()
            show_scheduled = request.args.get('show_scheduled', 'true') == 'true'
            show_unscheduled = request.args.get('show_unscheduled', 'true') == 'true'

            print(f"Trying to get Matches for League = {league_id}, match_type={match_type_str}")
            
            # Convert league_id to League object
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    flash(f'League with ID {league_id} not found', 'error')
                    league_id = None  # Reset to show all matches
            
            # Convert match_type string to MatchType enum using from_string()
            try:
                match_type = MatchType.from_string(match_type_str)
            except ValueError as e:
                print(f"Invalid match_type '{match_type_str}': {e}")
                flash(f'Invalid match type: {match_type_str}', 'error')
                match_type = MatchType.ALL  # Default to ALL if invalid
            
            # Get matches with proper parameters
            matches_list = db.list_matches(
                league=league,     # Pass League object, not league_id
                match_type=match_type  # Pass MatchType enum, not string
            )
            
            # Apply filters
            filtered_matches = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Apply scheduling filter
            if not show_scheduled:
                filtered_matches = [m for m in filtered_matches if not m.is_scheduled()]
            if not show_unscheduled:
                filtered_matches = [m for m in filtered_matches if m.is_scheduled()]
            
            # FIXED: Pass original Match objects to template instead of converting to dicts
            # The template expects Match objects with methods like get_scheduled_times()
            matches_display = filtered_matches  # Don't convert to display format
            
            # Get leagues for filter dropdown
            leagues = db.list_leagues()
            selected_league = db.get_league(league_id) if league_id else None
            
            return render_template('matches.html',
                                 matches=matches_display,  # Pass Match objects directly
                                 leagues=leagues,
                                 selected_league=selected_league,
                                 match_type=str(match_type_str),
                                 start_date=start_date,
                                 end_date=end_date,
                                 search_query=search_query,
                                 show_scheduled=show_scheduled,
                                 show_unscheduled=show_unscheduled)
        
        except Exception as e:
            print(f"Error in matches route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading matches: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
    
    @app.route('/match/<int:match_id>')
    def view_match(match_id):
        """View match details"""
        db = get_db()
        if not db:
            return redirect(url_for('connect'))
        
        try:
            match = db.get_match(match_id)
            if not match:
                flash('Match not found', 'error')
                return redirect(url_for('matches'))
            
            return render_template('view_match.html', match=match)
            
        except Exception as e:
            print(f"Error loading match {match_id}: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading match: {str(e)}', 'error')
            return redirect(url_for('matches'))

    @app.route('/matches/<int:match_id>/schedule', methods=['POST'])
    def schedule_match(match_id):
        """Schedule a match"""
        print(f"\n=== SCHEDULE MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Get form data
            facility_id = request.form.get('facility_id', type=int)
            date_str = request.form.get('date')
            times = request.form.getlist('times')
            
            print(f"Scheduling data: facility_id={facility_id}, date={date_str}, times={times}")
            
            # Validate inputs
            if not facility_id:
                return jsonify({'error': 'Facility is required'}), 400
            
            if not date_str:
                return jsonify({'error': 'Date is required'}), 400
            
            if not times:
                return jsonify({'error': 'At least one time slot is required'}), 400
            
            # Get facility
            facility = db.get_facility(facility_id)
            if not facility:
                return jsonify({'error': 'Invalid facility'}), 400
            
            # Parse date
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
            
            # Update match
            match.facility = facility
            match.date = match_date
            match.scheduled_times = times
            
            # Save to database
            db.update_match(match)
            
            print(f"Match {match_id} scheduled successfully")
            
            return jsonify({
                'success': True,
                'message': f'Match scheduled for {date_str} at {facility.name}'
            })
            
        except Exception as e:
            print(f"Schedule match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Scheduling failed: {str(e)}'}), 500

    @app.route('/matches/<int:match_id>/schedule', methods=['DELETE'])
    def clear_match_schedule(match_id):
        """Clear a match's schedule"""
        print(f"\n=== CLEAR SCHEDULE FOR MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Clear scheduling info
            match.facility = None
            match.date = None
            match.scheduled_times = []
            
            # Save to database
            db.update_match(match)
            
            print(f"Schedule cleared for match {match_id}")
            
            return jsonify({
                'success': True,
                'message': 'Match schedule cleared successfully'
            })
            
        except Exception as e:
            print(f"Clear schedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Failed to clear schedule: {str(e)}'}), 500

    @app.route('/matches/<int:match_id>', methods=['DELETE'])
    def delete_match(match_id):
        """Delete an unscheduled match"""
        print(f"\n=== DELETE MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Safety check - only allow deletion of unscheduled matches
            if match.is_scheduled():
                return jsonify({'error': 'Cannot delete scheduled matches. Unschedule first for safety.'}), 400
            
            db.delete_match(match_id)
            
            return jsonify({
                'success': True,
                'message': 'Match deleted successfully'
            })
            
        except Exception as e:
            print(f"Delete match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Deletion failed: {str(e)}'}), 500


    # ==================== Bulk Operations ====================

    @app.route('/api/import-matches', methods=['POST'])
    def api_import_matches():
        """API endpoint for importing matches from YAML"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
    
        try:
            # Validate file upload
            if 'yaml_file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
    
            file = request.files['yaml_file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
    
            if not file.filename.lower().endswith(('.yaml', '.yml')):
                return jsonify({'error': 'File must be a YAML file (.yaml or .yml)'}), 400
    
            # Read and parse YAML content
            try:
                yaml_content = file.read().decode('utf-8')
                data = yaml.safe_load(yaml_content)
            except UnicodeDecodeError:
                return jsonify({'error': 'File must be valid UTF-8 text'}), 400
            except yaml.YAMLError as e:
                return jsonify({'error': f'Invalid YAML format: {str(e)}'}), 400
    
            # Validate data structure
            if not isinstance(data, list):
                return jsonify({'error': 'YAML must contain a list of matches'}), 400
    
            return jsonify({'message': 'Match import endpoint not yet implemented', 'imported_count': 0})
    
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # ==================== Bulk Operations ====================
    
    @app.route('/api/bulk-auto-schedule', methods=['POST'])
    def bulk_auto_schedule():
        """Bulk auto-schedule matches using db.auto_schedule_matches"""
        print(f"\n=== BULK AUTO-SCHEDULE ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get scope and parameters
            scope = request.form.get('scope', 'all')
            league_id = request.form.get('league_id', type=int)
            
            print(f"Bulk auto-schedule scope: {scope}, league_id: {league_id}")
            
            # Determine which matches to schedule - use MatchType.UNSCHEDULED directly
            matches_to_schedule = []
            
            if scope == 'all':
                # All unscheduled matches - use MatchType.UNSCHEDULED directly
                matches_to_schedule = db.list_matches(match_type=MatchType.UNSCHEDULED)
                
            elif scope == 'league' and league_id:
                # Specific league only - get unscheduled matches for that league
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League {league_id} not found'}), 400
                
                matches_to_schedule = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                
            elif scope == 'selected':
                # Apply current filter parameters to get the same matches as displayed
                league_id_filter = request.form.get('league_id', type=int)
                match_type_str = request.form.get('match_type', 'all')
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                search_query = request.form.get('search', '').strip()
                
                # Get filtered matches - if original filter was for unscheduled, use that directly
                league = db.get_league(league_id_filter) if league_id_filter else None
                
                # For selected scope, we want unscheduled matches from the current view
                # So we use UNSCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                matches_to_schedule = filter_matches(all_matches, start_date, end_date, search_query)
            
            else:
                return jsonify({'error': 'Invalid scope or missing parameters'}), 400
            
            if not matches_to_schedule:
                return jsonify({
                    'success': True,
                    'message': 'No unscheduled matches found to schedule',
                    'scheduled_count': 0,
                    'total_count': 0
                })
            
            print(f"Found {len(matches_to_schedule)} unscheduled matches to auto-schedule")
            
            # Use the database's auto_schedule_matches method
            try:
                results = db.auto_schedule_matches(matches_to_schedule)
                
                # Extract results
                scheduled_count = results.get('scheduled', 0)
                failed_count = results.get('failed', 0)
                errors = results.get('errors', [])
                
                print(f"Auto-scheduling results: {scheduled_count} scheduled, {failed_count} failed")
                
                # Prepare response message
                if scheduled_count > 0 and failed_count == 0:
                    message = f"Successfully auto-scheduled all {scheduled_count} matches"
                elif scheduled_count > 0 and failed_count > 0:
                    message = f"Auto-scheduled {scheduled_count} of {len(matches_to_schedule)} matches. {failed_count} could not be scheduled."
                elif scheduled_count == 0:
                    message = f"Could not auto-schedule any of the {len(matches_to_schedule)} matches. No available time slots found."
                else:
                    message = f"Auto-scheduled {scheduled_count} of {len(matches_to_schedule)} matches"
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'scheduled_count': scheduled_count,
                    'failed_count': failed_count,
                    'total_count': len(matches_to_schedule),
                    'errors': errors[:5] if errors else []  # Limit error details
                })
                
            except AttributeError:
                # Fallback if db.auto_schedule_matches doesn't exist
                return jsonify({
                    'error': 'Auto-scheduling functionality not available. Database method auto_schedule_matches not found.'
                }), 500
                
            except Exception as db_error:
                print(f"Database auto-scheduling error: {str(db_error)}")
                return jsonify({
                    'error': f'Auto-scheduling failed: {str(db_error)}'
                }), 500
            
        except Exception as e:
            print(f"Bulk auto-schedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk auto-schedule failed: {str(e)}'}), 500
    
    
    @app.route('/api/bulk-unschedule', methods=['POST'])
    def bulk_unschedule():
        """Bulk unschedule matches"""
        print(f"\n=== BULK UNSCHEDULE ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get scope and parameters
            scope = request.form.get('scope', 'all')
            league_id = request.form.get('league_id', type=int)
            
            print(f"Bulk unschedule scope: {scope}, league_id: {league_id}")
            
            # Determine which matches to unschedule - use MatchType.SCHEDULED directly
            matches_to_unschedule = []
            
            if scope == 'all':
                # All scheduled matches - use MatchType.SCHEDULED directly
                matches_to_unschedule = db.list_matches(match_type=MatchType.SCHEDULED)
                
            elif scope == 'league' and league_id:
                # Specific league only - get scheduled matches for that league
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League {league_id} not found'}), 400
                
                matches_to_unschedule = db.list_matches(league=league, match_type=MatchType.SCHEDULED)
                
            elif scope == 'selected':
                # Apply current filter parameters to get the same matches as displayed
                league_id_filter = request.form.get('league_id', type=int)
                match_type_str = request.form.get('match_type', 'all')
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                search_query = request.form.get('search', '').strip()
                
                # Get filtered matches - for unscheduling, we want scheduled matches from the current view
                league = db.get_league(league_id_filter) if league_id_filter else None
                
                # For selected scope, we want scheduled matches from the current view
                # So we use SCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(league=league, match_type=MatchType.SCHEDULED)
                matches_to_unschedule = filter_matches(all_matches, start_date, end_date, search_query)
            
            else:
                return jsonify({'error': 'Invalid scope or missing parameters'}), 400
            
            if not matches_to_unschedule:
                return jsonify({
                    'success': True,
                    'message': 'No scheduled matches found to unschedule',
                    'unscheduled_count': 0,
                    'total_count': 0
                })
            
            print(f"Found {len(matches_to_unschedule)} scheduled matches to unschedule")
            
            # Unschedule each match
            unscheduled_count = 0
            errors = []
            
            for match in matches_to_unschedule:
                try:
                    # Clear scheduling info
                    match.facility = None
                    match.date = None
                    match.scheduled_times = []
                    
                    # Save to database
                    db.update_match(match)
                    unscheduled_count += 1
                    print(f"Successfully unscheduled match {match.id}")
                    
                except Exception as e:
                    errors.append(f"Error unscheduling match {match.id}: {str(e)}")
                    print(f"Error unscheduling match {match.id}: {str(e)}")
            
            # Prepare response
            message = f"Unscheduled {unscheduled_count} of {len(matches_to_unschedule)} matches"
            if errors:
                message += f". {len(errors)} matches could not be unscheduled."
            
            return jsonify({
                'success': True,
                'message': message,
                'unscheduled_count': unscheduled_count,
                'total_count': len(matches_to_unschedule),
                'errors': errors[:5]  # Limit error details
            })
            
        except Exception as e:
            print(f"Bulk unschedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk unschedule failed: {str(e)}'}), 500
    
    
    @app.route('/api/bulk-delete', methods=['POST'])
    def bulk_delete():
        """Bulk delete unscheduled matches (safety restriction)"""
        print(f"\n=== BULK DELETE ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get scope and parameters
            scope = request.form.get('scope', 'unscheduled')  # Default to unscheduled only
            league_id = request.form.get('league_id', type=int)
            
            print(f"Bulk delete scope: {scope}, league_id: {league_id}")
            
            # Determine which matches to delete - use MatchType.UNSCHEDULED directly for safety
            matches_to_delete = []
            
            if scope == 'unscheduled':
                # All unscheduled matches - use MatchType.UNSCHEDULED directly
                matches_to_delete = db.list_matches(match_type=MatchType.UNSCHEDULED)
                
            elif scope == 'league' and league_id:
                # Unscheduled matches in specific league only
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League {league_id} not found'}), 400
                
                matches_to_delete = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                
            elif scope == 'selected':
                # Apply current filter parameters, but only unscheduled
                league_id_filter = request.form.get('league_id', type=int)
                match_type_str = request.form.get('match_type', 'all')
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                search_query = request.form.get('search', '').strip()
                
                # Get filtered matches - for deletion, we only want unscheduled matches for safety
                league = db.get_league(league_id_filter) if league_id_filter else None
                
                # For selected scope, we only delete unscheduled matches for safety
                # So we use UNSCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
                matches_to_delete = filter_matches(all_matches, start_date, end_date, search_query)
            
            else:
                return jsonify({'error': 'Invalid scope or missing parameters'}), 400
            
            if not matches_to_delete:
                return jsonify({
                    'success': True,
                    'message': 'No unscheduled matches found to delete',
                    'deleted_count': 0,
                    'total_count': 0
                })
            
            print(f"Found {len(matches_to_delete)} unscheduled matches to delete")
            
            # Delete each match
            deleted_count = 0
            errors = []
            
            for match in matches_to_delete:
                try:
                    # Double-check it's unscheduled for safety (though we got them via UNSCHEDULED query)
                    if match.is_scheduled():
                        errors.append(f"Match {match.id} is scheduled - skipped for safety")
                        continue
                    
                    # Delete the match
                    db.delete_match(match.id)
                    deleted_count += 1
                    print(f"Successfully deleted match {match.id}")
                    
                except Exception as e:
                    errors.append(f"Error deleting match {match.id}: {str(e)}")
                    print(f"Error deleting match {match.id}: {str(e)}")
            
            # Prepare response
            message = f"Deleted {deleted_count} of {len(matches_to_delete)} unscheduled matches"
            if errors:
                message += f". {len(errors)} matches could not be deleted."
            
            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count,
                'total_count': len(matches_to_delete),
                'errors': errors[:5]  # Limit error details
            })
            
        except Exception as e:
            print(f"Bulk delete error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk delete failed: {str(e)}'}), 500


# ==================== HELPER FUNCTIONS ====================

def filter_matches(matches_list, start_date, end_date, search_query):
    """Filter matches based on date range and search query"""
    filtered_matches = matches_list
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and parse_match_date(m.date) >= start_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and parse_match_date(m.date) <= end_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    # Apply search filter
    if search_query:
        filtered_matches = search_matches(filtered_matches, search_query)
    
    return filtered_matches


def parse_match_date(date_value):
    """Parse match date to datetime.date object"""
    if isinstance(date_value, date):
        return date_value
    elif isinstance(date_value, datetime):
        return date_value.date()
    elif isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(date_value, '%m/%d/%Y').date()
            except ValueError:
                return None
    return None


def search_matches(matches_list, search_query):
    """Enhanced search functionality for matches with field-specific search"""
    if not search_query:
        return matches_list
    
    # Parse search query into field-specific and general terms
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    field_specific_terms = []
    general_terms = []
    
    for term in search_terms:
        if ':' in term:
            field_specific_terms.append(term.split(':', 1))
        else:
            general_terms.append(term)
    
    filtered_matches = []
    
    for match in matches_list:
        matches_query = True
        
        # Check field-specific terms
        for field, value in field_specific_terms:
            field_match = False
            
            if field in ['team', 'teams']:
                if ((match.home_team and value in match.home_team.name.lower()) or
                    (match.visitor_team and value in match.visitor_team.name.lower())):
                    field_match = True
            elif field in ['facility', 'venue']:
                if match.facility and value in match.facility.name.lower():
                    field_match = True
            elif field in ['league']:
                if match.league and value in match.league.name.lower():
                    field_match = True
            elif field in ['date']:
                if match.date and value in str(match.date).lower():
                    field_match = True
            elif field in ['status']:
                if value in match.get_status().lower():
                    field_match = True
            elif field in ['captain']:
                # Search in both team captains
                home_captain_match = (match.home_team and match.home_team.captain and 
                                    value in match.home_team.captain.lower())
                visitor_captain_match = (match.visitor_team and match.visitor_team.captain and 
                                      value in match.visitor_team.captain.lower())
                if home_captain_match or visitor_captain_match:
                    field_match = True
            elif field in ['division', 'div']:
                if match.league and match.league.division and value in match.league.division.lower():
                    field_match = True
            elif field in ['year']:
                if match.league and match.league.year and value in str(match.league.year):
                    field_match = True
            
            if not field_match:
                matches_query = False
                break
        
        # Check general search terms (search across all fields)
        if matches_query and general_terms:
            searchable_text = []
            
            if match.home_team:
                searchable_text.append(match.home_team.name.lower())
            if match.visitor_team:
                searchable_text.append(match.visitor_team.name.lower())
            if match.facility:
                searchable_text.append(match.facility.name.lower())
            if match.league:
                searchable_text.append(match.league.name.lower())
            if match.date:
                searchable_text.append(str(match.date).lower())
            if match.scheduled_times:
                searchable_text.extend([time.lower() for time in match.scheduled_times])
            
            # Add status using Match class method
            searchable_text.append(match.get_status().lower())
            searchable_text.append(str(match.id))
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches_query = False
                    break
        
        if matches_query:
            filtered_matches.append(match)
    
    return filtered_matches


# Export the register function for use in main app
__all__ = ['register_routes']