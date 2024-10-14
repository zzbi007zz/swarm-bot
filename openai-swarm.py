from swarm import Swarm, Agent
from flask import Flask, request, render_template_string, send_file
import PyPDF2
import io
import csv

app = Flask(__name__)
client = Swarm()

def create_test_cases(context_variables):
    ba_document = context_variables.get("ba_document", "")
    feedback = context_variables.get("feedback", "")
    return f"""Based on the BA document and any feedback provided, create detailed test cases:

BA Document:
{ba_document}

Feedback (if any):
{feedback}

Test Cases:
[Your detailed test cases here, following the format from the previous version]
"""

def review_test_cases(context_variables):
    ba_document = context_variables.get("ba_document", "")
    test_cases = context_variables.get("test_cases", "")
    review = f"""Review of test cases based on the BA document:

BA Document:
{ba_document}

Test Cases:
{test_cases}

Review:
1. Coverage: [Assess the comprehensiveness of test cases]
2. Detail: [Evaluate the level of detail in each test case]
3. Scenarios: [Comment on the variety of scenarios covered]
4. Requirements: [Check alignment with BA document requirements]
5. Edge Cases: [Identify any missing or well-covered edge cases]
6. Improvement Suggestions: [Provide specific areas for improvement]
7. Clarity: [Evaluate the clarity and ease of understanding of test cases]

Overall Assessment:
[Determine if test cases are acceptable or need rework]

Feedback for Rework (if needed):
[Provide specific feedback for the test case creator to address]
"""
    create_csv_file(test_cases, review)
    return review

def create_csv_file(test_cases, review):
    test_cases_list = test_cases.split('\n\n')[2:]  # Skip the first 2 paragraphs
    with open('test_cases.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Test Case ID', 'Test Case Description', 'Test Steps', 'Expected Result'])
        for i, test_case in enumerate(test_cases_list, start=1):
            if test_case.strip():
                lines = test_case.strip().split('\n')
                description = lines[0].strip()
                steps = "\n".join([line.strip() for line in lines if line.strip().startswith('-')])
                expected_result = "Not specified"
                for line in lines:
                    if line.strip().startswith('Expected Result:'):
                        expected_result = line.replace('Expected Result:', '').strip()
                        break
                writer.writerow([
                    f'TC_{i:03d}',
                    description,
                    steps,
                    expected_result
                ])

test_case_creator = Agent(
    name="Test Case Creator",
    instructions="Create detailed and comprehensive test cases based on the provided BA document and any feedback. Focus on covering all acceptance criteria, user flows, and potential edge cases.",
    functions=[create_test_cases],
)

test_case_reviewer = Agent(
    name="Test Case Reviewer",
    instructions="Review the test cases created by the Test Case Creator. Ensure they cover all acceptance criteria, are sufficiently detailed, and address potential edge cases. Provide specific feedback for improvements if needed.",
    functions=[review_test_cases],
)

def orchestrate_agents(ba_document):
    context_variables = {"ba_document": ba_document}
    max_iterations = 3
    
    for iteration in range(max_iterations):
        response = client.run(
            messages=[{"role": "user", "content": "Create detailed test cases based on the BA document and any previous feedback."}],
            agent=test_case_creator,
            context_variables=context_variables,
        )
        test_cases = response.messages[-1]["content"]

        context_variables["test_cases"] = test_cases
        response = client.run(
            messages=[{"role": "user", "content": "Review the test cases based on the BA document."}],
            agent=test_case_reviewer,
            context_variables=context_variables,
        )
        review = response.messages[-1]["content"]

        if "Feedback for Rework" not in review or iteration == max_iterations - 1:
            return test_cases, review
        else:
            context_variables["feedback"] = review

    return test_cases, review

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and file.filename.endswith('.pdf'):
            ba_document = extract_text_from_pdf(file)
            test_cases, review = orchestrate_agents(ba_document)
            return render_template_string('''
                <h2>Test Cases:</h2>
                <pre>{{ test_cases }}</pre>
                <h2>Review:</h2>
                <pre>{{ review }}</pre>
                <a href="/download" download>Download Test Cases CSV</a>
            ''', test_cases=test_cases, review=review)
    return '''
    <!doctype html>
    <title>Upload BA Document</title>
    <h1>Upload BA Document (PDF only)</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file accept=".pdf">
      <input type=submit value=Upload>
    </form>
    '''

@app.route('/download')
def download():
    return send_file('test_cases.csv', as_attachment=True, download_name='test_cases.csv', mimetype='text/csv')

if __name__ == '__main__':
    app.run(debug=True)
