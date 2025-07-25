"""
Flask Route Handler for Manual Match Scheduling
Fixed version with proper routes, data handling, and error handling
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from typing import Optional
import traceback
import math
from datetime import datetime, timedelta

from streamlit import success

from usta import League, Match, Facility, FacilityAvailabilityInfo, TimeSlotAvailability
from web_database import get_db, close_db

# Ensure we have the correct imports

from typing import List, Dict, Any, Tuple

from sql_match_manager import SQLMatchManager


# Create blueprint for scheduling routes
schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/matches/<int:match_id>/schedule")
def schedule_match_form(match_id: int):
    """
    Display the manual scheduling form for a specific match
    Updated to use db.get_facility_availability properly
    """
    from web_database import get_db
    from datetime import datetime

    try:
        # Get database interface
        db = get_db()
        if db is None:
            flash("No database connection available", "danger")
            return redirect(url_for("matches"))

        # Get match object
        match = db.get_match(match_id)
        if not match:
            flash(f"Match with ID {match_id} not found", "danger")
            return redirect(url_for("matches"))

        league = match.league

        # Check if match is already scheduled
        if match.is_scheduled():
            facility_name = (
                match.facility.name if match.facility else "Unknown Facility"
            )
            flash(
                f"Match is already scheduled for {match.date} at {facility_name}",
                "info",
            )
            return redirect(url_for("view_match", match_id=match_id))


        # Validate that match has a facility
        facility = match.get_facility()
        if not facility:
            flash("No facility associated with this match", "warning")
            return redirect(url_for("matches"))

        # Try to get viable dates, but handle the case where none are found
        try:
            viable_dates = db.match_manager.get_viable_scheduling_dates(
                match=match, max_dates=20
            )
            
            # Filter out None values and ensure we have valid dates
            viable_dates = [date for date in viable_dates if date is not None and isinstance(date, str)]
            
        except Exception as e:
            print(f"Error getting viable dates: {e}")
            viable_dates = []

        # Get facility availability if we have viable dates
        facility_availability = []
        if viable_dates:
            try:
                facility_availability = db.facility_manager.get_facility_availability(
                    facility=facility,
                    dates=viable_dates,
                    max_days=20,  # Allow some buffer
                )
            except Exception as e:
                print(f"Error getting facility availability: {e}")
                facility_availability = []
        
        # Convert FacilityAvailabilityInfo objects to format expected by template
        available_dates = []

        for facility_info in facility_availability:
            # put info expected by the form
            date_obj = datetime.strptime(facility_info.date, "%Y-%m-%d")
            num_lines = match.league.num_lines_per_match

            # available times are the set of times that can accommodate the match
            set_times = set(facility_info.get_available_times(num_lines))
            if match.league.allow_split_lines:
                # If split lines are allowed, we can also consider half the lines
                set_times.update(
                    facility_info.get_available_times(math.ceil(num_lines / 2))
                )

            available_times = list(set_times)
            available_times.sort()

            # Create time slot details from facility availability
            time_slot_details = []
            for time_slot in facility_info.time_slots:
                time_slot_details.append({
                    "time": time_slot.time,
                    "total_courts": time_slot.total_courts,
                    "available_courts": time_slot.available_courts,
                    "used_courts": time_slot.used_courts,
                    "utilization_percentage": time_slot.utilization_percentage
                })

            # Get facility for existing matches lookup
            facility = match.get_facility()
            
            # get the already scheduled matches on this date, its ok if this is empty
            existing_matches = []
            try:
                if facility:
                    existing_matches = get_existing_matches_on_date(db, facility, facility_info.date)
            except Exception as e:
                print(f"Error getting existing matches: {e}")
                existing_matches = []

            # Generate quality description based on match
            try:
                quality_score = match.get_quality_score(facility_info.date)
            except Exception as e:
                print(f"Error calculating quality score for date {facility_info.date}: {e}")
                quality_score = 50  # Default fallback value
                
            if quality_score >= 80:
                quality_description = "Ideal scheduling window"
            elif quality_score >= 60:
                quality_description = "Good scheduling option" 
            elif quality_score >= 40:
                quality_description = "Acceptable scheduling time"
            else:
                quality_description = "Available but not preferred"

            date_option = {
                    "date": facility_info.date,
                    "day_name": facility_info.day_of_week,
                    "formatted_date": date_obj.strftime("%B %d, %Y"),
                    "available_times": available_times,
                    "time_slot_details": time_slot_details,  # Enhanced court info per time
                    "score": quality_score,  # Use match quality score directly
                    "match_quality": quality_score,  # Add match quality for display
                    "quality_description": quality_description,  # Use match object's method
                    "in_round": bool(quality_score >= 80),  # Qualities 80+ are within round
                    "conflicts": None,
                    "existing_matches": existing_matches,  # Add existing match details
                    "courts_available": facility_info.available_court_slots,
                    "total_court_slots": facility_info.total_court_slots,
                    "utilization_percentage": facility_info.overall_utilization_percentage,
                    "facility_name": facility_info.facility_name,
                    }
            available_dates.append(date_option)
            print(f"Added date option: {facility_info.date} with {len(available_times)} times, quality: {quality_score}, description: {quality_description}")

        # Sort available dates by quality score (highest first)
        available_dates.sort(key=lambda x: x["score"], reverse=True)

        # Prepare match_info for template
        match_info = {
            "id": match.id,
            "home_team": match.home_team.name if match.home_team else "Unknown",
            "visitor_team": match.visitor_team.name if match.visitor_team else "Unknown", 
            "round": match.round,
            "num_rounds": match.num_rounds,
            "league": match.league.name if match.league else "Unknown League",
            "lines_needed": match.league.num_lines_per_match if match.league else 3
        }
        
        # Prepare facility_info for template
        facility_obj = match.get_facility()
        facility_info = None
        if facility_obj:
            facility_info = {
                "id": facility_obj.id,
                "name": facility_obj.name,
                "location": facility_obj.location
            }

        # Render the scheduling form with available dates
        return render_template(
            "schedule_match.html",
            success=True,
            match=match,
            match_info=match_info,
            league=league,
            available_dates=available_dates,
            facility=facility_obj,
            facility_info=facility_info,
            num_lines_per_match=league.num_lines_per_match,
            allow_split_lines=league.allow_split_lines,
        )
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading scheduling form: {str(e)}", "danger")
        return redirect(url_for("matches"))


# ====== Helper Functions for Scheduling Logic ======


def check_team_conflicts(db, match, date):
    """Simple team conflict checking"""
    if match.home_team and db.check_team_date_conflict(
        match.home_team, date
    ):
        return f"Home team {match.home_team.name} has a conflict on {date}"

    if match.visitor_team and db.check_team_date_conflict(
        match.visitor_team, date
    ):
        return f"Visitor team {match.visitor_team.name} has a conflict on {date}"

    return None


def get_existing_matches_on_date(db, facility, date):
    """Get existing matches scheduled at the facility on the given date"""
    try:
        # Get all matches on this date at this facility
        existing_matches = db.list_matches(facility=facility, date_str=date)

        # Convert to format suitable for template display
        match_info = []
        for match in existing_matches:
            if match.is_scheduled():
                match_info.append(
                    {
                        "id": match.id,
                        "home_team": match.home_team.name,
                        "visitor_team": match.visitor_team.name,
                        "league": match.league.name if match.league else "Unknown",
                        "scheduled_times": match.scheduled_times,
                        "earliest_time": match.get_earliest_time(),
                        "latest_time": match.get_latest_time(),
                        "num_lines": len(match.scheduled_times),
                    }
                )

        return match_info

    except Exception as e:
        print(f"Error getting existing matches on {date}: {e}")
        return []


def get_priority_label(priority: int) -> str:
    """
    Convert numeric priority to human-readable label

    Args:
        priority: Integer priority (lower number = higher priority)

    Returns:
        Human-readable priority label
    """
    if priority == 1:
        return "Ideal (Teams require, League prefers, In round)"
    elif priority == 2:
        return "Good (Teams require, League allows, In round)"
    elif priority == 3:
        return "Preferred (League prefers, In round)"
    elif priority == 4:
        return "Acceptable (League backup, In round)"
    elif priority <= 14:  # Out of round priorities (1-4 + 10)
        if priority == 11:
            return "Ideal (Teams require, League prefers, Out of round)"
        elif priority == 12:
            return "Good (Teams require, League allows, Out of round)"
        elif priority == 13:
            return "Preferred (League prefers, Out of round)"
        elif priority == 14:
            return "Acceptable (League backup, Out of round)"
        else:
            return "Available (Out of round)"
    else:
        return "Available"


# ======= Enhanced API Endpoint for Match Scheduling =======


# API endpoint to handle match scheduling with enhanced split times support
@schedule_bp.route("/api/schedule/match", methods=["POST"])
def api_schedule_match():
    """Simplified API endpoint using enhanced database validation"""
    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        match_id = data.get("match_id")
        facility_id = data.get("facility_id")
        date = data.get("date")
        times = data.get("times", [])
        scheduling_mode = data.get(
            "scheduling_mode", "same_time"
        )  # Default to 'same_time' if not provided
        if scheduling_mode not in ["same_time", "split_times", "custom"]:
            return jsonify({"success": False, "error": "Invalid scheduling mode"})

        # Basic validation
        if not all([match_id, date, times]):
            return jsonify({"success": False, "error": "Missing required fields"})

        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        if not facility:
            return jsonify({"success": False, "error": "No facility available"})

        # Check team conflicts (existing logic)
        team_conflict_error = check_team_conflicts(db, match, date)
        if team_conflict_error:
            return jsonify({"success": False, "error": team_conflict_error})

        # Ensure the match has the facility assigned
        if not match.facility:
            match.facility = facility

        # Use the database schedule_match method
        result = db.schedule_match(
            match=match, date=date, times=times, scheduling_mode=scheduling_mode
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"})


@schedule_bp.route("/api/schedule/facility-availability/<int:facility_id>/<date>")
def api_facility_availability(facility_id: int, date: str):
    """
    API endpoint to get detailed facility availability for a specific date
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        facility = db.facility_manager.get_facility(facility_id)
        if not facility:
            return jsonify({"success": False, "error": "Facility not found"})

        # Get facility availability using db.get_facility_availability
        try:
            facility_availability_list = db.facility_manager.get_facility_availability(
                facility=facility, dates=[date], max_days=1
            )

            if facility_availability_list and len(facility_availability_list) > 0:
                facility_info = facility_availability_list[0]

                if facility_info.available:
                    # Extract available and busy times
                    available_times = [
                        slot.time
                        for slot in facility_info.time_slots
                        if slot.has_availability()
                    ]
                    busy_times = [
                        slot.time
                        for slot in facility_info.time_slots
                        if slot.is_fully_booked()
                    ]

                    availability = {
                        "available_times": available_times,
                        "busy_times": busy_times,
                        "time_slots": [
                            slot.to_dict() for slot in facility_info.time_slots
                        ],
                        "overall_utilization": facility_info.overall_utilization_percentage,
                        "total_court_slots": facility_info.total_court_slots,
                        "available_court_slots": facility_info.available_court_slots,
                        "message": f"Found {len(available_times)} available time slots",
                    }
                else:
                    availability = {
                        "available_times": [],
                        "busy_times": [],
                        "message": facility_info.reason
                        or "Facility not available on this date",
                    }
            else:
                availability = {
                    "available_times": [],
                    "busy_times": [],
                    "message": "No availability information found for this date",
                }

        except Exception as e:
            availability = {
                "available_times": [],
                "busy_times": [],
                "message": f"Error checking availability: {str(e)}",
            }

        return jsonify({"success": True, "availability": availability})

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": f"Error getting facility availability: {str(e)}",
            }
        )


@schedule_bp.route("/matches/<int:match_id>/schedule/refresh-options")
def refresh_scheduling_options(match_id: int):
    """
    Refresh scheduling options with different parameters
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Get match object
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        # Get parameters from request
        facility_id = request.args.get("facility_id", type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        max_dates = int(request.args.get("max_dates", 20))

        # Get facility
        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)

        if not facility and match.home_team:
            facility = match.home_team.home_facility

        if not facility:
            return jsonify(
                {"success": False, "error": "No facility available for this match"}
            )

        # Get fresh scheduling options
        scheduling_options = get_scheduling_options_from_facility_availability(
            db=db,
            match=match,
            facility=facility,
            start_date=start_date,
            end_date=end_date,
            max_dates=max_dates,
        )

        return jsonify(scheduling_options)

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Error refreshing options: {str(e)}"}
        )


@schedule_bp.route("/api/schedule/match/preview", methods=["POST"])
def api_preview_schedule_match():
    """Simplified preview endpoint"""
    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        match_id = data.get("match_id")
        facility_id = data.get("facility_id")
        date = data.get("date")
        times = data.get("times", [])
        scheduling_mode = data.get("scheduling_mode", "custom")

        # Basic validation
        if not all([match_id, facility_id, date, times]):
            return jsonify({"success": False, "error": "Missing required fields"})

        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        facility = db.get_facility(facility_id)
        if not facility:
            return jsonify({"success": False, "error": "Facility not found"})

        # Use the enhanced database preview method
        result = db.preview_match_scheduling(
            match=match, date=date, times=times, scheduling_mode=scheduling_mode
        )

        # Return the preview result with success flag
        return jsonify(
            {
                "success": True,
                "preview": result,
                "can_schedule": result.get("schedulable", False),
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Error previewing schedule: {str(e)}"}
        )


# Add to the route registration function
def add_scheduling_routes_to_app(app):
    """
    Register all scheduling routes with the Flask app
    Enhanced with split times support
    """
    # Register the blueprint
    app.register_blueprint(schedule_bp)

    # Add any additional configuration for split times
    app.config.setdefault("TENNIS_SPLIT_TIMES_ENABLED", True)
    app.config.setdefault("TENNIS_SPLIT_TIMES_MIN_GAP_HOURS", 1)
    app.config.setdefault(
        "TENNIS_SPLIT_TIMES_DEFAULT_DISTRIBUTION", "balanced"
    )  # or 'majority_first'


# ======== Scheduling Options Retrieval ========


# NEW: Using db.get_facility_availability
def get_scheduling_options_from_facility_availability(
    db, match, facility, start_date=None, end_date=None, max_dates=20
):
    """
    Get scheduling options using db.get_facility_availability instead of utils.get_scheduling_options

    Returns:
        Dictionary with 'success', 'available_dates', and 'search_params' keys
    """
    try:
        # Generate date range to check
        from datetime import datetime, timedelta

        # Use provided dates or generate default range
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now()

        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = start_dt + timedelta(
                days=max_dates * 2
            )  # Give buffer for finding enough dates

        # Generate list of dates to check
        dates_to_check = []
        current_dt = start_dt
        while (
            current_dt <= end_dt and len(dates_to_check) < max_dates * 3
        ):  # Extra buffer
            dates_to_check.append(current_dt.strftime("%Y-%m-%d"))
            current_dt += timedelta(days=1)

        # Get facility availability for all dates at once
        facility_availability_list = db.facility_manager.get_facility_availability(
            facility=facility, dates=dates_to_check, max_days=max_dates * 2
        )

        # Convert FacilityAvailabilityInfo objects to the format expected by the template
        available_dates = []
        lines_needed = match.league.num_lines_per_match if match.league else 3

        for facility_info in facility_availability_list:
            if not facility_info.available:
                continue  # Skip unavailable dates

            # Extract available times that can accommodate the needed lines
            available_times = []
            for time_slot in facility_info.time_slots:
                if time_slot.can_accommodate(lines_needed):
                    available_times.append(time_slot.time)

            if not available_times:
                continue  # Skip dates with no suitable times

            # Calculate scheduling score based on availability
            score = calculate_scheduling_score(facility_info, match, lines_needed)

            # Check for conflicts (team conflicts, etc.)
            conflicts = check_match_conflicts(
                db, match, facility_info.date, available_times
            )

            # Create date option in expected format
            date_option = {
                "date": facility_info.date,
                "day_name": facility_info.day_of_week,
                "formatted_date": format_date_for_display(facility_info.date),
                "available_times": available_times,
                "score": score,
                "conflicts": conflicts,
                "courts_available": facility_info.available_court_slots,
                "facility_name": facility_info.facility_name,
                "utilization_percentage": facility_info.overall_utilization_percentage,
            }

            available_dates.append(date_option)

            # Stop once we have enough good options
            if len(available_dates) >= max_dates:
                break

        # Sort by score (highest first)
        available_dates.sort(key=lambda x: x["score"], reverse=True)

        return {
            "success": True,
            "available_dates": available_dates[:max_dates],
            "search_params": {
                "start_date": start_date,
                "end_date": end_date,
                "max_dates": max_dates,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error getting scheduling options: {str(e)}",
            "available_dates": [],
        }


def calculate_scheduling_score(facility_info, match, lines_needed):
    """Calculate a scheduling score based on facility availability and match preferences"""
    base_score = 5

    # Prefer dates with lower overall utilization
    utilization_bonus = (100 - facility_info.overall_utilization_percentage) / 20

    # Prefer weekends for recreational leagues (if that info is available)
    weekend_bonus = 1 if facility_info.day_of_week in ["Saturday", "Sunday"] else 0

    # Bonus for having multiple time options
    time_options_bonus = min(
        len(
            [
                slot
                for slot in facility_info.time_slots
                if slot.can_accommodate(lines_needed)
            ]
        )
        - 1,
        3,
    )

    return base_score + utilization_bonus + weekend_bonus + time_options_bonus


def check_match_conflicts(db, match, date, available_times):
    """Check for team conflicts on the given date/times"""
    conflicts = []

    for team in [match.home_team, match.visitor_team]:
        if team:
            for time in available_times[:3]:  # Check first few times only
                team_conflicts = db.scheduling_manager.get_team_conflicts(
                    team.id, date, time, duration_hours=3
                )
                conflicts.extend(team_conflicts)

    return conflicts


def format_date_for_display(date_str):
    """Format date string for display in template"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_str


# Alternative manual scheduling functions for direct use


def get_match_scheduling_data(match_id: int, facility_id: Optional[int] = None) -> dict:
    """
    Get scheduling data for a match (for use in other contexts)

    Args:
        match_id: Match ID to get scheduling options for
        facility_id: Optional facility ID (defaults to home team's facility)

    Returns:
        Dictionary with scheduling data
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return {"success": False, "error": "No database connection available"}
        match = db.get_match(match_id)
        if not match:
            return {"success": False, "error": "Match not found"}

        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)

        if not facility and match.home_team:
            facility = match.home_team.home_facility

        if not facility:
            return {"success": False, "error": "No facility available"}

        return get_scheduling_options_from_facility_availability(
            db=db, match=match, facility=facility
        )

    except Exception as e:
        return {"success": False, "error": str(e)}


# Example usage in a Flask app setup
"""
# In your main Flask app file:

from web_schedule_match import add_scheduling_routes_to_app

app = Flask(__name__)

# Add the scheduling routes to your app
add_scheduling_routes_to_app(app)

# Now the following routes will be available:
# GET  /matches/<match_id>/schedule  - Show scheduling form
# POST /api/schedule/match         - Schedule the match
# GET  /api/schedule/facility-availability/<facility_id>/<date> - Check availability
# GET  /matches/<match_id>/schedule/refresh-options - Refresh scheduling options
"""
