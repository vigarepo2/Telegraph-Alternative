import os
import json
import datetime
from flask import Flask, request, render_template, jsonify, send_from_directory
from pymongo import MongoClient
from bson.objectid import ObjectId
import bleach

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Configure MongoDB connection with the provided URL
MONGODB_URI = "mongodb+srv://viga:viga@cluster0.bael7c5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
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

# Use Gunicorn when deployed to production
if __name__ == "__main__":
    # Use this for local development
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
