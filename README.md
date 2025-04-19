# Python PLMXML Viewer

A simple desktop application for Windows to view the structure and data within PLMXML files, inspired by Krusty84/PLMXMLViewer for macOS.

## Features

*   Parses PLMXML files.
*   Displays the Bill of Materials (BOM) structure in a tree view.
*   Shows columns for Name/ID, Item Type, Revision, Quantity, Attributes (from UserData), and associated Datasets (including role, type, name, and file details).

## Requirements

*   Python 3.x
*   PySide6 (`pip install PySide6`)
*   lxml (`pip install lxml`)

## Setup and Running

1.  **Clone the repository (if applicable).**
2.  **Create and activate a virtual environment (Recommended):**
    ```bash
    cd PythonPLMXMLViewer
    python -m venv .venv
    .\ .venv\Scripts\activate 
    ```
3.  **Install dependencies:**
    ```bash
    pip install PySide6 lxml
    ```
4.  **Run the application:**
    ```bash
    python main.py
    ```
5.  Use the "File" -> "Open PLMXML..." menu to load a file.
