import sys
import os
from json_to_dataframe import read_json, json_to_dataframe
from dataframe_to_pdf import dataframe_to_pdf

def convert_sbom_to_pdf(json_path, pdf_path):
    json_data = read_json(json_path)
    df = json_to_dataframe(json_data)
    dataframe_to_pdf(json_data, df, pdf_path, json_path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <path_to_json_file>")
        sys.exit(1)

    json_path = sys.argv[1]
    pdf_path = os.path.splitext(json_path)[0] + ".pdf"
    convert_sbom_to_pdf(json_path, pdf_path)