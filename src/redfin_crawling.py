import numpy as np
from collections import defaultdict
import requests 
from bs4 import BeautifulSoup
import time


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

    # Extract all property listing containers
    soup_boxes = soup.find_all("div", {"class": "HomeCardContainer"})

    return soup_boxes


def key_metric_extraction(soup_boxes, real_estate_info):
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


def extracting_by_batch(head, batch_num, test_batch_index=[0,1]):
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
    coord_boxes = vancouver_grid(head)
    coord_box_batch = np.array_split(coord_boxes, batch_num)

    # Iterate over the specified batch range
    for i in range(test_batch_index[0], test_batch_index[1]):
        batch = coord_box_batch[i]

        # Process each coordinate box in the batch
        for coord_box in batch:
            listing_info = listing_count(head, coord_box)
            time.sleep(1)  # Prevent overwhelming the server

            # Skip if there are no listings in the area
            if listing_info == 'no_listing':
                print(f"Batch {i} has no listings.")
                continue
            else:
                viewport_url, select_listing_count, total_listing_count = listing_info

                # If the selected listing count is less than the total, store the coordinate box for further subdivision
                if select_listing_count != total_listing_count:
                    big_coord_boxes.append(coord_boxes)
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