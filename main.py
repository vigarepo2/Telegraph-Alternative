import os
import json
import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import bleach
import markdown

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://viga:viga@cluster0.bael7c5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = MongoClient(MONGODB_URI)
db = client.get_database("editor_db")
documents = db.documents

# Custom JSON encoder to handle MongoDB ObjectId and dates
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = MongoJSONEncoder

# Helper functions
def sanitize_content(content):
    """Sanitize HTML content to prevent XSS attacks"""
    allowed_tags = [
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'u', 's', 'code',
        'pre', 'ul', 'ol', 'li', 'blockquote', 'a', 'br', 'span', 'img', 'table',
        'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'target', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'span': ['style', 'class'],
        'div': ['class', 'style'],
        'code': ['class'],
        'pre': ['class'],
        '*': ['class', 'id']
    }
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs)

def serialize_document(doc):
    """Convert MongoDB document to serializable dictionary"""
    if doc:
        doc['id'] = str(doc.pop('_id'))
        return doc
    return None

# Routes
@app.route('/')
def home():
    """Render the home page with document list"""
    return render_template('index.html')

@app.route('/editor')
def editor():
    """Render the new document editor page"""
    return render_template('editor.html')

@app.route('/editor/<document_id>')
def edit_document(document_id):
    """Render the editor page for an existing document"""
    return render_template('editor.html', document_id=document_id)

@app.route('/view/<document_id>')
def view_document(document_id):
    """Render the document view page"""
    return render_template('view.html', document_id=document_id)

# API Routes
@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Get all documents"""
    try:
        docs = list(documents.find().sort('updatedAt', -1))
        return jsonify({"success": True, "data": [serialize_document(doc) for doc in docs]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/documents', methods=['POST'])
def create_document():
    """Create a new document"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({"success": False, "error": "Title is required"}), 400
            
        document = {
            "title": data.get('title'),
            "content": sanitize_content(data.get('content', '')),
            "author": data.get('author', 'Anonymous'),
            "tags": data.get('tags', []),
            "createdAt": datetime.datetime.utcnow(),
            "updatedAt": datetime.datetime.utcnow()
        }
        
        result = documents.insert_one(document)
        document['_id'] = result.inserted_id
        
        return jsonify({"success": True, "data": serialize_document(document)}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get a specific document"""
    try:
        doc = documents.find_one({"_id": ObjectId(document_id)})
        if not doc:
            return jsonify({"success": False, "error": "Document not found"}), 404
            
        return jsonify({"success": True, "data": serialize_document(doc)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['PUT'])
def update_document(document_id):
    """Update a specific document"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({"success": False, "error": "Title is required"}), 400
            
        update_data = {
            "title": data.get('title'),
            "content": sanitize_content(data.get('content', '')),
            "tags": data.get('tags', []),
            "updatedAt": datetime.datetime.utcnow()
        }
        
        result = documents.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Document not found"}), 404
            
        doc = documents.find_one({"_id": ObjectId(document_id)})
        return jsonify({"success": True, "data": serialize_document(doc)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a specific document"""
    try:
        result = documents.delete_one({"_id": ObjectId(document_id)})
        
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Document not found"}), 404
            
        return jsonify({"success": True, "data": {"id": document_id}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Create folder structure if it doesn't exist
for folder in ['templates', 'static', 'static/css', 'static/js', 'static/img']:
    os.makedirs(folder, exist_ok=True)

# Create necessary template files
with open('templates/index.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advanced Text Editor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div class="logo">
                    <h1>Advanced Text Editor</h1>
                </div>
                <div class="header-actions">
                    <a href="/editor" class="primary-button">
                        <i class="fas fa-plus"></i> New Document
                    </a>
                </div>
            </div>
        </header>

        <main class="main-content">
            <section class="documents-section">
                <div class="section-header">
                    <h2>Your Documents</h2>
                </div>
                <div id="documents-list" class="documents-grid">
                    <div class="loading-indicator">
                        <i class="fas fa-spinner fa-spin"></i> Loading documents...
                    </div>
                </div>
            </section>
        </main>

        <footer class="app-footer">
            <div class="footer-content">
                <p>&copy; 2025 Advanced Text Editor. All rights reserved.</p>
            </div>
        </footer>
    </div>

    <template id="document-card-template">
        <div class="document-card">
            <div class="document-info">
                <h3 class="document-title"></h3>
                <p class="document-date"></p>
            </div>
            <div class="document-actions">
                <a class="view-button" title="View Document">
                    <i class="fas fa-eye"></i>
                </a>
                <a class="edit-button" title="Edit Document">
                    <i class="fas fa-edit"></i>
                </a>
                <button class="delete-button" title="Delete Document">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        </div>
    </template>

    <div id="confirmation-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Confirm Deletion</h3>
                <button class="close-button">&times;</button>
            </div>
            <div class="modal-body">
                <p>Are you sure you want to delete this document? This action cannot be undone.</p>
            </div>
            <div class="modal-footer">
                <button class="secondary-button cancel-button">Cancel</button>
                <button class="primary-button confirm-button">Delete</button>
            </div>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/documents.js') }}"></script>
</body>
</html>
''')

with open('templates/editor.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Editor | Advanced Text Editor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <!-- Quill.js Rich Text Editor -->
    <link href="https://cdn.quilljs.com/1.3.7/quill.snow.css" rel="stylesheet">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div class="logo">
                    <h1>Document Editor</h1>
                </div>
                <div class="header-actions">
                    <a href="/" class="secondary-button">
                        <i class="fas fa-arrow-left"></i> Back to Documents
                    </a>
                </div>
            </div>
        </header>

        <main class="editor-main-content">
            <div class="editor-container">
                <div class="document-info">
                    <input type="text" id="document-title" placeholder="Document Title" class="title-input">
                    <p id="last-saved" class="last-saved-text">Not saved yet</p>
                </div>
                
                <div class="editor-wrapper">
                    <!-- Toolbar container -->
                    <div id="toolbar-container">
                        <span class="ql-formats">
                            <select class="ql-header">
                                <option value="1">Heading 1</option>
                                <option value="2">Heading 2</option>
                                <option value="3">Heading 3</option>
                                <option selected>Normal</option>
                            </select>
                            <select class="ql-font">
                                <option selected>Sans Serif</option>
                                <option value="serif">Serif</option>
                                <option value="monospace">Monospace</option>
                            </select>
                            <select class="ql-size">
                                <option value="small">Small</option>
                                <option selected>Normal</option>
                                <option value="large">Large</option>
                                <option value="huge">Huge</option>
                            </select>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-bold"></button>
                            <button class="ql-italic"></button>
                            <button class="ql-underline"></button>
                            <button class="ql-strike"></button>
                        </span>
                        <span class="ql-formats">
                            <select class="ql-color"></select>
                            <select class="ql-background"></select>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-script" value="sub"></button>
                            <button class="ql-script" value="super"></button>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-list" value="ordered"></button>
                            <button class="ql-list" value="bullet"></button>
                            <button class="ql-indent" value="-1"></button>
                            <button class="ql-indent" value="+1"></button>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-direction" value="rtl"></button>
                            <select class="ql-align"></select>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-link"></button>
                            <button class="ql-image"></button>
                            <button class="ql-code-block"></button>
                            <button class="ql-blockquote"></button>
                        </span>
                        <span class="ql-formats">
                            <button class="ql-clean"></button>
                        </span>
                    </div>
                    
                    <!-- Editor container -->
                    <div id="editor-container"></div>
                </div>
                
                <div class="editor-actions">
                    <div class="tags-container">
                        <label for="document-tags">Tags (comma separated):</label>
                        <input type="text" id="document-tags" placeholder="tech, notes, important" class="tags-input">
                    </div>
                    <div class="buttons-container">
                        <button id="discard-button" class="secondary-button">
                            <i class="fas fa-times"></i> Discard
                        </button>
                        <button id="save-button" class="primary-button">
                            <i class="fas fa-save"></i> Save Document
                        </button>
                    </div>
                </div>
            </div>
        </main>

        <footer class="app-footer">
            <div class="footer-content">
                <p>&copy; 2025 Advanced Text Editor. All rights reserved.</p>
            </div>
        </footer>
    </div>

    <div id="notification" class="notification hidden">
        <span id="notification-message"></span>
        <button id="notification-close">
            <i class="fas fa-times"></i>
        </button>
    </div>

    <!-- Quill.js library -->
    <script src="https://cdn.quilljs.com/1.3.7/quill.min.js"></script>
    <script src="{{ url_for('static', filename='js/editor.js') }}"></script>
    {% if document_id %}
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            loadDocument('{{ document_id }}');
        });
    </script>
    {% endif %}
</body>
</html>
''')

with open('templates/view.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>View Document | Advanced Text Editor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <!-- Quill.js styles for rendering -->
    <link href="https://cdn.quilljs.com/1.3.7/quill.snow.css" rel="stylesheet">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div class="logo">
                    <h1 id="document-title-display">Loading Document...</h1>
                </div>
                <div class="header-actions">
                    <a href="/" class="secondary-button">
                        <i class="fas fa-arrow-left"></i> Back to Documents
                    </a>
                    <a id="edit-document-link" class="primary-button">
                        <i class="fas fa-edit"></i> Edit
                    </a>
                </div>
            </div>
        </header>

        <main class="main-content">
            <div class="document-view-container">
                <div class="document-metadata">
                    <p id="document-date" class="document-date">Loading...</p>
                    <div id="document-tags-container" class="document-tags">
                        <!-- Tags will be inserted here -->
                    </div>
                </div>
                
                <div id="document-content" class="document-content">
                    <div class="loading-indicator">
                        <i class="fas fa-spinner fa-spin"></i> Loading document content...
                    </div>
                </div>
            </div>
        </main>

        <footer class="app-footer">
            <div class="footer-content">
                <p>&copy; 2025 Advanced Text Editor. All rights reserved.</p>
            </div>
        </footer>
    </div>

    <script src="{{ url_for('static', filename='js/view.js') }}"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            loadDocument('{{ document_id }}');
        });
    </script>
</body>
</html>
''')

with open('templates/404.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found | Advanced Text Editor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div class="logo">
                    <h1>Advanced Text Editor</h1>
                </div>
                <div class="header-actions">
                    <a href="/" class="primary-button">
                        <i class="fas fa-home"></i> Back to Home
                    </a>
                </div>
            </div>
        </header>

        <main class="main-content">
            <div class="error-container">
                <div class="error-code">404</div>
                <h2 class="error-title">Page Not Found</h2>
                <p class="error-message">The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.</p>
                <a href="/" class="primary-button">
                    <i class="fas fa-home"></i> Go to Homepage
                </a>
            </div>
        </main>

        <footer class="app-footer">
            <div class="footer-content">
                <p>&copy; 2025 Advanced Text Editor. All rights reserved.</p>
            </div>
        </footer>
    </div>
</body>
</html>
''')

with open('templates/500.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error | Advanced Text Editor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-content">
                <div class="logo">
                    <h1>Advanced Text Editor</h1>
                </div>
                <div class="header-actions">
                    <a href="/" class="primary-button">
                        <i class="fas fa-home"></i> Back to Home
                    </a>
                </div>
            </div>
        </header>

        <main class="main-content">
            <div class="error-container">
                <div class="error-code">500</div>
                <h2 class="error-title">Server Error</h2>
                <p class="error-message">Something went wrong on our servers. We're working to fix the issue.</p>
                <a href="/" class="primary-button">
                    <i class="fas fa-home"></i> Go to Homepage
                </a>
            </div>
        </main>

        <footer class="app-footer">
            <div class="footer-content">
                <p>&copy; 2025 Advanced Text Editor. All rights reserved.</p>
            </div>
        </footer>
    </div>
</body>
</html>
''')

# Create static files
with open('static/css/styles.css', 'w') as f:
    f.write('''
/* Base Styles and Variables */
:root {
    --primary-color: #4a72da;
    --primary-dark: #3a5bbd;
    --secondary-color: #2c3e50;
    --accent-color: #16a085;
    --background-color: #ffffff;
    --card-background: #ffffff;
    --border-color: #e0e0e0;
    --text-primary: #333333;
    --text-secondary: #666666;
    --text-light: #999999;
    --text-white: #ffffff;
    --shadow-light: 0 2px 5px rgba(0, 0, 0, 0.05);
    --shadow-medium: 0 4px 12px rgba(0, 0, 0, 0.1);
    --radius-small: 4px;
    --radius-medium: 8px;
    --radius-large: 12px;
    --transition: all 0.3s ease;
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}

/* Reset and Base Styles */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: var(--font-family);
    font-size: 16px;
    line-height: 1.5;
    color: var(--text-primary);
    background-color: #f8f9fa;
    min-height: 100vh;
}

a {
    color: var(--primary-color);
    text-decoration: none;
    transition: var(--transition);
}

a:hover {
    color: var(--primary-dark);
}

button,
.button {
    cursor: pointer;
    border: none;
    outline: none;
    font-family: inherit;
    font-size: 1rem;
    padding: 0.75rem 1.5rem;
    border-radius: var(--radius-medium);
    transition: var(--transition);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.primary-button {
    background-color: var(--primary-color);
    color: var(--text-white);
}

.primary-button:hover {
    background-color: var(--primary-dark);
    color: var(--text-white);
}

.secondary-button {
    background-color: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

.secondary-button:hover {
    background-color: #f2f2f2;
}

input, textarea {
    font-family: inherit;
    font-size: 1rem;
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-medium);
    outline: none;
    transition: var(--transition);
}

input:focus, textarea:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(74, 114, 218, 0.2);
}

/* App Layout */
.app-container {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

.app-header {
    background-color: var(--background-color);
    box-shadow: var(--shadow-light);
    border-bottom: 1px solid var(--border-color);
    padding: 1rem 0;
    position: sticky;
    top: 0;
    z-index: 10;
}

.header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logo h1 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
}

.header-actions {
    display: flex;
    gap: 1rem;
}

.main-content {
    flex: 1;
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    width: 100%;
}

.app-footer {
    background-color: var(--background-color);
    border-top: 1px solid var(--border-color);
    padding: 1.5rem 0;
    margin-top: auto;
}

.footer-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1.5rem;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

/* Document List */
.documents-section {
    background-color: var(--card-background);
    border-radius: var(--radius-large);
    box-shadow: var(--shadow-light);
    padding: 2rem;
}

.section-header {
    margin-bottom: 1.5rem;
}

.section-header h2 {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary);
}

.documents-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.document-card {
    background-color: var(--card-background);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-medium);
    padding: 1.5rem;
    transition: var(--transition);
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-light);
}

.document-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-medium);
    border-color: #d0d0d0;
}

.document-info {
    flex: 1;
    margin-bottom: 1rem;
}

.document-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}

.document-date {
    color: var(--text-light);
    font-size: 0.875rem;
}

.document-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border-color);
}

.document-actions a,
.document-actions button {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    padding: 0.5rem;
    border-radius: var(--radius-small);
    color: var(--text-secondary);
    transition: var(--transition);
}

.view-button:hover {
    background-color: #e3f2fd;
    color: #1976d2;
}

.edit-button:hover {
    background-color: #e8f5e9;
    color: #2e7d32;
}

.delete-button:hover {
    background-color: #ffebee;
    color: #c62828;
}

.loading-indicator {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
}

.loading-indicator i {
    margin-right: 0.5rem;
}

/* Editor Styles */
.editor-main-content {
    flex: 1;
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    width: 100%;
}

.editor-container {
    background-color: var(--card-background);
    border-radius: var(--radius-large);
    box-shadow: var(--shadow-light);
    padding: 2rem;
}

.document-info {
    margin-bottom: 1.5rem;
}

.title-input {
    font-size: 1.75rem;
    font-weight: 600;
    padding: 0.5rem 0;
    border: none;
    border-bottom: 2px solid var(--border-color);
    border-radius: 0;
}

.title-input:focus {
    border-color: var(--primary-color);
    box-shadow: none;
}

.last-saved-text {
    color: var(--text-light);
    font-size: 0.875rem;
    margin-top: 0.5rem;
}

.editor-wrapper {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-medium);
    margin-bottom: 1.5rem;
}

/* Quill editor customizations */
#toolbar-container {
    border-bottom: 1px solid var(--border-color) !important;
    border-top: none !important;
    border-left: none !important;
    border-right: none !important;
}

#editor-container {
    min-height: 350px;
    max-height: 600px;
    overflow-y: auto;
    padding: 1rem;
}

.ql-container {
    font-family: var(--font-family) !important;
    font-size: 1rem !important;
    border: none !important;
}

.editor-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 2rem;
    flex-wrap: wrap;
    gap: 1rem;
}

.tags-container {
    flex: 1;
    min-width: 250px;
}

.tags-container label {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--text-secondary);
}

.buttons-container {
    display: flex;
    gap: 1rem;
}

/* Document View */
.document-view-container {
    background-color: var(--card-background);
    border-radius: var(--radius-large);
    box-shadow: var(--shadow-light);
    padding: 2rem;
}

.document-metadata {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
    flex-wrap: wrap;
    gap: 1rem;
}

.document-tags {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.tag {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    background-color: #f2f7ff;
    border-radius: 50px;
    color: var(--primary-color);
    font-size: 0.875rem;
}

.document-content {
    line-height: 1.7;
}

/* Notification */
.notification {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    background-color: var(--card-background);
    box-shadow: var(--shadow-medium);
    border-radius: var(--radius-medium);
    padding: 1rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    z-index: 100;
    max-width: 350px;
    animation: slideIn 0.3s ease-out forwards;
}

.notification.success {
    border-left: 4px solid #4caf50;
}

.notification.error {
    border-left: 4px solid #f44336;
}

.notification.hidden {
    display: none;
}

#notification-close {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-light);
    padding: 0.25rem;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    justify-content: center;
    align-items: center;
    animation: fadeIn 0.3s ease-out forwards;
}

.modal-content {
    background-color: var(--card-background);
    border-radius: var(--radius-large);
    max-width: 500px;
    width: 90%;
    box-shadow: var(--shadow-medium);
    animation: zoomIn 0.3s ease-out forwards;
}

.modal-header {
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h3 {
    font-size: 1.25rem;
    font-weight: 600;
}

.close-button {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--text-light);
    padding: 0;
}

.modal-body {
    padding: 1.5rem;
}

.modal-footer {
    padding: 1.5rem;
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

@keyframes zoomIn {
    from {
        transform: scale(0.9);
        opacity: 0;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}

/* Error Pages */
.error-container {
    max-width: 600px;
    margin: 0 auto;
    text-align: center;
    padding: 4rem 1rem;
}

.error-code {
    font-size: 6rem;
    font-weight: 700;
    color: var(--primary-color);
    line-height: 1;
    margin-bottom: 1rem;
}

.error-title {
    font-size: 2rem;
    font-weight: 600;
    margin-bottom: 1.5rem;
}

.error-message {
    color: var(--text-secondary);
    margin-bottom: 2rem;
}

/* Responsive Adjustments */
@media (max-width: 768px) {
    .header-content {
        flex-direction: column;
        align-items: flex-start;
        gap: 1rem;
    }
    
    .header-actions {
        width: 100%;
    }
    
    .documents-grid {
        grid-template-columns: 1fr;
    }
    
    .editor-actions {
        flex-direction: column;
    }
    
    .document-metadata {
        flex-direction: column;
        align-items: flex-start;
    }
}

/* Focus Styles for Accessibility */
:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
}
''')

with open('static/js/documents.js', 'w') as f:
    f.write('''
document.addEventListener('DOMContentLoaded', () => {
    const documentsList = document.getElementById('documents-list');
    const documentCardTemplate = document.getElementById('document-card-template');
    const confirmationModal = document.getElementById('confirmation-modal');
    const closeModalButton = confirmationModal.querySelector('.close-button');
    const cancelButton = confirmationModal.querySelector('.cancel-button');
    const confirmButton = confirmationModal.querySelector('.confirm-button');
    
    let documentToDelete = null;
    
    // Load documents
    fetchDocuments();
    
    // Add event listeners for modal
    closeModalButton.addEventListener('click', closeModal);
    cancelButton.addEventListener('click', closeModal);
    confirmButton.addEventListener('click', confirmDelete);
    confirmationModal.addEventListener('click', (e) => {
        if (e.target === confirmationModal) closeModal();
    });
    
    // Functions
    async function fetchDocuments() {
        try {
            const response = await fetch('/api/documents');
            const result = await response.json();
            
            if (result.success) {
                renderDocuments(result.data);
            } else {
                showErrorMessage('Failed to load documents');
            }
        } catch (error) {
            console.error('Error fetching documents:', error);
            showErrorMessage('Failed to load documents. Please try again later.');
        }
    }
    
    function renderDocuments(documents) {
        // Clear loading indicator
        documentsList.innerHTML = '';
        
        if (documents.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            emptyState.innerHTML = `
                <p>No documents yet. Create your first one!</p>
                <a href="/editor" class="primary-button">
                    <i class="fas fa-plus"></i> Create Document
                </a>
            `;
            documentsList.appendChild(emptyState);
            return;
        }
        
        // Create document cards
        documents.forEach(doc => {
            const docCard = documentCardTemplate.content.cloneNode(true);
            
            // Set document title
            const titleElement = docCard.querySelector('.document-title');
            titleElement.textContent = doc.title;
            
            // Set document date
            const dateElement = docCard.querySelector('.document-date');
            const formattedDate = new Date(doc.updatedAt).toLocaleString();
            dateElement.textContent = `Last updated: ${formattedDate}`;
            
            // Set action links
            const viewButton = docCard.querySelector('.view-button');
            viewButton.href = `/view/${doc.id}`;
            
            const editButton = docCard.querySelector('.edit-button');
            editButton.href = `/editor/${doc.id}`;
            
            const deleteButton = docCard.querySelector('.delete-button');
            deleteButton.addEventListener('click', () => openDeleteModal(doc));
            
            documentsList.appendChild(docCard);
        });
    }
    
    function openDeleteModal(doc) {
        documentToDelete = doc;
        confirmationModal.style.display = 'flex';
    }
    
    function closeModal() {
        confirmationModal.style.display = 'none';
        documentToDelete = null;
    }
    
    async function confirmDelete() {
        if (!documentToDelete) return;
        
        try {
            const response = await fetch(`/api/documents/${documentToDelete.id}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Refresh the document list
                fetchDocuments();
                showSuccessMessage('Document deleted successfully');
            } else {
                showErrorMessage('Failed to delete document');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            showErrorMessage('Failed to delete document. Please try again later.');
        }
        
        closeModal();
    }
    
    function showSuccessMessage(message) {
        console.log('Success:', message);
        // In a full implementation, you would show a notification/toast here
    }
    
    function showErrorMessage(message) {
        console.error('Error:', message);
        // In a full implementation, you would show an error notification/toast here
    }
});
''')

with open('static/js/editor.js', 'w') as f:
    f.write('''
document.addEventListener('DOMContentLoaded', () => {
    // Initialize variables
    let currentDocumentId = null;
    let documentTags = [];
    let isEditingExisting = false;
    
    // DOM elements
    const titleInput = document.getElementById('document-title');
    const lastSavedText = document.getElementById('last-saved');
    const tagsInput = document.getElementById('document-tags');
    const saveButton = document.getElementById('save-button');
    const discardButton = document.getElementById('discard-button');
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    const notificationClose = document.getElementById('notification-close');
    
    // Initialize Quill editor
    const quill = new Quill('#editor-container', {
        theme: 'snow',
        modules: {
            toolbar: '#toolbar-container'
        },
        placeholder: 'Start writing your document...',
    });
    
    // Event listeners
    saveButton.addEventListener('click', saveDocument);
    discardButton.addEventListener('click', discardChanges);
    notificationClose.addEventListener('click', hideNotification);
    
    // Set up auto-save interval (every 30 seconds)
    let autoSaveInterval = setInterval(() => {
        if (hasUnsavedChanges()) {
            autoSave();
        }
    }, 30000);
    
    // Functions
    function hasUnsavedChanges() {
        // Check if there's content to save and if the title isn't empty
        return quill.getText().trim().length > 0 && titleInput.value.trim().length > 0;
    }
    
    async function saveDocument() {
        // Validate form
        const title = titleInput.value.trim();
        if (!title) {
            showNotification('Please enter a document title', 'error');
            titleInput.focus();
            return;
        }
        
        const content = quill.root.innerHTML;
        
        // Check if there's actual content
        if (quill.getText().trim() === '') {
            showNotification('Please add some content to your document', 'error');
            quill.focus();
            return;
        }
        
        // Prepare tags
        const tagsString = tagsInput.value.trim();
        const tags = tagsString ? tagsString.split(',').map(tag => tag.trim()) : [];
        
        // Prepare data to send
        const documentData = {
            title,
            content,
            tags
        };
        
        saveButton.disabled = true;
        saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        
        try {
            let response;
            
            if (isEditingExisting && currentDocumentId) {
                // Update existing document
                response = await fetch(`/api/documents/${currentDocumentId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(documentData)
                });
            } else {
                // Create new document
                response = await fetch('/api/documents', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(documentData)
                });
            }
            
            const result = await response.json();
            
            if (result.success) {
                // Update the current document ID if it's a new document
                if (!isEditingExisting) {
                    currentDocumentId = result.data.id;
                    isEditingExisting = true;
                    
                    // Update URL without reloading the page
                    window.history.replaceState({}, '', `/editor/${currentDocumentId}`);
                }
                
                // Update last saved text
                const now = new Date();
                lastSavedText.textContent = `Last saved: ${now.toLocaleString()}`;
                
                // Show success notification
                showNotification('Document saved successfully', 'success');
            } else {
                throw new Error(result.error || 'Failed to save document');
            }
        } catch (error) {
            console.error('Error saving document:', error);
            showNotification(`Error: ${error.message}`, 'error');
        } finally {
            saveButton.disabled = false;
            saveButton.innerHTML = '<i class="fas fa-save"></i> Save Document';
        }
    }
    
    async function autoSave() {
        if (!titleInput.value.trim()) return;
        
        try {
            const documentData = {
                title: titleInput.value.trim(),
                content: quill.root.innerHTML,
                tags: tagsInput.value.trim().split(',').map(tag => tag.trim())
            };
            
            let response;
            
            if (isEditingExisting && currentDocumentId) {
                // Update existing document
                response = await fetch(`/api/documents/${currentDocumentId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(documentData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Update last saved text
                    const now = new Date();
                    lastSavedText.textContent = `Auto-saved: ${now.toLocaleString()}`;
                }
            }
        } catch (error) {
            console.error('Error auto-saving document:', error);
        }
    }
    
    function discardChanges() {
        if (confirm('Are you sure you want to discard your changes? This cannot be undone.')) {
            window.location.href = '/';
        }
    }
    
    function showNotification(message, type) {
        notificationMessage.textContent = message;
        notification.className = `notification ${type}`;
        
        // Hide notification after 5 seconds
        setTimeout(hideNotification, 5000);
    }
    
    function hideNotification() {
        notification.className = 'notification hidden';
    }
    
    // Function to load a document by ID
    window.loadDocument = async function(documentId) {
        if (!documentId) return;
        
        try {
            const response = await fetch(`/api/documents/${documentId}`);
            const result = await response.json();
            
            if (result.success) {
                const doc = result.data;
                
                // Set document details
                titleInput.value = doc.title;
                quill.root.innerHTML = doc.content;
                
                // Set tags
                tagsInput.value = doc.tags.join(', ');
                
                // Set document state variables
                currentDocumentId = doc.id;
                isEditingExisting = true;
                
                // Update last saved text
                const lastUpdated = new Date(doc.updatedAt).toLocaleString();
                lastSavedText.textContent = `Last saved: ${lastUpdated}`;
            } else {
                showNotification('Failed to load document', 'error');
            }
        } catch (error) {
            console.error('Error loading document:', error);
            showNotification('Error loading document. Please try again later.', 'error');
        }
    };
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', (event) => {
        // Cancel the auto-save interval
        clearInterval(autoSaveInterval);
        
        // Show warning if there are unsaved changes
        if (hasUnsavedChanges()) {
            event.preventDefault();
            event.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            return event.returnValue;
        }
    });
});
''')

with open('static/js/view.js', 'w') as f:
    f.write('''
document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const titleElement = document.getElementById('document-title-display');
    const dateElement = document.getElementById('document-date');
    const tagsContainer = document.getElementById('document-tags-container');
    const contentElement = document.getElementById('document-content');
    const editLink = document.getElementById('edit-document-link');
    
    // Function to load document from API
    window.loadDocument = async function(documentId) {
        if (!documentId) return;
        
        try {
            const response = await fetch(`/api/documents/${documentId}`);
            const result = await response.json();
            
            if (result.success) {
                const doc = result.data;
                
                // Set document title
                titleElement.textContent = doc.title;
                document.title = `${doc.title} | Advanced Text Editor`;
                
                // Set document date
                const formattedDate = new Date(doc.updatedAt).toLocaleString();
                dateElement.textContent = `Last updated: ${formattedDate}`;
                
                // Set tags
                if (doc.tags && doc.tags.length > 0) {
                    tagsContainer.innerHTML = '';
                    doc.tags.forEach(tag => {
                        const tagElement = document.createElement('span');
                        tagElement.className = 'tag';
                        tagElement.textContent = tag;
                        tagsContainer.appendChild(tagElement);
                    });
                } else {
                    tagsContainer.innerHTML = '';
                }
                
                // Set document content
                contentElement.innerHTML = doc.content;
                
                // Set edit link
                editLink.href = `/editor/${doc.id}`;
            } else {
                showError('Failed to load document');
            }
        } catch (error) {
            console.error('Error loading document:', error);
            showError('Error loading document. Please try again later.');
        }
    };
    
    function showError(message) {
        contentElement.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <p>${message}</p>
            </div>
        `;
    }
});
''')

# Create vercel.json configuration
with open('vercel.json', 'w') as f:
    f.write('''
{
  "version": 2,
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    },
    {
      "src": "static/**",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ]
}
''')

# Main function to run the app
if __name__ == "__main__":
    app.run(debug=True)
