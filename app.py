from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import google.generativeai as genai
from kaggle.api.kaggle_api_extended import KaggleApi
from huggingface_hub import list_datasets, HfApi, HfFolder
from datasets import load_dataset
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import streamlit as st
import pickle
import numpy as np



load_dotenv()

# Set API keys
os.environ['KAGGLE_USERNAME'] = os.getenv("KAGGLE_USERNAME")
os.environ['KAGGLE_KEY'] = os.getenv("KAGGLE_KEY")
os.environ['HF_TOKEN'] = os.getenv("HF_TOKEN")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Gemini model
model = genai.GenerativeModel('models/gemini-2.5-flash')


# Hugging Face login (REQUIRED to access private/full datasets)
from huggingface_hub import login
login(token=os.getenv("HF_TOKEN"))


# ✅ Flask App
app = Flask(__name__)
CORS(app)

# ✅ Scrape description from dataset page
def get_description(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.content, "html.parser")
    paras = soup.find_all("p")
    text = "\n".join(p.text for p in paras if len(p.text) > 40)
    return text.strip()[:3000]

# ✅ Search Kaggle datasets
def get_kaggle_datasets(keyword, count=10):
    api = KaggleApi()
    api.authenticate()
    datasets = api.dataset_list(search=keyword)
    datasets = datasets[:count]  # manually slice top N results

    return [{
        "title": ds.title,
        "url": f"https://www.kaggle.com/datasets/{ds.ref}",
        "source": "Kaggle"
    } for ds in datasets]
import tempfile

def load_kaggle_dataset_csv(dataset_ref):
    api = KaggleApi()
    api.authenticate()

    with tempfile.TemporaryDirectory() as tmpdir:
        api.dataset_download_files(dataset_ref, path=tmpdir, unzip=True)

        # Look for the first CSV file
        for filename in os.listdir(tmpdir):
            if filename.endswith(".csv"):
                filepath = os.path.join(tmpdir, filename)
                return pd.read_csv(filepath)

    return pd.DataFrame()

# ✅ Search Hugging Face datasets (authenticated)
def get_hf_datasets(keyword, limit=10):
    api = HfApi(token=os.environ["HF_TOKEN"])
    results = api.list_datasets(search=keyword, limit=limit)
    return [{
        "title": ds.id,
        "url": f"https://huggingface.co/datasets/{ds.id}",
        "source": "HuggingFace"
    } for ds in results]

# ✅ Generate summary + synthetic rows + merge original (for HF only)
def generate_csv_data(url, row_count):
    # ✅ Fetch description
    description = get_description(url)

    # ✅ Build Gemini prompt
    prompt = f"""
You are a helpful generative AI assistant.

The user selected this dataset:
{url}

Use the content of the page to understand it.


Generate {row_count} realistic synthetic rows in CSV format (no header).
"""

    # ✅ Send to Gemini
    chat = model.start_chat()
    response = chat.send_message(prompt)
    full_text = response.text.strip()

    # ✅ Extract synthetic CSV rows
    csv_lines = [line for line in full_text.split("\n") if "," in line][-row_count:]
    synthetic_df = pd.DataFrame([line.split(",") for line in csv_lines])

    # ✅ Load original dataset
    original_df = pd.DataFrame()

    if "huggingface.co/datasets/" in url:
        try:
            dataset_id = url.replace("https://huggingface.co/datasets/", "").strip("/")
            dataset = load_dataset(dataset_id, split="train")
            original_df = pd.DataFrame(dataset)
            if synthetic_df.shape[1] == original_df.shape[1]:
               synthetic_df.columns = original_df.columns
        except Exception as e:
            print("⚠️ Could not load Hugging Face dataset:", e)

    elif "kaggle.com/datasets/" in url:
        try:
            dataset_ref = url.replace("https://www.kaggle.com/datasets/", "").strip("/")
            original_df = load_kaggle_dataset_csv(dataset_ref)
            if synthetic_df.shape[1] == original_df.shape[1]:
                synthetic_df.columns = original_df.columns
        except Exception as e:
            print("⚠️ Could not load Kaggle dataset:", e)

    # original_df = pd.DataFrame()
    # if "huggingface.co/datasets/" in url:
    #     try:
    #         dataset_id = url.replace("https://huggingface.co/datasets/", "").strip("/")
    #         dataset = load_dataset(dataset_id, split="train")
    #         original_df = pd.DataFrame(dataset)

    #         # ✅ Match headers if shape matches
    #         if synthetic_df.shape[1] == original_df.shape[1]:
    #             synthetic_df.columns = original_df.columns
    #     except Exception as e:
    #         print("⚠️ Could not load original dataset:", e)

    # ✅ Merge original + synthetic
    if not original_df.empty:
        combined_df = pd.concat([original_df, synthetic_df], ignore_index=True)
    else:
        combined_df = synthetic_df  # fallback if no original

    # ✅ Convert to CSV string
    synthetic_csv = synthetic_df.to_csv(index=False)
    combined_csv = combined_df.to_csv(index=False)
    return {
    "synthetic_csv": synthetic_csv,
    "combined_csv": combined_csv
}


#     # ✅ Build Gemini prompt (only rows, no summary)
#     prompt = f"""
# You are a helpful generative AI assistant.

# The user selected this dataset:
# {url}

# Generate {row_count} realistic synthetic rows in CSV format (no header).
# """

#     # ✅ Send to Gemini
#     chat = model.start_chat()
#     response = chat.send_message(prompt)
#     text = response.text.strip()

#     # ✅ Extract synthetic CSV rows
#     csv_lines = [line for line in text.split("\n") if "," in line][-row_count:]
#     synthetic_df = pd.DataFrame([line.split(",") for line in csv_lines])

#     # ✅ Load original dataset (Hugging Face only)
#     original_df = pd.DataFrame()
#     if "huggingface.co/datasets/" in url:
#         try:
#             dataset_id = url.strip().split("/")[-1]
#             dataset = load_dataset(dataset_id, split="train")
#             original_df = pd.DataFrame(dataset)

#             # ✅ Match headers if shape matches
#             if synthetic_df.shape[1] == original_df.shape[1]:
#                 synthetic_df.columns = original_df.columns
#         except Exception as e:
#             print("⚠️ Could not load original dataset:", e)

#     # ✅ Merge original + synthetic
#     if not original_df.empty:
#         combined_df = pd.concat([original_df, synthetic_df], ignore_index=True)
#     else:
#         combined_df = synthetic_df  # fallback if no original

#     # ✅ Convert to CSV string
#     final_csv = combined_df.to_csv(index=False)

#     return final_csv  # 🚨 No summary returned now


def summarize_only(url):
    prompt = f"""
You are a helpful generative AI assistant.

The user selected this dataset:
{url}

Use the title and content of the page to understand it.

Summarize the dataset clearly for a data scientist.
Include the dataset link in your summary.
"""

    chat = model.start_chat()
    response = chat.send_message(prompt)
    summary = response.text.strip()
    return summary

# =========================
# ✅ ROUTES
# =========================

@app.route("/search", methods=["POST"])
def search():
    keyword = request.json.get("query")
    kaggle_results = get_kaggle_datasets(keyword)
    hf_results = get_hf_datasets(keyword)
    return jsonify({"results": kaggle_results + hf_results})

@app.route("/generate_rows_only", methods=["POST"])
def generate_rows_only():
    url = request.json.get("url")
    rows = int(request.json.get("rows"))
    csv_data = generate_csv_data(url, rows)
    return jsonify({
        "synthetic_csv": csv_data["synthetic_csv"],
        "combined_csv": csv_data["combined_csv"]
    })


@app.route("/summarize_only", methods=["POST"])
def summarize_only_route():
    url = request.json.get("url")
    summary = summarize_only(url)
    return jsonify({ "summary": summary })


# =========================
if __name__ == "__main__":
    app.run(debug=True)
