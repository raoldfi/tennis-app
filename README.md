# Tennis Database Web Application

A comprehensive Flask-based web application for managing tennis league operations, match scheduling, and facility coordination. This full-featured system provides both web and command-line interfaces for USTA league management with sophisticated scheduling algorithms, quality scoring, and conflict detection.

    
    Database Capability:
    
     - generate a unique, deterministic match ID to avoid duplicate scheduling.
     - create functions to schedule (assign matches to facilities) following
       facility constraints, team preferences, then league preferences.
    
    Web App:
      - Add edit capability for facilities, leagues, teams, matches
      - Add unscheduled matches to the Matches page
      - Add ability to try to schedule unscheduled matches

## Setup Instructions

### 1. Install Dependencies

```bash
pip install flask pyyaml
```

### 2. Create Directory Structure

```
tennis_web_app/
├── web_app.py
├── start_tennis_app.py
├── sqlite_tennis_db.py
├── tennis_db_interface.py
├── usta.py
├── web_database.py
├── web_main.py
├── web_facilities.py
├── web_leagues.py
├── web_teams.py
├── web_matches.py
├── web_schedule.py
└── templates/
    ├── base.html
    ├── connect.html
    ├── dashboard.html
    ├── facilities.html
    ├── teams.html
    ├── matches.html
    ├── leagues.html
    ├── constants.html
    └── stats.html
```

### 3. Copy Files

1. Copy all the Python files (core modules and web modules)
2. Create a `templates` folder
3. Copy all the HTML template files into the `templates` folder

### 4. Run the Application

#### Option A: Simple startup (configure database through web interface)
```bash
python web_app.py
```

#### Option B: Pre-configured startup with database
```bash
python start_tennis_app.py --backend sqlite --db-path tennis.db
```

The application will start on `http://localhost:5000`

### 5. Connect to Database

1. Open `http://localhost:5000` in your browser
2. Enter the path to your tennis database (e.g., `tennis.db`)
3. If you don't have data yet, populate it using:

```bash
python populate_tennis_db.py tennis.db
```

Or load individual data files using the CLI:

```bash
python simple_cli.py --db-path tennis.db load facilities.yaml --execute
python simple_cli.py --db-path tennis.db load leagues.yaml --execute
python simple_cli.py --db-path tennis.db load teams.yaml --execute
python simple_cli.py --db-path tennis.db generate-matches --league-id 1 --execute
```

**CLI Safety Features:**
- All operations default to **dry-run mode** - add `--execute` to perform actual changes
- Preview operations before execution with detailed change descriptions
- Transaction support ensures data integrity

## Features

### 📊 **Dashboard**
- **Data Overview**: Real-time summary of all database entities with record counts
- **Quick Navigation**: Direct access links to all major sections (Facilities, Leagues, Teams, Matches)
- **Database Status**: Live connection monitoring with database path and health indicators
- **Recent Activity**: Summary of recent matches, scheduling operations, and system status
- **System Statistics**: Key metrics including total matches, scheduled vs unscheduled ratios, and facility utilization
- **Action Shortcuts**: Quick access to common operations like match generation and auto-scheduling
- **Bootstrap Interface**: Clean, responsive design with Tennis UI styling and intuitive navigation

### 🏢 **Facilities**
- **View & Manage**: Browse all tennis facilities with comprehensive details
- **Facility Information**: Names, locations, court counts, and availability schedules
- **Complex Scheduling**: Support for weekly availability patterns, blackout dates, and court-specific constraints
- **Capacity Management**: Track total courts and available time slots for scheduling optimization
- **Location Data**: Physical addresses and facility-specific notes for coordination
- **Sortable Interface**: Sort by name, location, court count, or availability

### 🏆 **Leagues**
- **USTA League Management**: Full support for USTA league structure and classifications
- **League Details**: Year, section, region, age group, division, and line configuration
- **Scheduling Preferences**: League-wide preferred days, backup days, and seasonal constraints
- **Match Configuration**: Define lines per match, tournament structure, and round timing
- **Season Management**: Start/end dates, round scheduling, and league-specific rules
- **Team Organization**: View all teams within leagues and their scheduling relationships

### 👥 **Teams**
- **Team Management**: View teams with detailed league filtering and organization
- **Team Details**: Names, captains, contact information, and home facility assignments
- **Scheduling Preferences**: Team-specific preferred playing days and availability constraints
- **League Integration**: Filter teams by specific leagues with expanded league information
- **Home Facility Links**: Direct connection to team home facilities for scheduling coordination

### 📅 **Matches**
- **View & Filter**: Browse all matches with advanced filtering by league, facility, team, status, date range, and search
- **Match Generation**: Bulk generate matches for leagues with sophisticated fairness algorithms:
  - **Round-Robin Scheduling**: Ensures every team plays every other team exactly once per round[^round]. When the configured number of matches doesn't equal a complete round, generates partial round-robin with balanced match distribution and home/away equity
  - **Home/Away Balance**: Equalizes home and away matches across all teams (within one match)
  - **Fair Distribution**: Minimizes variance in total matches per team for optimal competitive balance
  - **Customizable Rounds**: Configure number of rounds and lines per match based on league requirements
  - **Conflict Prevention**: Validates team availability and prevents impossible scheduling scenarios
- **Smart Scheduling**: Auto-schedule matches using intelligent algorithms that consider:
  - Team preferences and availability
  - League preferred/backup days
  - Facility availability and constraints
  - Quality score optimization (20-100 scale)
- **Manual Scheduling**: Interactive individual match scheduling with visual date selection:
  - Visual date browser with quality scores and facility information
  - Real-time conflict detection and court availability display
  - Three scheduling modes: same-time, split-time, or custom scheduling
  - Preview and confirm changes before committing to database
  - Comprehensive validation and warning system
- **Flexible Scheduling Modes**:
  - **Same Time**: All lines scheduled at the same time slot (e.g., all 3 lines at 9:00 AM)
  - **Split Times**: Lines split across multiple time slots (e.g., 2 lines at 9:00 AM, 1 line at 12:00 PM)
  - **Custom Times**: Each line individually scheduled at different times for maximum flexibility
- **Quality Scoring**: Real-time quality assessment of match schedules based on:
  - Team preference alignment (100 = optimal, 20 = poor)
  - League day preferences (preferred vs backup days)
  - Round timing compliance (within proper round window)
  - Average quality metrics for batches
  - Scoring: 100 (preferred, in-round) → 80 (backup, in-round) → 60 (preferred, out-of-round) → 40 (backup, out-of-round) → 20 (no preferences)
- **Bulk Operations**: 
  - Auto-schedule multiple matches with preview mode
  - Bulk unscheduling and deletion
  - Transaction support with dry-run capabilities
- **Preview & Retry**: Preview auto-scheduling results with "Try Again" functionality for better outcomes

### 📋 **USTA Constants**
- View official USTA sections, regions, age groups, divisions
- Reference for creating leagues

### 📈 **Statistics**
- Database overview with counts
- League breakdown showing teams and matches per league
- Quick insights into your data

### 🔧 **Implementation Details**
- **Interface-Based Architecture**: Pluggable database backends through TennisDBInterface abstraction
- **SQLite Implementation**: Full-featured SQLite backend with specialized entity managers
- **Transaction Support**: ACID compliance with rollback capabilities for data integrity
- **Database Factory**: TennisDBFactory for creating and managing database instances
- **Entity Managers**: Specialized managers for leagues, teams, facilities, matches, and scheduling
- **Data Import/Export**: YAML-based data loading with validation and bulk operations
- **CLI Integration**: Command-line tools with dry-run mode and safety features
- **Connection Management**: Robust connection handling with error recovery and status monitoring

## Usage Tips

### **Navigation**
- Use the top navigation bar to switch between sections
- Dashboard provides quick access to all features
- Database connection shown in top-right

### **Filtering**
- Teams and Matches can be filtered by league
- Use dropdown filters to narrow down results
- Clear filters to see all data

### **Sorting**
- Click table headers to sort columns
- Numeric and alphabetic sorting supported
- Use browser search (Ctrl+F) to find specific items

### **Data Management**
- Load new data using the command line interface
- Web app supports both viewing and editing
- Use CLI tools for bulk operations

### **Match Management Workflows**

#### **Generate Matches for a League**
```bash
# Preview match generation (dry-run)
python simple_cli.py --db-path tennis.db generate-matches --league-id 1

# Execute match generation
python simple_cli.py --db-path tennis.db generate-matches --league-id 1 --execute
```

#### **Auto-Schedule Matches**
```bash
# Preview auto-scheduling with quality scores
python simple_cli.py --db-path tennis.db auto-schedule

# Execute auto-scheduling
python simple_cli.py --db-path tennis.db auto-schedule --execute
```

#### **Manual Match Scheduling (Web Interface)**

The web application provides intuitive manual scheduling capabilities for individual matches with visual date selection and conflict detection:

**Interactive Scheduling Process:**
1. **Match Selection**: Navigate to Matches page → Click "Schedule" button on any unscheduled match
2. **Visual Date Browser**: View available dates with quality scores and facility information
3. **Conflict Detection**: See existing matches, court availability, and potential conflicts
4. **Multiple Scheduling Modes**: Choose from same-time, split-time, or custom scheduling
5. **Preview & Confirm**: Preview all changes before committing to database

**Features of Manual Scheduling:**

**Smart Date Recommendations:**
- Dates ranked by quality score (20-100 scale) based on team and league preferences
- Visual indicators for optimal (★), good (★), fair (◉), acceptable (◉), and poor (○) dates
- Real-time conflict detection showing existing matches at each facility
- Court availability display showing available courts per time slot

**Flexible Time Selection:**
- **Same Time Mode**: Select one time slot for all lines (e.g., all 3 lines at 9:00 AM)
- **Split Time Mode**: Select exactly 2 time slots with automatic line distribution
- **Custom Mode**: Individual time selection for each line with maximum flexibility

**Visual Scheduling Interface:**
- Interactive date cards with quality scores, existing matches, and facility constraints
- Color-coded time slots with hover effects and selection indicators
- Real-time validation ensuring proper line distribution and conflict avoidance
- Progress indicators showing match completion status

**Conflict Detection & Validation:**
- Team double-booking prevention (same team can't play multiple matches simultaneously)
- Facility court capacity validation (ensuring sufficient courts available)
- League constraint checking (preferred days, backup days, round timing)
- Warning system for scheduling outside optimal date ranges

**Schedule Preview & Confirmation:**
- Detailed preview showing all database operations before execution
- Conflict and warning display with explanations
- Quality score calculation for the proposed schedule
- Option to cancel or modify before finalizing

**Match Management Actions:**
- **Schedule**: Interactive scheduling with date/time selection
- **Reschedule**: Modify existing scheduled matches with same interface
- **Unschedule**: Remove scheduling while preserving match structure
- **Delete**: Remove matches entirely (unscheduled matches only)

#### **Scheduling Mode Examples**

**Same Time Scheduling** (all lines at one time):
- 3-line match: All lines at 9:00 AM
- Requires facility to have 3+ courts available at 9:00 AM
- Simplest coordination for teams

**Split Time Scheduling** (lines across 2 time slots):
- 3-line match: 2 lines at 9:00 AM, 1 line at 12:00 PM  
- 4-line match: 2 lines at 9:00 AM, 2 lines at 12:00 PM
- Reduces court requirements per time slot
- Allows matches when facilities have limited courts

**Custom Time Scheduling** (maximum flexibility):
- 3-line match: Line 1 at 9:00 AM, Line 2 at 10:30 AM, Line 3 at 1:00 PM
- Each line scheduled independently
- Accommodates complex facility constraints and team preferences

#### **Quality Score Optimization**

The quality scoring system evaluates match scheduling quality on a 20-100 scale by analyzing team preferences, league constraints, and round timing:

**Scoring Algorithm:**
1. **Team Preference Analysis**: Checks if both teams have preferred days and calculates intersection
2. **League Day Matching**: Evaluates against league preferred and backup days
3. **Round Timing Validation**: Determines if the date falls within the appropriate round window
4. **Score Calculation**: Combines team requirements + league preferences + timing compliance

**Quality Score Breakdown:**
- **100**: Optimal - Teams' preferred days within proper round timing
  - Both teams prefer the day AND league prefers the day AND within round window
- **80**: Good - Teams' backup days within round timing  
  - Teams require the day AND league uses as backup AND within round window
- **60**: Fair - League preferred days but outside round timing
  - League prefers the day but scheduling outside the optimal round timeframe
- **40**: Acceptable - League backup days outside round timing
  - League backup day but outside round timing (still schedulable but suboptimal)
- **20**: Poor - Days not preferred by anyone
  - Neither teams nor league prefer this day (last resort scheduling)

**Usage in Scheduling:**
- Auto-scheduling prioritizes higher quality scores when selecting dates
- Manual scheduling displays quality indicators (★ ◉ ○) for visual guidance
- Preview operations show average quality scores for batch scheduling assessment
- "Try Again" functionality seeks improved quality score combinations

#### **Transaction Safety**
- All bulk operations support **dry-run mode** by default
- Preview changes before committing with detailed operation descriptions
- Rollback capability for failed operations
- Conflict detection prevents double-booking teams or facilities

## Troubleshooting

### **Database Connection Issues**
- Ensure the database file path is correct
- Check file permissions
- Create directory if it doesn't exist

### **No Data Showing**
- Verify data was loaded using CLI commands or populate script
- Check for errors in data loading
- Use debug mode if needed

### **Web App Won't Start**
- Check Python version (3.7+)
- Install missing dependencies: `pip install flask pyyaml`
- Ensure all files are in correct directories
- Check import errors in console output

### **Templates Not Found**
- Verify `templates/` folder exists
- Check all HTML files are in templates folder
- File names must match exactly

### **Import Errors**
- Ensure all required Python modules are present
- Check that `web_database.py` exists
- Verify `tennis_db_interface.py` is available

## Development

### **Run in Debug Mode**
```bash
export FLASK_ENV=development
python web_app.py
```

Or use the startup script with debug flag:
```bash
python start_tennis_app.py --backend sqlite --db-path tennis.db --debug
```

### **Access from Other Devices**
The app runs on `0.0.0.0:5000` so it's accessible from other devices on your network at `http://your-ip-address:5000`

### **Customization**
- Modify templates for different styling
- Add new routes for additional functionality
- Extend database methods for more features

## Security Note

This application is designed for local use. For production deployment:
- Change the secret key
- Add authentication
- Use production WSGI server
- Enable HTTPS
- Validate all inputs

---

[^round]: A round is completed when every team in a league has played every other team exactly once. For example, in a 6-team league, each round consists of 15 matches (each team plays 5 opponents), and multiple rounds can be configured for extended seasons.