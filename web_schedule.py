
from typing import Optional, Type, Dict, Any

from flask import render_template, request, redirect, url_for, flash
from datetime import datetime

from web_database import get_db
from web_utils import filter_matches

def register_routes(app):
    """Register facility-related routes"""

    @app.route('/schedule')
    def schedule():
        """Schedule page - FIXED to use League objects"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search', '').strip()
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
            
            # Get only scheduled matches (those with dates) - FIXED to pass League object
            matches_list = db.list_matches(selected_league, include_unscheduled=False)
            
            # Filter to only matches with actual dates
            scheduled_matches = [m for m in matches_list if m.date]
            
            # Apply additional filters
            if start_date or end_date or search_query:
                scheduled_matches = filter_matches(scheduled_matches, start_date, end_date, search_query)
            
            # Sort by date
            scheduled_matches.sort(key=lambda x: x.date if x.date else datetime.min.date())
            
            # Convert to display format for schedule
            schedule_data = []
            for match in scheduled_matches:
                schedule_item = {
                    'id': match.id,
                    'date': match.date,
                    'time': ', '.join(match.scheduled_times) if match.scheduled_times else 'TBD',
                    'home_team': match.home_team.name if match.home_team else 'Unknown',
                    'visitor_team': match.visitor_team.name if match.visitor_team else 'Unknown',
                    'facility': match.facility.name if match.facility else 'TBD',
                    'league': match.league.name if match.league else 'Unknown',
                    'status': match.get_status() if hasattr(match, 'get_status') else 'Scheduled'
                }
                schedule_data.append(schedule_item)
            
            # Get leagues for filter dropdown
            leagues_list = db.list_leagues()
            
            return render_template('schedule.html',
                                 schedule=schedule_data,
                                 leagues=leagues_list,
                                 selected_league=selected_league,
                                 search_query=search_query,
                                 start_date=start_date,
                                 end_date=end_date)
            
        except Exception as e:
            flash(f'Error loading schedule: {e}', 'error')
            return redirect(url_for('index'))
    

