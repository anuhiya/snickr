# Snickr

A web-based team collaboration system similar to Slack, built for CS6083 - Principles of Database Systems at NYU Tandon School of Engineering.

## About

Snickr lets users create accounts, build workspaces, and communicate through channels. Channels can be public, private, or direct, depending on who should have access.

## Features

- User registration and login
- Create and manage workspaces
- Create public, private, and direct channels
- Post and read messages
- Invite users to workspaces and channels
- Search messages by keyword
- User profile management
- Access control — users only see content they are authorized to view

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS |
| Backend | Python 3.13, Flask |
| Database | PostgreSQL (Supabase) |
| Database Driver | psycopg2 |
| Session Management | Flask session |

## Project Structure

```
snickr/
    app.py                      # Main Flask application and routes
    db.py                       # Database connection module
    templates/
        login.html              # Login page
        register.html           # Registration page
        dashboard.html          # User dashboard
        workspace.html          # Workspace view
        channel.html            # Channel view with messages
        create_workspace.html   # Create workspace form
        create_channel.html     # Create channel form
        invite_workspace.html   # Invite user to workspace
        invite_channel.html     # Invite user to channel
        search.html             # Message search
        profile.html            # User profile
```

## Setup and Running

### Prerequisites

- Python 3.13+
- A Supabase account with the snickr database schema set up

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/snickr.git
cd snickr
```

2. Install dependencies:
```bash
pip install flask psycopg2-binary flask-session
```

3. Update `db.py` with your Supabase credentials:
```python
conn = psycopg2.connect(
    host="your-supabase-host",
    database="postgres",
    user="postgres",
    password="your-password",
    port=5432,
    sslmode="require"
)
```

4. Run the application:
```bash
python app.py
```

5. Visit `http://127.0.0.1:5000` in your browser.

## Database Schema

The database consists of 7 tables:

- **Users** — user accounts
- **Workspaces** — team workspaces
- **Workspace\_Members** — workspace memberships with roles (member/admin)
- **Channels** — channels within workspaces (public/private/direct)
- **Channel\_Members** — channel memberships
- **Invitations** — workspace and channel invitations
- **Messages** — messages posted in channels

## Security

- SQL injection prevention via parameterized queries (psycopg2)
- XSS prevention via Jinja2 auto-escaping
- Password hashing using MD5
- Session-based authentication via Flask session
- Application-level access control on every route

## Demo Users

| Username | Password | Role |
|----------|----------|------|
| alice | password123 | Admin: CS Department |
| bob | password123 | Admin: CS Department + PhD Students |
| carol | password123 | Member: both workspaces |
| dave | password123 | Member: CS Department |
| eve | password123 | Member: PhD Students |

## Course Information

- **Course:** CS6083 - Principles of Database Systems
- **Semester:** Spring 2026
- **University:** NYU Tandon School of Engineering
- **Students:** Anuhiya Surekha Suresh Babu (as21237), Pavan Veera (pv2337)
