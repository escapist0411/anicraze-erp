-- reports table placeholder
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
