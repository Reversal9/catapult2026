import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchmetrics import R2Score
from dataset import SOLAR_MODEL_FEATURES, WIND_MODEL_FEATURES, get_wind_data


torch.manual_seed(67)
batch_size = 32
# train_loader, test_loader, ds_size = get_solar_data("data/processed/solar.csv", SOLAR_MODEL_FEATURES, batch_size=32)
train_loader, test_loader, ds_size = get_wind_data("data/processed/wind.csv", WIND_MODEL_FEATURES, batch_size=32)

# PyTorch models inherit from torch.nn.Module
class Habakkuk(nn.Module):
    def __init__(self, input_size):
        super(Habakkuk, self).__init__()
        self.fc1 = nn.Linear(input_size, 480)
        self.fc2 = nn.Linear(480, 100)
        self.fc3 = nn.Linear(100, 24)
        self.fc4 = nn.Linear(24, 6)
        self.fc5 = nn.Linear(6, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        x = F.relu(self.fc4(x))
        x = self.fc5(x)
        return x

def train_one_epoch(model, optimizer, loss_fn):
    running_loss = 0.
    total_batches = 0

    for i, (inputs, labels) in enumerate(train_loader):
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = loss_fn(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        total_batches += 1

    avg_loss = running_loss / total_batches
    return avg_loss

def test_loop(model):
    
    model.eval()
    loss_fn = nn.MSELoss()
    r2_metric = R2Score()
    
    running_loss = 0.0
    
    with torch.no_grad():
        for inputs, labels in test_loader:
            outputs = model(inputs)
            
            loss = loss_fn(outputs, labels)
            running_loss += loss.item()

            r2_metric.update(outputs, labels)
    
    avg_loss = running_loss / len(test_loader)
    r2_score = r2_metric.compute().item()
    
    print(f"Test MSE Loss: {avg_loss:.6f}")
    print(f"Test R² Score: {r2_score:.6f}")
    
    return avg_loss, r2_score

def train_loop(filename, epochs=100):
    
    model = Habakkuk(ds_size)
    loss_fn = nn.HuberLoss(delta=1.0)
    optimizer = optim.Adam(model.parameters(), lr=1e-2, weight_decay=1e-2)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=7
    )

    best_loss = float('inf')
    for epoch in range(1, epochs + 1):
        train_loss = train_one_epoch(model, optimizer, loss_fn)
        val_loss, val_r2 = test_loop(model)
        scheduler.step(val_loss)

        if val_loss < best_loss:
            best_loss = val_loss

        print(f"EPOCH {epoch:3d} | train={train_loss:.4f} | val={val_loss:.4f} | R²={val_r2:.4f} | lr={optimizer.param_groups[0]['lr']:.2e}")

    torch.save(model, "model/habakkuk/" + filename + ".dat")
    return model
    
model = train_loop(filename="solar")
test_loop(model)
