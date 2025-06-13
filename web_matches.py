
from typing import Optional, Type, Dict, Any

from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import traceback

from web_database import get_db
from web_utils import enhance_match_for_template, filter_matches

def register_routes(app):
    """Register match-related routes"""


    
    @app.route('/matches')
    def matches():
        """Matches page - FIXED parameter mismatch for include unscheduled"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters - FIXED: Handle both parameter names
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search', '').strip()
        
        # CRITICAL FIX: Template uses 'show_unscheduled' but backend expects 'include_unscheduled'
        show_unscheduled = request.args.get('show_unscheduled', 'false').lower() == 'true'
        include_unscheduled = request.args.get('include_unscheduled', 'true').lower() == 'true'
        
        # Use either parameter name - prioritize show_unscheduled since that's what the template uses
        include_unscheduled = show_unscheduled or include_unscheduled
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
            
            # Get matches - Pass League object instead of ID
            matches_list = db.list_matches(selected_league, include_unscheduled)
            
            # Apply additional filters
            if start_date or end_date or search_query:
                matches_list = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Enhance matches for template display
            enhanced_matches = []
            for match in matches_list:
                enhanced_match = enhance_match_for_template(match)
                enhanced_matches.append(enhanced_match)
            
            # Get leagues for filter dropdown
            leagues_list = db.list_leagues()
            
            return render_template('matches.html', 
                                 matches=enhanced_matches,
                                 leagues=leagues_list,
                                 selected_league=selected_league,
                                 search_query=search_query,
                                 start_date=start_date,
                                 end_date=end_date,
                                 show_unscheduled=show_unscheduled,  # Use show_unscheduled for template
                                 include_unscheduled=include_unscheduled)  # Keep both for compatibility
            
        except Exception as e:
            flash(f'Error loading matches: {e}', 'error')
            return redirect(url_for('index'))
    
    
    @app.route('/matches')
    def list_matches():
        """
        List all matches  
        UPDATED: Much simpler since Match objects contain all needed data
        """
        db = get_db()
        if not db:
            return render_template('connect.html')
        
        try:
            # Get matches with full object data
            matches = db.list_matches()  # Now returns Match objects with League/Team/Facility objects
            
            # No need for separate team/facility/league lookups!
            # Template can directly access match.home_team.name, match.facility.location, etc.
            
            enhanced_matches = []
            for match in matches:
                enhanced_match = {
                    'id': match.id,
                    'home_team_name': match.home_team.name,           # Direct access!
                    'visitor_team_name': match.visitor_team.name,     # Direct access!
                    'league_name': match.league.name,                # Direct access!
                    'facility_name': match.facility.name if match.facility else 'Unscheduled',
                    'facility_location': match.facility.location if match.facility else '',
                    'date': match.date,
                    'time': match.time,
                    'is_scheduled': match.is_scheduled(),
                    'team_display': match.get_team_names_display(),
                    'scheduling_display': match.get_scheduling_display()
                }
                enhanced_matches.append(enhanced_match)
            
            return render_template('matches.html', matches=enhanced_matches)
            
        except Exception as e:
            flash(f'Error loading matches: {str(e)}', 'error')
            return render_template('matches.html', matches=[])
    
    
    @app.route('/match/<int:match_id>')
    def view_match(match_id):
        """View match details - optimized for object references"""
        db = get_db()
        if not db:
            return render_template('connect.html')
        
        try:
            match = db.get_match(match_id)  # Use get_match instead of get_match_with_lines
            if not match:
                flash('Match not found', 'error')
                return redirect(url_for('matches'))
            
            # All data is directly available from the match object
            return render_template('view_match.html', match=match)
            
        except Exception as e:
            flash(f'Error loading match: {str(e)}', 'error')
            return redirect(url_for('matches'))
    
    
    @app.route('/matches/<int:match_id>/schedule', methods=['POST'])
    def schedule_match(match_id):
        """Schedule a match - updated to work with scheduled_times"""
        print(f"\n=== SCHEDULE MATCH DEBUG START ===")
        print(f"Attempting to schedule match ID: {match_id}")
        
        db = get_db()
        if db is None:
            print("ERROR: No database connection")
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get the match object
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': f'Match {match_id} not found'}), 404
            
            # Check if already has scheduled times
            if hasattr(match, 'scheduled_times') and match.scheduled_times:
                return jsonify({'error': 'Match already has scheduled times'}), 400
            
            # Auto-schedule the match using available method
            success = db.auto_schedule_matches([match])
            
            if success:
                # Get updated match to return current status
                updated_match = db.get_match(match_id)
                enhanced_match = enhance_match_for_template(updated_match)
                
                return jsonify({
                    'success': True,
                    'message': f'Match {match_id} scheduled successfully',
                    'match': enhanced_match
                })
            else:
                return jsonify({'error': 'Could not find suitable scheduling slot'}), 400
                
        except Exception as e:
            print(f"ERROR scheduling match: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Scheduling failed: {str(e)}'}), 500
    
    # Fix for tennis_web_app.py - Update the schedule-all route
    
    @app.route('/matches/schedule-all', methods=['POST'])
    def schedule_all_matches():
        """Schedule all unscheduled matches, optionally filtered by league"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            league_id = request.form.get('league_id', type=int)
            dry_run = request.form.get('dry_run', 'false').lower() == 'true'
            
            if league_id:
                # Get all matches in the specific league
                all_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
                unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
                scope = f"league {league_id}"
            else:
                # Get all matches across all leagues
                all_matches = db.list_matches(include_unscheduled=True)
                unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
                scope = "all leagues"
            
            if not unscheduled_matches:
                return jsonify({
                    'success': True,
                    'message': f'No unscheduled matches found in {scope}',
                    'scheduled_count': 0,
                    'failed_count': 0,
                    'total_count': 0
                })
            
            initial_unscheduled_count = len(unscheduled_matches)
            
            # Use auto-scheduling
            try:
                # Use general match scheduling
                result = db.auto_schedule_matches(unscheduled_matches)
            except AttributeError:
                # If auto-scheduling methods don't exist, we can't schedule
                return jsonify({
                    'error': 'Auto-scheduling functionality not available in this database backend'
                }), 500
            
    
            # Re-fetch matches to count how many are now scheduled
            if league_id:
                current_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
            else:
                current_matches = db.list_matches(include_unscheduled=True)
            
            current_unscheduled = [match for match in current_matches if not match.is_scheduled()]
            scheduled_count = initial_unscheduled_count - len(current_unscheduled)
            failed_count = len(current_unscheduled)
    
            
            total_count = initial_unscheduled_count
            
            message = f"Scheduled {scheduled_count} of {total_count} matches in {scope}"
                
            if failed_count > 0:
                message += f" ({failed_count} failed)"
            
            return jsonify({
                'success': True,
                'message': message,
                'scheduled_count': scheduled_count,
                'failed_count': failed_count,
                'total_count': total_count,
                'details': result if isinstance(result, dict) else {}
            })
            
        except Exception as e:
            import traceback
            print(f"Error in schedule_all_matches: {e}")
            print(traceback.format_exc())
            return jsonify({'error': f'Failed to schedule matches: {e}'}), 500
    
    
            
    @app.route('/matches/<int:match_id>/unschedule', methods=['POST'])
    def unschedule_match(match_id):
        """Remove scheduling from a match, making it unscheduled"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            db.unschedule_match(match_id)
            
            return jsonify({
                'success': True,
                'message': f'Match {match_id} has been unscheduled'
            })
            
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': f'Failed to unschedule match: {e}'}), 500
    
    @app.route('/matches/delete-all', methods=['POST'])
    def delete_all_matches():
        """Delete all matches - useful for regenerating from pairings"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get confirmation from request
            confirm = request.form.get('confirm', '').lower() == 'true'
            if not confirm:
                return jsonify({'error': 'Confirmation required'}), 400
            
            # Count existing matches
            existing_matches = db.list_matches()
            match_count = len(existing_matches)
            
            # Delete all matches
            for match in existing_matches:
                db.delete_match(match.id)
            
            return jsonify({
                'success': True,
                'deleted_count': match_count,
                'message': f'Deleted {match_count} matches'
            })
            
        except Exception as e:
            return jsonify({'error': f'Failed to delete matches: {e}'}), 500
    
    
