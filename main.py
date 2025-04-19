from flask import Flask, render_template_string, request, redirect, url_for
import requests
import markdown
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Markdown to Telegraph Publisher</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f6f8fa; }
    .container { max-width: 900px; margin: 40px auto; background: #fff; border-radius: 12px; box-shadow: 0 4px 24px #0001; padding: 2.5em 2em; }
    .form-label { font-weight: 500; }
    .preview-box { border: 1px solid #eee; border-radius: 6px; background: #fafbfc; padding: 1em; min-height: 250px; }
    .btn-primary { background: #1565c0; border: none; }
    .btn-primary:disabled { background: #b0b0b0; }
    .token-hint { font-size: 0.95em; color: #888; }
    .result-link { font-size: 1.15em; }
    @media (max-width: 600px) {
      .container { padding: 1em; }
    }
  </style>
</head>
<body>
<div class="container">
  <h2 class="mb-4 text-center">Markdown to Telegraph Publisher</h2>
  {% if error %}
    <div class="alert alert-danger">{{ error }}</div>
  {% endif %}
  {% if result %}
    <div class="alert alert-success">
      <b>Article published!</b><br>
      <a class="result-link" href="{{ result }}" target="_blank">{{ result }}</a>
    </div>
  {% endif %}
  <form method="POST" enctype="multipart/form-data">
    <div class="mb-3">
      <label for="token" class="form-label">Telegraph Access Token</label>
      <div class="input-group">
        <input type="text" id="token" name="token" class="form-control" placeholder="Paste your Telegraph access token" required value="{{ request.form.token or '' }}">
        <button class="btn btn-outline-secondary" type="button" onclick="getToken()">Get Token</button>
      </div>
      <div id="tokenMsg" class="token-hint mt-1"></div>
    </div>
    <div class="row mb-3 g-3">
      <div class="col-md-6">
        <label for="title" class="form-label">Article Title</label>
        <input type="text" id="title" name="title" class="form-control" placeholder="Enter article title" required value="{{ request.form.title or '' }}">
      </div>
      <div class="col-md-3">
        <label for="author" class="form-label">Author Name</label>
        <input type="text" id="author" name="author" class="form-control" placeholder="Optional" value="{{ request.form.author or '' }}">
      </div>
      <div class="col-md-3">
        <label for="authorUrl" class="form-label">Author URL</label>
        <input type="text" id="authorUrl" name="authorUrl" class="form-control" placeholder="Optional" value="{{ request.form.authorUrl or '' }}">
      </div>
    </div>
    <div class="mb-3">
      <label for="markdown" class="form-label">Paste or Upload Markdown (README.md)</label>
      <textarea id="markdown" name="markdown" class="form-control" rows="10" placeholder="Paste your Markdown here...">{% if request.form.markdown %}{{ request.form.markdown }}{% endif %}</textarea>
      <input type="file" id="fileInput" name="fileInput" class="form-control mt-2" accept=".md,text/markdown" onchange="loadFile(event)">
    </div>
    <div class="mb-3">
      <label class="form-label">Live Preview</label>
      <div id="preview" class="preview-box"></div>
    </div>
    <div class="mb-4 text-end">
      <button type="submit" class="btn btn-primary px-4" id="publishBtn">Publish to Telegraph</button>
    </div>
  </form>
</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
  function loadFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
      document.getElementById('markdown').value = e.target.result;
      updatePreview();
    };
    reader.readAsText(file);
  }
  function updatePreview() {
    const md = document.getElementById('markdown').value;
    document.getElementById('preview').innerHTML = marked.parse(md);
  }
  document.getElementById('markdown').addEventListener('input', updatePreview);
  window.onload = updatePreview;

  function getToken() {
    const shortName = prompt("Short name for Telegraph account (e.g. your name or nickname):", "TelegraphUser");
    if (!shortName) return;
    document.getElementById("tokenMsg").innerText = "Creating account...";
    fetch("https://api.telegra.ph/createAccount?short_name=" + encodeURIComponent(shortName))
      .then(res => res.json())
      .then(data => {
        if (data.ok) {
          document.getElementById("token").value = data.result.access_token;
          document.getElementById("tokenMsg").innerText = "Token created! Copy and save it for future use.";
        } else {
          document.getElementById("tokenMsg").innerText = "Error: " + data.error;
        }
      })
      .catch(() => {
        document.getElementById("tokenMsg").innerText = "Network error.";
      });
  }
</script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    result = None
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        author_url = request.form.get('authorUrl', '').strip()
        markdown_text = request.form.get('markdown', '').strip()

        # Handle file upload
        file = request.files.get('fileInput')
        if file and file.filename:
            try:
                file_content = file.read().decode('utf-8')
                markdown_text = file_content
            except Exception:
                error = "Could not read uploaded file. Please ensure it's a valid UTF-8 Markdown file."
                return render_template_string(HTML_TEMPLATE, error=error, result=result, request=request)

        if not token or not title or not markdown_text:
            error = "Token, title, and Markdown content are required."
            return render_template_string(HTML_TEMPLATE, error=error, result=result, request=request)

        # Convert Markdown to HTML
        html = markdown.markdown(markdown_text, extensions=['extra', 'codehilite', 'tables', 'nl2br'])

        # Prepare content for Telegraph API (as a list of nodes, but Telegraph accepts HTML string too)
        api_url = "https://api.telegra.ph/createPage"
        payload = {
            "access_token": token,
            "title": title,
            "author_name": author,
            "author_url": author_url,
            "content": html,
            "return_content": False
        }
        try:
            resp = requests.post(api_url, json=payload, timeout=15)
            data = resp.json()
            if data.get("ok"):
                result = "https://telegra.ph/" + data["result"]["path"]
            else:
                error = "Telegraph API error: " + data.get("error", "Unknown error")
        except Exception as ex:
            error = "Network or API error: " + str(ex)

    return render_template_string(HTML_TEMPLATE, error=error, result=result, request=request)

if __name__ == '__main__':
    app.run(debug=True)
