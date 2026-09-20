import os
import glob
import pandas as pd
import numpy as np
import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from torch_geometric.nn import SAGEConv
from sklearn.preprocessing import OneHotEncoder
from math import radians, cos, sin, asin, sqrt

# -----------------------------
# BASE PATHS
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_DIR = os.path.join(BASE_DIR, "training_gnn")   # ✅ ONLY CHANGE


# -----------------------------
# LOAD STATION ORDER (NEW)
# -----------------------------
stations_file = os.path.join(BASE_DIR, "upstream_to_downstream_stations.csv")
stations_df = pd.read_csv(stations_file, header=None)

all_stations = stations_df.iloc[:, 0].astype(str).str.strip().tolist()

print(f"Total stations from file: {len(all_stations)}")



PARAM_FOLDERS = [
    "clpi_output","dpli_output","dss_output","isf_output","lfsf_output",
    "plaf_output","rdf_output","ri_output",
    "tsi_output",
    "sgp_output",
    "season_tag_output"
]

WQI_FOLDER = "wqi_normalized"

# -----------------------------
# HELPER: Haversine distance
# -----------------------------
def haversine(lon1, lat1, lon2, lat2):
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of earth in km
    return c * r

# -----------------------------
# 1. Collect stations
# -----------------------------
"""
all_stations = None
for folder in PARAM_FOLDERS + [WQI_FOLDER]:
    folder_path = os.path.join(TRAIN_DIR, folder)
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    stations = [os.path.basename(f).replace(".csv","") for f in files]

    if all_stations is None:
        all_stations = set(stations)
    else:
        all_stations = all_stations.intersection(set(stations))

all_stations = sorted(all_stations, key=lambda s: float(s.split("_")[0]), reverse=True)
print(f"Total common stations: {len(all_stations)}")
"""
# -----------------------------
# 2. Load parameter values per station
# -----------------------------
param_data = {p:{} for p in PARAM_FOLDERS}

for folder in PARAM_FOLDERS:
    folder_path = os.path.join(TRAIN_DIR, folder)
    for station in all_stations:
        file_path = os.path.join(folder_path, f"{station}.csv")
        df = pd.read_csv(file_path)
        param_data[folder][station] = df.set_index('Year') # year index, months as columns

# -----------------------------
# 3. Load WQI
# -----------------------------
wqi_data = {}
wqi_path = os.path.join(TRAIN_DIR, WQI_FOLDER)

for station in all_stations:
    file_path = os.path.join(wqi_path, f"{station}.csv")
    df = pd.read_csv(file_path)
    wqi_data[station] = df.set_index('Year')

# -----------------------------
# 1. Parse station coordinates from names
# -----------------------------
station_coords = {}
for s in all_stations:
    lon, lat = map(float, s.split("_"))
    station_coords[s] = (lon, lat)

# -----------------------------
# 2. Create all (year, month) combinations
# -----------------------------
years_months = set()
months_order = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

for folder in PARAM_FOLDERS:
    if folder == "season_tag_output":
        continue
    for station in all_stations:
        df = param_data[folder][station]
        for year in df.index:
            for month in df.columns:
                if not pd.isna(df.loc[year, month]):
                    years_months.add((year, month))

years_months = sorted(list(years_months), key=lambda x: (x[0], months_order.index(x[1])))
print(f"Total (year,month) graphs: {len(years_months)}")


"""
# -----------------------------
# 3. Build edges (directed along river flow, weighted by distance)
# Assuming stations are sorted upstream → downstream
# -----------------------------
edges_index = []
edges_weight = []
num_stations = len(all_stations)

for i in range(num_stations):
    for j in range(i+1, num_stations):  # directed i->j
        lon1, lat1 = station_coords[all_stations[i]]
        lon2, lat2 = station_coords[all_stations[j]]
        d = haversine(lon1, lat1, lon2, lat2)
        if d==0:
            w = 1.0
        else:
            w = 1.0 / d
        edges_index.append([i,j])
        edges_weight.append(w)

edge_index = torch.tensor(edges_index, dtype=torch.long).t().contiguous()
edge_weight = torch.tensor(edges_weight, dtype=torch.float)
print(f"Edge index shape: {edge_index.shape}, Edge weight shape: {edge_weight.shape}")
"""

# -----------------------------
# 3. Build edges (CHAIN GRAPH - FIXED)
# -----------------------------
edges_index = []
edges_weight = []
num_stations = len(all_stations)

for i in range(num_stations - 1):

    lon1, lat1 = station_coords[all_stations[i]]
    lon2, lat2 = station_coords[all_stations[i + 1]]

    dist = haversine(lon1, lat1, lon2, lat2)

    # avoid divide-by-zero
    """
    if dist < 1e-6:
        weight = 1.0
    else:
        weight = 1.0 
    """
    weight = 1.0 / (dist + 1e-6)

    # forward edge (upstream → downstream)
    edges_index.append([i, i + 1])
    edges_weight.append(1.0)

    # backward edge (downstream → upstream)
    edges_index.append([i + 1, i])
    edges_weight.append(1.0)

edge_index = torch.tensor(edges_index, dtype=torch.long).t().contiguous()
edge_weight = torch.tensor(edges_weight, dtype=torch.float)

print(f"Edge index shape: {edge_index.shape}, Edge weight shape: {edge_weight.shape}")
# -----------------------------
# 4. Build PyG Data objects
# -----------------------------
graphs = []

"""
season_encoder = LabelEncoder()
season_encoder.fit(['Winter','Pre-monsoon','Monsoon','Post-monsoon'])
"""
from sklearn.preprocessing import OneHotEncoder

season_encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
season_encoder.fit([['Winter'], ['Pre-monsoon'], ['Monsoon'], ['Post-monsoon']])
for year, month in years_months:
    node_features = []
    target = []

    for station in all_stations:
        feat = []

        for folder in PARAM_FOLDERS:
            df = param_data[folder][station]

            if folder == "season_tag_output":
                val = df.loc[year, month]

                if pd.isna(val):
                    val = "Winter"

                val = str(val).strip()

                if val not in ["Winter", "Pre-monsoon", "Monsoon", "Post-monsoon"]:
                    val = "Winter"

                val_onehot = season_encoder.transform([[val]])[0]
                feat.extend(val_onehot)

            else:
                val = df.loc[year, month]
                feat.append(float(val) if not pd.isna(val) else 0.0)

        node_features.append(feat)

        # WQI target
        wqi_val = wqi_data[station].loc[year, month]
        target.append(float(wqi_val) if not pd.isna(wqi_val) else 0.0)

    x = torch.tensor(node_features, dtype=torch.float)

    y = torch.tensor(target, dtype=torch.float).unsqueeze(1)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_weight, y=y)
    data.year = year
    data.month = month
    graphs.append(data)

print(f"Built {len(graphs)} graph objects.")

# -----------------------------
# TRAIN / VAL SPLIT
# -----------------------------
# -----------------------------
# TIME-BASED SPLIT (NO LEAKAGE)
# -----------------------------

graphs = sorted(graphs, key=lambda g: (g.year, g.month))

split_idx = int(len(graphs) * 0.8)

train_graphs = graphs[:split_idx]
val_graphs = graphs[split_idx:]

print(f"Train graphs: {len(train_graphs)}, Validation graphs: {len(val_graphs)}")

from torch_geometric.loader import DataLoader  # fixed import

train_loader = DataLoader(train_graphs, batch_size=4, shuffle=True)
val_loader = DataLoader(val_graphs, batch_size=4)


# -----------------------------
# MODEL
# -----------------------------
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, SAGEConv

class WQIGNN(nn.Module):
    def __init__(self, in_channels, hidden_channels=64, out_channels=1, num_layers=3):
        super(WQIGNN, self).__init__()
        self.convs = nn.ModuleList()
        self.convs.append(SAGEConv(in_channels, hidden_channels))
        for _ in range(num_layers-1):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
        self.fc = nn.Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):

        for i, conv in enumerate(self.convs):
            x_new = conv(x, edge_index)

            # apply residual ONLY if shapes match
            if x.shape == x_new.shape:
                x = x + x_new
            else:
                x = x_new

            x = F.relu(x)
            x = F.dropout(x, p=0.3, training=self.training)

        return self.fc(x)
    
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
##model = WQIGNN(in_channels=len(PARAM_FOLDERS), hidden_channels=64).to(device)
in_channels = graphs[0].x.shape[1]  # dynamically set input channels
model = WQIGNN(in_channels=in_channels, hidden_channels=64).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
##criterion = nn.MSELoss()
criterion = nn.MSELoss()

epochs = 500
best_val_loss = float("inf")
best_epoch = -1
counter = 0
patience = 30
min_save_epoch = 300

for epoch in range(1, epochs+1):
    model.train()
    total_loss = 0
    for batch in train_loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        out = model(batch.x, batch.edge_index)
        #loss = criterion(out, batch.y)

        
        # Base loss (element-wise)
        #base_loss = F.smooth_l1_loss(out, batch.y, reduction='none')

        base_loss = (out - batch.y) ** 2

        #changing to huber loss
         # Huber loss (element-wise)
        #base_loss = F.smooth_l1_loss(out, batch.y, reduction='none')

        # Create weights (focus more on high WQI)
        weights = 1 + 2 * (batch.y - 0.5).abs()
     

        # Apply weighting
        loss = (weights * base_loss).mean()
        

        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    total_loss /= len(train_loader)

    # Validation
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for batch in val_loader:
            batch = batch.to(device)
            out = model(batch.x, batch.edge_index)
            #base_loss = F.smooth_l1_loss(out, batch.y, reduction='none')
            base_loss = (out - batch.y) ** 2
            weights = 1 + 2 * (batch.y - 0.5).abs()
            loss = (weights * base_loss).mean()

            val_loss += loss.item()
    val_loss /= len(val_loader)

    print(f"Epoch {epoch:03d}, Train Loss: {total_loss:.4f}, Val Loss: {val_loss:.4f}")

    # -----------------------------
    # BEST MODEL SAVING (ONLY AFTER 300 EPOCHS)
    # -----------------------------
    if epoch >= min_save_epoch:

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            torch.save(model.state_dict(), "graphsage_model.pth")
            counter = 0
            print("Saved best model")
        else:
            counter += 1

    # -----------------------------
    # EARLY STOPPING (AFTER MINIMUM TRAINING)
    # -----------------------------
    if epoch >= min_save_epoch and counter >= patience:
        print(f"Early stopping triggered at epoch {epoch}")
        print(f"Best epoch was {best_epoch} with val loss {best_val_loss:.6f}")
        break


"""
# -----------------------------
# TRAINING LOOP
# -----------------------------
for epoch in range(1, 251):
    model.train()
    total_loss = 0

    for batch in train_loader:
        batch = batch.to(device)

        optimizer.zero_grad()
        out = model(batch.x, batch.edge_index, batch.edge_attr)

        base_loss = (out - batch.y) ** 2
        weights = 1 + 8 * (batch.y > 0.7).float()
        loss = (weights * base_loss).mean()

        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    total_loss /= len(train_loader)

    model.eval()
    val_loss = 0

    with torch.no_grad():
        for batch in val_loader:
            batch = batch.to(device)
            out = model(batch.x, batch.edge_index, batch.edge_attr)
            val_loss += criterion(out, batch.y).item()

    val_loss /= len(val_loader)

    print(f"Epoch {epoch}: Train {total_loss:.4f}, Val {val_loss:.4f}")

# -----------------------------
# SAVE MODEL
# -----------------------------
torch.save(model.state_dict(), "gnn_model.pth")
print("Model saved")
"""