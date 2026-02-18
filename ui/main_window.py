import sys
import csv
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTreeView, QFileDialog, QMessageBox,
    QHeaderView # Import QHeaderView
)
from PySide6.QtGui import QAction, QKeySequence, QStandardItemModel, QStandardItem
from PySide6.QtCore import Slot, Qt

# Import the full parser and models
from core.parser import parse_plmxml
from core.models import Occurrence, ParsedPLMXMLData # Import Occurrence for type hinting

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLMXML Viewer for Windows")
        self.setGeometry(100, 100, 800, 600) # Increased default size

        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- Tree View for BOM ---
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        # Define column headers (add "Item Type")
        self.column_headers = ["Name / ID", "Item Type", "Revision", "Qty", "Attributes", "Datasets"]
        self.tree_model.setHorizontalHeaderLabels(self.column_headers)
        self.tree_view.setModel(self.tree_model)
        # Allow interactive resizing
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Ensure scroll bars appear when needed
        self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tree_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Prevent last column stretching to ensure horizontal scrollbar appears correctly
        self.tree_view.header().setStretchLastSection(False)
        layout.addWidget(self.tree_view)

        self.parsed_data: ParsedPLMXMLData | None = None # Store parsed data

        # --- Menu Bar ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        # --- Open Action ---
        open_action = QAction("&Open PLMXML...", self)
        open_action.setShortcut(QKeySequence.Open) # Standard Ctrl+O shortcut
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        # --- Export CSV Action ---
        export_action = QAction("&Export to CSV...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_to_csv)
        file_menu.addAction(export_action)

        file_menu.addSeparator() # Add a separator

        # --- Exit Action ---
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q")) # Ctrl+Q shortcut
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    @Slot()
    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PLMXML File",
            "", # Start directory (empty means default/last used)
            "PLMXML Files (*.plmxml *.xml);;All Files (*)"
        )
        if file_path:
            self.load_plmxml(file_path)

    @Slot()
    def export_to_csv(self):
        """Exports the current BOM structure to a CSV file."""
        if not self.parsed_data or not self.parsed_data.productViews:
            QMessageBox.warning(self, "No Data", "No PLMXML data loaded to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export BOM to CSV",
            "", # Start directory
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return # User cancelled

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header including Level and Type
                header = ["Level", "Type", "Name / ID", "Item Type", "Revision", "Qty", "Attributes", "Datasets"]
                writer.writerow(header)

                # Write data for the first product view (or allow selection in a future version)
                first_product_view = self.parsed_data.productViews[0]
                for root_occ in first_product_view.occurrences:
                    self._write_csv_recursive(writer, root_occ, 0)

            self.statusBar().showMessage(f"Successfully exported BOM to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred while exporting to CSV:\n{e}")


    def _write_csv_recursive(self, writer, occurrence: Occurrence, level: int):
        """Recursively writes occurrence data and its children to the CSV writer."""

        # Determine Type (Assembly or Leaf)
        node_type = "Assembly" if occurrence.subOccurrences else "Leaf"

        # Prepare data (similar to _populate_tree)
        name = occurrence.displayName or occurrence.name or occurrence.id or 'Occurrence'
        item_type = occurrence.subType or "N/A"
        revision = occurrence.revision or "N/A"
        quantity = occurrence.quantity or "1"
        attributes = "; ".join(f"{k}={v}" for k, v in occurrence.userAttributes.items())

        # Format dataset info
        dataset_details_list = []
        if self.parsed_data:
            for attach_detail in occurrence.attachment_details:
                role = attach_detail.get('role', 'N/A')
                ds_id = attach_detail.get('dataSetId')
                if ds_id and ds_id in self.parsed_data.dataSets:
                    dataset = self.parsed_data.dataSets[ds_id]
                    ds_type = dataset.type or 'N/A'
                    ds_name = dataset.name or ds_id
                    file_info_parts = []
                    for member_ref in dataset.memberRefs:
                        if member_ref in self.parsed_data.externalFiles:
                            ext_file = self.parsed_data.externalFiles[member_ref]
                            file_loc = ext_file.locationRef or 'N/A'
                            file_fmt = ext_file.format or 'N/A'
                            file_info_parts.append(f"{file_loc} ({file_fmt})")
                        else:
                            file_info_parts.append(f"Ref: {member_ref} (Not Found)")
                    file_info_str = "; ".join(file_info_parts) if file_info_parts else "No Files"
                    dataset_details_list.append(f"Role: {role}, Type: {ds_type}, Name: {ds_name}, Files: [{file_info_str}]")
                else:
                     dataset_details_list.append(f"Role: {role}, DataSet ID: {ds_id} (Not Found)")
        datasets = " | ".join(dataset_details_list) if dataset_details_list else ""

        # Write the row with Level and Type first
        writer.writerow([
            level,
            node_type,
            name,
            item_type,
            revision,
            quantity,
            attributes,
            datasets
        ])

        # Recurse for children
        for child in occurrence.subOccurrences:
            self._write_csv_recursive(writer, child, level + 1)


    def load_plmxml(self, file_path):
        """Loads and parses the PLMXML file, then populates the tree view."""
        self.reset_tree() # Clear previous data
        try:
            self.parsed_data = parse_plmxml(file_path) # Store parsed data
            if self.parsed_data and self.parsed_data.productViews:
                # For simplicity, display the first ProductView's BOM
                first_product_view = self.parsed_data.productViews[0]
                self._populate_tree(self.tree_model.invisibleRootItem(), first_product_view.occurrences)
                self.tree_view.expandAll() # Expand the tree initially
                # Optionally display header info in status bar or title
                if self.parsed_data.generalInfo:
                    header = next(iter(self.parsed_data.generalInfo.values()))
                    self.statusBar().showMessage(f"Loaded: {file_path} | Author: {header.author} | Date: {header.date}")
                else:
                     self.statusBar().showMessage(f"Loaded: {file_path}")

            elif self.parsed_data: # Parsed ok, but no product views found
                 QMessageBox.information(self, "No BOM Data", "PLMXML file parsed, but no ProductView/BOM data found.")
            else: # Parsing failed (error message handled in parser)
                 QMessageBox.warning(self, "Parsing Error", f"Could not parse the PLMXML file: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"An unexpected error occurred:\n{e}")
            self.reset_tree()

    def _populate_tree(self, parent_item: QStandardItem, occurrences: list[Occurrence]):
        """Recursively populates the QStandardItemModel with Occurrence data across columns."""
        for occ in occurrences:
            # Create items for each column
            name_item = QStandardItem(occ.displayName or occ.name or occ.id or 'Occurrence')
            type_item = QStandardItem(occ.subType or "N/A") # Add Item Type item
            rev_item = QStandardItem(occ.revision or "N/A")
            qty_item = QStandardItem(occ.quantity or "1") # Default quantity to 1 if not specified

            # Format attributes dictionary into a string
            attr_str = "; ".join(f"{k}={v}" for k, v in occ.userAttributes.items())
            attr_item = QStandardItem(attr_str)

            # --- Format detailed dataset info ---
            dataset_details_list = []
            if self.parsed_data: # Check if parsed_data exists
                for attach_detail in occ.attachment_details:
                    role = attach_detail.get('role', 'N/A')
                    ds_id = attach_detail.get('dataSetId')
                    if ds_id and ds_id in self.parsed_data.dataSets:
                        dataset = self.parsed_data.dataSets[ds_id]
                        ds_type = dataset.type or 'N/A'
                        ds_name = dataset.name or ds_id # Fallback to ID if name missing

                        file_info_parts = []
                        for member_ref in dataset.memberRefs:
                            if member_ref in self.parsed_data.externalFiles:
                                ext_file = self.parsed_data.externalFiles[member_ref]
                                file_loc = ext_file.locationRef or 'N/A'
                                file_fmt = ext_file.format or 'N/A'
                                file_info_parts.append(f"{file_loc} ({file_fmt})")
                            else:
                                file_info_parts.append(f"Ref: {member_ref} (Not Found)")

                        file_info_str = "; ".join(file_info_parts) if file_info_parts else "No Files"
                        dataset_details_list.append(f"Role: {role}, Type: {ds_type}, Name: {ds_name}, Files: [{file_info_str}]")
                    else:
                         dataset_details_list.append(f"Role: {role}, DataSet ID: {ds_id} (Not Found)")

            dataset_str = " | ".join(dataset_details_list) if dataset_details_list else ""
            dataset_item = QStandardItem(dataset_str)
            # --- End Format detailed dataset info ---


            # Make items non-editable but selectable and enabled
            # Add type_item to the list
            for item in [name_item, type_item, rev_item, qty_item, attr_item, dataset_item]:
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                # Store the occurrence object on the first item for potential future use
                if item == name_item:
                     item.setData(occ, Qt.ItemDataRole.UserRole + 1)

            # Append the row of items (add type_item)
            parent_item.appendRow([name_item, type_item, rev_item, qty_item, attr_item, dataset_item])

            # Recursively populate children
            if occ.subOccurrences:
                self._populate_tree(name_item, occ.subOccurrences) # Children are added to the first column's item

    def reset_tree(self):
        """Clears the tree model, resets headers and stored data."""
        self.tree_model.clear()
        self.parsed_data = None # Clear stored data
        # Reapply headers after clearing
        self.tree_model.setHorizontalHeaderLabels(self.column_headers)
        self.statusBar().clearMessage()

if __name__ == '__main__':
    # For testing the window directly
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())