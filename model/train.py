import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from datetime import datetime
from torchmetrics import R2Score
import dataset
from dataset import SOLAR_MODEL_FEATURES, WIND_MODEL_FEATURES

batch_size = 32
train_loader, test_loader, ds_size = dataset.get_data("data/processed/solar.csv", SOLAR_MODEL_FEATURES, batch_size=32)

import torch.nn as nn
import torch.nn.functional as F

# PyTorch models inherit from torch.nn.Module
class Habakkuk(nn.Module):
    def __init__(self, input_size):
        super(Habakkuk, self).__init__()
        self.fc1 = nn.Linear(input_size, 48)
        self.fc2 = nn.Linear(48, 24)
        self.fc3 = nn.Linear(24, 12)
        self.fc4 = nn.Linear(12, 6)
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

def train_loop():
    
    model = Habakkuk(ds_size)
    loss_fn = nn.MSELoss()  # mean square error
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    EPOCHS = 100

    for epoch in range(0, EPOCHS):
        model.train(True)
        avg_loss = train_one_epoch(model, optimizer, loss_fn)
        print(f'EPOCH {epoch + 1}, LOSS: {avg_loss}')

    return model
    
model = train_loop()
test_loop(model)
torch.save(model, "model/habakkuk/model.dat")