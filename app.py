from flask import Flask, render_template, request, redirect, url_for, session
from db import get_connection
import hashlib

app = Flask(__name__)
app.secret_key = 'snickr_secret_key_2026'

# Home page - redirect to login
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username FROM Users WHERE username = %s AND password_hash = %s",
            (username, password_hash)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
    
    return render_template('login.html', error=error)

# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        nickname = request.form['nickname']
        password = request.form['password']
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO Users (email, username, nickname, password_hash) VALUES (%s, %s, %s, %s)",
                (email, username, nickname, password_hash)
            )
            conn.commit()
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            error = 'Username or email already exists'
        finally:
            cur.close()
            conn.close()
    
    return render_template('register.html', error=error)

# Dashboard - show all workspaces
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.workspace_id, w.name, w.description, wm.role
        FROM Workspaces w
        JOIN Workspace_Members wm ON w.workspace_id = wm.workspace_id
        WHERE wm.user_id = %s
        ORDER BY w.name
    """, (session['user_id'],))
    workspaces = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', workspaces=workspaces)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Create workspace
@app.route('/workspace/create', methods=['GET', 'POST'])
def create_workspace():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error = None
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Create workspace
            cur.execute(
                "INSERT INTO Workspaces (name, description, creator_id) VALUES (%s, %s, %s) RETURNING workspace_id",
                (name, description, session['user_id'])
            )
            workspace_id = cur.fetchone()[0]
            
            # Add creator as admin
            cur.execute(
                "INSERT INTO Workspace_Members (workspace_id, user_id, role) VALUES (%s, %s, 'admin')",
                (workspace_id, session['user_id'])
            )
            conn.commit()
            return redirect(url_for('view_workspace', workspace_id=workspace_id))
        except Exception as e:
            conn.rollback()
            error = 'Could not create workspace'
        finally:
            cur.close()
            conn.close()
    
    return render_template('create_workspace.html', error=error)

# View workspace
@app.route('/workspace/<int:workspace_id>')
def view_workspace(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Check user is a member
    cur.execute("""
        SELECT role FROM Workspace_Members 
        WHERE workspace_id = %s AND user_id = %s
    """, (workspace_id, session['user_id']))
    member = cur.fetchone()
    
    if not member:
        cur.close()
        conn.close()
        return "Access denied", 403
    
    # Get workspace details
    cur.execute("SELECT name, description FROM Workspaces WHERE workspace_id = %s", (workspace_id,))
    workspace = cur.fetchone()
    
    # Get channels
    cur.execute("""
        SELECT c.channel_id, c.name, c.type,
               EXISTS(SELECT 1 FROM Channel_Members cm 
                      WHERE cm.channel_id = c.channel_id 
                      AND cm.user_id = %s) as is_member
        FROM Channels c
        WHERE c.workspace_id = %s
        ORDER BY c.name
    """, (session['user_id'], workspace_id))
    channels = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('workspace.html', 
                         workspace=workspace,
                         workspace_id=workspace_id,
                         channels=channels,
                         role=member[0])

# Create channel
@app.route('/workspace/<int:workspace_id>/channel/create', methods=['GET', 'POST'])
def create_channel(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error = None
    if request.method == 'POST':
        name = request.form['name']
        channel_type = request.form['type']
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO Channels (workspace_id, name, type, creator_id)
                SELECT %s, %s, %s, %s
                WHERE EXISTS (
                    SELECT 1 FROM Workspace_Members
                    WHERE workspace_id = %s AND user_id = %s
                )
                RETURNING channel_id
            """, (workspace_id, name, channel_type, session['user_id'], workspace_id, session['user_id']))
            
            result = cur.fetchone()
            if result:
                channel_id = result[0]
                # Add creator as member
                cur.execute(
                    "INSERT INTO Channel_Members (channel_id, user_id) VALUES (%s, %s)",
                    (channel_id, session['user_id'])
                )
                conn.commit()
                return redirect(url_for('view_workspace', workspace_id=workspace_id))
            else:
                error = 'Could not create channel'
        except Exception as e:
            conn.rollback()
            error = 'Channel name already exists in this workspace'
        finally:
            cur.close()
            conn.close()
    
    return render_template('create_channel.html', workspace_id=workspace_id, error=error)

# View channel and messages
@app.route('/workspace/<int:workspace_id>/channel/<int:channel_id>')
def view_channel(workspace_id, channel_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Check access
    cur.execute("""
        SELECT 1 FROM Channel_Members
        WHERE channel_id = %s AND user_id = %s
    """, (channel_id, session['user_id']))
    
    if not cur.fetchone():
        cur.close()
        conn.close()
        return "Access denied", 403
    
    # Get channel info
    cur.execute("SELECT name, type FROM Channels WHERE channel_id = %s", (channel_id,))
    channel = cur.fetchone()
    
    # Get messages
    cur.execute("""
        SELECT m.message_id, u.username, m.body, m.posted_at
        FROM Messages m
        JOIN Users u ON u.user_id = m.user_id
        WHERE m.channel_id = %s
        ORDER BY m.posted_at ASC
    """, (channel_id,))
    messages = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('channel.html',
                         channel=channel,
                         channel_id=channel_id,
                         workspace_id=workspace_id,
                         messages=messages)

# Post message
@app.route('/workspace/<int:workspace_id>/channel/<int:channel_id>/post', methods=['POST'])
def post_message(workspace_id, channel_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Check user is a member of the channel
    cur.execute("""
        SELECT 1 FROM Channel_Members
        WHERE channel_id = %s AND user_id = %s
    """, (channel_id, session['user_id']))
    
    if not cur.fetchone():
        cur.close()
        conn.close()
        return "Access denied", 403
    
    body = request.form['body']
    
    try:
        cur.execute(
            "INSERT INTO Messages (channel_id, user_id, body) VALUES (%s, %s, %s)",
            (channel_id, session['user_id'], body)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('view_channel', workspace_id=workspace_id, channel_id=channel_id))

# Search messages
@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    keyword = request.args.get('q', '')
    results = []
    
    if keyword:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT m.message_id, w.name, c.name, u.username, m.body, m.posted_at
            FROM Messages m
            JOIN Channels c ON c.channel_id = m.channel_id
            JOIN Workspaces w ON w.workspace_id = c.workspace_id
            JOIN Users u ON u.user_id = m.user_id
            JOIN Workspace_Members wm ON wm.workspace_id = c.workspace_id
                                     AND wm.user_id = %s
            JOIN Channel_Members cm ON cm.channel_id = m.channel_id
                                    AND cm.user_id = %s
            WHERE m.body ILIKE %s
            ORDER BY m.posted_at DESC
        """, (session['user_id'], session['user_id'], f'%{keyword}%'))
        results = cur.fetchall()
        cur.close()
        conn.close()
    
    return render_template('search.html', results=results, keyword=keyword)

# Join channel
@app.route('/workspace/<int:workspace_id>/channel/<int:channel_id>/join', methods=['POST'])
def join_channel(workspace_id, channel_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Check user is a member of the workspace first
    cur.execute("""
        SELECT 1 FROM Workspace_Members
        WHERE workspace_id = %s AND user_id = %s
    """, (workspace_id, session['user_id']))
    
    if not cur.fetchone():
        cur.close()
        conn.close()
        return "Access denied - not a workspace member", 403
    
    # Check channel is public
    cur.execute("""
        SELECT type FROM Channels 
        WHERE channel_id = %s AND workspace_id = %s
    """, (channel_id, workspace_id))
    channel = cur.fetchone()
    
    if not channel or channel[0] != 'public':
        cur.close()
        conn.close()
        return "Access denied - channel is not public", 403
    
    try:
        cur.execute(
            "INSERT INTO Channel_Members (channel_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (channel_id, session['user_id'])
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('view_workspace', workspace_id=workspace_id))

# Invite user to workspace
@app.route('/workspace/<int:workspace_id>/invite', methods=['GET', 'POST'])
def invite_to_workspace(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check user is admin
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role FROM Workspace_Members
        WHERE workspace_id = %s AND user_id = %s
    """, (workspace_id, session['user_id']))
    member = cur.fetchone()
    
    if not member or member[0] != 'admin':
        cur.close()
        conn.close()
        return "Only admins can invite users", 403
    
    # Get workspace name
    cur.execute("SELECT name FROM Workspaces WHERE workspace_id = %s", (workspace_id,))
    workspace = cur.fetchone()
    
    error = None
    success = None
    
    if request.method == 'POST':
        username = request.form['username']
        
        # Find the user
        cur.execute("SELECT user_id FROM Users WHERE username = %s", (username,))
        invitee = cur.fetchone()
        
        if not invitee:
            error = f'User "{username}" not found'
        else:
            invitee_id = invitee[0]
            # Check if already a member
            cur.execute("""
                SELECT 1 FROM Workspace_Members
                WHERE workspace_id = %s AND user_id = %s
            """, (workspace_id, invitee_id))
            
            if cur.fetchone():
                error = f'User "{username}" is already a member'
            else:
                try:
                    cur.execute("""
                        INSERT INTO Invitations (inviter_id, invitee_id, workspace_id, status)
                        VALUES (%s, %s, %s, 'accepted')
                    """, (session['user_id'], invitee_id, workspace_id))
                    
                    cur.execute("""
                        INSERT INTO Workspace_Members (workspace_id, user_id, role)
                        VALUES (%s, %s, 'member')
                        ON CONFLICT DO NOTHING
                    """, (workspace_id, invitee_id))
                    
                    conn.commit()
                    success = f'User "{username}" added to workspace!'
                except Exception as e:
                    conn.rollback()
                    error = 'Could not invite user'
    
    cur.close()
    conn.close()
    
    return render_template('invite_workspace.html',
                         workspace=workspace,
                         workspace_id=workspace_id,
                         error=error,
                         success=success)

# Invite user to channel
@app.route('/workspace/<int:workspace_id>/channel/<int:channel_id>/invite', methods=['GET', 'POST'])
def invite_to_channel(workspace_id, channel_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Get channel info
    cur.execute("SELECT name, type FROM Channels WHERE channel_id = %s", (channel_id,))
    channel = cur.fetchone()
    
    error = None
    success = None
    
    if request.method == 'POST':
        username = request.form['username']
        
        cur.execute("SELECT user_id FROM Users WHERE username = %s", (username,))
        invitee = cur.fetchone()
        
        if not invitee:
            error = f'User "{username}" not found'
        else:
            invitee_id = invitee[0]
            try:
                cur.execute("""
                    INSERT INTO Invitations (inviter_id, invitee_id, channel_id, status)
                    VALUES (%s, %s, %s, 'accepted')
                """, (session['user_id'], invitee_id, channel_id))
                
                cur.execute("""
                    INSERT INTO Channel_Members (channel_id, user_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (channel_id, invitee_id))
                
                conn.commit()
                success = f'User "{username}" added to channel!'
            except Exception as e:
                conn.rollback()
                error = 'Could not invite user'
    
    cur.close()
    conn.close()
    
    return render_template('invite_channel.html',
                         channel=channel,
                         channel_id=channel_id,
                         workspace_id=workspace_id,
                         error=error,
                         success=success)
    
    # Profile page
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cur = conn.cursor()
    
    success = None
    error = None
    
    if request.method == 'POST':
        nickname = request.form['nickname']
        try:
            cur.execute(
                "UPDATE Users SET nickname = %s WHERE user_id = %s",
                (nickname, session['user_id'])
            )
            conn.commit()
            success = 'Profile updated successfully!'
        except Exception as e:
            conn.rollback()
            error = 'Could not update profile'
    
    cur.execute(
        "SELECT username, email, nickname, created_at FROM Users WHERE user_id = %s",
        (session['user_id'],)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    return render_template('profile.html', user=user, success=success, error=error)

# Promote user to admin
@app.route('/workspace/<int:workspace_id>/promote', methods=['GET', 'POST'])
def promote_member(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check user is admin
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role FROM Workspace_Members
        WHERE workspace_id = %s AND user_id = %s
    """, (workspace_id, session['user_id']))
    member = cur.fetchone()
    
    if not member or member[0] != 'admin':
        cur.close()
        conn.close()
        return "Only admins can promote members", 403
    
    # Get workspace name
    cur.execute("SELECT name FROM Workspaces WHERE workspace_id = %s", (workspace_id,))
    workspace = cur.fetchone()
    
    # Get all non-admin members
    cur.execute("""
        SELECT u.user_id, u.username FROM Users u
        JOIN Workspace_Members wm ON wm.user_id = u.user_id
        WHERE wm.workspace_id = %s AND wm.role = 'member'
    """, (workspace_id,))
    members = cur.fetchall()
    
    error = None
    success = None
    
    if request.method == 'POST':
        promote_user_id = request.form['user_id']
        try:
            cur.execute("""
                UPDATE Workspace_Members
                SET role = 'admin'
                WHERE workspace_id = %s AND user_id = %s
            """, (workspace_id, promote_user_id))
            conn.commit()
            success = 'User promoted to admin!'
            # Refresh members list
            cur.execute("""
                SELECT u.user_id, u.username FROM Users u
                JOIN Workspace_Members wm ON wm.user_id = u.user_id
                WHERE wm.workspace_id = %s AND wm.role = 'member'
            """, (workspace_id,))
            members = cur.fetchall()
        except Exception as e:
            conn.rollback()
            error = 'Could not promote user'
    
    cur.close()
    conn.close()
    
    return render_template('promote_member.html',
                         workspace=workspace,
                         workspace_id=workspace_id,
                         members=members,
                         error=error,
                         success=success)

# Remove workspace member
@app.route('/workspace/<int:workspace_id>/remove', methods=['GET', 'POST'])
def remove_member(workspace_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check user is admin
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT role FROM Workspace_Members
        WHERE workspace_id = %s AND user_id = %s
    """, (workspace_id, session['user_id']))
    member = cur.fetchone()
    
    if not member or member[0] != 'admin':
        cur.close()
        conn.close()
        return "Only admins can remove members", 403
    
    # Get workspace name
    cur.execute("SELECT name, creator_id FROM Workspaces WHERE workspace_id = %s", (workspace_id,))
    workspace = cur.fetchone()
    
    # Get all members except current user and creator
    cur.execute("""
        SELECT u.user_id, u.username, wm.role FROM Users u
        JOIN Workspace_Members wm ON wm.user_id = u.user_id
        WHERE wm.workspace_id = %s 
        AND u.user_id != %s
        AND u.user_id != %s
    """, (workspace_id, session['user_id'], workspace[1]))
    members = cur.fetchall()
    
    error = None
    success = None
    
    if request.method == 'POST':
        remove_user_id = request.form['user_id']
        try:
            # Remove from channel members first
            cur.execute("""
                DELETE FROM Channel_Members
                WHERE user_id = %s
                AND channel_id IN (
                    SELECT channel_id FROM Channels
                    WHERE workspace_id = %s
                )
            """, (remove_user_id, workspace_id))
            
            # Remove from workspace
            cur.execute("""
                DELETE FROM Workspace_Members
                WHERE workspace_id = %s AND user_id = %s
            """, (workspace_id, remove_user_id))
            
            conn.commit()
            success = 'Member removed successfully!'
            # Refresh members list
            cur.execute("""
                SELECT u.user_id, u.username, wm.role FROM Users u
                JOIN Workspace_Members wm ON wm.user_id = u.user_id
                WHERE wm.workspace_id = %s
                AND u.user_id != %s
                AND u.user_id != %s
            """, (workspace_id, session['user_id'], workspace[1]))
            members = cur.fetchall()
        except Exception as e:
            conn.rollback()
            error = 'Could not remove member'
    
    cur.close()
    conn.close()
    
    return render_template('remove_member.html',
                         workspace=workspace,
                         workspace_id=workspace_id,
                         members=members,
                         error=error,
                         success=success)

if __name__ == '__main__':
    app.run(debug=True)