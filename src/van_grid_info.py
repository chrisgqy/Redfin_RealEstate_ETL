import requests
from bs4 import BeautifulSoup
import re



def vancouver_grid(head, divisions_longs=15, devision_lats=15):
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

    # Calculate step size for dividing the area into grid cells
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
