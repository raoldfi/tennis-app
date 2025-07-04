# Tennis Database Web Application

A Flask-based web application for viewing and managing tennis league data.

    
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
python tennis_cli.py --db-path tennis.db load facilities facilities.yaml
python tennis_cli.py --db-path tennis.db load leagues leagues.yaml
python tennis_cli.py --db-path tennis.db load teams teams.yaml
python tennis_cli.py --db-path tennis.db load matches matches.yaml
```

## Features

### 📊 **Dashboard**
- Overview of all data tables
- Quick navigation to different sections
- Database connection status

### 🏢 **Facilities**
- View all tennis facilities
- See names and locations
- Sortable table

### 🏆 **Leagues**
- Browse all leagues
- See year, section, region, age group, division
- Organized display of league information

### 👥 **Teams**
- View teams with league filtering
- See team names, captains, home facilities
- Filter by specific league
- League information expanded inline

### 📅 **Matches**
- View scheduled matches
- Filter by league
- See team names, dates, times, facilities
- Enhanced with human-readable team and facility names

### 📋 **USTA Constants**
- View official USTA sections, regions, age groups, divisions
- Reference for creating leagues

### 📈 **Statistics**
- Database overview with counts
- League breakdown showing teams and matches per league
- Quick insights into your data

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