import pandas as pd
import numpy as np
import re
import json
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import time


def split_coordinate(four_coords, divisions_longs, divisions_lats, if_big_box):
    """
    Split a geographic bounding box into smaller grid cells based on specified divisions.

    Args:
        four_coords (list): A list of four float values representing the coordinates of the bounding box
                           in the order [min_latitude, max_latitude, min_longitude, max_longitude].
        divisions_longs (int): The number of divisions along the longitude axis.
        divisions_lats (int): The number of divisions along the latitude axis.
        if_big_box (str or None): A string in the format "min_lat:max_lat:min_lon:max_lon" representing
                                 the bounding box coordinates. If provided, this is used instead of four_coords.

    Returns:
        list: A list of strings, each representing a smaller bounding box in the format
              "min_lat:max_lat:min_lon:max_lon".

    Example:
        >>> split_coordinate([0, 1, 0, 1], 2, 2, None)
        ['0.0:0.5:0.0:0.5', '0.0:0.5:0.5:1.0', '0.5:1.0:0.0:0.5', '0.5:1.0:0.5:1.0']
    """
    # Determine the bounding box coordinates based on input
    if if_big_box:
        # Parse the string format "min_lat:max_lat:min_lon:max_lon" into a list of floats
        [min_latitude, max_latitude, min_longitude, max_longitude] = [float(x) for x in if_big_box.split(':')]
    else:
        # Use the provided list of coordinates
        [min_latitude, max_latitude, min_longitude, max_longitude] = four_coords

    # Calculate the step size for longitude and latitude divisions
    longitude_step = (max_longitude - min_longitude) / divisions_longs
    latitude_step = (max_latitude - min_latitude) / divisions_lats

    coord_boxes = []
    
    # Iterate over each grid cell to create smaller bounding boxes
    for i in range(divisions_longs):
        for j in range(divisions_lats):
            # Calculate the min and max latitude/longitude for the current grid cell
            box_min_lat = round(min_latitude + j * latitude_step, 5)
            box_max_lat = round(min_latitude + (j + 1) * latitude_step, 5)
            box_min_lon = round(min_longitude + i * longitude_step, 5)
            box_max_lon = round(min_longitude + (i + 1) * longitude_step, 5)

            # Format the bounding box as a string "min_lat:max_lat:min_lon:max_lon"
            box_str = f"{box_min_lat}:{box_max_lat}:{box_min_lon}:{box_max_lon}"
            coord_boxes.append(box_str)
    
    return coord_boxes


def vancouver_grid(head, divisions_longs, devision_lats):
    """
    Generates a grid of latitude-longitude bounding boxes within Vancouver's city boundary.

    Parameters:
    head (dict): Headers for the API request.
    divisions_longs (int): Number of divisions along the longitude (default is 15).
    devision_lats (int): Number of divisions along the latitude (default is 15).

    Returns:
    list: A list of strings representing bounding boxes in the format "min_lat:max_lat:min_lon:max_lon".
    """
    
    # API endpoint for Vancouver city boundary geo-coordinates
    van_geo_info_url = 'https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/city-boundary/records?limit=20'
    
    # Fetch geographical data from the API
    response = requests.get(van_geo_info_url, headers=head)
    geo_data = response.json()
    
    # Extract the city boundary coordinates
    contour = geo_data['results'][0]['geom']['geometry']['coordinates']

    # Flatten the list of coordinates and extract longitude and latitude values separately
    longitudes = [coord[0] for sublist in contour for coord in sublist]
    latitudes = [coord[1] for sublist in contour for coord in sublist]

    # Determine the minimum and maximum longitude and latitude values
    max_longitude = max(longitudes)
    min_longitude = min(longitudes)
    max_latitude = max(latitudes)
    min_latitude = min(latitudes)
    four_coords = [min_latitude, max_latitude, min_longitude, max_longitude]

    
    coord_boxes = split_coordinate(four_coords, divisions_longs, devision_lats, if_big_box = 0)
 
    
    return coord_boxes


def listing_count(head, coord_box):
    """
    Fetches the number of real estate listings within a specified coordinate box from Redfin.

    Parameters:
    head (dict): Headers for the HTTP request.
    coord_box (str): A string representing the bounding box in the format "min_lat:max_lat:min_lon:max_lon".

    Returns:
    tuple: (viewport_url, select_listing_count, total_listing_count)
        - viewport_url (str): The URL used for the request.
        - select_listing_count (int): The number of listings shown in the current viewport.
        - total_listing_count (int): The total number of listings available.
        - If no listings are found, returns 'no_listing'.
    """
    
    # Construct the URL for the given coordinate box
    viewport_url = f"https://www.redfin.ca/bc/vancouver/filter/viewport={coord_box}"
    
    # Send a GET request to fetch the webpage
    resp = requests.get(viewport_url, headers=head)

    # Raise an error if the request fails (non-200 status code)
    if resp.status_code != 200:
        raise Exception("Failing in webpage requests")
    
    # Parse the HTML response using BeautifulSoup
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Check if the page indicates no listings are available
    if soup.find('div', {'class': 'HomeViews reversePosition'}).find('h2'):
        return 'no_listing'
    
    # Extract the listing summary section
    listing_summary = soup.find('div', {'class': "homes summary reversePosition"})

    # Use regex to extract numeric values from the listing summary
    select_listing_count, total_listing_count = re.findall(r'\d{1,10}(?:,\d{1,10})*', listing_summary.text)
    
    # Convert extracted strings into integers, handling comma formatting
    select_listing_count, total_listing_count = int(select_listing_count), int(total_listing_count.replace(',', ''))
    
    return viewport_url, select_listing_count, total_listing_count


def crawling_redfin(head, viewport_url, page):
    """
    Crawls a specific page of real estate listings from Redfin within a given viewport.

    Parameters:
    head (dict): Headers for the HTTP request.
    viewport_url (str): Base URL for the listings search.
    page (int): Page number to crawl.

    Returns:
    list: A list of BeautifulSoup objects representing individual property listings.
    """
    
    # Construct the URL for the specified page number
    target_url = f"{viewport_url}/page-{page}"
    
    # Send a GET request to fetch the webpage
    resp = requests.get(target_url, headers=head)

    # Raise an error if the request fails (non-200 status code)
    if resp.status_code != 200:
        raise Exception("Failing in webpage requests")
    
    # Parse the HTML response using BeautifulSoup
    soup = BeautifulSoup(resp.text, 'html.parser')

    return soup



def key_metric_extraction(soup, real_estate_info):
    """
    Extracts key real estate metrics from Redfin listing elements.

    Parameters:
    soup_boxes (list): A list of BeautifulSoup objects representing property listings.
    real_estate_info (dict): A dictionary to store extracted real estate information. 
                             The dictionary should have keys: 'address', 'zip_code', 'price', 
                             'bed', 'bath', 'sqr_footage', and 'property_link'.

    Returns:
    list: A list of indices where data extraction was incomplete.
    """
    
    incomplete_idx = []  # Stores indices of listings with missing data

    soup_boxes = soup.find_all("div", {"class": "HomeCardContainer"})

    for i, box in enumerate(soup_boxes):
        try:
            # Extract address (excluding last 23 characters, likely city/state info)
            address = box.find('address').text[:(-23)]
            real_estate_info['address'].append(address)
        except: 
            real_estate_info['address'].append(np.nan)
            incomplete_idx.append(i)

        try:
            # Extract ZIP code (last 7 characters of address text)
            zip_code = box.find('address').text[-7:]
            real_estate_info['zip_code'].append(zip_code)
        except: 
            real_estate_info['zip_code'].append(np.nan)
            incomplete_idx.append(i)        

        try:
            # Extract price
            price = box.find('span', {'class': 'bp-Homecard__Price--value'}).text
            real_estate_info['price'].append(price)
        except: 
            real_estate_info['price'].append(np.nan)
            incomplete_idx.append(i)

        try:
            # Extract number of bedrooms
            bed = box.find('span', {'class': 'bp-Homecard__Stats--beds text-nowrap'}).text
            real_estate_info['bed'].append(bed)
        except: 
            real_estate_info['bed'].append(np.nan)
            incomplete_idx.append(i)   

        try:
            # Extract number of bathrooms
            bath = box.find('span', {'class': 'bp-Homecard__Stats--baths text-nowrap'}).text
            real_estate_info['bath'].append(bath)
        except: 
            real_estate_info['bath'].append(np.nan)
            incomplete_idx.append(i)   

        try:
            # Extract square footage (locked stats section)
            sqr_footage = box.find('span', {'class': 'bp-Homecard__LockedStat--value'}).text
            real_estate_info['sqr_footage'].append(sqr_footage)
        except:
            real_estate_info['sqr_footage'].append(np.nan)
            incomplete_idx.append(i)   

        try:
            # Extract property link (prepend base URL)
            property_link = "https://www.redfin.com" + box.find("a").get('href')
            real_estate_info['property_link'].append(property_link)
        except:
            real_estate_info['property_link'].append(np.nan)
            incomplete_idx.append(i)

    return incomplete_idx



def calculate_min_pages(total_count, items_per_page):
    """
    Calculates the minimum number of pages required to display all items.

    Parameters:
    total_count (int): The total number of items to be displayed.
    items_per_page (int): The maximum number of items that can be displayed per page.

    Returns:
    int: The minimum number of pages required.
    """
    
    # Use integer division to determine the number of pages needed
    # Adding (items_per_page - 1) ensures proper rounding up
    return (total_count + items_per_page - 1) // items_per_page




def extracting_by_batch(head, batch_num, divisions_longs=15, devision_lats=15, splitted_big_box = 0):
    """
    Extracts real estate listing data from Redfin in batches using predefined coordinate grids.

    Parameters:
    head (dict): Headers for the HTTP requests.
    batch_num (int): The number of batches to divide the coordinate boxes into.
    test_batch_index (list, optional): The range of batch indices to process. Defaults to [0,1].

    Returns:
    tuple: (real_estate_info, missing_entries, big_coord_boxes)
        - real_estate_info (dict): A dictionary storing extracted real estate information.
        - missing_entries (dict): A dictionary tracking missing entries for incomplete pages.
        - big_coord_boxes (list): A list of coordinate boxes requiring further subdivision.
    """
    
    big_coord_boxes = []  # Stores coordinate boxes where select listing count < total listing count
    real_estate_info = defaultdict(list)  # Dictionary to store extracted real estate information
    missing_entries = defaultdict(list)  # Dictionary to track missing data entries

    # Generate the coordinate grid for Vancouver and split into batches
    if splitted_big_box:
        coord_boxes = splitted_big_box

    else: coord_boxes = vancouver_grid(head, divisions_longs, devision_lats)
    
    coord_box_batch = np.array_split(coord_boxes, batch_num)

    # Iterate over the specified batch range
    for i in range(len(coord_box_batch)):
        batch = coord_box_batch[i]

        # Process each coordinate box in the batch
        for coord_box in batch:
            listing_info = listing_count(head, coord_box)
            time.sleep(1)  # Prevent overwhelming the server

            # Skip if there are no listings in the area
            if listing_info == 'no_listing':
                print(f"Batch {i}-{coord_box} has no listings.")
                continue
            else:
                viewport_url, select_listing_count, total_listing_count = listing_info

                # If the selected listing count is less than the total, store the coordinate box for further subdivision
                if select_listing_count != total_listing_count:
                    big_coord_boxes.append(coord_box)
                    continue
                else:
                    # Calculate the number of pages to crawl based on listings per page (assumed 9 per page)
                    max_page = calculate_min_pages(select_listing_count, items_per_page=9)
                    missing = defaultdict(list)  # Tracks missing indices for this coordinate box

                    # Crawl and extract data for each page
                    for page in range(1, max_page):
                        soup_boxes = crawling_redfin(head, viewport_url, page)                        
                        incomplete_idx = key_metric_extraction(soup_boxes, real_estate_info)

                        # Store any missing data indices
                        if incomplete_idx:
                            missing[f'page_{page}'].append(incomplete_idx)

                        time.sleep(1)  # Prevent overwhelming the server

                    # Store missing entries for this coordinate box
                    missing_entries[coord_box].append(missing)

    return real_estate_info, missing_entries, big_coord_boxes


def extraction_pipeline():
    """
    Execute a pipeline to extract real estate data by splitting geographic areas into batches and saving results.

    This function performs data extraction in two stages: first by processing larger geographic boxes,
    then by splitting those boxes into smaller ones for more detailed extraction. The results are saved
    as CSV files.

    Returns:
        None: This function does not return any value but saves the extracted data to CSV files.

    Notes:
        - Requires the `extracting_by_batch` function to fetch real estate data.
        - Assumes the `split_coordinate` function is defined to split geographic boxes.
        - Uses `pandas` (as `pd`) to handle data and save it to CSV.
        - Saves output to '../data/raw_extraction/' directory; ensure it exists before running.

    Example:
        extraction_pipeline()
        # Extracts data and saves to 'vancouver_real_estate_m1.csv' and 'vancouver_real_estate2_m1.csv'
    """
    # Define a user-agent header to mimic a browser request for web scraping
    head = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Perform initial extraction in batches over a grid of larger geographic boxes
    real_estate_info, missing_entries, big_coord_boxes = extracting_by_batch(
        head, batch_num=5, divisions_longs=6, divisions_lats=6
    )

    # Split each large geographic box into smaller boxes for detailed extraction
    splitted_boxes = []
    for big_box in big_coord_boxes:
        # Split the current big box into smaller boxes using a 2x2 grid
        splitted_box = split_coordinate(
            four_coords=1, divisions_longs=2, divisions_lats=2, if_big_box=big_box
        )
        splitted_boxes.append(splitted_box)
    # Flatten the list of lists into a single list of smaller boxes
    splitted_boxes = [x for ls in splitted_boxes for x in ls]

    # Perform a second extraction using the smaller, split boxes
    real_estate_info_big, missing_entries_big, big_coord_boxes_big = extracting_by_batch(
        head, batch_num=4, divisions_longs=1, divisions_lats=1, splitted_big_box=splitted_boxes
    )

    # Convert extracted data into pandas DataFrames for easy handling
    result = pd.DataFrame(real_estate_info)
    big_result = pd.DataFrame(real_estate_info_big)

    # Save the results to CSV files in the specified directory
    result.to_csv("../data/raw_extraction/vancouver_real_estate_m1.csv", index=False)
    big_result.to_csv("../data/raw_extraction/vancouver_real_estate2_m1.csv", index=False)
    
    
    