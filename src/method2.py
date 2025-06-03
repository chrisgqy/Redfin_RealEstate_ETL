import json
import numpy as np
from collections import defaultdict
import time
from common_functions import (
    vancouver_grid, 
    listing_count, 
    crawling_redfin, 
    calculate_min_pages
)


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
                        
                        time.sleep(1)  # Prevent overwhelming the server
    
    # Return extracted information
    return result, result_event, result_event_list, big_coord_boxes, url_with_issue


def extraction_pipeline_method2():
    """
    Execute a pipeline to extract real estate data using method 2 approach with JSON-LD extraction.

    This function performs data extraction in two stages: first by processing larger geographic boxes,
    then by splitting those boxes into smaller ones for more detailed extraction. Uses JSON-LD
    structured data extraction method.

    Returns:
        None: This function does not return any value but saves the extracted data to CSV files.

    Notes:
        - Uses the extracting_by_batch_method2 function to fetch real estate data.
        - Assumes the split_coordinate function is defined to split geographic boxes.
        - Uses pandas to handle data and save it to CSV.
        - Saves output to '../data/raw_extraction/' directory; ensure it exists before running.
    """
    import pandas as pd
    from common_functions import split_coordinate
    
    # Define a user-agent header to mimic a browser request for web scraping
    head = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Perform initial extraction in batches over a grid of larger geographic boxes
    result, result_event, result_event_list, big_coord_boxes, url_with_issue = extracting_by_batch_method2(
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
    result_big, result_event_big, result_event_list_big, big_coord_boxes_big, url_with_issue_big = extracting_by_batch_method2(
        head, batch_num=4, divisions_longs=1, divisions_lats=1, splitted_big_box=splitted_boxes
    )

    # Convert extracted data into pandas DataFrames for easy handling
    main_result = pd.DataFrame(result)
    event_result = pd.DataFrame(result_event)
    event_list_result = pd.DataFrame(result_event_list)
    
    main_result_big = pd.DataFrame(result_big)
    event_result_big = pd.DataFrame(result_event_big)
    event_list_result_big = pd.DataFrame(result_event_list_big)

    # Save the results to CSV files in the specified directory
    main_result.to_csv("../data/raw_extraction/vancouver_real_estate_main_m2.csv", index=False)
    event_result.to_csv("../data/raw_extraction/vancouver_real_estate_event_m2.csv", index=False)
    event_list_result.to_csv("../data/raw_extraction/vancouver_real_estate_event_list_m2.csv", index=False)
    
    main_result_big.to_csv("../data/raw_extraction/vancouver_real_estate_main2_m2.csv", index=False)
    event_result_big.to_csv("../data/raw_extraction/vancouver_real_estate_event2_m2.csv", index=False)
    event_list_result_big.to_csv("../data/raw_extraction/vancouver_real_estate_event_list2_m2.csv", index=False)