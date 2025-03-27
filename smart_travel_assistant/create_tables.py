import sqlite3

def create_tables():
    # Connect to the SQLite database
    conn = sqlite3.connect('database.db')
    
    # Open and read the schema.sql file to create the tables
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    
    # Commit changes and close the connection
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
