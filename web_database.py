from flask import g
from typing import Optional, Type, Dict, Any
from tennis_db_interface import TennisDBInterface


# Global database configuration
db_config = {
    'backend_class': None,
    'connection_params': {}
}

def configure_database(backend_class: Type[TennisDBInterface], **connection_params):
    """Configure the database backend and connection parameters"""
    global db_config
    db_config['backend_class'] = backend_class
    db_config['connection_params'] = connection_params



def get_db() -> Optional[TennisDBInterface]:
    """Get database connection for current thread"""
    if not hasattr(g, 'db') or g.db is None:
        if db_config['backend_class'] is None:
            return None
        try:
            # Fix: Pass as a dict since SQLiteTennisDB expects config dict
            g.db = db_config['backend_class'](db_config['connection_params'])
            g.db.connect()
        except Exception as e:
            print(f"Error creating database connection: {e}")
            return None
    return g.db

def close_db(error):
    """Close database connection at end of request"""
    db = getattr(g, 'db', None)
    if db is not None:
        try:
            db.disconnect()
        except:
            pass
        g.db = None

def init_db(backend_class: Type[TennisDBInterface], **connection_params) -> bool:
    """Initialize database with specified backend and parameters"""
    try:
        # Fix: Pass connection_params as a dict, since SQLiteTennisDB expects a config dict
        test_db = backend_class({'db_path': connection_params['db_path']})  # For SQLite specifically
        test_db.connect()
        if test_db.ping():
            test_db.disconnect()
            configure_database(backend_class, **connection_params)
            return True
        else:
            test_db.disconnect()
            return False
    except Exception as e:
        print(f"Error testing database: {e}")
        return False

