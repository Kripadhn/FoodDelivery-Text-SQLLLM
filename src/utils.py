import os, sys 
import pandas as pd 
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import sqlparse
from collections import OrderedDict, Counter
from github import Github
from databricks import sql 
import streamlit_authenticator as stauth
import yaml 
from yaml.loader import SafeLoader
from dotenv import load_dotenv
load_dotenv()

# LLM libraries
from langchain_core.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.chains.llm import LLMChain
from langchain_openai import ChatOpenAI

# Function to load the user_query_history table
@st.cache_data
def load_user_query_history(user_name):
    # Getting the sample details of the selected table
    conn = sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                    http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                    access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN"))

    query = f"SELECT * FROM dev_tools.sqlgenpro_user_query_history WHERE user_name = '{user_name}' AND timestamp > current_date - 20"
    df = pd.read_sql(sql=query,con=conn)
    return df


# Function to list all the catalog, schema and tables present in the database 
@st.cache_data
def list_catalog_schema_tables():
    with sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                    http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                    access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN")) as connection:
        with connection.cursor() as cursor:
            # cursor.catalogs()
            # result_catalogs = cursor.fetchall()

            # cursor.schemas()
            # result_schemas = cursor.fetchall()

            cursor.tables()
            result_tables = cursor.fetchall()

            return result_tables
        

# Function to create enriched database schema details for the Prompt
@st.cache_data        
def get_enriched_database_schema(catalog,schema,tables_list):
    table_schema = ""

    # Iterating through each selected tables and get the list of columns for each table.
    for table in tables_list:

        conn = sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                        http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                        access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN"))        

        # Getting the Schema for the table
        query = f"SHOW CREATE TABLE `{catalog}`.{schema}.{table}"
        df = pd.read_sql(sql=query,con=conn)
        stmt = df['createtab_stmt'][0]
        stmt = stmt.split("USING")[0]

        # Filtering the String columns from the table to identify Categorical columns
        query = f"DESCRIBE TABLE `{catalog}`.{schema}.{table}"
        df = pd.read_sql(sql=query,con=conn)
        string_cols = df[df['data_type']=='string']['col_name'].values.tolist()

        sql_distinct = ""
        for col in string_cols:
            # Getting the distinct values for each column as rows
            if col == string_cols[-1]:
                sql_distinct += f"SELECT '{col}' AS column_name, COUNT(DISTINCT {col}) AS cnt, ARRAY_AGG(DISTINCT {col}) AS values FROM `{catalog}`.{schema}.{table}"
            else:
                sql_distinct += f"SELECT '{col}' AS column_name, COUNT(DISTINCT {col}) AS cnt, ARRAY_AGG(DISTINCT {col}) AS values FROM `{catalog}`.{schema}.{table} UNION ALL "

        # print(sql_distinct)
        df_categories = pd.read_sql(sql=sql_distinct,con=conn)
        df_categories = df_categories[df_categories['cnt'] <= 20]
        df_categories = df_categories.drop(columns='cnt')

        if df_categories.empty:
            df_categories_string = "No Categorical Fields"
        else:
            df_categories_string = df_categories.to_string(index=False)


        # Getting the sample rows from the table
        query = f"SELECT * FROM `{catalog}`.{schema}.{table} LIMIT 3"
        df = pd.read_sql(sql=query,con=conn)
        sample_rows = df.to_string(index=False)

        if table_schema == "":
            table_schema = stmt + "\n" + sample_rows + "\n\nCategorical Fields:\n" + df_categories_string + "\n"
        else:
            table_schema = table_schema + "\n" + stmt + "\n" + sample_rows + "\n\nCategorical Fields:\n" + df_categories_string + "\n"        
    
    return table_schema
        

# Function to render the mermaid diagram
def process_llm_response_for_mermaid(response: str) -> str:
    # Extract the Mermaid code block from the response
    start_idx = response.find("```mermaid") + len("```mermaid")
    end_idx = response.find("```", start_idx)
    mermaid_code = response[start_idx:end_idx].strip()

    return mermaid_code

# Function to render the sql code
def process_llm_response_for_sql(response: str) -> str:
    # Extract the Mermaid code block from the response
    start_idx = response.find("```sql") + len("```sql")
    end_idx = response.find("```", start_idx)
    sql_code = response[start_idx:end_idx].strip()

    return sql_code


def mermaid(code: str) -> None:
    # Escaping backslashes for special characters in the code
    code_escaped = code.replace("\\", "\\\\").replace("`", "\\`")
    
    # components.html(
    #     f"""
    #     <div id="mermaid-container" style="width: 100%; height: 100%; overflow: auto;">
    #         <pre class="mermaid">
    #             {code_escaped}
    #         </pre>
    #     </div>

    #     <script type="module">
    #         import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    #         mermaid.initialize({{ startOnLoad: true }});
    #     </script>
    #     """,
    #     height=800  # You can adjust the height as needed
    # )       
    components.html(
        f"""
        <div id="mermaid-container" style="width: 100%; height: 800px; overflow: auto;">
            <pre class="mermaid">
                {code_escaped}
            </pre>
        </div>

        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        """,
        height=800  # You can adjust the height as needed
    )

# Function to create the ERD diagram for the selected schema and tables 
@st.experimental_fragment      
@st.cache_data 
def create_erd_diagram(catalog,schema,tables_list):

    table_schema = {}

    # Iterating through each selected tables and get the list of columns for each table.
    for table in tables_list:

        conn = sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                        http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                        access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN"))
            
        query = f"DESCRIBE TABLE `{catalog}`.{schema}.{table}"
        df = pd.read_sql(sql=query,con=conn)
        cols = df['col_name'].tolist()
        col_types = df['data_type'].tolist()
        cols_dict = [f"{col} : {col_type}" for col,col_type in zip(cols,col_types)]
        table_schema[table] = cols_dict

    # Generating the mermaid code for the ERD diagram
    ### Defining the prompt template
    template_string = """ 
    You are an expert in creating ERD diagrams (Entity Relationship Diagrams) for databases. 
    You have been given the task to create an ERD diagram for the selected tables in the database. 
    The ERD diagram should contain the tables and the columns present in the tables. 
    You need to generate the Mermaid code for the complete ERD diagram.
    Make sure the ERD diagram is clear and easy to understand with proper relationships details.

    The selected tables in the database are given below (delimited by ##) in the dictionary format: Keys being the table names and values being the list of columns and their datatype in the table.

    ##
    {table_schema}
    ##

    Before generating the mermaid code, validate it and make sure it is correct and clear.     
    Give me the final mermaid code for the ERD diagram after proper analysis.
    """

    prompt_template = PromptTemplate.from_template(template_string)

    ### Defining the LLM chain
    llm_chain = LLMChain(
        llm=ChatOpenAI(model="gpt-4o-mini",temperature=0),
        prompt=prompt_template
    )

    response =  llm_chain.invoke({"table_schema":table_schema})
    output = response['text']    
    return output

# Function to create Quick Analysis questions based on the given schema and tables
@st.experimental_fragment
@st.cache_data
def quick_analysis(table_schema):

    ### Defining the output schema from the LLM        
    output_schema = ResponseSchema(name="quick_analysis_questions",description="Generated Quick Analysis questions for the given tables list")
    output_parser = StructuredOutputParser.from_response_schemas([output_schema])
    format_instructions = output_parser.get_format_instructions()

    ### Defining the prompt template
    template_string = """
    Using the provided SCHEMA (delimited by ##), generate the top 5 "quick analysis" questions based on the relationships between the tables which can be answered by creating a Databricks SQL code. 
    These questions should be practical and insightful, targeting the kind of business inquiries a product manager or analyst would typically investigate daily.    

    SCHEMA:
    ##
    {table_schema}
    ##

    The output should be in a nested JSON format with the following structure:
    {fomat_instructions}
     """
    
    prompt_template = PromptTemplate.from_template(template_string)
    
    ### Defining the LLM chain
    llm_chain = LLMChain(
        llm=ChatOpenAI(model="gpt-4o-mini",temperature=0),
        prompt=prompt_template,
        output_parser=output_parser
    )

    response =  llm_chain.invoke({"table_schema":table_schema,"fomat_instructions":format_instructions})
    # output = response['text']  

    return response

# Function to create SQL code for the selected question and return the data from the database
@st.experimental_fragment
@st.cache_data
def create_sql(question,table_schema):

    ### Defining the prompt template
    template_string = """ 
    You are a expert data engineer working with a Databricks environment.\
    Your task is to generate a working SQL query in Databricks SQL dialect. \
    During join if column name are same please use alias ex llm.customer_id \
    in select statement. It is also important to respect the type of columns: \
    if a column is string, the value should be enclosed in quotes. \
    If you are writing CTEs then include all the required columns. \
    While concatenating a non string column, make sure cast the column to string. \
    For date columns comparing to string , please cast the string input.\
    For string columns, check if it is a categorical column and only use the appropriate values provided in the schema.\

    SCHEMA:
    ## {table_schema} ##

    QUESTION:
    ##
    {question}
    ##


    IMPORTANT: MAKE SURE THE OUTPUT IS JUST THE SQL CODE AND NOTHING ELSE. Ensure the appropriate CATALOG is used in the query and SCHEMA is specified when reading the tables.
    ##

    OUTPUT:
    """
    prompt_template = PromptTemplate.from_template(template_string)

    ### Defining the LLM chain
    llm_chain = LLMChain(
        llm=ChatOpenAI(model="gpt-4o-mini",temperature=0),
        prompt=prompt_template
    )

    response =  llm_chain.invoke({"question":question,"table_schema":table_schema})
    output = response['text']

    return output


# Function to create SQL code for the selected question and return the data from the database
@st.experimental_fragment
@st.cache_data
def create_advanced_sql(question,sql_code,table_schema):

    ### Defining the prompt template
    template_string = """ 
    You are a expert data engineer working with a Databricks environment.\
    Your task is to generate a working SQL query in Databricks SQL dialect. \
    Enclose the complete SQL_CODE in a WITH clause and name it as MASTER. DON'T ALTER THE given SQL_CODE. \
    Then based on the QUESTION and the master WITH clause, generate the final SQL query based on the WITH clause.\
    ONLY IF additional information is needed to answer the QUESTION, then use the SCHEMA to join the details to get the final answer. \


    INPUT:
    SQL_CODE:
    ##
    {sql_code}
    ##

    SCHEMA:
    ## {table_schema} ##

    QUESTION:
    ##
    {question}
    ##

    IMPORTANT: MAKE SURE THE OUTPUT IS JUST THE SQL CODE AND NOTHING ELSE.
    ##


    OUTPUT:
    """
    prompt_template = PromptTemplate.from_template(template_string)

    ### Defining the LLM chain
    llm_chain = LLMChain(
        llm=ChatOpenAI(model="gpt-4o-mini",temperature=0),
        prompt=prompt_template
    )

    response =  llm_chain.invoke({"sql_code":sql_code,"question":question,"table_schema":table_schema})
    output = response['text']

    return output



# Function to load data from the database given the SQL query
@st.experimental_fragment
@st.cache_data
def load_data_from_query(query):
    # Getting the sample details of the selected table
    conn = sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                    http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                    access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN"))

    # query = query.replace(";","")
    # query = query + f" LIMIT 1000;"
    df = pd.read_sql(sql=query,con=conn)
    return df         

# Function to validate if self-correction is needed for the generated SQL query
@st.experimental_fragment
def self_correction(query):
    error_msg = ""

    try:
        df = load_data_from_query(query)
        # print(df.shape)
        # df.head()
        error_msg += "Successful"
    except Exception as e:
        error_msg += str(e)
    
    if error_msg == "Successful":
        return error_msg
    else:
        # print("There is error")
        # print(error_msg)
        return error_msg

# Function to validate and self-correct generated SQL query    
@st.experimental_fragment
def correct_sql(question,sql_code,table_schema,error_msg):

    ### Defining the prompt template
    template_string = """ 
    You are a expert data engineer working with a Databricks environment.\
    Your task is to modify the SQL_CODE using Databricks SQL dialect based on the QUESTION, SCHEMA and the ERROR_MESSAGE. \
    If ERROR_MESSAGE is provided, then make sure to correct the SQL query according to that. \

    SCHEMA:
    ## {table_schema} ##

    ERROR_MESSAGE:
    ## {error_msg} ##

    SQL_CODE:
    ##
    {sql_code}

    QUESTION:
    ## {question} ##

    ##


    IMPORTANT: MAKE SURE THE OUTPUT IS JUST THE SQL CODE AND NOTHING ELSE. Ensure the appropriate CATALOG is used in the query and SCHEMA is specified when reading the tables.
    ##

    OUTPUT:
    """
    prompt_template = PromptTemplate.from_template(template_string)

    ### Defining the LLM chain
    llm_chain = LLMChain(
        llm=ChatOpenAI(model="gpt-4o-mini",temperature=0),
        prompt=prompt_template
    )

    response =  llm_chain.invoke({"question":question,"sql_code":sql_code,"table_schema":table_schema,"error_msg":error_msg})
    output = response['text']

    return output

# Final function to validate and self-correct
def validate_and_correct_sql(question,query,table_schema):
    error_msg = self_correction(query)

    if error_msg == "Successful":
        # print("Query is successful")
        return "Correct",query
    else:
        modified_query = correct_sql(question,query,table_schema,error_msg=error_msg)
        return "Incorrect",modified_query
    

# Add the selected question to the user history
@st.experimental_fragment
def add_to_user_history(user_name,question,query,favourite_ind):
    conn = sql.connect(server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME"),
                    http_path       = os.getenv("DATABRICKS_HTTP_PATH"),
                    access_token    = os.getenv("DATABRICKS_ACCESS_TOKEN"))
    
    user_history_table = "hive_metastore.dev_tools.sqlgenpro_user_query_history"

    query = f"""INSERT INTO {user_history_table} VALUES ('{user_name}',current_timestamp(),'{question}',"{query}",{favourite_ind})"""
    # query = f"SELECT * FROM {user_history_table}"
    df = pd.read_sql(sql=query,con=conn)