import pandas as pd
import random
 
# Function to classify driving behavior
def classify_driver(row):
    crossed_params = 0
 
    if row["sharp_turns"] > 3:
        crossed_params += 1
    if row["hard_brakes"] > 3:
        crossed_params += 1
    if row["rapid_acceleration"] > 3:
        crossed_params += 1
    if row["wrong_indicator_usage"] > 2:
        crossed_params += 1
 
    if crossed_params <= 1:
        return "Safe (Green)"
    elif crossed_params == 2:
        return "Moderate (Yellow)"
    else:
        return "Rash (Red)"
 
# Generate synthetic dataset
data = []
for driver_id in range(1, 101):  # 100 drivers
    sharp_turns = random.randint(0, 10)
    hard_brakes = random.randint(0, 10)
    rapid_acceleration = random.randint(0, 10)
    wrong_indicator_usage = random.randint(0, 5)
 
    data.append([driver_id, sharp_turns, hard_brakes, rapid_acceleration, wrong_indicator_usage])
 
# Create dataframe
df = pd.DataFrame(data, columns=["driver_id", "sharp_turns", "hard_brakes", "rapid_acceleration", "wrong_indicator_usage"])
 
# Apply classification
df["driving_category"] = df.apply(classify_driver, axis=1)
 
# Save dataset
df.to_csv(r'c:\Users\Tanaya\Desktop\SIH\rash_driving.csv', index=False)
df.to_csv(r"c:\Users\Tanaya\Desktop\SIH\classified_drivers.csv", index=False)
 
print("✅ Dataset generated: 'rash_driving_data.csv'")
print("✅ Classified results saved: 'classified_drivers.csv'")
print(df.head(10))  # Show first 10 rows
 