import json
import re
import ast
import traceback
import platform
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
import os
import subprocess
import jedi
import sys
import shutil

# Set up API Key
# os.environ["GOOGLE_API_KEY"] = "AIzaSyBvsCWfAhgNSPW8rQEu6187lwDbx7UGz8o"
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBvsCWfAhgNSPW8rQEu6187lwDbx7UGz8o")
if not GOOGLE_API_KEY:
    raise ValueError("Missing Google API Key")
genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    response = ""
    if request.method == "POST":
        prompt = request.form.get("prompt", "")
        if prompt:
            try:
                model = genai.GenerativeModel("gemini-1.5-pro-latest")
                response = model.generate_content(prompt).text
            except Exception as e:
                response = f"Error: {str(e)}"
    return render_template("index.html", response=response)

# @app.route('/autocomplete', methods=['POST'])
# def autocomplete():
#     data = request.json
#     code = data.get("code", "")
#     line, col = data.get("line", 0), data.get("col", 0)

#     try:
#         # Debugging Jedi autocompletion
#         print("Received code:", code)
#         print(f"Line: {line}, Column: {col}")

#         script = jedi.Script(code, line, col)
#         completions = script.complete()

#         completion_list = [comp.name for comp in completions]
#         print("Autocomplete suggestions:", completion_list)

#         return jsonify(completion_list)

#     except Exception as e:
#         print(f"Jedi error: {str(e)}")
#         return jsonify({"error": str(e)}), 500

@app.route('/autocomplete', methods=['POST'])
def autocomplete():
    data = request.json
    code = data.get("code", "")
    line = data.get("line", 1)
    col = data.get("col", 0)

    try:
        script = jedi.Script(code)  # Correct way to create a Jedi Script
        completions = script.complete(line, col)  # Call complete() properly
        return jsonify([comp.name for comp in completions])
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# 📌 Upload code file (Python, Java, C++, etc.)
@app.route("/upload_code", methods=["POST"])
def upload_code():
    if "code_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["code_file"]
    
    if file.filename == "":
        return jsonify({"error": "Empty file"}), 400
    
    try:
        file_content = file.read().decode("utf-8")  # Read and decode uploaded file
        return jsonify({"code": file_content})  # Send file content to frontend
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Function to extract errors from AI response

# def extract_errors(response_text):
#     try:
#         errors = json.loads(response_text)
#         if isinstance(errors, list):
#             return errors
#         return "No error in your code."
#     except json.JSONDecodeError:
#         return extract_errors_from_text(response_text)  # Fallback to text parsing

# def extract_errors(response_text):
#     """
#     Extracts errors from the AI model's response.
#     Assumes the response contains JSON-formatted error details.
#     """
#     try:
#         errors = json.loads(response_text)
#         return errors
#     except json.JSONDecodeError:
#         # If response is not valid JSON, return it as a plain message
#         return [{"error": response_text}]


def extract_errors(response_text):
    """ Extracts error messages and line numbers from the AI response. """
    errors = []
    
    # Regex to find error messages in the response
    error_pattern = r"(SyntaxError|IndentationError|TypeError|NameError|ValueError|IndexError|KeyError|AttributeError):\s*(.*)"
    line_pattern = r"line (\d+)"
    
    lines = response_text.split("\n")
    for line in lines:
        error_match = re.search(error_pattern, line)
        line_match = re.search(line_pattern, line)
        
        if error_match:
            error_type = error_match.group(1)
            error_message = error_match.group(2)
            line_number = line_match.group(1) if line_match else "Unknown"
            
            errors.append({
                "error_type": error_type,
                "message": error_message,
                "line": line_number
            })
    
    return errors

# def extract_errors(response_text):
#     """
#     Extracts errors from the AI model's response.
#     Assumes the response contains JSON-formatted error details.
#     """
#     try:
#         errors = json.loads(response_text)
#         return errors
#     except json.JSONDecodeError:
#         # If response is not valid JSON, return it as a plain message
#         return [{"error": response_text}]



# def extract_errors_from_text(response_text):
#     errors = []
#     lines = response_text.split("\n")
#     for line in lines:
#         parts = line.split(":")
#         if len(parts) >= 2:
#             error_type = parts[0].strip()
#             error_detail = ":".join(parts[1:]).strip()
#             errors.append({"error_type": error_type, "details": error_detail})
#         else:
#             # Handle cases where the error message has no colons
#             errors.append({"error_type": "UnknownError", "details": line})
#     return errors




def compile_c_code(file_path):
    if platform.system() == "Windows":
        return {"error": "C compilation is not supported on Windows without MinGW or WSL."}
    try:
        if not shutil.which("gcc"):
            return {"error": "GCC compiler not found. Install GCC to compile C programs."}
        
        result = subprocess.run(["gcc", file_path, "-o", "output"], capture_output=True, text=True)
        if result.returncode != 0:
            return {"error": result.stderr}
        return {"response": "Compilation Successful"}
    except Exception as e:
        return {"error": str(e)}


@app.route("/fix_bug", methods=["POST"])
def fix_bug():
    data = request.json
    user_code = data.get("code", "")

    if not user_code:
        return jsonify({"error": "No code provided"}), 400

    try:
        # Step 1: Check for Syntax Errors Using ast
        try:
            ast.parse(user_code)
        except SyntaxError as e:
            return jsonify({
                "errors": [
                    {
                        "error_type": "SyntaxError",
                        "message": e.msg,
                        "line": e.lineno
                    }
                ]
            })

        # # Step 2: Check for Runtime Errors
        # try:
        #     exec(user_code, {})  # Run user code safely (without access to sensitive modules)
        # except Exception as e:
        #     error_type = type(e).__name__
        #     tb = traceback.extract_tb(e.__traceback__)
        #     last_trace = tb[-1]  # Get the last error traceback (most relevant)
        #     return jsonify({
        #         "errors": [
        #             {
        #                 "error_type": error_type,
        #                 "message": str(e),
        #                 "line": last_trace.lineno
        #             }
        #         ]
        #     })
        
        # Step 3: Use Gemini API to Check for Logical Errors
        model = genai.GenerativeModel("gemini-1.5-pro-latest")

        prompt = f"""
        You are an AI code debugger.
        Analyze the given Python code for syntax, runtime, or logical errors.
        If there are errors, return a JSON list with:
        - error_type (e.g., SyntaxError, NameError, TypeError)
        - message (error description)
        - line (error line number)

        If no errors exist, return exactly this JSON: {{"No error"}}

        Code:
        ```python
        {user_code}
        ```
        """

        # prompt = f"""
        # You are an AI code debugger.
        # Analyze the given Python code and return:
        # - Syntax or logical errors with error type, line number, and explanation.
        # - If there are no errors, return "no_errors".

        # Code:
        # ```python
        # {user_code}
        # ```
        # """

        response = model.generate_content(prompt)

        if not response or not hasattr(response, "text") or not response.text.strip():
            return jsonify({"error": "Invalid response from the model"}), 500

        response_text = response.text.strip()

        # Check if the response indicates no errors
        if response_text.lower() == "no_errors":
            return jsonify({"response": "No errors"})

        # Attempt to extract errors from the response
        errors = extract_errors(response_text)

        # If errors were extracted, return them
        if errors:
            return jsonify({"errors": errors})

        # If no errors were extracted, assume the response is the corrected code
        return jsonify({
            "errors": errors,  # Send errors separately
            "message": "Bugs fixed successfully!",
            "original_code": user_code  # Preserve original code
        })


    except Exception as e:
        print(f"Error in fix_bug: {e}")
        return jsonify({
            "errors": errors,
            "original_code": user_code
        })
    


# 📌 Generate Code
@app.route("/generate_code", methods=["POST"])
def generate_code():
    prompt = request.form.get("code_prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(f"Write Python code for: {prompt}").text

    return jsonify({"response": response})


# 📌 Generate Unit Tests
@app.route("/generate_tests", methods=["POST"])
def generate_tests():
    prompt = request.form.get("test_prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(f"Generate unit tests for: {prompt}").text

    return jsonify({"response": response})


# 📌 Debugging (Separate from Bug Fixing)
@app.route("/debug_code", methods=["POST"])
def debug_code():
    prompt = request.form.get("debug_prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(f"Find and fix bugs in the following code:\n{prompt}").text

    return jsonify({"response": response})


# 📌 CI/CD Pipeline Generation
@app.route("/cicd_pipeline", methods=["POST"])
def cicd_pipeline():
    prompt = request.form.get("cicd_prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(f"Write a GitHub Actions workflow for: {prompt}").text

    return jsonify({"response": response})


@app.route('/api/run-code', methods=['POST'])
def run_code():
    try:
        data = request.json
        code = data.get('code', '')

        if not code.strip():
            return jsonify({'output': 'No code provided'}), 400

        print("Code received:", code)  # Debug print
        # python_cmd = "python" if platform.system() == "Windows" else "python3"

        # result = subprocess.run(
        #     ['python3', '-c', code],
        #     text=True,
        #     capture_output=True,
        #     timeout=5
        # )

        # result = subprocess.run(
        #     [python_cmd, "-c", code],
        #     text=True,
        #     capture_output=True,
        #     timeout=5
        # )

        result = subprocess.run(
            [sys.executable, "-c", code],
            text=True, 
            capture_output=True, 
            timeout=5
        )

        print("Result:", result.stdout, result.stderr)  # Debug print
        return jsonify({'output': result.stdout or result.stderr})

    except Exception as e:
        print("Error running code:", traceback.format_exc())  # Full error traceback
        return jsonify({'output': 'Internal server error'}), 500



if __name__ == "__main__":
    app.run(debug=True)