import pandas as pd
import numpy as np
import re
import json
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
import time

def split_coordinate(four_coords, divisions_longs, devision_lats, if_big_box):
    
    if if_big_box:
        [min_latitude, max_latitude, min_longitude, max_longitude] = [float(x) for x in if_big_box.split(':')]
    else:
         [min_latitude, max_latitude, min_longitude, max_longitude] = four_coords

    longitude_step = (max_longitude - min_longitude) / divisions_longs
    latitude_step = (max_latitude - min_latitude) / devision_lats  # Typo: should be "divisions_lats"

    coord_boxes = []
    
    # Generate bounding boxes for each grid cell
    for i in range(divisions_longs):
        for j in range(devision_lats):
            box_min_lat = round(min_latitude + j * latitude_step, 5)
            box_max_lat = round(min_latitude + (j + 1) * latitude_step, 5)
            box_min_lon = round(min_longitude + i * longitude_step, 5)
            box_max_lon = round(min_longitude + (i + 1) * longitude_step, 5)

            # Store bounding box as a string in the format "min_lat:max_lat:min_lon:max_lon"
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



def metrics_extraction(result, result_event, result_event_list, further_invest, soup):
    """
    Extract structured metadata from web pages using JSON-LD script tags.

    This function parses JSON-LD script tags in a BeautifulSoup object to extract 
    structured information about events, properties, and other entities.

    Args:
        result (dict): Dictionary to store extracted property information.
        result_event (dict): Dictionary to store extracted event information.
        result_event_list (dict): Dictionary to store alternative event information.
        further_invest (list): List to collect items that couldn't be fully processed.
        soup (BeautifulSoup): Parsed HTML document to extract metadata from.

    Returns:
        None: Modifies input dictionaries and list in-place.
    """
    # Find all JSON-LD script tags and parse their contents
    info = soup.find_all('script', {'type':'application/ld+json'})
    info = [json.loads(i.string) for i in info]

    # Iterate through each parsed JSON-LD item
    for j, i in enumerate(info):
        # Process dictionary-type items
        if isinstance(i, dict):
            # Get the type of the current item
            type_i = i.get('@type')
            
            # Skip Organization and BreadcrumbList types
            if type_i in ['Organization', 'BreadcrumbList']:
                continue
            
            # Process Event type items
            elif type_i == 'Event':
                # Handle location information
                location = i.get('location')
            
                # Process list-type location
                if isinstance(location, list):
                    try:
                        # Extract detailed location information
                        address = location[1].get('address').get('streetAddress')
                        postalCode = location[1].get('address').get('postalCode')
                        latitude = location[1].get('geo').get('latitude')
                        longitude = location[1].get('geo').get('longitude')
                        url = i.get('url')

                        # Store extracted information in result_event_list
                        result_event_list['address'].append(address)
                        result_event_list['postalCode'].append(postalCode)
                        result_event_list['latitude'].append(latitude)
                        result_event_list['longitude'].append(longitude)
                        result_event_list['url'].append(url)
                    except:
                        # Collect items that couldn't be processed
                        further_invest.append((j, i))
                
                # Process dictionary-type location
                else:
                    try:
                        # Extract location and event details
                        address = location.get('name')
                        postalCode = location.get('address').get('postalCode') 
                        latitude = location.get('geo').get('latitude')
                        longitude = location.get('geo').get('longitude')
                        price = i.get('offers').get('price')
                        url = i.get('url')
                        
                        # Store extracted information in result_event
                        result_event['address'].append(address)
                        result_event['postalCode'].append(postalCode)
                        result_event['latitude'].append(latitude)
                        result_event['longitude'].append(longitude)
                        result_event['price'].append(price)
                        result_event['url'].append(url)
                
                    except:
                        # Collect items that couldn't be processed
                        further_invest.append(i)

        # Process list-type items (likely property information)
        elif isinstance(i, list):
            try: 
                # Extract property details from first item in the list
                i_1 = i[0]
                address = i_1.get('address').get('streetAddress')
                postalCode = i_1.get('address').get('postalCode')
                latitude = i_1.get('geo').get('latitude')
                longitude = i_1.get('geo').get('longitude')
                sqr_footage = i_1.get('floorSize').get('value')
                bedrooms = i_1.get('numberOfRooms')
                url = i_1.get('url')
                
                # Extract price from second item in the list
                i_2 = i[1]
                price = i_2.get('offers').get('price')

                # Store extracted property information
                result['address'].append(address)
                result['postalCode'].append(postalCode)
                result['latitude'].append(latitude)
                result['longitude'].append(longitude)
                result['price'].append(price)
                result['square_footage'].append(sqr_footage)
                result['bedroom'].append(bedrooms)
                result['url'].append(url)
            
            except:
                # Collect items that couldn't be processed
                further_invest.append((j,i))


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


def extracting_by_batch_method2(head, batch_num, divisions_longs=15, divisions_lats=15, splitted_big_box=0):
    """
    Extract real estate listing information by dividing the area into batches and grid cells.

    This function breaks down a geographic area into smaller grid cells, then processes 
    these cells in batches to extract real estate listing information from Redfin.

    Args:
        head (dict): Headers for web requests.
        batch_num (int): Number of batches to split the coordinate boxes into.
        divisions_longs (int, optional): Number of divisions along longitude. Defaults to 15.
        divisions_lats (int, optional): Number of divisions along latitude. Defaults to 15.
        splitted_big_box (list, optional): Pre-defined coordinate boxes. Defaults to 0.

    Returns:
        tuple: A tuple containing:
            - result (dict): Main property listing information
            - result_event (dict): Event-related listing information
            - result_event_list (dict): Alternative event listing information
            - big_coord_boxes (list): Coordinate boxes with more than one page of listings
            - url_with_issue (list): URLs that encountered issues during extraction
    """
    # Initialize data containers
    big_coord_boxes = []  
    result_event = defaultdict(list)
    result_event_list = defaultdict(list)
    result = defaultdict(list)
    url_with_issue = []

    # Determine coordinate boxes
    if splitted_big_box:
        # Use pre-defined coordinate boxes if provided
        coord_boxes = splitted_big_box
    else:
        # Generate coordinate boxes using vancouver_grid function
        coord_boxes = vancouver_grid(head, divisions_longs, divisions_lats)
    
    # Split coordinate boxes into batches
    coord_box_batch = np.array_split(coord_boxes, batch_num)
    
    # Process each batch of coordinate boxes
    for i in range(len(coord_box_batch)):
        batch = coord_box_batch[i]
        
        # Process each coordinate box in the current batch
        for coord_box in batch:
            # Check the number of listings in the current coordinate box
            listing_info = listing_count(head, coord_box)
            time.sleep(1)  # Add a small delay to prevent overwhelming the server
            
            # Skip if no listings are found
            if listing_info == 'no_listing':
                print(f"Batch {i}-{coord_box} has no listings.")
                continue
            
            else:
                # Unpack listing information
                viewport_url, select_listing_count, total_listing_count = listing_info
                
                # If the number of selected listings doesn't match total listings
                # mark the coordinate box for further investigation
                if select_listing_count != total_listing_count:
                    big_coord_boxes.append(coord_box)
                    continue            
                
                else:
                    # Calculate the number of pages to crawl 
                    # Assumes 9 listings per page
                    max_page = calculate_min_pages(select_listing_count, items_per_page=9)
                    
                    # Crawl each page of listings
                    for page in range(1, max_page):
                        # Fetch the page content
                        soup = crawling_redfin(head, viewport_url, page)
                        
                        # Extract metrics from the page
                        metrics_extraction(
                            result, 
                            result_event, 
                            result_event_list, 
                            url_with_issue, 
                            soup
                        )
    
    # Return extracted information
    return result, result_event, result_event_list, big_coord_boxes, url_with_issue