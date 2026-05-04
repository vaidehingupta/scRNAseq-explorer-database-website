# scRNA-seq Explorer: iPSC-derived Alzheimer's Disease Models

Developed by **Team 14** in collaboration with the **[TCW Laboratory](https://sites.bu.edu/tcwlab/)** at Boston University (BF768).

## Team 14 Members
* Wendy Bui
* Chloe Ploss
* Vaidehi Gupta
* Mildred Monsivais

## Project Overview
The scRNA-seq Explorer is an interactive web application designed for investigating cellular heterogeneity and genotype-associated differences in iPSC-derived Alzheimer's disease models. 

By integrating cell-type annotation, gene expression across **19,429 filtered genes** and sample-level composition, this platform enables users to explore how the **APOE genotype** (APOE 33 vs. APOE 44) influences cell population structure and transcriptional activity across major neural cell types.

## Platform Features
* **Home:** Project overview, team attribution, and usage instructions.
* **Single-cell Expression:** Visualize cell clustering via UMAP across three genotype views (All, APOE 33, APOE 44) simultaneously. Supports **Violin, Dot, and Scatter plot** views to analyze gene distribution.
* **Multi-Gene Expression:** Compare expression patterns across up to 10 selected genes using interactive **Dot Plots** (size = % expressing, color = avg expression) or **Heatmaps** with custom genotype-specific color scales.
* **Cell Type Composition:** Display the relative abundance of each cell type per sample. Toggle between **Stacked Bar** and **Box Plot** views to identify shifts in cell population ratios.
* **Data Tables:** Queryable datasets for gene expression and cell proportions. Supports advanced filtering by genotype, cell type, and minimum expression, with **CSV export** functionality.

## Platform Architecture
* **Backend:** Python / Flask
* **Database:** MariaDB (Hosted on `bioed-new.bu.edu`)
* **Frontend:** HTML5, CSS3, JavaScript
* **Visualization:** Plotly.js
* **Data Source:** processed scRNA-seq outputs (UMAP coords and log-normalized expression values).

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-folder>
    ```

2.  **Install dependencies:**
    Ensure you have Python installed, then install the required packages:
    ```bash
    pip install flask pymysql
    ```

3.  **Database Configuration:**
    Open `app_final.py` and input your `bioed-new` credentials in the `DB_CONFIG` dictionary:
    ```python
    DB_CONFIG = {
        "host": "bioed-new.bu.edu",
        "user": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD",
        "database": "Team14",
        "port": 4253
    }
    ```

4.  **Run the Application:**
    ```bash
    python app_final.py
    ```
    Access the explorer at `http://localhost:5050` or the designated **[server url]([https://sites.bu.edu/tcwlab/](https://bioed-new.bu.edu/students_26/Team14/website/app)**.

## Notes about the Website
* **Interactivity:** All plots are interactive. Hovering over data points displays specific values. Clicking or double-clicking legend items allows you to toggle specific groups on or off.
* **Normalization:** All expression values are log-normalized.
* **Scales:** In the multi-gene tab, Blue represents APOE 33, Red represents APOE 44, and Purple represents the merged genotype view.

---
*Note: This project was developed as part of the BF768 curriculum at Boston University.* 
