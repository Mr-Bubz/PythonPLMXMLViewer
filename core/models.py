from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Using dataclasses for simplicity and clarity

@dataclass
class ProductData:
    id: str
    productId: Optional[str] = None
    name: Optional[str] = None
    subType: Optional[str] = None
    uid: Optional[str] = None # From ApplicationRef label
    # Add other attributes as needed

@dataclass
class ProductRevisionData:
    id: str
    name: Optional[str] = None
    subType: Optional[str] = None
    revision: Optional[str] = None
    masterRef: Optional[str] = None # Reference to ProductData id
    objectString: Optional[str] = None # From UserValue
    lastModDate: Optional[str] = None # From UserValue
    # dataSetRefs: List[str] = field(default_factory=list) # References to DataSetData ids - Replaced by attachment info
    associatedAttachmentRefs: List[str] = field(default_factory=list) # Store refs to AssociatedAttachment elements
    revisionUid: Optional[str] = None # From ApplicationRef version
    userAttributes: Dict[str, str] = field(default_factory=dict)
    # Add other attributes as needed

@dataclass
class Occurrence:
    id: str
    instancedRef: Optional[str] = None # Reference to ProductRevisionData id
    associatedAttachmentRefs: List[str] = field(default_factory=list)
    occurrenceRefIDs: List[str] = field(default_factory=list) # Child occurrence IDs
    sequenceNumber: Optional[str] = None # From UserValue
    quantity: Optional[str] = None # From UserValue
    userAttributes: Dict[str, str] = field(default_factory=dict) # Other UserValues

    # Fields populated during hierarchy build
    displayName: Optional[str] = None
    name: Optional[str] = None
    subType: Optional[str] = None
    revision: Optional[str] = None
    lastModDate: Optional[str] = None
    productId: Optional[str] = None # From linked ProductData
    # dataSetRefs: List[str] = field(default_factory=list) # Replaced by attachment_details
    attachment_details: List[Dict[str, Optional[str]]] = field(default_factory=list) # Stores {'role': role, 'dataSetId': id}
    subOccurrences: List['Occurrence'] = field(default_factory=list) # Child Occurrence objects

    # Allow comparison based on id for potential use in sets/dicts
    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Occurrence):
            return NotImplemented
        return self.id == other.id

@dataclass
class ProductView:
    id: str
    ruleRefs: Optional[List[str]] = None
    primaryOccurrenceRef: Optional[str] = None
    rootRefs: Optional[List[str]] = None
    occurrences: List[Occurrence] = field(default_factory=list) # Root occurrences after build

@dataclass
class RevisionRuleData:
    id: str
    name: Optional[str] = None

@dataclass
class AssociatedAttachment:
    id: str
    attachmentRef: Optional[str] = None # Reference to Form or DataSet id
    role: Optional[str] = None

@dataclass
class FormData:
    id: str
    name: Optional[str] = None
    subType: Optional[str] = None
    subClass: Optional[str] = None
    uid: Optional[str] = None # From ApplicationRef label
    userAttributes: Dict[str, str] = field(default_factory=dict)

@dataclass
class ExternalFileData:
    id: str
    format: Optional[str] = None
    locationRef: Optional[str] = None # Relative path within PLMXML package
    fullPath: Optional[str] = None # Calculated absolute path

@dataclass
class DataSetData:
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    version: Optional[str] = None
    memberRefs: List[str] = field(default_factory=list) # References to ExternalFileData ids
    uid: Optional[str] = None # From ApplicationRef label

@dataclass
class SiteData:
    id: str
    name: Optional[str] = None
    siteId: Optional[str] = None

@dataclass
class PLMXMLGeneralData:
    id: str # Using schemaVersion as id here based on Swift code
    author: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None

@dataclass
class PLMXMLTransferContextlData:
    id: str
    transferContext: Optional[str] = None

# Container for all parsed data
@dataclass
class ParsedPLMXMLData:
    productViews: List[ProductView] = field(default_factory=list)
    revisionRules: Dict[str, RevisionRuleData] = field(default_factory=dict)
    generalInfo: Dict[str, PLMXMLGeneralData] = field(default_factory=dict) # Keyed by schemaVersion
    sites: Dict[str, SiteData] = field(default_factory=dict)
    transferContexts: Dict[str, PLMXMLTransferContextlData] = field(default_factory=dict)
    productRevisions: Dict[str, ProductRevisionData] = field(default_factory=dict)
    products: Dict[str, ProductData] = field(default_factory=dict)
    occurrences: Dict[str, Occurrence] = field(default_factory=dict) # Flat list before hierarchy
    associatedAttachments: Dict[str, AssociatedAttachment] = field(default_factory=dict)
    forms: Dict[str, FormData] = field(default_factory=dict)
    dataSets: Dict[str, DataSetData] = field(default_factory=dict)
    externalFiles: Dict[str, ExternalFileData] = field(default_factory=dict)
    plmxml_directory: Optional[str] = None # Store the base directory for resolving relative paths
