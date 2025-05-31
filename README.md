# Tennis Database Web Application

A Flask-based web application for viewing and managing tennis league data.

## Setup Instructions

### 1. Install Dependencies

```bash
pip install flask pyyaml
```

### 2. Create Directory Structure

```
tennis_web_app/
├── tennis_web_app.py
├── sqlite_tennis_db.py
├── tennis_db.py
├── usta.py
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

1. Copy all the Python files (`usta.py`, `tennis_db.py`, `sqlite_tennis_db.py`, `tennis_web_app.py`)
2. Create a `templates` folder
3. Copy all the HTML template files into the `templates` folder

### 4. Run the Application

```bash
python tennis_web_app.py
```

The application will start on `http://localhost:5000`

### 5. Connect to Database

1. Open `http://localhost:5000` in your browser
2. Enter the path to your tennis database (e.g., `tennis.db`)
3. If you don't have data yet, load it using the command line:

```bash
python sqlite_tennis_db.py tennis.db load facilities facilities.yaml
python sqlite_tennis_db.py tennis.db load leagues leagues.yaml
python sqlite_tennis_db.py tennis.db load teams teams.yaml
python sqlite_tennis_db.py tennis.db load matches matches.yaml
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
- Web app is read-only (viewing only)
- Database changes require CLI tools

## Troubleshooting

### **Database Connection Issues**
- Ensure the database file path is correct
- Check file permissions
- Create directory if it doesn't exist

### **No Data Showing**
- Verify data was loaded using CLI commands
- Check for errors in data loading
- Use debug mode in `load_yaml` if needed

### **Web App Won't Start**
- Check Python version (3.7+)
- Install missing dependencies: `pip install flask pyyaml`
- Ensure all files are in correct directories

### **Templates Not Found**
- Verify `templates/` folder exists
- Check all HTML files are in templates folder
- File names must match exactly

## Development

### **Run in Debug Mode**
```bash
export FLASK_ENV=development
python tennis_web_app.py
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

