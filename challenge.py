"""
This script processes files containing US addresses and outputs a sorted JSON list.
"""
__version__ = '0.1'
__author__ = 'Sadra Dowlatshahi'

import argparse
import csv
import json
import logging
import os
import re
import sys
from xml.etree import ElementTree as ET


class InvalidFileFormatError(Exception):
    pass


# parse .xml files
def is_valid_data(value):
    """Check if the data value is not missing (not 'N/A' and not empty)."""
    return value not in ['N/A', '']


def check_xml_format(file_path, expected_tags):
    """Check if the XML file contains all expected tags and return missing tags."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        all_tags = {elem.tag for elem in root.iter()}
        missing_tags = [tag for tag in expected_tags if tag not in all_tags]
        return missing_tags
    except ET.ParseError as e:
        raise InvalidFileFormatError(f"Error parsing XML: {e}")


def parse_xml(file_path):
    """Parse XML file and return a list of addresses."""

    # Define the expected tags based on the updated requirements
    EXPERCTED_TAGS = [
        'NAME', 'COMPANY', 'STREET', 
        'STREET_2', 'STREET_3', 'CITY', 
        'STATE', 'COUNTRY', 'POSTAL_CODE'
    ]

    missing_tags = check_xml_format(file_path, EXPERCTED_TAGS)
    if missing_tags:
        raise InvalidFileFormatError(f"The XML file {file_path} is missing tags: {', '.join(missing_tags)}")

    tree = ET.parse(file_path)
    root = tree.getroot()
    addresses = []

    for entry in root.findall('.//ENT'):
        address = {}
        name = entry.find('NAME')
        company = entry.find('COMPANY')
        street_parts = [entry.find('STREET'), entry.find('STREET_2'), entry.find('STREET_3')]
        city = entry.find('CITY')
        state = entry.find('STATE')
        postal_code = entry.find('POSTAL_CODE')

        if name is not None and name.text.strip():
            address['name'] = name.text.strip()
        if company is not None and company.text.strip():
            address['organization'] = company.text.strip()

        streets = ' '.join(part.text.strip() for part in street_parts if part is not None and part.text.strip())
        if streets:
            address['street'] = streets

        if city is not None and city.text:
            address['city'] = city.text
        if state is not None and state.text:
            address['state'] = state.text
        if postal_code is not None and postal_code.text:
            address['zip'] = postal_code.text.strip().rstrip(" -")

        addresses.append(address)

    return addresses


# parse .tsv files
def check_tsv_format(headers, expected_headers):
    """Check if the file's headers match the expected format and return missing headers."""
    missing_headers = [header for header in expected_headers if header not in headers]
    return missing_headers


def parse_tsv(file_path):
    """Parse TSV file and return a list of addresses."""

    # Define the expected format (headers) as seen in input2.tsv
    EXPECTED_HEADERS = [
        'first', 'middle', 'last', 
        'organization', 'address', 'city', 
        'state', 'county', 'zip', 'zip4'
    ]
    addresses = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter='\t')
        headers = next(reader)

        missing_headers = check_tsv_format(headers, EXPECTED_HEADERS)
        if missing_headers:
            raise InvalidFileFormatError(f"The file {file_path} is missing headers: {', '.join(missing_headers)}")

        file.seek(0)
        dict_reader = csv.DictReader(file, delimiter='\t')

        for row in dict_reader:
            address = {}
            if not is_valid_data(row['first']) and is_valid_data(row['last']):
                address['organization'] = row['last']
            else:
                name_parts = [row['first'], row['middle'], row['last']]
                address['name'] = ' '.join(part for part in name_parts if is_valid_data(part))

            if is_valid_data(row['address']):
                address['street'] = row['address']
            if is_valid_data(row['city']):
                address['city'] = row['city']
            if is_valid_data(row['county']):
                address['county'] = row['county']
            if is_valid_data(row['state']):
                address['state'] = row['state']

            if is_valid_data(row['zip']):
                zip_code = row['zip']
                if is_valid_data(row['zip4']):
                    zip_code += '-' + row['zip4']
                address['zip'] = zip_code

            addresses.append(address)
    return addresses

# parse .txt files
def format_zip(zip_code):
    """Format ZIP code by removing trailing '-' and spaces around it."""
    return zip_code.strip().rstrip('-').strip()

def parse_txt(file_path):
    """Parse TXT file and return a list of addresses."""
    addresses = []
    with open(file_path, 'r') as file:
        content = file.read().strip()
        entries = content.split('\n\n')

        line_number = 0
        for entry in entries:
            address = {}
            lines = [line.strip() for line in entry.split('\n') if line.strip()]
            line_number += len(lines) + 1

            if len(lines) < 3 or len(lines) > 4:
                raise InvalidFileFormatError(
                    f"Format error in {file_path} at line \
                    {line_number-len(lines)}-{line_number-1}: Entry with \
                    incorrect number of lines ({len(lines)})"
                    )

            address["name"] =  lines[0].lstrip('\t')
            address["street"] = lines[1].lstrip('\t')

            if len(lines) == 4:
                county = lines[2].lstrip('\t')
                address["county"] = county

            city_state_zip_line = lines[-1].lstrip('\t')
            
            city_state_zip = city_state_zip_line.rsplit(',', 1)
            address["city"] = city_state_zip[0].strip()
            state_zip = city_state_zip[1].rsplit(' ', 1)

            address["state"] = state_zip[0].strip()
            address["zip"] = format_zip(state_zip[1])

            addresses.append(address)

    return addresses

# main application
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Process files containing US addresses and output a sorted JSON list.')
    parser.add_argument('files', nargs='+', help='List of file paths to process')
    return parser.parse_args()


def process_files(file_paths):
    """Process files and return a sorted list of addresses."""
    all_addresses = []
    for file_path in file_paths:
        if not os.path.isfile(file_path):
            logging.error(f"File not found: {file_path}")
            continue

        if file_path.endswith('.xml'):
            all_addresses.extend(parse_xml(file_path))
        elif file_path.endswith('.tsv'):
            all_addresses.extend(parse_tsv(file_path))
        elif file_path.endswith('.txt'):
            all_addresses.extend(parse_txt(file_path))
        else:
            logging.warning(f"Unsupported file format: {file_path}")

    return sorted(all_addresses, key=lambda x: x['zip'])


def main():
    """Main function to process files and output JSON."""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    args = parse_args()
    try:
        addresses = process_files(args.files)
        print(json.dumps(addresses, indent=2))
    except InvalidFileFormatError as e:
        logging.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()