import sys
import argparse
import csv
import os # Added for file existence check in CLI

# Conditional imports for PySide6 for GUI mode
# We'll define a function for GUI launch to keep CLI logic cleaner.
# from PySide6.QtWidgets import QApplication
# from ui.main_window import MainWindow

# Imports for CLI mode
from core.parser import parse_plmxml
from core.models import Occurrence, ParsedPLMXMLData # Ensure these are imported for type hinting and usage

def _write_csv_recursive_cli(writer: csv.writer, occurrence: Occurrence, level: int, parsed_data_for_lookup: ParsedPLMXMLData):
    """
    Recursively writes occurrence data to the CSV writer for CLI mode.
    This function is similar to _write_csv_recursive in MainWindow.
    """
    node_type = "Assembly" if occurrence.subOccurrences else "Leaf"
    name = occurrence.displayName or occurrence.name or occurrence.id or 'Occurrence'
    item_type_val = occurrence.subType or "N/A" # Renamed to avoid conflict with 'type' keyword
    revision = occurrence.revision or "N/A"
    quantity = occurrence.quantity or "1"
    attributes = "; ".join(f"{k}={v}" for k, v in occurrence.userAttributes.items())

    dataset_details_list = []
    if parsed_data_for_lookup: # Check if parsed_data_for_lookup exists
        for attach_detail in occurrence.attachment_details:
            role = attach_detail.get('role', 'N/A')
            ds_id = attach_detail.get('dataSetId')
            if ds_id and ds_id in parsed_data_for_lookup.dataSets:
                dataset = parsed_data_for_lookup.dataSets[ds_id]
                ds_type = dataset.type or 'N/A'
                ds_name = dataset.name or ds_id # Fallback to ID if name missing
                
                file_info_parts = []
                for member_ref in dataset.memberRefs:
                    if member_ref in parsed_data_for_lookup.externalFiles:
                        ext_file = parsed_data_for_lookup.externalFiles[member_ref]
                        file_loc = ext_file.locationRef or 'N/A'
                        file_fmt = ext_file.format or 'N/A'
                        file_info_parts.append(f"{file_loc} ({file_fmt})")
                    else:
                        file_info_parts.append(f"Ref: {member_ref} (Not Found)")
                
                file_info_str = "; ".join(file_info_parts) if file_info_parts else "No Files"
                dataset_details_list.append(f"Role: {role}, Type: {ds_type}, Name: {ds_name}, Files: [{file_info_str}]")
            else:
                 dataset_details_list.append(f"Role: {role}, DataSet ID: {ds_id} (Not Found)")

    datasets_str = " | ".join(dataset_details_list) if dataset_details_list else ""

    writer.writerow([
        level,
        node_type,
        name,
        item_type_val,
        revision,
        quantity,
        attributes,
        datasets_str
    ])

    for child_occ in occurrence.subOccurrences:
        _write_csv_recursive_cli(writer, child_occ, level + 1, parsed_data_for_lookup)

def run_cli_export(input_xml_path: str, output_csv_path: str):
    """
    Parses the input PLMXML file and exports its structure to the output CSV file.
    """
    print(f"Command-Line Mode: Processing input file '{input_xml_path}'...")

    if not os.path.exists(input_xml_path):
        print(f"Error: Input file not found: {input_xml_path}")
        sys.exit(1)

    parsed_data = parse_plmxml(input_xml_path)

    if not parsed_data:
        print(f"Error: Could not parse PLMXML file: {input_xml_path}. See parser logs for details.")
        sys.exit(1)

    if not parsed_data.productViews:
        print("No ProductView (BOM) data found in the PLMXML file.")
        # Decide if this is an error or just an empty output case
        # For now, create an empty CSV with headers
        try:
            with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                header = ["Level", "Type", "Name / ID", "Item Type", "Revision", "Qty", "Attributes", "Datasets"]
                writer.writerow(header)
            print(f"No BOM data found. Empty CSV with headers written to '{output_csv_path}'.")
            sys.exit(0)
        except Exception as e:
            print(f"An error occurred while writing empty CSV: {e}")
            sys.exit(1)

    print(f"Parsing successful. Exporting BOM structure to '{output_csv_path}'...")
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # CSV Header
            header = ["Level", "Type", "Name / ID", "Item Type", "Revision", "Qty", "Attributes", "Datasets"]
            writer.writerow(header)

            # For simplicity, process the first ProductView's BOM
            # (similar to how the GUI currently operates)
            first_product_view = parsed_data.productViews[0]
            for root_occurrence in first_product_view.occurrences:
                _write_csv_recursive_cli(writer, root_occurrence, 0, parsed_data)
        
        print(f"Successfully exported BOM structure to '{output_csv_path}'.")
        sys.exit(0)

    except Exception as e:
        print(f"An error occurred during CSV export: {e}")
        sys.exit(1)

def launch_gui():
    """Launches the PySide6 GUI application."""
    # Import GUI components here to avoid importing them if not needed
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    print("Launching GUI Mode...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PLMXML Viewer and Exporter.")
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Path to the input PLMXML (.xml) file for CLI export."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to the output CSV (.csv) file for CLI export."
    )

    args = parser.parse_args()

    if args.input and args.output:
        # Both input and output are provided, run in CLI mode
        run_cli_export(args.input, args.output)
    elif args.input or args.output:
        # Only one of the arguments is provided, which is an error for CLI mode
        print("Error: For command-line export, both --input and --output arguments are required.")
        print("To run in GUI mode, provide no arguments.")
        parser.print_help()
        sys.exit(1)
    else:
        # No arguments (or incomplete CLI arguments), launch GUI
        launch_gui()