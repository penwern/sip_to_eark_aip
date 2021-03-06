import hashlib
import logging
import mimetypes
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


SOFTWARE_NAME = "E-ARK AIP Creator"
SOFTWARE_VERSION = "v0.1.0-dev"


def get_arg(index):
    try:
        sys.argv[index]
    except IndexError:
        return None
    else:
        return sys.argv[index]


def get_checksum(file):
    sha256_hash = hashlib.sha256()
    with open(file, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


def validate_directories(sip_dir, output_dir):
    """
    Ensures sip_dir exists and is a dir. If output_dir exists ensure it is a directory
        :param Path sip_dir: location of the sip
        :param Path output_dir: desired output location
        :return Boolean: True if valid
    """
    if sip_dir.exists():
        if sip_dir.is_dir():
            if output_dir.exists():
                if output_dir.is_dir():
                    sip_name = sip_dir.stem
                    try:
                        sip_uuid = sip_name
                        if 'uuid-' in sip_name:
                            sip_uuid = sip_name[sip_name.index('uuid-') + len('uuid-'):]
                        uuid_obj = uuid.UUID(sip_uuid, version=4)
                        if sip_uuid == str(uuid_obj):
                            pass
                    except ValueError:
                        logging.error("SIP does not contain valid uuid4")
                        # print("Error: SIP doesn't contain valid uuid4")
                        sys.exit(2)
                    else:
                        return True
                else:
                    logging.error("Output is not a directory")
                    # print("Error: Output is not a directory")
            else:
                return True
        else:
            logging.error("Input is not a directory")
            # print("Error: Input is not a directory")
    else:
        logging.error("Input Directory doesn't exist")
        # print("Error: Input directory doesn't exist")
    return False


def overwrite_and_create_directory(directory):
    """
    Deletes directory if it exists and (re)creates directory
    :param Path directory: path that needs to be (re)created
    """
    if directory.is_dir():
        logging.info("Overwriting '%s'" % directory)
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=False)


def new_uuid():
    return 'uuid-' + str(uuid.uuid4())


def new_id():
    return 'ID-' + str(uuid.uuid4())


def update_all_mets_ids(mets_tree, id_updates, namespaces):
    """
    Updates all IDS in a mets file while maintaining connections using dict of updated IDs
    :param ElementTree mets_tree: tree for IDs to be updated on
    :param dict id_updates: contains tracked changes in ID's to maintain connections
    :param dict namespaces: contains namespaces and their schema locations
    """
    root = mets_tree.getroot()
    dmdsec_elements = root.findall('{%s}dmdSec' % namespaces[''])
    for dmdsec in dmdsec_elements:
        id_updates[dmdsec.attrib['ID']] = dmdsec.attrib['ID'] = new_uuid()

    amdsec_elements = root.findall('{%s}amdSec' % namespaces[''])
    for amdsec in amdsec_elements:
        id_updates[amdsec.attrib['ID']] = amdsec.attrib['ID'] = new_uuid()

    filesec_element = root.find('{%s}fileSec' % namespaces[''])
    filesec_element.attrib['ID'] = new_uuid()
    for filegrp in filesec_element.findall('{%s}fileGrp' % namespaces['']):
        filegrp_sub_filegrps = filegrp.findall('{%s}fileGrp' % namespaces[''])
        if filegrp_sub_filegrps:
            for sub_filegrp in filegrp.findall('{%s}fileGrp' % namespaces['']):
                id_updates[sub_filegrp.attrib['ID']] = sub_filegrp.attrib['ID'] = new_uuid()
                for file_element in sub_filegrp.findall('{%s}file' % namespaces['']):
                    id_updates[file_element.attrib['ID']] = file_element.attrib['ID'] = new_id()
        else:
            id_updates[filegrp.attrib['ID']] = filegrp.attrib['ID'] = new_uuid()
            for file_element in filegrp.findall('{%s}file' % namespaces['']):
                id_updates[file_element.attrib['ID']] = file_element.attrib['ID'] = new_id()

    structmap_element = root.find('{%s}structMap' % namespaces[''])
    structmap_element.attrib['ID'] = new_uuid()
    root_div_element = structmap_element.find('{%s}div' % namespaces[''])
    root_div_element.attrib['LABEL'] = root.attrib['OBJID']
    for div in root_div_element.findall('{%s}div' % namespaces['']):
        div.attrib['ID'] = new_uuid()
        if div.attrib['LABEL'].lower() == 'metadata':
            if div.attrib['DMDID'] in id_updates:
                div.attrib['DMDID'] = id_updates[div.attrib['DMDID']]
            else:
                div.attrib['DMDID'] = new_uuid()
        div_subdivs = div.findall('{%s}div' % namespaces[''])
        if div_subdivs:
            for sub_div in div_subdivs:
                sub_div_id = new_uuid()
                sub_div.attrib['ID'] = sub_div_id
                for item in sub_div:
                    if str(item.tag) == '{%s}fptr' % namespaces['']:
                        if item.attrib['FILEID'] in id_updates:
                            item.attrib['FILEID'] = id_updates[item.attrib['FILEID']]
                        elif '.' not in item.attrib['FILEID']:  # If the ID is a file name
                            item.attrib['FILEID'] = new_uuid()
                    elif str(item.tag) == '{%s}mptr' % namespaces['']:
                        try:
                            if item.attrib['{%s}title' % namespaces['xlink']] in id_updates:
                                item.attrib['{%s}title' % namespaces['xlink']] = id_updates[
                                    item.attrib['{%s}title' % namespaces['xlink']]]
                            else:
                                item.attrib['{%s}title' % namespaces['xlink']] = new_uuid()
                        except KeyError:
                            pass
        else:
            for item in div:
                if str(item.tag) == '{%s}fptr' % namespaces['']:
                    if item.attrib['FILEID'] in id_updates:
                        item.attrib['FILEID'] = id_updates[item.attrib['FILEID']]
                    else:
                        item.attrib['FILEID'] = new_uuid()
                elif str(item.tag) == '{%s}mptr' % namespaces['']:
                    try:
                        if item.attrib['{%s}title' % namespaces['xlink']] in id_updates:
                            item.attrib['{%s}title' % namespaces['xlink']] = id_updates[
                                item.attrib['{%s}title' % namespaces['xlink']]]
                        else:
                            item.attrib['{%s}title' % namespaces['xlink']] = new_uuid()
                    except KeyError:
                        pass


def get_namespaces(mets_file):
    # register namespaces to ET parser
    namespaces = {value[0]: value[1] for key, value in ET.iterparse(mets_file, events=['start-ns'])}
    for key in namespaces:
        ET.register_namespace(key, namespaces[key])
    return namespaces


def create_aip_rep_mets(sip_rep_mets, rep_root):
    """
    Generate preservation METs.xml in representations using sip rep mets as template
    :param sip_rep_mets: location of reference mets
    :param rep_root: preservation directory (representations/rep01.1)
    :return:
    """
    namespaces = get_namespaces(sip_rep_mets)
    tree = ET.parse(sip_rep_mets)
    root = tree.getroot()
    created_now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    root.attrib['OBJID'] = rep_root.name

    # METS HEADER
    metshdr_element = root.find('{%s}metsHdr' % namespaces[''])
    metshdr_element.attrib['CREATEDATE'] = created_now
    metshdr_element.attrib['LASTMODDATE'] = created_now
    metshdr_element.attrib['RECORDSTATUS'] = 'Revised'
    try:
        metshdr_element.attrib['{%s}OAISPACKAGETYPE' % namespaces['csip']] = 'AIP'
    except KeyError:
        logging.error("metsHdr doesn't containt OAISPACKAGETYPE as 'csip' is not in namespaces")
        sys.exit(2)

    for agent_element in metshdr_element.findall('{%s}agent' % namespaces['']):
        agent_attribs = agent_element.attrib
        try:
            if agent_attribs['ROLE'] == 'CREATOR' and agent_attribs['TYPE'] == 'OTHER' and agent_attribs['OTHERTYPE'] == 'SOFTWARE':
                metshdr_element.remove(agent_element)
        except KeyError:
            pass

        new_agent = ET.Element('{%s}agent' % namespaces[''], attrib={'ROLE': 'CREATOR', 'TYPE': 'OTHER', 'OTHERTYPE': 'SOFTWARE'})
        new_agent_name = ET.SubElement(new_agent, '{%s}name' % namespaces[''])
        new_agent_name.text = SOFTWARE_NAME
        new_agent_note = ET.SubElement(new_agent, '{%s}note' % namespaces[''], attrib={'{%s}NOTETYPE' % namespaces['csip']: 'SOFTWARE VERSION'})
        new_agent_note.text = SOFTWARE_VERSION
        metshdr_element.append(new_agent)

        try:
            if agent_attribs['ROLE'] == 'CREATOR' and agent_attribs['TYPE'] == 'INDIVIDUAL':
                metshdr_element.remove(agent_element)
        except KeyError:
            pass
    
    metsDocumentId_element = metshdr_element.find('{%s}metsDocumentID' % namespaces[''])
    if metsDocumentId_element is not None:
        metshdr_element.remove(metsDocumentId_element)

    # FILE SECTION
    filesec_element = root.find('{%s}fileSec' % namespaces[''])

    for fileGrp in filesec_element.findall('{%s}fileGrp' % namespaces['']):
        filesec_element.remove(fileGrp)

    new_filegrp_id = new_uuid()
    new_filegrp = ET.Element('{%s}fileGrp' % namespaces[''], attrib={'ID': new_filegrp_id, 'USE': 'Data'})

    for file in Path(rep_root / 'data').iterdir():
        new_file = ET.Element('{%s}file' % namespaces[''],
                              attrib={'ID': new_id(), 'MIMETYPE': str(mimetypes.guess_type(file)[0]),
                                      'SIZE': str(file.stat().st_size), 'CREATED': created_now,
                                      'CHECKSUM': get_checksum(file), 'CHECKSUMTYPE': 'SHA-256'})

        new_flocat = ET.Element('{%s}FLocat' % namespaces[''],
                                attrib={'{%s}type' % namespaces['xlink']: 'simple',
                                        '{%s}href' % namespaces['xlink']: 'data/' + file.name,
                                        'LOCTYPE': 'URL'})
        new_file.append(new_flocat)
        new_filegrp.append(new_file)
    filesec_element.append(new_filegrp)

    structmap_element = root.find('{%s}structMap' % namespaces[''])
    root_div_elements = structmap_element.findall('{%s}div' % namespaces[''])
    for div in root_div_elements:
        structmap_element.remove(div)
    new_div = ET.Element('{%s}div' % namespaces[''], attrib={'ID': new_uuid(), 'TYPE': 'ORIGINAL',
                                                             'LABEL': root.attrib['OBJID']})
    new_sub_div = ET.Element('{%s}div' % namespaces[''], attrib={'ID': new_uuid(), 'LABEL': 'DATA'})

    new_fptr = ET.Element('{%s}fptr' % namespaces[''], attrib={'FILEID': new_filegrp_id})

    new_sub_div.append(new_fptr)
    new_div.append(new_sub_div)
    structmap_element.append(new_div)

    # UPDATE IDS
    update_all_mets_ids(tree, {}, namespaces)

    ET.indent(tree, space='    ', level=0)
    tree.write(rep_root / 'METS.xml', encoding='utf-8', xml_declaration=True)


def create_aip_root_mets(sip_mets: Path, aip_root: Path, id_updates):
    """
    The structure of the SIP and AIP are similar so it is possible to alter the SIP METS.xml
    This method maintains namespaces with the original SIP mets and uses it as a template. The necessary adjustments are
    made to make it a conformant EARK AIP mets file.
    :param Path sip_mets: Path to SIP METS to use as template
    :param Path aip_root: Path to AIP root where METS will be written
    :param dict id_updates: Tracks ID changed to ensure connections remain
    """

    namespaces = get_namespaces(sip_mets)

    tree = ET.parse(sip_mets)
    root = tree.getroot()
    root.attrib['OBJID'] = str(aip_root.stem)[str(aip_root.stem).index('uuid'):]
    created_now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    # METS HEADER
    metshdr_element = root.find('{%s}metsHdr' % namespaces[''])
    metshdr_element.attrib['CREATEDATE'] = created_now
    metshdr_element.attrib['LASTMODDATE'] = created_now
    metshdr_element.attrib['RECORDSTATUS'] = 'Revised'
    try:
        metshdr_element.attrib['{%s}OAISPACKAGETYPE' % namespaces['csip']] = 'AIP'
    except KeyError:
        print("Warning: metsHdr doesn't contain OAISPACKAGETYPE")
        sys.exit(2)

    for agent_element in metshdr_element.findall('{%s}agent' % namespaces['']):
        agent_attribs = agent_element.attrib
        try:
            if agent_attribs['ROLE'] == 'CREATOR' and agent_attribs['TYPE'] == 'OTHER' and agent_attribs['OTHERTYPE'] == 'SOFTWARE':
                metshdr_element.remove(agent_element)
                new_agent = ET.Element('{%s}agent' % namespaces[''], attrib={'ROLE': 'CREATOR', 'TYPE': 'OTHER', 'OTHERTYPE': 'SOFTWARE'})
                new_agent_name = ET.SubElement(new_agent, '{%s}name' % namespaces[''])
                new_agent_name.text = SOFTWARE_NAME
                new_agent_note = ET.SubElement(new_agent, '{%s}note' % namespaces[''], attrib={'{%s}NOTETYPE' % namespaces['csip']: 'SOFTWARE VERSION'})
                new_agent_note.text = SOFTWARE_VERSION
                metshdr_element.append(new_agent)
        except KeyError:
            pass
        
        try:
            if agent_attribs['ROLE'] == 'CREATOR' and agent_attribs['TYPE'] == 'INDIVIDUAL':
                metshdr_element.remove(agent_element)
        except KeyError:
            pass


    # DMD SEC
    # Expected SHA-256 checksum
    try:
        dmdsec_element = root.find('{%s}dmdSec' % namespaces[''])
    except KeyError:
        pass
    else:
        try:
            mdref_element = dmdsec_element.find('{%s}mdRef' % namespaces[''])
        except KeyError:
            logging.error("No mdRef found in dmdSec")
            sys.exit(2)
        else:
            href = Path(mdref_element.attrib['{%s}href' % namespaces['xlink']])
            metadata_location = aip_root / href
            mdref_element.attrib['SIZE'] = str(metadata_location.stat().st_size)
            mdref_element.attrib['CHECKSUM'] = get_checksum(metadata_location)
        

    # FILE SECTION
    filesec_element = root.find('{%s}fileSec' % namespaces[''])

    # NEW SUBMISSION GROUP + FILES
    relative_mets = 'submission/submission-' + str(datetime.now().strftime("%Y-%m-%d")) +'/METS.xml'
    submission_mets = aip_root / relative_mets
    new_sub_id = new_uuid()
    new_filegrp = ET.Element('{%s}fileGrp' % namespaces[''], attrib={'ID': new_sub_id, 'USE': 'Submission'})

    new_file = ET.Element('{%s}file' % namespaces[''],
                          attrib={'ID': new_id(), 'MIMETYPE': str(mimetypes.guess_type(submission_mets)[0]),
                                  'SIZE': str(submission_mets.stat().st_size), 'CREATED': created_now,
                                  'CHECKSUM': get_checksum(submission_mets), 'CHECKSUMTYPE': 'SHA-256'})

    new_flocat = ET.Element('{%s}FLocat' % namespaces[''],
                            attrib={'{%s}type' % namespaces['xlink']: 'simple',
                                    '{%s}href' % namespaces['xlink']: relative_mets, 'LOCTYPE': 'URL'})

    new_file.append(new_flocat)
    new_filegrp.append(new_file)
    filesec_element.append(new_filegrp)
    
    preservation_rep_i = 1
    # EACH FILE GROUP
    for fileGrp_element in filesec_element.findall('{%s}fileGrp' % namespaces['']):
        # Convert SIP representations to preservation represnetations
        if fileGrp_element.attrib['USE'].lower().startswith('representations'):

            rep_use = Path(fileGrp_element.attrib['USE'])
            rep_parts = rep_use.parts

            id_updates[fileGrp_element.attrib['ID']] = fileGrp_element.attrib['ID'] = new_uuid()

            if len(rep_parts) == 2:   # Representations/rep1
                preservation_rep_num = "{:02}.1".format(preservation_rep_i)
                preservation_rep_name = rep_parts[0].lower() + '/' + 'rep' + preservation_rep_num
                preservation_rep_i += 1
                fileGrp_element.attrib['USE'] = preservation_rep_name.capitalize()
                for file_element in fileGrp_element.findall('{%s}file' % namespaces['']):
                    fileGrp_element.remove(file_element)
                
                preservation_mets_path: Path = aip_root / preservation_rep_name.lower() / 'METS.xml'
                if preservation_mets_path.exists():
                    new_file_element = ET.Element('{%s}file' % namespaces[''], 
                                                attrib={
                                                    'ID': new_id(),
                                                    'MIMETYPE': str(mimetypes.guess_type(preservation_mets_path)[0]),
                                                    'SIZE': str(preservation_mets_path.stat().st_size),
                                                    'CREATED': created_now,
                                                    'CHECKSUM': get_checksum(preservation_mets_path),
                                                    'CHECKSUMTYPE' : "SHA-256"
                                                })
                    new_FLocat_element = ET.Element('{%s}FLocat' % namespaces[''],
                                                    attrib={
                                                        '{%s}type' % namespaces['xlink']: 'simple',
                                                        '{%s}href' % namespaces['xlink']: preservation_rep_name + '/' + 'METS.xml',
                                                        'LOCTYPE': 'URL',
                                                    })
                    new_file_element.append(new_FLocat_element)
                    fileGrp_element.append(new_file_element)
            else:
                logging.error("Unsupported representations structure")
                sys.exit(2)

    # STRUCT MAP
    structmap_element = root.find('{%s}structMap' % namespaces[''])
    root_div_element = structmap_element.find('{%s}div' % namespaces[''])
    root_div_element.attrib['ID'] = new_uuid()
    rep_i = 1
    for div in root_div_element.findall('{%s}div' % namespaces['']):
        if div.attrib['LABEL'].lower().startswith('representations'):
            rep_parts = Path(div.attrib['LABEL']).parts
            if len(rep_parts) == 2:  # 'Representations/repx'
                rep_num = "{:02}.1".format(rep_i)
                rep_name = 'rep' + rep_num
                rep_i += 1
                preservation_rep_path = Path('representations', rep_name)
                div.attrib['LABEL'] = 'Representations'

                new_sub_div = ET.Element('{%s}div' % namespaces[''], attrib={'ID': '', 'LABEL': rep_name.capitalize()})
                div.append(new_sub_div)

                item = div.find('{%s}mptr' % namespaces[''])
                item.attrib['{%s}href' % namespaces['xlink']] = str(preservation_rep_path / 'METS.xml')
                div.remove(item)
                new_sub_div.append(item)
            else:
                logging.error("Unsupported representations structure")
                sys.exit(2)

        if div.attrib['LABEL'].lower() == 'submission':
            root_div_element.remove(div)

    new_sub_div = ET.Element('{%s}div' % namespaces[''],
                             attrib={'ID': new_sub_id,
                                     'LABEL': 'Submission'})
    new_sub_mptr = ET.Element(
        '{%s}mptr' % namespaces[''],
        attrib={'{%s}type' % namespaces['xlink']: 'simple',
                '{%s}href' % namespaces['xlink']: 'submission/METS.xml',
                '{%s}title' % namespaces['xlink']: new_sub_id, 'LOCTYPE': 'URL'}
    )
    new_sub_div.append(new_sub_mptr)
    root_div_element.append(new_sub_div)

    # UPDATE IDS
    update_all_mets_ids(tree, id_updates, namespaces)

    ET.indent(tree, space='    ', level=0)
    tree.write(aip_root / 'METS.xml', encoding='utf-8', xml_declaration=True)


def copy_sip_to_aip(sip_path, aip_path):
    """
    Copy the required items from the SIP into the necessary locations in the AIP
    :param Path sip_path: Location of sip to transform
    :param Path aip_path: Destination of transformed files (output / path / sipname)
    """
    # copy required items in to submissions and copy in to AIP root if required
    items_to_copy = {'representations': False, 'metadata': True, 'schemas': True, 'documentation': True,
                     'METS.xml': False}
    aip_submission_path = aip_path / "submission" / ('submission-' + str(datetime.now().strftime("%Y-%m-%d")))
    expected_sip_reps_path = sip_path / 'representations'
    if expected_sip_reps_path.is_dir():
        aip_submission_path.mkdir(parents=True)
        for item in items_to_copy.keys():
            item_path = sip_path / item
            destination_path = aip_submission_path / item
            if item_path.is_dir():
                shutil.copytree(item_path, destination_path)
                # if True, also copy item into aip root
                if items_to_copy[item]:
                    shutil.copytree(item_path, aip_path / item)
            elif item_path.is_file():
                # Will be METS.xml
                shutil.copy2(item_path, destination_path)
    else:
        print("Error: SIP representations directory not found")
        print("Exiting.")
        sys.exit(2)


def create_aip_representations(aip_path):
    """
    Create preservation directories to store archivematica transfer
    :param Path aip_path: path to AIP root
    """
    aip_submission_representations_path = aip_path / 'submission' / ('submission-' + str(datetime.now().strftime("%Y-%m-%d"))) / "representations"

    rep_i = 1
    for rep in sorted(aip_submission_representations_path.iterdir()):
        # make preservation directory rep0x.1
        preservation_rep_path = aip_path / "representations" / "{}{:02}.1".format('rep', rep_i)
        (preservation_rep_path / "data").mkdir(parents=True)
        with open(preservation_rep_path / 'data' / 'TestAMTransfer.txt', 'w') as f:
            f.write("Just some random text")

        create_aip_rep_mets(rep / 'METS.xml', preservation_rep_path)

        rep_i += 1


def get_uuid_from_string(filename):
    try:
        the_uuid = filename
        the_prefix = ''
        accepted_prefixs = ['uuid-']
        for prefix in accepted_prefixs:
            if prefix in filename:
                the_uuid = filename[filename.index(prefix) + len(prefix):]
                the_prefix = prefix
                break
        uuid_obj = uuid.UUID(the_uuid, version=4)
        if the_uuid == str(uuid_obj):
            pass
    except ValueError:
        logging.error(filename + " doesn't contain valid uuid4")
        # print("Error: " + filename + " doesn't contain valid uuid4")
        sys.exit(2)
    return the_prefix + the_uuid


def transform_sip_to_aip(sip_path, aip_path):
    # Make False for testing to prevent giving aip new uuid and save space
    if True:
        sip_name = sip_path.stem
        sip_uuid = get_uuid_from_string(sip_name)
        package_name = sip_name[:-len(sip_uuid)]
        aip_uuid = new_uuid()
        aip_name = package_name + aip_uuid
        aip_path = aip_path / aip_name
        id_updates = {sip_uuid: aip_uuid}
    else:
        sip_name = sip_path.stem
        aip_path = aip_path / sip_name
        sip_uuid = sip_name[sip_name.index('uuid'):]
        aip_uuid = sip_uuid
        id_updates = {}

    overwrite_and_create_directory(aip_path)

    copy_sip_to_aip(sip_path, aip_path)

    create_aip_representations(aip_path)

    sip_mets = Path(sip_path / 'METS.xml')

    descriptive_metadata_file = aip_path / 'metadata' / 'descriptive' / 'dc.xml'
    if descriptive_metadata_file.exists():
        desc_tree = ET.parse(descriptive_metadata_file)
        desc_root = desc_tree.getroot()
        for child in desc_root:
            if child.text == sip_uuid:
                child.text = aip_uuid
        desc_tree.write(descriptive_metadata_file, encoding='utf-8', xml_declaration=True)

    create_aip_root_mets(sip_mets, aip_path, id_updates)

    print(aip_name)

    logging.info("Finished transforming SIP: " + sip_name + " into AIP: " + aip_name)


if __name__ == '__main__':
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.DEBUG, filemode='a', filename='logs/sip_to_eark_aip.log', format='%(asctime)s %(levelname)s: %(message)s')
    if len(sys.argv) == 3:
        input_sip = Path(get_arg(1))
        output_dir = Path(get_arg(2))
        if validate_directories(input_sip, output_dir):
            transform_sip_to_aip(input_sip, output_dir)
        else:
            sys.exit(1)
    else:
        logging.error("Incorrect script call format")
        print("Error: Command should have the form:")
        print("python aip_to_eark_aip.py <SIP Directory> <Output Directory>")
        sys.exit(1)
