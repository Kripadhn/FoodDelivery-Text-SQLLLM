# SQLGenPro

Productivity Improvement tool for Product Managers, Business stakeholders and even intermediate-coders when it comes to working with data stored in a traditional SQL database.



## Prerequisites
Python 3.10 must be installed.
Ensure you have access to the required datasets and connection strings for databases.

### Virtual Environment Setup Instructions

#### For Mac and Linux:
Open a terminal and navigate to the project directory:

`cd /path/to/SQLGenPro`

Create a virtual environment using venv:


`python3 -m venv venv`


Activate the virtual environment:


`source venv/bin/activate`

Install the required dependencies from the requirements.txt file:


`pip install -r requirements.txt`

#### For Windows:
Open a command prompt and navigate to the project directory:

`cd \path\to\SQLGenPro`

Create a virtual environment using venv:

`python -m venv venv`


Activate the virtual environment:

`.\venv\Scripts\activate`

Install the required dependencies from the requirements.txt file:


`pip install -r requirements.txt`

#### Project Execution
Run the SQLGenPro application using Streamlit:


`streamlit run SQLGenPro.py`

Access the application:

After running the command, the app will open automatically in your default browser.
If not, navigate to the provided local URL (usually http://localhost:8501/) to access the SQLGenPro interface.


```
SQLGenPro

├─ .streamlit
│  └─ config.toml
├─ Langchain_Intro.ipynb
├─ README.md
├─ SQLGenPro.png
├─ SQLGenPro.py
├─ SQLGenPro_Live.py
├─ artifacts/
├─ authenticator.yml
├─ data/
├─ helper.ipynb
├─ requirements.txt
├─ src
│  ├─ add_logo.py
│  └─ utils.py
├─ test.sql
└─ utils.ipynb

```