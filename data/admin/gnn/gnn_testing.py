import os
import glob
import pandas as pd
import numpy as np
import torch
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv
from sklearn.preprocessing import OneHotEncoder
from math import radians, cos, sin, asin, sqrt
from sklearn.metrics import r2_score

# -----------------------------
# BASE PATHS
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, "testing_gnn", "year_month_files")

PARAM_FOLDERS = [
    "clpi_output","dpli_output","dss_output","isf_output","lfsf_output",
    "plaf_output","rdf_output","ri_output",
    "tddf_output","tsi_output","season_tag_output"
]

# -----------------------------
# HELPER: Haversine distance
# -----------------------------
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371
    return c * r

# -----------------------------
# LOAD ALL TEST FILES
# -----------------------------
test_files = sorted(glob.glob(os.path.join(TEST_DIR, "*.csv")))

# -----------------------------
# LOAD STATION ORDER (FIXED SAFE)
# -----------------------------
stations_file = os.path.join(BASE_DIR, "upstream_to_downstream_stations.csv")
stations_df = pd.read_csv(stations_file, header=None)

stations = stations_df.iloc[:, 0].astype(str).str.strip().tolist()
# -----------------------------
# SEASON ENCODER (same as training)
# -----------------------------
season_encoder = OneHotEncoder(sparse_output=False)
season_encoder.fit([['Winter'], ['Pre-monsoon'], ['Monsoon'], ['Post-monsoon']])

# -----------------------------
# BUILD GRAPH PER FILE
# -----------------------------
global_has_wqi = any("wqi" in pd.read_csv(f).columns for f in test_files)
test_graphs = []

for file in test_files:
    df = pd.read_csv(file)

    # -----------------------------
    # REORDER USING USER FILE (FIXED)
    # -----------------------------
    # safe filtering in case any station missing
    valid_stations = [s for s in stations if s in df["station"].values]
    df = df.set_index("station").loc[valid_stations].reset_index()

    # -----------------------------
    # BUILD EDGES (CHAIN GRAPH SAME AS TRAINING)
    # -----------------------------
    edges_index = []
    edges_weight = []
    num_stations = len(valid_stations)
    """
    for i in range(num_stations - 1):
        # forward edge (upstream → downstream)
        edges_index.append([i, i+1])
        # backward edge (optional but recommended)
        edges_index.append([i+1, i])

        edges_weight.append(1.0)
        edges_weight.append(1.0)
    """



    for i in range(num_stations - 1):

        # get coordinates from station name
        lon1, lat1 = map(float, valid_stations[i].split("_"))
        lon2, lat2 = map(float, valid_stations[i+1].split("_"))

        # compute distance
        dist = haversine(lon1, lat1, lon2, lat2)

        # compute weight (same as training)
        weight = 1.0 / (dist + 1e-6)

        # forward edge
        edges_index.append([i, i+1])
        edges_weight.append(1.0)
        # backward edge
        edges_index.append([i+1, i])
        edges_weight.append(1.0)


    edge_index = torch.tensor(edges_index, dtype=torch.long).t().contiguous()
    edge_weight = torch.tensor(edges_weight, dtype=torch.float)
    
    # -----------------------------
    # NODE FEATURES
    # -----------------------------
    node_features = []
    target = []
    
    has_wqi = "wqi" in df.columns
    for _, row in df.iterrows():
        feat = []

        for col in ["clpi","dpli","dss","isf","lfsf","plaf","rdf","ri","tsi","sgp"]:
          val = row[col]
          if pd.isna(val):
             val = 0.0
          feat.append(float(val))
          
          
        val = row["season_tag"]

        if pd.isna(val):
            val = "Winter"

        val = str(val).strip()

        if val not in ["Winter", "Pre-monsoon", "Monsoon", "Post-monsoon"]:
            val = "Winter"

        val_onehot = season_encoder.transform([[val]])[0]        
                
                
        feat.extend(val_onehot)

        node_features.append(feat)

        if has_wqi:
                val = row["wqi"]
                if pd.isna(val):
                    val = np.nan
                target.append(float(val) if not pd.isna(val) else np.nan)
        else:
                target.append(np.nan)
        

    x = torch.tensor(node_features, dtype=torch.float)
    
    """
    import numpy as np

    low_features = np.load("low_features.npy")

    high_features = [i for i in range(x.shape[1]) if i not in low_features]
    x = x[:, high_features]
    """   
        
    y = torch.tensor(target, dtype=torch.float).unsqueeze(1)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_weight, y=y)

    # 🔥 FIX: store station names inside graph
    data.station_names = valid_stations

    name = os.path.basename(file).replace(".csv","")
    year, month = name.split("_")
    data.year = int(year)
    data.month = month

    test_graphs.append(data)

# -----------------------------
# MODEL (EXACT SAME AS TRAINING)
# -----------------------------
import torch.nn as nn
import torch.nn.functional as F

class WQIGNN(nn.Module):
    def __init__(self, in_channels, hidden_channels=64, out_channels=1, num_layers=3):
        super(WQIGNN, self).__init__()
        self.convs = nn.ModuleList()
        self.convs.append(SAGEConv(in_channels, hidden_channels))
        for _ in range(num_layers-1):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
        self.fc = nn.Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):

        for conv in self.convs:
            x_new = conv(x, edge_index)

            if x.shape == x_new.shape:
                x = x + x_new
            else:
                x = x_new

            x = F.relu(x)
            x = F.dropout(x, p=0.3, training=self.training)

        return self.fc(x)

# -----------------------------
# LOAD MODEL
# -----------------------------
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
in_channels = test_graphs[0].x.shape[1]

model = WQIGNN(in_channels=in_channels, hidden_channels=64).to(device)
model.load_state_dict(torch.load("graphsage_model.pth"))
model.eval()

# -----------------------------
# TESTING LOOP
# -----------------------------
from sklearn.metrics import mean_squared_error, mean_absolute_error

records = []

with torch.no_grad():
    for graph in test_graphs:
        graph = graph.to(device)
        out = model(graph.x, graph.edge_index)

        y_true = graph.y.cpu().numpy().flatten()
        y_pred = out.cpu().numpy().flatten()

        # 🔥 loop over each station/node
        for i in range(len(y_true)):
            records.append({
                "Station": graph.station_names[i],   # ✅ FIXED
                "Year": graph.year,
                "Month": graph.month if hasattr(graph, "month") else "NA",
                "Actual": y_true[i],
                "Predicted": y_pred[i],
                "Error": abs(y_true[i] - y_pred[i])
            })

# -----------------------------
# Convert to DataFrame
# -----------------------------
df = pd.DataFrame(records)

# -----------------------------
# Metrics
# -----------------------------
if global_has_wqi:
    
    valid_df = df.dropna(subset=["Actual"])

    if len(valid_df) > 0:
        mae = mean_absolute_error(valid_df["Actual"], valid_df["Predicted"])
        rmse = np.sqrt(mean_squared_error(valid_df["Actual"], valid_df["Predicted"]))
        r2 = r2_score(valid_df["Actual"], valid_df["Predicted"])

        print(f"\nTest Results:")
        print(f"MAE = {mae:.6f}, RMSE = {rmse:.6f}, R2 = {r2:.6f}")
    else:
        print("⚠️ No valid WQI values")

else:
    print("⚠️ WQI not present → skipping metrics")



# -----------------------------
# Print sample
# -----------------------------
print("\nSample Predictions:")
print(df.head(20))

# -----------------------------
# SAVE CSV
# -----------------------------
df.to_csv("wqi_predictions_detailed_test_graphsage.csv", index=False)
print("\nSaved to wqi_predictions_detailed_test_graphsage.csv")