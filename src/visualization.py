import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import folium
from folium.plugins import MarkerCluster


dimport matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker

def plot_distribution(
    df,
    column,
    title,
    xlabel,
    unit="",  # E.g., "$" for currency, "" for square footage
    bins=50,
    figsize=(10, 6),
    color='skyblue',
    quantile_clip=0.99,
    show_xlim=True
):
    """
    Plots a histogram with mean and median lines for a specified column.

    Parameters:
        df (pd.DataFrame): DataFrame containing the data.
        column (str): Column name to plot.
        title (str): Plot title.
        xlabel (str): X-axis label.
        unit (str): String to prepend to x-axis tick labels and stats (e.g., "$").
        bins (int): Number of bins in histogram.
        figsize (tuple): Size of the figure.
        color (str): Color of the histogram bars.
        quantile_clip (float): Right x-limit as quantile (e.g., 0.99 for 99th percentile).
        show_xlim (bool): Whether to clip the x-axis at quantile.
    """
    sns.set(style="whitegrid")
    data = df[column].dropna()

    plt.figure(figsize=figsize)
    plt.hist(data, bins=bins, color=color, edgecolor='black')

    plt.title(title, fontsize=16, fontweight='bold')
    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel("Number of Properties", fontsize=14)

    # Format x-axis with unit and thousands separator
    plt.gca().xaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, pos: f'{unit}{int(x):,}')
    )

    # Compute mean and median
    mean_val = data.mean()
    median_val = data.median()

    plt.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {unit}{mean_val:,.0f}')
    plt.axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'Median: {unit}{median_val:,.0f}')

    plt.legend()

    if show_xlim:
        plt.xlim(0, data.quantile(quantile_clip))

    plt.tight_layout()
    plt.show()
