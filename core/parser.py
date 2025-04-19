import os
from lxml import etree
from pathlib import Path
from .models import (
    ProductData, ProductRevisionData, Occurrence, ProductView, RevisionRuleData,
    AssociatedAttachment, FormData, ExternalFileData, DataSetData, SiteData,
    PLMXMLGeneralData, PLMXMLTransferContextlData, ParsedPLMXMLData
)

# Define the main PLMXML namespace
PLMXML_NS = "http://www.plmxml.org/Schemas/PLMXMLSchema"
NS_MAP = {'plm': PLMXML_NS} # Namespace map for XPath or tag lookup if needed

def _strip_hash(ref: str) -> str:
    """Removes leading '#' from a reference string."""
    return ref[1:] if ref and ref.startswith('#') else ref

def _split_refs(refs_str: str | None) -> list[str]:
    """Splits a space-separated string of references and strips '#'."""
    if not refs_str:
        return []
    return [_strip_hash(ref) for ref in refs_str.split()]

class PLMXMLParser:
    """
    Parses a PLMXML file using lxml's iterparse for efficiency
    and builds a data structure representing the content.
    """
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.plmxml_directory = self.file_path.parent
        self.data = ParsedPLMXMLData(plmxml_directory=str(self.plmxml_directory))
        self._current_context = {} # To hold current parent elements during parsing

    def parse(self) -> ParsedPLMXMLData | None:
        """
        Parses the PLMXML file and returns the structured data.
        Returns None if a major parsing error occurs.
        """
        try:
            # Use iterparse to handle potentially large files efficiently
            context = etree.iterparse(
                str(self.file_path),
                events=('start', 'end'),
                # Remove tag filter - parse all elements and check namespace in the loop
                recover=True # Restore recover=True
            )
            print(f"Starting iterparse for {self.file_path}...") # Keep this basic print

            for event, elem in context:
                # Check if tag is valid before trying to get localname
                if elem.tag is None:
                    # print("Warning: Encountered element with None tag.") # Removed debug print
                    continue

                try:
                    qname = etree.QName(elem.tag)
                    tag_name = qname.localname # Get local tag name
                    tag_ns = qname.namespace
                except ValueError:
                    # print(f"Warning: Could not parse QName for tag '{elem.tag}'") # Removed debug print
                    continue

                if event == 'start':
                    # Pass tag_name AND tag_ns to the handler
                    self._handle_start_element(tag_name, tag_ns, elem.attrib)
                elif event == 'end':
                    self._handle_end_element(tag_name)
                    # Free memory after processing the element and its children
                    elem.clear()
                    # REMOVED custom memory cleanup loop - rely on elem.clear()


            # Once parsing is complete, build the hierarchy
            self._build_hierarchy_and_link_data()
            return self.data

        except etree.XMLSyntaxError as e:
            print(f"XML Syntax Error parsing {self.file_path}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during parsing {self.file_path}: {e}")
            return None

    # Update signature to accept tag_ns
    def _handle_start_element(self, tag_name: str, tag_ns: str | None, attrib: dict):
        """Handles the start of an XML element."""
        elem_id = attrib.get('id')

        # Only process elements within our target namespace
        if tag_ns != PLMXML_NS:
             return

        # --- Store elements in dictionaries ---
        if tag_name == 'PLMXML':
            schema_version = attrib.get('schemaVersion', 'unknown')
            info = PLMXMLGeneralData(
                id=schema_version,
                author=attrib.get('author'),
                date=attrib.get('date'),
                time=attrib.get('time')
            )
            self.data.generalInfo[schema_version] = info
            # Store the root element itself for potential later use if needed
            self._current_context['PLMXML'] = info

        elif tag_name == 'Header' and elem_id:
            context_info = PLMXMLTransferContextlData(
                id=elem_id,
                transferContext=attrib.get('transferContext')
            )
            self.data.transferContexts[elem_id] = context_info
            self._current_context['Header'] = context_info

        elif tag_name == 'Site' and elem_id:
            site = SiteData(
                id=elem_id,
                name=attrib.get('name'),
                siteId=attrib.get('siteId')
            )
            self.data.sites[elem_id] = site
            self._current_context['Site'] = site # Keep track if needed inside

        elif tag_name == 'ProductView' and elem_id:
            pv = ProductView(
                id=elem_id,
                ruleRefs=_split_refs(attrib.get('ruleRefs')),
                primaryOccurrenceRef=_strip_hash(attrib.get('primaryOccurrenceRef')),
                rootRefs=_split_refs(attrib.get('rootRefs'))
            )
            self.data.productViews.append(pv) # Append directly, hierarchy built later
            self._current_context['ProductView'] = pv

        elif tag_name == 'Occurrence' and elem_id: # Namespace already checked
            occ = Occurrence(
                id=elem_id,
                instancedRef=_strip_hash(attrib.get('instancedRef')),
                associatedAttachmentRefs=_split_refs(attrib.get('associatedAttachmentRefs')),
                occurrenceRefIDs=_split_refs(attrib.get('occurrenceRefs'))
            )
            self.data.occurrences[elem_id] = occ
            self._current_context['Occurrence'] = occ # Track current occurrence for UserData/UserValue

        elif tag_name == 'Product' and elem_id:
            prod = ProductData(
                id=elem_id,
                productId=attrib.get('productId'),
                name=attrib.get('name'),
                subType=attrib.get('subType')
            )
            self.data.products[elem_id] = prod
            self._current_context['Product'] = prod

        elif tag_name == 'ProductRevision' and elem_id: # Namespace already checked
            rev = ProductRevisionData(
                id=elem_id,
                name=attrib.get('name'),
                subType=attrib.get('subType'),
                revision=attrib.get('revision'),
                masterRef=_strip_hash(attrib.get('masterRef')),
                # Store associatedAttachmentRefs directly here if available in PLMXML
                # Note: Often AssociatedAttachment is a separate element referencing the revision,
                # so we might need to link them later or adjust based on actual PLMXML structure.
                # For now, initialize as empty, will be populated by <AssociatedDataSet> below.
                associatedAttachmentRefs=[] 
            )
            self.data.productRevisions[elem_id] = rev
            self._current_context['ProductRevision'] = rev

        elif tag_name == 'RevisionRule' and elem_id:
            rule = RevisionRuleData(
                id=elem_id,
                name=attrib.get('name')
            )
            self.data.revisionRules[elem_id] = rule

        elif tag_name == 'AssociatedAttachment' and elem_id:
            att = AssociatedAttachment(
                id=elem_id,
                attachmentRef=_strip_hash(attrib.get('attachmentRef')),
                role=attrib.get('role')
            )
            self.data.associatedAttachments[elem_id] = att

        elif tag_name == 'Form' and elem_id:
            form = FormData(
                id=elem_id,
                name=attrib.get('name'),
                subType=attrib.get('subType'),
                subClass=attrib.get('subClass')
            )
            self.data.forms[elem_id] = form
            self._current_context['Form'] = form

        elif tag_name == 'DataSet' and elem_id:
            ds = DataSetData(
                id=elem_id,
                name=attrib.get('name'),
                type=attrib.get('type'),
                version=attrib.get('version'),
                memberRefs=_split_refs(attrib.get('memberRefs'))
            )
            self.data.dataSets[elem_id] = ds
            self._current_context['DataSet'] = ds

        elif tag_name == 'ExternalFile' and elem_id:
            location_ref = attrib.get('locationRef')
            full_path = None
            if location_ref:
                # Resolve relative path - assumes PLMXML structure where files are relative to the XML
                try:
                    full_path = str(self.plmxml_directory.joinpath(location_ref).resolve())
                except Exception as path_e:
                    print(f"Warning: Could not resolve path for ExternalFile {elem_id}: {location_ref} - {path_e}")

            ef = ExternalFileData(
                id=elem_id,
                format=attrib.get('format'),
                locationRef=location_ref,
                fullPath=full_path
            )
            self.data.externalFiles[elem_id] = ef

        # --- Handle nested elements that modify context ---
        elif tag_name == 'UserData':
            # Check type to set context for UserValue parsing
            user_data_type = attrib.get('type')
            if user_data_type == "AttributesInContext":
                self._current_context['in_AttributesInContext'] = True
            # Add other UserData types if needed

        elif tag_name == 'UserValue':
            title = attrib.get('title')
            value = attrib.get('value')
            if not title or value is None: return # Skip if essential attributes missing

            # Update Occurrence if inside AttributesInContext
            if self._current_context.get('in_AttributesInContext') and 'Occurrence' in self._current_context:
                occ = self._current_context['Occurrence']
                if title == 'SequenceNumber':
                    occ.sequenceNumber = value
                elif title == 'Quantity':
                    occ.quantity = value
                else: # Store other attributes dynamically
                    occ.userAttributes[title] = value

            # Update ProductRevision
            elif 'ProductRevision' in self._current_context:
                rev = self._current_context['ProductRevision']
                if title == 'object_string':
                    rev.objectString = value
                elif title == 'last_mod_date':
                    rev.lastModDate = value
                else: # Store other attributes dynamically
                    rev.userAttributes[title] = value

            # Update Form
            elif 'Form' in self._current_context:
                form = self._current_context['Form']
                form.userAttributes[title] = value

        elif tag_name == 'AssociatedDataSet':
            # Link AssociatedAttachment ID to ProductRevision
            # This assumes <AssociatedDataSet> is a child of <ProductRevision>
            # An alternative structure is <AssociatedAttachment> elsewhere referencing the revision.
            # We will handle the linking primarily in the build hierarchy step for robustness.
            if 'ProductRevision' in self._current_context:
                 rev = self._current_context['ProductRevision']
                 # We don't store the dataset ref directly here anymore.
                 # Instead, we store the AssociatedAttachment element itself earlier,
                 # and link it during hierarchy build.
                 # If AssociatedDataSet is a direct child, we could store its ref:
                 # ds_ref = _strip_hash(attrib.get('dataSetRef'))
                 # if ds_ref:
                 #     # Need a way to link this specific AssociatedDataSet element if needed
                 #     pass # Logic adjusted in hierarchy building

        elif tag_name == 'ApplicationRef':
            version = attrib.get('version')
            label = attrib.get('label')

            # Add UID to ProductRevision (from version)
            if version and 'ProductRevision' in self._current_context:
                 self._current_context['ProductRevision'].revisionUid = version
            # Add UID to Product, DataSet, Form (from label)
            if label:
                if 'Product' in self._current_context:
                    self._current_context['Product'].uid = label
                elif 'DataSet' in self._current_context:
                    self._current_context['DataSet'].uid = label
                elif 'Form' in self._current_context:
                    self._current_context['Form'].uid = label


    def _handle_end_element(self, tag_name: str):
        """Handles the end of an XML element, cleaning up context."""
        # Remove the element from the current context stack
        if tag_name in self._current_context:
            # For simple cases, just remove. For nested structures, ensure correct popping.
            # This simple removal works if we don't rely on strict parent context beyond immediate need.
             if tag_name not in ['PLMXML']: # Don't remove the root context
                 del self._current_context[tag_name]

        # Reset specific context flags
        if tag_name == 'UserData':
            self._current_context.pop('in_AttributesInContext', None) # Remove flag if it exists


    def _build_hierarchy_and_link_data(self):
        """Builds the Occurrence tree and links related data after parsing."""
        print("Building BOM hierarchy...")
        for pv in self.data.productViews:
            root_ids = pv.rootRefs if pv.rootRefs else []
            if not root_ids and pv.primaryOccurrenceRef:
                 root_ids = [pv.primaryOccurrenceRef] # Fallback to primary if rootRefs missing

            root_occs = []
            for root_id in root_ids:
                if root_id in self.data.occurrences:
                    root_occurrence = self.data.occurrences[root_id]
                    built_root = self._build_sub_occurrences(root_occurrence)
                    root_occs.append(built_root)
                else:
                    print(f"Warning: Root occurrence ID '{root_id}' not found in parsed occurrences for ProductView '{pv.id}'.")
            pv.occurrences = root_occs
        print("BOM hierarchy build complete.")


    def _build_sub_occurrences(self, occurrence: Occurrence) -> Occurrence:
        """Recursively builds child occurrences and links data."""
        # Create a copy to avoid modifying the dictionary version directly during recursion
        # Although Occurrence is mutable, returning a potentially new/modified instance is cleaner
        new_occ = occurrence # Start with the occurrence from the dictionary

        # Link to ProductRevision and Product data
        if new_occ.instancedRef and new_occ.instancedRef in self.data.productRevisions:
            revision_data = self.data.productRevisions[new_occ.instancedRef]
            new_occ.displayName = revision_data.objectString or revision_data.name # Prefer objectString
            new_occ.name = revision_data.name
            new_occ.subType = revision_data.subType
            new_occ.revision = revision_data.revision
            new_occ.lastModDate = revision_data.lastModDate
            # new_occ.dataSetRefs = revision_data.dataSetRefs # Replaced by attachment_details population

            # Populate attachment_details using the Occurrence's associatedAttachmentRefs
            new_occ.attachment_details = []
            # Use occurrence.associatedAttachmentRefs which is parsed from the XML attribute
            for att_id in occurrence.associatedAttachmentRefs: 
                if att_id in self.data.associatedAttachments:
                    attachment = self.data.associatedAttachments[att_id]
                    # Check if the attachment points to a dataset
                    if attachment.attachmentRef and attachment.attachmentRef in self.data.dataSets:
                         detail = {
                             'role': attachment.role,
                             'dataSetId': attachment.attachmentRef
                         }
                         new_occ.attachment_details.append(detail)
                else:
                     print(f"Warning: AssociatedAttachment ID '{att_id}' referenced by ProductRevision '{revision_data.id}' not found.")


            # Link to Product via ProductRevision's masterRef
            if revision_data.masterRef and revision_data.masterRef in self.data.products:
                product_data = self.data.products[revision_data.masterRef]
                new_occ.productId = product_data.productId

        # Recursively build children
        children = []
        for child_id in new_occ.occurrenceRefIDs:
            if child_id in self.data.occurrences:
                 child_occ_template = self.data.occurrences[child_id]
                 built_child = self._build_sub_occurrences(child_occ_template)
                 children.append(built_child)
            else:
                print(f"Warning: Child occurrence ID '{child_id}' referenced by '{new_occ.id}' not found.")
        new_occ.subOccurrences = children

        return new_occ


# --- Main Parsing Function ---

def parse_plmxml(file_path: str) -> ParsedPLMXMLData | None:
    """
    High-level function to parse a PLMXML file.

    Args:
        file_path (str): Path to the PLMXML file.

    Returns:
        ParsedPLMXMLData: An object containing the parsed data, or None on failure.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return None

    parser = PLMXMLParser(file_path)
    parsed_data = parser.parse()
    return parsed_data

# --- Header Parsing Function (Kept for compatibility if needed elsewhere, but uses new parser) ---

def parse_plmxml_header(file_path: str) -> dict | None:
    """
    Parses *only* the PLMXML file header attributes using the full parser.
    Less efficient than the previous version if ONLY the header is needed,
    but reuses the main parsing logic.

    Args:
        file_path (str): The path to the PLMXML file.

    Returns:
        dict: A dictionary containing header attributes from the first
              PLMXMLGeneralData found, or None if parsing fails.
    """
    parsed_data = parse_plmxml(file_path)
    if parsed_data and parsed_data.generalInfo:
        # Return the attributes from the first general info object found
        first_general_info = next(iter(parsed_data.generalInfo.values()))
        return {
            'schemaVersion': first_general_info.id, # id holds schemaVersion here
            'author': first_general_info.author,
            'date': first_general_info.date,
            'time': first_general_info.time
        }
    elif parsed_data: # Parsed ok, but no header info found
         print(f"Warning: Parsed {file_path} but found no PLMXML header information.")
         return {} # Return empty dict as per original docstring intent
    else: # Parsing failed
        return None


if __name__ == '__main__':
    # Example usage for testing the full parser
    # Create a more complex dummy XML file for testing
    dummy_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<PLMXML xmlns="http://www.plmxml.org/Schemas/PLMXMLSchema" schemaVersion="6" author="Test User" date="2025-04-18" time="14:00:00">
    <Header id="h1" transferContext="TestCtx"/>
    <ProductView id="pv1" rootRefs="#occ1">
        <Occurrence id="occ1" instancedRef="#rev1">
            <UserData type="AttributesInContext">
                <UserValue title="SequenceNumber" value="10"/>
            </UserData>
        </Occurrence>
    </ProductView>
    <ProductRevision id="rev1" name="Part A Rev 1" revision="1" masterRef="#prodA">
         <UserData type="TC Specific Properties">
             <UserValue title="object_string" value="PartA-001 / A"/>
         </UserData>
    </ProductRevision>
    <Product id="prodA" name="Part A" productId="PartA-001"/>
</PLMXML>
"""
    dummy_file = "dummy_full_test.plmxml"
    with open(dummy_file, "w", encoding="utf-8") as f:
        f.write(dummy_xml_content)

    print(f"--- Testing Full Parser with {dummy_file} ---")
    parsed_result = parse_plmxml(dummy_file)

    if parsed_result:
        print("\nParsed General Info:")
        for key, info in parsed_result.generalInfo.items():
            print(f"  Schema {key}: Author={info.author}, Date={info.date}, Time={info.time}")

        print("\nParsed Products:")
        for key, prod in parsed_result.products.items():
            print(f"  ID {key}: Name={prod.name}, ProductID={prod.productId}")

        print("\nParsed Revisions:")
        for key, rev in parsed_result.productRevisions.items():
            print(f"  ID {key}: Name={rev.name}, Rev={rev.revision}, MasterRef={rev.masterRef}, ObjStr={rev.objectString}")

        print("\nParsed Occurrences (Flat):")
        for key, occ in parsed_result.occurrences.items():
            print(f"  ID {key}: InstRef={occ.instancedRef}, SeqNo={occ.sequenceNumber}")

        print("\nParsed Product Views (Hierarchical):")
        for pv in parsed_result.productViews:
            print(f"  ProductView ID: {pv.id}")
            for root_occ in pv.occurrences:
                 print(f"    Root Occ ID: {root_occ.id}, DisplayName: {root_occ.displayName}, SeqNo: {root_occ.sequenceNumber}")
                 # Add recursive printing if needed for deeper testing

        print("\n--- Testing Header Parser (using full parser) ---")
        header = parse_plmxml_header(dummy_file)
        if header is not None:
            print("Header Info:", header)
        else:
            print("Failed to parse header.")

    else:
        print("Full parsing failed.")

    # Clean up dummy file
    os.remove(dummy_file)
