
This file captures bugs and capabilities that need develped

### Feature Requests
1. **Team Facility Preferences.** Change home_team_facility to preferred and backup facilities.  
    - Treat these similar to preferred and backup dates for a league.  
    - Is there a way to incorporate this into the priority scoring for dates ? Maybe restructure what comes back get_viable_dates to be a Tuple (date, facility, score)
    - This would also require a change in the manual scheduling portion of the app. 


    - Add capability to schedule same day.  
        - Need 2 hr, rest times, limit number of matches/day

 
 ### Bug/feature development

 ### Main Code


 ### Web application
- **Team/Facility/League addition.**  Make sure these are complete and tested. There seem to be some fields missing. 

- **Facility Utilization** fix and test.  What is the right interface for this? 

- **YAML Export** export yaml with comments to make these easier to understand. 

- **Delete (League, Facilities, Teams).**  None of this is implemented yet in the web application. 

- **Access controls.** A production capability will need to authenticate and authorize users allowed to make changes to the database.



