import pandas as pd
import csv
import chardet
from collections import Counter
from flask import Flask, request, jsonify, render_template
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def detect_encoding(file_path, sample_size=10000):
    """Detects file encoding and defaults to UTF-8 if detection fails."""
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return result['encoding'] if result['encoding'] else "utf-8"

def detect_delimiter(file_path, encoding):
    """Detects delimiter and text separator in a CSV file."""
    with open(file_path, 'r', encoding=encoding, errors="replace") as f:
        sample = f.read(2048)
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(sample)
    return dialect.delimiter, dialect.quotechar

def has_inconsistent_quotes(row, quotechar):
    """Checks if a row has inconsistent quote usage."""
    quoted_fields = [field for field in row if field.startswith(quotechar) and field.endswith(quotechar)]
    unquoted_fields = [field for field in row if not (field.startswith(quotechar) and field.endswith(quotechar))]
    return len(quoted_fields) > 0 and len(unquoted_fields) > 0

def analyze_csv(file_path):
    """Analyzes CSV for delimiter, text separator issues, and row consistency."""
    encoding = detect_encoding(file_path)
    delimiter, quotechar = detect_delimiter(file_path, encoding)

    with open(file_path, 'r', encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
        rows = list(reader)

    col_counts = [len(row) for row in rows]
    most_common_col_count = Counter(col_counts).most_common(1)[0][0]

    problematic_rows = []
    inconsistent_quote_rows = []

    for i, row in enumerate(rows):
        if len(row) != most_common_col_count:
            problematic_rows.append({
                "Row Number": i + 1,
                "Actual Columns": len(row),
                "Expected": most_common_col_count,
                "Row Data": row
            })

        if has_inconsistent_quotes(row, quotechar):
            inconsistent_quote_rows.append({
                "Row Number": i + 1,
                "Row Data": row
            })

    result = {
        "Encoding": encoding,
        "Delimiter": delimiter,
        "Text Separator": quotechar,
        "Expected Column Count": most_common_col_count,
        "Row Consistency": len(problematic_rows) == 0,
        "Problematic Rows": problematic_rows,
        "Inconsistent Quote Usage Rows": inconsistent_quote_rows
    }

    return result

def analyze_excel(file_path):
    """Analyzes Excel files for row consistency."""
    df = pd.ExcelFile(file_path)
    sheet_analysis = {}

    for sheet in df.sheet_names:
        data = df.parse(sheet, dtype=str).fillna("")
        col_counts = data.apply(lambda x: x.count(), axis=1).tolist()
        most_common_col_count = Counter(col_counts).most_common(1)[0][0]

        problematic_rows = [
            {"Row Number": i + 1, "Actual Columns": col_counts[i], "Expected": most_common_col_count, "Row Data": data.iloc[i].tolist()}
            for i in range(len(col_counts)) if col_counts[i] != most_common_col_count
        ]

        sheet_analysis[sheet] = {
            "Expected Column Count": most_common_col_count,
            "Row Consistency": len(problematic_rows) == 0,
            "Problematic Rows": problematic_rows
        }

    return sheet_analysis

def analyze_file(file_path):
    """Determines file type and runs the appropriate analysis."""
    if file_path.endswith('.csv'):
        return analyze_csv(file_path)
    elif file_path.endswith(('.xls', '.xlsx')):
        return analyze_excel(file_path)
    else:
        return {"error": "Unsupported file format. Please use CSV or Excel files."}

@app.route('/')
def index():
    """Render Upload Page with Better UI."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file upload and runs analysis."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"})
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        result = analyze_file(file_path)
        return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)

