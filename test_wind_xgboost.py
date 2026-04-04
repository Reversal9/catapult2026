import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_squared_error
import xgboost as xgb

# ── Config ────────────────────────────────────────────────────────────────────

DATA_PATH = "data/processed/wind.csv"
TARGET    = "avg_annual_generation"
SEED      = 42

WIND_DATA_FEATURES = ["t_cap", "t_hh", "t_rd", "t_rsa", "t_ttlh"]
WIND_CLIMATE_FEATURES = [
    "climate_annual_temperature_c",
    "climate_annual_relative_humidity_pct",
    "climate_annual_total_precipitation_mm",
    "climate_annual_snowfall_mm",
    "climate_annual_cloud_cover_pct",
    "climate_annual_windspeed_m_s",
    "climate_install_month_windspeed_m_s",
]
EXTRA_FEATURES = ["area", "num_turbines"]

FEATURE_COLS = WIND_DATA_FEATURES + WIND_CLIMATE_FEATURES + EXTRA_FEATURES

# ── Load & clean ──────────────────────────────────────────────────────────────

df = pd.read_csv(DATA_PATH)

# Drop bad labels
df = df[df[TARGET].notna() & (df[TARGET] > 0)].reset_index(drop=True)

# ── Feature engineering ───────────────────────────────────────────────────────

# Wind power ∝ v³ — much stronger signal than raw wind speed
df["wind_power_proxy"] = df["climate_annual_windspeed_m_s"] ** 3

# Turbine density: turbines per unit area (avoid div-by-zero)
df["turbine_density"] = df["num_turbines"] / df["area"].replace(0, np.nan)

# Capacity factor target: generation / (nameplate × 8760 h)
# Use this as an alternative target to remove farm-size confound
total_capacity_kw = df["t_cap"] * df["num_turbines"]        # kW
df["capacity_factor"] = df[TARGET] / (total_capacity_kw * 8.76)  # MWh → fraction

FEATURE_COLS = FEATURE_COLS + ["wind_power_proxy", "turbine_density"]

# ── Prepare X / y ─────────────────────────────────────────────────────────────

df[FEATURE_COLS] = df[FEATURE_COLS].astype(float)

# Log-transform the raw target to reduce skew (same as your neural net)
y_raw = np.log1p(df[TARGET].values)

X = df[FEATURE_COLS].values
y = y_raw

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=SEED
)

# Impute missing turbine specs with column medians
imputer = SimpleImputer(strategy="median")
X_train = imputer.fit_transform(X_train)
X_test  = imputer.transform(X_test)

# ── Model ─────────────────────────────────────────────────────────────────────

model = xgb.XGBRegressor(
    n_estimators      = 500,
    learning_rate     = 0.05,
    max_depth         = 6,
    subsample         = 0.8,
    colsample_bytree  = 0.8,
    min_child_weight  = 5,
    reg_alpha         = 0.1,   # L1
    reg_lambda        = 1.0,   # L2
    random_state      = SEED,
    n_jobs            = -1,
    early_stopping_rounds = 30,
    eval_metric       = "rmse",
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=50,
)

# ── Evaluate ──────────────────────────────────────────────────────────────────

y_pred = model.predict(X_test)

mse = mean_squared_error(y_test, y_pred)
r2  = r2_score(y_test, y_pred)

print(f"\n{'─'*40}")
print(f"Test MSE (log space): {mse:.4f}")
print(f"Test R²             : {r2:.4f}")
print(f"Best iteration      : {model.best_iteration}")
print(f"{'─'*40}\n")

# ── Feature importance ────────────────────────────────────────────────────────

importance = (
    pd.Series(model.feature_importances_, index=FEATURE_COLS)
    .sort_values(ascending=False)
)

print("Feature importances (gain):")
print(importance.to_string())

# ── Also run on capacity factor target for comparison ─────────────────────────

print(f"\n{'─'*40}")
print("Re-running on capacity_factor target (removes farm-size confound)...")
print(f"{'─'*40}\n")

cf_df = df[df["capacity_factor"].notna() & df["capacity_factor"].between(0, 1)].reset_index(drop=True)
y_cf  = cf_df["capacity_factor"].values
X_cf  = imputer.fit_transform(cf_df[FEATURE_COLS].astype(float).values)

X_cf_train, X_cf_test, y_cf_train, y_cf_test = train_test_split(
    X_cf, y_cf, test_size=0.2, random_state=SEED
)

cf_model = xgb.XGBRegressor(
    n_estimators          = 500,
    learning_rate         = 0.05,
    max_depth             = 6,
    subsample             = 0.8,
    colsample_bytree      = 0.8,
    min_child_weight      = 5,
    reg_alpha             = 0.1,
    reg_lambda            = 1.0,
    random_state          = SEED,
    n_jobs                = -1,
    early_stopping_rounds = 30,
    eval_metric           = "rmse",
)

cf_model.fit(
    X_cf_train, y_cf_train,
    eval_set=[(X_cf_test, y_cf_test)],
    verbose=50,
)

cf_pred = cf_model.predict(X_cf_test)
print(f"\nCapacity factor — Test R²: {r2_score(y_cf_test, cf_pred):.4f}")
print(f"Capacity factor — Test RMSE: {mean_squared_error(y_cf_test, cf_pred)**0.5:.4f}")
print("\nFeature importances (capacity factor target):")
print(
    pd.Series(cf_model.feature_importances_, index=FEATURE_COLS)
    .sort_values(ascending=False)
    .to_string()
)