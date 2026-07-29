# Kilburn Klues

Kilburn Klues is an interactive web experience for learning your way around the Kilburn Building, home of Computer Science at the University of Manchester. It combines a photo guide with a location quiz, map-based questions, Google sign-in, score history, and a global leaderboard.

The project is designed to run in two environments from the same front end:

- **University hosting:** `api.php` serves the JSON API using PHP and MySQL.
- **Local development:** `app.py` mirrors the PHP API with Flask and MySQL while also serving the static site.

The browser always calls `api.php?action=...`, so moving between the two environments does not require front-end changes.

## Features

- Photo-based exploration of locations around the Kilburn Building
- Randomised quiz sessions backed by server-side session state
- Multiple-choice questions worth one point each
- Map questions where players place a marker on a floor plan
- Distance-based map scoring with configurable maximum points
- Guide filtering through database-backed tags
- Google Identity Services sign-in
- Persistent lifetime scores and recent score history
- Top-ten global leaderboard
- Light and dark themes saved in the browser
- Responsive landing page with React-powered account and sign-in UI
- Matching PHP and Flask implementations of the application API

> [!IMPORTANT]
> The current repository contains the landing page and both API implementations, but it does not contain the linked `templates/` pages or `static/scores.js`. The guide, game, past-scores, and leaderboard interfaces therefore need those missing front-end files before the full experience can run from this checkout.

## How it works

```text
Browser
  |-- index.html + index.css
  |-- React 18 + Babel CDN -> index.jsx
  |-- Google Identity Services
  |
  `-- fetch("api.php?action=...")
          |
          |-- University server -> api.php -> MySQL
          |
          `-- Local machine -----> app.py  -> MySQL
```

The landing page is plain HTML and CSS with a small React “island” in `index.jsx`. React handles the sign-in modal, account menu, theme toggle, score badge, and scroll animations. React, ReactDOM, Babel, Google Fonts, and Google Identity Services are loaded from CDNs, so there is no Node.js build step.

Both back ends expose the same action-based API. PHP uses `mysqli` and credentials supplied by the university's generated `config.inc.php`; Flask uses `mysql-connector-python` and values loaded from a local `.env` file.

### Quiz flow

1. `start_game` reads every question, shuffles the IDs, calculates the maximum possible score, and stores the game in the server session.
2. `get_question` returns the current question and image filenames. Map coordinates are removed before the response is sent.
3. `submit_answer` checks an MCQ answer or scores a map guess, updates the session, and advances the question index.
4. `get_results` returns the final score and clears the game state.
5. Signed-in players can submit the result to their lifetime total and score history.

### Scoring

- **Multiple choice:** one point for an exact match with `correct_answer`.
- **Map question:** full points within 2 percentage points of the target, zero points at 30 or more, and a linear falloff between them.

Map coordinates use a normalised `0–100` coordinate space, which keeps scoring independent of the rendered floor-plan size.

### Guide tags

`sync_tags` derives labels from underscore-separated image filenames:

```text
<location>_<tag>_<tag>.<extension>
```

For example, `Lab2.25_Two_Easy.jpg` produces the tags `Two` and `Easy`. The first segment identifies the location and is skipped. `INSERT IGNORE` makes repeated syncs duplicate-safe when the relevant database columns are unique.

## Tech stack

| Layer | Technology |
| --- | --- |
| Front end | HTML5, CSS3, JavaScript, React 18 |
| Browser JSX | Babel Standalone |
| Authentication UI | Google Identity Services |
| Production API | PHP, `mysqli`, PHP sessions |
| Local API | Python, Flask, `mysql-connector-python` |
| Database | MySQL |
| Configuration | University `config.inc.php` or local `.env` |

## Repository structure

```text
KilburnKlues/
|-- index.html             # Landing page and links into the guide/game
|-- index.css              # Theme, layout, responsive styles, and animations
|-- index.jsx              # React account, auth, theme, and score UI
|-- api.php                # Main API for university PHP hosting
|-- app.py                 # Equivalent Flask API and local static server
|-- guide_images.php       # Legacy/standalone guide-image endpoint
`-- kilburn_building.jpg   # Landing-page hero image
```

## Running locally

### Prerequisites

- Python 3.10 or newer
- MySQL
- A populated Kilburn Klues database

### 1. Clone the repository

```bash
git clone https://github.com/raina-ayaan/KilburnKlues.git
cd KilburnKlues
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install the Python dependencies

The repository does not currently include a `requirements.txt`, so install the packages used by `app.py` directly:

```bash
pip install Flask mysql-connector-python python-dotenv
```

### 4. Configure MySQL

Create `.env` in the project root:

```dotenv
DB_HOST=localhost
DB_USER=your_mysql_user
DB_PSWD=your_mysql_password
DB_NAME=your_database_name
```

> [!NOTE]
> The password variable is named `DB_PSWD` in the current code.

### 5. Start the development server

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000). Flask serves the project files and intercepts requests to `/api.php`, allowing the same browser code to work locally.

## Database model

The repository does not currently include migrations or a schema dump. The API expects the following data model.

### `quiz_questions`

Core fields referenced by the code:

| Field | Purpose |
| --- | --- |
| `id` | Question identifier |
| `image_url` | Location image path |
| `question_type` | `mcq` or `map`; defaults logically to `mcq` |
| `question` | Prompt shown to the player |
| `option_a`–`option_d` | Multiple-choice answers |
| `correct_answer` | Correct MCQ option |
| `floorplan_url` | Floor-plan image path for map questions |
| `correct_x`, `correct_y` | Correct map position in `0–100` coordinates |
| `score` | Maximum score for a map question; defaults logically to 10 |

### Tagging tables

- `labels`: label ID and a unique `name`
- `question_labels`: unique question/label pairs linking questions to filters

### Score tables

`user_scores` and `score_history` are created automatically the first time a score endpoint is used. They store a player's lifetime score and their ten most recent games. Scores are keyed by the Google account subject ID.

## API reference

All main operations use `/api.php?action=<action>`.

| Action | Method | Purpose |
| --- | --- | --- |
| `guide_images` | GET | Return all questions/images; accepts optional `tag` |
| `guide_tags` | GET | Return labels in alphabetical order |
| `start_game` | GET | Shuffle questions and initialise a session |
| `get_question` | GET | Return the current question |
| `submit_answer` | POST | Submit `{ "answer": "A" }` or map coordinates `{ "x": 50, "y": 25 }` |
| `get_results` | GET | Return the result and clear game state |
| `sync_tags` | GET | Generate labels from image filenames |
| `get_total_score` | GET | Return a player's lifetime score by `google_id` |
| `add_score` | POST | Add a game score and history entry |
| `get_leaderboard` | GET | Return the ten highest lifetime scores |
| `get_score_history` | GET | Return the latest ten games and best score for a player |

`guide_images.php` also exposes an older standalone endpoint that returns every quiz question ordered by ID.

## University deployment

On the University of Manchester CS web server, static files are served directly and PHP handles the API. `api.php` and `guide_images.php` expect a server-generated `config.inc.php` containing the database credentials and `$group_dbnames` array.



## Team

Built by **KilburnDevGroup (Group X16 2025-26)** at the University of Manchester as a playful way to explore and learn the Kilburn Building.

## License

No license is currently included. Unless one is added, standard copyright rules apply.

