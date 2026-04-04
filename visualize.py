import pandas as pd
import matplotlib.pyplot as plt
df = pd.read_csv("solar.csv")

plt.hist(df["p_cap_ac"]/df["p_area"],bins=100)
plt.show()
