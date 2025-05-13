# 🏙️ Vancouver Redfin Real Estate Crawler

Welcome to the Vancouver Redfin Grid Crawler – a Python-based project that transforms real estate exploration into a data-driven adventure.

This project scrapes real-time listing data from [Redfin](https://www.redfin.ca), dynamically slicing up the Vancouver city map into intelligent latitude-longitude grids to ensure comprehensive and complete data coverage. Whether you're a real estate enthusiast, data analyst, or urban planner – this tool is your launchpad to deeper insights on the Vancouver housing market.

---

## 🚀 Why I Built This

I was curious:  
**"How many listings are really out there on Redfin?"**  
Turns out, when you zoom into different neighborhoods, Redfin's listings count and availability changes dramatically.

So I built a crawler that:

- Maps out Vancouver using Open Data's official city boundary
- Divides it into a grid (like tiles on Google Maps)
- Systematically queries each tile on Redfin to extract real estate listings
- Finally, scrapes details like price, beds, baths, square footage, ZIP code, and more

---

## 🧠 Key Features

- 📦 **Geospatial Grid Crawler**: Splits Vancouver into latitude-longitude bounding boxes using Open Data API.
- 🧭 **Adaptive Viewport Querying**: Detects areas with active listings using Redfin’s viewport filtering.
- 🕵️‍♂️ **Real Estate Data Extraction**: Scrapes detailed property information using BeautifulSoup.
- 💡 **Error-Resistant**: Skips failed extractions while logging incomplete entries for review.
- 🧰 **Modular Design**: Clean Python functions with helpful docstrings and flexible parameters.

---

## 🗺️ How It Works

### ✅ 1. Get Vancouver's Boundary  
The script fetches official city borders using the City of Vancouver's Open Data API.

### 🧱 2. Divide into Grids  
The boundary box is split into subregions (grid cells) using `split_coordinate()`.

### 🔍 3. Query Each Grid Box  
Each grid cell is queried on Redfin using viewport-specific URLs.

### 🏡 4. Extract Listing Data  
For each listing, it scrapes:
- Address 🏡  
- ZIP Code 📮  
- Price 💰  
- Bedrooms 🛏️  
- Bathrooms 🛁  
- Square Footage 📐  
- Property URL 🔗

---

## 🧪 Example Use Case

```python
head = {
    'User-Agent': 'Mozilla/5.0',
    'Accept-Language': 'en-US,en;q=0.9'
}

# Step 1: Generate bounding boxes for Vancouver
coord_boxes = vancouver_grid(head, divisions_longs=10, devision_lats=10)

# Step 2: For each box, get listing stats
for box in coord_boxes:
    result = listing_count(head, box)
    if result != 'no_listing':
        url, shown_count, total_count = result
        for page in range(1, (total_count // 20) + 2):
            soup = crawling_redfin(head, url, page)
            metrics_extraction_m1(soup, real_estate_info)
```

## 📁 Project Structure
.
├── crawler.py               # Main script with all functions
├── README.md                # You're reading it!
├── requirements.txt         # Python dependencies (optional)


## 🧰 Dependencies
- pandas
- numpy
- requests
- beautifulsoup4

Install all dependencies with:
```
pip install -r requirements.txt
```

## ⚠️ Disclaimer
This project is for educational and research purposes.
Respect Redfin’s Terms of Use – excessive or automated scraping may violate their policies.
Use responsibly.

## 💬 Let’s Connect
Love real estate + data? Let’s collaborate on real-world urban data projects!
Feel free to open issues, suggest improvements, or fork the repo 🌟

## 📌 To-Do
- Save output as .csv or .json
- Add retries for failed HTTP requests
- Build a visualization dashboard (e.g., Folium or Plotly)
- Dockerize the crawler for scalable deployment