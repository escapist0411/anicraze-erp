-- audit_logs table placeholder
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
