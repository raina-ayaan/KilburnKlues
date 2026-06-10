"""
Local development server for Kilburn Klues.

Serves the plain HTML/CSS/image files AND provides the same API endpoints
that api.php handles on the university web server, so the exact same front-end
code works in both environments.

    python app.py          → http://localhost:5000

On the uni server (web.cs.manchester.ac.uk) api.php does this job natively.
"""

import os
import math
import random
import mysql.connector
from flask import Flask, jsonify, request, session, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.urandom(24)

# Root of the project (where index.html etc. live)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Database Configuration ────────────────────────────────────────────────────


DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PSWD'),
    'database': os.getenv('DB_NAME'),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# ── API endpoint (mirrors api.php) ───────────────────────────────────────────
# The front-end fetches "api.php?action=..." — Flask intercepts that URL
# and runs the equivalent Python/MySQL logic.

@app.route('/api.php')
def api_endpoint():
    action = request.args.get('action', '')

    try:
        if action == 'guide_images':
            return api_guide_images()
        elif action == 'guide_tags':
            return api_guide_tags()
        elif action == 'start_game':
            return api_start_game()
        elif action == 'get_question':
            return api_get_question()
        elif action == 'submit_answer':
            return api_submit_answer()
        elif action == 'get_results':
            return api_get_results()
        elif action == 'sync_tags':
            return api_sync_tags()
        elif action == 'get_total_score':
            return api_get_total_score()
        elif action == 'add_score':
            return api_add_score()
        elif action == 'get_leaderboard':
            return api_get_leaderboard()
        elif action == 'get_score_history':
            return api_get_score_history()
        else:
            return jsonify({'error': f'Unknown action: {action}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Also accept POST to the same URL (for submit_answer)
@app.route('/api.php', methods=['POST'])
def api_endpoint_post():
    return api_endpoint()


# ── Guide API ─────────────────────────────────────────────────────────────────

def api_guide_images():
    tag = request.args.get('tag', '').strip()
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if tag:
        cursor.execute("""
            SELECT q.* FROM quiz_questions q
            JOIN question_labels ql ON q.id = ql.question_id
            JOIN labels l ON l.id = ql.label_id
            WHERE l.name = %s
        """, (tag,))
    else:
        cursor.execute("SELECT * FROM quiz_questions")

    rows = cursor.fetchall()
    for row in rows:
        row['image_file'] = os.path.basename(row.get('image_url', ''))
    cursor.close()
    conn.close()
    return jsonify(rows)

def api_guide_tags():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM labels ORDER BY name")
    tags = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(tags)


# ── Game API ──────────────────────────────────────────────────────────────────

def api_start_game():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, question_type, score FROM quiz_questions")
    rows = cursor.fetchall()
    ids = [row['id'] for row in rows]

    max_score_total = 0
    for row in rows:
        if (row.get('question_type') or 'mcq') == 'map':
            max_score_total += int(row['score']) if row.get('score') else 10
        else:
            # MCQ currently awards 1 point for correct answers.
            max_score_total += 1

    cursor.close()
    conn.close()

    if not ids:
        return jsonify({'error': 'No questions found in the database'})

    random.shuffle(ids)
    session['question_ids'] = ids
    session['current_index'] = 0
    session['score'] = 0
    session['max_score_total'] = max_score_total

    return _send_current_question()

def api_get_question():
    if 'question_ids' not in session:
        return jsonify({'error': 'No game in progress', 'redirect': True})
    return _send_current_question()

def _send_current_question():
    idx = session.get('current_index', 0)
    ids = session.get('question_ids', [])
    total = len(ids)

    if idx >= total:
        return jsonify({
            'game_over': True,
            'score': session.get('score', 0),
            'total': total
        })

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM quiz_questions WHERE id = %s", (ids[idx],))
    q = cursor.fetchone()
    cursor.close()
    conn.close()

    if q:
        q['image_file']     = os.path.basename(q.get('image_url', ''))
        q['floorplan_file'] = os.path.basename(q['floorplan_url']) if q.get('floorplan_url') else None
        # Never expose the correct location before the user answers
        q.pop('correct_x', None)
        q.pop('correct_y', None)

    return jsonify({
        'question': q,
        'current_index': idx,
        'total': total,
        'score': session.get('score', 0)
    })

def api_submit_answer():
    if 'question_ids' not in session:
        return jsonify({'error': 'No game in progress'})

    data = request.get_json(silent=True) or {}

    idx = session['current_index']
    ids = session['question_ids']
    qid = ids[idx]

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT question_type, correct_answer, correct_x, correct_y, score FROM quiz_questions WHERE id = %s",
        (qid,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    question_type = row.get('question_type') or 'mcq'

    if question_type == 'map':
        gx = float(data.get('x', 0))
        gy = float(data.get('y', 0))
        cx = float(row['correct_x'])
        cy = float(row['correct_y'])
        distance = math.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
        max_score = int(row['score']) if row.get('score') else 10
        # Full points within 2%, zero at 30%, linear between
        points = int(round(max_score * max(0, min(1, (30 - distance) / 28))))
        session['score'] = session.get('score', 0) + points
        session['current_index'] = idx + 1
        game_over = session['current_index'] >= len(ids)

        return jsonify({
            'question_type': 'map',
            'correct_x':     cx,
            'correct_y':     cy,
            'distance':      round(distance, 1),
            'points_earned': points,
            'max_score':     max_score,
            'game_over':     game_over,
            'score':         session['score'],
            'current_index': session['current_index'],
            'total':         len(ids)
        })
    else:
        # MCQ — original logic
        answer = data.get('answer') or request.form.get('answer') or request.args.get('answer', '')
        is_correct = (answer == row['correct_answer'])
        if is_correct:
            session['score'] = session.get('score', 0) + 1
        session['current_index'] = idx + 1
        game_over = session['current_index'] >= len(ids)

        return jsonify({
            'correct':        is_correct,
            'correct_answer': row['correct_answer'],
            'game_over':      game_over,
            'score':          session['score'],
            'current_index':  session['current_index'],
            'total':          len(ids)
        })

def api_get_results():
    score = session.get('score', 0)
    total_questions = len(session.get('question_ids', []))
    total_points = session.get('max_score_total', total_questions)
    # Clear game state
    session.pop('question_ids', None)
    session.pop('current_index', None)
    session.pop('score', None)
    session.pop('max_score_total', None)
    return jsonify({'score': score, 'total': total_questions, 'total_points': total_points})

def api_sync_tags():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, image_url FROM quiz_questions")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        if not row['image_url']:
            continue
        filename = os.path.basename(row['image_url'])
        clean = os.path.splitext(filename)[0]
        parts = clean.split('_')[1:]  # skip name part

        for tag in parts:
            tag = tag.strip().capitalize()
            if not tag:
                continue
            cursor.execute("INSERT IGNORE INTO labels (name) VALUES (%s)", (tag,))
            cursor.execute("SELECT id FROM labels WHERE name = %s", (tag,))
            label_id = cursor.fetchone()['id']
            cursor.execute(
                "INSERT IGNORE INTO question_labels (question_id, label_id) VALUES (%s, %s)",
                (row['id'], label_id)
            )
            count += 1

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': f'Synced tags. {count} tag-links processed.'})


# ── User Scores ──────────────────────────────────────────────────────────────

def _ensure_user_scores_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_scores (
            google_id VARCHAR(255) PRIMARY KEY,
            email     VARCHAR(255),
            name      VARCHAR(255),
            total_score INT DEFAULT 0
        )
    """)
    # Supports fast leaderboard queries by total_score.
    cursor.execute("SHOW INDEX FROM user_scores WHERE Key_name = 'idx_user_scores_total_score'")
    if cursor.fetchone() is None:
        cursor.execute("CREATE INDEX idx_user_scores_total_score ON user_scores (total_score)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS score_history (
            id        INT AUTO_INCREMENT PRIMARY KEY,
            google_id VARCHAR(255) NOT NULL,
            score     INT NOT NULL,
            played_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_score_history_google_id (google_id)
        )
    """)
    conn.commit()
    cursor.close()

def api_get_total_score():
    google_id = request.args.get('google_id', '').strip()
    if not google_id:
        return jsonify({'total_score': 0})

    conn = get_db()
    _ensure_user_scores_table(conn)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT total_score FROM user_scores WHERE google_id = %s", (google_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({'total_score': row['total_score'] if row else 0})

def api_add_score():
    data = request.get_json(silent=True) or {}
    google_id = data.get('google_id', '').strip()
    if not google_id:
        return jsonify({'error': 'google_id required'}), 400

    email = data.get('email', '')
    name  = data.get('name', '')
    score = int(data.get('score', 0))

    conn = get_db()
    _ensure_user_scores_table(conn)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """INSERT INTO user_scores (google_id, email, name, total_score)
           VALUES (%s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
               email = VALUES(email),
               name  = VALUES(name),
               total_score = total_score + VALUES(total_score)""",
        (google_id, email, name, score)
    )
    cursor.execute(
        "INSERT INTO score_history (google_id, score) VALUES (%s, %s)",
        (google_id, score)
    )
    conn.commit()

    cursor.execute("SELECT total_score FROM user_scores WHERE google_id = %s", (google_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({'total_score': row['total_score'] if row else score})


def api_get_score_history():
    google_id = request.args.get('google_id', '').strip()
    if not google_id:
        return jsonify({'scores': [], 'best_score': 0})

    conn = get_db()
    _ensure_user_scores_table(conn)
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT score, played_at FROM score_history WHERE google_id = %s ORDER BY played_at DESC LIMIT 10",
        (google_id,)
    )
    scores = cursor.fetchall()
    for row in scores:
        if row.get('played_at'):
            row['played_at'] = str(row['played_at'])

    cursor.execute(
        "SELECT COALESCE(MAX(score), 0) AS best_score FROM score_history WHERE google_id = %s",
        (google_id,)
    )
    best = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({'scores': scores, 'best_score': best['best_score'] if best else 0})


def api_get_leaderboard():
    conn = get_db()
    _ensure_user_scores_table(conn)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            COALESCE(NULLIF(TRIM(name), ''), 'Anonymous') AS name,
            total_score
        FROM user_scores
        ORDER BY total_score DESC, name ASC
        LIMIT 10
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    rows.insert(0, {'name': 'KilburnDevGroup', 'total_score': 9999999999})
    return jsonify({'leaderboard': rows})


# ── Serve static HTML files from root ─────────────────────────────────────────
# This mirrors how the uni web server serves .html files directly.

@app.route('/')
def serve_index():
    return send_from_directory(PROJECT_DIR, 'index.html')

@app.route('/<path:filepath>')
def serve_files(filepath):
    """Serve any file from the project root (HTML, CSS, images, etc.)."""
    return send_from_directory(PROJECT_DIR, filepath)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Kilburn Klues dev server → http://localhost:5000")
    app.run(debug=True, port=5000)


