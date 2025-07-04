from flask import Flask, render_template_string, request
import os
from summarizer import WebSummarizer, OpenAIConfig

app = Flask(__name__)

# HTML template
TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Webpage Summarizer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2em; background: #f9f9f9; }
        .container { max-width: 600px; margin: auto; background: #fff; padding: 2em; border-radius: 8px; box-shadow: 0 2px 8px #0001; }
        input[type=url] { width: 100%; padding: 0.5em; font-size: 1em; }
        button { padding: 0.5em 1.5em; font-size: 1em; margin-top: 1em; }
        .summary { margin-top: 2em; background: #f4f4f4; padding: 1em; border-radius: 6px; }
        .error { color: #b00; margin-top: 1em; }
        #processing-message { display: none; color: #0074d9; margin-top: 1em; }
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var form = document.querySelector('form');
            var processing = document.getElementById('processing-message');
            if (form) {
                form.addEventListener('submit', function() {
                    if (processing) {
                        processing.style.display = 'block';
                    }
                });
            }
        });
    </script>
</head>
<body>
    <div class="container">
        <h1>Webpage Summarizer</h1>
        <form method="post">
            <label for="url">Enter a URL to summarize:</label><br>
            <input type="url" id="url" name="url" required placeholder="https://example.com" value="{{ url|default('') }}"><br>
            <button type="submit">Summarize</button>
        </form>
        <div id="processing-message">Processing... Please wait.</div>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        {% if summary %}
            <div class="summary">
                <h2>Summary</h2>
                <pre style="white-space: pre-wrap;">{{ summary }}</pre>
            </div>
        {% endif %}
    </div>
</body>
</html>
'''

# Load OpenAI API key from environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

@app.route('/', methods=['GET', 'POST'])
def index():
    summary = None
    error = None
    url = ''
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        if not url:
            error = 'Please enter a URL.'
        else:
            if not OPENAI_API_KEY:
                error = 'OpenAI API key not found. Please set OPENAI_API_KEY in your environment.'
            else:
                try:
                    openai_config = OpenAIConfig(api_key=OPENAI_API_KEY)
                    summarizer = WebSummarizer(openai_config)
                    summary = summarizer.summarize_url(url)
                    if not summary:
                        error = 'Could not generate summary. The URL may be invalid or the site could not be scraped.'
                except Exception as e:
                    error = f'Error: {e}'
    return render_template_string(TEMPLATE, summary=summary, error=error, url=url)

if __name__ == '__main__':
    app.run(debug=True) 