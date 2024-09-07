CREATE TABLE team_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    team_number TEXT NOT NULL,
    problem_statement_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
	marks TEXT
);
